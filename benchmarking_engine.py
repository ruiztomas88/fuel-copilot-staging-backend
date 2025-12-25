"""
Benchmarking Engine v1.0.0
Compares truck performance against peers and fleet averages

Features:
- Peer group identification (same make/model/year)
- MPG benchmarking with percentiles
- Idle time comparison
- Cost per mile analysis
- Fuel efficiency trends
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
class PeerGroup:
    """Defines a peer group for benchmarking"""

    make: Optional[str]
    model: Optional[str]
    year: Optional[int]
    truck_ids: List[str]

    def __str__(self):
        if self.make and self.model and self.year:
            return f"{self.make} {self.model} {self.year}"
        return "Unknown peer group"


@dataclass
class BenchmarkResult:
    """Result of benchmarking analysis"""

    truck_id: str
    metric_name: str
    actual_value: float
    benchmark_value: float  # Median of peers
    percentile: float  # 0-100, where truck ranks vs peers
    peer_count: int
    peer_group: str
    deviation_pct: float  # % difference from benchmark
    performance_tier: str  # TOP_10, TOP_25, AVERAGE, BELOW_AVERAGE, BOTTOM_10
    confidence: float  # 0-1, based on peer count and data quality

    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "metric_name": self.metric_name,
            "actual_value": round(self.actual_value, 2),
            "benchmark_value": round(self.benchmark_value, 2),
            "percentile": round(self.percentile, 1),
            "peer_count": self.peer_count,
            "peer_group": self.peer_group,
            "deviation_pct": round(self.deviation_pct, 1),
            "performance_tier": self.performance_tier,
            "confidence": round(self.confidence, 2),
        }


class BenchmarkingEngine:
    """
    Engine for benchmarking truck performance

    Usage:
        engine = BenchmarkingEngine()
        result = engine.benchmark_mpg("RA9250", period_days=30)
        print(f"MPG: {result.actual_value:.1f} vs peer median: {result.benchmark_value:.1f}")
        print(f"Percentile: {result.percentile}% (Tier: {result.performance_tier})")
    """

    def __init__(self, db_connection=None):
        """
        Initialize benchmarking engine

        Args:
            db_connection: Optional database connection (uses default if not provided)
        """
        if db_connection is not None:
            self.db = db_connection
            self._should_close_db = False
        else:
            # Create new pymysql connection
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
            except Exception as e:
                logger.debug(f"Error closing database: {e}")

    def identify_peer_group(self, truck_id: str) -> PeerGroup:
        """
        Identify peer group for a truck (same make/model/year)

        Args:
            truck_id: Truck identifier

        Returns:
            PeerGroup with matching trucks
        """
        query = """
            SELECT make, model, year
            FROM trucks
            WHERE truck_id = %s
        """

        try:
            with self.db.cursor() as cursor:
                cursor.execute(query, (truck_id,))
                result = cursor.fetchone()

                if not result:
                    logger.warning(f"Truck {truck_id} not found in trucks table")
                    return PeerGroup(None, None, None, [truck_id])

                make = result["make"]
                model = result["model"]
                year = result["year"]

                # Find peers with same make/model/year
                peer_query = """
                    SELECT truck_id
                    FROM trucks
                    WHERE is_active = 1
                """

                params = []

                if make:
                    peer_query += " AND make = %s"
                    params.append(make)
                if model:
                    peer_query += " AND model = %s"
                    params.append(model)
                if year:
                    peer_query += " AND year = %s"
                    params.append(year)

                cursor.execute(peer_query, params)
                peer_ids = [row["truck_id"] for row in cursor.fetchall()]

                return PeerGroup(make=make, model=model, year=year, truck_ids=peer_ids)

        except Exception as e:
            logger.error(f"Error identifying peer group for {truck_id}: {e}")
            return PeerGroup(None, None, None, [truck_id])

    def get_mpg_data(
        self, truck_ids: List[str], period_days: int = 30, min_samples: int = 10
    ) -> Dict[str, float]:
        """
        Get average MPG for multiple trucks

        Args:
            truck_ids: List of truck identifiers
            period_days: Number of days to analyze
            min_samples: Minimum samples required for valid average

        Returns:
            Dict mapping truck_id to average MPG
        """
        if not truck_ids:
            return {}

        placeholders = ",".join(["%s"] * len(truck_ids))
        query = f"""
            SELECT 
                truck_id,
                AVG(mpg_current) as avg_mpg,
                COUNT(*) as sample_count
            FROM fuel_metrics
            WHERE truck_id IN ({placeholders})
              AND mpg_current IS NOT NULL
              AND mpg_current > 2  -- Filter outliers
              AND mpg_current < 12
              AND truck_status = 'MOVING'
              AND timestamp_utc > DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY truck_id
            HAVING sample_count >= %s
        """

        try:
            with self.db.cursor() as cursor:
                cursor.execute(query, truck_ids + [period_days, min_samples])
                results = cursor.fetchall()

                return {row["truck_id"]: float(row["avg_mpg"]) for row in results}

        except Exception as e:
            logger.error(f"Error getting MPG data: {e}")
            return {}

    def get_idle_time_pct(
        self, truck_ids: List[str], period_days: int = 30
    ) -> Dict[str, float]:
        """
        Get idle time percentage for trucks

        Args:
            truck_ids: List of truck identifiers
            period_days: Number of days to analyze

        Returns:
            Dict mapping truck_id to idle time percentage
        """
        if not truck_ids:
            return {}

        placeholders = ",".join(["%s"] * len(truck_ids))
        query = f"""
            SELECT 
                truck_id,
                SUM(CASE WHEN truck_status = 'IDLE' THEN 1 ELSE 0 END) * 100.0 / COUNT(*) as idle_pct
            FROM fuel_metrics
            WHERE truck_id IN ({placeholders})
              AND timestamp_utc > DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY truck_id
        """

        try:
            with self.db.cursor() as cursor:
                cursor.execute(query, truck_ids + [period_days])
                results = cursor.fetchall()

                return {row["truck_id"]: float(row["idle_pct"]) for row in results}

        except Exception as e:
            logger.error(f"Error getting idle time data: {e}")
            return {}

    def get_cost_per_mile(
        self, truck_ids: List[str], period_days: int = 30, min_samples: int = 10
    ) -> Dict[str, float]:
        """
        Get average cost per mile for trucks

        Args:
            truck_ids: List of truck identifiers
            period_days: Number of days to analyze
            min_samples: Minimum samples required

        Returns:
            Dict mapping truck_id to average cost per mile
        """
        if not truck_ids:
            return {}

        placeholders = ",".join(["%s"] * len(truck_ids))
        query = f"""
            SELECT 
                truck_id,
                AVG(cost_per_mile) as avg_cost,
                COUNT(*) as sample_count
            FROM fuel_metrics
            WHERE truck_id IN ({placeholders})
              AND cost_per_mile IS NOT NULL
              AND cost_per_mile > 0
              AND cost_per_mile < 5  -- Filter outliers
              AND timestamp_utc > DATE_SUB(NOW(), INTERVAL %s DAY)
            GROUP BY truck_id
            HAVING sample_count >= %s
        """

        try:
            with self.db.cursor() as cursor:
                cursor.execute(query, truck_ids + [period_days, min_samples])
                results = cursor.fetchall()

                return {row["truck_id"]: float(row["avg_cost"]) for row in results}

        except Exception as e:
            logger.error(f"Error getting cost per mile data: {e}")
            return {}

    def calculate_percentile(self, value: float, peer_values: List[float]) -> float:
        """
        Calculate percentile rank of value among peers

        Args:
            value: The value to rank
            peer_values: List of peer values

        Returns:
            Percentile (0-100)
        """
        if not peer_values:
            return 50.0

        count_below = sum(1 for v in peer_values if v < value)
        percentile = (count_below / len(peer_values)) * 100

        return percentile

    def get_performance_tier(self, percentile: float, metric_name: str) -> str:
        """
        Classify performance into tier

        Args:
            percentile: Percentile rank (0-100)
            metric_name: Name of metric (for direction - higher is better for MPG)

        Returns:
            Performance tier string
        """
        # For MPG, higher is better
        # For idle_pct and cost_per_mile, lower is better
        reverse_metrics = ["idle_time_pct", "cost_per_mile"]

        if metric_name in reverse_metrics:
            # Reverse the percentile for metrics where lower is better
            percentile = 100 - percentile

        if percentile >= 90:
            return "TOP_10"
        elif percentile >= 75:
            return "TOP_25"
        elif percentile >= 50:
            return "AVERAGE"
        elif percentile >= 25:
            return "BELOW_AVERAGE"
        else:
            return "BOTTOM_25"

    def benchmark_metric(
        self,
        truck_id: str,
        metric_name: str,
        period_days: int = 30,
        min_samples: int = 10,
    ) -> Optional[BenchmarkResult]:
        """
        Benchmark a specific metric for a truck

        Args:
            truck_id: Truck identifier
            metric_name: Metric to benchmark (mpg, idle_time_pct, cost_per_mile)
            period_days: Number of days to analyze
            min_samples: Minimum samples for valid comparison

        Returns:
            BenchmarkResult or None if insufficient data
        """
        # Identify peer group
        peer_group = self.identify_peer_group(truck_id)

        if len(peer_group.truck_ids) < 2:
            logger.warning(f"No peers found for {truck_id}")
            return None

        # Get data for metric
        if metric_name == "mpg":
            data = self.get_mpg_data(peer_group.truck_ids, period_days, min_samples)
        elif metric_name == "idle_time_pct":
            data = self.get_idle_time_pct(peer_group.truck_ids, period_days)
        elif metric_name == "cost_per_mile":
            data = self.get_cost_per_mile(
                peer_group.truck_ids, period_days, min_samples
            )
        else:
            logger.error(f"Unknown metric: {metric_name}")
            return None

        if truck_id not in data:
            logger.warning(f"No data for {truck_id} on metric {metric_name}")
            return None

        actual_value = data[truck_id]
        peer_values = [v for k, v in data.items() if k != truck_id]

        if len(peer_values) < 1:
            logger.warning(f"Insufficient peer data for {truck_id}")
            return None

        # Calculate benchmark
        benchmark_value = float(np.median(peer_values))
        percentile = self.calculate_percentile(actual_value, peer_values)
        deviation_pct = ((actual_value - benchmark_value) / benchmark_value) * 100
        performance_tier = self.get_performance_tier(percentile, metric_name)

        # Calculate confidence based on peer count and data quality
        confidence = min(1.0, len(peer_values) / 10)  # Full confidence with 10+ peers

        return BenchmarkResult(
            truck_id=truck_id,
            metric_name=metric_name,
            actual_value=actual_value,
            benchmark_value=benchmark_value,
            percentile=percentile,
            peer_count=len(peer_values),
            peer_group=str(peer_group),
            deviation_pct=deviation_pct,
            performance_tier=performance_tier,
            confidence=confidence,
        )

    def benchmark_truck(
        self, truck_id: str, period_days: int = 30
    ) -> Dict[str, BenchmarkResult]:
        """
        Benchmark all metrics for a truck

        Args:
            truck_id: Truck identifier
            period_days: Number of days to analyze

        Returns:
            Dict mapping metric name to BenchmarkResult
        """
        results = {}

        for metric in ["mpg", "idle_time_pct", "cost_per_mile"]:
            result = self.benchmark_metric(truck_id, metric, period_days)
            if result:
                results[metric] = result

        return results

    def get_fleet_outliers(
        self,
        metric_name: str = "mpg",
        period_days: int = 30,
        threshold_percentile: float = 10.0,
    ) -> List[BenchmarkResult]:
        """
        Find fleet outliers (trucks performing significantly worse than peers)

        Args:
            metric_name: Metric to analyze
            period_days: Number of days to analyze
            threshold_percentile: Percentile threshold (trucks below this are outliers)

        Returns:
            List of BenchmarkResults for outlier trucks
        """
        # Get all active trucks
        query = "SELECT truck_id FROM trucks WHERE is_active = 1"

        outliers = []

        try:
            with self.db.cursor() as cursor:
                cursor.execute(query)
                truck_ids = [row["truck_id"] for row in cursor.fetchall()]

                for truck_id in truck_ids:
                    result = self.benchmark_metric(truck_id, metric_name, period_days)

                    if result and result.percentile <= threshold_percentile:
                        outliers.append(result)

                # Sort by percentile (worst first)
                outliers.sort(key=lambda x: x.percentile)

        except Exception as e:
            logger.error(f"Error finding outliers: {e}")

        return outliers


# Singleton instance
_engine_instance = None


def get_benchmarking_engine() -> BenchmarkingEngine:
    """Get singleton benchmarking engine instance"""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = BenchmarkingEngine()
    return _engine_instance
