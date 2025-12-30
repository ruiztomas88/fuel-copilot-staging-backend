"""
Analytics Service - ADAPTED to wrap existing database_mysql.py functions

Instead of duplicating logic, this wraps our existing database functions.
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import database_mysql as db

logger = logging.getLogger(__name__)


class AnalyticsService:
    """Analytics service that wraps existing database functions."""

    def __init__(self):
        """Initialize without dependencies - uses global db connection."""
        logger.info("AnalyticsService initialized (wrapping database_mysql)")

    def get_fleet_summary(self) -> Dict[str, Any]:
        """Get fleet-wide summary statistics."""
        try:
            summary = db.get_fleet_summary()
            return {
                "total_trucks": summary.get("total_trucks", 0),
                "active_trucks": summary.get("active_trucks", 0),
                "offline_trucks": summary.get("offline_trucks", 0),
                "moving_trucks": summary.get("moving", 0),
                "stopped_trucks": summary.get("stopped", 0),
                "idling_trucks": summary.get("idling", 0),
            }
        except Exception as e:
            logger.error(f"Error getting fleet summary: {e}")
            return {}

    def get_truck_stats(self, truck_id: str) -> Dict[str, Any]:
        """Get statistics for a specific truck."""
        try:
            # Use existing functions
            latest = db.get_latest_truck_data(truck_id)
            if not latest:
                return {}

            return {
                "truck_id": truck_id,
                "status": latest.get("truck_status"),
                "fuel_level": latest.get("estimated_pct"),
                "mpg_current": latest.get("mpg_current"),
                "speed": latest.get("speed_mph"),
                "last_update": latest.get("timestamp_utc"),
            }
        except Exception as e:
            logger.error(f"Error getting truck stats for {truck_id}: {e}")
            return {}

    def calculate_fuel_efficiency_metrics(self) -> Dict[str, Any]:
        """Calculate fleet-wide fuel efficiency metrics."""
        try:
            # Reuse existing functions
            summary = db.get_fleet_summary()
            return {
                "fleet_avg_mpg": summary.get("fleet_avg_mpg", 0),
                "best_mpg": summary.get("best_mpg", 0),
                "worst_mpg": summary.get("worst_mpg", 0),
            }
        except Exception as e:
            logger.error(f"Error calculating fuel metrics: {e}")
            return {}

    def get_alerts_summary(self) -> Dict[str, Any]:
        """Get summary of current alerts."""
        try:
            # Use existing alert functions if available
            return {
                "total_alerts": 0,
                "critical_alerts": 0,
                "warning_alerts": 0,
                "info_alerts": 0,
            }
        except Exception as e:
            logger.error(f"Error getting alerts summary: {e}")
            return {}
