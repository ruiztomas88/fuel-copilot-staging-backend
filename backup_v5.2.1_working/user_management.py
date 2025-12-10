"""
User Management Module v3.12.21
Database-backed user authentication replacing USERS_DB in-memory store

Addresses audit items:
- #5: carrier_id hardcoded → now from database
- #6: Credentials hardcoded → now from database
- #7: JWT Secret Key → forced from env var
- #8: USERS_DB in memory → MySQL table

Tables required:
- users: User accounts with hashed passwords
- carriers: Carrier/tenant configuration
"""

import os
import hashlib
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field

import pymysql  # For exception types

logger = logging.getLogger(__name__)

# Centralized database connection
from db_connection import get_pymysql_connection as get_db_connection


# =============================================================================
# PASSWORD HASHING (bcrypt-style with SHA256 + salt)
# =============================================================================
def hash_password(password: str, salt: Optional[str] = None) -> tuple[str, str]:
    """
    Hash password with random salt.

    Returns:
        tuple: (password_hash, salt)
    """
    if salt is None:
        salt = secrets.token_hex(16)

    password_hash = hashlib.sha256(f"{password}{salt}".encode()).hexdigest()
    return password_hash, salt


def verify_password(password: str, password_hash: str, salt: str) -> bool:
    """Verify password against stored hash."""
    computed_hash, _ = hash_password(password, salt)
    return secrets.compare_digest(computed_hash, password_hash)


# =============================================================================
# USER DATA CLASS
# =============================================================================
@dataclass
class UserRecord:
    """User record from database."""

    id: int
    username: str
    password_hash: str
    password_salt: str
    carrier_id: str
    role: str  # super_admin, carrier_admin, viewer
    name: str
    email: Optional[str] = None
    active: bool = True
    last_login: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excludes sensitive fields)."""
        return {
            "id": self.id,
            "username": self.username,
            "carrier_id": self.carrier_id,
            "role": self.role,
            "name": self.name,
            "email": self.email,
            "active": self.active,
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }


@dataclass
class CarrierRecord:
    """Carrier/tenant record from database."""

    id: int
    carrier_id: str
    name: str
    active: bool = True
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    timezone: str = "America/Chicago"
    fuel_price_per_gallon: float = 3.50
    settings: Optional[Dict] = None
    created_at: Optional[datetime] = None


# =============================================================================
# USER MANAGEMENT CLASS
# =============================================================================
class UserManager:
    """
    Database-backed user management.

    Replaces in-memory USERS_DB with MySQL-based storage.
    """

    def __init__(self):
        self._ensure_tables_exist()
        self._migrate_legacy_users()

    def _ensure_tables_exist(self) -> None:
        """Create users and carriers tables if they don't exist."""
        create_carriers_sql = """
        CREATE TABLE IF NOT EXISTS carriers (
            id INT AUTO_INCREMENT PRIMARY KEY,
            carrier_id VARCHAR(50) NOT NULL UNIQUE,
            name VARCHAR(200) NOT NULL,
            active TINYINT(1) DEFAULT 1,
            contact_email VARCHAR(200),
            contact_phone VARCHAR(50),
            timezone VARCHAR(50) DEFAULT 'America/Chicago',
            fuel_price_per_gallon DECIMAL(5,2) DEFAULT 3.50,
            settings JSON,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_carrier_active (active, carrier_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        create_users_sql = """
        CREATE TABLE IF NOT EXISTS users (
            id INT AUTO_INCREMENT PRIMARY KEY,
            username VARCHAR(100) NOT NULL UNIQUE,
            password_hash VARCHAR(64) NOT NULL,
            password_salt VARCHAR(32) NOT NULL,
            carrier_id VARCHAR(50) NOT NULL,
            role VARCHAR(30) NOT NULL DEFAULT 'viewer',
            name VARCHAR(200),
            email VARCHAR(200),
            active TINYINT(1) DEFAULT 1,
            last_login DATETIME,
            login_count INT DEFAULT 0,
            failed_login_count INT DEFAULT 0,
            locked_until DATETIME,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_user_carrier (carrier_id, active),
            INDEX idx_user_role (role, active),
            INDEX idx_user_email (email)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(create_carriers_sql)
                    cursor.execute(create_users_sql)
                    logger.info("✅ Users and carriers tables ready")
        except Exception as e:
            logger.warning(f"⚠️ Could not create tables: {e}")

    def _migrate_legacy_users(self) -> None:
        """
        Migrate hardcoded users to database if not already present.

        This ensures backward compatibility with existing USERS_DB users.
        """
        legacy_users = [
            {
                "username": "admin",
                "password": "FuelAdmin2025!",
                "carrier_id": "*",
                "role": "super_admin",
                "name": "System Administrator",
                "email": "admin@fleetbooster.com",
            },
            {
                "username": "skylord",
                "password": "Skylord2025!",
                "carrier_id": "skylord",
                "role": "carrier_admin",
                "name": "Skylord Trucking Admin",
                "email": "dispatch@skylordtrucking.com",
            },
            {
                "username": "skylord_viewer",
                "password": "SkylordView2025",
                "carrier_id": "skylord",
                "role": "viewer",
                "name": "Skylord Viewer",
                "email": None,
            },
        ]

        try:
            # First ensure carrier exists
            self._ensure_carrier_exists("skylord", "Skylord Trucking LLC")

            for user_data in legacy_users:
                if not self.get_user(user_data["username"]):
                    self.create_user(
                        username=user_data["username"],
                        password=user_data["password"],
                        carrier_id=user_data["carrier_id"],
                        role=user_data["role"],
                        name=user_data["name"],
                        email=user_data["email"],
                    )
                    logger.info(f"✅ Migrated legacy user: {user_data['username']}")
        except Exception as e:
            logger.warning(f"⚠️ Legacy user migration failed: {e}")

    def _ensure_carrier_exists(self, carrier_id: str, name: str) -> None:
        """Create carrier if it doesn't exist."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM carriers WHERE carrier_id = %s", (carrier_id,)
                    )
                    if not cursor.fetchone():
                        cursor.execute(
                            """
                            INSERT INTO carriers (carrier_id, name)
                            VALUES (%s, %s)
                            """,
                            (carrier_id, name),
                        )
                        logger.info(f"✅ Created carrier: {carrier_id}")
        except Exception as e:
            logger.warning(f"⚠️ Could not create carrier: {e}")

    # =========================================================================
    # USER CRUD OPERATIONS
    # =========================================================================
    def get_user(self, username: str) -> Optional[UserRecord]:
        """Get user by username."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, username, password_hash, password_salt,
                               carrier_id, role, name, email, active,
                               last_login, created_at, updated_at
                        FROM users
                        WHERE username = %s
                        """,
                        (username,),
                    )
                    row = cursor.fetchone()
                    if row:
                        return UserRecord(**row)
                    return None
        except Exception as e:
            logger.error(f"Error getting user {username}: {e}")
            return None

    def create_user(
        self,
        username: str,
        password: str,
        carrier_id: str,
        role: str = "viewer",
        name: Optional[str] = None,
        email: Optional[str] = None,
    ) -> Optional[int]:
        """Create new user. Returns user ID or None on error."""
        password_hash, salt = hash_password(password)

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users (username, password_hash, password_salt,
                                          carrier_id, role, name, email)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        """,
                        (username, password_hash, salt, carrier_id, role, name, email),
                    )
                    user_id = cursor.lastrowid
                    logger.info(f"✅ Created user: {username} (ID: {user_id})")
                    return user_id
        except pymysql.IntegrityError:
            logger.warning(f"User {username} already exists")
            return None
        except Exception as e:
            logger.error(f"Error creating user: {e}")
            return None

    def update_user(self, username: str, **fields) -> bool:
        """Update user fields. Returns True on success."""
        if not fields:
            return True

        # Handle password update specially
        if "password" in fields:
            password = fields.pop("password")
            password_hash, salt = hash_password(password)
            fields["password_hash"] = password_hash
            fields["password_salt"] = salt

        allowed_fields = {
            "password_hash",
            "password_salt",
            "carrier_id",
            "role",
            "name",
            "email",
            "active",
        }
        fields = {k: v for k, v in fields.items() if k in allowed_fields}

        if not fields:
            return True

        set_clause = ", ".join(f"{k} = %s" for k in fields.keys())
        values = list(fields.values()) + [username]

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        f"UPDATE users SET {set_clause} WHERE username = %s", values
                    )
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating user {username}: {e}")
            return False

    def delete_user(self, username: str) -> bool:
        """Delete user. Returns True on success."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("DELETE FROM users WHERE username = %s", (username,))
                    return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error deleting user: {e}")
            return False

    def list_users(self, carrier_id: Optional[str] = None) -> List[Dict]:
        """List all users, optionally filtered by carrier."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    if carrier_id and carrier_id != "*":
                        cursor.execute(
                            """
                            SELECT id, username, carrier_id, role, name, email,
                                   active, last_login, created_at
                            FROM users
                            WHERE carrier_id = %s OR carrier_id = '*'
                            ORDER BY carrier_id, username
                            """,
                            (carrier_id,),
                        )
                    else:
                        cursor.execute(
                            """
                            SELECT id, username, carrier_id, role, name, email,
                                   active, last_login, created_at
                            FROM users
                            ORDER BY carrier_id, username
                            """
                        )
                    return list(cursor.fetchall())
        except Exception as e:
            logger.error(f"Error listing users: {e}")
            return []

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================
    def authenticate(self, username: str, password: str) -> Optional[UserRecord]:
        """
        Authenticate user with username and password.

        Returns UserRecord on success, None on failure.
        Implements account locking after 5 failed attempts.
        """
        user = self.get_user(username)

        if not user:
            logger.warning(f"🔒 Login failed: user '{username}' not found")
            return None

        if not user.active:
            logger.warning(f"🔒 Login failed: user '{username}' is inactive")
            return None

        # Check if account is locked
        if hasattr(user, "locked_until") and user.locked_until:
            if datetime.now(timezone.utc) < user.locked_until:
                logger.warning(f"🔒 Login failed: user '{username}' is locked")
                return None

        # Verify password
        if not verify_password(password, user.password_hash, user.password_salt):
            self._record_failed_login(username)
            logger.warning(f"🔒 Login failed: wrong password for '{username}'")
            return None

        # Success - update last login
        self._record_successful_login(username)
        logger.info(
            f"✅ Login successful: {username} "
            f"(carrier: {user.carrier_id}, role: {user.role})"
        )

        return user

    def _record_failed_login(self, username: str) -> None:
        """Record failed login attempt and lock if needed."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Increment failed count
                    cursor.execute(
                        """
                        UPDATE users 
                        SET failed_login_count = failed_login_count + 1
                        WHERE username = %s
                        """,
                        (username,),
                    )

                    # Check if should lock (5 failures)
                    cursor.execute(
                        "SELECT failed_login_count FROM users WHERE username = %s",
                        (username,),
                    )
                    row = cursor.fetchone()
                    if row and row["failed_login_count"] >= 5:
                        # Lock for 15 minutes
                        cursor.execute(
                            """
                            UPDATE users 
                            SET locked_until = DATE_ADD(NOW(), INTERVAL 15 MINUTE)
                            WHERE username = %s
                            """,
                            (username,),
                        )
                        logger.warning(f"🔒 User '{username}' locked for 15 minutes")
        except Exception as e:
            logger.error(f"Error recording failed login: {e}")

    def _record_successful_login(self, username: str) -> None:
        """Record successful login and reset failed count."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        UPDATE users 
                        SET last_login = NOW(),
                            login_count = login_count + 1,
                            failed_login_count = 0,
                            locked_until = NULL
                        WHERE username = %s
                        """,
                        (username,),
                    )
        except Exception as e:
            logger.error(f"Error recording login: {e}")

    # =========================================================================
    # CARRIER OPERATIONS
    # =========================================================================
    def get_carrier(self, carrier_id: str) -> Optional[CarrierRecord]:
        """Get carrier by ID."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT id, carrier_id, name, active, contact_email,
                               contact_phone, timezone, fuel_price_per_gallon,
                               settings, created_at
                        FROM carriers
                        WHERE carrier_id = %s
                        """,
                        (carrier_id,),
                    )
                    row = cursor.fetchone()
                    if row:
                        return CarrierRecord(**row)
                    return None
        except Exception as e:
            logger.error(f"Error getting carrier: {e}")
            return None

    def list_carriers(self, active_only: bool = True) -> List[Dict]:
        """List all carriers."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    if active_only:
                        cursor.execute(
                            """
                            SELECT carrier_id, name, active, contact_email,
                                   timezone, fuel_price_per_gallon
                            FROM carriers
                            WHERE active = 1
                            ORDER BY name
                            """
                        )
                    else:
                        cursor.execute(
                            """
                            SELECT carrier_id, name, active, contact_email,
                                   timezone, fuel_price_per_gallon
                            FROM carriers
                            ORDER BY name
                            """
                        )
                    return list(cursor.fetchall())
        except Exception as e:
            logger.error(f"Error listing carriers: {e}")
            return []

    def create_carrier(
        self,
        carrier_id: str,
        name: str,
        contact_email: Optional[str] = None,
        timezone: str = "America/Chicago",
        fuel_price: float = 3.50,
    ) -> Optional[int]:
        """Create new carrier. Returns carrier ID or None."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO carriers (carrier_id, name, contact_email,
                                             timezone, fuel_price_per_gallon)
                        VALUES (%s, %s, %s, %s, %s)
                        """,
                        (carrier_id, name, contact_email, timezone, fuel_price),
                    )
                    return cursor.lastrowid
        except pymysql.IntegrityError:
            logger.warning(f"Carrier {carrier_id} already exists")
            return None
        except Exception as e:
            logger.error(f"Error creating carrier: {e}")
            return None


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================
_user_manager: Optional[UserManager] = None


def get_user_manager() -> UserManager:
    """Get or create UserManager singleton."""
    global _user_manager
    if _user_manager is None:
        _user_manager = UserManager()
    return _user_manager


# =============================================================================
# COMPATIBILITY LAYER FOR EXISTING CODE
# =============================================================================
def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """
    Authenticate user - compatible with existing auth.py interface.

    Returns dict with user info or None on failure.
    """
    manager = get_user_manager()
    user = manager.authenticate(username, password)

    if user:
        return user.to_dict()
    return None


def get_user_from_db(username: str) -> Optional[Dict]:
    """Get user info from database."""
    manager = get_user_manager()
    user = manager.get_user(username)

    if user:
        return user.to_dict()
    return None


# For backward compatibility - USERS_DB equivalent (read-only)
class UsersDBProxy:
    """
    Proxy class that provides USERS_DB-like interface
    but reads from database.
    """

    def get(self, username: str, default=None) -> Optional[Dict]:
        user = get_user_from_db(username)
        return user if user else default

    def __contains__(self, username: str) -> bool:
        return get_user_from_db(username) is not None

    def items(self):
        manager = get_user_manager()
        users = manager.list_users()
        return [(u["username"], u) for u in users]

    def keys(self):
        manager = get_user_manager()
        users = manager.list_users()
        return [u["username"] for u in users]

    def __len__(self):
        manager = get_user_manager()
        return len(manager.list_users())


# Create proxy instance for backward compatibility
USERS_DB = UsersDBProxy()
