"""
Health Check Endpoint and System Diagnostics
Provides detailed health status for monitoring
"""

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

import psutil
from fastapi import APIRouter, Response, status

router = APIRouter(tags=["health"])


def get_system_health() -> Dict[str, Any]:
    """Get comprehensive system health metrics"""
    cpu_percent = psutil.cpu_percent(interval=1)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "system": {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available / (1024 * 1024),
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free / (1024**3),
        },
        "health_checks": {
            "cpu_ok": cpu_percent < 90,
            "memory_ok": memory.percent < 90,
            "disk_ok": disk.percent < 90,
        },
    }


@router.get("/health")
async def health_check():
    """
    Health check endpoint
    Returns 200 if system is healthy, 503 if degraded
    """
    health = get_system_health()

    # Determine if system is healthy
    checks = health["health_checks"]
    all_healthy = all(checks.values())

    if all_healthy:
        return health
    else:
        return Response(
            content=str(health),
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@router.get("/health/detailed")
async def detailed_health():
    """Detailed health information including process info"""
    process = psutil.Process()

    health = get_system_health()
    health["process"] = {
        "pid": process.pid,
        "memory_mb": process.memory_info().rss / (1024 * 1024),
        "cpu_percent": process.cpu_percent(interval=0.1),
        "num_threads": process.num_threads(),
        "create_time": datetime.fromtimestamp(
            process.create_time(), tz=timezone.utc
        ).isoformat(),
    }

    return health


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness check - returns 200 when app is ready to serve traffic
    """
    try:
        # Add any checks needed to verify app is ready
        # e.g., database connection, cache availability, etc.
        return {"status": "ready", "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        return Response(
            content=f"Not ready: {str(e)}",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


@router.get("/health/live")
async def liveness_check():
    """
    Liveness check - returns 200 if app is alive
    Use this for Kubernetes liveness probes
    """
    return {"status": "alive", "timestamp": datetime.now(timezone.utc).isoformat()}
