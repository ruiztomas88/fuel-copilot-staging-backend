"""
db_config.py - Configuración Centralizada de Base de Datos
═══════════════════════════════════════════════════════════════════════════════
Reemplaza credenciales hardcodeadas con variables de entorno
"""

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Cargar .env automáticamente
# ─────────────────────────────────────────────────────────────────────────────
try:
    from dotenv import load_dotenv

    for env_path in [
        Path(__file__).parent / ".env",
        Path(__file__).parent.parent / ".env",
    ]:
        if env_path.exists():
            load_dotenv(env_path)
            logger.info(f"✅ Loaded .env from {env_path}")
            break
except ImportError:
    logger.warning("⚠️ python-dotenv not installed, using system env vars only")
    pass


@dataclass
class DatabaseConfig:
    """Configuración de base de datos desde variables de entorno"""

    host: str = ""
    port: int = 3306
    user: str = ""
    password: str = ""
    database: str = ""
    charset: str = "utf8mb4"
    pool_size: int = 10
    max_overflow: int = 5
    pool_recycle: int = 3600

    def __post_init__(self):
        self.host = os.getenv("MYSQL_HOST", "localhost")
        self.port = int(os.getenv("MYSQL_PORT", "3306"))
        self.user = os.getenv("MYSQL_USER", "fuel_admin")
        self.password = os.getenv("MYSQL_PASSWORD", "")
        self.database = os.getenv("MYSQL_DATABASE", "fuel_copilot")

        if not self.password:
            if os.getenv("ENVIRONMENT") == "production":
                raise RuntimeError("🔐 MYSQL_PASSWORD requerido en producción!")
            logger.warning("⚠️ MYSQL_PASSWORD no configurado en .env")

    @property
    def connection_dict(self) -> Dict[str, Any]:
        """Dict para pymysql.connect()"""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": self.charset,
        }

    @property
    def sqlalchemy_url(self) -> str:
        """URL para SQLAlchemy"""
        return (
            f"mysql+pymysql://{self.user}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}?charset={self.charset}"
        )


# Singleton global
_config: Optional[DatabaseConfig] = None


def get_config() -> DatabaseConfig:
    """Obtener configuración singleton"""
    global _config
    if _config is None:
        _config = DatabaseConfig()
    return _config


def get_connection():
    """Conexión simple a MySQL"""
    import pymysql

    return pymysql.connect(**get_config().connection_dict)


def get_dict_connection():
    """Conexión con DictCursor"""
    import pymysql

    return pymysql.connect(
        **get_config().connection_dict, cursorclass=pymysql.cursors.DictCursor
    )


@contextmanager
def get_cursor(dict_cursor: bool = True):
    """
    Context manager para cursor con auto-commit/rollback.

    Uso:
        with get_cursor() as cursor:
            cursor.execute("SELECT * FROM trucks")
            rows = cursor.fetchall()
    """
    import pymysql

    cfg = get_config().connection_dict.copy()
    if dict_cursor:
        cfg["cursorclass"] = pymysql.cursors.DictCursor

    conn = pymysql.connect(**cfg)
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


# SQLAlchemy Engine singleton
_engine = None


def get_engine():
    """SQLAlchemy engine con connection pooling"""
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine
        from sqlalchemy.pool import QueuePool

        cfg = get_config()
        _engine = create_engine(
            cfg.sqlalchemy_url,
            poolclass=QueuePool,
            pool_size=cfg.pool_size,
            max_overflow=cfg.max_overflow,
            pool_pre_ping=True,
            pool_recycle=cfg.pool_recycle,
        )
        logger.info(
            f"✅ SQLAlchemy engine created: {cfg.host}:{cfg.port}/{cfg.database}"
        )
    return _engine


# Backward compatibility aliases
db_config = get_config()
get_db_connection = get_connection
get_db_dict_connection = get_dict_connection
get_sqlalchemy_engine = get_engine


if __name__ == "__main__":
    # Test
    print("Testing db_config...")
    config = get_config()
    print(f"Host: {config.host}")
    print(f"Database: {config.database}")
    print(f"User: {config.user}")
    print(f"Password: {'*' * len(config.password)}")

    try:
        conn = get_connection()
        print("✅ Connection successful!")
        conn.close()
    except Exception as e:
        print(f"❌ Connection failed: {e}")
