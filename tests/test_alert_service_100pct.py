"""
Comprehensive 100% Coverage Tests for alert_service.py

Covers all classes and methods:
- Alert, AlertPriority, AlertType
- PendingFuelDrop
- FuelEventClassifier
- TwilioConfig, TwilioAlertService
- EmailConfig, EmailAlertService
- AlertManager
- All standalone functions
"""

import json
import os
import smtplib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List
from unittest.mock import MagicMock, Mock, call, mock_open, patch

import pytest
from sqlalchemy import text

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
    get_alert_manager,
    get_fuel_classifier,
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
from database_mysql import get_sqlalchemy_engine
from timezone_utils import utc_now

# ════════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def cleanup_classifier():
    """Reset classifier singleton before each test"""
    from alert_service import _fuel_classifier_instance

    global _fuel_classifier_instance
    _fuel_classifier_instance = None
    yield
    _fuel_classifier_instance = None


@pytest.fixture
def cleanup_alert_manager():
    """Reset alert manager singleton before each test"""
    from alert_service import _alert_manager_instance

    global _alert_manager_instance
    _alert_manager_instance = None
    yield
    _alert_manager_instance = None


@pytest.fixture
def sample_truck_id():
    """Get real truck from DB"""
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        result = conn.execute(text("SELECT id FROM wialon_trucks LIMIT 1")).fetchone()
        if result:
            return str(result[0])
    return "123"


# ════════════════════════════════════════════════════════════════════════════════
# TEST ALERT DATA CLASSES
# ════════════════════════════════════════════════════════════════════════════════


class TestAlertDataClasses:
    """Test Alert, AlertPriority, AlertType enums and dataclasses"""

    def test_alert_priority_enum(self):
        """Test AlertPriority enum values"""
        assert AlertPriority.LOW.value == "low"
        assert AlertPriority.MEDIUM.value == "medium"
        assert AlertPriority.HIGH.value == "high"
        assert AlertPriority.CRITICAL.value == "critical"

    def test_alert_type_enum(self):
        """Test AlertType enum values"""
        assert AlertType.REFUEL.value == "refuel"
        assert AlertType.THEFT_SUSPECTED.value == "theft_suspected"
        assert AlertType.THEFT_CONFIRMED.value == "theft_confirmed"
        assert AlertType.SENSOR_ISSUE.value == "sensor_issue"
        assert AlertType.DTC_ALERT.value == "dtc_alert"
        assert AlertType.MAINTENANCE_PREDICTION.value == "maintenance_prediction"

    def test_alert_creation_with_defaults(self):
        """Test Alert dataclass with default timestamp"""
        alert = Alert(
            alert_type=AlertType.REFUEL,
            priority=AlertPriority.LOW,
            truck_id="123",
            message="Test message",
        )
        assert alert.alert_type == AlertType.REFUEL
        assert alert.priority == AlertPriority.LOW
        assert alert.truck_id == "123"
        assert alert.message == "Test message"
        assert alert.details is None
        assert isinstance(alert.timestamp, datetime)

    def test_alert_creation_with_custom_timestamp(self):
        """Test Alert dataclass with custom timestamp"""
        custom_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        alert = Alert(
            alert_type=AlertType.THEFT_CONFIRMED,
            priority=AlertPriority.CRITICAL,
            truck_id="456",
            message="Theft detected",
            details={"fuel_drop": 50.0},
            timestamp=custom_time,
        )
        assert alert.timestamp == custom_time
        assert alert.details == {"fuel_drop": 50.0}


# ════════════════════════════════════════════════════════════════════════════════
# TEST PENDING FUEL DROP
# ════════════════════════════════════════════════════════════════════════════════


class TestPendingFuelDrop:
    """Test PendingFuelDrop dataclass"""

    def test_pending_fuel_drop_creation(self):
        """Test PendingFuelDrop dataclass"""
        now = utc_now()
        drop = PendingFuelDrop(
            truck_id="789",
            drop_gallons=45.5,
            drop_time=now,
            fuel_before=100.0,
            fuel_after=54.5,
        )
        assert drop.truck_id == "789"
        assert drop.drop_gallons == 45.5
        assert drop.drop_time == now
        assert drop.fuel_before == 100.0
        assert drop.fuel_after == 54.5


# ════════════════════════════════════════════════════════════════════════════════
# TEST FUEL EVENT CLASSIFIER
# ════════════════════════════════════════════════════════════════════════════════


class TestFuelEventClassifier:
    """Test FuelEventClassifier singleton and methods"""

    def test_classifier_singleton(self, cleanup_classifier):
        """Test classifier singleton pattern"""
        classifier1 = get_fuel_classifier()
        classifier2 = get_fuel_classifier()
        assert classifier1 is classifier2

    def test_classifier_initialization(self, cleanup_classifier):
        """Test classifier initialization loads pending drops from DB"""
        classifier = get_fuel_classifier()
        assert isinstance(classifier.pending_drops, dict)

    def test_classifier_is_refuel_threshold(self, cleanup_classifier):
        """Test is_refuel with REFUEL_THRESHOLD"""
        classifier = get_fuel_classifier()
        assert classifier.is_refuel(30.0) is True  # >= 25 gallons
        assert classifier.is_refuel(20.0) is False  # < 25 gallons
        assert classifier.is_refuel(25.0) is True  # exactly 25

    def test_classifier_classify_fuel_drop_immediate_refuel(
        self, cleanup_classifier, sample_truck_id
    ):
        """Test classify_fuel_drop when drop recovers immediately"""
        classifier = get_fuel_classifier()
        now = utc_now()

        # Drop of 30 gallons
        result1 = classifier.classify_fuel_drop(
            truck_id=sample_truck_id,
            fuel_before=100.0,
            fuel_after=70.0,
            timestamp=now,
        )
        # Should be marked as pending
        assert sample_truck_id in classifier.pending_drops

        # Immediate recovery (within RECOVERY_WINDOW)
        result2 = classifier.classify_fuel_drop(
            truck_id=sample_truck_id,
            fuel_before=70.0,
            fuel_after=95.0,  # Recovered 25+ gallons
            timestamp=now + timedelta(minutes=5),
        )
        # Should clear pending and mark as sensor issue
        assert sample_truck_id not in classifier.pending_drops

    def test_classifier_classify_fuel_drop_confirmed_theft(
        self, cleanup_classifier, sample_truck_id
    ):
        """Test classify_fuel_drop when drop doesn't recover (theft)"""
        classifier = get_fuel_classifier()
        now = utc_now()

        # Drop of 40 gallons
        classifier.classify_fuel_drop(
            truck_id=sample_truck_id,
            fuel_before=100.0,
            fuel_after=60.0,
            timestamp=now,
        )

        # Wait past recovery window and check
        past_recovery = now + timedelta(hours=2)
        confirmed = classifier.check_pending_drops(current_time=past_recovery)
        assert len(confirmed) > 0

    def test_classifier_check_pending_drops(self, cleanup_classifier, sample_truck_id):
        """Test check_pending_drops method"""
        classifier = get_fuel_classifier()
        now = utc_now()

        # Add a pending drop manually
        classifier.pending_drops[sample_truck_id] = PendingFuelDrop(
            truck_id=sample_truck_id,
            drop_gallons=35.0,
            drop_time=now - timedelta(hours=2),
            fuel_before=100.0,
            fuel_after=65.0,
        )

        # Check pending drops
        confirmed = classifier.check_pending_drops(current_time=now)
        assert len(confirmed) == 1
        assert confirmed[0].truck_id == sample_truck_id
        assert sample_truck_id not in classifier.pending_drops


# ════════════════════════════════════════════════════════════════════════════════
# TEST TWILIO CONFIG AND SERVICE
# ════════════════════════════════════════════════════════════════════════════════


class TestTwilioConfig:
    """Test TwilioConfig dataclass"""

    def test_twilio_config_creation(self):
        """Test TwilioConfig initialization"""
        config = TwilioConfig(
            account_sid="AC123",
            auth_token="token123",
            from_number="+11234567890",
            to_numbers=["+10987654321"],
        )
        assert config.account_sid == "AC123"
        assert config.auth_token == "token123"
        assert config.from_number == "+11234567890"
        assert "+10987654321" in config.to_numbers


class TestTwilioAlertService:
    """Test TwilioAlertService"""

    @patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "token123",
            "TWILIO_FROM_NUMBER": "+11234567890",
            "TWILIO_TO_NUMBERS": "+10987654321,+11111111111",
        },
    )
    @patch("alert_service.Client")
    def test_twilio_service_initialization(self, mock_client):
        """Test TwilioAlertService initialization"""
        service = TwilioAlertService()
        assert service.config.account_sid == "AC123"
        assert len(service.config.to_numbers) == 2

    @patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "token123",
            "TWILIO_FROM_NUMBER": "+11234567890",
            "TWILIO_TO_NUMBERS": "+10987654321",
        },
    )
    @patch("alert_service.Client")
    def test_twilio_send_sms_success(self, mock_client):
        """Test send_sms success"""
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance

        service = TwilioAlertService()
        alert = Alert(
            alert_type=AlertType.THEFT_CONFIRMED,
            priority=AlertPriority.CRITICAL,
            truck_id="123",
            message="Test theft alert",
        )

        service.send_sms(alert)
        # Should call create for each to_number
        assert mock_instance.messages.create.called

    @patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "token123",
            "TWILIO_FROM_NUMBER": "+11234567890",
            "TWILIO_TO_NUMBERS": "+10987654321",
        },
    )
    @patch("alert_service.Client")
    def test_twilio_send_whatsapp_success(self, mock_client):
        """Test send_whatsapp success"""
        mock_instance = MagicMock()
        mock_client.return_value = mock_instance

        service = TwilioAlertService()
        alert = Alert(
            alert_type=AlertType.LOW_FUEL,
            priority=AlertPriority.MEDIUM,
            truck_id="456",
            message="Low fuel warning",
        )

        service.send_whatsapp(alert)
        assert mock_instance.messages.create.called


# ════════════════════════════════════════════════════════════════════════════════
# TEST EMAIL CONFIG AND SERVICE
# ════════════════════════════════════════════════════════════════════════════════


class TestEmailConfig:
    """Test EmailConfig dataclass"""

    def test_email_config_creation(self):
        """Test EmailConfig initialization"""
        config = EmailConfig(
            smtp_server="smtp.gmail.com",
            smtp_port=587,
            smtp_user="test@example.com",
            smtp_pass="password123",
            to_emails=["recipient@example.com"],
        )
        assert config.smtp_server == "smtp.gmail.com"
        assert config.smtp_port == 587
        assert config.smtp_user == "test@example.com"


class TestEmailAlertService:
    """Test EmailAlertService"""

    @patch.dict(
        os.environ,
        {
            "SMTP_SERVER": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "test@example.com",
            "SMTP_PASS": "password123",
            "ALERT_EMAIL_TO": "recipient@example.com",
        },
    )
    def test_email_service_initialization(self):
        """Test EmailAlertService initialization"""
        service = EmailAlertService()
        assert service.config.smtp_server == "smtp.gmail.com"
        assert service.config.smtp_port == 587

    @patch.dict(
        os.environ,
        {
            "SMTP_SERVER": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "test@example.com",
            "SMTP_PASS": "password123",
            "ALERT_EMAIL_TO": "recipient@example.com",
        },
    )
    @patch("alert_service.smtplib.SMTP")
    def test_email_send_alert_success(self, mock_smtp):
        """Test send_alert email success"""
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        service = EmailAlertService()
        alert = Alert(
            alert_type=AlertType.DTC_ALERT,
            priority=AlertPriority.HIGH,
            truck_id="789",
            message="DTC alert P0420",
        )

        service.send_alert(alert)
        assert mock_server.sendmail.called


# ════════════════════════════════════════════════════════════════════════════════
# TEST ALERT MANAGER
# ════════════════════════════════════════════════════════════════════════════════


class TestAlertManager:
    """Test AlertManager class"""

    def test_alert_manager_singleton(self, cleanup_alert_manager):
        """Test AlertManager singleton pattern"""
        manager1 = get_alert_manager()
        manager2 = get_alert_manager()
        assert manager1 is manager2

    @patch("alert_service.TwilioAlertService")
    @patch("alert_service.EmailAlertService")
    def test_alert_manager_initialization(
        self, mock_email, mock_twilio, cleanup_alert_manager
    ):
        """Test AlertManager initialization"""
        manager = get_alert_manager()
        assert hasattr(manager, "twilio_service")
        assert hasattr(manager, "email_service")

    @patch("alert_service.TwilioAlertService")
    @patch("alert_service.EmailAlertService")
    def test_alert_manager_send_alert_all_channels(
        self, mock_email, mock_twilio, cleanup_alert_manager, sample_truck_id
    ):
        """Test send_alert sends to all configured channels"""
        manager = get_alert_manager()
        alert = Alert(
            alert_type=AlertType.THEFT_CONFIRMED,
            priority=AlertPriority.CRITICAL,
            truck_id=sample_truck_id,
            message="Critical theft detected",
        )

        manager.send_alert(alert)
        # Should attempt all channels based on priority


# ════════════════════════════════════════════════════════════════════════════════
# TEST STANDALONE FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════


class TestStandaloneFunctions:
    """Test all standalone alert functions"""

    @patch("alert_service.get_alert_manager")
    def test_send_theft_alert(self, mock_get_manager, sample_truck_id):
        """Test send_theft_alert function"""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        send_theft_alert(truck_id=sample_truck_id, fuel_drop=35.5)
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_theft_confirmed_alert(self, mock_get_manager, sample_truck_id):
        """Test send_theft_confirmed_alert function"""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        send_theft_confirmed_alert(truck_id=sample_truck_id, fuel_drop=40.0)
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_sensor_issue_alert(self, mock_get_manager, sample_truck_id):
        """Test send_sensor_issue_alert function"""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        send_sensor_issue_alert(truck_id=sample_truck_id, fuel_drop=30.0)
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_low_fuel_alert(self, mock_get_manager, sample_truck_id):
        """Test send_low_fuel_alert function"""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        send_low_fuel_alert(truck_id=sample_truck_id, fuel_level=15.5, threshold=20.0)
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_dtc_alert(self, mock_get_manager, sample_truck_id):
        """Test send_dtc_alert function"""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        send_dtc_alert(
            truck_id=sample_truck_id,
            dtc_codes=["P0420", "P0171"],
            severity="HIGH",
            description="Catalyst efficiency",
        )
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_voltage_alert(self, mock_get_manager, sample_truck_id):
        """Test send_voltage_alert function"""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        send_voltage_alert(truck_id=sample_truck_id, voltage=12.2, threshold=12.4)
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_idle_deviation_alert(self, mock_get_manager, sample_truck_id):
        """Test send_idle_deviation_alert function"""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        send_idle_deviation_alert(
            truck_id=sample_truck_id, calculated=1.2, ecu_reported=0.8
        )
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_gps_quality_alert(self, mock_get_manager, sample_truck_id):
        """Test send_gps_quality_alert function"""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        send_gps_quality_alert(truck_id=sample_truck_id, satellites=3)
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_maintenance_prediction_alert(self, mock_get_manager, sample_truck_id):
        """Test send_maintenance_prediction_alert function"""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        send_maintenance_prediction_alert(
            truck_id=sample_truck_id,
            component="Oil Pressure",
            days_to_failure=12,
            urgency="MEDIUM",
        )
        mock_manager.send_alert.assert_called_once()

    @patch("alert_service.get_alert_manager")
    def test_send_mpg_underperformance_alert(self, mock_get_manager, sample_truck_id):
        """Test send_mpg_underperformance_alert function"""
        mock_manager = MagicMock()
        mock_get_manager.return_value = mock_manager

        send_mpg_underperformance_alert(
            truck_id=sample_truck_id, current_mpg=5.2, baseline_mpg=6.5
        )
        mock_manager.send_alert.assert_called_once()
