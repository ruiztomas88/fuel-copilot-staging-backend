"""
Async MySQL Database Module for Fuel Copilot
==============================================

Provides non-blocking async database operations using aiomysql.

Features:
- Connection pooling for optimal performance
- Async context managers for safe resource handling
- Type hints for better IDE support
- Comprehensive error handling

Usage:
    from database_async import execute_query, execute_query_one

    # Single row
    truck = await execute_query_one(
        "SELECT * FROM trucks WHERE truck_id = %s",
        ("FL-0208",)
    )

    # Multiple rows
    events = await execute_query(
        "SELECT * FROM fuel_events WHERE truck_id = %s LIMIT 10",
        ("FL-0208",)
    )

Author: Fuel Copilot Team
Date: 26 Dec 2025
Version: 1.0.0
"""

import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import aiomysql
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Global connection pool (initialized on first use)
_pool: Optional[aiomysql.Pool] = None

# Database configuration
DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
    "user": os.getenv("MYSQL_USER", "fuel_user"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "db": os.getenv("MYSQL_DATABASE", "fuel_monitoring"),
    "charset": "utf8mb4",
    "autocommit": True,
}

# Pool configuration
POOL_CONFIG = {
    "minsize": int(os.getenv("DB_POOL_MIN_SIZE", 5)),
    "maxsize": int(os.getenv("DB_POOL_MAX_SIZE", 20)),
    "echo": os.getenv("DB_POOL_ECHO", "false").lower() == "true",
}


async def get_async_pool() -> aiomysql.Pool:
    """
    Get or create the async MySQL connection pool.

    Returns:
        aiomysql.Pool: Active connection pool

    Raises:
        Exception: If pool creation fails
    """
    global _pool

    if _pool is None:
        try:
            logger.info("🔄 Creating async MySQL connection pool...")
            logger.info(f"   Host: {DB_CONFIG['host']}:{DB_CONFIG['port']}")
            logger.info(f"   Database: {DB_CONFIG['db']}")
            logger.info(
                f"   Pool size: {POOL_CONFIG['minsize']}-{POOL_CONFIG['maxsize']}"
            )

            _pool = await aiomysql.create_pool(
                host=DB_CONFIG["host"],
                port=DB_CONFIG["port"],
                user=DB_CONFIG["user"],
                password=DB_CONFIG["password"],
                db=DB_CONFIG["db"],
                charset=DB_CONFIG["charset"],
                autocommit=DB_CONFIG["autocommit"],
                minsize=POOL_CONFIG["minsize"],
                maxsize=POOL_CONFIG["maxsize"],
                echo=POOL_CONFIG["echo"],
            )

            logger.info("✅ Async MySQL connection pool created successfully")

        except Exception as e:
            logger.error(f"❌ Failed to create async MySQL pool: {e}")
            raise

    return _pool


async def close_async_pool():
    """
    Close the async MySQL connection pool.

    Should be called during application shutdown.
    """
    global _pool

    if _pool:
        logger.info("🔄 Closing async MySQL connection pool...")
        _pool.close()
        await _pool.wait_closed()
        _pool = None
        logger.info("✅ Async MySQL connection pool closed")


async def execute_query(
    query: str, params: Optional[Tuple] = None, cursor_class=aiomysql.DictCursor
) -> List[Dict[str, Any]]:
    """
    Execute a SELECT query and return all results.

    Args:
        query: SQL query string (use %s for parameters)
        params: Tuple of parameters to bind to query
        cursor_class: Cursor class to use (default: DictCursor for dict results)

    Returns:
        List of dictionaries (rows)

    Example:
        results = await execute_query(
            "SELECT * FROM trucks WHERE status = %s",
            ("active",)
        )
    """
    pool = await get_async_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.cursor(cursor_class) as cursor:
                await cursor.execute(query, params)
                results = await cursor.fetchall()
                return results

    except Exception as e:
        logger.error(f"❌ Query error: {e}")
        logger.error(f"   Query: {query}")
        logger.error(f"   Params: {params}")
        raise


async def execute_query_one(
    query: str, params: Optional[Tuple] = None, cursor_class=aiomysql.DictCursor
) -> Optional[Dict[str, Any]]:
    """
    Execute a SELECT query and return one result.

    Args:
        query: SQL query string (use %s for parameters)
        params: Tuple of parameters to bind to query
        cursor_class: Cursor class to use (default: DictCursor for dict results)

    Returns:
        Dictionary (row) or None if no results

    Example:
        truck = await execute_query_one(
            "SELECT * FROM trucks WHERE truck_id = %s",
            ("FL-0208",)
        )
    """
    pool = await get_async_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.cursor(cursor_class) as cursor:
                await cursor.execute(query, params)
                result = await cursor.fetchone()
                return result

    except Exception as e:
        logger.error(f"❌ Query error: {e}")
        logger.error(f"   Query: {query}")
        logger.error(f"   Params: {params}")
        raise


async def execute_insert(query: str, params: Optional[Tuple] = None) -> int:
    """
    Execute an INSERT query and return the last inserted ID.

    Args:
        query: SQL INSERT statement
        params: Tuple of parameters to bind

    Returns:
        Last inserted row ID

    Example:
        new_id = await execute_insert(
            "INSERT INTO fuel_events (truck_id, event_type) VALUES (%s, %s)",
            ("FL-0208", "refuel")
        )
    """
    pool = await get_async_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return cursor.lastrowid

    except Exception as e:
        logger.error(f"❌ Insert error: {e}")
        logger.error(f"   Query: {query}")
        logger.error(f"   Params: {params}")
        raise


async def execute_update(query: str, params: Optional[Tuple] = None) -> int:
    """
    Execute an UPDATE query and return affected rows.

    Args:
        query: SQL UPDATE statement
        params: Tuple of parameters to bind

    Returns:
        Number of affected rows

    Example:
        affected = await execute_update(
            "UPDATE trucks SET status = %s WHERE truck_id = %s",
            ("inactive", "FL-0208")
        )
    """
    pool = await get_async_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return cursor.rowcount

    except Exception as e:
        logger.error(f"❌ Update error: {e}")
        logger.error(f"   Query: {query}")
        logger.error(f"   Params: {params}")
        raise


async def execute_delete(query: str, params: Optional[Tuple] = None) -> int:
    """
    Execute a DELETE query and return affected rows.

    Args:
        query: SQL DELETE statement
        params: Tuple of parameters to bind

    Returns:
        Number of deleted rows

    Example:
        deleted = await execute_delete(
            "DELETE FROM old_events WHERE timestamp < %s",
            (cutoff_date,)
        )
    """
    pool = await get_async_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute(query, params)
                return cursor.rowcount

    except Exception as e:
        logger.error(f"❌ Delete error: {e}")
        logger.error(f"   Query: {query}")
        logger.error(f"   Params: {params}")
        raise


async def execute_many(query: str, params_list: List[Tuple]) -> int:
    """
    Execute a query multiple times with different parameters (bulk insert).

    Args:
        query: SQL statement
        params_list: List of parameter tuples

    Returns:
        Number of affected rows

    Example:
        rows = await execute_many(
            "INSERT INTO fuel_events (truck_id, gallons) VALUES (%s, %s)",
            [("FL-0208", 50), ("FL-0209", 45), ("FL-0210", 52)]
        )
    """
    pool = await get_async_pool()

    try:
        async with pool.acquire() as conn:
            async with conn.cursor() as cursor:
                await cursor.executemany(query, params_list)
                return cursor.rowcount

    except Exception as e:
        logger.error(f"❌ Bulk execute error: {e}")
        logger.error(f"   Query: {query}")
        logger.error(f"   Params count: {len(params_list)}")
        raise


async def get_pool_stats() -> Dict[str, Any]:
    """
    Get connection pool statistics.

    Returns:
        Dictionary with pool stats
    """
    pool = await get_async_pool()

    return {
        "size": pool.size,
        "free": pool.freesize,
        "minsize": pool.minsize,
        "maxsize": pool.maxsize,
        "used": pool.size - pool.freesize,
    }


async def health_check() -> Dict[str, Any]:
    """
    Perform a health check on the database connection.

    Returns:
        Dictionary with health status

    Example:
        status = await health_check()
        if status['healthy']:
            print("Database OK")
    """
    try:
        result = await execute_query_one("SELECT 1 as test, NOW() as server_time")

        pool_stats = await get_pool_stats()

        return {
            "healthy": True,
            "server_time": result["server_time"],
            "pool_stats": pool_stats,
        }

    except Exception as e:
        logger.error(f"❌ Database health check failed: {e}")
        return {
            "healthy": False,
            "error": str(e),
        }


# ============================================================================
# CONTEXT MANAGERS (Advanced Usage)
# ============================================================================


class AsyncConnection:
    """
    Async context manager for manual connection handling.

    Use when you need more control over the connection lifecycle.

    Example:
        async with AsyncConnection() as conn:
            async with conn.cursor() as cursor:
                await cursor.execute("SELECT * FROM trucks")
                results = await cursor.fetchall()
    """

    def __init__(self):
        self.pool = None
        self.conn = None

    async def __aenter__(self):
        self.pool = await get_async_pool()
        self.conn = await self.pool.acquire()
        return self.conn

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            await self.pool.release(self.conn)


# ============================================================================
# TESTING UTILITIES
# ============================================================================


async def test_connection():
    """
    Test the database connection.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        result = await execute_query_one("SELECT 1 as test")
        logger.info(f"✅ Database connection test successful: {result}")
        return True

    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return False


if __name__ == "__main__":
    # Test script
    import asyncio

    async def main():
        logger.info("🧪 Testing async database module...")

        # Test connection
        await test_connection()

        # Test health check
        health = await health_check()
        logger.info(f"Health check: {health}")

        # Test pool stats
        stats = await get_pool_stats()
        logger.info(f"Pool stats: {stats}")

        # Cleanup
        await close_async_pool()

        logger.info("✅ All tests completed")

    asyncio.run(main())
