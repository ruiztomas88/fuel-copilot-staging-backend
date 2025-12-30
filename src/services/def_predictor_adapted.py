"""
DEF Predictor Service - ADAPTED for fuel_copilot_local

Predicts DEF depletion based on consumption patterns.
Uses actual truck data from fuel_metrics.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class DEFPredictor:
    """Predicts DEF depletion and generates warnings."""

    # Default configuration for Class 8 trucks
    DEFAULT_TANK_CAPACITY_LITERS = 75
    DEFAULT_DEF_PCT_OF_DIESEL = 2.5  # DEF is ~2.5% of diesel consumption
    DERATE_THRESHOLD_PCT = 5
    WARNING_THRESHOLD_PCT = 15
    GALLONS_TO_LITERS = 3.785

    def __init__(
        self,
        tank_capacity_liters: float = DEFAULT_TANK_CAPACITY_LITERS,
        def_pct_of_diesel: float = DEFAULT_DEF_PCT_OF_DIESEL,
    ):
        """Initialize DEF Predictor."""
        self.tank_capacity_liters = tank_capacity_liters
        self.def_pct_of_diesel = def_pct_of_diesel
        logger.info(f"DEFPredictor initialized (tank: {tank_capacity_liters}L)")

    def predict_def_depletion(
        self,
        truck_id: str,
        current_level_pct: Optional[float],
        daily_miles: Optional[float] = None,
        avg_mpg: Optional[float] = None,
        avg_consumption_gph: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Predict when DEF will run out.

        Args:
            truck_id: Truck ID
            current_level_pct: Current DEF level (0-100)
            daily_miles: Average daily miles
            avg_mpg: Average MPG
            avg_consumption_gph: Average fuel consumption in GPH

        Returns:
            Prediction dict with days_until_empty, days_until_derate, etc.
        """
        if current_level_pct is None or current_level_pct <= 0:
            return {
                "truck_id": truck_id,
                "status": "NO_DATA",
                "message": "DEF level not available",
                "days_until_empty": None,
                "days_until_derate": None,
            }

        # Clamp level to valid range
        current_level_pct = max(0, min(100, current_level_pct))

        # Calculate current DEF liters
        current_def_liters = (current_level_pct / 100) * self.tank_capacity_liters

        # Calculate daily DEF consumption
        if daily_miles and avg_mpg and avg_mpg > 0:
            # Calculate from actual driving data
            daily_diesel_gallons = daily_miles / avg_mpg
            daily_diesel_liters = daily_diesel_gallons * self.GALLONS_TO_LITERS
            daily_def_liters = daily_diesel_liters * (self.def_pct_of_diesel / 100)
        elif avg_consumption_gph:
            # Use consumption rate (assume 10 hours/day)
            daily_diesel_gallons = avg_consumption_gph * 10
            daily_diesel_liters = daily_diesel_gallons * self.GALLONS_TO_LITERS
            daily_def_liters = daily_diesel_liters * (self.def_pct_of_diesel / 100)
        else:
            # Use default (400 miles/day at 6.5 MPG)
            daily_diesel_gallons = 400 / 6.5
            daily_diesel_liters = daily_diesel_gallons * self.GALLONS_TO_LITERS
            daily_def_liters = daily_diesel_liters * (self.def_pct_of_diesel / 100)

        # Ensure minimum consumption
        daily_def_liters = max(0.5, daily_def_liters)

        # Calculate days until empty
        days_until_empty = current_def_liters / daily_def_liters

        # Calculate days until derate (5% threshold)
        derate_liters = (self.DERATE_THRESHOLD_PCT / 100) * self.tank_capacity_liters
        liters_until_derate = current_def_liters - derate_liters
        days_until_derate = max(0, liters_until_derate / daily_def_liters)

        # Determine status
        if current_level_pct < self.DERATE_THRESHOLD_PCT:
            status = "CRITICAL"
            message = f"DEF at {current_level_pct:.1f}% - DERATE IMMINENT"
        elif current_level_pct < self.WARNING_THRESHOLD_PCT:
            status = "WARNING"
            message = f"DEF at {current_level_pct:.1f}% - refill soon"
        elif current_level_pct < 30:
            status = "NOTICE"
            message = f"DEF at {current_level_pct:.1f}%"
        else:
            status = "OK"
            message = f"DEF at {current_level_pct:.1f}%"

        return {
            "truck_id": truck_id,
            "status": status,
            "message": message,
            "current_level_pct": round(current_level_pct, 1),
            "current_liters": round(current_def_liters, 1),
            "days_until_empty": round(days_until_empty, 1),
            "days_until_derate": round(days_until_derate, 1),
            "daily_consumption_liters": round(daily_def_liters, 2),
            "refill_recommended": current_level_pct < self.WARNING_THRESHOLD_PCT,
        }

    def get_low_def_trucks(
        self,
        trucks_def_data: Dict[str, float],
        threshold_pct: float = WARNING_THRESHOLD_PCT,
    ) -> list[Dict[str, Any]]:
        """
        Get trucks with DEF below threshold.

        Args:
            trucks_def_data: Dict of truck_id -> def_level_pct
            threshold_pct: Threshold percentage

        Returns:
            List of dicts with truck_id and prediction
        """
        low_def_trucks = []

        # Support both dict and list formats
        if isinstance(trucks_def_data, dict):
            for truck_id, def_level in trucks_def_data.items():
                if def_level is not None and def_level < threshold_pct:
                    prediction = self.predict_def_depletion(truck_id, def_level)
                    low_def_trucks.append(prediction)
        elif isinstance(trucks_def_data, list):
            for truck_data in trucks_def_data:
                truck_id = truck_data.get("truck_id")
                def_level = truck_data.get("def_level_pct")
                if def_level is not None and def_level < threshold_pct:
                    prediction = self.predict_def_depletion(
                        truck_id, def_level, avg_mpg=truck_data.get("avg_mpg")
                    )
                    low_def_trucks.append(prediction)

        # Sort by severity (lowest level first)
        low_def_trucks.sort(key=lambda x: x["current_level_pct"])

        return low_def_trucks
