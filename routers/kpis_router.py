"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         KPIs ROUTER v5.6.0                                     ║
║                    KPIs, Loss Analysis & Financial Metrics                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Endpoints:
- GET /kpis - Financial KPIs
- GET /loss-analysis - Fuel loss by root cause
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from observability import logger

# Try importing optional dependencies
try:
    from cache_manager import cache
except ImportError:
    cache = None

try:
    from memory_cache import memory_cache

    MEMORY_CACHE_AVAILABLE = True
except ImportError:
    MEMORY_CACHE_AVAILABLE = False
    memory_cache = None

router = APIRouter(prefix="/fuelAnalytics/api", tags=["KPIs"])


@router.get("/kpis")
async def get_kpis(
    days: int = Query(1, ge=1, le=90, description="Number of days to analyze"),
):
    """
    Get financial KPIs for fleet.

    Returns key metrics for the specified time period:
    - Total fuel consumed (gallons)
    - Idle waste (gallons and cost)
    - Fleet average MPG
    - Total distance traveled (miles)
    - Cost savings vs baseline
    """
    try:
        if days < 1:
            days = 1
        elif days > 90:
            days = 90

        cache_key = f"kpis:fleet:{days}d"

        # Try Redis cache
        if cache and hasattr(cache, "_available") and cache._available:
            try:
                cached = cache._redis.get(cache_key)
                if cached:
                    logger.info(f"⚡ KPIs from Redis cache ({days}d)")
                    return json.loads(cached)
            except Exception as e:
                logger.warning(f"Redis cache read error: {e}")

        # Try memory cache
        if MEMORY_CACHE_AVAILABLE and memory_cache:
            cached_data = memory_cache.get(cache_key)
            if cached_data:
                logger.info(f"⚡ KPIs from memory cache ({days}d)")
                return cached_data

        # Compute from database
        from database_mysql import get_kpi_summary

        kpi_data = get_kpi_summary(days_back=days)

        # Cache the result
        cache_ttl = 60 if days == 1 else 300

        if cache and hasattr(cache, "_available") and cache._available:
            try:
                cache._redis.setex(cache_key, cache_ttl, json.dumps(kpi_data))
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")

        if MEMORY_CACHE_AVAILABLE and memory_cache:
            memory_cache.set(cache_key, kpi_data, ttl=cache_ttl)

        return kpi_data

    except Exception as e:
        logger.error(f"Error fetching KPIs: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching KPIs: {str(e)}")


@router.get("/loss-analysis")
async def get_loss_analysis(
    days: int = Query(1, ge=1, le=90, description="Days to analyze"),
):
    """
    Fuel Loss Analysis by Root Cause.

    Analyzes fuel consumption losses and classifies them into:
    1. EXCESSIVE IDLE (~50%): Engine running while stopped
    2. HIGH ALTITUDE (~25%): Efficiency loss from altitude > 3000ft
    3. MECHANICAL/DRIVING (~25%): Other inefficiencies

    Returns summary with total losses by cause and per-truck breakdown.
    """
    try:
        if days < 1:
            days = 1
        elif days > 90:
            days = 90

        from database_mysql import get_loss_analysis as mysql_loss_analysis

        result = mysql_loss_analysis(days_back=days)

        return result
    except Exception as e:
        logger.error(f"Error in loss analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Error in loss analysis: {str(e)}")
