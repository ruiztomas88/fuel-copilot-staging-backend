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
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import deque

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
                state.fuel_waste_brake += self.config.fuel_waste_hard_brake_gal * 0.5

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

        Returns breakdown of:
        - Best/worst performers
        - Total fuel waste by category
        - Common issues
        """
        if not self.truck_states:
            return {"error": "No truck data available"}

        scores = []
        total_waste = {
            "hard_acceleration": 0.0,
            "hard_braking": 0.0,
            "high_rpm": 0.0,
            "wrong_gear": 0.0,
            "overspeeding": 0.0,
        }

        for truck_id, state in self.truck_states.items():
            score = self.calculate_heavy_foot_score(truck_id)
            scores.append(score)

            total_waste["hard_acceleration"] += state.fuel_waste_accel
            total_waste["hard_braking"] += state.fuel_waste_brake
            total_waste["high_rpm"] += state.fuel_waste_rpm
            total_waste["wrong_gear"] += state.fuel_waste_gear
            total_waste["overspeeding"] += state.fuel_waste_speed

        # Sort by score (ascending = worst first)
        scores.sort(key=lambda x: x.score)

        # Identify biggest issue
        biggest_waste = max(total_waste.items(), key=lambda x: x[1])

        return {
            "fleet_size": len(scores),
            "average_score": round(sum(s.score for s in scores) / len(scores), 1),
            "best_performers": [s.to_dict() for s in scores[-3:]],  # Top 3
            "worst_performers": [s.to_dict() for s in scores[:3]],  # Bottom 3
            "total_fuel_waste_gal": round(sum(total_waste.values()), 2),
            "waste_breakdown": {k: round(v, 3) for k, v in total_waste.items()},
            "biggest_issue": {
                "category": biggest_waste[0],
                "gallons": round(biggest_waste[1], 2),
            },
            "recommendations": self._generate_fleet_recommendations(
                scores, total_waste
            ),
        }

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
