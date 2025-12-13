"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         FLEET ROUTER v5.6.0                                    ║
║                    Fleet Summary & Truck Listing                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Endpoints:
- GET /fleet - Fleet summary statistics
- GET /trucks - List all truck IDs
- GET /fleet/sensor-health - Fleet sensor health metrics
"""

from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database import db
from observability import logger

# Try importing optional dependencies
try:
    from memory_cache import memory_cache

    MEMORY_CACHE_AVAILABLE = True
except ImportError:
    MEMORY_CACHE_AVAILABLE = False
    memory_cache = None

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Fleet"])


class TruckSummary(BaseModel):
    """Brief truck status summary"""

    truck_id: str
    status: str
    mpg: Optional[float] = None
    idle_gph: Optional[float] = None
    fuel_L: Optional[float] = None
    estimated_pct: Optional[float] = None
    estimated_gallons: Optional[float] = None
    sensor_pct: Optional[float] = None
    sensor_gallons: Optional[float] = None
    drift_pct: Optional[float] = None
    speed_mph: Optional[float] = None
    health_score: Optional[int] = None
    health_category: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None


class FleetSummary(BaseModel):
    """Fleet-wide summary statistics"""

    total_trucks: int
    active_trucks: int
    offline_trucks: int
    critical_count: int
    warning_count: int
    healthy_count: int
    avg_mpg: float
    avg_idle_gph: float
    truck_details: List[TruckSummary]
    timestamp: datetime


@router.get("/fleet", response_model=FleetSummary)
async def get_fleet_summary():
    """
    Get fleet-wide summary statistics.

    Returns aggregated metrics for the entire fleet including:
    - Total number of trucks (active and offline)
    - Average MPG and idle consumption across fleet
    - Brief status for each truck

    Data is refreshed every 30 seconds from Kalman-filtered estimates.
    """
    try:
        cache_key = "fleet_summary"

        # Try memory cache first
        if MEMORY_CACHE_AVAILABLE and memory_cache:
            cached_data = memory_cache.get(cache_key)
            if cached_data:
                logger.debug("⚡ Fleet summary from memory cache")
                return cached_data

        summary = db.get_fleet_summary()
        summary["data_source"] = "MySQL" if db.mysql_available else "CSV"

        # Cache for 30 seconds
        if MEMORY_CACHE_AVAILABLE and memory_cache:
            memory_cache.set(cache_key, summary, ttl=30)
            logger.debug("💾 Fleet summary cached for 30s")

        return summary
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching fleet summary: {str(e)}"
        )


@router.get("/trucks", response_model=List[str])
async def get_all_trucks():
    """
    Get list of all available truck IDs.
    Returns a simple list of truck identifiers.
    """
    try:
        trucks = db.get_all_trucks()
        return trucks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching trucks: {str(e)}")


@router.get("/fleet/sensor-health")
async def get_fleet_sensor_health():
    """
    Get sensor health status for the entire fleet.
    Returns calibration status, drift patterns, and sensor reliability metrics.
    """
    try:
        cache_key = "fleet_sensor_health"

        if MEMORY_CACHE_AVAILABLE and memory_cache:
            cached = memory_cache.get(cache_key)
            if cached:
                return cached

        trucks = db.get_all_trucks()
        sensor_health = []

        for truck_id in trucks:
            try:
                record = db.get_truck_latest_record(truck_id)
                if record:
                    drift = record.get("drift_pct", 0) or 0
                    sensor_health.append(
                        {
                            "truck_id": truck_id,
                            "sensor_status": (
                                "healthy"
                                if abs(drift) < 5
                                else "warning" if abs(drift) < 10 else "critical"
                            ),
                            "drift_pct": drift,
                            "last_calibration": record.get("last_calibration"),
                            "confidence": record.get("confidence_indicator", "medium"),
                        }
                    )
            except Exception as e:
                logger.warning(f"Error getting sensor health for {truck_id}: {e}")

        result = {
            "total_trucks": len(trucks),
            "healthy_sensors": len(
                [s for s in sensor_health if s["sensor_status"] == "healthy"]
            ),
            "warning_sensors": len(
                [s for s in sensor_health if s["sensor_status"] == "warning"]
            ),
            "critical_sensors": len(
                [s for s in sensor_health if s["sensor_status"] == "critical"]
            ),
            "sensors": sensor_health,
            "timestamp": datetime.now().isoformat(),
        }

        if MEMORY_CACHE_AVAILABLE and memory_cache:
            memory_cache.set(cache_key, result, ttl=60)

        return result
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching sensor health: {str(e)}"
        )
