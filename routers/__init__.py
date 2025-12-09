"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         ROUTERS PACKAGE                                        ║
║         Modular API routing (from 5,954-line main.py monolith)                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Routers:                                                                      ║
║  - health_router: System health checks (/health, /status)                      ║
║  - maintenance_router: Predictive maintenance (/maintenance/*)                 ║
║  - fleet_router: Fleet management (/trucks, /fleet-summary)                    ║
║  - analytics_router: Fuel analytics (/analytics/*)                             ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

from .health import router as health_router
from .maintenance import router as maintenance_router
from .fleet import router as fleet_router
from .analytics import router as analytics_router

__all__ = [
    "health_router",
    "maintenance_router",
    "fleet_router",
    "analytics_router",
]


def include_all_routers(app, auth_dependency=None):
    """
    Include all routers in the FastAPI app.

    Args:
        app: FastAPI application instance
        auth_dependency: Optional auth dependency to inject

    Usage in main.py:
        from routers import include_all_routers
        include_all_routers(app, require_auth)
    """
    # Set auth dependency for maintenance router
    if auth_dependency:
        from .maintenance import set_auth_dependency

        set_auth_dependency(auth_dependency)

    # Include routers
    app.include_router(health_router)
    app.include_router(maintenance_router)
    app.include_router(fleet_router)
    app.include_router(analytics_router)
