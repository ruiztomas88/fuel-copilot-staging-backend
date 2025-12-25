"""
Truck Repository - Database access for truck operations

Handles all truck-related database queries and data persistence.

Extracted from database_mysql.py for better separation of concerns.

Usage:
    repo = TruckRepository(db_config)
    trucks = repo.get_all_trucks()
    truck = repo.get_truck_by_id("FF7702")
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import structlog
import mysql.connector
from mysql.connector import pooling

logger = structlog.get_logger(__name__)


class TruckRepository:
    """
    Repository for truck data access operations.

    Provides abstraction over MySQL database for truck-related queries.
    """

    def __init__(self, db_config: Dict[str, Any], pool_size: int = 5):
        """
        Initialize TruckRepository with database configuration.

        Args:
            db_config: MySQL connection config (host, user, password, database)
            pool_size: Connection pool size for concurrent queries
        """
        self.db_config = db_config
        self.pool = self._create_connection_pool(pool_size)
        logger.info("TruckRepository initialized", pool_size=pool_size)

    def _create_connection_pool(self, pool_size: int) -> pooling.MySQLConnectionPool:
        """Create MySQL connection pool."""
        return pooling.MySQLConnectionPool(
            pool_name="truck_pool",
            pool_size=pool_size,
            pool_reset_session=True,
            **self.db_config,
        )

    def _get_connection(self):
        """Get connection from pool."""
        return self.pool.get_connection()

    def get_all_trucks(self) -> List[Dict[str, Any]]:
        """
        Get all trucks in the fleet.

        Returns:
            List of truck dictionaries with id, name, status, etc.

        Example:
            >>> repo.get_all_trucks()
            [{'truck_id': 'FF7702', 'name': 'Truck 1', 'status': 'active'}, ...]
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT 
                    truck_id,
                    truck_name,
                    status,
                    last_seen,
                    total_miles,
                    avg_mpg
                FROM trucks
                WHERE status = 'active'
                ORDER BY truck_name
            """
            )
            trucks = cursor.fetchall()
            logger.debug("Fetched all trucks", count=len(trucks))
            return trucks
        finally:
            conn.close()

    def get_truck_by_id(self, truck_id: str) -> Optional[Dict[str, Any]]:
        """
        Get truck details by ID.

        Args:
            truck_id: Unique truck identifier

        Returns:
            Truck dictionary or None if not found
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT * FROM trucks WHERE truck_id = %s
            """,
                (truck_id,),
            )
            truck = cursor.fetchone()

            if truck:
                logger.debug("Truck found", truck_id=truck_id)
            else:
                logger.warning("Truck not found", truck_id=truck_id)

            return truck
        finally:
            conn.close()

    def get_truck_status(self, truck_id: str) -> Optional[str]:
        """
        Get current status of a truck.

        Args:
            truck_id: Truck identifier

        Returns:
            Status string ('active', 'inactive', 'maintenance') or None
        """
        truck = self.get_truck_by_id(truck_id)
        return truck.get("status") if truck else None

    def update_truck_status(self, truck_id: str, status: str) -> bool:
        """
        Update truck status.

        Args:
            truck_id: Truck identifier
            status: New status ('active', 'inactive', 'maintenance')

        Returns:
            True if updated, False otherwise
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE trucks 
                SET status = %s, updated_at = NOW()
                WHERE truck_id = %s
            """,
                (status, truck_id),
            )
            conn.commit()

            success = cursor.rowcount > 0
            if success:
                logger.info("Truck status updated", truck_id=truck_id, status=status)
            else:
                logger.warning("Truck not found for update", truck_id=truck_id)

            return success
        finally:
            conn.close()

    def get_truck_last_location(self, truck_id: str) -> Optional[Dict[str, float]]:
        """
        Get truck's last known location.

        Args:
            truck_id: Truck identifier

        Returns:
            Dict with lat, lon, timestamp or None
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT latitude, longitude, timestamp
                FROM gps_readings
                WHERE truck_id = %s
                ORDER BY timestamp DESC
                LIMIT 1
            """,
                (truck_id,),
            )
            location = cursor.fetchone()
            return location
        finally:
            conn.close()

    def get_trucks_offline(self, hours: int = 24) -> List[str]:
        """
        Get trucks that haven't reported in specified hours.

        Args:
            hours: Hours threshold for offline detection

        Returns:
            List of truck IDs that are offline
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT truck_id
                FROM trucks
                WHERE last_seen < NOW() - INTERVAL %s HOUR
                AND status = 'active'
            """,
                (hours,),
            )
            offline_trucks = [row[0] for row in cursor.fetchall()]

            if offline_trucks:
                logger.warning("Offline trucks detected", count=len(offline_trucks))

            return offline_trucks
        finally:
            conn.close()

    def save_truck(self, truck_data: Dict[str, Any]) -> bool:
        """
        Save or update truck data.

        Args:
            truck_data: Dict with truck fields

        Returns:
            True if saved successfully
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO trucks (truck_id, truck_name, status, total_miles, avg_mpg)
                VALUES (%(truck_id)s, %(truck_name)s, %(status)s, %(total_miles)s, %(avg_mpg)s)
                ON DUPLICATE KEY UPDATE
                    truck_name = VALUES(truck_name),
                    status = VALUES(status),
                    total_miles = VALUES(total_miles),
                    avg_mpg = VALUES(avg_mpg),
                    updated_at = NOW()
            """,
                truck_data,
            )
            conn.commit()
            logger.info("Truck saved", truck_id=truck_data.get("truck_id"))
            return True
        except Exception as e:
            logger.error("Failed to save truck", error=str(e))
            return False
        finally:
            conn.close()

    def get_truck_metrics(self, truck_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Get aggregated metrics for a truck over time period.

        Args:
            truck_id: Truck identifier
            days: Number of days to aggregate

        Returns:
            Dict with avg_mpg, total_miles, avg_speed, etc.
        """
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT 
                    AVG(mpg) as avg_mpg,
                    SUM(miles_driven) as total_miles,
                    AVG(avg_speed) as avg_speed,
                    COUNT(*) as trip_count
                FROM trips
                WHERE truck_id = %s
                AND trip_date >= NOW() - INTERVAL %s DAY
            """,
                (truck_id, days),
            )
            metrics = cursor.fetchone() or {}
            return metrics
        finally:
            conn.close()

    def close(self):
        """Close all connections in the pool."""
        # MySQL connection pool doesn't have explicit close
        # Connections are closed automatically when pool is garbage collected
        logger.info("TruckRepository closing")
