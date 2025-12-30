"""
Comprehensive tests for alert_service.py - targeting 100% coverage
Current: 30.59% (171/559), Need to cover: 388 statements
"""

import os
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from alert_service import (
    Alert,
    AlertManager,
    AlertPriority,
    AlertType,
    EmailAlertService,
    EmailConfig,
    FuelEventClassifier,
    PendingFuelDrop,
    TwilioAlertService,
    TwilioConfig,
    send_dtc_alert,
    send_gps_quality_alert,
    send_idle_deviation_alert,
    send_low_fuel_alert,
    send_maintenance_prediction_alert,
    send_mpg_underperformance_alert,
    send_sensor_issue_alert,
    send_theft_alert,
    send_theft_confirmed_alert,
    send_voltage_alert,
)
from timezone_utils import utc_now


class TestFuelEventClassifierComprehensive:
    """Test all FuelEventClassifier methods"""

    def test_fuel_classifier_init(self):
        """Test classifier initialization with env vars"""
        with patch.dict(
            os.environ,
            {
                "RECOVERY_WINDOW_MINUTES": "15",
                "RECOVERY_TOLERANCE_PCT": "7.0",
                "DROP_THRESHOLD_PCT": "12.0",
                "REFUEL_THRESHOLD_PCT": "10.0",
                "SENSOR_VOLATILITY_THRESHOLD": "10.0",
            },
        ):
            classifier = FuelEventClassifier()
            assert classifier.recovery_window_minutes == 15
            assert classifier.recovery_tolerance_pct == 7.0
            assert classifier.drop_threshold_pct == 12.0
            assert classifier.refuel_threshold_pct == 10.0
            assert classifier.sensor_volatility_threshold == 10.0

    def test_add_fuel_reading(self):
        """Test add_fuel_reading with history tracking"""
        classifier = FuelEventClassifier()

        # Add readings
        for i in range(25):
            classifier.add_fuel_reading("CO0681", 50.0 + i, utc_now())

        # Should keep only max_history_per_truck (20)
        assert len(classifier._fuel_history["CO0681"]) == 20

    def test_get_sensor_volatility_insufficient_data(self):
        """Test volatility with less than 5 readings"""
        classifier = FuelEventClassifier()
        classifier.add_fuel_reading("CO0681", 50.0)
        classifier.add_fuel_reading("CO0681", 51.0)

        # < 5 readings should return 0.0
        assert classifier.get_sensor_volatility("CO0681") == 0.0

    def test_get_sensor_volatility_high(self):
        """Test high volatility calculation"""
        classifier = FuelEventClassifier()

        # Add very volatile readings
        values = [50, 45, 60, 40, 70, 35]
        for v in values:
            classifier.add_fuel_reading("CO0681", v)

        volatility = classifier.get_sensor_volatility("CO0681")
        assert volatility > 0

    def test_register_fuel_drop_high_volatility(self):
        """Test drop registration with very high sensor volatility"""
        classifier = FuelEventClassifier()

        # Create very high volatility
        for v in [50, 30, 70, 20, 80, 15]:
            classifier.add_fuel_reading("CO0681", v)

        result = classifier.register_fuel_drop(
            truck_id="CO0681",
            fuel_before=60.0,
            fuel_after=50.0,
            tank_capacity_gal=200.0,
            truck_status="MOVING",
        )

        # Should return SENSOR_VOLATILE due to high volatility
        assert result == "SENSOR_VOLATILE"

    def test_register_fuel_drop_extreme_theft(self):
        """Test extreme drop while stopped (immediate theft)"""
        classifier = FuelEventClassifier()

        result = classifier.register_fuel_drop(
            truck_id="CO0681",
            fuel_before=100.0,
            fuel_after=60.0,  # 40% drop
            tank_capacity_gal=200.0,
            location="Test Location",
            truck_status="STOPPED",
        )

        assert result == "IMMEDIATE_THEFT"

    def test_register_fuel_drop_buffered(self):
        """Test normal drop that gets buffered"""
        classifier = FuelEventClassifier()

        result = classifier.register_fuel_drop(
            truck_id="CO0681",
            fuel_before=80.0,
            fuel_after=65.0,  # 15% drop, not extreme
            tank_capacity_gal=200.0,
            truck_status="MOVING",
        )

        assert result is None  # Buffered for recovery check
        assert "CO0681" in classifier._pending_drops

    def test_check_recovery_no_pending(self):
        """Test recovery check with no pending drop"""
        classifier = FuelEventClassifier()
        result = classifier.check_recovery("CO0681", 50.0)
        assert result is None

    def test_check_recovery_too_soon(self):
        """Test recovery check before window expires"""
        classifier = FuelEventClassifier()
        classifier.recovery_window_minutes = 10

        # Register drop
        classifier.register_fuel_drop("CO0681", 80.0, 70.0, 200.0)

        # Check immediately (too soon)
        result = classifier.check_recovery("CO0681", 75.0)
        assert result is None

    def test_check_recovery_sensor_issue(self):
        """Test recovery to original level (sensor issue)"""
        classifier = FuelEventClassifier()
        classifier.recovery_window_minutes = 0  # Instant window for testing

        # Register drop
        classifier.register_fuel_drop("CO0681", 80.0, 70.0, 200.0)

        # Fuel recovered to near-original
        result = classifier.check_recovery("CO0681", 79.0)
        assert result is not None
        assert result["classification"] == "SENSOR_ISSUE"

    def test_check_recovery_refuel_after_drop(self):
        """Test fuel increase after drop (refuel)"""
        classifier = FuelEventClassifier()
        classifier.recovery_window_minutes = 0

        # Register drop
        classifier.register_fuel_drop("CO0681", 50.0, 40.0, 200.0)

        # Fuel went UP significantly
        result = classifier.check_recovery("CO0681", 60.0)
        assert result is not None
        assert result["classification"] == "REFUEL_AFTER_DROP"

    def test_check_recovery_theft_confirmed(self):
        """Test fuel stays low (theft confirmed)"""
        classifier = FuelEventClassifier()
        classifier.recovery_window_minutes = 0

        # Register drop
        classifier.register_fuel_drop("CO0681", 80.0, 60.0, 200.0)

        # Fuel stayed low
        result = classifier.check_recovery("CO0681", 62.0)
        assert result is not None
        assert result["classification"] == "THEFT_CONFIRMED"

    def test_process_fuel_reading_refuel(self):
        """Test refuel detection via process_fuel_reading"""
        classifier = FuelEventClassifier()

        result = classifier.process_fuel_reading(
            truck_id="CO0681",
            last_fuel_pct=30.0,
            current_fuel_pct=50.0,  # +20% >= 8% threshold
            tank_capacity_gal=200.0,
            location="Gas Station",
        )

        assert result is not None
        assert result["classification"] == "REFUEL"

    def test_process_fuel_reading_immediate_theft(self):
        """Test immediate theft detection"""
        classifier = FuelEventClassifier()

        result = classifier.process_fuel_reading(
            truck_id="CO0681",
            last_fuel_pct=100.0,
            current_fuel_pct=55.0,  # -45% while stopped
            tank_capacity_gal=200.0,
            truck_status="STOPPED",
        )

        assert result is not None
        assert result["classification"] == "THEFT_SUSPECTED"

    def test_process_fuel_reading_sensor_volatile(self):
        """Test sensor volatile classification"""
        classifier = FuelEventClassifier()

        # Create very high volatility
        for v in [50, 20, 80, 10, 90, 5]:
            classifier.add_fuel_reading("CO0681", v)

        result = classifier.process_fuel_reading(
            truck_id="CO0681",
            last_fuel_pct=70.0,
            current_fuel_pct=55.0,
            tank_capacity_gal=200.0,
        )

        assert result is not None
        assert result["classification"] == "SENSOR_ISSUE"

    def test_process_fuel_reading_pending(self):
        """Test drop buffered for verification"""
        classifier = FuelEventClassifier()

        result = classifier.process_fuel_reading(
            truck_id="CO0681",
            last_fuel_pct=70.0,
            current_fuel_pct=55.0,  # -15% but not extreme
            tank_capacity_gal=200.0,
            truck_status="MOVING",
        )

        assert result is not None
        assert result["classification"] == "PENDING_VERIFICATION"

    def test_cleanup_stale_drops(self):
        """Test cleanup of old pending drops"""
        classifier = FuelEventClassifier()

        # Create old drop
        old_drop = PendingFuelDrop(
            truck_id="CO0681",
            drop_timestamp=utc_now() - timedelta(hours=30),
            fuel_before=80.0,
            fuel_after=70.0,
            drop_pct=10.0,
            drop_gal=20.0,
        )
        classifier._pending_drops["CO0681"] = old_drop

        # Cleanup with 24h threshold
        classifier.cleanup_stale_drops(max_age_hours=24.0)

        # Should be removed
        assert "CO0681" not in classifier._pending_drops


class TestTwilioAlertService:
    """Test TwilioAlertService"""

    def test_twilio_config_init(self):
        """Test TwilioConfig initialization"""
        config = TwilioConfig(
            account_sid="AC123",
            auth_token="token",
            from_number="+11234567890",
            to_numbers=["+10987654321"],
        )
        assert config.is_configured() is True

    def test_twilio_config_not_configured(self):
        """Test empty TwilioConfig"""
        config = TwilioConfig()
        assert config.is_configured() is False

    @patch("alert_service.Client")
    def test_twilio_send_sms_success(self, mock_client_class):
        """Test SMS sending success"""
        mock_client = Mock()
        mock_client.messages.create.return_value = Mock(sid="SM123")
        mock_client_class.return_value = mock_client

        service = TwilioAlertService(
            TwilioConfig(
                account_sid="AC123", auth_token="token", from_number="+11234567890"
            )
        )

        result = service.send_sms("+10987654321", "Test message")
        assert result is True

    @patch("alert_service.Client")
    def test_twilio_send_sms_failure(self, mock_client_class):
        """Test SMS sending failure"""
        mock_client = Mock()
        mock_client.messages.create.side_effect = Exception("API error")
        mock_client_class.return_value = mock_client

        service = TwilioAlertService(
            TwilioConfig(
                account_sid="AC123", auth_token="token", from_number="+11234567890"
            )
        )

        result = service.send_sms("+10987654321", "Test")
        assert result is False

    @patch("alert_service.Client")
    def test_twilio_send_whatsapp(self, mock_client_class):
        """Test WhatsApp sending"""
        mock_client = Mock()
        mock_client.messages.create.return_value = Mock(sid="SM123")
        mock_client_class.return_value = mock_client

        service = TwilioAlertService(
            TwilioConfig(
                account_sid="AC123", auth_token="token", from_number="+11234567890"
            )
        )

        result = service.send_whatsapp("+10987654321", "Test")
        assert result is True

    @patch("alert_service.Client")
    def test_twilio_broadcast_sms(self, mock_client_class):
        """Test broadcast SMS to multiple numbers"""
        mock_client = Mock()
        mock_client.messages.create.return_value = Mock(sid="SM123")
        mock_client_class.return_value = mock_client

        service = TwilioAlertService(
            TwilioConfig(
                account_sid="AC123",
                auth_token="token",
                from_number="+11234567890",
                to_numbers=["+11111111111", "+12222222222"],
            )
        )

        results = service.broadcast_sms("Broadcast message")
        assert isinstance(results, dict)
        assert len(results) == 2


class TestEmailAlertService:
    """Test EmailAlertService"""

    def test_email_config_init(self):
        """Test EmailConfig initialization"""
        config = EmailConfig(
            smtp_host="smtp.gmail.com",
            smtp_port=587,
            from_email="test@test.com",
            to_email="recipient@test.com",
            password="pass123",
        )
        assert config.is_configured() is True

    def test_email_config_not_configured(self):
        """Test empty EmailConfig"""
        config = EmailConfig()
        assert config.is_configured() is False

    @patch("smtplib.SMTP")
    def test_email_send_success(self, mock_smtp):
        """Test email sending success"""
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        service = EmailAlertService(
            EmailConfig(
                smtp_host="smtp.gmail.com",
                smtp_port=587,
                from_email="test@test.com",
                to_email="recipient@test.com",
                password="pass123",
            )
        )

        result = service.send_email("Subject", "Body text")
        assert result is True

    @patch("smtplib.SMTP")
    def test_email_send_html(self, mock_smtp):
        """Test email with HTML body"""
        mock_server = Mock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        service = EmailAlertService(
            EmailConfig(
                smtp_host="smtp.gmail.com",
                smtp_port=587,
                from_email="test@test.com",
                to_email="recipient@test.com",
                password="pass123",
            )
        )

        result = service.send_email("Subject", "Body", html_body="<h1>HTML</h1>")
        assert result is True

    @patch("smtplib.SMTP")
    def test_email_send_failure(self, mock_smtp):
        """Test email sending failure"""
        mock_smtp.side_effect = Exception("SMTP error")

        service = EmailAlertService(
            EmailConfig(
                smtp_host="smtp.gmail.com",
                smtp_port=587,
                from_email="test@test.com",
                to_email="recipient@test.com",
                password="pass123",
            )
        )

        result = service.send_email("Subject", "Body")
        assert result is False

    def test_format_alert_email(self):
        """Test alert email formatting"""
        service = EmailAlertService(
            EmailConfig(
                smtp_host="smtp.gmail.com",
                smtp_port=587,
                from_email="test@test.com",
                to_email="recipient@test.com",
                password="pass123",
            )
        )

        alert = Alert(
            alert_type=AlertType.THEFT_SUSPECTED,
            priority=AlertPriority.HIGH,
            truck_id="CO0681",
            message="Fuel theft detected",
        )

        subject, html_body = service.format_alert_email(alert)
        assert "CO0681" in subject
        assert "THEFT" in html_body or "theft" in html_body


class TestAlertManager:
    """Test AlertManager"""

    @patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "token",
            "TWILIO_FROM_NUMBER": "+11234567890",
        },
    )
    def test_alert_manager_init(self):
        """Test AlertManager initialization"""
        manager = AlertManager()
        assert manager.twilio_service is not None

    @patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "token",
            "TWILIO_FROM_NUMBER": "+11234567890",
        },
    )
    @patch("alert_service.Client")
    def test_alert_manager_send_alert(self, mock_client_class):
        """Test sending alert through manager"""
        mock_client = Mock()
        mock_client.messages.create.return_value = Mock(sid="SM123")
        mock_client_class.return_value = mock_client

        manager = AlertManager()

        alert = Alert(
            alert_type=AlertType.THEFT_SUSPECTED,
            priority=AlertPriority.HIGH,
            truck_id="CO0681",
            message="Test alert",
        )

        result = manager.send_alert(alert)
        assert isinstance(result, dict)


class TestStandaloneFunctions:
    """Test standalone alert functions"""

    @patch("alert_service.get_alert_manager")
    def test_send_theft_alert(self, mock_get_manager):
        """Test send_theft_alert function"""
        mock_manager = Mock()
        mock_manager.send_alert.return_value = {"sms": True}
        mock_get_manager.return_value = mock_manager

        send_theft_alert("CO0681", "Theft detected", channel="SMS")
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_low_fuel_alert(self, mock_get_manager):
        """Test send_low_fuel_alert function"""
        mock_manager = Mock()
        mock_manager.send_alert.return_value = {"sms": True}
        mock_get_manager.return_value = mock_manager

        send_low_fuel_alert("CO0681", 15.0, channel="SMS")
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_dtc_alert(self, mock_get_manager):
        """Test send_dtc_alert function"""
        mock_manager = Mock()
        mock_manager.send_alert.return_value = {"sms": True}
        mock_get_manager.return_value = mock_manager

        send_dtc_alert("CO0681", "P0420", "Catalyst issue", channel="SMS")
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_voltage_alert(self, mock_get_manager):
        """Test send_voltage_alert function"""
        mock_manager = Mock()
        mock_manager.send_alert.return_value = {"sms": True}
        mock_get_manager.return_value = mock_manager

        send_voltage_alert("CO0681", 11.5, channel="SMS")
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_maintenance_prediction_alert(self, mock_get_manager):
        """Test send_maintenance_prediction_alert function"""
        mock_manager = Mock()
        mock_manager.send_alert.return_value = {"sms": True}
        mock_get_manager.return_value = mock_manager

        send_maintenance_prediction_alert("CO0681", "Oil Change", 5, channel="SMS")
        mock_manager.send_alert.assert_called_once()
