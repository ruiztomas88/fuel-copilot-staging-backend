"""
Admin Router - Super Admin endpoints
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/carriers")
async def list_carriers() -> Dict[str, Any]:
    """List all carriers (super_admin only)."""
    try:
        return {"carriers": [], "total": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users")
async def list_users() -> Dict[str, Any]:
    """List all users (super_admin only)."""
    try:
        return {"users": [], "total": 0}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_admin_stats() -> Dict[str, Any]:
    """Get system-wide statistics (super_admin only)."""
    try:
        return {
            "total_records": 0,
            "total_refuels": 0,
            "carriers": [],
            "users_count": 0,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
