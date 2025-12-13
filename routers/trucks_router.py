"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         TRUCKS ROUTER v5.6.0                                   ║
║                    Individual Truck Data & History                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Endpoints:
- GET /trucks/{truck_id} - Truck detail
- GET /trucks/{truck_id}/refuels - Refuel history
- GET /trucks/{truck_id}/history - Historical data
- GET /trucks/{truck_id}/sensor-history - Sensor history
- GET /trucks/{truck_id}/fuel-trend - Fuel level trend
- GET /efficiency - Efficiency rankings
"""

from datetime import datetime
from pathlib import Path
from typing import List, Optional
import math

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from database import db
from observability import logger

# Try importing optional dependencies
try:
    from cache_manager import cache
except ImportError:
    cache = None

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Trucks"])


class RefuelEvent(BaseModel):
    """Refuel event model"""

    truck_id: str
    timestamp: datetime
    gallons_added: float
    liters_added: float
    fuel_before_pct: float
    fuel_after_pct: float
    location: Optional[str] = None


class HistoricalRecord(BaseModel):
    """Historical data point"""

    timestamp: datetime
    mpg: Optional[float] = None
    idle_gph: Optional[float] = None
    fuel_percent: Optional[float] = None
    speed_mph: Optional[float] = None
    status: Optional[str] = None


class EfficiencyRanking(BaseModel):
    """Efficiency ranking model"""

    truck_id: str
    rank: int
    mpg: Optional[float] = None
    idle_gph: Optional[float] = None
    efficiency_score: float
    status: str


def sanitize_nan(value):
    """Replace NaN/Inf with None for JSON serialization"""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


@router.get("/trucks/{truck_id}")
async def get_truck_detail(truck_id: str):
    """
    Get detailed information for a specific truck.

    Returns complete real-time data including:
    - Fuel level (sensor and Kalman-estimated)
    - Current MPG and idle consumption
    - GPS location and speed
    - Engine status and sensor health
    """
    import yaml

    try:
        logger.info(f"[get_truck_detail] Fetching data for {truck_id}")
        record = db.get_truck_latest_record(truck_id)

        if not record:
            # Check if truck exists in tanks.yaml config
            tanks_path = Path(__file__).parent.parent / "tanks.yaml"
            if tanks_path.exists():
                with open(tanks_path, "r") as f:
                    tanks_config = yaml.safe_load(f)
                    trucks = tanks_config.get("trucks", {})
                    if truck_id in trucks:
                        truck_config = trucks[truck_id]
                        return {
                            "truck_id": truck_id,
                            "status": "OFFLINE",
                            "truck_status": "OFFLINE",
                            "mpg": None,
                            "idle_gph": None,
                            "fuel_L": None,
                            "estimated_pct": None,
                            "estimated_gallons": None,
                            "sensor_pct": None,
                            "sensor_gallons": None,
                            "tank_capacity_gallons": truck_config.get(
                                "capacity_gal", 300
                            ),
                            "data_age_seconds": None,
                            "message": f"Truck {truck_id} exists in fleet config but has no recent telemetry data",
                        }

            raise HTTPException(status_code=404, detail=f"Truck {truck_id} not found")

        return record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching truck data: {str(e)}"
        )


@router.get("/trucks/{truck_id}/refuels", response_model=List[RefuelEvent])
async def get_truck_refuel_history(
    truck_id: str,
    days: int = Query(30, ge=1, le=90, description="Days of refuel history (1-90)"),
):
    """Get refuel events history for a truck."""
    try:
        refuels = db.get_refuel_history(truck_id, days)

        # Ensure all refuels have truck_id
        if refuels:
            for refuel in refuels:
                if "truck_id" not in refuel or not refuel.get("truck_id"):
                    refuel["truck_id"] = truck_id

        return refuels or []
    except Exception as e:
        logger.error(f"Error in get_truck_refuel_history for {truck_id}: {e}")
        return []


@router.get("/trucks/{truck_id}/history", response_model=List[HistoricalRecord])
async def get_truck_history(
    truck_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history (1-168)"),
):
    """Get historical data for a truck."""
    try:
        records = db.get_truck_history(truck_id, hours)
        if not records:
            raise HTTPException(
                status_code=404, detail=f"No history found for {truck_id}"
            )

        history = []
        for rec in records:
            mpg_raw = sanitize_nan(rec.get("mpg_current"))
            mpg_valid = (
                mpg_raw if mpg_raw is not None and 2.5 <= mpg_raw <= 15 else None
            )

            history.append(
                {
                    "timestamp": rec.get("timestamp"),
                    "mpg": mpg_valid,
                    "idle_gph": sanitize_nan(rec.get("idle_consumption_gph")),
                    "fuel_percent": sanitize_nan(rec.get("fuel_percent")),
                    "speed_mph": sanitize_nan(rec.get("speed_mph")),
                    "status": rec.get("status"),
                }
            )

        return history
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {str(e)}")


@router.get("/trucks/{truck_id}/sensor-history")
async def get_truck_sensor_history(
    truck_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history"),
):
    """Get sensor history with drift analysis for a truck."""
    try:
        records = db.get_truck_history(truck_id, hours)
        if not records:
            return {"truck_id": truck_id, "data": [], "message": "No sensor history"}

        sensor_data = []
        for rec in records:
            sensor_data.append(
                {
                    "timestamp": rec.get("timestamp"),
                    "sensor_pct": sanitize_nan(rec.get("sensor_pct")),
                    "estimated_pct": sanitize_nan(rec.get("estimated_pct")),
                    "drift_pct": sanitize_nan(rec.get("drift_pct")),
                    "confidence": rec.get("confidence_indicator"),
                }
            )

        return {
            "truck_id": truck_id,
            "data": sensor_data,
            "hours": hours,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching sensor history: {str(e)}"
        )


@router.get("/trucks/{truck_id}/fuel-trend")
async def get_truck_fuel_trend(
    truck_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history"),
):
    """Get fuel level trend for a truck."""
    try:
        records = db.get_truck_history(truck_id, hours)
        if not records:
            return {"truck_id": truck_id, "data": [], "message": "No fuel trend data"}

        trend_data = []
        for rec in records:
            trend_data.append(
                {
                    "timestamp": rec.get("timestamp"),
                    "fuel_pct": sanitize_nan(
                        rec.get("estimated_pct") or rec.get("sensor_pct")
                    ),
                    "fuel_gallons": sanitize_nan(rec.get("estimated_gallons")),
                }
            )

        return {
            "truck_id": truck_id,
            "data": trend_data,
            "hours": hours,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching fuel trend: {str(e)}"
        )


@router.get("/efficiency", response_model=List[EfficiencyRanking])
async def get_efficiency_rankings():
    """
    Get efficiency rankings for all active trucks.

    Returns trucks sorted by efficiency score:
    - MPG score (60% weight)
    - Idle score (40% weight)
    """
    try:
        # Try cache first
        cache_key = "efficiency:rankings:1"
        if cache and hasattr(cache, "_available") and cache._available:
            try:
                cached = cache._redis.get(cache_key)
                if cached:
                    import json

                    return json.loads(cached)
            except Exception:
                pass

        fleet_data = db.get_fleet_summary()
        trucks = fleet_data.get("truck_details", [])

        # Calculate efficiency scores
        rankings = []
        for truck in trucks:
            if truck.get("status") == "OFFLINE":
                continue

            mpg = truck.get("mpg") or 0
            idle = truck.get("idle_gph") or 0

            # Score calculation (higher MPG = better, lower idle = better)
            mpg_score = min(mpg / 8.0, 1.0) * 60  # Max 60 points for MPG
            idle_score = max(0, (2.0 - idle) / 2.0) * 40  # Max 40 points for low idle

            rankings.append(
                {
                    "truck_id": truck["truck_id"],
                    "rank": 0,
                    "mpg": mpg,
                    "idle_gph": idle,
                    "efficiency_score": round(mpg_score + idle_score, 1),
                    "status": truck.get("status", "UNKNOWN"),
                }
            )

        # Sort by score descending
        rankings.sort(key=lambda x: x["efficiency_score"], reverse=True)

        # Assign ranks
        for i, r in enumerate(rankings):
            r["rank"] = i + 1

        # Cache for 5 minutes
        if cache and hasattr(cache, "_available") and cache._available:
            try:
                import json

                cache._redis.setex(cache_key, 300, json.dumps(rankings))
            except Exception:
                pass

        return rankings
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching rankings: {str(e)}"
        )
