"""
Memory Cache - Simple in-memory caching for Fuel Copilot
Zero dependencies, instant performance boost for heavy endpoints

Author: Fuel Copilot Team
Version: v1.0.0
Date: December 2025

Usage:
    from memory_cache import cache, cached

    # Option 1: Decorator
    @cached(ttl_seconds=30)
    def get_fleet_summary():
        # expensive query...
        return data

    # Option 2: Manual
    data = cache.get("my_key")
    if data is None:
        data = expensive_query()
        cache.set("my_key", data, ttl=30)
"""

import time
import threading
import logging
from typing import Any, Optional, Dict, Callable
from functools import wraps
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Single cache entry with expiration"""

    value: Any
    expires_at: float
    created_at: float = field(default_factory=time.time)
    hits: int = 0


class MemoryCache:
    """
    Thread-safe in-memory cache with TTL support.

    Features:
    - Automatic expiration
    - Hit/miss statistics
    - Thread-safe operations
    - Configurable max size
    - Background cleanup
    """

    def __init__(self, max_size: int = 1000, cleanup_interval: int = 60):
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._max_size = max_size
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }

        # Start background cleanup thread
        self._cleanup_interval = cleanup_interval
        self._running = True
        self._cleanup_thread = threading.Thread(target=self._cleanup_loop, daemon=True)
        self._cleanup_thread.start()

        logger.info(f"✅ MemoryCache initialized (max_size={max_size})")

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.
        Returns None if key doesn't exist or is expired.
        """
        with self._lock:
            entry = self._cache.get(key)

            if entry is None:
                self._stats["misses"] += 1
                return None

            # Check expiration
            if time.time() > entry.expires_at:
                del self._cache[key]
                self._stats["misses"] += 1
                return None

            # Cache hit
            entry.hits += 1
            self._stats["hits"] += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: int = 30) -> None:
        """
        Set value in cache with TTL (time-to-live in seconds).
        """
        with self._lock:
            # Evict if at max capacity
            if len(self._cache) >= self._max_size and key not in self._cache:
                self._evict_oldest()

            self._cache[key] = CacheEntry(
                value=value,
                expires_at=time.time() + ttl,
                created_at=time.time(),
            )
            self._stats["sets"] += 1

    def delete(self, key: str) -> bool:
        """Delete a key from cache. Returns True if key existed."""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> int:
        """Clear all cache entries. Returns number of entries cleared."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"🗑️ Cache cleared ({count} entries)")
            return count

    def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate all keys matching a pattern.
        Pattern uses simple prefix matching.
        Returns number of keys invalidated.
        """
        with self._lock:
            keys_to_delete = [k for k in self._cache.keys() if k.startswith(pattern)]
            for key in keys_to_delete:
                del self._cache[key]

            if keys_to_delete:
                logger.debug(
                    f"🗑️ Invalidated {len(keys_to_delete)} keys matching '{pattern}'"
                )

            return len(keys_to_delete)

    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        with self._lock:
            total = self._stats["hits"] + self._stats["misses"]
            hit_rate = (self._stats["hits"] / total * 100) if total > 0 else 0

            return {
                "entries": len(self._cache),
                "max_size": self._max_size,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate_pct": round(hit_rate, 2),
                "sets": self._stats["sets"],
                "evictions": self._stats["evictions"],
            }

    def _evict_oldest(self) -> None:
        """Evict the oldest entry to make room"""
        if not self._cache:
            return

        oldest_key = min(self._cache.keys(), key=lambda k: self._cache[k].created_at)
        del self._cache[oldest_key]
        self._stats["evictions"] += 1

    def _cleanup_expired(self) -> int:
        """Remove all expired entries. Returns count removed."""
        with self._lock:
            now = time.time()
            expired_keys = [k for k, v in self._cache.items() if now > v.expires_at]

            for key in expired_keys:
                del self._cache[key]

            return len(expired_keys)

    def _cleanup_loop(self) -> None:
        """Background thread that periodically cleans up expired entries"""
        while self._running:
            time.sleep(self._cleanup_interval)
            try:
                count = self._cleanup_expired()
                if count > 0:
                    logger.debug(f"🧹 Cleanup removed {count} expired cache entries")
            except Exception as e:
                logger.error(f"Cache cleanup error: {e}")

    def shutdown(self) -> None:
        """Stop background cleanup thread"""
        self._running = False


# Global cache instance
cache = MemoryCache(max_size=500)


def cached(ttl_seconds: int = 30, key_prefix: str = ""):
    """
    Decorator for caching function results.

    Args:
        ttl_seconds: Time-to-live in seconds (default: 30)
        key_prefix: Optional prefix for cache key

    Example:
        @cached(ttl_seconds=60)
        def get_kpis(days: int):
            # expensive calculation
            return result
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Build cache key from function name and arguments
            func_name = key_prefix or func.__name__
            args_key = ":".join(str(a) for a in args) if args else ""
            kwargs_key = (
                ":".join(f"{k}={v}" for k, v in sorted(kwargs.items()))
                if kwargs
                else ""
            )

            cache_key = f"{func_name}:{args_key}:{kwargs_key}".rstrip(":")

            # Try cache first
            result = cache.get(cache_key)
            if result is not None:
                logger.debug(f"💨 Cache HIT: {cache_key}")
                return result

            # Cache miss - call function
            logger.debug(f"📥 Cache MISS: {cache_key}")
            result = func(*args, **kwargs)

            # Store in cache
            cache.set(cache_key, result, ttl=ttl_seconds)

            return result

        # Add method to invalidate this function's cache
        wrapper.invalidate = lambda: cache.invalidate_pattern(
            key_prefix or func.__name__
        )

        return wrapper

    return decorator


# Convenience functions for common operations
def invalidate_fleet_cache() -> int:
    """Invalidate all fleet-related cache entries"""
    count = 0
    count += cache.invalidate_pattern("get_fleet_summary")
    count += cache.invalidate_pattern("get_kpi")
    count += cache.invalidate_pattern("get_efficiency")
    count += cache.invalidate_pattern("get_loss")
    count += cache.invalidate_pattern("get_driver")
    return count


def invalidate_truck_cache(truck_id: str) -> int:
    """Invalidate cache entries for a specific truck"""
    return cache.invalidate_pattern(f"truck:{truck_id}")


# For debugging/monitoring
def get_cache_status() -> Dict[str, Any]:
    """Get current cache status for monitoring endpoint"""
    return {"type": "memory", "status": "active", **cache.get_stats()}
