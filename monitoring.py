"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    MONITORING & OBSERVABILITY SETUP                            ║
║                    Prometheus Metrics & Health Checks                          ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Basic monitoring setup for Fuel Copilot backend.
Provides health checks and Prometheus-compatible metrics.

Created: Dec 26, 2025
Author: Auditoría Implementation
"""

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Try to import Prometheus client
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        Info,
        generate_latest,
    )

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logger.warning("⚠️ Prometheus client not installed. Metrics disabled.")


# ═══════════════════════════════════════════════════════════════════════════════
# PROMETHEUS METRICS
# ═══════════════════════════════════════════════════════════════════════════════

if PROMETHEUS_AVAILABLE:
    # Create custom registry
    registry = CollectorRegistry()

    # Application info
    app_info = Info("fuel_copilot_app", "Application information", registry=registry)
    app_info.info(
        {
            "version": "v6.3.0",
            "environment": os.getenv("ENVIRONMENT", "production"),
            "deployment": "local",
        }
    )

    # Request metrics
    http_requests_total = Counter(
        "fuel_copilot_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
        registry=registry,
    )

    http_request_duration_seconds = Histogram(
        "fuel_copilot_http_request_duration_seconds",
        "HTTP request latency",
        ["method", "endpoint"],
        registry=registry,
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
    )

    # Database metrics
    db_connections_active = Gauge(
        "fuel_copilot_db_connections_active",
        "Number of active database connections",
        registry=registry,
    )

    db_query_duration_seconds = Histogram(
        "fuel_copilot_db_query_duration_seconds",
        "Database query duration",
        ["query_type"],
        registry=registry,
        buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0),
    )

    db_queries_total = Counter(
        "fuel_copilot_db_queries_total",
        "Total database queries",
        ["query_type", "status"],
        registry=registry,
    )

    # Cache metrics
    cache_hits_total = Counter(
        "fuel_copilot_cache_hits_total",
        "Total cache hits",
        ["cache_key"],
        registry=registry,
    )

    cache_misses_total = Counter(
        "fuel_copilot_cache_misses_total",
        "Total cache misses",
        ["cache_key"],
        registry=registry,
    )

    # Business metrics
    trucks_active = Gauge(
        "fuel_copilot_trucks_active", "Number of active trucks", registry=registry
    )

    alerts_generated_total = Counter(
        "fuel_copilot_alerts_generated_total",
        "Total alerts generated",
        ["alert_type", "severity"],
        registry=registry,
    )

    fuel_theft_detected_total = Counter(
        "fuel_copilot_fuel_theft_detected_total",
        "Total fuel theft events detected",
        registry=registry,
    )

    # Error metrics
    errors_total = Counter(
        "fuel_copilot_errors_total", "Total errors", ["error_type"], registry=registry
    )


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


async def check_database_health() -> Dict[str, Any]:
    """Check if database is accessible"""
    try:
        from database_async import health_check

        result = await health_check()
        return {
            "status": "healthy" if result.get("healthy") else "unhealthy",
            "details": result,
        }
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


async def check_cache_health() -> Dict[str, Any]:
    """Check if Redis cache is accessible"""
    try:
        from cache import cache

        if cache and cache._available:
            # Try a simple ping
            cache._redis.ping()
            return {"status": "healthy", "type": "redis"}
        else:
            return {"status": "unavailable", "type": "none"}
    except Exception as e:
        logger.error(f"Cache health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


async def get_system_metrics() -> Dict[str, Any]:
    """Get current system metrics"""
    try:
        import psutil

        # CPU and memory
        cpu_percent = psutil.cpu_percent(interval=0.1)
        memory = psutil.virtual_memory()

        # Disk usage
        disk = psutil.disk_usage("/")

        return {
            "cpu_percent": cpu_percent,
            "memory_percent": memory.percent,
            "memory_available_mb": memory.available / (1024 * 1024),
            "disk_percent": disk.percent,
            "disk_free_gb": disk.free / (1024 * 1024 * 1024),
        }
    except ImportError:
        return {"error": "psutil not installed"}
    except Exception as e:
        logger.error(f"System metrics failed: {e}")
        return {"error": str(e)}


async def comprehensive_health_check() -> Dict[str, Any]:
    """
    Comprehensive health check of all system components.
    Returns detailed status for monitoring systems.
    """
    start_time = time.time()

    # Check all components
    db_health = await check_database_health()
    cache_health = await check_cache_health()
    system_metrics = await get_system_metrics()

    # Determine overall status
    overall_healthy = db_health["status"] == "healthy" and cache_health["status"] in [
        "healthy",
        "unavailable",
    ]  # Cache is optional

    elapsed = time.time() - start_time

    return {
        "status": "healthy" if overall_healthy else "unhealthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "v6.3.0",
        "checks": {
            "database": db_health,
            "cache": cache_health,
            "system": system_metrics,
        },
        "response_time_ms": round(elapsed * 1000, 2),
    }


def get_prometheus_metrics() -> bytes:
    """Get Prometheus-formatted metrics"""
    if not PROMETHEUS_AVAILABLE:
        return b"# Prometheus not available\n"

    try:
        return generate_latest(registry)
    except Exception as e:
        logger.error(f"Error generating Prometheus metrics: {e}")
        return b"# Error generating metrics\n"


# ═══════════════════════════════════════════════════════════════════════════════
# MIDDLEWARE HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


class RequestMetrics:
    """Context manager for tracking request metrics"""

    def __init__(self, method: str, endpoint: str):
        self.method = method
        self.endpoint = endpoint
        self.start_time = None

    async def __aenter__(self):
        self.start_time = time.time()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if PROMETHEUS_AVAILABLE and self.start_time:
            duration = time.time() - self.start_time

            # Record duration
            http_request_duration_seconds.labels(
                method=self.method, endpoint=self.endpoint
            ).observe(duration)

            # Record request count
            status = "error" if exc_type else "success"
            http_requests_total.labels(
                method=self.method, endpoint=self.endpoint, status=status
            ).inc()

            # Record errors
            if exc_type:
                errors_total.labels(error_type=exc_type.__name__).inc()


# ═══════════════════════════════════════════════════════════════════════════════
# EXPORT
# ═══════════════════════════════════════════════════════════════════════════════

__all__ = [
    "PROMETHEUS_AVAILABLE",
    "comprehensive_health_check",
    "get_prometheus_metrics",
    "RequestMetrics",
    "http_requests_total",
    "http_request_duration_seconds",
    "db_connections_active",
    "db_query_duration_seconds",
    "cache_hits_total",
    "cache_misses_total",
    "trucks_active",
    "alerts_generated_total",
    "errors_total",
]
