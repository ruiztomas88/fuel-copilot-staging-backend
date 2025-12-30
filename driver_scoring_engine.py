"""
Driver Behavior Scoring Engine
Scores drivers 0-100 based on MPG efficiency, idle time, and driving patterns
Part of ML/AI Roadmap - Feature #4
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Optional

import numpy as np
import pymysql
from pymysql.cursors import DictCursor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventType(Enum):
    """Driver event types for scoring"""

    OVERSPEED = "overspeed"
    LONG_IDLE = "long_idle"
    HARSH_BRAKING = "harsh_braking"
    HARSH_ACCELERATION = "harsh_acceleration"
    LOW_MPG = "low_mpg"


@dataclass
class DriverScore:
    """Represents a driver's behavior score"""

    truck_id: str
    period_start: datetime
    period_end: datetime
    overall_score: float  # 0-100
    mpg_score: float  # 0-100
    idle_score: float  # 0-100
    consistency_score: float  # 0-100
    fleet_percentile: Optional[float] = None  # 0-100 (vs fleet)
    grade: str = ""  # A+, A, B+, B, C+, C, D, F

    def __post_init__(self):
        """Calculate grade based on overall score"""
        if self.grade == "":
            if self.overall_score >= 95:
                self.grade = "A+"
            elif self.overall_score >= 90:
                self.grade = "A"
            elif self.overall_score >= 85:
                self.grade = "B+"
            elif self.overall_score >= 80:
                self.grade = "B"
            elif self.overall_score >= 75:
                self.grade = "C+"
            elif self.overall_score >= 70:
                self.grade = "C"
            elif self.overall_score >= 60:
                self.grade = "D"
            else:
                self.grade = "F"

    def to_dict(self) -> dict:
        """Convert to dictionary"""
        return {
            "truck_id": self.truck_id,
            "period_start": (
                self.period_start.isoformat() if self.period_start else None
            ),
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "overall_score": round(self.overall_score, 1),
            "mpg_score": round(self.mpg_score, 1),
            "idle_score": round(self.idle_score, 1),
            "consistency_score": round(self.consistency_score, 1),
            "fleet_percentile": (
                round(self.fleet_percentile, 1) if self.fleet_percentile else None
            ),
            "grade": self.grade,
        }


class DriverScoringEngine:
    """
    Scores driver behavior based on fuel efficiency and driving patterns.

    Scoring Components:
    - MPG Score (40%): Compared to truck baseline and fleet
    - Idle Score (30%): Percentage of time spent idling
    - Consistency Score (30%): Variance in MPG (smooth driving = higher score)
    """

    def __init__(self, db_connection=None):
        """Initialize scoring engine"""
        if db_connection:
            self.db = db_connection
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

        # Scoring weights
        self.mpg_weight = 0.40
        self.idle_weight = 0.30
        self.consistency_weight = 0.30

        # Thresholds
        self.excellent_mpg_threshold = 1.15  # 15% above baseline
        self.good_mpg_threshold = 1.05  # 5% above baseline
        self.poor_mpg_threshold = 0.90  # 10% below baseline

        self.excellent_idle_threshold = 15.0  # <15% idle
        self.good_idle_threshold = 25.0  # <25% idle
        self.poor_idle_threshold = 40.0  # >40% idle

    def calculate_score(
        self, truck_id: str, period_days: int = 7, min_samples: int = 20
    ) -> Optional[DriverScore]:
        """Calculate driver score for a truck"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        # Get MPG and idle data
        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT 
                    mpg_current,
                    idle_hours_ecu / NULLIF(engine_hours, 0) * 100 as idle_pct
                FROM fuel_metrics
                WHERE truck_id = %s
                  AND timestamp_utc >= %s
                  AND timestamp_utc <= %s
                  AND mpg_current IS NOT NULL
                  AND mpg_current > 0
                  AND engine_hours IS NOT NULL
                ORDER BY timestamp_utc
            """,
                (truck_id, start_date, end_date),
            )

            rows = cursor.fetchall()

        if len(rows) < min_samples:
            logger.info(
                f"Insufficient data for {truck_id}: {len(rows)} < {min_samples}"
            )
            return None

        # Extract values
        mpg_values = [float(row["mpg_current"]) for row in rows if row["mpg_current"]]
        idle_values = [float(row["idle_pct"] or 0) for row in rows]

        if len(mpg_values) < min_samples:
            return None

        # Calculate component scores
        mpg_score = self._calculate_mpg_score(truck_id, mpg_values)
        idle_score = self._calculate_idle_score(idle_values)
        consistency_score = self._calculate_consistency_score(mpg_values)

        # Overall score (weighted average)
        overall_score = (
            mpg_score * self.mpg_weight
            + idle_score * self.idle_weight
            + consistency_score * self.consistency_weight
        )

        return DriverScore(
            truck_id=truck_id,
            period_start=start_date,
            period_end=end_date,
            overall_score=overall_score,
            mpg_score=mpg_score,
            idle_score=idle_score,
            consistency_score=consistency_score,
        )

    def _calculate_mpg_score(self, truck_id: str, mpg_values: List[float]) -> float:
        """Calculate MPG score (0-100) compared to baseline"""
        avg_mpg = np.mean(mpg_values)

        # Get truck baseline
        baseline_mpg = self._get_truck_baseline_mpg(truck_id)

        if baseline_mpg is None:
            baseline_mpg = self._get_fleet_average_mpg()

        if baseline_mpg is None or baseline_mpg == 0:
            baseline_mpg = 6.5  # Typical heavy truck MPG

        # Calculate ratio
        mpg_ratio = avg_mpg / baseline_mpg

        # Score based on ratio
        if mpg_ratio >= self.excellent_mpg_threshold:
            score = 90 + min((mpg_ratio - self.excellent_mpg_threshold) * 200, 10)
        elif mpg_ratio >= self.good_mpg_threshold:
            score = (
                75
                + (
                    (mpg_ratio - self.good_mpg_threshold)
                    / (self.excellent_mpg_threshold - self.good_mpg_threshold)
                )
                * 15
            )
        elif mpg_ratio >= 1.0:
            score = 60 + ((mpg_ratio - 1.0) / (self.good_mpg_threshold - 1.0)) * 15
        elif mpg_ratio >= self.poor_mpg_threshold:
            score = (
                40
                + (
                    (mpg_ratio - self.poor_mpg_threshold)
                    / (1.0 - self.poor_mpg_threshold)
                )
                * 20
            )
        else:
            score = max(0, 40 * mpg_ratio / self.poor_mpg_threshold)

        return min(100, max(0, score))

    def _calculate_idle_score(self, idle_values: List[float]) -> float:
        """Calculate idle time score (0-100)"""
        avg_idle = np.mean(idle_values)

        if avg_idle <= self.excellent_idle_threshold:
            score = 90 + min(
                (self.excellent_idle_threshold - avg_idle)
                / self.excellent_idle_threshold
                * 10,
                10,
            )
        elif avg_idle <= self.good_idle_threshold:
            score = (
                75
                + (
                    (self.good_idle_threshold - avg_idle)
                    / (self.good_idle_threshold - self.excellent_idle_threshold)
                )
                * 15
            )
        elif avg_idle <= self.poor_idle_threshold:
            score = (
                50
                + (
                    (self.poor_idle_threshold - avg_idle)
                    / (self.poor_idle_threshold - self.good_idle_threshold)
                )
                * 25
            )
        else:
            score = max(0, 50 - (avg_idle - self.poor_idle_threshold) * 1.5)

        return min(100, max(0, score))

    def _calculate_consistency_score(self, mpg_values: List[float]) -> float:
        """Calculate driving consistency score (0-100)"""
        if len(mpg_values) < 2:
            return 50.0

        mean_mpg = np.mean(mpg_values)
        std_mpg = np.std(mpg_values)

        # Coefficient of variation
        cv = (std_mpg / mean_mpg) * 100 if mean_mpg > 0 else 100

        if cv <= 10:
            score = 90 + min((10 - cv) / 10 * 10, 10)
        elif cv <= 20:
            score = 75 + ((20 - cv) / 10) * 15
        elif cv <= 30:
            score = 50 + ((30 - cv) / 10) * 25
        else:
            score = max(0, 50 - (cv - 30) * 1.5)

        return min(100, max(0, score))

    def _get_truck_baseline_mpg(self, truck_id: str) -> Optional[float]:
        """Get truck's baseline MPG"""
        try:
            with self.db.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT baseline_mpg
                    FROM mpg_baselines
                    WHERE truck_id = %s
                    ORDER BY created_at DESC
                    LIMIT 1
                """,
                    (truck_id,),
                )

                result = cursor.fetchone()
                return float(result["baseline_mpg"]) if result else None
        except (pymysql.Error, KeyError, TypeError, ValueError) as e:
            logger.debug(f"Error getting baseline MPG: {e}")
            return None

    def _get_fleet_average_mpg(self) -> Optional[float]:
        """Get fleet average MPG"""
        try:
            with self.db.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT AVG(mpg_current) as fleet_avg
                    FROM fuel_metrics
                    WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                      AND mpg_current IS NOT NULL
                      AND mpg_current > 0
                """
                )

                result = cursor.fetchone()
                return float(result["fleet_avg"]) if result else None
        except (pymysql.Error, KeyError, TypeError, ValueError) as e:
            logger.debug(f"Error getting fleet average MPG: {e}")
            return None

    def get_fleet_scores(
        self, period_days: int = 7, min_score: float = 0.0
    ) -> Dict[str, DriverScore]:
        """Get scores for entire fleet"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=period_days)

        with self.db.cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT truck_id
                FROM fuel_metrics
                WHERE timestamp_utc >= %s
                  AND mpg_current IS NOT NULL
                ORDER BY truck_id
            """,
                (start_date,),
            )

            truck_ids = [row["truck_id"] for row in cursor.fetchall()]

        fleet_scores = {}
        all_scores = []

        for truck_id in truck_ids:
            score = self.calculate_score(truck_id, period_days=period_days)
            if score and score.overall_score >= min_score:
                fleet_scores[truck_id] = score
                all_scores.append(score.overall_score)

        # Calculate percentiles
        if len(all_scores) > 0:
            all_scores_sorted = sorted(all_scores)
            for truck_id, score in fleet_scores.items():
                percentile = (
                    all_scores_sorted.index(score.overall_score)
                    / len(all_scores_sorted)
                ) * 100
                score.fleet_percentile = percentile

        return fleet_scores

    def store_score(self, score: DriverScore) -> bool:
        """Store driver score in database"""
        try:
            with self.db.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS driver_scores (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        truck_id VARCHAR(50) NOT NULL,
                        period_start DATETIME NOT NULL,
                        period_end DATETIME NOT NULL,
                        overall_score FLOAT NOT NULL,
                        mpg_score FLOAT NOT NULL,
                        idle_score FLOAT NOT NULL,
                        consistency_score FLOAT NOT NULL,
                        fleet_percentile FLOAT,
                        grade VARCHAR(5),
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_truck_period (truck_id, period_end),
                        INDEX idx_score (overall_score),
                        INDEX idx_grade (grade)
                    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
                )

            with self.db.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO driver_scores
                    (truck_id, period_start, period_end, overall_score, mpg_score, 
                     idle_score, consistency_score, fleet_percentile, grade)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        score.truck_id,
                        score.period_start,
                        score.period_end,
                        score.overall_score,
                        score.mpg_score,
                        score.idle_score,
                        score.consistency_score,
                        score.fleet_percentile,
                        score.grade,
                    ),
                )

            return True
        except Exception as e:
            logger.error(f"Error storing score: {e}")
            return False


# Singleton
_driver_scoring_engine_instance = None


def get_driver_scoring_engine(db_connection=None) -> DriverScoringEngine:
    """Get singleton instance"""
    global _driver_scoring_engine_instance
    if _driver_scoring_engine_instance is None:
        _driver_scoring_engine_instance = DriverScoringEngine(
            db_connection=db_connection
        )
    return _driver_scoring_engine_instance


# Alias for compatibility
def get_scoring_engine(db_connection=None) -> DriverScoringEngine:
    """Alias for get_driver_scoring_engine"""
    return get_driver_scoring_engine(db_connection)
