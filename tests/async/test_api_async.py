"""
E2E Test Suite for Async API Endpoints
======================================

Tests all migrated async endpoints to ensure:
- Correct async/await usage
- No blocking I/O
- Connection pool efficiency
- Error handling
- Response times

Run with: pytest tests/async/test_api_async.py -v -s

Author: Fuel Copilot Team
Date: December 27, 2025
"""

import asyncio
import time

import pytest
from httpx import ASGITransport, AsyncClient

from main import app

# Configure pytest-asyncio
pytest_plugins = ("pytest_asyncio",)


@pytest.fixture(scope="function")
async def setup_database():
    """Setup and teardown database pool for each test"""
    from database_async import close_async_pool, get_async_pool

    # Initialize pool for this test by getting it
    try:
        await asyncio.wait_for(get_async_pool(), timeout=10.0)
    except asyncio.TimeoutError:
        pytest.skip("Database connection timeout - DB may not be available")
    except Exception as e:
        pytest.skip(f"Database initialization failed: {e}")

    yield

    # Clean up pool after test
    try:
        await close_async_pool()
    except Exception:
        pass  # Ignore cleanup errors


@pytest.fixture
async def client(setup_database):
    """Async HTTP client for testing"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
class TestAsyncEndpoints:
    """Test suite for async API endpoints"""

    async def test_truck_sensors_async(self, client):
        """Test /trucks/{truck_id}/sensors endpoint"""
        start = time.time()
        response = await client.get("/fuelAnalytics/api/v2/trucks/CO0681/sensors")
        elapsed = time.time() - start

        assert response.status_code == 200
        data = response.json()
        assert data["truck_id"] == "CO0681"
        assert "data_available" in data
        assert elapsed < 0.5, f"Response too slow: {elapsed:.3f}s"
        print(f"✅ Sensors endpoint: {elapsed*1000:.0f}ms")

    async def test_fleet_summary_async(self, client):
        """Test /fleet/summary endpoint"""
        start = time.time()
        response = await client.get("/fuelAnalytics/api/v2/fleet/summary")
        elapsed = time.time() - start

        assert response.status_code == 200
        data = response.json()
        assert "cost_per_mile" in data
        assert "active_trucks" in data
        assert "avg_mpg" in data
        assert elapsed < 0.5, f"Response too slow: {elapsed:.3f}s"
        print(f"✅ Fleet summary: {elapsed*1000:.0f}ms")

    async def test_concurrent_requests(self, client):
        """Test concurrent async requests (should not block)"""
        start = time.time()

        # Fire 10 concurrent requests
        tasks = [
            client.get("/fuelAnalytics/api/v2/trucks/CO0681/sensors") for _ in range(10)
        ]
        responses = await asyncio.gather(*tasks)

        elapsed = time.time() - start

        # All should succeed
        assert all(r.status_code == 200 for r in responses)

        # Should complete faster than sequential (10 * 50ms = 500ms)
        # With async, should be ~100-150ms
        assert elapsed < 0.3, f"Concurrent requests too slow: {elapsed:.3f}s"
        print(f"✅ 10 concurrent requests: {elapsed*1000:.0f}ms")

    async def test_error_handling(self, client):
        """Test error handling for invalid truck ID"""
        response = await client.get("/fuelAnalytics/api/v2/trucks/INVALID999/sensors")

        # Should return 200 with data_available=False (graceful handling)
        assert response.status_code == 200
        data = response.json()
        assert data["truck_id"] == "INVALID999"
        print("✅ Error handling works correctly")

    async def test_pool_not_exhausted(self, client):
        """Test that connection pool handles heavy load without exhaustion"""
        start = time.time()

        # Fire 50 concurrent requests (pool size is 20 max)
        tasks = [client.get("/fuelAnalytics/api/v2/fleet/summary") for _ in range(50)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start

        # Count successes
        successes = sum(
            1
            for r in responses
            if not isinstance(r, Exception) and r.status_code == 200
        )

        # Should handle all requests without errors
        assert successes == 50, f"Only {successes}/50 requests succeeded"
        assert elapsed < 2.0, f"Pool exhaustion suspected: {elapsed:.3f}s"
        print(f"✅ 50 concurrent requests: {elapsed*1000:.0f}ms ({successes}/50 OK)")


@pytest.mark.asyncio
class TestDatabasePool:
    """Test database connection pool functionality"""

    async def test_pool_initialization(self, setup_database):
        """Test that async DB pool initializes correctly"""
        from database_async import get_async_pool, get_pool_stats

        pool = await get_async_pool()
        assert pool is not None

        stats = await get_pool_stats()
        assert stats["size"] >= stats["minsize"]
        assert stats["size"] <= stats["maxsize"]
        assert stats["free"] >= 0
        print(f"✅ Pool stats: {stats}")

    async def test_health_check(self, setup_database):
        """Test database health check"""
        from database_async import health_check

        health = await health_check()
        assert health["healthy"] is True
        assert "server_time" in health
        assert "pool_stats" in health
        print(f"✅ DB health check passed")

    async def test_query_execution(self, setup_database):
        """Test basic query execution"""
        from database_async import execute_query_one

        result = await execute_query_one("SELECT 1 as test, NOW() as time")
        assert result["test"] == 1
        assert "time" in result
        print(f"✅ Query execution works")


@pytest.mark.asyncio
class TestPerformanceBenchmarks:
    """Performance regression tests"""

    async def test_sensor_endpoint_performance(self, client):
        """Ensure sensor endpoint stays under 100ms"""
        times = []

        for _ in range(10):
            start = time.time()
            await client.get("/fuelAnalytics/api/v2/trucks/CO0681/sensors")
            times.append(time.time() - start)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        assert avg_time < 0.1, f"Avg response time too high: {avg_time*1000:.0f}ms"
        assert max_time < 0.2, f"Max response time too high: {max_time*1000:.0f}ms"
        print(f"✅ Performance: avg={avg_time*1000:.0f}ms, max={max_time*1000:.0f}ms")

    async def test_no_n_plus_one(self, client):
        """Ensure no N+1 query problems"""
        # Test fleet summary (aggregates data from many trucks)
        start = time.time()
        await client.get("/fuelAnalytics/api/v2/fleet/summary")
        elapsed = time.time() - start

        # Should complete in one efficient query
        assert elapsed < 0.3, f"Possible N+1 query problem: {elapsed:.3f}s"
        print(f"✅ No N+1 queries detected: {elapsed*1000:.0f}ms")


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "-s", "--tb=short"])
