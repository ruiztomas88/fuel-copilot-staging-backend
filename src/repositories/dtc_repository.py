"""
DTC Repository - Diagnostic Trouble Code data access

Handles DTC (Diagnostic Trouble Code) storage and retrieval.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime
import structlog
from mysql.connector import pooling

logger = structlog.get_logger(__name__)


class DTCRepository:
    """Repository for DTC operations."""

    def __init__(self, db_config: Dict[str, Any], pool_size: int = 3):
        self.db_config = db_config
        self.pool = pooling.MySQLConnectionPool(
            pool_name="dtc_pool",
            pool_size=pool_size,
            pool_reset_session=True,
            **db_config,
        )

    def _get_connection(self):
        return self.pool.get_connection()

    def get_active_dtcs(self, truck_id: str) -> List[Dict]:
        """Get currently active DTCs for a truck."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT dtc_code, spn, fmi, occurrence_count, first_seen, last_seen
                FROM dtc_events
                WHERE truck_id = %s AND status = 'active'
                ORDER BY last_seen DESC
            """,
                (truck_id,),
            )
            return cursor.fetchall()
        finally:
            conn.close()

    def save_dtc_event(self, truck_id: str, dtc_code: str, spn: int, fmi: int) -> bool:
        """Save new DTC event or update existing."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO dtc_events (truck_id, dtc_code, spn, fmi, first_seen, last_seen, occurrence_count, status)
                VALUES (%s, %s, %s, %s, NOW(), NOW(), 1, 'active')
                ON DUPLICATE KEY UPDATE
                    last_seen = NOW(),
                    occurrence_count = occurrence_count + 1,
                    status = 'active'
            """,
                (truck_id, dtc_code, spn, fmi),
            )
            conn.commit()
            return True
        except Exception as e:
            logger.error("Failed to save DTC", error=str(e))
            return False
        finally:
            conn.close()

    def resolve_dtc(self, truck_id: str, dtc_code: str) -> bool:
        """Mark DTC as resolved."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE dtc_events
                SET status = 'resolved', resolved_at = NOW()
                WHERE truck_id = %s AND dtc_code = %s AND status = 'active'
            """,
                (truck_id, dtc_code),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()

    def get_dtc_history(self, truck_id: str, days: int = 30) -> List[Dict]:
        """Get DTC history for analysis."""
        conn = self._get_connection()
        try:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(
                """
                SELECT * FROM dtc_events
                WHERE truck_id = %s
                AND first_seen >= NOW() - INTERVAL %s DAY
                ORDER BY first_seen DESC
            """,
                (truck_id, days),
            )
            return cursor.fetchall()
        finally:
            conn.close()
