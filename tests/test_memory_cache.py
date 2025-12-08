"""
Tests for Memory Cache (v4.0.0)
In-memory caching system with TTL support
"""

import pytest
import time
from unittest.mock import patch


class TestMemoryCacheBasics:
    """Test basic cache operations"""

    def test_cache_import(self):
        """Should be able to import memory cache"""
        from memory_cache import cache, cached, MemoryCache

        assert cache is not None
        assert cached is not None

    def test_cache_set_and_get(self):
        """Should set and retrieve values"""
        from memory_cache import cache

        # Set value
        cache.set("test_key", {"data": "value"}, ttl=60)

        # Get value
        result = cache.get("test_key")
        assert result == {"data": "value"}

    def test_cache_get_nonexistent_key(self):
        """Should return None for nonexistent keys"""
        from memory_cache import cache

        result = cache.get("nonexistent_key_12345")
        assert result is None

    def test_cache_ttl_expiration(self):
        """Should expire values after TTL"""
        from memory_cache import cache

        # Set with very short TTL
        cache.set("expiring_key", "value", ttl=1)

        # Should be available immediately
        assert cache.get("expiring_key") == "value"

        # Wait for expiration
        time.sleep(1.5)

        # Should be expired
        assert cache.get("expiring_key") is None

    def test_cache_overwrite(self):
        """Should overwrite existing values"""
        from memory_cache import cache

        cache.set("overwrite_key", "value1", ttl=60)
        cache.set("overwrite_key", "value2", ttl=60)

        assert cache.get("overwrite_key") == "value2"


class TestMemoryCacheDecorator:
    """Test @cached decorator"""

    def test_cached_decorator_basic(self):
        """Should cache function results"""
        from memory_cache import cached

        call_count = 0

        @cached(ttl_seconds=60)
        def expensive_function():
            nonlocal call_count
            call_count += 1
            return {"result": call_count}

        # First call - computes
        result1 = expensive_function()
        assert result1["result"] == 1

        # Second call - from cache
        result2 = expensive_function()
        assert result2["result"] == 1  # Same as first

        # Function only called once
        assert call_count == 1

    def test_cached_decorator_with_args(self):
        """Should cache based on arguments"""
        from memory_cache import cached

        call_count = 0

        @cached(ttl_seconds=60)
        def function_with_args(x, y):
            nonlocal call_count
            call_count += 1
            return x + y

        # Different args = different cache entries
        result1 = function_with_args(1, 2)
        result2 = function_with_args(3, 4)
        result3 = function_with_args(1, 2)  # Same as first

        assert result1 == 3
        assert result2 == 7
        assert result3 == 3
        assert call_count == 2  # Only 2 unique calls


class TestMemoryCacheStats:
    """Test cache statistics"""

    def test_cache_stats(self):
        """Should track hit/miss statistics"""
        from memory_cache import cache

        # Get initial stats
        stats = cache.get_stats()
        initial_hits = stats["hits"]
        initial_misses = stats["misses"]

        # Cache miss
        cache.get("nonexistent_stats_key")

        # Cache set + hit
        cache.set("stats_test_key", "value", ttl=60)
        cache.get("stats_test_key")

        # Check stats updated
        new_stats = cache.get_stats()
        assert new_stats["hits"] >= initial_hits + 1
        assert new_stats["misses"] >= initial_misses + 1


class TestMemoryCacheDelete:
    """Test cache deletion"""

    def test_cache_delete(self):
        """Should delete specific keys"""
        from memory_cache import cache

        cache.set("delete_test", "value", ttl=60)
        assert cache.get("delete_test") == "value"

        cache.delete("delete_test")
        assert cache.get("delete_test") is None

    def test_cache_clear(self):
        """Should clear all entries"""
        from memory_cache import cache

        # Set multiple values
        cache.set("clear_test_1", "value1", ttl=60)
        cache.set("clear_test_2", "value2", ttl=60)

        # Clear all
        cache.clear()

        # Both should be gone
        assert cache.get("clear_test_1") is None
        assert cache.get("clear_test_2") is None


class TestMemoryCacheThreadSafety:
    """Test thread safety"""

    def test_concurrent_access(self):
        """Should handle concurrent access"""
        import threading
        from memory_cache import cache

        errors = []

        def writer():
            try:
                for i in range(100):
                    cache.set(f"thread_test_{i}", i, ttl=60)
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for i in range(100):
                    cache.get(f"thread_test_{i}")
            except Exception as e:
                errors.append(e)

        # Run multiple threads
        threads = []
        for _ in range(5):
            threads.append(threading.Thread(target=writer))
            threads.append(threading.Thread(target=reader))

        for t in threads:
            t.start()

        for t in threads:
            t.join()

        # No errors should occur
        assert len(errors) == 0


class TestMemoryCacheIntegration:
    """Test integration with main app"""

    def test_memory_cache_available_in_main(self):
        """Memory cache should be available in main.py"""
        from main import MEMORY_CACHE_AVAILABLE, memory_cache

        assert MEMORY_CACHE_AVAILABLE is True
        assert memory_cache is not None

    def test_fleet_endpoint_uses_cache(self):
        """Fleet endpoint should use memory cache"""
        from fastapi.testclient import TestClient
        from main import app, memory_cache, MEMORY_CACHE_AVAILABLE

        if not MEMORY_CACHE_AVAILABLE:
            pytest.skip("Memory cache not available")

        client = TestClient(app)

        # Clear cache first
        memory_cache.clear()

        # First request - cache miss
        response1 = client.get("/fuelAnalytics/api/fleet")
        assert response1.status_code == 200

        # Second request - should be from cache (faster)
        response2 = client.get("/fuelAnalytics/api/fleet")
        assert response2.status_code == 200

        # Data should be consistent
        assert response1.json()["total_trucks"] == response2.json()["total_trucks"]
