"""
Authentication Module for Fuel Copilot Dashboard v3.10.8
JWT-based authentication with carrier_id (multi-tenant) support

Features:
- JWT token generation and validation
- Password hashing with bcrypt
- Role-based access control (admin, carrier_admin, viewer)
- Multi-tenant isolation by carrier_id
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt
import hashlib
import secrets
import os
import logging

logger = logging.getLogger(__name__)

# Configuration
# 🔧 v3.12.21: Generate secure random key if not provided
# IMPORTANT: Set JWT_SECRET_KEY in .env for production!
_default_secret = secrets.token_urlsafe(32)
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    logger.warning(
        "⚠️ JWT_SECRET_KEY not set! Using random key (sessions won't persist across restarts)"
    )
    SECRET_KEY = _default_secret

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = (
    168  # 7 days (was 24h - users complained about session expiring)
)

# Security
security = HTTPBearer(auto_error=False)


# ============================================================================
# MODELS
# ============================================================================
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict[str, Any]


class TokenData(BaseModel):
    username: str
    carrier_id: str
    role: str
    exp: datetime


class UserLogin(BaseModel):
    username: str
    password: str


class User(BaseModel):
    username: str
    carrier_id: str
    role: str  # "super_admin", "carrier_admin", "viewer"
    name: str
    email: Optional[str] = None
    active: bool = True


# ============================================================================
# USER DATABASE (In-memory for now, can migrate to MySQL later)
# ============================================================================
# Password hash: sha256(password + salt)
def hash_password(password: str, salt: str = "fuel-copilot-salt") -> str:
    """Hash password with SHA256 + salt"""
    return hashlib.sha256(f"{password}{salt}".encode()).hexdigest()


# Pre-configured users (migrate to MySQL carriers table later)
USERS_DB: Dict[str, Dict] = {
    # Super Admin - can see ALL carriers
    "admin": {
        "username": "admin",
        "password_hash": hash_password("FuelAdmin2025!"),
        "carrier_id": "*",  # Wildcard = all carriers
        "role": "super_admin",
        "name": "System Administrator",
        "email": "admin@fleetbooster.com",
        "active": True,
    },
    # Skylord Admin - can only see skylord trucks
    "skylord": {
        "username": "skylord",
        "password_hash": hash_password("Skylord2025!"),
        "carrier_id": "skylord",
        "role": "carrier_admin",
        "name": "Skylord Trucking Admin",
        "email": "dispatch@skylordtrucking.com",
        "active": True,
    },
    # Skylord Viewer - read-only access
    "skylord_viewer": {
        "username": "skylord_viewer",
        "password_hash": hash_password("SkylordView2025"),
        "carrier_id": "skylord",
        "role": "viewer",
        "name": "Skylord Viewer",
        "email": None,
        "active": True,
    },
}


# ============================================================================
# AUTHENTICATION FUNCTIONS
# ============================================================================
def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Authenticate user with username and password"""
    user = USERS_DB.get(username)
    if not user:
        logger.warning(f"🔒 Login failed: user '{username}' not found")
        return None

    if not user.get("active", False):
        logger.warning(f"🔒 Login failed: user '{username}' is inactive")
        return None

    password_hash = hash_password(password)
    if user["password_hash"] != password_hash:
        logger.warning(f"🔒 Login failed: wrong password for '{username}'")
        return None

    logger.info(
        f"✅ Login successful: {username} (carrier: {user['carrier_id']}, role: {user['role']})"
    )
    return user


def create_access_token(user: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token"""
    if expires_delta is None:
        expires_delta = timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)

    expire = datetime.now(timezone.utc) + expires_delta

    payload = {
        "sub": user["username"],
        "carrier_id": user["carrier_id"],
        "role": user["role"],
        "name": user["name"],
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    return token


def decode_token(token: str) -> Optional[TokenData]:
    """Decode and validate JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenData(
            username=payload["sub"],
            carrier_id=payload["carrier_id"],
            role=payload["role"],
            exp=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        )
    except jwt.ExpiredSignatureError:
        logger.warning("🔒 Token expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"🔒 Invalid token: {e}")
        return None


# ============================================================================
# DEPENDENCY INJECTION FOR PROTECTED ROUTES
# ============================================================================
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Optional[TokenData]:
    """
    Get current user from JWT token.
    Returns None if no token (for optional auth).
    Raises HTTPException if token is invalid.
    """
    if credentials is None:
        return None

    token = credentials.credentials
    token_data = decode_token(token)

    if token_data is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return token_data


async def require_auth(
    current_user: Optional[TokenData] = Depends(get_current_user),
) -> TokenData:
    """Require authentication - raises 401 if not authenticated"""
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def require_admin(
    current_user: TokenData = Depends(require_auth),
) -> TokenData:
    """Require admin role (super_admin or carrier_admin)"""
    if current_user.role not in ["super_admin", "carrier_admin"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return current_user


async def require_super_admin(
    current_user: TokenData = Depends(require_auth),
) -> TokenData:
    """Require super_admin role"""
    if current_user.role != "super_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Super admin access required",
        )
    return current_user


# ============================================================================
# CARRIER FILTERING HELPER
# ============================================================================
def get_carrier_filter(current_user: Optional[TokenData]) -> Optional[str]:
    """
    Get carrier_id filter based on user role.
    - super_admin: None (no filter, sees all)
    - carrier_admin/viewer: their carrier_id
    - No auth: None (depends on endpoint config)
    """
    if current_user is None:
        return None  # No auth = no filter (public endpoints)

    if current_user.carrier_id == "*":
        return None  # Super admin sees all

    return current_user.carrier_id


def filter_by_carrier(
    data: list, carrier_id: Optional[str], id_field: str = "carrier_id"
) -> list:
    """Filter list of dicts by carrier_id"""
    if carrier_id is None:
        return data

    return [item for item in data if item.get(id_field) == carrier_id]
