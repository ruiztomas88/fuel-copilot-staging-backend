"""
Tests for Alert Service (v3.12.21)
Phase 5: Additional test coverage

Tests the actual classes and functions in alert_service.py
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock


class TestAlertDataClasses:
    """Test Alert data structures"""

    def test_alert_type_enum(self):
        """Should have all expected alert types"""
        from alert_service import AlertType

        assert AlertType.REFUEL.value == "refuel"
        assert AlertType.THEFT_SUSPECTED.value == "theft_suspected"
        assert AlertType.DRIFT_WARNING.value == "drift_warning"
        assert AlertType.SENSOR_OFFLINE.value == "sensor_offline"
        assert AlertType.LOW_FUEL.value == "low_fuel"
        assert AlertType.EFFICIENCY_DROP.value == "efficiency_drop"

    def test_alert_priority_enum(self):
        """Should have all expected priority levels"""
        from alert_service import AlertPriority

        assert AlertPriority.LOW.value == "low"
        assert AlertPriority.MEDIUM.value == "medium"
        assert AlertPriority.HIGH.value == "high"
        assert AlertPriority.CRITICAL.value == "critical"

    def test_alert_creation(self):
        """Should create Alert with all required fields"""
        from alert_service import Alert, AlertType, AlertPriority

        alert = Alert(
            alert_type=AlertType.REFUEL,
            priority=AlertPriority.LOW,
            truck_id="TRUCK001",
            message="Refuel detected: 50 gallons",
        )

        assert alert.alert_type == AlertType.REFUEL
        assert alert.priority == AlertPriority.LOW
        assert alert.truck_id == "TRUCK001"
        assert "50 gallons" in alert.message
        assert alert.timestamp is not None

    def test_alert_auto_timestamp(self):
        """Should auto-generate timestamp if not provided"""
        from alert_service import Alert, AlertType, AlertPriority

        before = datetime.now(timezone.utc)
        alert = Alert(
            alert_type=AlertType.THEFT_SUSPECTED,
            priority=AlertPriority.CRITICAL,
            truck_id="TRUCK002",
            message="Fuel theft suspected!",
        )
        after = datetime.now(timezone.utc)

        assert alert.timestamp is not None
        assert before <= alert.timestamp <= after

    def test_alert_with_details(self):
        """Should accept optional details dict"""
        from alert_service import Alert, AlertType, AlertPriority

        details = {
            "fuel_before": 100,
            "fuel_after": 40,
            "drop_gallons": 60,
            "location": {"lat": 40.7128, "lng": -74.0060},
        }

        alert = Alert(
            alert_type=AlertType.THEFT_SUSPECTED,
            priority=AlertPriority.CRITICAL,
            truck_id="TRUCK003",
            message="60 gallons missing!",
            details=details,
        )

        assert alert.details == details
        assert alert.details["drop_gallons"] == 60


class TestTwilioConfig:
    """Test Twilio configuration"""

    def test_twilio_config_defaults(self):
        """Should load from environment or use empty defaults"""
        from alert_service import TwilioConfig

        config = TwilioConfig()

        # These should exist as attributes
        assert hasattr(config, "account_sid")
        assert hasattr(config, "auth_token")
        assert hasattr(config, "from_number")
        assert hasattr(config, "to_numbers")

    def test_twilio_is_configured_empty(self):
        """Should report not configured when missing credentials"""
        from alert_service import TwilioConfig

        # Create config with empty values
        with patch.dict(
            "os.environ",
            {"TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "TWILIO_FROM_NUMBER": ""},
        ):
            config = TwilioConfig()
            # Force re-initialization
            config.account_sid = ""
            config.auth_token = ""
            config.from_number = ""

            assert config.is_configured() is False


class TestEmailConfig:
    """Test Email configuration"""

    def test_email_config_defaults(self):
        """Should have default SMTP settings"""
        from alert_service import EmailConfig

        config = EmailConfig()

        assert hasattr(config, "smtp_server")
        assert hasattr(config, "smtp_port")
        assert hasattr(config, "smtp_user")
        assert hasattr(config, "smtp_pass")
        assert config.smtp_port == 587  # Default SMTP port


class TestTwilioAlertService:
    """Test Twilio alert service"""

    def test_service_initialization(self):
        """Should initialize without errors"""
        from alert_service import TwilioAlertService, TwilioConfig

        config = TwilioConfig()
        service = TwilioAlertService(config)

        assert service is not None
        assert service.config == config

    def test_send_sms_without_config(self):
        """Should return False if not configured"""
        from alert_service import TwilioAlertService, TwilioConfig

        # Create unconfigured service
        config = TwilioConfig()
        config.account_sid = ""
        config.auth_token = ""
        config.from_number = ""

        service = TwilioAlertService(config)
        result = service.send_sms("+1234567890", "Test message")

        assert result is False


class TestEmailAlertService:
    """Test Email alert service"""

    def test_email_service_initialization(self):
        """Should initialize without errors"""
        from alert_service import EmailAlertService, EmailConfig

        config = EmailConfig()
        service = EmailAlertService(config)

        assert service is not None
        assert service.config == config


class TestAlertFormatting:
    """Test alert message formatting"""

    def test_format_alert_sms(self):
        """Alert should be formattable for SMS"""
        from alert_service import Alert, AlertType, AlertPriority

        alert = Alert(
            alert_type=AlertType.REFUEL,
            priority=AlertPriority.LOW,
            truck_id="ABC123",
            message="Refuel: 50 gal at Pilot #1234",
        )

        # SMS format should be concise
        sms_message = f"[{alert.priority.value.upper()}] {alert.truck_id}: {alert.message}"

        assert "LOW" in sms_message
        assert "ABC123" in sms_message
        assert "50 gal" in sms_message
