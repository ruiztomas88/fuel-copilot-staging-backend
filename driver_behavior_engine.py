"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    DRIVER BEHAVIOR DETECTION ENGINE v1.0.0                     ║
║                            Fuel Copilot 2025                                   ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Purpose: Detect driving behaviors that cause fuel waste                       ║
║                                                                                ║
║  Features:                                                                     ║
║  - Hard acceleration detection (Δspeed/Δt > threshold)                        ║
║  - Hard braking detection                                                      ║
║  - Wrong gear usage (high RPM in low gear)                                    ║
║  - "Heavy foot" scoring (0-100)                                               ║
║  - Fuel waste estimation per behavior                                          ║
║  - Cross-validation: Kalman MPG vs ECU fuel_economy                           ║
║                                                                                ║
║  🎯 KEY INSIGHT: This answers "WHY does truck X lose money?"                  ║
║     → Heavy foot? Excessive idling? Wrong gear? Hard braking?                 ║
║                                                                                ║
║  Data Sources:                                                                 ║
║  - speed: GPS speed (mph)                                                      ║
║  - rpm: Engine RPM                                                             ║
║  - gear: Current gear (1-18) ← 🆕 NEW SENSOR                                  ║
║  - fuel_economy: ECU MPG ← 🆕 NEW SENSOR (cross-validation)                   ║
║  - fuel_rate: Instantaneous fuel consumption (GPH)                            ║
║                                                                                ║
║  Author: Fuel Copilot Team                                                     ║
║  Created: December 2025                                                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS AND CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


class BehaviorType(str, Enum):
    """Types of driving behaviors detected"""

    HARD_ACCELERATION = "hard_acceleration"
    HARD_BRAKING = "hard_braking"
    EXCESSIVE_RPM = "excessive_rpm"
    WRONG_GEAR = "wrong_gear"  # High RPM in low gear when could upshift
    OVERSPEEDING = "overspeeding"
    HARSH_CORNERING = "harsh_cornering"  # Future: needs accelerometer
    EXCESSIVE_IDLE = "excessive_idle"


class SeverityLevel(str, Enum):
    """Severity of behavior event"""

    MINOR = "minor"  # 1-2 penalty points
    MODERATE = "moderate"  # 3-5 penalty points
    SEVERE = "severe"  # 6-10 penalty points
    CRITICAL = "critical"  # 10+ penalty points


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class BehaviorConfig:
    """Configuration thresholds for behavior detection"""

    # Hard acceleration thresholds (mph per second)
    # Semi-trucks: 0-60 mph in ~30-60 seconds = ~1-2 mph/s normal
    accel_minor_threshold: float = 3.0  # mph/s - slight aggressive
    accel_moderate_threshold: float = 4.5  # mph/s - notably aggressive
    accel_severe_threshold: float = 6.0  # mph/s - very aggressive

    # Hard braking thresholds (negative mph per second)
    brake_minor_threshold: float = -4.0  # mph/s
    brake_moderate_threshold: float = -6.0  # mph/s
    brake_severe_threshold: float = -8.0  # mph/s - emergency brake

    # RPM thresholds (semi-truck diesel engines)
    rpm_optimal_min: int = 1200  # Green zone lower
    rpm_optimal_max: int = 1600  # Green zone upper (peak torque)
    rpm_high_warning: int = 1800  # Amber - above peak efficiency
    rpm_excessive: int = 2100  # Red - significant fuel waste
    rpm_redline: int = 2500  # Critical - engine damage risk

    # Gear-RPM correlation (wrong gear detection)
    # If RPM > threshold AND could upshift (not at max gear), flag it
    wrong_gear_rpm_threshold: int = 1700  # RPM where should upshift
    wrong_gear_min_duration_sec: float = 5.0  # Must persist for X seconds

    # Speed thresholds
    speed_warning: float = 65.0  # mph - mild overspeeding
    speed_excessive: float = 70.0  # mph - notable overspeeding
    speed_severe: float = 75.0  # mph - significant fuel waste

    # Fuel waste coefficients (gallons per event, approximate)
    # Based on DOE studies on aggressive driving
    fuel_waste_hard_accel_gal: float = 0.05  # ~0.05 gal per event
    fuel_waste_hard_brake_gal: float = 0.02  # Indirect waste (momentum lost)
    fuel_waste_high_rpm_gal_per_min: float = 0.02  # Extra GPM above optimal
    fuel_waste_wrong_gear_gal_per_min: float = 0.03  # Higher than just high RPM
    fuel_waste_overspeeding_gal_per_min: float = 0.01  # Per mph above 65

    # Cross-validation thresholds
    mpg_cross_validation_tolerance: float = 15.0  # % difference before flagging


# Global config
CONFIG = BehaviorConfig()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class BehaviorEvent:
    """Single detected behavior event"""

    truck_id: str
    timestamp: datetime
    behavior_type: BehaviorType
    severity: SeverityLevel
    value: float  # The measured value that triggered detection
    threshold: float  # The threshold that was exceeded
    duration_sec: float = 0.0  # Duration of event (for sustained behaviors)
    fuel_waste_gal: float = 0.0  # Estimated fuel waste from this event
    context: Dict[str, Any] = field(default_factory=dict)  # Additional context

    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "timestamp": self.timestamp.isoformat(),
            "behavior_type": self.behavior_type.value,
            "severity": self.severity.value,
            "value": round(self.value, 2),
            "threshold": round(self.threshold, 2),
            "duration_sec": round(self.duration_sec, 1),
            "fuel_waste_gal": round(self.fuel_waste_gal, 4),
            "context": self.context,
        }


@dataclass
class HeavyFootScore:
    """Heavy foot score for a driver/truck"""

    truck_id: str
    score: float  # 0-100 (100 = perfect, 0 = heavy foot)
    grade: str  # A, B, C, D, F

    # Component scores
    acceleration_score: float  # 0-100
    braking_score: float  # 0-100
    rpm_score: float  # 0-100
    gear_score: float  # 0-100 (only if gear sensor available)
    speed_score: float  # 0-100

    # Event counts
    hard_accel_count: int = 0
    hard_brake_count: int = 0
    high_rpm_minutes: float = 0.0
    wrong_gear_minutes: float = 0.0
    overspeeding_minutes: float = 0.0

    # Fuel impact
    total_fuel_waste_gal: float = 0.0
    fuel_waste_breakdown: Dict[str, float] = field(default_factory=dict)

    # Period
    period_hours: float = 24.0
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "score": round(self.score, 1),
            "grade": self.grade,
            "components": {
                "acceleration": round(self.acceleration_score, 1),
                "braking": round(self.braking_score, 1),
                "rpm_management": round(self.rpm_score, 1),
                "gear_usage": round(self.gear_score, 1),
                "speed_control": round(self.speed_score, 1),
            },
            "events": {
                "hard_accelerations": self.hard_accel_count,
                "hard_brakes": self.hard_brake_count,
                "high_rpm_minutes": round(self.high_rpm_minutes, 1),
                "wrong_gear_minutes": round(self.wrong_gear_minutes, 1),
                "overspeeding_minutes": round(self.overspeeding_minutes, 1),
            },
            "fuel_impact": {
                "total_waste_gallons": round(self.total_fuel_waste_gal, 2),
                "breakdown": {
                    k: round(v, 3) for k, v in self.fuel_waste_breakdown.items()
                },
            },
            "period_hours": self.period_hours,
            "calculated_at": self.calculated_at.isoformat(),
        }


@dataclass
class MPGCrossValidation:
    """Result of comparing Kalman MPG vs ECU fuel_economy"""

    truck_id: str
    timestamp: datetime
    kalman_mpg: float
    ecu_mpg: float
    difference_pct: float
    is_valid: bool  # Within tolerance?
    recommendation: str

    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "timestamp": self.timestamp.isoformat(),
            "kalman_mpg": round(self.kalman_mpg, 2),
            "ecu_mpg": round(self.ecu_mpg, 2),
            "difference_pct": round(self.difference_pct, 1),
            "is_valid": self.is_valid,
            "recommendation": self.recommendation,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TRUCK STATE TRACKER
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TruckBehaviorState:
    """Tracks behavior state for a single truck"""

    truck_id: str

    # Previous readings for delta calculation
    last_speed: Optional[float] = None
    last_rpm: Optional[int] = None
    last_gear: Optional[int] = None
    last_timestamp: Optional[datetime] = None

    # Sustained behavior tracking
    high_rpm_start: Optional[datetime] = None
    wrong_gear_start: Optional[datetime] = None
    overspeeding_start: Optional[datetime] = None

    # Event history (last 24 hours)
    events: List[BehaviorEvent] = field(default_factory=list)

    # Counters for scoring
    hard_accel_count: int = 0
    hard_brake_count: int = 0
    high_rpm_seconds: float = 0.0
    wrong_gear_seconds: float = 0.0
    overspeeding_seconds: float = 0.0

    # Fuel waste accumulators
    fuel_waste_accel: float = 0.0
    fuel_waste_brake: float = 0.0
    fuel_waste_rpm: float = 0.0
    fuel_waste_gear: float = 0.0
    fuel_waste_speed: float = 0.0

    # MPG cross-validation
    kalman_mpg_samples: deque = field(default_factory=lambda: deque(maxlen=10))
    ecu_mpg_samples: deque = field(default_factory=lambda: deque(maxlen=10))

    def reset_daily(self):
        """Reset counters at start of new day"""
        self.hard_accel_count = 0
        self.hard_brake_count = 0
        self.high_rpm_seconds = 0.0
        self.wrong_gear_seconds = 0.0
        self.overspeeding_seconds = 0.0
        self.fuel_waste_accel = 0.0
        self.fuel_waste_brake = 0.0
        self.fuel_waste_rpm = 0.0
        self.fuel_waste_gear = 0.0
        self.fuel_waste_speed = 0.0
        self.events = []


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE CLASS
# ═══════════════════════════════════════════════════════════════════════════════


class DriverBehaviorEngine:
    """
    🚛 Driver Behavior Detection Engine

    Analyzes sensor data to detect driving behaviors that waste fuel:
    - Hard acceleration (Δspeed/Δt)
    - Hard braking
    - Excessive RPM
    - Wrong gear (high RPM when could upshift)
    - Overspeeding

    Produces:
    - Individual behavior events with severity
    - "Heavy Foot" score (0-100) per truck
    - Fuel waste estimation per behavior type
    - MPG cross-validation (Kalman vs ECU)
    """

    def __init__(self, config: Optional[BehaviorConfig] = None):
        self.config = config or CONFIG
        self.truck_states: Dict[str, TruckBehaviorState] = {}
        self._last_daily_reset: Optional[datetime] = None

    def _get_or_create_state(self, truck_id: str) -> TruckBehaviorState:
        """Get or create state tracker for a truck"""
        if truck_id not in self.truck_states:
            self.truck_states[truck_id] = TruckBehaviorState(truck_id=truck_id)
        return self.truck_states[truck_id]

    def _check_daily_reset(self):
        """Reset counters at midnight UTC"""
        now = datetime.now(timezone.utc)
        if self._last_daily_reset is None or now.date() > self._last_daily_reset.date():
            logger.info(f"🔄 Daily reset of behavior counters")
            for state in self.truck_states.values():
                state.reset_daily()
            self._last_daily_reset = now

    # ═══════════════════════════════════════════════════════════════════════════
    # CORE DETECTION METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def process_reading(
        self,
        truck_id: str,
        timestamp: datetime,
        speed: Optional[float] = None,
        rpm: Optional[int] = None,
        gear: Optional[int] = None,
        fuel_rate: Optional[float] = None,
        fuel_economy: Optional[float] = None,  # ECU MPG
        kalman_mpg: Optional[float] = None,  # Our calculated MPG
        # 🆕 v5.10.1: Brake sensor inputs
        brake_switch: Optional[int] = None,  # Brake pedal (0/1)
        brake_pressure: Optional[float] = None,  # Brake application pressure (psi)
        # 🆕 v5.10.1: Device-detected harsh events (from accelerometer)
        device_harsh_accel: Optional[int] = None,  # Device harsh accel count
        device_harsh_brake: Optional[int] = None,  # Device harsh brake count
    ) -> List[BehaviorEvent]:
        """
        Process a sensor reading and detect behavior events.

        Args:
            truck_id: Truck identifier
            timestamp: Reading timestamp (UTC)
            speed: GPS speed in mph
            rpm: Engine RPM
            gear: Current gear (1-18), None if sensor unavailable
            fuel_rate: Instantaneous fuel consumption (GPH)
            fuel_economy: ECU-reported MPG (for cross-validation)
            kalman_mpg: Our Kalman-filtered MPG
            brake_switch: Brake pedal status (0/1)
            brake_pressure: Brake application pressure (psi)
            device_harsh_accel: Device-detected harsh acceleration event count
            device_harsh_brake: Device-detected harsh braking event count

        Returns:
            List of detected behavior events
        """
        self._check_daily_reset()

        state = self._get_or_create_state(truck_id)
        events: List[BehaviorEvent] = []

        # Calculate time delta
        dt_seconds = 0.0
        if state.last_timestamp is not None:
            dt_seconds = (timestamp - state.last_timestamp).total_seconds()

            # Skip if gap is too large (data gap) or too small (duplicate)
            if dt_seconds > 300 or dt_seconds < 1:
                state.last_speed = speed
                state.last_rpm = rpm
                state.last_gear = gear
                state.last_timestamp = timestamp
                return events

        # ═══════════════════════════════════════════════════════════════════
        # 0. DEVICE-DETECTED HARSH EVENTS (most reliable - from accelerometer)
        # ═══════════════════════════════════════════════════════════════════
        # These come from the device's 280mg/320mg thresholds
        if device_harsh_accel is not None and device_harsh_accel > 0:
            events.append(
                BehaviorEvent(
                    truck_id=truck_id,
                    timestamp=timestamp,
                    behavior_type=BehaviorType.HARD_ACCELERATION,
                    severity=SeverityLevel.MODERATE,  # Device threshold = 280mg ≈ moderate
                    value=280.0,  # mg threshold
                    threshold=280.0,
                    fuel_waste_gal=self.config.fuel_waste_hard_accel_gal
                    * device_harsh_accel,
                    context={
                        "source": "device_accelerometer",
                        "count": device_harsh_accel,
                    },
                )
            )
            state.hard_accel_count += device_harsh_accel
            state.fuel_waste_accel += (
                self.config.fuel_waste_hard_accel_gal * device_harsh_accel
            )

        if device_harsh_brake is not None and device_harsh_brake > 0:
            events.append(
                BehaviorEvent(
                    truck_id=truck_id,
                    timestamp=timestamp,
                    behavior_type=BehaviorType.HARD_BRAKING,
                    severity=SeverityLevel.MODERATE,  # Device threshold = 320mg ≈ moderate
                    value=320.0,  # mg threshold
                    threshold=320.0,
                    fuel_waste_gal=self.config.fuel_waste_hard_brake_gal
                    * device_harsh_brake,
                    context={
                        "source": "device_accelerometer",
                        "count": device_harsh_brake,
                    },
                )
            )
            state.hard_brake_count += device_harsh_brake
            state.fuel_waste_brake += (
                self.config.fuel_waste_hard_brake_gal * device_harsh_brake
            )

        # ═══════════════════════════════════════════════════════════════════
        # 1. ACCELERATION/BRAKING DETECTION (calculated from speed delta)
        # ═══════════════════════════════════════════════════════════════════
        if speed is not None and state.last_speed is not None and dt_seconds > 0:
            accel_mpss = (speed - state.last_speed) / dt_seconds  # mph/s

            # Hard acceleration (only if device didn't already detect)
            if device_harsh_accel is None or device_harsh_accel == 0:
                if accel_mpss >= self.config.accel_severe_threshold:
                    events.append(
                        self._create_accel_event(
                            truck_id, timestamp, accel_mpss, SeverityLevel.SEVERE
                        )
                    )
                    state.hard_accel_count += 1
                    state.fuel_waste_accel += self.config.fuel_waste_hard_accel_gal * 2

                elif accel_mpss >= self.config.accel_moderate_threshold:
                    events.append(
                        self._create_accel_event(
                            truck_id, timestamp, accel_mpss, SeverityLevel.MODERATE
                        )
                    )
                    state.hard_accel_count += 1
                    state.fuel_waste_accel += self.config.fuel_waste_hard_accel_gal

                elif accel_mpss >= self.config.accel_minor_threshold:
                    events.append(
                        self._create_accel_event(
                            truck_id, timestamp, accel_mpss, SeverityLevel.MINOR
                        )
                    )
                    state.hard_accel_count += 1
                    state.fuel_waste_accel += (
                        self.config.fuel_waste_hard_accel_gal * 0.5
                    )

            # Hard braking (only if device didn't already detect)
            if device_harsh_brake is None or device_harsh_brake == 0:
                if accel_mpss <= self.config.brake_severe_threshold:
                    events.append(
                        self._create_brake_event(
                            truck_id, timestamp, accel_mpss, SeverityLevel.SEVERE
                        )
                    )
                    state.hard_brake_count += 1
                    state.fuel_waste_brake += self.config.fuel_waste_hard_brake_gal * 2

                elif accel_mpss <= self.config.brake_moderate_threshold:
                    events.append(
                        self._create_brake_event(
                            truck_id, timestamp, accel_mpss, SeverityLevel.MODERATE
                        )
                    )
                    state.hard_brake_count += 1
                    state.fuel_waste_brake += self.config.fuel_waste_hard_brake_gal

                elif accel_mpss <= self.config.brake_minor_threshold:
                    events.append(
                        self._create_brake_event(
                            truck_id, timestamp, accel_mpss, SeverityLevel.MINOR
                        )
                    )
                    state.hard_brake_count += 1
                    state.fuel_waste_brake += (
                        self.config.fuel_waste_hard_brake_gal * 0.5
                    )

        # ═══════════════════════════════════════════════════════════════════
        # 2. RPM MANAGEMENT DETECTION
        # ═══════════════════════════════════════════════════════════════════
        if rpm is not None and rpm > 0:
            if rpm >= self.config.rpm_excessive:
                # Track duration
                if state.high_rpm_start is None:
                    state.high_rpm_start = timestamp

                duration = (timestamp - state.high_rpm_start).total_seconds()
                state.high_rpm_seconds += dt_seconds
                state.fuel_waste_rpm += (
                    dt_seconds / 60
                ) * self.config.fuel_waste_high_rpm_gal_per_min

                if duration >= 10 and rpm >= self.config.rpm_redline:
                    events.append(
                        BehaviorEvent(
                            truck_id=truck_id,
                            timestamp=timestamp,
                            behavior_type=BehaviorType.EXCESSIVE_RPM,
                            severity=SeverityLevel.CRITICAL,
                            value=float(rpm),
                            threshold=float(self.config.rpm_redline),
                            duration_sec=duration,
                            fuel_waste_gal=(duration / 60)
                            * self.config.fuel_waste_high_rpm_gal_per_min,
                            context={"gear": gear, "speed": speed},
                        )
                    )
                elif duration >= 5:
                    events.append(
                        BehaviorEvent(
                            truck_id=truck_id,
                            timestamp=timestamp,
                            behavior_type=BehaviorType.EXCESSIVE_RPM,
                            severity=(
                                SeverityLevel.MODERATE
                                if rpm < self.config.rpm_redline
                                else SeverityLevel.SEVERE
                            ),
                            value=float(rpm),
                            threshold=float(self.config.rpm_excessive),
                            duration_sec=duration,
                            fuel_waste_gal=(duration / 60)
                            * self.config.fuel_waste_high_rpm_gal_per_min,
                            context={"gear": gear, "speed": speed},
                        )
                    )
            else:
                state.high_rpm_start = None

        # ═══════════════════════════════════════════════════════════════════
        # 3. WRONG GEAR DETECTION (requires gear sensor)
        # ═══════════════════════════════════════════════════════════════════
        if gear is not None and rpm is not None and speed is not None:
            # Wrong gear: High RPM but not at max gear (could upshift)
            # Typical semi: 10-18 gears, assume max gear ~12-18
            max_gear = 13  # Conservative estimate for most semis

            is_wrong_gear = (
                rpm >= self.config.wrong_gear_rpm_threshold
                and gear < max_gear
                and speed > 25  # Only above 25 mph (not starting from stop)
            )

            if is_wrong_gear:
                if state.wrong_gear_start is None:
                    state.wrong_gear_start = timestamp

                duration = (timestamp - state.wrong_gear_start).total_seconds()
                state.wrong_gear_seconds += dt_seconds
                state.fuel_waste_gear += (
                    dt_seconds / 60
                ) * self.config.fuel_waste_wrong_gear_gal_per_min

                if duration >= self.config.wrong_gear_min_duration_sec:
                    events.append(
                        BehaviorEvent(
                            truck_id=truck_id,
                            timestamp=timestamp,
                            behavior_type=BehaviorType.WRONG_GEAR,
                            severity=SeverityLevel.MODERATE,
                            value=float(rpm),
                            threshold=float(self.config.wrong_gear_rpm_threshold),
                            duration_sec=duration,
                            fuel_waste_gal=(duration / 60)
                            * self.config.fuel_waste_wrong_gear_gal_per_min,
                            context={
                                "gear": gear,
                                "speed": speed,
                                "should_upshift": True,
                                "message": f"RPM {rpm} en marcha {gear}, podría subir marcha",
                            },
                        )
                    )
            else:
                state.wrong_gear_start = None

        # ═══════════════════════════════════════════════════════════════════
        # 4. OVERSPEEDING DETECTION
        # ═══════════════════════════════════════════════════════════════════
        if speed is not None:
            if speed >= self.config.speed_warning:
                if state.overspeeding_start is None:
                    state.overspeeding_start = timestamp

                duration = (timestamp - state.overspeeding_start).total_seconds()
                state.overspeeding_seconds += dt_seconds

                # Fuel waste scales with speed above 65
                mph_over = speed - 65
                state.fuel_waste_speed += (
                    (dt_seconds / 60)
                    * self.config.fuel_waste_overspeeding_gal_per_min
                    * mph_over
                )

                if duration >= 60:  # Only report after 1 minute sustained
                    severity = SeverityLevel.MINOR
                    if speed >= self.config.speed_severe:
                        severity = SeverityLevel.SEVERE
                    elif speed >= self.config.speed_excessive:
                        severity = SeverityLevel.MODERATE

                    events.append(
                        BehaviorEvent(
                            truck_id=truck_id,
                            timestamp=timestamp,
                            behavior_type=BehaviorType.OVERSPEEDING,
                            severity=severity,
                            value=speed,
                            threshold=self.config.speed_warning,
                            duration_sec=duration,
                            fuel_waste_gal=(duration / 60)
                            * self.config.fuel_waste_overspeeding_gal_per_min
                            * mph_over,
                            context={"mph_over_limit": mph_over},
                        )
                    )
            else:
                state.overspeeding_start = None

        # ═══════════════════════════════════════════════════════════════════
        # 5. MPG CROSS-VALIDATION
        # ═══════════════════════════════════════════════════════════════════
        if kalman_mpg is not None and kalman_mpg > 0:
            state.kalman_mpg_samples.append(kalman_mpg)

        if fuel_economy is not None and fuel_economy > 0:
            state.ecu_mpg_samples.append(fuel_economy)

        # Update state
        state.last_speed = speed
        state.last_rpm = rpm
        state.last_gear = gear
        state.last_timestamp = timestamp

        # Add events to state history
        state.events.extend(events)

        return events

    def _create_accel_event(
        self, truck_id: str, timestamp: datetime, accel: float, severity: SeverityLevel
    ) -> BehaviorEvent:
        """Create a hard acceleration event"""
        return BehaviorEvent(
            truck_id=truck_id,
            timestamp=timestamp,
            behavior_type=BehaviorType.HARD_ACCELERATION,
            severity=severity,
            value=accel,
            threshold=self.config.accel_minor_threshold,
            fuel_waste_gal=self.config.fuel_waste_hard_accel_gal,
            context={"unit": "mph/s"},
        )

    def _create_brake_event(
        self, truck_id: str, timestamp: datetime, decel: float, severity: SeverityLevel
    ) -> BehaviorEvent:
        """Create a hard braking event"""
        return BehaviorEvent(
            truck_id=truck_id,
            timestamp=timestamp,
            behavior_type=BehaviorType.HARD_BRAKING,
            severity=severity,
            value=abs(decel),  # Store as positive
            threshold=abs(self.config.brake_minor_threshold),
            fuel_waste_gal=self.config.fuel_waste_hard_brake_gal,
            context={"unit": "mph/s", "indirect_waste": True},
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # SCORING METHODS
    # ═══════════════════════════════════════════════════════════════════════════

    def calculate_heavy_foot_score(
        self,
        truck_id: str,
        period_hours: float = 24.0,
        total_driving_hours: Optional[float] = None,
    ) -> HeavyFootScore:
        """
        Calculate the "Heavy Foot" score for a truck.

        Score: 100 = Perfect driver, 0 = Extremely aggressive

        Components:
        - Acceleration (30%): Penalize hard accelerations
        - Braking (20%): Penalize hard braking
        - RPM (20%): Penalize time above optimal RPM
        - Gear (15%): Penalize wrong gear usage
        - Speed (15%): Penalize overspeeding

        Args:
            truck_id: Truck identifier
            period_hours: Period to calculate over (default 24h)
            total_driving_hours: Total driving hours in period (for normalization)

        Returns:
            HeavyFootScore with breakdown
        """
        state = self._get_or_create_state(truck_id)

        # If no driving hours provided, estimate from events
        if total_driving_hours is None:
            total_driving_hours = max(1.0, period_hours * 0.4)  # Assume 40% driving

        driving_minutes = total_driving_hours * 60

        # Calculate component scores

        # 1. Acceleration score (100 - penalties)
        # ~2 hard accels per hour is acceptable, more is aggressive
        expected_accels = total_driving_hours * 2
        accel_penalty = max(0, state.hard_accel_count - expected_accels) * 3
        accel_score = max(0, 100 - accel_penalty)

        # 2. Braking score
        expected_brakes = total_driving_hours * 3
        brake_penalty = max(0, state.hard_brake_count - expected_brakes) * 2
        brake_score = max(0, 100 - brake_penalty)

        # 3. RPM score
        # More than 10% of time in high RPM is concerning
        high_rpm_pct = (
            (state.high_rpm_seconds / 60) / driving_minutes * 100
            if driving_minutes > 0
            else 0
        )
        rpm_penalty = max(0, high_rpm_pct - 10) * 3
        rpm_score = max(0, 100 - rpm_penalty)

        # 4. Gear score (only if we have gear data)
        if state.wrong_gear_seconds > 0:
            wrong_gear_pct = (
                (state.wrong_gear_seconds / 60) / driving_minutes * 100
                if driving_minutes > 0
                else 0
            )
            gear_penalty = max(0, wrong_gear_pct - 5) * 4
            gear_score = max(0, 100 - gear_penalty)
        else:
            gear_score = 100.0  # No gear data, assume optimal

        # 5. Speed score
        # More than 5% overspeeding is concerning
        overspeeding_pct = (
            (state.overspeeding_seconds / 60) / driving_minutes * 100
            if driving_minutes > 0
            else 0
        )
        speed_penalty = max(0, overspeeding_pct - 5) * 3
        speed_score = max(0, 100 - speed_penalty)

        # Calculate weighted overall score
        overall_score = (
            accel_score * 0.30
            + brake_score * 0.20
            + rpm_score * 0.20
            + gear_score * 0.15
            + speed_score * 0.15
        )

        # Determine grade
        if overall_score >= 90:
            grade = "A"
        elif overall_score >= 80:
            grade = "B"
        elif overall_score >= 70:
            grade = "C"
        elif overall_score >= 60:
            grade = "D"
        else:
            grade = "F"

        # Total fuel waste
        total_waste = (
            state.fuel_waste_accel
            + state.fuel_waste_brake
            + state.fuel_waste_rpm
            + state.fuel_waste_gear
            + state.fuel_waste_speed
        )

        return HeavyFootScore(
            truck_id=truck_id,
            score=overall_score,
            grade=grade,
            acceleration_score=accel_score,
            braking_score=brake_score,
            rpm_score=rpm_score,
            gear_score=gear_score,
            speed_score=speed_score,
            hard_accel_count=state.hard_accel_count,
            hard_brake_count=state.hard_brake_count,
            high_rpm_minutes=state.high_rpm_seconds / 60,
            wrong_gear_minutes=state.wrong_gear_seconds / 60,
            overspeeding_minutes=state.overspeeding_seconds / 60,
            total_fuel_waste_gal=total_waste,
            fuel_waste_breakdown={
                "hard_acceleration": state.fuel_waste_accel,
                "hard_braking": state.fuel_waste_brake,
                "high_rpm": state.fuel_waste_rpm,
                "wrong_gear": state.fuel_waste_gear,
                "overspeeding": state.fuel_waste_speed,
            },
            period_hours=period_hours,
        )

    def cross_validate_mpg(self, truck_id: str) -> Optional[MPGCrossValidation]:
        """
        Compare Kalman MPG vs ECU fuel_economy sensor.

        Returns validation result if enough samples available.
        """
        state = self._get_or_create_state(truck_id)

        if len(state.kalman_mpg_samples) < 5 or len(state.ecu_mpg_samples) < 5:
            return None  # Not enough data

        kalman_avg = sum(state.kalman_mpg_samples) / len(state.kalman_mpg_samples)
        ecu_avg = sum(state.ecu_mpg_samples) / len(state.ecu_mpg_samples)

        if ecu_avg <= 0:
            return None

        difference_pct = abs(kalman_avg - ecu_avg) / ecu_avg * 100
        is_valid = difference_pct <= self.config.mpg_cross_validation_tolerance

        if is_valid:
            recommendation = "✅ MPG validated - Kalman estimate matches ECU"
        elif kalman_avg > ecu_avg:
            recommendation = f"⚠️ Kalman MPG {difference_pct:.1f}% higher than ECU - may be overestimating"
        else:
            recommendation = f"⚠️ Kalman MPG {difference_pct:.1f}% lower than ECU - may be underestimating"

        return MPGCrossValidation(
            truck_id=truck_id,
            timestamp=datetime.now(timezone.utc),
            kalman_mpg=kalman_avg,
            ecu_mpg=ecu_avg,
            difference_pct=difference_pct,
            is_valid=is_valid,
            recommendation=recommendation,
        )

    # ═══════════════════════════════════════════════════════════════════════════
    # FLEET ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════

    def get_fleet_behavior_summary(self) -> Dict[str, Any]:
        """
        Get fleet-wide behavior summary.

        🔧 v6.2.5: Now loads from database if no in-memory data available.

        Returns breakdown of:
        - Best/worst performers
        - Total fuel waste by category
        - Common issues
        """
        # If we have in-memory state, use it
        if self.truck_states:
            return self._get_behavior_summary_from_memory()

        # Otherwise, load from database
        logger.info("[BehaviorEngine] No in-memory state, loading from database...")
        return self._get_behavior_summary_from_database()

    def _get_behavior_summary_from_memory(self) -> Dict[str, Any]:
        """Get behavior summary from in-memory truck states"""
        scores = []
        total_waste = {
            "hard_acceleration": 0.0,
            "hard_braking": 0.0,
            "high_rpm": 0.0,
            "wrong_gear": 0.0,
            "overspeeding": 0.0,
        }

        # Track total events for behavior scores
        total_accel_events = 0
        total_brake_events = 0
        total_rpm_events = 0
        total_speed_events = 0

        for truck_id, state in self.truck_states.items():
            score = self.calculate_heavy_foot_score(truck_id)
            scores.append(score)

            total_waste["hard_acceleration"] += state.fuel_waste_accel
            total_waste["hard_braking"] += state.fuel_waste_brake
            total_waste["high_rpm"] += state.fuel_waste_rpm
            total_waste["wrong_gear"] += state.fuel_waste_gear
            total_waste["overspeeding"] += state.fuel_waste_speed

            # Count events from score attributes (not dict)
            total_accel_events += score.hard_accel_count
            total_brake_events += score.hard_brake_count
            total_rpm_events += score.high_rpm_minutes
            total_speed_events += score.overspeeding_minutes

        # Sort by score (ascending = worst first)
        scores.sort(key=lambda x: x.score)

        # Identify biggest issue
        biggest_waste = max(total_waste.items(), key=lambda x: x[1])

        # Calculate behavior scores (similar to database version)
        n_trucks = len(scores) if scores else 1
        avg_daily_accel = total_accel_events / n_trucks
        avg_daily_brake = total_brake_events / n_trucks
        avg_daily_rpm = total_rpm_events / n_trucks
        avg_daily_speed = total_speed_events / n_trucks

        behavior_scores = {
            "acceleration": round(max(0, min(100, 100 - (avg_daily_accel * 8))), 1),
            "braking": round(max(0, min(100, 100 - (avg_daily_brake * 6))), 1),
            "rpm_mgmt": round(max(0, min(100, 100 - (avg_daily_rpm * 2))), 1),
            "gear_usage": round(max(0, min(100, 100 - (avg_daily_rpm * 1.5))), 1),
            "speed_control": round(max(0, min(100, 100 - (avg_daily_speed * 1))), 1),
        }

        # Count needs work
        needs_work_count = len([s for s in scores if s.score < 70])

        return {
            "fleet_size": len(scores),
            "average_score": (
                round(sum(s.score for s in scores) / len(scores), 1) if scores else 0
            ),
            "best_performers": [s.to_dict() for s in scores[-3:]],  # Top 3
            "worst_performers": [s.to_dict() for s in scores[:3]],  # Bottom 3
            "total_fuel_waste_gal": round(sum(total_waste.values()), 2),
            "waste_breakdown": {k: round(v, 3) for k, v in total_waste.items()},
            "behavior_scores": behavior_scores,  # 🆕 Fleet-wide behavior scores by category
            "needs_work_count": needs_work_count,  # 🆕 Count of trucks with score < 70
            "biggest_issue": {
                "category": biggest_waste[0],
                "gallons": round(biggest_waste[1], 2),
            },
            "recommendations": self._generate_fleet_recommendations(
                scores, total_waste
            ),
            "data_source": "real-time",
        }

    def _get_behavior_summary_from_database(self) -> Dict[str, Any]:
        """
        🆕 v6.2.5: Get behavior summary from database (last 7 days).

        Uses harsh_accel, harsh_brake columns from fuel_metrics table.
        Calculates scores based on event counts per truck.
        """
        try:
            from sqlalchemy import text

            from database_mysql import get_sqlalchemy_engine

            engine = get_sqlalchemy_engine()

            # Get behavior events from last 7 days
            # 🔧 DEC 30 2025: Updated to use REAL harsh_accel, harsh_brake, gear columns
            # These columns are now populated from calculate_acceleration() in wialon_sync
            query = """
                SELECT 
                    truck_id,
                    -- 🆕 DEC 30 2025: REAL harsh event counts from speed delta detection
                    SUM(COALESCE(harsh_accel, 0)) as harsh_accel_count,
                    SUM(COALESCE(harsh_brake, 0)) as harsh_brake_count,
                    -- High RPM: count minutes where RPM > 1800 (excessive)
                    SUM(CASE WHEN rpm > 1800 THEN 0.25 ELSE 0 END) as high_rpm_minutes,
                    -- Overspeeding: count minutes where speed > 65
                    SUM(CASE WHEN speed_mph > 65 THEN 0.25 ELSE 0 END) as overspeed_minutes,
                    -- 🆕 DEC 30 2025: Wrong gear detection (high RPM in high gear while moving slow)
                    SUM(CASE 
                        WHEN gear IS NOT NULL AND gear > 0 AND gear <= 6 
                        AND rpm > 1600 AND speed_mph > 25 THEN 1 
                        ELSE 0 
                    END) as wrong_gear_events,
                    -- MPG data for scoring
                    AVG(CASE WHEN speed_mph > 10 THEN mpg_current END) as avg_mpg,
                    COUNT(DISTINCT DATE(timestamp_utc)) as active_days,
                    COUNT(*) as total_readings
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 7 DAY)
                GROUP BY truck_id
                HAVING active_days >= 1
                ORDER BY harsh_accel_count DESC
            """

            with engine.connect() as conn:
                result = conn.execute(text(query))
                rows = result.fetchall()

            if not rows:
                # Return empty but valid response instead of error
                logger.warning(
                    "No truck data in database for last 7 days, returning empty data"
                )
                return {
                    "fleet_size": 0,
                    "average_score": 0,
                    "best_performers": [],
                    "worst_performers": [],
                    "total_fuel_waste_gal": 0,
                    "waste_breakdown": {
                        "hard_acceleration": 0,
                        "hard_braking": 0,
                        "high_rpm": 0,
                        "wrong_gear": 0,
                        "overspeeding": 0,
                    },
                    "behavior_scores": {
                        "acceleration": 100,
                        "braking": 100,
                        "rpm_mgmt": 100,
                        "gear_usage": 100,
                        "speed_control": 100,
                    },
                    "needs_work_count": 0,
                    "biggest_issue": {"category": "none", "gallons": 0},
                    "recommendations": ["No data available for the last 7 days"],
                    "data_source": "database",
                    "period_days": 7,
                }

            # Calculate scores and waste for each truck
            truck_data = []
            total_waste = {
                "hard_acceleration": 0.0,
                "hard_braking": 0.0,
                "high_rpm": 0.0,
                "wrong_gear": 0.0,
                "overspeeding": 0.0,
            }

            for row in rows:
                truck_id = row[0]
                # 🔧 DEC 30 2025: Updated column mapping to use REAL harsh event data
                harsh_accel_count = int(row[1] or 0)  # REAL from speed delta
                harsh_brake_count = int(row[2] or 0)  # REAL from speed delta
                high_rpm_min = float(row[3] or 0)
                overspeed_min = float(row[4] or 0)
                wrong_gear_events = int(row[5] or 0)  # REAL from gear vs RPM analysis
                avg_mpg = float(row[6]) if row[6] else 6.5
                active_days = int(row[7] or 1)
                total_readings = int(row[8] or 1)

                # Use REAL event counts now instead of estimates
                daily_accel = harsh_accel_count / active_days
                daily_brake = harsh_brake_count / active_days
                daily_rpm_high = high_rpm_min / active_days
                daily_overspeed = overspeed_min / active_days
                daily_wrong_gear = wrong_gear_events / active_days

                # Calculate score (100 = perfect, lower = worse)
                # 🔧 DEC 30 2025: Updated scoring using REAL event data
                accel_penalty = min(
                    daily_accel * 4, 20
                )  # Up to 20 points (4 pts per harsh accel/day)
                brake_penalty = min(
                    daily_brake * 3, 15
                )  # Up to 15 points (3 pts per harsh brake/day)
                rpm_penalty = min(daily_rpm_high * 0.3, 15)  # Up to 15 points
                speed_penalty = min(daily_overspeed * 0.2, 15)  # Up to 15 points
                gear_penalty = min(
                    daily_wrong_gear * 2, 10
                )  # Up to 10 points (2 pts per wrong gear/day)

                score = max(
                    0,
                    100
                    - accel_penalty
                    - brake_penalty
                    - rpm_penalty
                    - speed_penalty
                    - gear_penalty,
                )

                # Calculate fuel waste estimates (gallons)
                waste_accel = harsh_accel_count * self.config.fuel_waste_hard_accel_gal
                waste_brake = harsh_brake_count * self.config.fuel_waste_hard_brake_gal
                waste_rpm = high_rpm_min * self.config.fuel_waste_high_rpm_gal_per_min
                waste_speed = (
                    overspeed_min * self.config.fuel_waste_overspeeding_gal_per_min
                )
                # 🆕 DEC 30 2025: Wrong gear fuel waste (estimated 0.02 gal per event)
                waste_wrong_gear = wrong_gear_events * 0.02

                total_waste["hard_acceleration"] += waste_accel
                total_waste["hard_braking"] += waste_brake
                total_waste["high_rpm"] += waste_rpm
                total_waste["wrong_gear"] += waste_wrong_gear
                total_waste["overspeeding"] += waste_speed

                # Determine grade
                if score >= 90:
                    grade = "A"
                elif score >= 80:
                    grade = "B"
                elif score >= 70:
                    grade = "C"
                elif score >= 60:
                    grade = "D"
                else:
                    grade = "F"

                trend = "stable"

                truck_data.append(
                    {
                        "truck_id": truck_id,
                        "score": round(score, 1),
                        "grade": grade,
                        "trend": trend,
                        # 🔧 DEC 30 2025: Updated to use REAL event counts
                        "components": {
                            "acceleration": round(
                                max(0, min(100, 100 - (daily_accel * 8))), 1
                            ),
                            "braking": round(
                                max(0, min(100, 100 - (daily_brake * 6))), 1
                            ),
                            "rpm_management": round(
                                max(0, min(100, 100 - (daily_rpm_high * 0.3))), 1
                            ),
                            "gear_usage": round(
                                max(0, min(100, 100 - (daily_wrong_gear * 5))), 1
                            ),
                            "speed_control": round(
                                max(0, min(100, 100 - (daily_overspeed * 0.2))), 1
                            ),
                        },
                        "events": {
                            "hard_accelerations": harsh_accel_count,  # REAL
                            "hard_brakes": harsh_brake_count,  # REAL
                            "high_rpm_minutes": round(high_rpm_min, 1),
                            "wrong_gear_events": wrong_gear_events,  # REAL
                            "overspeeding_minutes": round(overspeed_min, 1),
                        },
                        "fuel_impact": {
                            "total_waste_gallons": round(
                                waste_accel
                                + waste_brake
                                + waste_rpm
                                + waste_speed
                                + waste_wrong_gear,
                                2,
                            ),
                            "breakdown": {
                                "accel_gal": round(waste_accel, 3),
                                "brake_gal": round(waste_brake, 3),
                                "rpm_gal": round(waste_rpm, 3),
                                "gear_gal": round(waste_wrong_gear, 3),
                                "speed_gal": round(waste_speed, 3),
                            },
                        },
                        "avg_mpg": round(avg_mpg, 1),
                        "active_days": active_days,
                    }
                )

            # Sort by score
            truck_data.sort(key=lambda x: x["score"])

            # Calculate average score
            avg_score = (
                sum(t["score"] for t in truck_data) / len(truck_data)
                if truck_data
                else 0
            )

            # 🆕 Calculate behavior scores per category (aggregate across fleet)
            # Score = 100 - penalty based on average events per truck
            n_trucks = len(truck_data) if truck_data else 1
            total_accel_events = sum(
                t["events"].get("hard_accelerations", 0) for t in truck_data
            )
            total_brake_events = sum(
                t["events"].get("hard_brakes", 0) for t in truck_data
            )
            total_rpm_min = sum(
                t["events"].get("high_rpm_minutes", 0) for t in truck_data
            )
            total_overspeed_min = sum(
                t["events"].get("overspeeding_minutes", 0) for t in truck_data
            )

            # Calculate avg events per truck per day (assuming 7 days period)
            days = 7
            avg_daily_accel = (total_accel_events / n_trucks) / days
            avg_daily_brake = (total_brake_events / n_trucks) / days
            avg_daily_rpm = (total_rpm_min / n_trucks) / days
            avg_daily_speed = (total_overspeed_min / n_trucks) / days

            # Score formula: 100 - (events * penalty_factor), capped at min 0
            # More aggressive scaling to show realistic scores
            accel_score = max(
                0, min(100, 100 - (avg_daily_accel * 8))
            )  # 8 events/day = 36% penalty
            brake_score = max(
                0, min(100, 100 - (avg_daily_brake * 6))
            )  # 6 events/day = 36% penalty
            rpm_score = max(
                0, min(100, 100 - (avg_daily_rpm * 2))
            )  # 20 min/day = 40% penalty
            gear_score = max(0, min(100, 100 - (avg_daily_rpm * 1.5)))  # Related to RPM
            speed_score = max(
                0, min(100, 100 - (avg_daily_speed * 1))
            )  # 40 min/day = 40% penalty

            behavior_scores = {
                "acceleration": round(accel_score, 1),
                "braking": round(brake_score, 1),
                "rpm_mgmt": round(rpm_score, 1),
                "gear_usage": round(gear_score, 1),
                "speed_control": round(speed_score, 1),
            }

            # Identify biggest issue
            biggest_waste = max(total_waste.items(), key=lambda x: x[1])

            # Generate recommendations
            recommendations = self._generate_fleet_recommendations_from_data(
                truck_data, total_waste, avg_score
            )

            # Count trucks needing work (score < 70)
            needs_work_count = len([t for t in truck_data if t["score"] < 70])

            return {
                "fleet_size": len(truck_data),
                "average_score": round(avg_score, 1),
                "best_performers": (
                    truck_data[-3:][::-1] if len(truck_data) >= 3 else truck_data[::-1]
                ),  # Top 3 (highest scores)
                "worst_performers": truck_data[:3],  # Bottom 3 (lowest scores)
                "total_fuel_waste_gal": round(sum(total_waste.values()), 2),
                "waste_breakdown": {k: round(v, 3) for k, v in total_waste.items()},
                "behavior_scores": behavior_scores,  # 🆕 Fleet-wide behavior scores by category
                "needs_work_count": needs_work_count,  # 🆕 Count of trucks with score < 70
                "biggest_issue": {
                    "category": biggest_waste[0],
                    "gallons": round(biggest_waste[1], 2),
                },
                "recommendations": recommendations,
                "data_source": "database",
                "period_days": 7,
            }

        except Exception as e:
            logger.error(
                f"Error loading behavior summary from database: {e}", exc_info=True
            )
            # Return empty but valid response instead of error to avoid 404
            return {
                "fleet_size": 0,
                "average_score": 0,
                "best_performers": [],
                "worst_performers": [],
                "total_fuel_waste_gal": 0,
                "waste_breakdown": {
                    "hard_acceleration": 0,
                    "hard_braking": 0,
                    "high_rpm": 0,
                    "wrong_gear": 0,
                    "overspeeding": 0,
                },
                "behavior_scores": {
                    "acceleration": 100,
                    "braking": 100,
                    "rpm_mgmt": 100,
                    "gear_usage": 100,
                    "speed_control": 100,
                },
                "needs_work_count": 0,
                "biggest_issue": {"category": "error", "gallons": 0},
                "recommendations": [f"Error loading data: {str(e)}"],
                "data_source": "database",
                "period_days": 7,
                "error_detail": str(e),
            }

    def _generate_fleet_recommendations_from_data(
        self, truck_data: List[Dict], waste: Dict[str, float], avg_score: float
    ) -> List[str]:
        """Generate recommendations based on database data"""
        recommendations = []

        if avg_score < 70:
            recommendations.append(
                "🚨 Fleet average score is below 70 - consider driver training program"
            )
        elif avg_score >= 85:
            recommendations.append(
                "✅ Fleet is performing well! Focus on maintaining good habits."
            )

        # Check biggest waste category
        max_waste_category = max(waste.items(), key=lambda x: x[1])

        if max_waste_category[1] > 0:
            if max_waste_category[0] == "hard_acceleration":
                recommendations.append(
                    "⚡ Hard acceleration is primary fuel waste source - train drivers on smooth acceleration"
                )
            elif max_waste_category[0] == "hard_braking":
                recommendations.append(
                    "🛑 Frequent hard braking detected - encourage anticipatory driving"
                )
            elif max_waste_category[0] == "high_rpm":
                recommendations.append(
                    "🔧 High RPM operation is wasting fuel - train drivers on optimal RPM range (1200-1600)"
                )
            elif max_waste_category[0] == "overspeeding":
                recommendations.append(
                    "🏎️ Overspeeding is wasting fuel - each mph above 65 reduces efficiency by ~0.1 MPG"
                )

        # Check for outliers
        outliers = [t for t in truck_data if t["score"] < 50]
        if outliers:
            truck_ids = [t["truck_id"] for t in outliers]
            recommendations.append(
                f"⚠️ {len(outliers)} trucks need immediate attention: {', '.join(truck_ids[:5])}"
            )

        return recommendations

    def _generate_fleet_recommendations(
        self, scores: List[HeavyFootScore], waste: Dict[str, float]
    ) -> List[str]:
        """Generate actionable recommendations based on fleet data"""
        recommendations = []

        # Check for widespread issues
        avg_score = sum(s.score for s in scores) / len(scores) if scores else 0

        if avg_score < 70:
            recommendations.append(
                "🚨 Fleet average score is below 70 - consider driver training program"
            )

        # Check biggest waste category
        max_waste_category = max(waste.items(), key=lambda x: x[1])

        if max_waste_category[0] == "hard_acceleration":
            recommendations.append(
                "⚡ Hard acceleration is primary fuel waste source - train drivers on smooth acceleration"
            )
        elif max_waste_category[0] == "high_rpm":
            recommendations.append(
                "🔧 High RPM operation is wasting fuel - train drivers on optimal RPM range (1200-1600)"
            )
        elif max_waste_category[0] == "wrong_gear":
            recommendations.append(
                "⚙️ Wrong gear usage detected - drivers should upshift earlier to stay in torque band"
            )
        elif max_waste_category[0] == "overspeeding":
            recommendations.append(
                "🏎️ Overspeeding is wasting fuel - each mph above 65 reduces efficiency by ~0.1 MPG"
            )

        # Check for outliers (very bad performers)
        outliers = [s for s in scores if s.score < 50]
        if outliers:
            truck_ids = [s.truck_id for s in outliers]
            recommendations.append(
                f"⚠️ {len(outliers)} trucks need immediate attention: {', '.join(truck_ids[:5])}"
            )

        return recommendations

    def cleanup_inactive_trucks(
        self, active_truck_ids: set, max_inactive_days: int = 30
    ) -> int:
        """
        🆕 v6.5.0: Remove state for trucks inactive > max_inactive_days.

        Prevents memory leaks from trucks removed from fleet or long offline.

        Args:
            active_truck_ids: Set of currently active truck IDs
            max_inactive_days: Days of inactivity before cleanup (default 30)

        Returns:
            Number of trucks cleaned up
        """
        from datetime import datetime, timedelta, timezone

        cleaned_count = 0
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=max_inactive_days)
        trucks_to_remove = []

        for truck_id, state in self.truck_states.items():
            # Remove if not in active fleet
            if truck_id not in active_truck_ids:
                trucks_to_remove.append(truck_id)
                continue

            # Check if last data is older than cutoff
            if state.last_timestamp and state.last_timestamp < cutoff_time:
                trucks_to_remove.append(truck_id)

        # Remove inactive trucks
        for truck_id in trucks_to_remove:
            del self.truck_states[truck_id]
            cleaned_count += 1
            logger.info(f"🧹 Cleaned up behavior state for inactive truck: {truck_id}")

        return cleaned_count


# ═══════════════════════════════════════════════════════════════════════════════
# COACHING TIPS ENGINE v1.1.0
# ═══════════════════════════════════════════════════════════════════════════════

# Bilingual coaching tips library - personalized by behavior
COACHING_TIPS_LIBRARY = {
    "hard_acceleration": {
        "mild": {
            "en": "💡 Tip: Accelerate smoothly over 10-15 seconds to improve fuel economy by up to 10%.",
            "es": "💡 Tip: Acelera suavemente durante 10-15 segundos para mejorar el consumo hasta un 10%.",
        },
        "moderate": {
            "en": "⚠️ Your hard accelerations are costing ~$0.15 each. Try pretending there's an egg under the pedal.",
            "es": "⚠️ Tus aceleraciones bruscas cuestan ~$0.15 cada una. Imagina que hay un huevo bajo el pedal.",
        },
        "severe": {
            "en": "🚨 Aggressive acceleration detected. Each event wastes 0.05 gal. This week: ~${waste:.2f} lost.",
            "es": "🚨 Aceleración agresiva detectada. Cada evento desperdicia 0.05 gal. Esta semana: ~${waste:.2f} perdidos.",
        },
    },
    "hard_braking": {
        "mild": {
            "en": "💡 Tip: Anticipate stops by coasting. Looking further ahead saves brakes AND fuel.",
            "es": "💡 Tip: Anticipa las paradas dejando rodar. Mirar más adelante ahorra frenos Y combustible.",
        },
        "moderate": {
            "en": "⚠️ Hard braking wastes momentum. Each event loses energy equivalent to ~0.02 gallons.",
            "es": "⚠️ El frenado brusco desperdicia momentum. Cada evento pierde energía equivalente a ~0.02 galones.",
        },
        "severe": {
            "en": "🚨 Frequent hard braking detected. This indicates late reaction or tailgating. Safety concern.",
            "es": "🚨 Frenados bruscos frecuentes detectados. Indica reacción tardía o seguir muy cerca. Riesgo de seguridad.",
        },
    },
    "high_rpm": {
        "mild": {
            "en": "💡 Tip: Sweet spot is 1200-1600 RPM. Your engine's peak torque = best efficiency.",
            "es": "💡 Tip: El punto óptimo es 1200-1600 RPM. Torque máximo de tu motor = mejor eficiencia.",
        },
        "moderate": {
            "en": "⚠️ Running above 1800 RPM? That's {rpm_pct:.0f}% above optimal. Upshift earlier to save fuel.",
            "es": "⚠️ ¿Corriendo arriba de 1800 RPM? Eso es {rpm_pct:.0f}% arriba de lo óptimo. Sube cambio antes.",
        },
        "severe": {
            "en": "🚨 Excessive RPM burning fuel fast. Every minute at 2100+ RPM wastes ~0.02 gal extra.",
            "es": "🚨 RPM excesivo quema combustible rápido. Cada minuto a 2100+ RPM desperdicia ~0.02 gal extra.",
        },
    },
    "wrong_gear": {
        "mild": {
            "en": "💡 Tip: Match RPM to speed. If RPM > 1700 and you can upshift, do it!",
            "es": "💡 Tip: Sincroniza RPM con velocidad. Si RPM > 1700 y puedes subir cambio, ¡hazlo!",
        },
        "moderate": {
            "en": "⚠️ Wrong gear detected {min:.0f}+ minutes. Upshifting earlier saves ~0.03 gal/min.",
            "es": "⚠️ Cambio incorrecto detectado {min:.0f}+ minutos. Subir cambio antes ahorra ~0.03 gal/min.",
        },
        "severe": {
            "en": "🚨 Significant wrong gear usage. This is costing ~${waste:.2f}/day in extra fuel.",
            "es": "🚨 Uso significativo de cambio incorrecto. Esto cuesta ~${waste:.2f}/día en combustible extra.",
        },
    },
    "overspeeding": {
        "mild": {
            "en": "💡 Tip: 65 mph = optimal. Each mph above reduces efficiency by ~0.1 MPG.",
            "es": "💡 Tip: 65 mph = óptimo. Cada mph arriba reduce eficiencia ~0.1 MPG.",
        },
        "moderate": {
            "en": "⚠️ Averaging {avg_speed:.0f} mph. Slowing to 65 could save ~${weekly_savings:.0f}/week.",
            "es": "⚠️ Promediando {avg_speed:.0f} mph. Bajar a 65 podría ahorrar ~${weekly_savings:.0f}/semana.",
        },
        "severe": {
            "en": "🚨 Speed consistently above 70 mph. Fuel economy drops ~15% compared to 65 mph.",
            "es": "🚨 Velocidad constantemente arriba de 70 mph. Economía de combustible cae ~15% vs 65 mph.",
        },
    },
    "idle": {
        "mild": {
            "en": "💡 Tip: 1 hour idle = 1 gallon. Consider APU or turn off when parked > 3 min.",
            "es": "💡 Tip: 1 hora idle = 1 galón. Considera APU o apagar cuando estacionas > 3 min.",
        },
        "moderate": {
            "en": "⚠️ Idle time {idle_pct:.0f}% of driving. Fleet avg is {fleet_idle:.0f}%. Reducing saves ~${potential_save:.0f}/month.",
            "es": "⚠️ Tiempo idle {idle_pct:.0f}% del manejo. Promedio flota es {fleet_idle:.0f}%. Reducir ahorra ~${potential_save:.0f}/mes.",
        },
        "severe": {
            "en": "🚨 Excessive idling detected. You're using ~{idle_gal:.1f} gal/day just sitting still.",
            "es": "🚨 Ralentí excesivo detectado. Estás usando ~{idle_gal:.1f} gal/día solo estando parado.",
        },
    },
    "mpg_performance": {
        "below_baseline": {
            "en": "📊 Your MPG ({mpg:.1f}) is {pct:.0f}% below fleet baseline ({baseline:.1f}). Focus on smooth driving.",
            "es": "📊 Tu MPG ({mpg:.1f}) está {pct:.0f}% abajo del baseline de flota ({baseline:.1f}). Enfócate en manejo suave.",
        },
        "at_baseline": {
            "en": "✅ On track! Your MPG ({mpg:.1f}) matches fleet baseline. Keep it up!",
            "es": "✅ ¡En buen camino! Tu MPG ({mpg:.1f}) iguala el baseline de flota. ¡Sigue así!",
        },
        "above_baseline": {
            "en": "🌟 Excellent! Your MPG ({mpg:.1f}) is {pct:.0f}% ABOVE baseline. You're a fuel champion!",
            "es": "🌟 ¡Excelente! Tu MPG ({mpg:.1f}) está {pct:.0f}% ARRIBA del baseline. ¡Eres un campeón del combustible!",
        },
    },
    "overall_grade": {
        "A": {
            "en": "🏆 Grade A - Excellent driver! Share your techniques with the team.",
            "es": "🏆 Calificación A - ¡Excelente conductor! Comparte tus técnicas con el equipo.",
        },
        "B": {
            "en": "👍 Grade B - Good performance. Small tweaks can push you to A level.",
            "es": "👍 Calificación B - Buen desempeño. Pequeños ajustes pueden llevarte a nivel A.",
        },
        "C": {
            "en": "📈 Grade C - Room for improvement. Focus on your biggest issue first.",
            "es": "📈 Calificación C - Espacio para mejorar. Enfócate en tu problema más grande primero.",
        },
        "D": {
            "en": "⚠️ Grade D - Needs attention. Let's schedule a coaching session.",
            "es": "⚠️ Calificación D - Necesita atención. Programemos una sesión de coaching.",
        },
        "F": {
            "en": "🚨 Grade F - Urgent improvement needed. Contact your fleet manager.",
            "es": "🚨 Calificación F - Mejora urgente necesaria. Contacta a tu gerente de flota.",
        },
    },
}


def generate_coaching_tips(
    driver_data: Dict[str, Any],
    language: str = "en",
    max_tips: int = 5,
) -> List[Dict[str, Any]]:
    """
    Generate personalized coaching tips based on driver performance data.

    Args:
        driver_data: Dict with scores, metrics, etc from driver scorecard
        language: "en" or "es"
        max_tips: Maximum number of tips to return

    Returns:
        List of tip dicts with priority, category, message, and potential_savings
    """
    tips = []
    scores = driver_data.get("scores", {})
    metrics = driver_data.get("metrics", {})
    overall_score = driver_data.get("overall_score", 50)
    grade = driver_data.get("grade", "C")

    # Fuel price for savings calculations
    FUEL_PRICE = 3.50  # $/gal
    BASELINE_MPG = 6.5

    # Determine severity level based on score
    def get_severity(score: float) -> str:
        if score >= 80:
            return "mild"
        elif score >= 60:
            return "moderate"
        return "severe"

    # 1. Analyze each behavior category
    behavior_priorities = []

    # Speed optimization
    speed_score = scores.get("speed_optimization", 70)
    if speed_score < 85:
        severity = get_severity(speed_score)
        avg_speed = metrics.get("avg_speed_mph", 65)
        weekly_miles = metrics.get("total_miles", 500) / 7 * 7  # Weekly projection
        # Calculate savings: each mph above 65 = ~0.1 MPG loss
        mph_above_65 = max(0, avg_speed - 65)
        mpg_loss = mph_above_65 * 0.1
        weekly_fuel_without = weekly_miles / max(BASELINE_MPG - mpg_loss, 3)
        weekly_fuel_with = weekly_miles / BASELINE_MPG
        weekly_savings = (weekly_fuel_without - weekly_fuel_with) * FUEL_PRICE

        tip_template = COACHING_TIPS_LIBRARY["overspeeding"].get(severity, {})
        message = tip_template.get(language, tip_template.get("en", ""))
        message = message.format(avg_speed=avg_speed, weekly_savings=weekly_savings)

        behavior_priorities.append(
            {
                "priority": 100 - speed_score,
                "category": "overspeeding",
                "message": message,
                "potential_savings_weekly": round(weekly_savings, 2),
                "score": speed_score,
                "severity": severity,
            }
        )

    # RPM discipline
    rpm_score = scores.get("rpm_discipline", 70)
    if rpm_score < 85:
        severity = get_severity(rpm_score)
        avg_rpm = metrics.get("avg_rpm", 1500)
        rpm_pct = max(0, (avg_rpm - 1600) / 1600 * 100) if avg_rpm > 1600 else 0

        tip_template = COACHING_TIPS_LIBRARY["high_rpm"].get(severity, {})
        message = tip_template.get(language, tip_template.get("en", ""))
        message = message.format(rpm_pct=rpm_pct)

        # Estimate weekly waste: ~0.02 gal/min at high RPM
        estimated_high_rpm_mins = (100 - rpm_score) / 100 * 60 * 8  # per day estimate
        weekly_waste = estimated_high_rpm_mins * 7 * 0.02

        behavior_priorities.append(
            {
                "priority": 100 - rpm_score,
                "category": "high_rpm",
                "message": message,
                "potential_savings_weekly": round(weekly_waste * FUEL_PRICE, 2),
                "score": rpm_score,
                "severity": severity,
            }
        )

    # Idle management
    idle_score = scores.get("idle_management", 70)
    if idle_score < 85:
        severity = get_severity(idle_score)
        idle_pct = metrics.get("idle_pct", 15)
        fleet_idle = 10.0  # Assume fleet average

        # Estimate savings: 1 gal/hour idle, ~8 hours driving/day
        daily_idle_hours = (idle_pct / 100) * 8
        monthly_idle_gal = daily_idle_hours * 22  # 22 working days
        potential_save = monthly_idle_gal * 0.5 * FUEL_PRICE  # Assume can cut 50%

        tip_template = COACHING_TIPS_LIBRARY["idle"].get(severity, {})
        message = tip_template.get(language, tip_template.get("en", ""))
        message = message.format(
            idle_pct=idle_pct,
            fleet_idle=fleet_idle,
            potential_save=potential_save,
            idle_gal=daily_idle_hours,
        )

        behavior_priorities.append(
            {
                "priority": 100 - idle_score,
                "category": "idle_management",
                "message": message,
                "potential_savings_weekly": round(potential_save / 4, 2),
                "score": idle_score,
                "severity": severity,
            }
        )

    # MPG Performance
    mpg_score = scores.get("mpg_performance", 70)
    avg_mpg = metrics.get("avg_mpg", BASELINE_MPG)
    mpg_diff_pct = ((avg_mpg - BASELINE_MPG) / BASELINE_MPG) * 100

    if mpg_diff_pct < -5:
        category = "below_baseline"
        pct = abs(mpg_diff_pct)
    elif mpg_diff_pct > 5:
        category = "above_baseline"
        pct = mpg_diff_pct
    else:
        category = "at_baseline"
        pct = 0

    tip_template = COACHING_TIPS_LIBRARY["mpg_performance"].get(category, {})
    message = tip_template.get(language, tip_template.get("en", ""))
    message = message.format(mpg=avg_mpg, pct=pct, baseline=BASELINE_MPG)

    behavior_priorities.append(
        {
            "priority": 50 if category == "below_baseline" else 10,
            "category": "mpg_performance",
            "message": message,
            "potential_savings_weekly": 0,
            "score": mpg_score,
            "severity": "info",
        }
    )

    # Overall grade tip
    grade_key = grade[0] if grade else "C"  # Handle "A+", "A-", etc.
    tip_template = COACHING_TIPS_LIBRARY["overall_grade"].get(grade_key, {})
    message = tip_template.get(language, tip_template.get("en", ""))

    behavior_priorities.append(
        {
            "priority": 5,  # Always show but low priority
            "category": "overall_grade",
            "message": message,
            "potential_savings_weekly": 0,
            "score": overall_score,
            "severity": "info",
        }
    )

    # Sort by priority (highest first) and take top N
    behavior_priorities.sort(key=lambda x: x["priority"], reverse=True)
    tips = behavior_priorities[:max_tips]

    return tips


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

# Singleton instance for use across the application
_behavior_engine: Optional[DriverBehaviorEngine] = None


def get_behavior_engine() -> DriverBehaviorEngine:
    """Get or create the global behavior engine instance"""
    global _behavior_engine
    if _behavior_engine is None:
        _behavior_engine = DriverBehaviorEngine()
    return _behavior_engine


# ═══════════════════════════════════════════════════════════════════════════════
# CLI TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 70)
    print("🚛 DRIVER BEHAVIOR DETECTION ENGINE v1.0.0")
    print("=" * 70)

    engine = get_behavior_engine()

    # Simulate some readings
    test_truck = "TEST001"
    base_time = datetime.now(timezone.utc)

    # Normal driving
    for i in range(10):
        engine.process_reading(
            truck_id=test_truck,
            timestamp=base_time + timedelta(seconds=i * 15),
            speed=55 + i * 0.5,
            rpm=1400,
            gear=10,
        )

    # Hard acceleration
    engine.process_reading(
        truck_id=test_truck,
        timestamp=base_time + timedelta(seconds=160),
        speed=40,
        rpm=1400,
        gear=8,
    )
    engine.process_reading(
        truck_id=test_truck,
        timestamp=base_time + timedelta(seconds=163),
        speed=60,  # +20 mph in 3 sec = 6.67 mph/s (severe)
        rpm=2200,
        gear=8,
    )

    # Wrong gear (high RPM in low gear)
    for i in range(5):
        engine.process_reading(
            truck_id=test_truck,
            timestamp=base_time + timedelta(seconds=180 + i * 10),
            speed=50,
            rpm=1900,  # High RPM
            gear=6,  # Low gear (could upshift)
        )

    # Calculate score
    score = engine.calculate_heavy_foot_score(
        test_truck, period_hours=1, total_driving_hours=0.5
    )

    print("\n📊 HEAVY FOOT SCORE:")
    print(json.dumps(score.to_dict(), indent=2))

    # Show events
    state = engine.truck_states[test_truck]
    print(f"\n📋 DETECTED EVENTS ({len(state.events)}):")
    for event in state.events:
        print(
            f"  [{event.severity.value.upper()}] {event.behavior_type.value}: {event.value:.2f}"
        )
