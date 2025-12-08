"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    CENTRALIZED DATABASE CONNECTION MODULE                      ║
║                         Fuel Copilot v4.0                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Purpose: Single source of truth for all database connections                  ║
║  Features:                                                                     ║
║    - Connection pooling via SQLAlchemy                                         ║
║    - Context managers for safe connection handling                             ║
║    - Retry logic with exponential backoff                                      ║
║    - Support for both SQLAlchemy and raw pymysql                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import time
import logging
from contextlib import contextmanager
from typing import Optional, Generator, Any
from functools import wraps

import pymysql
from pymysql.cursors import DictCursor
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine, Connection
from sqlalchemy.pool import QueuePool

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

# Connection pool settings
POOL_SIZE = 10
MAX_OVERFLOW = 5
POOL_RECYCLE = 3600  # Recycle connections after 1 hour
POOL_PRE_PING = True  # Test connections before using

# Retry settings
MAX_RETRIES = 3
BASE_DELAY = 0.5  # 500ms base delay
MAX_DELAY = 10.0  # 10 second max delay


def _get_db_config() -> dict:
    """Get database configuration from environment."""
    return {
        "host": os.getenv("MYSQL_HOST", "fuelcopilot.mysql.database.azure.com"),
        "user": os.getenv("MYSQL_USER", "tomas"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "fuel_copilot"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "charset": "utf8mb4",
        "ssl": {"ca": None, "check_hostname": False},
        "autocommit": True,
        "cursorclass": DictCursor,  # Always use DictCursor for dict results
    }


def _get_connection_string() -> str:
    """Generate SQLAlchemy connection string."""
    config = _get_db_config()
    return (
        f"mysql+pymysql://{config['user']}:{config['password']}"
        f"@{config['host']}:{config['port']}/{config['database']}"
        f"?charset=utf8mb4"
    )


# ═══════════════════════════════════════════════════════════════════════════════
# RETRY DECORATOR
# ═══════════════════════════════════════════════════════════════════════════════


def with_retry(
    max_retries: int = MAX_RETRIES,
    base_delay: float = BASE_DELAY,
    max_delay: float = MAX_DELAY,
    retryable_exceptions: tuple = (
        pymysql.err.OperationalError,
        pymysql.err.InterfaceError,
        ConnectionError,
        TimeoutError,
    ),
):
    """
    Decorator for retrying database operations with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (doubles each time)
        max_delay: Maximum delay between retries
        retryable_exceptions: Tuple of exceptions that trigger retry
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        delay = min(base_delay * (2**attempt), max_delay)
                        logger.warning(
                            f"Database operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                            f"Retrying in {delay:.1f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"Database operation failed after {max_retries + 1} attempts: {e}"
                        )

            raise last_exception

        return wrapper

    return decorator


# ═══════════════════════════════════════════════════════════════════════════════
# SQLALCHEMY ENGINE (SINGLETON WITH POOLING)
# ═══════════════════════════════════════════════════════════════════════════════

_engine: Optional[Engine] = None


def get_sqlalchemy_engine() -> Engine:
    """
    Get SQLAlchemy engine with connection pooling (singleton).

    Returns:
        SQLAlchemy Engine with configured connection pool
    """
    global _engine

    if _engine is None:
        try:
            _engine = create_engine(
                _get_connection_string(),
                poolclass=QueuePool,
                pool_size=POOL_SIZE,
                max_overflow=MAX_OVERFLOW,
                pool_recycle=POOL_RECYCLE,
                pool_pre_ping=POOL_PRE_PING,
                echo=False,
            )
            logger.info(
                f"✅ SQLAlchemy engine created with pooling "
                f"(pool_size={POOL_SIZE}, max_overflow={MAX_OVERFLOW})"
            )
        except Exception as e:
            logger.error(f"❌ Failed to create SQLAlchemy engine: {e}")
            raise

    return _engine


# ═══════════════════════════════════════════════════════════════════════════════
# CONNECTION CONTEXT MANAGERS
# ═══════════════════════════════════════════════════════════════════════════════


@contextmanager
def get_db_connection() -> Generator[Connection, None, None]:
    """
    Context manager for SQLAlchemy pooled connections.

    This is the PRIMARY method for database access.
    Uses connection pooling for better performance.

    Usage:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT * FROM trucks"))
            data = result.fetchall()

    Yields:
        SQLAlchemy Connection object
    """
    engine = get_sqlalchemy_engine()
    conn = engine.connect()
    try:
        yield conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        conn.close()


@contextmanager
def get_pymysql_connection() -> Generator[pymysql.Connection, None, None]:
    """
    Context manager for raw pymysql connections.

    Use this when you need pymysql-specific features or
    direct cursor access with DictCursor.

    Usage:
        with get_pymysql_connection() as conn:
            with conn.cursor(DictCursor) as cursor:
                cursor.execute("SELECT * FROM trucks")
                rows = cursor.fetchall()

    Yields:
        pymysql Connection object
    """
    conn = None
    try:
        conn = pymysql.connect(**_get_db_config())
        yield conn
    except Exception as e:
        logger.error(f"PyMySQL connection error: {e}")
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_cursor(dict_cursor: bool = True) -> Generator[Any, None, None]:
    """
    Context manager that provides a cursor directly.

    Args:
        dict_cursor: If True, returns DictCursor (rows as dicts)

    Usage:
        with get_db_cursor() as cursor:
            cursor.execute("SELECT * FROM trucks WHERE truck_id = %s", (truck_id,))
            row = cursor.fetchone()

    Yields:
        pymysql Cursor object
    """
    conn = None
    cursor = None
    try:
        conn = pymysql.connect(**_get_db_config())
        cursor_class = DictCursor if dict_cursor else None
        cursor = conn.cursor(cursor_class)
        yield cursor
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Database cursor error: {e}")
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


@with_retry()
def execute_query(query: str, params: Optional[dict] = None) -> list:
    """
    Execute a SELECT query with retry logic.

    Args:
        query: SQL query string
        params: Optional dict of query parameters

    Returns:
        List of result rows as dictionaries
    """
    with get_db_connection() as conn:
        result = conn.execute(text(query), params or {})
        return [dict(row._mapping) for row in result.fetchall()]


@with_retry()
def execute_write(query: str, params: Optional[dict] = None) -> int:
    """
    Execute an INSERT/UPDATE/DELETE query with retry logic.

    Args:
        query: SQL query string
        params: Optional dict of query parameters

    Returns:
        Number of affected rows
    """
    with get_db_connection() as conn:
        result = conn.execute(text(query), params or {})
        conn.commit()
        return result.rowcount


def test_connection() -> bool:
    """
    Test database connectivity.

    Returns:
        True if connection successful, False otherwise
    """
    try:
        with get_db_connection() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        logger.info("✅ Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"❌ Database connection test failed: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

# Warm up connection pool on import (optional)
# Uncomment if you want eager initialization
# get_sqlalchemy_engine()
