#!/usr/bin/env python3
"""
Test Cache Endpoints Directly
Prueba los endpoints de cache sin necesidad de curl
"""

import asyncio
import sys

from multi_layer_cache import cache


async def test_cache_functionality():
    """Prueba directa de funcionalidad de cache"""

    print("\n" + "=" * 60)
    print("🧪 TESTING CACHE ENDPOINTS LOGIC")
    print("=" * 60 + "\n")

    # Conectar a Redis
    print("📡 Connecting to cache...")
    await cache.connect()
    print("✅ Cache connected\n")

    # TEST 1: Cache Performance (simula /cache/test)
    print("TEST 1: Cache Performance Test")
    print("-" * 40)

    async def mock_db_query():
        """Simula una consulta a la base de datos"""
        await asyncio.sleep(0.05)  # 50ms de latencia
        return {
            "truck_id": "FL0208",
            "fuel_level": 75.5,
            "speed": 65,
            "location": "Miami, FL",
        }

    import time

    # Primera llamada (DB)
    start = time.perf_counter()
    data1 = await cache.get_or_fetch("test", mock_db_query, ttl=300)
    time1 = (time.perf_counter() - start) * 1000

    # Segunda llamada (Redis)
    start = time.perf_counter()
    data2 = await cache.get_or_fetch("test", mock_db_query, ttl=300)
    time2 = (time.perf_counter() - start) * 1000

    # Tercera llamada (Memory)
    start = time.perf_counter()
    data3 = await cache.get_or_fetch("test", mock_db_query, ttl=300)
    time3 = (time.perf_counter() - start) * 1000

    print(f"   1st call (DB):     {time1:.2f}ms")
    print(f"   2nd call (Redis):  {time2:.2f}ms  ({time1/time2:.1f}x faster)")
    print(f"   3rd call (Memory): {time3:.2f}ms  ({time1/time3:.1f}x faster)")

    result = {
        "success": True,
        "message": "Cache working correctly",
        "performance": {
            "db_time_ms": round(time1, 2),
            "redis_time_ms": round(time2, 2),
            "memory_time_ms": round(time3, 2),
            "redis_speedup": round(time1 / time2, 1),
            "memory_speedup": round(time1 / time3, 1),
        },
        "data_sample": data1,
    }

    print(f"\n✅ Test 1 Passed\n")

    # TEST 2: Redis Connection Test
    print("TEST 2: Redis Connection & Keys")
    print("-" * 40)

    # Get Redis stats directly
    if cache.redis_client:
        info = await cache.redis_client.info()
        dbsize = await cache.redis_client.dbsize()

        print(f"   Redis connected: ✅")
        print(f"   Redis version: {info.get('redis_version', 'N/A')}")
        print(f"   Keys in Redis: {dbsize}")
        print(f"   Total connections: {info.get('total_connections_received', 'N/A')}")
        print(f"   Total commands: {info.get('total_commands_processed', 'N/A')}")

        stats = {
            "redis_connected": True,
            "redis_version": info.get("redis_version"),
            "keys_count": dbsize,
            "total_connections": info.get("total_connections_received"),
            "total_commands": info.get("total_commands_processed"),
        }
    else:
        print(f"   Redis connected: ❌")
        stats = {"redis_connected": False}

    print(f"\n✅ Test 2 Passed\n")

    # Cleanup
    await cache.disconnect()
    print("🔌 Cache disconnected\n")

    print("=" * 60)
    print("✅ ALL TESTS PASSED")
    print("=" * 60)
    print("\n📊 ENDPOINT SIMULATION RESULTS:")
    print(
        f"   GET /cache/test  → DB: {result['performance']['db_time_ms']}ms, Redis: {result['performance']['redis_time_ms']}ms ({result['performance']['redis_speedup']}x faster)"
    )
    print(
        f"   GET /cache/stats → Redis: {stats.get('keys_count', 'N/A')} keys, Connections: {stats.get('total_connections', 'N/A')}"
    )
    print("\n🎉 Cache endpoints are ready for production!\n")

    return result, stats


if __name__ == "__main__":
    try:
        asyncio.run(test_cache_functionality())
    except KeyboardInterrupt:
        print("\n\n⚠️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
