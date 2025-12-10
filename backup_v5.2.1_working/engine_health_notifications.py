"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║              ENGINE HEALTH ALERT NOTIFICATION SERVICE                          ║
║                         Fuel Copilot v3.13.0                                   ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Purpose: Send SMS/Email notifications for critical engine health alerts       ║
║  Integrations: Twilio SMS, Gmail SMTP                                          ║
║                                                                                ║
║  Alert Priority:                                                               ║
║  - CRITICAL: Immediate SMS + Email (engine damage imminent)                    ║
║  - WARNING: Email notification (schedule maintenance)                          ║
║  - WATCH: Daily digest email                                                   ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Try to import Twilio
try:
    from twilio.rest import Client as TwilioClient

    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("⚠️ Twilio not installed - SMS notifications disabled")


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════


class NotificationConfig:
    """Configuration for notification services"""

    # Twilio SMS
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER = os.getenv("TWILIO_FROM_NUMBER", "")
    TWILIO_TO_NUMBERS = os.getenv("TWILIO_TO_NUMBERS", "").split(",")

    # Email SMTP
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASS = os.getenv("SMTP_PASS", "")
    ALERT_EMAIL_TO = os.getenv("ALERT_EMAIL_TO", "").split(",")

    # Notification settings
    SMS_ENABLED = bool(TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN)
    EMAIL_ENABLED = bool(SMTP_USER and SMTP_PASS)

    # Cooldown to prevent notification spam (minutes)
    SMS_COOLDOWN_MINUTES = 30
    EMAIL_COOLDOWN_MINUTES = 15


class AlertPriority(Enum):
    """Alert notification priority levels"""

    IMMEDIATE = "immediate"  # SMS + Email right now
    HIGH = "high"  # Email immediately
    MEDIUM = "medium"  # Email within hour
    LOW = "low"  # Daily digest


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class NotificationResult:
    """Result of a notification attempt"""

    success: bool
    notification_type: str  # "sms", "email"
    recipient: str
    message: str
    error: Optional[str] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "notification_type": self.notification_type,
            "recipient": self.recipient,
            "message": (
                self.message[:100] + "..." if len(self.message) > 100 else self.message
            ),
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ENGINE HEALTH NOTIFICATION SERVICE
# ═══════════════════════════════════════════════════════════════════════════════


class EngineHealthNotificationService:
    """
    Service for sending engine health alert notifications via SMS and Email.

    Features:
    - Immediate SMS for critical alerts
    - Email notifications with HTML formatting
    - Cooldown tracking to prevent spam
    - Notification logging
    """

    def __init__(self):
        self.config = NotificationConfig()
        self._sms_cooldown: Dict[str, datetime] = {}  # truck_id:sensor -> last_sent
        self._email_cooldown: Dict[str, datetime] = {}
        self._twilio_client = None

        # Initialize Twilio if available
        if TWILIO_AVAILABLE and self.config.SMS_ENABLED:
            try:
                self._twilio_client = TwilioClient(
                    self.config.TWILIO_ACCOUNT_SID, self.config.TWILIO_AUTH_TOKEN
                )
                logger.info("✅ Twilio SMS client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Twilio: {e}")

    # ───────────────────────────────────────────────────────────────────────────
    # MAIN NOTIFICATION METHODS
    # ───────────────────────────────────────────────────────────────────────────

    def notify_critical_alert(self, alert: Dict) -> List[NotificationResult]:
        """
        Send immediate notifications for a critical alert.

        Args:
            alert: Alert data dict with truck_id, message, action_required, etc.

        Returns:
            List of NotificationResults
        """
        results = []

        truck_id = alert.get("truck_id", "UNKNOWN")
        sensor = alert.get("sensor_name", "unknown")
        cooldown_key = f"{truck_id}:{sensor}"

        # Check SMS cooldown
        if self._check_cooldown(cooldown_key, "sms"):
            sms_results = self._send_sms_alert(alert)
            results.extend(sms_results)
            self._update_cooldown(cooldown_key, "sms")
        else:
            logger.info(f"SMS cooldown active for {cooldown_key}")

        # Check email cooldown
        if self._check_cooldown(cooldown_key, "email"):
            email_result = self._send_email_alert(alert, priority="critical")
            results.append(email_result)
            self._update_cooldown(cooldown_key, "email")
        else:
            logger.info(f"Email cooldown active for {cooldown_key}")

        # Log notifications
        self._log_notifications(results)

        return results

    def notify_warning_alert(self, alert: Dict) -> NotificationResult:
        """
        Send email notification for a warning alert.

        Args:
            alert: Alert data dict

        Returns:
            NotificationResult
        """
        truck_id = alert.get("truck_id", "UNKNOWN")
        sensor = alert.get("sensor_name", "unknown")
        cooldown_key = f"{truck_id}:{sensor}"

        if self._check_cooldown(cooldown_key, "email"):
            result = self._send_email_alert(alert, priority="warning")
            self._update_cooldown(cooldown_key, "email")
            self._log_notifications([result])
            return result

        return NotificationResult(
            success=False,
            notification_type="email",
            recipient="",
            message="Cooldown active",
            error="Email cooldown period has not expired",
        )

    def send_daily_digest(self, alerts: List[Dict], stats: Dict) -> NotificationResult:
        """
        Send daily digest email with summary of alerts and fleet health.

        Args:
            alerts: List of alerts from the day
            stats: Fleet health statistics

        Returns:
            NotificationResult
        """
        return self._send_digest_email(alerts, stats)

    # ───────────────────────────────────────────────────────────────────────────
    # SMS METHODS
    # ───────────────────────────────────────────────────────────────────────────

    def _send_sms_alert(self, alert: Dict) -> List[NotificationResult]:
        """Send SMS to all configured recipients"""
        results = []

        if not self._twilio_client:
            logger.warning("Twilio client not available")
            return [
                NotificationResult(
                    success=False,
                    notification_type="sms",
                    recipient="",
                    message="",
                    error="Twilio not configured",
                )
            ]

        # Format SMS message (keep it short for SMS)
        message = self._format_sms_message(alert)

        for phone in self.config.TWILIO_TO_NUMBERS:
            phone = phone.strip()
            if not phone:
                continue

            try:
                sms = self._twilio_client.messages.create(
                    body=message, from_=self.config.TWILIO_FROM_NUMBER, to=phone
                )

                results.append(
                    NotificationResult(
                        success=True,
                        notification_type="sms",
                        recipient=phone,
                        message=message,
                    )
                )
                logger.info(f"📱 SMS sent to {phone}: {alert.get('truck_id')}")

            except Exception as e:
                results.append(
                    NotificationResult(
                        success=False,
                        notification_type="sms",
                        recipient=phone,
                        message=message,
                        error=str(e),
                    )
                )
                logger.error(f"Failed to send SMS to {phone}: {e}")

        return results

    def _format_sms_message(self, alert: Dict) -> str:
        """Format alert for SMS (max 160 chars ideal)"""
        severity_emoji = "🔴" if alert.get("severity") == "critical" else "🟡"
        truck = alert.get("truck_id", "?")
        sensor = alert.get("sensor_name", "sensor")
        value = alert.get("current_value", "?")

        # Short message format
        message = f"{severity_emoji} {truck}: {sensor} = {value}\n{alert.get('message', '')[:80]}"

        return message[:160]  # SMS limit

    # ───────────────────────────────────────────────────────────────────────────
    # EMAIL METHODS
    # ───────────────────────────────────────────────────────────────────────────

    def _send_email_alert(
        self, alert: Dict, priority: str = "warning"
    ) -> NotificationResult:
        """Send email alert"""
        if not self.config.EMAIL_ENABLED:
            return NotificationResult(
                success=False,
                notification_type="email",
                recipient="",
                message="",
                error="Email not configured",
            )

        try:
            # Build email
            subject = self._format_email_subject(alert, priority)
            html_body = self._format_email_html(alert, priority)

            recipients = [e.strip() for e in self.config.ALERT_EMAIL_TO if e.strip()]

            if not recipients:
                return NotificationResult(
                    success=False,
                    notification_type="email",
                    recipient="",
                    message="",
                    error="No email recipients configured",
                )

            # Create message
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.SMTP_USER
            msg["To"] = ", ".join(recipients)

            # Add HTML content
            msg.attach(MIMEText(html_body, "html"))

            # Send
            with smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT) as server:
                server.starttls()
                server.login(self.config.SMTP_USER, self.config.SMTP_PASS)
                server.sendmail(self.config.SMTP_USER, recipients, msg.as_string())

            logger.info(f"📧 Email sent: {subject}")

            return NotificationResult(
                success=True,
                notification_type="email",
                recipient=", ".join(recipients),
                message=subject,
            )

        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return NotificationResult(
                success=False,
                notification_type="email",
                recipient=", ".join(self.config.ALERT_EMAIL_TO),
                message="",
                error=str(e),
            )

    def _format_email_subject(self, alert: Dict, priority: str) -> str:
        """Format email subject line"""
        severity = alert.get("severity", "alert").upper()
        truck = alert.get("truck_id", "Unknown")
        sensor = alert.get("sensor_name", "sensor")

        prefix = "🔴 CRITICAL" if priority == "critical" else "🟡 WARNING"

        return f"{prefix} | {truck} - {sensor} | Fuel Copilot Engine Health"

    def _format_email_html(self, alert: Dict, priority: str) -> str:
        """Format alert as HTML email"""

        severity = alert.get("severity", "warning")
        truck = alert.get("truck_id", "Unknown")
        sensor = alert.get("sensor_name", "Unknown Sensor")
        value = alert.get("current_value", "N/A")
        threshold = alert.get("threshold_value", "N/A")
        message = alert.get("message", "")
        action = alert.get("action_required", "Check the vehicle")
        timestamp = alert.get("timestamp", datetime.now(timezone.utc).isoformat())

        # Color based on severity
        colors = {
            "critical": {"bg": "#FEE2E2", "border": "#EF4444", "text": "#991B1B"},
            "warning": {"bg": "#FEF3C7", "border": "#F59E0B", "text": "#92400E"},
            "watch": {"bg": "#DBEAFE", "border": "#3B82F6", "text": "#1E40AF"},
        }
        color = colors.get(severity, colors["warning"])

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .header {{ background: {color['border']}; color: white; padding: 20px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ padding: 24px; }}
        .alert-box {{ background: {color['bg']}; border-left: 4px solid {color['border']}; padding: 16px; margin: 16px 0; border-radius: 4px; }}
        .alert-box h2 {{ color: {color['text']}; margin: 0 0 8px 0; font-size: 18px; }}
        .metric {{ display: flex; justify-content: space-between; padding: 12px 0; border-bottom: 1px solid #eee; }}
        .metric-label {{ color: #666; }}
        .metric-value {{ font-weight: 600; color: #333; }}
        .action-box {{ background: #F0FDF4; border: 1px solid #22C55E; padding: 16px; border-radius: 8px; margin-top: 20px; }}
        .action-box h3 {{ color: #166534; margin: 0 0 8px 0; }}
        .footer {{ background: #f9fafb; padding: 16px; text-align: center; color: #666; font-size: 12px; }}
        .button {{ display: inline-block; background: {color['border']}; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; margin-top: 16px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>⚠️ Engine Health Alert</h1>
        </div>
        
        <div class="content">
            <div class="alert-box">
                <h2>{message}</h2>
            </div>
            
            <div class="metrics">
                <div class="metric">
                    <span class="metric-label">Truck ID</span>
                    <span class="metric-value">{truck}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Sensor</span>
                    <span class="metric-value">{sensor}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Current Value</span>
                    <span class="metric-value" style="color: {color['border']}; font-size: 18px;">{value}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Threshold</span>
                    <span class="metric-value">{threshold}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Severity</span>
                    <span class="metric-value">{severity.upper()}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Time</span>
                    <span class="metric-value">{timestamp}</span>
                </div>
            </div>
            
            <div class="action-box">
                <h3>✅ Required Action</h3>
                <p style="margin: 0; color: #166534;">{action}</p>
            </div>
            
            <center>
                <a href="https://fleetbooster.net/engine-health" class="button">View in Dashboard</a>
            </center>
        </div>
        
        <div class="footer">
            <p>Fuel Copilot Engine Health Monitoring</p>
            <p>This is an automated alert from your fleet management system.</p>
        </div>
    </div>
</body>
</html>
"""
        return html

    def _send_digest_email(self, alerts: List[Dict], stats: Dict) -> NotificationResult:
        """Send daily digest email with summary"""
        if not self.config.EMAIL_ENABLED:
            return NotificationResult(
                success=False,
                notification_type="email",
                recipient="",
                message="",
                error="Email not configured",
            )

        try:
            subject = f"📊 Daily Engine Health Report | {datetime.now().strftime('%Y-%m-%d')} | Fuel Copilot"
            html_body = self._format_digest_html(alerts, stats)

            recipients = [e.strip() for e in self.config.ALERT_EMAIL_TO if e.strip()]

            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.SMTP_USER
            msg["To"] = ", ".join(recipients)
            msg.attach(MIMEText(html_body, "html"))

            with smtplib.SMTP(self.config.SMTP_SERVER, self.config.SMTP_PORT) as server:
                server.starttls()
                server.login(self.config.SMTP_USER, self.config.SMTP_PASS)
                server.sendmail(self.config.SMTP_USER, recipients, msg.as_string())

            logger.info(f"📧 Daily digest sent: {len(alerts)} alerts")

            return NotificationResult(
                success=True,
                notification_type="email",
                recipient=", ".join(recipients),
                message=subject,
            )

        except Exception as e:
            logger.error(f"Failed to send digest email: {e}")
            return NotificationResult(
                success=False,
                notification_type="email",
                recipient="",
                message="",
                error=str(e),
            )

    def _format_digest_html(self, alerts: List[Dict], stats: Dict) -> str:
        """Format daily digest as HTML"""

        critical_count = sum(1 for a in alerts if a.get("severity") == "critical")
        warning_count = sum(1 for a in alerts if a.get("severity") == "warning")

        # Build alert rows
        alert_rows = ""
        for alert in alerts[:20]:  # Limit to 20
            severity = alert.get("severity", "info")
            color = (
                "#EF4444"
                if severity == "critical"
                else "#F59E0B" if severity == "warning" else "#3B82F6"
            )
            alert_rows += f"""
                <tr>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.get('truck_id', '?')}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.get('sensor_name', '?')}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee; color: {color}; font-weight: 600;">{severity.upper()}</td>
                    <td style="padding: 8px; border-bottom: 1px solid #eee;">{alert.get('message', '')[:50]}...</td>
                </tr>
            """

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 700px; margin: 0 auto; background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .header {{ background: linear-gradient(135deg, #3B82F6 0%, #1D4ED8 100%); color: white; padding: 24px; text-align: center; }}
        .content {{ padding: 24px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
        .stat-card {{ background: #f9fafb; padding: 16px; border-radius: 8px; text-align: center; }}
        .stat-value {{ font-size: 28px; font-weight: 700; }}
        .stat-label {{ color: #666; font-size: 12px; margin-top: 4px; }}
        .healthy {{ color: #22C55E; }}
        .warning {{ color: #F59E0B; }}
        .critical {{ color: #EF4444; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th {{ background: #f3f4f6; padding: 12px 8px; text-align: left; font-size: 12px; text-transform: uppercase; color: #666; }}
        .footer {{ background: #f9fafb; padding: 16px; text-align: center; color: #666; font-size: 12px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1 style="margin: 0;">📊 Daily Engine Health Report</h1>
            <p style="margin: 8px 0 0 0; opacity: 0.9;">{datetime.now().strftime('%A, %B %d, %Y')}</p>
        </div>
        
        <div class="content">
            <div class="stats-grid">
                <div class="stat-card">
                    <div class="stat-value healthy">{stats.get('healthy', 0)}</div>
                    <div class="stat-label">Healthy</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value warning">{stats.get('warning', 0)}</div>
                    <div class="stat-label">Warning</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value critical">{stats.get('critical', 0)}</div>
                    <div class="stat-label">Critical</div>
                </div>
                <div class="stat-card">
                    <div class="stat-value" style="color: #666;">{stats.get('offline', 0)}</div>
                    <div class="stat-label">Offline</div>
                </div>
            </div>
            
            <h2 style="margin: 0 0 16px 0; font-size: 18px;">Today's Alerts ({len(alerts)})</h2>
            
            <table>
                <thead>
                    <tr>
                        <th>Truck</th>
                        <th>Sensor</th>
                        <th>Severity</th>
                        <th>Message</th>
                    </tr>
                </thead>
                <tbody>
                    {alert_rows if alert_rows else '<tr><td colspan="4" style="padding: 16px; text-align: center; color: #666;">No alerts today! 🎉</td></tr>'}
                </tbody>
            </table>
        </div>
        
        <div class="footer">
            <p>Fuel Copilot Engine Health Monitoring | <a href="https://fleetbooster.net/engine-health">View Dashboard</a></p>
        </div>
    </div>
</body>
</html>
"""
        return html

    # ───────────────────────────────────────────────────────────────────────────
    # COOLDOWN MANAGEMENT
    # ───────────────────────────────────────────────────────────────────────────

    def _check_cooldown(self, key: str, notification_type: str) -> bool:
        """Check if cooldown period has passed"""
        now = datetime.now(timezone.utc)

        if notification_type == "sms":
            cooldown_dict = self._sms_cooldown
            cooldown_minutes = self.config.SMS_COOLDOWN_MINUTES
        else:
            cooldown_dict = self._email_cooldown
            cooldown_minutes = self.config.EMAIL_COOLDOWN_MINUTES

        last_sent = cooldown_dict.get(key)
        if last_sent is None:
            return True

        elapsed = (now - last_sent).total_seconds() / 60
        return elapsed >= cooldown_minutes

    def _update_cooldown(self, key: str, notification_type: str):
        """Update cooldown timestamp"""
        now = datetime.now(timezone.utc)

        if notification_type == "sms":
            self._sms_cooldown[key] = now
        else:
            self._email_cooldown[key] = now

    def _log_notifications(self, results: List[NotificationResult]):
        """Log notification results to database"""
        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()

            for result in results:
                query = text(
                    """
                    INSERT INTO engine_health_notifications 
                    (alert_id, notification_type, recipient, status, sent_at, error_message, message_content)
                    VALUES (0, :type, :recipient, :status, NOW(), :error, :message)
                """
                )

                with engine.connect() as conn:
                    conn.execute(
                        query,
                        {
                            "type": result.notification_type,
                            "recipient": result.recipient,
                            "status": "sent" if result.success else "failed",
                            "error": result.error,
                            "message": (
                                result.message[:1000] if result.message else None
                            ),
                        },
                    )
                    conn.commit()

        except Exception as e:
            # Don't fail if logging fails
            logger.warning(f"Could not log notification: {e}")


# ═══════════════════════════════════════════════════════════════════════════════
# CONVENIENCE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# Singleton instance
_notification_service: Optional[EngineHealthNotificationService] = None


def get_notification_service() -> EngineHealthNotificationService:
    """Get or create the notification service singleton"""
    global _notification_service
    if _notification_service is None:
        _notification_service = EngineHealthNotificationService()
    return _notification_service


def send_critical_alert(alert: Dict) -> List[NotificationResult]:
    """Convenience function to send critical alert"""
    service = get_notification_service()
    return service.notify_critical_alert(alert)


def send_warning_alert(alert: Dict) -> NotificationResult:
    """Convenience function to send warning alert"""
    service = get_notification_service()
    return service.notify_warning_alert(alert)


def send_daily_digest(alerts: List[Dict], stats: Dict) -> NotificationResult:
    """Convenience function to send daily digest"""
    service = get_notification_service()
    return service.send_daily_digest(alerts, stats)


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 60)
    print("ENGINE HEALTH NOTIFICATION SERVICE TEST")
    print("=" * 60)

    service = EngineHealthNotificationService()

    print(f"\nConfiguration:")
    print(f"  SMS Enabled: {service.config.SMS_ENABLED}")
    print(f"  Email Enabled: {service.config.EMAIL_ENABLED}")
    print(f"  Twilio Available: {TWILIO_AVAILABLE}")

    # Test alert
    test_alert = {
        "truck_id": "FM3679",
        "severity": "critical",
        "sensor_name": "oil_pressure_psi",
        "current_value": 18,
        "threshold_value": 20,
        "message": "CRITICAL: Oil pressure 18 psi is below 20 psi",
        "action_required": "STOP ENGINE IMMEDIATELY - Check oil level and pump",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    print(f"\n📧 Testing email format...")
    html = service._format_email_html(test_alert, "critical")
    print(f"   Generated {len(html)} bytes of HTML")

    print(f"\n📱 Testing SMS format...")
    sms = service._format_sms_message(test_alert)
    print(f"   SMS: {sms}")

    # Uncomment to actually send test notification
    # print(f"\n🚀 Sending test notification...")
    # results = service.notify_critical_alert(test_alert)
    # for r in results:
    #     print(f"   {r.notification_type}: {'✅' if r.success else '❌'} {r.recipient}")
