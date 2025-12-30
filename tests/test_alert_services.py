"""
Tests for AlertManager.send_alert and external service integrations
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from alert_service import (
    Alert,
    AlertManager,
    AlertPriority,
    AlertType,
    EmailAlertService,
    EmailConfig,
    TwilioAlertService,
    TwilioConfig,
)


class TestAlertManagerSendAlert:
    """Test send_alert functionality"""

    def test_send_alert_adds_to_history(self):
        """Test that send_alert adds alert to history"""
        manager = AlertManager()

        alert = Alert(
            alert_type=AlertType.REFUEL,
            priority=AlertPriority.LOW,
            truck_id="TEST_001",
            message="Refuel detected",
        )

        # Mock external services to avoid actual sends
        manager.twilio._client = None
        manager.email.config.to_email = ""

        manager.send_alert(alert, channels=[])

        assert len(manager._alert_history) > 0
        assert manager._alert_history[-1].truck_id == "TEST_001"

    def test_send_alert_history_max_limit(self):
        """Test that history is trimmed when exceeding max"""
        manager = AlertManager()
        manager._max_history = 10

        # Add 15 alerts
        for i in range(15):
            alert = Alert(
                alert_type=AlertType.REFUEL,
                priority=AlertPriority.LOW,
                truck_id=f"TRUCK_{i:03d}",
                message="Test",
            )
            manager.send_alert(alert, channels=[])

        # Should only keep last 10
        assert len(manager._alert_history) == 10

    def test_send_alert_updates_last_alert_timestamps(self):
        """Test that send_alert updates tracking timestamps"""
        manager = AlertManager()

        alert = Alert(
            alert_type=AlertType.SENSOR_ISSUE,
            priority=AlertPriority.MEDIUM,
            truck_id="TEST_002",
            message="Sensor issue",
        )

        manager.send_alert(alert, channels=[])

        # Should update general truck timestamp
        assert "TEST_002" in manager._last_alert_by_truck

        # Should update per-type timestamp
        type_key = f"TEST_002:{AlertType.SENSOR_ISSUE.value}"
        assert type_key in manager._last_alert_by_type

    def test_send_alert_critical_priority_uses_all_channels(self):
        """Test that CRITICAL alerts default to all channels"""
        manager = AlertManager()

        alert = Alert(
            alert_type=AlertType.THEFT_CONFIRMED,
            priority=AlertPriority.CRITICAL,
            truck_id="TEST_003",
            message="Theft confirmed",
        )

        # Mock services
        manager.twilio.broadcast_sms = Mock(return_value={"number": True})
        manager.twilio.send_whatsapp = Mock(return_value=True)
        manager.twilio.config.to_numbers = ["+1234567890"]
        manager.email.send_email = Mock(return_value=True)
        manager.email.format_alert_email = Mock(
            return_value=("Subject", "Body", "HTML")
        )

        result = manager.send_alert(alert)  # channels=None, should default to all

        # Should try SMS
        assert manager.twilio.broadcast_sms.called

        # Should try WhatsApp
        assert manager.twilio.send_whatsapp.called

        # Should try Email
        assert manager.email.send_email.called

    def test_send_alert_high_priority_uses_sms_email(self):
        """Test that HIGH alerts default to SMS and email"""
        manager = AlertManager()

        alert = Alert(
            alert_type=AlertType.THEFT_SUSPECTED,
            priority=AlertPriority.HIGH,
            truck_id="TEST_004",
            message="Theft suspected",
        )

        # Mock services
        manager.twilio.broadcast_sms = Mock(return_value={"number": True})
        manager.twilio.send_whatsapp = Mock(return_value=True)
        manager.email.send_email = Mock(return_value=True)
        manager.email.format_alert_email = Mock(
            return_value=("Subject", "Body", "HTML")
        )

        result = manager.send_alert(alert)

        # Should try SMS
        assert manager.twilio.broadcast_sms.called

        # Should try Email
        assert manager.email.send_email.called

    def test_send_alert_low_priority_no_channels(self):
        """Test that LOW/MEDIUM priority alerts don't send by default"""
        manager = AlertManager()

        alert = Alert(
            alert_type=AlertType.REFUEL,
            priority=AlertPriority.LOW,
            truck_id="TEST_005",
            message="Refuel",
        )

        # Mock services
        manager.twilio.broadcast_sms = Mock(return_value={})
        manager.email.send_email = Mock(return_value=True)

        result = manager.send_alert(alert)  # channels=None

        # Should NOT try to send (no channels for LOW)
        assert not manager.twilio.broadcast_sms.called
        assert not manager.email.send_email.called

        # But should return True (logged)
        assert result is True

    def test_send_alert_explicit_channels(self):
        """Test sending with explicit channels"""
        manager = AlertManager()

        alert = Alert(
            alert_type=AlertType.MAINTENANCE_DUE,
            priority=AlertPriority.MEDIUM,
            truck_id="TEST_006",
            message="Maintenance due",
        )

        # Mock services
        manager.email.send_email = Mock(return_value=True)
        manager.email.format_alert_email = Mock(return_value=("Subject", "Body", None))

        result = manager.send_alert(alert, channels=["email"])

        # Should send email
        assert manager.email.send_email.called
        assert result is True


class TestTwilioAlertService:
    """Test TwilioAlertService"""

    def test_twilio_not_configured(self):
        """Test Twilio service when not configured"""
        config = TwilioConfig()
        config.account_sid = ""
        config.auth_token = ""

        service = TwilioAlertService(config)

        result = service.send_sms("+1234567890", "Test message")

        assert result is False

    def test_twilio_config_is_configured(self):
        """Test TwilioConfig.is_configured()"""
        # Not configured
        config1 = TwilioConfig()
        config1.account_sid = ""
        assert config1.is_configured() is False

        # Configured
        config2 = TwilioConfig()
        config2.account_sid = "ACxxx"
        config2.auth_token = "xxx"
        config2.from_number = "+1234567890"
        assert config2.is_configured() is True


class TestEmailAlertService:
    """Test EmailAlertService"""

    def test_email_not_configured(self):
        """Test EmailAlertService when not configured"""
        config = EmailConfig()
        config.smtp_user = ""
        config.to_email = ""

        service = EmailAlertService(config)

        result = service.send_email("Subject", "Body")

        assert result is False

    def test_email_config_is_configured(self):
        """Test EmailConfig.is_configured()"""
        # Not configured
        config1 = EmailConfig()
        config1.smtp_user = ""
        assert config1.is_configured() is False

        # Configured
        config2 = EmailConfig()
        config2.smtp_server = "smtp.test.com"
        config2.smtp_user = "user@test.com"
        config2.smtp_pass = "password"
        config2.to_email = "alert@test.com"
        assert config2.is_configured() is True

    def test_format_alert_email(self):
        """Test email formatting"""
        service = EmailAlertService()

        alert = Alert(
            alert_type=AlertType.DTC_ALERT,
            priority=AlertPriority.HIGH,
            truck_id="TEST_007",
            message="DTC detected",
            details={
                "code": "P0420",
                "description": "Catalyst System Efficiency Below Threshold",
            },
        )

        subject, body, html = service.format_alert_email(alert)

        assert "TEST_007" in subject or "TEST_007" in body
        assert "DTC" in subject or "DTC" in body
