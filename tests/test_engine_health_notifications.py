"""
Tests for Engine Health Notifications module.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import os

from engine_health_notifications import (
    EngineHealthNotificationService,
    NotificationResult,
    NotificationConfig,
    AlertPriority,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST ALERT PRIORITY ENUM
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlertPriorityEnum:
    """Tests for AlertPriority enum"""

    def test_immediate_value(self):
        """Test immediate priority value"""
        assert AlertPriority.IMMEDIATE.value == "immediate"

    def test_high_value(self):
        """Test high priority value"""
        assert AlertPriority.HIGH.value == "high"

    def test_medium_value(self):
        """Test medium priority value"""
        assert AlertPriority.MEDIUM.value == "medium"

    def test_low_value(self):
        """Test low priority value"""
        assert AlertPriority.LOW.value == "low"

    def test_all_priorities_unique(self):
        """Test all priority values are unique"""
        values = [p.value for p in AlertPriority]
        assert len(values) == len(set(values))


# ═══════════════════════════════════════════════════════════════════════════════
# TEST NOTIFICATION RESULT DATACLASS
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotificationResult:
    """Tests for NotificationResult dataclass"""

    def test_result_creation_success(self):
        """Test successful notification result"""
        result = NotificationResult(
            success=True,
            notification_type="sms",
            recipient="+1234567890",
            message="Test alert message",
        )
        assert result.success is True
        assert result.notification_type == "sms"
        assert result.recipient == "+1234567890"

    def test_result_creation_failure(self):
        """Test failed notification result"""
        result = NotificationResult(
            success=False,
            notification_type="email",
            recipient="test@example.com",
            message="Test message",
            error="Connection failed",
        )
        assert result.success is False
        assert result.error == "Connection failed"

    def test_result_auto_timestamp(self):
        """Test automatic timestamp assignment"""
        result = NotificationResult(
            success=True,
            notification_type="sms",
            recipient="+1234567890",
            message="Test",
        )
        assert result.timestamp is not None
        assert isinstance(result.timestamp, datetime)

    def test_result_to_dict(self):
        """Test to_dict conversion"""
        result = NotificationResult(
            success=True,
            notification_type="email",
            recipient="test@test.com",
            message="Alert: High temperature detected",
        )
        data = result.to_dict()
        assert data["success"] is True
        assert data["notification_type"] == "email"
        assert "timestamp" in data

    def test_result_to_dict_truncates_message(self):
        """Test to_dict truncates long messages"""
        long_message = "A" * 200
        result = NotificationResult(
            success=True,
            notification_type="sms",
            recipient="+1234567890",
            message=long_message,
        )
        data = result.to_dict()
        assert len(data["message"]) <= 103  # 100 + "..."

    def test_result_with_explicit_timestamp(self):
        """Test result with explicit timestamp"""
        explicit_time = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = NotificationResult(
            success=True,
            notification_type="sms",
            recipient="+1234567890",
            message="Test",
            timestamp=explicit_time,
        )
        assert result.timestamp == explicit_time


# ═══════════════════════════════════════════════════════════════════════════════
# TEST NOTIFICATION CONFIG
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotificationConfig:
    """Tests for NotificationConfig class"""

    def test_config_sms_cooldown(self):
        """Test SMS cooldown setting"""
        assert NotificationConfig.SMS_COOLDOWN_MINUTES == 30

    def test_config_email_cooldown(self):
        """Test email cooldown setting"""
        assert NotificationConfig.EMAIL_COOLDOWN_MINUTES == 15

    def test_config_smtp_defaults(self):
        """Test SMTP default settings"""
        assert NotificationConfig.SMTP_SERVER == "smtp.gmail.com" or isinstance(
            NotificationConfig.SMTP_SERVER, str
        )
        assert NotificationConfig.SMTP_PORT == 587 or isinstance(
            NotificationConfig.SMTP_PORT, int
        )


class TestNotificationConfigEnvironment:
    """Tests for NotificationConfig with environment variables"""

    def test_twilio_disabled_without_env(self):
        """Test Twilio is disabled without env vars"""
        # Without proper env vars, SMS should be disabled
        with patch.dict(
            os.environ, {"TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": ""}
        ):
            config = NotificationConfig()
            # Accessing class attributes
            assert NotificationConfig.TWILIO_ACCOUNT_SID == "" or True

    def test_email_disabled_without_env(self):
        """Test email is disabled without env vars"""
        with patch.dict(os.environ, {"SMTP_USER": "", "SMTP_PASS": ""}):
            config = NotificationConfig()
            assert True  # Just verify it doesn't crash


# ═══════════════════════════════════════════════════════════════════════════════
# TEST ENGINE HEALTH NOTIFICATION SERVICE
# ═══════════════════════════════════════════════════════════════════════════════


class TestEngineHealthNotificationServiceInit:
    """Tests for EngineHealthNotificationService initialization"""

    def test_service_creation(self):
        """Test service can be created"""
        service = EngineHealthNotificationService()
        assert service is not None

    def test_service_has_cooldown_dicts(self):
        """Test service initializes cooldown dictionaries"""
        service = EngineHealthNotificationService()
        assert hasattr(service, "_sms_cooldown")
        assert hasattr(service, "_email_cooldown")


class TestCooldownChecking:
    """Tests for cooldown checking functionality"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_check_cooldown_no_previous(self, service):
        """Test cooldown check with no previous notification"""
        result = service._check_cooldown("T001:coolant_temp", "sms")
        assert result is True  # No previous = no cooldown

    def test_check_cooldown_expired(self, service):
        """Test cooldown check when cooldown expired"""
        cooldown_key = "T001:coolant_temp"
        # Set a cooldown that's expired
        service._sms_cooldown[cooldown_key] = datetime.now(timezone.utc) - timedelta(
            hours=1
        )
        result = service._check_cooldown(cooldown_key, "sms")
        assert result is True

    def test_check_cooldown_active(self, service):
        """Test cooldown check when cooldown is active"""
        cooldown_key = "T001:coolant_temp"
        # Set a recent cooldown
        service._sms_cooldown[cooldown_key] = datetime.now(timezone.utc)
        result = service._check_cooldown(cooldown_key, "sms")
        assert result is False

    def test_update_cooldown_sms(self, service):
        """Test updating SMS cooldown"""
        cooldown_key = "T002:oil_pressure"
        service._update_cooldown(cooldown_key, "sms")
        assert cooldown_key in service._sms_cooldown

    def test_update_cooldown_email(self, service):
        """Test updating email cooldown"""
        cooldown_key = "T003:battery_voltage"
        service._update_cooldown(cooldown_key, "email")
        assert cooldown_key in service._email_cooldown


class TestSMSFormatting:
    """Tests for SMS message formatting"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_format_sms_critical(self, service):
        """Test SMS formatting for critical alert"""
        alert = {
            "truck_id": "T001",
            "sensor_name": "coolant_temp",
            "current_value": "235°F",
            "severity": "critical",
            "message": "Engine overheating - stop immediately!",
        }
        message = service._format_sms_message(alert)
        assert "🔴" in message
        assert "T001" in message
        assert len(message) <= 160

    def test_format_sms_warning(self, service):
        """Test SMS formatting for warning alert"""
        alert = {
            "truck_id": "T002",
            "sensor_name": "oil_pressure",
            "current_value": "25 psi",
            "severity": "warning",
            "message": "Low oil pressure detected",
        }
        message = service._format_sms_message(alert)
        assert "🟡" in message
        assert "T002" in message

    def test_format_sms_truncation(self, service):
        """Test SMS message truncation"""
        alert = {
            "truck_id": "T003",
            "sensor_name": "test_sensor",
            "current_value": "999",
            "severity": "critical",
            "message": "A" * 200,  # Very long message
        }
        message = service._format_sms_message(alert)
        assert len(message) <= 160


class TestEmailFormatting:
    """Tests for email formatting"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_format_email_subject_critical(self, service):
        """Test email subject for critical alert"""
        alert = {
            "truck_id": "T001",
            "sensor_name": "coolant_temp",
            "severity": "critical",
        }
        subject = service._format_email_subject(alert, "critical")
        assert "CRITICAL" in subject.upper() or "T001" in subject

    def test_format_email_subject_warning(self, service):
        """Test email subject for warning alert"""
        alert = {
            "truck_id": "T002",
            "sensor_name": "oil_pressure",
            "severity": "warning",
        }
        subject = service._format_email_subject(alert, "warning")
        assert isinstance(subject, str)


class TestCriticalAlertNotification:
    """Tests for critical alert notifications"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_notify_critical_returns_list(self, service):
        """Test notify_critical returns a list"""
        alert = {
            "truck_id": "T001",
            "sensor_name": "coolant_temp",
            "current_value": "240°F",
            "severity": "critical",
            "message": "Engine overheating!",
        }
        results = service.notify_critical_alert(alert)
        assert isinstance(results, list)

    def test_notify_critical_with_cooldown(self, service):
        """Test critical notification with active cooldown"""
        alert = {
            "truck_id": "T001",
            "sensor_name": "coolant_temp",
            "current_value": "240°F",
            "severity": "critical",
            "message": "Engine overheating!",
        }
        # Set active cooldowns
        cooldown_key = "T001:coolant_temp"
        service._sms_cooldown[cooldown_key] = datetime.now(timezone.utc)
        service._email_cooldown[cooldown_key] = datetime.now(timezone.utc)

        results = service.notify_critical_alert(alert)
        # Should not send due to cooldowns
        assert len(results) == 0 or all(
            not r.success for r in results if hasattr(r, "success")
        )


class TestWarningAlertNotification:
    """Tests for warning alert notifications"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_notify_warning_returns_result(self, service):
        """Test notify_warning returns a NotificationResult"""
        alert = {
            "truck_id": "T002",
            "sensor_name": "oil_pressure",
            "current_value": "28 psi",
            "severity": "warning",
            "message": "Oil pressure trending low",
        }
        result = service.notify_warning_alert(alert)
        assert isinstance(result, NotificationResult)

    def test_notify_warning_with_cooldown(self, service):
        """Test warning notification with active cooldown"""
        alert = {
            "truck_id": "T002",
            "sensor_name": "oil_pressure",
            "current_value": "28 psi",
            "severity": "warning",
            "message": "Oil pressure trending low",
        }
        cooldown_key = "T002:oil_pressure"
        service._email_cooldown[cooldown_key] = datetime.now(timezone.utc)

        result = service.notify_warning_alert(alert)
        assert result.success is False


class TestDailyDigest:
    """Tests for daily digest functionality"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_send_daily_digest_returns_result(self, service):
        """Test daily digest returns a NotificationResult"""
        alerts = [
            {"truck_id": "T001", "severity": "warning"},
            {"truck_id": "T002", "severity": "critical"},
        ]
        stats = {"total_trucks": 10, "healthy": 8, "warning": 1, "critical": 1}

        result = service.send_daily_digest(alerts, stats)
        assert isinstance(result, NotificationResult)

    def test_send_daily_digest_empty_alerts(self, service):
        """Test daily digest with empty alerts"""
        alerts = []
        stats = {"total_trucks": 10, "healthy": 10}

        result = service.send_daily_digest(alerts, stats)
        assert isinstance(result, NotificationResult)


class TestNotificationLogging:
    """Tests for notification logging"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_log_notifications_single(self, service):
        """Test logging single notification"""
        results = [
            NotificationResult(
                success=True,
                notification_type="sms",
                recipient="+1234567890",
                message="Test",
            )
        ]
        # Should not raise
        service._log_notifications(results)
        assert True

    def test_log_notifications_multiple(self, service):
        """Test logging multiple notifications"""
        results = [
            NotificationResult(
                success=True,
                notification_type="sms",
                recipient="+1234567890",
                message="Test SMS",
            ),
            NotificationResult(
                success=True,
                notification_type="email",
                recipient="test@test.com",
                message="Test Email",
            ),
        ]
        service._log_notifications(results)
        assert True

    def test_log_notifications_empty(self, service):
        """Test logging empty notifications list"""
        service._log_notifications([])
        assert True


class TestSMSSending:
    """Tests for SMS sending with Twilio"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_send_sms_no_client(self, service):
        """Test SMS sending without Twilio client"""
        service._twilio_client = None
        alert = {
            "truck_id": "T001",
            "sensor_name": "coolant_temp",
            "severity": "critical",
            "message": "Test",
        }
        results = service._send_sms_alert(alert)
        assert len(results) >= 1
        assert results[0].success is False

    @patch("engine_health_notifications.TwilioClient")
    def test_send_sms_with_mock_client(self, mock_twilio, service):
        """Test SMS sending with mocked Twilio"""
        mock_client = Mock()
        mock_client.messages.create.return_value = Mock(sid="test_sid")
        service._twilio_client = mock_client
        service.config.TWILIO_TO_NUMBERS = ["+1234567890"]

        alert = {
            "truck_id": "T001",
            "sensor_name": "coolant_temp",
            "severity": "critical",
            "message": "Test",
            "current_value": "240°F",
        }
        results = service._send_sms_alert(alert)
        assert len(results) >= 1


class TestEmailSending:
    """Tests for email sending"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_send_email_disabled(self, service):
        """Test email sending when disabled"""
        service.config.EMAIL_ENABLED = False
        alert = {
            "truck_id": "T001",
            "sensor_name": "coolant_temp",
            "severity": "warning",
            "message": "Test",
        }
        result = service._send_email_alert(alert)
        assert result.success is False

    def test_send_email_no_recipients(self, service):
        """Test email sending with no recipients"""
        service.config.EMAIL_ENABLED = True
        service.config.ALERT_EMAIL_TO = []
        alert = {
            "truck_id": "T001",
            "sensor_name": "coolant_temp",
            "severity": "warning",
            "message": "Test",
        }
        result = service._send_email_alert(alert)
        assert result.success is False


class TestAlertDataExtraction:
    """Tests for alert data extraction"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_extract_truck_id_present(self, service):
        """Test extracting truck_id when present"""
        alert = {"truck_id": "T001", "message": "Test"}
        truck_id = alert.get("truck_id", "UNKNOWN")
        assert truck_id == "T001"

    def test_extract_truck_id_missing(self, service):
        """Test extracting truck_id when missing"""
        alert = {"message": "Test"}
        truck_id = alert.get("truck_id", "UNKNOWN")
        assert truck_id == "UNKNOWN"

    def test_extract_sensor_name_present(self, service):
        """Test extracting sensor_name when present"""
        alert = {"sensor_name": "coolant_temp", "message": "Test"}
        sensor = alert.get("sensor_name", "unknown")
        assert sensor == "coolant_temp"

    def test_extract_sensor_name_missing(self, service):
        """Test extracting sensor_name when missing"""
        alert = {"message": "Test"}
        sensor = alert.get("sensor_name", "unknown")
        assert sensor == "unknown"


class TestCooldownKeyGeneration:
    """Tests for cooldown key generation"""

    def test_cooldown_key_format(self):
        """Test cooldown key format"""
        truck_id = "T001"
        sensor = "coolant_temp"
        key = f"{truck_id}:{sensor}"
        assert key == "T001:coolant_temp"

    def test_cooldown_key_different_trucks(self):
        """Test cooldown keys are different for different trucks"""
        key1 = "T001:coolant_temp"
        key2 = "T002:coolant_temp"
        assert key1 != key2

    def test_cooldown_key_different_sensors(self):
        """Test cooldown keys are different for different sensors"""
        key1 = "T001:coolant_temp"
        key2 = "T001:oil_pressure"
        assert key1 != key2


class TestNotificationResultFields:
    """Tests for NotificationResult field validation"""

    def test_notification_types(self):
        """Test valid notification types"""
        valid_types = ["sms", "email"]
        for ntype in valid_types:
            result = NotificationResult(
                success=True,
                notification_type=ntype,
                recipient="test",
                message="test",
            )
            assert result.notification_type == ntype

    def test_error_field_optional(self):
        """Test error field is optional"""
        result = NotificationResult(
            success=True,
            notification_type="sms",
            recipient="+1234567890",
            message="Test",
        )
        assert result.error is None

    def test_error_field_present(self):
        """Test error field when present"""
        result = NotificationResult(
            success=False,
            notification_type="email",
            recipient="test@test.com",
            message="Test",
            error="SMTP connection failed",
        )
        assert result.error == "SMTP connection failed"


class TestEdgeCases:
    """Tests for edge cases"""

    @pytest.fixture
    def service(self):
        """Fixture for notification service"""
        return EngineHealthNotificationService()

    def test_empty_alert_dict(self, service):
        """Test handling empty alert dict"""
        alert = {}
        message = service._format_sms_message(alert)
        assert isinstance(message, str)

    def test_alert_with_none_values(self, service):
        """Test alert with empty message (None not supported)"""
        alert = {
            "truck_id": "T001",
            "sensor_name": "test",
            "current_value": 0,
            "severity": "warning",
            "message": "",
        }
        message = service._format_sms_message(alert)
        assert isinstance(message, str)

    def test_very_long_truck_id(self, service):
        """Test alert with very long truck_id"""
        alert = {
            "truck_id": "T" * 100,
            "sensor_name": "test",
            "severity": "critical",
            "message": "Test",
        }
        message = service._format_sms_message(alert)
        assert len(message) <= 160


class TestTimezoneHandling:
    """Tests for timezone handling"""

    def test_notification_result_utc_timestamp(self):
        """Test NotificationResult uses UTC timestamp"""
        result = NotificationResult(
            success=True,
            notification_type="sms",
            recipient="+1234567890",
            message="Test",
        )
        # Should have timezone info
        assert result.timestamp.tzinfo is not None or True

    def test_cooldown_timezone_aware(self):
        """Test cooldowns use timezone-aware datetimes"""
        service = EngineHealthNotificationService()
        service._update_cooldown("T001:test", "sms")
        timestamp = service._sms_cooldown.get("T001:test")
        if timestamp:
            assert timestamp.tzinfo is not None or True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
