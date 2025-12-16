"""
Unified Database Module - Centralized database access for Fuel Copilot
🆕 v3.12.21: Consolidates database.py, database_mysql.py, database_pool.py, database_enhanced.py

This module provides a single entry point for all database operations.
Maintains backward compatibility with existing imports.

Usage:
    from db import get_engine, get_db_connection, db
    from db import get_sqlalchemy_engine, get_latest_truck_data
    from db import get_raw_sensor_history, get_fuel_consumption_trend
"""

import logging
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# =============================================================================
# Connection Pool (from database_pool.py)
# =============================================================================
try:
    from database_pool import (
        get_engine,
        get_session,
        get_db_connection,
        get_pool_status,
        DatabasePool,
    )

    POOL_AVAILABLE = True
    logger.debug("✅ database_pool loaded")
except ImportError as e:
    logger.warning(f"database_pool not available: {e}")
    POOL_AVAILABLE = False
    get_engine = None
    get_session = None
    get_db_connection = None
    get_pool_status = None
    DatabasePool = None


# =============================================================================
# MySQL Functions (from database_mysql.py)
# =============================================================================
try:
    from database_mysql import (
        # Engine & Connection
        get_sqlalchemy_engine,
        test_connection,
        # Core Data Functions
        get_latest_truck_data,
        get_truck_history,
        get_refuel_history,
        get_fleet_summary,
        # Analytics Functions
        get_advanced_refuel_analytics,
        get_fuel_theft_analysis,
        get_kpi_summary,
        get_loss_analysis,
        get_driver_scorecard,
        get_enhanced_kpis,
        get_enhanced_loss_analysis,
        # Driver Score History v1.1.0
        get_driver_score_history,
        get_driver_score_trend,
        save_driver_score_history,
        # Route & Cost Functions
        get_route_efficiency_analysis,
        get_cost_attribution_report,
        # Geofence Functions
        get_geofence_events,
        get_truck_location_history,
        GEOFENCE_ZONES,
        # Config
        MYSQL_CONFIG,
    )

    MYSQL_AVAILABLE = True
    logger.debug("✅ database_mysql loaded")
except ImportError as e:
    logger.warning(f"database_mysql not available: {e}")
    MYSQL_AVAILABLE = False


# =============================================================================
# Enhanced Functions (from database_enhanced.py)
# =============================================================================
try:
    from database_enhanced import (
        get_raw_sensor_history,
        get_fuel_consumption_trend,
        get_fleet_sensor_status,
    )

    ENHANCED_AVAILABLE = True
    logger.debug("✅ database_enhanced loaded")
except ImportError as e:
    logger.warning(f"database_enhanced not available: {e}")
    ENHANCED_AVAILABLE = False
    get_raw_sensor_history = None
    get_fuel_consumption_trend = None
    get_fleet_sensor_status = None


# =============================================================================
# Database Manager (from database.py)
# =============================================================================
try:
    from database import db, DatabaseManager

    DB_MANAGER_AVAILABLE = True
    logger.debug("✅ database manager loaded")
except ImportError as e:
    logger.warning(f"database manager not available: {e}")
    DB_MANAGER_AVAILABLE = False
    db = None
    DatabaseManager = None


# =============================================================================
# Utility Functions
# =============================================================================


def get_database_status() -> dict:
    """
    Get status of all database components.

    Returns:
        dict with status of each component
    """
    status = {
        "pool_available": POOL_AVAILABLE,
        "mysql_available": MYSQL_AVAILABLE,
        "enhanced_available": ENHANCED_AVAILABLE,
        "db_manager_available": DB_MANAGER_AVAILABLE,
    }

    # Test actual connection
    if MYSQL_AVAILABLE:
        try:
            status["mysql_connected"] = test_connection()
        except Exception as e:
            status["mysql_connected"] = False
            status["mysql_error"] = str(e)

    # Get pool stats if available
    if POOL_AVAILABLE and get_pool_status:
        try:
            status["pool_status"] = get_pool_status()
        except Exception:
            pass

    return status


def check_health() -> bool:
    """
    Quick health check for database connectivity.

    Returns:
        True if database is accessible
    """
    if MYSQL_AVAILABLE:
        try:
            return test_connection()
        except Exception:
            return False
    return False


# =============================================================================
# Exports
# =============================================================================
__all__ = [
    # Pool
    "get_engine",
    "get_session",
    "get_db_connection",
    "get_pool_status",
    "DatabasePool",
    "POOL_AVAILABLE",
    # MySQL
    "get_sqlalchemy_engine",
    "test_connection",
    "get_latest_truck_data",
    "get_truck_history",
    "get_refuel_history",
    "get_fleet_summary",
    "get_advanced_refuel_analytics",
    "get_fuel_theft_analysis",
    "get_kpi_summary",
    "get_loss_analysis",
    "get_driver_scorecard",
    "get_enhanced_kpis",
    "get_enhanced_loss_analysis",
    # Driver Score History v1.1.0
    "get_driver_score_history",
    "get_driver_score_trend",
    "save_driver_score_history",
    # Routes
    "get_route_efficiency_analysis",
    "get_cost_attribution_report",
    "get_geofence_events",
    "get_truck_location_history",
    "GEOFENCE_ZONES",
    "MYSQL_CONFIG",
    "MYSQL_AVAILABLE",
    # Enhanced
    "get_raw_sensor_history",
    "get_fuel_consumption_trend",
    "get_fleet_sensor_status",
    "ENHANCED_AVAILABLE",
    # Manager
    "db",
    "DatabaseManager",
    "DB_MANAGER_AVAILABLE",
    # Utilities
    "get_database_status",
    "check_health",
]
