"""
MPG Engine - Isolated MPG calculation logic

This module provides pure functions for MPG tracking with proper validation,
windowing, and EMA smoothing. Designed for easy testing and reusability.

Author: Fuel Copilot Team
Version: v3.9.6
Date: November 26, 2025
"""

from dataclasses import dataclass, field
from typing import Optional
import logging

logger = logging.getLogger(__name__)


# 🔧 FIX v3.9.6: Moved before MPGState class so it can be used in get_variance()
def filter_outliers_iqr(readings: list, multiplier: float = 1.5) -> list:
    """
    IQR-based outlier rejection for MPG readings.

    Removes extreme values that are likely sensor errors or edge cases.
    Uses Interquartile Range (IQR) method which is robust to outliers.

    Args:
        readings: List of MPG readings
        multiplier: IQR multiplier for bounds (default 1.5 = standard)

    Returns:
        Filtered list without outliers

    Example:
        >>> filter_outliers_iqr([5.0, 5.5, 6.0, 15.0, 5.2])  # 15 is outlier
        [5.0, 5.5, 6.0, 5.2]
    """
    if len(readings) < 4:
        return readings  # Not enough data for IQR

    sorted_data = sorted(readings)
    n = len(sorted_data)

    # Calculate Q1 (25th percentile) and Q3 (75th percentile)
    q1_idx = n // 4
    q3_idx = (3 * n) // 4
    q1 = sorted_data[q1_idx]
    q3 = sorted_data[q3_idx]

    iqr = q3 - q1
    lower_bound = q1 - multiplier * iqr
    upper_bound = q3 + multiplier * iqr

    filtered = [r for r in readings if lower_bound <= r <= upper_bound]

    if len(filtered) < len(readings):
        removed = len(readings) - len(filtered)
        logger.debug(
            f"IQR filter removed {removed} outliers. Bounds: [{lower_bound:.2f}, {upper_bound:.2f}]"
        )

    return filtered if filtered else readings  # Return original if all filtered


@dataclass
class MPGState:
    """
    State for MPG tracking with accumulator pattern

    Attributes:
        distance_accum: Accumulated distance in miles for current window
        fuel_accum_gal: Accumulated fuel in gallons for current window
        mpg_current: Current MPG value (EMA smoothed), None if not yet calculated
        window_count: Number of completed windows (for debugging)
        last_raw_mpg: Last raw MPG before smoothing (for debugging)
        mpg_history: Recent MPG values for variance calculation
    """

    distance_accum: float = 0.0
    fuel_accum_gal: float = 0.0
    mpg_current: Optional[float] = None
    window_count: int = 0
    last_raw_mpg: Optional[float] = None

    # 🆕 Track previous sensor readings for delta calculation
    last_fuel_lvl_pct: Optional[float] = None  # Previous fuel level %
    last_odometer_mi: Optional[float] = None  # Previous odometer in miles
    last_timestamp: Optional[float] = None  # Epoch of last reading

    # History for variance-based adaptive alpha
    mpg_history: list = field(default_factory=list)
    max_history_size: int = 10

    # Validation stats (optional, for monitoring)
    total_discarded: int = 0
    total_accepted: int = 0
    fuel_source_stats: dict = field(
        default_factory=lambda: {"sensor": 0, "fallback": 0}
    )

    def add_to_history(self, mpg_value: float):
        """Add MPG value to history, maintaining max size"""
        self.mpg_history.append(mpg_value)
        if len(self.mpg_history) > self.max_history_size:
            self.mpg_history.pop(0)

    def get_variance(self) -> float:
        """
        Calculate variance of recent MPG values.

        🔧 FIX v3.9.6: Apply IQR outlier rejection before variance calculation
        to prevent extreme values from skewing the dynamic alpha.
        """
        if len(self.mpg_history) < 3:
            return 0.0

        # Apply IQR filter to remove outliers before variance calculation
        filtered = filter_outliers_iqr(self.mpg_history)
        if len(filtered) < 2:
            filtered = self.mpg_history  # Fallback if too many removed

        mean = sum(filtered) / len(filtered)
        variance = sum((x - mean) ** 2 for x in filtered) / len(filtered)
        return variance


@dataclass
class MPGConfig:
    """Configuration for MPG calculation

    MPG Ranges for US Freight Trucks (2006-2019 models):
    - Reefer loaded, mountain: 4.0 - 5.0 MPG
    - Dry van loaded, city: 4.5 - 5.5 MPG
    - Flatbed loaded, highway: 5.5 - 6.5 MPG
    - Dry van empty, highway: 6.5 - 7.5 MPG
    - Optimal (descent, empty): 7.0 - 8.5 MPG

    🔧 v3.12.18: Reduced min_miles from 10.0 to 5.0 for faster MPG updates
    This allows MPG to update more frequently while still having enough data
    for a reasonable calculation. Trade-off: slightly more variance in readings.
    """

    min_miles: float = 5.0  # 🔧 v3.12.18: Reduced from 10.0 for faster updates
    min_fuel_gal: float = 0.75  # 🔧 v3.12.18: Reduced from 1.5 proportionally

    # Physical limits for Class 8 trucks (realistic ranges)
    min_mpg: float = 3.5  # Absolute minimum (reefer, loaded, mountain, city)
    max_mpg: float = 9.0  # 🔧 v3.10.7: Absolute maximum (empty, downhill, highway)
    ema_alpha: float = 0.4  # 🔧 v3.10.7: Reduced from 0.6 for smoother readings
    fallback_mpg: float = 5.8  # Conservative baseline for estimation

    # Dynamic alpha settings
    use_dynamic_alpha: bool = True  # Enable variance-based alpha adjustment
    alpha_high_variance: float = 0.3  # Alpha when variance is high (smoother)
    alpha_low_variance: float = 0.6  # Alpha when variance is low (more responsive)
    variance_threshold: float = 0.25  # Variance threshold to switch alpha

    def __post_init__(self):
        """Validate config"""
        if self.min_miles <= 0:
            raise ValueError("min_miles must be positive")
        if self.min_fuel_gal <= 0:
            raise ValueError("min_fuel_gal must be positive")
        if self.min_mpg >= self.max_mpg:
            raise ValueError("min_mpg must be less than max_mpg")
        if not (0 < self.ema_alpha <= 1):
            raise ValueError("ema_alpha must be between 0 and 1")


def get_dynamic_alpha(state: MPGState, config: MPGConfig) -> float:
    """
    Calculate dynamic EMA alpha based on variance of recent MPG values.

    High variance (noisy data) -> lower alpha (smoother, less responsive)
    Low variance (stable data) -> higher alpha (more responsive to changes)

    Args:
        state: Current MPG state with history
        config: MPG configuration

    Returns:
        Appropriate alpha value
    """
    if not config.use_dynamic_alpha:
        return config.ema_alpha

    variance = state.get_variance()

    if variance > config.variance_threshold:
        # High variance - use lower alpha for smoother response
        return config.alpha_high_variance
    else:
        # Low variance - use higher alpha for faster response
        return config.alpha_low_variance


def update_mpg_state(
    state: MPGState,
    delta_miles: float,
    delta_gallons: float,
    config: MPGConfig = MPGConfig(),
    truck_id: str = "UNKNOWN",
) -> MPGState:
    """
    Update MPG state with new delta values

    Args:
        state: Current MPG state (will be modified in place)
        delta_miles: Distance traveled since last update (miles)
        delta_gallons: Fuel consumed since last update (gallons)
        config: MPG configuration parameters
        truck_id: Truck identifier for logging

    Returns:
        Updated state (same object, modified in place)

    Logic:
        1. Force non-negative deltas (safety)
        2. Accumulate distance and fuel
        3. If window threshold reached:
           a. Calculate raw MPG
           b. Validate against physical limits
           c. Apply EMA smoothing if valid
           d. Reset accumulator
        4. Track statistics
    """
    # Force non-negative (safety against sensor glitches)
    delta_miles = max(delta_miles, 0.0)
    delta_gallons = max(delta_gallons, 0.0)

    # Accumulate
    state.distance_accum += delta_miles
    state.fuel_accum_gal += delta_gallons

    # Check if window is complete
    if (
        state.distance_accum >= config.min_miles
        and state.fuel_accum_gal >= config.min_fuel_gal
    ):

        # Calculate raw MPG
        raw_mpg = state.distance_accum / state.fuel_accum_gal
        state.last_raw_mpg = raw_mpg

        # Validate against physical limits
        if config.min_mpg <= raw_mpg <= config.max_mpg:
            # Valid MPG - add to history for variance calculation
            state.add_to_history(raw_mpg)

            # Get dynamic alpha based on variance
            alpha = get_dynamic_alpha(state, config)

            # Apply EMA smoothing
            if state.mpg_current is None:
                # First calculation - use raw value
                state.mpg_current = raw_mpg
                logger.info(f"[{truck_id}] MPG initialized: {raw_mpg:.2f} MPG")
            else:
                # Apply EMA: new_value = alpha * raw + (1-alpha) * old
                old_mpg = state.mpg_current
                state.mpg_current = alpha * raw_mpg + (1 - alpha) * state.mpg_current
                variance = state.get_variance()
                logger.info(
                    f"[{truck_id}] MPG updated: {old_mpg:.2f} → {state.mpg_current:.2f} "
                    f"(raw: {raw_mpg:.2f}, alpha: {alpha:.2f}, variance: {variance:.3f}, "
                    f"window: {state.distance_accum:.1f}mi/{state.fuel_accum_gal:.2f}gal)"
                )

            state.total_accepted += 1
            state.window_count += 1

        else:
            # Invalid MPG - discard but still reset window
            logger.warning(
                f"[{truck_id}] MPG discarded: {raw_mpg:.2f} MPG out of range "
                f"[{config.min_mpg:.1f}, {config.max_mpg:.1f}]. "
                f"Window: {state.distance_accum:.1f}mi / {state.fuel_accum_gal:.2f}gal. "
                f"Current MPG unchanged: {state.mpg_current if state.mpg_current else 'N/A'}"
            )
            state.total_discarded += 1

        # Reset window (always, even if discarded)
        state.distance_accum = 0.0
        state.fuel_accum_gal = 0.0

    return state


def reset_mpg_state(
    state: MPGState, reason: str, truck_id: str = "UNKNOWN"
) -> MPGState:
    """
    Reset MPG state (e.g., after refuel or long offline period)

    Args:
        state: Current MPG state
        reason: Reason for reset (for logging)
        truck_id: Truck identifier

    Returns:
        Reset state (accumulators cleared, mpg_current preserved)
    """
    logger.info(f"[{truck_id}] MPG state reset: {reason}")

    state.distance_accum = 0.0
    state.fuel_accum_gal = 0.0
    # Note: We keep mpg_current to avoid losing good data
    # Only accumulator is reset

    return state


def estimate_fuel_from_distance(
    distance_miles: float, config: MPGConfig = MPGConfig()
) -> float:
    """
    Estimate fuel consumption from distance using conservative baseline

    Args:
        distance_miles: Distance traveled in miles
        config: MPG config (uses fallback_mpg)

    Returns:
        Estimated fuel consumption in gallons

    Example:
        >>> estimate_fuel_from_distance(10.0)  # 10 miles
        1.72  # gallons (at 5.8 MPG baseline)
    """
    if distance_miles <= 0:
        return 0.0

    # Conservative estimate: 1 / fallback_mpg = gal/mile
    gal_per_mile = 1.0 / config.fallback_mpg
    return distance_miles * gal_per_mile


def get_mpg_status(state: MPGState, config: MPGConfig) -> dict:
    """
    Get human-readable MPG status for monitoring/dashboards

    Returns:
        Dict with status information
    """
    if state.mpg_current is None:
        status = "NOT_READY"
        message = "Insufficient data"
    elif state.mpg_current < config.min_mpg:
        status = "CRITICAL"
        message = f"MPG too low: {state.mpg_current:.2f}"
    elif state.mpg_current > config.max_mpg:
        status = "WARNING"
        message = f"MPG too high: {state.mpg_current:.2f}"
    elif state.mpg_current < (config.min_mpg + 1.0):
        status = "POOR"
        message = f"Below average: {state.mpg_current:.2f}"
    elif state.mpg_current > (config.max_mpg - 0.5):
        status = "EXCELLENT"
        message = f"Optimal: {state.mpg_current:.2f}"
    else:
        status = "GOOD"
        message = f"Normal: {state.mpg_current:.2f}"

    return {
        "status": status,
        "message": message,
        "mpg_current": state.mpg_current,
        "window_progress": f"{state.distance_accum:.1f}/{config.min_miles}mi",
        "windows_completed": state.window_count,
        "acceptance_rate": (
            state.total_accepted / (state.total_accepted + state.total_discarded)
            if (state.total_accepted + state.total_discarded) > 0
            else 0.0
        ),
    }
