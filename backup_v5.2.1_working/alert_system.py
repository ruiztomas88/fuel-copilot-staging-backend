"""
Fuel Copilot - Alert System v2.0
Automated alerts for fuel monitoring with PREDICTIVE capabilities

v2.0 Enhancements:
- Predictive maintenance alerts (low MPG trends)
- Fuel theft detection via anomaly patterns
- Driver behavior alerts
- Route efficiency warnings
"""

import os
import smtplib
import logging
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""

    CRITICAL = "CRITICAL"  # Immediate action required
    HIGH = "HIGH"  # Action required soon
    MEDIUM = "MEDIUM"  # Monitor closely
    LOW = "LOW"  # Informational


class AlertCategory(Enum):
    """Alert categories for grouping"""

    FUEL = "FUEL"
    MAINTENANCE = "MAINTENANCE"
    DRIVER = "DRIVER"
    SECURITY = "SECURITY"
    SYSTEM = "SYSTEM"


@dataclass
class Alert:
    """Single alert event"""

    truck_id: str
    alert_type: str
    level: AlertLevel
    message: str
    category: AlertCategory = AlertCategory.FUEL
    value: Optional[float] = None
    timestamp: datetime = None
    recommended_action: str = ""
    estimated_cost_impact: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict:
        """Convert to dictionary for API response"""
        return {
            "truck_id": self.truck_id,
            "alert_type": self.alert_type,
            "level": self.level.value,
            "category": self.category.value,
            "message": self.message,
            "value": self.value,
            "timestamp": self.timestamp.isoformat(),
            "recommended_action": self.recommended_action,
            "estimated_cost_impact": self.estimated_cost_impact,
        }


@dataclass
class TruckMetricsHistory:
    """Track historical metrics for trend analysis"""

    mpg_history: List[Tuple[datetime, float]] = field(default_factory=list)
    idle_history: List[Tuple[datetime, float]] = field(default_factory=list)
    drift_history: List[Tuple[datetime, float]] = field(default_factory=list)
    fuel_drops: List[Tuple[datetime, float, str]] = field(
        default_factory=list
    )  # timestamp, drop_pct, status

    def add_mpg(self, value: float, timestamp: datetime = None):
        ts = timestamp or datetime.now(timezone.utc)
        self.mpg_history.append((ts, value))
        # Keep only last 7 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        self.mpg_history = [(t, v) for t, v in self.mpg_history if t > cutoff]

    def add_idle(self, value: float, timestamp: datetime = None):
        ts = timestamp or datetime.now(timezone.utc)
        self.idle_history.append((ts, value))
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        self.idle_history = [(t, v) for t, v in self.idle_history if t > cutoff]

    def add_drift(self, value: float, timestamp: datetime = None):
        ts = timestamp or datetime.now(timezone.utc)
        self.drift_history.append((ts, value))
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        self.drift_history = [(t, v) for t, v in self.drift_history if t > cutoff]

    def add_fuel_drop(self, drop_pct: float, status: str, timestamp: datetime = None):
        ts = timestamp or datetime.now(timezone.utc)
        self.fuel_drops.append((ts, drop_pct, status))
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        self.fuel_drops = [(t, d, s) for t, d, s in self.fuel_drops if t > cutoff]

    def get_mpg_trend(self) -> Optional[float]:
        """Calculate MPG trend (positive = improving, negative = declining)"""
        if len(self.mpg_history) < 5:
            return None

        recent = [v for _, v in self.mpg_history[-10:]]
        older = [v for _, v in self.mpg_history[:10]]

        if not recent or not older:
            return None

        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)

        if older_avg == 0:
            return None

        return ((recent_avg - older_avg) / older_avg) * 100  # % change

    def get_suspicious_fuel_drops(self) -> List[Tuple[datetime, float]]:
        """Get fuel drops that occurred while truck was STOPPED (potential theft)"""
        return [(t, d) for t, d, s in self.fuel_drops if s == "STOPPED" and d > 5]


class AlertSystem:
    """
    Manages fleet alerts and notifications

    Features:
    - Low fuel warnings
    - High drift detection
    - Offline truck notifications
    - IDLE waste tracking
    - Cooldown to prevent spam
    - 🆕 Predictive maintenance alerts
    - 🆕 Fuel theft anomaly detection
    - 🆕 Driver coaching recommendations
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.alerts_log: List[Alert] = []
        self.last_alert_time: Dict[str, datetime] = {}
        self.truck_history: Dict[str, TruckMetricsHistory] = defaultdict(
            TruckMetricsHistory
        )

        # Alert thresholds (configurable)
        self.FUEL_CRITICAL = self.config.get("fuel_critical_pct", 15)  # 15%
        self.FUEL_WARNING = self.config.get("fuel_warning_pct", 25)  # 25%
        self.DRIFT_HIGH = self.config.get("drift_high_pct", 10)  # 10%
        self.DRIFT_CRITICAL = self.config.get("drift_critical_pct", 15)  # 15%
        self.IDLE_HIGH_GPH = self.config.get("idle_high_gph", 2.5)  # 2.5 gph
        self.IDLE_HIGH_MINUTES = self.config.get("idle_high_minutes", 30)  # 30 min
        self.OFFLINE_HOURS = self.config.get("offline_hours", 4)  # 4 hours

        # 🆕 Predictive thresholds
        self.MPG_DECLINE_THRESHOLD = self.config.get(
            "mpg_decline_pct", -10
        )  # -10% decline
        self.THEFT_PATTERN_THRESHOLD = self.config.get(
            "theft_drops_count", 3
        )  # 3 suspicious drops

        # Cooldown (prevent spam)
        self.COOLDOWN_MINUTES = self.config.get("cooldown_minutes", 30)

        # Email configuration
        self.SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
        self.SMTP_USER = os.getenv("SMTP_USER")
        self.SMTP_PASS = os.getenv("SMTP_PASS")
        self.ALERT_TO = os.getenv("ALERT_TO", "ops@example.com")

        self.email_enabled = bool(self.SMTP_USER and self.SMTP_PASS)

        if not self.email_enabled:
            logger.warning("⚠️  Email alerts DISABLED - SMTP credentials not configured")
            logger.info("💡 Set SMTP_USER and SMTP_PASS in .env to enable email alerts")
        else:
            logger.info(f"✅ Email alerts ENABLED - sending to {self.ALERT_TO}")

    def update_truck_metrics(self, truck: Dict):
        """Update historical metrics for a truck (call this on each data point)"""
        truck_id = truck.get("truck_id")
        if not truck_id:
            return

        history = self.truck_history[truck_id]

        # Record MPG
        mpg = truck.get("mpg_current") or truck.get("mpg")
        if mpg and mpg > 0:
            history.add_mpg(mpg)

        # Record idle
        idle_gph = truck.get("idle_gph") or truck.get("consumption_gph")
        if idle_gph and idle_gph > 0:
            history.add_idle(idle_gph)

        # Record drift
        drift = truck.get("drift_pct")
        if drift is not None:
            history.add_drift(abs(drift))

        # Record fuel drops (for theft detection)
        fuel_change = truck.get("fuel_change_pct")
        status = truck.get("status") or truck.get("truck_status")
        if fuel_change is not None and fuel_change < -2:  # Significant drop
            history.add_fuel_drop(abs(fuel_change), status or "UNKNOWN")

    def check_fleet_alerts(self, truck_data: List[Dict]) -> List[Alert]:
        """
        Check all trucks for alert conditions

        Args:
            truck_data: List of truck dictionaries with current status

        Returns:
            List of Alert objects for triggered conditions
        """
        alerts = []

        for truck in truck_data:
            truck_id = truck.get("truck_id")
            if not truck_id:
                continue

            # Update historical metrics
            self.update_truck_metrics(truck)

            # Check each alert type
            alerts.extend(self._check_low_fuel(truck))
            alerts.extend(self._check_high_drift(truck))
            alerts.extend(self._check_offline(truck))
            alerts.extend(self._check_idle_waste(truck))
            alerts.extend(self._check_sensor_failure(truck))

            # 🆕 Predictive alerts
            alerts.extend(self._check_mpg_decline(truck))
            alerts.extend(self._check_theft_pattern(truck))
            alerts.extend(self._check_driver_behavior(truck))

        # Send alerts (respecting cooldown)
        for alert in alerts:
            self._send_alert(alert)

        # Log to memory
        self.alerts_log.extend(alerts)

        return alerts

    def _check_mpg_decline(self, truck: Dict) -> List[Alert]:
        """Check for MPG decline trend (predictive maintenance)"""
        alerts = []
        truck_id = truck.get("truck_id")
        if not truck_id:
            return alerts

        history = self.truck_history.get(truck_id)
        if not history:
            return alerts

        mpg_trend = history.get_mpg_trend()
        if mpg_trend is not None and mpg_trend < self.MPG_DECLINE_THRESHOLD:
            # Estimate cost impact (10% MPG decline = ~$200/month extra fuel for avg truck)
            cost_impact = abs(mpg_trend) * 20  # $20 per % decline per month

            alerts.append(
                Alert(
                    truck_id=truck_id,
                    alert_type="MPG_DECLINE_TREND",
                    level=AlertLevel.MEDIUM,
                    category=AlertCategory.MAINTENANCE,
                    message=f"MPG declining: {mpg_trend:.1f}% over last 7 days. Check engine, tires, or driving habits.",
                    value=mpg_trend,
                    recommended_action="Schedule preventive maintenance: check tire pressure, air filter, fuel injectors",
                    estimated_cost_impact=cost_impact,
                )
            )

        return alerts

    def _check_theft_pattern(self, truck: Dict) -> List[Alert]:
        """Check for fuel theft pattern (multiple suspicious drops while stopped)"""
        alerts = []
        truck_id = truck.get("truck_id")
        if not truck_id:
            return alerts

        history = self.truck_history.get(truck_id)
        if not history:
            return alerts

        suspicious_drops = history.get_suspicious_fuel_drops()

        # Check drops in last 24 hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        recent_drops = [(t, d) for t, d in suspicious_drops if t > cutoff]

        if len(recent_drops) >= self.THEFT_PATTERN_THRESHOLD:
            total_drop = sum(d for _, d in recent_drops)
            # Estimate stolen fuel: avg 150 gal tank, % drop
            estimated_gallons = (total_drop / 100) * 150
            cost_impact = estimated_gallons * 3.50  # $3.50/gal

            alerts.append(
                Alert(
                    truck_id=truck_id,
                    alert_type="FUEL_THEFT_PATTERN",
                    level=AlertLevel.CRITICAL,
                    category=AlertCategory.SECURITY,
                    message=f"POSSIBLE FUEL THEFT: {len(recent_drops)} unexplained fuel drops ({total_drop:.1f}% total) while truck was stopped in 24h",
                    value=total_drop,
                    recommended_action="1) Review GPS locations during drops 2) Check fuel cap seal 3) Interview driver 4) Consider fuel cap lock",
                    estimated_cost_impact=cost_impact,
                )
            )

        return alerts

    def _check_driver_behavior(self, truck: Dict) -> List[Alert]:
        """Check for driver behavior issues (coaching opportunity)"""
        alerts = []
        truck_id = truck.get("truck_id")
        if not truck_id:
            return alerts

        # Check excessive speeding
        speed = truck.get("speed_mph") or truck.get("speed")
        if speed and speed > 75:
            # Speeding reduces MPG significantly
            mpg_penalty = (speed - 65) * 0.1  # ~0.1 MPG per mph over 65
            monthly_cost = mpg_penalty * 50  # Approx extra cost

            alerts.append(
                Alert(
                    truck_id=truck_id,
                    alert_type="EXCESSIVE_SPEED",
                    level=AlertLevel.LOW,
                    category=AlertCategory.DRIVER,
                    message=f"High speed: {speed:.0f} mph. Fuel efficiency drops ~1% per mph above 65.",
                    value=speed,
                    recommended_action="Coach driver on optimal cruising speed (55-65 mph)",
                    estimated_cost_impact=monthly_cost,
                )
            )

        # Check high RPM (aggressive driving)
        rpm = truck.get("rpm")
        if rpm and rpm > 1800:
            alerts.append(
                Alert(
                    truck_id=truck_id,
                    alert_type="HIGH_RPM",
                    level=AlertLevel.LOW,
                    category=AlertCategory.DRIVER,
                    message=f"High RPM: {rpm}. Consider upshifting earlier for better fuel economy.",
                    value=float(rpm),
                    recommended_action="Coach driver on progressive shifting and maintaining lower RPM",
                    estimated_cost_impact=15.0,  # Approx monthly impact
                )
            )

        return alerts

    def get_fleet_health_summary(self, truck_data: List[Dict]) -> Dict:
        """Generate fleet-wide health summary with predictive insights"""
        summary = {
            "total_trucks": len(truck_data),
            "alerts_24h": len(self.get_recent_alerts(24)),
            "critical_alerts": 0,
            "high_alerts": 0,
            "trucks_with_declining_mpg": 0,
            "trucks_with_theft_risk": 0,
            "estimated_monthly_waste": 0.0,
            "top_issues": [],
        }

        issue_counts: Dict[str, int] = defaultdict(int)

        for truck in truck_data:
            truck_id = truck.get("truck_id")
            if not truck_id:
                continue

            history = self.truck_history.get(truck_id)
            if history:
                mpg_trend = history.get_mpg_trend()
                if mpg_trend and mpg_trend < self.MPG_DECLINE_THRESHOLD:
                    summary["trucks_with_declining_mpg"] += 1
                    issue_counts["Declining MPG"] += 1

                suspicious = history.get_suspicious_fuel_drops()
                if len(suspicious) >= 2:
                    summary["trucks_with_theft_risk"] += 1
                    issue_counts["Theft Risk"] += 1

        # Count alerts by level
        recent_alerts = self.get_recent_alerts(24)
        for alert in recent_alerts:
            if alert.level == AlertLevel.CRITICAL:
                summary["critical_alerts"] += 1
            elif alert.level == AlertLevel.HIGH:
                summary["high_alerts"] += 1

            if alert.estimated_cost_impact:
                summary["estimated_monthly_waste"] += alert.estimated_cost_impact

            issue_counts[alert.alert_type] += 1

        # Top 5 issues
        summary["top_issues"] = sorted(
            [{"issue": k, "count": v} for k, v in issue_counts.items()],
            key=lambda x: x["count"],
            reverse=True,
        )[:5]

        return summary

    def _check_low_fuel(self, truck: Dict) -> List[Alert]:
        """Check for low fuel conditions"""
        alerts = []
        fuel_pct = truck.get("fuel_pct") or truck.get("estimated_pct")
        fuel_gal = truck.get("fuel_gallons") or truck.get("estimated_gallons")

        if fuel_pct is None:
            return alerts

        # CRITICAL: < 15% fuel
        if fuel_pct < self.FUEL_CRITICAL:
            alerts.append(
                Alert(
                    truck_id=truck["truck_id"],
                    alert_type="LOW_FUEL_CRITICAL",
                    level=AlertLevel.CRITICAL,
                    category=AlertCategory.FUEL,
                    message=f"CRITICAL: Only {fuel_pct:.1f}% fuel remaining ({fuel_gal:.1f if fuel_gal else 0} gal)",
                    value=fuel_pct,
                    recommended_action="IMMEDIATE: Refuel truck to prevent breakdown",
                )
            )

        # WARNING: < 25% fuel
        elif fuel_pct < self.FUEL_WARNING:
            alerts.append(
                Alert(
                    truck_id=truck["truck_id"],
                    alert_type="LOW_FUEL_WARNING",
                    level=AlertLevel.HIGH,
                    category=AlertCategory.FUEL,
                    message=f"LOW FUEL: {fuel_pct:.1f}% remaining ({fuel_gal:.1f} gal)",
                    value=fuel_pct,
                )
            )

        return alerts

    def _check_high_drift(self, truck: Dict) -> List[Alert]:
        """Check for high drift (fuel estimation error)"""
        alerts = []
        drift_pct = truck.get("drift_pct")

        if drift_pct is None:
            return alerts

        # CRITICAL: > 15% drift
        if drift_pct > self.DRIFT_CRITICAL:
            alerts.append(
                Alert(
                    truck_id=truck["truck_id"],
                    alert_type="DRIFT_CRITICAL",
                    level=AlertLevel.CRITICAL,
                    message=f"CRITICAL DRIFT: {drift_pct:.1f}% discrepancy (possible fuel theft or sensor malfunction)",
                    value=drift_pct,
                )
            )

        # HIGH: > 10% drift
        elif drift_pct > self.DRIFT_HIGH:
            alerts.append(
                Alert(
                    truck_id=truck["truck_id"],
                    alert_type="DRIFT_HIGH",
                    level=AlertLevel.HIGH,
                    message=f"HIGH DRIFT: {drift_pct:.1f}% discrepancy (investigate sensor or consumption)",
                    value=drift_pct,
                )
            )

        return alerts

    def _check_offline(self, truck: Dict) -> List[Alert]:
        """Check for offline trucks"""
        alerts = []
        data_age_hours = truck.get("data_age_hours")
        status = truck.get("status")

        if status == "OFFLINE" and data_age_hours is not None:
            if data_age_hours > self.OFFLINE_HOURS:
                alerts.append(
                    Alert(
                        truck_id=truck["truck_id"],
                        alert_type="TRUCK_OFFLINE",
                        level=AlertLevel.MEDIUM,
                        message=f"OFFLINE: No data for {data_age_hours:.1f} hours",
                        value=data_age_hours,
                    )
                )

        return alerts

    def _check_idle_waste(self, truck: Dict) -> List[Alert]:
        """Check for excessive IDLE consumption"""
        alerts = []
        status = truck.get("status")
        idle_gph = truck.get("idle_gph")
        idle_duration_min = truck.get("idle_duration_min")

        if status != "STOPPED" or idle_gph is None or idle_duration_min is None:
            return alerts

        # HIGH IDLE + LONG DURATION
        if idle_gph > self.IDLE_HIGH_GPH and idle_duration_min > self.IDLE_HIGH_MINUTES:
            gallons_wasted = (idle_gph * idle_duration_min) / 60.0
            cost_wasted = gallons_wasted * 4.0  # $4/gal average

            alerts.append(
                Alert(
                    truck_id=truck["truck_id"],
                    alert_type="IDLE_WASTE",
                    level=AlertLevel.MEDIUM,
                    message=f"HIGH IDLE: {idle_gph:.2f} gph for {idle_duration_min:.0f} min (${cost_wasted:.2f} wasted)",
                    value=idle_gph,
                )
            )

        return alerts

    def _check_sensor_failure(self, truck: Dict) -> List[Alert]:
        """Check for sensor failure (repeated auto-resyncs)"""
        alerts = []
        auto_resync_count = truck.get("auto_resync_count_1h", 0)

        # CRITICAL: 3+ auto-resyncs in 1 hour (sensor malfunction or fuel theft)
        if auto_resync_count >= 3:
            alerts.append(
                Alert(
                    truck_id=truck["truck_id"],
                    alert_type="SENSOR_FAILURE_SUSPECTED",
                    level=AlertLevel.CRITICAL,
                    message=f"SENSOR FAILURE: {auto_resync_count} auto-corrections in 1 hour (check sensor or investigate theft)",
                    value=float(auto_resync_count),
                )
            )

        return alerts

    def _should_send_alert(self, truck_id: str, alert_type: str) -> bool:
        """Check if alert should be sent (cooldown)"""
        key = f"{truck_id}:{alert_type}"
        last_time = self.last_alert_time.get(key)

        if last_time is None:
            return True

        elapsed_min = (datetime.now(timezone.utc) - last_time).total_seconds() / 60.0
        return elapsed_min >= self.COOLDOWN_MINUTES

    def _send_alert(self, alert: Alert):
        """Send alert via email (if enabled)"""
        # Check cooldown
        if not self._should_send_alert(alert.truck_id, alert.alert_type):
            logger.debug(
                f"⏳ Alert cooldown active for {alert.truck_id}:{alert.alert_type}"
            )
            return

        # Update last alert time
        key = f"{alert.truck_id}:{alert.alert_type}"
        self.last_alert_time[key] = datetime.now(timezone.utc)

        # Log alert
        logger.warning(
            f"🚨 ALERT [{alert.level.value}] {alert.truck_id}: {alert.message}"
        )

        # Send email if enabled
        if self.email_enabled:
            self._send_email(alert)
        else:
            logger.info(f"📧 Email not configured - alert logged only")

    def _send_email(self, alert: Alert):
        """Send alert via email"""
        try:
            msg = EmailMessage()
            msg["From"] = self.SMTP_USER
            msg["To"] = self.ALERT_TO
            msg["Subject"] = self._get_email_subject(alert)

            # Email body
            body = f"""
Fuel Copilot Alert
==================

Truck:    {alert.truck_id}
Level:    {alert.level.value}
Type:     {alert.alert_type}
Time:     {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Message:
{alert.message}

{self._get_action_items(alert)}

---
This is an automated alert from Fuel Copilot.
Dashboard: http://localhost:5001/truck/{alert.truck_id}
"""

            msg.set_content(body)

            # Send
            with smtplib.SMTP(self.SMTP_SERVER, self.SMTP_PORT, timeout=10) as server:
                server.starttls()
                server.login(self.SMTP_USER, self.SMTP_PASS)
                server.send_message(msg)

            logger.info(f"📧 Alert email sent to {self.ALERT_TO}")

        except Exception as e:
            logger.error(f"❌ Failed to send alert email: {e}")

    def _get_email_subject(self, alert: Alert) -> str:
        """Generate email subject line"""
        emoji = {
            AlertLevel.CRITICAL: "🔴",
            AlertLevel.HIGH: "🟠",
            AlertLevel.MEDIUM: "🟡",
            AlertLevel.LOW: "🔵",
        }.get(alert.level, "⚪")

        return f"{emoji} [{alert.level.value}] {alert.truck_id} - {alert.alert_type}"

    def _get_action_items(self, alert: Alert) -> str:
        """Generate recommended actions"""
        actions = {
            "LOW_FUEL_CRITICAL": "⚡ IMMEDIATE ACTION: Refuel truck or risk breakdown",
            "LOW_FUEL_WARNING": "⚠️  ACTION REQUIRED: Schedule refuel soon",
            "DRIFT_CRITICAL": "🔍 INVESTIGATE: Check for fuel theft or sensor malfunction",
            "DRIFT_HIGH": "🔍 MONITOR: Review fuel consumption and sensor readings",
            "TRUCK_OFFLINE": "📡 CHECK: Verify GPS device and truck status",
            "IDLE_WASTE": "💰 OPTIMIZE: Coach driver on reducing idle time",
            "SENSOR_FAILURE_SUSPECTED": "🔧 URGENT: Inspect fuel sensor - repeated drift corrections indicate hardware failure or active fuel theft",
        }

        action = actions.get(alert.alert_type, "")
        if action:
            return f"\nRecommended Action:\n{action}"
        return ""

    def get_recent_alerts(self, hours: int = 24) -> List[Alert]:
        """Get alerts from last N hours"""
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        return [a for a in self.alerts_log if a.timestamp >= cutoff]

    def get_alerts_by_truck(self, truck_id: str, hours: int = 24) -> List[Alert]:
        """Get alerts for specific truck"""
        recent = self.get_recent_alerts(hours)
        return [a for a in recent if a.truck_id == truck_id]

    def export_alerts_csv(self, filepath: str, hours: int = 24):
        """Export alerts to CSV file"""
        import csv

        alerts = self.get_recent_alerts(hours)

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(
                ["Timestamp", "Truck ID", "Alert Type", "Level", "Message", "Value"]
            )

            for alert in alerts:
                writer.writerow(
                    [
                        alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                        alert.truck_id,
                        alert.alert_type,
                        alert.level.value,
                        alert.message,
                        alert.value if alert.value is not None else "",
                    ]
                )

        logger.info(f"📄 Exported {len(alerts)} alerts to {filepath}")
