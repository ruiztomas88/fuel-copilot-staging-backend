"""
Database Connection Pool Manager
Centralized SQLAlchemy engine with connection pooling for all database operations
Replaces individual pymysql connections to prevent connection exhaustion
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
import logging
from typing import Generator
import os

logger = logging.getLogger(__name__)

# MySQL Configuration
MYSQL_HOST = os.getenv("MYSQL_HOST", "20.127.200.135")
MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
MYSQL_USER = os.getenv("MYSQL_USER", "tomas")
MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "Tomas2025")
MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "wialon_collect")

# Build connection string for Wialon (remote)
DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@"
    f"{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    f"?charset=utf8mb4"
)

# Local MySQL Configuration (fuel_copilot database)
LOCAL_DB_HOST = os.getenv("LOCAL_DB_HOST", "localhost")
LOCAL_DB_PORT = int(os.getenv("LOCAL_DB_PORT", "3306"))
LOCAL_DB_USER = os.getenv("LOCAL_DB_USER", "fuel_admin")
LOCAL_DB_PASSWORD = os.getenv("LOCAL_DB_PASS", "FuelCopilot2025!")
LOCAL_DB_NAME = os.getenv("LOCAL_DB_NAME", "fuel_copilot")

# Build connection string for fuel_copilot (local)
LOCAL_DATABASE_URL = (
    f"mysql+pymysql://{LOCAL_DB_USER}:{LOCAL_DB_PASSWORD}@"
    f"{LOCAL_DB_HOST}:{LOCAL_DB_PORT}/{LOCAL_DB_NAME}"
    f"?charset=utf8mb4"
)

# Global engine instances (singletons)
_engine = None
_SessionLocal = None
_local_engine = None
_LocalSessionLocal = None


def get_engine():
    """
    Get or create the global SQLAlchemy engine with connection pooling

    Pool Configuration (UPGRADED for 1000+ trucks):
    - pool_size: 50 persistent connections (was 10)
    - max_overflow: 100 additional connections under load (was 20)
    - pool_timeout: 60s wait for connection (was 30s)
    - pool_recycle: 1800s (30min) recycle connections (was 3600s)
    - pool_pre_ping: Test connection before use (detect stale connections)
    - pool_use_lifo: LIFO queue for better burst handling

    Total max connections: 150 (pool_size + max_overflow)
    Designed for: 100+ parallel workers + dashboard queries
    """
    global _engine

    if _engine is None:
        logger.info("🔌 Creating SQLAlchemy engine with connection pool...")

        _engine = create_engine(
            DATABASE_URL,
            poolclass=QueuePool,
            pool_size=50,  # Base pool size (INCREASED 10→50 for 1000+ trucks)
            max_overflow=100,  # Additional connections under load (INCREASED 20→100)
            pool_timeout=60,  # Wait 60s for connection (INCREASED 30→60)
            pool_recycle=1800,  # Recycle connections every 30min (DECREASED 3600→1800)
            pool_pre_ping=True,  # Validate connections before use
            pool_use_lifo=True,  # Use LIFO for better burst handling
            echo=False,  # Set True for SQL query debugging
            echo_pool=False,  # Set True for pool debugging
        )

        # Test connection
        try:
            with _engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info(f"✅ Database connection pool initialized successfully")
                logger.info(
                    f"   Pool size: 50 | Max overflow: 100 | Total max: 150 (UPGRADED for scale)"
                )
        except Exception as e:
            logger.error(f"❌ Failed to connect to MySQL: {e}")
            _engine = None
            raise

    return _engine


def get_session_maker():
    """Get or create the global session maker"""
    global _SessionLocal

    if _SessionLocal is None:
        engine = get_engine()
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    return _SessionLocal


# ═══════════════════════════════════════════════════════════════════════════════
# LOCAL DATABASE POOL (fuel_copilot)
# ═══════════════════════════════════════════════════════════════════════════════


def get_local_engine():
    """
    Get or create the LOCAL SQLAlchemy engine (fuel_copilot database) with connection pooling.

    This pool is for local MySQL queries (fuel_metrics, etc.)
    Separate from Wialon remote database pool.

    Pool Configuration:
    - pool_size: 20 persistent connections
    - max_overflow: 30 additional connections under load
    - pool_timeout: 30s wait for connection
    - pool_recycle: 1800s (30min) recycle connections
    - pool_pre_ping: Test connection before use
    """
    global _local_engine

    if _local_engine is None:
        logger.info(
            "🔌 Creating LOCAL SQLAlchemy engine (fuel_copilot) with connection pool..."
        )

        _local_engine = create_engine(
            LOCAL_DATABASE_URL,
            poolclass=QueuePool,
            pool_size=20,  # Smaller than Wialon pool (local has less traffic)
            max_overflow=30,
            pool_timeout=30,
            pool_recycle=1800,
            pool_pre_ping=True,
            pool_use_lifo=True,
            echo=False,
            echo_pool=False,
        )

        # Test connection
        try:
            with _local_engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                logger.info(
                    f"✅ LOCAL database pool (fuel_copilot) initialized successfully"
                )
                logger.info(f"   Pool size: 20 | Max overflow: 30 | Total max: 50")
        except Exception as e:
            logger.error(f"❌ Failed to connect to LOCAL MySQL (fuel_copilot): {e}")
            _local_engine = None
            raise

    return _local_engine


def get_local_session_maker():
    """Get or create the LOCAL session maker (fuel_copilot)"""
    global _LocalSessionLocal

    if _LocalSessionLocal is None:
        engine = get_local_engine()
        _LocalSessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=engine
        )

    return _LocalSessionLocal


@contextmanager
def get_local_db_session() -> Generator[Session, None, None]:
    """
    Context manager for LOCAL database sessions (fuel_copilot)
    Automatically commits on success, rolls back on error

    Usage:
        with get_local_db_session() as session:
            results = session.execute(text("SELECT ..."))
    """
    SessionLocal = get_local_session_maker()
    session = SessionLocal()

    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Local database session error: {e}")
        raise
    finally:
        session.close()


def execute_local_query(query: str, params: tuple = None) -> list:
    """
    Execute query on fuel_copilot database using connection pool.
    Returns list of dict rows or empty list on error.

    This replaces direct pymysql connections in predictive_maintenance_v3.py
    """
    try:
        engine = get_local_engine()
        with engine.connect() as conn:
            if params:
                result = conn.execute(text(query), dict(enumerate(params)))
            else:
                result = conn.execute(text(query))

            # Convert to list of dicts
            columns = result.keys()
            rows = [dict(zip(columns, row)) for row in result.fetchall()]
            return rows
    except Exception as e:
        logger.warning(f"[Pool] Local DB query error: {e}")
        return []


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions
    Automatically commits on success, rolls back on error

    Usage:
        with get_db_session() as session:
            results = session.execute(text("SELECT ..."))
    """
    SessionLocal = get_session_maker()
    session = SessionLocal()

    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}")
        raise
    finally:
        session.close()


@contextmanager
def get_db_connection():
    """
    Context manager for raw connections (backwards compatibility)
    Uses connection pool instead of creating new connections

    Usage:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(...)
    """
    engine = get_engine()

    conn = engine.raw_connection()
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database connection error: {e}")
        raise
    finally:
        conn.close()


def get_pool_stats() -> dict:
    """
    Get current connection pool statistics
    Useful for monitoring and debugging

    Returns:
        Dict with pool metrics for both Wialon and Local pools
    """
    stats = {}

    try:
        engine = get_engine()
        stats["wialon"] = {
            "engine_url": str(engine.url).replace(MYSQL_PASSWORD, "****"),
            "pool_class": engine.pool.__class__.__name__,
            "status": "healthy",
        }
    except Exception as e:
        stats["wialon"] = {"status": "error", "error": str(e)}

    try:
        local_engine = get_local_engine()
        stats["local"] = {
            "engine_url": str(local_engine.url).replace(LOCAL_DB_PASSWORD, "****"),
            "pool_class": local_engine.pool.__class__.__name__,
            "status": "healthy",
        }
    except Exception as e:
        stats["local"] = {"status": "error", "error": str(e)}

    return stats


def close_engine():
    """
    Close both engines and dispose all connections
    Call this on application shutdown
    """
    global _engine, _SessionLocal, _local_engine, _LocalSessionLocal

    if _engine:
        logger.info("🔌 Disposing Wialon database connection pool...")
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        logger.info("✅ Wialon database pool disposed")

    if _local_engine:
        logger.info("🔌 Disposing LOCAL database connection pool...")
        _local_engine.dispose()
        _local_engine = None
        _LocalSessionLocal = None
        logger.info("✅ Local database pool disposed")


# Initialize engines on module import
try:
    get_engine()
except Exception as e:
    logger.warning(f"⚠️ Could not initialize Wialon database pool on import: {e}")
    logger.warning("   Pool will be created on first use")

# Don't auto-init local pool - it may not exist in all environments
