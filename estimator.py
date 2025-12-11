"""
Fuel Estimator Module - Extracted from fuel_copilot_v2_1_fixed.py

Kalman Filter for Fuel Level Estimation with:
- Adaptive noise based on physical conditions
- ECU-based consumption calculation
- Emergency reset and auto-resync
- Anchor-based calibration support
- 🆕 v5.3.0: Adaptive Q_r based on truck status (PARKED/IDLE/MOVING)
- 🆕 v5.3.0: Kalman confidence indicator

Author: Fuel Copilot Team
Version: 5.3.0
Date: December 9, 2025
"""

import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass
from enum import Enum
import numpy as np

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

    - PARKED: Very low process noise (fuel shouldn't change)
    - STOPPED/IDLE: Low process noise (only idle consumption)
    - MOVING: Higher process noise (active consumption)

    This improves Kalman filter accuracy by adjusting expectations
    based on what the truck is actually doing.

    Args:
        truck_status: "PARKED", "STOPPED", "IDLE", or "MOVING"
        consumption_lph: Current fuel consumption in liters per hour

    Returns:
        Recommended Q_r (process noise) value
    """
    if truck_status == "PARKED":
        return 0.01  # Almost no expected change
    elif truck_status == "STOPPED":
        return 0.05  # Small idle consumption
    elif truck_status == "IDLE":
        return 0.05 + (consumption_lph / 100) * 0.02
    else:  # MOVING
        # Base + proportional to consumption rate
        return 0.1 + (consumption_lph / 50) * 0.1


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
    Q_r: float = 0.1  # Process noise (model)
    Q_L_moving: float = 4.0  # Measurement noise when moving
    Q_L_static: float = 1.0  # Measurement noise when static

    # Drift thresholds
    max_drift_pct: float = 7.5
    emergency_drift_threshold: float = 30.0
    emergency_gap_hours: float = 2.0
    auto_resync_threshold: float = 15.0

    # ECU validation
    min_consumption_gph: float = 0.1
    max_consumption_gph: float = 50.0
    max_ecu_failures: int = 5


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

        # Internal Kalman state
        self.L = None
        self.P_L = 20.0

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

    def auto_resync(self, sensor_pct: float):
        """Auto-resync on extreme drift (>15%)"""
        if not self.initialized or sensor_pct is None or self.L is None:
            return

        estimated_pct = (self.L / self.capacity_liters) * 100
        drift_pct = abs(estimated_pct - sensor_pct)

        RESYNC_THRESHOLD = 15.0
        RESYNC_THRESHOLD_REFUEL = 30.0

        if drift_pct > RESYNC_THRESHOLD and (
            not self.recent_refuel or drift_pct > RESYNC_THRESHOLD_REFUEL
        ):
            logger.warning(
                f"[{self.truck_id}] ⚠️ EXTREME DRIFT ({drift_pct:.1f}%) - Auto-resyncing"
            )
            self.initialize(sensor_pct=sensor_pct)

    def update_adaptive_Q_r(
        self, speed: float = None, rpm: float = None, consumption_lph: float = None
    ):
        """
        🆕 v5.3.0: Update Q_r based on truck status for improved Kalman accuracy.

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

    def predict(
        self,
        dt_hours: float,
        consumption_lph: float = None,
        rate_lph: float = None,
        speed_mph: float = None,
    ):
        """Predict next state based on consumption"""
        if not self.initialized:
            return

        # Handle legacy parameter name
        if consumption_lph is None and rate_lph is not None:
            consumption_lph = rate_lph

        # Skip large time gaps
        if dt_hours > 1.0:
            return

        # Idle fallback if no consumption provided
        if consumption_lph is None or consumption_lph < 0:
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

        fuel_delta_gal = total_fuel_used - self.last_total_fuel_used

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

    def calculate_adaptive_noise(
        self,
        speed: Optional[float],
        altitude: Optional[float],
        timestamp: datetime,
        engine_load: Optional[float] = None,
    ) -> float:
        """
        Intelligent adaptive noise based on physical conditions:
        - Grade/incline
        - Acceleration
        - Slosh from stop-and-go
        - Engine load
        """
        Q_L_BASE = 1.0
        Q_L_MOVING = 2.0
        Q_L_GRADE = 3.0
        Q_L_ACCEL = 4.0
        Q_L_SLOSH = 5.0
        Q_L_MAX = 6.0

        noise_factors = []

        if speed is None or speed < 1.0:
            self.is_moving = False
            return Q_L_BASE

        self.is_moving = True
        noise_factors.append(("moving", Q_L_MOVING))

        # Grade detection
        if altitude is not None and self.last_altitude is not None and speed > 5:
            time_delta_h = 15 / 3600
            distance_mi = speed * time_delta_h
            distance_ft = distance_mi * 5280

            if distance_ft > 10:
                altitude_delta = altitude - self.last_altitude
                grade_pct = (altitude_delta / distance_ft) * 100

                if abs(grade_pct) > 10:
                    noise_factors.append(("steep_grade", Q_L_MAX))
                elif abs(grade_pct) > 6:
                    noise_factors.append(("medium_grade", Q_L_GRADE + 1.5))
                elif abs(grade_pct) > 3:
                    noise_factors.append(("mild_grade", Q_L_GRADE))

        # Acceleration detection
        if speed is not None and self.last_speed is not None:
            accel = abs(speed - self.last_speed) / 15
            if accel > 3:
                noise_factors.append(("hard_accel", Q_L_SLOSH + 1.0))
            elif accel > 2:
                noise_factors.append(("moderate_accel", Q_L_ACCEL))
            elif accel > 1:
                noise_factors.append(("mild_accel", Q_L_ACCEL - 1.0))

        # Speed variance (slosh)
        self.speed_history.append(speed)
        if len(self.speed_history) > 10:
            self.speed_history.pop(0)

        if len(self.speed_history) >= 5:
            speed_std = np.std(self.speed_history)
            speed_mean = np.mean(self.speed_history)

            if speed_mean > 5:
                cv = speed_std / speed_mean
                if cv > 0.5:
                    noise_factors.append(("stop_and_go", Q_L_SLOSH))
                elif cv > 0.3:
                    noise_factors.append(("variable_speed", Q_L_GRADE))

        # High speed
        if speed > 70:
            noise_factors.append(("high_speed", Q_L_MOVING + 0.5))

        # Engine load
        if engine_load is not None:
            if engine_load > 80:
                noise_factors.append(("high_engine_load", Q_L_SLOSH))
            elif engine_load > 60:
                noise_factors.append(("medium_engine_load", Q_L_ACCEL))
            elif engine_load > 40:
                noise_factors.append(("mild_engine_load", Q_L_GRADE))

        self.last_speed = speed
        self.last_altitude = altitude
        self.last_timestamp = timestamp

        if noise_factors:
            final_Q_L = max(f[1] for f in noise_factors)
            return min(final_Q_L, Q_L_MAX)

        return Q_L_MOVING

    def set_movement_state(self, is_moving: bool):
        """Set movement state for basic adaptive noise"""
        self.is_moving = is_moving
        self.Q_L = self.Q_L_moving if is_moving else self.Q_L_static

    def update(self, measured_pct: float):
        """Update state with measurement using adaptive Kalman gain"""
        measured_liters = (measured_pct / 100.0) * self.capacity_liters
        self.last_update_time = datetime.now(timezone.utc)

        if not self.initialized:
            self.initialize(sensor_pct=measured_pct)
            return

        # Kalman Gain
        R = self.Q_L
        K = self.P / (self.P + R)
        K = min(K, 0.30)  # Clamp to prevent over-correction

        # Update state
        innovation = measured_liters - self.level_liters
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
        return {
            "level_liters": self.level_liters,
            "level_pct": self.level_pct,
            "consumption_lph": self.consumption_lph,
            "drift_pct": self.drift_pct,
            "drift_warning": self.drift_warning,
            "kalman_gain": self.P / (self.P + self.Q_L),
            "is_moving": self.is_moving,
            "ecu_consumption_available": self.ecu_consumption_available,
        }


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
