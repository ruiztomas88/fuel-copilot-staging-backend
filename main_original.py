"""
FastAPI Backend for Fuel Copilot Dashboard v3.10.8
Modern async API with WebSocket support for real-time updates

🔧 FIX v3.9.3: Migrated from deprecated @app.on_event to lifespan handlers
🆕 v3.10.8: Added JWT authentication and multi-tenant support
"""

from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    HTTPException,
    Query,
    Depends,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import asyncio
import json
import logging
import os
import pandas as pd  # For KPIs calculation
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Prometheus metrics
try:
    from prometheus_client import (
        Counter,
        Histogram,
        Gauge,
        generate_latest,
        CONTENT_TYPE_LATEST,
    )
    from prometheus_fastapi_instrumentator import Instrumentator

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("⚠️ Prometheus client not available - metrics disabled")

logger = logging.getLogger(__name__)

try:
    from .models import (
        FleetSummary,
        TruckDetail,
        HistoricalRecord,
        EfficiencyRanking,
        Alert,
        KPIData,
        HealthCheck,
        WebSocketMessage,
        RefuelEvent,
    )
    from .database import db  # CSV-based database (optimized with 30s updates)
    from .database_enhanced import (
        get_raw_sensor_history,
        get_fuel_consumption_trend,
        get_fleet_sensor_status,
    )  # NEW: Enhanced MySQL features
except ImportError:
    from models import (
        FleetSummary,
        TruckDetail,
        HistoricalRecord,
        EfficiencyRanking,
        Alert,
        KPIData,
        HealthCheck,
        WebSocketMessage,
        RefuelEvent,
    )
    from database import db  # CSV-based database (optimized with 30s updates)
    from database_enhanced import (
        get_raw_sensor_history,
        get_fuel_consumption_trend,
        get_fleet_sensor_status,
    )  # NEW: Enhanced MySQL features

# 🆕 v3.10.8: Authentication module
try:
    from .auth import (
        authenticate_user,
        create_access_token,
        decode_token,
        get_current_user,
        require_auth,
        require_admin,
        require_super_admin,
        get_carrier_filter,
        filter_by_carrier,
        Token,
        UserLogin,
        TokenData,
        User,
        USERS_DB,
    )
except ImportError:
    from auth import (
        authenticate_user,
        create_access_token,
        decode_token,
        get_current_user,
        require_auth,
        require_admin,
        require_super_admin,
        get_carrier_filter,
        filter_by_carrier,
        Token,
        UserLogin,
        TokenData,
        User,
        USERS_DB,
    )

# Redis Cache setup (optional)
try:
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from redis_cache import FuelCopilotCache, RedisCacheConfig

    # Initialize cache if Redis is enabled
    cache = None
    REDIS_ENABLED = os.getenv("REDIS_ENABLED", "false").lower() == "true"
    if REDIS_ENABLED:
        redis_host = os.getenv("REDIS_HOST", "localhost")
        redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_password = os.getenv("REDIS_PASSWORD")
        redis_ssl = os.getenv("REDIS_SSL", "false").lower() == "true"

        cache_config = RedisCacheConfig(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            ssl=redis_ssl,
            db=0,
        )
        cache = FuelCopilotCache(config=cache_config)
        logger.info(f"✅ Redis cache enabled: {redis_host}:{redis_port}")
    else:
        logger.info("ℹ️  Redis cache disabled (set REDIS_ENABLED=true to enable)")
except Exception as e:
    cache = None
    logger.warning(f"⚠️  Redis cache unavailable: {e}")


# 🔧 FIX v3.9.3: Lifespan context manager (replaces deprecated @app.on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown tasks.

    This is the modern replacement for @app.on_event("startup") and @app.on_event("shutdown").
    See: https://fastapi.tiangolo.com/advanced/events/
    """
    # Startup
    print("🚀 Fuel Copilot API v3.9.3 starting...")
    print(f"📊 Available trucks: {len(db.get_all_trucks())}")
    print("🔌 MySQL enhanced features: enabled")
    print("✅ API ready for connections")

    yield  # App runs here

    # Shutdown
    print("👋 Shutting down Fuel Copilot API")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Fuel Copilot API",
    description="""
# Fuel Copilot Fleet Management API

Real-time fleet fuel monitoring, analytics, and efficiency tracking.

## Features

- 🚛 **Fleet Monitoring**: Track all trucks in real-time
- ⛽ **Fuel Analytics**: Kalman-filtered fuel level estimation
- 📊 **Efficiency Metrics**: MPG tracking with EMA smoothing
- 🔔 **Alerts**: Automated drift, refuel, and anomaly detection
- 📈 **KPIs**: Fleet-wide performance indicators

## Data Sources

- **Wialon**: Real-time sensor data (GPS, fuel, engine)
- **MySQL**: Historical data storage and analytics
- **Kalman Filter**: AI-powered fuel level estimation

## Authentication

Currently no authentication required (internal fleet API).

## Rate Limits

No rate limits enforced. Recommended: max 10 req/s per client.
""",
    version="3.10.2",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=[
        {
            "name": "Fleet",
            "description": "Fleet-wide summary and statistics",
        },
        {
            "name": "Trucks",
            "description": "Individual truck data and history",
        },
        {
            "name": "Efficiency",
            "description": "MPG rankings and driver efficiency",
        },
        {
            "name": "Alerts",
            "description": "System alerts and notifications",
        },
        {
            "name": "KPIs",
            "description": "Key Performance Indicators",
        },
        {
            "name": "Health",
            "description": "API health and status checks",
        },
    ],
    lifespan=lifespan,  # 🔧 FIX v3.9.3: Use lifespan instead of on_event
)

# Prometheus metrics instrumentation
if PROMETHEUS_AVAILABLE:
    from prometheus_client import REGISTRY

    # Custom metrics - check if already registered to avoid duplicates on reload
    def get_or_create_counter(name, description, labels):
        """Get existing counter or create new one"""
        try:
            return Counter(name, description, labels)
        except ValueError:
            # Already registered, get from registry
            return REGISTRY._names_to_collectors.get(
                name.replace("_total", ""), REGISTRY._names_to_collectors.get(name)
            )

    def get_or_create_gauge(name, description, labels=None):
        """Get existing gauge or create new one"""
        try:
            if labels:
                return Gauge(name, description, labels)
            return Gauge(name, description)
        except ValueError:
            return REGISTRY._names_to_collectors.get(name)

    # Custom metrics (safe for reload)
    cache_hits = get_or_create_counter(
        "cache_hits_total", "Total cache hits", ["endpoint"]
    )
    cache_misses = get_or_create_counter(
        "cache_misses_total", "Total cache misses", ["endpoint"]
    )
    active_trucks = get_or_create_gauge("active_trucks", "Number of active trucks")
    fleet_alerts = get_or_create_gauge(
        "fleet_alerts_total", "Total active alerts", ["severity"]
    )

    # Setup instrumentator
    instrumentator = Instrumentator(
        should_group_status_codes=False,
        should_ignore_untemplated=True,
        should_respect_env_var=False,
        should_instrument_requests_inprogress=True,
        excluded_handlers=[],
        inprogress_name="http_requests_inprogress",
        inprogress_labels=True,
    )
    instrumentator.instrument(app).expose(
        app, endpoint="/metrics", include_in_schema=False
    )

    logger.info("✅ Prometheus metrics enabled")
else:
    logger.warning("⚠️ Prometheus metrics disabled")

# CORS configuration - allow React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "http://localhost:3001",  # Vite dev server (alternate port)
        "http://localhost:5173",  # Vite dev server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:5173",
        "https://uninterrogative-unputrefiable-maleah.ngrok-free.dev",  # ngrok tunnel
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# WEBSOCKET CONNECTION MANAGER
# ============================================================================


class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""

    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"✅ WebSocket connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            print(f"❌ WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Send message to all connected clients with robust error handling"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                logger.debug("WebSocket disconnected during broadcast")
                disconnected.append(connection)
            except RuntimeError as e:
                if "closed" in str(e).lower() or "websocket" in str(e).lower():
                    logger.debug(f"Connection closed: {e}")
                    disconnected.append(connection)
            except ConnectionResetError:
                logger.debug("Connection reset by peer")
                disconnected.append(connection)
            except Exception as e:
                logger.warning(f"Error sending to client: {e}")
                disconnected.append(connection)

        # Remove disconnected clients
        for conn in disconnected:
            if conn in self.active_connections:
                self.active_connections.remove(conn)
                logger.info(
                    f"🧹 Cleaned up dead connection. Total: {len(self.active_connections)}"
                )


manager = ConnectionManager()


# ============================================================================
# 🆕 v3.10.8: AUTHENTICATION ENDPOINTS
# ============================================================================


@app.post("/api/auth/login", response_model=Token, tags=["Authentication"])
async def login(credentials: UserLogin):
    """
    Authenticate user and return JWT token.

    Credentials:
    - admin / FuelAdmin2025! (super_admin - all carriers)
    - skylord / Skylord2025! (carrier_admin - skylord only)
    - skylord_viewer / SkylordView2025 (viewer - skylord read-only)
    """
    user = authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    from datetime import timedelta

    ACCESS_TOKEN_EXPIRE_HOURS = 24

    access_token = create_access_token(
        user=user, expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        user={
            "username": user["username"],
            "name": user["name"],
            "carrier_id": user["carrier_id"],
            "role": user["role"],
            "email": user.get("email"),
        },
    )


@app.get("/api/auth/me", tags=["Authentication"])
async def get_current_user_info(current_user: TokenData = Depends(require_auth)):
    """Get current authenticated user info."""
    user_data = USERS_DB.get(current_user.username, {})
    return {
        "username": current_user.username,
        "name": user_data.get("name", current_user.username),
        "carrier_id": current_user.carrier_id,
        "role": current_user.role,
        "email": user_data.get("email"),
        "permissions": {
            "can_view_all_carriers": current_user.carrier_id == "*",
            "can_edit": current_user.role in ["super_admin", "carrier_admin"],
            "can_manage_users": current_user.role == "super_admin",
        },
    }


@app.post("/api/auth/refresh", response_model=Token, tags=["Authentication"])
async def refresh_token(current_user: TokenData = Depends(require_auth)):
    """Refresh JWT token before it expires."""
    user_data = USERS_DB.get(current_user.username)
    if not user_data:
        raise HTTPException(status_code=401, detail="User not found")

    from datetime import timedelta

    ACCESS_TOKEN_EXPIRE_HOURS = 24

    new_token = create_access_token(
        user=user_data, expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    )

    return Token(
        access_token=new_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
        user={
            "username": user_data["username"],
            "name": user_data["name"],
            "carrier_id": user_data["carrier_id"],
            "role": user_data["role"],
            "email": user_data.get("email"),
        },
    )


# ============================================================================
# 🆕 v3.10.8: ADMIN ENDPOINTS (Super Admin Only)
# ============================================================================


@app.get("/api/admin/carriers", tags=["Admin"])
async def list_carriers(current_user: TokenData = Depends(require_super_admin)):
    """
    List all carriers (super_admin only).
    Reads from MySQL carriers table.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT carrier_id, name, contact_email, timezone, 
                       created_at, updated_at, active
                FROM carriers
                ORDER BY name
            """
                )
            )
            carriers = [dict(row._mapping) for row in result]

            # Add truck count for each carrier
            for carrier in carriers:
                count_result = conn.execute(
                    text(
                        """
                    SELECT COUNT(DISTINCT truck_id) as truck_count
                    FROM fuel_metrics
                    WHERE carrier_id = :carrier_id
                """
                    ),
                    {"carrier_id": carrier["carrier_id"]},
                )
                carrier["truck_count"] = count_result.scalar() or 0

            return {"carriers": carriers, "total": len(carriers)}
    except Exception as e:
        logger.error(f"Error listing carriers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/users", tags=["Admin"])
async def list_users(current_user: TokenData = Depends(require_super_admin)):
    """List all users (super_admin only)."""
    users = []
    for username, user_data in USERS_DB.items():
        users.append(
            {
                "username": username,
                "name": user_data["name"],
                "carrier_id": user_data["carrier_id"],
                "role": user_data["role"],
                "email": user_data.get("email"),
                "active": user_data.get("active", True),
            }
        )
    return {"users": users, "total": len(users)}


@app.get("/api/admin/stats", tags=["Admin"])
async def get_admin_stats(current_user: TokenData = Depends(require_super_admin)):
    """
    Get system-wide statistics (super_admin only).
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            # Total records
            total_records = conn.execute(
                text("SELECT COUNT(*) FROM fuel_metrics")
            ).scalar()

            # Records by carrier
            carrier_stats = conn.execute(
                text(
                    """
                SELECT carrier_id, 
                       COUNT(*) as records,
                       COUNT(DISTINCT truck_id) as trucks,
                       MIN(timestamp_utc) as first_record,
                       MAX(timestamp_utc) as last_record
                FROM fuel_metrics
                GROUP BY carrier_id
            """
                )
            )

            carriers = [dict(row._mapping) for row in carrier_stats]

            # Total refuels
            total_refuels = (
                conn.execute(text("SELECT COUNT(*) FROM refuel_events")).scalar() or 0
            )

            return {
                "total_records": total_records,
                "total_refuels": total_refuels,
                "carriers": carriers,
                "users_count": len(USERS_DB),
            }
    except Exception as e:
        logger.error(f"Error getting admin stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================


@app.get("/api/status", response_model=HealthCheck, tags=["Health"])
async def api_status():
    """Quick API status check. Returns basic health info."""
    trucks = db.get_all_trucks()
    return {
        "status": "healthy",
        "version": "3.9.5",
        "timestamp": datetime.now(),
        "trucks_available": len(trucks),
    }


@app.get("/api/cache/stats", tags=["Health"])
async def get_cache_stats():
    """
    Get Redis cache statistics and performance metrics.

    Returns cache availability, hit/miss rates, and memory usage.
    """
    if not cache:
        return {
            "available": False,
            "message": "Redis cache not configured (set REDIS_ENABLED=true)",
        }

    try:
        stats = cache.get_stats()
        return stats
    except Exception as e:
        return {"available": False, "error": str(e)}


@app.get("/api/health", response_model=HealthCheck, tags=["Health"])
async def health_check():
    """
    Comprehensive system health check.

    Checks:
    - API status
    - MySQL connection
    - Data freshness
    - Bulk insert statistics
    - WebSocket connections
    - Redis cache status
    """
    trucks = db.get_all_trucks()
    mysql_status = "connected" if db.mysql_available else "unavailable"
    cache_status = "available" if (cache and cache._available) else "unavailable"

    # Check data freshness
    try:
        fleet_summary = db.get_fleet_summary()
        data_fresh = fleet_summary.get("active_trucks", 0) > 0
    except:
        data_fresh = False

    # Get bulk handler stats if available
    bulk_stats = None
    try:
        from bulk_mysql_handler import get_bulk_handler

        handler = get_bulk_handler()
        bulk_stats = handler.get_stats()
    except:
        pass

    # Build health response
    health_data = {
        "status": (
            "healthy" if mysql_status == "connected" and data_fresh else "degraded"
        ),
        "version": "3.1.0",
        "timestamp": datetime.now(),
        "trucks_available": len(trucks),
        "mysql_status": mysql_status,
        "cache_status": cache_status,
        "data_freshness": "fresh" if data_fresh else "stale",
        "websocket_connections": len(manager.active_connections),
    }

    if bulk_stats:
        health_data["bulk_insert_stats"] = bulk_stats

    return health_data


# ============================================================================
# FLEET ENDPOINTS
# ============================================================================


@app.get("/api/fleet", response_model=FleetSummary, tags=["Fleet"])
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
        # Use CSV for all metrics (Kalman-filtered, accurate)
        summary = db.get_fleet_summary()

        # Add metadata
        summary["data_source"] = "MySQL" if db.mysql_available else "CSV"

        # Note: Fleet summary caching disabled due to schema complexity
        # Cache is used for KPIs and efficiency rankings instead

        return summary
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching fleet summary: {str(e)}"
        )


@app.get("/api/trucks", response_model=List[str], tags=["Trucks"])
async def get_all_trucks():
    """
    Get list of all available truck IDs.

    Returns a simple list of truck identifiers (e.g., ["JC1282", "NQ6975", ...]).
    """
    try:
        trucks = db.get_all_trucks()
        return trucks
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching trucks: {str(e)}")


# ============================================================================
# TRUCK DETAIL ENDPOINTS
# ============================================================================


@app.get("/api/trucks/{truck_id}", tags=["Trucks"])
async def get_truck_detail(truck_id: str):
    """
    Get detailed information for a specific truck.

    Returns complete real-time data including:
    - Fuel level (sensor and Kalman-estimated)
    - Current MPG and idle consumption
    - GPS location and speed
    - Engine status and sensor health

    🔧 FIX v3.10.3: Returns basic info if truck exists in config but has no recent data
    """
    try:
        record = db.get_truck_latest_record(truck_id)
        if not record:
            # 🔧 FIX v3.10.3: Check if truck exists in tanks.yaml config
            # If it does, return a minimal "offline" record instead of 404
            import yaml

            tanks_path = Path(__file__).parent.parent.parent / "tanks.yaml"
            if tanks_path.exists():
                with open(tanks_path, "r") as f:
                    tanks_config = yaml.safe_load(f)
                    trucks = tanks_config.get("trucks", {})
                    if truck_id in trucks:
                        # Truck exists in config but has no data - return offline status
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
                            "speed_mph": None,
                            "health_score": 50,
                            "health_category": "warning",
                            "capacity_gallons": truck_config.get(
                                "capacity_gallons", 200
                            ),
                            "capacity_liters": truck_config.get("capacity_liters", 757),
                            "message": "No recent data available for this truck",
                            "data_available": False,
                        }
            # Truck not in config either - truly not found
            raise HTTPException(status_code=404, detail=f"Truck {truck_id} not found")

        # Convert NaN to None for JSON serialization
        import pandas as pd

        clean_record = {}
        for key, value in record.items():
            if pd.isna(value):
                clean_record[key] = None
            else:
                clean_record[key] = value

        # 🔧 FIX: Add 'status' alias for frontend compatibility
        if "truck_status" in clean_record:
            clean_record["status"] = clean_record["truck_status"]

        clean_record["data_available"] = True

        return clean_record
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching truck history: {str(e)}"
        )


@app.get(
    "/api/trucks/{truck_id}/refuels", response_model=List[RefuelEvent], tags=["Trucks"]
)
async def get_truck_refuel_history(
    truck_id: str,
    days: int = Query(
        30, ge=1, le=90, description="Days of refuel history to fetch (1-90)"
    ),
):
    """
    Get refuel events history for a truck.

    Returns detected refueling events with:
    - Timestamp of the refuel
    - Gallons and liters added
    - Fuel level before and after
    """
    try:
        refuels = db.get_refuel_history(truck_id, days)

        # CRITICAL FIX: Ensure ALL refuels have truck_id before Pydantic validation
        if refuels:
            for i, refuel in enumerate(refuels):
                if "truck_id" not in refuel or not refuel.get("truck_id"):
                    logger.warning(
                        f"⚠️ Refuel #{i} for {truck_id} missing truck_id, adding it"
                    )
                    refuel["truck_id"] = truck_id

            logger.info(f"📊 Returning {len(refuels)} refuels for {truck_id}")
        else:
            logger.info(f"📭 No refuels found for {truck_id}")

        return refuels
    except Exception as e:
        logger.error(f"❌ Error in get_truck_refuel_history for {truck_id}: {e}")
        # Return empty list instead of error to prevent dashboard crash
        return []


def sanitize_nan(value):
    """Replace NaN/Inf with None for JSON serialization"""
    import math

    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


@app.get("/api/trucks/{truck_id}/history", response_model=List[HistoricalRecord])
async def get_truck_history(
    truck_id: str,
    hours: int = Query(
        24, ge=1, le=168, description="Hours of history to fetch (1-168)"
    ),
):
    """
    Get historical data for a truck

    Args:
        truck_id: Truck identifier
        hours: Number of hours of history (default 24, max 168)

    Returns:
        List of historical data points
    """
    try:
        records = db.get_truck_history(truck_id, hours)
        if not records:
            raise HTTPException(
                status_code=404, detail=f"No history found for {truck_id}"
            )

        # Convert to HistoricalRecord models with NaN sanitization
        history = []
        for rec in records:
            history.append(
                {
                    "timestamp": rec.get("timestamp"),
                    "mpg": sanitize_nan(rec.get("mpg_current")),
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


# ============================================================================
# EFFICIENCY & RANKINGS
# ============================================================================


@app.get("/api/efficiency", response_model=List[EfficiencyRanking], tags=["Efficiency"])
async def get_efficiency_rankings():
    """
    Get efficiency rankings for all active trucks.

    Returns trucks sorted by efficiency score:
    - MPG score (60% weight)
    - Idle score (40% weight)

    Results are cached for 5 minutes when Redis is enabled.
    """
    try:
        # Try cache first
        cache_key = "efficiency:rankings:1"
        if cache and cache._available:
            try:
                cached = cache._redis.get(cache_key)
                if cached:
                    logger.info("⚡ Efficiency rankings from cache (5min TTL)")
                    if PROMETHEUS_AVAILABLE:
                        cache_hits.labels(endpoint="efficiency").inc()
                    return json.loads(cached)
                else:
                    logger.info("💨 Efficiency rankings cache miss - computing...")
                    if PROMETHEUS_AVAILABLE:
                        cache_misses.labels(endpoint="efficiency").inc()
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

        rankings = db.get_efficiency_rankings()

        # Add rank numbers
        for i, ranking in enumerate(rankings, 1):
            ranking["rank"] = i

        # Cache the result
        if cache and cache._available:
            try:
                cache._redis.setex(cache_key, 300, json.dumps(rankings))  # 5 minutes
                logger.info("💾 Efficiency rankings cached for 5 minutes")
            except Exception as e:
                logger.warning(f"Cache write error: {e}")

        return rankings
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching efficiency rankings: {str(e)}"
        )


# ============================================================================
# REFUELS
# ============================================================================


@app.get("/api/refuels", response_model=List[RefuelEvent])
async def get_all_refuels(
    days: int = Query(
        7, ge=1, le=30, description="Days of refuel history to fetch (1-30)"
    ),
    truck_id: Optional[str] = Query(None, description="Filter by truck ID"),
):
    """
    Get all refuel events for the fleet

    Args:
        days: Number of days of history (default 7, max 30)
        truck_id: Filter by specific truck (optional)

    Returns:
        List of refuel events sorted by timestamp (most recent first)
    """
    try:
        # If truck_id specified, get refuels for that truck only
        if truck_id:
            refuels = db.get_refuel_history(truck_id, days)
        else:
            # Get refuels for all trucks
            refuels = db.get_all_refuels(days)

        return refuels
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching refuels: {str(e)}")


@app.get("/api/refuels/analytics", tags=["Refuels"])
async def get_refuel_analytics(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze")
):
    """
    🆕 v3.10.3: Advanced Refuel Analytics

    Comprehensive refuel intelligence:
    - Refuel events with precise gallons
    - Pattern analysis (hourly, daily)
    - Cost tracking
    - Anomaly detection
    - Per-truck summaries
    """
    try:
        try:
            from .database_mysql import get_advanced_refuel_analytics
        except ImportError:
            from database_mysql import get_advanced_refuel_analytics

        analytics = get_advanced_refuel_analytics(days_back=days)
        return JSONResponse(content=analytics)
    except Exception as e:
        logger.error(f"Error in refuel analytics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching refuel analytics: {str(e)}"
        )


@app.get("/api/theft-analysis", tags=["Security"])
async def get_theft_analysis(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze")
):
    """
    🆕 v3.10.3: Fuel Theft Detection & Analysis

    Detects suspicious fuel level drops:
    - Sudden drops when truck is off
    - Overnight siphoning patterns
    - Tank leak detection
    - Sensor manipulation detection

    Returns events ranked by confidence level
    """
    try:
        try:
            from .database_mysql import get_fuel_theft_analysis
        except ImportError:
            from database_mysql import get_fuel_theft_analysis

        analysis = get_fuel_theft_analysis(days_back=days)
        return JSONResponse(content=analysis)
    except Exception as e:
        logger.error(f"Error in theft analysis: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching theft analysis: {str(e)}"
        )


# ============================================================================
# ALERTS
# ============================================================================


@app.get("/api/alerts", response_model=List[Alert], tags=["Alerts"])
async def get_alerts(
    severity: Optional[str] = Query(
        None, description="Filter by severity (critical, warning, info)"
    ),
    truck_id: Optional[str] = Query(None, description="Filter by truck ID"),
):
    """
    Get active alerts for fleet.

    Alerts include drift warnings, offline trucks, and anomalies.
    Can be filtered by severity level or specific truck.
    """
    try:
        alerts = db.get_alerts()

        # Apply filters
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]

        if truck_id:
            alerts = [a for a in alerts if a["truck_id"] == truck_id]

        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alerts: {str(e)}")


# ============================================================================
# KPIS (FINANCIAL)
# ============================================================================


@app.get("/api/kpis", tags=["KPIs"])
async def get_kpis(
    days: int = Query(1, ge=1, le=90, description="Number of days to analyze")
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
        # Validate days parameter
        if days < 1:
            days = 1
        elif days > 90:
            days = 90

        # Try cache first
        cache_key = f"kpis:fleet:{days}d"
        if cache and cache._available:
            try:
                cached = cache._redis.get(cache_key)
                if cached:
                    logger.info(f"⚡ KPIs from cache ({days}d)")
                    if PROMETHEUS_AVAILABLE:
                        cache_hits.labels(endpoint="kpis").inc()
                    return json.loads(cached)
                else:
                    logger.info(f"💨 KPIs cache miss - computing for {days}d...")
                    if PROMETHEUS_AVAILABLE:
                        cache_misses.labels(endpoint="kpis").inc()
            except Exception as e:
                logger.warning(f"Cache read error: {e}")

        # 🆕 Use optimized MySQL function
        from database_mysql import get_kpi_summary

        kpi_data = get_kpi_summary(days_back=days)

        # Cache the result (shorter TTL for daily, longer for weekly/monthly)
        cache_ttl = 60 if days == 1 else 300  # 1 min for daily, 5 min for longer
        if cache and cache._available:
            try:
                cache._redis.setex(cache_key, cache_ttl, json.dumps(kpi_data))
                logger.info(f"💾 KPIs cached for {cache_ttl}s")
            except Exception as e:
                logger.warning(f"Cache write error: {e}")

        return kpi_data

    except Exception as e:
        logger.error(f"Error fetching KPIs: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching KPIs: {str(e)}")


# ============================================================================
# LOSS ANALYSIS (ROOT CAUSE)
# ============================================================================


@app.get("/api/loss-analysis")
async def get_loss_analysis(days: int = 1):
    """
    🆕 v3.9.0: Fuel Loss Analysis by Root Cause

    Analyzes fuel consumption losses and classifies them into:
    1. EXCESSIVE IDLE (~50%): Engine running while stopped
    2. HIGH ALTITUDE (~25%): Efficiency loss from altitude > 3000ft
    3. MECHANICAL/DRIVING (~25%): Other inefficiencies

    Args:
        days: Analysis period (1=today, 7=week, 30=month)

    Returns:
        Summary with total losses by cause and per-truck breakdown
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


# ============================================================================
# 🚀 ANALYTICS v3.10.0: World-Class Fleet Intelligence
# ============================================================================


@app.get("/api/analytics/driver-scorecard")
async def get_driver_scorecard_endpoint(
    days: int = Query(default=7, ge=1, le=30, description="Days to analyze")
):
    """
    🆕 v3.10.0: Comprehensive Driver Scorecard System

    Returns multi-dimensional driver scores based on:
    - Speed Optimization (55-65 mph optimal)
    - RPM Discipline (1200-1600 optimal)
    - Idle Management (vs fleet average)
    - Fuel Consistency (consumption variability)
    - MPG Performance (vs 6.5 baseline)

    Returns:
        Driver rankings with overall score, grade (A+/A/B/C/D), and breakdown
    """
    try:
        from database_mysql import get_driver_scorecard

        result = get_driver_scorecard(days_back=days)
        return result

    except Exception as e:
        logger.error(f"Error in driver scorecard: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error in driver scorecard: {str(e)}"
        )


@app.get("/api/analytics/enhanced-kpis")
async def get_enhanced_kpis_endpoint(
    days: int = Query(default=1, ge=1, le=30, description="Days to analyze")
):
    """
    🆕 v3.10.0: Enhanced KPI Dashboard with Fleet Health Index

    Provides comprehensive financial intelligence:
    - Fleet Health Index (composite score 0-100)
    - Fuel cost breakdown (moving vs idle vs inefficiency)
    - ROI and cost-per-mile analysis
    - Savings opportunity matrix
    - Monthly/annual projections

    Returns:
        Complete KPI dashboard with actionable insights
    """
    try:
        from database_mysql import get_enhanced_kpis

        result = get_enhanced_kpis(days_back=days)
        return result

    except Exception as e:
        logger.error(f"Error in enhanced KPIs: {e}")
        raise HTTPException(status_code=500, detail=f"Error in enhanced KPIs: {str(e)}")


@app.get("/api/analytics/enhanced-loss-analysis")
async def get_enhanced_loss_analysis_endpoint(
    days: int = Query(default=1, ge=1, le=30, description="Days to analyze")
):
    """
    🆕 v3.10.0: Enhanced Loss Analysis with Root Cause Intelligence

    Provides detailed breakdown of fuel losses:
    - EXCESSIVE IDLE: Detailed by patterns and impact
    - HIGH ALTITUDE: Route-based analysis
    - RPM ABUSE: High RPM driving patterns
    - OVERSPEEDING: Speed profile analysis
    - THERMAL: Coolant temperature issues

    Includes actionable insights with priority and expected ROI

    Returns:
        Comprehensive loss analysis with recommendations
    """
    try:
        from database_mysql import get_enhanced_loss_analysis

        result = get_enhanced_loss_analysis(days_back=days)
        return result

    except Exception as e:
        logger.error(f"Error in enhanced loss analysis: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error in enhanced loss analysis: {str(e)}"
        )


# ============================================================================
# WEBSOCKET FOR REAL-TIME UPDATES
# ============================================================================


@app.websocket("/ws/updates")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates with intelligent diff

    Only sends changes instead of full data every time
    Reduces bandwidth and improves dashboard performance

    Features:
    - Sends full data on first connection
    - Sends only changes (diffs) on subsequent updates
    - Detects new/removed trucks
    - Tracks alert changes
    - Robust error handling and task cleanup
    """
    await manager.connect(websocket)

    update_task = None
    receive_task = None
    shutdown_event = asyncio.Event()

    # Track previous state for diff calculation
    previous_fleet = None
    previous_alerts = None

    try:
        # Create a task for sending periodic updates
        async def send_updates():
            nonlocal previous_fleet, previous_alerts

            first_update = True
            consecutive_errors = 0
            max_consecutive_errors = 3

            while not shutdown_event.is_set():
                try:
                    fleet_summary = db.get_fleet_summary()
                    alerts = db.get_alerts()

                    # On first update, send full data
                    if first_update or previous_fleet is None:
                        message = {
                            "type": "fleet_update",
                            "update_type": "full",
                            "data": {"fleet": fleet_summary, "alerts": alerts},
                            "timestamp": datetime.now().isoformat(),
                        }
                        previous_fleet = fleet_summary
                        previous_alerts = alerts
                        first_update = False
                    else:
                        # Calculate diff for subsequent updates
                        fleet_changes = calculate_fleet_diff(
                            previous_fleet, fleet_summary
                        )
                        alert_changes = calculate_alert_diff(previous_alerts, alerts)

                        # Only send if there are changes
                        if fleet_changes or alert_changes:
                            message = {
                                "type": "fleet_update",
                                "update_type": "diff",
                                "changes": {
                                    "fleet": fleet_changes,
                                    "alerts": alert_changes,
                                },
                                "timestamp": datetime.now().isoformat(),
                            }
                        else:
                            # No changes, send heartbeat only
                            message = {
                                "type": "heartbeat",
                                "timestamp": datetime.now().isoformat(),
                            }

                        previous_fleet = fleet_summary
                        previous_alerts = alerts

                    # Send message with error handling
                    try:
                        await websocket.send_json(message)
                        consecutive_errors = 0  # Reset on success
                    except (WebSocketDisconnect, RuntimeError) as e:
                        logger.info(f"WebSocket disconnected during send: {e}")
                        break
                    except Exception as e:
                        consecutive_errors += 1
                        logger.error(
                            f"Error sending WebSocket message ({consecutive_errors}/{max_consecutive_errors}): {e}"
                        )
                        if consecutive_errors >= max_consecutive_errors:
                            logger.error(
                                "Max consecutive errors reached, stopping updates"
                            )
                            break

                    # Wait for next update or shutdown
                    try:
                        await asyncio.wait_for(shutdown_event.wait(), timeout=30.0)
                        break  # Shutdown requested
                    except asyncio.TimeoutError:
                        continue  # Continue with next update

                except asyncio.CancelledError:
                    logger.info("Send updates task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Unexpected error in send_updates: {e}")
                    consecutive_errors += 1
                    if consecutive_errors >= max_consecutive_errors:
                        break
                    await asyncio.sleep(5)  # Backoff on error

        # Create a task for receiving messages (pings)
        async def receive_messages():
            nonlocal previous_fleet

            while not shutdown_event.is_set():
                try:
                    data = await websocket.receive_text()
                    try:
                        message = json.loads(data)
                    except json.JSONDecodeError:
                        logger.warning("Invalid JSON received from WebSocket client")
                        continue

                    # Respond to ping with pong
                    if message.get("type") == "ping":
                        try:
                            await websocket.send_json({"type": "pong"})
                        except Exception as e:
                            logger.warning(f"Failed to send pong: {e}")
                            break

                    # Handle force full update request
                    elif message.get("type") == "request_full_update":
                        previous_fleet = None  # Force full update on next cycle

                except WebSocketDisconnect:
                    logger.info("WebSocket disconnected")
                    break
                except asyncio.CancelledError:
                    logger.info("Receive messages task cancelled")
                    break
                except Exception as e:
                    logger.error(f"Error receiving message: {e}")
                    break

        # Run both tasks concurrently
        update_task = asyncio.create_task(send_updates())
        receive_task = asyncio.create_task(receive_messages())

        # Wait for either task to complete (indicates disconnection)
        done, pending = await asyncio.wait(
            [update_task, receive_task], return_when=asyncio.FIRST_COMPLETED
        )

        # Signal shutdown to both tasks
        shutdown_event.set()

    except WebSocketDisconnect:
        logger.info("Client disconnected normally")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
    finally:
        # Ensure shutdown is signaled
        shutdown_event.set()

        # Cancel and cleanup tasks properly
        tasks_to_cleanup = []
        if update_task and not update_task.done():
            update_task.cancel()
            tasks_to_cleanup.append(update_task)
        if receive_task and not receive_task.done():
            receive_task.cancel()
            tasks_to_cleanup.append(receive_task)

        # Wait for tasks to finish cancellation
        if tasks_to_cleanup:
            await asyncio.gather(*tasks_to_cleanup, return_exceptions=True)

        # Disconnect from manager
        manager.disconnect(websocket)
        logger.info(
            f"WebSocket cleanup complete. Active connections: {len(manager.active_connections)}"
        )


def calculate_fleet_diff(previous: Dict, current: Dict) -> Dict:
    """
    Calculate changes between previous and current fleet data
    Returns dict with changed trucks only

    🔧 FIX v3.9.1: Changed 'trucks' to 'truck_details' (correct field name)
    """
    if not previous or not current:
        return None

    changes = {
        "updated_trucks": [],
        "new_trucks": [],
        "removed_trucks": [],
        "summary_changed": False,
    }

    # 🔧 FIX: Use 'truck_details' instead of 'trucks'
    prev_trucks = {t["truck_id"]: t for t in previous.get("truck_details", [])}
    curr_trucks = {t["truck_id"]: t for t in current.get("truck_details", [])}

    # Find updated and new trucks
    for truck_id, truck_data in curr_trucks.items():
        if truck_id in prev_trucks:
            # Check if truck data changed
            if truck_data != prev_trucks[truck_id]:
                changes["updated_trucks"].append(truck_data)
        else:
            changes["new_trucks"].append(truck_data)

    # Find removed trucks
    for truck_id in prev_trucks:
        if truck_id not in curr_trucks:
            changes["removed_trucks"].append(truck_id)

    # Check summary changes (active_trucks, etc.)
    if (
        previous.get("active_trucks") != current.get("active_trucks")
        or previous.get("offline_trucks") != current.get("offline_trucks")
        or previous.get("critical_alerts") != current.get("critical_alerts")
    ):
        changes["summary_changed"] = True
        changes["summary"] = {
            "active_trucks": current.get("active_trucks"),
            "offline_trucks": current.get("offline_trucks"),
            "critical_alerts": current.get("critical_alerts"),
            "total_trucks": current.get("total_trucks"),
        }

    # Return None if no changes
    if (
        not changes["updated_trucks"]
        and not changes["new_trucks"]
        and not changes["removed_trucks"]
        and not changes["summary_changed"]
    ):
        return None

    return changes


def calculate_alert_diff(previous: List, current: List) -> Dict:
    """
    Calculate changes in alerts
    Returns dict with new and resolved alerts
    """
    if previous is None:
        return None

    prev_alert_ids = {f"{a['truck_id']}_{a['type']}" for a in previous}
    curr_alert_ids = {f"{a['truck_id']}_{a['type']}" for a in current}

    new_alerts = [
        a for a in current if f"{a['truck_id']}_{a['type']}" not in prev_alert_ids
    ]
    resolved_alerts = list(prev_alert_ids - curr_alert_ids)

    if not new_alerts and not resolved_alerts:
        return None

    return {
        "new_alerts": new_alerts,
        "resolved_alerts": resolved_alerts,
        "total_count": len(current),
    }


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.exception_handler(404)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": "Resource not found"})


@app.exception_handler(500)
async def internal_error_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ============================================================================
# STARTUP/SHUTDOWN
# ============================================================================


# ============================================================================
# SERVE FRONTEND (for production via ngrok)
# ============================================================================

# Mount static files from React build
FRONTEND_DIR = Path(__file__).parent.parent / "frontend" / "dist"
if FRONTEND_DIR.exists():
    app.mount(
        "/assets", StaticFiles(directory=str(FRONTEND_DIR / "assets")), name="assets"
    )
    print(f"📦 Serving frontend from: {FRONTEND_DIR}")


# Root route - serve frontend (lower priority than /api/health)
@app.get("/", include_in_schema=False)
async def root():
    """Serve React frontend at root"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Fuel Copilot API v3.1.0", "docs": "/api/docs"}


# Catch-all route for React Router (must be AFTER all API routes)
@app.api_route("/{full_path:path}", methods=["GET"], include_in_schema=False)
async def catch_all_routes(full_path: str):
    """Catch-all for React Router - serve index.html for non-API routes"""
    # Don't interfere with API routes
    if (
        full_path.startswith("api/")
        or full_path.startswith("ws/")
        or full_path.startswith("assets/")
    ):
        raise HTTPException(status_code=404, detail="Not found")

    # Serve index.html for all other routes (React Router handles routing)
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Frontend not found")


# ============================================================================
# NEW ENDPOINTS - Enhanced MySQL Features
# ============================================================================


@app.get("/api/trucks/{truck_id}/sensor-history")
async def get_truck_sensor_history(
    truck_id: str,
    hours: int = Query(default=48, ge=1, le=168),
    sensor_type: str = Query(default="fuel_lvl"),
):
    """
    Get raw sensor history from MySQL for specific truck
    NEW FEATURE: Access historical sensor readings
    """
    try:
        df = get_raw_sensor_history(truck_id, hours_back=hours, sensor_type=sensor_type)

        if df.empty:
            return {
                "truck_id": truck_id,
                "sensor_type": sensor_type,
                "hours": hours,
                "data": [],
                "count": 0,
            }

        return {
            "truck_id": truck_id,
            "sensor_type": sensor_type,
            "hours": hours,
            "data": df.to_dict("records"),
            "count": len(df),
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/trucks/{truck_id}/fuel-trend")
async def get_truck_fuel_trend(
    truck_id: str,
    hours: int = Query(default=48, ge=1, le=168),
):
    """
    Get fuel consumption trend analysis
    NEW FEATURE: Shows fuel level changes and consumption rate
    """
    try:
        trend = get_fuel_consumption_trend(truck_id, hours_back=hours)
        return trend

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fleet/sensor-health")
async def get_fleet_sensor_health():
    """
    Check sensor health status for entire fleet
    NEW FEATURE: Identifies trucks with sensor issues
    """
    try:
        health_data = get_fleet_sensor_status()

        # Group by status
        summary = {
            "healthy": len([t for t in health_data if t["sensor_status"] == "HEALTHY"]),
            "failed": len([t for t in health_data if t["sensor_status"] == "FAILED"]),
            "stuck": len([t for t in health_data if t["sensor_status"] == "STUCK"]),
            "sparse": len([t for t in health_data if t["sensor_status"] == "SPARSE"]),
            "total_analyzed": len(health_data),
        }

        return {"summary": summary, "trucks": health_data}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
