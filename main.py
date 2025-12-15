"""
FastAPI Backend for Fuel Copilot Dashboard v4.0.0
Modern async API with HTTP polling (WebSocket removed for simplicity)

🔧 FIX v3.9.3: Migrated from deprecated @app.on_event to lifespan handlers
🆕 v3.10.8: Added JWT authentication and multi-tenant support
🆕 v3.10.9: Removed WebSocket - dashboard uses HTTP polling
🆕 v3.12.21: Unified version, fixed bugs from Phase 1 audit
🆕 v4.0.0: Redis caching, distributed rate limiting, scalability improvements
"""

from contextlib import asynccontextmanager
from fastapi import (
    FastAPI,
    HTTPException,
    Query,
    Depends,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field  # 🆕 v5.5.4: For batch endpoint request model
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timezone
from pathlib import Path
import asyncio
import json
import logging
import os

# Import centralized settings for VERSION
from settings import settings
import pandas as pd  # For KPIs calculation
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Helper for timezone-aware UTC datetime (Python 3.12+ compatible)
def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


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

# Memory cache as fallback (always available, no dependencies)
try:
    from memory_cache import cache as memory_cache

    MEMORY_CACHE_AVAILABLE = True
    logger.info("✅ Memory cache initialized (in-memory fallback)")
except Exception as e:
    memory_cache = None
    MEMORY_CACHE_AVAILABLE = False
    logger.warning(f"⚠️  Memory cache unavailable: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v4.2: MODULAR ROUTERS
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from routers import include_all_routers

    ROUTERS_AVAILABLE = True
    logger.info("✅ Routers module loaded")
except ImportError as e:
    ROUTERS_AVAILABLE = False
    logger.warning(f"⚠️ Routers not available: {e}")


# 🔧 FIX v3.9.3: Lifespan context manager (replaces deprecated @app.on_event)
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown tasks.

    This is the modern replacement for @app.on_event("startup") and @app.on_event("shutdown").
    See: https://fastapi.tiangolo.com/advanced/events/
    """
    # Startup - using logger to avoid Unicode encoding issues in PowerShell
    logger = logging.getLogger(__name__)
    logger.info("Fuel Copilot API v3.12.0 starting...")

    # 🔧 FIX: Run DB query in threadpool to avoid blocking async loop
    try:
        loop = asyncio.get_running_loop()
        truck_count = await loop.run_in_executor(None, lambda: len(db.get_all_trucks()))
        logger.info(f"Available trucks: {truck_count}")
    except Exception as e:
        logger.warning(f"Could not count trucks on startup (non-critical): {e}")
        logger.info("API starting without truck count - will work normally")

    logger.info("MySQL enhanced features: enabled")
    logger.info("API ready for connections")

    yield  # App runs here

    # Shutdown
    logger.info("Shutting down Fuel Copilot API")


# Initialize FastAPI app with lifespan
app = FastAPI(
    title="Fuel Copilot API",
    description="""
# Fuel Copilot Fleet Management API v3.12.21

Real-time fleet fuel monitoring, analytics, and efficiency tracking for Class 8 trucks.

## 🚀 Features

### Core Analytics
- 🚛 **Fleet Monitoring**: Real-time tracking of 40+ trucks
- ⛽ **Fuel Analytics**: Kalman-filtered fuel level estimation with ±2% accuracy
- 📊 **Efficiency Metrics**: MPG tracking with EMA smoothing (α=0.4)
- 🔔 **Smart Alerts**: Automated drift, refuel, theft, and anomaly detection
- 📈 **KPIs Dashboard**: Fleet-wide performance indicators

### Advanced Features
- 🤖 **ML Predictions**: ARIMA-based fuel consumption forecasting
- 🗺️ **GPS Tracking**: Real-time positions with geofencing
- 📋 **Custom Reports**: Scheduled report generation (PDF, Excel, CSV)
- 🔔 **Push Notifications**: Real-time alert delivery
- 📊 **Dashboard Widgets**: Customizable user dashboards

### Health Monitoring
- 🔬 **Nelson Rules**: Statistical process control for sensor anomaly detection
- 🏥 **Truck Health Scores**: Composite health metrics (0-100)
- ⚠️ **Predictive Maintenance**: Early warning for sensor failures

## 📡 Data Sources

| Source | Update Rate | Data Type |
|--------|-------------|-----------|
| Wialon API | 30s | GPS, fuel, engine sensors |
| MySQL | Real-time | Historical analytics |
| Kalman Filter | 30s | AI-powered fuel estimation |

## 🔐 Authentication

JWT Bearer token authentication. Roles: `super_admin`, `admin`, `viewer`, `anonymous`.

```
Authorization: Bearer <token>
```

## 🚦 Rate Limits

| Role | Requests/min | Burst |
|------|--------------|-------|
| super_admin | 300 | 30/s |
| admin | 120 | 15/s |
| viewer | 60 | 10/s |
| anonymous | 30 | 5/s |

## 📦 Response Format

All responses follow this structure:
```json
{
  "data": {...},
  "timestamp": "2025-12-04T12:00:00Z",
  "status": "success"
}
```

## 🔗 Related Links

- [GitHub Repository](https://github.com/fleetbooster/Fuel-Analytics-Backend)
- [API Changelog](/fuelAnalytics/api/docs#changelog)
""",
    version=settings.app.version,
    docs_url="/fuelAnalytics/api/docs",
    redoc_url="/fuelAnalytics/api/redoc",
    openapi_tags=[
        {
            "name": "Fleet",
            "description": "Fleet-wide summary and real-time statistics for all trucks.",
        },
        {
            "name": "Trucks",
            "description": "Individual truck data, details, and historical records.",
        },
        {
            "name": "Efficiency",
            "description": "MPG rankings, driver efficiency scores, and fuel economy analytics.",
        },
        {
            "name": "Alerts",
            "description": "System alerts, notifications, and alert management.",
        },
        {
            "name": "KPIs",
            "description": "Key Performance Indicators and fleet health metrics.",
        },
        {
            "name": "Health",
            "description": "API health checks and truck health monitoring (Nelson Rules).",
        },
        {
            "name": "Predictions",
            "description": "ML-based fuel consumption and empty tank predictions.",
        },
        {
            "name": "Analytics",
            "description": "Advanced analytics, historical comparisons, and trends.",
        },
        {
            "name": "Dashboard",
            "description": "User dashboard configuration and widget management.",
        },
        {
            "name": "GPS",
            "description": "Real-time GPS tracking and geofence management.",
        },
        {
            "name": "Notifications",
            "description": "Push notification subscriptions and delivery.",
        },
        {
            "name": "Reports",
            "description": "Scheduled reports and export functionality.",
        },
        {
            "name": "Export",
            "description": "Data export to CSV and Excel formats.",
        },
        {
            "name": "Authentication",
            "description": "JWT authentication, login, and token management.",
        },
        {
            "name": "Admin",
            "description": "Administrative endpoints for carrier and user management.",
        },
        {
            "name": "Cost Analysis",
            "description": "Cost per mile calculations and speed impact analysis.",
        },
        {
            "name": "Fleet Utilization",
            "description": "Fleet utilization analysis and optimization recommendations.",
        },
        {
            "name": "Gamification",
            "description": "Driver leaderboards, badges, and performance gamification.",
        },
        {
            "name": "Geofencing",
            "description": "Geofence zones, events, and location history tracking.",
        },
        {
            "name": "Engine Health",
            "description": "Engine health monitoring, alerts, and maintenance predictions.",
        },
        {
            "name": "Predictive Maintenance",
            "description": "V3/V5 predictive maintenance with operational context.",
        },
        {
            "name": "Refuels",
            "description": "Refuel events, analytics, and theft detection.",
        },
        {
            "name": "ML Intelligence",
            "description": "Machine learning anomaly detection and driver clustering.",
        },
    ],
    lifespan=lifespan,  # 🔧 FIX v3.9.3: Use lifespan instead of on_event
)

# 🆕 v3.12.21: Register centralized error handlers
try:
    from errors import register_exception_handlers

    register_exception_handlers(app)
except ImportError:
    logger.warning("errors module not available - using default error handling")

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


# =============================================================================
# 🆕 v3.12.21: RATE LIMITING MIDDLEWARE (#31)
# =============================================================================
from collections import defaultdict
from time import time as current_time

# Rate limit storage: {ip: [(timestamp, count)]}
_rate_limit_store: Dict[str, list] = defaultdict(list)

# Rate limits by role (requests per minute)
# 🔧 v5.7.9: Increased limits - ML/SensorHealth pages need ~100 calls on load
RATE_LIMITS = {
    "super_admin": 1000,
    "carrier_admin": 500,
    "admin": 500,
    "viewer": 300,
    "anonymous": 200,  # Increased from 120 - ML+SensorHealth pages are heavy
}


def get_rate_limit_for_role(role: str) -> int:
    """Get rate limit for a given role."""
    return RATE_LIMITS.get(role, RATE_LIMITS["anonymous"])


def check_rate_limit(client_id: str, role: str = "anonymous") -> tuple[bool, int]:
    """
    Check if client has exceeded rate limit.

    Returns:
        (allowed: bool, remaining: int)

    🆕 v4.1: Skips rate limiting when SKIP_RATE_LIMIT=1
    """
    # Skip rate limiting in test mode
    if os.getenv("SKIP_RATE_LIMIT", "").lower() in ("1", "true", "yes"):
        return True, 999

    now = current_time()
    window = 60  # 1 minute window
    limit = get_rate_limit_for_role(role)

    # Clean old entries
    _rate_limit_store[client_id] = [
        ts for ts in _rate_limit_store[client_id] if now - ts < window
    ]

    # Check limit
    current_count = len(_rate_limit_store[client_id])
    if current_count >= limit:
        return False, 0

    # Add new request
    _rate_limit_store[client_id].append(now)
    return True, limit - current_count - 1


from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware based on user role."""

    async def dispatch(self, request, call_next):
        # Skip rate limiting for health checks and metrics
        if request.url.path in ["/health", "/metrics", "/fuelAnalytics/api/health"]:
            return await call_next(request)

        # Get client identifier
        client_ip = request.client.host if request.client else "unknown"

        # Try to get role from JWT token
        role = "anonymous"
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            try:
                token = auth_header.split(" ")[1]
                token_data = decode_token(token)
                if token_data:
                    role = token_data.role
                    client_id = f"{client_ip}:{token_data.username}"
                else:
                    client_id = client_ip
            except Exception:
                client_id = client_ip
        else:
            client_id = client_ip

        # Check rate limit
        allowed, remaining = check_rate_limit(client_id, role)

        if not allowed:
            # 🔧 v5.7.8: Add CORS headers to 429 response to prevent browser CORS errors
            origin = request.headers.get("origin", "")
            cors_headers = {
                "Retry-After": "60",
                "X-RateLimit-Limit": str(get_rate_limit_for_role(role)),
                "X-RateLimit-Remaining": "0",
            }
            # Add CORS headers if origin is allowed
            allowed_origins = [
                "http://localhost:3000",
                "http://localhost:3001",
                "http://localhost:5173",
                "https://fuelanalytics.fleetbooster.net",
                "https://fleetbooster.net",
            ]
            if origin in allowed_origins:
                cors_headers["Access-Control-Allow-Origin"] = origin
                cors_headers["Access-Control-Allow-Credentials"] = "true"
                cors_headers["Access-Control-Allow-Methods"] = (
                    "GET, POST, PUT, DELETE, OPTIONS"
                )
                cors_headers["Access-Control-Allow-Headers"] = "*"

            return JSONResponse(
                status_code=429,
                content={
                    "error": "Too Many Requests",
                    "message": f"Rate limit exceeded. Limit: {get_rate_limit_for_role(role)}/min for role '{role}'",
                    "retry_after": 60,
                },
                headers=cors_headers,
            )

        # Process request
        response = await call_next(request)

        # Add rate limit headers
        response.headers["X-RateLimit-Limit"] = str(get_rate_limit_for_role(role))
        response.headers["X-RateLimit-Remaining"] = str(remaining)

        return response


# Add rate limiting middleware
app.add_middleware(RateLimitMiddleware)
logger.info("✅ Rate limiting middleware enabled")

# 🆕 v5.6: GZip compression for large responses (>1KB)
app.add_middleware(GZipMiddleware, minimum_size=1000)
logger.info("✅ GZip compression middleware enabled")

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
        "https://fuelanalytics.fleetbooster.net",
        "https://fleetbooster.net",
        "https://uninterrogative-unputrefiable-maleah.ngrok-free.dev",  # ngrok tunnel
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v4.2: INCLUDE MODULAR ROUTERS
# ═══════════════════════════════════════════════════════════════════════════════
if ROUTERS_AVAILABLE:
    try:
        include_all_routers(app, auth_dependency=require_auth)
        logger.info("✅ All routers included successfully")
    except Exception as e:
        logger.error(f"❌ Failed to include routers: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.2: CLEAN V5 ENDPOINTS (Fleet Analytics, Leaderboard ONLY)
# 🚫 v5.2.1: PREDICTIVE MAINTENANCE REMOVED - crashes on startup
# ═══════════════════════════════════════════════════════════════════════════════
try:
    from v5_endpoints import register_v5_endpoints

    register_v5_endpoints(app)
    logger.info("✅ V5 Clean Endpoints registered (Fleet Analytics, Leaderboard)")
except Exception as e:
    logger.error(f"❌ Failed to register V5 endpoints: {e}")


# ============================================================================
# 🆕 v3.10.8: AUTHENTICATION ENDPOINTS
# ============================================================================
# ⚠️ v5.6.0: MIGRATED TO routers/auth_router.py - DO NOT ENABLE
# These endpoints are now served by the auth_router module
# ============================================================================

# @app.post(
#     "/fuelAnalytics/api/auth/login", response_model=Token, tags=["Authentication"]
# )
# async def login(credentials: UserLogin):
#     """
#     Authenticate user and return JWT token.
#
#     Credentials:
#     - admin / FuelAdmin2025! (super_admin - all carriers)
#     - skylord / Skylord2025! (carrier_admin - skylord only)
#     - skylord_viewer / SkylordView2025 (viewer - skylord read-only)
#     """
#     user = authenticate_user(credentials.username, credentials.password)
#     if not user:
#         raise HTTPException(
#             status_code=status.HTTP_401_UNAUTHORIZED,
#             detail="Invalid username or password",
#             headers={"WWW-Authenticate": "Bearer"},
#         )
#
#     from datetime import timedelta
#
#     ACCESS_TOKEN_EXPIRE_HOURS = 24
#
#     access_token = create_access_token(
#         user=user, expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
#     )
#
#     return Token(
#         access_token=access_token,
#         token_type="bearer",
#         expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
#         user={
#             "username": user["username"],
#             "name": user["name"],
#             "carrier_id": user["carrier_id"],
#             "role": user["role"],
#             "email": user.get("email"),
#         },
#     )


# @app.get("/fuelAnalytics/api/auth/me", tags=["Authentication"])
# async def get_current_user_info(current_user: TokenData = Depends(require_auth)):
#     """Get current authenticated user info."""
#     user_data = USERS_DB.get(current_user.username, {})
#     return {
#         "username": current_user.username,
#         "name": user_data.get("name", current_user.username),
#         "carrier_id": current_user.carrier_id,
#         "role": current_user.role,
#         "email": user_data.get("email"),
#         "permissions": {
#             "can_view_all_carriers": current_user.carrier_id == "*",
#             "can_edit": current_user.role in ["super_admin", "carrier_admin"],
#             "can_manage_users": current_user.role == "super_admin",
#         },
#     }


# @app.post(
#     "/fuelAnalytics/api/auth/refresh", response_model=Token, tags=["Authentication"]
# )
# async def refresh_token(current_user: TokenData = Depends(require_auth)):
#     """Refresh JWT token before it expires."""
#     user_data = USERS_DB.get(current_user.username)
#     if not user_data:
#         raise HTTPException(status_code=401, detail="User not found")
#
#     from datetime import timedelta
#
#     ACCESS_TOKEN_EXPIRE_HOURS = 24
#
#     new_token = create_access_token(
#         user=user_data, expires_delta=timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
#     )
#
#     return Token(
#         access_token=new_token,
#         token_type="bearer",
#         expires_in=ACCESS_TOKEN_EXPIRE_HOURS * 3600,
#         user={
#             "username": user_data["username"],
#             "name": user_data["name"],
#             "carrier_id": user_data["carrier_id"],
#             "role": user_data["role"],
#             "email": user_data.get("email"),
#         },
#     )


# ============================================================================
# 🆕 v3.10.8: ADMIN ENDPOINTS (Super Admin Only)
# ============================================================================
# ⚠️ v5.6.0: MIGRATED TO routers/admin_router.py - DO NOT ENABLE
# These endpoints are now served by the admin_router module
# ============================================================================

# @app.get("/fuelAnalytics/api/admin/carriers", tags=["Admin"])
# async def list_carriers(current_user: TokenData = Depends(require_super_admin)):
#     """
#     List all carriers (super_admin only).
#     Reads from MySQL carriers table.
#     """
#     try:
#         from database_mysql import get_sqlalchemy_engine
#         from sqlalchemy import text
#
#         engine = get_sqlalchemy_engine()
#         with engine.connect() as conn:
#             result = conn.execute(
#                 text(
#                     """
#                 SELECT carrier_id, name, contact_email, timezone,
#                        created_at, updated_at, active
#                 FROM carriers
#                 ORDER BY name
#             """
#                 )
#             )
#             carriers = [dict(row._mapping) for row in result]
#
#             # Add truck count for each carrier
#             for carrier in carriers:
#                 count_result = conn.execute(
#                     text(
#                         """
#                     SELECT COUNT(DISTINCT truck_id) as truck_count
#                     FROM fuel_metrics
#                     WHERE carrier_id = :carrier_id
#                 """
#                     ),
#                     {"carrier_id": carrier["carrier_id"]},
#                 )
#                 carrier["truck_count"] = count_result.scalar() or 0
#
#             return {"carriers": carriers, "total": len(carriers)}
#     except Exception as e:
#         logger.error(f"Error listing carriers: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# @app.get("/fuelAnalytics/api/admin/users", tags=["Admin"])
# async def list_users(current_user: TokenData = Depends(require_super_admin)):
#     """List all users (super_admin only)."""
#     users = []
#     for username, user_data in USERS_DB.items():
#         users.append(
#             {
#                 "username": username,
#                 "name": user_data["name"],
#                 "carrier_id": user_data["carrier_id"],
#                 "role": user_data["role"],
#                 "email": user_data.get("email"),
#                 "active": user_data.get("active", True),
#             }
#         )
#     return {"users": users, "total": len(users)}


# @app.get("/fuelAnalytics/api/admin/stats", tags=["Admin"])
# async def get_admin_stats(current_user: TokenData = Depends(require_super_admin)):
#     """
#     Get system-wide statistics (super_admin only).
#     """
#     try:
#         from database_mysql import get_sqlalchemy_engine
#         from sqlalchemy import text
#
#         engine = get_sqlalchemy_engine()
#         with engine.connect() as conn:
#             # Total records
#             total_records = conn.execute(
#                 text("SELECT COUNT(*) FROM fuel_metrics")
#             ).scalar()
#
#             # Records by carrier
#             carrier_stats = conn.execute(
#                 text(
#                     """
#                 SELECT carrier_id,
#                        COUNT(*) as records,
#                        COUNT(DISTINCT truck_id) as trucks,
#                        MIN(timestamp_utc) as first_record,
#                        MAX(timestamp_utc) as last_record
#                 FROM fuel_metrics
#                 GROUP BY carrier_id
#             """
#                 )
#             )
#
#             carriers = [dict(row._mapping) for row in carrier_stats]
#
#             # Total refuels
#             total_refuels = (
#                 conn.execute(text("SELECT COUNT(*) FROM refuel_events")).scalar() or 0
#             )
#
#             return {
#                 "total_records": total_records,
#                 "total_refuels": total_refuels,
#                 "carriers": carriers,
#                 "users_count": len(USERS_DB),
#             }
#     except Exception as e:
#         logger.error(f"Error getting admin stats: {e}")
#         raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================


@app.get("/fuelAnalytics/api/status", response_model=HealthCheck, tags=["Health"])
async def api_status():
    """Quick API status check. Returns basic health info."""
    trucks = db.get_all_trucks()
    return {
        "status": "healthy",
        "version": settings.app.version,
        "timestamp": datetime.now(),
        "trucks_available": len(trucks),
    }


@app.get("/fuelAnalytics/api/cache/stats", tags=["Health"])
async def get_cache_stats():
    """
    Get cache statistics and performance metrics.

    Returns cache availability, hit/miss rates, and memory usage.
    🆕 v3.12.22: Now uses in-memory cache instead of Redis
    """
    # Try memory cache first
    try:
        from memory_cache import get_cache_status

        stats = get_cache_status()
        return {"available": True, **stats}
    except ImportError:
        pass

    # Fallback to Redis cache if available
    if not cache:
        return {
            "available": False,
            "message": "Cache not configured",
        }

    try:
        stats = cache.get_stats()
        return stats
    except Exception as e:
        return {"available": False, "error": str(e)}


@app.get("/fuelAnalytics/api/health", response_model=HealthCheck, tags=["Health"])
def health_check():
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
    # 🔧 FIX: Use synchronous def to run in threadpool (avoids blocking event loop)
    try:
        trucks = db.get_all_trucks()
    except Exception as e:
        logger.error(f"Health check DB error: {e}")
        trucks = []

    mysql_status = "connected" if db.mysql_available else "unavailable"
    cache_status = "available" if (cache and cache._available) else "unavailable"

    # Check data freshness
    try:
        fleet_summary = db.get_fleet_summary()
        data_fresh = fleet_summary.get("active_trucks", 0) > 0
    except Exception as e:
        # 🔧 FIX v3.12.23: Properly catch and log exceptions instead of bare except
        logger.warning(f"Failed to check data freshness: {e}")
        data_fresh = False

    # Get bulk handler stats if available
    bulk_stats = None
    try:
        from bulk_mysql_handler import get_bulk_handler

        handler = get_bulk_handler()
        bulk_stats = handler.get_stats()
    except Exception as e:
        # 🔧 FIX v3.12.23: Properly handle exception instead of bare except
        logger.debug(f"Bulk handler stats not available: {e}")

    # Build health response
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


# ============================================================================
# 🆕 v5.3.1: DEEP HEALTH CHECK ENDPOINTS
# ============================================================================


@app.get("/fuelAnalytics/api/health/deep", tags=["Health"])
def deep_health_check():
    """
    🆕 v5.3.1: Deep health check with memory, DB pool, and Wialon sync status

    Checks:
    - Memory usage (alerts if >80% or >1GB)
    - Database connection pool status and latency
    - Wialon sync cache freshness
    - Detects potential deadlocks or resource exhaustion

    Returns detailed report with errors and warnings.
    Use this endpoint for monitoring and alerting.
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


@app.get("/fuelAnalytics/api/health/quick", tags=["Health"])
def quick_health_check():
    """
    🆕 v5.3.1: Quick health check (no DB query)

    Fast endpoint for load balancer health probes.
    Only checks memory usage, no database queries.
    """
    try:
        from health_monitor import quick_status

        return quick_status()
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ============================================================================
# BATCH ENDPOINTS - v5.5.4: Combined API calls for dashboard efficiency
# ============================================================================


class BatchRequest(BaseModel):
    """Request model for batch API calls"""

    # 🆕 v5.5.5: Limit max endpoints to prevent abuse
    endpoints: List[str] = Field(default=[], max_length=10)
    truck_ids: Optional[List[str]] = None  # Optional truck IDs for truck-specific data
    days: Optional[int] = Field(default=7, ge=1, le=90)  # Limit days range


@app.post("/fuelAnalytics/api/batch", tags=["Batch"])
async def batch_fetch(request: BatchRequest):
    """
    🆕 v5.5.4: Batch endpoint to fetch multiple datasets in a single request.

    Reduces HTTP round-trips for dashboard initial load.
    Instead of 5-10 separate API calls, frontend makes ONE batch call.

    Available endpoints:
    - "fleet": Fleet summary with all trucks
    - "alerts": Active alerts
    - "refuels": Recent refuels (uses 'days' param)
    - "kpis": KPI metrics
    - "efficiency": Efficiency rankings
    - "maintenance": Maintenance alerts

    Example request:
    ```json
    {
        "endpoints": ["fleet", "alerts", "refuels"],
        "days": 7
    }
    ```

    Returns combined response with all requested data.
    """
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    results = {}
    errors = {}

    async def fetch_fleet():
        try:
            cache_key = "fleet_summary"
            if MEMORY_CACHE_AVAILABLE and memory_cache:
                cached = memory_cache.get(cache_key)
                if cached:
                    return cached
            summary = db.get_fleet_summary()
            summary["data_source"] = "MySQL" if db.mysql_available else "CSV"
            if MEMORY_CACHE_AVAILABLE and memory_cache:
                memory_cache.set(cache_key, summary, ttl=30)
            return summary
        except Exception as e:
            raise Exception(f"Fleet fetch error: {e}")

    async def fetch_alerts():
        try:
            cache_key = "active_alerts"
            if MEMORY_CACHE_AVAILABLE and memory_cache:
                cached = memory_cache.get(cache_key)
                if cached:
                    return cached
            alerts = db.get_active_alerts()
            if MEMORY_CACHE_AVAILABLE and memory_cache:
                memory_cache.set(cache_key, alerts, ttl=60)
            return alerts
        except Exception as e:
            raise Exception(f"Alerts fetch error: {e}")

    async def fetch_refuels():
        try:
            days = request.days or 7
            return db.get_all_refuels(days)
        except Exception as e:
            raise Exception(f"Refuels fetch error: {e}")

    async def fetch_kpis():
        try:
            cache_key = "kpis_data"
            if MEMORY_CACHE_AVAILABLE and memory_cache:
                cached = memory_cache.get(cache_key)
                if cached:
                    return cached
            # Get KPI data
            kpis = db.get_fleet_kpis() if hasattr(db, "get_fleet_kpis") else {}
            if MEMORY_CACHE_AVAILABLE and memory_cache:
                memory_cache.set(cache_key, kpis, ttl=60)
            return kpis
        except Exception as e:
            raise Exception(f"KPIs fetch error: {e}")

    async def fetch_efficiency():
        try:
            # Use the existing efficiency rankings logic
            rankings = (
                db.get_efficiency_rankings()
                if hasattr(db, "get_efficiency_rankings")
                else []
            )
            return rankings
        except Exception as e:
            raise Exception(f"Efficiency fetch error: {e}")

    async def fetch_maintenance():
        try:
            # Get maintenance/engine health alerts
            from engine_health_engine import get_fleet_health_alerts

            alerts = (
                get_fleet_health_alerts() if "get_fleet_health_alerts" in dir() else []
            )
            return alerts
        except Exception as e:
            raise Exception(f"Maintenance fetch error: {e}")

    # Map endpoint names to fetch functions
    endpoint_map = {
        "fleet": fetch_fleet,
        "alerts": fetch_alerts,
        "refuels": fetch_refuels,
        "kpis": fetch_kpis,
        "efficiency": fetch_efficiency,
        "maintenance": fetch_maintenance,
    }

    # Fetch all requested endpoints in parallel
    tasks = []
    endpoint_names = []

    for endpoint in request.endpoints:
        if endpoint in endpoint_map:
            tasks.append(endpoint_map[endpoint]())
            endpoint_names.append(endpoint)
        else:
            errors[endpoint] = f"Unknown endpoint: {endpoint}"

    if tasks:
        # Execute all fetches concurrently
        fetch_results = await asyncio.gather(*tasks, return_exceptions=True)

        for name, result in zip(endpoint_names, fetch_results):
            if isinstance(result, Exception):
                errors[name] = str(result)
            else:
                results[name] = result

    return {
        "success": True,
        "data": results,
        "errors": errors if errors else None,
        "fetched_endpoints": list(results.keys()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/fuelAnalytics/api/batch/dashboard", tags=["Batch"])
async def batch_dashboard():
    """
    🆕 v5.5.4: Pre-configured batch endpoint for dashboard initial load.

    Fetches all data needed for the main dashboard in ONE call:
    - Fleet summary (all trucks)
    - Active alerts
    - Recent refuels (7 days)

    This replaces 3 separate API calls with 1, reducing latency by ~60%.
    """
    try:
        import asyncio

        # Fetch all in parallel
        fleet_task = asyncio.create_task(_fetch_fleet_for_batch())
        alerts_task = asyncio.create_task(_fetch_alerts_for_batch())
        refuels_task = asyncio.create_task(_fetch_refuels_for_batch(7))

        fleet, alerts, refuels = await asyncio.gather(
            fleet_task, alerts_task, refuels_task, return_exceptions=True
        )

        return {
            "success": True,
            "fleet": fleet if not isinstance(fleet, Exception) else None,
            "alerts": alerts if not isinstance(alerts, Exception) else [],
            "refuels": refuels if not isinstance(refuels, Exception) else [],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch dashboard error: {e}")


async def _fetch_fleet_for_batch():
    """Helper for batch fleet fetch"""
    cache_key = "fleet_summary"
    if MEMORY_CACHE_AVAILABLE and memory_cache:
        cached = memory_cache.get(cache_key)
        if cached:
            return cached
    summary = db.get_fleet_summary()
    summary["data_source"] = "MySQL" if db.mysql_available else "CSV"
    if MEMORY_CACHE_AVAILABLE and memory_cache:
        memory_cache.set(cache_key, summary, ttl=30)
    return summary


async def _fetch_alerts_for_batch():
    """Helper for batch alerts fetch"""
    cache_key = "active_alerts"
    if MEMORY_CACHE_AVAILABLE and memory_cache:
        cached = memory_cache.get(cache_key)
        if cached:
            return cached
    alerts = db.get_active_alerts()
    if MEMORY_CACHE_AVAILABLE and memory_cache:
        memory_cache.set(cache_key, alerts, ttl=60)
    return alerts


async def _fetch_refuels_for_batch(days: int):
    """Helper for batch refuels fetch"""
    return db.get_all_refuels(days)


# ============================================================================
# FLEET ENDPOINTS
# ============================================================================


@app.get("/fuelAnalytics/api/fleet", response_model=FleetSummary, tags=["Fleet"])
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

        # Try memory cache first (fast, always available)
        if MEMORY_CACHE_AVAILABLE and memory_cache:
            cached_data = memory_cache.get(cache_key)
            if cached_data:
                logger.debug("⚡ Fleet summary from memory cache")
                return cached_data

        # Use CSV for all metrics (Kalman-filtered, accurate)
        summary = db.get_fleet_summary()

        # Add metadata
        summary["data_source"] = "MySQL" if db.mysql_available else "CSV"

        # Cache for 30 seconds (matches data refresh interval)
        if MEMORY_CACHE_AVAILABLE and memory_cache:
            memory_cache.set(cache_key, summary, ttl=30)
            logger.debug("💾 Fleet summary cached for 30s")

        return summary
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error fetching fleet summary: {str(e)}"
        )


@app.get("/fuelAnalytics/api/trucks", response_model=List[str], tags=["Trucks"])
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
# TRUCK DETAIL ENDPOINTS testing
# ============================================================================


@app.get("/fuelAnalytics/api/trucks/{truck_id}", tags=["Trucks"])
async def get_truck_detail(truck_id: str):
    """
    Get  detailed information for a specific truck.

    Returns complete real-time data including:
    - Fuel level (sensor and Kalman-estimated)
    - Current MPG and idle consumption
    - GPS location and speed
    - Engine status and sensor health

    🔧 FIX v3.10.3: Returns basic info if truck exists in config but has no recent data
    """
    import pandas as pd
    import numpy as np

    try:
        logger.info(f"[get_truck_detail] Fetching data for {truck_id}")
        record = db.get_truck_latest_record(truck_id)
        logger.info(f"[get_truck_detail] Record retrieved: {record is not None}")

        if not record:
            # 🔧 FIX v3.10.3: Check if truck exists in tanks.yaml config
            # If it does, return a minimal "offline" record instead of 404
            import yaml

            # 🔧 FIX v3.12.4: Correct path - tanks.yaml is in same directory as main.py
            tanks_path = Path(__file__).parent / "tanks.yaml"
            logger.info(f"[get_truck_detail] Checking tanks.yaml at {tanks_path}")
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
        logger.info(f"[get_truck_detail] Converting record with {len(record)} fields")
        clean_record = {}
        for key, value in record.items():
            try:
                # Handle various null types
                if value is None:
                    clean_record[key] = None
                elif isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
                    clean_record[key] = None
                elif pd.isna(value):
                    clean_record[key] = None
                # Convert numpy types to Python native types
                elif hasattr(np, "integer") and isinstance(value, np.integer):
                    clean_record[key] = int(value)
                elif hasattr(np, "floating") and isinstance(value, np.floating):
                    clean_record[key] = float(value)
                elif hasattr(np, "bool_") and isinstance(value, np.bool_):
                    clean_record[key] = bool(value)
                elif isinstance(value, pd.Timestamp):
                    clean_record[key] = value.isoformat()
                else:
                    clean_record[key] = value
            except (TypeError, ValueError) as conv_err:
                # If we can't process the value, set it to None
                logger.warning(
                    f"[get_truck_detail] Failed to convert {key}: {conv_err}"
                )
                clean_record[key] = None

        # 🔧 FIX: Add 'status' alias for frontend compatibility
        if "truck_status" in clean_record:
            clean_record["status"] = clean_record["truck_status"]

        clean_record["data_available"] = True
        logger.info(
            f"[get_truck_detail] Returning {len(clean_record)} fields for {truck_id}"
        )

        return clean_record
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[get_truck_detail] ERROR for {truck_id}: {e}", exc_info=True)
        
        # 🔧 FIX v3.12.22: On ANY error, try to return offline status from tanks.yaml
        # This prevents 500 errors for trucks that exist but have DB/encoding issues
        try:
            import yaml
            tanks_path = Path(__file__).parent / "tanks.yaml"
            if tanks_path.exists():
                with open(tanks_path, "r") as f:
                    tanks_config = yaml.safe_load(f)
                    trucks = tanks_config.get("trucks", {})
                    if truck_id in trucks:
                        truck_config = trucks[truck_id]
                        logger.warning(f"[get_truck_detail] Returning OFFLINE status for {truck_id} due to error: {e}")
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
                            "capacity_gallons": truck_config.get("capacity_gallons", 200),
                            "capacity_liters": truck_config.get("capacity_liters", 757),
                            "message": f"Error loading real-time data: {str(e)[:100]}",
                            "data_available": False,
                        }
        except Exception as fallback_error:
            logger.error(f"[get_truck_detail] Fallback also failed: {fallback_error}")
        
        raise HTTPException(
            status_code=500, detail=f"Error fetching truck data: {str(e)}"
        )


@app.get(
    "/fuelAnalytics/api/trucks/{truck_id}/refuels",
    response_model=List[RefuelEvent],
    tags=["Trucks"],
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


@app.get(
    "/fuelAnalytics/api/trucks/{truck_id}/history",
    response_model=List[HistoricalRecord],
)
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

        # Convert to HistoricalRecord models with NaN sanitization and MPG validation
        history = []
        for rec in records:
            # Get and validate MPG - must be physically possible (2.5-15 for Class 8 trucks)
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


# ============================================================================
# EFFICIENCY & RANKINGS
# ============================================================================


@app.get(
    "/fuelAnalytics/api/efficiency",
    response_model=List[EfficiencyRanking],
    tags=["Efficiency"],
)
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


@app.get("/fuelAnalytics/api/refuels", response_model=List[RefuelEvent])
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


@app.get("/fuelAnalytics/api/refuels/analytics", tags=["Refuels"])
async def get_refuel_analytics(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze")
):
    """
    🆕 v3.10.3: Advanced Refuel Analytics
    🆕 v4.0.0: Added Redis caching (60s TTL) for faster responses

    Comprehensive refuel intelligence:
    - Refuel events with precise gallons
    - Pattern analysis (hourly, daily)
    - Cost tracking
    - Anomaly detection
    - Per-truck summaries
    """
    try:
        # Try cache first
        from cache_service import get_cache

        cache = await get_cache()
        cache_key = f"refuel:analytics:{days}d"
        cached = await cache.get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        try:
            from .database_mysql import get_advanced_refuel_analytics
        except ImportError:
            from database_mysql import get_advanced_refuel_analytics

        analytics = get_advanced_refuel_analytics(days_back=days)

        # Cache for 60 seconds
        await cache.set(cache_key, analytics, ttl=60)

        return JSONResponse(content=analytics)
    except Exception as e:
        logger.error(f"Error in refuel analytics: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching refuel analytics: {str(e)}"
        )


@app.get("/fuelAnalytics/api/theft-analysis", tags=["Security"])
@app.get(
    "/fuelAnalytics/api/theft/analysis", tags=["Security"], include_in_schema=False
)
async def get_theft_analysis(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze"),
    algorithm: str = Query(
        "advanced",
        description="Algorithm version: 'advanced' (v4.1 with trip correlation) or 'legacy' (v3.x)",
    ),
):
    """
    🛡️ v4.1.0: ADVANCED Fuel Theft Detection & Analysis

    Sophisticated multi-signal theft detection that combines:
    - Fuel level analysis (drops, recovery patterns)
    - Trip/movement correlation from Wialon (was truck moving during drop?)
    - Time pattern analysis (night, weekends)
    - Sensor health scoring (is sensor reliable?)
    - Machine learning-style confidence scoring

    KEY IMPROVEMENT: Cross-references fuel drops with actual trip data
    to eliminate false positives from normal fuel consumption.

    Algorithms:
    - 'advanced' (default): New v4.1 algorithm with Wialon trip correlation
    - 'legacy': Previous v3.x algorithm for comparison

    Returns events classified as:
    - ROBO CONFIRMADO: High confidence theft (>85%)
    - ROBO SOSPECHOSO: Possible theft (60-85%)
    - CONSUMO NORMAL: Fuel drop during active trip
    - PROBLEMA DE SENSOR: Sensor glitch with recovery
    """
    try:
        # Try cache first
        from cache_service import get_cache

        cache = await get_cache()
        cache_key = f"theft:analysis:{algorithm}:{days}d"
        cached = await cache.get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        if algorithm == "advanced":
            # 🆕 v4.1.0: Use new advanced engine with Wialon trip correlation
            try:
                from theft_detection_engine import analyze_fuel_drops_advanced

                analysis = analyze_fuel_drops_advanced(days_back=days)
            except Exception as e:
                logger.warning(
                    f"Advanced algorithm failed, falling back to legacy: {e}"
                )
                # Fallback to legacy
                try:
                    from .database_mysql import get_fuel_theft_analysis
                except ImportError:
                    from database_mysql import get_fuel_theft_analysis
                analysis = get_fuel_theft_analysis(days_back=days)
        else:
            # Legacy algorithm
            try:
                from .database_mysql import get_fuel_theft_analysis
            except ImportError:
                from database_mysql import get_fuel_theft_analysis
            analysis = get_fuel_theft_analysis(days_back=days)

        # Cache for 60 seconds
        await cache.set(cache_key, analysis, ttl=60)

        return JSONResponse(content=analysis)
    except Exception as e:
        logger.error(f"Error in theft analysis: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching theft analysis: {str(e)}"
        )


# ============================================================================
# ALERTS
# ============================================================================


@app.get("/fuelAnalytics/api/alerts", response_model=List[Alert], tags=["Alerts"])
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


@app.get("/fuelAnalytics/api/kpis", tags=["KPIs"])
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

        # Try cache first (Redis → Memory Cache → Compute)
        cache_key = f"kpis:fleet:{days}d"

        # 1. Try Redis cache
        if cache and cache._available:
            try:
                cached = cache._redis.get(cache_key)
                if cached:
                    logger.info(f"⚡ KPIs from Redis cache ({days}d)")
                    if PROMETHEUS_AVAILABLE:
                        cache_hits.labels(endpoint="kpis").inc()
                    return json.loads(cached)
                else:
                    logger.info(f"💨 Redis cache miss for KPIs ({days}d)")
                    if PROMETHEUS_AVAILABLE:
                        cache_misses.labels(endpoint="kpis").inc()
            except Exception as e:
                logger.warning(f"Redis cache read error: {e}")

        # 2. Try memory cache (fallback)
        if MEMORY_CACHE_AVAILABLE and memory_cache:
            cached_data = memory_cache.get(cache_key)
            if cached_data:
                logger.info(f"⚡ KPIs from memory cache ({days}d)")
                return cached_data

        # 3. Compute from database
        from database_mysql import get_kpi_summary

        kpi_data = get_kpi_summary(days_back=days)

        # Cache the result (shorter TTL for daily, longer for weekly/monthly)
        cache_ttl = 60 if days == 1 else 300  # 1 min for daily, 5 min for longer

        # Save to Redis if available
        if cache and cache._available:
            try:
                cache._redis.setex(cache_key, cache_ttl, json.dumps(kpi_data))
                logger.info(f"💾 KPIs saved to Redis ({cache_ttl}s)")
            except Exception as e:
                logger.warning(f"Redis cache write error: {e}")

        # Always save to memory cache (faster fallback)
        if MEMORY_CACHE_AVAILABLE and memory_cache:
            memory_cache.set(cache_key, kpi_data, ttl=cache_ttl)
            logger.debug(f"💾 KPIs saved to memory cache ({cache_ttl}s)")

        return kpi_data

    except Exception as e:
        logger.error(f"Error fetching KPIs: {e}")
        raise HTTPException(status_code=500, detail=f"Error fetching KPIs: {str(e)}")


# ============================================================================
# LOSS ANALYSIS (ROOT CAUSE)
# ============================================================================


@app.get("/fuelAnalytics/api/loss-analysis")
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


@app.get("/fuelAnalytics/api/analytics/driver-scorecard")
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
    - MPG Performance (vs 5.7 baseline)

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


@app.get("/fuelAnalytics/api/analytics/enhanced-kpis")
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


@app.get("/fuelAnalytics/api/analytics/enhanced-loss-analysis")
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


# Root route - serve frontend (lower priority than /fuelAnalytics/api/health)
@app.get("/", include_in_schema=False)
async def root():
    """Serve React frontend at root"""
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "Fuel Copilot API v3.1.0", "docs": "/fuelAnalytics/api/docs"}


# NOTE: Catch-all moved to end of file to avoid capturing API routes
# See bottom of file for the actual catch_all_routes function


# ============================================================================
# NEW ENDPOINTS - Enhanced MySQL Features
# ============================================================================


@app.get("/fuelAnalytics/api/trucks/{truck_id}/sensor-history")
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


@app.get("/fuelAnalytics/api/trucks/{truck_id}/fuel-trend")
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


@app.get("/fuelAnalytics/api/fleet/sensor-health")
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


# ============================================================================
# 🆕 TRUCK HEALTH MONITORING ENDPOINTS - v3.11.0
# Statistical analysis for predictive maintenance
# ============================================================================

# ============================================================================
# 🚫 DISABLED v5.2: TruckHealthMonitor causes startup crashes
# Using new v5 endpoints with direct DB queries instead
# ============================================================================
# import sys
# sys.path.insert(0, str(Path(__file__).parent))
# try:
#     from truck_health_monitor import (
#         TruckHealthMonitor,
#         SensorType,
#         AlertSeverity,
#         integrate_with_truck_data,
#     )
#     HEALTH_MONITOR_AVAILABLE = True
#     try:
#         _health_monitor = TruckHealthMonitor(
#             data_dir=str(Path(__file__).parent / "data" / "health_stats")
#         )
#         logger.info("🏥 Truck Health Monitor initialized successfully")
#     except Exception as e:
#         logger.error(f"❌ Failed to initialize TruckHealthMonitor: {e}")
#         _health_monitor = None
#         HEALTH_MONITOR_AVAILABLE = False
# except ImportError as e:
#     HEALTH_MONITOR_AVAILABLE = False
#     _health_monitor = None
#     logger.warning(f"⚠️ Truck Health Monitor not available: {e}")

HEALTH_MONITOR_AVAILABLE = False
_health_monitor = None
logger.info("🚀 v5.2: Using new lightweight v5 endpoints (TruckHealthMonitor disabled)")


# NOTE: Fleet summary must be defined BEFORE /truck/{truck_id} to avoid route capture
@app.get("/fuelAnalytics/api/health/fleet/summary", tags=["Health Monitoring"])
async def get_fleet_health_summary():
    """
    Get health summary for entire fleet.

    Returns aggregated statistics including:
        - total_trucks: Number of trucks with health data
        - healthy/watch/warning/critical: Counts by status
        - trucks: Array of truck health reports for frontend

    🔧 v2.0: Falls back to fuel_metrics data if health monitor has no data
    """
    try:
        # First try the specialized health monitor
        if HEALTH_MONITOR_AVAILABLE:
            summary = _health_monitor.get_fleet_health_summary()

            # If health monitor has data, use it
            if summary.get("total_trucks", 0) > 0:
                trucks_list = []
                for truck_id, score in summary.get("truck_scores", {}).items():
                    report = _health_monitor.get_truck_health_report(truck_id)
                    if report:
                        trucks_list.append(
                            {
                                "truck_id": truck_id,
                                "truck_name": truck_id,
                                "overall_status": (
                                    "CRITICAL"
                                    if score < 40
                                    else (
                                        "WARNING"
                                        if score < 60
                                        else "WATCH" if score < 80 else "NORMAL"
                                    )
                                ),
                                "health_score": score,
                                "sensors": [],
                                "alerts": (
                                    [a.to_dict() for a in report.alerts]
                                    if report.alerts
                                    else []
                                ),
                                "last_updated": datetime.now().isoformat(),
                            }
                        )

                return {
                    "total_trucks": summary.get("total_trucks", 0),
                    "healthy": summary.get("healthy_count", 0),
                    "watch": summary.get("watch_count", 0),
                    "warning": summary.get("warning_count", 0),
                    "critical": summary.get("critical_count", 0),
                    "trucks": trucks_list,
                }

        # 🔧 v2.0: Fallback to fuel_metrics data
        # Calculate health from existing fuel_metrics data
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()
        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT 
                    t1.truck_id,
                    t1.truck_status,
                    t1.estimated_pct,
                    t1.sensor_pct,
                    t1.drift_pct,
                    t1.coolant_temp_f,
                    t1.speed_mph,
                    t1.rpm,
                    t1.timestamp_utc
                FROM fuel_metrics t1
                INNER JOIN (
                    SELECT truck_id, MAX(timestamp_utc) as max_time
                    FROM fuel_metrics
                    WHERE timestamp_utc > NOW() - INTERVAL 24 HOUR
                    GROUP BY truck_id
                ) t2 ON t1.truck_id = t2.truck_id AND t1.timestamp_utc = t2.max_time
                ORDER BY t1.truck_id
            """
                )
            )

            trucks_list = []
            healthy = 0
            watch = 0
            warning = 0
            critical = 0

            for row in result:
                truck_id = row[0]
                status = row[1]
                estimated_pct = row[2]
                sensor_pct = row[3]
                drift_pct = row[4]
                coolant_temp = row[5]
                speed = row[6]
                rpm = row[7]
                timestamp = row[8]

                # Calculate health score based on available data
                health_score = 100.0
                alerts = []

                # Check fuel level (critical if very low)
                if estimated_pct is not None:
                    if estimated_pct < 10:
                        health_score -= 30
                        alerts.append(
                            {
                                "type": "LOW_FUEL",
                                "message": f"Critical fuel level: {estimated_pct:.1f}%",
                            }
                        )
                    elif estimated_pct < 20:
                        health_score -= 15
                        alerts.append(
                            {
                                "type": "LOW_FUEL",
                                "message": f"Low fuel level: {estimated_pct:.1f}%",
                            }
                        )

                # Check drift (sensor vs estimated difference)
                if drift_pct is not None and abs(drift_pct) > 10:
                    health_score -= 20
                    alerts.append(
                        {"type": "DRIFT", "message": f"High drift: {drift_pct:.1f}%"}
                    )

                # Check coolant temperature (warning if too high)
                if coolant_temp is not None and coolant_temp > 220:
                    health_score -= 25
                    alerts.append(
                        {
                            "type": "OVERHEATING",
                            "message": f"High coolant temp: {coolant_temp:.1f}°F",
                        }
                    )

                # Check offline status
                if status == "OFFLINE":
                    health_score -= 10

                # Clamp score
                health_score = max(0, min(100, health_score))

                # Determine overall status
                if health_score >= 80:
                    overall_status = "NORMAL"
                    healthy += 1
                elif health_score >= 60:
                    overall_status = "WATCH"
                    watch += 1
                elif health_score >= 40:
                    overall_status = "WARNING"
                    warning += 1
                else:
                    overall_status = "CRITICAL"
                    critical += 1

                trucks_list.append(
                    {
                        "truck_id": truck_id,
                        "truck_name": truck_id,
                        "overall_status": overall_status,
                        "health_score": round(health_score, 1),
                        "sensors": [],
                        "alerts": alerts,
                        "last_updated": (
                            timestamp.isoformat()
                            if timestamp
                            else datetime.now().isoformat()
                        ),
                    }
                )

            return {
                "total_trucks": len(trucks_list),
                "healthy": healthy,
                "watch": watch,
                "warning": warning,
                "critical": critical,
                "trucks": trucks_list,
            }

    except Exception as e:
        logger.error(f"Error getting fleet health summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fuelAnalytics/api/health/truck/{truck_id}", tags=["Health Monitoring"])
async def get_truck_health_report(truck_id: str):
    """
    Get comprehensive health report for a specific truck.

    Uses statistical analysis (Shewhart control charts, Nelson rules)
    to detect sensor anomalies and predict maintenance needs.

    Returns:
        - health_score: 0-100 overall health score
        - sensors: Statistical analysis for each monitored sensor
        - alerts: Current active alerts
        - recommendations: Maintenance recommendations
    """
    if not HEALTH_MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Health monitoring service not available"
        )

    try:
        report = _health_monitor.get_truck_health_report(truck_id)

        if report is None:
            return {
                "truck_id": truck_id,
                "health_score": None,
                "message": "No health data available for this truck",
                "sensors": {},
                "alerts": [],
                "recommendations": [
                    "No data available - ensure truck is transmitting sensor data"
                ],
            }

        return report.to_dict()

    except Exception as e:
        logger.error(f"Error getting health report for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/fuelAnalytics/api/health/truck/{truck_id}/alerts", tags=["Health Monitoring"]
)
async def get_truck_health_alerts(
    truck_id: str,
    hours: int = Query(default=24, ge=1, le=168, description="Hours of alert history"),
):
    """
    Get recent health alerts for a specific truck.

    Returns alerts generated by statistical anomaly detection,
    including Nelson rule violations and sigma-based warnings.
    """
    if not HEALTH_MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Health monitoring service not available"
        )

    try:
        alerts = _health_monitor.get_alerts_for_truck(truck_id, hours=hours)
        return {
            "truck_id": truck_id,
            "hours_back": hours,
            "alert_count": len(alerts),
            "alerts": [alert.to_dict() for alert in alerts],
        }

    except Exception as e:
        logger.error(f"Error getting health alerts for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fuelAnalytics/api/health/record", tags=["Health Monitoring"])
async def record_health_data(
    truck_id: str,
    coolant_temp: Optional[float] = None,
    battery_voltage: Optional[float] = None,
    oil_pressure: Optional[float] = None,
    oil_temp: Optional[float] = None,
):
    """
    Record sensor data for health monitoring.

    This endpoint is called automatically by the data collection service,
    but can also be used manually for testing.

    Returns any alerts triggered by the recorded data.
    """
    if not HEALTH_MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Health monitoring service not available"
        )

    try:
        from datetime import timezone

        alerts = _health_monitor.record_sensor_data(
            truck_id=truck_id,
            timestamp=datetime.now(timezone.utc),
            coolant_temp=coolant_temp,
            battery_voltage=battery_voltage,
            oil_pressure=oil_pressure,
            oil_temp=oil_temp,
        )

        return {
            "success": True,
            "truck_id": truck_id,
            "alerts_triggered": len(alerts),
            "alerts": [alert.to_dict() for alert in alerts],
        }

    except Exception as e:
        logger.error(f"Error recording health data for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fuelAnalytics/api/health/sensors", tags=["Health Monitoring"])
async def get_monitored_sensors():
    """
    Get list of monitored sensors and their configurations.

    Returns the sensors being monitored for health analysis,
    including expected value ranges and units.
    """
    if not HEALTH_MONITOR_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Health monitoring service not available"
        )

    from truck_health_monitor import SENSOR_RANGES

    return {
        "sensors": {
            sensor_type.value: {
                "name": config["name"],
                "min": config["min"],
                "max": config["max"],
                "unit": config["unit"],
            }
            for sensor_type, config in SENSOR_RANGES.items()
        },
        "analysis_windows": ["day", "week", "month"],
        "alert_thresholds": {
            "normal": "< 1σ from mean",
            "watch": "1-2σ from mean",
            "warning": "2-3σ from mean",
            "critical": "> 3σ from mean",
        },
        "nelson_rules": [
            "Rule 1: Point > 3σ (outlier detection)",
            "Rule 2: 9+ points same side of mean (process shift)",
            "Rule 5: 2 of 3 points > 2σ (trend detection)",
            "Rule 7: 15+ points within 1σ (stuck sensor)",
        ],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 ROUTE EFFICIENCY & COST ATTRIBUTION ENDPOINTS (v3.12.0)
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/fuelAnalytics/api/analytics/route-efficiency")
async def get_route_efficiency(
    truck_id: Optional[str] = Query(None, description="Specific truck ID to analyze"),
    days: int = Query(7, ge=1, le=90, description="Days of history to analyze"),
):
    """
    Analyze route efficiency comparing actual vs expected fuel consumption.

    Identifies:
    - Routes with poor fuel economy
    - Driver behavior issues on specific routes
    - Vehicle performance problems

    Returns efficiency metrics, recommendations, and savings opportunities.
    """
    try:
        from database_mysql import get_route_efficiency_analysis

        result = get_route_efficiency_analysis(truck_id=truck_id, days_back=days)
        return result

    except Exception as e:
        logger.error(f"Route efficiency analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fuelAnalytics/api/analytics/cost-attribution")
async def get_cost_attribution(
    days: int = Query(30, ge=1, le=365, description="Days of history to analyze"),
):
    """
    Generate detailed cost attribution report for fleet fuel expenses.

    Breaks down costs by:
    - Per-truck consumption
    - Driving vs idling
    - Efficiency losses
    - Waste categories

    Includes savings opportunities and recommendations.
    """
    try:
        from database_mysql import get_cost_attribution_report

        result = get_cost_attribution_report(days_back=days)
        return result

    except Exception as e:
        logger.error(f"Cost attribution report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fuelAnalytics/api/analytics/inefficiency-causes")
async def get_inefficiency_causes_endpoint(
    truck_id: str = Query("fleet", description="Truck ID or 'fleet' for all"),
    days: int = Query(30, ge=1, le=365, description="Days of history to analyze"),
):
    """
    🆕 v3.14.0: Analyze REAL causes of fuel inefficiency using sensor data.

    Uses actual speed, RPM, and behavior patterns to attribute inefficiency:
    - High Speed Driving (>65 mph): Aerodynamic drag
    - High RPM Operation (>1600): Less efficient
    - Excessive Idle: Fuel burned with no miles

    Returns breakdown with percentages, impact in gallons/cost, and recommendations.
    """
    try:
        from database_mysql import get_inefficiency_causes

        result = get_inefficiency_causes(truck_id=truck_id, days_back=days)
        return result

    except Exception as e:
        logger.error(f"Inefficiency causes analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fuelAnalytics/api/analytics/inefficiency-by-truck")
async def get_inefficiency_by_truck_endpoint(
    days: int = Query(30, ge=1, le=365, description="Days of history to analyze"),
    sort_by: str = Query(
        "total_cost",
        description="Sort by: total_cost, high_load, high_speed, idle, low_mpg, high_rpm",
    ),
):
    """
    🆕 v3.12.33: Get inefficiency breakdown BY TRUCK with all causes.

    Returns each truck with their specific inefficiency causes and costs,
    sorted by the specified metric.

    Useful for:
    - Identifying which trucks need attention
    - Driver coaching targets
    - Maintenance prioritization
    - Route optimization candidates
    """
    try:
        from database_mysql import get_inefficiency_by_truck

        result = get_inefficiency_by_truck(days_back=days, sort_by=sort_by)
        return result

    except Exception as e:
        logger.error(f"Inefficiency by truck error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 GEOFENCING ENDPOINTS (v3.12.0)
# ═══════════════════════════════════════════════════════════════════════════════


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/geofence/events")
# MIGRATED_TO_ROUTER: async def get_geofence_events_endpoint(
# MIGRATED_TO_ROUTER:     truck_id: Optional[str] = Query(None, description="Specific truck ID"),
# MIGRATED_TO_ROUTER:     hours: int = Query(24, ge=1, le=168, description="Hours of history"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     Get geofence entry/exit events for trucks.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Tracks when trucks enter or exit defined zones.
# MIGRATED_TO_ROUTER:     Useful for monitoring:
# MIGRATED_TO_ROUTER:     - Fuel station visits
# MIGRATED_TO_ROUTER:     - Unauthorized stops
# MIGRATED_TO_ROUTER:     - Route compliance
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_geofence_events
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         result = get_geofence_events(truck_id=truck_id, hours_back=hours)
# MIGRATED_TO_ROUTER:         return result
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Geofence events error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/geofence/location-history/{truck_id}")
# MIGRATED_TO_ROUTER: async def get_location_history(
# MIGRATED_TO_ROUTER:     truck_id: str,
# MIGRATED_TO_ROUTER:     hours: int = Query(24, ge=1, le=168, description="Hours of history"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     Get GPS location history for a truck (for map visualization).
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns a list of location points with timestamps,
# MIGRATED_TO_ROUTER:     speed, status, and fuel level.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_truck_location_history
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         result = get_truck_location_history(truck_id=truck_id, hours_back=hours)
# MIGRATED_TO_ROUTER:         return {"truck_id": truck_id, "hours": hours, "locations": result}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Location history error for {truck_id}: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/geofence/zones")
# MIGRATED_TO_ROUTER: async def get_geofence_zones():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     Get list of defined geofence zones.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns zone configurations including:
# MIGRATED_TO_ROUTER:     - Zone ID and name
# MIGRATED_TO_ROUTER:     - Type (CIRCLE, POLYGON)
# MIGRATED_TO_ROUTER:     - Coordinates and radius
# MIGRATED_TO_ROUTER:     - Alert settings
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import GEOFENCE_ZONES
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         zones = []
# MIGRATED_TO_ROUTER:         for zone_id, zone in GEOFENCE_ZONES.items():
# MIGRATED_TO_ROUTER:             zones.append(
# MIGRATED_TO_ROUTER:                 {
# MIGRATED_TO_ROUTER:                     "zone_id": zone_id,
# MIGRATED_TO_ROUTER:                     "name": zone["name"],
# MIGRATED_TO_ROUTER:                     "type": zone["type"],
# MIGRATED_TO_ROUTER:                     "latitude": zone.get("lat"),
# MIGRATED_TO_ROUTER:                     "longitude": zone.get("lon"),
# MIGRATED_TO_ROUTER:                     "radius_miles": zone.get("radius_miles"),
# MIGRATED_TO_ROUTER:                     "alert_on_enter": zone.get("alert_on_enter", False),
# MIGRATED_TO_ROUTER:                     "alert_on_exit": zone.get("alert_on_exit", False),
# MIGRATED_TO_ROUTER:                 }
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {"zones": zones, "total": len(zones)}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Get geofence zones error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 PREDICTIVE ALERTS ENDPOINT (v3.12.0)
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/fuelAnalytics/api/alerts/predictive")
async def get_predictive_alerts(
    hours: int = Query(24, ge=1, le=168, description="Hours of alert history"),
):
    """
    Get predictive alerts including:
    - MPG decline trends (maintenance indicator)
    - Fuel theft patterns
    - Driver behavior issues
    - Fleet health summary

    These alerts use historical data to predict issues
    before they become critical problems.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        # Get current truck data from fuel_metrics
        engine = get_sqlalchemy_engine()
        query = text(
            """
            SELECT 
                fm.truck_id,
                fm.truck_status as status,
                fm.sensor_pct as fuel_pct,
                fm.estimated_pct,
                fm.mpg_current as mpg,
                fm.consumption_gph,
                fm.drift_pct,
                fm.drift_warning,
                fm.timestamp_utc
            FROM fuel_metrics fm
            INNER JOIN (
                SELECT truck_id, MAX(timestamp_utc) as max_ts
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 2 HOUR)
                GROUP BY truck_id
            ) latest ON fm.truck_id = latest.truck_id AND fm.timestamp_utc = latest.max_ts
        """
        )

        with engine.connect() as conn:
            result = conn.execute(query)
            rows = result.fetchall()

        truck_data = []
        for row in rows:
            truck_data.append(
                {
                    "truck_id": row[0],
                    "truck_status": row[1],
                    "status": row[1],
                    "fuel_pct": row[2],
                    "estimated_pct": row[3],
                    "mpg": row[4],
                    "mpg_current": row[4],
                    "consumption_gph": row[5],
                    "drift_pct": row[6],
                    "drift_warning": row[7],
                    "timestamp": row[8].isoformat() if row[8] else None,
                }
            )

        # Try to use AlertSystem, fallback to basic response
        alerts_list = []
        health_summary = {
            "total_trucks": len(truck_data),
            "healthy_trucks": len(
                [t for t in truck_data if t.get("drift_warning") != "YES"]
            ),
            "trucks_with_alerts": 0,
            "critical_alerts": 0,
        }

        try:
            from alert_system import AlertSystem

            alert_system = AlertSystem()
            alerts = alert_system.check_fleet_alerts(truck_data)
            health_summary = alert_system.get_fleet_health_summary(truck_data)
            alerts_list = [alert.to_dict() for alert in alerts]
        except Exception as alert_err:
            logger.warning(
                f"AlertSystem not available, using basic response: {alert_err}"
            )

        return {
            "alerts": alerts_list,
            "fleet_health": health_summary,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        import traceback

        error_details = traceback.format_exc()
        logger.error(f"Predictive alerts error: {e}\n{error_details}")
        raise HTTPException(
            status_code=500, detail=f"{str(e)} - Check server logs for details"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.8.3: DIAGNOSTICS ALERTS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/fuelAnalytics/api/alerts/diagnostics", tags=["Alerts"])
async def get_diagnostics_alerts():
    """
    🆕 v5.8.3: Get diagnostic alerts (DTC, Voltage, GPS quality).

    Returns alerts for:
    - DTC codes (engine trouble codes)
    - Low/high voltage issues
    - Poor GPS quality
    """
    try:
        from routers.alerts_router import get_diagnostic_alerts, DIAGNOSTICS_AVAILABLE

        if not DIAGNOSTICS_AVAILABLE:
            return {"alerts": [], "message": "Diagnostic modules not available"}

        return await get_diagnostic_alerts()
    except Exception as e:
        logger.error(f"Error getting diagnostic alerts: {e}")
        return {"alerts": [], "error": str(e)}


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.8.3: UNIFIED ALERTS ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@app.get("/fuelAnalytics/api/alerts/unified", tags=["Alerts"])
async def get_unified_alerts(
    include_predictive: bool = Query(True, description="Include predictive alerts"),
    include_diagnostics: bool = Query(True, description="Include diagnostic alerts"),
    include_system: bool = Query(True, description="Include system alerts"),
    days_ahead: int = Query(7, ge=1, le=30, description="Days ahead for predictions"),
):
    """
    🆕 v5.8.3: Unified alerts endpoint combining all alert types.

    Returns a single response with:
    - System alerts (drift, offline, anomalies)
    - Predictive alerts (low fuel, calibration, efficiency)
    - Diagnostic alerts (DTC, voltage, GPS quality)
    """
    try:
        result = {
            "system_alerts": [],
            "predictive_alerts": [],
            "diagnostic_alerts": [],
            "summary": {
                "total": 0,
                "critical": 0,
                "warning": 0,
                "info": 0,
            },
            "generated_at": datetime.now().isoformat(),
        }

        # Get system alerts
        if include_system:
            try:
                from database import db

                system_alerts = db.get_alerts()
                result["system_alerts"] = system_alerts
                for alert in system_alerts:
                    severity = alert.get("severity", "info")
                    result["summary"]["total"] += 1
                    result["summary"][severity] = result["summary"].get(severity, 0) + 1
            except Exception as e:
                logger.warning(f"Could not get system alerts: {e}")

        # Get predictive alerts
        if include_predictive:
            try:
                predictive_response = await get_predictive_alerts(hours=24)
                result["predictive_alerts"] = predictive_response.get("alerts", [])
                for alert in result["predictive_alerts"]:
                    severity = alert.get("severity", "info")
                    result["summary"]["total"] += 1
                    result["summary"][severity] = result["summary"].get(severity, 0) + 1
            except Exception as e:
                logger.warning(f"Could not get predictive alerts: {e}")

        # Get diagnostic alerts
        if include_diagnostics:
            try:
                from routers.alerts_router import (
                    get_diagnostic_alerts,
                    DIAGNOSTICS_AVAILABLE,
                )

                if DIAGNOSTICS_AVAILABLE:
                    diag_response = await get_diagnostic_alerts()
                    import json

                    diag_data = (
                        json.loads(diag_response.body.decode())
                        if hasattr(diag_response, "body")
                        else {}
                    )
                    result["diagnostic_alerts"] = diag_data.get("alerts", [])
                    for alert in result["diagnostic_alerts"]:
                        severity = alert.get("severity", "info")
                        result["summary"]["total"] += 1
                        result["summary"][severity] = (
                            result["summary"].get(severity, 0) + 1
                        )
            except Exception as e:
                logger.warning(f"Could not get diagnostic alerts: {e}")

        return result

    except Exception as e:
        logger.error(f"Error in unified alerts: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generating unified alerts: {str(e)}"
        )


# ============================================================================
# 🆕 FASE 2: NEXT REFUEL PREDICTION v3.12.21
# ============================================================================


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/analytics/next-refuel-prediction")
# MIGRATED_TO_ROUTER: async def get_next_refuel_prediction(
# MIGRATED_TO_ROUTER:     truck_id: Optional[str] = Query(
# MIGRATED_TO_ROUTER:         default=None, description="Specific truck or None for all"
# MIGRATED_TO_ROUTER:     ),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Predict when each truck needs its next refuel
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Uses:
# MIGRATED_TO_ROUTER:     - Current fuel level (%)
# MIGRATED_TO_ROUTER:     - Average consumption rate (gal/hour moving, gal/hour idle)
# MIGRATED_TO_ROUTER:     - Historical refuel patterns
# MIGRATED_TO_ROUTER:     - Planned route (if available)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:         - Estimated hours/miles until refuel needed
# MIGRATED_TO_ROUTER:         - Recommended refuel location (nearest fuel stops)
# MIGRATED_TO_ROUTER:         - Confidence level based on data quality
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# Query using fuel_metrics table (which exists)
# Get latest data for each truck
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 fm.truck_id,
# MIGRATED_TO_ROUTER:                 fm.sensor_pct as current_fuel_pct,
# MIGRATED_TO_ROUTER:                 fm.estimated_pct as kalman_fuel_pct,
# MIGRATED_TO_ROUTER:                 fm.mpg_current as avg_mpg_24h,
# MIGRATED_TO_ROUTER:                 fm.consumption_gph as avg_consumption_gph_24h,
# MIGRATED_TO_ROUTER:                 CASE WHEN fm.truck_status = 'IDLE' THEN fm.consumption_gph ELSE 0.8 END as avg_idle_gph_24h,
# MIGRATED_TO_ROUTER:                 fm.truck_status,
# MIGRATED_TO_ROUTER:                 fm.speed_mph as speed,
# MIGRATED_TO_ROUTER:                 fm.timestamp_utc
# MIGRATED_TO_ROUTER:             FROM fuel_metrics fm
# MIGRATED_TO_ROUTER:             INNER JOIN (
# MIGRATED_TO_ROUTER:                 SELECT truck_id, MAX(timestamp_utc) as max_ts
# MIGRATED_TO_ROUTER:                 FROM fuel_metrics
# MIGRATED_TO_ROUTER:                 WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 2 HOUR)
# MIGRATED_TO_ROUTER:                 GROUP BY truck_id
# MIGRATED_TO_ROUTER:             ) latest ON fm.truck_id = latest.truck_id AND fm.timestamp_utc = latest.max_ts
# MIGRATED_TO_ROUTER:             WHERE fm.truck_id IS NOT NULL
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if truck_id:
# MIGRATED_TO_ROUTER:             query += " AND fm.truck_id = :truck_id"
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             if truck_id:
# MIGRATED_TO_ROUTER:                 result = conn.execute(text(query), {"truck_id": truck_id})
# MIGRATED_TO_ROUTER:             else:
# MIGRATED_TO_ROUTER:                 result = conn.execute(text(query))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             rows = result.fetchall()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         predictions = []
# MIGRATED_TO_ROUTER:         for row in rows:
# MIGRATED_TO_ROUTER:             row_dict = dict(row._mapping)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             current_pct = (
# MIGRATED_TO_ROUTER:                 row_dict.get("kalman_fuel_pct")
# MIGRATED_TO_ROUTER:                 or row_dict.get("current_fuel_pct")
# MIGRATED_TO_ROUTER:                 or 50
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:             consumption_gph = row_dict.get("avg_consumption_gph_24h") or 4.0
# MIGRATED_TO_ROUTER:             idle_gph = row_dict.get("avg_idle_gph_24h") or 0.8
# MIGRATED_TO_ROUTER:             avg_mpg = row_dict.get("avg_mpg_24h") or 5.7  # v3.12.31: updated baseline
# MIGRATED_TO_ROUTER:             status = row_dict.get("truck_status") or "STOPPED"
# MIGRATED_TO_ROUTER:
# Estimate tank capacity (assume 200 gal for now, could be from trucks table)
# MIGRATED_TO_ROUTER:             tank_capacity_gal = 200
# MIGRATED_TO_ROUTER:
# Current gallons
# MIGRATED_TO_ROUTER:             current_gallons = (current_pct / 100) * tank_capacity_gal
# MIGRATED_TO_ROUTER:
# Gallons until low fuel (assume 15% threshold)
# MIGRATED_TO_ROUTER:             low_fuel_threshold_pct = 15
# MIGRATED_TO_ROUTER:             gallons_until_low = current_gallons - (
# MIGRATED_TO_ROUTER:                 low_fuel_threshold_pct / 100 * tank_capacity_gal
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             if gallons_until_low <= 0:
# MIGRATED_TO_ROUTER:                 hours_until_refuel = 0
# MIGRATED_TO_ROUTER:                 miles_until_refuel = 0
# MIGRATED_TO_ROUTER:                 urgency = "critical"
# MIGRATED_TO_ROUTER:             else:
# Calculate based on moving vs idle
# MIGRATED_TO_ROUTER:                 if status == "MOVING":
# MIGRATED_TO_ROUTER:                     current_consumption = consumption_gph
# MIGRATED_TO_ROUTER:                 else:
# MIGRATED_TO_ROUTER:                     current_consumption = idle_gph
# MIGRATED_TO_ROUTER:
# Weighted average assuming 70% moving, 30% idle
# MIGRATED_TO_ROUTER:                 blended_consumption = (consumption_gph * 0.7) + (idle_gph * 0.3)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:                 hours_until_refuel = (
# MIGRATED_TO_ROUTER:                     gallons_until_low / blended_consumption
# MIGRATED_TO_ROUTER:                     if blended_consumption > 0
# MIGRATED_TO_ROUTER:                     else 999
# MIGRATED_TO_ROUTER:                 )
# MIGRATED_TO_ROUTER:                 miles_until_refuel = (
# MIGRATED_TO_ROUTER:                     hours_until_refuel * 50 if avg_mpg and avg_mpg > 0 else 0
# MIGRATED_TO_ROUTER:                 )  # Assume 50 mph avg
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:                 if hours_until_refuel < 4:
# MIGRATED_TO_ROUTER:                     urgency = "critical"
# MIGRATED_TO_ROUTER:                 elif hours_until_refuel < 8:
# MIGRATED_TO_ROUTER:                     urgency = "warning"
# MIGRATED_TO_ROUTER:                 elif hours_until_refuel < 24:
# MIGRATED_TO_ROUTER:                     urgency = "normal"
# MIGRATED_TO_ROUTER:                 else:
# MIGRATED_TO_ROUTER:                     urgency = "good"
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             predictions.append(
# MIGRATED_TO_ROUTER:                 {
# MIGRATED_TO_ROUTER:                     "truck_id": row_dict["truck_id"],
# MIGRATED_TO_ROUTER:                     "current_fuel_pct": round(current_pct, 1),
# MIGRATED_TO_ROUTER:                     "current_gallons": round(current_gallons, 1),
# MIGRATED_TO_ROUTER:                     "hours_until_refuel": (
# MIGRATED_TO_ROUTER:                         round(hours_until_refuel, 1)
# MIGRATED_TO_ROUTER:                         if hours_until_refuel < 999
# MIGRATED_TO_ROUTER:                         else None
# MIGRATED_TO_ROUTER:                     ),
# MIGRATED_TO_ROUTER:                     "miles_until_refuel": (
# MIGRATED_TO_ROUTER:                         round(miles_until_refuel, 0) if miles_until_refuel > 0 else None
# MIGRATED_TO_ROUTER:                     ),
# MIGRATED_TO_ROUTER:                     "urgency": urgency,
# MIGRATED_TO_ROUTER:                     "estimated_refuel_time": (
# MIGRATED_TO_ROUTER:                         (
# MIGRATED_TO_ROUTER:                             datetime.now() + timedelta(hours=hours_until_refuel)
# MIGRATED_TO_ROUTER:                         ).isoformat()
# MIGRATED_TO_ROUTER:                         if hours_until_refuel < 999
# MIGRATED_TO_ROUTER:                         else None
# MIGRATED_TO_ROUTER:                     ),
# MIGRATED_TO_ROUTER:                     "avg_consumption_gph": round(consumption_gph, 2),
# MIGRATED_TO_ROUTER:                     "confidence": (
# MIGRATED_TO_ROUTER:                         "high" if row_dict.get("avg_consumption_gph_24h") else "medium"
# MIGRATED_TO_ROUTER:                     ),
# MIGRATED_TO_ROUTER:                 }
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# Sort by urgency (critical first)
# MIGRATED_TO_ROUTER:         urgency_order = {"critical": 0, "warning": 1, "normal": 2, "good": 3}
# MIGRATED_TO_ROUTER:         predictions.sort(
# MIGRATED_TO_ROUTER:             key=lambda x: (
# MIGRATED_TO_ROUTER:                 urgency_order.get(x["urgency"], 99),
# MIGRATED_TO_ROUTER:                 x.get("hours_until_refuel") or 999,
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "predictions": predictions,
# MIGRATED_TO_ROUTER:             "count": len(predictions),
# MIGRATED_TO_ROUTER:             "critical_count": len(
# MIGRATED_TO_ROUTER:                 [p for p in predictions if p["urgency"] == "critical"]
# MIGRATED_TO_ROUTER:             ),
# MIGRATED_TO_ROUTER:             "warning_count": len([p for p in predictions if p["urgency"] == "warning"]),
# MIGRATED_TO_ROUTER:             "timestamp": datetime.now().isoformat(),
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Next refuel prediction error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 FASE 2: EXPORT TO EXCEL/CSV v3.12.21
# ============================================================================


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/export/fleet-report")
# MIGRATED_TO_ROUTER: async def export_fleet_report(
# MIGRATED_TO_ROUTER:     format: str = Query(default="csv", description="Export format: csv or excel"),
# MIGRATED_TO_ROUTER:     days: int = Query(default=7, ge=1, le=90, description="Days to include"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Export fleet data to CSV or Excel
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Includes:
# MIGRATED_TO_ROUTER:     - All trucks with current status
# MIGRATED_TO_ROUTER:     - MPG, fuel consumption, idle metrics
# MIGRATED_TO_ROUTER:     - Refuel events
# MIGRATED_TO_ROUTER:     - Alerts/issues
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         import io
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# Get fleet data
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 truck_id,
# MIGRATED_TO_ROUTER:                 truck_status as status,
# MIGRATED_TO_ROUTER:                 COALESCE(sensor_pct, 0) as fuel_pct,
# MIGRATED_TO_ROUTER:                 COALESCE(estimated_pct, 0) as estimated_fuel_pct,
# MIGRATED_TO_ROUTER:                 COALESCE(drift_pct, 0) as drift_pct,
# MIGRATED_TO_ROUTER:                 COALESCE(mpg_current, 0) as current_mpg,
# MIGRATED_TO_ROUTER:                 COALESCE(avg_mpg_24h, 0) as avg_mpg_24h,
# MIGRATED_TO_ROUTER:                 COALESCE(consumption_gph, 0) as consumption_gph,
# MIGRATED_TO_ROUTER:                 COALESCE(idle_consumption_gph, 0) as idle_gph,
# MIGRATED_TO_ROUTER:                 COALESCE(speed, 0) as speed_mph,
# MIGRATED_TO_ROUTER:                 latitude,
# MIGRATED_TO_ROUTER:                 longitude,
# MIGRATED_TO_ROUTER:                 timestamp_utc as last_update
# MIGRATED_TO_ROUTER:             FROM truck_data_latest
# MIGRATED_TO_ROUTER:             WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:             ORDER BY truck_id
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(query), {"days": days})
# MIGRATED_TO_ROUTER:             data = [dict(row._mapping) for row in result.fetchall()]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if not data:
# MIGRATED_TO_ROUTER:             raise HTTPException(
# MIGRATED_TO_ROUTER:                 status_code=404, detail="No data found for the specified period"
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         df = pd.DataFrame(data)
# MIGRATED_TO_ROUTER:
# Format datetime columns
# MIGRATED_TO_ROUTER:         if "last_update" in df.columns:
# MIGRATED_TO_ROUTER:             df["last_update"] = pd.to_datetime(df["last_update"]).dt.strftime(
# MIGRATED_TO_ROUTER:                 "%Y-%m-%d %H:%M:%S"
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if format.lower() == "excel":
# MIGRATED_TO_ROUTER:             output = io.BytesIO()
# MIGRATED_TO_ROUTER:             with pd.ExcelWriter(output, engine="openpyxl") as writer:
# MIGRATED_TO_ROUTER:                 df.to_excel(writer, sheet_name="Fleet Report", index=False)
# MIGRATED_TO_ROUTER:             output.seek(0)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             filename = f"fleet_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
# MIGRATED_TO_ROUTER:             return Response(
# MIGRATED_TO_ROUTER:                 content=output.getvalue(),
# MIGRATED_TO_ROUTER:                 media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
# MIGRATED_TO_ROUTER:                 headers={"Content-Disposition": f"attachment; filename={filename}"},
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:         else:
# Default to CSV
# MIGRATED_TO_ROUTER:             output = io.StringIO()
# MIGRATED_TO_ROUTER:             df.to_csv(output, index=False)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             filename = f"fleet_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
# MIGRATED_TO_ROUTER:             return Response(
# MIGRATED_TO_ROUTER:                 content=output.getvalue(),
# MIGRATED_TO_ROUTER:                 media_type="text/csv",
# MIGRATED_TO_ROUTER:                 headers={"Content-Disposition": f"attachment; filename={filename}"},
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Export error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v3.12.21: HISTORICAL COMPARISON ENDPOINTS (#12)
# ============================================================================


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/analytics/historical-comparison", tags=["Analytics"])
# MIGRATED_TO_ROUTER: async def get_historical_comparison(
# MIGRATED_TO_ROUTER:     period1_start: str = Query(..., description="Start date for period 1 (YYYY-MM-DD)"),
# MIGRATED_TO_ROUTER:     period1_end: str = Query(..., description="End date for period 1 (YYYY-MM-DD)"),
# MIGRATED_TO_ROUTER:     period2_start: str = Query(..., description="Start date for period 2 (YYYY-MM-DD)"),
# MIGRATED_TO_ROUTER:     period2_end: str = Query(..., description="End date for period 2 (YYYY-MM-DD)"),
# MIGRATED_TO_ROUTER:     truck_id: Optional[str] = Query(None, description="Specific truck ID (optional)"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Compare fleet metrics between two time periods.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Useful for:
# MIGRATED_TO_ROUTER:     - Month-over-month comparison
# MIGRATED_TO_ROUTER:     - Before/after analysis (e.g., driver training impact)
# MIGRATED_TO_ROUTER:     - Seasonal patterns
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns changes in:
# MIGRATED_TO_ROUTER:     - MPG, fuel consumption, idle time
# MIGRATED_TO_ROUTER:     - Cost metrics
# MIGRATED_TO_ROUTER:     - Refuel patterns
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# Build query for both periods
# MIGRATED_TO_ROUTER:         base_query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 COUNT(DISTINCT truck_id) as truck_count,
# MIGRATED_TO_ROUTER:                 AVG(mpg) as avg_mpg,
# MIGRATED_TO_ROUTER:                 AVG(consumption_gph) as avg_consumption_gph,
# MIGRATED_TO_ROUTER:                 AVG(idle_pct) as avg_idle_pct,
# MIGRATED_TO_ROUTER:                 SUM(CASE WHEN event_type = 'REFUEL' THEN 1 ELSE 0 END) as refuel_count,
# MIGRATED_TO_ROUTER:                 AVG(sensor_fuel_pct) as avg_fuel_level,
# MIGRATED_TO_ROUTER:                 AVG(daily_miles) as avg_daily_miles,
# MIGRATED_TO_ROUTER:                 SUM(fuel_consumed_gal) as total_fuel_consumed
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE timestamp_utc BETWEEN :start_date AND :end_date
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         truck_filter = " AND truck_id = :truck_id" if truck_id else ""
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# Period 1
# MIGRATED_TO_ROUTER:             params1 = {
# MIGRATED_TO_ROUTER:                 "start_date": period1_start,
# MIGRATED_TO_ROUTER:                 "end_date": period1_end,
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:             if truck_id:
# MIGRATED_TO_ROUTER:                 params1["truck_id"] = truck_id
# MIGRATED_TO_ROUTER:             result1 = (
# MIGRATED_TO_ROUTER:                 conn.execute(text(base_query + truck_filter), params1)
# MIGRATED_TO_ROUTER:                 .mappings()
# MIGRATED_TO_ROUTER:                 .fetchone()
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# Period 2
# MIGRATED_TO_ROUTER:             params2 = {
# MIGRATED_TO_ROUTER:                 "start_date": period2_start,
# MIGRATED_TO_ROUTER:                 "end_date": period2_end,
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:             if truck_id:
# MIGRATED_TO_ROUTER:                 params2["truck_id"] = truck_id
# MIGRATED_TO_ROUTER:             result2 = (
# MIGRATED_TO_ROUTER:                 conn.execute(text(base_query + truck_filter), params2)
# MIGRATED_TO_ROUTER:                 .mappings()
# MIGRATED_TO_ROUTER:                 .fetchone()
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         def safe_pct_change(old, new):
# MIGRATED_TO_ROUTER:             if old and old > 0 and new:
# MIGRATED_TO_ROUTER:                 return round(((new - old) / old) * 100, 1)
# MIGRATED_TO_ROUTER:             return None
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         def safe_val(val):
# MIGRATED_TO_ROUTER:             return round(float(val), 2) if val else 0
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         period1_data = dict(result1) if result1 else {}
# MIGRATED_TO_ROUTER:         period2_data = dict(result2) if result2 else {}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "period1": {
# MIGRATED_TO_ROUTER:                 "start": period1_start,
# MIGRATED_TO_ROUTER:                 "end": period1_end,
# MIGRATED_TO_ROUTER:                 "avg_mpg": safe_val(period1_data.get("avg_mpg")),
# MIGRATED_TO_ROUTER:                 "avg_consumption_gph": safe_val(
# MIGRATED_TO_ROUTER:                     period1_data.get("avg_consumption_gph")
# MIGRATED_TO_ROUTER:                 ),
# MIGRATED_TO_ROUTER:                 "avg_idle_pct": safe_val(period1_data.get("avg_idle_pct")),
# MIGRATED_TO_ROUTER:                 "refuel_count": int(period1_data.get("refuel_count") or 0),
# MIGRATED_TO_ROUTER:                 "total_fuel_consumed": safe_val(
# MIGRATED_TO_ROUTER:                     period1_data.get("total_fuel_consumed")
# MIGRATED_TO_ROUTER:                 ),
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             "period2": {
# MIGRATED_TO_ROUTER:                 "start": period2_start,
# MIGRATED_TO_ROUTER:                 "end": period2_end,
# MIGRATED_TO_ROUTER:                 "avg_mpg": safe_val(period2_data.get("avg_mpg")),
# MIGRATED_TO_ROUTER:                 "avg_consumption_gph": safe_val(
# MIGRATED_TO_ROUTER:                     period2_data.get("avg_consumption_gph")
# MIGRATED_TO_ROUTER:                 ),
# MIGRATED_TO_ROUTER:                 "avg_idle_pct": safe_val(period2_data.get("avg_idle_pct")),
# MIGRATED_TO_ROUTER:                 "refuel_count": int(period2_data.get("refuel_count") or 0),
# MIGRATED_TO_ROUTER:                 "total_fuel_consumed": safe_val(
# MIGRATED_TO_ROUTER:                     period2_data.get("total_fuel_consumed")
# MIGRATED_TO_ROUTER:                 ),
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             "changes": {
# MIGRATED_TO_ROUTER:                 "mpg_change_pct": safe_pct_change(
# MIGRATED_TO_ROUTER:                     period1_data.get("avg_mpg"), period2_data.get("avg_mpg")
# MIGRATED_TO_ROUTER:                 ),
# MIGRATED_TO_ROUTER:                 "consumption_change_pct": safe_pct_change(
# MIGRATED_TO_ROUTER:                     period1_data.get("avg_consumption_gph"),
# MIGRATED_TO_ROUTER:                     period2_data.get("avg_consumption_gph"),
# MIGRATED_TO_ROUTER:                 ),
# MIGRATED_TO_ROUTER:                 "idle_change_pct": safe_pct_change(
# MIGRATED_TO_ROUTER:                     period1_data.get("avg_idle_pct"), period2_data.get("avg_idle_pct")
# MIGRATED_TO_ROUTER:                 ),
# MIGRATED_TO_ROUTER:                 "fuel_consumed_change_pct": safe_pct_change(
# MIGRATED_TO_ROUTER:                     period1_data.get("total_fuel_consumed"),
# MIGRATED_TO_ROUTER:                     period2_data.get("total_fuel_consumed"),
# MIGRATED_TO_ROUTER:                 ),
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             "truck_id": truck_id,
# MIGRATED_TO_ROUTER:             "generated_at": datetime.now().isoformat(),
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Historical comparison error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/analytics/trends", tags=["Analytics"])
# MIGRATED_TO_ROUTER: async def get_fleet_trends(
# MIGRATED_TO_ROUTER:     days: int = Query(30, ge=7, le=365, description="Days of history"),
# MIGRATED_TO_ROUTER:     metric: str = Query(
# MIGRATED_TO_ROUTER:         "mpg", description="Metric to trend: mpg, consumption, idle, fuel_level"
# MIGRATED_TO_ROUTER:     ),
# MIGRATED_TO_ROUTER:     truck_id: Optional[str] = Query(None, description="Specific truck ID (optional)"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get daily trends for a specific metric.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns daily averages for charting/visualization.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         metric_map = {
# MIGRATED_TO_ROUTER:             "mpg": "AVG(mpg)",
# MIGRATED_TO_ROUTER:             "consumption": "AVG(consumption_gph)",
# MIGRATED_TO_ROUTER:             "idle": "AVG(idle_pct)",
# MIGRATED_TO_ROUTER:             "fuel_level": "AVG(sensor_fuel_pct)",
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if metric not in metric_map:
# MIGRATED_TO_ROUTER:             raise HTTPException(status_code=400, detail=f"Invalid metric: {metric}")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         query = f"""
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 DATE(timestamp_utc) as date,
# MIGRATED_TO_ROUTER:                 {metric_map[metric]} as value,
# MIGRATED_TO_ROUTER:                 COUNT(*) as sample_count
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:             {"AND truck_id = :truck_id" if truck_id else ""}
# MIGRATED_TO_ROUTER:             GROUP BY DATE(timestamp_utc)
# MIGRATED_TO_ROUTER:             ORDER BY date ASC
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         params = {"days": days}
# MIGRATED_TO_ROUTER:         if truck_id:
# MIGRATED_TO_ROUTER:             params["truck_id"] = truck_id
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(query), params).mappings().fetchall()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         trends = [
# MIGRATED_TO_ROUTER:             {
# MIGRATED_TO_ROUTER:                 "date": str(row["date"]),
# MIGRATED_TO_ROUTER:                 "value": round(float(row["value"]), 2) if row["value"] else None,
# MIGRATED_TO_ROUTER:                 "sample_count": int(row["sample_count"]),
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:             for row in result
# MIGRATED_TO_ROUTER:         ]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "metric": metric,
# MIGRATED_TO_ROUTER:             "days": days,
# MIGRATED_TO_ROUTER:             "truck_id": truck_id,
# MIGRATED_TO_ROUTER:             "data": trends,
# MIGRATED_TO_ROUTER:             "count": len(trends),
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Fleet trends error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v3.12.21: SCHEDULED REPORTS ENDPOINTS (#13)
# ============================================================================

# In-memory storage for report schedules (in production, use database)
_scheduled_reports: Dict[str, Dict] = {}


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/reports/schedules", tags=["Reports"])
# MIGRATED_TO_ROUTER: async def get_report_schedules():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get all scheduled reports.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     return {
# MIGRATED_TO_ROUTER:         "schedules": list(_scheduled_reports.values()),
# MIGRATED_TO_ROUTER:         "count": len(_scheduled_reports),
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post("/fuelAnalytics/api/reports/schedules", tags=["Reports"])
# MIGRATED_TO_ROUTER: async def create_report_schedule(
# MIGRATED_TO_ROUTER:     name: str = Query(..., description="Report name"),
# MIGRATED_TO_ROUTER:     report_type: str = Query(
# MIGRATED_TO_ROUTER:         ..., description="Type: daily_summary, weekly_kpis, monthly_analysis"
# MIGRATED_TO_ROUTER:     ),
# MIGRATED_TO_ROUTER:     frequency: str = Query(..., description="Frequency: daily, weekly, monthly"),
# MIGRATED_TO_ROUTER:     email_to: str = Query(..., description="Email recipient(s), comma-separated"),
# MIGRATED_TO_ROUTER:     include_trucks: Optional[str] = Query(
# MIGRATED_TO_ROUTER:         None, description="Truck IDs to include, comma-separated (all if empty)"
# MIGRATED_TO_ROUTER:     ),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Create a scheduled report.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Note: In production, this would be stored in database and processed by a scheduler.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     import uuid
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     schedule_id = str(uuid.uuid4())[:8]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     schedule = {
# MIGRATED_TO_ROUTER:         "id": schedule_id,
# MIGRATED_TO_ROUTER:         "name": name,
# MIGRATED_TO_ROUTER:         "report_type": report_type,
# MIGRATED_TO_ROUTER:         "frequency": frequency,
# MIGRATED_TO_ROUTER:         "email_to": [e.strip() for e in email_to.split(",")],
# MIGRATED_TO_ROUTER:         "include_trucks": (
# MIGRATED_TO_ROUTER:             [t.strip() for t in include_trucks.split(",")] if include_trucks else None
# MIGRATED_TO_ROUTER:         ),
# MIGRATED_TO_ROUTER:         "created_at": datetime.now().isoformat(),
# MIGRATED_TO_ROUTER:         "last_run": None,
# MIGRATED_TO_ROUTER:         "next_run": None,  # Would be calculated by scheduler
# MIGRATED_TO_ROUTER:         "status": "active",
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     _scheduled_reports[schedule_id] = schedule
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {
# MIGRATED_TO_ROUTER:         "success": True,
# MIGRATED_TO_ROUTER:         "schedule": schedule,
# MIGRATED_TO_ROUTER:         "message": f"Report schedule '{name}' created successfully",
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.delete("/fuelAnalytics/api/reports/schedules/{schedule_id}", tags=["Reports"])
# MIGRATED_TO_ROUTER: async def delete_report_schedule(schedule_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Delete a scheduled report.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if schedule_id not in _scheduled_reports:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=404, detail="Schedule not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     del _scheduled_reports[schedule_id]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {
# MIGRATED_TO_ROUTER:         "success": True,
# MIGRATED_TO_ROUTER:         "message": f"Schedule {schedule_id} deleted",
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post("/fuelAnalytics/api/reports/generate", tags=["Reports"])
# MIGRATED_TO_ROUTER: async def generate_report_now(
# MIGRATED_TO_ROUTER:     report_type: str = Query(
# MIGRATED_TO_ROUTER:         ..., description="Type: daily_summary, weekly_kpis, theft_analysis"
# MIGRATED_TO_ROUTER:     ),
# MIGRATED_TO_ROUTER:     days: int = Query(7, ge=1, le=90, description="Days to include"),
# MIGRATED_TO_ROUTER:     format: str = Query("json", description="Format: json, csv, excel"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Generate a report immediately.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns the report data or file depending on format.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:         import io
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if report_type == "daily_summary":
# MIGRATED_TO_ROUTER:             query = """
# MIGRATED_TO_ROUTER:                 SELECT
# MIGRATED_TO_ROUTER:                     truck_id,
# MIGRATED_TO_ROUTER:                     DATE(timestamp_utc) as date,
# MIGRATED_TO_ROUTER:                     AVG(mpg) as avg_mpg,
# MIGRATED_TO_ROUTER:                     AVG(consumption_gph) as avg_consumption,
# MIGRATED_TO_ROUTER:                     AVG(sensor_fuel_pct) as avg_fuel_level,
# MIGRATED_TO_ROUTER:                     MAX(daily_miles) as miles_driven,
# MIGRATED_TO_ROUTER:                     SUM(CASE WHEN event_type = 'REFUEL' THEN 1 ELSE 0 END) as refuel_count
# MIGRATED_TO_ROUTER:                 FROM fuel_metrics
# MIGRATED_TO_ROUTER:                 WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:                 GROUP BY truck_id, DATE(timestamp_utc)
# MIGRATED_TO_ROUTER:                 ORDER BY date DESC, truck_id
# MIGRATED_TO_ROUTER:             """
# MIGRATED_TO_ROUTER:         elif report_type == "weekly_kpis":
# MIGRATED_TO_ROUTER:             query = """
# MIGRATED_TO_ROUTER:                 SELECT
# MIGRATED_TO_ROUTER:                     YEARWEEK(timestamp_utc) as week,
# MIGRATED_TO_ROUTER:                     COUNT(DISTINCT truck_id) as active_trucks,
# MIGRATED_TO_ROUTER:                     AVG(mpg) as fleet_avg_mpg,
# MIGRATED_TO_ROUTER:                     AVG(idle_pct) as fleet_avg_idle,
# MIGRATED_TO_ROUTER:                     SUM(fuel_consumed_gal) as total_fuel_gal,
# MIGRATED_TO_ROUTER:                     SUM(daily_miles) / COUNT(DISTINCT DATE(timestamp_utc)) as avg_daily_miles
# MIGRATED_TO_ROUTER:                 FROM fuel_metrics
# MIGRATED_TO_ROUTER:                 WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:                 GROUP BY YEARWEEK(timestamp_utc)
# MIGRATED_TO_ROUTER:                 ORDER BY week DESC
# MIGRATED_TO_ROUTER:             """
# MIGRATED_TO_ROUTER:         elif report_type == "theft_analysis":
# MIGRATED_TO_ROUTER:             query = """
# MIGRATED_TO_ROUTER:                 SELECT
# MIGRATED_TO_ROUTER:                     truck_id,
# MIGRATED_TO_ROUTER:                     timestamp_utc,
# MIGRATED_TO_ROUTER:                     sensor_fuel_pct,
# MIGRATED_TO_ROUTER:                     estimated_fuel_pct,
# MIGRATED_TO_ROUTER:                     status,
# MIGRATED_TO_ROUTER:                     CASE
# MIGRATED_TO_ROUTER:                         WHEN ABS(sensor_fuel_pct - estimated_fuel_pct) > 10
# MIGRATED_TO_ROUTER:                         AND status = 'STOPPED' THEN 'SUSPICIOUS'
# MIGRATED_TO_ROUTER:                         ELSE 'NORMAL'
# MIGRATED_TO_ROUTER:                     END as alert_status
# MIGRATED_TO_ROUTER:                 FROM fuel_metrics
# MIGRATED_TO_ROUTER:                 WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:                   AND ABS(sensor_fuel_pct - estimated_fuel_pct) > 5
# MIGRATED_TO_ROUTER:                 ORDER BY timestamp_utc DESC
# MIGRATED_TO_ROUTER:                 LIMIT 500
# MIGRATED_TO_ROUTER:             """
# MIGRATED_TO_ROUTER:         else:
# MIGRATED_TO_ROUTER:             raise HTTPException(
# MIGRATED_TO_ROUTER:                 status_code=400, detail=f"Unknown report type: {report_type}"
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             df = pd.read_sql(text(query), conn, params={"days": days})
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if format == "json":
# MIGRATED_TO_ROUTER:             return {
# MIGRATED_TO_ROUTER:                 "report_type": report_type,
# MIGRATED_TO_ROUTER:                 "days": days,
# MIGRATED_TO_ROUTER:                 "generated_at": datetime.now().isoformat(),
# MIGRATED_TO_ROUTER:                 "row_count": len(df),
# MIGRATED_TO_ROUTER:                 "data": df.to_dict(orient="records"),
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:         elif format == "excel":
# MIGRATED_TO_ROUTER:             output = io.BytesIO()
# MIGRATED_TO_ROUTER:             with pd.ExcelWriter(output, engine="openpyxl") as writer:
# MIGRATED_TO_ROUTER:                 df.to_excel(writer, sheet_name=report_type, index=False)
# MIGRATED_TO_ROUTER:             output.seek(0)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             filename = f"{report_type}_{datetime.now().strftime('%Y%m%d')}.xlsx"
# MIGRATED_TO_ROUTER:             return Response(
# MIGRATED_TO_ROUTER:                 content=output.getvalue(),
# MIGRATED_TO_ROUTER:                 media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
# MIGRATED_TO_ROUTER:                 headers={"Content-Disposition": f"attachment; filename={filename}"},
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:         else:  # CSV
# MIGRATED_TO_ROUTER:             output = io.StringIO()
# MIGRATED_TO_ROUTER:             df.to_csv(output, index=False)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             filename = f"{report_type}_{datetime.now().strftime('%Y%m%d')}.csv"
# MIGRATED_TO_ROUTER:             return Response(
# MIGRATED_TO_ROUTER:                 content=output.getvalue(),
# MIGRATED_TO_ROUTER:                 media_type="text/csv",
# MIGRATED_TO_ROUTER:                 headers={"Content-Disposition": f"attachment; filename={filename}"},
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Report generation error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v4.0: COST PER MILE ENDPOINTS (Geotab-inspired)
# ============================================================================


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/cost/per-mile", tags=["Cost Analysis"])
# MIGRATED_TO_ROUTER: async def get_fleet_cost_per_mile(
# MIGRATED_TO_ROUTER:     days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v4.0: Get cost per mile analysis for entire fleet.
# MIGRATED_TO_ROUTER:     🔧 v4.3.2: Removed auth requirement for consistency with dashboard endpoints.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:         Fleet-wide cost analysis with individual truck breakdowns
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from cost_per_mile_engine import CostPerMileEngine
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:         cpm_engine = CostPerMileEngine()
# MIGRATED_TO_ROUTER:
# Get fleet data for the period
# 🔧 v4.3: Simplified query - calculate miles from odometer, gallons from miles/mpg
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 truck_id,
# MIGRATED_TO_ROUTER:                 (MAX(odometer_mi) - MIN(odometer_mi)) as miles,
# MIGRATED_TO_ROUTER:                 MAX(engine_hours) - MIN(engine_hours) as engine_hours,
# MIGRATED_TO_ROUTER:                 AVG(CASE WHEN mpg_current > 3 AND mpg_current < 12 THEN mpg_current END) as avg_mpg
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:             GROUP BY truck_id
# MIGRATED_TO_ROUTER:             HAVING miles > 10
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         trucks_data = []
# MIGRATED_TO_ROUTER:         try:
# MIGRATED_TO_ROUTER:             with engine.connect() as conn:
# MIGRATED_TO_ROUTER:                 result = conn.execute(text(query), {"days": days})
# MIGRATED_TO_ROUTER:                 rows = result.fetchall()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             for row in rows:
# MIGRATED_TO_ROUTER:                 miles = float(row[1] or 0)
# MIGRATED_TO_ROUTER:                 avg_mpg = float(row[3] or 5.5)
# MIGRATED_TO_ROUTER:                 if avg_mpg < 3:
# MIGRATED_TO_ROUTER:                     avg_mpg = 5.5  # Fallback to reasonable default
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:                 trucks_data.append(
# MIGRATED_TO_ROUTER:                     {
# MIGRATED_TO_ROUTER:                         "truck_id": row[0],
# MIGRATED_TO_ROUTER:                         "miles": miles,
# MIGRATED_TO_ROUTER:                         "gallons": miles / avg_mpg if avg_mpg > 0 else 0,
# MIGRATED_TO_ROUTER:                         "engine_hours": float(row[2] or 0),
# MIGRATED_TO_ROUTER:                         "avg_mpg": avg_mpg,
# MIGRATED_TO_ROUTER:                     }
# MIGRATED_TO_ROUTER:                 )
# MIGRATED_TO_ROUTER:         except Exception as db_err:
# MIGRATED_TO_ROUTER:             logger.warning(f"DB query failed, using fallback: {db_err}")
# MIGRATED_TO_ROUTER:
# 🆕 v4.3: Fallback - use current truck data if no historical data
# MIGRATED_TO_ROUTER:         if not trucks_data:
# MIGRATED_TO_ROUTER:             logger.info("No historical data, using current truck data for estimates")
# MIGRATED_TO_ROUTER:             try:
# MIGRATED_TO_ROUTER:                 all_trucks = db.get_all_trucks()
# MIGRATED_TO_ROUTER:                 for tid in all_trucks[:20]:
# MIGRATED_TO_ROUTER:                     truck_data = db.get_truck_latest_record(tid)
# MIGRATED_TO_ROUTER:                     if truck_data:
# MIGRATED_TO_ROUTER:                         mpg = truck_data.get("mpg_current", 5.5) or 5.5
# MIGRATED_TO_ROUTER:                         if mpg < 3 or mpg > 12:
# MIGRATED_TO_ROUTER:                             mpg = 5.5
# MIGRATED_TO_ROUTER:                         miles = 8000  # Default monthly miles estimate
# MIGRATED_TO_ROUTER:                         trucks_data.append(
# MIGRATED_TO_ROUTER:                             {
# MIGRATED_TO_ROUTER:                                 "truck_id": tid,
# MIGRATED_TO_ROUTER:                                 "miles": miles,
# MIGRATED_TO_ROUTER:                                 "gallons": miles / max(mpg, 1),
# MIGRATED_TO_ROUTER:                                 "engine_hours": truck_data.get("engine_hours", 200)
# MIGRATED_TO_ROUTER:                                 or 200,
# MIGRATED_TO_ROUTER:                                 "avg_mpg": mpg,
# MIGRATED_TO_ROUTER:                             }
# MIGRATED_TO_ROUTER:                         )
# MIGRATED_TO_ROUTER:             except Exception as fallback_err:
# MIGRATED_TO_ROUTER:                 logger.error(f"Fallback also failed: {fallback_err}")
# MIGRATED_TO_ROUTER:
# Final fallback - return demo data
# MIGRATED_TO_ROUTER:         if not trucks_data:
# MIGRATED_TO_ROUTER:             logger.warning("All data sources failed, returning demo data")
# MIGRATED_TO_ROUTER:             trucks_data = [
# MIGRATED_TO_ROUTER:                 {
# MIGRATED_TO_ROUTER:                     "truck_id": "DEMO-001",
# MIGRATED_TO_ROUTER:                     "miles": 8000,
# MIGRATED_TO_ROUTER:                     "gallons": 1450,
# MIGRATED_TO_ROUTER:                     "engine_hours": 200,
# MIGRATED_TO_ROUTER:                     "avg_mpg": 5.5,
# MIGRATED_TO_ROUTER:                 },
# MIGRATED_TO_ROUTER:                 {
# MIGRATED_TO_ROUTER:                     "truck_id": "DEMO-002",
# MIGRATED_TO_ROUTER:                     "miles": 7500,
# MIGRATED_TO_ROUTER:                     "gallons": 1250,
# MIGRATED_TO_ROUTER:                     "engine_hours": 190,
# MIGRATED_TO_ROUTER:                     "avg_mpg": 6.0,
# MIGRATED_TO_ROUTER:                 },
# MIGRATED_TO_ROUTER:             ]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         report = cpm_engine.generate_cost_report(trucks_data, period_days=days)
# MIGRATED_TO_ROUTER:         return report
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Cost per mile analysis error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/cost/per-mile/{truck_id}", tags=["Cost Analysis"])
# MIGRATED_TO_ROUTER: async def get_truck_cost_per_mile(
# MIGRATED_TO_ROUTER:     truck_id: str,
# MIGRATED_TO_ROUTER:     days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v4.0: Get cost per mile analysis for a specific truck.
# MIGRATED_TO_ROUTER:     🔧 v4.3.2: Removed auth requirement for consistency with dashboard endpoints.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:         Detailed cost breakdown and comparison for the specified truck
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from cost_per_mile_engine import CostPerMileEngine
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# Note: Access control by carrier_id (currently single carrier)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:         cpm_engine = CostPerMileEngine()
# MIGRATED_TO_ROUTER:
# Get truck data for the period
# 🔧 v4.3: Fixed column names - use mpg_current, calculate miles from odometer
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 (MAX(odometer_mi) - MIN(odometer_mi)) as miles,
# MIGRATED_TO_ROUTER:                 (MAX(odometer_mi) - MIN(odometer_mi)) / NULLIF(AVG(CASE WHEN mpg_current > 0 THEN mpg_current END), 0) as gallons,
# MIGRATED_TO_ROUTER:                 MAX(engine_hours) - MIN(engine_hours) as engine_hours,
# MIGRATED_TO_ROUTER:                 AVG(CASE WHEN mpg_current > 0 THEN mpg_current END) as avg_mpg
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE truck_id = :truck_id
# MIGRATED_TO_ROUTER:                 AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:                 AND mpg_current > 0
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(query), {"truck_id": truck_id, "days": days})
# MIGRATED_TO_ROUTER:             row = result.fetchone()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if not row or not row[0]:
# MIGRATED_TO_ROUTER:             raise HTTPException(
# MIGRATED_TO_ROUTER:                 status_code=404, detail=f"No data found for truck {truck_id}"
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         truck_data = {
# MIGRATED_TO_ROUTER:             "miles": float(row[0] or 0),
# MIGRATED_TO_ROUTER:             "gallons": float(row[1] or 0),
# MIGRATED_TO_ROUTER:             "engine_hours": float(row[2] or 0),
# MIGRATED_TO_ROUTER:             "avg_mpg": float(row[3] or 0),
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         analysis = cpm_engine.analyze_truck_costs(
# MIGRATED_TO_ROUTER:             truck_id=truck_id,
# MIGRATED_TO_ROUTER:             period_days=days,
# MIGRATED_TO_ROUTER:             truck_data=truck_data,
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "status": "success",
# MIGRATED_TO_ROUTER:             "data": analysis.to_dict(),
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Truck cost analysis error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/cost/speed-impact", tags=["Cost Analysis"])
# MIGRATED_TO_ROUTER: async def get_speed_cost_impact(
# MIGRATED_TO_ROUTER:     avg_speed_mph: float = Query(65, ge=40, le=90, description="Average highway speed"),
# MIGRATED_TO_ROUTER:     monthly_miles: float = Query(8000, ge=1000, le=50000, description="Monthly miles"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v4.0: Calculate cost impact of speeding.
# MIGRATED_TO_ROUTER:     🔧 v4.3.2: Removed auth requirement for consistency with dashboard endpoints.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Based on DOE research: "Every 5 mph over 60 reduces fuel efficiency by ~0.7 MPG"
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:         Cost impact analysis showing potential savings from speed reduction
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from cost_per_mile_engine import calculate_speed_cost_impact
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         impact = calculate_speed_cost_impact(
# MIGRATED_TO_ROUTER:             avg_speed_mph=avg_speed_mph,
# MIGRATED_TO_ROUTER:             monthly_miles=monthly_miles,
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "status": "success",
# MIGRATED_TO_ROUTER:             "data": impact,
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Speed impact analysis error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v4.0: FLEET UTILIZATION ENDPOINTS (Geotab-inspired, target 95%)
# ============================================================================


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/utilization/fleet", tags=["Fleet Utilization"])
# MIGRATED_TO_ROUTER: async def get_fleet_utilization(
# MIGRATED_TO_ROUTER:     days: int = Query(7, ge=1, le=90, description="Analysis period in days"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v4.0: Get fleet utilization analysis.
# MIGRATED_TO_ROUTER:     🔧 v4.3.2: Removed auth requirement for consistency with dashboard endpoints.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Calculates utilization rate (target: 95%) based on:
# MIGRATED_TO_ROUTER:     - Driving time vs Available time
# MIGRATED_TO_ROUTER:     - Productive idle (loading/unloading) vs Non-productive idle
# MIGRATED_TO_ROUTER:     - Engine off time
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:         Fleet-wide utilization metrics and individual truck breakdowns
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from fleet_utilization_engine import FleetUtilizationEngine
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:         util_engine = FleetUtilizationEngine()
# MIGRATED_TO_ROUTER:
# Get activity data for the period
# 🔧 v4.3: Fixed column name speed -> speed_mph
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 truck_id,
# MIGRATED_TO_ROUTER:                 SUM(CASE
# MIGRATED_TO_ROUTER:                     WHEN speed_mph > 5 THEN 0.0167  -- ~1 minute per reading when moving
# MIGRATED_TO_ROUTER:                     ELSE 0
# MIGRATED_TO_ROUTER:                 END) as driving_hours,
# MIGRATED_TO_ROUTER:                 SUM(CASE
# MIGRATED_TO_ROUTER:                     WHEN speed_mph <= 5 AND rpm > 400 THEN 0.0167  -- Idle
# MIGRATED_TO_ROUTER:                     ELSE 0
# MIGRATED_TO_ROUTER:                 END) as idle_hours,
# MIGRATED_TO_ROUTER:                 COUNT(DISTINCT DATE(timestamp_utc)) as active_days,
# MIGRATED_TO_ROUTER:                 COUNT(*) as readings
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:             GROUP BY truck_id
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         trucks_data = []
# MIGRATED_TO_ROUTER:         total_hours = days * 24
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         try:
# MIGRATED_TO_ROUTER:             with engine.connect() as conn:
# MIGRATED_TO_ROUTER:                 result = conn.execute(text(query), {"days": days})
# MIGRATED_TO_ROUTER:                 rows = result.fetchall()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             for row in rows:
# MIGRATED_TO_ROUTER:                 driving = float(row[1] or 0)
# MIGRATED_TO_ROUTER:                 idle = float(row[2] or 0)
# Estimate productive vs non-productive idle (assume 30% is productive)
# MIGRATED_TO_ROUTER:                 productive_idle = idle * 0.3
# MIGRATED_TO_ROUTER:                 non_productive_idle = idle * 0.7
# MIGRATED_TO_ROUTER:                 engine_off = total_hours - driving - idle
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:                 trucks_data.append(
# MIGRATED_TO_ROUTER:                     {
# MIGRATED_TO_ROUTER:                         "truck_id": row[0],
# MIGRATED_TO_ROUTER:                         "driving_hours": driving,
# MIGRATED_TO_ROUTER:                         "productive_idle_hours": productive_idle,
# MIGRATED_TO_ROUTER:                         "non_productive_idle_hours": non_productive_idle,
# MIGRATED_TO_ROUTER:                         "engine_off_hours": max(0, engine_off),
# MIGRATED_TO_ROUTER:                     }
# MIGRATED_TO_ROUTER:                 )
# MIGRATED_TO_ROUTER:         except Exception as db_err:
# MIGRATED_TO_ROUTER:             logger.warning(f"DB query failed for utilization: {db_err}")
# MIGRATED_TO_ROUTER:
# 🆕 v4.3: Fallback - generate estimates from current truck list
# MIGRATED_TO_ROUTER:         if not trucks_data:
# MIGRATED_TO_ROUTER:             logger.info("No utilization data, generating estimates from truck list")
# MIGRATED_TO_ROUTER:             try:
# MIGRATED_TO_ROUTER:                 all_trucks = db.get_all_trucks()
# MIGRATED_TO_ROUTER:                 for tid in all_trucks[:20]:
# Generate reasonable estimates based on typical fleet usage
# MIGRATED_TO_ROUTER:                     driving = 4.0 * days  # ~4 hours/day driving on average
# MIGRATED_TO_ROUTER:                     idle = 1.0 * days  # ~1 hour idle per day
# MIGRATED_TO_ROUTER:                     productive_idle = idle * 0.3
# MIGRATED_TO_ROUTER:                     non_productive_idle = idle * 0.7
# MIGRATED_TO_ROUTER:                     engine_off = max(0, total_hours - driving - idle)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:                     trucks_data.append(
# MIGRATED_TO_ROUTER:                         {
# MIGRATED_TO_ROUTER:                             "truck_id": tid,
# MIGRATED_TO_ROUTER:                             "driving_hours": driving,
# MIGRATED_TO_ROUTER:                             "productive_idle_hours": productive_idle,
# MIGRATED_TO_ROUTER:                             "non_productive_idle_hours": non_productive_idle,
# MIGRATED_TO_ROUTER:                             "engine_off_hours": engine_off,
# MIGRATED_TO_ROUTER:                         }
# MIGRATED_TO_ROUTER:                     )
# MIGRATED_TO_ROUTER:             except Exception as fallback_err:
# MIGRATED_TO_ROUTER:                 logger.error(f"Utilization fallback failed: {fallback_err}")
# MIGRATED_TO_ROUTER:
# Final fallback - return demo data
# MIGRATED_TO_ROUTER:         if not trucks_data:
# MIGRATED_TO_ROUTER:             logger.warning("All utilization sources failed, returning demo data")
# MIGRATED_TO_ROUTER:             for i in range(5):
# MIGRATED_TO_ROUTER:                 driving = 4.0 * days
# MIGRATED_TO_ROUTER:                 idle = 1.0 * days
# MIGRATED_TO_ROUTER:                 trucks_data.append(
# MIGRATED_TO_ROUTER:                     {
# MIGRATED_TO_ROUTER:                         "truck_id": f"DEMO-{i+1:03d}",
# MIGRATED_TO_ROUTER:                         "driving_hours": driving,
# MIGRATED_TO_ROUTER:                         "productive_idle_hours": idle * 0.3,
# MIGRATED_TO_ROUTER:                         "non_productive_idle_hours": idle * 0.7,
# MIGRATED_TO_ROUTER:                         "engine_off_hours": max(0, total_hours - driving - idle),
# MIGRATED_TO_ROUTER:                     }
# MIGRATED_TO_ROUTER:                 )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         report = util_engine.generate_utilization_report(trucks_data, period_days=days)
# MIGRATED_TO_ROUTER:         return report
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Fleet utilization error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/utilization/{truck_id}", tags=["Fleet Utilization"])
# MIGRATED_TO_ROUTER: async def get_truck_utilization(
# MIGRATED_TO_ROUTER:     truck_id: str,
# MIGRATED_TO_ROUTER:     days: int = Query(7, ge=1, le=90, description="Analysis period in days"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v4.0: Get utilization analysis for a specific truck.
# MIGRATED_TO_ROUTER:     🔧 v4.3.2: Removed auth requirement for consistency with dashboard endpoints.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:         Detailed utilization metrics and recommendations for the specified truck
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from fleet_utilization_engine import FleetUtilizationEngine
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# Note: Access control by carrier_id (currently single carrier)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:         util_engine = FleetUtilizationEngine()
# MIGRATED_TO_ROUTER:
# 🔧 v4.3: Fixed column name speed -> speed_mph
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 SUM(CASE
# MIGRATED_TO_ROUTER:                     WHEN speed_mph > 5 THEN 0.0167
# MIGRATED_TO_ROUTER:                     ELSE 0
# MIGRATED_TO_ROUTER:                 END) as driving_hours,
# MIGRATED_TO_ROUTER:                 SUM(CASE
# MIGRATED_TO_ROUTER:                     WHEN speed_mph <= 5 AND rpm > 400 THEN 0.0167
# MIGRATED_TO_ROUTER:                     ELSE 0
# MIGRATED_TO_ROUTER:                 END) as idle_hours
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE truck_id = :truck_id
# MIGRATED_TO_ROUTER:                 AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(query), {"truck_id": truck_id, "days": days})
# MIGRATED_TO_ROUTER:             row = result.fetchone()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if not row:
# MIGRATED_TO_ROUTER:             raise HTTPException(
# MIGRATED_TO_ROUTER:                 status_code=404, detail=f"No data found for truck {truck_id}"
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         total_hours = days * 24
# MIGRATED_TO_ROUTER:         driving = float(row[0] or 0)
# MIGRATED_TO_ROUTER:         idle = float(row[1] or 0)
# MIGRATED_TO_ROUTER:         productive_idle = idle * 0.3
# MIGRATED_TO_ROUTER:         non_productive_idle = idle * 0.7
# MIGRATED_TO_ROUTER:         engine_off = total_hours - driving - idle
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         truck_data = {
# MIGRATED_TO_ROUTER:             "driving_hours": driving,
# MIGRATED_TO_ROUTER:             "productive_idle_hours": productive_idle,
# MIGRATED_TO_ROUTER:             "non_productive_idle_hours": non_productive_idle,
# MIGRATED_TO_ROUTER:             "engine_off_hours": max(0, engine_off),
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         analysis = util_engine.analyze_truck_utilization(
# MIGRATED_TO_ROUTER:             truck_id=truck_id,
# MIGRATED_TO_ROUTER:             period_days=days,
# MIGRATED_TO_ROUTER:             truck_data=truck_data,
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "status": "success",
# MIGRATED_TO_ROUTER:             "data": analysis.to_dict(),
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Truck utilization error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/utilization/optimization", tags=["Fleet Utilization"])
# MIGRATED_TO_ROUTER: async def get_utilization_optimization(
# MIGRATED_TO_ROUTER:     days: int = Query(7, ge=1, le=90, description="Analysis period in days"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v4.0: Get fleet optimization recommendations based on utilization.
# MIGRATED_TO_ROUTER:     🔧 v4.3.2: Removed auth requirement for consistency with dashboard endpoints.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Identifies:
# MIGRATED_TO_ROUTER:     - Underutilized trucks (candidates for reassignment)
# MIGRATED_TO_ROUTER:     - Fleet size recommendations
# MIGRATED_TO_ROUTER:     - Potential revenue recovery
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:         Optimization recommendations with financial impact
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from fleet_utilization_engine import FleetUtilizationEngine
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:         util_engine = FleetUtilizationEngine()
# MIGRATED_TO_ROUTER:
# Get utilization data (same as fleet endpoint)
# 🔧 v4.3: Fixed column name speed -> speed_mph
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 truck_id,
# MIGRATED_TO_ROUTER:                 SUM(CASE
# MIGRATED_TO_ROUTER:                     WHEN speed_mph > 5 THEN 0.0167
# MIGRATED_TO_ROUTER:                     ELSE 0
# MIGRATED_TO_ROUTER:                 END) as driving_hours,
# MIGRATED_TO_ROUTER:                 SUM(CASE
# MIGRATED_TO_ROUTER:                     WHEN speed_mph <= 5 AND rpm > 400 THEN 0.0167
# MIGRATED_TO_ROUTER:                     ELSE 0
# MIGRATED_TO_ROUTER:                 END) as idle_hours
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:             GROUP BY truck_id
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(query), {"days": days})
# MIGRATED_TO_ROUTER:             rows = result.fetchall()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         trucks_data = []
# MIGRATED_TO_ROUTER:         total_hours = days * 24
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         for row in rows:
# MIGRATED_TO_ROUTER:             driving = float(row[1] or 0)
# MIGRATED_TO_ROUTER:             idle = float(row[2] or 0)
# MIGRATED_TO_ROUTER:             productive_idle = idle * 0.3
# MIGRATED_TO_ROUTER:             non_productive_idle = idle * 0.7
# MIGRATED_TO_ROUTER:             engine_off = total_hours - driving - idle
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             trucks_data.append(
# MIGRATED_TO_ROUTER:                 {
# MIGRATED_TO_ROUTER:                     "truck_id": row[0],
# MIGRATED_TO_ROUTER:                     "driving_hours": driving,
# MIGRATED_TO_ROUTER:                     "productive_idle_hours": productive_idle,
# MIGRATED_TO_ROUTER:                     "non_productive_idle_hours": non_productive_idle,
# MIGRATED_TO_ROUTER:                     "engine_off_hours": max(0, engine_off),
# MIGRATED_TO_ROUTER:                 }
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# Note: Currently fleet is single-carrier, no filtering needed
# MIGRATED_TO_ROUTER:
# Analyze fleet utilization
# MIGRATED_TO_ROUTER:         summary = util_engine.analyze_fleet_utilization(trucks_data, period_days=days)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if not summary:
# MIGRATED_TO_ROUTER:             return {
# MIGRATED_TO_ROUTER:                 "status": "error",
# MIGRATED_TO_ROUTER:                 "message": "No data available for optimization analysis",
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:
# Get optimization opportunities
# MIGRATED_TO_ROUTER:         opportunities = util_engine.identify_fleet_optimization_opportunities(summary)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "status": "success",
# MIGRATED_TO_ROUTER:             "period_days": days,
# MIGRATED_TO_ROUTER:             "fleet_avg_utilization": round(summary.fleet_avg_utilization * 100, 1),
# MIGRATED_TO_ROUTER:             "target_utilization": 95,
# MIGRATED_TO_ROUTER:             "data": opportunities,
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Utilization optimization error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v4.0: GAMIFICATION ENDPOINTS
# ============================================================================


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/gamification/leaderboard", tags=["Gamification"])
# MIGRATED_TO_ROUTER: async def get_driver_leaderboard():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v4.0: Get driver leaderboard with rankings, scores, and badges.
# MIGRATED_TO_ROUTER:     🔧 v4.3.2: Removed auth requirement for consistency with dashboard endpoints.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Features:
# MIGRATED_TO_ROUTER:     - Overall score based on MPG, idle, consistency, and improvement
# MIGRATED_TO_ROUTER:     - Trend indicators (↑↓) showing performance direction
# MIGRATED_TO_ROUTER:     - Badge counts and streak days
# MIGRATED_TO_ROUTER:     - Fleet statistics
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:         Leaderboard with all drivers ranked by performance
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from gamification_engine import GamificationEngine
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:         gam_engine = GamificationEngine()
# MIGRATED_TO_ROUTER:
# 🔧 v5.5.1: Filter by allowed trucks from tanks.yaml
# MIGRATED_TO_ROUTER:         from config import get_allowed_trucks
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         allowed_trucks = get_allowed_trucks()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if not allowed_trucks:
# MIGRATED_TO_ROUTER:             logger.warning("No allowed trucks configured in tanks.yaml")
# MIGRATED_TO_ROUTER:             return {
# MIGRATED_TO_ROUTER:                 "leaderboard": [],
# MIGRATED_TO_ROUTER:                 "fleet_stats": {},
# MIGRATED_TO_ROUTER:                 "timestamp": datetime.utcnow().isoformat(),
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:
# Build placeholders for IN clause
# MIGRATED_TO_ROUTER:         placeholders = ",".join([f":truck_{i}" for i in range(len(allowed_trucks))])
# MIGRATED_TO_ROUTER:         truck_params = {f"truck_{i}": t for i, t in enumerate(allowed_trucks)}
# MIGRATED_TO_ROUTER:
# Get driver performance data from last 7 days
# 🔧 v4.3: Fixed column name mpg -> mpg_current, speed -> speed_mph
# 🔧 v5.5.1: Added filter by allowed_trucks
# MIGRATED_TO_ROUTER:         query = f"""
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 fm.truck_id,
# MIGRATED_TO_ROUTER:                 AVG(CASE WHEN fm.mpg_current > 0 THEN fm.mpg_current END) as mpg,
# MIGRATED_TO_ROUTER:                 AVG(CASE
# MIGRATED_TO_ROUTER:                     WHEN fm.speed_mph <= 5 AND fm.rpm > 400 THEN 1.0
# MIGRATED_TO_ROUTER:                     ELSE 0.0
# MIGRATED_TO_ROUTER:                 END) * 100 as idle_pct,
# MIGRATED_TO_ROUTER:                 COUNT(DISTINCT DATE(fm.timestamp_utc)) as active_days
# MIGRATED_TO_ROUTER:             FROM fuel_metrics fm
# MIGRATED_TO_ROUTER:             WHERE fm.timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)
# MIGRATED_TO_ROUTER:             AND fm.truck_id IN ({placeholders})
# MIGRATED_TO_ROUTER:             GROUP BY fm.truck_id
# MIGRATED_TO_ROUTER:             HAVING mpg IS NOT NULL
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         drivers_data = []
# MIGRATED_TO_ROUTER:         try:
# MIGRATED_TO_ROUTER:             with engine.connect() as conn:
# MIGRATED_TO_ROUTER:                 result = conn.execute(text(query), truck_params)
# MIGRATED_TO_ROUTER:                 rows = result.fetchall()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             for row in rows:
# MIGRATED_TO_ROUTER:                 drivers_data.append(
# MIGRATED_TO_ROUTER:                     {
# MIGRATED_TO_ROUTER:                         "truck_id": row[0],
# MIGRATED_TO_ROUTER:                         "mpg": float(row[1] or 6.0),
# MIGRATED_TO_ROUTER:                         "idle_pct": float(row[2] or 12.0),
# MIGRATED_TO_ROUTER:                         "driver_name": f"Driver {row[0]}",
# MIGRATED_TO_ROUTER:                         "previous_score": 50,
# MIGRATED_TO_ROUTER:                         "streak_days": int(row[3] or 0),
# MIGRATED_TO_ROUTER:                         "badges_earned": 0,
# MIGRATED_TO_ROUTER:                     }
# MIGRATED_TO_ROUTER:                 )
# MIGRATED_TO_ROUTER:         except Exception as db_err:
# MIGRATED_TO_ROUTER:             logger.warning(f"Leaderboard DB query failed: {db_err}")
# MIGRATED_TO_ROUTER:
# 🆕 v4.3: Fallback - use current truck data if no historical data
# 🔧 v5.5.1: Filter by allowed trucks from tanks.yaml
# 🔧 v5.6.0: Fixed N+1 query - batch fetch truck data
# MIGRATED_TO_ROUTER:         if not drivers_data:
# MIGRATED_TO_ROUTER:             logger.info("No leaderboard data, generating from current trucks")
# MIGRATED_TO_ROUTER:             try:
# MIGRATED_TO_ROUTER:                 all_trucks = db.get_all_trucks()
# Filter to only include trucks from tanks.yaml
# MIGRATED_TO_ROUTER:                 fallback_allowed = get_allowed_trucks()
# MIGRATED_TO_ROUTER:                 filtered_trucks = [t for t in all_trucks if t in fallback_allowed][:20]
# MIGRATED_TO_ROUTER:
# 🔧 v5.6.0: Batch query instead of N+1
# MIGRATED_TO_ROUTER:                 trucks_data = (
# MIGRATED_TO_ROUTER:                     db.get_trucks_batch(filtered_trucks)
# MIGRATED_TO_ROUTER:                     if hasattr(db, "get_trucks_batch")
# MIGRATED_TO_ROUTER:                     else {}
# MIGRATED_TO_ROUTER:                 )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:                 for tid in filtered_trucks:
# Use batch data if available, otherwise fall back to individual query
# MIGRATED_TO_ROUTER:                     truck_data = (
# MIGRATED_TO_ROUTER:                         trucks_data.get(tid)
# MIGRATED_TO_ROUTER:                         if trucks_data
# MIGRATED_TO_ROUTER:                         else db.get_truck_latest_record(tid)
# MIGRATED_TO_ROUTER:                     )
# MIGRATED_TO_ROUTER:                     if truck_data:
# MIGRATED_TO_ROUTER:                         mpg = truck_data.get("mpg_current", 5.5) or 5.5
# MIGRATED_TO_ROUTER:                         if mpg < 3 or mpg > 12:
# MIGRATED_TO_ROUTER:                             mpg = 5.5
# MIGRATED_TO_ROUTER:                         drivers_data.append(
# MIGRATED_TO_ROUTER:                             {
# MIGRATED_TO_ROUTER:                                 "truck_id": tid,
# MIGRATED_TO_ROUTER:                                 "mpg": mpg,
# MIGRATED_TO_ROUTER:                                 "idle_pct": 12.0,  # Default
# MIGRATED_TO_ROUTER:                                 "driver_name": f"Driver {tid}",
# MIGRATED_TO_ROUTER:                                 "previous_score": 50,
# MIGRATED_TO_ROUTER:                                 "streak_days": 3,
# MIGRATED_TO_ROUTER:                                 "badges_earned": 1,
# MIGRATED_TO_ROUTER:                             }
# MIGRATED_TO_ROUTER:                         )
# MIGRATED_TO_ROUTER:             except Exception as fallback_err:
# MIGRATED_TO_ROUTER:                 logger.error(f"Leaderboard fallback failed: {fallback_err}")
# MIGRATED_TO_ROUTER:
# Final fallback - return demo data
# MIGRATED_TO_ROUTER:         if not drivers_data:
# MIGRATED_TO_ROUTER:             logger.warning("All leaderboard sources failed, returning demo data")
# MIGRATED_TO_ROUTER:             for i in range(5):
# MIGRATED_TO_ROUTER:                 drivers_data.append(
# MIGRATED_TO_ROUTER:                     {
# MIGRATED_TO_ROUTER:                         "truck_id": f"DEMO-{i+1:03d}",
# MIGRATED_TO_ROUTER:                         "mpg": 5.5 + i * 0.3,
# MIGRATED_TO_ROUTER:                         "idle_pct": 12.0 - i,
# MIGRATED_TO_ROUTER:                         "driver_name": f"Driver DEMO-{i+1:03d}",
# MIGRATED_TO_ROUTER:                         "previous_score": 50 + i * 5,
# MIGRATED_TO_ROUTER:                         "streak_days": i + 1,
# MIGRATED_TO_ROUTER:                         "badges_earned": i,
# MIGRATED_TO_ROUTER:                     }
# MIGRATED_TO_ROUTER:                 )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         report = gam_engine.generate_gamification_report(drivers_data)
# MIGRATED_TO_ROUTER:         return report
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Gamification leaderboard error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/gamification/badges/{truck_id}", tags=["Gamification"])
# MIGRATED_TO_ROUTER: async def get_driver_badges(
# MIGRATED_TO_ROUTER:     truck_id: str,
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v4.0: Get badges for a specific driver/truck.
# MIGRATED_TO_ROUTER:     🔧 v4.3.2: Removed auth requirement for consistency with dashboard endpoints.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:         List of earned and in-progress badges with progress percentages
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from gamification_engine import GamificationEngine
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:         gam_engine = GamificationEngine()
# MIGRATED_TO_ROUTER:
# Get driver's historical data for badge calculation
# 🔧 v4.3: Fixed column names mpg -> mpg_current, speed -> speed_mph
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 DATE(timestamp_utc) as date,
# MIGRATED_TO_ROUTER:                 AVG(CASE WHEN mpg_current > 0 THEN mpg_current END) as mpg,
# MIGRATED_TO_ROUTER:                 AVG(CASE
# MIGRATED_TO_ROUTER:                     WHEN speed_mph <= 5 AND rpm > 400 THEN 1.0
# MIGRATED_TO_ROUTER:                     ELSE 0.0
# MIGRATED_TO_ROUTER:                 END) * 100 as idle_pct
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE truck_id = :truck_id
# MIGRATED_TO_ROUTER:                 AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY)
# MIGRATED_TO_ROUTER:             GROUP BY DATE(timestamp_utc)
# MIGRATED_TO_ROUTER:             ORDER BY date DESC
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(query), {"truck_id": truck_id})
# MIGRATED_TO_ROUTER:             rows = result.fetchall()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if not rows:
# MIGRATED_TO_ROUTER:             raise HTTPException(
# MIGRATED_TO_ROUTER:                 status_code=404, detail=f"No data found for truck {truck_id}"
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         mpg_history = [float(row[1] or 6.0) for row in rows]
# MIGRATED_TO_ROUTER:         idle_history = [float(row[2] or 12.0) for row in rows]
# MIGRATED_TO_ROUTER:
# Get fleet average MPG
# 🔧 v4.3: Fixed column name mpg -> mpg_current
# MIGRATED_TO_ROUTER:         avg_query = """
# MIGRATED_TO_ROUTER:             SELECT AVG(CASE WHEN mpg_current > 0 THEN mpg_current END) as fleet_avg
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             avg_result = conn.execute(text(avg_query))
# MIGRATED_TO_ROUTER:             fleet_avg = avg_result.fetchone()
# MIGRATED_TO_ROUTER:             fleet_avg_mpg = float(fleet_avg[0] or 6.0) if fleet_avg else 6.0
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         driver_data = {
# MIGRATED_TO_ROUTER:             "mpg_history": mpg_history,
# MIGRATED_TO_ROUTER:             "idle_history": idle_history,
# MIGRATED_TO_ROUTER:             "rank": 5,  # Would come from leaderboard calculation
# MIGRATED_TO_ROUTER:             "total_trucks": 25,
# MIGRATED_TO_ROUTER:             "overall_score": 65,  # Calculated score
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         badges = gam_engine.get_driver_badges(truck_id, driver_data, fleet_avg_mpg)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return badges
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Driver badges error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v5.0: PREDICTIVE MAINTENANCE ENDPOINTS
# ============================================================================


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/maintenance/fleet-health", tags=["Predictive Maintenance"])
# MIGRATED_TO_ROUTER: async def get_fleet_health(
# MIGRATED_TO_ROUTER:     include_trends: bool = Query(False, description="Include 7-day trend analysis"),
# MIGRATED_TO_ROUTER:     include_anomalies: bool = Query(
# MIGRATED_TO_ROUTER:         False, description="Include Nelson Rules anomaly detection"
# MIGRATED_TO_ROUTER:     ),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v5.0: Unified fleet health endpoint.
# MIGRATED_TO_ROUTER:     🔧 v4.3.2: Removed auth requirement for consistency with dashboard endpoints.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns fleet health report with demo data if real data unavailable.
# MIGRATED_TO_ROUTER:     """
# Default demo response - always works
# MIGRATED_TO_ROUTER:     demo_response = {
# MIGRATED_TO_ROUTER:         "status": "success",
# MIGRATED_TO_ROUTER:         "data_source": "demo",
# MIGRATED_TO_ROUTER:         "fleet_summary": {
# MIGRATED_TO_ROUTER:             "total_trucks": 3,
# MIGRATED_TO_ROUTER:             "healthy_count": 2,
# MIGRATED_TO_ROUTER:             "warning_count": 1,
# MIGRATED_TO_ROUTER:             "critical_count": 0,
# MIGRATED_TO_ROUTER:             "fleet_health_score": 85,
# MIGRATED_TO_ROUTER:             "data_freshness": "Demo data",
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         "alert_summary": {
# MIGRATED_TO_ROUTER:             "critical": 0,
# MIGRATED_TO_ROUTER:             "high": 1,
# MIGRATED_TO_ROUTER:             "medium": 2,
# MIGRATED_TO_ROUTER:             "low": 1,
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         "trucks": [
# MIGRATED_TO_ROUTER:             {
# MIGRATED_TO_ROUTER:                 "truck_id": "T101",
# MIGRATED_TO_ROUTER:                 "overall_score": 95,
# MIGRATED_TO_ROUTER:                 "status": "healthy",
# MIGRATED_TO_ROUTER:                 "current_values": {"oil_press": 45, "cool_temp": 195, "pwr_ext": 14.1},
# MIGRATED_TO_ROUTER:                 "alerts": [],
# MIGRATED_TO_ROUTER:                 "last_updated": datetime.now(timezone.utc).isoformat(),
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             {
# MIGRATED_TO_ROUTER:                 "truck_id": "T102",
# MIGRATED_TO_ROUTER:                 "overall_score": 72,
# MIGRATED_TO_ROUTER:                 "status": "warning",
# MIGRATED_TO_ROUTER:                 "current_values": {"oil_press": 28, "cool_temp": 215, "pwr_ext": 13.2},
# MIGRATED_TO_ROUTER:                 "alerts": [
# MIGRATED_TO_ROUTER:                     {
# MIGRATED_TO_ROUTER:                         "category": "engine",
# MIGRATED_TO_ROUTER:                         "severity": "high",
# MIGRATED_TO_ROUTER:                         "title": "Low Oil Pressure",
# MIGRATED_TO_ROUTER:                         "message": "Oil pressure below normal range",
# MIGRATED_TO_ROUTER:                         "metric": "oil_press",
# MIGRATED_TO_ROUTER:                         "current_value": 28,
# MIGRATED_TO_ROUTER:                         "threshold": 30,
# MIGRATED_TO_ROUTER:                         "recommendation": "Check oil level and pressure sensor",
# MIGRATED_TO_ROUTER:                     }
# MIGRATED_TO_ROUTER:                 ],
# MIGRATED_TO_ROUTER:                 "last_updated": datetime.now(timezone.utc).isoformat(),
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             {
# MIGRATED_TO_ROUTER:                 "truck_id": "T103",
# MIGRATED_TO_ROUTER:                 "overall_score": 88,
# MIGRATED_TO_ROUTER:                 "status": "healthy",
# MIGRATED_TO_ROUTER:                 "current_values": {"oil_press": 52, "cool_temp": 188, "pwr_ext": 14.3},
# MIGRATED_TO_ROUTER:                 "alerts": [],
# MIGRATED_TO_ROUTER:                 "last_updated": datetime.now(timezone.utc).isoformat(),
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:         ],
# MIGRATED_TO_ROUTER:         "alerts": [
# MIGRATED_TO_ROUTER:             {
# MIGRATED_TO_ROUTER:                 "truck_id": "T102",
# MIGRATED_TO_ROUTER:                 "category": "engine",
# MIGRATED_TO_ROUTER:                 "severity": "high",
# MIGRATED_TO_ROUTER:                 "title": "Low Oil Pressure",
# MIGRATED_TO_ROUTER:                 "message": "Oil pressure 28 psi (threshold: 30 psi)",
# MIGRATED_TO_ROUTER:                 "recommendation": "Check oil level and sensor",
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:         ],
# MIGRATED_TO_ROUTER:         "generated_at": datetime.now(timezone.utc).isoformat(),
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# 🔧 v5.1: TEMPORALMENTE usar solo demo data para evitar crashes
# El import de routers.maintenance causaba crashes al conectar a Wialon
# MIGRATED_TO_ROUTER:     logger.info("Predictive Maintenance: Using demo data (Wialon integration disabled)")
# MIGRATED_TO_ROUTER:     return demo_response
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/maintenance/truck/{truck_id}", tags=["Predictive Maintenance"]
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def get_truck_health(
# MIGRATED_TO_ROUTER:     truck_id: str,
# MIGRATED_TO_ROUTER:     days: int = Query(7, ge=1, le=30, description="History days"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v5.0: Get detailed health analysis for a specific truck.
# MIGRATED_TO_ROUTER:     🔧 v5.1: Returns demo data (Wialon integration disabled).
# MIGRATED_TO_ROUTER:     """
# 🔧 v5.1: Return demo data to avoid crashes
# MIGRATED_TO_ROUTER:     return {
# MIGRATED_TO_ROUTER:         "status": "success",
# MIGRATED_TO_ROUTER:         "data_source": "demo",
# MIGRATED_TO_ROUTER:         "truck_id": truck_id,
# MIGRATED_TO_ROUTER:         "overall_score": 85,
# MIGRATED_TO_ROUTER:         "status": "healthy",
# MIGRATED_TO_ROUTER:         "current_values": {"oil_press": 45, "cool_temp": 195, "pwr_ext": 14.1},
# MIGRATED_TO_ROUTER:         "alerts": [],
# MIGRATED_TO_ROUTER:         "trends": {},
# MIGRATED_TO_ROUTER:         "generated_at": datetime.now(timezone.utc).isoformat(),
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v5.3.7: PREDICTIVE MAINTENANCE V5 WRAPPER
# ============================================================================
# This endpoint wraps V3 to maintain backward compatibility with frontend
# The frontend's useFleetHealth.ts expects this endpoint format


# MIGRATED_TO_ROUTER: @app.get(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/v5/predictive-maintenance", tags=["Predictive Maintenance"]
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def get_predictive_maintenance_v5():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v5.3.7: Wrapper for V3 fleet health that filters by tanks.yaml.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     This endpoint:
# MIGRATED_TO_ROUTER:     1. Calls the V3 analyze_fleet_health() function
# MIGRATED_TO_ROUTER:     2. Returns data in the format expected by useFleetHealth.ts frontend hook
# MIGRATED_TO_ROUTER:     3. Ensures only trucks in tanks.yaml are included (41 trucks)
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from predictive_maintenance_v3 import analyze_fleet_health
# MIGRATED_TO_ROUTER:
# Get V3 report (already filtered by tanks.yaml)
# MIGRATED_TO_ROUTER:         report = analyze_fleet_health(include_trends=True, include_maintenance=True)
# MIGRATED_TO_ROUTER:         report_dict = report.to_dict()
# MIGRATED_TO_ROUTER:
# Transform to V5 format expected by frontend
# MIGRATED_TO_ROUTER:         trucks_list = report_dict.get("trucks", [])
# MIGRATED_TO_ROUTER:
# Count status breakdown
# MIGRATED_TO_ROUTER:         status_breakdown = {"NORMAL": 0, "WARNING": 0, "WATCH": 0, "CRITICAL": 0}
# MIGRATED_TO_ROUTER:         for truck in trucks_list:
# MIGRATED_TO_ROUTER:             status = truck.get("status", "NORMAL").upper()
# MIGRATED_TO_ROUTER:             if status in status_breakdown:
# MIGRATED_TO_ROUTER:                 status_breakdown[status] += 1
# MIGRATED_TO_ROUTER:             elif status == "HEALTHY":
# MIGRATED_TO_ROUTER:                 status_breakdown["NORMAL"] += 1
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "success": True,
# MIGRATED_TO_ROUTER:             "source": "predictive_maintenance_v3",
# MIGRATED_TO_ROUTER:             "timestamp": datetime.now(timezone.utc).isoformat(),
# MIGRATED_TO_ROUTER:             "fleet_health": {
# MIGRATED_TO_ROUTER:                 "total_trucks": len(trucks_list),
# MIGRATED_TO_ROUTER:                 "average_health_score": report_dict.get("fleet_summary", {}).get(
# MIGRATED_TO_ROUTER:                     "average_score", 80
# MIGRATED_TO_ROUTER:                 ),
# MIGRATED_TO_ROUTER:                 "status_breakdown": status_breakdown,
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             "trucks": [
# MIGRATED_TO_ROUTER:                 {
# MIGRATED_TO_ROUTER:                     "truck_id": t.get("truck_id"),
# MIGRATED_TO_ROUTER:                     "health_score": t.get("overall_score", 80),
# MIGRATED_TO_ROUTER:                     "status": t.get("status", "NORMAL"),
# MIGRATED_TO_ROUTER:                     "sensors": t.get("current_values", {}),
# MIGRATED_TO_ROUTER:                     "issues": [a.get("title", "") for a in t.get("alerts", [])],
# MIGRATED_TO_ROUTER:                     "last_updated": t.get(
# MIGRATED_TO_ROUTER:                         "last_updated", datetime.now(timezone.utc).isoformat()
# MIGRATED_TO_ROUTER:                     ),
# MIGRATED_TO_ROUTER:                 }
# MIGRATED_TO_ROUTER:                 for t in trucks_list
# MIGRATED_TO_ROUTER:             ],
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"[V5] Predictive maintenance error: {e}")
# Return empty but valid response
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "success": True,
# MIGRATED_TO_ROUTER:             "source": "fallback",
# MIGRATED_TO_ROUTER:             "timestamp": datetime.now(timezone.utc).isoformat(),
# MIGRATED_TO_ROUTER:             "fleet_health": {
# MIGRATED_TO_ROUTER:                 "total_trucks": 0,
# MIGRATED_TO_ROUTER:                 "average_health_score": 0,
# MIGRATED_TO_ROUTER:                 "status_breakdown": {
# MIGRATED_TO_ROUTER:                     "NORMAL": 0,
# MIGRATED_TO_ROUTER:                     "WARNING": 0,
# MIGRATED_TO_ROUTER:                     "WATCH": 0,
# MIGRATED_TO_ROUTER:                     "CRITICAL": 0,
# MIGRATED_TO_ROUTER:                 },
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             "trucks": [],
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v5.3.0: PREDICTIVE MAINTENANCE V3 - NEW IMPLEMENTATION
# ============================================================================
# Features:
# - Operational Context (smart threshold adjustment based on driving conditions)
# - Nelson Rules (statistical anomaly detection BEFORE thresholds are crossed)
# - Kalman Confidence Indicator
# - Adaptive Q_r (process noise based on truck status)
# - Maintenance Schedule Engine
# ============================================================================


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/v3/fleet-health", tags=["Predictive Maintenance V3"])
# MIGRATED_TO_ROUTER: async def get_fleet_health_v3(
# MIGRATED_TO_ROUTER:     include_trends: bool = Query(True, description="Include 7-day trend analysis"),
# MIGRATED_TO_ROUTER:     include_maintenance: bool = Query(True, description="Include maintenance schedule"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v5.3.0: PREDICTIVE MAINTENANCE V3 - Complete fleet health analysis.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     NEW FEATURES (competitive advantage over Geotab/Samsara):
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     1. **Operational Context**: Smart threshold adjustment based on conditions
# MIGRATED_TO_ROUTER:        - Climbing grade → allow higher temps
# MIGRATED_TO_ROUTER:        - Heavy haul → adjust oil pressure thresholds
# MIGRATED_TO_ROUTER:        - Idle → stricter cooling requirements
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     2. **Nelson Rules**: Statistical anomaly detection BEFORE thresholds
# MIGRATED_TO_ROUTER:        - Rule 1: Extreme outliers (3σ)
# MIGRATED_TO_ROUTER:        - Rule 2: Mean shift (9 consecutive above/below mean)
# MIGRATED_TO_ROUTER:        - Rule 3: Trends (6 consecutive increases/decreases)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     3. **Suppressed Alerts Count**: Shows how many false positives were prevented
# MIGRATED_TO_ROUTER:        by operational context (alerts that Geotab/Samsara would have fired)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:     - total_trucks, healthy/warning/critical counts
# MIGRATED_TO_ROUTER:     - average_score: Fleet-wide health score (0-100)
# MIGRATED_TO_ROUTER:     - total_potential_savings: Cost savings from preventive action
# MIGRATED_TO_ROUTER:     - trucks: Detailed health data with operational context
# MIGRATED_TO_ROUTER:     - all_alerts: Sorted by severity
# MIGRATED_TO_ROUTER:     - all_anomalies: Nelson rule violations (early warnings)
# MIGRATED_TO_ROUTER:     - suppressed_alerts_count: False positives prevented by context
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from predictive_maintenance_v3 import analyze_fleet_health, generate_demo_report
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         report = analyze_fleet_health(
# MIGRATED_TO_ROUTER:             include_trends=include_trends,
# MIGRATED_TO_ROUTER:             include_maintenance=include_maintenance,
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return JSONResponse(
# MIGRATED_TO_ROUTER:             content=report.to_dict(),
# MIGRATED_TO_ROUTER:             headers={
# MIGRATED_TO_ROUTER:                 "Cache-Control": "max-age=60",
# MIGRATED_TO_ROUTER:                 "X-Predictive-V3": "true",
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"[V3] Fleet health error: {e}")
# Never crash - return demo data
# MIGRATED_TO_ROUTER:         from predictive_maintenance_v3 import generate_demo_report
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return JSONResponse(
# MIGRATED_TO_ROUTER:             content=generate_demo_report().to_dict(),
# MIGRATED_TO_ROUTER:             headers={
# MIGRATED_TO_ROUTER:                 "X-Predictive-V3": "true",
# MIGRATED_TO_ROUTER:                 "X-Data-Source": "demo",
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/v3/truck-health/{truck_id}", tags=["Predictive Maintenance V3"]
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def get_truck_health_v3(
# MIGRATED_TO_ROUTER:     truck_id: str,
# MIGRATED_TO_ROUTER:     include_trends: bool = Query(True, description="Include 7-day trend analysis"),
# MIGRATED_TO_ROUTER:     include_maintenance: bool = Query(True, description="Include maintenance schedule"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v5.3.0: Get detailed V3 health analysis for a single truck.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Includes operational context, Nelson violations, and maintenance schedule.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from predictive_maintenance_v3 import analyze_single_truck
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         result = analyze_single_truck(
# MIGRATED_TO_ROUTER:             truck_id=truck_id,
# MIGRATED_TO_ROUTER:             include_trends=include_trends,
# MIGRATED_TO_ROUTER:             include_maintenance=include_maintenance,
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if result is None:
# MIGRATED_TO_ROUTER:             raise HTTPException(
# MIGRATED_TO_ROUTER:                 status_code=404,
# MIGRATED_TO_ROUTER:                 detail=f"Truck {truck_id} not found or no recent data available",
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return JSONResponse(
# MIGRATED_TO_ROUTER:             content=result,
# MIGRATED_TO_ROUTER:             headers={
# MIGRATED_TO_ROUTER:                 "Cache-Control": "max-age=30",
# MIGRATED_TO_ROUTER:                 "X-Predictive-V3": "true",
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"[V3] Truck health error for {truck_id}: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(
# MIGRATED_TO_ROUTER:             status_code=500, detail=f"Error analyzing truck {truck_id}: {str(e)}"
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/v3/kalman-recommendation/{truck_id}",
# MIGRATED_TO_ROUTER:     tags=["Predictive Maintenance V3"],
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def get_kalman_recommendation_v3(truck_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v5.3.0: Get recommended Kalman filter Q_r (process noise) for a truck.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Adaptive recommendations based on truck status:
# MIGRATED_TO_ROUTER:     - PARKED: Q_r = 0.01 (fuel shouldn't change)
# MIGRATED_TO_ROUTER:     - STOPPED: Q_r = 0.05 (engine running, stationary)
# MIGRATED_TO_ROUTER:     - IDLE: Q_r = 0.05 + consumption factor
# MIGRATED_TO_ROUTER:     - MOVING: Q_r = 0.1 + consumption factor
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Use this to dynamically adjust Kalman filter sensitivity.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from predictive_maintenance_v3 import get_recommended_Q_r
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         result = get_recommended_Q_r(truck_id)
# MIGRATED_TO_ROUTER:         return JSONResponse(content=result)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"[V3] Kalman recommendation error for {truck_id}: {e}")
# MIGRATED_TO_ROUTER:         return JSONResponse(
# MIGRATED_TO_ROUTER:             content={
# MIGRATED_TO_ROUTER:                 "Q_r": 0.1,
# MIGRATED_TO_ROUTER:                 "status": "UNKNOWN",
# MIGRATED_TO_ROUTER:                 "reason": f"Could not determine truck status: {str(e)}",
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/v3/kalman-confidence", tags=["Predictive Maintenance V3"])
# MIGRATED_TO_ROUTER: async def get_kalman_confidence_v3(
# MIGRATED_TO_ROUTER:     P: float = Query(..., description="Kalman covariance (P) value"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v5.3.0: Convert Kalman covariance (P) to confidence level.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Lower P = higher confidence in the fuel estimate.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns: level (HIGH/MEDIUM/LOW/VERY_LOW), score (0-100), color, description
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     from predictive_maintenance_v3 import get_kalman_confidence
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     result = get_kalman_confidence(P)
# MIGRATED_TO_ROUTER:     return JSONResponse(content=result)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/v3/context-info", tags=["Predictive Maintenance V3"])
# MIGRATED_TO_ROUTER: async def get_context_info_v3():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v5.3.0: Documentation for Operational Context feature.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Explains how your system differs from Geotab/Samsara:
# MIGRATED_TO_ROUTER:     - Traditional: Static thresholds (Coolant > 220°F = ALERT always)
# MIGRATED_TO_ROUTER:     - Your system: Context-aware thresholds that adjust based on conditions
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     return JSONResponse(
# MIGRATED_TO_ROUTER:         content={
# MIGRATED_TO_ROUTER:             "feature": "Operational Context",
# MIGRATED_TO_ROUTER:             "version": "V3",
# MIGRATED_TO_ROUTER:             "description": "Smart threshold adjustment based on driving conditions",
# MIGRATED_TO_ROUTER:             "competitive_advantage": "Unlike Geotab/Samsara, alerts are contextual not just threshold-based",
# MIGRATED_TO_ROUTER:             "supported_contexts": {
# MIGRATED_TO_ROUTER:                 "grade_climbing": {
# MIGRATED_TO_ROUTER:                     "detection": "High load + low speed + altitude increasing",
# MIGRATED_TO_ROUTER:                     "adjustments": {
# MIGRATED_TO_ROUTER:                         "coolant_temp": "+15°F",
# MIGRATED_TO_ROUTER:                         "oil_temp": "+10°F",
# MIGRATED_TO_ROUTER:                         "oil_press": "-5 PSI",
# MIGRATED_TO_ROUTER:                     },
# MIGRATED_TO_ROUTER:                 },
# MIGRATED_TO_ROUTER:                 "heavy_haul": {
# MIGRATED_TO_ROUTER:                     "detection": "Very high engine load + moderate speed",
# MIGRATED_TO_ROUTER:                     "adjustments": {
# MIGRATED_TO_ROUTER:                         "coolant_temp": "+10°F",
# MIGRATED_TO_ROUTER:                         "oil_temp": "+8°F",
# MIGRATED_TO_ROUTER:                         "oil_press": "-3 PSI",
# MIGRATED_TO_ROUTER:                     },
# MIGRATED_TO_ROUTER:                 },
# MIGRATED_TO_ROUTER:                 "idle": {
# MIGRATED_TO_ROUTER:                     "detection": "Speed < 3 mph + RPM < 900",
# MIGRATED_TO_ROUTER:                     "adjustments": {"coolant_temp": "-5°F (stricter)"},
# MIGRATED_TO_ROUTER:                 },
# MIGRATED_TO_ROUTER:                 "cold_start": {
# MIGRATED_TO_ROUTER:                     "detection": "Coolant or oil temp below 160°F",
# MIGRATED_TO_ROUTER:                     "adjustments": {"oil_press": "+10 PSI"},
# MIGRATED_TO_ROUTER:                 },
# MIGRATED_TO_ROUTER:                 "hot_ambient": {
# MIGRATED_TO_ROUTER:                     "detection": "Ambient temp > 95°F",
# MIGRATED_TO_ROUTER:                     "adjustments": {"coolant_temp": "+8°F", "oil_temp": "+5°F"},
# MIGRATED_TO_ROUTER:                 },
# MIGRATED_TO_ROUTER:                 "normal": {
# MIGRATED_TO_ROUTER:                     "detection": "Default when no special conditions",
# MIGRATED_TO_ROUTER:                     "adjustments": "None",
# MIGRATED_TO_ROUTER:                 },
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             "benefits": [
# MIGRATED_TO_ROUTER:                 "Fewer false positive alerts",
# MIGRATED_TO_ROUTER:                 "More actionable warnings",
# MIGRATED_TO_ROUTER:                 "Reduced alert fatigue",
# MIGRATED_TO_ROUTER:                 "Better than Geotab/Samsara static thresholds",
# MIGRATED_TO_ROUTER:             ],
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:     )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
@app.post("/fuelAnalytics/api/alerts/test", tags=["Alerts"])
async def send_test_alert(
    alert_type: str = Query(
        default="low_fuel", description="Type: low_fuel, theft, refuel"
    ),
    truck_id: str = Query(default="TEST-001", description="Test truck ID"),
):
    """
    🆕 v3.12.21: Send a test alert to verify SMS/Email configuration
    """
    try:
        from alert_service import get_alert_manager

        manager = get_alert_manager()

        if alert_type == "low_fuel":
            result = manager.alert_low_fuel(
                truck_id=truck_id,
                current_level_pct=12.5,  # Critical level
                estimated_miles_remaining=45,
                send_sms=True,
            )
        elif alert_type == "theft":
            result = manager.alert_theft_suspected(
                truck_id=truck_id,
                fuel_drop_gallons=35.0,
                fuel_drop_pct=18.5,
                location="Test Location, TX",
            )
        elif alert_type == "refuel":
            result = manager.alert_refuel(
                truck_id=truck_id,
                gallons_added=75.5,
                new_level_pct=92.0,
                location="Test Fuel Stop",
                send_sms=True,
            )
        else:
            raise HTTPException(
                status_code=400, detail=f"Unknown alert type: {alert_type}"
            )

        return {
            "success": result,
            "alert_type": alert_type,
            "truck_id": truck_id,
            "message": (
                "Alert sent successfully"
                if result
                else "Alert failed - check configuration"
            ),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending test alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/export/refuels")
# MIGRATED_TO_ROUTER: async def export_refuels_report(
# MIGRATED_TO_ROUTER:     format: str = Query(default="csv", description="Export format: csv or excel"),
# MIGRATED_TO_ROUTER:     days: int = Query(default=30, ge=1, le=365, description="Days to include"),
# MIGRATED_TO_ROUTER:     truck_id: Optional[str] = Query(default=None, description="Filter by truck"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Export refuel events to CSV or Excel
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         import io
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 truck_id,
# MIGRATED_TO_ROUTER:                 timestamp_utc as refuel_time,
# MIGRATED_TO_ROUTER:                 fuel_before,
# MIGRATED_TO_ROUTER:                 fuel_after,
# MIGRATED_TO_ROUTER:                 gallons_added,
# MIGRATED_TO_ROUTER:                 refuel_type,
# MIGRATED_TO_ROUTER:                 latitude,
# MIGRATED_TO_ROUTER:                 longitude,
# MIGRATED_TO_ROUTER:                 validated
# MIGRATED_TO_ROUTER:             FROM refuel_events
# MIGRATED_TO_ROUTER:             WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         params = {"days": days}
# MIGRATED_TO_ROUTER:         if truck_id:
# MIGRATED_TO_ROUTER:             query += " AND truck_id = :truck_id"
# MIGRATED_TO_ROUTER:             params["truck_id"] = truck_id
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         query += " ORDER BY timestamp_utc DESC"
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(query), params)
# MIGRATED_TO_ROUTER:             data = [dict(row._mapping) for row in result.fetchall()]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if not data:
# MIGRATED_TO_ROUTER:             raise HTTPException(status_code=404, detail="No refuel events found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         df = pd.DataFrame(data)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if "refuel_time" in df.columns:
# MIGRATED_TO_ROUTER:             df["refuel_time"] = pd.to_datetime(df["refuel_time"]).dt.strftime(
# MIGRATED_TO_ROUTER:                 "%Y-%m-%d %H:%M:%S"
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if format.lower() == "excel":
# MIGRATED_TO_ROUTER:             output = io.BytesIO()
# MIGRATED_TO_ROUTER:             with pd.ExcelWriter(output, engine="openpyxl") as writer:
# MIGRATED_TO_ROUTER:                 df.to_excel(writer, sheet_name="Refuel Events", index=False)
# MIGRATED_TO_ROUTER:             output.seek(0)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             filename = f"refuels_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
# MIGRATED_TO_ROUTER:             return Response(
# MIGRATED_TO_ROUTER:                 content=output.getvalue(),
# MIGRATED_TO_ROUTER:                 media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
# MIGRATED_TO_ROUTER:                 headers={"Content-Disposition": f"attachment; filename={filename}"},
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:         else:
# MIGRATED_TO_ROUTER:             output = io.StringIO()
# MIGRATED_TO_ROUTER:             df.to_csv(output, index=False)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             filename = f"refuels_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
# MIGRATED_TO_ROUTER:             return Response(
# MIGRATED_TO_ROUTER:                 content=output.getvalue(),
# MIGRATED_TO_ROUTER:                 media_type="text/csv",
# MIGRATED_TO_ROUTER:                 headers={"Content-Disposition": f"attachment; filename={filename}"},
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Export refuels error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v3.12.21: DASHBOARD CUSTOMIZATION ENDPOINTS (#11)
# ============================================================================

# In-memory storage for user dashboards (replace with DB in production)
_user_dashboards: Dict[str, Dict] = {}
_user_preferences: Dict[str, Dict] = {}
_scheduled_reports: Dict[str, Dict] = {}


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/dashboard/widgets/available", tags=["Dashboard"])
# MIGRATED_TO_ROUTER: async def get_available_widgets():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get list of available widget types for dashboard customization.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     from models import WidgetType, WidgetSize
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     widgets = [
# MIGRATED_TO_ROUTER:         {
# MIGRATED_TO_ROUTER:             "type": WidgetType.FLEET_SUMMARY.value,
# MIGRATED_TO_ROUTER:             "name": "Fleet Summary",
# MIGRATED_TO_ROUTER:             "description": "Overview of fleet status, active/offline trucks",
# MIGRATED_TO_ROUTER:             "default_size": WidgetSize.LARGE.value,
# MIGRATED_TO_ROUTER:             "available_sizes": [WidgetSize.MEDIUM.value, WidgetSize.LARGE.value],
# MIGRATED_TO_ROUTER:             "config_options": ["showOffline", "showAlerts"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         {
# MIGRATED_TO_ROUTER:             "type": WidgetType.TRUCK_MAP.value,
# MIGRATED_TO_ROUTER:             "name": "Truck Map",
# MIGRATED_TO_ROUTER:             "description": "Real-time GPS locations of all trucks",
# MIGRATED_TO_ROUTER:             "default_size": WidgetSize.LARGE.value,
# MIGRATED_TO_ROUTER:             "available_sizes": [WidgetSize.LARGE.value, WidgetSize.FULL_WIDTH.value],
# MIGRATED_TO_ROUTER:             "config_options": ["showLabels", "clusterMarkers"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         {
# MIGRATED_TO_ROUTER:             "type": WidgetType.EFFICIENCY_CHART.value,
# MIGRATED_TO_ROUTER:             "name": "Efficiency Chart",
# MIGRATED_TO_ROUTER:             "description": "MPG and fuel consumption trends",
# MIGRATED_TO_ROUTER:             "default_size": WidgetSize.MEDIUM.value,
# MIGRATED_TO_ROUTER:             "available_sizes": [
# MIGRATED_TO_ROUTER:                 WidgetSize.SMALL.value,
# MIGRATED_TO_ROUTER:                 WidgetSize.MEDIUM.value,
# MIGRATED_TO_ROUTER:                 WidgetSize.LARGE.value,
# MIGRATED_TO_ROUTER:             ],
# MIGRATED_TO_ROUTER:             "config_options": ["period", "showTrend"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         {
# MIGRATED_TO_ROUTER:             "type": WidgetType.FUEL_LEVELS.value,
# MIGRATED_TO_ROUTER:             "name": "Fuel Levels",
# MIGRATED_TO_ROUTER:             "description": "Current fuel levels across fleet",
# MIGRATED_TO_ROUTER:             "default_size": WidgetSize.MEDIUM.value,
# MIGRATED_TO_ROUTER:             "available_sizes": [WidgetSize.SMALL.value, WidgetSize.MEDIUM.value],
# MIGRATED_TO_ROUTER:             "config_options": ["sortBy", "lowFuelThreshold"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         {
# MIGRATED_TO_ROUTER:             "type": WidgetType.ALERTS.value,
# MIGRATED_TO_ROUTER:             "name": "Alerts",
# MIGRATED_TO_ROUTER:             "description": "Active alerts and notifications",
# MIGRATED_TO_ROUTER:             "default_size": WidgetSize.SMALL.value,
# MIGRATED_TO_ROUTER:             "available_sizes": [WidgetSize.SMALL.value, WidgetSize.MEDIUM.value],
# MIGRATED_TO_ROUTER:             "config_options": ["severityFilter", "limit"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         {
# MIGRATED_TO_ROUTER:             "type": WidgetType.MPG_RANKING.value,
# MIGRATED_TO_ROUTER:             "name": "MPG Ranking",
# MIGRATED_TO_ROUTER:             "description": "Top/bottom performers by MPG",
# MIGRATED_TO_ROUTER:             "default_size": WidgetSize.SMALL.value,
# MIGRATED_TO_ROUTER:             "available_sizes": [WidgetSize.SMALL.value, WidgetSize.MEDIUM.value],
# MIGRATED_TO_ROUTER:             "config_options": ["topN", "showBottom"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         {
# MIGRATED_TO_ROUTER:             "type": WidgetType.IDLE_TRACKING.value,
# MIGRATED_TO_ROUTER:             "name": "Idle Tracking",
# MIGRATED_TO_ROUTER:             "description": "Idle time and consumption analysis",
# MIGRATED_TO_ROUTER:             "default_size": WidgetSize.MEDIUM.value,
# MIGRATED_TO_ROUTER:             "available_sizes": [WidgetSize.SMALL.value, WidgetSize.MEDIUM.value],
# MIGRATED_TO_ROUTER:             "config_options": ["period", "threshold"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         {
# MIGRATED_TO_ROUTER:             "type": WidgetType.REFUEL_HISTORY.value,
# MIGRATED_TO_ROUTER:             "name": "Refuel History",
# MIGRATED_TO_ROUTER:             "description": "Recent refueling events",
# MIGRATED_TO_ROUTER:             "default_size": WidgetSize.MEDIUM.value,
# MIGRATED_TO_ROUTER:             "available_sizes": [
# MIGRATED_TO_ROUTER:                 WidgetSize.SMALL.value,
# MIGRATED_TO_ROUTER:                 WidgetSize.MEDIUM.value,
# MIGRATED_TO_ROUTER:                 WidgetSize.LARGE.value,
# MIGRATED_TO_ROUTER:             ],
# MIGRATED_TO_ROUTER:             "config_options": ["limit", "showCost"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         {
# MIGRATED_TO_ROUTER:             "type": WidgetType.PREDICTIONS.value,
# MIGRATED_TO_ROUTER:             "name": "Predictions",
# MIGRATED_TO_ROUTER:             "description": "Fuel consumption and empty tank predictions",
# MIGRATED_TO_ROUTER:             "default_size": WidgetSize.MEDIUM.value,
# MIGRATED_TO_ROUTER:             "available_sizes": [WidgetSize.MEDIUM.value, WidgetSize.LARGE.value],
# MIGRATED_TO_ROUTER:             "config_options": ["predictionHours", "showRange"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         {
# MIGRATED_TO_ROUTER:             "type": WidgetType.HEALTH_MONITOR.value,
# MIGRATED_TO_ROUTER:             "name": "Health Monitor",
# MIGRATED_TO_ROUTER:             "description": "Truck health scores and anomaly detection",
# MIGRATED_TO_ROUTER:             "default_size": WidgetSize.LARGE.value,
# MIGRATED_TO_ROUTER:             "available_sizes": [WidgetSize.MEDIUM.value, WidgetSize.LARGE.value],
# MIGRATED_TO_ROUTER:             "config_options": ["alertsOnly", "showTrends"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:     ]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"widgets": widgets, "total": len(widgets)}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/dashboard/layout/{user_id}", tags=["Dashboard"])
# MIGRATED_TO_ROUTER: async def get_dashboard_layout(user_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get user's dashboard layout configuration.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if user_id in _user_dashboards:
# MIGRATED_TO_ROUTER:         return _user_dashboards[user_id]
# MIGRATED_TO_ROUTER:
# Return default layout
# MIGRATED_TO_ROUTER:     from models import WidgetType, WidgetSize
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     default_layout = {
# MIGRATED_TO_ROUTER:         "user_id": user_id,
# MIGRATED_TO_ROUTER:         "name": "Default Dashboard",
# MIGRATED_TO_ROUTER:         "columns": 4,
# MIGRATED_TO_ROUTER:         "theme": "dark",
# MIGRATED_TO_ROUTER:         "widgets": [
# MIGRATED_TO_ROUTER:             {
# MIGRATED_TO_ROUTER:                 "id": "widget-1",
# MIGRATED_TO_ROUTER:                 "widget_type": WidgetType.FLEET_SUMMARY.value,
# MIGRATED_TO_ROUTER:                 "title": "Fleet Overview",
# MIGRATED_TO_ROUTER:                 "size": WidgetSize.LARGE.value,
# MIGRATED_TO_ROUTER:                 "position": {"x": 0, "y": 0},
# MIGRATED_TO_ROUTER:                 "config": {},
# MIGRATED_TO_ROUTER:                 "visible": True,
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             {
# MIGRATED_TO_ROUTER:                 "id": "widget-2",
# MIGRATED_TO_ROUTER:                 "widget_type": WidgetType.ALERTS.value,
# MIGRATED_TO_ROUTER:                 "title": "Active Alerts",
# MIGRATED_TO_ROUTER:                 "size": WidgetSize.SMALL.value,
# MIGRATED_TO_ROUTER:                 "position": {"x": 2, "y": 0},
# MIGRATED_TO_ROUTER:                 "config": {"limit": 5},
# MIGRATED_TO_ROUTER:                 "visible": True,
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             {
# MIGRATED_TO_ROUTER:                 "id": "widget-3",
# MIGRATED_TO_ROUTER:                 "widget_type": WidgetType.EFFICIENCY_CHART.value,
# MIGRATED_TO_ROUTER:                 "title": "Fleet Efficiency",
# MIGRATED_TO_ROUTER:                 "size": WidgetSize.MEDIUM.value,
# MIGRATED_TO_ROUTER:                 "position": {"x": 0, "y": 2},
# MIGRATED_TO_ROUTER:                 "config": {"period": "24h"},
# MIGRATED_TO_ROUTER:                 "visible": True,
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:             {
# MIGRATED_TO_ROUTER:                 "id": "widget-4",
# MIGRATED_TO_ROUTER:                 "widget_type": WidgetType.MPG_RANKING.value,
# MIGRATED_TO_ROUTER:                 "title": "Top Performers",
# MIGRATED_TO_ROUTER:                 "size": WidgetSize.SMALL.value,
# MIGRATED_TO_ROUTER:                 "position": {"x": 2, "y": 2},
# MIGRATED_TO_ROUTER:                 "config": {"topN": 5},
# MIGRATED_TO_ROUTER:                 "visible": True,
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:         ],
# MIGRATED_TO_ROUTER:         "created_at": utc_now().isoformat(),
# MIGRATED_TO_ROUTER:         "updated_at": utc_now().isoformat(),
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return default_layout
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post("/fuelAnalytics/api/dashboard/layout/{user_id}", tags=["Dashboard"])
# MIGRATED_TO_ROUTER: async def save_dashboard_layout(user_id: str, layout: Dict[str, Any]):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Save user's dashboard layout configuration.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     layout["user_id"] = user_id
# MIGRATED_TO_ROUTER:     layout["updated_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     if user_id not in _user_dashboards:
# MIGRATED_TO_ROUTER:         layout["created_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:     else:
# MIGRATED_TO_ROUTER:         layout["created_at"] = _user_dashboards[user_id].get(
# MIGRATED_TO_ROUTER:             "created_at", utc_now().isoformat()
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     _user_dashboards[user_id] = layout
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     logger.info(f"📊 Dashboard layout saved for user {user_id}")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "saved", "layout": layout}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.put(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/dashboard/widget/{user_id}/{widget_id}", tags=["Dashboard"]
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def update_widget(user_id: str, widget_id: str, widget_config: Dict[str, Any]):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Update a specific widget's configuration.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if user_id not in _user_dashboards:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=404, detail="Dashboard not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     dashboard = _user_dashboards[user_id]
# MIGRATED_TO_ROUTER:     widget_found = False
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     for widget in dashboard.get("widgets", []):
# MIGRATED_TO_ROUTER:         if widget["id"] == widget_id:
# MIGRATED_TO_ROUTER:             widget.update(widget_config)
# MIGRATED_TO_ROUTER:             widget_found = True
# MIGRATED_TO_ROUTER:             break
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     if not widget_found:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     dashboard["updated_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "updated", "widget_id": widget_id}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.delete(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/dashboard/widget/{user_id}/{widget_id}", tags=["Dashboard"]
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def delete_widget(user_id: str, widget_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Remove a widget from user's dashboard.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if user_id not in _user_dashboards:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=404, detail="Dashboard not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     dashboard = _user_dashboards[user_id]
# MIGRATED_TO_ROUTER:     original_count = len(dashboard.get("widgets", []))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     dashboard["widgets"] = [
# MIGRATED_TO_ROUTER:         w for w in dashboard.get("widgets", []) if w["id"] != widget_id
# MIGRATED_TO_ROUTER:     ]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     if len(dashboard["widgets"]) == original_count:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     dashboard["updated_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "deleted", "widget_id": widget_id}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/user/preferences/{user_id}", tags=["Dashboard"])
# MIGRATED_TO_ROUTER: async def get_user_preferences(user_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get user preferences.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if user_id in _user_preferences:
# MIGRATED_TO_ROUTER:         return _user_preferences[user_id]
# MIGRATED_TO_ROUTER:
# Default preferences
# MIGRATED_TO_ROUTER:     return {
# MIGRATED_TO_ROUTER:         "user_id": user_id,
# MIGRATED_TO_ROUTER:         "default_dashboard": None,
# MIGRATED_TO_ROUTER:         "favorite_trucks": [],
# MIGRATED_TO_ROUTER:         "alert_settings": {
# MIGRATED_TO_ROUTER:             "email_alerts": False,
# MIGRATED_TO_ROUTER:             "sms_alerts": False,
# MIGRATED_TO_ROUTER:             "push_notifications": True,
# MIGRATED_TO_ROUTER:             "severity_filter": ["critical", "warning"],
# MIGRATED_TO_ROUTER:         },
# MIGRATED_TO_ROUTER:         "timezone": "America/Chicago",
# MIGRATED_TO_ROUTER:         "units": "imperial",
# MIGRATED_TO_ROUTER:         "notifications_enabled": True,
# MIGRATED_TO_ROUTER:         "email_reports": False,
# MIGRATED_TO_ROUTER:         "report_frequency": "daily",
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.put("/fuelAnalytics/api/user/preferences/{user_id}", tags=["Dashboard"])
# MIGRATED_TO_ROUTER: async def update_user_preferences(user_id: str, preferences: Dict[str, Any]):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Update user preferences.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     preferences["user_id"] = user_id
# MIGRATED_TO_ROUTER:     _user_preferences[user_id] = preferences
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     logger.info(f"⚙️ Preferences updated for user {user_id}")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "updated", "preferences": preferences}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v3.12.21: SCHEDULED REPORTS ENDPOINTS (#13)
# ============================================================================


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/reports/scheduled/{user_id}", tags=["Reports"])
# MIGRATED_TO_ROUTER: async def get_scheduled_reports(user_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get user's scheduled reports.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     user_reports = [
# MIGRATED_TO_ROUTER:         r for r in _scheduled_reports.values() if r.get("user_id") == user_id
# MIGRATED_TO_ROUTER:     ]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"reports": user_reports, "total": len(user_reports)}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post("/fuelAnalytics/api/reports/schedule", tags=["Reports"])
# MIGRATED_TO_ROUTER: async def create_scheduled_report(report: Dict[str, Any]):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Create a new scheduled report.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     import uuid
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     report_id = f"report-{uuid.uuid4().hex[:8]}"
# MIGRATED_TO_ROUTER:     report["id"] = report_id
# MIGRATED_TO_ROUTER:     report["created_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:     report["enabled"] = True
# MIGRATED_TO_ROUTER:     report["last_run"] = None
# MIGRATED_TO_ROUTER:
# Calculate next run based on schedule
# MIGRATED_TO_ROUTER:     schedule = report.get("schedule", "daily")
# MIGRATED_TO_ROUTER:     if schedule == "daily":
# MIGRATED_TO_ROUTER:         report["next_run"] = (
# MIGRATED_TO_ROUTER:             (utc_now() + timedelta(days=1))
# MIGRATED_TO_ROUTER:             .replace(hour=6, minute=0, second=0)
# MIGRATED_TO_ROUTER:             .isoformat()
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:     elif schedule == "weekly":
# MIGRATED_TO_ROUTER:         report["next_run"] = (
# MIGRATED_TO_ROUTER:             (utc_now() + timedelta(days=7))
# MIGRATED_TO_ROUTER:             .replace(hour=6, minute=0, second=0)
# MIGRATED_TO_ROUTER:             .isoformat()
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:     elif schedule == "monthly":
# MIGRATED_TO_ROUTER:         report["next_run"] = (
# MIGRATED_TO_ROUTER:             (utc_now() + timedelta(days=30))
# MIGRATED_TO_ROUTER:             .replace(hour=6, minute=0, second=0)
# MIGRATED_TO_ROUTER:             .isoformat()
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     _scheduled_reports[report_id] = report
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     logger.info(f"📅 Scheduled report created: {report_id}")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "created", "report": report}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.put("/fuelAnalytics/api/reports/schedule/{report_id}", tags=["Reports"])
# MIGRATED_TO_ROUTER: async def update_scheduled_report(report_id: str, updates: Dict[str, Any]):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Update a scheduled report.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if report_id not in _scheduled_reports:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=404, detail="Report not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     report = _scheduled_reports[report_id]
# MIGRATED_TO_ROUTER:     report.update(updates)
# MIGRATED_TO_ROUTER:     report["updated_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "updated", "report": report}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.delete("/fuelAnalytics/api/reports/schedule/{report_id}", tags=["Reports"])
# MIGRATED_TO_ROUTER: async def delete_scheduled_report(report_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Delete a scheduled report.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if report_id not in _scheduled_reports:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=404, detail="Report not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     del _scheduled_reports[report_id]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     logger.info(f"🗑️ Scheduled report deleted: {report_id}")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "deleted", "report_id": report_id}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post("/fuelAnalytics/api/reports/run/{report_id}", tags=["Reports"])
# MIGRATED_TO_ROUTER: async def run_report_now(report_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Run a scheduled report immediately.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if report_id not in _scheduled_reports:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=404, detail="Report not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     report = _scheduled_reports[report_id]
# MIGRATED_TO_ROUTER:     report_type = report.get("report_type", "fleet_summary")
# MIGRATED_TO_ROUTER:
# Generate report based on type
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         if report_type == "fleet_summary":
# MIGRATED_TO_ROUTER:             data = await get_fleet_summary()
# MIGRATED_TO_ROUTER:         elif report_type == "efficiency":
# MIGRATED_TO_ROUTER:             data = await get_efficiency_rankings()
# MIGRATED_TO_ROUTER:         elif report_type == "fuel_usage":
# Get fuel consumption data
# MIGRATED_TO_ROUTER:             data = {"message": "Fuel usage report generated"}
# MIGRATED_TO_ROUTER:         else:
# MIGRATED_TO_ROUTER:             data = {"message": f"Report type '{report_type}' generated"}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         report["last_run"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "status": "success",
# MIGRATED_TO_ROUTER:             "report_id": report_id,
# MIGRATED_TO_ROUTER:             "generated_at": report["last_run"],
# MIGRATED_TO_ROUTER:             "data_preview": str(data)[:500] if data else None,
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Report generation error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v3.12.21: GPS TRACKING ENDPOINTS (#17)
# ============================================================================

# In-memory storage for GPS tracking (replace with DB in production)
_gps_tracking_data: Dict[str, Dict] = {}
_geofences: Dict[str, Dict] = {}


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/gps/trucks", tags=["GPS"])
# MIGRATED_TO_ROUTER: async def get_gps_truck_positions():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get real-time GPS positions for all trucks.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# Get truck data from database
# MIGRATED_TO_ROUTER:         fleet = await get_fleet_summary()
# MIGRATED_TO_ROUTER:         trucks = fleet.get("truck_details", []) if isinstance(fleet, dict) else []
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         positions = []
# MIGRATED_TO_ROUTER:         for truck in trucks:
# MIGRATED_TO_ROUTER:             truck_id = truck.get("truck_id", "")
# MIGRATED_TO_ROUTER:             positions.append(
# MIGRATED_TO_ROUTER:                 {
# MIGRATED_TO_ROUTER:                     "truck_id": truck_id,
# MIGRATED_TO_ROUTER:                     "latitude": truck.get("latitude"),
# MIGRATED_TO_ROUTER:                     "longitude": truck.get("longitude"),
# MIGRATED_TO_ROUTER:                     "speed_mph": truck.get("speed_mph", 0),
# MIGRATED_TO_ROUTER:                     "heading": truck.get("heading", 0),
# MIGRATED_TO_ROUTER:                     "status": truck.get("status", "UNKNOWN"),
# MIGRATED_TO_ROUTER:                     "last_update": truck.get("last_update") or utc_now().isoformat(),
# MIGRATED_TO_ROUTER:                     "address": _gps_tracking_data.get(truck_id, {}).get("last_address"),
# MIGRATED_TO_ROUTER:                 }
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "trucks": positions,
# MIGRATED_TO_ROUTER:             "total": len(positions),
# MIGRATED_TO_ROUTER:             "timestamp": utc_now().isoformat(),
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"GPS positions error: {e}")
# MIGRATED_TO_ROUTER:         return {"trucks": [], "total": 0, "error": str(e)}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/gps/truck/{truck_id}/history", tags=["GPS"])
# MIGRATED_TO_ROUTER: async def get_truck_route_history(
# MIGRATED_TO_ROUTER:     truck_id: str,
# MIGRATED_TO_ROUTER:     hours: int = Query(24, ge=1, le=168, description="Hours of history to retrieve"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get GPS route history for a specific truck.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# In production, this would query MySQL historical GPS data
# For now, return sample data structure
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "truck_id": truck_id,
# MIGRATED_TO_ROUTER:             "period_hours": hours,
# MIGRATED_TO_ROUTER:             "route": [],  # Would contain [{lat, lon, timestamp, speed}]
# MIGRATED_TO_ROUTER:             "total_distance_miles": 0,
# MIGRATED_TO_ROUTER:             "stops": [],  # Detected stops/rest areas
# MIGRATED_TO_ROUTER:             "geofence_events": [],
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Route history error: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/gps/geofences", tags=["GPS"])
# MIGRATED_TO_ROUTER: async def get_geofences():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get all configured geofences.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     return {"geofences": list(_geofences.values()), "total": len(_geofences)}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post("/fuelAnalytics/api/gps/geofence", tags=["GPS"])
# MIGRATED_TO_ROUTER: async def create_geofence(geofence: Dict[str, Any]):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Create a new geofence zone.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Types: circle (center + radius) or polygon (list of coordinates)
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     import uuid
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     geofence_id = f"geofence-{uuid.uuid4().hex[:8]}"
# MIGRATED_TO_ROUTER:     geofence["id"] = geofence_id
# MIGRATED_TO_ROUTER:     geofence["created_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:     geofence["active"] = True
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     _geofences[geofence_id] = geofence
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     logger.info(f"📍 Geofence created: {geofence.get('name', geofence_id)}")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "created", "geofence": geofence}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.delete("/fuelAnalytics/api/gps/geofence/{geofence_id}", tags=["GPS"])
# MIGRATED_TO_ROUTER: async def delete_geofence(geofence_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Delete a geofence.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if geofence_id not in _geofences:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=404, detail="Geofence not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     del _geofences[geofence_id]
# MIGRATED_TO_ROUTER:     return {"status": "deleted", "geofence_id": geofence_id}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/gps/geofence/{geofence_id}/events", tags=["GPS"])
# MIGRATED_TO_ROUTER: async def get_geofence_events(
# MIGRATED_TO_ROUTER:     geofence_id: str,
# MIGRATED_TO_ROUTER:     hours: int = Query(24, ge=1, le=168),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get entry/exit events for a geofence.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if geofence_id not in _geofences:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=404, detail="Geofence not found")
# MIGRATED_TO_ROUTER:
# In production, query historical events from database
# MIGRATED_TO_ROUTER:     return {
# MIGRATED_TO_ROUTER:         "geofence_id": geofence_id,
# MIGRATED_TO_ROUTER:         "geofence_name": _geofences[geofence_id].get("name"),
# MIGRATED_TO_ROUTER:         "period_hours": hours,
# MIGRATED_TO_ROUTER:         "events": [],  # Would contain [{truck_id, event_type, timestamp}]
# MIGRATED_TO_ROUTER:         "summary": {"total_entries": 0, "total_exits": 0, "unique_trucks": 0},
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 v3.12.21: PUSH NOTIFICATIONS ENDPOINTS (#19)
# ============================================================================

# In-memory storage for notifications
_push_subscriptions: Dict[str, Dict] = {}
_notification_queue: List[Dict] = []


# MIGRATED_TO_ROUTER: @app.post("/fuelAnalytics/api/notifications/subscribe", tags=["Notifications"])
# MIGRATED_TO_ROUTER: async def subscribe_to_push(subscription: Dict[str, Any]):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Subscribe a device to push notifications.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     user_id = subscription.get("user_id")
# MIGRATED_TO_ROUTER:     if not user_id:
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=400, detail="user_id is required")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     subscription["subscribed_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:     subscription["active"] = True
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     _push_subscriptions[user_id] = subscription
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     logger.info(f"🔔 Push subscription added for user {user_id}")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "subscribed", "user_id": user_id}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.delete(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/notifications/unsubscribe/{user_id}", tags=["Notifications"]
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def unsubscribe_from_push(user_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Unsubscribe a device from push notifications.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     if user_id in _push_subscriptions:
# MIGRATED_TO_ROUTER:         del _push_subscriptions[user_id]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "unsubscribed", "user_id": user_id}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/notifications/{user_id}", tags=["Notifications"])
# MIGRATED_TO_ROUTER: async def get_user_notifications(
# MIGRATED_TO_ROUTER:     user_id: str,
# MIGRATED_TO_ROUTER:     limit: int = Query(20, ge=1, le=100),
# MIGRATED_TO_ROUTER:     unread_only: bool = Query(False),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Get notifications for a user.
# MIGRATED_TO_ROUTER:     """
# Filter notifications for this user
# MIGRATED_TO_ROUTER:     user_notifications = [
# MIGRATED_TO_ROUTER:         n
# MIGRATED_TO_ROUTER:         for n in _notification_queue
# MIGRATED_TO_ROUTER:         if n.get("user_id") == user_id or n.get("broadcast", False)
# MIGRATED_TO_ROUTER:     ]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     if unread_only:
# MIGRATED_TO_ROUTER:         user_notifications = [n for n in user_notifications if not n.get("read", False)]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {
# MIGRATED_TO_ROUTER:         "notifications": user_notifications[-limit:],
# MIGRATED_TO_ROUTER:         "total": len(user_notifications),
# MIGRATED_TO_ROUTER:         "unread_count": len(
# MIGRATED_TO_ROUTER:             [n for n in user_notifications if not n.get("read", False)]
# MIGRATED_TO_ROUTER:         ),
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post("/fuelAnalytics/api/notifications/send", tags=["Notifications"])
# MIGRATED_TO_ROUTER: async def send_notification(notification: Dict[str, Any]):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Send a push notification.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     For internal/admin use to send alerts to users.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     import uuid
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     notification["id"] = f"notif-{uuid.uuid4().hex[:8]}"
# MIGRATED_TO_ROUTER:     notification["created_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:     notification["read"] = False
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     _notification_queue.append(notification)
# MIGRATED_TO_ROUTER:
# Limit queue size
# MIGRATED_TO_ROUTER:     if len(_notification_queue) > 1000:
# MIGRATED_TO_ROUTER:         _notification_queue.pop(0)
# MIGRATED_TO_ROUTER:
# In production, this would trigger actual push via FCM/APNs
# MIGRATED_TO_ROUTER:     target = notification.get("user_id", "broadcast")
# MIGRATED_TO_ROUTER:     logger.info(
# MIGRATED_TO_ROUTER:         f"📨 Notification sent to {target}: {notification.get('title', 'No title')}"
# MIGRATED_TO_ROUTER:     )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "sent", "notification_id": notification["id"]}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.put(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/notifications/{notification_id}/read", tags=["Notifications"]
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def mark_notification_read(notification_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Mark a notification as read.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     for notification in _notification_queue:
# MIGRATED_TO_ROUTER:         if notification.get("id") == notification_id:
# MIGRATED_TO_ROUTER:             notification["read"] = True
# MIGRATED_TO_ROUTER:             notification["read_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:             return {"status": "marked_read", "notification_id": notification_id}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     raise HTTPException(status_code=404, detail="Notification not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post("/fuelAnalytics/api/notifications/{user_id}/read-all", tags=["Notifications"])
# MIGRATED_TO_ROUTER: async def mark_all_notifications_read(user_id: str):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.12.21: Mark all notifications as read for a user.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     count = 0
# MIGRATED_TO_ROUTER:     for notification in _notification_queue:
# MIGRATED_TO_ROUTER:         if notification.get("user_id") == user_id or notification.get(
# MIGRATED_TO_ROUTER:             "broadcast", False
# MIGRATED_TO_ROUTER:         ):
# MIGRATED_TO_ROUTER:             if not notification.get("read", False):
# MIGRATED_TO_ROUTER:                 notification["read"] = True
# MIGRATED_TO_ROUTER:                 notification["read_at"] = utc_now().isoformat()
# MIGRATED_TO_ROUTER:                 count += 1
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {"status": "success", "marked_read": count}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# 🆕 ENGINE HEALTH MONITORING ENDPOINTS - v3.13.0
# ============================================================================


# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/engine-health/fleet-summary", tags=["Engine Health"])
# MIGRATED_TO_ROUTER: async def get_engine_health_fleet_summary():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.13.0: Get fleet-wide engine health summary.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:     - Count of healthy/warning/critical/offline trucks
# MIGRATED_TO_ROUTER:     - Top critical and warning alerts
# MIGRATED_TO_ROUTER:     - Sensor coverage statistics
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:         from engine_health_engine import EngineHealthAnalyzer, FleetHealthSummary
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:         analyzer = EngineHealthAnalyzer()
# MIGRATED_TO_ROUTER:
# Get latest reading for each truck
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 fm.truck_id,
# MIGRATED_TO_ROUTER:                 fm.timestamp_utc,
# MIGRATED_TO_ROUTER:                 fm.oil_pressure_psi,
# MIGRATED_TO_ROUTER:                 fm.coolant_temp_f,
# MIGRATED_TO_ROUTER:                 fm.oil_temp_f,
# MIGRATED_TO_ROUTER:                 fm.battery_voltage,
# MIGRATED_TO_ROUTER:                 fm.def_level_pct,
# MIGRATED_TO_ROUTER:                 fm.engine_load_pct,
# MIGRATED_TO_ROUTER:                 fm.rpm,
# MIGRATED_TO_ROUTER:                 fm.speed_mph,
# MIGRATED_TO_ROUTER:                 fm.truck_status
# MIGRATED_TO_ROUTER:             FROM fuel_metrics fm
# MIGRATED_TO_ROUTER:             INNER JOIN (
# MIGRATED_TO_ROUTER:                 SELECT truck_id, MAX(timestamp_utc) as max_ts
# MIGRATED_TO_ROUTER:                 FROM fuel_metrics
# MIGRATED_TO_ROUTER:                 WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
# MIGRATED_TO_ROUTER:                 GROUP BY truck_id
# MIGRATED_TO_ROUTER:             ) latest ON fm.truck_id = latest.truck_id
# MIGRATED_TO_ROUTER:                      AND fm.timestamp_utc = latest.max_ts
# MIGRATED_TO_ROUTER:             ORDER BY fm.truck_id
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(query))
# MIGRATED_TO_ROUTER:             rows = result.fetchall()
# MIGRATED_TO_ROUTER:             columns = result.keys()
# MIGRATED_TO_ROUTER:
# Convert to list of dicts
# MIGRATED_TO_ROUTER:         fleet_data = [dict(zip(columns, row)) for row in rows]
# MIGRATED_TO_ROUTER:
# Analyze fleet health
# MIGRATED_TO_ROUTER:         summary = analyzer.analyze_fleet_health(fleet_data)
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return summary.to_dict()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except ImportError as e:
# MIGRATED_TO_ROUTER:         logger.warning(f"Engine health module not available: {e}")
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "error": "Engine health module not available",
# MIGRATED_TO_ROUTER:             "summary": {
# MIGRATED_TO_ROUTER:                 "total_trucks": 0,
# MIGRATED_TO_ROUTER:                 "healthy": 0,
# MIGRATED_TO_ROUTER:                 "warning": 0,
# MIGRATED_TO_ROUTER:                 "critical": 0,
# MIGRATED_TO_ROUTER:                 "offline": 0,
# MIGRATED_TO_ROUTER:             },
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Error getting fleet health summary: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/engine-health/trucks/{truck_id}", tags=["Engine Health"])
# MIGRATED_TO_ROUTER: async def get_truck_health_detail(
# MIGRATED_TO_ROUTER:     truck_id: str,
# MIGRATED_TO_ROUTER:     include_history: bool = Query(True, description="Include 7-day history for trends"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.13.0: Get detailed engine health status for a specific truck.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns:
# MIGRATED_TO_ROUTER:     - Current sensor values with status indicators
# MIGRATED_TO_ROUTER:     - Active alerts (critical, warning, watch)
# MIGRATED_TO_ROUTER:     - Trend analysis (7-day comparison to 30-day baseline)
# MIGRATED_TO_ROUTER:     - Maintenance predictions with cost estimates
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:         from engine_health_engine import EngineHealthAnalyzer, BaselineCalculator
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:         analyzer = EngineHealthAnalyzer()
# MIGRATED_TO_ROUTER:
# Get current reading
# MIGRATED_TO_ROUTER:         current_query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 truck_id,
# MIGRATED_TO_ROUTER:                 timestamp_utc,
# MIGRATED_TO_ROUTER:                 oil_pressure_psi,
# MIGRATED_TO_ROUTER:                 coolant_temp_f,
# MIGRATED_TO_ROUTER:                 oil_temp_f,
# MIGRATED_TO_ROUTER:                 battery_voltage,
# MIGRATED_TO_ROUTER:                 def_level_pct,
# MIGRATED_TO_ROUTER:                 engine_load_pct,
# MIGRATED_TO_ROUTER:                 rpm,
# MIGRATED_TO_ROUTER:                 speed_mph,
# MIGRATED_TO_ROUTER:                 truck_status,
# MIGRATED_TO_ROUTER:                 latitude,
# MIGRATED_TO_ROUTER:                 longitude
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE truck_id = :truck_id
# MIGRATED_TO_ROUTER:             ORDER BY timestamp_utc DESC
# MIGRATED_TO_ROUTER:             LIMIT 1
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(current_query), {"truck_id": truck_id})
# MIGRATED_TO_ROUTER:             row = result.fetchone()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             if not row:
# MIGRATED_TO_ROUTER:                 raise HTTPException(
# MIGRATED_TO_ROUTER:                     status_code=404, detail=f"Truck {truck_id} not found"
# MIGRATED_TO_ROUTER:                 )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             columns = result.keys()
# MIGRATED_TO_ROUTER:             current_data = dict(zip(columns, row))
# MIGRATED_TO_ROUTER:
# Get historical data for trend analysis
# MIGRATED_TO_ROUTER:         historical_data = []
# MIGRATED_TO_ROUTER:         baselines = {}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if include_history:
# MIGRATED_TO_ROUTER:             history_query = """
# MIGRATED_TO_ROUTER:                 SELECT
# MIGRATED_TO_ROUTER:                     timestamp_utc,
# MIGRATED_TO_ROUTER:                     oil_pressure_psi,
# MIGRATED_TO_ROUTER:                     coolant_temp_f,
# MIGRATED_TO_ROUTER:                     oil_temp_f,
# MIGRATED_TO_ROUTER:                     battery_voltage,
# MIGRATED_TO_ROUTER:                     def_level_pct,
# MIGRATED_TO_ROUTER:                     engine_load_pct,
# MIGRATED_TO_ROUTER:                     rpm
# MIGRATED_TO_ROUTER:                 FROM fuel_metrics
# MIGRATED_TO_ROUTER:                 WHERE truck_id = :truck_id
# MIGRATED_TO_ROUTER:                   AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY)
# MIGRATED_TO_ROUTER:                   AND rpm > 400  -- Only when engine running
# MIGRATED_TO_ROUTER:                 ORDER BY timestamp_utc DESC
# MIGRATED_TO_ROUTER:                 LIMIT 5000
# MIGRATED_TO_ROUTER:             """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             with engine.connect() as conn:
# MIGRATED_TO_ROUTER:                 result = conn.execute(text(history_query), {"truck_id": truck_id})
# MIGRATED_TO_ROUTER:                 rows = result.fetchall()
# MIGRATED_TO_ROUTER:                 columns = result.keys()
# MIGRATED_TO_ROUTER:                 historical_data = [dict(zip(columns, row)) for row in rows]
# MIGRATED_TO_ROUTER:
# Calculate baselines
# MIGRATED_TO_ROUTER:             for sensor in ["oil_pressure_psi", "coolant_temp_f", "battery_voltage"]:
# MIGRATED_TO_ROUTER:                 baseline = BaselineCalculator.calculate_baseline(
# MIGRATED_TO_ROUTER:                     truck_id, sensor, historical_data
# MIGRATED_TO_ROUTER:                 )
# MIGRATED_TO_ROUTER:                 baselines[sensor] = baseline
# MIGRATED_TO_ROUTER:
# Analyze truck health
# MIGRATED_TO_ROUTER:         status = analyzer.analyze_truck_health(
# MIGRATED_TO_ROUTER:             truck_id, current_data, historical_data, baselines
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         response = status.to_dict()
# MIGRATED_TO_ROUTER:
# Add historical chart data (last 7 days, sampled)
# MIGRATED_TO_ROUTER:         if include_history and historical_data:
# Sample to ~100 points for charts
# MIGRATED_TO_ROUTER:             sample_rate = max(1, len(historical_data) // 100)
# MIGRATED_TO_ROUTER:             sampled = historical_data[::sample_rate][:100]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             response["history"] = {
# MIGRATED_TO_ROUTER:                 "timestamps": [str(d.get("timestamp_utc", "")) for d in sampled],
# MIGRATED_TO_ROUTER:                 "oil_pressure": [d.get("oil_pressure_psi") for d in sampled],
# MIGRATED_TO_ROUTER:                 "coolant_temp": [d.get("coolant_temp_f") for d in sampled],
# MIGRATED_TO_ROUTER:                 "oil_temp": [d.get("oil_temp_f") for d in sampled],
# MIGRATED_TO_ROUTER:                 "battery": [d.get("battery_voltage") for d in sampled],
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:
# Add baselines to response
# MIGRATED_TO_ROUTER:             response["baselines"] = {
# MIGRATED_TO_ROUTER:                 sensor: {
# MIGRATED_TO_ROUTER:                     "mean_30d": b.mean_30d,
# MIGRATED_TO_ROUTER:                     "mean_7d": b.mean_7d,
# MIGRATED_TO_ROUTER:                     "std_30d": b.std_30d,
# MIGRATED_TO_ROUTER:                     "min_30d": b.min_30d,
# MIGRATED_TO_ROUTER:                     "max_30d": b.max_30d,
# MIGRATED_TO_ROUTER:                 }
# MIGRATED_TO_ROUTER:                 for sensor, b in baselines.items()
# MIGRATED_TO_ROUTER:                 if b.sample_count > 0
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return response
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Error getting truck health for {truck_id}: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/engine-health/alerts", tags=["Engine Health"])
# MIGRATED_TO_ROUTER: async def get_health_alerts(
# MIGRATED_TO_ROUTER:     severity: Optional[str] = Query(
# MIGRATED_TO_ROUTER:         None, description="Filter by severity: critical, warning, watch"
# MIGRATED_TO_ROUTER:     ),
# MIGRATED_TO_ROUTER:     truck_id: Optional[str] = Query(None, description="Filter by truck"),
# MIGRATED_TO_ROUTER:     active_only: bool = Query(True, description="Only active alerts"),
# MIGRATED_TO_ROUTER:     limit: int = Query(50, ge=1, le=200),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.13.0: Get engine health alerts.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns list of alerts sorted by severity and timestamp.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# Build query with filters
# MIGRATED_TO_ROUTER:         conditions = []
# MIGRATED_TO_ROUTER:         params = {"limit": limit}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if active_only:
# MIGRATED_TO_ROUTER:             conditions.append("is_active = TRUE")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if severity:
# MIGRATED_TO_ROUTER:             conditions.append("severity = :severity")
# MIGRATED_TO_ROUTER:             params["severity"] = severity
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if truck_id:
# MIGRATED_TO_ROUTER:             conditions.append("truck_id = :truck_id")
# MIGRATED_TO_ROUTER:             params["truck_id"] = truck_id
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         where_clause = " AND ".join(conditions) if conditions else "1=1"
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         query = f"""
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 id, truck_id, category, severity, sensor_name,
# MIGRATED_TO_ROUTER:                 current_value, threshold_value, baseline_value,
# MIGRATED_TO_ROUTER:                 message, action_required, trend_direction,
# MIGRATED_TO_ROUTER:                 is_active, created_at, acknowledged_at
# MIGRATED_TO_ROUTER:             FROM engine_health_alerts
# MIGRATED_TO_ROUTER:             WHERE {where_clause}
# MIGRATED_TO_ROUTER:             ORDER BY
# MIGRATED_TO_ROUTER:                 FIELD(severity, 'critical', 'warning', 'watch', 'info'),
# MIGRATED_TO_ROUTER:                 created_at DESC
# MIGRATED_TO_ROUTER:             LIMIT :limit
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         try:
# MIGRATED_TO_ROUTER:             with engine.connect() as conn:
# MIGRATED_TO_ROUTER:                 result = conn.execute(text(query), params)
# MIGRATED_TO_ROUTER:                 rows = result.fetchall()
# MIGRATED_TO_ROUTER:                 columns = result.keys()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             alerts = [dict(zip(columns, row)) for row in rows]
# MIGRATED_TO_ROUTER:
# Convert datetime objects to strings
# MIGRATED_TO_ROUTER:             for alert in alerts:
# MIGRATED_TO_ROUTER:                 for key in ["created_at", "acknowledged_at"]:
# MIGRATED_TO_ROUTER:                     if alert.get(key):
# MIGRATED_TO_ROUTER:                         alert[key] = str(alert[key])
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             return {
# MIGRATED_TO_ROUTER:                 "alerts": alerts,
# MIGRATED_TO_ROUTER:                 "count": len(alerts),
# MIGRATED_TO_ROUTER:                 "filters": {
# MIGRATED_TO_ROUTER:                     "severity": severity,
# MIGRATED_TO_ROUTER:                     "truck_id": truck_id,
# MIGRATED_TO_ROUTER:                     "active_only": active_only,
# MIGRATED_TO_ROUTER:                 },
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:         except Exception as db_error:
# Table might not exist yet - return empty
# MIGRATED_TO_ROUTER:             logger.warning(f"Engine health alerts table may not exist: {db_error}")
# MIGRATED_TO_ROUTER:             return {
# MIGRATED_TO_ROUTER:                 "alerts": [],
# MIGRATED_TO_ROUTER:                 "count": 0,
# MIGRATED_TO_ROUTER:                 "message": "No alerts table - run migration first",
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Error getting health alerts: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/engine-health/alerts/{alert_id}/acknowledge",
# MIGRATED_TO_ROUTER:     tags=["Engine Health"],
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def acknowledge_alert(
# MIGRATED_TO_ROUTER:     alert_id: int,
# MIGRATED_TO_ROUTER:     acknowledged_by: str = Query(..., description="User who acknowledged"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.13.0: Acknowledge an engine health alert.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             UPDATE engine_health_alerts
# MIGRATED_TO_ROUTER:             SET acknowledged_at = NOW(),
# MIGRATED_TO_ROUTER:                 acknowledged_by = :acknowledged_by
# MIGRATED_TO_ROUTER:             WHERE id = :alert_id
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(
# MIGRATED_TO_ROUTER:                 text(query), {"alert_id": alert_id, "acknowledged_by": acknowledged_by}
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:             conn.commit()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if result.rowcount == 0:
# MIGRATED_TO_ROUTER:             raise HTTPException(status_code=404, detail="Alert not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {"status": "acknowledged", "alert_id": alert_id}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Error acknowledging alert {alert_id}: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/engine-health/alerts/{alert_id}/resolve", tags=["Engine Health"]
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def resolve_alert(
# MIGRATED_TO_ROUTER:     alert_id: int,
# MIGRATED_TO_ROUTER:     resolution_notes: str = Query(None, description="Notes about the resolution"),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.13.0: Resolve/close an engine health alert.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             UPDATE engine_health_alerts
# MIGRATED_TO_ROUTER:             SET is_active = FALSE,
# MIGRATED_TO_ROUTER:                 resolved_at = NOW(),
# MIGRATED_TO_ROUTER:                 resolution_notes = :notes
# MIGRATED_TO_ROUTER:             WHERE id = :alert_id
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(
# MIGRATED_TO_ROUTER:                 text(query), {"alert_id": alert_id, "notes": resolution_notes}
# MIGRATED_TO_ROUTER:             )
# MIGRATED_TO_ROUTER:             conn.commit()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if result.rowcount == 0:
# MIGRATED_TO_ROUTER:             raise HTTPException(status_code=404, detail="Alert not found")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {"status": "resolved", "alert_id": alert_id}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except HTTPException:
# MIGRATED_TO_ROUTER:         raise
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Error resolving alert {alert_id}: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get("/fuelAnalytics/api/engine-health/thresholds", tags=["Engine Health"])
# MIGRATED_TO_ROUTER: async def get_health_thresholds():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.13.0: Get current engine health thresholds.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns the threshold configuration for all monitored sensors.
# MIGRATED_TO_ROUTER:     Useful for frontend to display gauge ranges and alert levels.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     from engine_health_engine import ENGINE_HEALTH_THRESHOLDS
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     return {
# MIGRATED_TO_ROUTER:         "thresholds": ENGINE_HEALTH_THRESHOLDS,
# MIGRATED_TO_ROUTER:         "description": "Threshold values for engine health monitoring",
# MIGRATED_TO_ROUTER:     }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/engine-health/maintenance-predictions", tags=["Engine Health"]
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def get_maintenance_predictions(
# MIGRATED_TO_ROUTER:     truck_id: Optional[str] = Query(None, description="Filter by truck"),
# MIGRATED_TO_ROUTER:     urgency: Optional[str] = Query(
# MIGRATED_TO_ROUTER:         None, description="Filter by urgency: low, medium, high, critical"
# MIGRATED_TO_ROUTER:     ),
# MIGRATED_TO_ROUTER:     status: str = Query(
# MIGRATED_TO_ROUTER:         "active", description="Status: active, scheduled, completed, all"
# MIGRATED_TO_ROUTER:     ),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.13.0: Get maintenance predictions based on engine health analysis.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Returns predicted maintenance needs with cost estimates.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         conditions = []
# MIGRATED_TO_ROUTER:         params = {}
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if status != "all":
# MIGRATED_TO_ROUTER:             conditions.append("status = :status")
# MIGRATED_TO_ROUTER:             params["status"] = status
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if truck_id:
# MIGRATED_TO_ROUTER:             conditions.append("truck_id = :truck_id")
# MIGRATED_TO_ROUTER:             params["truck_id"] = truck_id
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         if urgency:
# MIGRATED_TO_ROUTER:             conditions.append("urgency = :urgency")
# MIGRATED_TO_ROUTER:             params["urgency"] = urgency
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         where_clause = " AND ".join(conditions) if conditions else "1=1"
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         query = f"""
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 id, truck_id, component, urgency, prediction,
# MIGRATED_TO_ROUTER:                 recommended_action, estimated_repair_cost, if_ignored_cost,
# MIGRATED_TO_ROUTER:                 predicted_failure_date, confidence_pct, status,
# MIGRATED_TO_ROUTER:                 scheduled_date, created_at
# MIGRATED_TO_ROUTER:             FROM maintenance_predictions
# MIGRATED_TO_ROUTER:             WHERE {where_clause}
# MIGRATED_TO_ROUTER:             ORDER BY
# MIGRATED_TO_ROUTER:                 FIELD(urgency, 'critical', 'high', 'medium', 'low'),
# MIGRATED_TO_ROUTER:                 predicted_failure_date ASC
# MIGRATED_TO_ROUTER:             LIMIT 100
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         try:
# MIGRATED_TO_ROUTER:             with engine.connect() as conn:
# MIGRATED_TO_ROUTER:                 result = conn.execute(text(query), params)
# MIGRATED_TO_ROUTER:                 rows = result.fetchall()
# MIGRATED_TO_ROUTER:                 columns = result.keys()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             predictions = [dict(zip(columns, row)) for row in rows]
# MIGRATED_TO_ROUTER:
# Convert dates to strings
# MIGRATED_TO_ROUTER:             for pred in predictions:
# MIGRATED_TO_ROUTER:                 for key in ["predicted_failure_date", "scheduled_date", "created_at"]:
# MIGRATED_TO_ROUTER:                     if pred.get(key):
# MIGRATED_TO_ROUTER:                         pred[key] = str(pred[key])
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             return {
# MIGRATED_TO_ROUTER:                 "predictions": predictions,
# MIGRATED_TO_ROUTER:                 "count": len(predictions),
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:         except Exception:
# Table might not exist
# MIGRATED_TO_ROUTER:             return {
# MIGRATED_TO_ROUTER:                 "predictions": [],
# MIGRATED_TO_ROUTER:                 "count": 0,
# MIGRATED_TO_ROUTER:                 "message": "Run migration to create maintenance_predictions table",
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Error getting maintenance predictions: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.get(
# MIGRATED_TO_ROUTER:     "/fuelAnalytics/api/engine-health/sensor-history/{truck_id}/{sensor}",
# MIGRATED_TO_ROUTER:     tags=["Engine Health"],
# MIGRATED_TO_ROUTER: )
# MIGRATED_TO_ROUTER: async def get_sensor_history(
# MIGRATED_TO_ROUTER:     truck_id: str,
# MIGRATED_TO_ROUTER:     sensor: str,
# MIGRATED_TO_ROUTER:     days: int = Query(7, ge=1, le=30),
# MIGRATED_TO_ROUTER: ):
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.13.0: Get historical data for a specific sensor.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Useful for detailed trend charts.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     Valid sensors: oil_pressure_psi, coolant_temp_f, oil_temp_f,
# MIGRATED_TO_ROUTER:                    battery_voltage, def_level_pct, engine_load_pct
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     valid_sensors = [
# MIGRATED_TO_ROUTER:         "oil_pressure_psi",
# MIGRATED_TO_ROUTER:         "coolant_temp_f",
# MIGRATED_TO_ROUTER:         "oil_temp_f",
# MIGRATED_TO_ROUTER:         "battery_voltage",
# MIGRATED_TO_ROUTER:         "def_level_pct",
# MIGRATED_TO_ROUTER:         "engine_load_pct",
# MIGRATED_TO_ROUTER:     ]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     if sensor not in valid_sensors:
# MIGRATED_TO_ROUTER:         raise HTTPException(
# MIGRATED_TO_ROUTER:             status_code=400, detail=f"Invalid sensor. Valid options: {valid_sensors}"
# MIGRATED_TO_ROUTER:         )
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:
# Get hourly averages for cleaner charts
# MIGRATED_TO_ROUTER:         query = f"""
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 DATE_FORMAT(timestamp_utc, '%Y-%m-%d %H:00:00') as hour,
# MIGRATED_TO_ROUTER:                 AVG({sensor}) as avg_value,
# MIGRATED_TO_ROUTER:                 MIN({sensor}) as min_value,
# MIGRATED_TO_ROUTER:                 MAX({sensor}) as max_value,
# MIGRATED_TO_ROUTER:                 COUNT(*) as sample_count
# MIGRATED_TO_ROUTER:             FROM fuel_metrics
# MIGRATED_TO_ROUTER:             WHERE truck_id = :truck_id
# MIGRATED_TO_ROUTER:               AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
# MIGRATED_TO_ROUTER:               AND {sensor} IS NOT NULL
# MIGRATED_TO_ROUTER:               AND rpm > 400  -- Only when engine running
# MIGRATED_TO_ROUTER:             GROUP BY DATE_FORMAT(timestamp_utc, '%Y-%m-%d %H:00:00')
# MIGRATED_TO_ROUTER:             ORDER BY hour DESC
# MIGRATED_TO_ROUTER:             LIMIT 720
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(query), {"truck_id": truck_id, "days": days})
# MIGRATED_TO_ROUTER:             rows = result.fetchall()
# MIGRATED_TO_ROUTER:             columns = result.keys()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         data = [dict(zip(columns, row)) for row in rows]
# MIGRATED_TO_ROUTER:
# Calculate statistics
# MIGRATED_TO_ROUTER:         values = [d["avg_value"] for d in data if d["avg_value"] is not None]
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         stats = {}
# MIGRATED_TO_ROUTER:         if values:
# MIGRATED_TO_ROUTER:             import statistics
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:             stats = {
# MIGRATED_TO_ROUTER:                 "mean": round(statistics.mean(values), 2),
# MIGRATED_TO_ROUTER:                 "min": round(min(values), 2),
# MIGRATED_TO_ROUTER:                 "max": round(max(values), 2),
# MIGRATED_TO_ROUTER:                 "std": round(statistics.stdev(values), 2) if len(values) > 1 else 0,
# MIGRATED_TO_ROUTER:             }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "truck_id": truck_id,
# MIGRATED_TO_ROUTER:             "sensor": sensor,
# MIGRATED_TO_ROUTER:             "days": days,
# MIGRATED_TO_ROUTER:             "data": data,
# MIGRATED_TO_ROUTER:             "statistics": stats,
# MIGRATED_TO_ROUTER:             "data_points": len(data),
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Error getting sensor history: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER: @app.post("/fuelAnalytics/api/engine-health/analyze-now", tags=["Engine Health"])
# MIGRATED_TO_ROUTER: async def trigger_health_analysis():
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     🆕 v3.13.0: Trigger immediate health analysis for all trucks.
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     This runs the analysis and saves any new alerts to the database.
# MIGRATED_TO_ROUTER:     Normally this runs automatically, but can be triggered manually.
# MIGRATED_TO_ROUTER:     """
# MIGRATED_TO_ROUTER:     try:
# MIGRATED_TO_ROUTER:         from database_mysql import get_sqlalchemy_engine
# MIGRATED_TO_ROUTER:         from sqlalchemy import text
# MIGRATED_TO_ROUTER:         from engine_health_engine import EngineHealthAnalyzer
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         engine = get_sqlalchemy_engine()
# MIGRATED_TO_ROUTER:         analyzer = EngineHealthAnalyzer()
# MIGRATED_TO_ROUTER:
# Get latest reading for each truck
# MIGRATED_TO_ROUTER:         query = """
# MIGRATED_TO_ROUTER:             SELECT
# MIGRATED_TO_ROUTER:                 fm.truck_id,
# MIGRATED_TO_ROUTER:                 fm.timestamp_utc,
# MIGRATED_TO_ROUTER:                 fm.oil_pressure_psi,
# MIGRATED_TO_ROUTER:                 fm.coolant_temp_f,
# MIGRATED_TO_ROUTER:                 fm.oil_temp_f,
# MIGRATED_TO_ROUTER:                 fm.battery_voltage,
# MIGRATED_TO_ROUTER:                 fm.def_level_pct,
# MIGRATED_TO_ROUTER:                 fm.engine_load_pct,
# MIGRATED_TO_ROUTER:                 fm.rpm
# MIGRATED_TO_ROUTER:             FROM fuel_metrics fm
# MIGRATED_TO_ROUTER:             INNER JOIN (
# MIGRATED_TO_ROUTER:                 SELECT truck_id, MAX(timestamp_utc) as max_ts
# MIGRATED_TO_ROUTER:                 FROM fuel_metrics
# MIGRATED_TO_ROUTER:                 WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 15 MINUTE)
# MIGRATED_TO_ROUTER:                 GROUP BY truck_id
# MIGRATED_TO_ROUTER:             ) latest ON fm.truck_id = latest.truck_id
# MIGRATED_TO_ROUTER:                      AND fm.timestamp_utc = latest.max_ts
# MIGRATED_TO_ROUTER:         """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         with engine.connect() as conn:
# MIGRATED_TO_ROUTER:             result = conn.execute(text(query))
# MIGRATED_TO_ROUTER:             rows = result.fetchall()
# MIGRATED_TO_ROUTER:             columns = result.keys()
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         fleet_data = [dict(zip(columns, row)) for row in rows]
# MIGRATED_TO_ROUTER:
# Analyze fleet
# MIGRATED_TO_ROUTER:         summary = analyzer.analyze_fleet_health(fleet_data)
# MIGRATED_TO_ROUTER:
# Save new alerts to database
# MIGRATED_TO_ROUTER:         alerts_saved = 0
# MIGRATED_TO_ROUTER:         try:
# MIGRATED_TO_ROUTER:             for alert in summary.critical_alerts + summary.warning_alerts:
# MIGRATED_TO_ROUTER:                 insert_query = """
# MIGRATED_TO_ROUTER:                     INSERT INTO engine_health_alerts
# MIGRATED_TO_ROUTER:                     (truck_id, category, severity, sensor_name, current_value,
# MIGRATED_TO_ROUTER:                      threshold_value, baseline_value, message, action_required,
# MIGRATED_TO_ROUTER:                      trend_direction, is_active)
# MIGRATED_TO_ROUTER:                     VALUES
# MIGRATED_TO_ROUTER:                     (:truck_id, :category, :severity, :sensor_name, :current_value,
# MIGRATED_TO_ROUTER:                      :threshold_value, :baseline_value, :message, :action_required,
# MIGRATED_TO_ROUTER:                      :trend_direction, TRUE)
# MIGRATED_TO_ROUTER:                 """
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:                 with engine.connect() as conn:
# MIGRATED_TO_ROUTER:                     conn.execute(
# MIGRATED_TO_ROUTER:                         text(insert_query),
# MIGRATED_TO_ROUTER:                         {
# MIGRATED_TO_ROUTER:                             "truck_id": alert.truck_id,
# MIGRATED_TO_ROUTER:                             "category": alert.category.value,
# MIGRATED_TO_ROUTER:                             "severity": alert.severity.value,
# MIGRATED_TO_ROUTER:                             "sensor_name": alert.sensor_name,
# MIGRATED_TO_ROUTER:                             "current_value": alert.current_value,
# MIGRATED_TO_ROUTER:                             "threshold_value": alert.threshold_value,
# MIGRATED_TO_ROUTER:                             "baseline_value": alert.baseline_value,
# MIGRATED_TO_ROUTER:                             "message": alert.message,
# MIGRATED_TO_ROUTER:                             "action_required": alert.action_required,
# MIGRATED_TO_ROUTER:                             "trend_direction": alert.trend_direction,
# MIGRATED_TO_ROUTER:                         },
# MIGRATED_TO_ROUTER:                     )
# MIGRATED_TO_ROUTER:                     conn.commit()
# MIGRATED_TO_ROUTER:                     alerts_saved += 1
# MIGRATED_TO_ROUTER:         except Exception as save_error:
# MIGRATED_TO_ROUTER:             logger.warning(f"Could not save alerts (table may not exist): {save_error}")
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:         return {
# MIGRATED_TO_ROUTER:             "status": "completed",
# MIGRATED_TO_ROUTER:             "trucks_analyzed": len(fleet_data),
# MIGRATED_TO_ROUTER:             "critical_alerts": summary.trucks_critical,
# MIGRATED_TO_ROUTER:             "warning_alerts": summary.trucks_warning,
# MIGRATED_TO_ROUTER:             "alerts_saved": alerts_saved,
# MIGRATED_TO_ROUTER:             "timestamp": datetime.now(timezone.utc).isoformat(),
# MIGRATED_TO_ROUTER:         }
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:     except Exception as e:
# MIGRATED_TO_ROUTER:         logger.error(f"Error running health analysis: {e}")
# MIGRATED_TO_ROUTER:         raise HTTPException(status_code=500, detail=str(e))
# MIGRATED_TO_ROUTER:
# MIGRATED_TO_ROUTER:
# ============================================================================
# CATCH-ALL ROUTE - Must be at the END of file after all API routes
# ============================================================================
@app.api_route("/{full_path:path}", methods=["GET"], include_in_schema=False)
async def catch_all_routes(full_path: str):
    """Catch-all for React Router - serve index.html for non-API routes"""
    # Don't interfere with API routes
    if (
        full_path.startswith("api/")
        or full_path.startswith("fuelAnalytics/")
        or full_path.startswith("ws/")
        or full_path.startswith("assets/")
    ):
        raise HTTPException(status_code=404, detail="Resource not found")

    # Serve index.html for all other routes (React Router handles routing)
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)

    raise HTTPException(status_code=404, detail="Frontend not found")


if __name__ == "__main__":
    import uvicorn
    import os
    import sys

    # 🔧 v5.4.3: Windows-specific asyncio fixes for WinError 64
    if sys.platform == "win32":
        import asyncio

        # Use ProactorEventLoop instead of SelectorEventLoop on Windows
        # This prevents WinError 64 network errors
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        logger.info("🪟 Windows detected - using ProactorEventLoop policy")

    # Only use reload in development (when DEV_MODE env var is set)
    is_dev = os.getenv("DEV_MODE", "false").lower() == "true"

    # 🔧 v5.4.3: Enhanced uvicorn config for stability on Windows
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=is_dev,
        log_level="info",
        # Windows-specific: prevent socket reuse issues
        timeout_keep_alive=5,  # Close idle connections faster
        limit_concurrency=1000,  # Prevent socket exhaustion
        backlog=2048,  # Larger backlog for Windows
    )
