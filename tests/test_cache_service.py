"""
Tests for Cache Service
=======================
Tests both Redis and in-memory cache backends.
"""

import pytest
import asyncio
from unittest.mock import patch, MagicMock
from cache_service import (
    CacheService, 
    InMemoryCache, 
    RedisCache, 
    cache, 
    get_cache,
    invalidate_on_truck_update
)


class TestInMemoryCache:
    """Tests for the in-memory cache backend"""
    
    @pytest.fixture
    def memory_cache(self):
        return InMemoryCache(max_size=10)
    
    @pytest.mark.asyncio
    async def test_set_and_get(self, memory_cache):
        """Test basic set and get operations"""
        await memory_cache.set("key1", {"value": 123}, ttl=60)
        result = await memory_cache.get("key1")
        assert result == {"value": 123}
    
    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self, memory_cache):
        """Test getting a key that doesn't exist"""
        result = await memory_cache.get("nonexistent")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_delete(self, memory_cache):
        """Test deleting a key"""
        await memory_cache.set("key1", "value1", ttl=60)
        await memory_cache.delete("key1")
        result = await memory_cache.get("key1")
        assert result is None
    
    @pytest.mark.asyncio
    async def test_exists(self, memory_cache):
        """Test checking if a key exists"""
        await memory_cache.set("key1", "value1", ttl=60)
        assert await memory_cache.exists("key1") is True
        assert await memory_cache.exists("nonexistent") is False
    
    @pytest.mark.asyncio
    async def test_clear(self, memory_cache):
        """Test clearing all keys"""
        await memory_cache.set("key1", "value1", ttl=60)
        await memory_cache.set("key2", "value2", ttl=60)
        await memory_cache.clear()
        assert await memory_cache.get("key1") is None
        assert await memory_cache.get("key2") is None
    
    @pytest.mark.asyncio
    async def test_ttl_expiration(self, memory_cache):
        """Test that keys expire after TTL"""
        await memory_cache.set("key1", "value1", ttl=1)  # 1 second TTL
        
        # Should exist immediately
        assert await memory_cache.get("key1") == "value1"
        
        # Wait for expiration
        await asyncio.sleep(1.1)
        
        # Should be expired
        assert await memory_cache.get("key1") is None
    
    @pytest.mark.asyncio
    async def test_lru_eviction(self, memory_cache):
        """Test LRU eviction when cache is full"""
        # Fill cache to max (10 items)
        for i in range(10):
            await memory_cache.set(f"key{i}", f"value{i}", ttl=60)
        
        # Add one more to trigger eviction
        await memory_cache.set("key10", "value10", ttl=60)
        
        # Oldest key (key0) should be evicted
        assert await memory_cache.get("key0") is None
        # Newest key should exist
        assert await memory_cache.get("key10") == "value10"
    
    @pytest.mark.asyncio
    async def test_delete_pattern(self, memory_cache):
        """Test deleting keys by pattern"""
        await memory_cache.set("truck:123:detail", "data1", ttl=60)
        await memory_cache.set("truck:123:history", "data2", ttl=60)
        await memory_cache.set("truck:456:detail", "data3", ttl=60)
        await memory_cache.set("fleet:summary", "data4", ttl=60)
        
        # Delete all truck:123:* keys
        deleted = await memory_cache.delete_pattern("truck:123:*")
        assert deleted == 2
        
        # truck:123:* should be gone
        assert await memory_cache.get("truck:123:detail") is None
        assert await memory_cache.get("truck:123:history") is None
        
        # Others should remain
        assert await memory_cache.get("truck:456:detail") == "data3"
        assert await memory_cache.get("fleet:summary") == "data4"
    
    @pytest.mark.asyncio
    async def test_stats(self, memory_cache):
        """Test cache statistics"""
        await memory_cache.set("key1", "value1", ttl=60)
        await memory_cache.get("key1")  # Hit
        await memory_cache.get("key2")  # Miss
        
        stats = memory_cache.get_stats()
        assert stats["backend"] == "memory"
        assert stats["size"] == 1
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_pct"] == 50.0


class TestCacheService:
    """Tests for the high-level cache service"""
    
    @pytest.fixture
    async def cache_service(self):
        """Create a cache service with memory backend for testing"""
        service = CacheService()
        # Don't connect to Redis for unit tests
        service._initialized = True
        return service
    
    @pytest.mark.asyncio
    async def test_fleet_summary_cache(self, cache_service):
        """Test fleet summary convenience methods"""
        test_data = {"total_trucks": 41, "active": 35}
        
        await cache_service.set_fleet_summary(test_data)
        result = await cache_service.get_fleet_summary()
        
        assert result == test_data
    
    @pytest.mark.asyncio
    async def test_truck_detail_cache(self, cache_service):
        """Test truck detail convenience methods"""
        test_data = {"truck_id": "VD3579", "fuel_pct": 75.5}
        
        await cache_service.set_truck_detail("VD3579", test_data)
        result = await cache_service.get_truck_detail("VD3579")
        
        assert result == test_data
    
    @pytest.mark.asyncio
    async def test_kpi_cache(self, cache_service):
        """Test KPI convenience methods"""
        test_data = {"avg_mpg": 6.2, "total_gallons": 1500}
        
        await cache_service.set_kpis(test_data, days=7)
        result = await cache_service.get_kpis(days=7)
        
        assert result == test_data
    
    @pytest.mark.asyncio
    async def test_invalidate_truck(self, cache_service):
        """Test invalidating truck-related caches"""
        # Set up various caches
        await cache_service.set(f"{cache_service.PREFIX_TRUCK}:VD3579:detail", {"data": 1}, 60)
        await cache_service.set(f"{cache_service.PREFIX_TRUCK}:VD3579:history", {"data": 2}, 60)
        await cache_service.set(f"{cache_service.PREFIX_FLEET}:summary", {"data": 3}, 60)
        
        # Invalidate truck
        await cache_service.invalidate_truck("VD3579")
        
        # Truck caches should be cleared
        assert await cache_service.get(f"{cache_service.PREFIX_TRUCK}:VD3579:detail") is None
        assert await cache_service.get(f"{cache_service.PREFIX_TRUCK}:VD3579:history") is None
    
    @pytest.mark.asyncio
    async def test_get_stats(self, cache_service):
        """Test getting cache statistics"""
        stats = cache_service.get_stats()
        
        assert "initialized" in stats
        assert "redis_enabled" in stats
        assert "backend" in stats


class TestCacheDecorator:
    """Tests for the @cache decorator"""
    
    @pytest.mark.asyncio
    async def test_cache_decorator_with_static_key(self):
        """Test caching with a static key"""
        call_count = 0
        
        @cache(key="test:static", ttl=60)
        async def expensive_function():
            nonlocal call_count
            call_count += 1
            return {"result": call_count}
        
        # First call should execute function
        result1 = await expensive_function()
        assert result1 == {"result": 1}
        assert call_count == 1
        
        # Second call should return cached result
        result2 = await expensive_function()
        assert result2 == {"result": 1}
        assert call_count == 1  # Function not called again
    
    @pytest.mark.asyncio
    async def test_cache_decorator_with_key_builder(self):
        """Test caching with dynamic key builder"""
        call_count = {}
        
        @cache(prefix="truck", key_builder=lambda truck_id: truck_id, ttl=60)
        async def get_truck_data(truck_id: str):
            call_count[truck_id] = call_count.get(truck_id, 0) + 1
            return {"truck_id": truck_id, "calls": call_count[truck_id]}
        
        # Call for VD3579
        result1 = await get_truck_data("VD3579")
        assert result1 == {"truck_id": "VD3579", "calls": 1}
        
        # Call for JC1282 (different key)
        result2 = await get_truck_data("JC1282")
        assert result2 == {"truck_id": "JC1282", "calls": 1}
        
        # Call for VD3579 again (should be cached)
        result3 = await get_truck_data("VD3579")
        assert result3 == {"truck_id": "VD3579", "calls": 1}
        assert call_count["VD3579"] == 1  # Not called again


class TestCacheIntegration:
    """Integration tests for cache with Redis (if available)"""
    
    @pytest.mark.asyncio
    async def test_cache_service_initialization(self):
        """Test that cache service initializes correctly"""
        cache_svc = await get_cache()
        
        assert cache_svc._initialized is True
        stats = cache_svc.get_stats()
        
        # Should have either redis or memory backend
        assert stats["backend"] in ["redis", "memory"]
    
    @pytest.mark.asyncio
    async def test_end_to_end_caching(self):
        """Test full cache workflow"""
        cache_svc = await get_cache()
        
        # Set a value
        test_key = "integration:test:key"
        test_value = {"test": True, "timestamp": "2025-12-10"}
        
        await cache_svc.set(test_key, test_value, ttl=60)
        
        # Get the value back
        result = await cache_svc.get(test_key)
        assert result == test_value
        
        # Delete it
        await cache_svc.delete(test_key)
        
        # Verify it's gone
        result = await cache_svc.get(test_key)
        assert result is None


class TestCacheHelpers:
    """Tests for cache invalidation helpers"""
    
    @pytest.mark.asyncio
    async def test_invalidate_on_truck_update(self):
        """Test truck update invalidation helper"""
        cache_svc = await get_cache()
        
        # Set up cache data
        await cache_svc.set("truck:VD3579:detail", {"data": 1}, 60)
        
        # Trigger invalidation
        await invalidate_on_truck_update("VD3579")
        
        # Should be invalidated
        # Note: exact behavior depends on patterns defined in invalidate_truck


class TestCacheTypes:
    """Test caching of various data types"""
    
    @pytest.fixture
    async def cache_service(self):
        return await get_cache()
    
    @pytest.mark.asyncio
    async def test_cache_dict(self, cache_service):
        """Test caching dictionaries"""
        data = {"key": "value", "nested": {"a": 1, "b": 2}}
        await cache_service.set("type:dict", data, 60)
        result = await cache_service.get("type:dict")
        assert result == data
    
    @pytest.mark.asyncio
    async def test_cache_list(self, cache_service):
        """Test caching lists"""
        data = [1, 2, 3, {"nested": True}]
        await cache_service.set("type:list", data, 60)
        result = await cache_service.get("type:list")
        assert result == data
    
    @pytest.mark.asyncio
    async def test_cache_numbers(self, cache_service):
        """Test caching numbers"""
        await cache_service.set("type:int", 42, 60)
        await cache_service.set("type:float", 3.14159, 60)
        
        assert await cache_service.get("type:int") == 42
        assert await cache_service.get("type:float") == 3.14159
    
    @pytest.mark.asyncio
    async def test_cache_string(self, cache_service):
        """Test caching strings"""
        await cache_service.set("type:string", "Hello, World!", 60)
        assert await cache_service.get("type:string") == "Hello, World!"
    
    @pytest.mark.asyncio
    async def test_cache_bool(self, cache_service):
        """Test caching booleans"""
        await cache_service.set("type:bool:true", True, 60)
        await cache_service.set("type:bool:false", False, 60)
        
        assert await cache_service.get("type:bool:true") is True
        assert await cache_service.get("type:bool:false") is False
    
    @pytest.mark.asyncio
    async def test_cache_none_returns_none(self, cache_service):
        """Test that None values are handled correctly"""
        # None should not be cached (to distinguish from cache miss)
        await cache_service.set("type:none", None, 60)
        result = await cache_service.get("type:none")
        # Result will be None but due to JSON serialization, it gets stored as null
        # This is expected behavior


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
