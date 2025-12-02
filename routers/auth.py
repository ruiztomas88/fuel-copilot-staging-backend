"""
Auth Router - Authentication endpoints
"""

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import jwt
import os
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# JWT Configuration
JWT_SECRET = os.getenv("JWT_SECRET_KEY", "your-super-secret-key-change-in-production")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_HOURS = int(os.getenv("ACCESS_TOKEN_EXPIRE_HOURS", "24"))


# Models
class UserLogin(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    user: Dict[str, Any]


# Simple user database (replace with real database in production)
USERS_DB = {
    "admin": {
        "username": "admin",
        "password": "FuelAdmin2025!",
        "name": "System Admin",
        "carrier_id": "*",
        "role": "super_admin",
        "email": "admin@fuelcopilot.com",
    },
    "skylord": {
        "username": "skylord",
        "password": "Skylord2025!",
        "name": "Skylord Admin",
        "carrier_id": "skylord",
        "role": "carrier_admin",
        "email": "admin@skylord.com",
    },
    "viewer": {
        "username": "viewer",
        "password": "ViewOnly2025!",
        "name": "Read Only User",
        "carrier_id": "skylord",
        "role": "viewer",
        "email": "viewer@skylord.com",
    },
}


def authenticate_user(username: str, password: str) -> Optional[Dict]:
    """Verify username and password."""
    user = USERS_DB.get(username)
    if user and user["password"] == password:
        return user
    return None


def create_access_token(user: Dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT token."""
    to_encode = {
        "sub": user["username"],
        "carrier_id": user["carrier_id"],
        "role": user["role"],
        "name": user["name"],
    }
    expire = datetime.utcnow() + (
        expires_delta or timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )
    to_encode["exp"] = expire
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """Authenticate user and return JWT token."""
    user = authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        user=user, expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        user={
            "username": user["username"],
            "name": user["name"],
            "carrier_id": user["carrier_id"],
            "role": user["role"],
            "email": user.get("email"),
        },
    )


@router.get("/me")
async def get_current_user():
    """Get current authenticated user info."""
    # TODO: Implement token verification
    return {"message": "Implement token verification"}


@router.post("/refresh")
async def refresh_token():
    """Refresh JWT token before it expires."""
    # TODO: Implement token refresh
    return {"message": "Implement token refresh"}
