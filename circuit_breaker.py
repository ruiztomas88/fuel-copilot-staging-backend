"""
Circuit Breaker and Error Handling Module

Implements resilient error handling patterns:
- Circuit Breaker: Prevents repeated calls to failing services
- Exponential Backoff: Intelligent retry with increasing delays
- Dead Letter Queue: Tracks consistently failing operations

Author: Fuel Copilot Team
Version: 1.0.0
Date: November 26, 2025
"""

import time
import logging
import functools
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, List, Any
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from collections import deque

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""

    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Failing, reject all calls
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker"""

    failure_threshold: int = 5  # Failures before opening
    success_threshold: int = 3  # Successes to close from half-open
    timeout_seconds: float = 60.0  # Time before trying half-open
    excluded_exceptions: tuple = ()  # Exceptions that don't count as failures


@dataclass
class CircuitStats:
    """Statistics for circuit breaker"""

    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    consecutive_failures: int = 0
    consecutive_successes: int = 0


class CircuitBreaker:
    """
    Circuit Breaker Pattern Implementation

    Prevents cascading failures by stopping calls to failing services.

    States:
    - CLOSED: Normal operation, calls pass through
    - OPEN: Service failing, all calls rejected immediately
    - HALF_OPEN: Testing recovery, limited calls allowed

    Usage:
        breaker = CircuitBreaker("mysql_connection")

        @breaker
        def query_database():
            ...

        # Or manually:
        if breaker.can_execute():
            try:
                result = risky_operation()
                breaker.record_success()
            except Exception as e:
                breaker.record_failure(e)
    """

    def __init__(self, name: str, config: CircuitBreakerConfig = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitStats()
        self._lock = Lock()
        self._last_state_change = datetime.now()

    def __call__(self, func: Callable) -> Callable:
        """Decorator usage"""

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return self.execute(func, *args, **kwargs)

        return wrapper

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with circuit breaker protection"""
        if not self.can_execute():
            self.stats.rejected_calls += 1
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' is OPEN. "
                f"Failures: {self.stats.consecutive_failures}"
            )

        self.stats.total_calls += 1

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except self.config.excluded_exceptions:
            # Don't count excluded exceptions as failures
            raise
        except Exception as e:
            self.record_failure(e)
            raise

    def can_execute(self) -> bool:
        """Check if circuit allows execution"""
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True

            if self.state == CircuitState.OPEN:
                # Check if timeout passed to try half-open
                elapsed = (datetime.now() - self._last_state_change).total_seconds()
                if elapsed >= self.config.timeout_seconds:
                    self._transition_to(CircuitState.HALF_OPEN)
                    return True
                return False

            if self.state == CircuitState.HALF_OPEN:
                return True

            return False

    def record_success(self):
        """Record successful call"""
        with self._lock:
            self.stats.successful_calls += 1
            self.stats.consecutive_successes += 1
            self.stats.consecutive_failures = 0
            self.stats.last_success_time = datetime.now()

            if self.state == CircuitState.HALF_OPEN:
                if self.stats.consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)
                    logger.info(f"🟢 Circuit '{self.name}' CLOSED (service recovered)")

    def record_failure(self, exception: Exception = None):
        """Record failed call"""
        with self._lock:
            self.stats.failed_calls += 1
            self.stats.consecutive_failures += 1
            self.stats.consecutive_successes = 0
            self.stats.last_failure_time = datetime.now()

            if self.state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)
                logger.warning(
                    f"🔴 Circuit '{self.name}' OPEN (failed during recovery): {exception}"
                )

            elif self.state == CircuitState.CLOSED:
                if self.stats.consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
                    logger.warning(
                        f"🔴 Circuit '{self.name}' OPEN after {self.stats.consecutive_failures} failures"
                    )

    def _transition_to(self, new_state: CircuitState):
        """Transition to new state"""
        old_state = self.state
        self.state = new_state
        self._last_state_change = datetime.now()

        if new_state == CircuitState.HALF_OPEN:
            self.stats.consecutive_successes = 0
            logger.info(f"🟡 Circuit '{self.name}' HALF_OPEN (testing recovery)")

    def reset(self):
        """Manually reset circuit breaker"""
        with self._lock:
            self.state = CircuitState.CLOSED
            self.stats = CircuitStats()
            self._last_state_change = datetime.now()
            logger.info(f"🔄 Circuit '{self.name}' manually reset")

    def get_status(self) -> Dict:
        """Get current status"""
        return {
            "name": self.name,
            "state": self.state.value,
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "rejected_calls": self.stats.rejected_calls,
                "consecutive_failures": self.stats.consecutive_failures,
            },
            "last_failure": (
                self.stats.last_failure_time.isoformat()
                if self.stats.last_failure_time
                else None
            ),
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""

    pass


@dataclass
class RetryConfig:
    """Configuration for retry with exponential backoff"""

    max_retries: int = 3
    base_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd


def retry_with_backoff(
    config: RetryConfig = None,
    on_retry: Callable[[int, Exception], None] = None,
):
    """
    Decorator for retry with exponential backoff

    Usage:
        @retry_with_backoff(RetryConfig(max_retries=5))
        def flaky_operation():
            ...
    """
    config = config or RetryConfig()

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(config.max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    if attempt == config.max_retries:
                        logger.error(
                            f"❌ {func.__name__} failed after {config.max_retries + 1} attempts: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay_seconds * (config.exponential_base**attempt),
                        config.max_delay_seconds,
                    )

                    # Add jitter (0-50% of delay)
                    if config.jitter:
                        import random

                        delay *= 1 + random.random() * 0.5

                    logger.warning(
                        f"⚠️ {func.__name__} attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    if on_retry:
                        on_retry(attempt + 1, e)

                    time.sleep(delay)

            raise last_exception

        return wrapper

    return decorator


@dataclass
class DeadLetterItem:
    """Item in dead letter queue"""

    truck_id: str
    operation: str
    error: str
    timestamp: datetime
    attempts: int
    data: Dict = field(default_factory=dict)


class DeadLetterQueue:
    """
    Dead Letter Queue for consistently failing operations

    Tracks operations that fail repeatedly for later investigation
    or manual retry.

    Usage:
        dlq = DeadLetterQueue(max_size=1000)

        try:
            process_truck(truck_data)
        except Exception as e:
            if truck_id in consistently_failing:
                dlq.add(truck_id, "process", str(e), {"data": truck_data})
    """

    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._queue: deque = deque(maxlen=max_size)
        self._failure_counts: Dict[str, int] = {}  # truck_id -> count
        self._lock = Lock()

    def add(
        self,
        truck_id: str,
        operation: str,
        error: str,
        data: Dict = None,
        attempts: int = 1,
    ):
        """Add item to dead letter queue"""
        with self._lock:
            item = DeadLetterItem(
                truck_id=truck_id,
                operation=operation,
                error=error,
                timestamp=datetime.now(),
                attempts=attempts,
                data=data or {},
            )
            self._queue.append(item)
            self._failure_counts[truck_id] = self._failure_counts.get(truck_id, 0) + 1

            logger.warning(
                f"📥 DLQ: Added {truck_id}/{operation} "
                f"(total failures: {self._failure_counts[truck_id]})"
            )

    def get_all(self) -> List[DeadLetterItem]:
        """Get all items in queue"""
        with self._lock:
            return list(self._queue)

    def get_by_truck(self, truck_id: str) -> List[DeadLetterItem]:
        """Get items for specific truck"""
        with self._lock:
            return [item for item in self._queue if item.truck_id == truck_id]

    def remove(self, truck_id: str, operation: str = None) -> int:
        """Remove items from queue (after successful retry)"""
        with self._lock:
            original_len = len(self._queue)

            if operation:
                self._queue = deque(
                    [
                        i
                        for i in self._queue
                        if not (i.truck_id == truck_id and i.operation == operation)
                    ],
                    maxlen=self.max_size,
                )
            else:
                self._queue = deque(
                    [i for i in self._queue if i.truck_id != truck_id],
                    maxlen=self.max_size,
                )

            removed = original_len - len(self._queue)
            if removed:
                logger.info(f"📤 DLQ: Removed {removed} items for {truck_id}")

            return removed

    def get_failure_count(self, truck_id: str) -> int:
        """Get failure count for truck"""
        return self._failure_counts.get(truck_id, 0)

    def get_problem_trucks(self, min_failures: int = 5) -> List[str]:
        """Get trucks with many failures"""
        return [
            truck_id
            for truck_id, count in self._failure_counts.items()
            if count >= min_failures
        ]

    def clear(self):
        """Clear entire queue"""
        with self._lock:
            self._queue.clear()
            self._failure_counts.clear()
            logger.info("🗑️ DLQ: Cleared all items")

    def get_stats(self) -> Dict:
        """Get queue statistics"""
        with self._lock:
            return {
                "size": len(self._queue),
                "max_size": self.max_size,
                "unique_trucks": len(self._failure_counts),
                "total_failures": sum(self._failure_counts.values()),
                "top_failures": sorted(
                    self._failure_counts.items(), key=lambda x: x[1], reverse=True
                )[:10],
            }


# Global instances for easy access
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_dead_letter_queue = DeadLetterQueue()


def get_circuit_breaker(
    name: str, config: CircuitBreakerConfig = None
) -> CircuitBreaker:
    """Get or create a circuit breaker by name"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


def get_dead_letter_queue() -> DeadLetterQueue:
    """Get global dead letter queue"""
    return _dead_letter_queue


# Convenience decorators for common use cases
def with_circuit_breaker(name: str, config: CircuitBreakerConfig = None):
    """Decorator to wrap function with circuit breaker"""
    return get_circuit_breaker(name, config)


def with_retry(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator with retry and exponential backoff"""
    return retry_with_backoff(
        RetryConfig(max_retries=max_retries, base_delay_seconds=base_delay)
    )


# Example usage showing all patterns together
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Circuit breaker example
    db_breaker = get_circuit_breaker(
        "database",
        CircuitBreakerConfig(
            failure_threshold=3,
            timeout_seconds=30,
        ),
    )

    @db_breaker
    @retry_with_backoff(RetryConfig(max_retries=2, base_delay_seconds=0.5))
    def query_database(query: str):
        """Example function with circuit breaker + retry"""
        import random

        if random.random() < 0.5:
            raise ConnectionError("Database unavailable")
        return f"Result for: {query}"

    # Test it
    dlq = get_dead_letter_queue()

    for i in range(10):
        try:
            result = query_database(f"SELECT * FROM trucks WHERE id = {i}")
            print(f"✅ {result}")
        except CircuitBreakerOpenError as e:
            print(f"🔴 Circuit open: {e}")
            dlq.add(f"truck_{i}", "query", str(e))
        except Exception as e:
            print(f"❌ Failed: {e}")
            dlq.add(f"truck_{i}", "query", str(e))

    print("\n📊 Circuit Status:", db_breaker.get_status())
    print("📊 DLQ Stats:", dlq.get_stats())
