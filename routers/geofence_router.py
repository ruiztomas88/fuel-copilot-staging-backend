"""
Geofence Router - v3.12.0
Geofencing endpoints for tracking truck zone entries/exits
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Geofencing"])


@router.get("/geofence/events")
async def get_geofence_events_endpoint(
    truck_id: Optional[str] = Query(None, description="Specific truck ID"),
    hours: int = Query(24, ge=1, le=168, description="Hours of history"),
):
    """
    Get geofence entry/exit events for trucks.

    Tracks when trucks enter or exit defined zones.
    Useful for monitoring:
    - Fuel station visits
    - Unauthorized stops
    - Route compliance
    """
    try:
        from database_mysql import get_geofence_events

        result = get_geofence_events(truck_id=truck_id, hours_back=hours)
        return result

    except Exception as e:
        logger.error(f"Geofence events error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/geofence/location-history/{truck_id}")
async def get_location_history(
    truck_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history"),
):
    """
    Get GPS location history for a truck (for map visualization).

    Returns a list of location points with timestamps,
    speed, status, and fuel level.
    """
    try:
        from database_mysql import get_truck_location_history

        result = get_truck_location_history(truck_id=truck_id, hours_back=hours)
        return {"truck_id": truck_id, "hours": hours, "locations": result}

    except Exception as e:
        logger.error(f"Location history error for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/geofence/zones")
async def get_geofence_zones():
    """
    Get list of defined geofence zones.

    Returns zone configurations including:
    - Zone ID and name
    - Type (CIRCLE, POLYGON)
    - Coordinates and radius
    - Alert settings
    """
    try:
        from database_mysql import GEOFENCE_ZONES

        zones = []
        for zone_id, zone in GEOFENCE_ZONES.items():
            zones.append(
                {
                    "zone_id": zone_id,
                    "name": zone["name"],
                    "type": zone["type"],
                    "latitude": zone.get("lat"),
                    "longitude": zone.get("lon"),
                    "radius_miles": zone.get("radius_miles"),
                    "alert_on_enter": zone.get("alert_on_enter", False),
                    "alert_on_exit": zone.get("alert_on_exit", False),
                }
            )

        return {"zones": zones, "total": len(zones)}

    except Exception as e:
        logger.error(f"Get geofence zones error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
