"""
DEF Predictor Service

Extracted from fleet_command_center.py for cleaner architecture.

This service handles DEF (Diesel Exhaust Fluid) consumption prediction
and depletion warnings for Class 8 trucks.

v1.0.0 Features:
- DEF consumption rate calculation (based on diesel consumption)
- Days until empty prediction
- Days until derate threshold prediction
- Actual driving data vs default consumption
- DEF level validation and sanitization

Author: Fleet Analytics Team
Created: 2025-12-18
"""

import structlog
from typing import Optional
from src.models.command_center_models import DEFPrediction

logger = structlog.get_logger()


class DEFPredictor:
    """
    Predicts DEF depletion based on consumption patterns.

    DEF consumption for Class 8 trucks is typically 2-3% of diesel consumption.
    This predictor calculates:
    - How many days until DEF tank is empty
    - How many days until derate threshold (5%)
    - Daily DEF consumption rate

    Example Usage:
        predictor = DEFPredictor()

        # With actual driving data
        prediction = predictor.predict_def_depletion(
            truck_id="FF7702",
            current_level_pct=25.0,
            daily_miles=400,
            avg_mpg=6.5
        )

        # With defaults
        prediction = predictor.predict_def_depletion(
            truck_id="FF7702",
            current_level_pct=15.0
        )

        print(f"Days until empty: {prediction.days_until_empty:.1f}")
        print(f"Days until derate: {prediction.days_until_derate:.1f}")
    """

    # Default DEF consumption configuration for Class 8 trucks
    DEFAULT_CONFIG = {
        "tank_capacity_liters": 75,  # Typical DEF tank size
        "avg_consumption_pct_diesel": 2.5,  # 2.5% of diesel = DEF consumption
        "avg_daily_diesel_liters": 150,  # ~40 gallons/day for Class 8
        "derate_threshold_pct": 5,  # Truck derates at 5% DEF
        "warning_threshold_pct": 15,  # Warning at 15% DEF
    }

    # Constants
    GALLONS_TO_LITERS = 3.785
    MIN_DEF_CONSUMPTION = 0.1  # Minimum consumption assumption (liters/day)

    def __init__(
        self,
        tank_capacity_liters: Optional[float] = None,
        avg_consumption_pct_diesel: Optional[float] = None,
        avg_daily_diesel_liters: Optional[float] = None,
        derate_threshold_pct: Optional[float] = None,
        warning_threshold_pct: Optional[float] = None,
    ):
        """
        Initialize DEFPredictor with optional custom configuration.

        Args:
            tank_capacity_liters: DEF tank capacity in liters (default 75)
            avg_consumption_pct_diesel: DEF as % of diesel consumption (default 2.5%)
            avg_daily_diesel_liters: Average daily diesel consumption (default 150L)
            derate_threshold_pct: DEF level that triggers derate (default 5%)
            warning_threshold_pct: DEF level for warning (default 15%)
        """
        self.tank_capacity_liters = (
            tank_capacity_liters or self.DEFAULT_CONFIG["tank_capacity_liters"]
        )
        self.avg_consumption_pct_diesel = (
            avg_consumption_pct_diesel
            or self.DEFAULT_CONFIG["avg_consumption_pct_diesel"]
        )
        self.avg_daily_diesel_liters = (
            avg_daily_diesel_liters or self.DEFAULT_CONFIG["avg_daily_diesel_liters"]
        )
        self.derate_threshold_pct = (
            derate_threshold_pct or self.DEFAULT_CONFIG["derate_threshold_pct"]
        )
        self.warning_threshold_pct = (
            warning_threshold_pct or self.DEFAULT_CONFIG["warning_threshold_pct"]
        )

        logger.debug(
            "DEFPredictor initialized",
            tank_capacity=self.tank_capacity_liters,
            def_pct_diesel=self.avg_consumption_pct_diesel,
        )

    def predict_def_depletion(
        self,
        truck_id: str,
        current_level_pct: float,
        daily_miles: Optional[float] = None,
        avg_mpg: Optional[float] = None,
    ) -> DEFPrediction:
        """
        Predict when DEF will run out based on consumption patterns.

        Real DEF prediction using liters/consumption = days.
        DEF consumption is typically 2-3% of diesel consumption for Class 8 trucks.

        Args:
            truck_id: Truck identifier
            current_level_pct: Current DEF level (0-100%)
            daily_miles: Average daily miles (optional)
            avg_mpg: Average MPG (optional)

        Returns:
            DEFPrediction with days until empty and derate

        Examples:
            >>> predictor = DEFPredictor()
            >>> prediction = predictor.predict_def_depletion(
            ...     truck_id="FF7702",
            ...     current_level_pct=25.0,
            ...     daily_miles=400,
            ...     avg_mpg=6.5
            ... )
            >>> prediction.days_until_empty > 0
            True
            >>> prediction.days_until_derate >= 0
            True
        """
        # Validate and clamp DEF level
        current_level_pct = self._validate_def_level(current_level_pct)

        # Calculate current DEF liters
        current_liters = (current_level_pct / 100) * self.tank_capacity_liters

        # Calculate daily DEF consumption
        daily_def_liters = self._calculate_daily_def_consumption(daily_miles, avg_mpg)

        # Calculate days until empty
        days_until_empty = current_liters / daily_def_liters

        # Calculate days until derate (typically at 5% DEF)
        derate_level_liters = (
            self.derate_threshold_pct / 100
        ) * self.tank_capacity_liters
        liters_until_derate = current_liters - derate_level_liters
        days_until_derate = max(0, liters_until_derate / daily_def_liters)

        logger.debug(
            "DEF prediction calculated",
            truck_id=truck_id,
            current_pct=current_level_pct,
            days_empty=round(days_until_empty, 1),
            days_derate=round(days_until_derate, 1),
        )

        return DEFPrediction(
            truck_id=truck_id,
            current_level_pct=current_level_pct,
            estimated_liters_remaining=current_liters,
            avg_consumption_liters_per_day=daily_def_liters,
            days_until_empty=days_until_empty,
            days_until_derate=days_until_derate,
        )

    def _calculate_daily_def_consumption(
        self, daily_miles: Optional[float], avg_mpg: Optional[float]
    ) -> float:
        """
        Calculate daily DEF consumption in liters.

        Uses actual driving data if available, otherwise uses defaults.

        Args:
            daily_miles: Average daily miles driven
            avg_mpg: Average fuel economy in MPG

        Returns:
            Daily DEF consumption in liters

        Examples:
            >>> predictor = DEFPredictor()
            >>> # With actual data
            >>> consumption = predictor._calculate_daily_def_consumption(400, 6.5)
            >>> consumption > 0
            True
            >>> # With defaults
            >>> consumption = predictor._calculate_daily_def_consumption(None, None)
            >>> consumption > 0
            True
        """
        def_pct_diesel = self.avg_consumption_pct_diesel / 100

        if daily_miles and avg_mpg and avg_mpg > 0:
            # Calculate based on actual driving data
            daily_diesel_gallons = daily_miles / avg_mpg
            daily_diesel_liters = daily_diesel_gallons * self.GALLONS_TO_LITERS
            daily_def_liters = daily_diesel_liters * def_pct_diesel
        else:
            # Use default consumption rate
            daily_def_liters = self.avg_daily_diesel_liters * def_pct_diesel

        # Avoid division by zero with minimum consumption
        if daily_def_liters <= 0:
            daily_def_liters = self.MIN_DEF_CONSUMPTION

        return daily_def_liters

    def _validate_def_level(self, level_pct: float) -> float:
        """
        Validate and clamp DEF level to 0-100 range.

        Args:
            level_pct: DEF level percentage

        Returns:
            Clamped DEF level (0-100)

        Examples:
            >>> predictor = DEFPredictor()
            >>> predictor._validate_def_level(50.0)
            50.0
            >>> predictor._validate_def_level(-10.0)
            0.0
            >>> predictor._validate_def_level(150.0)
            100.0
        """
        if level_pct < 0:
            logger.warning("DEF level below 0%, clamping to 0", level=level_pct)
            return 0.0
        elif level_pct > 100:
            logger.warning("DEF level above 100%, clamping to 100", level=level_pct)
            return 100.0
        return level_pct

    def is_critical(self, current_level_pct: float) -> bool:
        """
        Check if DEF level is at critical threshold (derate imminent).

        Args:
            current_level_pct: Current DEF level percentage

        Returns:
            True if DEF level is at or below derate threshold

        Examples:
            >>> predictor = DEFPredictor()
            >>> predictor.is_critical(3.0)
            True
            >>> predictor.is_critical(10.0)
            False
        """
        return current_level_pct <= self.derate_threshold_pct

    def is_warning(self, current_level_pct: float) -> bool:
        """
        Check if DEF level is at warning threshold.

        Args:
            current_level_pct: Current DEF level percentage

        Returns:
            True if DEF level is at or below warning threshold

        Examples:
            >>> predictor = DEFPredictor()
            >>> predictor.is_warning(12.0)
            True
            >>> predictor.is_warning(20.0)
            False
        """
        return current_level_pct <= self.warning_threshold_pct

    def get_status(self, current_level_pct: float) -> str:
        """
        Get human-readable status for DEF level.

        Args:
            current_level_pct: Current DEF level percentage

        Returns:
            Status string: "CRITICAL", "WARNING", "OK"

        Examples:
            >>> predictor = DEFPredictor()
            >>> predictor.get_status(3.0)
            'CRITICAL'
            >>> predictor.get_status(12.0)
            'WARNING'
            >>> predictor.get_status(50.0)
            'OK'
        """
        if self.is_critical(current_level_pct):
            return "CRITICAL"
        elif self.is_warning(current_level_pct):
            return "WARNING"
        else:
            return "OK"

    def calculate_refill_amount(
        self, current_level_pct: float, target_level_pct: float = 100.0
    ) -> float:
        """
        Calculate how much DEF is needed to reach target level.

        Args:
            current_level_pct: Current DEF level percentage
            target_level_pct: Desired DEF level percentage (default 100%)

        Returns:
            DEF needed in liters

        Examples:
            >>> predictor = DEFPredictor()
            >>> # Tank is 75L, at 25% = 18.75L, to fill to 100% needs 56.25L
            >>> refill = predictor.calculate_refill_amount(25.0, 100.0)
            >>> 56 <= refill <= 57
            True
        """
        current_level_pct = self._validate_def_level(current_level_pct)
        target_level_pct = self._validate_def_level(target_level_pct)

        current_liters = (current_level_pct / 100) * self.tank_capacity_liters
        target_liters = (target_level_pct / 100) * self.tank_capacity_liters

        return max(0, target_liters - current_liters)

    def estimate_consumption_rate(
        self, initial_level_pct: float, final_level_pct: float, days_elapsed: float
    ) -> float:
        """
        Estimate actual DEF consumption rate from historical data.

        Args:
            initial_level_pct: Starting DEF level percentage
            final_level_pct: Ending DEF level percentage
            days_elapsed: Days between measurements

        Returns:
            Estimated daily consumption in liters/day

        Examples:
            >>> predictor = DEFPredictor()
            >>> # 75L tank, 80% to 60% over 5 days = 15L over 5 days = 3L/day
            >>> rate = predictor.estimate_consumption_rate(80.0, 60.0, 5.0)
            >>> 2.9 <= rate <= 3.1
            True
        """
        if days_elapsed <= 0:
            logger.warning(
                "Invalid days_elapsed for consumption rate", days=days_elapsed
            )
            return 0.0

        initial_liters = (initial_level_pct / 100) * self.tank_capacity_liters
        final_liters = (final_level_pct / 100) * self.tank_capacity_liters
        liters_consumed = initial_liters - final_liters

        return max(0, liters_consumed / days_elapsed)
