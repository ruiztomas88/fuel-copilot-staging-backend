"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         AUTHENTICATION ROUTER                                  ║
║                    JWT Login, Refresh, User Info Endpoints                     ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Endpoints:                                                                    ║
║  - POST /auth/login    → Authenticate and get JWT token                        ║
║  - GET  /auth/me       → Get current user info                                 ║
║  - POST /auth/refresh  → Refresh JWT token                                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

@version 5.6.0
@date December 2025
"""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fuelAnalytics/api/auth",
    tags=["Authentication"],
)

# Import auth dependencies
try:
    from auth import (
        USERS_DB,
        Token,
        TokenData,
        UserLogin,
        authenticate_user,
        create_access_token,
        require_auth,
    )
except ImportError:
    from ..auth import (
        USERS_DB,
        Token,
        TokenData,
        UserLogin,
        authenticate_user,
        create_access_token,
        require_auth,
    )

ACCESS_TOKEN_EXPIRE_HOURS = 24


@router.post("/login", response_model=Token)
async def login(credentials: UserLogin):
    """
    Authenticate user and return JWT token.

    Credentials:
    - admin / FuelAdmin2025! (super_admin - all carriers)
    - skylord / Skylord2025! (carrier_admin - skylord only)
    - skylord_viewer / SkylordView2025 (viewer - skylord read-only)
    """
    logger.info(
        f"🔍 Login endpoint received: username={repr(credentials.username)}, password_length={len(credentials.password)}"
    )
    logger.info(f"   Password first 10 chars: {repr(credentials.password[:10])}")
    logger.info(f"   Password last 4 chars: {repr(credentials.password[-4:])}")

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
async def get_current_user_info(current_user: TokenData = Depends(require_auth)):
    """Get current authenticated user info."""
    user_data = USERS_DB.get(current_user.username, {})
    return {
        "username": current_user.username,
        "name": user_data.get("name", current_user.username),
        "carrier_id": current_user.carrier_id,
        "role": current_user.role,
        "email": user_data.get("email"),
        "permissions": {
            "can_view_all_carriers": current_user.carrier_id == "*",
            "can_edit": current_user.role in ["super_admin", "carrier_admin"],
            "can_manage_users": current_user.role == "super_admin",
        },
    }


@router.post("/refresh", response_model=Token)
async def refresh_token(current_user: TokenData = Depends(require_auth)):
    """Refresh JWT token before it expires."""
    user_data = USERS_DB.get(current_user.username)
    if not user_data:
        raise HTTPException(status_code=401, detail="User not found")

    new_token = create_access_token(
        user=user_data, expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )

    return Token(
        access_token=new_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        user={
            "username": user_data["username"],
            "name": user_data["name"],
            "carrier_id": user_data["carrier_id"],
            "role": user_data["role"],
            "email": user_data.get("email"),
        },
    )
