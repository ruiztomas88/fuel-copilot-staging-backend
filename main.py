"""
FastAPI Backend for Fuel Copilot Dashboard v4.0.0
Modern async API with HTTP polling (WebSocket removed for simplicity)

🔧 FIX v3.9.3: Migrated from deprecated @app.on_event to lifespan handlers
🆕 v3.10.8: Added JWT authentication and multi-tenant support
🆕 v3.10.9: Removed WebSocket - dashboard uses HTTP polling
🆕 v3.12.21: Unified version, fixed bugs from Phase 1 audit
🆕 v4.0.0: Redis caching, distributed rate limiting, scalability improvements
"""

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd  # For KPIs calculation
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field  # 🆕 v5.5.4: For batch endpoint request model

# Import centralized settings for VERSION
from settings import settings

# Load environment variables from .env file
load_dotenv()


# Helper for timezone-aware UTC datetime (Python 3.12+ compatible)
def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


# Prometheus metrics
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )
    from prometheus_fastapi_instrumentator import Instrumentator

    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    logging.warning("⚠️ Prometheus client not available - metrics disabled")

logger = logging.getLogger(__name__)

try:
    from .database import db  # CSV-based database (optimized with 30s updates)
    from .database_enhanced import (  # NEW: Enhanced MySQL features
        get_fleet_sensor_status,
        get_fuel_consumption_trend,
        get_raw_sensor_history,
    )
    from .models import (
        Alert,
        EfficiencyRanking,
        FleetSummary,
        HealthCheck,
        HistoricalRecord,
        KPIData,
        RefuelEvent,
        TruckDetail,
    )
except ImportError:
    from database import db  # CSV-based database (optimized with 30s updates)
    from database_enhanced import (  # NEW: Enhanced MySQL features
        get_fleet_sensor_status,
        get_fuel_consumption_trend,
        get_raw_sensor_history,
    )
    from models import (
        Alert,
        EfficiencyRanking,
        FleetSummary,
        HealthCheck,
        HistoricalRecord,
        KPIData,
        RefuelEvent,
        TruckDetail,
    )

# 🆕 v3.10.8: Authentication module
try:
    from .auth import (
        USERS_DB,
        Token,
        TokenData,
        User,
        UserLogin,
        authenticate_user,
        create_access_token,
        decode_token,
        filter_by_carrier,
        get_carrier_filter,
        get_current_user,
        require_admin,
        require_auth,
        require_super_admin,
    )
except ImportError:
    from auth import (
        USERS_DB,
        Token,
        TokenData,
        User,
        UserLogin,
        authenticate_user,
        create_access_token,
        decode_token,
        filter_by_carrier,
        get_carrier_filter,
        get_current_user,
        require_admin,
        require_auth,
        require_super_admin,
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

# 🔧 v6.3.1: Register Cost Analysis Router
try:
    from routers.cost_router import router as cost_router

    app.include_router(cost_router)
    logger.info("✅ Cost Analysis router registered")
except ImportError as e:
    logger.warning(f"⚠️ Cost router not available: {e}")

# 🆕 v7.0.0: Register ML/AI Router (LSTM + Isolation Forest)
try:
    from routers.ml import router as ml_router

    app.include_router(ml_router)
    logger.info("✅ Machine Learning router registered (LSTM + Theft Detection)")
except ImportError as e:
    logger.warning(f"⚠️ ML router not available: {e}")

# 🆕 DEC 24 2025: Register Truck MPG History Router
try:
    from routers.truck_mpg_history import router as mpg_history_router

    app.include_router(mpg_history_router)
    logger.info("✅ Truck MPG History router registered")
except ImportError as e:
    logger.warning(f"⚠️ MPG History router not available: {e}")

# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 FASE 2A, 2B, 2C: EXTENDED KALMAN FILTER + ML PIPELINE + EVENT-DRIVEN ARCHITECTURE
# ═══════════════════════════════════════════════════════════════════════════════

# 🆕 FASE 2A: EKF Integration & Diagnostics Endpoints
try:
    from ekf_diagnostics_endpoints import router as ekf_router
    from ekf_integration import get_ekf_manager, initialize_ekf_manager

    initialize_ekf_manager()
    app.include_router(ekf_router)
    logger.info("✅ FASE 2A: EKF Integration & Diagnostics endpoints registered")
except ImportError as e:
    logger.warning(f"⚠️ FASE 2A (EKF) not available: {e}")
except Exception as e:
    logger.warning(f"⚠️ FASE 2A initialization error: {e}")

# 🆕 FASE 2B: ML Pipeline (LSTM Predictor, Anomaly Detection, Driver Scoring)
try:
    from anomaly_detection_v2 import get_anomaly_detector
    from driver_behavior_scoring_v2 import get_behavior_scorer
    from lstm_fuel_predictor import get_lstm_predictor

    logger.info(
        "✅ FASE 2B: ML Pipeline (LSTM + Anomaly Detection + Driver Scoring) loaded"
    )
except ImportError as e:
    logger.warning(f"⚠️ FASE 2B (ML Pipeline) not available: {e}")
except Exception as e:
    logger.warning(f"⚠️ FASE 2B initialization error: {e}")

# 🆕 FASE 2C: Event-Driven Architecture (Kafka Event Bus + Microservices)
try:
    from kafka_event_bus import get_event_bus, initialize_event_bus
    from microservices_orchestrator import get_orchestrator

    initialize_event_bus()
    logger.info("✅ FASE 2C: Event Bus & Microservices Orchestrator loaded")
except ImportError as e:
    logger.warning(f"⚠️ FASE 2C (Event-Driven) not available: {e}")
except Exception as e:
    logger.warning(f"⚠️ FASE 2C initialization error: {e}")

# 🆕 FASE 2C: Route Optimization Engine
try:
    from route_optimization_engine import get_route_optimizer

    logger.info("✅ FASE 2C: Route Optimization Engine loaded")
except ImportError as e:
    logger.warning(f"⚠️ FASE 2C (Routes) not available: {e}")
except Exception as e:
    logger.warning(f"⚠️ FASE 2C Routes initialization error: {e}")

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

# CORS configuration - production-ready with environment-based origins
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,https://fuelanalytics.fleetbooster.net",
).split(",")

# In development, add local variants
if os.getenv("ENVIRONMENT", "production") == "development":
    ALLOWED_ORIGINS.extend(
        [
            "http://127.0.0.1:3000",
            "http://127.0.0.1:3001",
            "http://127.0.0.1:5173",
        ]
    )
    logger.info("🔧 Development mode: Added localhost origins")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],  # Explicit methods only
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-API-Key",
    ],  # Explicit headers only
    max_age=3600,  # Cache preflight requests for 1 hour
)
logger.info(f"✅ CORS configured with {len(ALLOWED_ORIGINS)} allowed origins")


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v4.2: INCLUDE MODULAR ROUTERS
# ═══════════════════════════════════════════════════════════════════════════════
if ROUTERS_AVAILABLE:
    try:
        include_all_routers(app, auth_dependency=require_auth)
        logger.info("✅ All routers included successfully")
    except Exception as e:
        logger.error(f"❌ Failed to include routers: {e}")

# 🆕 v3.12.21: Register API v2 Router (truck-specs and other v2 endpoints)
try:
    import os
    import sys

    # Import from routers.py file directly (not routers/ package)
    routers_module_path = os.path.join(os.path.dirname(__file__), "routers.py")
    if os.path.exists(routers_module_path):
        import importlib.util

        spec = importlib.util.spec_from_file_location("routers_v3", routers_module_path)
        routers_v3 = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(routers_v3)

        routers_v3.register_v3_12_21_routers(app)
        logger.info("✅ v3.12.21 API v2 router registered")
    else:
        logger.warning("⚠️ routers.py file not found")
except Exception as e:
    logger.warning(f"⚠️ v3.12.21 router registration skipped: {e}")

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

        # 🔍 DEBUG Dec 23: Check what's in truck_details
        if summary and "truck_details" in summary and summary["truck_details"]:
            sample_truck = summary["truck_details"][0]
            logger.warning(f"🔍 DEBUG: First truck keys: {list(sample_truck.keys())}")
            logger.warning(
                f"🔍 DEBUG: sensor_pct value: {sample_truck.get('sensor_pct')}"
            )

        return summary
    except Exception as e:
        logger.error(f"❌ Error fetching fleet summary: {e}", exc_info=True)
        # 🔧 v5.19.2: Return minimal valid response instead of 500
        return {
            "total_trucks": 0,
            "active_trucks": 0,
            "offline_trucks": 0,
            "total_fuel_consumed_gal": 0.0,
            "avg_mpg": 0.0,
            "avg_idle_consumption_gph": 0.0,
            "trucks": [],
            "data_source": "ERROR",
            "error": str(e),
        }


# 🐛 DEBUG ENDPOINT - Remove after testing
@app.get("/fuelAnalytics/api/fleet/raw")
async def get_fleet_raw():
    """DEBUG: Get raw fleet summary without response_model filtering"""
    summary = db.get_fleet_summary()
    summary["data_source"] = "MySQL" if db.mysql_available else "CSV"
    return summary


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
    🔧 FIX v6.2.2: Improved error handling to prevent 502 errors
    """
    import numpy as np
    import pandas as pd

    try:
        logger.info(f"[get_truck_detail] Fetching data for {truck_id}")
        record = None
        try:
            record = db.get_truck_latest_record(truck_id)
            logger.info(f"[get_truck_detail] Record retrieved: {record is not None}")
        except Exception as db_error:
            logger.error(f"[get_truck_detail] DB error for {truck_id}: {db_error}")
            # Continue to fallback logic

        if not record:
            # 🔧 FIX v3.10.3: Check if truck exists in tanks.yaml config
            # If it does, return a minimal "offline" record instead of 404
            import yaml

            # 🔧 FIX v3.12.4: Correct path - tanks.yaml is in same directory as main.py
            tanks_path = Path(__file__).parent / "tanks.yaml"
            logger.info(f"[get_truck_detail] Checking tanks.yaml at {tanks_path}")
            if tanks_path.exists():
                with open(tanks_path, "r", encoding="utf-8") as f:
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
                with open(tanks_path, "r", encoding="utf-8") as f:
                    tanks_config = yaml.safe_load(f)
                    trucks = tanks_config.get("trucks", {})
                    if truck_id in trucks:
                        truck_config = trucks[truck_id]
                        logger.warning(
                            f"[get_truck_detail] Returning OFFLINE status for {truck_id} due to error: {e}"
                        )
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
                            "message": f"Error loading real-time data: {str(e)[:100]}",
                            "data_available": False,
                        }
        except Exception as fallback_error:
            logger.error(f"[get_truck_detail] Fallback also failed: {fallback_error}")

        # Last resort: return minimal error response instead of 500
        logger.error(f"[get_truck_detail] All fallbacks failed for {truck_id}")
        return {
            "truck_id": truck_id,
            "status": "ERROR",
            "truck_status": "ERROR",
            "message": f"Error fetching truck data: {str(e)[:100]}",
            "data_available": False,
            "health_score": 0,
            "health_category": "error",
        }


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

    🔧 FIX v6.2.2: Never throw 500, always return valid response
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
        logger.error(
            f"❌ Error in get_truck_refuel_history for {truck_id}: {e}", exc_info=True
        )
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

    🔧 FIX v6.2.2: Never throw 500, always return empty list on error

    Returns:
        List of historical data points
    """
    try:
        records = db.get_truck_history(truck_id, hours)
        if not records:
            logger.info(f"📭 No history found for {truck_id} (last {hours} hours)")
            return []  # Return empty list instead of 404

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
        logger.error(
            f"❌ Error in get_truck_history for {truck_id}: {e}", exc_info=True
        )
        return []  # Return empty list instead of 500


# ============================================================================
# V2 API ALIASES (for frontend compatibility)
# ============================================================================


@app.get("/fuelAnalytics/api/v2/trucks/{truck_id}", tags=["Trucks v2"])
async def get_truck_detail_v2(truck_id: str):
    """V2 API alias for get_truck_detail"""
    return await get_truck_detail(truck_id)


@app.get(
    "/fuelAnalytics/api/v2/trucks/{truck_id}/history",
    response_model=List[HistoricalRecord],
    tags=["Trucks v2"],
)
async def get_truck_history_v2(
    truck_id: str,
    hours: int = Query(
        24, ge=1, le=168, description="Hours of history to fetch (1-168)"
    ),
):
    """V2 API alias for get_truck_history"""
    return await get_truck_history(truck_id, hours)


@app.get("/fuelAnalytics/api/v2/trucks/{truck_id}/refuels", tags=["Trucks v2"])
async def get_truck_refuels_v2(
    truck_id: str,
    days: int = Query(
        30, ge=1, le=90, description="Days of refuel history to fetch (1-90)"
    ),
):
    """V2 API alias for get_truck_refuel_history"""
    return await get_truck_refuel_history(truck_id, days)


@app.get("/fuelAnalytics/api/v2/trucks/{truck_id}/sensors", tags=["Trucks v2"])
async def get_truck_sensors_v2(truck_id: str):
    """
    V2 API endpoint for truck sensor data.

    Returns real-time sensor data including:
    - Fuel level, RPM, speed, odometer
    - Engine sensors (coolant temp, oil pressure, etc.)
    - GPS location and status

    🔧 FIX v6.2.3: Use fuel_metrics instead of non-existent truck_sensors_cache
    """
    try:
        import pymysql

        from database_mysql import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get latest data from fuel_metrics
        cursor.execute(
            """
            SELECT 
                timestamp_utc,
                speed_mph,
                rpm,
                estimated_gallons,
                estimated_pct,
                sensor_pct,
                consumption_gph,
                mpg_current,
                engine_hours,
                odometer_mi,
                idle_gph,
                idle_mode,
                coolant_temp_f,
                oil_pressure_psi,
                oil_temp_f,
                battery_voltage,
                engine_load_pct,
                def_level_pct,
                ambient_temp_f,
                intake_air_temp_f,
                trans_temp_f,
                fuel_temp_f,
                altitude_ft,
                latitude,
                longitude,
                truck_status
            FROM fuel_metrics
            WHERE truck_id = %s
            ORDER BY timestamp_utc DESC
            LIMIT 1
        """,
            (truck_id,),
        )

        sensor_data = cursor.fetchone()
        cursor.close()
        conn.close()

        if not sensor_data:
            logger.info(f"📭 No sensor data found for {truck_id}")
            return {
                "truck_id": truck_id,
                "timestamp": None,
                "sensors": {},
                "message": "No recent sensor data available",
            }

        return {
            "truck_id": truck_id,
            "timestamp": sensor_data.get("timestamp_utc"),
            "sensors": {
                k: v
                for k, v in sensor_data.items()
                if k not in ["timestamp_utc"] and v is not None
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error fetching sensors for {truck_id}: {e}", exc_info=True)
        # Return empty sensors instead of 500
        return {
            "truck_id": truck_id,
            "timestamp": None,
            "sensors": {},
            "error": str(e)[:100],
        }


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
# BENCHMARKING ENGINE 🆕 v4.1.0
# ============================================================================


@app.get("/fuelAnalytics/api/benchmark/{truck_id}/mpg", tags=["Benchmarking"])
async def benchmark_truck_mpg(
    truck_id: str,
    period_days: int = Query(30, ge=7, le=90, description="Days to analyze (7-90)"),
):
    """
    🆕 v4.1.0: Benchmark truck MPG against peer group

    Compares truck MPG performance to similar trucks (same make/model/year):
    - Actual MPG vs peer median
    - Percentile ranking (0-100%)
    - Performance tier (TOP_10, TOP_25, AVERAGE, BELOW_AVERAGE, BOTTOM_25)
    - Deviation from benchmark
    - Confidence score based on peer count

    Args:
        truck_id: Truck identifier
        period_days: Analysis period (default 30 days)

    Returns:
        Benchmark result with peer comparison
    """
    try:
        from benchmarking_engine import get_benchmarking_engine

        engine = get_benchmarking_engine()
        result = engine.benchmark_metric(truck_id, "mpg", period_days=period_days)

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Insufficient data to benchmark {truck_id} (need peers or data)",
            )

        return result.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error benchmarking MPG for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Benchmarking error: {str(e)}")


@app.get("/fuelAnalytics/api/benchmark/{truck_id}/idle", tags=["Benchmarking"])
async def benchmark_truck_idle(
    truck_id: str,
    period_days: int = Query(30, ge=7, le=90, description="Days to analyze (7-90)"),
):
    """
    🆕 v4.1.0: Benchmark truck idle time against peer group

    Compares idle time percentage to similar trucks.
    Lower idle time is better (reversed percentile).

    Args:
        truck_id: Truck identifier
        period_days: Analysis period

    Returns:
        Benchmark result with peer comparison
    """
    try:
        from benchmarking_engine import get_benchmarking_engine

        engine = get_benchmarking_engine()
        result = engine.benchmark_metric(
            truck_id, "idle_time_pct", period_days=period_days
        )

        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Insufficient data to benchmark {truck_id}"
            )

        return result.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error benchmarking idle time for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Benchmarking error: {str(e)}")


@app.get("/fuelAnalytics/api/benchmark/{truck_id}/cost", tags=["Benchmarking"])
async def benchmark_truck_cost(
    truck_id: str,
    period_days: int = Query(30, ge=7, le=90, description="Days to analyze (7-90)"),
):
    """
    🆕 v4.1.0: Benchmark truck cost per mile against peer group

    Compares cost per mile to similar trucks.
    Lower cost is better (reversed percentile).

    Args:
        truck_id: Truck identifier
        period_days: Analysis period

    Returns:
        Benchmark result with peer comparison
    """
    try:
        from benchmarking_engine import get_benchmarking_engine

        engine = get_benchmarking_engine()
        result = engine.benchmark_metric(
            truck_id, "cost_per_mile", period_days=period_days
        )

        if result is None:
            raise HTTPException(
                status_code=404, detail=f"Insufficient data to benchmark {truck_id}"
            )

        return result.to_dict()

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error benchmarking cost for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Benchmarking error: {str(e)}")


@app.get("/fuelAnalytics/api/benchmark/{truck_id}", tags=["Benchmarking"])
async def benchmark_truck_all(
    truck_id: str,
    period_days: int = Query(30, ge=7, le=90, description="Days to analyze (7-90)"),
):
    """
    🆕 v4.1.0: Benchmark all metrics for a truck

    Returns comprehensive benchmarking across:
    - MPG (fuel efficiency)
    - Idle time percentage
    - Cost per mile

    Args:
        truck_id: Truck identifier
        period_days: Analysis period

    Returns:
        Dict with all benchmark results
    """
    try:
        from benchmarking_engine import get_benchmarking_engine

        engine = get_benchmarking_engine()
        results = engine.benchmark_truck(truck_id, period_days=period_days)

        if not results:
            raise HTTPException(
                status_code=404, detail=f"No benchmarking data available for {truck_id}"
            )

        return {metric: result.to_dict() for metric, result in results.items()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error benchmarking {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Benchmarking error: {str(e)}")


@app.get("/fuelAnalytics/api/benchmark/fleet/outliers", tags=["Benchmarking"])
async def get_fleet_outliers(
    metric: str = Query("mpg", regex="^(mpg|idle_time_pct|cost_per_mile)$"),
    period_days: int = Query(30, ge=7, le=90),
    threshold: float = Query(10.0, ge=1.0, le=50.0, description="Percentile threshold"),
):
    """
    🆕 v4.1.0: Identify fleet outliers (poor performers)

    Finds trucks performing significantly worse than their peers.

    Args:
        metric: Metric to analyze (mpg, idle_time_pct, cost_per_mile)
        period_days: Analysis period
        threshold: Percentile threshold (default 10% = bottom 10%)

    Returns:
        List of underperforming trucks with benchmark data
    """
    try:
        from benchmarking_engine import get_benchmarking_engine

        engine = get_benchmarking_engine()
        outliers = engine.get_fleet_outliers(
            metric_name=metric, period_days=period_days, threshold_percentile=threshold
        )

        return {
            "metric": metric,
            "period_days": period_days,
            "threshold_percentile": threshold,
            "outlier_count": len(outliers),
            "outliers": [o.to_dict() for o in outliers],
        }

    except Exception as e:
        logger.error(f"Error finding fleet outliers: {e}")
        raise HTTPException(status_code=500, detail=f"Benchmarking error: {str(e)}")


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
        "ml",
        description="Algorithm version: 'ml' (Random Forest ML), 'advanced' (v4.1 with trip correlation) or 'legacy' (v3.x)",
    ),
):
    """
    🛡️ v5.0.0: ML-POWERED Fuel Theft Detection & Analysis

    Sophisticated multi-signal theft detection with three algorithms:

    1. 'ml' (NEW - Default): Random Forest machine learning model
       - 8 features: fuel_drop, speed, location, time, sensor quality, etc.
       - Trained on historical patterns
       - Confidence scores with feature importance
       - Best accuracy for complex scenarios

    2. 'advanced': v4.1 algorithm with Wialon trip correlation
       - Fuel level analysis (drops, recovery patterns)
       - Trip/movement correlation from Wialon
       - Time pattern analysis (night, weekends)
       - Sensor health scoring

    3. 'legacy': Previous v3.x algorithm for comparison

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

        if algorithm == "ml":
            # 🆕 DEC 23: Use ML-based theft detection
            try:
                from datetime import timedelta

                import pymysql

                from database_mysql import get_db_connection
                from theft_detection_ml import TheftDetectionML

                ml_detector = TheftDetectionML()
                conn = get_db_connection()
                cursor = conn.cursor(pymysql.cursors.DictCursor)

                # Get fuel drops in the period
                start_date = datetime.now(timezone.utc) - timedelta(days=days)
                cursor.execute(
                    """
                    SELECT 
                        fm1.truck_id,
                        fm1.timestamp_utc,
                        fm1.sensor_pct as fuel_before,
                        fm2.sensor_pct as fuel_after,
                        (fm1.sensor_pct - fm2.sensor_pct) as fuel_drop_pct,
                        fm1.latitude,
                        fm1.longitude,
                        fm1.speed_mph,
                        fm1.truck_status,
                        fm1.drift_pct,
                        HOUR(fm1.timestamp_utc) as hour_of_day
                    FROM fuel_metrics fm1
                    INNER JOIN fuel_metrics fm2 
                        ON fm1.truck_id = fm2.truck_id 
                        AND fm2.timestamp_utc = (
                            SELECT MIN(timestamp_utc) 
                            FROM fuel_metrics 
                            WHERE truck_id = fm1.truck_id 
                            AND timestamp_utc > fm1.timestamp_utc
                        )
                    WHERE fm1.timestamp_utc >= %s
                        AND (fm1.sensor_pct - fm2.sensor_pct) > 3.0
                    ORDER BY fm1.timestamp_utc DESC
                    LIMIT 1000
                """,
                    (start_date,),
                )

                fuel_drops = cursor.fetchall()
                cursor.close()
                conn.close()

                # Run ML prediction on each drop
                theft_events = []
                for drop in fuel_drops:
                    prediction = ml_detector.predict_theft(
                        fuel_drop_pct=drop["fuel_drop_pct"],
                        speed=drop["speed_mph"] or 0,
                        is_moving=(drop["truck_status"] == "MOVING"),
                        latitude=drop["latitude"],
                        longitude=drop["longitude"],
                        hour_of_day=drop["hour_of_day"],
                        is_weekend=start_date.weekday() >= 5,
                        sensor_drift=abs(drop["drift_pct"]) if drop["drift_pct"] else 0,
                    )

                    if prediction.is_theft:
                        theft_events.append(
                            {
                                "truck_id": drop["truck_id"],
                                "timestamp": drop["timestamp_utc"].isoformat(),
                                "fuel_drop_pct": round(drop["fuel_drop_pct"], 2),
                                "fuel_drop_gal": round(
                                    drop["fuel_drop_pct"] * 1.5, 2
                                ),  # Approx 150gal tank
                                "confidence": round(prediction.confidence * 100, 1),
                                "classification": (
                                    "ROBO CONFIRMADO"
                                    if prediction.confidence > 0.85
                                    else "ROBO SOSPECHOSO"
                                ),
                                "algorithm": "Random Forest ML",
                                "feature_importance": prediction.feature_importance,
                                "location": (
                                    f"{drop['latitude']:.6f},{drop['longitude']:.6f}"
                                    if drop["latitude"]
                                    else None
                                ),
                                "speed_mph": drop["speed_mph"],
                                "status": drop["truck_status"],
                            }
                        )

                analysis = {
                    "period_days": days,
                    "algorithm": "ml",
                    "total_events": len(theft_events),
                    "confirmed_thefts": len(
                        [
                            e
                            for e in theft_events
                            if e["classification"] == "ROBO CONFIRMADO"
                        ]
                    ),
                    "suspected_thefts": len(
                        [
                            e
                            for e in theft_events
                            if e["classification"] == "ROBO SOSPECHOSO"
                        ]
                    ),
                    "total_fuel_lost_gal": sum(
                        e["fuel_drop_gal"] for e in theft_events
                    ),
                    "events": theft_events,
                    "model_info": {
                        "type": "Random Forest",
                        "features": 8,
                        "training_samples": 200,
                        "accuracy": "~95% (synthetic data)",
                    },
                }

            except Exception as e:
                logger.warning(f"ML algorithm failed, falling back to advanced: {e}")
                # Fallback to advanced
                from theft_detection_engine import analyze_fuel_drops_advanced

                analysis = analyze_fuel_drops_advanced(days_back=days)

        elif algorithm == "advanced":
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


@app.get("/fuelAnalytics/api/predictive-maintenance", tags=["Maintenance"])
async def get_predictive_maintenance(
    truck_id: Optional[str] = Query(None, description="Filter by specific truck"),
    component: Optional[str] = Query(
        None,
        description="Filter by component: turbocharger, oil_pump, coolant_pump, fuel_pump, def_pump",
    ),
):
    """
    🔧 v5.0.0: PREDICTIVE MAINTENANCE - Ensemble Model (Weibull + ARIMA)

    Predicts component failures using hybrid statistical approach:
    - Weibull distribution: Age-based failure probability (mechanical wear)
    - ARIMA time series: Sensor trend analysis (degradation patterns)
    - Weighted ensemble: Combines both models (60% Weibull, 40% ARIMA)

    Monitored Components:
    - turbocharger: Intake pressure trends, boost monitoring
    - oil_pump: Oil pressure degradation, temperature patterns
    - coolant_pump: Coolant temp trends, circulation efficiency
    - fuel_pump: Fuel pressure stability (when sensor available)
    - def_pump: DEF level patterns, dosing efficiency

    Returns:
    - Time-to-failure predictions (hours)
    - Confidence intervals (90%, 95%, 99%)
    - Alert severity (OK, WARNING, CRITICAL)
    - Recommended maintenance actions
    - Sensor health indicators
    """
    try:
        from cache_service import get_cache

        cache = await get_cache()
        cache_key = f"maintenance:predict:{truck_id or 'all'}:{component or 'all'}"
        cached = await cache.get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        import numpy as np
        import pymysql

        from database_mysql import get_db_connection
        from predictive_maintenance_config import (
            CRITICAL_COMPONENTS,
            get_all_component_names,
            should_alert,
        )
        from predictive_maintenance_ensemble import PredictiveMaintenanceEnsemble

        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Get list of trucks to analyze
        if truck_id:
            trucks = [truck_id]
        else:
            cursor.execute(
                "SELECT DISTINCT truck_id FROM fuel_metrics WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)"
            )
            trucks = [row["truck_id"] for row in cursor.fetchall()]

        # Get components to analyze
        components_to_check = [component] if component else get_all_component_names()

        predictions = []

        for truck in trucks:
            for comp_name in components_to_check:
                try:
                    comp_config = CRITICAL_COMPONENTS[comp_name]
                    sensor_name = comp_config["sensors"]["primary"]

                    # Get sensor history (last 30 days)
                    cursor.execute(
                        f"""
                        SELECT 
                            timestamp_utc,
                            engine_hours,
                            {sensor_name}
                        FROM fuel_metrics
                        WHERE truck_id = %s
                            AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                            AND {sensor_name} IS NOT NULL
                        ORDER BY timestamp_utc ASC
                        LIMIT 1000
                    """,
                        (truck,),
                    )

                    sensor_data = cursor.fetchall()

                    if len(sensor_data) < 10:
                        # Not enough data
                        continue

                    # Extract sensor values and engine hours
                    sensor_values = [row[sensor_name] for row in sensor_data]
                    engine_hours_list = [
                        row["engine_hours"]
                        for row in sensor_data
                        if row["engine_hours"]
                    ]

                    current_engine_hours = (
                        engine_hours_list[-1] if engine_hours_list else 5000
                    )

                    # Create ensemble model
                    ensemble = PredictiveMaintenanceEnsemble(
                        component_name=comp_name,
                        weibull_shape=comp_config["weibull_params"]["shape"],
                        weibull_scale=comp_config["weibull_params"]["scale"],
                        arima_order=comp_config["arima_order"],
                        ensemble_weight_weibull=comp_config["ensemble_weight_weibull"],
                        ensemble_weight_arima=comp_config["ensemble_weight_arima"],
                    )

                    # Train models
                    ensemble.train_models(
                        sensor_history=sensor_values,
                        current_age_hours=current_engine_hours,
                    )

                    # Predict
                    prediction = ensemble.predict(
                        current_age_hours=current_engine_hours,
                        forecast_steps=30,  # 30 time steps ahead
                    )

                    # Check if alert needed
                    should_send_alert, severity = should_alert(
                        comp_name, prediction.ttf_hours
                    )

                    # Calculate days until failure
                    avg_hours_per_day = 8  # Assume 8 hours driving per day
                    days_until_failure = prediction.ttf_hours / avg_hours_per_day

                    predictions.append(
                        {
                            "truck_id": truck,
                            "component": comp_name,
                            "component_description": comp_config["description"],
                            "ttf_hours": round(prediction.ttf_hours, 1),
                            "ttf_days": round(days_until_failure, 1),
                            "confidence_90": [
                                round(prediction.confidence_intervals["90%"][0], 1),
                                round(prediction.confidence_intervals["90%"][1], 1),
                            ],
                            "confidence_95": [
                                round(prediction.confidence_intervals["95%"][0], 1),
                                round(prediction.confidence_intervals["95%"][1], 1),
                            ],
                            "weibull_contribution": round(
                                prediction.weibull_prediction, 1
                            ),
                            "arima_contribution": round(prediction.arima_prediction, 1),
                            "sensor_monitored": sensor_name,
                            "current_sensor_value": round(sensor_values[-1], 2),
                            "sensor_trend": prediction.metadata.get(
                                "sensor_trend", "stable"
                            ),
                            "alert_severity": severity,
                            "should_alert": should_send_alert,
                            "maintenance_due_hours": comp_config[
                                "maintenance_interval_hours"
                            ],
                            "current_engine_hours": round(current_engine_hours, 1),
                            "recommended_action": (
                                f"URGENT: Schedule maintenance within {int(days_until_failure)} days"
                                if severity == "CRITICAL"
                                else (
                                    f"Plan maintenance in next {int(days_until_failure)} days"
                                    if severity == "WARNING"
                                    else "Component healthy, monitor trends"
                                )
                            ),
                        }
                    )

                except Exception as comp_error:
                    logger.warning(
                        f"Error analyzing {comp_name} for {truck}: {comp_error}"
                    )
                    continue

        cursor.close()
        conn.close()

        # Aggregate stats
        critical_count = len(
            [p for p in predictions if p["alert_severity"] == "CRITICAL"]
        )
        warning_count = len(
            [p for p in predictions if p["alert_severity"] == "WARNING"]
        )

        result = {
            "total_predictions": len(predictions),
            "trucks_analyzed": len(trucks),
            "components_analyzed": len(components_to_check),
            "critical_alerts": critical_count,
            "warning_alerts": warning_count,
            "predictions": sorted(
                predictions, key=lambda x: x["ttf_hours"]
            ),  # Sort by urgency
            "model_info": {
                "type": "Weibull + ARIMA Ensemble",
                "weibull_purpose": "Age-based mechanical failure probability",
                "arima_purpose": "Sensor degradation trend analysis",
                "ensemble_method": "Weighted average (configurable per component)",
            },
        }

        # Cache for 5 minutes (predictions don't change frequently)
        await cache.set(cache_key, result, ttl=300)

        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"❌ Error in predictive maintenance: {e}", exc_info=True)
        # 🔧 v5.19.2: Return empty response instead of 500 error
        # This prevents frontend from breaking when predictive model has issues
        # (e.g., missing dependencies, insufficient data, etc.)
        return JSONResponse(
            content={
                "total_predictions": 0,
                "trucks_analyzed": 0,
                "components_analyzed": 0,
                "critical_alerts": 0,
                "warning_alerts": 0,
                "predictions": [],
                "error": str(e),
                "status": "unavailable",
                "message": "Predictive maintenance temporarily unavailable. Check logs for details.",
            }
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


@app.get("/fuelAnalytics/api/truck-costs", tags=["Cost Analysis"])
async def get_truck_costs(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze")
):
    """
    🆕 DEC 25 2025: Get per-truck cost breakdown with real data

    Returns actual cost data for each truck including:
    - Total miles driven
    - Fuel consumed (gallons)
    - Fuel cost (USD)
    - Maintenance cost estimate
    - Cost per mile

    Args:
        days: Analysis period (1-90 days)

    Returns:
        List of truck cost data with real metrics
    """
    try:
        import pandas as pd

        from database_mysql import get_sqlalchemy_engine

        engine = get_sqlalchemy_engine()

        # Get per-truck aggregated data from fuel_metrics table
        # Calculate total miles from odometer deltas and total fuel from consumption
        query = """
        SELECT 
            truck_id,
            SUM(odom_delta_mi) as total_miles,
            SUM(consumption_gph * (odom_delta_mi / NULLIF(speed_mph, 0))) as total_fuel_gal,
            AVG(cost_per_mile) as avg_cost_per_mile
        FROM fuel_metrics
        WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL %s DAY)
          AND odom_delta_mi > 0
          AND consumption_gph > 0
          AND speed_mph > 0
        GROUP BY truck_id
        HAVING total_miles > 0
        ORDER BY total_miles DESC
        """

        df = pd.read_sql(query, engine, params=(days,))

        if df.empty:
            return []

        # Replace NaN with 0 for calculations
        df = df.fillna(0)

        # Calculate fuel cost (assume $3.50/gal average diesel price)
        DIESEL_PRICE_PER_GAL = 3.50
        df["total_fuel_cost"] = df["total_fuel_gal"] * DIESEL_PRICE_PER_GAL

        # Calculate maintenance cost (typically 18% of fuel cost)
        df["maintenance_cost"] = df["total_fuel_cost"] * 0.18

        # Calculate actual cost per mile if not available
        df["cost_per_mile"] = df.apply(
            lambda row: (
                row["avg_cost_per_mile"]
                if pd.notna(row["avg_cost_per_mile"]) and row["avg_cost_per_mile"] > 0
                else (
                    (row["total_fuel_cost"] + row["maintenance_cost"])
                    / row["total_miles"]
                    if row["total_miles"] > 0
                    else 0
                )
            ),
            axis=1,
        )

        # Format result
        truck_costs = []
        for _, row in df.iterrows():
            truck_costs.append(
                {
                    "truckId": row["truck_id"],
                    "totalMiles": round(row["total_miles"], 1),
                    "fuelConsumedGal": round(row["total_fuel_gal"], 2),
                    "fuelCost": round(row["total_fuel_cost"], 2),
                    "maintenanceCost": round(row["maintenance_cost"], 2),
                    "costPerMile": round(row["cost_per_mile"], 3),
                    "totalCost": round(
                        row["total_fuel_cost"] + row["maintenance_cost"], 2
                    ),
                }
            )

        logger.info(f"✅ Returned {len(truck_costs)} trucks with cost data ({days}d)")
        return truck_costs

    except Exception as e:
        logger.error(f"Error fetching truck costs: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching truck costs: {str(e)}"
        )


@app.get("/fuelAnalytics/api/truck-utilization", tags=["Utilization"])
async def get_truck_utilization(
    days: int = Query(7, ge=1, le=90, description="Number of days to analyze")
):
    """
    🆕 DEC 25 2025: Get per-truck utilization with real hours data

    Returns actual utilization data for each truck including:
    - Active hours (MOVING status)
    - Idle hours (STOPPED status with engine on)
    - Parked hours (remaining time)
    - Utilization percentage

    Args:
        days: Analysis period (1-90 days)

    Returns:
        List of truck utilization data with real metrics
    """
    try:
        import pandas as pd

        from database_mysql import get_sqlalchemy_engine

        engine = get_sqlalchemy_engine()

        # Get per-truck time distribution from fuel_metrics
        # Each record ≈ 1 minute, so count records by status
        query = """
        SELECT 
            truck_id,
            SUM(CASE WHEN truck_status = 'MOVING' THEN 1 ELSE 0 END) as moving_records,
            SUM(CASE WHEN truck_status = 'STOPPED' THEN 1 ELSE 0 END) as stopped_records,
            COUNT(*) as total_records
        FROM fuel_metrics
        WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL %s DAY)
        GROUP BY truck_id
        HAVING total_records > 10
        ORDER BY total_records DESC
        """

        df = pd.read_sql(query, engine, params=(days,))

        if df.empty:
            return []

        # Convert records to hours (each record ≈ 1 minute)
        RECORD_INTERVAL_HOURS = 1 / 60
        total_hours_period = days * 24

        truck_utilization = []
        for _, row in df.iterrows():
            active_hours = round(row["moving_records"] * RECORD_INTERVAL_HOURS, 1)
            idle_hours = round(row["stopped_records"] * RECORD_INTERVAL_HOURS, 1)
            parked_hours = round(
                max(0, total_hours_period - active_hours - idle_hours), 1
            )

            # Utilization = (active + idle) / total * 100
            utilization_pct = round(
                (
                    ((active_hours + idle_hours) / total_hours_period * 100)
                    if total_hours_period > 0
                    else 0
                ),
                1,
            )

            truck_utilization.append(
                {
                    "truckId": row["truck_id"],
                    "activeHours": active_hours,
                    "idleHours": idle_hours,
                    "parkedHours": parked_hours,
                    "utilizationPct": utilization_pct,
                }
            )

        logger.info(
            f"✅ Returned {len(truck_utilization)} trucks with utilization data ({days}d)"
        )
        return truck_utilization

    except Exception as e:
        logger.error(f"Error fetching truck utilization: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching truck utilization: {str(e)}"
        )


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
    days: int = Query(default=7, ge=1, le=30, description="Days to analyze"),
    include_tips: bool = Query(default=True, description="Include coaching tips"),
    include_history: bool = Query(default=False, description="Include score history"),
    language: str = Query(default="en", description="Language for tips: en or es"),
):
    """
    🆕 v3.10.0: Comprehensive Driver Scorecard System
    🆕 v3.11.0: Added coaching_tips and score_history

    Returns multi-dimensional driver scores based on:
    - Speed Optimization (55-65 mph optimal)
    - RPM Discipline (1200-1600 optimal)
    - Idle Management (vs fleet average)
    - Fuel Consistency (consumption variability)
    - MPG Performance (vs 5.7 baseline)

    New in v3.11.0:
    - coaching_tips: Personalized tips per driver (bilingual)
    - score_history: Historical trend for each driver
    - trend_analysis: Is the driver improving?

    Returns:
        Driver rankings with overall score, grade (A+/A/B/C/D), breakdown, tips, and history
    """
    try:
        from database_mysql import (
            get_driver_score_history,
            get_driver_score_trend,
            get_driver_scorecard,
        )
        from driver_behavior_engine import generate_coaching_tips

        result = get_driver_scorecard(days_back=days)

        # Enhance each driver with tips and history
        if result.get("drivers"):
            for driver in result["drivers"]:
                # Add personalized coaching tips
                if include_tips:
                    driver["coaching_tips"] = generate_coaching_tips(
                        driver_data=driver,
                        language=language,
                        max_tips=5,
                    )

                # Add score history and trend
                if include_history:
                    truck_id = driver.get("truck_id")
                    driver["score_history"] = get_driver_score_history(
                        truck_id, days_back=30
                    )
                    driver["trend_analysis"] = get_driver_score_trend(
                        truck_id, days_back=30
                    )

        return result

    except Exception as e:
        logger.error(f"Error in driver scorecard: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error in driver scorecard: {str(e)}"
        )


@app.get("/fuelAnalytics/api/analytics/driver/{truck_id}/history")
async def get_driver_history_endpoint(
    truck_id: str,
    days: int = Query(default=30, ge=1, le=90, description="Days of history"),
):
    """
    🆕 v3.11.0: Get historical score data for a specific driver/truck

    Returns:
        List of historical scores and trend analysis
    """
    try:
        from database_mysql import get_driver_score_history, get_driver_score_trend

        history = get_driver_score_history(truck_id, days_back=days)
        trend = get_driver_score_trend(truck_id, days_back=days)

        return {
            "truck_id": truck_id,
            "period_days": days,
            "history": history,
            "trend_analysis": trend,
        }
    except Exception as e:
        logger.error(f"Error getting driver history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/fuelAnalytics/api/analytics/driver-scores/snapshot")
async def save_driver_scores_snapshot():
    """
    🆕 v3.11.0: Save current driver scores to history table

    Should be called daily (via cron) to build trend data.

    Returns:
        Number of records saved
    """
    try:
        from database_mysql import get_driver_scorecard, save_driver_score_history

        # Get current scores
        result = get_driver_scorecard(days_back=1)
        drivers = result.get("drivers", [])

        # Save to history
        saved = save_driver_score_history(drivers)

        return {
            "success": True,
            "records_saved": saved,
            "message": f"Saved {saved} driver score snapshots",
        }
    except Exception as e:
        logger.error(f"Error saving driver scores snapshot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/fuelAnalytics/api/analytics/mpg-contextualized")
async def get_contextualized_mpg_endpoint(
    days: int = Query(default=1, ge=1, le=30, description="Days to analyze"),
    include_fleet_terrain: bool = Query(
        default=True, description="Include fleet terrain summary"
    ),
):
    """
    🆕 v3.11.0: Contextualized MPG Analysis with Terrain Factors

    This endpoint answers: "Is my truck performing well GIVEN THE CONDITIONS?"

    MPG can look low but actually be excellent if:
    - Truck is climbing mountains (terrain_factor > 1.0)
    - Weather is harsh (headwinds, cold)
    - Fully loaded cargo

    Returns for each truck:
    - raw_mpg: Actual measured MPG
    - adjusted_mpg: What MPG would be in ideal conditions
    - expected_mpg: What we expect given current conditions
    - performance_vs_expected_pct: How truck performs vs expectation
    - rating: EXCELLENT/GOOD/NEEDS_ATTENTION/CRITICAL

    Example response:
        {
            "truck_id": "T101",
            "raw_mpg": 5.0,
            "adjusted_mpg": 5.78,
            "expected_mpg": 5.19,
            "performance_vs_expected_pct": -3.7,
            "rating": "GOOD",
            "message": "Performing as expected",
            "factors": {"terrain": 1.10, "weather": 1.0, "load": 1.05}
        }
    """
    try:
        from database_mysql import get_kpi_summary
        from terrain_factor import get_fleet_summary as get_terrain_fleet_summary
        from terrain_factor import get_terrain_manager, get_truck_contextualized_mpg

        # Get current MPG data for all trucks
        kpi_data = get_kpi_summary(days_back=days)

        results = {
            "period_days": days,
            "trucks": [],
            "fleet_summary": {},
            "terrain_summary": {},
        }

        # Get terrain manager for fleet-wide data
        terrain_manager = get_terrain_manager()

        # Process each truck
        trucks_data = kpi_data.get("trucks", [])
        for truck in trucks_data:
            truck_id = truck.get("truck_id")
            raw_mpg = truck.get("avg_mpg", 0)
            baseline_mpg = truck.get("baseline_mpg", 5.7)

            # Get tracker data if available
            tracker = terrain_manager.trackers.get(truck_id)
            altitude = None
            latitude = None
            longitude = None
            speed = None

            if tracker and tracker.current_altitude is not None:
                altitude = tracker.current_altitude
                latitude = getattr(tracker, "latitude", None)
                longitude = getattr(tracker, "longitude", None)
                speed = getattr(tracker, "current_speed", None)

            # Calculate contextualized MPG
            if raw_mpg > 0:
                mpg_analysis = get_truck_contextualized_mpg(
                    truck_id=truck_id,
                    raw_mpg=raw_mpg,
                    altitude=altitude,
                    latitude=latitude,
                    longitude=longitude,
                    speed=speed,
                    baseline_mpg=baseline_mpg,
                )
                mpg_analysis["truck_id"] = truck_id
                mpg_analysis["truck_name"] = truck.get("truck_name", truck_id)
                results["trucks"].append(mpg_analysis)

        # Fleet summary statistics
        if results["trucks"]:
            ratings = [t["rating"] for t in results["trucks"]]
            performances = [t["performance_vs_expected_pct"] for t in results["trucks"]]

            results["fleet_summary"] = {
                "total_trucks": len(results["trucks"]),
                "excellent_count": ratings.count("EXCELLENT"),
                "good_count": ratings.count("GOOD"),
                "needs_attention_count": ratings.count("NEEDS_ATTENTION"),
                "critical_count": ratings.count("CRITICAL"),
                "avg_performance_vs_expected": round(
                    sum(performances) / len(performances), 1
                ),
                "best_performer": max(
                    results["trucks"], key=lambda x: x["performance_vs_expected_pct"]
                )["truck_id"],
                "worst_performer": min(
                    results["trucks"], key=lambda x: x["performance_vs_expected_pct"]
                )["truck_id"],
            }

        # Terrain summary if requested
        if include_fleet_terrain:
            try:
                results["terrain_summary"] = get_terrain_fleet_summary()
            except Exception as e:
                logger.warning(f"Could not get terrain summary: {e}")
                results["terrain_summary"] = {"error": str(e)}

        return results

    except Exception as e:
        logger.error(f"Error in contextualized MPG: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error in contextualized MPG: {str(e)}"
        )


@app.get("/fuelAnalytics/api/analytics/truck/{truck_id}/mpg-context")
async def get_truck_mpg_context(
    truck_id: str,
    raw_mpg: float = Query(..., description="Current raw MPG reading"),
    altitude: Optional[float] = Query(None, description="Current altitude (ft)"),
    latitude: Optional[float] = Query(None, description="GPS latitude"),
    longitude: Optional[float] = Query(None, description="GPS longitude"),
    speed: Optional[float] = Query(None, description="Current speed (mph)"),
    baseline_mpg: float = Query(5.7, description="Truck's baseline MPG"),
):
    """
    🆕 v3.11.0: Get contextualized MPG for a specific truck with live data

    Use this for real-time MPG evaluation when you have live GPS/altitude data.

    Returns:
        Contextualized analysis showing if truck is performing well for conditions
    """
    try:
        from terrain_factor import get_truck_contextualized_mpg

        result = get_truck_contextualized_mpg(
            truck_id=truck_id,
            raw_mpg=raw_mpg,
            altitude=altitude,
            latitude=latitude,
            longitude=longitude,
            speed=speed,
            baseline_mpg=baseline_mpg,
        )
        result["truck_id"] = truck_id

        return result

    except Exception as e:
        logger.error(f"Error in truck MPG context: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
    🆕 v6.4.0: Enhanced Loss Analysis V2 with ROI & Actionable Insights

    Major improvements:
    - 4-tier severity classification (CRITICAL/HIGH/MEDIUM/LOW)
    - Actionable insights with detailed ROI calculations
    - Implementation cost estimates & payback periods
    - Priority scoring for action items
    - Quick wins identification (high impact, low effort)
    - Annual savings potential with confidence intervals

    Provides detailed breakdown of fuel losses by category:
    1. EXCESSIVE IDLE: truck_status='STOPPED' with engine running (~40%)
    2. HIGH RPM: RPM > 1800 causing ~15% extra fuel consumption (~20%)
    3. SPEEDING: Speed > 70 mph causing ~12% extra fuel consumption (~20%)
    4. HIGH ALTITUDE: Altitude > 3000 ft affecting efficiency (~10%)
    5. MECHANICAL/OTHER: Remaining efficiency losses (~10%)

    Returns:
        Comprehensive loss analysis with ROI insights and action recommendations
    """
    try:
        from database_mysql import get_loss_analysis_v2

        result = get_loss_analysis_v2(days_back=days)
        return result

    except Exception as e:
        logger.error(f"Error in enhanced loss analysis v2: {e}")
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
        from sqlalchemy import text

        from database_mysql import get_sqlalchemy_engine

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


# [CLEANED 2025-12-25] Removed 83 lines of migrated code

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
        from sqlalchemy import text

        from database_mysql import get_sqlalchemy_engine

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
        from routers.alerts_router import DIAGNOSTICS_AVAILABLE, get_diagnostic_alerts

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
                    DIAGNOSTICS_AVAILABLE,
                    get_diagnostic_alerts,
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


# [CLEANED 2025-12-25] Removed 109 lines of migrated code

# Query using fuel_metrics table (which exists)
# Get latest data for each truck
# [CLEANED 2025-12-25] Removed 155 lines of migrated code

# Estimate tank capacity (assume 200 gal for now, could be from trucks table)
# [CLEANED 2025-12-25] Removed 157 lines of migrated code

# Current gallons
# [CLEANED 2025-12-25] Removed 159 lines of migrated code

# Gallons until low fuel (assume 15% threshold)
# [CLEANED 2025-12-25] Removed 169 lines of migrated code

# Calculate based on moving vs idle
# [CLEANED 2025-12-25] Removed 174 lines of migrated code

# Weighted average assuming 70% moving, 30% idle
# [CLEANED 2025-12-25] Removed 222 lines of migrated code

# Sort by urgency (critical first)
# [CLEANED 2025-12-25] Removed 245 lines of migrated code

# ============================================================================
# 🆕 FASE 2: EXPORT TO EXCEL/CSV v3.12.21
# ============================================================================


# [CLEANED 2025-12-25] Removed 266 lines of migrated code

# Get fleet data
# [CLEANED 2025-12-25] Removed 297 lines of migrated code

# Format datetime columns
# [CLEANED 2025-12-25] Removed 315 lines of migrated code

# Default to CSV
# [CLEANED 2025-12-25] Removed 332 lines of migrated code

# ============================================================================
# 🆕 v3.12.21: HISTORICAL COMPARISON ENDPOINTS (#12)
# ============================================================================


# [CLEANED 2025-12-25] Removed 359 lines of migrated code

# Build query for both periods
# [CLEANED 2025-12-25] Removed 376 lines of migrated code

# Period 1
# [CLEANED 2025-12-25] Removed 388 lines of migrated code

# Period 2
# [CLEANED 2025-12-25] Removed 535 lines of migrated code

# ============================================================================
# 🆕 v3.12.21: SCHEDULED REPORTS ENDPOINTS (#13)
# ============================================================================

# In-memory storage for report schedules (in production, use database)
_scheduled_reports: Dict[str, Dict] = {}


# [CLEANED 2025-12-25] Removed 721 lines of migrated code

# ============================================================================
# 🆕 v4.0: COST PER MILE ENDPOINTS (Geotab-inspired)
# ============================================================================


# [CLEANED 2025-12-25] Removed 740 lines of migrated code

# Get fleet data for the period
# 🔧 v4.3: Simplified query - calculate miles from odometer, gallons from miles/mpg
# [CLEANED 2025-12-25] Removed 776 lines of migrated code

# 🆕 v4.3: Fallback - use current truck data if no historical data
# [CLEANED 2025-12-25] Removed 800 lines of migrated code

# Final fallback - return demo data
# [CLEANED 2025-12-25] Removed 844 lines of migrated code

# Note: Access control by carrier_id (currently single carrier)
# [CLEANED 2025-12-25] Removed 848 lines of migrated code

# Get truck data for the period
# 🔧 v4.3: Fixed column names - use mpg_current, calculate miles from odometer
# [CLEANED 2025-12-25] Removed 926 lines of migrated code

# ============================================================================
# 🆕 v4.0: FLEET UTILIZATION ENDPOINTS (Geotab-inspired, target 95%)
# ============================================================================


# [CLEANED 2025-12-25] Removed 950 lines of migrated code

# Get activity data for the period
# 🔧 v4.3: Fixed column name speed -> speed_mph
# [CLEANED 2025-12-25] Removed 979 lines of migrated code

# Estimate productive vs non-productive idle (assume 30% is productive)
# [CLEANED 2025-12-25] Removed 995 lines of migrated code

# 🆕 v4.3: Fallback - generate estimates from current truck list
# [CLEANED 2025-12-25] Removed 1000 lines of migrated code

# Generate reasonable estimates based on typical fleet usage
# [CLEANED 2025-12-25] Removed 1018 lines of migrated code

# Final fallback - return demo data
# [CLEANED 2025-12-25] Removed 1058 lines of migrated code

# Note: Access control by carrier_id (currently single carrier)
# [CLEANED 2025-12-25] Removed 1062 lines of migrated code

# 🔧 v4.3: Fixed column name speed -> speed_mph
# [CLEANED 2025-12-25] Removed 1142 lines of migrated code

# Get utilization data (same as fleet endpoint)
# 🔧 v4.3: Fixed column name speed -> speed_mph
# [CLEANED 2025-12-25] Removed 1182 lines of migrated code

# Note: Currently fleet is single-carrier, no filtering needed
# [CLEANED 2025-12-25] Removed 1183 lines of migrated code

# Analyze fleet utilization
# [CLEANED 2025-12-25] Removed 1191 lines of migrated code

# Get optimization opportunities
# [CLEANED 2025-12-25] Removed 1206 lines of migrated code

# ============================================================================
# 🆕 v4.0: GAMIFICATION ENDPOINTS
# ============================================================================


# [CLEANED 2025-12-25] Removed 1229 lines of migrated code

# 🔧 v5.5.1: Filter by allowed trucks from tanks.yaml
# [CLEANED 2025-12-25] Removed 1241 lines of migrated code

# Build placeholders for IN clause
# [CLEANED 2025-12-25] Removed 1244 lines of migrated code

# Get driver performance data from last 7 days
# 🔧 v4.3: Fixed column name mpg -> mpg_current, speed -> speed_mph
# 🔧 v5.5.1: Added filter by allowed_trucks
# [CLEANED 2025-12-25] Removed 1281 lines of migrated code

# 🆕 v4.3: Fallback - use current truck data if no historical data
# 🔧 v5.5.1: Filter by allowed trucks from tanks.yaml
# 🔧 v5.6.0: Fixed N+1 query - batch fetch truck data
# [CLEANED 2025-12-25] Removed 1285 lines of migrated code

# Filter to only include trucks from tanks.yaml
# [CLEANED 2025-12-25] Removed 1288 lines of migrated code

# 🔧 v5.6.0: Batch query instead of N+1
# [CLEANED 2025-12-25] Removed 1295 lines of migrated code

# Use batch data if available, otherwise fall back to individual query
# [CLEANED 2025-12-25] Removed 1318 lines of migrated code

# Final fallback - return demo data
# [CLEANED 2025-12-25] Removed 1360 lines of migrated code

# Get driver's historical data for badge calculation
# 🔧 v4.3: Fixed column names mpg -> mpg_current, speed -> speed_mph
# [CLEANED 2025-12-25] Removed 1387 lines of migrated code

# Get fleet average MPG
# 🔧 v4.3: Fixed column name mpg -> mpg_current
# [CLEANED 2025-12-25] Removed 1417 lines of migrated code

# ============================================================================
# 🆕 v5.0: PREDICTIVE MAINTENANCE ENDPOINTS
# ============================================================================


# [CLEANED 2025-12-25] Removed 1430 lines of migrated code

# Default demo response - always works
# [CLEANED 2025-12-25] Removed 1497 lines of migrated code

# 🔧 v5.1: TEMPORALMENTE usar solo demo data para evitar crashes
# El import de routers.maintenance causaba crashes al conectar a Wialon
# [CLEANED 2025-12-25] Removed 1512 lines of migrated code

# 🔧 v5.1: Return demo data to avoid crashes
# [CLEANED 2025-12-25] Removed 1525 lines of migrated code

# ============================================================================
# 🆕 v5.3.7: PREDICTIVE MAINTENANCE V5 WRAPPER
# ============================================================================
# This endpoint wraps V3 to maintain backward compatibility with frontend
# The frontend's useFleetHealth.ts expects this endpoint format


# [CLEANED 2025-12-25] Removed 1540 lines of migrated code

# Get V3 report (already filtered by tanks.yaml)
# [CLEANED 2025-12-25] Removed 1543 lines of migrated code

# Transform to V5 format expected by frontend
# [CLEANED 2025-12-25] Removed 1545 lines of migrated code

# Count status breakdown
# [CLEANED 2025-12-25] Removed 1581 lines of migrated code

# Return empty but valid response
# [CLEANED 2025-12-25] Removed 1599 lines of migrated code

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


# [CLEANED 2025-12-25] Removed 1649 lines of migrated code

# Never crash - return demo data
# [CLEANED 2025-12-25] Removed 1814 lines of migrated code

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


# [CLEANED 2025-12-25] Removed 1896 lines of migrated code

# ============================================================================
# 🆕 v3.12.21: DASHBOARD CUSTOMIZATION ENDPOINTS (#11)
# ============================================================================

# In-memory storage for user dashboards (replace with DB in production)
_user_dashboards: Dict[str, Dict] = {}
_user_preferences: Dict[str, Dict] = {}
_scheduled_reports: Dict[str, Dict] = {}


# [CLEANED 2025-12-25] Removed 2005 lines of migrated code

# Return default layout
# [CLEANED 2025-12-25] Removed 2139 lines of migrated code

# Default preferences
# [CLEANED 2025-12-25] Removed 2170 lines of migrated code

# ============================================================================
# 🆕 v3.12.21: SCHEDULED REPORTS ENDPOINTS (#13)
# ============================================================================


# [CLEANED 2025-12-25] Removed 2195 lines of migrated code

# Calculate next run based on schedule
# [CLEANED 2025-12-25] Removed 2263 lines of migrated code

# Generate report based on type
# [CLEANED 2025-12-25] Removed 2269 lines of migrated code

# Get fuel consumption data
# [CLEANED 2025-12-25] Removed 2286 lines of migrated code

# ============================================================================
# 🆕 v3.12.21: GPS TRACKING ENDPOINTS (#17)
# ============================================================================

# In-memory storage for GPS tracking (replace with DB in production)
_gps_tracking_data: Dict[str, Dict] = {}
_geofences: Dict[str, Dict] = {}


# [CLEANED 2025-12-25] Removed 2292 lines of migrated code

# Get truck data from database
# [CLEANED 2025-12-25] Removed 2330 lines of migrated code

# In production, this would query MySQL historical GPS data
# For now, return sample data structure
# [CLEANED 2025-12-25] Removed 2395 lines of migrated code

# In production, query historical events from database
# [CLEANED 2025-12-25] Removed 2404 lines of migrated code

# ============================================================================
# 🆕 v3.12.21: PUSH NOTIFICATIONS ENDPOINTS (#19)
# ============================================================================

# In-memory storage for notifications
_push_subscriptions: Dict[str, Dict] = {}
_notification_queue: List[Dict] = []


# [CLEANED 2025-12-25] Removed 2445 lines of migrated code

# Filter notifications for this user
# [CLEANED 2025-12-25] Removed 2478 lines of migrated code

# Limit queue size
# [CLEANED 2025-12-25] Removed 2481 lines of migrated code

# In production, this would trigger actual push via FCM/APNs
# [CLEANED 2025-12-25] Removed 2523 lines of migrated code

# ============================================================================
# 🆕 ENGINE HEALTH MONITORING ENDPOINTS - v3.13.0
# ============================================================================


# [CLEANED 2025-12-25] Removed 2541 lines of migrated code

# Get latest reading for each truck
# [CLEANED 2025-12-25] Removed 2570 lines of migrated code

# Convert to list of dicts
# [CLEANED 2025-12-25] Removed 2572 lines of migrated code

# Analyze fleet health
# [CLEANED 2025-12-25] Removed 2615 lines of migrated code

# Get current reading
# [CLEANED 2025-12-25] Removed 2648 lines of migrated code

# Get historical data for trend analysis
# [CLEANED 2025-12-25] Removed 2676 lines of migrated code

# Calculate baselines
# [CLEANED 2025-12-25] Removed 2682 lines of migrated code

# Analyze truck health
# [CLEANED 2025-12-25] Removed 2688 lines of migrated code

# Add historical chart data (last 7 days, sampled)
# [CLEANED 2025-12-25] Removed 2689 lines of migrated code

# Sample to ~100 points for charts
# [CLEANED 2025-12-25] Removed 2700 lines of migrated code

# Add baselines to response
# [CLEANED 2025-12-25] Removed 2741 lines of migrated code

# Build query with filters
# [CLEANED 2025-12-25] Removed 2779 lines of migrated code

# Convert datetime objects to strings
# [CLEANED 2025-12-25] Removed 2794 lines of migrated code

# Table might not exist yet - return empty
# [CLEANED 2025-12-25] Removed 2968 lines of migrated code

# Convert dates to strings
# [CLEANED 2025-12-25] Removed 2978 lines of migrated code

# Table might not exist
# [CLEANED 2025-12-25] Removed 3026 lines of migrated code

# Get hourly averages for cleaner charts
# [CLEANED 2025-12-25] Removed 3050 lines of migrated code

# Calculate statistics
# [CLEANED 2025-12-25] Removed 3093 lines of migrated code

# Get latest reading for each truck
# [CLEANED 2025-12-25] Removed 3121 lines of migrated code

# Analyze fleet
# [CLEANED 2025-12-25] Removed 3123 lines of migrated code

# Save new alerts to database
# [CLEANED 2025-12-25] Removed 3172 lines of migrated code

# ============================================================================


# ============================================================================
# TRUCK SPECS ENDPOINTS - MPG Baselines & Fleet Comparison
# NOTE: These endpoints are defined in api_v2.py and registered via routers.py
# They are available at /fuelAnalytics/api/v2/truck-specs (and other routes)
# ============================================================================


@app.get("/api/v2/fleet/specs-summary", tags=["Truck Specs"])
async def get_fleet_specs_summary():
    """Get fleet-wide MPG baseline summary grouped by make/model"""
    try:
        from sqlalchemy import text

        from database_mysql import get_db_connection

        with get_db_connection() as conn:
            result = conn.execute(
                text(
                    """
                SELECT 
                    make,
                    model,
                    COUNT(*) as truck_count,
                    AVG(mpg_loaded) as avg_mpg_loaded,
                    AVG(mpg_empty) as avg_mpg_empty,
                    MIN(year) as oldest_year,
                    MAX(year) as newest_year
                FROM truck_specs
                GROUP BY make, model
                ORDER BY make, model
            """
                )
            )

            summary = [dict(row._mapping) for row in result.fetchall()]

        # Format year_range
        for row in summary:
            if row["oldest_year"] and row["newest_year"]:
                if row["oldest_year"] == row["newest_year"]:
                    row["year_range"] = str(row["oldest_year"])
                else:
                    row["year_range"] = f"{row['oldest_year']}-{row['newest_year']}"

        return {"fleet_summary": summary, "total_groups": len(summary)}
    except Exception as e:
        logger.error(f"Error fetching fleet specs summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# 🆕 API v2: Command Center (Repository-Service-Orchestrator Architecture)
# Implements clean architecture from commits 190h + 245h
# ============================================================================

@app.get("/api/v2/command-center", tags=["Fleet Command Center"])
async def get_command_center():
    """
    🆕 v2 Command Center - Repository-Service-Orchestrator Architecture
    
    Returns comprehensive fleet data using clean architecture pattern:
    - Repositories: Data access layer
    - Services: Business logic layer  
    - Orchestrator: Coordination layer
    
    This endpoint provides:
    - Fleet summary (active/offline/moving/idling trucks)
    - Truck details with latest metrics
    - Active alerts (sensors, DEF, DTCs)
    - Health metrics
    """
    try:
        from src.config_helper import get_db_config
        from src.repositories.truck_repository import TruckRepository
        from src.repositories.sensor_repository import SensorRepository
        from src.repositories.def_repository import DEFRepository
        from src.repositories.dtc_repository import DTCRepository
        from src.orchestrators.fleet_orchestrator_adapted import FleetOrchestrator
        
        # Create repositories
        db_config = get_db_config()
        truck_repo = TruckRepository(db_config)
        sensor_repo = SensorRepository(db_config)
        def_repo = DEFRepository(db_config)
        dtc_repo = DTCRepository(db_config)
        
        # Create orchestrator
        orchestrator = FleetOrchestrator(truck_repo, sensor_repo, def_repo, dtc_repo)
        
        # Get command center data
        data = orchestrator.get_command_center_data()
        
        return JSONResponse(content=data)
        
    except Exception as e:
        logger.error(f"❌ Error in /api/v2/command-center: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/truck/{truck_id}/detail", tags=["Fleet Command Center"])
async def get_truck_detail(truck_id: str):
    """
    🆕 v2 Truck Detail - Get comprehensive truck information
    
    Returns detailed information for a specific truck including:
    - Basic truck info (status, fuel, speed, MPG)
    - Sensor readings (coolant, oil, battery, etc.)
    - Active alerts
    - DEF level
    - Active DTCs
    """
    try:
        from src.config_helper import get_db_config
        from src.repositories.truck_repository import TruckRepository
        from src.repositories.sensor_repository import SensorRepository
        from src.repositories.def_repository import DEFRepository
        from src.repositories.dtc_repository import DTCRepository
        from src.orchestrators.fleet_orchestrator_adapted import FleetOrchestrator
        
        # Create repositories
        db_config = get_db_config()
        truck_repo = TruckRepository(db_config)
        sensor_repo = SensorRepository(db_config)
        def_repo = DEFRepository(db_config)
        dtc_repo = DTCRepository(db_config)
        
        # Create orchestrator
        orchestrator = FleetOrchestrator(truck_repo, sensor_repo, def_repo, dtc_repo)
        
        # Get truck detail
        detail = orchestrator.get_truck_detail(truck_id)
        
        if 'error' in detail:
            raise HTTPException(status_code=404, detail=detail['error'])
        
        return JSONResponse(content=detail)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error getting truck detail for {truck_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/v2/fleet/health", tags=["Fleet Command Center"])
async def get_fleet_health():
    """
    🆕 v2 Fleet Health Overview
    
    Returns fleet-wide health metrics:
    - Total trucks
    - Trucks with sensor issues
    - Trucks with low DEF
    - Trucks with active DTCs
    - Overall health score (0-100)
    """
    try:
        from src.config_helper import get_db_config
        from src.repositories.truck_repository import TruckRepository
        from src.repositories.sensor_repository import SensorRepository
        from src.repositories.def_repository import DEFRepository
        from src.repositories.dtc_repository import DTCRepository
        from src.orchestrators.fleet_orchestrator_adapted import FleetOrchestrator
        
        # Create repositories
        db_config = get_db_config()
        truck_repo = TruckRepository(db_config)
        sensor_repo = SensorRepository(db_config)
        def_repo = DEFRepository(db_config)
        dtc_repo = DTCRepository(db_config)
        
        # Create orchestrator
        orchestrator = FleetOrchestrator(truck_repo, sensor_repo, def_repo, dtc_repo)
        
        # Get fleet health
        health = orchestrator.get_fleet_health_overview()
        
        return JSONResponse(content=health)
        
    except Exception as e:
        logger.error(f"❌ Error getting fleet health: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


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
    import os
    import sys

    import uvicorn

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
