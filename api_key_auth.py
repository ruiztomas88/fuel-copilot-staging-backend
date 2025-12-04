"""
API Key Authentication Module v3.12.21
Implements API key-based authentication for integrations

Addresses audit item #33: API Key authentication

Features:
- Generate secure API keys with prefix for identification
- Store key hashes (not plaintext) in database
- Role-based permissions per key
- Rate limiting per key
- Expiration support
"""

import os
import hashlib
import secrets
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from contextlib import contextmanager

import pymysql
from pymysql.cursors import DictCursor
from fastapi import Request, HTTPException, status

logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE CONNECTION (shared with user_management)
# =============================================================================
def _get_db_config() -> Dict:
    """Get database configuration from environment."""
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "fuel_admin"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "fuel_copilot"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": True,
    }


@contextmanager
def get_db_connection():
    """Get database connection with automatic cleanup."""
    conn = None
    try:
        conn = pymysql.connect(**_get_db_config())
        yield conn
    finally:
        if conn:
            conn.close()


# =============================================================================
# API KEY DATA CLASS
# =============================================================================
@dataclass
class APIKeyRecord:
    """API Key record from database."""

    id: int
    key_prefix: str
    name: str
    description: Optional[str]
    carrier_id: Optional[str]
    user_id: Optional[str]
    role: str
    scopes: Optional[List[str]]
    rate_limit_per_minute: int
    rate_limit_per_day: int
    is_active: bool
    last_used_at: Optional[datetime]
    usage_count: int
    expires_at: Optional[datetime]
    created_at: Optional[datetime]
    created_by: Optional[str]

    @property
    def is_expired(self) -> bool:
        """Check if key is expired."""
        if not self.expires_at:
            return False
        return datetime.now(timezone.utc) > self.expires_at.replace(tzinfo=timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (safe for API response)."""
        return {
            "id": self.id,
            "key_prefix": self.key_prefix,
            "name": self.name,
            "description": self.description,
            "carrier_id": self.carrier_id,
            "role": self.role,
            "scopes": self.scopes,
            "rate_limit_per_minute": self.rate_limit_per_minute,
            "rate_limit_per_day": self.rate_limit_per_day,
            "is_active": self.is_active,
            "is_expired": self.is_expired,
            "last_used_at": (
                self.last_used_at.isoformat() if self.last_used_at else None
            ),
            "usage_count": self.usage_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# API KEY MANAGER
# =============================================================================
class APIKeyManager:
    """
    Database-backed API key management.

    API keys are stored as SHA-256 hashes. The actual key is only
    shown once when created.
    """

    # Key format: fba_<prefix>_<secret> (fba = FleetBooster API)
    KEY_PREFIX = "fba"

    def __init__(self):
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Create api_keys table if it doesn't exist."""
        # Table already created in migrations/optimize_database_v3_12_21.sql
        pass

    @staticmethod
    def generate_key() -> tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            tuple: (full_key, key_hash, key_prefix)

        Example key: fba_abc12345_x9Kj2mNpQrStUvWx...
        """
        prefix = secrets.token_hex(4)  # 8 chars
        secret = secrets.token_urlsafe(32)  # ~43 chars

        full_key = f"fba_{prefix}_{secret}"
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()

        return full_key, key_hash, prefix

    @staticmethod
    def hash_key(api_key: str) -> str:
        """Hash an API key for lookup."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================
    def create_key(
        self,
        name: str,
        description: Optional[str] = None,
        carrier_id: Optional[str] = None,
        user_id: Optional[str] = None,
        role: str = "viewer",
        scopes: Optional[List[str]] = None,
        rate_limit_per_minute: int = 60,
        rate_limit_per_day: int = 10000,
        expires_in_days: Optional[int] = None,
        created_by: Optional[str] = None,
    ) -> Optional[tuple[str, Dict]]:
        """
        Create a new API key.

        Returns:
            tuple: (full_key, key_info_dict) or None on error

        IMPORTANT: The full_key is only returned once! Store it securely.
        """
        full_key, key_hash, key_prefix = self.generate_key()

        expires_at = None
        if expires_in_days:
            expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

        scopes_json = None
        if scopes:
            import json

            scopes_json = json.dumps(scopes)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO api_keys (
                            key_hash, key_prefix, name, description,
                            carrier_id, user_id, role, scopes,
                            rate_limit_per_minute, rate_limit_per_day,
                            expires_at, created_by
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            key_hash,
                            key_prefix,
                            name,
                            description,
                            carrier_id,
                            user_id,
                            role,
                            scopes_json,
                            rate_limit_per_minute,
                            rate_limit_per_day,
                            expires_at,
                            created_by,
                        ),
                    )

                    key_id = cursor.lastrowid

                    logger.info(f"✅ Created API key: {name} (prefix: {key_prefix})")

                    return full_key, {
                        "id": key_id,
                        "key_prefix": key_prefix,
                        "name": name,
                        "role": role,
                        "carrier_id": carrier_id,
                        "expires_at": expires_at.isoformat() if expires_at else None,
                    }

        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return None

    def get_key_by_hash(self, key_hash: str) -> Optional[APIKeyRecord]:
        """Get API key record by hash."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, key_prefix, name, description,
                               carrier_id, user_id, role, scopes,
                               rate_limit_per_minute, rate_limit_per_day,
                               is_active, last_used_at, usage_count,
                               expires_at, created_at, created_by
                        FROM api_keys
                        WHERE key_hash = %s
                        """,
                        (key_hash,),
                    )
                    row = cursor.fetchone()

                    if row:
                        # Parse scopes JSON
                        if row.get("scopes"):
                            import json

                            row["scopes"] = json.loads(row["scopes"])
                        return APIKeyRecord(**row)
                    return None

        except Exception as e:
            logger.error(f"Error getting API key: {e}")
            return None

    def validate_key(self, api_key: str) -> Optional[APIKeyRecord]:
        """
        Validate an API key and return its record.

        Also updates last_used_at and usage_count.
        """
        if not api_key or not api_key.startswith("fba_"):
            return None

        key_hash = self.hash_key(api_key)
        key_record = self.get_key_by_hash(key_hash)

        if not key_record:
            logger.warning(f"🔒 Invalid API key (prefix: {api_key[:12]}...)")
            return None

        if not key_record.is_active:
            logger.warning(f"🔒 Inactive API key: {key_record.name}")
            return None

        if key_record.is_expired:
            logger.warning(f"🔒 Expired API key: {key_record.name}")
            return None

        # Update usage stats
        self._record_usage(key_record.id)

        return key_record

    def _record_usage(self, key_id: int) -> None:
        """Record API key usage."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE api_keys
                        SET last_used_at = NOW(),
                            usage_count = usage_count + 1
                        WHERE id = %s
                        """,
                        (key_id,),
                    )
        except Exception as e:
            logger.error(f"Error recording API key usage: {e}")

    def revoke_key(self, key_id: int) -> bool:
        """Revoke (deactivate) an API key."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "UPDATE api_keys SET is_active = 0 WHERE id = %s", (key_id,)
                    )
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error revoking API key: {e}")
            return False

    def delete_key(self, key_id: int) -> bool:
        """Permanently delete an API key."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM api_keys WHERE id = %s", (key_id,))
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting API key: {e}")
            return False

    def list_keys(
        self, carrier_id: Optional[str] = None, include_inactive: bool = False
    ) -> List[Dict]:
        """List API keys, optionally filtered by carrier."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    where_clauses = []
                    params = []

                    if carrier_id and carrier_id != "*":
                        where_clauses.append("carrier_id = %s")
                        params.append(carrier_id)

                    if not include_inactive:
                        where_clauses.append("is_active = 1")

                    where_sql = ""
                    if where_clauses:
                        where_sql = "WHERE " + " AND ".join(where_clauses)

                    cursor.execute(
                        f"""
                        SELECT id, key_prefix, name, description,
                               carrier_id, role, is_active,
                               last_used_at, usage_count,
                               expires_at, created_at
                        FROM api_keys
                        {where_sql}
                        ORDER BY created_at DESC
                        """,
                        params,
                    )
                    return list(cursor.fetchall())

        except Exception as e:
            logger.error(f"Error listing API keys: {e}")
            return []


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> APIKeyManager:
    """Get or create APIKeyManager singleton."""
    global _api_key_manager
    if _api_key_manager is None:
        _api_key_manager = APIKeyManager()
    return _api_key_manager


# =============================================================================
# FASTAPI DEPENDENCY
# =============================================================================
async def get_api_key_auth(request: Request) -> Optional[APIKeyRecord]:
    """
    FastAPI dependency for API key authentication.

    Checks for API key in:
    1. X-API-Key header
    2. api_key query parameter

    Returns APIKeyRecord if valid, None if no key provided.
    Raises HTTPException if key is invalid.
    """
    # Check header first
    api_key = request.headers.get("X-API-Key")

    # Then check query param
    if not api_key:
        api_key = request.query_params.get("api_key")

    if not api_key:
        return None

    manager = get_api_key_manager()
    key_record = manager.validate_key(api_key)

    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return key_record


def require_api_key(request: Request) -> APIKeyRecord:
    """
    FastAPI dependency that requires a valid API key.

    Unlike get_api_key_auth, this raises an exception if no key is provided.
    """
    api_key = request.headers.get("X-API-Key") or request.query_params.get("api_key")

    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    manager = get_api_key_manager()
    key_record = manager.validate_key(api_key)

    if not key_record:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired API key",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    return key_record


def require_api_key_scope(required_scope: str):
    """
    Factory for FastAPI dependency that requires a specific scope.

    Usage:
        @app.get("/sensitive", dependencies=[Depends(require_api_key_scope("admin:read"))])
    """

    async def dependency(request: Request) -> APIKeyRecord:
        key_record = require_api_key(request)

        if key_record.scopes and required_scope not in key_record.scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"API key lacks required scope: {required_scope}",
            )

        return key_record

    return dependency
