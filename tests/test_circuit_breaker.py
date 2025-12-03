"""
Tests for Circuit Breaker and Error Handling Module

Run with: pytest tests/test_circuit_breaker.py -v
"""

import pytest
import time
import threading
from concurrent.futures import ThreadPoolExecutor
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerOpenError,
    RetryConfig,
    retry_with_backoff,
    DeadLetterQueue,
    DeadLetterItem,
    get_circuit_breaker,
    get_dead_letter_queue,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker class"""

    def test_initial_state_is_closed(self):
        """Circuit starts in CLOSED state"""
        breaker = CircuitBreaker("test")
        assert breaker.state == CircuitState.CLOSED

    def test_success_keeps_circuit_closed(self):
        """Successful calls keep circuit closed"""
        breaker = CircuitBreaker("test")

        @breaker
        def success():
            return "ok"

        for _ in range(10):
            result = success()
            assert result == "ok"

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.successful_calls == 10

    def test_failures_open_circuit(self):
        """Repeated failures open the circuit"""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker("test", config)

        @breaker
        def fail():
            raise ValueError("error")

        # Trigger threshold failures
        for _ in range(3):
            with pytest.raises(ValueError):
                fail()

        assert breaker.state == CircuitState.OPEN

    def test_open_circuit_rejects_calls(self):
        """Open circuit rejects all calls"""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)

        @breaker
        def fail():
            raise ValueError("error")

        # Open the circuit
        with pytest.raises(ValueError):
            fail()

        assert breaker.state == CircuitState.OPEN

        # Next call should be rejected
        with pytest.raises(CircuitBreakerOpenError):
            fail()

        assert breaker.stats.rejected_calls == 1

    def test_timeout_transitions_to_half_open(self):
        """After timeout, circuit goes to HALF_OPEN"""
        config = CircuitBreakerConfig(failure_threshold=1, timeout_seconds=0.1)
        breaker = CircuitBreaker("test", config)

        # Open the circuit
        breaker.record_failure(ValueError("test"))
        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(0.15)

        # Check should now allow (transition to half-open)
        assert breaker.can_execute()
        assert breaker.state == CircuitState.HALF_OPEN

    def test_success_in_half_open_closes_circuit(self):
        """Success in HALF_OPEN closes the circuit"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            timeout_seconds=0.1,
            success_threshold=2,
        )
        breaker = CircuitBreaker("test", config)

        # Open and wait for half-open
        breaker.record_failure(ValueError("test"))
        time.sleep(0.15)
        breaker.can_execute()  # Trigger half-open

        assert breaker.state == CircuitState.HALF_OPEN

        # Record successes
        breaker.record_success()
        breaker.record_success()

        assert breaker.state == CircuitState.CLOSED

    def test_failure_in_half_open_reopens_circuit(self):
        """Failure in HALF_OPEN reopens the circuit"""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            timeout_seconds=0.1,
        )
        breaker = CircuitBreaker("test", config)

        # Open and wait for half-open
        breaker.record_failure(ValueError("test"))
        time.sleep(0.15)
        breaker.can_execute()

        assert breaker.state == CircuitState.HALF_OPEN

        # Fail in half-open
        breaker.record_failure(ValueError("still failing"))

        assert breaker.state == CircuitState.OPEN

    def test_excluded_exceptions_dont_count(self):
        """Excluded exceptions don't count as failures"""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            excluded_exceptions=(ValueError,),
        )
        breaker = CircuitBreaker("test", config)

        @breaker
        def raise_value_error():
            raise ValueError("expected")

        # These shouldn't count as failures
        for _ in range(5):
            with pytest.raises(ValueError):
                raise_value_error()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.consecutive_failures == 0

    def test_reset_clears_state(self):
        """Manual reset clears all state"""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker("test", config)

        # Open circuit
        breaker.record_failure(ValueError("test"))
        assert breaker.state == CircuitState.OPEN

        # Reset
        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.consecutive_failures == 0
        assert breaker.stats.total_calls == 0

    def test_thread_safety(self):
        """Circuit breaker is thread-safe"""
        config = CircuitBreakerConfig(failure_threshold=100)
        breaker = CircuitBreaker("test", config)

        def record_both():
            for _ in range(50):
                breaker.record_success()
                breaker.record_failure(ValueError("test"))

        threads = [threading.Thread(target=record_both) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have all records (no race conditions)
        assert breaker.stats.successful_calls == 500
        assert breaker.stats.failed_calls == 500


class TestRetryWithBackoff:
    """Tests for retry_with_backoff decorator"""

    def test_success_no_retry(self):
        """Successful call doesn't retry"""
        call_count = 0

        @retry_with_backoff(RetryConfig(max_retries=3))
        def success():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = success()
        assert result == "ok"
        assert call_count == 1

    def test_retry_on_failure(self):
        """Retries on failure until success"""
        call_count = 0

        @retry_with_backoff(RetryConfig(max_retries=3, base_delay_seconds=0.01))
        def fail_twice():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "ok"

        result = fail_twice()
        assert result == "ok"
        assert call_count == 3

    def test_max_retries_exceeded(self):
        """Raises after max retries exceeded"""
        call_count = 0

        @retry_with_backoff(RetryConfig(max_retries=2, base_delay_seconds=0.01))
        def always_fail():
            nonlocal call_count
            call_count += 1
            raise ValueError("always fails")

        with pytest.raises(ValueError):
            always_fail()

        assert call_count == 3  # 1 initial + 2 retries

    def test_exponential_backoff(self):
        """Delays increase exponentially"""
        delays = []
        last_time = [time.time()]

        def on_retry(attempt, exc):
            now = time.time()
            delays.append(now - last_time[0])
            last_time[0] = now

        @retry_with_backoff(
            RetryConfig(
                max_retries=3,
                base_delay_seconds=0.1,
                exponential_base=2.0,
                jitter=False,
            ),
            on_retry=on_retry,
        )
        def always_fail():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            always_fail()

        # Delays should be approximately: 0.1, 0.2, 0.4
        assert len(delays) == 3
        assert delays[1] > delays[0]
        assert delays[2] > delays[1]


class TestDeadLetterQueue:
    """Tests for DeadLetterQueue"""

    def test_add_and_get(self):
        """Items can be added and retrieved"""
        dlq = DeadLetterQueue()

        dlq.add("TRUCK001", "process", "Connection error")
        dlq.add("TRUCK002", "save", "Disk full")

        items = dlq.get_all()
        assert len(items) == 2

    def test_get_by_truck(self):
        """Can filter by truck ID"""
        dlq = DeadLetterQueue()

        dlq.add("TRUCK001", "process", "Error 1")
        dlq.add("TRUCK001", "save", "Error 2")
        dlq.add("TRUCK002", "process", "Error 3")

        truck1_items = dlq.get_by_truck("TRUCK001")
        assert len(truck1_items) == 2
        assert all(i.truck_id == "TRUCK001" for i in truck1_items)

    def test_remove_by_truck(self):
        """Can remove items for a truck"""
        dlq = DeadLetterQueue()

        dlq.add("TRUCK001", "process", "Error 1")
        dlq.add("TRUCK001", "save", "Error 2")
        dlq.add("TRUCK002", "process", "Error 3")

        removed = dlq.remove("TRUCK001")

        assert removed == 2
        assert len(dlq.get_all()) == 1
        assert dlq.get_all()[0].truck_id == "TRUCK002"

    def test_max_size_enforced(self):
        """Queue respects max size"""
        dlq = DeadLetterQueue(max_size=5)

        for i in range(10):
            dlq.add(f"TRUCK{i:03d}", "process", f"Error {i}")

        assert len(dlq.get_all()) == 5
        # Oldest items should be gone
        truck_ids = [i.truck_id for i in dlq.get_all()]
        assert "TRUCK000" not in truck_ids
        assert "TRUCK009" in truck_ids

    def test_failure_counts(self):
        """Tracks failure counts per truck"""
        dlq = DeadLetterQueue()

        for _ in range(5):
            dlq.add("TRUCK001", "process", "Error")
        for _ in range(3):
            dlq.add("TRUCK002", "process", "Error")

        assert dlq.get_failure_count("TRUCK001") == 5
        assert dlq.get_failure_count("TRUCK002") == 3
        assert dlq.get_failure_count("TRUCK999") == 0

    def test_problem_trucks(self):
        """Can identify trucks with many failures"""
        dlq = DeadLetterQueue()

        for _ in range(10):
            dlq.add("BAD_TRUCK", "process", "Error")
        for _ in range(3):
            dlq.add("OK_TRUCK", "process", "Error")

        problem_trucks = dlq.get_problem_trucks(min_failures=5)

        assert "BAD_TRUCK" in problem_trucks
        assert "OK_TRUCK" not in problem_trucks

    def test_stats(self):
        """Statistics are accurate"""
        dlq = DeadLetterQueue()

        dlq.add("TRUCK001", "process", "Error 1")
        dlq.add("TRUCK001", "process", "Error 2")
        dlq.add("TRUCK002", "save", "Error 3")

        stats = dlq.get_stats()

        assert stats["size"] == 3
        assert stats["unique_trucks"] == 2
        assert stats["total_failures"] == 3


class TestGlobalInstances:
    """Tests for global circuit breaker and DLQ instances"""

    def test_get_circuit_breaker_creates_new(self):
        """get_circuit_breaker creates new instance if needed"""
        breaker1 = get_circuit_breaker("unique_name_1")
        breaker2 = get_circuit_breaker("unique_name_1")

        assert breaker1 is breaker2

    def test_get_circuit_breaker_with_config(self):
        """Can provide config when creating"""
        config = CircuitBreakerConfig(failure_threshold=10)
        breaker = get_circuit_breaker("unique_name_2", config)

        assert breaker.config.failure_threshold == 10


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
