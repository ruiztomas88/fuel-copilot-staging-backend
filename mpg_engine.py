"""
MPG Engine - Isolated MPG calculation logic

This module provides pure functions for MPG tracking with proper validation,
windowing, and EMA smoothing. Designed for easy testing and reusability.

Author: Fuel Copilot Team
Version: v2.0.0
Date: December 22, 2025

Changelog:
- v2.0.0: MAJOR REDESIGN - max_mpg 12.0→8.5 realista para 44k lbs, min_fuel 1.2→2.0 gal
- v3.15.3: FIXED MPG inflados - restaurar thresholds 8.0mi/1.2gal (era 5.0mi/0.75gal que amplificaba errores)
- v3.15.2: RESTORED Wednesday Dec 18 config (5.0mi/0.75gal/9.0max) - was showing correct 4-7.5 range
- v3.15.1: Fix MPG config - min_miles 4.0/max_mpg 7.8 for accurate tracking (44k lbs trucks)
- v3.15.0: Increased max_mpg from 9.0 to 12.0 - trucks were getting rejected with valid 9-11 MPG
- v3.14.0: Improved filter_outliers_iqr (empty list on total corruption)
- v3.14.0: Added auto-save/load for TruckBaselineManager
- v3.14.0: Added shutdown_baseline_manager() for clean service shutdown
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# 🔧 FIX v3.9.6: Moved before MPGState class so it can be used in get_variance()
def filter_outliers_mad(readings: list, threshold: float = 3.0) -> list:
    """
    🆕 v3.13.0: MAD-based outlier rejection for small samples (n < 4).

    Uses Median Absolute Deviation which is more robust than IQR
    for small sample sizes.

    Args:
        readings: List of MPG readings
        threshold: Number of MADs from median to consider outlier (default 3.0)

    Returns:
        Filtered list without outliers
    """
    if len(readings) < 2:
        return readings

    sorted_data = sorted(readings)
    median = sorted_data[len(sorted_data) // 2]

    # Calculate MAD (Median Absolute Deviation)
    absolute_deviations = [abs(x - median) for x in readings]
    mad = sorted(absolute_deviations)[len(absolute_deviations) // 2]

    if mad < 0.01:  # All values very similar
        return readings

    # Filter outliers beyond threshold * MAD
    filtered = [r for r in readings if abs(r - median) <= threshold * mad]

    if len(filtered) < len(readings):
        removed = len(readings) - len(filtered)
        logger.debug(
            f"MAD filter removed {removed} outliers (median={median:.2f}, MAD={mad:.2f})"
        )

    return filtered if filtered else readings


def filter_outliers_iqr(readings: list, multiplier: float = 1.5) -> list:
    """
    IQR-based outlier rejection for MPG readings.

    Removes extreme values that are likely sensor errors or edge cases.
    Uses Interquartile Range (IQR) method which is robust to outliers.
    🆕 v3.13.0: Falls back to MAD for n < 4.

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
        # 🆕 v3.13.0: Use MAD for small samples instead of no filtering
        return filter_outliers_mad(readings)

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

    # 🔧 v3.14.0 FIX: Handle total corruption case
    # If less than 2 readings remain after filtering, the sample is unreliable.
    # Return empty list to signal caller should use fallback, not corrupted data.
    if len(filtered) < 2:
        if len(readings) >= 2:  # Had enough data but all was bad
            logger.warning(
                f"IQR filter: {len(readings)} readings all rejected as outliers. "
                f"Bounds: [{lower_bound:.2f}, {upper_bound:.2f}]. Returning empty list."
            )
        return []

    return filtered


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
    last_total_fuel_gal: Optional[float] = (
        None  # 🆕 v2.0.1: Previous ECU cumulative fuel
    )

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

        🔧 FIX v3.14.1: Return high variance (1.0) when filtered is empty
        to force conservative alpha (more smoothing) instead of using corrupted data.
        """
        if len(self.mpg_history) < 3:
            return 0.0

        # Apply IQR filter to remove outliers before variance calculation
        filtered = filter_outliers_iqr(self.mpg_history)
        if len(filtered) < 2:
            # 🔧 v3.14.1: Return high variance to force conservative smoothing
            # instead of using potentially corrupted mpg_history
            return 1.0

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

    🔧 v3.15.3 FIX CRÍTICO: MPG inflados por thresholds muy bajos
    Problema: min_fuel_gal = 0.75 gal → cálculos con muy poco combustible
    - Errores pequeños del sensor (10-20%) se amplifican enormemente en MPG
    - Ejemplo: 5mi / 0.5gal (error 33%) = 10 MPG falso vs 5mi / 0.75gal = 6.67 MPG correcto

    Solución: Volver a thresholds más conservadores (8.0mi/1.2gal)
    - Requiere más distancia y combustible antes de calcular → más preciso
    - Trade-off: MPG se actualiza menos frecuentemente, pero es más confiable

    🔧 v3.12.18: Reduced min_miles from 10.0 to 5.0 for faster MPG updates
    This allows MPG to update more frequently while still having enough data
    for a reasonable calculation. Trade-off: slightly more variance in readings.

    🔧 v5.18.0 FIX: Reverted to stable balanced thresholds
    From experimentation: 8.0mi/1.2gal provides best balance of coverage vs accuracy.
    Avoids excessive noise while maintaining reasonable update frequency.
    """

    # 🔧 v3.12.18 DEC 4: Reduced for faster updates (5mi vs 10mi)
    # 🔧 v2.0.1 DEC 22: Restored with tighter max_mpg cap (8.2 vs 9.0)
    # 🔧 v3.13.0 DEC 23: Increased min_fuel_gal to reduce variance (FIX P0 - Auditoría)
    # Basado en datos reales de flota: Flatbed/Reefer/Dry Van cargados
    min_miles: float = 5.0  # ✅ Fast updates - MPG muestra después de 5mi
    min_fuel_gal: float = 1.5  # 🔧 FIX: Increased from 0.75 to reduce sensor noise variance

    # Physical limits for Class 8 trucks (44,000 lbs realistic ranges)
    # Loaded (44k): 4.0-6.5 MPG | Empty (10k): 6.5-8.0 MPG
    min_mpg: float = 3.8  # Absolute minimum (reefer on, loaded, mountain, city)
    max_mpg: float = (
        8.2  # ✅ DEC 22: Realistic max (was 9.0, capped to prevent inflation)
    )
    ema_alpha: float = 0.4  # 🔧 v3.10.7: Reduced from 0.6 for smoother readings
    fallback_mpg: float = 5.7  # 🔧 v3.12.31: Updated to fleet average (was 5.8)

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
                
                # 🔧 CRITICAL FIX: Clamp post-EMA to prevent values exceeding physical limits
                # Even if raw_mpg is valid, EMA can push current value out of bounds
                state.mpg_current = max(config.min_mpg, min(state.mpg_current, config.max_mpg))
                
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
        1.75  # gallons (at 5.7 MPG baseline)
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


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v3.12.28: PER-TRUCK MPG BASELINE
# Learns historical baseline per truck for anomaly detection
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TruckMPGBaseline:
    """
    Per-truck MPG baseline learned from historical data.

    Instead of comparing against fleet average (5.7 MPG), each truck
    has its own baseline based on its typical performance. This accounts for:
    - Different engine configurations
    - Different route profiles (city vs highway)
    - Different cargo types (reefer vs dry van)
    - Different driver habits

    Attributes:
        truck_id: Truck identifier
        baseline_mpg: Learned baseline for this truck
        min_observed: Minimum MPG ever observed (within valid range)
        max_observed: Maximum MPG ever observed (within valid range)
        sample_count: Number of samples used to calculate baseline
        last_updated: Timestamp of last update
        confidence: Confidence level based on sample count
    """

    truck_id: str
    baseline_mpg: float = 5.7  # Start with fleet average
    min_observed: float = 5.7
    max_observed: float = 5.7
    sample_count: int = 0
    last_updated: Optional[float] = None  # Epoch timestamp
    confidence: str = "LOW"  # LOW, MEDIUM, HIGH

    # Running statistics for online mean calculation
    _mpg_sum: float = 0.0
    _mpg_squared_sum: float = 0.0

    @property
    def std_dev(self) -> float:
        """Calculate standard deviation from running stats"""
        if self.sample_count < 2:
            return 1.0  # Default uncertainty
        mean = self._mpg_sum / self.sample_count
        variance = (self._mpg_squared_sum / self.sample_count) - (mean**2)
        # 🔧 v5.7.8: Fix BUG #10 - prevent negative variance from floating point errors
        variance = max(variance, 0.0)
        return max(variance**0.5, 0.1)  # At least 0.1 to avoid division issues

    def update(
        self, mpg_value: float, timestamp: float, config: MPGConfig = MPGConfig()
    ):
        """
        Update baseline with new MPG observation.

        Uses exponential moving average weighted by sample count for stability.

        Args:
            mpg_value: New MPG observation
            timestamp: Epoch timestamp of observation
            config: MPG config for validation
        """
        # Validate range
        if not (config.min_mpg <= mpg_value <= config.max_mpg):
            logger.debug(
                f"[{self.truck_id}] MPG {mpg_value:.2f} outside valid range, skipping baseline update"
            )
            return

        self.sample_count += 1
        self.last_updated = timestamp

        # Update running statistics
        self._mpg_sum += mpg_value
        self._mpg_squared_sum += mpg_value**2

        # Update min/max
        self.min_observed = min(self.min_observed, mpg_value)
        self.max_observed = max(self.max_observed, mpg_value)

        # Calculate baseline using weighted EMA
        # Weight increases with sample count for stability
        if self.sample_count == 1:
            self.baseline_mpg = mpg_value
        else:
            # Adaptive alpha: starts responsive (0.3), stabilizes (0.05)
            alpha = max(0.05, 0.3 / (self.sample_count**0.5))
            self.baseline_mpg = alpha * mpg_value + (1 - alpha) * self.baseline_mpg

        # Update confidence
        if self.sample_count >= 50:
            self.confidence = "HIGH"
        elif self.sample_count >= 20:
            self.confidence = "MEDIUM"
        else:
            self.confidence = "LOW"

    def get_deviation(self, current_mpg: float) -> dict:
        """
        Calculate how current MPG deviates from this truck's baseline.

        Args:
            current_mpg: Current MPG reading

        Returns:
            Dict with deviation analysis
        """
        if self.sample_count < 5:
            return {
                "deviation_pct": 0.0,
                "z_score": 0.0,
                "status": "INSUFFICIENT_DATA",
                "message": f"Need more data ({self.sample_count}/5 samples)",
            }

        deviation_pct = ((current_mpg - self.baseline_mpg) / self.baseline_mpg) * 100
        z_score = (current_mpg - self.baseline_mpg) / self.std_dev

        # Determine status based on z-score
        if abs(z_score) < 1.0:
            status = "NORMAL"
            message = "Within expected range"
        elif abs(z_score) < 2.0:
            status = "NOTABLE"
            message = "Slightly unusual" + (" (low)" if z_score < 0 else " (high)")
        elif abs(z_score) < 3.0:
            status = "ANOMALY"
            message = "Significant deviation" + (
                " - investigate" if z_score < -2 else ""
            )
        else:
            status = "CRITICAL"
            message = "Extreme deviation - immediate attention needed"

        return {
            "deviation_pct": round(deviation_pct, 1),
            "z_score": round(z_score, 2),
            "status": status,
            "message": message,
            "baseline_mpg": round(self.baseline_mpg, 2),
            "std_dev": round(self.std_dev, 2),
            "confidence": self.confidence,
        }

    def to_dict(self) -> dict:
        """Serialize baseline for storage"""
        return {
            "truck_id": self.truck_id,
            "baseline_mpg": round(self.baseline_mpg, 3),
            "min_observed": round(self.min_observed, 2),
            "max_observed": round(self.max_observed, 2),
            "sample_count": self.sample_count,
            "last_updated": self.last_updated,
            "confidence": self.confidence,
            "_mpg_sum": self._mpg_sum,
            "_mpg_squared_sum": self._mpg_squared_sum,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "TruckMPGBaseline":
        """Deserialize baseline from storage"""
        baseline = cls(truck_id=data["truck_id"])
        baseline.baseline_mpg = data.get("baseline_mpg", 5.7)
        baseline.min_observed = data.get("min_observed", 5.7)
        baseline.max_observed = data.get("max_observed", 5.7)
        baseline.sample_count = data.get("sample_count", 0)
        baseline.last_updated = data.get("last_updated")
        baseline.confidence = data.get("confidence", "LOW")
        baseline._mpg_sum = data.get("_mpg_sum", 0.0)
        baseline._mpg_squared_sum = data.get("_mpg_squared_sum", 0.0)
        return baseline


class TruckBaselineManager:
    """
    Manages per-truck MPG baselines for the fleet.
    🔧 v3.14.0: Added auto-save/load with configurable persistence

    Usage:
        manager = TruckBaselineManager()

        # Update baseline when we get a good MPG reading
        manager.update_baseline("CO0681", 5.8, timestamp)

        # Check if current MPG is anomalous
        deviation = manager.get_deviation("CO0681", 4.2)
        if deviation["status"] == "ANOMALY":
            send_alert(...)
    """

    DEFAULT_BASELINE_FILE = "data/mpg_baselines.json"
    SAVE_INTERVAL = 100  # Save every N updates

    def __init__(self, baseline_file: str = None, auto_load: bool = True):
        self._baselines: dict[str, TruckMPGBaseline] = {}
        self._baseline_file = baseline_file or self.DEFAULT_BASELINE_FILE
        self._update_count = 0
        self._dirty = False  # Track if we need to save

        # 🔧 v3.14.0: Auto-load on initialization
        if auto_load:
            self.load_from_file(self._baseline_file)

    def get_or_create(self, truck_id: str) -> TruckMPGBaseline:
        """Get existing baseline or create new one"""
        if truck_id not in self._baselines:
            self._baselines[truck_id] = TruckMPGBaseline(truck_id=truck_id)
        return self._baselines[truck_id]

    def update_baseline(
        self,
        truck_id: str,
        mpg_value: float,
        timestamp: float,
        config: MPGConfig = MPGConfig(),
    ):
        """Update baseline for a truck"""
        baseline = self.get_or_create(truck_id)
        baseline.update(mpg_value, timestamp, config)

        # 🔧 v3.14.0: Auto-save periodically
        self._dirty = True
        self._update_count += 1
        if self._update_count >= self.SAVE_INTERVAL:
            self._auto_save()

    def get_deviation(self, truck_id: str, current_mpg: float) -> dict:
        """Get deviation from baseline for a truck"""
        baseline = self.get_or_create(truck_id)
        return baseline.get_deviation(current_mpg)

    def get_fleet_summary(self) -> dict:
        """Get summary of all truck baselines"""
        if not self._baselines:
            return {"trucks": 0, "avg_baseline": 5.7, "baselines": []}

        baselines_list = []
        total_baseline = 0.0
        high_confidence_count = 0

        for truck_id, baseline in self._baselines.items():
            baselines_list.append(
                {
                    "truck_id": truck_id,
                    "baseline_mpg": round(baseline.baseline_mpg, 2),
                    "samples": baseline.sample_count,
                    "confidence": baseline.confidence,
                    "range": f"{baseline.min_observed:.1f}-{baseline.max_observed:.1f}",
                }
            )
            total_baseline += baseline.baseline_mpg
            if baseline.confidence == "HIGH":
                high_confidence_count += 1

        avg_baseline = total_baseline / len(self._baselines)

        return {
            "trucks": len(self._baselines),
            "avg_baseline": round(avg_baseline, 2),
            "high_confidence_count": high_confidence_count,
            "baselines": sorted(baselines_list, key=lambda x: x["baseline_mpg"]),
        }

    def save_to_file(self, filepath: str):
        """Save all baselines to JSON file"""
        import json

        data = {truck_id: bl.to_dict() for truck_id, bl in self._baselines.items()}
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(data)} truck baselines to {filepath}")

    def load_from_file(self, filepath: str):
        """Load baselines from JSON file"""
        import json
        from pathlib import Path

        if not Path(filepath).exists():
            logger.info(f"No baseline file found at {filepath}, starting fresh")
            return

        with open(filepath, "r") as f:
            data = json.load(f)

        for truck_id, bl_data in data.items():
            self._baselines[truck_id] = TruckMPGBaseline.from_dict(bl_data)

        logger.info(f"Loaded {len(self._baselines)} truck baselines from {filepath}")

    def _auto_save(self):
        """🔧 v3.14.0: Periodic auto-save to prevent data loss"""
        if self._dirty:
            try:
                self.save_to_file(self._baseline_file)
                self._update_count = 0
                self._dirty = False
            except Exception as e:
                logger.error(f"Auto-save failed: {e}")

    def shutdown(self):
        """🔧 v3.14.0: Call on service shutdown to save pending changes"""
        if self._dirty:
            logger.info("Saving baselines on shutdown...")
            self._auto_save()

    def cleanup_inactive_trucks(
        self, active_truck_ids: set, max_inactive_days: int = 30
    ) -> int:
        """
        🆕 v6.5.0: Remove baselines for trucks inactive > max_inactive_days.

        Prevents memory leaks from trucks removed from fleet.

        Args:
            active_truck_ids: Set of currently active truck IDs
            max_inactive_days: Days of inactivity before cleanup (default 30)

        Returns:
            Number of trucks cleaned up
        """
        from datetime import datetime

        cleaned_count = 0
        cutoff_timestamp = datetime.now().timestamp() - (max_inactive_days * 86400)
        trucks_to_remove = []

        for truck_id, baseline in self._baselines.items():
            # Remove if not in active fleet
            if truck_id not in active_truck_ids:
                trucks_to_remove.append(truck_id)
                continue

            # Check if last update is older than cutoff
            if baseline.last_updated and baseline.last_updated < cutoff_timestamp:
                trucks_to_remove.append(truck_id)

        # Remove inactive trucks
        for truck_id in trucks_to_remove:
            del self._baselines[truck_id]
            cleaned_count += 1
            self._dirty = True
            logger.info(f"🧹 Cleaned up MPG baseline for inactive truck: {truck_id}")

        # Save after cleanup
        if self._dirty:
            self._auto_save()

        return cleaned_count


# Global baseline manager instance
_baseline_manager: Optional[TruckBaselineManager] = None


def get_baseline_manager() -> TruckBaselineManager:
    """Get or create global baseline manager"""
    global _baseline_manager
    if _baseline_manager is None:
        _baseline_manager = TruckBaselineManager()
    return _baseline_manager


def shutdown_baseline_manager():
    """🔧 v3.14.0: Call on service shutdown to persist baselines"""
    global _baseline_manager
    if _baseline_manager is not None:
        _baseline_manager.shutdown()
        logger.info("Baseline manager shutdown complete")


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.7.8: ALGORITHM 1 - LOAD-AWARE CONSUMPTION FACTOR
# Adjusts expected consumption based on engine load percentage
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_load_factor(engine_load_pct: Optional[float]) -> float:
    """
    🆕 v5.7.8: Calculate consumption adjustment factor based on engine load.

    Engine load significantly affects fuel consumption:
    - Idle/low load (0-20%): ~50% baseline consumption
    - Medium load (40-60%): ~75-90% baseline consumption
    - High load (80-100%): 100-110% baseline consumption

    Formula: load_factor = 0.5 + (engine_load / 200)
    This gives: 0.5 at 0% load, 1.0 at 100% load

    Args:
        engine_load_pct: Engine load percentage (0-100), None if unavailable

    Returns:
        Float factor to multiply against baseline consumption.
        Returns 1.0 (no adjustment) if engine_load is None.

    Examples:
        >>> calculate_load_factor(0)      # Idle
        0.5
        >>> calculate_load_factor(50)     # Medium load
        0.75
        >>> calculate_load_factor(100)    # Full load
        1.0
        >>> calculate_load_factor(None)   # No data
        1.0
    """
    if engine_load_pct is None:
        return 1.0  # No adjustment if data unavailable

    # Clamp to valid range
    engine_load_pct = max(0.0, min(100.0, engine_load_pct))

    # Linear relationship: 0% load = 0.5 factor, 100% load = 1.0 factor
    load_factor = 0.5 + (engine_load_pct / 200.0)

    return round(load_factor, 3)


def get_load_adjusted_consumption(
    base_consumption_lph: float,
    engine_load_pct: Optional[float],
) -> dict:
    """
    🆕 v5.7.8: Get consumption adjusted for engine load.

    Args:
        base_consumption_lph: Base fuel consumption in liters per hour
        engine_load_pct: Current engine load percentage

    Returns:
        Dict with adjusted consumption and factor details
    """
    load_factor = calculate_load_factor(engine_load_pct)
    adjusted_consumption = base_consumption_lph * load_factor

    return {
        "base_consumption_lph": round(base_consumption_lph, 2),
        "load_factor": load_factor,
        "adjusted_consumption_lph": round(adjusted_consumption, 2),
        "engine_load_pct": engine_load_pct,
        "adjustment_applied": engine_load_pct is not None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.7.8: ALGORITHM 2 - WEATHER MPG ADJUSTMENT FACTOR
# Adjusts expected MPG based on ambient temperature
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_weather_mpg_factor(ambient_temp_f: Optional[float]) -> float:
    """
    🆕 v5.7.8: Calculate MPG adjustment factor based on ambient temperature.

    Temperature affects fuel economy:
    - Cold weather (<32°F): Increases fuel consumption due to:
      - Thicker engine oil viscosity
      - Longer warm-up periods
      - Heater usage
    - Hot weather (>95°F): Slightly increases consumption due to:
      - A/C usage
      - Engine cooling demands

    Optimal temperature range: 50-75°F (no adjustment needed)

    Args:
        ambient_temp_f: Ambient temperature in Fahrenheit, None if unavailable

    Returns:
        Float factor to multiply against expected MPG.
        Returns 1.0 (no adjustment) if temperature is None or in optimal range.

    Reference ranges (based on EPA and fleet studies):
    - <20°F: 0.88-0.90 (10-12% worse MPG)
    - 20-32°F: 0.92-0.95 (5-8% worse)
    - 32-50°F: 0.96-0.98 (2-4% worse)
    - 50-75°F: 1.0 (optimal)
    - 75-95°F: 0.98-1.0 (0-2% worse)
    - >95°F: 0.95-0.97 (3-5% worse)

    Examples:
        >>> calculate_weather_mpg_factor(70)    # Optimal
        1.0
        >>> calculate_weather_mpg_factor(20)    # Very cold
        0.88
        >>> calculate_weather_mpg_factor(100)   # Hot
        0.96
        >>> calculate_weather_mpg_factor(None)  # No data
        1.0
    """
    if ambient_temp_f is None:
        return 1.0  # No adjustment if data unavailable

    # Very cold: < 20°F
    if ambient_temp_f < 20:
        return 0.88

    # Cold: 20-32°F
    if ambient_temp_f < 32:
        # Linear interpolation: 0.88 at 20°F to 0.92 at 32°F
        return 0.88 + ((ambient_temp_f - 20) / 12) * 0.04

    # Cool: 32-50°F
    if ambient_temp_f < 50:
        # Linear interpolation: 0.92 at 32°F to 0.96 at 50°F
        return 0.92 + ((ambient_temp_f - 32) / 18) * 0.04

    # Optimal: 50-75°F
    if ambient_temp_f <= 75:
        return 1.0

    # Warm: 75-95°F
    if ambient_temp_f <= 95:
        # Linear interpolation: 1.0 at 75°F to 0.97 at 95°F
        return 1.0 - ((ambient_temp_f - 75) / 20) * 0.03

    # Hot: > 95°F
    if ambient_temp_f <= 110:
        # Linear interpolation: 0.97 at 95°F to 0.94 at 110°F
        return 0.97 - ((ambient_temp_f - 95) / 15) * 0.03

    # Extreme heat: > 110°F
    return 0.94


def get_weather_adjusted_mpg(
    base_mpg: float,
    ambient_temp_f: Optional[float],
) -> dict:
    """
    🆕 v5.7.8: Get MPG expectation adjusted for weather.

    Args:
        base_mpg: Expected MPG under normal conditions
        ambient_temp_f: Current ambient temperature in Fahrenheit

    Returns:
        Dict with adjusted MPG and factor details
    """
    weather_factor = calculate_weather_mpg_factor(ambient_temp_f)
    adjusted_mpg = base_mpg * weather_factor

    # Determine weather category
    if ambient_temp_f is None:
        category = "UNKNOWN"
    elif ambient_temp_f < 32:
        category = "COLD"
    elif ambient_temp_f < 50:
        category = "COOL"
    elif ambient_temp_f <= 75:
        category = "OPTIMAL"
    elif ambient_temp_f <= 95:
        category = "WARM"
    else:
        category = "HOT"

    return {
        "base_mpg": round(base_mpg, 2),
        "weather_factor": round(weather_factor, 3),
        "adjusted_mpg": round(adjusted_mpg, 2),
        "ambient_temp_f": ambient_temp_f,
        "weather_category": category,
        "adjustment_applied": ambient_temp_f is not None,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.7.8: ALGORITHM 3 - DAYS-TO-FAILURE PREDICTION
# Estimates time until maintenance needed based on trend analysis
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_days_to_failure(
    current_value: float,
    threshold: float,
    trend_slope_per_day: float,
    min_days: float = 0.5,
    max_days: float = 365.0,
) -> Optional[float]:
    """
    🆕 v5.7.8: Calculate estimated days until a metric crosses a threshold.

    This is a simple linear extrapolation based on observed trend.
    Used for predictive maintenance scheduling.

    Formula: days = (threshold - current_value) / trend_slope_per_day

    Args:
        current_value: Current sensor/metric value
        threshold: Failure/warning threshold to reach
        trend_slope_per_day: Rate of change per day (positive = increasing)
        min_days: Minimum days to return (avoid near-zero predictions)
        max_days: Maximum days to cap predictions

    Returns:
        Estimated days until threshold is crossed, or None if:
        - Trend is moving away from threshold
        - Trend is near zero

    Note: If already at threshold, returns min_days.

    Examples:
        >>> calculate_days_to_failure(70.0, 100.0, 5.0)  # Approaching upper threshold
        6.0  # 30 points to go / 5 per day = 6 days

        >>> calculate_days_to_failure(70.0, 50.0, -5.0)  # Approaching lower threshold
        4.0  # 20 points to go / 5 per day = 4 days

        >>> calculate_days_to_failure(70.0, 100.0, -5.0)  # Moving away from threshold
        None  # Not approaching threshold
    """
    # Near-zero trend - can't predict
    if abs(trend_slope_per_day) < 0.001:
        return None  # No meaningful trend

    # Calculate direction to threshold
    distance_to_threshold = threshold - current_value

    # Already at threshold - return min_days
    if abs(distance_to_threshold) < 0.001:
        return min_days

    # Determine if we're approaching or moving away from threshold
    # Approaching means: (threshold - current) and slope have the same sign
    # i.e., if threshold > current (distance > 0), we need slope > 0 to approach
    # if threshold < current (distance < 0), we need slope < 0 to approach

    approaching = (distance_to_threshold > 0 and trend_slope_per_day > 0) or (
        distance_to_threshold < 0 and trend_slope_per_day < 0
    )

    if not approaching:
        # Moving away from threshold
        return None

    # Calculate days (both values have same sign, so result is positive)
    days = abs(distance_to_threshold) / abs(trend_slope_per_day)

    # Clamp to reasonable range
    days = max(min_days, min(max_days, days))

    return round(days, 1)


def predict_maintenance_timing(
    sensor_name: str,
    current_value: float,
    history: list,
    warning_threshold: float,
    critical_threshold: float,
    is_higher_worse: bool = True,
    readings_per_day: float = 1.0,  # 🆕 v6.2.2: BUG-024 FIX - Explicit parameter
) -> dict:
    """
    🆕 v5.7.8 / 🔧 v6.2.2: Comprehensive maintenance timing prediction for a sensor.

    Analyzes recent history to determine trend and predicts when
    maintenance will be needed.

    Args:
        sensor_name: Name of the sensor/metric
        current_value: Current sensor value
        history: List of recent values (oldest first)
        warning_threshold: Threshold for warning state
        critical_threshold: Threshold for critical state
        is_higher_worse: If True, increasing values are bad (e.g., temperature)
                        If False, decreasing values are bad (e.g., battery voltage)
        readings_per_day: 🆕 Number of readings per day in history data.
                         1.0 = daily aggregated (default)
                         24.0 = hourly readings
                         96.0 = 15-min readings
                         5760.0 = raw sensor data (15-second intervals)

    Returns:
        Dict with prediction details

    ⚠️ CRITICAL (BUG-024): Always specify readings_per_day if using non-daily data!
    If readings are hourly and you pass 1.0, predictions will be off by 24x.
    If readings are raw (15s) and you pass 1.0, predictions will be off by 5760x!
    """
    # 🆕 v6.2.2: Validate readings_per_day parameter
    if not (0.1 <= readings_per_day <= 10000):
        logger.error(
            f"Invalid readings_per_day={readings_per_day} for {sensor_name}. "
            f"Must be between 0.1 and 10000. Using default 1.0."
        )
        readings_per_day = 1.0

    # Warn if suspicious value
    if readings_per_day > 100 and len(history) < 10:
        logger.warning(
            f"⚠️ {sensor_name}: readings_per_day={readings_per_day} but only "
            f"{len(history)} data points. Are you sure this is correct? "
            f"This suggests <1 day of data with high-frequency sampling."
        )
    result = {
        "sensor": sensor_name,
        "current_value": round(current_value, 2),
        "warning_threshold": warning_threshold,
        "critical_threshold": critical_threshold,
        "trend_slope_per_day": None,
        "trend_direction": "UNKNOWN",
        "days_to_warning": None,
        "days_to_critical": None,
        "urgency": "UNKNOWN",
        "recommendation": "Insufficient data for prediction",
    }

    # Need at least 3 data points for trend
    if len(history) < 3:
        return result

    # Calculate trend using linear regression (simple least squares)
    n = len(history)
    x_values = list(range(n))  # Assumes evenly spaced readings
    x_mean = sum(x_values) / n
    y_mean = sum(history) / n

    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, history))
    denominator = sum((x - x_mean) ** 2 for x in x_values)

    if denominator == 0:
        return result

    slope = numerator / denominator  # Units per reading interval

    # Convert slope from "per reading" to "per day"
    # ═══════════════════════════════════════════════════════════════════════════
    # 🔧 v6.2.2: BUG-024 FIX - Use explicit readings_per_day parameter
    # ═══════════════════════════════════════════════════════════════════════════
    # readings_per_day now comes from the parameter, NOT hardcoded.
    # Callers MUST specify the correct frequency:
    # - Daily aggregated data: readings_per_day=1.0 (default)
    # - Hourly rollups: readings_per_day=24.0
    # - 15-minute data: readings_per_day=96.0
    # - Raw sensor (15s): readings_per_day=5760.0
    #
    # If wrong value is passed, predictions will be catastrophically wrong:
    # Example: Hourly data with readings_per_day=1.0
    #   → slope=0.5°F/hour becomes 0.5°F/day (should be 12°F/day)
    #   → "30 days to critical" becomes "1.25 days to critical" (HUGE ERROR!)
    # ═══════════════════════════════════════════════════════════════════════════
    trend_slope_per_day = slope * readings_per_day

    result["trend_slope_per_day"] = round(trend_slope_per_day, 4)
    result["readings_frequency"] = (
        f"{readings_per_day} readings/day"  # 🆕 Add to output
    )

    # Determine trend direction relative to "worse"
    if is_higher_worse:
        if trend_slope_per_day > 0.1:
            result["trend_direction"] = "DEGRADING"
        elif trend_slope_per_day < -0.1:
            result["trend_direction"] = "IMPROVING"
        else:
            result["trend_direction"] = "STABLE"
    else:
        if trend_slope_per_day < -0.1:
            result["trend_direction"] = "DEGRADING"
        elif trend_slope_per_day > 0.1:
            result["trend_direction"] = "IMPROVING"
        else:
            result["trend_direction"] = "STABLE"

    # Calculate days to thresholds
    if is_higher_worse:
        days_to_warning = calculate_days_to_failure(
            current_value, warning_threshold, trend_slope_per_day
        )
        days_to_critical = calculate_days_to_failure(
            current_value, critical_threshold, trend_slope_per_day
        )
    else:
        # For "lower is worse", we track decreasing toward threshold
        days_to_warning = calculate_days_to_failure(
            current_value, warning_threshold, trend_slope_per_day
        )
        days_to_critical = calculate_days_to_failure(
            current_value, critical_threshold, trend_slope_per_day
        )

    result["days_to_warning"] = days_to_warning
    result["days_to_critical"] = days_to_critical

    # Determine urgency and recommendation
    if days_to_critical is not None and days_to_critical < 7:
        result["urgency"] = "CRITICAL"
        result["recommendation"] = (
            f"Schedule maintenance within {int(days_to_critical)} days"
        )
    elif days_to_warning is not None and days_to_warning < 7:
        result["urgency"] = "HIGH"
        result["recommendation"] = (
            f"Monitor closely, warning expected in ~{int(days_to_warning)} days"
        )
    elif days_to_critical is not None and days_to_critical < 30:
        result["urgency"] = "MEDIUM"
        result["recommendation"] = (
            f"Plan maintenance within {int(days_to_critical)} days"
        )
    elif result["trend_direction"] == "DEGRADING":
        result["urgency"] = "LOW"
        result["recommendation"] = "Gradual degradation detected, continue monitoring"
    elif result["trend_direction"] == "IMPROVING":
        result["urgency"] = "NONE"
        result["recommendation"] = "Condition improving, no action needed"
    else:
        result["urgency"] = "NONE"
        result["recommendation"] = "Stable condition, routine monitoring"

    return result
