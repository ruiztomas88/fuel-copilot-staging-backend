"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║              PREDICTIVE MAINTENANCE ENGINE v1.0                                ║
║                     Fuel Copilot - FleetBooster                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Purpose: Engine health monitoring and predictive maintenance alerts          ║
║                                                                                ║
║  Strategy: START SIMPLE, BUILD UP                                              ║
║  - Phase 1: Rules + Thresholds + 7-day Trends (THIS FILE)                     ║
║  - Phase 2: Statistical anomaly detection (Nelson rules, Z-scores)            ║
║  - Phase 3: ML models when we have 6+ months of failure data                  ║
║                                                                                ║
║  Competitive Advantage vs Geotab/Samsara:                                      ║
║  - They charge $50-100/truck/month for predictive maintenance                 ║
║  - We include it FREE with smarter algorithms                                  ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS AND CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


class HealthStatus(str, Enum):
    """Component health status"""

    CRITICAL = "critical"  # Red - Immediate attention needed
    WARNING = "warning"  # Yellow - Monitor closely
    GOOD = "good"  # Green - Operating normally
    UNKNOWN = "unknown"  # Gray - No data available


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    CRITICAL = "critical"  # Action required NOW
    HIGH = "high"  # Action required within 24h
    MEDIUM = "medium"  # Action required within 7 days
    LOW = "low"  # Informational


class AlertCategory(str, Enum):
    """Alert categories for grouping"""

    ENGINE = "engine"
    COOLING = "cooling"
    ELECTRICAL = "electrical"
    FUEL = "fuel"
    EMISSIONS = "emissions"
    DRIVETRAIN = "drivetrain"


# ═══════════════════════════════════════════════════════════════════════════════
# THRESHOLDS - Based on J1939 standards and OEM recommendations
# ═══════════════════════════════════════════════════════════════════════════════

# These are conservative thresholds for Class 8 trucks (Freightliner, Peterbilt, etc.)
THRESHOLDS = {
    # Oil Pressure (psi) - SPN 100
    "oil_press": {
        "critical_low": 15,  # Engine damage imminent
        "warning_low": 25,  # Check oil level/pump
        "normal_min": 30,  # Normal operating range
        "normal_max": 75,  # Normal operating range
        "warning_high": 85,  # Possible sensor issue
    },
    # Coolant Temperature (°F) - SPN 110
    "cool_temp": {
        "critical_low": 100,  # Engine too cold (thermostat stuck open)
        "warning_low": 160,  # Not at operating temp
        "normal_min": 180,  # Normal operating range
        "normal_max": 210,  # Normal operating range
        "warning_high": 220,  # Overheating warning
        "critical_high": 230,  # Overheating critical
    },
    # Oil Temperature (°F) - SPN 175
    "oil_temp": {
        "normal_min": 180,
        "normal_max": 230,
        "warning_high": 245,  # Oil breakdown begins
        "critical_high": 260,  # Severe oil degradation
    },
    # Battery Voltage (V) - SPN 168
    "pwr_ext": {
        "critical_low": 11.5,  # Battery dead/alternator failed
        "warning_low": 12.4,  # Battery weak
        "normal_min": 13.2,  # Normal with engine running
        "normal_max": 14.8,  # Normal charging
        "warning_high": 15.2,  # Overcharging
        "critical_high": 16.0,  # Regulator failed
    },
    # RPM - SPN 190
    "rpm": {
        "idle_min": 550,  # Low idle
        "idle_max": 900,  # High idle
        "normal_max": 2100,  # Normal operating
        "warning_high": 2300,  # Over-revving
        "critical_high": 2500,  # Engine damage risk
    },
    # Engine Load (%) - SPN 92
    "engine_load": {
        "normal_max": 85,  # Sustained load limit
        "warning_high": 95,  # High stress
        "critical_high": 100,  # Overloaded
    },
    # DEF Level (%) - SPN 1761
    "def_level": {
        "critical_low": 5,  # Derate imminent
        "warning_low": 15,  # Refill soon
        "normal_min": 20,  # Acceptable
    },
    # Fuel Rate (gal/h) - SPN 183
    "fuel_rate": {
        "idle_max": 1.5,  # Max acceptable idle consumption
        "normal_max": 15,  # Normal driving
        "warning_high": 20,  # Excessive consumption
    },
}

# Trend thresholds (% change over 7 days that triggers alert)
TREND_THRESHOLDS = {
    "oil_press": {"decline": -10, "severity": AlertSeverity.HIGH},
    "cool_temp": {"increase": 8, "severity": AlertSeverity.MEDIUM},
    "oil_temp": {"increase": 10, "severity": AlertSeverity.MEDIUM},
    "pwr_ext": {"decline": -5, "severity": AlertSeverity.MEDIUM},
    "fuel_rate": {"increase": 15, "severity": AlertSeverity.LOW},
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class HealthAlert:
    """A single health alert"""

    truck_id: str
    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    metric: str
    current_value: float
    threshold: float
    trend_pct: Optional[float] = None
    recommendation: str = ""
    estimated_days_to_failure: Optional[int] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "category": self.category.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "metric": self.metric,
            "current_value": (
                round(self.current_value, 2) if self.current_value else None
            ),
            "threshold": self.threshold,
            "trend_pct": round(self.trend_pct, 1) if self.trend_pct else None,
            "recommendation": self.recommendation,
            "estimated_days_to_failure": self.estimated_days_to_failure,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ComponentHealth:
    """Health score for a component category"""

    category: AlertCategory
    score: int  # 0-100
    status: HealthStatus
    alerts: List[HealthAlert] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "category": self.category.value,
            "score": self.score,
            "status": self.status.value,
            "alert_count": len(self.alerts),
            "metrics": self.metrics,
        }


@dataclass
class TruckHealth:
    """Overall health for a single truck"""

    truck_id: str
    overall_score: int  # 0-100
    overall_status: HealthStatus
    components: Dict[str, ComponentHealth]
    alerts: List[HealthAlert]
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "overall_score": self.overall_score,
            "overall_status": self.overall_status.value,
            "components": {k: v.to_dict() for k, v in self.components.items()},
            "alerts": [a.to_dict() for a in self.alerts],
            "last_updated": self.last_updated.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE CLASS
# ═══════════════════════════════════════════════════════════════════════════════


class PredictiveMaintenanceEngine:
    """
    Engine Health Monitoring and Predictive Maintenance

    Phase 1: Rule-based alerts + 7-day trend analysis
    - Threshold alerts (immediate issues)
    - Trend alerts (developing problems)
    - Component health scores
    """

    def __init__(self):
        self.thresholds = THRESHOLDS
        self.trend_thresholds = TREND_THRESHOLDS

    # ═══════════════════════════════════════════════════════════════════════════
    # THRESHOLD CHECKS
    # ═══════════════════════════════════════════════════════════════════════════

    def check_oil_pressure(
        self, truck_id: str, current: float, rpm: Optional[float] = None
    ) -> List[HealthAlert]:
        """Check oil pressure against thresholds"""
        alerts = []
        t = self.thresholds["oil_press"]

        # Adjust threshold based on RPM (pressure lower at idle is normal)
        # For Cummins/Detroit, 15-20 psi at hot idle is normal
        is_idle = rpm is not None and rpm < 900
        critical_low = 8 if is_idle else 15  # Below 8 psi at idle = pump failure
        warning_low = 15 if is_idle else 25  # 15-20 psi at idle is acceptable

        if current < critical_low:
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.ENGINE,
                    severity=AlertSeverity.CRITICAL,
                    title="Critical Oil Pressure",
                    message=f"Oil pressure at {current:.0f} psi - STOP ENGINE IMMEDIATELY",
                    metric="oil_press",
                    current_value=current,
                    threshold=critical_low,
                    recommendation="Stop truck immediately. Check oil level, filter, and pump. Do not drive.",
                    estimated_days_to_failure=0,
                )
            )
        elif current < warning_low:
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.ENGINE,
                    severity=AlertSeverity.HIGH,
                    title="Low Oil Pressure",
                    message=f"Oil pressure at {current:.0f} psi - below safe operating range",
                    metric="oil_press",
                    current_value=current,
                    threshold=warning_low,
                    recommendation="Check oil level immediately. Schedule service within 24 hours.",
                    estimated_days_to_failure=1,
                )
            )

        return alerts

    def check_coolant_temp(
        self, truck_id: str, current: float, engine_running: bool = True
    ) -> List[HealthAlert]:
        """Check coolant temperature against thresholds"""
        alerts = []
        t = self.thresholds["cool_temp"]

        if not engine_running:
            return alerts

        if current >= t["critical_high"]:
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.COOLING,
                    severity=AlertSeverity.CRITICAL,
                    title="Engine Overheating",
                    message=f"Coolant at {current:.0f}°F - PULL OVER IMMEDIATELY",
                    metric="cool_temp",
                    current_value=current,
                    threshold=t["critical_high"],
                    recommendation="Stop truck, let engine cool. Check coolant level, radiator, water pump, thermostat.",
                    estimated_days_to_failure=0,
                )
            )
        elif current >= t["warning_high"]:
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.COOLING,
                    severity=AlertSeverity.HIGH,
                    title="High Coolant Temperature",
                    message=f"Coolant at {current:.0f}°F - approaching overheat",
                    metric="cool_temp",
                    current_value=current,
                    threshold=t["warning_high"],
                    recommendation="Reduce load, monitor closely. Schedule cooling system inspection.",
                    estimated_days_to_failure=3,
                )
            )
        elif current < t["warning_low"] and engine_running:
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.COOLING,
                    severity=AlertSeverity.MEDIUM,
                    title="Engine Running Cold",
                    message=f"Coolant at {current:.0f}°F after warmup - thermostat may be stuck open",
                    metric="cool_temp",
                    current_value=current,
                    threshold=t["warning_low"],
                    recommendation="Check thermostat. Running cold reduces fuel efficiency and increases wear.",
                    estimated_days_to_failure=14,
                )
            )

        return alerts

    def check_battery_voltage(
        self, truck_id: str, current: float, engine_running: bool = True
    ) -> List[HealthAlert]:
        """Check battery/alternator voltage"""
        alerts = []
        t = self.thresholds["pwr_ext"]

        if engine_running:
            if current < t["critical_low"]:
                alerts.append(
                    HealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.ELECTRICAL,
                        severity=AlertSeverity.CRITICAL,
                        title="Charging System Failure",
                        message=f"Voltage at {current:.1f}V - alternator not charging",
                        metric="pwr_ext",
                        current_value=current,
                        threshold=t["critical_low"],
                        recommendation="Check alternator belt and connections. May need immediate replacement.",
                        estimated_days_to_failure=0,
                    )
                )
            elif current < t["warning_low"]:
                alerts.append(
                    HealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.ELECTRICAL,
                        severity=AlertSeverity.MEDIUM,
                        title="Low Charging Voltage",
                        message=f"Voltage at {current:.1f}V - battery may not be fully charging",
                        metric="pwr_ext",
                        current_value=current,
                        threshold=t["warning_low"],
                        recommendation="Check battery terminals, alternator output. Schedule electrical inspection.",
                        estimated_days_to_failure=7,
                    )
                )
            elif current > t["warning_high"]:
                alerts.append(
                    HealthAlert(
                        truck_id=truck_id,
                        category=AlertCategory.ELECTRICAL,
                        severity=AlertSeverity.MEDIUM,
                        title="Overcharging",
                        message=f"Voltage at {current:.1f}V - voltage regulator may be failing",
                        metric="pwr_ext",
                        current_value=current,
                        threshold=t["warning_high"],
                        recommendation="Check voltage regulator. Overcharging damages batteries.",
                        estimated_days_to_failure=7,
                    )
                )

        return alerts

    def check_def_level(self, truck_id: str, current: float) -> List[HealthAlert]:
        """Check DEF level"""
        alerts = []
        t = self.thresholds["def_level"]

        if current <= t["critical_low"]:
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.EMISSIONS,
                    severity=AlertSeverity.CRITICAL,
                    title="DEF Tank Critical",
                    message=f"DEF level at {current:.0f}% - derate imminent",
                    metric="def_level",
                    current_value=current,
                    threshold=t["critical_low"],
                    recommendation="Refill DEF immediately. Engine will derate to 5 mph if empty.",
                    estimated_days_to_failure=0,
                )
            )
        elif current <= t["warning_low"]:
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.EMISSIONS,
                    severity=AlertSeverity.MEDIUM,
                    title="DEF Tank Low",
                    message=f"DEF level at {current:.0f}% - refill soon",
                    metric="def_level",
                    current_value=current,
                    threshold=t["warning_low"],
                    recommendation="Plan DEF refill at next stop.",
                    estimated_days_to_failure=3,
                )
            )

        return alerts

    def check_oil_temp(self, truck_id: str, current: float) -> List[HealthAlert]:
        """Check oil temperature"""
        alerts = []
        t = self.thresholds["oil_temp"]

        if current >= t["critical_high"]:
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.ENGINE,
                    severity=AlertSeverity.CRITICAL,
                    title="Critical Oil Temperature",
                    message=f"Oil temp at {current:.0f}°F - oil breakdown occurring",
                    metric="oil_temp",
                    current_value=current,
                    threshold=t["critical_high"],
                    recommendation="Stop truck. Oil is losing lubricating properties. Check cooling system.",
                    estimated_days_to_failure=0,
                )
            )
        elif current >= t["warning_high"]:
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=AlertCategory.ENGINE,
                    severity=AlertSeverity.HIGH,
                    title="High Oil Temperature",
                    message=f"Oil temp at {current:.0f}°F - elevated",
                    metric="oil_temp",
                    current_value=current,
                    threshold=t["warning_high"],
                    recommendation="Reduce load, check oil cooler and level.",
                    estimated_days_to_failure=3,
                )
            )

        return alerts

    # ═══════════════════════════════════════════════════════════════════════════
    # TREND ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════

    # Minimum floor values per metric to avoid inflated trend percentages
    # e.g., if first_avg is 0.5, pct_change would be huge and misleading
    MIN_TREND_FLOORS = {
        "oil_press": 10.0,  # psi - anything below 10 is already a problem
        "cool_temp": 100.0,  # °F - below 100 engine is cold
        "oil_temp": 100.0,  # °F
        "pwr_ext": 10.0,  # V - below 10V battery is dead
        "fuel_rate": 1.0,  # gal/h - idle consumption
        "def_level": 5.0,  # % - low DEF is already critical
        "rpm": 500.0,  # RPM - below 500 is idle/off
    }

    def calculate_trend(
        self, values: List[Tuple[datetime, float]], metric: str = "", days: int = 7
    ) -> Optional[float]:
        """
        Calculate percentage change over time period

        Args:
            values: List of (timestamp, value) tuples, ordered by time
            metric: Metric name for floor lookup (oil_press, cool_temp, etc.)
            days: Number of days to analyze

        Returns:
            Percentage change (positive = increase, negative = decrease)
        """
        if len(values) < 10:  # Need minimum data points
            return None

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        recent = [v for ts, v in values if ts >= cutoff]

        if len(recent) < 5:
            return None

        # Compare first quarter average to last quarter average
        quarter = len(recent) // 4
        if quarter < 2:
            return None

        first_avg = statistics.mean(recent[:quarter])
        last_avg = statistics.mean(recent[-quarter:])

        if first_avg == 0:
            return None

        # Use metric-specific floor, default to 5.0 for unknown metrics
        min_floor = self.MIN_TREND_FLOORS.get(metric, 5.0)
        if first_avg < min_floor:
            return None

        pct_change = ((last_avg - first_avg) / first_avg) * 100
        return pct_change

    def check_trends(
        self,
        truck_id: str,
        metric: str,
        values: List[Tuple[datetime, float]],
    ) -> List[HealthAlert]:
        """Check for concerning trends in a metric"""
        alerts = []

        if metric not in self.trend_thresholds:
            return alerts

        trend_pct = self.calculate_trend(values, metric=metric)
        if trend_pct is None:
            return alerts

        config = self.trend_thresholds[metric]

        # Check for decline (negative trend)
        if "decline" in config and trend_pct <= config["decline"]:
            category = (
                AlertCategory.ENGINE
                if metric in ["oil_press"]
                else AlertCategory.ELECTRICAL
            )
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=category,
                    severity=config["severity"],
                    title=f"{metric.replace('_', ' ').title()} Trending Down",
                    message=f"{metric} has declined {abs(trend_pct):.1f}% over 7 days",
                    metric=metric,
                    current_value=values[-1][1] if values else 0,
                    threshold=config["decline"],
                    trend_pct=trend_pct,
                    recommendation=f"Schedule inspection. Gradual decline indicates developing problem.",
                    estimated_days_to_failure=7,
                )
            )

        # Check for increase (positive trend)
        if "increase" in config and trend_pct >= config["increase"]:
            category = (
                AlertCategory.COOLING
                if metric in ["cool_temp", "oil_temp"]
                else AlertCategory.FUEL
            )
            alerts.append(
                HealthAlert(
                    truck_id=truck_id,
                    category=category,
                    severity=config["severity"],
                    title=f"{metric.replace('_', ' ').title()} Trending Up",
                    message=f"{metric} has increased {trend_pct:.1f}% over 7 days",
                    metric=metric,
                    current_value=values[-1][1] if values else 0,
                    threshold=config["increase"],
                    trend_pct=trend_pct,
                    recommendation=f"Monitor closely. Gradual increase may indicate cooling or efficiency issue.",
                    estimated_days_to_failure=14,
                )
            )

        return alerts

    # ═══════════════════════════════════════════════════════════════════════════
    # HEALTH SCORE CALCULATION
    # ═══════════════════════════════════════════════════════════════════════════

    def calculate_component_score(
        self,
        category: AlertCategory,
        alerts: List[HealthAlert],
        metrics: Dict[str, float],
    ) -> ComponentHealth:
        """Calculate health score for a component category"""

        # Start with perfect score
        score = 100

        # Deduct points based on alert severity
        for alert in alerts:
            if alert.severity == AlertSeverity.CRITICAL:
                score -= 40
            elif alert.severity == AlertSeverity.HIGH:
                score -= 25
            elif alert.severity == AlertSeverity.MEDIUM:
                score -= 15
            elif alert.severity == AlertSeverity.LOW:
                score -= 5

        # Ensure score is in valid range
        score = max(0, min(100, score))

        # Determine status
        if score >= 80:
            status = HealthStatus.GOOD
        elif score >= 50:
            status = HealthStatus.WARNING
        else:
            status = HealthStatus.CRITICAL

        return ComponentHealth(
            category=category,
            score=score,
            status=status,
            alerts=alerts,
            metrics=metrics,
        )

    def analyze_truck(
        self,
        truck_id: str,
        current_values: Dict[str, float],
        historical_values: Optional[Dict[str, List[Tuple[datetime, float]]]] = None,
    ) -> TruckHealth:
        """
        Perform complete health analysis for a single truck

        Args:
            truck_id: Truck identifier
            current_values: Current sensor readings {metric: value}
            historical_values: Historical readings for trend analysis

        Returns:
            TruckHealth object with scores and alerts
        """
        all_alerts: List[HealthAlert] = []
        components: Dict[str, ComponentHealth] = {}

        # Get current values with defaults
        oil_press = current_values.get("oil_press")
        cool_temp = current_values.get("cool_temp")
        oil_temp = current_values.get("oil_temp")
        pwr_ext = current_values.get("pwr_ext")
        def_level = current_values.get("def_level")
        rpm = current_values.get("rpm")
        engine_load = current_values.get("engine_load")

        engine_running = rpm is not None and rpm > 400

        # ─────────────────────────────────────────────────────────────────────
        # ENGINE HEALTH
        # ─────────────────────────────────────────────────────────────────────
        engine_alerts = []
        engine_metrics = {}

        if oil_press is not None:
            engine_alerts.extend(self.check_oil_pressure(truck_id, oil_press, rpm))
            engine_metrics["oil_pressure_psi"] = oil_press

        if oil_temp is not None:
            engine_alerts.extend(self.check_oil_temp(truck_id, oil_temp))
            engine_metrics["oil_temp_f"] = oil_temp

        if rpm is not None:
            engine_metrics["rpm"] = rpm

        if engine_load is not None:
            engine_metrics["engine_load_pct"] = engine_load

        # Trend analysis for oil pressure
        if historical_values and "oil_press" in historical_values:
            engine_alerts.extend(
                self.check_trends(truck_id, "oil_press", historical_values["oil_press"])
            )

        components["engine"] = self.calculate_component_score(
            AlertCategory.ENGINE, engine_alerts, engine_metrics
        )
        all_alerts.extend(engine_alerts)

        # ─────────────────────────────────────────────────────────────────────
        # COOLING SYSTEM
        # ─────────────────────────────────────────────────────────────────────
        cooling_alerts = []
        cooling_metrics = {}

        if cool_temp is not None:
            cooling_alerts.extend(
                self.check_coolant_temp(truck_id, cool_temp, engine_running)
            )
            cooling_metrics["coolant_temp_f"] = cool_temp

        # Trend analysis
        if historical_values and "cool_temp" in historical_values:
            cooling_alerts.extend(
                self.check_trends(truck_id, "cool_temp", historical_values["cool_temp"])
            )

        components["cooling"] = self.calculate_component_score(
            AlertCategory.COOLING, cooling_alerts, cooling_metrics
        )
        all_alerts.extend(cooling_alerts)

        # ─────────────────────────────────────────────────────────────────────
        # ELECTRICAL SYSTEM
        # ─────────────────────────────────────────────────────────────────────
        electrical_alerts = []
        electrical_metrics = {}

        if pwr_ext is not None:
            electrical_alerts.extend(
                self.check_battery_voltage(truck_id, pwr_ext, engine_running)
            )
            electrical_metrics["battery_voltage"] = pwr_ext

        # Trend analysis
        if historical_values and "pwr_ext" in historical_values:
            electrical_alerts.extend(
                self.check_trends(truck_id, "pwr_ext", historical_values["pwr_ext"])
            )

        components["electrical"] = self.calculate_component_score(
            AlertCategory.ELECTRICAL, electrical_alerts, electrical_metrics
        )
        all_alerts.extend(electrical_alerts)

        # ─────────────────────────────────────────────────────────────────────
        # FUEL SYSTEM
        # ─────────────────────────────────────────────────────────────────────
        fuel_alerts = []
        fuel_metrics = {}

        if "fuel_rate" in current_values:
            fuel_metrics["fuel_rate_gph"] = current_values["fuel_rate"]

        if "fuel_lvl" in current_values:
            fuel_metrics["fuel_level_pct"] = current_values["fuel_lvl"]

        # Trend analysis for fuel efficiency
        if historical_values and "fuel_rate" in historical_values:
            fuel_alerts.extend(
                self.check_trends(truck_id, "fuel_rate", historical_values["fuel_rate"])
            )

        components["fuel"] = self.calculate_component_score(
            AlertCategory.FUEL, fuel_alerts, fuel_metrics
        )
        all_alerts.extend(fuel_alerts)

        # ─────────────────────────────────────────────────────────────────────
        # EMISSIONS SYSTEM
        # ─────────────────────────────────────────────────────────────────────
        emissions_alerts = []
        emissions_metrics = {}

        if def_level is not None:
            emissions_alerts.extend(self.check_def_level(truck_id, def_level))
            emissions_metrics["def_level_pct"] = def_level

        components["emissions"] = self.calculate_component_score(
            AlertCategory.EMISSIONS, emissions_alerts, emissions_metrics
        )
        all_alerts.extend(emissions_alerts)

        # ─────────────────────────────────────────────────────────────────────
        # OVERALL HEALTH
        # ─────────────────────────────────────────────────────────────────────

        # Calculate overall score (weighted average of components with data)
        valid_components = [c for c in components.values() if c.metrics]
        if valid_components:
            # Weight engine and cooling higher
            weights = {
                AlertCategory.ENGINE: 2.0,
                AlertCategory.COOLING: 1.5,
                AlertCategory.ELECTRICAL: 1.0,
                AlertCategory.FUEL: 1.0,
                AlertCategory.EMISSIONS: 0.8,
            }

            total_weight = sum(weights.get(c.category, 1.0) for c in valid_components)
            weighted_sum = sum(
                c.score * weights.get(c.category, 1.0) for c in valid_components
            )
            overall_score = (
                int(weighted_sum / total_weight) if total_weight > 0 else 100
            )
        else:
            overall_score = 100  # No data = assume OK

        # Determine overall status
        if overall_score >= 80:
            overall_status = HealthStatus.GOOD
        elif overall_score >= 50:
            overall_status = HealthStatus.WARNING
        else:
            overall_status = HealthStatus.CRITICAL

        # Sort alerts by severity
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.HIGH: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.LOW: 3,
        }
        all_alerts.sort(key=lambda a: severity_order[a.severity])

        return TruckHealth(
            truck_id=truck_id,
            overall_score=overall_score,
            overall_status=overall_status,
            components=components,
            alerts=all_alerts,
        )

    def generate_fleet_health_report(
        self,
        trucks_data: List[Dict],
    ) -> Dict:
        """
        Generate health report for entire fleet

        Args:
            trucks_data: List of truck data dicts with current sensor values

        Returns:
            Fleet health report with summaries and alerts
        """
        truck_health_results = []
        all_alerts = []

        for truck_data in trucks_data:
            truck_id = truck_data.get("truck_id", "Unknown")

            # Extract current values, filtering out None values
            raw_values = {
                "oil_press": truck_data.get("oil_press"),
                "cool_temp": truck_data.get("cool_temp"),
                "oil_temp": truck_data.get("oil_temp"),
                "pwr_ext": truck_data.get("pwr_ext"),
                "def_level": truck_data.get("def_level"),
                "rpm": truck_data.get("rpm"),
                "engine_load": truck_data.get("engine_load"),
                "fuel_rate": truck_data.get("fuel_rate"),
                "fuel_lvl": truck_data.get("fuel_lvl"),
            }
            # Filter out None values and convert to floats
            current_values: Dict[str, float] = {
                k: float(v) for k, v in raw_values.items() if v is not None
            }

            # Extract historical values if provided
            historical = truck_data.get("historical", {})

            # Analyze truck
            health = self.analyze_truck(truck_id, current_values, historical)
            truck_health_results.append(health)
            all_alerts.extend(health.alerts)

        # Calculate fleet summary
        total_trucks = len(truck_health_results)
        trucks_ok = sum(
            1 for t in truck_health_results if t.overall_status == HealthStatus.GOOD
        )
        trucks_warning = sum(
            1 for t in truck_health_results if t.overall_status == HealthStatus.WARNING
        )
        trucks_critical = sum(
            1 for t in truck_health_results if t.overall_status == HealthStatus.CRITICAL
        )

        fleet_score = (
            sum(t.overall_score for t in truck_health_results) // total_trucks
            if total_trucks > 0
            else 100
        )

        # Count alerts by severity
        critical_alerts = sum(
            1 for a in all_alerts if a.severity == AlertSeverity.CRITICAL
        )
        high_alerts = sum(1 for a in all_alerts if a.severity == AlertSeverity.HIGH)
        medium_alerts = sum(1 for a in all_alerts if a.severity == AlertSeverity.MEDIUM)

        # Sort all alerts by severity
        severity_order = {
            AlertSeverity.CRITICAL: 0,
            AlertSeverity.HIGH: 1,
            AlertSeverity.MEDIUM: 2,
            AlertSeverity.LOW: 3,
        }
        all_alerts.sort(key=lambda a: severity_order[a.severity])

        return {
            "status": "success",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "fleet_summary": {
                "total_trucks": total_trucks,
                "fleet_health_score": fleet_score,
                "trucks_ok": trucks_ok,
                "trucks_warning": trucks_warning,
                "trucks_critical": trucks_critical,
            },
            "alert_summary": {
                "total_alerts": len(all_alerts),
                "critical": critical_alerts,
                "high": high_alerts,
                "medium": medium_alerts,
            },
            "alerts": [a.to_dict() for a in all_alerts[:20]],  # Top 20 alerts
            "trucks": [t.to_dict() for t in truck_health_results],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test the engine
    engine = PredictiveMaintenanceEngine()

    # Sample truck data (simulating what comes from Wialon)
    test_trucks = [
        {
            "truck_id": "T101",
            "oil_press": 42,
            "cool_temp": 195,
            "oil_temp": 210,
            "pwr_ext": 14.2,
            "def_level": 45,
            "rpm": 1400,
            "engine_load": 65,
            "fuel_rate": 8.5,
        },
        {
            "truck_id": "T102",
            "oil_press": 22,  # Low!
            "cool_temp": 225,  # High!
            "oil_temp": 248,  # High!
            "pwr_ext": 12.8,
            "def_level": 8,  # Low!
            "rpm": 1600,
            "engine_load": 85,
            "fuel_rate": 12.0,
        },
        {
            "truck_id": "T103",
            "oil_press": 55,
            "cool_temp": 188,
            "oil_temp": 195,
            "pwr_ext": 11.8,  # Low!
            "def_level": 72,
            "rpm": 1200,
            "engine_load": 45,
            "fuel_rate": 6.5,
        },
    ]

    # Generate report
    report = engine.generate_fleet_health_report(test_trucks)

    # Print results
    import json

    print(json.dumps(report, indent=2))
