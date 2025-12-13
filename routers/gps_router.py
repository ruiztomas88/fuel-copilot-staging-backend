"""
GPS Tracking Router - v3.12.21
GPS positions, route history, and geofence management endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, List
import logging
from datetime import datetime
from timezone_utils import utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api", tags=["GPS"])

# In-memory storage for GPS tracking (replace with DB in production)
_gps_tracking_data: Dict[str, Dict] = {}
_geofences: Dict[str, Dict] = {}


@router.get("/gps/trucks")
async def get_gps_truck_positions():
    """
    🆕 v3.12.21: Get real-time GPS positions for all trucks.
    """
    try:
        from database import db

        trucks = db.get_all_trucks()

        positions = []
        for truck_id in trucks:
            truck_data = db.get_truck_latest_record(truck_id)
            if truck_data:
                positions.append(
                    {
                        "truck_id": truck_id,
                        "latitude": truck_data.get("latitude"),
                        "longitude": truck_data.get("longitude"),
                        "speed_mph": truck_data.get("speed_mph", 0),
                        "heading": truck_data.get("heading", 0),
                        "status": truck_data.get("status", "UNKNOWN"),
                        "last_update": truck_data.get("last_update")
                        or utc_now().isoformat(),
                        "address": _gps_tracking_data.get(truck_id, {}).get(
                            "last_address"
                        ),
                    }
                )

        return {
            "trucks": positions,
            "total": len(positions),
            "timestamp": utc_now().isoformat(),
        }
    except Exception as e:
        logger.error(f"GPS positions error: {e}")
        return {"trucks": [], "total": 0, "error": str(e)}


@router.get("/gps/truck/{truck_id}/history")
async def get_truck_route_history(
    truck_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve"),
):
    """
    🆕 v3.12.21: Get GPS route history for a specific truck.
    """
    try:
        return {
            "truck_id": truck_id,
            "period_hours": hours,
            "route": [],
            "total_distance_miles": 0,
            "stops": [],
            "geofence_events": [],
        }
    except Exception as e:
        logger.error(f"Route history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gps/geofences")
async def get_geofences():
    """
    🆕 v3.12.21: Get all configured geofences.
    """
    return {"geofences": list(_geofences.values()), "total": len(_geofences)}


@router.post("/gps/geofence")
async def create_geofence(geofence: Dict[str, Any]):
    """
    🆕 v3.12.21: Create a new geofence zone.

    Types: circle (center + radius) or polygon (list of coordinates)
    """
    import uuid

    geofence_id = f"geofence-{uuid.uuid4().hex[:8]}"
    geofence["id"] = geofence_id
    geofence["created_at"] = utc_now().isoformat()
    geofence["active"] = True

    _geofences[geofence_id] = geofence

    logger.info(f"📍 Geofence created: {geofence.get('name', geofence_id)}")
    return {"status": "created", "geofence": geofence}


@router.delete("/gps/geofence/{geofence_id}")
async def delete_geofence(geofence_id: str):
    """
    🆕 v3.12.21: Delete a geofence.
    """
    if geofence_id not in _geofences:
        raise HTTPException(status_code=404, detail="Geofence not found")

    del _geofences[geofence_id]
    return {"status": "deleted", "geofence_id": geofence_id}


@router.get("/gps/geofence/{geofence_id}/events")
async def get_geofence_events_by_id(
    geofence_id: str,
    hours: int = Query(24, ge=1, le=168),
):
    """
    🆕 v3.12.21: Get entry/exit events for a geofence.
    """
    if geofence_id not in _geofences:
        raise HTTPException(status_code=404, detail="Geofence not found")

    return {
        "geofence_id": geofence_id,
        "geofence_name": _geofences[geofence_id].get("name"),
        "period_hours": hours,
        "events": [],
        "summary": {"total_entries": 0, "total_exits": 0, "unique_trucks": 0},
    }
