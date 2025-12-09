"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         ROUTERS PACKAGE                                        ║
║         Modular API routing (from 5,954-line main.py monolith)                 ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  STATUS: ALL ROUTERS DISABLED TO PREVENT DUPLICATE ENDPOINTS                   ║
║                                                                                ║
║  The main.py already has these endpoints. Enabling routers causes duplicates:  ║
║  - /health, /status, /cache/stats (health_router)                              ║
║  - /trucks (fleet_router)                                                      ║
║  - maintenance_router: Also crashed backend with Wialon DB                     ║
║                                                                                ║
║  TODO: Properly migrate endpoints from main.py to routers                      ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

# 🔧 ALL ROUTERS DISABLED - main.py already has these endpoints
# Enabling causes "duplicate endpoint" errors in tests and runtime conflicts

# from .health import router as health_router
# from .maintenance import router as maintenance_router
# from .fleet import router as fleet_router
# from .analytics import router as analytics_router

__all__ = [
    # All routers disabled until main.py endpoints are removed
    # "health_router",
    # "maintenance_router",
    # "fleet_router",
    # "analytics_router",
]


def include_all_routers(app, auth_dependency=None):
    """
    Include all routers in the FastAPI app.

    NOTE: ALL ROUTERS DISABLED until we properly migrate from main.py
    The endpoints already exist in main.py - enabling routers creates duplicates.
    """
    # 🔧 ALL DISABLED - main.py has these endpoints already
    # app.include_router(health_router)
    # app.include_router(maintenance_router)
    # app.include_router(fleet_router)
    # app.include_router(analytics_router)
    pass  # No-op until migration is complete
