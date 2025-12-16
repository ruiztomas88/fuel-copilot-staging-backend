"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║               COMPONENT WEAR PREDICTION ENGINE v1.0.0                          ║
║                         Fuel Copilot 2025                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Purpose: Predict component wear and remaining life using sensor data          ║
║                                                                                ║
║  🎯 KEY FEATURE: Answers "Brake pad wear detected - Est. 2,400 mi remaining"  ║
║                                                                                ║
║  Components Tracked:                                                           ║
║  - Brake pads/shoes (using brake_app_press, brake_switch events)              ║
║  - Turbo health (using turbo_temp, boost correlation)                         ║
║  - Transmission (using trans_temp trending)                                    ║
║  - Engine oil (using oil_temp, oil_press trending)                            ║
║  - Air filter (using intake_press vs barometer)                               ║
║  - DEF system (using def_level consumption rate)                              ║
║                                                                                ║
║  Data Sources (Pacific Track sensors):                                         ║
║  - brake_app_press, brake_switch, brake_primary_press                         ║
║  - turbo_temp, intercooler_temp, boost/intake_press                           ║
║  - trans_temp (transmission oil temperature)                                   ║
║  - oil_temp, oil_press                                                         ║
║  - barometer, intake_press                                                     ║
║  - def_level                                                                   ║
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


class ComponentType(str, Enum):
    """Types of components we track wear for"""

    BRAKE_PADS = "brake_pads"
    BRAKE_DRUMS = "brake_drums"
    TURBOCHARGER = "turbocharger"
    TRANSMISSION = "transmission"
    ENGINE_OIL = "engine_oil"
    AIR_FILTER = "air_filter"
    DEF_SYSTEM = "def_system"
    FUEL_FILTER = "fuel_filter"
    COOLANT = "coolant"


class WearSeverity(str, Enum):
    """Severity of component wear"""

    GOOD = "good"  # 75-100% life remaining
    FAIR = "fair"  # 50-75% life remaining
    WORN = "worn"  # 25-50% life remaining
    CRITICAL = "critical"  # 0-25% life remaining
    FAILED = "failed"  # Component has failed


class AlertPriority(str, Enum):
    """Priority for maintenance alerts"""

    INFO = "info"  # FYI, no action needed
    LOW = "low"  # Schedule when convenient
    MEDIUM = "medium"  # Schedule within 2 weeks
    HIGH = "high"  # Schedule within 1 week
    CRITICAL = "critical"  # Immediate attention


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION - Component Lifespans and Thresholds
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ComponentConfig:
    """Configuration for component wear tracking"""

    # Brake pads (semi-truck, depending on driving style)
    brake_pad_life_miles: int = 250_000  # Typical: 200K-300K miles
    brake_pad_warning_pct: float = 25.0  # Warn at 25% remaining
    brake_events_per_mile_normal: float = 0.5  # Expected brake events per mile
    brake_events_per_mile_aggressive: float = 1.5  # Aggressive = 3x normal

    # Turbocharger
    turbo_max_temp_warning: float = 1200.0  # °F - warn above this
    turbo_max_temp_critical: float = 1400.0  # °F - critical above this
    turbo_life_hours: int = 250_000  # Typical turbo life in engine hours

    # Transmission
    trans_max_temp_warning: float = 225.0  # °F - warn above this
    trans_max_temp_critical: float = 275.0  # °F - critical (damage occurs)
    trans_optimal_temp: float = 175.0  # °F - optimal operating temp

    # Engine oil
    oil_change_interval_miles: int = 25_000  # Full synthetic
    oil_max_temp_warning: float = 250.0  # °F
    oil_max_temp_critical: float = 280.0  # °F
    oil_min_press_warning: float = 25.0  # psi at idle
    oil_min_press_critical: float = 15.0  # psi - danger zone

    # Air filter (intake restriction)
    # Normal intake_press should be close to barometer (within 2 kPa)
    intake_restriction_warning: float = 5.0  # kPa difference
    intake_restriction_critical: float = 10.0  # kPa difference

    # DEF system
    def_consumption_rate: float = 2.5  # % of diesel consumption
    def_warning_level: float = 15.0  # Warn below 15%
    def_critical_level: float = 5.0  # Critical below 5%

    # Coolant
    coolant_max_temp_warning: float = 220.0  # °F
    coolant_max_temp_critical: float = 240.0  # °F


CONFIG = ComponentConfig()


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ComponentStatus:
    """Status of a single component"""

    component: ComponentType
    truck_id: str

    # Wear estimation
    wear_pct: float  # 0-100, how much worn (100 = needs replacement)
    remaining_life_pct: float  # 0-100, how much life left
    estimated_miles_remaining: Optional[int] = None
    estimated_days_remaining: Optional[int] = None

    # Status
    severity: WearSeverity = WearSeverity.GOOD
    alert_priority: AlertPriority = AlertPriority.INFO

    # Tracking
    last_service_miles: Optional[int] = None
    last_service_date: Optional[datetime] = None
    current_miles: Optional[int] = None

    # Alert message
    message: str = ""
    recommendation: str = ""

    # Confidence in estimate
    confidence_pct: float = 50.0  # 0-100

    def to_dict(self) -> Dict:
        return {
            "component": self.component.value,
            "truck_id": self.truck_id,
            "wear_pct": round(self.wear_pct, 1),
            "remaining_life_pct": round(self.remaining_life_pct, 1),
            "estimated_miles_remaining": self.estimated_miles_remaining,
            "estimated_days_remaining": self.estimated_days_remaining,
            "severity": self.severity.value,
            "alert_priority": self.alert_priority.value,
            "last_service_miles": self.last_service_miles,
            "last_service_date": (
                self.last_service_date.isoformat() if self.last_service_date else None
            ),
            "current_miles": self.current_miles,
            "message": self.message,
            "recommendation": self.recommendation,
            "confidence_pct": round(self.confidence_pct, 1),
        }


@dataclass
class MaintenanceAlert:
    """Maintenance alert for predictive maintenance"""

    truck_id: str
    component: ComponentType
    priority: AlertPriority
    title: str
    message: str
    recommendation: str
    estimated_cost: Optional[float] = None
    estimated_downtime_hours: Optional[float] = None
    schedule_before_miles: Optional[int] = None
    schedule_before_date: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "component": self.component.value,
            "priority": self.priority.value,
            "title": self.title,
            "message": self.message,
            "recommendation": self.recommendation,
            "estimated_cost": self.estimated_cost,
            "estimated_downtime_hours": self.estimated_downtime_hours,
            "schedule_before_miles": self.schedule_before_miles,
            "schedule_before_date": (
                self.schedule_before_date.isoformat()
                if self.schedule_before_date
                else None
            ),
            "created_at": self.created_at.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TRUCK COMPONENT STATE TRACKER
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TruckComponentState:
    """Tracks component wear state for a single truck"""

    truck_id: str

    # Odometer tracking
    first_seen_miles: Optional[float] = None
    current_miles: Optional[float] = None
    miles_per_day_avg: float = 500.0  # Default: 500 mi/day

    # Brake tracking
    brake_events_total: int = 0  # Total brake events detected
    brake_events_last_service: int = 0  # Events since last brake service
    last_brake_service_miles: Optional[float] = None
    brake_pressure_samples: deque = field(default_factory=lambda: deque(maxlen=100))

    # Turbo tracking
    turbo_temp_max_seen: float = 0.0
    turbo_temp_samples: deque = field(default_factory=lambda: deque(maxlen=100))
    turbo_overtemp_events: int = 0
    boost_samples: deque = field(default_factory=lambda: deque(maxlen=100))

    # Transmission tracking
    trans_temp_max_seen: float = 0.0
    trans_temp_samples: deque = field(default_factory=lambda: deque(maxlen=100))
    trans_overtemp_events: int = 0

    # Oil tracking
    oil_temp_max_seen: float = 0.0
    oil_press_min_seen: float = 100.0  # Start high
    oil_temp_samples: deque = field(default_factory=lambda: deque(maxlen=100))
    oil_press_samples: deque = field(default_factory=lambda: deque(maxlen=100))
    last_oil_change_miles: Optional[float] = None

    # Air filter tracking (intake restriction)
    intake_restriction_samples: deque = field(default_factory=lambda: deque(maxlen=50))

    # DEF tracking
    def_level_samples: deque = field(default_factory=lambda: deque(maxlen=50))
    last_def_fill_miles: Optional[float] = None


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE CLASS
# ═══════════════════════════════════════════════════════════════════════════════


class ComponentWearEngine:
    """
    🔧 Component Wear Prediction Engine

    Tracks sensor data to predict component wear and remaining life.
    Generates actionable maintenance alerts.

    Key Features:
    - Brake pad wear estimation from brake event frequency
    - Turbo health monitoring from temperature and boost
    - Transmission health from temperature trending
    - Oil condition estimation from temp/pressure
    - Air filter condition from intake restriction
    """

    def __init__(self, config: Optional[ComponentConfig] = None):
        self.config = config or CONFIG
        self.truck_states: Dict[str, TruckComponentState] = {}
        self._alerts_sent: Dict[str, datetime] = {}  # Prevent duplicate alerts

    def _get_or_create_state(self, truck_id: str) -> TruckComponentState:
        """Get or create state tracker for a truck"""
        if truck_id not in self.truck_states:
            self.truck_states[truck_id] = TruckComponentState(truck_id=truck_id)
        return self.truck_states[truck_id]

    # ═══════════════════════════════════════════════════════════════════════════
    # SENSOR DATA PROCESSING
    # ═══════════════════════════════════════════════════════════════════════════

    def process_reading(
        self,
        truck_id: str,
        timestamp: datetime,
        odometer: Optional[float] = None,
        # Brake sensors
        brake_switch: Optional[int] = None,
        brake_app_press: Optional[float] = None,
        brake_primary_press: Optional[float] = None,
        # Turbo sensors
        turbo_temp: Optional[float] = None,
        boost: Optional[float] = None,
        intake_press: Optional[float] = None,
        intercooler_temp: Optional[float] = None,
        # Transmission sensors
        trans_temp: Optional[float] = None,
        # Oil sensors
        oil_temp: Optional[float] = None,
        oil_press: Optional[float] = None,
        # Air filter sensors
        barometer: Optional[float] = None,
        # DEF sensor
        def_level: Optional[float] = None,
        # Coolant
        coolant_temp: Optional[float] = None,
    ) -> List[MaintenanceAlert]:
        """
        Process sensor reading and update component wear estimates.

        Returns list of any new maintenance alerts generated.
        """
        state = self._get_or_create_state(truck_id)
        alerts: List[MaintenanceAlert] = []

        # Update odometer tracking
        if odometer is not None:
            if state.first_seen_miles is None:
                state.first_seen_miles = odometer
            state.current_miles = odometer

        # ═══════════════════════════════════════════════════════════════════
        # BRAKE TRACKING
        # ═══════════════════════════════════════════════════════════════════
        if brake_switch is not None and brake_switch == 1:
            state.brake_events_total += 1
            state.brake_events_last_service += 1

        if brake_app_press is not None:
            state.brake_pressure_samples.append(brake_app_press)

        # ═══════════════════════════════════════════════════════════════════
        # TURBO TRACKING
        # ═══════════════════════════════════════════════════════════════════
        if turbo_temp is not None:
            state.turbo_temp_samples.append(turbo_temp)
            if turbo_temp > state.turbo_temp_max_seen:
                state.turbo_temp_max_seen = turbo_temp

            # Check for overtemp event
            if turbo_temp >= self.config.turbo_max_temp_critical:
                state.turbo_overtemp_events += 1
                alert = self._create_turbo_alert(truck_id, turbo_temp, "CRITICAL")
                if alert:
                    alerts.append(alert)
            elif turbo_temp >= self.config.turbo_max_temp_warning:
                alert = self._create_turbo_alert(truck_id, turbo_temp, "WARNING")
                if alert:
                    alerts.append(alert)

        if boost is not None:
            state.boost_samples.append(boost)
        elif intake_press is not None:
            state.boost_samples.append(intake_press)

        # ═══════════════════════════════════════════════════════════════════
        # TRANSMISSION TRACKING
        # ═══════════════════════════════════════════════════════════════════
        if trans_temp is not None:
            state.trans_temp_samples.append(trans_temp)
            if trans_temp > state.trans_temp_max_seen:
                state.trans_temp_max_seen = trans_temp

            # Check for overtemp
            if trans_temp >= self.config.trans_max_temp_critical:
                state.trans_overtemp_events += 1
                alert = self._create_trans_alert(truck_id, trans_temp, "CRITICAL")
                if alert:
                    alerts.append(alert)
            elif trans_temp >= self.config.trans_max_temp_warning:
                alert = self._create_trans_alert(truck_id, trans_temp, "WARNING")
                if alert:
                    alerts.append(alert)

        # ═══════════════════════════════════════════════════════════════════
        # OIL TRACKING
        # ═══════════════════════════════════════════════════════════════════
        if oil_temp is not None:
            state.oil_temp_samples.append(oil_temp)
            if oil_temp > state.oil_temp_max_seen:
                state.oil_temp_max_seen = oil_temp

        if oil_press is not None:
            state.oil_press_samples.append(oil_press)
            if oil_press < state.oil_press_min_seen:
                state.oil_press_min_seen = oil_press

            # Check for low pressure
            if oil_press <= self.config.oil_min_press_critical:
                alert = self._create_oil_press_alert(truck_id, oil_press, "CRITICAL")
                if alert:
                    alerts.append(alert)
            elif oil_press <= self.config.oil_min_press_warning:
                alert = self._create_oil_press_alert(truck_id, oil_press, "WARNING")
                if alert:
                    alerts.append(alert)

        # ═══════════════════════════════════════════════════════════════════
        # AIR FILTER TRACKING (intake restriction)
        # ═══════════════════════════════════════════════════════════════════
        if barometer is not None and intake_press is not None:
            restriction = barometer - intake_press  # kPa difference
            state.intake_restriction_samples.append(restriction)

            if restriction >= self.config.intake_restriction_critical:
                alert = self._create_air_filter_alert(truck_id, restriction, "CRITICAL")
                if alert:
                    alerts.append(alert)
            elif restriction >= self.config.intake_restriction_warning:
                alert = self._create_air_filter_alert(truck_id, restriction, "WARNING")
                if alert:
                    alerts.append(alert)

        # ═══════════════════════════════════════════════════════════════════
        # DEF TRACKING
        # ═══════════════════════════════════════════════════════════════════
        if def_level is not None:
            state.def_level_samples.append(def_level)

            if def_level <= self.config.def_critical_level:
                alert = self._create_def_alert(truck_id, def_level, "CRITICAL")
                if alert:
                    alerts.append(alert)
            elif def_level <= self.config.def_warning_level:
                alert = self._create_def_alert(truck_id, def_level, "WARNING")
                if alert:
                    alerts.append(alert)

        return alerts

    # ═══════════════════════════════════════════════════════════════════════════
    # COMPONENT STATUS CALCULATION
    # ═══════════════════════════════════════════════════════════════════════════

    def get_brake_status(self, truck_id: str) -> ComponentStatus:
        """
        Estimate brake pad wear based on brake event frequency.

        Logic:
        - Count brake events since last service
        - Compare to expected events for miles driven
        - Aggressive braking = faster wear
        """
        state = self._get_or_create_state(truck_id)

        # Calculate miles since last brake service
        if (
            state.last_brake_service_miles is not None
            and state.current_miles is not None
        ):
            miles_since_service = state.current_miles - state.last_brake_service_miles
        else:
            # Assume brake service at 50K miles ago if unknown
            miles_since_service = 50_000.0

        # Calculate brake aggressiveness factor
        if miles_since_service > 0:
            events_per_mile = state.brake_events_last_service / miles_since_service
            aggressiveness = events_per_mile / self.config.brake_events_per_mile_normal
        else:
            aggressiveness = 1.0

        # Estimate wear based on miles and aggressiveness
        base_wear_pct = (miles_since_service / self.config.brake_pad_life_miles) * 100
        adjusted_wear_pct = base_wear_pct * max(1.0, aggressiveness)
        wear_pct = min(100.0, adjusted_wear_pct)
        remaining_pct = max(0.0, 100.0 - wear_pct)

        # Estimate remaining miles
        if aggressiveness > 0:
            remaining_miles = int(
                (remaining_pct / 100)
                * self.config.brake_pad_life_miles
                / aggressiveness
            )
        else:
            remaining_miles = int(
                (remaining_pct / 100) * self.config.brake_pad_life_miles
            )

        # Estimate days remaining
        days_remaining = (
            int(remaining_miles / state.miles_per_day_avg)
            if state.miles_per_day_avg > 0
            else None
        )

        # Determine severity
        if remaining_pct <= 10:
            severity = WearSeverity.CRITICAL
            priority = AlertPriority.CRITICAL
            message = (
                f"🚨 Brake pads critically worn - Est. {remaining_miles:,} mi remaining"
            )
            recommendation = "REPLACE IMMEDIATELY - Schedule service within 1 week"
        elif remaining_pct <= 25:
            severity = WearSeverity.WORN
            priority = AlertPriority.HIGH
            message = (
                f"⚠️ Brake pad wear detected - Est. {remaining_miles:,} mi remaining"
            )
            recommendation = "Schedule brake service within 2 weeks"
        elif remaining_pct <= 50:
            severity = WearSeverity.FAIR
            priority = AlertPriority.MEDIUM
            message = f"Brake pads at {remaining_pct:.0f}% life - Est. {remaining_miles:,} mi remaining"
            recommendation = "Monitor and schedule service at next major stop"
        else:
            severity = WearSeverity.GOOD
            priority = AlertPriority.INFO
            message = (
                f"Brake pads in good condition - Est. {remaining_miles:,} mi remaining"
            )
            recommendation = "No action needed"

        # Confidence based on data quality
        confidence = 50.0
        if state.brake_events_last_service > 100:
            confidence += 20.0
        if state.last_brake_service_miles is not None:
            confidence += 20.0
        if len(state.brake_pressure_samples) > 50:
            confidence += 10.0

        return ComponentStatus(
            component=ComponentType.BRAKE_PADS,
            truck_id=truck_id,
            wear_pct=wear_pct,
            remaining_life_pct=remaining_pct,
            estimated_miles_remaining=remaining_miles,
            estimated_days_remaining=days_remaining,
            severity=severity,
            alert_priority=priority,
            last_service_miles=(
                int(state.last_brake_service_miles)
                if state.last_brake_service_miles
                else None
            ),
            current_miles=int(state.current_miles) if state.current_miles else None,
            message=message,
            recommendation=recommendation,
            confidence_pct=min(100.0, confidence),
        )

    def get_turbo_status(self, truck_id: str) -> ComponentStatus:
        """Estimate turbocharger health from temperature data"""
        state = self._get_or_create_state(truck_id)

        # Base health on overtemp events and max temp seen
        health_score = 100.0

        # Penalize for overtemp events (each event degrades turbo)
        health_score -= state.turbo_overtemp_events * 5

        # Penalize for high max temp
        if state.turbo_temp_max_seen > self.config.turbo_max_temp_critical:
            health_score -= 20
        elif state.turbo_temp_max_seen > self.config.turbo_max_temp_warning:
            health_score -= 10

        health_score = max(0.0, health_score)
        wear_pct = 100.0 - health_score

        # Determine severity
        if health_score <= 25:
            severity = WearSeverity.CRITICAL
            priority = AlertPriority.CRITICAL
        elif health_score <= 50:
            severity = WearSeverity.WORN
            priority = AlertPriority.HIGH
        elif health_score <= 75:
            severity = WearSeverity.FAIR
            priority = AlertPriority.MEDIUM
        else:
            severity = WearSeverity.GOOD
            priority = AlertPriority.INFO

        message = f"Turbo health: {health_score:.0f}% - Max temp seen: {state.turbo_temp_max_seen:.0f}°F"

        return ComponentStatus(
            component=ComponentType.TURBOCHARGER,
            truck_id=truck_id,
            wear_pct=wear_pct,
            remaining_life_pct=health_score,
            severity=severity,
            alert_priority=priority,
            message=message,
            recommendation=(
                "Monitor turbo temperatures"
                if health_score > 50
                else "Inspect turbocharger"
            ),
            confidence_pct=70.0 if len(state.turbo_temp_samples) > 50 else 40.0,
        )

    def get_all_component_status(self, truck_id: str) -> Dict[str, ComponentStatus]:
        """Get status of all tracked components for a truck"""
        return {
            "brake_pads": self.get_brake_status(truck_id),
            "turbocharger": self.get_turbo_status(truck_id),
            # Add more components as needed
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # ALERT CREATION HELPERS
    # ═══════════════════════════════════════════════════════════════════════════

    def _should_send_alert(self, alert_key: str, cooldown_hours: int = 24) -> bool:
        """Check if we should send an alert (prevent duplicates)"""
        if alert_key in self._alerts_sent:
            last_sent = self._alerts_sent[alert_key]
            if datetime.now(timezone.utc) - last_sent < timedelta(hours=cooldown_hours):
                return False
        self._alerts_sent[alert_key] = datetime.now(timezone.utc)
        return True

    def _create_turbo_alert(
        self, truck_id: str, temp: float, level: str
    ) -> Optional[MaintenanceAlert]:
        """Create turbo temperature alert"""
        alert_key = f"{truck_id}_turbo_{level}"
        if not self._should_send_alert(alert_key, cooldown_hours=4):
            return None

        if level == "CRITICAL":
            return MaintenanceAlert(
                truck_id=truck_id,
                component=ComponentType.TURBOCHARGER,
                priority=AlertPriority.CRITICAL,
                title="🚨 TURBO OVERTEMP CRITICAL",
                message=f"Turbo temperature {temp:.0f}°F exceeds critical threshold ({self.config.turbo_max_temp_critical}°F)",
                recommendation="STOP TRUCK - Allow turbo to cool before continuing. Inspect for damage.",
                estimated_downtime_hours=2.0,
            )
        else:
            return MaintenanceAlert(
                truck_id=truck_id,
                component=ComponentType.TURBOCHARGER,
                priority=AlertPriority.HIGH,
                title="⚠️ Turbo Temperature Warning",
                message=f"Turbo temperature {temp:.0f}°F above normal ({self.config.turbo_max_temp_warning}°F)",
                recommendation="Reduce engine load. Check for boost leaks or clogged intercooler.",
            )

    def _create_trans_alert(
        self, truck_id: str, temp: float, level: str
    ) -> Optional[MaintenanceAlert]:
        """Create transmission temperature alert"""
        alert_key = f"{truck_id}_trans_{level}"
        if not self._should_send_alert(alert_key, cooldown_hours=4):
            return None

        if level == "CRITICAL":
            return MaintenanceAlert(
                truck_id=truck_id,
                component=ComponentType.TRANSMISSION,
                priority=AlertPriority.CRITICAL,
                title="🚨 TRANSMISSION OVERTEMP CRITICAL",
                message=f"Trans temp {temp:.0f}°F - DAMAGE IMMINENT (limit: {self.config.trans_max_temp_critical}°F)",
                recommendation="STOP IMMEDIATELY - Continuing will cause transmission damage. Check trans cooler.",
                estimated_cost=8000.0,  # Trans rebuild cost
            )
        else:
            return MaintenanceAlert(
                truck_id=truck_id,
                component=ComponentType.TRANSMISSION,
                priority=AlertPriority.HIGH,
                title="⚠️ Transmission Temperature High",
                message=f"Trans temp {temp:.0f}°F above normal (warning: {self.config.trans_max_temp_warning}°F)",
                recommendation="Reduce speed, avoid heavy loads. Check transmission cooler and fluid level.",
            )

    def _create_oil_press_alert(
        self, truck_id: str, pressure: float, level: str
    ) -> Optional[MaintenanceAlert]:
        """Create oil pressure alert"""
        alert_key = f"{truck_id}_oil_press_{level}"
        if not self._should_send_alert(alert_key, cooldown_hours=1):
            return None

        if level == "CRITICAL":
            return MaintenanceAlert(
                truck_id=truck_id,
                component=ComponentType.ENGINE_OIL,
                priority=AlertPriority.CRITICAL,
                title="🚨 OIL PRESSURE CRITICAL",
                message=f"Oil pressure {pressure:.0f} psi - ENGINE DAMAGE RISK",
                recommendation="STOP ENGINE IMMEDIATELY - Do not run until oil system inspected",
                estimated_cost=20000.0,  # Engine rebuild
            )
        else:
            return MaintenanceAlert(
                truck_id=truck_id,
                component=ComponentType.ENGINE_OIL,
                priority=AlertPriority.HIGH,
                title="⚠️ Low Oil Pressure Warning",
                message=f"Oil pressure {pressure:.0f} psi below normal (min: {self.config.oil_min_press_warning} psi)",
                recommendation="Check oil level. Schedule oil system inspection.",
            )

    def _create_air_filter_alert(
        self, truck_id: str, restriction: float, level: str
    ) -> Optional[MaintenanceAlert]:
        """Create air filter restriction alert"""
        alert_key = f"{truck_id}_air_filter_{level}"
        if not self._should_send_alert(alert_key, cooldown_hours=24):
            return None

        return MaintenanceAlert(
            truck_id=truck_id,
            component=ComponentType.AIR_FILTER,
            priority=(
                AlertPriority.HIGH if level == "CRITICAL" else AlertPriority.MEDIUM
            ),
            title=f"{'🚨' if level == 'CRITICAL' else '⚠️'} Air Filter Restricted",
            message=f"Intake restriction {restriction:.1f} kPa - filter likely clogged",
            recommendation="Replace air filter at next stop",
            estimated_cost=100.0,
            estimated_downtime_hours=0.5,
        )

    def _create_def_alert(
        self, truck_id: str, level: float, severity: str
    ) -> Optional[MaintenanceAlert]:
        """Create DEF level alert"""
        alert_key = f"{truck_id}_def_{severity}"
        if not self._should_send_alert(alert_key, cooldown_hours=12):
            return None

        if severity == "CRITICAL":
            return MaintenanceAlert(
                truck_id=truck_id,
                component=ComponentType.DEF_SYSTEM,
                priority=AlertPriority.CRITICAL,
                title="🚨 DEF LEVEL CRITICAL",
                message=f"DEF level {level:.0f}% - Engine derate imminent",
                recommendation="FILL DEF IMMEDIATELY - Engine will derate if empty",
            )
        else:
            return MaintenanceAlert(
                truck_id=truck_id,
                component=ComponentType.DEF_SYSTEM,
                priority=AlertPriority.MEDIUM,
                title="⚠️ DEF Level Low",
                message=f"DEF level {level:.0f}% - Plan to refill soon",
                recommendation="Fill DEF at next fuel stop",
            )

    # ═══════════════════════════════════════════════════════════════════════════
    # API METHODS - Used by api_v2.py endpoints
    # ═══════════════════════════════════════════════════════════════════════════

    def get_truck_wear_status(self, truck_id: str) -> Optional[Dict]:
        """
        Get comprehensive wear status for all components.
        Used by GET /maintenance/wear/{truck_id}
        """
        if truck_id not in self.truck_states:
            return None

        state = self.truck_states[truck_id]

        return {
            "truck_id": truck_id,
            "last_update": state.last_update.isoformat() if state.last_update else None,
            "current_miles": state.current_miles,
            "engine_hours": state.engine_hours,
            "components": {
                "brake_pads": self.get_brake_status(truck_id).to_dict(),
                "turbo": self.get_turbo_status(truck_id).to_dict(),
            },
            "sensor_availability": {
                "brake_info": state.brake_events_last_service > 0,
                "trans_temp": state.trans_temp_max is not None,
                "turbo_temp": state.turbo_temp_max is not None,
            },
        }

    def get_maintenance_predictions(self, truck_id: str) -> Optional[Dict]:
        """
        Get predictive maintenance timeline for a truck.
        Used by GET /maintenance/predictions/{truck_id}
        """
        if truck_id not in self.truck_states:
            return None

        state = self.truck_states[truck_id]
        brake_status = self.get_brake_status(truck_id)
        turbo_status = self.get_turbo_status(truck_id)

        predictions = {}

        # Brake pad prediction
        if brake_status.wear_percentage > 0:
            # Estimate days remaining based on wear rate
            miles_since_service = state.current_miles - state.last_brake_service_miles
            if miles_since_service > 0 and brake_status.wear_percentage > 0:
                miles_per_pct = miles_since_service / brake_status.wear_percentage
                miles_remaining = (100 - brake_status.wear_percentage) * miles_per_pct
                # Assume 400 miles/day average
                days_remaining = int(miles_remaining / 400)
            else:
                miles_remaining = None
                days_remaining = None

            predictions["brake_pads"] = {
                "wear_pct": brake_status.wear_percentage,
                "health_score": brake_status.health_score,
                "miles_remaining": int(miles_remaining) if miles_remaining else None,
                "days_to_service": days_remaining,
                "confidence": brake_status.confidence,
                "action": self._get_brake_recommendation(brake_status.wear_percentage),
            }

        # Turbo prediction
        if turbo_status.health_score < 100:
            predictions["turbo"] = {
                "health_score": turbo_status.health_score,
                "max_temp_recorded": state.turbo_temp_max,
                "overtemp_events": state.turbo_overtemp_events,
                "confidence": turbo_status.confidence,
                "action": self._get_turbo_recommendation(turbo_status.health_score),
            }

        if not predictions:
            return None

        return {
            "truck_id": truck_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "predictions": predictions,
        }

    def _get_brake_recommendation(self, wear_pct: float) -> str:
        """Get action recommendation based on brake wear"""
        if wear_pct >= 85:
            return "🚨 URGENT: Schedule brake service immediately"
        elif wear_pct >= 70:
            return "⚠️ Schedule brake inspection within 2 weeks"
        elif wear_pct >= 50:
            return "Monitor brake wear, plan service in ~6 weeks"
        else:
            return "No immediate action required"

    def _get_turbo_recommendation(self, health: float) -> str:
        """Get action recommendation based on turbo health"""
        if health <= 50:
            return "🚨 Turbo showing significant wear - inspect ASAP"
        elif health <= 70:
            return "⚠️ Schedule turbo inspection"
        elif health <= 85:
            return "Monitor turbo temps closely"
        else:
            return "Turbo operating normally"

    def get_maintenance_alerts(self, truck_id: str) -> List[Dict]:
        """
        Get active maintenance alerts for a truck.
        Used by GET /maintenance/alerts/{truck_id}
        """
        alerts = []

        if truck_id not in self.truck_states:
            return alerts

        state = self.truck_states[truck_id]
        brake_status = self.get_brake_status(truck_id)
        turbo_status = self.get_turbo_status(truck_id)

        # Brake alerts
        if brake_status.wear_percentage >= 85:
            alerts.append({
                "component": "BRAKE_PADS",
                "priority": "CRITICAL",
                "title": "Brake pads nearing end of life",
                "message": f"Wear: {brake_status.wear_percentage:.1f}%",
                "action": "Schedule brake service immediately",
            })
        elif brake_status.wear_percentage >= 70:
            alerts.append({
                "component": "BRAKE_PADS",
                "priority": "WARNING",
                "title": "Brake pad wear elevated",
                "message": f"Wear: {brake_status.wear_percentage:.1f}%",
                "action": "Plan brake inspection within 2 weeks",
            })

        # Turbo alerts
        if turbo_status.health_score <= 50:
            alerts.append({
                "component": "TURBO",
                "priority": "CRITICAL",
                "title": "Turbo health critical",
                "message": f"Health score: {turbo_status.health_score:.1f}%",
                "action": "Inspect turbo system immediately",
            })
        elif state.turbo_overtemp_events >= 5:
            alerts.append({
                "component": "TURBO",
                "priority": "WARNING",
                "title": "Repeated turbo overtemp events",
                "message": f"Overtemp events: {state.turbo_overtemp_events}",
                "action": "Check boost pressure and intercooler",
            })

        # Trans temp alert
        if state.trans_temp_max and state.trans_temp_max > 220:
            alerts.append({
                "component": "TRANSMISSION",
                "priority": "WARNING",
                "title": "High transmission temps recorded",
                "message": f"Max temp: {state.trans_temp_max:.0f}°F",
                "action": "Check trans fluid level and cooler",
            })

        return alerts

    def get_fleet_maintenance_summary(self) -> Dict:
        """
        Get fleet-wide maintenance overview.
        Used by GET /maintenance/fleet
        """
        if not self.truck_states:
            return {
                "message": "No trucks being monitored yet",
                "total_trucks": 0,
            }

        urgent_trucks = []
        warning_trucks = []
        healthy_trucks = []
        upcoming_services = []

        for truck_id, state in self.truck_states.items():
            brake_status = self.get_brake_status(truck_id)
            turbo_status = self.get_turbo_status(truck_id)

            # Categorize by urgency
            if brake_status.wear_percentage >= 85 or turbo_status.health_score <= 50:
                urgent_trucks.append({
                    "truck_id": truck_id,
                    "issue": "brake" if brake_status.wear_percentage >= 85 else "turbo",
                    "value": brake_status.wear_percentage if brake_status.wear_percentage >= 85 else turbo_status.health_score,
                })
            elif brake_status.wear_percentage >= 70 or turbo_status.health_score <= 70:
                warning_trucks.append({
                    "truck_id": truck_id,
                    "brake_wear": brake_status.wear_percentage,
                    "turbo_health": turbo_status.health_score,
                })
            else:
                healthy_trucks.append(truck_id)

            # Upcoming services (wear between 50-70%)
            if 50 <= brake_status.wear_percentage < 70:
                miles_remaining = int(
                    (100 - brake_status.wear_percentage)
                    / max(brake_status.wear_percentage, 1)
                    * (state.current_miles - state.last_brake_service_miles)
                )
                upcoming_services.append({
                    "truck_id": truck_id,
                    "component": "BRAKE_PADS",
                    "wear_pct": brake_status.wear_percentage,
                    "estimated_miles_remaining": miles_remaining,
                })

        # Sort upcoming by urgency
        upcoming_services.sort(key=lambda x: -x["wear_pct"])

        return {
            "summary": {
                "total_trucks_monitored": len(self.truck_states),
                "urgent_attention": len(urgent_trucks),
                "warnings": len(warning_trucks),
                "healthy": len(healthy_trucks),
            },
            "urgent_trucks": urgent_trucks[:10],  # Top 10
            "warning_trucks": warning_trucks[:10],
            "upcoming_services": upcoming_services[:10],
            "cost_analysis": {
                "note": "Proactive maintenance can reduce costs by 25-40%",
                "estimated_savings_per_truck": "$500-1500/year",
            },
        }

    def get_wear_history(
        self, truck_id: str, component: Optional[str] = None, days: int = 30
    ) -> List[Dict]:
        """
        Get historical wear progression.
        Used by GET /maintenance/history/{truck_id}

        Note: Currently returns current state only - historical tracking
        would require database storage (future enhancement).
        """
        if truck_id not in self.truck_states:
            return []

        # For now, return current state as single point
        # Future: Query from database for time-series data
        state = self.truck_states[truck_id]
        brake_status = self.get_brake_status(truck_id)
        turbo_status = self.get_turbo_status(truck_id)

        history = []

        if component is None or component.upper() == "BRAKE_PADS":
            history.append({
                "timestamp": state.last_update.isoformat() if state.last_update else None,
                "component": "BRAKE_PADS",
                "wear_pct": brake_status.wear_percentage,
                "health_score": brake_status.health_score,
                "odometer": state.current_miles,
            })

        if component is None or component.upper() == "TURBO":
            history.append({
                "timestamp": state.last_update.isoformat() if state.last_update else None,
                "component": "TURBO",
                "health_score": turbo_status.health_score,
                "max_temp": state.turbo_temp_max,
                "overtemp_events": state.turbo_overtemp_events,
            })

        return history


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCE
# ═══════════════════════════════════════════════════════════════════════════════

_wear_engine: Optional[ComponentWearEngine] = None


def get_wear_engine() -> ComponentWearEngine:
    """Get or create the global component wear engine instance"""
    global _wear_engine
    if _wear_engine is None:
        _wear_engine = ComponentWearEngine()
    return _wear_engine


# ═══════════════════════════════════════════════════════════════════════════════
# CLI TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import json

    logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 70)
    print("🔧 COMPONENT WEAR PREDICTION ENGINE v1.0.0")
    print("=" * 70)

    engine = get_wear_engine()

    # Simulate readings
    test_truck = "JB6858"

    # Set last brake service
    state = engine._get_or_create_state(test_truck)
    state.last_brake_service_miles = 150_000
    state.current_miles = 200_000
    state.brake_events_last_service = 30_000  # 30K brake events in 50K miles

    # Get brake status
    brake_status = engine.get_brake_status(test_truck)

    print("\n📋 BRAKE PAD STATUS:")
    print(json.dumps(brake_status.to_dict(), indent=2))

    # Simulate turbo overtemp
    alerts = engine.process_reading(
        truck_id=test_truck,
        timestamp=datetime.now(timezone.utc),
        odometer=200_500,
        turbo_temp=1250.0,  # High temp
        trans_temp=180.0,  # Normal
        oil_press=35.0,  # Normal
    )

    if alerts:
        print("\n🚨 ALERTS GENERATED:")
        for alert in alerts:
            print(json.dumps(alert.to_dict(), indent=2))
