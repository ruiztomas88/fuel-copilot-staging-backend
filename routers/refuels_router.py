"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         REFUELS ROUTER v5.6.0                                  ║
║                    Refuel Events & Theft Analysis                              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Endpoints:
- GET /refuels - All refuel events
- GET /refuels/analytics - Advanced refuel analytics
- GET /theft-analysis - Fuel theft detection
- GET /export/refuels - Export refuels to CSV
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from database import db
from observability import logger

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Refuels"])


class RefuelEvent(BaseModel):
    """Refuel event model"""

    truck_id: str
    timestamp: datetime
    gallons_added: float
    liters_added: float
    fuel_before_pct: float
    fuel_after_pct: float
    location: Optional[str] = None


@router.get("/refuels", response_model=List[RefuelEvent])
async def get_all_refuels(
    days: int = Query(7, ge=1, le=30, description="Days of refuel history (1-30)"),
    truck_id: Optional[str] = Query(None, description="Filter by truck ID"),
):
    """
    Get all refuel events for the fleet.

    Args:
        days: Number of days of history (default 7, max 30)
        truck_id: Filter by specific truck (optional)
    """
    try:
        if truck_id:
            refuels = db.get_refuel_history(truck_id, days)
        else:
            refuels = db.get_all_refuels(days)

        return refuels
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching refuels: {str(e)}")


@router.get("/refuels/analytics")
async def get_refuel_analytics(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
):
    """
    Advanced Refuel Analytics with caching.

    Includes:
    - Refuel events with precise gallons
    - Pattern analysis (hourly, daily)
    - Cost tracking
    - Anomaly detection
    - Per-truck summaries
    """
    try:
        from cache_service import get_cache

        cache = await get_cache()
        cache_key = f"refuel:analytics:{days}d"
        cached = await cache.get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        try:
            from database_mysql import get_advanced_refuel_analytics
        except ImportError:
            from .database_mysql import get_advanced_refuel_analytics

        analytics = get_advanced_refuel_analytics(days_back=days)

        await cache.set(cache_key, analytics, ttl=60)
        return JSONResponse(content=analytics)
    except Exception as e:
        logger.error(f"Error in refuel analytics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching refuel analytics: {str(e)}"
        )


@router.get("/theft-analysis")
async def get_theft_analysis(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    algorithm: str = Query(
        "advanced",
        description="Algorithm: 'advanced' (v4.1 with trip correlation) or 'legacy'",
    ),
):
    """
    ADVANCED Fuel Theft Detection & Analysis.

    Sophisticated multi-signal theft detection:
    - Fuel level analysis (drops, recovery patterns)
    - Trip/movement correlation from Wialon
    - Time pattern analysis (night, weekends)
    - Sensor health scoring
    - ML-style confidence scoring

    Returns events classified as:
    - ROBO CONFIRMADO: High confidence theft (>85%)
    - ROBO SOSPECHOSO: Possible theft (60-85%)
    - CONSUMO NORMAL: Fuel drop during active trip
    - PROBLEMA DE SENSOR: Sensor glitch with recovery
    """
    try:
        from cache_service import get_cache

        cache = await get_cache()
        cache_key = f"theft:analysis:{algorithm}:{days}d"
        cached = await cache.get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        if algorithm == "advanced":
            try:
                from theft_detection_engine import analyze_fuel_drops_advanced

                analysis = analyze_fuel_drops_advanced(days_back=days)
            except Exception as e:
                logger.warning(
                    f"Advanced algorithm failed, falling back to legacy: {e}"
                )
                try:
                    from database_mysql import get_fuel_theft_analysis
                except ImportError:
                    from .database_mysql import get_fuel_theft_analysis
                analysis = get_fuel_theft_analysis(days_back=days)
        else:
            try:
                from database_mysql import get_fuel_theft_analysis
            except ImportError:
                from .database_mysql import get_fuel_theft_analysis
            analysis = get_fuel_theft_analysis(days_back=days)

        await cache.set(cache_key, analysis, ttl=60)
        return JSONResponse(content=analysis)
    except Exception as e:
        logger.error(f"Error in theft analysis: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching theft analysis: {str(e)}"
        )


@router.get("/export/refuels")
async def export_refuels(
    days: int = Query(7, ge=1, le=90, description="Days of history"),
    format: str = Query("csv", description="Export format: csv or json"),
):
    """Export refuel events to CSV or JSON."""
    try:
        refuels = db.get_all_refuels(days)

        if format == "json":
            return JSONResponse(content=refuels)

        # CSV export
        import csv
        import io

        output = io.StringIO()
        if refuels:
            writer = csv.DictWriter(output, fieldnames=refuels[0].keys())
            writer.writeheader()
            writer.writerows(refuels)

        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename=refuels_{days}d.csv"
            },
        )
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error exporting refuels: {str(e)}"
        )
