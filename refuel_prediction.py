"""
Refuel Prediction Engine v3.12.21
ML-based prediction of next refuel timing

Addresses audit item #17: Predicción próximo refuel

Features:
- Predict when truck will need refueling based on consumption history
- Consider day-of-week patterns
- Account for route/driver variations
- Provide confidence intervals
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass
import statistics
import math
from contextlib import contextmanager
import os

import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE CONNECTION
# =============================================================================
def _get_db_config() -> Dict:
    """Get database configuration from environment."""
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "fuel_admin"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "fuel_copilot"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": True,
    }


@contextmanager
def get_db_connection():
    """Get database connection with automatic cleanup."""
    conn = None
    try:
        conn = pymysql.connect(**_get_db_config())
        yield conn
    finally:
        if conn:
            conn.close()


# =============================================================================
# PREDICTION DATA CLASSES
# =============================================================================
@dataclass
class ConsumptionProfile:
    """Historical consumption profile for a truck."""

    truck_id: str
    avg_consumption_gph: float  # Gallons per hour when running
    avg_consumption_gpd: float  # Gallons per day
    avg_daily_miles: float
    avg_mpg: float
    std_consumption_gpd: float  # Standard deviation
    weekday_factor: Dict[int, float]  # 0=Monday, 6=Sunday
    sample_days: int
    last_updated: datetime


@dataclass
class RefuelPrediction:
    """Prediction of next refuel."""

    truck_id: str
    current_fuel_pct: float
    current_fuel_gal: float
    tank_capacity_gal: float

    # Predictions
    predicted_empty_time: datetime
    predicted_refuel_needed_time: datetime  # When to refuel (at 20%)
    hours_until_empty: float
    hours_until_refuel_needed: float

    # Confidence
    confidence: float  # 0-1
    confidence_interval_hours: Tuple[float, float]  # Low, High

    # Factors
    consumption_rate_gph: float
    daily_consumption_gal: float
    is_weekend: bool

    # Recommendations
    recommended_refuel_location: Optional[str]
    recommended_refuel_amount_gal: float
    estimated_cost: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "truck_id": self.truck_id,
            "current_fuel": {
                "percent": round(self.current_fuel_pct, 1),
                "gallons": round(self.current_fuel_gal, 1),
                "tank_capacity": self.tank_capacity_gal,
            },
            "prediction": {
                "empty_time": self.predicted_empty_time.isoformat(),
                "refuel_needed_time": self.predicted_refuel_needed_time.isoformat(),
                "hours_until_empty": round(self.hours_until_empty, 1),
                "hours_until_refuel_needed": round(self.hours_until_refuel_needed, 1),
            },
            "confidence": {
                "value": round(self.confidence, 2),
                "interval_hours": {
                    "low": round(self.confidence_interval_hours[0], 1),
                    "high": round(self.confidence_interval_hours[1], 1),
                },
            },
            "consumption": {
                "rate_gph": round(self.consumption_rate_gph, 2),
                "daily_gal": round(self.daily_consumption_gal, 1),
                "is_weekend": self.is_weekend,
            },
            "recommendations": {
                "refuel_amount_gal": round(self.recommended_refuel_amount_gal, 1),
                "estimated_cost": round(self.estimated_cost, 2),
                "suggested_location": self.recommended_refuel_location,
            },
        }


# =============================================================================
# REFUEL PREDICTION ENGINE
# =============================================================================
class RefuelPredictionEngine:
    """
    ML-based refuel prediction using historical consumption patterns.

    Uses weighted moving average with:
    - Recent data weighted higher
    - Day-of-week adjustments
    - Driver/route variations
    """

    # Fuel price per gallon (should come from settings)
    FUEL_PRICE = float(os.getenv("FUEL_PRICE_PER_GALLON", "3.50"))

    # Refuel threshold (recommend refuel at this %)
    REFUEL_THRESHOLD_PCT = 20.0

    # Minimum samples for reliable prediction
    MIN_SAMPLES = 7

    def __init__(self):
        self._consumption_cache: Dict[str, ConsumptionProfile] = {}
        self._cache_ttl = timedelta(hours=1)

    def predict_refuel(
        self,
        truck_id: str,
        current_fuel_pct: float,
        tank_capacity_gal: float = 200.0,
    ) -> Optional[RefuelPrediction]:
        """
        Predict when truck will need refueling.

        Args:
            truck_id: Truck identifier
            current_fuel_pct: Current fuel level (0-100)
            tank_capacity_gal: Tank capacity in gallons

        Returns:
            RefuelPrediction or None if insufficient data
        """
        # Get consumption profile
        profile = self._get_consumption_profile(truck_id)

        if not profile or profile.sample_days < self.MIN_SAMPLES:
            logger.warning(
                f"Insufficient data for {truck_id}: "
                f"{profile.sample_days if profile else 0} days"
            )
            return None

        # Current fuel in gallons
        current_fuel_gal = current_fuel_pct * tank_capacity_gal / 100

        # Fuel until empty and until refuel threshold
        fuel_until_empty = current_fuel_gal
        fuel_until_refuel = current_fuel_gal - (
            self.REFUEL_THRESHOLD_PCT * tank_capacity_gal / 100
        )
        fuel_until_refuel = max(0, fuel_until_refuel)

        # Get day-of-week factor
        now = datetime.now(timezone.utc)
        weekday = now.weekday()
        is_weekend = weekday >= 5

        # Adjust consumption rate for day of week
        weekday_factor = profile.weekday_factor.get(weekday, 1.0)
        adjusted_consumption_gph = profile.avg_consumption_gph * weekday_factor

        # Calculate hours until events
        if adjusted_consumption_gph > 0:
            hours_until_empty = fuel_until_empty / adjusted_consumption_gph
            hours_until_refuel = fuel_until_refuel / adjusted_consumption_gph
        else:
            # Truck not consuming fuel (parked?)
            hours_until_empty = 999
            hours_until_refuel = 999

        # Predicted times
        predicted_empty = now + timedelta(hours=hours_until_empty)
        predicted_refuel_needed = now + timedelta(hours=hours_until_refuel)

        # Confidence calculation
        # Based on: sample size, variation, recency of data
        confidence = self._calculate_confidence(profile, hours_until_empty)

        # Confidence interval (±1 std dev)
        std_factor = (
            profile.std_consumption_gpd / profile.avg_consumption_gpd
            if profile.avg_consumption_gpd > 0
            else 0.3
        )
        interval_low = hours_until_empty * (1 - std_factor)
        interval_high = hours_until_empty * (1 + std_factor)

        # Recommendations
        recommended_amount = tank_capacity_gal - current_fuel_gal  # Fill up
        estimated_cost = recommended_amount * self.FUEL_PRICE

        return RefuelPrediction(
            truck_id=truck_id,
            current_fuel_pct=current_fuel_pct,
            current_fuel_gal=current_fuel_gal,
            tank_capacity_gal=tank_capacity_gal,
            predicted_empty_time=predicted_empty,
            predicted_refuel_needed_time=predicted_refuel_needed,
            hours_until_empty=hours_until_empty,
            hours_until_refuel_needed=hours_until_refuel,
            confidence=confidence,
            confidence_interval_hours=(interval_low, interval_high),
            consumption_rate_gph=adjusted_consumption_gph,
            daily_consumption_gal=adjusted_consumption_gph * 24,
            is_weekend=is_weekend,
            recommended_refuel_location=None,  # TODO: Integrate fuel station API
            recommended_refuel_amount_gal=recommended_amount,
            estimated_cost=estimated_cost,
        )

    def predict_fleet(
        self,
        carrier_id: Optional[str] = None,
    ) -> List[Dict]:
        """
        Get refuel predictions for entire fleet.

        Returns trucks sorted by urgency (hours until refuel needed).
        """
        trucks = self._get_fleet_status(carrier_id)

        predictions = []
        for truck in trucks:
            try:
                pred = self.predict_refuel(
                    truck_id=truck["truck_id"],
                    current_fuel_pct=truck.get("fuel_pct", 50),
                    tank_capacity_gal=truck.get("tank_capacity", 200),
                )
                if pred:
                    predictions.append(pred.to_dict())
            except Exception as e:
                logger.error(f"Error predicting for {truck['truck_id']}: {e}")

        # Sort by urgency
        predictions.sort(key=lambda p: p["prediction"]["hours_until_refuel_needed"])

        return predictions

    def _get_consumption_profile(self, truck_id: str) -> Optional[ConsumptionProfile]:
        """Get or build consumption profile for truck."""
        # Check cache
        cached = self._consumption_cache.get(truck_id)
        if cached:
            if datetime.now(timezone.utc) - cached.last_updated < self._cache_ttl:
                return cached

        # Build from database
        profile = self._build_consumption_profile(truck_id)

        if profile:
            self._consumption_cache[truck_id] = profile

        return profile

    def _build_consumption_profile(self, truck_id: str) -> Optional[ConsumptionProfile]:
        """Build consumption profile from historical data."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    # Get daily consumption data for last 30 days
                    cursor.execute(
                        """
                        SELECT 
                            DATE(timestamp_utc) as day,
                            DAYOFWEEK(timestamp_utc) as dow,
                            SUM(consumption_gph * 0.5) as daily_gallons,
                            SUM(mileage_delta) as daily_miles,
                            AVG(mpg_current) as avg_mpg,
                            COUNT(*) as samples
                        FROM fuel_metrics
                        WHERE truck_id = %s
                          AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                          AND consumption_gph IS NOT NULL
                          AND consumption_gph > 0
                        GROUP BY DATE(timestamp_utc), DAYOFWEEK(timestamp_utc)
                        ORDER BY day DESC
                        """,
                        (truck_id,),
                    )
                    rows = cursor.fetchall()

                    if not rows:
                        return None

                    # Calculate averages
                    daily_consumptions = [
                        r["daily_gallons"] or 0 for r in rows if r["daily_gallons"]
                    ]
                    daily_miles = [
                        r["daily_miles"] or 0 for r in rows if r["daily_miles"]
                    ]
                    mpgs = [
                        r["avg_mpg"] or 0
                        for r in rows
                        if r["avg_mpg"] and r["avg_mpg"] > 0
                    ]

                    if not daily_consumptions:
                        return None

                    avg_consumption_gpd = statistics.mean(daily_consumptions)
                    std_consumption_gpd = (
                        statistics.stdev(daily_consumptions)
                        if len(daily_consumptions) > 1
                        else avg_consumption_gpd * 0.2
                    )

                    # Calculate weekday factors
                    weekday_totals: Dict[int, List[float]] = {i: [] for i in range(7)}
                    for row in rows:
                        # MySQL DAYOFWEEK: 1=Sunday, 2=Monday, ...
                        dow = (row["dow"] - 2) % 7  # Convert to 0=Monday
                        if row["daily_gallons"]:
                            weekday_totals[dow].append(row["daily_gallons"])

                    weekday_factor = {}
                    for dow, values in weekday_totals.items():
                        if values:
                            weekday_factor[dow] = (
                                statistics.mean(values) / avg_consumption_gpd
                            )
                        else:
                            weekday_factor[dow] = 1.0

                    return ConsumptionProfile(
                        truck_id=truck_id,
                        avg_consumption_gph=avg_consumption_gpd / 24,  # Approximate
                        avg_consumption_gpd=avg_consumption_gpd,
                        avg_daily_miles=(
                            statistics.mean(daily_miles) if daily_miles else 0
                        ),
                        avg_mpg=(
                            statistics.mean(mpgs) if mpgs else 5.7
                        ),  # v3.12.31: updated baseline
                        std_consumption_gpd=std_consumption_gpd,
                        weekday_factor=weekday_factor,
                        sample_days=len(rows),
                        last_updated=datetime.now(timezone.utc),
                    )

        except Exception as e:
            logger.error(f"Error building consumption profile for {truck_id}: {e}")
            return None

    def _calculate_confidence(
        self,
        profile: ConsumptionProfile,
        hours_predicted: float,
    ) -> float:
        """
        Calculate prediction confidence.

        Factors:
        - Sample size (more = higher)
        - Variation (less = higher)
        - Prediction horizon (shorter = higher)
        """
        # Sample size factor (0.5 at MIN_SAMPLES, 0.9 at 30 samples)
        sample_factor = min(0.9, 0.5 + (profile.sample_days - self.MIN_SAMPLES) * 0.02)

        # Variation factor (lower CV = higher confidence)
        cv = (
            profile.std_consumption_gpd / profile.avg_consumption_gpd
            if profile.avg_consumption_gpd > 0
            else 0.3
        )
        variation_factor = max(0.5, 1.0 - cv)

        # Horizon factor (longer predictions = lower confidence)
        horizon_factor = max(0.5, 1.0 - (hours_predicted / 168))  # 1 week = 168 hours

        # Combine factors
        confidence = sample_factor * variation_factor * horizon_factor

        return min(0.95, max(0.1, confidence))

    def _get_fleet_status(self, carrier_id: Optional[str] = None) -> List[Dict]:
        """Get current fuel status for all trucks."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    where = ""
                    params = []

                    if carrier_id and carrier_id != "*":
                        where = "WHERE carrier_id = %s"
                        params = [carrier_id]

                    cursor.execute(
                        f"""
                        SELECT 
                            truck_id,
                            carrier_id,
                            estimated_pct as fuel_pct,
                            200 as tank_capacity
                        FROM fuel_metrics
                        WHERE (truck_id, timestamp_utc) IN (
                            SELECT truck_id, MAX(timestamp_utc)
                            FROM fuel_metrics
                            {where}
                            GROUP BY truck_id
                        )
                        """,
                        params,
                    )
                    return list(cursor.fetchall())

        except Exception as e:
            logger.error(f"Error getting fleet status: {e}")
            return []

    # =========================================================================
    # HISTORICAL ANALYSIS
    # =========================================================================
    def get_refuel_history(
        self,
        truck_id: str,
        days: int = 30,
    ) -> List[Dict]:
        """Get refuel event history for analysis."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT 
                            timestamp_utc,
                            fuel_before_pct,
                            fuel_after_pct,
                            gallons_added,
                            location_name,
                            confidence
                        FROM refuel_events
                        WHERE truck_id = %s
                          AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s DAY)
                        ORDER BY timestamp_utc DESC
                        """,
                        (truck_id, days),
                    )
                    return list(cursor.fetchall())

        except Exception as e:
            logger.error(f"Error getting refuel history: {e}")
            return []

    def get_consumption_trend(
        self,
        truck_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get consumption trend analysis."""
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT 
                            DATE(timestamp_utc) as date,
                            SUM(consumption_gph * 0.5) as daily_gallons,
                            SUM(mileage_delta) as daily_miles,
                            AVG(mpg_current) as avg_mpg
                        FROM fuel_metrics
                        WHERE truck_id = %s
                          AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s DAY)
                        GROUP BY DATE(timestamp_utc)
                        ORDER BY date
                        """,
                        (truck_id, days),
                    )
                    rows = list(cursor.fetchall())

                    if not rows:
                        return {"error": "No data available"}

                    # Calculate trend
                    gallons = [r["daily_gallons"] or 0 for r in rows]

                    # Simple linear regression for trend
                    n = len(gallons)
                    if n >= 3:
                        x_mean = (n - 1) / 2
                        y_mean = statistics.mean(gallons)

                        numerator = sum(
                            (i - x_mean) * (g - y_mean) for i, g in enumerate(gallons)
                        )
                        denominator = sum((i - x_mean) ** 2 for i in range(n))

                        slope = numerator / denominator if denominator != 0 else 0
                        trend = (
                            "increasing"
                            if slope > 0.5
                            else "decreasing" if slope < -0.5 else "stable"
                        )
                    else:
                        trend = "insufficient_data"
                        slope = 0

                    return {
                        "truck_id": truck_id,
                        "period_days": days,
                        "data_points": len(rows),
                        "daily_data": [
                            {
                                "date": r["date"].isoformat() if r["date"] else None,
                                "gallons": round(r["daily_gallons"] or 0, 1),
                                "miles": round(r["daily_miles"] or 0, 1),
                                "mpg": round(r["avg_mpg"] or 0, 1),
                            }
                            for r in rows
                        ],
                        "summary": {
                            "avg_daily_gallons": round(statistics.mean(gallons), 1),
                            "max_daily_gallons": round(max(gallons), 1),
                            "min_daily_gallons": round(min(gallons), 1),
                            "trend": trend,
                            "trend_slope": round(slope, 3),
                        },
                    }

        except Exception as e:
            logger.error(f"Error getting consumption trend: {e}")
            return {"error": str(e)}


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================
_prediction_engine: Optional[RefuelPredictionEngine] = None


def get_prediction_engine() -> RefuelPredictionEngine:
    """Get or create RefuelPredictionEngine singleton."""
    global _prediction_engine
    if _prediction_engine is None:
        _prediction_engine = RefuelPredictionEngine()
    return _prediction_engine
