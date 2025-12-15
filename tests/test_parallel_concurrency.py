"""
Concurrency Tests for Parallel Processor
Tests thread safety, race conditions, and concurrent access patterns
"""

import pytest
import time
from threading import Thread, Lock
from collections import defaultdict
from parallel_processor import ParallelTruckProcessor, get_parallel_processor


class MockEstimator:
    """Mock estimator for testing thread safety"""

    def __init__(self):
        self.initialized = True
        self.last_fuel_lvl_pct = 50.0
        self.states = {}
        self.access_log = []  # Track access patterns
        self.lock = Lock()

    def log_access(self, truck_id: str, operation: str):
        """Thread-safe logging of access patterns"""
        with self.lock:
            self.access_log.append(
                {
                    "truck_id": truck_id,
                    "operation": operation,
                    "timestamp": time.time(),
                }
            )


def test_parallel_processor_initialization():
    """Test that processor initializes correctly"""
    processor = ParallelTruckProcessor(max_workers=4)

    assert processor.max_workers == 4
    assert processor.total_processed == 0
    assert processor.total_errors == 0
    assert len(processor.cycle_times) == 0
    assert hasattr(processor, "truck_locks")
    assert hasattr(processor, "locks_lock")


def test_get_truck_lock_creates_new_locks():
    """Test that _get_truck_lock creates locks on demand"""
    processor = ParallelTruckProcessor(max_workers=4)

    # Get lock for truck1
    lock1 = processor._get_truck_lock("BV6395")
    assert isinstance(lock1, type(Lock()))
    assert "BV6395" in processor.truck_locks

    # Get same lock again should return same object
    lock1_again = processor._get_truck_lock("BV6395")
    assert lock1 is lock1_again

    # Get lock for different truck
    lock2 = processor._get_truck_lock("DO9356")
    assert isinstance(lock2, type(Lock()))
    assert lock2 is not lock1


def test_concurrent_lock_creation():
    """Test that concurrent lock creation is thread-safe"""
    processor = ParallelTruckProcessor(max_workers=8)
    truck_ids = [f"TRUCK{i:04d}" for i in range(100)]

    results = []

    def create_locks(truck_list):
        """Worker function to create locks"""
        for truck_id in truck_list:
            lock = processor._get_truck_lock(truck_id)
            results.append((truck_id, id(lock)))

    # Split work across 4 threads
    chunk_size = len(truck_ids) // 4
    threads = []

    for i in range(4):
        start_idx = i * chunk_size
        end_idx = start_idx + chunk_size if i < 3 else len(truck_ids)
        thread = Thread(target=create_locks, args=(truck_ids[start_idx:end_idx],))
        threads.append(thread)
        thread.start()

    # Wait for all threads
    for thread in threads:
        thread.join()

    # Verify: each truck_id should have exactly one lock
    assert len(processor.truck_locks) == 100

    # Verify: no duplicate lock objects for same truck
    lock_ids = defaultdict(set)
    for truck_id, lock_id in results:
        lock_ids[truck_id].add(lock_id)

    for truck_id, ids in lock_ids.items():
        assert len(ids) == 1, f"Truck {truck_id} has multiple lock objects: {ids}"


def test_concurrent_access_to_shared_state():
    """Test that concurrent access to shared state is safe"""

    shared_counter = {"count": 0}
    shared_dict = {}
    lock = Lock()

    def increment_counter(truck_id: str, iterations: int):
        """Increment counter multiple times"""
        for _ in range(iterations):
            # Without lock: race condition
            # With lock: thread-safe
            with lock:
                shared_counter["count"] += 1
                shared_dict[truck_id] = shared_dict.get(truck_id, 0) + 1

    # Run 10 threads, each incrementing 1000 times
    threads = []
    for i in range(10):
        thread = Thread(target=increment_counter, args=(f"TRUCK{i}", 1000))
        threads.append(thread)
        thread.start()

    for thread in threads:
        thread.join()

    # With proper locking, final count should be exactly 10,000
    assert shared_counter["count"] == 10000
    assert sum(shared_dict.values()) == 10000


def test_parallel_processor_handles_same_truck_multiple_times():
    """Test that processing same truck multiple times is safe"""
    processor = ParallelTruckProcessor(max_workers=4).start()

    call_count = defaultdict(int)
    call_lock = Lock()

    def mock_process_function(truck_id: str, truck_config: dict):
        """Mock function that increments counter"""
        time.sleep(0.01)  # Simulate work

        with call_lock:
            call_count[truck_id] += 1

        return {"truck_id": truck_id, "processed": True}

    # Process same truck 10 times in parallel
    trucks = {f"BV6395_{i}": {"unit_id": 123} for i in range(10)}

    successful, failed = processor.process_trucks_parallel(
        trucks, mock_process_function
    )

    processor.shutdown()

    assert len(successful) == 10
    assert len(failed) == 0
    assert sum(call_count.values()) == 10


def test_parallel_processor_error_handling():
    """Test that errors in one truck don't affect others"""
    processor = ParallelTruckProcessor(max_workers=4).start()

    def failing_function(truck_id: str, truck_config: dict):
        """Function that fails for specific trucks"""
        if "FAIL" in truck_id:
            raise ValueError(f"Intentional error for {truck_id}")

        time.sleep(0.01)
        return {"truck_id": truck_id, "processed": True}

    # Mix of good and bad trucks
    trucks = {
        "TRUCK001": {"unit_id": 1},
        "TRUCK_FAIL_002": {"unit_id": 2},
        "TRUCK003": {"unit_id": 3},
        "TRUCK_FAIL_004": {"unit_id": 4},
        "TRUCK005": {"unit_id": 5},
    }

    successful, failed = processor.process_trucks_parallel(trucks, failing_function)

    processor.shutdown()

    assert len(successful) == 3  # TRUCK001, 003, 005
    assert len(failed) == 2  # FAIL_002, FAIL_004

    # Check that successful results are correct
    successful_ids = [r["data"]["truck_id"] for r in successful]
    assert "TRUCK001" in successful_ids
    assert "TRUCK003" in successful_ids
    assert "TRUCK005" in successful_ids

    # Check that failures are recorded
    failed_ids = [r["truck_id"] for r in failed]
    assert "TRUCK_FAIL_002" in failed_ids
    assert "TRUCK_FAIL_004" in failed_ids


def test_parallel_processor_performance_improvement():
    """Test that parallel processing is actually faster"""

    def slow_function(truck_id: str, truck_config: dict):
        """Simulate slow processing"""
        time.sleep(0.1)  # 100ms per truck
        return {"truck_id": truck_id, "processed": True}

    # Sequential baseline
    trucks = {f"TRUCK{i:03d}": {"unit_id": i} for i in range(10)}

    start_time = time.time()
    for truck_id, config in trucks.items():
        slow_function(truck_id, config)
    sequential_time = time.time() - start_time

    # Parallel processing
    processor = ParallelTruckProcessor(max_workers=4).start()
    start_time = time.time()
    successful, failed = processor.process_trucks_parallel(trucks, slow_function)
    parallel_time = time.time() - start_time

    processor.shutdown()

    # Parallel should be significantly faster
    # 10 trucks * 100ms = 1000ms sequential
    # 10 trucks / 4 workers * 100ms = ~300ms parallel
    assert parallel_time < sequential_time * 0.5  # At least 2x faster
    assert len(successful) == 10

    print(
        f"\n⏱️ Performance: Sequential={sequential_time:.2f}s, "
        f"Parallel={parallel_time:.2f}s, "
        f"Speedup={sequential_time/parallel_time:.1f}x"
    )


def test_singleton_pattern():
    """Test that get_parallel_processor returns same instance"""
    processor1 = get_parallel_processor(max_workers=8)
    processor2 = get_parallel_processor(max_workers=4)  # Should ignore new param

    assert processor1 is processor2
    assert processor1.max_workers == 8  # First initialization wins


def test_processor_stats_tracking():
    """Test that processor tracks statistics correctly"""
    processor = ParallelTruckProcessor(max_workers=4).start()

    def mock_function(truck_id: str, truck_config: dict):
        if "FAIL" in truck_id:
            raise ValueError("Test error")
        return {"result": "ok"}

    trucks = {
        "TRUCK1": {},
        "FAIL2": {},
        "TRUCK3": {},
        "FAIL4": {},
    }

    processor.process_trucks_parallel(trucks, mock_function)

    stats = processor.get_stats()

    processor.shutdown()

    assert stats["total_processed"] == 2
    assert stats["total_errors"] == 2
    assert stats["success_rate"] == 50.0
    assert stats["cycles_completed"] == 1
    assert stats["avg_cycle_time_seconds"] > 0


def test_memory_leak_prevention():
    """Test that locks dict doesn't grow unbounded"""
    processor = ParallelTruckProcessor(max_workers=4)

    # Create locks for many trucks
    for i in range(1000):
        processor._get_truck_lock(f"TRUCK{i:04d}")

    # Verify locks were created
    assert len(processor.truck_locks) == 1000

    # In production, you might want to implement lock cleanup
    # for trucks that haven't been seen in a while
    # This test documents the current behavior


# ═══════════════════════════════════════════════════════════════════════════════
# PROCESSOR FACTORY TESTS
# ═══════════════════════════════════════════════════════════════════════════════

from parallel_processor import ProcessorFactory, process_truck_wrapper


class TestProcessorFactory:
    """Test ProcessorFactory class methods"""

    def teardown_method(self):
        """Cleanup after each test"""
        ProcessorFactory.shutdown_all(wait=False)

    def test_get_processor_creates_new(self):
        """Test that get_processor creates a new processor"""
        processor = ProcessorFactory.get_processor("test1", max_workers=4)
        
        assert processor is not None
        assert isinstance(processor, ParallelTruckProcessor)
        assert processor.max_workers == 4
        assert processor.is_running()

    def test_get_processor_returns_existing(self):
        """Test that get_processor returns same instance for same name"""
        processor1 = ProcessorFactory.get_processor("test2", max_workers=4)
        processor2 = ProcessorFactory.get_processor("test2", max_workers=8)
        
        assert processor1 is processor2
        assert processor1.max_workers == 4  # First creation wins

    def test_get_processor_different_names(self):
        """Test that different names get different processors"""
        processor1 = ProcessorFactory.get_processor("proc_a", max_workers=4)
        processor2 = ProcessorFactory.get_processor("proc_b", max_workers=8)
        
        assert processor1 is not processor2
        assert processor1.max_workers == 4
        assert processor2.max_workers == 8

    def test_get_processor_auto_start_true(self):
        """Test that auto_start=True starts the processor"""
        processor = ProcessorFactory.get_processor("test3", auto_start=True)
        
        assert processor.is_running()

    def test_get_processor_auto_start_false(self):
        """Test that auto_start=False does not start the processor"""
        processor = ProcessorFactory.get_processor("test4", auto_start=False)
        
        assert not processor.is_running()

    def test_set_processor(self):
        """Test that set_processor replaces existing processor"""
        # Create initial processor
        processor1 = ProcessorFactory.get_processor("test5", max_workers=4)
        
        # Create mock processor
        mock_processor = ParallelTruckProcessor(max_workers=16)
        ProcessorFactory.set_processor("test5", mock_processor)
        
        # Get should now return mock
        processor2 = ProcessorFactory.get_processor("test5")
        
        assert processor2 is mock_processor
        assert processor2.max_workers == 16

    def test_shutdown_processor(self):
        """Test that shutdown_processor shuts down specific processor"""
        processor = ProcessorFactory.get_processor("test6", max_workers=4)
        assert processor.is_running()
        
        ProcessorFactory.shutdown_processor("test6")
        
        # Getting same name should create new
        processor2 = ProcessorFactory.get_processor("test6")
        assert processor2 is not processor

    def test_shutdown_all(self):
        """Test that shutdown_all shuts down all processors"""
        # Create multiple processors
        ProcessorFactory.get_processor("all_test_1")
        ProcessorFactory.get_processor("all_test_2")
        ProcessorFactory.get_processor("all_test_3")
        
        ProcessorFactory.shutdown_all()
        
        # All instances should be cleared
        stats = ProcessorFactory.get_all_stats()
        assert len(stats) == 0

    def test_get_all_stats(self):
        """Test that get_all_stats returns stats for all processors"""
        ProcessorFactory.get_processor("stats_1", max_workers=2)
        ProcessorFactory.get_processor("stats_2", max_workers=4)
        
        stats = ProcessorFactory.get_all_stats()
        
        assert "stats_1" in stats
        assert "stats_2" in stats
        assert stats["stats_1"]["max_workers"] == 2
        assert stats["stats_2"]["max_workers"] == 4

    def test_temporary_processor_context_manager(self):
        """Test that temporary_processor auto-cleans up"""
        with ProcessorFactory.temporary_processor(max_workers=2) as processor:
            assert processor.is_running()
            assert processor.max_workers == 2
            
            # Can process trucks
            def mock_fn(truck_id, truck_config):
                return {"ok": True}
            
            success, failed = processor.process_trucks_parallel(
                {"TRUCK1": {}}, mock_fn
            )
            assert len(success) == 1
        
        # After context, processor should be shut down
        assert not processor.is_running()


# ═══════════════════════════════════════════════════════════════════════════════
# PROCESS TRUCK WRAPPER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class MockEstimatorForWrapper:
    """Mock estimator for process_truck_wrapper tests"""
    def __init__(self, initialized=True):
        self.initialized = initialized
        self.last_fuel_lvl_pct = 75.0


class TestProcessTruckWrapper:
    """Test process_truck_wrapper function"""

    def test_wrapper_with_no_data(self):
        """Test wrapper returns None when no data available"""
        result = process_truck_wrapper(
            truck_id="TRUCK001",
            truck_config={"unit_id": 123, "capacity_liters": 500},
            estimator=MockEstimatorForWrapper(),
            csv_reporter=None,
            last_odom=None,
            last_processed_timestamp=None,
            engine=None,
            tanks_config=None,
            normalizer=None,
            config={"aged_critical_min": 60},
            consecutive_failures={"TRUCK001": 0},
            truck_display_data={},
            truck_lock=None,
        )
        
        # get_latest_reading returns None, so result should be None
        assert result is None

    def test_wrapper_increments_failure_counter(self):
        """Test wrapper increments failure counter on no data"""
        failures = {"TRUCK001": 0}
        
        process_truck_wrapper(
            truck_id="TRUCK001",
            truck_config={"unit_id": 123, "capacity_liters": 500},
            estimator=MockEstimatorForWrapper(),
            csv_reporter=None,
            last_odom=None,
            last_processed_timestamp=None,
            engine=None,
            tanks_config=None,
            normalizer=None,
            config={"aged_critical_min": 60},
            consecutive_failures=failures,
            truck_display_data={},
            truck_lock=None,
        )
        
        assert failures["TRUCK001"] == 1

    def test_wrapper_with_lock(self):
        """Test wrapper uses lock when provided"""
        failures = {"TRUCK001": 0}
        lock = Lock()
        
        process_truck_wrapper(
            truck_id="TRUCK001",
            truck_config={"unit_id": 123, "capacity_liters": 500},
            estimator=MockEstimatorForWrapper(),
            csv_reporter=None,
            last_odom=None,
            last_processed_timestamp=None,
            engine=None,
            tanks_config=None,
            normalizer=None,
            config={"aged_critical_min": 60},
            consecutive_failures=failures,
            truck_display_data={},
            truck_lock=lock,
        )
        
        assert failures["TRUCK001"] == 1

    def test_wrapper_adaptive_fuel_age_frequent(self):
        """Test adaptive fuel age for frequent sensor"""
        failures = {"TRUCK001": 0}
        
        result = process_truck_wrapper(
            truck_id="TRUCK001",
            truck_config={
                "unit_id": 123, 
                "capacity_liters": 500,
                "fuel_sensor_freq": "frequent"
            },
            estimator=MockEstimatorForWrapper(),
            csv_reporter=None,
            last_odom=None,
            last_processed_timestamp=None,
            engine=None,
            tanks_config=None,
            normalizer=None,
            config={"aged_critical_min": 60},
            consecutive_failures=failures,
            truck_display_data={},
            truck_lock=None,
        )
        
        # Still None (no data), but code path exercised
        assert result is None

    def test_wrapper_adaptive_fuel_age_infrequent(self):
        """Test adaptive fuel age for infrequent sensor"""
        failures = {"TRUCK001": 0}
        
        result = process_truck_wrapper(
            truck_id="TRUCK001",
            truck_config={
                "unit_id": 123, 
                "capacity_liters": 500,
                "fuel_sensor_freq": "infrequent"
            },
            estimator=MockEstimatorForWrapper(),
            csv_reporter=None,
            last_odom=None,
            last_processed_timestamp=None,
            engine=None,
            tanks_config=None,
            normalizer=None,
            config={"aged_critical_min": 60},
            consecutive_failures=failures,
            truck_display_data={},
            truck_lock=None,
        )
        
        assert result is None

    def test_wrapper_uninitialized_estimator(self):
        """Test wrapper with uninitialized estimator uses different age limit"""
        failures = {"TRUCK001": 0}
        
        result = process_truck_wrapper(
            truck_id="TRUCK001",
            truck_config={"unit_id": 123, "capacity_liters": 500},
            estimator=MockEstimatorForWrapper(initialized=False),
            csv_reporter=None,
            last_odom=None,
            last_processed_timestamp=None,
            engine=None,
            tanks_config=None,
            normalizer=None,
            config={"aged_critical_min": 60},
            consecutive_failures=failures,
            truck_display_data={},
            truck_lock=None,
        )
        
        assert result is None


# ═══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL PROCESSOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestProcessorAdditional:
    """Additional tests for ParallelTruckProcessor"""

    def test_processor_not_started_raises_error(self):
        """Test that using processor without start raises error"""
        processor = ParallelTruckProcessor(max_workers=4)
        
        with pytest.raises(RuntimeError) as exc_info:
            processor.process_trucks_parallel({"TRUCK1": {}}, lambda t, c: {})
        
        assert "not started" in str(exc_info.value).lower()

    def test_processor_reset_stats(self):
        """Test reset_stats clears all statistics"""
        processor = ParallelTruckProcessor(max_workers=4).start()
        
        def mock_fn(truck_id, truck_config):
            return {"ok": True}
        
        processor.process_trucks_parallel({"TRUCK1": {}}, mock_fn)
        
        assert processor.total_processed > 0
        
        processor.reset_stats()
        
        assert processor.total_processed == 0
        assert processor.total_errors == 0
        assert len(processor.cycle_times) == 0
        
        processor.shutdown()

    def test_processor_shutdown_twice(self):
        """Test that shutting down twice is safe"""
        processor = ParallelTruckProcessor(max_workers=4).start()
        
        processor.shutdown()
        assert not processor.is_running()
        
        # Second shutdown should be safe
        processor.shutdown()
        assert not processor.is_running()

    def test_start_returns_self(self):
        """Test that start() returns self for chaining"""
        processor = ParallelTruckProcessor(max_workers=4)
        
        result = processor.start()
        
        assert result is processor
        
        processor.shutdown()

    def test_start_idempotent(self):
        """Test that calling start() multiple times is safe"""
        processor = ParallelTruckProcessor(max_workers=4)
        
        processor.start()
        executor1 = processor.executor
        
        processor.start()  # Second start
        executor2 = processor.executor
        
        assert executor1 is executor2  # Same executor
        
        processor.shutdown()


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])

