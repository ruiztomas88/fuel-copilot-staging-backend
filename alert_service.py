"""
Alert Service - Multi-channel notifications for Fuel Copilot

Supports:
- SMS via Twilio
- WhatsApp via Twilio
- Email via SMTP
- Webhook for custom integrations

Author: Fuel Copilot Team
Version: v3.4.1
Date: November 25, 2025

Setup:
1. Get Twilio credentials: https://www.twilio.com/console
2. Add to .env:
   TWILIO_ACCOUNT_SID=your_sid
   TWILIO_AUTH_TOKEN=your_token
   TWILIO_FROM_NUMBER=+1234567890
   TWILIO_TO_NUMBERS=+1234567890,+0987654321

3. For Email alerts:
   SMTP_SERVER=smtp-mail.outlook.com
   SMTP_PORT=587
   SMTP_USER=your_email@domain.com
   SMTP_PASS=your_password
   ALERT_EMAIL_TO=recipient@domain.com

⏰ TIMEZONE:
- Uses timezone_utils for consistent UTC handling
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from dotenv import load_dotenv

from timezone_utils import utc_now

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)


class AlertPriority(Enum):
    """Alert priority levels"""

    LOW = "low"  # Informational
    MEDIUM = "medium"  # Needs attention soon
    HIGH = "high"  # Needs attention now
    CRITICAL = "critical"  # Emergency - possible theft


class AlertType(Enum):
    """Types of alerts"""

    REFUEL = "refuel"
    THEFT_SUSPECTED = "theft_suspected"
    DRIFT_WARNING = "drift_warning"
    SENSOR_OFFLINE = "sensor_offline"
    LOW_FUEL = "low_fuel"
    EFFICIENCY_DROP = "efficiency_drop"
    MAINTENANCE_DUE = "maintenance_due"


@dataclass
class Alert:
    """Alert data structure"""

    alert_type: AlertType
    priority: AlertPriority
    truck_id: str
    message: str
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = utc_now()


@dataclass
class TwilioConfig:
    """Twilio configuration from environment"""

    account_sid: str = None
    auth_token: str = None
    from_number: str = None
    to_numbers: List[str] = None
    whatsapp_from: str = None

    def __post_init__(self):
        self.account_sid = os.getenv("TWILIO_ACCOUNT_SID", "")
        self.auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
        self.from_number = os.getenv("TWILIO_FROM_NUMBER", "")
        to_numbers_str = os.getenv("TWILIO_TO_NUMBERS", "")
        self.to_numbers = [n.strip() for n in to_numbers_str.split(",") if n.strip()]
        self.whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM", "")

    def is_configured(self) -> bool:
        """Check if Twilio is properly configured"""
        return bool(self.account_sid and self.auth_token and self.from_number)


class TwilioAlertService:
    """Send alerts via Twilio SMS and WhatsApp"""

    def __init__(self, config: TwilioConfig = None):
        self.config = config or TwilioConfig()
        self._client = None
        self._initialized = False

    def _initialize_client(self):
        """Lazy initialization of Twilio client"""
        if self._initialized:
            return self._client is not None

        if not self.config.is_configured():
            logger.warning("⚠️ Twilio not configured. SMS alerts disabled.")
            logger.info(
                "   Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_FROM_NUMBER in .env"
            )
            self._initialized = True
            return False

        try:
            from twilio.rest import Client

            self._client = Client(self.config.account_sid, self.config.auth_token)
            logger.info("✅ Twilio client initialized successfully")
            self._initialized = True
            return True
        except ImportError:
            logger.warning("⚠️ Twilio library not installed. Run: pip install twilio")
            self._initialized = True
            return False
        except Exception as e:
            logger.error(f"❌ Failed to initialize Twilio: {e}")
            self._initialized = True
            return False

    def send_sms(self, to_number: str, message: str) -> bool:
        """
        Send SMS to a specific number

        Args:
            to_number: Recipient phone number (E.164 format: +1234567890)
            message: Message content (max 1600 chars for concatenated SMS)

        Returns:
            True if sent successfully
        """
        if not self._initialize_client():
            return False

        try:
            # Truncate message if too long
            if len(message) > 1600:
                message = message[:1597] + "..."

            result = self._client.messages.create(
                body=message, from_=self.config.from_number, to=to_number
            )
            logger.info(f"📱 SMS sent to {to_number}: {result.sid}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send SMS to {to_number}: {e}")
            return False

    def send_whatsapp(self, to_number: str, message: str) -> bool:
        """
        Send WhatsApp message

        Args:
            to_number: Recipient phone number (E.164 format)
            message: Message content

        Returns:
            True if sent successfully
        """
        if not self._initialize_client():
            return False

        if not self.config.whatsapp_from:
            logger.warning("WhatsApp not configured (TWILIO_WHATSAPP_FROM missing)")
            return False

        try:
            result = self._client.messages.create(
                body=message,
                from_=f"whatsapp:{self.config.whatsapp_from}",
                to=f"whatsapp:{to_number}",
            )
            logger.info(f"📲 WhatsApp sent to {to_number}: {result.sid}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to send WhatsApp to {to_number}: {e}")
            return False

    def broadcast_sms(self, message: str, numbers: List[str] = None) -> Dict[str, bool]:
        """
        Send SMS to multiple numbers

        Args:
            message: Message content
            numbers: List of phone numbers (uses config.to_numbers if None)

        Returns:
            Dict mapping number to success status
        """
        numbers = numbers or self.config.to_numbers
        if not numbers:
            logger.warning("No recipient numbers configured")
            return {}

        results = {}
        for number in numbers:
            results[number] = self.send_sms(number, message)

        success_count = sum(results.values())
        logger.info(f"📱 Broadcast complete: {success_count}/{len(numbers)} sent")
        return results


@dataclass
class EmailConfig:
    """Email/SMTP configuration from environment"""

    smtp_server: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    to_email: str = ""

    def __post_init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp-mail.outlook.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_user = os.getenv("SMTP_USER", "")
        self.smtp_pass = os.getenv("SMTP_PASS", "")
        self.to_email = os.getenv("ALERT_EMAIL_TO", "")

    def is_configured(self) -> bool:
        """Check if email is properly configured"""
        return bool(
            self.smtp_server and self.smtp_user and self.smtp_pass and self.to_email
        )


class EmailAlertService:
    """Send alerts via Email/SMTP"""

    def __init__(self, config: EmailConfig = None):
        self.config = config or EmailConfig()
        self._initialized = False

    def send_email(self, subject: str, body: str, html_body: str = None) -> bool:
        """
        Send email alert

        Args:
            subject: Email subject
            body: Plain text body
            html_body: Optional HTML body

        Returns:
            True if sent successfully
        """
        if not self.config.is_configured():
            logger.warning("⚠️ Email not configured. Email alerts disabled.")
            logger.info(
                "   Set SMTP_SERVER, SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO in .env"
            )
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = self.config.smtp_user
            msg["To"] = self.config.to_email

            # Add plain text
            msg.attach(MIMEText(body, "plain"))

            # Add HTML if provided
            if html_body:
                msg.attach(MIMEText(html_body, "html"))

            # Connect and send
            with smtplib.SMTP(self.config.smtp_server, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_pass)
                server.send_message(msg)

            logger.info(f"📧 Email sent to {self.config.to_email}: {subject}")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to send email: {e}")
            return False

    def format_alert_email(self, alert) -> tuple:
        """
        Format alert as email subject and body

        Returns:
            Tuple of (subject, plain_body, html_body)
        """
        type_labels = {
            AlertType.REFUEL: "⛽ Refuel Detected",
            AlertType.THEFT_SUSPECTED: "🚨 FUEL THEFT SUSPECTED",
            AlertType.LOW_FUEL: "🔋 Low Fuel Warning",
            AlertType.SENSOR_OFFLINE: "📵 Sensor Offline",
            AlertType.DRIFT_WARNING: "📉 Drift Warning",
        }

        subject = f"[Fuel Copilot] {type_labels.get(alert.alert_type, 'Alert')} - {alert.truck_id}"

        # Plain text body
        plain_body = f"""
FUEL COPILOT ALERT
==================

Truck: {alert.truck_id}
Type: {alert.alert_type.value.upper()}
Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

{alert.message}
"""
        if alert.details:
            plain_body += "\nDetails:\n"
            for key, value in alert.details.items():
                plain_body += f"  • {key}: {value}\n"

        # HTML body
        priority_colors = {
            AlertPriority.LOW: "#17a2b8",
            AlertPriority.MEDIUM: "#ffc107",
            AlertPriority.HIGH: "#fd7e14",
            AlertPriority.CRITICAL: "#dc3545",
        }
        color = priority_colors.get(alert.priority, "#6c757d")

        details_html = ""
        if alert.details:
            details_html = "<ul>"
            for key, value in alert.details.items():
                details_html += f"<li><strong>{key}:</strong> {value}</li>"
            details_html += "</ul>"

        html_body = f"""
<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
        .container {{ max-width: 600px; margin: 0 auto; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .header {{ background: {color}; color: white; padding: 20px; text-align: center; }}
        .header h1 {{ margin: 0; font-size: 24px; }}
        .content {{ padding: 20px; }}
        .truck-id {{ font-size: 28px; font-weight: bold; color: #333; margin-bottom: 10px; }}
        .timestamp {{ color: #666; font-size: 14px; margin-bottom: 20px; }}
        .message {{ background: #f8f9fa; padding: 15px; border-radius: 4px; margin-bottom: 15px; }}
        .details {{ margin-top: 15px; }}
        .footer {{ background: #f8f9fa; padding: 15px; text-align: center; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚛 FUEL COPILOT ALERT</h1>
        </div>
        <div class="content">
            <div class="truck-id">Truck: {alert.truck_id}</div>
            <div class="timestamp">🕐 {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</div>
            <div class="message">{alert.message}</div>
            <div class="details">
                {details_html}
            </div>
        </div>
        <div class="footer">
            Fuel Copilot v3.4.1 | Automated Fleet Monitoring
        </div>
    </div>
</body>
</html>
"""
        return subject, plain_body, html_body


class AlertManager:
    """Central manager for all alert channels"""

    def __init__(self):
        self.twilio = TwilioAlertService()
        self.email = EmailAlertService()  # 🆕 Email service
        self._alert_history: List[Alert] = []
        self._max_history = 1000

        # Rate limiting: prevent spam
        self._last_alert_by_truck: Dict[str, datetime] = {}
        self._min_alert_interval_seconds = 300  # 5 minutes between alerts per truck

    def _format_alert_message(self, alert: Alert) -> str:
        """Format alert for SMS/WhatsApp"""
        priority_emoji = {
            AlertPriority.LOW: "ℹ️",
            AlertPriority.MEDIUM: "⚠️",
            AlertPriority.HIGH: "🚨",
            AlertPriority.CRITICAL: "🆘",
        }

        type_emoji = {
            AlertType.REFUEL: "⛽",
            AlertType.THEFT_SUSPECTED: "🚨",
            AlertType.DRIFT_WARNING: "📉",
            AlertType.SENSOR_OFFLINE: "📵",
            AlertType.LOW_FUEL: "🔋",
            AlertType.EFFICIENCY_DROP: "📊",
            AlertType.MAINTENANCE_DUE: "🔧",
        }

        emoji = f"{priority_emoji.get(alert.priority, '📢')} {type_emoji.get(alert.alert_type, '📢')}"
        timestamp = alert.timestamp.strftime("%H:%M")

        msg = f"{emoji} FUEL COPILOT\n"
        msg += f"🚛 Truck: {alert.truck_id}\n"
        msg += f"⏰ {timestamp}\n"
        msg += f"\n{alert.message}"

        if alert.details:
            msg += "\n\nDetails:"
            for key, value in alert.details.items():
                msg += f"\n• {key}: {value}"

        return msg

    def _should_send_alert(self, alert: Alert) -> bool:
        """Check rate limiting and filters"""
        # Critical alerts always go through
        if alert.priority == AlertPriority.CRITICAL:
            return True

        # Check rate limit per truck
        last_alert = self._last_alert_by_truck.get(alert.truck_id)
        if last_alert:
            elapsed = (utc_now() - last_alert).total_seconds()
            if elapsed < self._min_alert_interval_seconds:
                logger.debug(
                    f"Rate limited: {alert.truck_id} (last alert {elapsed:.0f}s ago)"
                )
                return False

        return True

    def send_alert(self, alert: Alert, channels: List[str] = None) -> bool:
        """
        Send alert through configured channels

        Args:
            alert: Alert to send
            channels: List of channels ("sms", "whatsapp", "email"). Uses all if None.

        Returns:
            True if at least one channel succeeded
        """
        # Add to history
        self._alert_history.append(alert)
        if len(self._alert_history) > self._max_history:
            self._alert_history.pop(0)

        # Rate limiting
        if not self._should_send_alert(alert):
            return False

        # Update last alert time
        self._last_alert_by_truck[alert.truck_id] = utc_now()

        # Default channels based on priority
        if channels is None:
            if alert.priority == AlertPriority.CRITICAL:
                channels = ["sms", "whatsapp", "email"]
            elif alert.priority == AlertPriority.HIGH:
                channels = ["sms", "email"]
            else:
                channels = []  # Low/medium alerts don't send by default

        if not channels:
            logger.info(
                f"Alert logged (no channels): {alert.truck_id} - {alert.alert_type.value}"
            )
            return True

        message = self._format_alert_message(alert)
        success = False

        if "sms" in channels:
            results = self.twilio.broadcast_sms(message)
            if any(results.values()):
                success = True

        if "whatsapp" in channels:
            for number in self.twilio.config.to_numbers:
                if self.twilio.send_whatsapp(number, message):
                    success = True

        # 🆕 Email channel
        if "email" in channels:
            subject, plain_body, html_body = self.email.format_alert_email(alert)
            if self.email.send_email(subject, plain_body, html_body):
                success = True

        return success

    # Convenience methods for common alerts

    def alert_theft_suspected(
        self,
        truck_id: str,
        fuel_drop_gallons: float,
        fuel_drop_pct: float,
        location: str = None,
    ) -> bool:
        """Send theft suspected alert (CRITICAL priority) - SMS + Email"""
        alert = Alert(
            alert_type=AlertType.THEFT_SUSPECTED,
            priority=AlertPriority.CRITICAL,
            truck_id=truck_id,
            message=f"⚠️ POSSIBLE FUEL THEFT DETECTED!\n"
            f"Fuel drop: {fuel_drop_gallons:.1f} gal ({fuel_drop_pct:.1f}%)",
            details={
                "fuel_drop_gallons": f"{fuel_drop_gallons:.1f}",
                "fuel_drop_pct": f"{fuel_drop_pct:.1f}%",
                "location": location or "Unknown",
            },
        )
        return self.send_alert(alert, channels=["sms", "email"])  # 🆕 Added email

    def alert_refuel(
        self,
        truck_id: str,
        gallons_added: float,
        new_level_pct: float,
        location: str = None,
        send_sms: bool = True,
    ) -> bool:
        """
        Send refuel notification - SMS + Email

        Args:
            truck_id: Truck identifier
            gallons_added: Amount of fuel added
            new_level_pct: New fuel level percentage
            location: Optional location string
            send_sms: Whether to send SMS (default True)
        """
        alert = Alert(
            alert_type=AlertType.REFUEL,
            priority=AlertPriority.LOW,
            truck_id=truck_id,
            message=f"⛽ Refuel detected: +{gallons_added:.1f} gallons\n"
            f"New level: {new_level_pct:.1f}%",
            details={
                "gallons_added": f"{gallons_added:.1f}",
                "new_level": f"{new_level_pct:.1f}%",
                "location": location or "Unknown",
            },
        )
        channels = ["sms", "email"] if send_sms else ["email"]  # 🆕 Always send email
        return self.send_alert(alert, channels=channels)

    def alert_low_fuel(
        self,
        truck_id: str,
        current_level_pct: float,
        estimated_miles_remaining: float = None,
    ) -> bool:
        """Send low fuel alert (logged only, no SMS per user request)"""
        alert = Alert(
            alert_type=AlertType.LOW_FUEL,
            priority=AlertPriority.MEDIUM,  # Changed from HIGH to avoid SMS
            truck_id=truck_id,
            message=f"Low fuel warning: {current_level_pct:.1f}%",
            details={
                "current_level": f"{current_level_pct:.1f}%",
                "estimated_miles": (
                    f"{estimated_miles_remaining:.0f}"
                    if estimated_miles_remaining
                    else "N/A"
                ),
            },
        )
        return self.send_alert(alert, channels=[])  # Log only, no SMS

    def alert_sensor_offline(self, truck_id: str, offline_minutes: int) -> bool:
        """Send sensor offline alert (MEDIUM priority)"""
        alert = Alert(
            alert_type=AlertType.SENSOR_OFFLINE,
            priority=AlertPriority.MEDIUM,
            truck_id=truck_id,
            message=f"Sensor offline for {offline_minutes} minutes",
            details={"offline_minutes": str(offline_minutes)},
        )
        return self.send_alert(alert, channels=[])  # Log only

    def get_alert_history(
        self, truck_id: str = None, alert_type: AlertType = None, limit: int = 100
    ) -> List[Alert]:
        """Get recent alerts, optionally filtered"""
        alerts = self._alert_history

        if truck_id:
            alerts = [a for a in alerts if a.truck_id == truck_id]

        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]

        return alerts[-limit:]


# Global instance for easy access
_alert_manager: AlertManager = None


def get_alert_manager() -> AlertManager:
    """Get global AlertManager instance"""
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager()
    return _alert_manager


# Convenience functions
def send_theft_alert(
    truck_id: str, fuel_drop_gallons: float, fuel_drop_pct: float, location: str = None
) -> bool:
    """Quick function to send theft alert"""
    return get_alert_manager().alert_theft_suspected(
        truck_id, fuel_drop_gallons, fuel_drop_pct, location
    )


def send_low_fuel_alert(
    truck_id: str, current_level_pct: float, estimated_miles: float = None
) -> bool:
    """Quick function to send low fuel alert"""
    return get_alert_manager().alert_low_fuel(
        truck_id, current_level_pct, estimated_miles
    )


if __name__ == "__main__":
    # Test the alert service
    logging.basicConfig(level=logging.INFO)

    print("🧪 Testing Alert Service")
    print("=" * 50)

    manager = get_alert_manager()

    # Check configuration
    print(f"\nTwilio configured: {manager.twilio.config.is_configured()}")
    print(
        f"Account SID: {manager.twilio.config.account_sid[:10]}..."
        if manager.twilio.config.account_sid
        else "Not set"
    )
    print(f"From number: {manager.twilio.config.from_number or 'Not set'}")
    print(f"To numbers: {manager.twilio.config.to_numbers or 'Not set'}")

    # Test alert (won't actually send if not configured)
    print("\n📱 Testing theft alert...")
    result = manager.alert_theft_suspected(
        truck_id="TEST123",
        fuel_drop_gallons=50.5,
        fuel_drop_pct=15.2,
        location="Houston, TX",
    )
    print(f"Alert sent: {result}")

    # Show history
    print(f"\n📋 Alert history: {len(manager._alert_history)} alerts")
