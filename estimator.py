"""
Fuel Estimator Module - Kalman Filter v6.2.1

Kalman Filter for Fuel Level Estimation with production-validated improvements.

Features:
- Adaptive noise based on physical conditions
- ECU-based consumption calculation
- Emergency reset and auto-resync
- Anchor-based calibration support
- v5.3.0: Adaptive Q_r based on truck status (PARKED/IDLE/MOVING)
- v5.3.0: Kalman confidence indicator
- v5.4.0: GPS Quality adaptive Q_L (satellites-based)
- v5.4.0: Voltage quality factor integration
- v5.8.4: Negative consumption treated as sensor error
- v5.8.5: More conservative Q_r for PARKED/IDLE states
- v5.8.5: Auto-resync cooldown (30 min) to prevent oscillation
- v5.8.5: Innovation-based K adjustment for faster correction
- v5.8.6: Unified Q_L calculation (GPS + Voltage combined)
- v5.9.0: Fix P growth during large time gaps (audit fix)
- v5.9.0: Removed legacy calculate_adaptive_noise (dead code)
- v6.1.0: Sensor bias detection via innovation history tracking
- v6.1.0: Adaptive R v2 based on consistency (not magnitude)
- v6.1.0: Biodiesel blend correction for fuel density
- v6.2.0: ECU consumption validation against physics-based model
- v6.2.0: Calibrated consumption model for fallback and validation
- v6.2.1: CRITICAL FIX - RPM vs ECU cross-validation (prevent engine-off drift)

Author: Fuel Copilot Team
Version: 6.2.1
Date: December 29, 2025
"""

import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

# 🆕 v5.4.0: Import GPS and Voltage quality modules
try:
    from gps_quality import (
        AdaptiveQLManager,
        analyze_gps_quality,
        calculate_adjusted_Q_L,
    )

    GPS_QUALITY_AVAILABLE = True
except ImportError:
    GPS_QUALITY_AVAILABLE = False

try:
    from voltage_monitor import analyze_voltage, get_voltage_quality_factor

    VOLTAGE_MONITOR_AVAILABLE = True
except ImportError:
    VOLTAGE_MONITOR_AVAILABLE = False

logger = logging.getLogger(__name__)


class AnchorType(Enum):
    """Types of anchors for Kalman calibration"""

    NONE = "NONE"
    STATIC = "STATIC"  # Truck stopped
    MICRO = "MICRO"  # Stable cruise
    REFUEL = "REFUEL"  # Refueling event


class TruckStatus(Enum):
    """Truck operational status"""

    MOVING = "MOVING"
    STOPPED = "STOPPED"  # Engine ON, parked
    PARKED = "PARKED"  # Engine OFF, recently
    OFFLINE = "OFFLINE"  # No data > 30 min
    IDLE = "IDLE"  # Engine ON, not moving (🆕 v5.3.0)


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.3.0: ADAPTIVE Q_r CALCULATION - From predictive_maintenance_v3.py
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_adaptive_Q_r(truck_status: str, consumption_lph: float = 0.0) -> float:
    """
    🆕 v5.3.0: Calculate adaptive process noise based on truck operational state.
    🔧 v5.8.5: Made more conservative for PARKED/IDLE per audit recommendations.

    - PARKED: Very low process noise (fuel shouldn't change)
    - STOPPED/IDLE: Low process noise (only idle consumption ~1-2 GPH)
    - MOVING: Higher process noise (active consumption)

    This improves Kalman filter accuracy by adjusting expectations
    based on what the truck is actually doing.

    Args:
        truck_status: "PARKED", "STOPPED", "IDLE", or "MOVING"
        consumption_lph: Current fuel consumption in liters per hour

    Returns:
        Recommended Q_r (process noise) value
    """
    # 🔧 v5.8.5: More conservative values per audit
    # 🔧 DEC 23: Further reduced MOVING Q_r to reduce over-estimation
    # PARKED: 0.005 (was 0.01) - fuel should NOT change
    # IDLE: 0.02 (was 0.05) - very predictable ~1-2 GPH
    if truck_status == "PARKED":
        return 0.005  # Almost no expected change
    elif truck_status == "STOPPED":
        return 0.02  # Minimal idle consumption
    elif truck_status == "IDLE":
        # Idle is very predictable: ~2-4 LPH (0.5-1 GPH)
        return 0.02 + (consumption_lph / 100) * 0.01
    else:  # MOVING
        # Base + proportional to consumption rate
        # 🔧 DEC 23: Reduced base from 0.05 to 0.03, reduced multiplier
        return 0.03 + (consumption_lph / 50) * 0.05


def get_kalman_confidence(P: float) -> Dict:
    """
    🆕 v5.3.0: Convert Kalman filter covariance (P) to confidence level.
    Lower P = higher confidence in the estimate.

    Args:
        P: Current Kalman covariance value

    Returns:
        Dict with level, score, color, description
    """
    if P < 0.5:
        return {
            "level": "HIGH",
            "score": 95,
            "color": "green",
            "description": "Highly confident estimate based on consistent sensor data",
        }
    elif P < 2.0:
        return {
            "level": "MEDIUM",
            "score": 75,
            "color": "yellow",
            "description": "Moderate confidence - some sensor variability detected",
        }
    elif P < 5.0:
        return {
            "level": "LOW",
            "score": 50,
            "color": "orange",
            "description": "Low confidence - high sensor variability or limited data",
        }
    else:
        return {
            "level": "VERY_LOW",
            "score": 25,
            "color": "red",
            "description": "Very low confidence - sensor data unreliable or insufficient",
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ESTIMATOR CONFIG
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class EstimatorConfig:
    """Configuration for FuelEstimator"""

    # Kalman parameters
    # 🔧 DEC 23: Reduced defaults to match KALMAN_CONFIG adjustments
    Q_r: float = 0.05  # Process noise (model) - reduced from 0.1
    Q_L_moving: float = 2.5  # Measurement noise when moving - reduced from 4.0
    Q_L_static: float = 1.0  # Measurement noise when static

    # Drift thresholds
    max_drift_pct: float = 5.0  # Reduced from 7.5 for earlier warnings
    emergency_drift_threshold: float = 30.0
    emergency_gap_hours: float = 2.0
    auto_resync_threshold: float = 15.0
    resync_cooldown_sec: int = 1800  # 🔧 FIX DEC 29: Configurable (was hardcoded)

    # ECU validation
    min_consumption_gph: float = 0.1
    max_consumption_gph: float = 50.0
    max_ecu_failures: int = 5

    # 🆕 v6.1.0: Biodiesel blend correction
    biodiesel_blend_pct: float = 0.0  # % of biodiesel in fuel (0-100)


class FuelEstimator:
    """
    Kalman Filter for Fuel Level Estimation and Drift Detection

    Features:
    - Adaptive measurement noise based on driving conditions
    - ECU-based exact consumption calculation
    - Emergency reset for extreme drift
    - Refuel detection and handling
    """

    def __init__(
        self,
        truck_id: str,
        capacity_liters: float,
        config: Dict,
        tanks_config=None,
    ):
        self.truck_id = truck_id
        # 🔧 v5.7.8: Validate capacity to prevent division by zero
        if capacity_liters is None or capacity_liters <= 0:
            raise ValueError(f"capacity_liters must be positive, got {capacity_liters}")
        self.capacity_liters = capacity_liters
        self.capacity = capacity_liters  # Alias for compatibility
        self.config = config

        # State
        self.initialized = False
        self.level_liters = 0.0
        self.level_pct = 0.0
        self.consumption_lph = 0.0
        self.last_update_time = None
        self.last_fuel_lvl_pct = None

        # Refuel tracking
        self.recent_refuel = False
        self.refuel_volume_factor = 1.0
        if tanks_config:
            self.refuel_volume_factor = tanks_config.get_refuel_factor(
                truck_id, config.get("refuel_volume_factor", 1.0)
            )

        # Kalman parameters
        self.Q_r = config.get("Q_r", 0.1)
        self.Q_L_moving = config.get("Q_L_moving", 4.0)
        self.Q_L_static = config.get("Q_L_static", 1.0)
        self.Q_L = self.Q_L_moving
        self.P = 1.0
        self.is_moving = True

        # History for adaptive noise
        self.speed_history: List[float] = []
        self.altitude_history: List[float] = []
        self.last_speed = None
        self.last_altitude = None
        self.last_timestamp = None

        # ECU tracking
        self.last_total_fuel_used = None
        self.ecu_consumption_available = False
        self.ecu_failure_count = 0
        self.ecu_last_success_time = None
        self.ecu_degraded = False

        # Drift tracking
        self.drift_pct = 0.0
        self.drift_warning = False

        # 🔧 FIX DEC 29: Sensor skip counter for consistent failures
        self.sensor_skip_count = 0

        # Internal Kalman state
        self.L = None
        self.P_L = 20.0

        # 🆕 v5.4.0: GPS Quality Manager for adaptive Q_L
        self.gps_quality_manager: Optional[AdaptiveQLManager] = None
        if GPS_QUALITY_AVAILABLE:
            self.gps_quality_manager = AdaptiveQLManager(
                base_Q_L=self.Q_L_moving,
                smoothing_factor=0.3,
            )

        # 🆕 v5.4.0: Sensor quality tracking
        self.last_gps_quality = None
        self.last_voltage_quality = 1.0
        self.sensor_quality_factor = 1.0  # Combined quality factor

        # v6.1.0: Innovation history for bias detection (last 4 measurements)
        self.innovation_history: deque = deque(maxlen=4)
        self.bias_detected = False
        self.bias_magnitude = 0.0

        # v6.1.0: Biodiesel blend percentage (affects fuel density)
        self.biodiesel_blend_pct = config.get("biodiesel_blend_pct", 0.0)
        self.biodiesel_correction = self._get_biodiesel_correction(
            self.biodiesel_blend_pct
        )

        # 🆕 v6.2.0: Physics-based model parameters (loaded from calibration)
        self.baseline_consumption: float = 0.015  # %/min default
        self.load_factor: float = 0.002  # per % engine load
        self.altitude_factor: float = 0.0001  # per m/min climb
        self.calibration_loaded: bool = False

    def _get_biodiesel_correction(self, blend_pct: float) -> float:
        """
        🆕 v6.1.0: Calculate correction factor for biodiesel blends.

        Biodiesel has higher dielectric constant → capacitive sensors read high
        Args:
            blend_pct: Biodiesel percentage (0, 5, 10, 20)
        Returns:
            Correction factor (multiply sensor reading)
        """
        if blend_pct <= 0:
            return 1.0
        elif blend_pct <= 5:
            return 0.997  # -0.3%
        elif blend_pct <= 10:
            return 0.994  # -0.6%
        elif blend_pct <= 20:
            return 0.988  # -1.2%
        else:
            return 0.980  # >20% blend

    def initialize(self, fuel_lvl_pct: float = None, sensor_pct: float = None):
        """Initialize the filter with a sensor reading"""
        pct = fuel_lvl_pct if fuel_lvl_pct is not None else sensor_pct
        if pct is None:
            return

        self.level_pct = pct
        self.level_liters = (pct / 100.0) * self.capacity_liters
        self.L = self.level_liters
        self.initialized = True
        self.last_fuel_lvl_pct = pct
        self.P = 1.0

    def load_calibrated_params(
        self, calibration_file: str = "data/kalman_calibration.json"
    ) -> bool:
        """
        🆕 v6.2.0: Load physics-based consumption model from calibration.

        These parameters enable ECU validation and fallback consumption estimation.

        Args:
            calibration_file: Path to JSON file with calibrated parameters

        Returns:
            True if loaded successfully, False otherwise
        """
        import json
        from pathlib import Path

        try:
            cal_path = Path(calibration_file)
            if not cal_path.exists():
                logger.info(
                    f"[{self.truck_id}] No calibration file found at {calibration_file}, using defaults"
                )
                return False

            with open(calibration_file, "r") as f:
                cal = json.load(f)

            params = cal.get("parameters", {})
            self.baseline_consumption = params.get("baseline_consumption", 0.015)
            self.load_factor = params.get("load_factor", 0.002)
            self.altitude_factor = params.get("altitude_factor", 0.0001)
            self.calibration_loaded = True

            logger.info(
                f"[{self.truck_id}] ✅ Loaded calibrated consumption model: "
                f"baseline={self.baseline_consumption:.4f}, "
                f"load_factor={self.load_factor:.4f}, "
                f"altitude_factor={self.altitude_factor:.6f}"
            )
            return True

        except Exception as e:
            logger.warning(
                f"[{self.truck_id}] Failed to load calibration: {e}, using defaults"
            )
            return False

    def _calculate_physics_consumption(
        self,
        dt_hours: float,
        engine_load_pct: Optional[float] = None,
        altitude_change_m: Optional[float] = None,
    ) -> float:
        """
        🆕 v6.2.0: Calculate consumption using physics-based model.

        Model: fuel_rate = baseline + load_factor × load + altitude_factor × climb_rate

        Used for ECU validation and fallback when ECU unavailable.

        Args:
            dt_hours: Time interval in hours
            engine_load_pct: Engine load percentage (0-100)
            altitude_change_m: Altitude change in meters during dt_hours

        Returns:
            Estimated consumption in LPH
        """
        # Base consumption (idle)
        fuel_rate_pct_per_min = self.baseline_consumption

        # Add engine load effect
        if engine_load_pct is not None and engine_load_pct > 0:
            fuel_rate_pct_per_min += self.load_factor * engine_load_pct

        # Add altitude climbing effect
        if altitude_change_m is not None and dt_hours > 0:
            climb_rate_m_per_min = altitude_change_m / (dt_hours * 60)
            fuel_rate_pct_per_min += self.altitude_factor * climb_rate_m_per_min

        # Convert %/min to LPH
        # Tank capacity in liters (120 gal ≈ 454 L)
        fuel_rate_lph = (fuel_rate_pct_per_min / 100.0) * self.capacity_liters * 60.0

        # Clamp to reasonable range
        return max(2.0, min(fuel_rate_lph, 80.0))

    def validate_ecu_consumption(
        self,
        ecu_consumption_lph: float,
        dt_hours: float,
        engine_load_pct: Optional[float] = None,
        altitude_change_m: Optional[float] = None,
        threshold_pct: float = 30.0,
    ) -> dict:
        """
        🆕 v6.2.0: Validate ECU consumption against physics-based model.

        Detects potentially faulty ECU sensors by comparing against calibrated model.

        Args:
            ecu_consumption_lph: ECU-reported consumption in LPH
            dt_hours: Time interval
            engine_load_pct: Engine load percentage
            altitude_change_m: Altitude change in meters
            threshold_pct: Max allowed deviation % (default 30%)

        Returns:
            Dict with validation results:
            {
                'valid': bool,
                'ecu_lph': float,
                'model_lph': float,
                'deviation_pct': float,
                'status': str,  # 'OK', 'WARNING', 'CRITICAL'
                'message': str
            }
        """
        if not self.calibration_loaded:
            return {
                "valid": True,
                "ecu_lph": ecu_consumption_lph,
                "model_lph": None,
                "deviation_pct": 0.0,
                "status": "NO_CALIBRATION",
                "message": "Calibration not loaded, skipping validation",
            }

        # Calculate expected consumption using physics model
        model_consumption_lph = self._calculate_physics_consumption(
            dt_hours, engine_load_pct, altitude_change_m
        )

        # Calculate deviation
        if model_consumption_lph > 0.1:
            deviation_pct = (
                abs(ecu_consumption_lph - model_consumption_lph) / model_consumption_lph
            ) * 100.0
        else:
            deviation_pct = 0.0

        # Determine status
        if deviation_pct > threshold_pct:
            status = "CRITICAL"
            valid = False
            message = f"ECU sensor possibly faulty: {deviation_pct:.1f}% deviation"
        elif deviation_pct > threshold_pct * 0.5:  # Warning at 50% of threshold
            status = "WARNING"
            valid = True
            message = f"ECU reading unusual: {deviation_pct:.1f}% deviation"
        else:
            status = "OK"
            valid = True
            message = "ECU sensor healthy"

        return {
            "valid": valid,
            "ecu_lph": round(ecu_consumption_lph, 2),
            "model_lph": round(model_consumption_lph, 2),
            "deviation_pct": round(deviation_pct, 1),
            "status": status,
            "message": message,
        }

    def check_emergency_reset(
        self, sensor_pct: float, time_gap_hours: float, truck_status: str = "UNKNOWN"
    ) -> bool:
        """
        Emergency reset for high drift after long offline gaps

        Reset when BOTH:
        1. Time gap > 2 hours
        2. Drift > 30%
        """
        if sensor_pct is None or not self.initialized or self.L is None:
            return False

        estimated_pct = (self.L / self.capacity_liters) * 100
        drift_pct = abs(estimated_pct - sensor_pct)

        EMERGENCY_GAP_THRESHOLD = 2.0
        EMERGENCY_DRIFT_THRESHOLD = 30.0

        if (
            time_gap_hours > EMERGENCY_GAP_THRESHOLD
            and drift_pct > EMERGENCY_DRIFT_THRESHOLD
        ):

            logger.warning(
                f"[{self.truck_id}] 🔴 EMERGENCY RESET:\n"
                f"   Time gap: {time_gap_hours:.1f}h, Drift: {drift_pct:.1f}%\n"
                f"   Estimated: {estimated_pct:.1f}%, Sensor: {sensor_pct:.1f}%"
            )

            self.initialize(sensor_pct=sensor_pct)
            self.P_L = 20.0
            return True

        return False

    def auto_resync(
        self, sensor_pct: float, speed: float = None, is_trip_active: bool = None
    ):
        """
        Auto-resync on extreme drift (>15%)
        🔧 v5.8.5: Added 30-minute cooldown to prevent oscillation.
        🔧 v5.9.1 (Fix C5): Added theft protection - don't auto-resync during
                           potential theft conditions (parked + downward drift).
        🔧 v6.3.0: Improved theft protection using internal truck_status

        Args:
            sensor_pct: Current sensor reading as percentage
            speed: Current speed (optional, for theft detection)
            is_trip_active: Whether truck is on active trip (optional)
        """
        if not self.initialized or sensor_pct is None or self.L is None:
            return

        estimated_pct = (self.L / self.capacity_liters) * 100
        drift_pct = abs(estimated_pct - sensor_pct)
        drift_direction = "down" if sensor_pct < estimated_pct else "up"

        RESYNC_THRESHOLD = 15.0
        RESYNC_THRESHOLD_REFUEL = 30.0
        # 🔧 FIX DEC 29: Use configurable cooldown instead of hardcoded
        resync_cooldown_sec = self.config.get("resync_cooldown_sec", 1800)

        # 🆕 v5.8.5: Check cooldown to prevent oscillation
        if hasattr(self, "_last_resync_time") and self._last_resync_time:
            time_since_resync = (
                datetime.now(timezone.utc) - self._last_resync_time
            ).total_seconds()
            if time_since_resync < resync_cooldown_sec:
                return  # Still in cooldown period

        # 🔧 v6.3.0: Determine truck status internally for better theft protection
        # Prefer internal truck_status from update_adaptive_Q_r() if available
        if hasattr(self, "truck_status"):
            # Use tracked status from update_adaptive_Q_r()
            is_parked = self.truck_status == "PARKED"
        else:
            # Fallback to external parameters
            is_parked = speed is not None and speed < 2.0
            is_inactive = is_trip_active is not None and not is_trip_active
            is_parked = is_parked or is_inactive

        # 🆕 v6.3.0: THEFT PROTECTION (production v5.8.6 logic)
        # Block resync on downward drift while parked
        if drift_direction == "down" and drift_pct > RESYNC_THRESHOLD:
            if is_parked:
                # Potential theft - DO NOT auto-resync
                logger.warning(
                    f"[{self.truck_id}] 🔒 THEFT PROTECTION: "
                    f"Blocking resync on downward drift while parked "
                    f"(kalman={estimated_pct:.1f}%, sensor={sensor_pct:.1f}%, "
                    f"drift={drift_pct:.1f}%)"
                )
                self._flag_potential_theft(drift_pct, sensor_pct, estimated_pct)
                self.drift_warning = True
                return  # Don't resync - preserve theft evidence

        if drift_pct > RESYNC_THRESHOLD and (
            not self.recent_refuel or drift_pct > RESYNC_THRESHOLD_REFUEL
        ):
            logger.warning(
                f"[{self.truck_id}] ⚠️ EXTREME DRIFT ({drift_pct:.1f}%) - Auto-resyncing"
            )
            self.initialize(sensor_pct=sensor_pct)
            self._last_resync_time = datetime.now(
                timezone.utc
            )  # 🆕 v5.8.5: Track resync time

    def _flag_potential_theft(
        self, drift_pct: float, sensor_pct: float, estimated_pct: float
    ):
        """
        🆕 v5.9.1 (Fix C5): Flag potential theft for manual review.

        This prevents auto-resync from masking theft events by creating
        a record that can be reviewed by the theft detection system.
        """
        if not hasattr(self, "_potential_theft_flags"):
            self._potential_theft_flags = []

        self._potential_theft_flags.append(
            {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "truck_id": self.truck_id,
                "drift_pct": drift_pct,
                "sensor_pct": sensor_pct,
                "estimated_pct": estimated_pct,
                "potential_gallons_lost": (estimated_pct - sensor_pct)
                / 100
                * self.capacity_liters
                / 3.785,
                "reviewed": False,
            }
        )

        # Keep only last 10 flags
        self._potential_theft_flags = self._potential_theft_flags[-10:]

    def _adaptive_measurement_noise_v2(self) -> float:
        """
        v6.1.0: Adaptive measurement noise (R) based on CONSISTENCY, not magnitude.

        Uses innovation history to detect sensor bias:
        - If last 4 innovations all same sign → sensor biased → R × 2.5
        - If innovations alternate signs → sensor noisy but unbiased → R × 1.0
        - If insufficient history → R × 1.0 (neutral)

        This prevents systematic sensor bias from pulling Kalman estimate away from truth.

        Returns:
            R multiplier (1.0 = normal, 2.5 = biased sensor detected)
        """
        # Need at least 4 measurements to detect bias
        if len(self.innovation_history) < 4:
            self.bias_detected = False
            self.bias_magnitude = 0.0
            return 1.0

        # Check if all innovations have same sign (persistent bias)
        signs = [np.sign(inn) for inn in self.innovation_history]
        all_positive = all(s > 0 for s in signs)
        all_negative = all(s < 0 for s in signs)

        if all_positive or all_negative:
            # Sensor showing persistent bias → reduce trust (increase R)
            self.bias_detected = True
            self.bias_magnitude = sum(self.innovation_history) / len(
                self.innovation_history
            )
            logger.debug(
                f"[{self.truck_id}] Sensor bias detected: "
                f"innovations={list(self.innovation_history)} → R×2.5, "
                f"magnitude={self.bias_magnitude:.2f}L"
            )
            return 2.5
        else:
            # Sensor noisy but unbiased → normal trust
            self.bias_detected = False
            self.bias_magnitude = 0.0
            return 1.0

    def update_adaptive_Q_r(
        self, speed: float = None, rpm: float = None, consumption_lph: float = None
    ):
        """
        🆕 v5.3.0: Update Q_r based on truck status for improved Kalman accuracy.
        🔧 v6.3.0: Now tracks truck_status for theft protection in auto_resync

        Call this before predict() to adapt process noise to operational state.

        Args:
            speed: Current speed in mph
            rpm: Engine RPM
            consumption_lph: Current fuel consumption rate
        """
        # Determine truck status
        if speed is not None and rpm is not None:
            if speed < 1 and rpm < 100:
                status = "PARKED"
            elif speed < 3 and rpm < 900:
                status = "IDLE"
            elif speed < 3:
                status = "STOPPED"
            else:
                status = "MOVING"
        elif speed is not None:
            if speed < 1:
                status = "PARKED"
            elif speed < 5:
                status = "IDLE"
            else:
                status = "MOVING"
        else:
            status = "MOVING"  # Default to moving if unknown

        # 🆕 v6.3.0: Store status for theft protection
        self.truck_status = status

        # Calculate and set adaptive Q_r
        self.Q_r = calculate_adaptive_Q_r(status, consumption_lph or 0)

        logger.debug(
            f"[{self.truck_id}] Adaptive Q_r: {self.Q_r:.4f} (status={status})"
        )

    def get_confidence(self) -> Dict:
        """
        🆕 v5.3.0: Get confidence level of current estimate.

        Returns:
            Dict with level, score, color, description
        """
        return get_kalman_confidence(self.P)

    def update_sensor_quality(
        self,
        satellites: Optional[int] = None,
        voltage: Optional[float] = None,
        is_engine_running: bool = True,
    ) -> float:
        """
        🆕 v5.4.0: Update Q_L based on GPS and voltage quality.
        🔧 v5.8.6: Unified - Q_L now reflects BOTH GPS and voltage factors.

        This provides adaptive measurement noise based on sensor reliability:
        - Poor GPS (few satellites) → increase Q_L (less trust in measurement)
        - Poor voltage → increase Q_L (sensor readings less reliable)

        The combined effect means worse sensor conditions = higher Q_L =
        Kalman filter trusts predictions more than measurements.

        Call this before update() to adapt measurement noise.

        Args:
            satellites: Number of GPS satellites visible
            voltage: Battery/alternator voltage (pwr_int sensor)
            is_engine_running: Whether engine is currently running

        Returns:
            Combined sensor quality factor (0.5-1.0)
        """
        gps_factor = 1.0
        voltage_factor = 1.0

        # Start with base Q_L (moving or static based on current state)
        base_Q_L = self.Q_L_moving if self.is_moving else self.Q_L_static

        # GPS Quality factor
        if (
            satellites is not None
            and GPS_QUALITY_AVAILABLE
            and self.gps_quality_manager
        ):
            adaptive_Q_L = self.gps_quality_manager.get_adaptive_Q_L(
                self.truck_id,
                satellites,
            )
            # Calculate GPS factor relative to base
            gps_factor = adaptive_Q_L / base_Q_L if base_Q_L > 0 else 1.0

            # Store quality info
            gps_result = analyze_gps_quality(satellites, self.truck_id)
            self.last_gps_quality = gps_result.to_dict()

            logger.debug(
                f"[{self.truck_id}] GPS Quality: {gps_result.quality.value} "
                f"({satellites} sats) → factor={gps_factor:.2f}"
            )

        # Voltage Quality factor
        if voltage is not None and VOLTAGE_MONITOR_AVAILABLE:
            voltage_factor = get_voltage_quality_factor(voltage, is_engine_running)
            self.last_voltage_quality = voltage_factor

            # Invert: low voltage quality means HIGHER Q_L (less trust)
            # voltage_factor 0.7 → Q_L multiplier 1.43 (1/0.7)
            voltage_q_multiplier = 1.0 / max(voltage_factor, 0.5)

            if voltage_factor < 0.9:
                logger.debug(
                    f"[{self.truck_id}] Voltage quality degraded: {voltage:.1f}V "
                    f"→ factor={voltage_factor:.2f}, Q_L mult={voltage_q_multiplier:.2f}"
                )
        else:
            voltage_q_multiplier = 1.0

        # 🔧 v5.8.6: UNIFIED Q_L calculation
        # Combined Q_L = base * gps_factor * voltage_multiplier
        # Higher Q_L = less trust in measurement = more smoothing
        combined_Q_L = base_Q_L * gps_factor * voltage_q_multiplier

        # Clamp to reasonable bounds
        self.Q_L = max(0.5, min(combined_Q_L, 20.0))

        # Combined quality factor for reporting (0.5-1.0, higher = better)
        self.sensor_quality_factor = min(1.0, 1.0 / (gps_factor * voltage_q_multiplier))

        logger.debug(
            f"[{self.truck_id}] Unified Q_L: base={base_Q_L:.2f} × "
            f"gps={gps_factor:.2f} × volt={voltage_q_multiplier:.2f} = {self.Q_L:.2f}"
        )

        return self.sensor_quality_factor

    def get_sensor_diagnostics(self) -> Dict:
        """
        🆕 v5.4.0: Get current sensor quality diagnostics.

        Returns:
            Dict with GPS quality, voltage quality, and combined factor
        """
        return {
            "gps_quality": self.last_gps_quality,
            "voltage_quality_factor": self.last_voltage_quality,
            "combined_quality_factor": self.sensor_quality_factor,
            "current_Q_L": self.Q_L,
            "modules_available": {
                "gps_quality": GPS_QUALITY_AVAILABLE,
                "voltage_monitor": VOLTAGE_MONITOR_AVAILABLE,
            },
        }

    # 🔧 FIX DEC 29: Método duplicado eliminado - ver _calculate_physics_consumption() en línea 380
    # 🔧 FIX DEC 29: Método duplicado eliminado - ver validate_ecu_consumption() en línea 420

    def predict(
        self,
        dt_hours: float,
        consumption_lph: float = None,
        rate_lph: float = None,
        speed_mph: float = None,
        rpm: float = None,  # 🆕 v5.15.1: Added to detect engine-off state
    ):
        """Predict next state based on consumption"""
        if not self.initialized:
            return

        # Handle legacy parameter name
        if consumption_lph is None and rate_lph is not None:
            consumption_lph = rate_lph

        # 🔧 v5.9.0 FIX: Large time gaps - update P BEFORE returning
        # Without this, P doesn't grow during offline periods, causing
        # the filter to be "overconfident" when data returns
        if dt_hours > 1.0:
            # Increase P aggressively to reflect uncertainty during gap
            # Factor of 5 accounts for unknown events (refuels, theft, etc.)
            p_increase = self.Q_r * dt_hours * 5.0
            self.P += p_increase
            logger.info(
                f"[{self.truck_id}] Large gap ({dt_hours:.1f}h) - "
                f"skipping prediction, P increased by {p_increase:.2f} to {self.P:.2f}"
            )
            return

        # 🔧 v5.8.4: Handle negative consumption as sensor error
        if consumption_lph is not None and consumption_lph < 0:
            logger.warning(
                f"[{self.truck_id}] Negative consumption {consumption_lph:.2f} LPH detected - "
                f"treating as sensor error, using fallback"
            )
            consumption_lph = None  # Force fallback

        # 🆕 v6.2.1: CRITICAL FIX - Validate ECU vs RPM consistency
        # If engine is OFF (rpm=0) but ECU reports consumption → ECU is wrong
        if rpm is not None and rpm == 0:
            if consumption_lph is not None and consumption_lph > 0.5:
                logger.warning(
                    f"[{self.truck_id}] ⚠️ ECU INCONSISTENCY: "
                    f"rpm=0 (engine OFF) but ECU reports consumption={consumption_lph:.2f} LPH. "
                    f"Forcing consumption to 0.0 (ECU sensor may be faulty)."
                )
            consumption_lph = 0.0  # Engine off - ZERO consumption, always

        # 🔧 v5.15.1: Fallback logic (only if consumption_lph is still None)
        elif consumption_lph is None:
            # Engine running but no ECU data
            if speed_mph is not None and speed_mph < 5:
                consumption_lph = 2.0  # Idle fallback
            else:
                consumption_lph = 15.0  # City fallback

        # Predict: x = x - u * dt
        consumed = consumption_lph * dt_hours
        self.level_liters -= consumed
        self.level_pct = (self.level_liters / self.capacity_liters) * 100.0
        self.consumption_lph = consumption_lph

        if self.L is not None:
            self.L -= consumed

        # Update covariance
        self.P += self.Q_r * dt_hours

    def calculate_ecu_consumption(
        self,
        total_fuel_used: Optional[float],
        dt_hours: float,
        fuel_rate_lph: Optional[float] = None,
    ) -> Optional[float]:
        """
        ECU-based exact consumption calculation

        Uses cumulative fuel counter for accurate consumption.
        Falls back gracefully if ECU data unavailable.
        """
        MAX_CONSUMPTION_GPH = 50.0
        MIN_TIME_DELTA_HOURS = 10 / 3600

        if self.ecu_degraded:
            if self.ecu_last_success_time:
                time_since = (
                    datetime.now(timezone.utc) - self.ecu_last_success_time
                ).total_seconds()
                if time_since > 600:
                    self.ecu_degraded = False
                    self.ecu_failure_count = 0
                else:
                    return None
            else:
                return None

        if total_fuel_used is None:
            self._record_ecu_failure("no_data")
            return None

        if dt_hours < MIN_TIME_DELTA_HOURS:
            return None

        if self.last_total_fuel_used is None:
            self.last_total_fuel_used = total_fuel_used
            self.ecu_consumption_available = False
            return None

        # 🔧 CRITICAL FIX DEC 25 2025: ECU sensors report in LITERS, not GALLONS
        # If total_fuel_used > 300,000, it's definitely in liters (lifetime counter)
        # Normal truck: ~50,000-200,000 gal lifetime vs 180,000-750,000 L
        LITERS_PER_GALLON = 3.78541

        # Detect units and convert to gallons if needed
        if total_fuel_used > 300000 or self.last_total_fuel_used > 300000:
            # Sensor is in LITERS - convert to GALLONS
            total_fuel_gal = total_fuel_used / LITERS_PER_GALLON
            last_fuel_gal = self.last_total_fuel_used / LITERS_PER_GALLON
            logger.debug(
                f"[{self.truck_id}] ECU sensor in LITERS detected "
                f"(total={total_fuel_used:.0f}L → {total_fuel_gal:.0f}gal)"
            )
        else:
            # Sensor already in GALLONS
            total_fuel_gal = total_fuel_used
            last_fuel_gal = self.last_total_fuel_used

        fuel_delta_gal = total_fuel_gal - last_fuel_gal

        if fuel_delta_gal < 0:
            logger.warning(f"[{self.truck_id}] ECU counter reset detected")
            self.last_total_fuel_used = total_fuel_used
            self._record_ecu_failure("reset")
            return None

        consumption_gph = fuel_delta_gal / dt_hours if dt_hours > 0 else 0

        if consumption_gph > MAX_CONSUMPTION_GPH:
            self.last_total_fuel_used = total_fuel_used
            self._record_ecu_failure("high_consumption")
            return None

        self.last_total_fuel_used = total_fuel_used
        consumption_lph = consumption_gph * 3.78541
        self._record_ecu_success()

        return consumption_lph

    def _record_ecu_failure(self, reason: str):
        """Track ECU failures"""
        self.ecu_failure_count += 1
        self.ecu_consumption_available = False

        if self.ecu_failure_count >= 5:
            if not self.ecu_degraded:
                logger.warning(f"[{self.truck_id}] 🔴 ECU DEGRADED ({reason})")
            self.ecu_degraded = True

    def _record_ecu_success(self):
        """Track ECU success"""
        self.ecu_failure_count = 0
        self.ecu_consumption_available = True
        self.ecu_last_success_time = datetime.now(timezone.utc)

        if self.ecu_degraded:
            logger.info(f"[{self.truck_id}] ✅ ECU recovered")
            self.ecu_degraded = False

    # 🔧 v5.9.0: REMOVED calculate_adaptive_noise (dead code)
    # This function was never called - Q_L is now unified in update_sensor_quality()
    # See v5.8.6 for the current adaptive Q_L implementation

    def set_movement_state(self, is_moving: bool):
        """Set movement state for basic adaptive noise"""
        self.is_moving = is_moving
        self.Q_L = self.Q_L_moving if is_moving else self.Q_L_static

    def update(self, measured_pct: float):
        """Update state with measurement using adaptive Kalman gain"""
        # Fix M1: Handle NaN/Inf values to prevent corrupted calculations
        if measured_pct is None or not isinstance(measured_pct, (int, float)):
            logger.warning(f"[{self.truck_id}] Invalid measured_pct: {measured_pct}")
            # 🔧 FIX DEC 29: Track consecutive sensor failures
            self.sensor_skip_count += 1
            if self.sensor_skip_count >= 10:
                logger.error(
                    f"[{self.truck_id}] SENSOR FAILURE: 10+ consecutive invalid readings - "
                    f"filter predictions may diverge from reality"
                )
            return

        import math

        if math.isnan(measured_pct) or math.isinf(measured_pct):
            logger.warning(f"[{self.truck_id}] NaN/Inf measured_pct: {measured_pct}")
            self.sensor_skip_count += 1
            if self.sensor_skip_count >= 10:
                logger.error(
                    f"[{self.truck_id}] SENSOR FAILURE: 10+ consecutive NaN/Inf readings"
                )
            return

        # Reset skip counter on valid reading
        self.sensor_skip_count = 0

        # Clamp to valid range
        measured_pct = max(0.0, min(100.0, measured_pct))

        # ═══════════════════════════════════════════════════════════════════════
        # 🚫 BIODIESEL CORRECTION - DISABLED (DEC 29, 2025)
        # ═══════════════════════════════════════════════════════════════════════
        # This feature is NOT currently used by any truck in the fleet.
        # tanks.yaml does not have biodiesel_blend_pct configured for any truck.
        # All trucks use standard diesel (biodiesel_blend_pct = 0).
        #
        # If biodiesel support is needed in the future:
        # 1. Add biodiesel_blend_pct field to tanks.yaml for specific trucks
        # 2. Load it in wialon_sync_enhanced.py load_tank_config()
        # 3. Pass it to FuelEstimator config
        # 4. VERIFY physics: biodiesel has HIGHER dielectric constant
        #    → capacitive sensors read HIGH → should MULTIPLY to reduce, not DIVIDE
        #
        # Original code preserved for reference:
        # if self.biodiesel_blend_pct > 0:
        #     density_correction = 1.0 - (self.biodiesel_blend_pct / 100.0) * 0.12
        #     measured_pct = measured_pct * density_correction  # FIX: multiply not divide
        #     logger.debug(f"[{self.truck_id}] Biodiesel correction...")
        # ═══════════════════════════════════════════════════════════════════════

        measured_liters = (measured_pct / 100.0) * self.capacity_liters
        self.last_update_time = datetime.now(timezone.utc)

        if not self.initialized:
            self.initialize(sensor_pct=measured_pct)
            return

        # 🆕 v6.1.0: Calculate innovation for bias detection
        innovation = measured_liters - self.level_liters
        self.innovation_history.append(innovation)

        # 🆕 v6.1.0: Adaptive R based on consistency (not magnitude)
        R_multiplier = self._adaptive_measurement_noise_v2()
        R = self.Q_L * R_multiplier

        K = self.P / (self.P + R)

        # Fix M1: Validate K before proceeding
        if math.isnan(K) or math.isinf(K):
            logger.error(
                f"[{self.truck_id}] Invalid Kalman gain K={K}, resetting filter"
            )
            self.initialize(sensor_pct=measured_pct)
            return

        # 🔧 v5.8.2: Dynamic K clamp based on uncertainty (P)
        # Higher P = less certainty = allow more correction
        # Lower P = high certainty = limit correction
        # P typically ranges from 0.5 (high confidence) to 10+ (low confidence)
        if self.P > 5.0:
            k_max = 0.50  # Low confidence: allow larger corrections
        elif self.P > 2.0:
            k_max = 0.35  # Medium confidence
        else:
            k_max = 0.20  # High confidence: limit over-correction

        # 🆕 v5.8.5: Innovation-based K adjustment
        # If innovation is unexpectedly large (>3x expected noise), allow faster correction
        # This helps the filter react quickly to real changes (refuels, actual drift)
        # 🔧 FIX DEC 29: innovation already calculated above for bias detection (line 1054)
        innovation_pct = abs(innovation / self.capacity_liters * 100)
        expected_noise_pct = (R**0.5) * 2  # ~2 sigma of expected measurement noise

        if innovation_pct > expected_noise_pct * 3:
            # Large unexpected change - allow stronger correction
            k_max = min(k_max * 1.5, 0.70)  # Boost k_max but cap at 0.70
            logger.debug(
                f"[{self.truck_id}] Large innovation ({innovation_pct:.1f}%) > "
                f"3x expected ({expected_noise_pct:.1f}%) - boosting K_max to {k_max:.2f}"
            )

        K = min(K, k_max)
        # Innovation ya calculado arriba para bias detection
        self.level_liters += K * innovation
        self.level_pct = (self.level_liters / self.capacity_liters) * 100.0

        if self.L is not None:
            self.L = self.level_liters

        self.P = (1 - K) * self.P

        # Calculate drift
        self.drift_pct = self.level_pct - measured_pct
        self.drift_warning = abs(self.drift_pct) > self.config.get("max_drift_pct", 5.0)
        self.last_fuel_lvl_pct = measured_pct

        self.auto_resync(measured_pct)

    def apply_refuel_reset(
        self, new_fuel_pct: float, timestamp: datetime = None, gallons_added: float = 0
    ):
        """Hard reset after refuel detection"""
        self.L = (new_fuel_pct / 100.0) * self.capacity_liters
        self.level_liters = self.L
        self.level_pct = new_fuel_pct
        self.P_L = 5.0  # High confidence after refuel
        self.P = 1.0
        self.recent_refuel = True
        self.drift_pct = 0.0
        self.drift_warning = False

        logger.info(
            f"[{self.truck_id}] ⛽ Refuel reset: {new_fuel_pct:.1f}% "
            f"(+{gallons_added:.1f} gal)"
        )

    def get_estimate(self) -> Dict:
        """Get current estimate with diagnostics"""
        # 🆕 v5.8.3: Include kalman_confidence in output
        confidence = self.get_confidence()

        estimate = {
            "level_liters": self.level_liters,
            "level_pct": self.level_pct,
            "consumption_lph": self.consumption_lph,
            "drift_pct": self.drift_pct,
            "drift_warning": self.drift_warning,
            "kalman_gain": self.P / (self.P + self.Q_L),
            "is_moving": self.is_moving,
            "ecu_consumption_available": self.ecu_consumption_available,
            # 🆕 v5.4.0: Sensor quality info
            "sensor_quality_factor": self.sensor_quality_factor,
            "current_Q_L": self.Q_L,
            # v5.8.3: Kalman confidence
            "kalman_confidence": confidence,
            # v6.1.0: Bias detection info
            "bias_detected": self.bias_detected,
            "bias_magnitude_pct": (
                round((self.bias_magnitude / self.capacity_liters) * 100, 2)
                if self.bias_detected
                else 0.0
            ),
            "biodiesel_correction_applied": self.biodiesel_blend_pct > 0,
        }

        # Add GPS quality if available
        if self.last_gps_quality:
            estimate["gps_quality"] = self.last_gps_quality.get("quality")
            estimate["gps_satellites"] = self.last_gps_quality.get("satellites")

        return estimate


class AnchorDetector:
    """
    Detects stable conditions (anchors) for Kalman filter calibration.

    Two types:
    1. STATIC: Truck stopped with engine idling
    2. MICRO: Stable cruise on highway
    """

    def __init__(self, config: Dict):
        self.config = config
        self.static_start_time: Optional[datetime] = None
        self.static_fuel_readings: List[float] = []
        self.cruise_readings: List[Dict] = []
        self.last_anchor_time: Optional[datetime] = None
        self.anchor_cooldown_s = 60

    def check_static_anchor(
        self,
        timestamp: datetime,
        speed: Optional[float],
        rpm: Optional[float],
        fuel_pct: Optional[float],
        hdop: Optional[float] = None,
        drift_pct: float = 0.0,
    ) -> Optional[Dict]:
        """Check for STATIC anchor (truck stopped, engine idling)"""
        if speed is None or rpm is None or fuel_pct is None:
            self._reset_static()
            return None

        speed_max = self.config.get("anchor_static_speed_max", 0.5)
        rpm_min = self.config.get("anchor_static_rpm_min", 500)
        hdop_max = self.config.get("anchor_static_hdop_max", 1.5)
        min_duration = self.config.get("anchor_static_min_duration_s", 30)
        drift_min = self.config.get("anchor_static_drift_min", 0.3)

        is_static = (
            speed <= speed_max and rpm >= rpm_min and (hdop is None or hdop <= hdop_max)
        )

        if not is_static:
            self._reset_static()
            return None

        if self.static_start_time is None:
            self.static_start_time = timestamp
            self.static_fuel_readings = [fuel_pct]
            return None

        self.static_fuel_readings.append(fuel_pct)
        duration = (timestamp - self.static_start_time).total_seconds()

        if duration < min_duration:
            return None

        if self.last_anchor_time:
            cooldown = (timestamp - self.last_anchor_time).total_seconds()
            if cooldown < self.anchor_cooldown_s:
                return None

        if len(self.static_fuel_readings) >= 2:
            fuel_var = np.var(self.static_fuel_readings)
            if fuel_var > self.config.get("anchor_static_fuel_var_max", 0.25):
                self._reset_static()
                return None

        if abs(drift_pct) < drift_min:
            return None

        median_fuel = np.median(self.static_fuel_readings)
        self.last_anchor_time = timestamp
        self._reset_static()

        return {
            "type": AnchorType.STATIC,
            "timestamp": timestamp,
            "fuel_pct": median_fuel,
            "duration_s": duration,
            "drift_pct": drift_pct,
        }

    def check_micro_anchor(
        self,
        timestamp: datetime,
        speed: Optional[float],
        fuel_pct: Optional[float],
        hdop: Optional[float] = None,
        altitude_ft: Optional[float] = None,
        drift_pct: float = 0.0,
    ) -> Optional[Dict]:
        """Check for MICRO anchor (stable cruise)"""
        if speed is None or fuel_pct is None:
            self._reset_cruise()
            return None

        speed_min = self.config.get("anchor_micro_speed_min", 30)
        hdop_max = self.config.get("anchor_micro_hdop_max", 2.5)
        min_duration = self.config.get("anchor_micro_min_duration_s", 90)
        drift_min = self.config.get("anchor_micro_drift_min", 0.5)

        is_cruising = speed >= speed_min and (hdop is None or hdop <= hdop_max)

        if not is_cruising:
            self._reset_cruise()
            return None

        self.cruise_readings.append(
            {
                "timestamp": timestamp,
                "speed": speed,
                "fuel_pct": fuel_pct,
                "altitude_ft": altitude_ft,
            }
        )

        if len(self.cruise_readings) > 30:
            self.cruise_readings = self.cruise_readings[-25:]

        if len(self.cruise_readings) < 5:
            return None

        start_time = self.cruise_readings[0]["timestamp"]
        duration = (timestamp - start_time).total_seconds()

        if duration < min_duration:
            return None

        if self.last_anchor_time:
            cooldown = (timestamp - self.last_anchor_time).total_seconds()
            if cooldown < self.anchor_cooldown_s * 2:
                return None

        speeds = [r["speed"] for r in self.cruise_readings]
        fuels = [r["fuel_pct"] for r in self.cruise_readings]

        speed_mean = np.mean(speeds)
        speed_std = np.std(speeds)
        max_speed_std = max(5.0, 0.15 * speed_mean)

        if speed_std > max_speed_std:
            return None

        fuel_var = np.var(fuels)
        if fuel_var > self.config.get("anchor_micro_fuel_var_max", 0.5):
            return None

        if abs(drift_pct) < drift_min:
            return None

        median_fuel = np.median(fuels)
        self.last_anchor_time = timestamp
        self._reset_cruise()

        return {
            "type": AnchorType.MICRO,
            "timestamp": timestamp,
            "fuel_pct": median_fuel,
            "duration_s": duration,
            "speed_mean": speed_mean,
            "drift_pct": drift_pct,
        }

    def _reset_static(self):
        self.static_start_time = None
        self.static_fuel_readings = []

    def _reset_cruise(self):
        self.cruise_readings = []


# ============================================================================
# COMMON_CONFIG - Migrated from fuel_copilot_v2_1_fixed.py for test compatibility
# ============================================================================
COMMON_CONFIG = {
    # ─────────────────────────────────────────────────────────────────────
    # Kalman Filter Parameters
    # ─────────────────────────────────────────────────────────────────────
    "idle_rate_lph": 2.0,  # Liters per hour when idling
    "Q_r": 0.1,  # Process noise for consumption rate
    "Q_L_moving": 4.0,  # Level noise when moving
    "Q_L_static": 1.0,  # Level noise when static
    "Q_L": 4.0,  # Default level noise
    "R_base": 4.0,  # Base measurement noise
    "R_scale_drift": 0.5,  # Scale measurement noise by drift
    # ─────────────────────────────────────────────────────────────────────
    # Drift & Reset Thresholds
    # ─────────────────────────────────────────────────────────────────────
    "max_drift_pct": 7.5,  # Warning threshold for drift
    "reset_drift_pct": 15.0,  # Auto-reset threshold
    "refuel_jump_threshold_pct": 15.0,  # Min jump to detect refuel
    "emergency_drift_pct": 25.0,  # Emergency reset threshold
    # ─────────────────────────────────────────────────────────────────────
    # Static Anchor Parameters
    # ─────────────────────────────────────────────────────────────────────
    "anchor_static_speed_max": 0.5,  # Max speed (km/h) for static
    "anchor_static_rpm_min": 500,  # Min RPM (engine on)
    "anchor_static_hdop_max": 1.5,  # Max HDOP for good GPS
    "anchor_static_min_duration_s": 30,  # Min duration for anchor
    "anchor_static_readings_min": 3,  # Min readings for anchor
    "anchor_static_std_max": 0.5,  # Max std dev of fuel readings
    "anchor_drift_min": 1.5,  # Min drift to trigger anchor
    # ─────────────────────────────────────────────────────────────────────
    # Micro Anchor Parameters (Cruise)
    # ─────────────────────────────────────────────────────────────────────
    "anchor_micro_min_readings": 10,
    "anchor_micro_min_duration_s": 60,
    "anchor_micro_speed_min": 60,  # km/h
    "anchor_micro_speed_max": 100,  # km/h
    "anchor_micro_speed_var_max": 25,  # km/h variance
    "anchor_micro_fuel_var_max": 0.5,  # % variance
    "anchor_micro_drift_min": 2.0,  # Min drift to trigger
    # ─────────────────────────────────────────────────────────────────────
    # Adaptive Q_r (v5.3.0)
    # ─────────────────────────────────────────────────────────────────────
    "Q_r_parked": 0.01,  # Very low noise when parked
    "Q_r_idle": 0.05,  # Low noise when idling
    "Q_r_moving": 0.1,  # Normal noise when moving
}
