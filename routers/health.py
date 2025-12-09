"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         HEALTH ROUTER                                          ║
║                    System Health Check Endpoints                               ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Endpoints:                                                                    ║
║  - /health (basic health check)                                                ║
║  - /status (detailed status)                                                   ║
║  - /cache/stats (cache statistics)                                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter
import pymysql

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fuelanalytics/api",
    tags=["System Health"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def check_wialon_db() -> dict:
    """Check Wialon database connectivity"""
    try:
        conn = pymysql.connect(
            host=os.getenv("WIALON_DB_HOST", "localhost"),
            port=int(os.getenv("WIALON_DB_PORT", "3306")),
            user=os.getenv("WIALON_DB_USER", ""),
            password=os.getenv("WIALON_DB_PASS", ""),
            database=os.getenv("WIALON_DB_NAME", "wialon_collect"),
            connect_timeout=5,
        )
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
        return {"status": "healthy", "message": "Connected"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


def check_fuel_db() -> dict:
    """Check Fuel Analytics database connectivity"""
    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "fuel_analytics"),
            connect_timeout=5,
        )
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
        conn.close()
        return {"status": "healthy", "message": "Connected"}
    except Exception as e:
        return {"status": "unhealthy", "message": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/health")
async def health_check():
    """
    Basic health check endpoint.
    Returns 200 OK if the service is running.
    Used by load balancers and monitoring.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "5.0.0",
    }


@router.get("/status")
async def detailed_status():
    """
    Detailed status endpoint with database connectivity.
    Checks all external dependencies.
    """
    wialon_status = check_wialon_db()
    fuel_status = check_fuel_db()

    # Overall health
    all_healthy = (
        wialon_status["status"] == "healthy" and fuel_status["status"] == "healthy"
    )

    return {
        "status": "healthy" if all_healthy else "degraded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "5.0.0",
        "components": {
            "wialon_db": wialon_status,
            "fuel_db": fuel_status,
            "api": {"status": "healthy", "message": "Running"},
        },
        "uptime_info": {
            "started_at": None,  # Would need to track this globally
            "environment": os.getenv("ENVIRONMENT", "development"),
        },
    }


@router.get("/cache/stats")
async def cache_statistics():
    """
    Get cache statistics for performance monitoring.
    Shows hits, misses, and cache efficiency.
    """
    # Import here to avoid circular imports
    try:
        from database import cache_manager

        if hasattr(cache_manager, "get_stats"):
            stats = cache_manager.get_stats()
        else:
            # Estimate from cache
            stats = {
                "total_keys": len(getattr(cache_manager, "_cache", {})),
                "hit_rate": "N/A",
                "miss_rate": "N/A",
            }

        return {
            "status": "success",
            "cache": stats,
        }
    except Exception as e:
        logger.warning(f"Cache stats error: {e}")
        return {
            "status": "success",
            "cache": {
                "message": "Cache statistics not available",
                "error": str(e),
            },
        }
