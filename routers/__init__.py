"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         ROUTERS PACKAGE                                        ║
║         Modular API routing (from 5,954-line main.py monolith)                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Routers:                                                                      ║
║  - health_router: System health checks (/health, /status)                      ║
║  - maintenance_router: DISABLED - was causing crashes                          ║
║  - fleet_router: Fleet management (/trucks, /fleet-summary)                    ║
║  - analytics_router: Fuel analytics (/analytics/*)                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from .health import router as health_router

# 🔧 DISABLED: maintenance_router was crashing the backend
# from .maintenance import router as maintenance_router
from .fleet import router as fleet_router
from .analytics import router as analytics_router

__all__ = [
    "health_router",
    # "maintenance_router",  # DISABLED
    "fleet_router",
    "analytics_router",
]


def include_all_routers(app, auth_dependency=None):
    """
    Include all routers in the FastAPI app.

    NOTE: maintenance_router is DISABLED until properly tested.
    """
    # 🔧 DISABLED: maintenance router was causing crashes
    # if auth_dependency:
    #     from .maintenance import set_auth_dependency
    #     set_auth_dependency(auth_dependency)

    # Include routers (maintenance DISABLED)
    app.include_router(health_router)
    # app.include_router(maintenance_router)  # DISABLED
    app.include_router(fleet_router)
    app.include_router(analytics_router)
