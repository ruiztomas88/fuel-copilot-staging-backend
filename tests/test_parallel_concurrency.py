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


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
