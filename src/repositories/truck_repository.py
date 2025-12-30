"""
Truck Repository - Database access for truck operations

⚠️ ADAPTED for fuel_copilot_local schema (fuel_metrics + truck_specs)
Original commit 190h expected different schema - this is the adapted version.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import pymysql
from pymysql import cursors

logger = logging.getLogger(__name__)


class TruckRepository:
    """Repository for truck data access operations."""

    def __init__(self, db_config: Dict[str, Any], pool_size: int = 5):
        self.db_config = db_config
        logger.info(f"TruckRepository initialized for DB: {db_config.get('database')}")

    def _get_connection(self):
        """Get database connection."""
        return pymysql.connect(**self.db_config, cursorclass=cursors.DictCursor)

    def get_all_trucks(self) -> List[Dict[str, Any]]:
        """Get all trucks in the fleet from fuel_metrics (latest data per truck)."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        truck_id,
                        truck_status as status,
                        estimated_pct as fuel_level,
                        speed_mph as speed,
                        timestamp_utc as last_update,
                        mpg_current as mpg,
                        idle_gph
                    FROM fuel_metrics fm1
                    WHERE timestamp_utc = (
                        SELECT MAX(timestamp_utc) 
                        FROM fuel_metrics fm2 
                        WHERE fm2.truck_id = fm1.truck_id
                    )
                    ORDER BY truck_id
                """
                )
                trucks = cursor.fetchall()
                logger.debug(f"Fetched {len(trucks)} trucks")
                return trucks
        finally:
            conn.close()

    def get_truck_by_id(self, truck_id: str) -> Optional[Dict[str, Any]]:
        """Get latest truck data by ID from fuel_metrics."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        truck_id,
                        truck_status as status,
                        estimated_pct as fuel_level_pct,
                        speed_mph,
                        timestamp_utc as last_update,
                        mpg_current as mpg,
                        idle_gph,
                        rpm,
                        latitude,
                        longitude
                    FROM fuel_metrics
                    WHERE truck_id = %s
                    ORDER BY timestamp_utc DESC
                    LIMIT 1
                """,
                    (truck_id,),
                )
                truck = cursor.fetchone()
                if truck:
                    logger.debug(f"Truck found: {truck_id}")
                else:
                    logger.warning(f"Truck not found: {truck_id}")
                return truck
        finally:
            conn.close()

    def get_truck_status(self, truck_id: str) -> Optional[str]:
        """Get current status of a truck."""
        truck = self.get_truck_by_id(truck_id)
        return truck.get("status") if truck else None

    def get_truck_specs(self, truck_id: str) -> Optional[Dict[str, Any]]:
        """Get truck specifications from truck_specs table."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        truck_id,
                        vin,
                        year,
                        make,
                        model,
                        baseline_mpg_loaded,
                        baseline_mpg_empty
                    FROM truck_specs
                    WHERE truck_id = %s
                """,
                    (truck_id,),
                )
                return cursor.fetchone()
        finally:
            conn.close()

    def get_trucks_offline(self, hours: int = 2) -> List[str]:
        """Get trucks that haven't reported in specified hours."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                cursor.execute(
                    """
                    SELECT DISTINCT truck_id
                    FROM fuel_metrics fm1
                    WHERE timestamp_utc = (
                        SELECT MAX(timestamp_utc)
                        FROM fuel_metrics fm2
                        WHERE fm2.truck_id = fm1.truck_id
                    )
                    AND timestamp_utc < %s
                    ORDER BY truck_id
                """,
                    (cutoff,),
                )
                offline = [row["truck_id"] for row in cursor.fetchall()]
                logger.debug(f"Found {len(offline)} offline trucks (>{hours}h)")
                return offline
        finally:
            conn.close()

    def get_truck_metrics_history(
        self, truck_id: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """Get truck metrics history for specified hours."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                cursor.execute(
                    """
                    SELECT 
                        truck_id,
                        timestamp_utc,
                        truck_status as status,
                        estimated_pct as fuel_level_pct,
                        speed_mph,
                        mpg_current as mpg,
                        idle_gph,
                        rpm
                    FROM fuel_metrics
                    WHERE truck_id = %s
                      AND timestamp_utc >= %s
                    ORDER BY timestamp_utc ASC
                """,
                    (truck_id, cutoff),
                )
                metrics = cursor.fetchall()
                logger.debug(
                    f"Fetched {len(metrics)} metrics for {truck_id} ({hours}h)"
                )
                return metrics
        finally:
            conn.close()

    def get_active_trucks(self, hours: int = 1) -> List[str]:
        """Get trucks that have reported in the last specified hours."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                cursor.execute(
                    """
                    SELECT DISTINCT truck_id
                    FROM fuel_metrics fm1
                    WHERE timestamp_utc = (
                        SELECT MAX(timestamp_utc)
                        FROM fuel_metrics fm2
                        WHERE fm2.truck_id = fm1.truck_id
                    )
                    AND timestamp_utc >= %s
                    ORDER BY truck_id
                """,
                    (cutoff,),
                )
                active = [row["truck_id"] for row in cursor.fetchall()]
                logger.debug(f"Found {len(active)} active trucks (<{hours}h)")
                return active
        finally:
            conn.close()
