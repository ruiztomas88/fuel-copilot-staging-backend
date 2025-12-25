"""
DEF Repository - DEF system data access

Handles DEF level, predictions, and consumption data.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import structlog
from mysql.connector import pooling

logger = structlog.get_logger(__name__)


class DEFRepository:
    """Repository for DEF system data."""

    def __init__(self, db_config: Dict[str, Any], pool_size: int = 3):
        self.db_config = db_config
        self.pool = pooling.MySQLConnectionPool(
            pool_name="def_pool",
            pool_size=pool_size,
            pool_reset_session=True,
            **db_config,
        )

    def _get_connection(self):
        return self.pool.get_connection()

    def get_def_level(self, truck_id: str) -> Optional[float]:
        """Get current DEF level percentage."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT sensor_value
                FROM sensor_readings
                WHERE truck_id = %s AND sensor_name = 'def_level'
                ORDER BY timestamp DESC
                LIMIT 1
            """,
                (truck_id,),
            )
            result = cursor.fetchone()
            return result[0] if result else None
        finally:
            conn.close()

    def save_def_prediction(self, truck_id: str, prediction_data: Dict) -> bool:
        """Save DEF depletion prediction."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO def_predictions 
                (truck_id, current_level, days_until_empty, days_until_derate, predicted_at)
                VALUES (%s, %s, %s, %s, NOW())
            """,
                (
                    truck_id,
                    prediction_data.get("current_level_pct"),
                    prediction_data.get("days_until_empty"),
                    prediction_data.get("days_until_derate"),
                ),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to save DEF prediction", error=str(e))
            return False
        finally:
            conn.close()

    def get_def_consumption_history(self, truck_id: str, days: int = 30) -> List[Dict]:
        """Get historical DEF consumption data."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT sensor_value as def_level, timestamp
                FROM sensor_readings
                WHERE truck_id = %s AND sensor_name = 'def_level'
                AND timestamp >= NOW() - INTERVAL %s DAY
                ORDER BY timestamp ASC
            """,
                (truck_id, days),
            )
            return cursor.fetchall()
        finally:
            conn.close()
