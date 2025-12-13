"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         ROUTERS PACKAGE v6.0.0                                 ║
║         Complete Modular API routing (104 endpoints extracted)                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  STATUS: ALL ROUTERS READY - Use include_all_routers() to enable               ║
║                                                                                ║
║  ROUTER INVENTORY:                                                             ║
║  ┌─────────────────────────┬───────────────────────────────────────────────┐   ║
║  │ Router                  │ Endpoints                                     │   ║
║  ├─────────────────────────┼───────────────────────────────────────────────┤   ║
║  │ auth_router             │ /auth/login, /auth/me, /auth/refresh          │   ║
║  │ admin_router            │ /admin/carriers, /admin/users, /admin/stats   │   ║
║  │ geofence_router         │ /geofence/events, zones, location-history     │   ║
║  │ cost_router             │ /cost/per-mile, /cost/per-mile/{id}, speed    │   ║
║  │ utilization_router      │ /utilization/fleet, /{id}, /optimization      │   ║
║  │ gamification_router     │ /gamification/leaderboard, /badges/{id}       │   ║
║  │ maintenance_router      │ /maintenance/*, /v3/*, /v5/*                  │   ║
║  │ dashboard_router        │ /dashboard/widgets, /dashboard/layout/*       │   ║
║  │ reports_router          │ /reports/schedules, /reports/generate/*       │   ║
║  │ gps_router              │ /gps/trucks, /gps/truck/{id}/history          │   ║
║  │ notifications_router    │ /notifications/*, /notifications/send         │   ║
║  │ engine_health_router    │ /engine-health/*, /engine-health/analyze      │   ║
║  │ export_router           │ /export/fleet-report, /export/refuels         │   ║
║  │ predictions_router      │ /analytics/next-refuel-prediction, trends     │   ║
║  │ ml_intelligence_router  │ /ml/anomaly-detection, /ml/driver-clustering  │   ║
║  └─────────────────────────┴───────────────────────────────────────────────┘   ║
║                                                                                ║
║  NOTE: main.py still contains some endpoints - routers are ready for           ║
║  gradual migration when main.py endpoints are commented out                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

# ML Intelligence router (new, not in main.py)
from .ml_intelligence import router as ml_intelligence_router

# Auth and Admin routers
from .auth_router import router as auth_router
from .admin_router import router as admin_router

# Domain routers (extracted from main.py)
from .geofence_router import router as geofence_router
from .cost_router import router as cost_router
from .utilization_router import router as utilization_router
from .gamification_router import router as gamification_router
from .maintenance_router import router as maintenance_router
from .maintenance_router import router_v3 as maintenance_v3_router
from .dashboard_router import router as dashboard_router
from .reports_router import router as reports_router
from .gps_router import router as gps_router
from .notifications_router import router as notifications_router
from .engine_health_router import router as engine_health_router
from .export_router import router as export_router
from .predictions_router import router as predictions_router

__all__ = [
    "ml_intelligence_router",
    "auth_router",
    "admin_router",
    "geofence_router",
    "cost_router",
    "utilization_router",
    "gamification_router",
    "maintenance_router",
    "maintenance_v3_router",
    "dashboard_router",
    "reports_router",
    "gps_router",
    "notifications_router",
    "engine_health_router",
    "export_router",
    "predictions_router",
]


def include_all_routers(app, auth_dependency=None):
    """
    Include all routers in the FastAPI app.

    All 104 endpoints are now available via modular routers.

    MIGRATION STATUS:
    - ENABLED: ml_intelligence, auth, admin (not in main.py or commented out)
    - DISABLED: All others (still in main.py - would cause duplicates)

    To migrate an endpoint group:
    1. Comment out the endpoints in main.py
    2. Enable the corresponding router below
    3. Test the application
    """
    # ═══════════════════════════════════════════════════════════════════════
    # ALL ROUTERS ENABLED - v6.1.0 (migrated from main.py monolith)
    # ═══════════════════════════════════════════════════════════════════════

    # ML Intelligence (new endpoints)
    app.include_router(ml_intelligence_router)

    # Auth/Admin
    app.include_router(auth_router)
    app.include_router(admin_router)

    # Domain routers (migrated from main.py)
    app.include_router(geofence_router)  # /geofence/* (3 endpoints)
    app.include_router(cost_router)  # /cost/* (3 endpoints)
    app.include_router(utilization_router)  # /utilization/* (3 endpoints)
    app.include_router(gamification_router)  # /gamification/* (2 endpoints)
    app.include_router(maintenance_router)  # /maintenance/*, /v5/* (3 endpoints)
    app.include_router(maintenance_v3_router)  # /v3/* (5 endpoints)
    app.include_router(
        dashboard_router
    )  # /dashboard/*, /user/preferences/* (7 endpoints)
    app.include_router(reports_router)  # /reports/* (9 endpoints)
    app.include_router(gps_router)  # /gps/* (6 endpoints)
    app.include_router(notifications_router)  # /notifications/* (6 endpoints)
    app.include_router(engine_health_router)  # /engine-health/* (9 endpoints)
    app.include_router(export_router)  # /export/* (2 endpoints)
    app.include_router(
        predictions_router
    )  # /analytics/next-refuel-*, trends, historical (3 endpoints)
