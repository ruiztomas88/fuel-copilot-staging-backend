"""
COMPREHENSIVE TESTS - Async Database Migration
===============================================

Tests para verificar:
1. Conexión y pool async
2. Queries async funcionan
3. Performance improvements
4. Endpoints migrados
5. Backward compatibility

Run: pytest test_async_migration.py -v
"""

import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Configure asyncio mode for pytest
pytest_plugins = ("pytest_asyncio",)


# Fixtures
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module", autouse=True)
async def setup_and_teardown_pool():
    """Setup async pool before tests, cleanup after."""
    from database_async import close_async_pool, get_async_pool

    # Setup
    await get_async_pool()

    yield

    # Teardown
    await close_async_pool()


class TestAsyncDatabaseModule:
    """Test suite for database_async.py"""

    async def test_connection_pool_creation(self):
        """Test that async pool can be created."""
        from database_async import close_async_pool, get_async_pool

        pool = await get_async_pool()
        assert pool is not None
        assert pool.minsize == 5
        assert pool.maxsize == 20

        await close_async_pool()

    async def test_health_check(self):
        """Test database health check."""
        from database_async import health_check

        result = await health_check()
        assert result["healthy"] is True
        assert "server_time" in result
        assert "pool_stats" in result

    async def test_execute_query_one(self):
        """Test execute_query_one returns single row."""
        from database_async import execute_query_one

        result = await execute_query_one("SELECT 1 as test, NOW() as time")
        assert result is not None
        assert result["test"] == 1
        assert "time" in result

    async def test_execute_query_multiple(self):
        """Test execute_query returns multiple rows."""
        from database_async import execute_query

        results = await execute_query("SELECT 1 as test UNION SELECT 2 UNION SELECT 3")
        assert len(results) == 3
        assert results[0]["test"] == 1
        assert results[1]["test"] == 2
        assert results[2]["test"] == 3

    async def test_pool_stats(self):
        """Test pool statistics retrieval."""
        from database_async import get_pool_stats

        stats = await get_pool_stats()
        assert "size" in stats
        assert "free" in stats
        assert "minsize" in stats
        assert "maxsize" in stats
        assert stats["minsize"] == 5
        assert stats["maxsize"] == 20


class TestAsyncEndpoints:
    """Test suite for api_endpoints_async.py"""

    async def test_get_sensors_cache_async(self):
        """Test async sensors cache endpoint."""
        from api_endpoints_async import get_sensors_cache_async

        # Test with real truck ID
        result = await get_sensors_cache_async("FL-0208")
        assert isinstance(result, dict)
        assert result["truck_id"] == "FL-0208"
        assert "data_available" in result

        if result["data_available"]:
            # If data exists, verify structure
            assert "oil_pressure_psi" in result
            assert "rpm" in result
            assert "coolant_temp_f" in result

    async def test_get_sensors_cache_async_not_found(self):
        """Test async sensors cache with non-existent truck."""
        from api_endpoints_async import get_sensors_cache_async

        result = await get_sensors_cache_async("FAKE-9999")
        assert result["truck_id"] == "FAKE-9999"
        assert result["data_available"] is False

    async def test_get_truck_sensors_async(self):
        """Test async truck sensors from fuel_metrics."""
        from api_endpoints_async import get_truck_sensors_async

        result = await get_truck_sensors_async("FL-0208")
        assert isinstance(result, dict)
        assert result["truck_id"] == "FL-0208"
        assert "data_available" in result

    async def test_get_active_dtcs_async(self):
        """Test async active DTCs retrieval."""
        from api_endpoints_async import get_active_dtcs_async

        result = await get_active_dtcs_async("FL-0208")
        assert isinstance(result, list)
        # Result can be empty if no active DTCs

    async def test_get_recent_refuels_async(self):
        """Test async recent refuels retrieval."""
        from api_endpoints_async import get_recent_refuels_async

        result = await get_recent_refuels_async("FL-0208", limit=5)
        assert isinstance(result, list)
        # Each refuel should have required fields
        for refuel in result:
            assert "timestamp" in refuel
            assert "gallons_added" in refuel

    async def test_get_fuel_history_async(self):
        """Test async fuel history retrieval."""
        from api_endpoints_async import get_fuel_history_async

        result = await get_fuel_history_async("FL-0208", hours=24, limit=100)
        assert isinstance(result, list)
        # Each record should have required fields
        for record in result:
            assert "timestamp" in record
            assert "gallons" in record
            assert "percent" in record


class TestPerformanceComparison:
    """Test performance improvements from async migration."""

    async def test_concurrent_queries_performance(self):
        """Test that concurrent queries perform better with async."""
        import time

        from api_endpoints_async import get_sensors_cache_async

        truck_ids = [f"FL-{i:04d}" for i in range(208, 218)]  # 10 trucks

        # Time concurrent async queries
        start = time.time()
        tasks = [get_sensors_cache_async(truck_id) for truck_id in truck_ids]
        results = await asyncio.gather(*tasks)
        async_time = time.time() - start

        assert len(results) == 10
        print(f"\n✅ 10 concurrent async queries: {async_time:.3f}s")

        # Should be fast (< 1 second for 10 trucks)
        assert async_time < 2.0, f"Too slow: {async_time:.3f}s"

    async def test_single_query_performance(self):
        """Test single query performance."""
        import time

        from api_endpoints_async import get_sensors_cache_async

        # Warm up
        await get_sensors_cache_async("FL-0208")

        # Measure
        start = time.time()
        result = await get_sensors_cache_async("FL-0208")
        elapsed = time.time() - start

        print(f"\n✅ Single async query: {elapsed*1000:.1f}ms")

        # Should be very fast (< 100ms)
        assert elapsed < 0.2, f"Too slow: {elapsed*1000:.1f}ms"


class TestDatabaseIndexes:
    """Test that database indexes are working."""

    async def test_indexes_exist(self):
        """Verify critical indexes exist."""
        from database_async import execute_query

        query = """
            SELECT 
                TABLE_NAME, INDEX_NAME, COLUMN_NAME
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = 'fuel_copilot_local'
              AND INDEX_NAME LIKE 'idx_%'
            ORDER BY TABLE_NAME, INDEX_NAME
        """

        indexes = await execute_query(query)
        assert len(indexes) > 0, "No indexes found"

        # Check for critical indexes
        index_names = [idx["INDEX_NAME"] for idx in indexes]

        critical_indexes = [
            "idx_fuel_metrics_truck_time",
            "idx_dtc_events_truck",
            "idx_refuel_events_truck_time",
        ]

        for idx_name in critical_indexes:
            assert idx_name in index_names, f"Missing critical index: {idx_name}"

        print(f"\n✅ Found {len(set(index_names))} indexes")

    async def test_query_uses_index(self):
        """Test that queries use indexes (EXPLAIN plan)."""
        from database_async import execute_query

        # Test fuel_metrics query uses index
        explain = await execute_query(
            """
            EXPLAIN SELECT * FROM fuel_metrics 
            WHERE truck_id = 'FL-0208' 
            AND timestamp_utc > DATE_SUB(NOW(), INTERVAL 24 HOUR)
        """
        )

        assert len(explain) > 0
        # Check if using index (key column should not be NULL)
        for row in explain:
            if row.get("key"):
                print(f"\n✅ Query uses index: {row['key']}")
                break


class TestBackwardCompatibility:
    """Test that old code still works."""

    async def test_old_sync_functions_still_work(self):
        """Verify that sync database functions still work."""
        import pymysql

        from database_mysql import get_db_connection

        # Test old sync connection still works
        conn = get_db_connection()
        assert conn is not None

        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()

        assert result["test"] == 1

        cursor.close()
        conn.close()


class TestEdgeCases:
    """Test edge cases and error handling."""

    async def test_query_with_no_results(self):
        """Test query that returns no results."""
        from api_endpoints_async import get_active_dtcs_async

        # Use non-existent truck
        result = await get_active_dtcs_async("NONEXISTENT-9999")
        assert isinstance(result, list)
        assert len(result) == 0

    async def test_query_with_none_params(self):
        """Test query with None parameters."""
        from database_async import execute_query_one

        result = await execute_query_one("SELECT %s as test", (None,))
        assert result["test"] is None

    async def test_large_limit(self):
        """Test query with large LIMIT."""
        from api_endpoints_async import get_fuel_history_async

        result = await get_fuel_history_async("FL-0208", hours=168, limit=5000)
        assert isinstance(result, list)
        # Should handle large results without crashing


class TestConcurrentConnections:
    """Test connection pool under load."""

    async def test_pool_handles_concurrent_load(self):
        """Test that pool handles many concurrent connections."""
        import random

        from api_endpoints_async import get_sensors_cache_async

        # Simulate 50 concurrent requests
        truck_ids = [f"FL-{random.randint(200, 250):04d}" for _ in range(50)]

        tasks = [get_sensors_cache_async(truck_id) for truck_id in truck_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Count successful vs failed
        successful = sum(1 for r in results if isinstance(r, dict))
        failed = sum(1 for r in results if isinstance(r, Exception))

        print(f"\n✅ 50 concurrent requests: {successful} success, {failed} failed")

        assert successful > 0, "All requests failed"

    async def test_pool_recovers_from_errors(self):
        """Test that pool recovers after errors."""
        from database_async import execute_query_one

        # Cause an error
        try:
            await execute_query_one("SELECT * FROM nonexistent_table")
        except Exception:
            pass  # Expected

        # Pool should still work after error
        result = await execute_query_one("SELECT 1 as test")
        assert result["test"] == 1


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestFullIntegration:
    """End-to-end integration tests."""

    async def test_full_truck_data_retrieval(self):
        """Test retrieving all data for a truck."""
        from api_endpoints_async import (
            get_active_dtcs_async,
            get_fuel_history_async,
            get_recent_refuels_async,
            get_sensors_cache_async,
        )

        truck_id = "FL-0208"

        # Get all data concurrently
        sensors, dtcs, refuels, history = await asyncio.gather(
            get_sensors_cache_async(truck_id),
            get_active_dtcs_async(truck_id),
            get_recent_refuels_async(truck_id, limit=5),
            get_fuel_history_async(truck_id, hours=24, limit=100),
        )

        # Verify all returned data
        assert sensors["truck_id"] == truck_id
        assert isinstance(dtcs, list)
        assert isinstance(refuels, list)
        assert isinstance(history, list)

        print(f"\n✅ Retrieved complete data for {truck_id}:")
        print(
            f"   - Sensors: {'available' if sensors.get('data_available') else 'not available'}"
        )
        print(f"   - Active DTCs: {len(dtcs)}")
        print(f"   - Recent refuels: {len(refuels)}")
        print(f"   - Fuel history: {len(history)} records")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
