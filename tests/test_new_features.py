"""
Integration Tests - New Features
=================================

Tests for all new features:
- Multi-layer cache
- WebSocket real-time
- ML theft detection
- Driver coaching

Date: December 26, 2025
"""

import asyncio
from datetime import datetime

import httpx
import pytest

BASE_URL = "http://localhost:8001/fuelAnalytics/api/v2"


class TestWebSocketEndpoints:
    """Test WebSocket functionality"""

    @pytest.mark.asyncio
    async def test_websocket_stats(self):
        """Test WebSocket stats endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/ws/stats")
            assert response.status_code == 200

            data = response.json()
            assert "total_connections" in data
            assert "truck_subscriptions" in data
            assert "fleet_monitors" in data
            assert isinstance(data["total_connections"], int)


class TestCachedEndpoints:
    """Test multi-layer caching"""

    @pytest.mark.asyncio
    async def test_cached_truck_sensors(self):
        """Test cached truck sensors endpoint"""
        async with httpx.AsyncClient() as client:
            truck_id = "FL0208"

            # First call - should fetch from "database"
            start = asyncio.get_event_loop().time()
            response1 = await client.get(f"{BASE_URL}/trucks/{truck_id}/sensors/cached")
            time1 = asyncio.get_event_loop().time() - start

            assert response1.status_code == 200
            data1 = response1.json()
            assert data1["truck_id"] == truck_id

            # Second call - should be cached (much faster)
            start = asyncio.get_event_loop().time()
            response2 = await client.get(f"{BASE_URL}/trucks/{truck_id}/sensors/cached")
            time2 = asyncio.get_event_loop().time() - start

            assert response2.status_code == 200
            data2 = response2.json()

            # Cached response should be significantly faster
            print(f"First call: {time1*1000:.2f}ms, Cached: {time2*1000:.2f}ms")
            # Note: In practice, cached should be <10ms vs ~50ms

    @pytest.mark.asyncio
    async def test_cached_fleet_summary(self):
        """Test cached fleet summary endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{BASE_URL}/fleet/summary/cached")

            assert response.status_code == 200
            data = response.json()
            assert "total_trucks" in data
            assert "active_trucks" in data
            assert "avg_mpg" in data


class TestMLTheftDetection:
    """Test ML-based fuel theft detection"""

    @pytest.mark.asyncio
    async def test_theft_detection_endpoint(self):
        """Test ML theft detection endpoint"""
        async with httpx.AsyncClient() as client:
            truck_id = "FL0208"
            response = await client.get(
                f"{BASE_URL}/trucks/{truck_id}/theft/ml", params={"hours": 24}
            )

            assert response.status_code == 200
            data = response.json()
            assert data["truck_id"] == truck_id
            assert "theft_events" in data
            assert "detection_method" in data
            assert data["detection_method"] == "machine_learning"
            assert "model_accuracy" in data

    @pytest.mark.asyncio
    async def test_ml_train_endpoint(self):
        """Test ML model training endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.post(f"{BASE_URL}/ml/train")

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert "model_type" in data
            assert data["model_type"] == "Isolation Forest"


class TestDriverCoaching:
    """Test driver coaching endpoints"""

    @pytest.mark.asyncio
    async def test_coaching_report(self):
        """Test driver coaching report endpoint"""
        async with httpx.AsyncClient() as client:
            truck_id = "FL0208"
            response = await client.get(
                f"{BASE_URL}/trucks/{truck_id}/coaching", params={"days": 30}
            )

            assert response.status_code == 200
            data = response.json()
            assert "overall_score" in data
            assert "behavior_category" in data
            assert "coaching_tips" in data
            assert "potential_monthly_savings" in data
            assert "strengths" in data
            assert "weaknesses" in data

            # Validate score range
            assert 0 <= data["overall_score"] <= 100

    @pytest.mark.asyncio
    async def test_driver_leaderboard(self):
        """Test driver leaderboard endpoint"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{BASE_URL}/fleet/coaching/leaderboard", params={"days": 30}
            )

            assert response.status_code == 200
            data = response.json()
            assert "leaderboard" in data
            assert "total_drivers" in data
            assert isinstance(data["leaderboard"], list)


class TestPerformance:
    """Performance tests for new features"""

    @pytest.mark.asyncio
    async def test_cache_performance_improvement(self):
        """Test that caching actually improves performance"""
        async with httpx.AsyncClient() as client:
            truck_id = "FL0208"

            times = []
            for i in range(5):
                start = asyncio.get_event_loop().time()
                await client.get(f"{BASE_URL}/trucks/{truck_id}/sensors/cached")
                elapsed = asyncio.get_event_loop().time() - start
                times.append(elapsed * 1000)  # Convert to ms

            # First call might be slow, subsequent should be fast
            avg_cached = sum(times[1:]) / len(times[1:])

            print(f"\\nCache performance:")
            print(f"  First call: {times[0]:.2f}ms")
            print(f"  Avg cached: {avg_cached:.2f}ms")

            # Cached calls should be faster
            assert avg_cached < times[0], "Cached calls should be faster"


# Run tests
if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
