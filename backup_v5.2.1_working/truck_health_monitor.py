"""
Truck Health Monitor - Statistical Analysis for Predictive Maintenance
Version 1.0

Uses Shewhart/Nelson rules to detect sensor anomalies and predict maintenance needs.

📊 STATISTICAL METHODS:
1. Normal Distribution Analysis (μ ± σ)
2. Shewhart Control Charts (3σ rule)
3. Nelson Rules for drift detection
4. Shapiro-Wilk test for normality validation

🎯 MONITORED SENSORS:
- Oil Temperature (°F) - Engine health indicator
- Coolant Temperature (°F) - Cooling system health
- Battery Voltage (V) - Electrical system health
- Oil Pressure (PSI) - Lubrication system health

⚠️ ALERT THRESHOLDS:
- Green: < 1σ from mean (normal operation)
- Yellow: 1-2σ from mean (monitor closely)
- Red: > 2σ from mean (investigate)
- Critical: > 3σ from mean (immediate action)

🔍 NELSON RULES IMPLEMENTED:
- Rule 1: Point > 3σ from mean (outlier)
- Rule 2: 9+ consecutive points on same side of mean (shift)
- Rule 5: 2 of 3 consecutive points > 2σ from mean (trend)
- Rule 7: 15+ consecutive points within 1σ of mean (stratification - possible stuck sensor)
"""

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Sequence, Union
import statistics
import json
from pathlib import Path

# Optional imports - graceful degradation
try:
    import numpy as np
    from scipy import stats

    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    np = None
    stats = None

logger = logging.getLogger(__name__)


# =============================================================================
# Enums and Data Classes
# =============================================================================


class SensorType(Enum):
    """Types of sensors monitored for health analysis"""

    OIL_TEMP = "oil_temp"
    COOLANT_TEMP = "coolant_temp"
    BATTERY_VOLTAGE = "battery_voltage"
    OIL_PRESSURE = "oil_pressure"


class AlertSeverity(Enum):
    """Severity levels for health alerts"""

    NORMAL = "NORMAL"  # Green: < 1σ
    WATCH = "WATCH"  # Yellow: 1-2σ
    WARNING = "WARNING"  # Orange: 2-3σ
    CRITICAL = "CRITICAL"  # Red: > 3σ


class NelsonRule(Enum):
    """Nelson Rules for statistical process control"""

    RULE_1_OUTLIER = "Rule 1: Point > 3σ (outlier)"
    RULE_2_SHIFT = "Rule 2: 9+ points same side of mean (shift)"
    RULE_5_TREND = "Rule 5: 2 of 3 points > 2σ (trend)"
    RULE_7_STRATIFICATION = "Rule 7: 15+ points within 1σ (stuck sensor)"


@dataclass
class SensorStats:
    """Statistical summary for a sensor"""

    sensor_type: SensorType
    truck_id: str
    window_name: str  # "day", "week", "month"

    # Basic statistics
    mean: float
    std: float
    min_val: float
    max_val: float
    sample_count: int

    # Current value analysis
    current_value: Optional[float] = None
    z_score: Optional[float] = None  # How many σ from mean

    # Normality test
    is_normal: bool = True
    shapiro_p_value: Optional[float] = None

    # Nelson rules violations
    nelson_violations: List[NelsonRule] = field(default_factory=list)

    # Timestamps
    window_start: Optional[datetime] = None
    window_end: Optional[datetime] = None
    calculated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def severity(self) -> AlertSeverity:
        """Calculate severity based on z-score"""
        if self.z_score is None:
            return AlertSeverity.NORMAL

        abs_z = abs(self.z_score)

        if abs_z >= 3.0:
            return AlertSeverity.CRITICAL
        elif abs_z >= 2.0:
            return AlertSeverity.WARNING
        elif abs_z >= 1.0:
            return AlertSeverity.WATCH
        else:
            return AlertSeverity.NORMAL

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/API"""
        return {
            "sensor_type": self.sensor_type.value,
            "truck_id": self.truck_id,
            "window": self.window_name,
            "mean": round(self.mean, 2),
            "std": round(self.std, 2),
            "min": round(self.min_val, 2),
            "max": round(self.max_val, 2),
            "sample_count": self.sample_count,
            "current_value": (
                round(self.current_value, 2) if self.current_value else None
            ),
            "z_score": round(self.z_score, 2) if self.z_score else None,
            "severity": self.severity.value,
            "is_normal_distribution": self.is_normal,
            "shapiro_p_value": (
                round(self.shapiro_p_value, 4) if self.shapiro_p_value else None
            ),
            "nelson_violations": [v.value for v in self.nelson_violations],
            "calculated_at": (
                self.calculated_at.isoformat() if self.calculated_at else None
            ),
        }


@dataclass
class TruckHealthReport:
    """Complete health report for a truck"""

    truck_id: str
    timestamp: datetime

    # Sensor stats by type and window
    sensor_stats: Dict[str, Dict[str, SensorStats]] = field(default_factory=dict)
    # Structure: {sensor_type: {window: SensorStats}}

    # Overall health score (0-100)
    health_score: float = 100.0

    # Active alerts
    alerts: List[str] = field(default_factory=list)

    # Recommendations
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/API"""
        return {
            "truck_id": self.truck_id,
            "timestamp": self.timestamp.isoformat(),
            "health_score": round(self.health_score, 1),
            "sensors": {
                sensor_type: {
                    window: stats.to_dict() for window, stats in windows.items()
                }
                for sensor_type, windows in self.sensor_stats.items()
            },
            "alerts": self.alerts,
            "recommendations": self.recommendations,
        }


@dataclass
class HealthAlert:
    """Health monitoring alert"""

    truck_id: str
    sensor_type: SensorType
    severity: AlertSeverity
    message: str
    z_score: float
    current_value: float
    expected_range: Tuple[float, float]  # (lower, upper) based on 2σ
    nelson_violations: List[NelsonRule]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON/API"""
        return {
            "truck_id": self.truck_id,
            "sensor_type": self.sensor_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "z_score": round(self.z_score, 2),
            "current_value": round(self.current_value, 2),
            "expected_range": [round(v, 2) for v in self.expected_range],
            "nelson_violations": [v.value for v in self.nelson_violations],
            "timestamp": self.timestamp.isoformat(),
        }


# =============================================================================
# Sensor Configuration
# =============================================================================

# Expected ranges for sensors (for sanity checks)
SENSOR_RANGES = {
    SensorType.OIL_TEMP: {
        "min": 100,
        "max": 300,
        "unit": "°F",
        "name": "Oil Temperature",
    },
    SensorType.COOLANT_TEMP: {
        "min": 100,
        "max": 250,
        "unit": "°F",
        "name": "Coolant Temperature",
    },
    SensorType.BATTERY_VOLTAGE: {
        "min": 10.0,
        "max": 15.0,
        "unit": "V",
        "name": "Battery Voltage",
    },
    SensorType.OIL_PRESSURE: {
        "min": 10,
        "max": 100,
        "unit": "PSI",
        "name": "Oil Pressure",
    },
}

# Mapping from TruckSensorData field names to SensorType
SENSOR_FIELD_MAPPING = {
    # "oil_temp": SensorType.OIL_TEMP,  # Not currently in TruckSensorData
    "coolant_temp": SensorType.COOLANT_TEMP,
    "pwr_ext": SensorType.BATTERY_VOLTAGE,  # External power = battery
    "oil_press": SensorType.OIL_PRESSURE,
}


# =============================================================================
# Statistical Analysis Functions
# =============================================================================


def calculate_z_score(value: float, mean: float, std: float) -> Optional[float]:
    """Calculate z-score (number of standard deviations from mean)"""
    if std == 0 or std is None:
        return None
    return (value - mean) / std


def shapiro_wilk_test(
    data: Sequence[Union[int, float]], alpha: float = 0.05
) -> Tuple[bool, Optional[float]]:
    """
    Perform Shapiro-Wilk test for normality.

    Args:
        data: List of values to test
        alpha: Significance level (default 0.05)

    Returns:
        Tuple of (is_normal, p_value)
        is_normal = True if p_value > alpha (cannot reject normality)
    """
    if not SCIPY_AVAILABLE:
        logger.debug("scipy not available, skipping Shapiro-Wilk test")
        return True, None  # Assume normal if can't test

    if len(data) < 3:
        return True, None  # Need at least 3 samples

    if len(data) > 5000:
        # Shapiro-Wilk works best with n < 5000
        # Use sample if too large
        import random

        data = random.sample(data, 5000)

    try:
        stat, p_value = stats.shapiro(data)
        is_normal = p_value > alpha
        return is_normal, p_value
    except Exception as e:
        logger.warning(f"Shapiro-Wilk test failed: {e}")
        return True, None


# =============================================================================
# Nelson Rules Implementation
# =============================================================================


class NelsonRulesChecker:
    """
    Implements Nelson Rules for statistical process control.

    These rules help detect non-random patterns in sensor data
    that may indicate developing problems.
    """

    @staticmethod
    def check_all_rules(
        values: Sequence[Union[int, float]], mean: float, std: float
    ) -> List[NelsonRule]:
        """
        Check all implemented Nelson rules against the data.

        Args:
            values: Recent sensor readings (chronological order)
            mean: Historical mean
            std: Historical standard deviation

        Returns:
            List of violated rules
        """
        violations = []

        if std == 0 or len(values) == 0:
            return violations

        # Rule 1: Any point > 3σ from mean
        if NelsonRulesChecker.check_rule_1(values, mean, std):
            violations.append(NelsonRule.RULE_1_OUTLIER)

        # Rule 2: 9+ consecutive points on same side of mean
        if NelsonRulesChecker.check_rule_2(values, mean):
            violations.append(NelsonRule.RULE_2_SHIFT)

        # Rule 5: 2 of 3 consecutive points > 2σ from mean
        if NelsonRulesChecker.check_rule_5(values, mean, std):
            violations.append(NelsonRule.RULE_5_TREND)

        # Rule 7: 15+ consecutive points within 1σ (stratification)
        if NelsonRulesChecker.check_rule_7(values, mean, std):
            violations.append(NelsonRule.RULE_7_STRATIFICATION)

        return violations

    @staticmethod
    def check_rule_1(
        values: Sequence[Union[int, float]], mean: float, std: float
    ) -> bool:
        """
        Rule 1: One point is more than 3 standard deviations from the mean.

        Indicates: Outlier, possible measurement error or sudden change
        """
        if not values:
            return False

        # Check the most recent value
        latest = values[-1]
        z_score = abs(calculate_z_score(latest, mean, std) or 0)
        return z_score > 3.0

    @staticmethod
    def check_rule_2(values: Sequence[Union[int, float]], mean: float) -> bool:
        """
        Rule 2: Nine (or more) points in a row are on the same side of the mean.

        Indicates: Process shift, sensor drift
        """
        if len(values) < 9:
            return False

        # Check last 9 points
        last_9 = values[-9:]
        above_count = sum(1 for v in last_9 if v > mean)
        below_count = 9 - above_count

        return above_count == 9 or below_count == 9

    @staticmethod
    def check_rule_5(
        values: Sequence[Union[int, float]], mean: float, std: float
    ) -> bool:
        """
        Rule 5: Two of three consecutive points > 2σ from mean (same side).

        Indicates: Trend developing, possible impending failure
        """
        if len(values) < 3:
            return False

        # Check last 3 points
        last_3 = values[-3:]
        z_scores = [calculate_z_score(v, mean, std) or 0 for v in last_3]

        # Check if 2+ points are > 2σ on the same side
        above_2sigma = sum(1 for z in z_scores if z > 2.0)
        below_2sigma = sum(1 for z in z_scores if z < -2.0)

        return above_2sigma >= 2 or below_2sigma >= 2

    @staticmethod
    def check_rule_7(
        values: Sequence[Union[int, float]], mean: float, std: float
    ) -> bool:
        """
        Rule 7: Fifteen consecutive points within 1σ of the mean.

        Indicates: Stratification (reduced variation) - possible stuck sensor
        This is important for detecting sensors that are "frozen" at a value
        """
        if len(values) < 15:
            return False

        # Check last 15 points
        last_15 = values[-15:]
        z_scores = [abs(calculate_z_score(v, mean, std) or 0) for v in last_15]

        # All points should be within 1σ
        return all(z < 1.0 for z in z_scores)


# =============================================================================
# Main Truck Health Monitor Class
# =============================================================================


class TruckHealthMonitor:
    """
    Monitors truck sensor health using statistical analysis.

    Features:
    - Normal distribution validation (Shapiro-Wilk)
    - Shewhart control charts (μ ± 3σ)
    - Nelson rules for pattern detection
    - Multi-window analysis (day/week/month)
    - Predictive maintenance alerts
    """

    # Analysis windows in hours
    WINDOWS = {
        "day": 24,
        "week": 24 * 7,
        "month": 24 * 30,
    }

    def __init__(self, data_dir: str = "data/health_stats"):
        """
        Initialize health monitor.

        Args:
            data_dir: Directory to store historical statistics
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache of recent sensor values by truck
        # Structure: {truck_id: {sensor_type: [(timestamp, value), ...]}}
        self._sensor_cache: Dict[str, Dict[str, List[Tuple[datetime, float]]]] = {}

        # Historical stats loaded from disk
        # Structure: {truck_id: {sensor_type: {window: SensorStats}}}
        self._historical_stats: Dict[str, Dict[str, Dict[str, SensorStats]]] = {}

        # Alert history
        self._alert_history: List[HealthAlert] = []

        logger.info(
            f"🏥 TruckHealthMonitor initialized (scipy available: {SCIPY_AVAILABLE})"
        )

    def record_sensor_data(
        self,
        truck_id: str,
        timestamp: datetime,
        coolant_temp: Optional[float] = None,
        battery_voltage: Optional[float] = None,
        oil_pressure: Optional[float] = None,
        oil_temp: Optional[float] = None,
    ) -> List[HealthAlert]:
        """
        Record new sensor data and check for anomalies.

        Args:
            truck_id: Truck identifier
            timestamp: When the reading was taken
            coolant_temp: Coolant temperature in °F
            battery_voltage: Battery/external power voltage
            oil_pressure: Oil pressure in PSI
            oil_temp: Oil temperature in °F (if available)

        Returns:
            List of triggered health alerts
        """
        alerts = []

        # Ensure timestamp is timezone-aware
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        # Initialize cache for truck if needed
        if truck_id not in self._sensor_cache:
            self._sensor_cache[truck_id] = {}

        # Process each sensor
        sensor_values = {
            SensorType.COOLANT_TEMP: coolant_temp,
            SensorType.BATTERY_VOLTAGE: battery_voltage,
            SensorType.OIL_PRESSURE: oil_pressure,
            SensorType.OIL_TEMP: oil_temp,
        }

        for sensor_type, value in sensor_values.items():
            if value is None:
                continue

            # Validate value is within reasonable range
            sensor_range = SENSOR_RANGES.get(sensor_type, {})
            min_val = sensor_range.get("min", float("-inf"))
            max_val = sensor_range.get("max", float("inf"))

            if not (min_val <= value <= max_val):
                logger.warning(
                    f"[{truck_id}] {sensor_type.value} value {value} outside expected range "
                    f"[{min_val}, {max_val}] - skipping"
                )
                continue

            # Record to cache
            sensor_key = sensor_type.value
            if sensor_key not in self._sensor_cache[truck_id]:
                self._sensor_cache[truck_id][sensor_key] = []

            self._sensor_cache[truck_id][sensor_key].append((timestamp, value))

            # Keep only last 30 days of data in memory
            cutoff = datetime.now(timezone.utc) - timedelta(days=30)
            self._sensor_cache[truck_id][sensor_key] = [
                (ts, v)
                for ts, v in self._sensor_cache[truck_id][sensor_key]
                if ts > cutoff
            ]

            # Check for anomalies
            alert = self._check_sensor_anomaly(truck_id, sensor_type, value, timestamp)
            if alert:
                alerts.append(alert)
                self._alert_history.append(alert)

        return alerts

    def _check_sensor_anomaly(
        self,
        truck_id: str,
        sensor_type: SensorType,
        current_value: float,
        timestamp: datetime,
    ) -> Optional[HealthAlert]:
        """
        Check if current sensor value is anomalous.

        Uses historical statistics to calculate z-score and check Nelson rules.
        """
        sensor_key = sensor_type.value

        # Get historical data for this truck/sensor
        if truck_id not in self._sensor_cache:
            return None

        if sensor_key not in self._sensor_cache[truck_id]:
            return None

        history = self._sensor_cache[truck_id][sensor_key]

        # Need at least 20 samples for meaningful statistics
        if len(history) < 20:
            return None

        # Calculate statistics from last week
        week_ago = datetime.now(timezone.utc) - timedelta(days=7)
        week_data = [v for ts, v in history if ts > week_ago]

        if len(week_data) < 10:
            # Fall back to all available data
            week_data = [v for _, v in history]

        if len(week_data) < 10:
            return None

        # Calculate mean and std
        mean = statistics.mean(week_data)
        std = statistics.stdev(week_data) if len(week_data) > 1 else 0

        if std == 0:
            # No variation - might be stuck sensor
            if len(week_data) >= 15:
                sensor_config = SENSOR_RANGES.get(sensor_type, {})
                sensor_name = sensor_config.get("name", sensor_type.value)
                unit = sensor_config.get("unit", "")

                return HealthAlert(
                    truck_id=truck_id,
                    sensor_type=sensor_type,
                    severity=AlertSeverity.WARNING,
                    message=f"{sensor_name} shows NO variation (stuck at {current_value:.1f}{unit}). "
                    f"Possible sensor malfunction.",
                    z_score=0.0,
                    current_value=current_value,
                    expected_range=(mean, mean),
                    nelson_violations=[NelsonRule.RULE_7_STRATIFICATION],
                    timestamp=timestamp,
                )
            return None

        # Calculate z-score
        z_score = calculate_z_score(current_value, mean, std)
        if z_score is None:
            return None

        # Check Nelson rules
        recent_values = [v for _, v in history[-20:]]  # Last 20 readings
        nelson_violations = NelsonRulesChecker.check_all_rules(recent_values, mean, std)

        # Determine severity
        abs_z = abs(z_score)
        if abs_z < 2.0 and not nelson_violations:
            # Normal operation
            return None

        # Calculate expected range (2σ)
        expected_range = (mean - 2 * std, mean + 2 * std)

        # Generate alert
        sensor_config = SENSOR_RANGES.get(sensor_type, {})
        sensor_name = sensor_config.get("name", sensor_type.value)
        unit = sensor_config.get("unit", "")

        if abs_z >= 3.0:
            severity = AlertSeverity.CRITICAL
            direction = "HIGH" if z_score > 0 else "LOW"
            message = (
                f"CRITICAL: {sensor_name} is {direction} at {current_value:.1f}{unit} "
                f"({abs_z:.1f}σ from normal). Immediate inspection recommended."
            )
        elif abs_z >= 2.0:
            severity = AlertSeverity.WARNING
            direction = "elevated" if z_score > 0 else "low"
            message = (
                f"WARNING: {sensor_name} is {direction} at {current_value:.1f}{unit} "
                f"({abs_z:.1f}σ from normal). Monitor closely."
            )
        else:
            # Only Nelson rule violations without high z-score
            severity = AlertSeverity.WATCH
            violations_str = ", ".join(v.value for v in nelson_violations)
            message = (
                f"PATTERN DETECTED: {sensor_name} at {current_value:.1f}{unit}. "
                f"Statistical anomaly: {violations_str}"
            )

        return HealthAlert(
            truck_id=truck_id,
            sensor_type=sensor_type,
            severity=severity,
            message=message,
            z_score=z_score,
            current_value=current_value,
            expected_range=expected_range,
            nelson_violations=nelson_violations,
            timestamp=timestamp,
        )

    def get_truck_health_report(self, truck_id: str) -> Optional[TruckHealthReport]:
        """
        Generate comprehensive health report for a truck.

        Analyzes all sensors across multiple time windows.
        """
        if truck_id not in self._sensor_cache:
            return None

        timestamp = datetime.now(timezone.utc)
        report = TruckHealthReport(
            truck_id=truck_id,
            timestamp=timestamp,
        )

        health_deductions = 0  # Points to deduct from 100

        for sensor_key, data in self._sensor_cache[truck_id].items():
            if not data:
                continue

            try:
                sensor_type = SensorType(sensor_key)
            except ValueError:
                continue

            sensor_stats_by_window = {}

            for window_name, hours in self.WINDOWS.items():
                cutoff = timestamp - timedelta(hours=hours)
                window_data = [v for ts, v in data if ts > cutoff]

                if len(window_data) < 5:
                    continue

                # Calculate statistics
                mean = statistics.mean(window_data)
                std = statistics.stdev(window_data) if len(window_data) > 1 else 0
                min_val = min(window_data)
                max_val = max(window_data)

                # Current value (latest)
                current_value = data[-1][1] if data else None
                z_score = (
                    calculate_z_score(current_value, mean, std)
                    if current_value
                    else None
                )

                # Normality test
                is_normal, p_value = shapiro_wilk_test(window_data)

                # Nelson rules
                recent_values = [v for _, v in data[-20:]]
                nelson_violations = NelsonRulesChecker.check_all_rules(
                    recent_values, mean, std
                )

                # 🆕 Special detection: std=0 with sufficient samples = stuck sensor
                # This is important because Nelson Rule 7 can't detect stuck sensors
                # when std=0 (all z-scores would be undefined/0)
                if std == 0 and len(window_data) >= 15:
                    if NelsonRule.RULE_7_STRATIFICATION not in nelson_violations:
                        nelson_violations.append(NelsonRule.RULE_7_STRATIFICATION)

                stats_obj = SensorStats(
                    sensor_type=sensor_type,
                    truck_id=truck_id,
                    window_name=window_name,
                    mean=mean,
                    std=std,
                    min_val=min_val,
                    max_val=max_val,
                    sample_count=len(window_data),
                    current_value=current_value,
                    z_score=z_score,
                    is_normal=is_normal,
                    shapiro_p_value=p_value,
                    nelson_violations=nelson_violations,
                    window_start=cutoff,
                    window_end=timestamp,
                )

                sensor_stats_by_window[window_name] = stats_obj

                # Health score deductions (use week window for scoring)
                if window_name == "week":
                    severity = stats_obj.severity
                    if severity == AlertSeverity.CRITICAL:
                        health_deductions += 30
                        report.alerts.append(
                            f"CRITICAL: {sensor_type.value} at {abs(z_score or 0):.1f}σ"
                        )
                    elif severity == AlertSeverity.WARNING:
                        health_deductions += 15
                        report.alerts.append(
                            f"WARNING: {sensor_type.value} at {abs(z_score or 0):.1f}σ"
                        )
                    elif severity == AlertSeverity.WATCH:
                        health_deductions += 5

                    # Additional deductions for Nelson violations
                    for violation in nelson_violations:
                        if violation == NelsonRule.RULE_7_STRATIFICATION:
                            health_deductions += 20
                            report.alerts.append(
                                f"STUCK SENSOR: {sensor_type.value} shows no variation"
                            )
                        elif violation == NelsonRule.RULE_2_SHIFT:
                            health_deductions += 10
                            report.alerts.append(
                                f"DRIFT: {sensor_type.value} trending consistently"
                            )

            if sensor_stats_by_window:
                report.sensor_stats[sensor_key] = sensor_stats_by_window

        # Calculate final health score
        report.health_score = max(0, 100 - health_deductions)

        # Generate recommendations
        report.recommendations = self._generate_recommendations(report)

        return report

    def _generate_recommendations(self, report: TruckHealthReport) -> List[str]:
        """Generate maintenance recommendations based on health report"""
        recommendations = []

        for sensor_key, windows in report.sensor_stats.items():
            week_stats = windows.get("week")
            if not week_stats:
                continue

            sensor_config = SENSOR_RANGES.get(week_stats.sensor_type, {})
            sensor_name = sensor_config.get("name", sensor_key)

            if week_stats.severity == AlertSeverity.CRITICAL:
                recommendations.append(
                    f"🔴 URGENT: Schedule immediate inspection for {sensor_name}"
                )
            elif week_stats.severity == AlertSeverity.WARNING:
                recommendations.append(
                    f"🟠 Schedule {sensor_name} inspection within 48 hours"
                )

            for violation in week_stats.nelson_violations:
                if violation == NelsonRule.RULE_7_STRATIFICATION:
                    recommendations.append(
                        f"🔧 {sensor_name} sensor may be malfunctioning (no variation)"
                    )
                elif violation == NelsonRule.RULE_2_SHIFT:
                    recommendations.append(
                        f"📈 {sensor_name} showing consistent drift - monitor trend"
                    )

        if not recommendations and report.health_score >= 90:
            recommendations.append("✅ All sensors operating within normal parameters")

        return recommendations

    def get_fleet_health_summary(self) -> Dict[str, Any]:
        """
        Get health summary for entire fleet.

        Returns aggregated statistics and alerts.
        """
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "total_trucks": len(self._sensor_cache),
            "trucks_with_alerts": 0,
            "critical_count": 0,
            "warning_count": 0,
            "watch_count": 0,
            "healthy_count": 0,
            "truck_scores": {},
            "recent_alerts": [],
        }

        for truck_id in self._sensor_cache:
            report = self.get_truck_health_report(truck_id)
            if report:
                summary["truck_scores"][truck_id] = report.health_score

                if report.alerts:
                    summary["trucks_with_alerts"] += 1

                    # Count by severity
                    for sensor_stats in report.sensor_stats.values():
                        for stats in sensor_stats.values():
                            if stats.severity == AlertSeverity.CRITICAL:
                                summary["critical_count"] += 1
                            elif stats.severity == AlertSeverity.WARNING:
                                summary["warning_count"] += 1
                            elif stats.severity == AlertSeverity.WATCH:
                                summary["watch_count"] += 1
                else:
                    summary["healthy_count"] += 1

        # Add recent alerts (last 24 hours)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent = [
            alert.to_dict() for alert in self._alert_history if alert.timestamp > cutoff
        ]
        summary["recent_alerts"] = sorted(
            recent, key=lambda x: x["timestamp"], reverse=True
        )[
            :50
        ]  # Max 50 alerts

        return summary

    def get_alerts_for_truck(self, truck_id: str, hours: int = 24) -> List[HealthAlert]:
        """Get recent alerts for a specific truck"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [
            alert
            for alert in self._alert_history
            if alert.truck_id == truck_id and alert.timestamp > cutoff
        ]

    def save_state(self, filepath: Optional[str] = None):
        """Save current state to disk"""
        save_path: Path
        if filepath is None:
            save_path = self.data_dir / "health_monitor_state.json"
        else:
            save_path = Path(filepath)

        state = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "sensor_cache": {
                truck_id: {
                    sensor: [(ts.isoformat(), v) for ts, v in values]
                    for sensor, values in sensors.items()
                }
                for truck_id, sensors in self._sensor_cache.items()
            },
            "alert_history": [alert.to_dict() for alert in self._alert_history[-1000:]],
        }

        with open(save_path, "w") as f:
            json.dump(state, f, indent=2)

        logger.info(f"💾 Health monitor state saved to {save_path}")

    def load_state(self, filepath: Optional[str] = None):
        """Load state from disk"""
        load_path: Path
        if filepath is None:
            load_path = self.data_dir / "health_monitor_state.json"
        else:
            load_path = Path(filepath)

        if not load_path.exists():
            logger.info(f"No saved state found at {load_path}")
            return

        try:
            with open(load_path) as f:
                state = json.load(f)

            # Restore sensor cache
            for truck_id, sensors in state.get("sensor_cache", {}).items():
                self._sensor_cache[truck_id] = {}
                for sensor, values in sensors.items():
                    self._sensor_cache[truck_id][sensor] = [
                        (datetime.fromisoformat(ts), v) for ts, v in values
                    ]

            logger.info(
                f"📂 Health monitor state loaded: " f"{len(self._sensor_cache)} trucks"
            )

        except Exception as e:
            logger.error(f"Failed to load health monitor state: {e}")


# =============================================================================
# Integration with WialonReader
# =============================================================================


def integrate_with_truck_data(
    health_monitor: TruckHealthMonitor,
    truck_sensor_data: Any,  # TruckSensorData from wialon_reader
) -> List[HealthAlert]:
    """
    Helper function to integrate TruckHealthMonitor with WialonReader data.

    Args:
        health_monitor: TruckHealthMonitor instance
        truck_sensor_data: TruckSensorData from wialon_reader

    Returns:
        List of health alerts (if any)
    """
    return health_monitor.record_sensor_data(
        truck_id=truck_sensor_data.truck_id,
        timestamp=truck_sensor_data.timestamp,
        coolant_temp=truck_sensor_data.coolant_temp,
        battery_voltage=truck_sensor_data.pwr_ext,  # pwr_ext is battery voltage
        oil_pressure=truck_sensor_data.oil_press,
        # oil_temp not currently available in TruckSensorData
    )


# =============================================================================
# Standalone Testing
# =============================================================================

if __name__ == "__main__":
    import random

    # Configure logging for standalone run
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    print("=" * 70)
    print("TRUCK HEALTH MONITOR - TEST")
    print("=" * 70)

    # Create monitor
    monitor = TruckHealthMonitor(data_dir="data/test_health_stats")

    # Simulate sensor data for a truck
    truck_id = "TEST_TRUCK"
    base_time = datetime.now(timezone.utc) - timedelta(days=7)

    # Generate normal data for a week
    print("\n📊 Generating simulated sensor data for 7 days...")
    for i in range(7 * 24 * 4):  # 15-min intervals for 7 days
        ts = base_time + timedelta(minutes=15 * i)

        # Normal operation with some variation
        coolant = 190 + random.gauss(0, 8)  # Mean 190°F, std 8
        battery = 12.5 + random.gauss(0, 0.3)  # Mean 12.5V, std 0.3
        oil_press = 45 + random.gauss(0, 5)  # Mean 45 PSI, std 5

        monitor.record_sensor_data(
            truck_id=truck_id,
            timestamp=ts,
            coolant_temp=coolant,
            battery_voltage=battery,
            oil_pressure=oil_press,
        )

    # Now inject an anomaly
    print("\n⚠️  Injecting anomaly: High coolant temperature")
    alerts = monitor.record_sensor_data(
        truck_id=truck_id,
        timestamp=datetime.now(timezone.utc),
        coolant_temp=240,  # Abnormally high!
        battery_voltage=12.4,
        oil_pressure=44,
    )

    if alerts:
        print(f"\n🚨 ALERTS TRIGGERED: {len(alerts)}")
        for alert in alerts:
            print(f"   [{alert.severity.value}] {alert.message}")

    # Generate health report
    print("\n📋 HEALTH REPORT:")
    report = monitor.get_truck_health_report(truck_id)
    if report:
        print(f"   Truck: {report.truck_id}")
        print(f"   Health Score: {report.health_score}/100")
        print(f"   Alerts: {len(report.alerts)}")
        for alert in report.alerts:
            print(f"      - {alert}")
        print(f"   Recommendations: {len(report.recommendations)}")
        for rec in report.recommendations:
            print(f"      - {rec}")

    # Test stuck sensor detection
    print("\n🔧 Testing stuck sensor detection (Rule 7)...")
    stuck_truck = "STUCK_SENSOR_TRUCK"
    for i in range(50):
        ts = base_time + timedelta(minutes=15 * i)
        monitor.record_sensor_data(
            truck_id=stuck_truck,
            timestamp=ts,
            coolant_temp=185.0,  # Exactly the same every time
            battery_voltage=12.5,
            oil_pressure=45,
        )

    alerts = monitor.record_sensor_data(
        truck_id=stuck_truck,
        timestamp=datetime.now(timezone.utc),
        coolant_temp=185.0,
        battery_voltage=12.5,
        oil_pressure=45,
    )

    report = monitor.get_truck_health_report(stuck_truck)
    if report:
        print(f"   Health Score: {report.health_score}/100")
        for alert in report.alerts:
            print(f"   ⚠️  {alert}")

    # Fleet summary
    print("\n📊 FLEET SUMMARY:")
    summary = monitor.get_fleet_health_summary()
    print(f"   Total Trucks: {summary['total_trucks']}")
    print(f"   Trucks with Alerts: {summary['trucks_with_alerts']}")
    print(f"   Critical: {summary['critical_count']}")
    print(f"   Warning: {summary['warning_count']}")

    print("\n✅ Test complete!")
