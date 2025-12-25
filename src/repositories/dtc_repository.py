"""
DTC Repository - Database access for Diagnostic Trouble Codes

⚠️ ADAPTED for fuel_copilot_local schema (fuel_metrics)
DTC data is stored in fuel_metrics.dtc and fuel_metrics.dtc_code columns.
"""

from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
import logging
import pymysql
from pymysql import cursors

logger = logging.getLogger(__name__)


class DTCRepository:
    """Repository for DTC (Diagnostic Trouble Code) data access operations."""

    def __init__(self, db_config: Dict[str, Any]):
        self.db_config = db_config
        logger.info(f"DTCRepository initialized for DB: {db_config.get('database')}")

    def _get_connection(self):
        """Get database connection."""
        return pymysql.connect(**self.db_config, cursorclass=cursors.DictCursor)

    def get_active_dtcs(self, truck_id: str) -> List[Dict[str, Any]]:
        """Get current active DTCs for a truck."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        truck_id,
                        dtc,
                        dtc_code,
                        timestamp_utc
                    FROM fuel_metrics
                    WHERE truck_id = %s
                      AND (dtc IS NOT NULL OR dtc_code IS NOT NULL)
                    ORDER BY timestamp_utc DESC
                    LIMIT 1
                """, (truck_id,))
                result = cursor.fetchone()
                
                if not result or not result.get('dtc'):
                    return []
                
                # Return as list for consistency
                return [{
                    'truck_id': result['truck_id'],
                    'dtc': result['dtc'],
                    'dtc_code': result['dtc_code'],
                    'timestamp': result['timestamp_utc']
                }]
        finally:
            conn.close()

    def get_dtc_history(self, truck_id: str, hours: int = 168) -> List[Dict[str, Any]]:
        """Get DTC history for specified hours (default 7 days)."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cutoff = datetime.utcnow() - timedelta(hours=hours)
                cursor.execute("""
                    SELECT 
                        timestamp_utc,
                        dtc,
                        dtc_code
                    FROM fuel_metrics
                    WHERE truck_id = %s
                      AND timestamp_utc >= %s
                      AND (dtc IS NOT NULL OR dtc_code IS NOT NULL)
                    ORDER BY timestamp_utc DESC
                """, (truck_id, cutoff))
                history = cursor.fetchall()
                logger.debug(f"Fetched {len(history)} DTC records for {truck_id}")
                return history
        finally:
            conn.close()

    def get_fleet_dtcs(self) -> List[Dict[str, Any]]:
        """Get all active DTCs across the fleet."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                    SELECT 
                        fm1.truck_id,
                        fm1.dtc,
                        fm1.dtc_code,
                        fm1.timestamp_utc
                    FROM fuel_metrics fm1
                    WHERE timestamp_utc = (
                        SELECT MAX(timestamp_utc)
                        FROM fuel_metrics fm2
                        WHERE fm2.truck_id = fm1.truck_id
                    )
                    AND (fm1.dtc IS NOT NULL OR fm1.dtc_code IS NOT NULL)
                    ORDER BY fm1.truck_id
                """)
                dtcs = cursor.fetchall()
                logger.debug(f"Found {len(dtcs)} trucks with active DTCs")
                return dtcs
        finally:
            conn.close()

    def get_dtc_count_by_truck(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get count of DTC occurrences by truck in last N days."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cutoff = datetime.utcnow() - timedelta(days=days)
                cursor.execute("""
                    SELECT 
                        truck_id,
                        COUNT(DISTINCT dtc_code) as dtc_count,
                        GROUP_CONCAT(DISTINCT dtc_code) as dtc_codes
                    FROM fuel_metrics
                    WHERE timestamp_utc >= %s
                      AND dtc_code IS NOT NULL
                    GROUP BY truck_id
                    ORDER BY dtc_count DESC
                """, (cutoff,))
                counts = cursor.fetchall()
                logger.debug(f"DTC counts for {len(counts)} trucks ({days} days)")
                return counts
        finally:
            conn.close()

    def get_most_common_dtcs(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get most commonly occurring DTCs across fleet."""
        conn = self._get_connection()
        try:
            with conn.cursor() as cursor:
                cutoff = datetime.utcnow() - timedelta(days=days)
                cursor.execute("""
                    SELECT 
                        dtc_code,
                        COUNT(DISTINCT truck_id) as truck_count,
                        COUNT(*) as occurrence_count
                    FROM fuel_metrics
                    WHERE timestamp_utc >= %s
                      AND dtc_code IS NOT NULL
                    GROUP BY dtc_code
                    ORDER BY occurrence_count DESC
                    LIMIT 10
                """, (cutoff,))
                common_dtcs = cursor.fetchall()
                logger.debug(f"Found {len(common_dtcs)} common DTCs ({days} days)")
                return common_dtcs
        finally:
            conn.close()
