"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         HEALTH ROUTER v5.6.0                                   ║
║                    Health Check & Status Endpoints                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Endpoints:
- GET /status - Quick API status
- GET /health - Comprehensive health check
- GET /health/deep - Deep health with memory/DB pool
- GET /health/quick - Fast health for load balancers
- GET /cache/stats - Cache performance metrics
"""

from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import db
from config import settings
from observability import logger

# Try importing optional dependencies
try:
    from cache_manager import cache
except ImportError:
    cache = None

try:
    from memory_cache import get_cache_status

    MEMORY_CACHE_AVAILABLE = True
except ImportError:
    MEMORY_CACHE_AVAILABLE = False
    get_cache_status = None

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Health"])


class HealthCheck(BaseModel):
    """Health check response model"""

    status: str
    version: str
    timestamp: datetime
    trucks_available: int
    mysql_status: Optional[str] = None
    cache_status: Optional[str] = None
    data_freshness: Optional[str] = None


@router.get("/status", response_model=HealthCheck)
async def api_status():
    """Quick API status check. Returns basic health info."""
    trucks = db.get_all_trucks()
    return {
        "status": "healthy",
        "version": settings.app.version,
        "timestamp": datetime.now(),
        "trucks_available": len(trucks),
    }


@router.get("/cache/stats")
async def get_cache_stats():
    """
    Get cache statistics and performance metrics.
    Returns cache availability, hit/miss rates, and memory usage.
    """
    if MEMORY_CACHE_AVAILABLE and get_cache_status:
        try:
            stats = get_cache_status()
            return {"available": True, **stats}
        except Exception as e:
            logger.warning(f"Memory cache stats error: {e}")

    if cache and hasattr(cache, "_available") and cache._available:
        try:
            stats = cache.get_stats()
            return stats
        except Exception as e:
            return {"available": False, "error": str(e)}

    return {"available": False, "message": "Cache not configured"}


@router.get("/health", response_model=HealthCheck)
def health_check():
    """
    Comprehensive system health check.

    Checks:
    - API status
    - MySQL connection
    - Data freshness
    - Bulk insert statistics
    - Cache status
    """
    try:
        trucks = db.get_all_trucks()
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        trucks = []

    mysql_status = "connected" if db.mysql_available else "unavailable"
    cache_status = "unavailable"
    if cache and hasattr(cache, "_available"):
        cache_status = "available" if cache._available else "unavailable"

    # Check data freshness
    try:
        fleet_summary = db.get_fleet_summary()
        data_fresh = fleet_summary.get("active_trucks", 0) > 0
    except Exception as e:
        logger.warning(f"Failed to check data freshness: {e}")
        data_fresh = False

    # Get bulk handler stats if available
    bulk_stats = None
    try:
        from bulk_mysql_handler import get_bulk_handler

        handler = get_bulk_handler()
        bulk_stats = handler.get_stats()
    except Exception as e:
        logger.debug(f"Bulk handler stats not available: {e}")

    health_data = {
        "status": (
            "healthy" if mysql_status == "connected" and data_fresh else "degraded"
        ),
        "version": settings.app.version,
        "timestamp": datetime.now(),
        "trucks_available": len(trucks),
        "mysql_status": mysql_status,
        "cache_status": cache_status,
        "data_freshness": "fresh" if data_fresh else "stale",
    }

    if bulk_stats:
        health_data["bulk_insert_stats"] = bulk_stats

    return health_data


@router.get("/health/deep")
def deep_health_check():
    """
    Deep health check with memory, DB pool, and Wialon sync status.

    Checks:
    - Memory usage (alerts if >80% or >1GB)
    - Database connection pool status and latency
    - Wialon sync cache freshness
    - Detects potential deadlocks or resource exhaustion
    """
    try:
        from health_monitor import deep_health_check as run_deep_check

        report = run_deep_check()
        return JSONResponse(
            content=report.to_dict(),
            status_code=(
                200
                if report.status.value == "healthy"
                else 503 if report.status.value == "critical" else 200
            ),
        )
    except Exception as e:
        logger.error(f"Deep health check error: {e}")
        return JSONResponse(
            content={
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
            status_code=500,
        )


@router.get("/health/quick")
def quick_health_check():
    """
    Quick health check (no DB query).
    Fast endpoint for load balancer health probes.
    """
    try:
        from health_monitor import quick_status

        return quick_status()
    except Exception as e:
        return {"status": "error", "error": str(e)}
