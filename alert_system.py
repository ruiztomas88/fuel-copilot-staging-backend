"""
Fuel Copilot - Alert System v1.0
Automated alerts for fuel monitoring
"""

import os
import smtplib
import logging
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class AlertLevel(Enum):
    """Alert severity levels"""

    CRITICAL = "CRITICAL"  # Immediate action required
    HIGH = "HIGH"  # Action required soon
    MEDIUM = "MEDIUM"  # Monitor closely
    LOW = "LOW"  # Informational


@dataclass
class Alert:
    """Single alert event"""

    truck_id: str
    alert_type: str
    level: AlertLevel
    message: str
    value: Optional[float] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


class AlertSystem:
    """
    Manages fleet alerts and notifications

    Features:
    - Low fuel warnings
    - High drift detection
    - Offline truck notifications
    - IDLE waste tracking
    - Cooldown to prevent spam
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        self.alerts_log = []
        self.last_alert_time: Dict[str, datetime] = {}

        # Alert thresholds (configurable)
        self.FUEL_CRITICAL = self.config.get("fuel_critical_pct", 15)  # 15%
        self.FUEL_WARNING = self.config.get("fuel_warning_pct", 25)  # 25%
        self.DRIFT_HIGH = self.config.get("drift_high_pct", 10)  # 10%
        self.DRIFT_CRITICAL = self.config.get("drift_critical_pct", 15)  # 15%
        self.IDLE_HIGH_GPH = self.config.get("idle_high_gph", 2.5)  # 2.5 gph
        self.IDLE_HIGH_MINUTES = self.config.get("idle_high_minutes", 30)  # 30 min
        self.OFFLINE_HOURS = self.config.get("offline_hours", 4)  # 4 hours

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

            # Check each alert type
            alerts.extend(self._check_low_fuel(truck))
            alerts.extend(self._check_high_drift(truck))
            alerts.extend(self._check_offline(truck))
            alerts.extend(self._check_idle_waste(truck))
            alerts.extend(self._check_sensor_failure(truck))  # 🆕 Sensor health check

        # Send alerts (respecting cooldown)
        for alert in alerts:
            self._send_alert(alert)

        # Log to memory
        self.alerts_log.extend(alerts)

        return alerts

    def _check_low_fuel(self, truck: Dict) -> List[Alert]:
        """Check for low fuel conditions"""
        alerts = []
        fuel_pct = truck.get("fuel_pct")
        fuel_gal = truck.get("fuel_gallons")

        if fuel_pct is None:
            return alerts

        # CRITICAL: < 15% fuel
        if fuel_pct < self.FUEL_CRITICAL:
            alerts.append(
                Alert(
                    truck_id=truck["truck_id"],
                    alert_type="LOW_FUEL_CRITICAL",
                    level=AlertLevel.CRITICAL,
                    message=f"CRITICAL: Only {fuel_pct:.1f}% fuel remaining ({fuel_gal:.1f} gal)",
                    value=fuel_pct,
                )
            )

        # WARNING: < 25% fuel
        elif fuel_pct < self.FUEL_WARNING:
            alerts.append(
                Alert(
                    truck_id=truck["truck_id"],
                    alert_type="LOW_FUEL_WARNING",
                    level=AlertLevel.HIGH,
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
