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

# Build connection string
DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}@"
    f"{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}"
    f"?charset=utf8mb4"
)

# Global engine instance (singleton)
_engine = None
_SessionLocal = None


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
        Dict with pool metrics
    """
    engine = get_engine()

    try:
        # Basic stats that work across SQLAlchemy versions
        return {
            "engine_url": str(engine.url).replace(MYSQL_PASSWORD, "****"),
            "pool_class": engine.pool.__class__.__name__,
            "status": "healthy",
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


def close_engine():
    """
    Close the engine and dispose all connections
    Call this on application shutdown
    """
    global _engine, _SessionLocal

    if _engine:
        logger.info("🔌 Disposing database connection pool...")
        _engine.dispose()
        _engine = None
        _SessionLocal = None
        logger.info("✅ Database pool disposed")


# Initialize engine on module import
try:
    get_engine()
except Exception as e:
    logger.warning(f"⚠️ Could not initialize database pool on import: {e}")
    logger.warning("   Pool will be created on first use")
