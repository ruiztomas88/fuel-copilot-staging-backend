"""
MPG Baseline Tracker v1.0.0
Tracks baseline MPG per truck and detects degradation over time

Features:
- Calculate and store baseline MPG for each truck
- Detect degradation (>5% drop over 3 days)
- Track trends and anomalies
- Alert integration
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)


@dataclass
class MPGBaseline:
    """Represents MPG baseline for a truck"""

    truck_id: str
    baseline_mpg: float
    period_start: datetime
    period_end: datetime
    sample_count: int
    std_dev: float
    confidence: float

    def to_dict(self) -> dict:
        """Convert to dictionary for API response"""
        return {
            "truck_id": self.truck_id,
            "baseline_mpg": round(self.baseline_mpg, 2),
            "period_start": (
                self.period_start.isoformat() if self.period_start else None
            ),
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "sample_count": self.sample_count,
            "std_dev": round(self.std_dev, 2),
            "confidence": round(self.confidence, 2),
        }


@dataclass
class MPGDegradation:
    """Represents MPG degradation alert"""

    truck_id: str
    current_mpg: float
    baseline_mpg: float
    degradation_pct: float
    days_declining: int
    severity: str  # LOW, MEDIUM, HIGH, CRITICAL
    timestamp: datetime

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "truck_id": self.truck_id,
            "current_mpg": round(self.current_mpg, 2),
            "baseline_mpg": round(self.baseline_mpg, 2),
            "degradation_pct": round(self.degradation_pct, 1),
            "days_declining": self.days_declining,
            "severity": self.severity,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }


class MPGBaselineTracker:
    """
    Tracks MPG baselines and detects degradation

    Usage:
        tracker = MPGBaselineTracker()

        # Calculate baseline
        baseline = tracker.calculate_baseline("RA9250", period_days=30)

        # Store baseline
        tracker.store_baseline(baseline)

        # Check for degradation
        degradation = tracker.check_degradation("RA9250")
        if degradation and degradation.degradation_pct > 5.0:
            print(f"Alert: {degradation.truck_id} MPG down {degradation.degradation_pct}%")
    """

    def __init__(self, db_connection=None):
        """
        Initialize tracker

        Args:
            db_connection: Optional database connection
        """
        if db_connection is not None:
            self.db = db_connection
            self._should_close_db = False
        else:
            self.db = pymysql.connect(
                host=os.getenv("MYSQL_HOST", "localhost"),
                user=os.getenv("MYSQL_USER", "root"),
                password=os.getenv("MYSQL_PASSWORD", ""),
                database=os.getenv("MYSQL_DATABASE", "fuel_copilot_local"),
                port=int(os.getenv("MYSQL_PORT", "3306")),
                charset="utf8mb4",
                autocommit=True,
                cursorclass=DictCursor,
            )
            self._should_close_db = True

    def __del__(self):
        """Clean up database connection"""
        if self._should_close_db and self.db:
            try:
                self.db.close()
            except:
                pass

    def calculate_baseline(
        self, truck_id: str, period_days: int = 30, min_samples: int = 50
    ) -> Optional[MPGBaseline]:
        """
        Calculate baseline MPG for a truck

        Args:
            truck_id: Truck identifier
            period_days: Number of days to analyze
            min_samples: Minimum samples required

        Returns:
            MPGBaseline or None if insufficient data
        """
        query = """
            SELECT 
                mpg_current,
                timestamp_utc
            FROM fuel_metrics
            WHERE truck_id = %s
              AND mpg_current IS NOT NULL
              AND mpg_current > 2
              AND mpg_current < 12
              AND truck_status = 'MOVING'
              AND timestamp_utc > DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY timestamp_utc DESC
        """

        try:
            with self.db.cursor() as cursor:
                cursor.execute(query, (truck_id, period_days))
                results = cursor.fetchall()

                if len(results) < min_samples:
                    logger.warning(
                        f"Insufficient data for {truck_id}: {len(results)} samples"
                    )
                    return None

                mpg_values = [row["mpg_current"] for row in results]
                timestamps = [row["timestamp_utc"] for row in results]

                baseline_mpg = float(np.mean(mpg_values))
                std_dev = float(np.std(mpg_values))

                # Confidence based on sample size and consistency
                confidence = min(
                    1.0, len(results) / 100.0
                )  # Max confidence at 100+ samples
                if std_dev > 1.0:
                    confidence *= 0.8  # Reduce confidence if high variance

                return MPGBaseline(
                    truck_id=truck_id,
                    baseline_mpg=baseline_mpg,
                    period_start=min(timestamps),
                    period_end=max(timestamps),
                    sample_count=len(results),
                    std_dev=std_dev,
                    confidence=confidence,
                )

        except Exception as e:
            logger.error(f"Error calculating baseline for {truck_id}: {e}")
            return None

    def store_baseline(self, baseline: MPGBaseline) -> bool:
        """
        Store baseline in database

        Args:
            baseline: MPGBaseline to store

        Returns:
            True if stored successfully
        """
        # Create table if not exists
        create_table_query = """
            CREATE TABLE IF NOT EXISTS mpg_baselines (
                id INT AUTO_INCREMENT PRIMARY KEY,
                truck_id VARCHAR(20) NOT NULL,
                baseline_mpg DECIMAL(6,2) NOT NULL,
                period_start DATETIME NOT NULL,
                period_end DATETIME NOT NULL,
                sample_count INT NOT NULL,
                std_dev DECIMAL(6,2) NOT NULL,
                confidence DECIMAL(4,2) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                INDEX idx_truck_created (truck_id, created_at),
                INDEX idx_created (created_at)
            )
        """

        insert_query = """
            INSERT INTO mpg_baselines 
            (truck_id, baseline_mpg, period_start, period_end, sample_count, std_dev, confidence)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """

        try:
            with self.db.cursor() as cursor:
                cursor.execute(create_table_query)
                cursor.execute(
                    insert_query,
                    (
                        baseline.truck_id,
                        baseline.baseline_mpg,
                        baseline.period_start,
                        baseline.period_end,
                        baseline.sample_count,
                        baseline.std_dev,
                        baseline.confidence,
                    ),
                )

                logger.info(
                    f"Stored baseline for {baseline.truck_id}: {baseline.baseline_mpg:.2f} MPG"
                )
                return True

        except Exception as e:
            logger.error(f"Error storing baseline: {e}")
            return False

    def get_latest_baseline(self, truck_id: str) -> Optional[MPGBaseline]:
        """
        Get most recent baseline for truck

        Args:
            truck_id: Truck identifier

        Returns:
            MPGBaseline or None
        """
        query = """
            SELECT 
                truck_id, baseline_mpg, period_start, period_end,
                sample_count, std_dev, confidence
            FROM mpg_baselines
            WHERE truck_id = %s
            ORDER BY created_at DESC
            LIMIT 1
        """

        try:
            with self.db.cursor() as cursor:
                cursor.execute(query, (truck_id,))
                row = cursor.fetchone()

                if not row:
                    return None

                return MPGBaseline(
                    truck_id=row["truck_id"],
                    baseline_mpg=float(row["baseline_mpg"]),
                    period_start=row["period_start"],
                    period_end=row["period_end"],
                    sample_count=row["sample_count"],
                    std_dev=float(row["std_dev"]),
                    confidence=float(row["confidence"]),
                )

        except Exception as e:
            logger.error(f"Error getting baseline for {truck_id}: {e}")
            return None

    def check_degradation(
        self, truck_id: str, check_period_days: int = 3, threshold_pct: float = 5.0
    ) -> Optional[MPGDegradation]:
        """
        Check if truck MPG has degraded

        Args:
            truck_id: Truck identifier
            check_period_days: Days to check for degradation
            threshold_pct: Minimum degradation % to report

        Returns:
            MPGDegradation or None
        """
        # Get baseline
        baseline = self.get_latest_baseline(truck_id)
        if not baseline:
            logger.warning(f"No baseline found for {truck_id}")
            return None

        # Get recent MPG
        query = """
            SELECT 
                AVG(mpg_current) as current_mpg,
                COUNT(*) as sample_count,
                MIN(timestamp_utc) as period_start
            FROM fuel_metrics
            WHERE truck_id = %s
              AND mpg_current IS NOT NULL
              AND mpg_current > 2
              AND mpg_current < 12
              AND truck_status = 'MOVING'
              AND timestamp_utc > DATE_SUB(NOW(), INTERVAL %s DAY)
        """

        try:
            with self.db.cursor() as cursor:
                cursor.execute(query, (truck_id, check_period_days))
                row = cursor.fetchone()

                if not row or row["sample_count"] < 10:
                    logger.warning(f"Insufficient recent data for {truck_id}")
                    return None

                current_mpg = float(row["current_mpg"])
                degradation_pct = (
                    (baseline.baseline_mpg - current_mpg) / baseline.baseline_mpg
                ) * 100

                if degradation_pct < threshold_pct:
                    # No significant degradation
                    return None

                # Determine severity
                if degradation_pct >= 20:
                    severity = "CRITICAL"
                elif degradation_pct >= 15:
                    severity = "HIGH"
                elif degradation_pct >= 10:
                    severity = "MEDIUM"
                else:
                    severity = "LOW"

                return MPGDegradation(
                    truck_id=truck_id,
                    current_mpg=current_mpg,
                    baseline_mpg=baseline.baseline_mpg,
                    degradation_pct=degradation_pct,
                    days_declining=check_period_days,
                    severity=severity,
                    timestamp=datetime.utcnow(),
                )

        except Exception as e:
            logger.error(f"Error checking degradation for {truck_id}: {e}")
            return None

    def get_all_degradations(
        self, threshold_pct: float = 5.0, check_period_days: int = 3
    ) -> List[MPGDegradation]:
        """
        Check all trucks for degradation

        Args:
            threshold_pct: Minimum degradation % to report
            check_period_days: Days to check

        Returns:
            List of MPGDegradation objects
        """
        # Get all active trucks
        query = """
            SELECT DISTINCT truck_id
            FROM fuel_metrics
            WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 7 DAY)
              AND mpg_current IS NOT NULL
        """

        degradations = []

        try:
            with self.db.cursor() as cursor:
                cursor.execute(query)
                truck_ids = [row["truck_id"] for row in cursor.fetchall()]

                for truck_id in truck_ids:
                    degradation = self.check_degradation(
                        truck_id,
                        check_period_days=check_period_days,
                        threshold_pct=threshold_pct,
                    )
                    if degradation:
                        degradations.append(degradation)

                # Sort by severity and degradation %
                severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
                degradations.sort(
                    key=lambda x: (
                        severity_order.get(x.severity, 4),
                        -x.degradation_pct,
                    )
                )

        except Exception as e:
            logger.error(f"Error getting all degradations: {e}")

        return degradations

    def update_all_baselines(self, period_days: int = 30) -> Dict[str, bool]:
        """
        Update baselines for all active trucks

        Args:
            period_days: Days to use for baseline

        Returns:
            Dict mapping truck_id to success status
        """
        # Get active trucks
        query = """
            SELECT DISTINCT truck_id
            FROM fuel_metrics
            WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL %s DAY)
              AND mpg_current IS NOT NULL
        """

        results = {}

        try:
            with self.db.cursor() as cursor:
                cursor.execute(query, (period_days,))
                truck_ids = [row["truck_id"] for row in cursor.fetchall()]

                for truck_id in truck_ids:
                    baseline = self.calculate_baseline(truck_id, period_days)
                    if baseline:
                        success = self.store_baseline(baseline)
                        results[truck_id] = success
                    else:
                        results[truck_id] = False

                logger.info(f"Updated baselines for {len(results)} trucks")

        except Exception as e:
            logger.error(f"Error updating baselines: {e}")

        return results


# Singleton instance
_tracker_instance = None


def get_mpg_baseline_tracker() -> MPGBaselineTracker:
    """Get singleton tracker instance"""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = MPGBaselineTracker()
    return _tracker_instance
