"""
DEF Repository - Database access for DEF (Diesel Exhaust Fluid) operations

⚠️ ADAPTED for fuel_copilot_local schema (fuel_metrics)
DEF data is stored in fuel_metrics.def_level_pct column.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging
import pymysql
from pymysql import cursors

logger = logging.getLogger(__name__)


class DEFRepository:
    """Repository for DEF data access operations."""

    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        logger.info(f"DEFRepository initialized for DB: {db_config.get('database')}")

    def _get_connection(self):
        """Get database connection."""
        return pymysql.connect(**self.db_config, cursorclass=cursors.DictCursor)

    def get_def_level(self, truck_id: str) -> Optional[float]:
        """Get current DEF level for a truck."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT def_level_pct
                    FROM fuel_metrics
                    WHERE truck_id = %s
                    ORDER BY timestamp_utc DESC
                    LIMIT 1
                """, (truck_id,))
                result = cursor.fetchone()
                return result['def_level_pct'] if result else None
        finally:
            conn.close()

    def get_def_history(self, truck_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get DEF level history for specified hours."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                cursor.execute("""
                    SELECT 
                        timestamp_utc,
                        def_level_pct
                    FROM fuel_metrics
                    WHERE truck_id = %s
                      AND timestamp_utc >= %s
                    ORDER BY timestamp_utc ASC
                """, (truck_id, cutoff))
                history = cursor.fetchall()
                logger.debug(f"Fetched {len(history)} DEF readings for {truck_id}")
                return history
        finally:
            conn.close()

    def get_low_def_trucks(self, threshold: float = 15.0) -> List[Dict[str, Any]]:
        """Get trucks with DEF level below threshold."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        fm1.truck_id,
                        fm1.def_level_pct,
                        fm1.timestamp_utc
                    FROM fuel_metrics fm1
                    WHERE timestamp_utc = (
                        SELECT MAX(timestamp_utc)
                        FROM fuel_metrics fm2
                        WHERE fm2.truck_id = fm1.truck_id
                    )
                    AND fm1.def_level_pct < %s
                    AND fm1.def_level_pct IS NOT NULL
                    ORDER BY fm1.def_level_pct ASC
                """, (threshold,))
                trucks = cursor.fetchall()
                logger.debug(f"Found {len(trucks)} trucks with DEF < {threshold}%")
                return trucks
        finally:
            conn.close()

    def calculate_def_burn_rate(self, truck_id: str, hours: int = 24) -> Optional[float]:
        """Calculate DEF consumption rate (% per hour)."""
        history = self.get_def_history(truck_id, hours=hours)
        
        if len(history) < 2:
            return None
        
        # Get first and last readings
        first = history[0]
        last = history[-1]
        
        if not first.get('def_level_pct') or not last.get('def_level_pct'):
            return None
        
        time_diff_hours = (last['timestamp_utc'] - first['timestamp_utc']).total_seconds() / 3600
        if time_diff_hours <= 0:
            return None
        
        level_diff = first['def_level_pct'] - last['def_level_pct']
        burn_rate = level_diff / time_diff_hours
        
        logger.debug(f"DEF burn rate for {truck_id}: {burn_rate:.2f}%/hr")
        return burn_rate
