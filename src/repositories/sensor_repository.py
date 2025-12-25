"""
Sensor Repository - Sensor readings data access

Handles sensor reading queries, persistence, and anomaly detection.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import structlog
from mysql.connector import pooling

logger = structlog.get_logger(__name__)


class SensorRepository:
    """Repository for sensor data operations."""

    def __init__(self, db_config: Dict[str, Any], pool_size: int = 5):
        self.db_config = db_config
        self.pool = pooling.MySQLConnectionPool(
            pool_name="sensor_pool",
            pool_size=pool_size,
            pool_reset_session=True,
            **db_config,
        )

    def _get_connection(self):
        return self.pool.get_connection()

    def get_sensor_readings(
        self, truck_id: str, sensor_name: str, hours: int = 24
    ) -> List[Dict]:
        """Get recent sensor readings."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT sensor_value, timestamp
                FROM sensor_readings
                WHERE truck_id = %s AND sensor_name = %s
                AND timestamp >= NOW() - INTERVAL %s HOUR
                ORDER BY timestamp DESC
            """,
                (truck_id, sensor_name, hours),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def save_sensor_reading(
        self, truck_id: str, sensor_name: str, value: float, timestamp: datetime = None
    ) -> bool:
        """Save sensor reading."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO sensor_readings (truck_id, sensor_name, sensor_value, timestamp)
                VALUES (%s, %s, %s, %s)
            """,
                (truck_id, sensor_name, value, timestamp or datetime.now()),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to save sensor reading", error=str(e))
            return False
        finally:
            conn.close()

    def get_sensor_stats(
        self, truck_id: str, sensor_name: str, days: int = 7
    ) -> Dict[str, float]:
        """Get sensor statistics (avg, min, max)."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT 
                    AVG(sensor_value) as avg_value,
                    MIN(sensor_value) as min_value,
                    MAX(sensor_value) as max_value,
                    STDDEV(sensor_value) as std_dev
                FROM sensor_readings
                WHERE truck_id = %s AND sensor_name = %s
                AND timestamp >= NOW() - INTERVAL %s DAY
            """,
                (truck_id, sensor_name, days),
            )
            return cursor.fetchone() or {}
        finally:
            conn.close()
