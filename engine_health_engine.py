"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    ENGINE HEALTH MONITORING ENGINE                             ║
║                         Fuel Copilot v3.13.0                                   ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Purpose: Predictive maintenance through engine sensor analysis                ║
║  Sensors: Oil Pressure, Coolant Temp, Oil Temp, Battery, DEF, Engine Load     ║
║  Methods: Threshold alerts, trend analysis, Nelson rules, baseline comparison ║
║                                                                                ║
║  ROI: One prevented engine failure ($40K) = 5 years of system cost            ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import statistics
from sqlalchemy import text

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS AND CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


class AlertSeverity(Enum):
    """Alert severity levels"""

    CRITICAL = "critical"  # Stop engine / pull over immediately
    WARNING = "warning"  # Schedule maintenance soon
    WATCH = "watch"  # Monitor closely
    INFO = "info"  # Informational only


class AlertCategory(Enum):
    """Categories of health alerts"""

    OIL_PRESSURE = "oil_pressure"
    COOLANT_TEMP = "coolant_temp"
    OIL_TEMP = "oil_temp"
    BATTERY = "battery"
    DEF_LEVEL = "def_level"
    ENGINE_LOAD = "engine_load"
    TREND = "trend"
    DIFFERENTIAL = "differential"


class HealthStatus(Enum):
    """Overall health status for a truck"""

    HEALTHY = "healthy"  # All sensors normal
    WARNING = "warning"  # Some warnings, can continue
    CRITICAL = "critical"  # Critical issue, stop recommended
    OFFLINE = "offline"  # No recent data
    UNKNOWN = "unknown"  # Insufficient data


# ═══════════════════════════════════════════════════════════════════════════════
# THRESHOLD CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

ENGINE_HEALTH_THRESHOLDS = {
    "oil_pressure_psi": {
        "critical_low": 20,  # STOP ENGINE - Severe damage risk
        "warning_low": 30,  # Schedule maintenance ASAP
        "watch_low": 35,  # Monitor closely
        "normal_range": (35, 65),  # Normal operating range
        "trend_warning_drop": -10,  # psi drop vs 30-day baseline = warning
        "trend_critical_drop": -15,  # psi drop vs baseline = critical
        "unit": "psi",
        "description": "Engine Oil Pressure",
        "action_critical": "STOP ENGINE IMMEDIATELY - Check oil level and pump",
        "action_warning": "Schedule oil change and pump inspection within 48 hours",
    },
    "coolant_temp_f": {
        "critical_high": 230,  # PULL OVER - Engine damage imminent
        "warning_high": 220,  # Overheating warning
        "watch_high": 215,  # Running hot
        "normal_range": (180, 210),  # Normal operating range
        "cold_warning": 140,  # Not warming up (thermostat stuck open)
        "trend_warning_rise": 10,  # °F rise vs baseline = warning
        "trend_critical_rise": 20,  # °F rise vs baseline = critical
        "unit": "°F",
        "description": "Coolant Temperature",
        "action_critical": "PULL OVER IMMEDIATELY - Risk of engine damage",
        "action_warning": "Check coolant level, radiator, and thermostat",
    },
    "oil_temp_f": {
        "critical_high": 260,  # Oil breakdown temperature
        "warning_high": 250,  # Running very hot
        "watch_high": 240,  # Running hot
        "normal_range": (180, 235),  # Normal operating range
        "coolant_diff_critical": 60,  # oil - coolant > 60°F = cooling problem
        "coolant_diff_warning": 50,  # oil - coolant > 50°F = monitor
        "unit": "°F",
        "description": "Engine Oil Temperature",
        "action_critical": "REDUCE LOAD - Oil viscosity compromised",
        "action_warning": "Check oil cooler and cooling system",
    },
    "battery_voltage": {
        # Engine OFF thresholds
        "off_critical_low": 12.0,  # Battery won't start engine
        "off_warning_low": 12.3,  # Battery weak, may not start
        "off_watch_low": 12.4,  # Battery aging
        "off_normal_range": (12.4, 12.8),
        # Engine ON thresholds
        "on_critical_low": 13.0,  # Alternator not charging
        "on_warning_low": 13.5,  # Charging system weak
        "on_normal_range": (13.8, 14.4),
        "on_warning_high": 14.8,  # Overcharging
        "on_critical_high": 15.0,  # Voltage regulator failed
        "trend_warning_drop": -0.3,  # V drop over 7 days
        "unit": "V",
        "description": "Battery Voltage",
        "action_critical": "Check alternator and battery immediately",
        "action_warning": "Schedule electrical system inspection",
    },
    "def_level_pct": {
        "critical_low": 5,  # Risk of engine derate/limp mode
        "warning_low": 10,  # Refill soon
        "watch_low": 15,  # Plan refill
        "normal_range": (15, 100),  # Normal range
        "consumption_warning": 4.0,  # >4% of diesel = too high
        "consumption_critical": 5.0,  # >5% = injector problem
        "unit": "%",
        "description": "DEF Level",
        "action_critical": "REFILL DEF IMMEDIATELY - Engine derate imminent",
        "action_warning": "Schedule DEF refill within 24 hours",
    },
    "engine_load_pct": {
        "critical_high": 95,  # Sustained overload
        "warning_high": 90,  # Heavy sustained load
        "watch_high": 85,  # Above normal operation
        "normal_range": (20, 80),  # Normal operating range
        "sustained_minutes": 30,  # Minutes at high load before alert
        "unit": "%",
        "description": "Engine Load",
        "action_critical": "REDUCE LOAD - Risk of overheating and wear",
        "action_warning": "Monitor engine temperatures closely",
    },
    # 🆕 v5.4.2: New sensor thresholds
    "fuel_rate_gph": {
        "critical_high": 15.0,  # Excessive consumption - possible leak or injector issue
        "warning_high": 12.0,  # Higher than expected for Class 8 trucks
        "watch_high": 10.0,  # Above typical highway cruising
        "normal_range": (2.0, 8.0),  # Normal operating range (idle to highway)
        "idle_critical_high": 2.5,  # Too high at idle (injector leak?)
        "idle_warning_high": 2.0,  # Elevated idle consumption
        "idle_normal_max": 1.5,  # Normal idle consumption
        "sustained_minutes": 15,  # Minutes at high rate before alert
        "unit": "gph",
        "description": "Fuel Consumption Rate",
        "action_critical": "CHECK FOR FUEL LEAK - Excessive consumption detected",
        "action_warning": "Monitor fuel economy - consider injector inspection",
    },
    "intake_air_temp_f": {
        "critical_high": 150,  # Turbo/intercooler failure risk
        "warning_high": 140,  # Intercooler efficiency reduced
        "watch_high": 130,  # Running hot for intake
        "normal_range": (60, 120),  # Normal based on ambient + turbo heat
        "ambient_delta_warning": 60,  # intake - ambient > 60°F = intercooler issue
        "ambient_delta_critical": 80,  # intake - ambient > 80°F = intercooler failed
        "unit": "°F",
        "description": "Intake Air Temperature",
        "action_critical": "CHECK INTERCOOLER - Risk of turbo damage",
        "action_warning": "Inspect intercooler and air intake system",
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class EngineHealthAlert:
    """Represents a single health alert"""

    truck_id: str
    category: AlertCategory
    severity: AlertSeverity
    sensor_name: str
    current_value: float
    threshold_value: float
    message: str
    action_required: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    baseline_value: Optional[float] = None
    trend_direction: Optional[str] = None  # "rising", "falling", "stable"
    is_active: bool = True

    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "sensor_name": self.sensor_name,
            "current_value": self.current_value,
            "threshold_value": self.threshold_value,
            "message": self.message,
            "action_required": self.action_required,
            "timestamp": self.timestamp.isoformat(),
            "baseline_value": self.baseline_value,
            "trend_direction": self.trend_direction,
            "is_active": self.is_active,
        }


@dataclass
class SensorReading:
    """Current sensor reading with metadata"""

    value: Optional[float]
    timestamp: datetime
    is_valid: bool = True
    quality: str = "good"  # "good", "stale", "suspect"


@dataclass
class SensorBaseline:
    """Baseline statistics for a sensor"""

    sensor_name: str
    truck_id: str
    mean_30d: Optional[float] = None
    std_30d: Optional[float] = None
    mean_7d: Optional[float] = None
    std_7d: Optional[float] = None
    min_30d: Optional[float] = None
    max_30d: Optional[float] = None
    sample_count: int = 0
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class TruckHealthStatus:
    """Complete health status for a truck"""

    truck_id: str
    overall_status: HealthStatus
    last_reading: datetime
    data_age_minutes: float

    # Current sensor values
    oil_pressure_psi: Optional[float] = None
    coolant_temp_f: Optional[float] = None
    oil_temp_f: Optional[float] = None
    battery_voltage: Optional[float] = None
    def_level_pct: Optional[float] = None
    engine_load_pct: Optional[float] = None
    rpm: Optional[float] = None

    # Status per sensor
    oil_pressure_status: str = "unknown"
    coolant_temp_status: str = "unknown"
    oil_temp_status: str = "unknown"
    battery_status: str = "unknown"
    def_level_status: str = "unknown"
    engine_load_status: str = "unknown"

    # Trends
    oil_pressure_trend: Optional[str] = None
    coolant_temp_trend: Optional[str] = None
    battery_trend: Optional[str] = None

    # Active alerts
    active_alerts: List[EngineHealthAlert] = field(default_factory=list)
    alert_count_critical: int = 0
    alert_count_warning: int = 0

    # Maintenance predictions
    maintenance_predictions: List[Dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "overall_status": self.overall_status.value,
            "last_reading": (
                self.last_reading.isoformat() if self.last_reading else None
            ),
            "data_age_minutes": round(self.data_age_minutes, 1),
            "sensors": {
                "oil_pressure": {
                    "value": self.oil_pressure_psi,
                    "unit": "psi",
                    "status": self.oil_pressure_status,
                    "trend": self.oil_pressure_trend,
                    "thresholds": {
                        "critical": ENGINE_HEALTH_THRESHOLDS["oil_pressure_psi"][
                            "critical_low"
                        ],
                        "warning": ENGINE_HEALTH_THRESHOLDS["oil_pressure_psi"][
                            "warning_low"
                        ],
                        "normal_min": ENGINE_HEALTH_THRESHOLDS["oil_pressure_psi"][
                            "normal_range"
                        ][0],
                        "normal_max": ENGINE_HEALTH_THRESHOLDS["oil_pressure_psi"][
                            "normal_range"
                        ][1],
                    },
                },
                "coolant_temp": {
                    "value": self.coolant_temp_f,
                    "unit": "°F",
                    "status": self.coolant_temp_status,
                    "trend": self.coolant_temp_trend,
                    "thresholds": {
                        "critical": ENGINE_HEALTH_THRESHOLDS["coolant_temp_f"][
                            "critical_high"
                        ],
                        "warning": ENGINE_HEALTH_THRESHOLDS["coolant_temp_f"][
                            "warning_high"
                        ],
                        "normal_min": ENGINE_HEALTH_THRESHOLDS["coolant_temp_f"][
                            "normal_range"
                        ][0],
                        "normal_max": ENGINE_HEALTH_THRESHOLDS["coolant_temp_f"][
                            "normal_range"
                        ][1],
                    },
                },
                "oil_temp": {
                    "value": self.oil_temp_f,
                    "unit": "°F",
                    "status": self.oil_temp_status,
                    "thresholds": {
                        "critical": ENGINE_HEALTH_THRESHOLDS["oil_temp_f"][
                            "critical_high"
                        ],
                        "warning": ENGINE_HEALTH_THRESHOLDS["oil_temp_f"][
                            "warning_high"
                        ],
                        "normal_min": ENGINE_HEALTH_THRESHOLDS["oil_temp_f"][
                            "normal_range"
                        ][0],
                        "normal_max": ENGINE_HEALTH_THRESHOLDS["oil_temp_f"][
                            "normal_range"
                        ][1],
                    },
                },
                "battery": {
                    "value": self.battery_voltage,
                    "unit": "V",
                    "status": self.battery_status,
                    "trend": self.battery_trend,
                    "engine_running": self.rpm and self.rpm > 400,
                },
                "def_level": {
                    "value": self.def_level_pct,
                    "unit": "%",
                    "status": self.def_level_status,
                    "thresholds": {
                        "critical": ENGINE_HEALTH_THRESHOLDS["def_level_pct"][
                            "critical_low"
                        ],
                        "warning": ENGINE_HEALTH_THRESHOLDS["def_level_pct"][
                            "warning_low"
                        ],
                    },
                },
                "engine_load": {
                    "value": self.engine_load_pct,
                    "unit": "%",
                    "status": self.engine_load_status,
                },
            },
            "alerts": {
                "active": [a.to_dict() for a in self.active_alerts],
                "critical_count": self.alert_count_critical,
                "warning_count": self.alert_count_warning,
            },
            "maintenance_predictions": self.maintenance_predictions,
        }


@dataclass
class FleetHealthSummary:
    """Summary of fleet health status"""

    timestamp: datetime
    total_trucks: int
    trucks_healthy: int
    trucks_warning: int
    trucks_critical: int
    trucks_offline: int

    # Top issues
    critical_alerts: List[EngineHealthAlert] = field(default_factory=list)
    warning_alerts: List[EngineHealthAlert] = field(default_factory=list)

    # Sensor coverage
    sensor_coverage: Dict[str, int] = field(default_factory=dict)

    # Trucks by status
    trucks_by_status: Dict[str, List[str]] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "summary": {
                "total_trucks": self.total_trucks,
                "healthy": self.trucks_healthy,
                "warning": self.trucks_warning,
                "critical": self.trucks_critical,
                "offline": self.trucks_offline,
                "health_percentage": round(
                    (self.trucks_healthy / max(self.total_trucks, 1)) * 100, 1
                ),
            },
            "critical_alerts": [a.to_dict() for a in self.critical_alerts[:10]],
            "warning_alerts": [a.to_dict() for a in self.warning_alerts[:20]],
            "sensor_coverage": self.sensor_coverage,
            "trucks_by_status": self.trucks_by_status,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ENGINE HEALTH ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════


class EngineHealthAnalyzer:
    """
    Main class for analyzing engine health sensors and generating alerts.

    Features:
    - Real-time threshold monitoring
    - Baseline comparison (7-day and 30-day)
    - Trend detection (Nelson rules simplified)
    - Cross-sensor correlation (oil-coolant differential)
    - Predictive maintenance suggestions
    """

    def __init__(self, db_connection=None):
        self.db = db_connection
        self.thresholds = ENGINE_HEALTH_THRESHOLDS
        self._baselines_cache: Dict[str, Dict[str, SensorBaseline]] = {}
        self._alert_cooldown: Dict[str, datetime] = {}  # Prevent alert spam
        self.cooldown_minutes = 30  # Don't repeat same alert within 30 min

    # ───────────────────────────────────────────────────────────────────────────
    # MAIN ANALYSIS METHODS
    # ───────────────────────────────────────────────────────────────────────────

    def analyze_truck_health(
        self,
        truck_id: str,
        current_data: Dict[str, Any],
        historical_data: Optional[List[Dict]] = None,
        baselines: Optional[Dict[str, SensorBaseline]] = None,
    ) -> TruckHealthStatus:
        """
        Comprehensive health analysis for a single truck.

        Args:
            truck_id: Truck identifier
            current_data: Current sensor readings from fuel_metrics
            historical_data: Last 7 days of readings for trend analysis
            baselines: Pre-calculated baselines (30d, 7d)

        Returns:
            TruckHealthStatus with all alerts and predictions
        """
        alerts: List[EngineHealthAlert] = []
        now = datetime.now(timezone.utc)

        # Parse timestamp
        timestamp = current_data.get("timestamp_utc")
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        elif timestamp is None:
            timestamp = now

        data_age = (now - timestamp).total_seconds() / 60.0

        # Check if data is stale (offline)
        if data_age > 15:  # More than 15 minutes old
            return TruckHealthStatus(
                truck_id=truck_id,
                overall_status=HealthStatus.OFFLINE,
                last_reading=timestamp,
                data_age_minutes=data_age,
            )

        # Extract sensor values
        oil_pressure = current_data.get("oil_pressure_psi")
        coolant_temp = current_data.get("coolant_temp_f")
        oil_temp = current_data.get("oil_temp_f")
        battery = current_data.get("battery_voltage")
        def_level = current_data.get("def_level_pct")
        engine_load = current_data.get("engine_load_pct")
        rpm = current_data.get("rpm")

        # Initialize status
        status = TruckHealthStatus(
            truck_id=truck_id,
            overall_status=HealthStatus.HEALTHY,
            last_reading=timestamp,
            data_age_minutes=data_age,
            oil_pressure_psi=oil_pressure,
            coolant_temp_f=coolant_temp,
            oil_temp_f=oil_temp,
            battery_voltage=battery,
            def_level_pct=def_level,
            engine_load_pct=engine_load,
            rpm=rpm,
        )

        # Get baselines for trend analysis
        if baselines is None and self.db:
            baselines = self._get_baselines(truck_id)

        # ─────────────────────────────────────────────────────────────────────
        # 1. OIL PRESSURE ANALYSIS
        # ─────────────────────────────────────────────────────────────────────
        if oil_pressure is not None:
            oil_alerts, oil_status, oil_trend = self._analyze_oil_pressure(
                truck_id, oil_pressure, rpm, baselines
            )
            alerts.extend(oil_alerts)
            status.oil_pressure_status = oil_status
            status.oil_pressure_trend = oil_trend

        # ─────────────────────────────────────────────────────────────────────
        # 2. COOLANT TEMPERATURE ANALYSIS
        # ─────────────────────────────────────────────────────────────────────
        if coolant_temp is not None:
            coolant_alerts, coolant_status, coolant_trend = self._analyze_coolant_temp(
                truck_id, coolant_temp, rpm, baselines
            )
            alerts.extend(coolant_alerts)
            status.coolant_temp_status = coolant_status
            status.coolant_temp_trend = coolant_trend

        # ─────────────────────────────────────────────────────────────────────
        # 3. OIL TEMPERATURE ANALYSIS (with coolant differential)
        # ─────────────────────────────────────────────────────────────────────
        if oil_temp is not None:
            oil_temp_alerts, oil_temp_status = self._analyze_oil_temp(
                truck_id, oil_temp, coolant_temp
            )
            alerts.extend(oil_temp_alerts)
            status.oil_temp_status = oil_temp_status

        # ─────────────────────────────────────────────────────────────────────
        # 4. BATTERY VOLTAGE ANALYSIS
        # ─────────────────────────────────────────────────────────────────────
        if battery is not None:
            engine_running = rpm is not None and rpm > 400
            battery_alerts, battery_status, battery_trend = self._analyze_battery(
                truck_id, battery, engine_running, baselines
            )
            alerts.extend(battery_alerts)
            status.battery_status = battery_status
            status.battery_trend = battery_trend

        # ─────────────────────────────────────────────────────────────────────
        # 5. DEF LEVEL ANALYSIS
        # ─────────────────────────────────────────────────────────────────────
        if def_level is not None:
            def_alerts, def_status = self._analyze_def_level(truck_id, def_level)
            alerts.extend(def_alerts)
            status.def_level_status = def_status

        # ─────────────────────────────────────────────────────────────────────
        # 6. ENGINE LOAD ANALYSIS
        # ─────────────────────────────────────────────────────────────────────
        if engine_load is not None:
            load_alerts, load_status = self._analyze_engine_load(truck_id, engine_load)
            alerts.extend(load_alerts)
            status.engine_load_status = load_status

        # ─────────────────────────────────────────────────────────────────────
        # 7. TREND ANALYSIS (if historical data available)
        # ─────────────────────────────────────────────────────────────────────
        if historical_data and len(historical_data) > 10:
            trend_alerts = self._analyze_trends(truck_id, historical_data, baselines)
            alerts.extend(trend_alerts)

        # ─────────────────────────────────────────────────────────────────────
        # 8. MAINTENANCE PREDICTIONS
        # ─────────────────────────────────────────────────────────────────────
        predictions = self._generate_maintenance_predictions(
            truck_id, status, alerts, baselines
        )
        status.maintenance_predictions = predictions

        # ─────────────────────────────────────────────────────────────────────
        # 9. DETERMINE OVERALL STATUS
        # ─────────────────────────────────────────────────────────────────────
        # Filter alerts by cooldown
        filtered_alerts = self._filter_alerts_by_cooldown(alerts)
        status.active_alerts = filtered_alerts

        critical_count = sum(
            1 for a in filtered_alerts if a.severity == AlertSeverity.CRITICAL
        )
        warning_count = sum(
            1 for a in filtered_alerts if a.severity == AlertSeverity.WARNING
        )

        status.alert_count_critical = critical_count
        status.alert_count_warning = warning_count

        if critical_count > 0:
            status.overall_status = HealthStatus.CRITICAL
        elif warning_count > 0:
            status.overall_status = HealthStatus.WARNING
        else:
            status.overall_status = HealthStatus.HEALTHY

        return status

    def analyze_fleet_health(
        self, fleet_data: List[Dict[str, Any]]
    ) -> FleetHealthSummary:
        """
        Analyze health status for entire fleet.

        Args:
            fleet_data: List of current readings for all trucks

        Returns:
            FleetHealthSummary with counts and top alerts
        """
        now = datetime.now(timezone.utc)

        healthy = []
        warning = []
        critical = []
        offline = []

        all_critical_alerts = []
        all_warning_alerts = []

        sensor_coverage = {
            "oil_pressure": 0,
            "coolant_temp": 0,
            "oil_temp": 0,
            "battery": 0,
            "def_level": 0,
            "engine_load": 0,
        }

        for truck_data in fleet_data:
            truck_id = truck_data.get("truck_id", "unknown")

            # Analyze this truck
            status = self.analyze_truck_health(truck_id, truck_data)

            # Categorize by status
            if status.overall_status == HealthStatus.CRITICAL:
                critical.append(truck_id)
            elif status.overall_status == HealthStatus.WARNING:
                warning.append(truck_id)
            elif status.overall_status == HealthStatus.OFFLINE:
                offline.append(truck_id)
            else:
                healthy.append(truck_id)

            # Collect alerts
            for alert in status.active_alerts:
                if alert.severity == AlertSeverity.CRITICAL:
                    all_critical_alerts.append(alert)
                elif alert.severity == AlertSeverity.WARNING:
                    all_warning_alerts.append(alert)

            # Track sensor coverage
            if status.oil_pressure_psi is not None:
                sensor_coverage["oil_pressure"] += 1
            if status.coolant_temp_f is not None:
                sensor_coverage["coolant_temp"] += 1
            if status.oil_temp_f is not None:
                sensor_coverage["oil_temp"] += 1
            if status.battery_voltage is not None:
                sensor_coverage["battery"] += 1
            if status.def_level_pct is not None:
                sensor_coverage["def_level"] += 1
            if status.engine_load_pct is not None:
                sensor_coverage["engine_load"] += 1

        # Sort alerts by timestamp (most recent first)
        all_critical_alerts.sort(key=lambda x: x.timestamp, reverse=True)
        all_warning_alerts.sort(key=lambda x: x.timestamp, reverse=True)

        return FleetHealthSummary(
            timestamp=now,
            total_trucks=len(fleet_data),
            trucks_healthy=len(healthy),
            trucks_warning=len(warning),
            trucks_critical=len(critical),
            trucks_offline=len(offline),
            critical_alerts=all_critical_alerts,
            warning_alerts=all_warning_alerts,
            sensor_coverage=sensor_coverage,
            trucks_by_status={
                "healthy": healthy,
                "warning": warning,
                "critical": critical,
                "offline": offline,
            },
        )

    # ───────────────────────────────────────────────────────────────────────────
    # INDIVIDUAL SENSOR ANALYSIS
    # ───────────────────────────────────────────────────────────────────────────

    def _analyze_oil_pressure(
        self,
        truck_id: str,
        oil_pressure: float,
        rpm: Optional[float],
        baselines: Optional[Dict],
    ) -> Tuple[List[EngineHealthAlert], str, Optional[str]]:
        """Analyze oil pressure with thresholds and trends."""
        alerts = []
        status = "normal"
        trend = None
        thresholds = self.thresholds["oil_pressure_psi"]

        # Only analyze if engine is running (rpm > 400)
        engine_running = rpm is not None and rpm > 400

        if engine_running:
            # Critical low
            if oil_pressure < thresholds["critical_low"]:
                status = "critical"
                alerts.append(
                    EngineHealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.OIL_PRESSURE,
                        severity=AlertSeverity.CRITICAL,
                        sensor_name="oil_pressure_psi",
                        current_value=oil_pressure,
                        threshold_value=thresholds["critical_low"],
                        message=f"CRITICAL: Oil pressure {oil_pressure} psi is below {thresholds['critical_low']} psi",
                        action_required=thresholds["action_critical"],
                    )
                )
            # Warning low
            elif oil_pressure < thresholds["warning_low"]:
                status = "warning"
                alerts.append(
                    EngineHealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.OIL_PRESSURE,
                        severity=AlertSeverity.WARNING,
                        sensor_name="oil_pressure_psi",
                        current_value=oil_pressure,
                        threshold_value=thresholds["warning_low"],
                        message=f"WARNING: Oil pressure {oil_pressure} psi is below {thresholds['warning_low']} psi",
                        action_required=thresholds["action_warning"],
                    )
                )
            # Watch low
            elif oil_pressure < thresholds["watch_low"]:
                status = "watch"

            # Check baseline trend
            if baselines and "oil_pressure_psi" in baselines:
                baseline = baselines["oil_pressure_psi"]
                if baseline.mean_30d:
                    diff = oil_pressure - baseline.mean_30d
                    if diff < thresholds["trend_critical_drop"]:
                        trend = "falling_critical"
                        if status != "critical":
                            status = "warning"
                            alerts.append(
                                EngineHealthAlert(
                                    truck_id=truck_id,
                                    category=AlertCategory.TREND,
                                    severity=AlertSeverity.WARNING,
                                    sensor_name="oil_pressure_psi",
                                    current_value=oil_pressure,
                                    threshold_value=baseline.mean_30d,
                                    baseline_value=baseline.mean_30d,
                                    trend_direction="falling",
                                    message=f"Oil pressure dropped {abs(diff):.1f} psi below 30-day average ({baseline.mean_30d:.1f} psi)",
                                    action_required="Schedule oil change and pump inspection",
                                )
                            )
                    elif diff < thresholds["trend_warning_drop"]:
                        trend = "falling"
                    elif diff > 5:
                        trend = "rising"
                    else:
                        trend = "stable"
        else:
            status = "engine_off"

        return alerts, status, trend

    def _analyze_coolant_temp(
        self,
        truck_id: str,
        coolant_temp: float,
        rpm: Optional[float],
        baselines: Optional[Dict],
    ) -> Tuple[List[EngineHealthAlert], str, Optional[str]]:
        """Analyze coolant temperature with thresholds and trends."""
        alerts = []
        status = "normal"
        trend = None
        thresholds = self.thresholds["coolant_temp_f"]

        engine_running = rpm is not None and rpm > 400

        # Critical high (always check, even engine off - could be heat soak)
        if coolant_temp >= thresholds["critical_high"]:
            status = "critical"
            alerts.append(
                EngineHealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.COOLANT_TEMP,
                    severity=AlertSeverity.CRITICAL,
                    sensor_name="coolant_temp_f",
                    current_value=coolant_temp,
                    threshold_value=thresholds["critical_high"],
                    message=f"CRITICAL: Coolant temp {coolant_temp}°F exceeds {thresholds['critical_high']}°F",
                    action_required=thresholds["action_critical"],
                )
            )
        # Warning high
        elif coolant_temp >= thresholds["warning_high"]:
            status = "warning"
            alerts.append(
                EngineHealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.COOLANT_TEMP,
                    severity=AlertSeverity.WARNING,
                    sensor_name="coolant_temp_f",
                    current_value=coolant_temp,
                    threshold_value=thresholds["warning_high"],
                    message=f"WARNING: Coolant temp {coolant_temp}°F is above {thresholds['warning_high']}°F",
                    action_required=thresholds["action_warning"],
                )
            )
        # Watch high
        elif coolant_temp >= thresholds["watch_high"]:
            status = "watch"
        # Cold warning (only when running)
        elif engine_running and coolant_temp < thresholds["cold_warning"]:
            status = "cold"
            alerts.append(
                EngineHealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.COOLANT_TEMP,
                    severity=AlertSeverity.WATCH,
                    sensor_name="coolant_temp_f",
                    current_value=coolant_temp,
                    threshold_value=thresholds["cold_warning"],
                    message=f"Engine not warming up - coolant only {coolant_temp}°F after running",
                    action_required="Check thermostat - may be stuck open",
                )
            )

        # Trend analysis
        if baselines and "coolant_temp_f" in baselines:
            baseline = baselines["coolant_temp_f"]
            if baseline.mean_30d:
                diff = coolant_temp - baseline.mean_30d
                if diff > thresholds["trend_critical_rise"]:
                    trend = "rising_critical"
                elif diff > thresholds["trend_warning_rise"]:
                    trend = "rising"
                elif diff < -10:
                    trend = "falling"
                else:
                    trend = "stable"

        return alerts, status, trend

    def _analyze_oil_temp(
        self, truck_id: str, oil_temp: float, coolant_temp: Optional[float]
    ) -> Tuple[List[EngineHealthAlert], str]:
        """Analyze oil temperature including coolant differential."""
        alerts = []
        status = "normal"
        thresholds = self.thresholds["oil_temp_f"]

        # Critical high
        if oil_temp >= thresholds["critical_high"]:
            status = "critical"
            alerts.append(
                EngineHealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.OIL_TEMP,
                    severity=AlertSeverity.CRITICAL,
                    sensor_name="oil_temp_f",
                    current_value=oil_temp,
                    threshold_value=thresholds["critical_high"],
                    message=f"CRITICAL: Oil temp {oil_temp}°F - oil viscosity breakdown risk",
                    action_required=thresholds["action_critical"],
                )
            )
        # Warning high
        elif oil_temp >= thresholds["warning_high"]:
            status = "warning"
            alerts.append(
                EngineHealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.OIL_TEMP,
                    severity=AlertSeverity.WARNING,
                    sensor_name="oil_temp_f",
                    current_value=oil_temp,
                    threshold_value=thresholds["warning_high"],
                    message=f"WARNING: Oil temp {oil_temp}°F is above {thresholds['warning_high']}°F",
                    action_required=thresholds["action_warning"],
                )
            )
        # Watch high
        elif oil_temp >= thresholds["watch_high"]:
            status = "watch"

        # Oil-Coolant Differential Analysis
        if coolant_temp is not None:
            differential = oil_temp - coolant_temp

            if differential > thresholds["coolant_diff_critical"]:
                if status != "critical":
                    status = "warning"
                alerts.append(
                    EngineHealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.DIFFERENTIAL,
                        severity=AlertSeverity.WARNING,
                        sensor_name="oil_coolant_diff",
                        current_value=differential,
                        threshold_value=thresholds["coolant_diff_critical"],
                        message=f"High oil-coolant differential: {differential:.0f}°F (oil {oil_temp}°F, coolant {coolant_temp}°F)",
                        action_required="Check oil cooler and cooling system efficiency",
                    )
                )
            elif differential > thresholds["coolant_diff_warning"]:
                if status == "normal":
                    status = "watch"

        return alerts, status

    def _analyze_battery(
        self,
        truck_id: str,
        voltage: float,
        engine_running: bool,
        baselines: Optional[Dict],
    ) -> Tuple[List[EngineHealthAlert], str, Optional[str]]:
        """Analyze battery voltage based on engine state."""
        alerts = []
        status = "normal"
        trend = None
        thresholds = self.thresholds["battery_voltage"]

        if engine_running:
            # Engine ON - check charging system
            if voltage < thresholds["on_critical_low"]:
                status = "critical"
                alerts.append(
                    EngineHealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.BATTERY,
                        severity=AlertSeverity.CRITICAL,
                        sensor_name="battery_voltage",
                        current_value=voltage,
                        threshold_value=thresholds["on_critical_low"],
                        message=f"CRITICAL: Battery {voltage}V while running - alternator not charging",
                        action_required=thresholds["action_critical"],
                    )
                )
            elif voltage < thresholds["on_warning_low"]:
                status = "warning"
                alerts.append(
                    EngineHealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.BATTERY,
                        severity=AlertSeverity.WARNING,
                        sensor_name="battery_voltage",
                        current_value=voltage,
                        threshold_value=thresholds["on_warning_low"],
                        message=f"WARNING: Battery {voltage}V while running - charging system weak",
                        action_required=thresholds["action_warning"],
                    )
                )
            elif voltage > thresholds["on_critical_high"]:
                status = "critical"
                alerts.append(
                    EngineHealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.BATTERY,
                        severity=AlertSeverity.CRITICAL,
                        sensor_name="battery_voltage",
                        current_value=voltage,
                        threshold_value=thresholds["on_critical_high"],
                        message=f"CRITICAL: Battery {voltage}V - voltage regulator failed (overcharging)",
                        action_required="Check voltage regulator immediately",
                    )
                )
            elif voltage > thresholds["on_warning_high"]:
                status = "warning"
        else:
            # Engine OFF - check battery health
            if voltage < thresholds["off_critical_low"]:
                status = "critical"
                alerts.append(
                    EngineHealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.BATTERY,
                        severity=AlertSeverity.CRITICAL,
                        sensor_name="battery_voltage",
                        current_value=voltage,
                        threshold_value=thresholds["off_critical_low"],
                        message=f"CRITICAL: Battery {voltage}V - may not start engine",
                        action_required="Charge or replace battery before next trip",
                    )
                )
            elif voltage < thresholds["off_warning_low"]:
                status = "warning"
                alerts.append(
                    EngineHealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.BATTERY,
                        severity=AlertSeverity.WARNING,
                        sensor_name="battery_voltage",
                        current_value=voltage,
                        threshold_value=thresholds["off_warning_low"],
                        message=f"WARNING: Battery {voltage}V - battery weak, replace soon",
                        action_required="Schedule battery replacement",
                    )
                )
            elif voltage < thresholds["off_watch_low"]:
                status = "watch"

        # Trend analysis
        if baselines and "battery_voltage" in baselines:
            baseline = baselines["battery_voltage"]
            if baseline.mean_7d:
                diff = voltage - baseline.mean_7d
                if diff < thresholds["trend_warning_drop"]:
                    trend = "falling"
                elif diff > 0.2:
                    trend = "rising"
                else:
                    trend = "stable"

        return alerts, status, trend

    def _analyze_def_level(
        self, truck_id: str, def_level: float
    ) -> Tuple[List[EngineHealthAlert], str]:
        """Analyze DEF fluid level."""
        alerts = []
        status = "normal"
        thresholds = self.thresholds["def_level_pct"]

        if def_level <= thresholds["critical_low"]:
            status = "critical"
            alerts.append(
                EngineHealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.DEF_LEVEL,
                    severity=AlertSeverity.CRITICAL,
                    sensor_name="def_level_pct",
                    current_value=def_level,
                    threshold_value=thresholds["critical_low"],
                    message=f"CRITICAL: DEF level {def_level}% - engine derate imminent",
                    action_required=thresholds["action_critical"],
                )
            )
        elif def_level <= thresholds["warning_low"]:
            status = "warning"
            alerts.append(
                EngineHealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.DEF_LEVEL,
                    severity=AlertSeverity.WARNING,
                    sensor_name="def_level_pct",
                    current_value=def_level,
                    threshold_value=thresholds["warning_low"],
                    message=f"WARNING: DEF level {def_level}% - refill needed soon",
                    action_required=thresholds["action_warning"],
                )
            )
        elif def_level <= thresholds["watch_low"]:
            status = "watch"

        return alerts, status

    def _analyze_engine_load(
        self, truck_id: str, engine_load: float
    ) -> Tuple[List[EngineHealthAlert], str]:
        """Analyze engine load percentage."""
        alerts = []
        status = "normal"
        thresholds = self.thresholds["engine_load_pct"]

        if engine_load >= thresholds["critical_high"]:
            status = "critical"
            alerts.append(
                EngineHealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.ENGINE_LOAD,
                    severity=AlertSeverity.WARNING,  # Not critical immediately
                    sensor_name="engine_load_pct",
                    current_value=engine_load,
                    threshold_value=thresholds["critical_high"],
                    message=f"High engine load: {engine_load}% - sustained overload",
                    action_required=thresholds["action_critical"],
                )
            )
        elif engine_load >= thresholds["warning_high"]:
            status = "warning"
        elif engine_load >= thresholds["watch_high"]:
            status = "watch"

        return alerts, status

    # ───────────────────────────────────────────────────────────────────────────
    # TREND ANALYSIS
    # ───────────────────────────────────────────────────────────────────────────

    def _analyze_trends(
        self, truck_id: str, historical_data: List[Dict], baselines: Optional[Dict]
    ) -> List[EngineHealthAlert]:
        """
        Analyze trends in historical data using simplified Nelson rules.

        Nelson Rule 1: Point outside control limits (already covered in threshold checks)
        Nelson Rule 2: 9 consecutive points on same side of mean
        Nelson Rule 3: 6 consecutive points steadily increasing/decreasing
        """
        alerts = []

        if len(historical_data) < 10:
            return alerts

        # Sort by timestamp
        sorted_data = sorted(historical_data, key=lambda x: x.get("timestamp_utc", ""))

        # Analyze each critical sensor for trends
        sensors_to_check = [
            ("oil_pressure_psi", "Oil Pressure", "falling"),
            ("coolant_temp_f", "Coolant Temperature", "rising"),
            ("battery_voltage", "Battery Voltage", "falling"),
        ]

        for sensor_key, sensor_name, bad_direction in sensors_to_check:
            values = [
                d.get(sensor_key) for d in sorted_data if d.get(sensor_key) is not None
            ]

            if len(values) < 6:
                continue

            # Check for monotonic trend (6+ points)
            recent_values = values[-6:]

            is_increasing = all(
                recent_values[i] <= recent_values[i + 1]
                for i in range(len(recent_values) - 1)
            )
            is_decreasing = all(
                recent_values[i] >= recent_values[i + 1]
                for i in range(len(recent_values) - 1)
            )

            if (bad_direction == "falling" and is_decreasing) or (
                bad_direction == "rising" and is_increasing
            ):
                # Calculate rate of change
                change = recent_values[-1] - recent_values[0]

                alerts.append(
                    EngineHealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.TREND,
                        severity=AlertSeverity.WATCH,
                        sensor_name=sensor_key,
                        current_value=recent_values[-1],
                        threshold_value=recent_values[0],
                        trend_direction=bad_direction,
                        message=f"{sensor_name} showing consistent {bad_direction} trend: {change:+.1f} over last 6 readings",
                        action_required=f"Monitor {sensor_name} closely - schedule inspection if trend continues",
                    )
                )

        return alerts

    # ───────────────────────────────────────────────────────────────────────────
    # MAINTENANCE PREDICTIONS
    # ───────────────────────────────────────────────────────────────────────────

    def _generate_maintenance_predictions(
        self,
        truck_id: str,
        status: TruckHealthStatus,
        alerts: List[EngineHealthAlert],
        baselines: Optional[Dict],
    ) -> List[Dict]:
        """Generate maintenance predictions based on current status and trends."""
        predictions = []

        # Oil pressure prediction
        if status.oil_pressure_status in [
            "warning",
            "watch",
        ] or status.oil_pressure_trend in ["falling", "falling_critical"]:

            # Estimate days until critical based on trend
            days_estimate = (
                "3-7" if status.oil_pressure_trend == "falling_critical" else "7-14"
            )

            predictions.append(
                {
                    "component": "Oil System",
                    "urgency": (
                        "high" if status.oil_pressure_status == "warning" else "medium"
                    ),
                    "prediction": f"Oil pressure declining - potential failure in {days_estimate} days",
                    "recommended_action": "Schedule oil change and pump inspection",
                    "estimated_repair_cost": "$500 - $2,000",
                    "if_ignored_cost": "$15,000 - $40,000 (engine damage)",
                }
            )

        # Coolant system prediction
        if status.coolant_temp_status in [
            "warning",
            "watch",
        ] or status.coolant_temp_trend in ["rising", "rising_critical"]:
            predictions.append(
                {
                    "component": "Cooling System",
                    "urgency": (
                        "high" if status.coolant_temp_status == "warning" else "medium"
                    ),
                    "prediction": "Cooling system efficiency degrading",
                    "recommended_action": "Check coolant level, radiator, thermostat, water pump",
                    "estimated_repair_cost": "$200 - $1,500",
                    "if_ignored_cost": "$10,000 - $25,000 (head gasket, engine damage)",
                }
            )

        # Battery prediction
        if (
            status.battery_status in ["warning", "watch"]
            or status.battery_trend == "falling"
        ):
            predictions.append(
                {
                    "component": "Electrical System",
                    "urgency": "medium",
                    "prediction": "Battery health declining - may not start within 2-4 weeks",
                    "recommended_action": "Test battery and alternator, replace if needed",
                    "estimated_repair_cost": "$150 - $400",
                    "if_ignored_cost": "$500+ (tow) + downtime",
                }
            )

        # DEF prediction
        if status.def_level_status in ["warning", "critical"]:
            predictions.append(
                {
                    "component": "DEF System",
                    "urgency": (
                        "high" if status.def_level_status == "critical" else "medium"
                    ),
                    "prediction": "DEF level low - engine derate risk",
                    "recommended_action": "Refill DEF tank at next stop",
                    "estimated_repair_cost": "$50 - $100 (DEF fluid)",
                    "if_ignored_cost": "$2,000+ (derate penalties, delays)",
                }
            )

        return predictions

    # ───────────────────────────────────────────────────────────────────────────
    # HELPER METHODS
    # ───────────────────────────────────────────────────────────────────────────

    def _get_baselines(self, truck_id: str) -> Dict[str, SensorBaseline]:
        """
        🔧 v6.2.2: BUG-001 FIX - Load baselines from database with caching.
        
        Baselines are now persisted to prevent loss on server restart.
        """
        # Check memory cache first
        if truck_id in self._baselines_cache:
            return self._baselines_cache[truck_id]
        
        # Try to load from database
        baselines = {}
        try:
            if self.db:  # If we have a database connection
                from database_pool import get_local_engine
                engine = get_local_engine()
                if engine:
                    with engine.connect() as conn:
                        result = conn.execute(
                            text("""
                                SELECT sensor_name, mean_value, std_dev, min_value, max_value,
                                       median_value, sample_count, days_analyzed, last_updated
                                FROM engine_health_baselines
                                WHERE truck_id = :truck_id
                                AND last_updated > NOW() - INTERVAL :days DAY
                            """),
                            {"truck_id": truck_id, "days": 60}  # Use baselines up to 60 days old
                        )
                        
                        for row in result:
                            sensor_name = row[0]
                            baselines[sensor_name] = SensorBaseline(
                                sensor_name=sensor_name,
                                truck_id=truck_id,
                                mean_30d=float(row[1]) if row[1] else None,
                                std_30d=float(row[2]) if row[2] else None,
                                min_30d=float(row[3]) if row[3] else None,
                                max_30d=float(row[4]) if row[4] else None,
                                sample_count=int(row[6]) if row[6] else 0,
                                last_updated=row[8] if row[8] else datetime.now(timezone.utc)
                            )
                        
                        if baselines:
                            logger.info(f"📥 Loaded {len(baselines)} baselines for {truck_id} from DB")
                            # Cache the loaded baselines
                            self._baselines_cache[truck_id] = baselines
        except Exception as e:
            logger.debug(f"Could not load baselines from DB for {truck_id}: {e}")
        
        return baselines

    def _save_baselines(self, truck_id: str, baselines: Dict[str, SensorBaseline]):
        """
        🔧 v6.2.2: BUG-001 FIX - Persist baselines to database.
        
        Uses INSERT ... ON DUPLICATE KEY UPDATE for upsert behavior.
        """
        if not baselines:
            return
        
        try:
            from database_pool import get_local_engine
            engine = get_local_engine()
            if not engine:
                logger.debug("No database engine - baselines not persisted")
                return
            
            with engine.connect() as conn:
                for sensor_name, baseline in baselines.items():
                    conn.execute(
                        text("""
                            INSERT INTO engine_health_baselines 
                            (truck_id, sensor_name, mean_value, std_dev, min_value, max_value,
                             median_value, sample_count, days_analyzed, last_updated)
                            VALUES 
                            (:truck_id, :sensor_name, :mean_value, :std_dev, :min_value, :max_value,
                             :median_value, :sample_count, :days, NOW())
                            ON DUPLICATE KEY UPDATE
                                mean_value = VALUES(mean_value),
                                std_dev = VALUES(std_dev),
                                min_value = VALUES(min_value),
                                max_value = VALUES(max_value),
                                median_value = VALUES(median_value),
                                sample_count = VALUES(sample_count),
                                days_analyzed = VALUES(days_analyzed),
                                last_updated = NOW()
                        """),
                        {
                            "truck_id": truck_id,
                            "sensor_name": sensor_name,
                            "mean_value": baseline.mean_30d,
                            "std_dev": baseline.std_30d,
                            "min_value": baseline.min_30d,
                            "max_value": baseline.max_30d,
                            "median_value": baseline.mean_30d,  # Use mean as median approximation
                            "sample_count": baseline.sample_count,
                            "days": 30
                        }
                    )
                conn.commit()
                logger.info(f"💾 Saved {len(baselines)} baselines for {truck_id} to DB")
                
                # Update cache
                self._baselines_cache[truck_id] = baselines
                
        except Exception as e:
            logger.error(f"Failed to save baselines for {truck_id}: {e}")

    def _filter_alerts_by_cooldown(
        self, alerts: List[EngineHealthAlert]
    ) -> List[EngineHealthAlert]:
        """Filter out alerts that are within cooldown period to prevent spam."""
        filtered = []
        now = datetime.now(timezone.utc)

        for alert in alerts:
            key = f"{alert.truck_id}:{alert.category.value}:{alert.sensor_name}"
            last_alert = self._alert_cooldown.get(key)

            # Always include critical alerts
            if alert.severity == AlertSeverity.CRITICAL:
                filtered.append(alert)
                self._alert_cooldown[key] = now
            # Check cooldown for non-critical
            elif last_alert is None or (now - last_alert).total_seconds() > (
                self.cooldown_minutes * 60
            ):
                filtered.append(alert)
                self._alert_cooldown[key] = now

        return filtered


# ═══════════════════════════════════════════════════════════════════════════════
# BASELINE CALCULATOR
# ═══════════════════════════════════════════════════════════════════════════════


class BaselineCalculator:
    """Calculate and update sensor baselines from historical data."""

    @staticmethod
    def calculate_baseline(
        truck_id: str, sensor_name: str, historical_data: List[Dict], days: int = 30
    ) -> SensorBaseline:
        """
        Calculate baseline statistics for a sensor.

        Args:
            truck_id: Truck identifier
            sensor_name: Sensor field name (e.g., "oil_pressure_psi")
            historical_data: List of readings with timestamps
            days: Number of days for baseline calculation

        Returns:
            SensorBaseline with statistics
        """
        now = datetime.now(timezone.utc)
        cutoff_30d = now - timedelta(days=30)
        cutoff_7d = now - timedelta(days=7)

        values_30d = []
        values_7d = []

        for record in historical_data:
            value = record.get(sensor_name)
            if value is None:
                continue

            timestamp = record.get("timestamp_utc")
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))

            if timestamp and timestamp >= cutoff_30d:
                values_30d.append(value)
                if timestamp >= cutoff_7d:
                    values_7d.append(value)

        baseline = SensorBaseline(
            sensor_name=sensor_name,
            truck_id=truck_id,
            sample_count=len(values_30d),
        )

        if values_30d:
            baseline.mean_30d = statistics.mean(values_30d)
            baseline.min_30d = min(values_30d)
            baseline.max_30d = max(values_30d)
            if len(values_30d) > 1:
                baseline.std_30d = statistics.stdev(values_30d)

        if values_7d:
            baseline.mean_7d = statistics.mean(values_7d)
            if len(values_7d) > 1:
                baseline.std_7d = statistics.stdev(values_7d)

        return baseline


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_health_color(status: str) -> str:
    """Get color code for health status (for frontend)."""
    colors = {
        "healthy": "#22c55e",  # Green
        "normal": "#22c55e",
        "warning": "#f59e0b",  # Amber
        "watch": "#eab308",  # Yellow
        "critical": "#ef4444",  # Red
        "offline": "#6b7280",  # Gray
        "unknown": "#9ca3af",  # Light gray
    }
    return colors.get(status, "#9ca3af")


def get_status_icon(status: str) -> str:
    """Get emoji icon for health status."""
    icons = {
        "healthy": "🟢",
        "normal": "🟢",
        "warning": "🟡",
        "watch": "🟡",
        "critical": "🔴",
        "offline": "⚫",
        "unknown": "⚪",
    }
    return icons.get(status, "⚪")


def format_alert_for_sms(alert: EngineHealthAlert) -> str:
    """Format an alert for SMS notification."""
    severity_emoji = "🔴" if alert.severity == AlertSeverity.CRITICAL else "🟡"
    return (
        f"{severity_emoji} {alert.truck_id}: {alert.message}\n"
        f"Action: {alert.action_required}"
    )


def format_alert_for_email(alert: EngineHealthAlert) -> Dict:
    """Format an alert for email notification."""
    return {
        "subject": f"[{alert.severity.value.upper()}] {alert.truck_id} - {alert.sensor_name}",
        "body": f"""
Engine Health Alert

Truck: {alert.truck_id}
Severity: {alert.severity.value.upper()}
Sensor: {alert.sensor_name}
Current Value: {alert.current_value}
Threshold: {alert.threshold_value}

Message: {alert.message}

Required Action: {alert.action_required}

Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}
        """.strip(),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Quick test
    analyzer = EngineHealthAnalyzer()

    # Test data - critical oil pressure
    test_data = {
        "truck_id": "TEST001",
        "timestamp_utc": datetime.now(timezone.utc),
        "oil_pressure_psi": 18,  # Critical!
        "coolant_temp_f": 205,
        "oil_temp_f": 230,
        "battery_voltage": 14.1,
        "def_level_pct": 8,  # Warning
        "engine_load_pct": 75,
        "rpm": 1500,
    }

    status = analyzer.analyze_truck_health("TEST001", test_data)

    print("=" * 60)
    print("ENGINE HEALTH TEST")
    print("=" * 60)
    print(f"Truck: {status.truck_id}")
    print(f"Overall Status: {status.overall_status.value}")
    print(f"Critical Alerts: {status.alert_count_critical}")
    print(f"Warning Alerts: {status.alert_count_warning}")
    print()

    for alert in status.active_alerts:
        print(
            f"{get_status_icon(alert.severity.value)} [{alert.severity.value.upper()}] {alert.message}"
        )
        print(f"   Action: {alert.action_required}")
        print()

    if status.maintenance_predictions:
        print("Maintenance Predictions:")
        for pred in status.maintenance_predictions:
            print(f"  • {pred['component']}: {pred['prediction']}")
            print(f"    Cost if ignored: {pred['if_ignored_cost']}")
