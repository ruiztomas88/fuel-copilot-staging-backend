"""
routers.py - Centralized Router Registration for v3.12.21
This file consolidates all new API routers for easy integration into main.py
"""

import logging
from fastapi import FastAPI

logger = logging.getLogger(__name__)


def register_v3_12_21_routers(app: FastAPI) -> None:
    """
    Register all new routers added in v3.12.21.
    Call this function from main.py after app initialization.

    Routers added:
    - api_v2: Consolidated endpoints for new features
    - sse_endpoints: Server-Sent Events for real-time updates
    - fuel_stations: External fuel station API integration
    """

    try:
        # API v2 - New consolidated endpoints
        from api_v2 import router as api_v2_router

        app.include_router(api_v2_router, prefix="/api/v2", tags=["API v2"])
        logger.info("✅ Registered api_v2 router")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import api_v2 router: {e}")

    try:
        # SSE Endpoints - Real-time streaming
        from sse_endpoints import router as sse_router

        app.include_router(sse_router, prefix="/api", tags=["SSE"])
        logger.info("✅ Registered sse_endpoints router")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import sse_endpoints router: {e}")

    try:
        # Fuel Stations - External API integration
        from fuel_stations import router as fuel_stations_router

        app.include_router(fuel_stations_router, prefix="/api", tags=["Fuel Stations"])
        logger.info("✅ Registered fuel_stations router")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import fuel_stations router: {e}")

    logger.info("🚀 v3.12.21 routers registration complete")


def register_middleware(app: FastAPI) -> None:
    """
    Register new middleware added in v3.12.21.
    """
    try:
        from field_normalizer import FieldNormalizationMiddleware

        app.add_middleware(
            FieldNormalizationMiddleware,
            exclude_paths=[
                "/docs",
                "/redoc",
                "/openapi.json",
                "/health",
                "/metrics",
                "/api/sse",
            ],
        )
        logger.info("✅ Registered FieldNormalizationMiddleware")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import FieldNormalizationMiddleware: {e}")

    try:
        from audit_log import AuditMiddleware

        app.add_middleware(AuditMiddleware)
        logger.info("✅ Registered AuditMiddleware")
    except ImportError as e:
        logger.warning(f"⚠️ Could not import AuditMiddleware: {e}")


async def initialize_new_modules() -> None:
    """
    Initialize new modules that require async setup.
    Call this during app startup.
    """
    try:
        # Migrate in-memory users to database
        from user_management import migrate_users_db

        await migrate_users_db()
        logger.info("✅ User database migration completed")
    except Exception as e:
        logger.warning(f"⚠️ User migration skipped: {e}")

    try:
        # Initialize sensor anomaly detector
        from sensor_anomaly import SensorAnomalyDetector

        detector = SensorAnomalyDetector()
        logger.info("✅ Sensor anomaly detector initialized")
    except Exception as e:
        logger.warning(f"⚠️ Sensor anomaly detector not initialized: {e}")


# Integration snippet for main.py:
"""
# Add to main.py after app initialization:

# v3.12.21 - Register new routers and middleware
try:
    from routers import register_v3_12_21_routers, register_middleware, initialize_new_modules
    
    # Register middleware (before routers)
    register_middleware(app)
    
    # Register new API routers
    register_v3_12_21_routers(app)
    
    # Add to lifespan startup:
    # await initialize_new_modules()
    
except ImportError as e:
    logger.warning(f"v3.12.21 router registration skipped: {e}")
"""
