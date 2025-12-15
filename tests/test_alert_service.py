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
            {
                "TWILIO_ACCOUNT_SID": "",
                "TWILIO_AUTH_TOKEN": "",
                "TWILIO_FROM_NUMBER": "",
            },
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
        sms_message = (
            f"[{alert.priority.value.upper()}] {alert.truck_id}: {alert.message}"
        )

        assert "LOW" in sms_message
        assert "ABC123" in sms_message
        assert "50 gal" in sms_message


class TestFuelEventClassifier:
    """Test FuelEventClassifier for theft vs sensor issue detection"""

    def test_classifier_initialization(self):
        """Should initialize with default configuration"""
        from alert_service import FuelEventClassifier

        classifier = FuelEventClassifier()

        assert classifier.recovery_window_minutes >= 1
        assert classifier.recovery_tolerance_pct > 0
        assert classifier.drop_threshold_pct > 0
        assert classifier.sensor_volatility_threshold > 0

    def test_add_fuel_reading(self):
        """Should record fuel readings for volatility analysis"""
        from alert_service import FuelEventClassifier

        classifier = FuelEventClassifier()
        classifier.add_fuel_reading("TRUCK001", 75.0)
        classifier.add_fuel_reading("TRUCK001", 74.5)
        classifier.add_fuel_reading("TRUCK001", 74.0)

        assert "TRUCK001" in classifier._fuel_history
        assert len(classifier._fuel_history["TRUCK001"]) == 3

    def test_get_sensor_volatility_insufficient_data(self):
        """Should return 0 if insufficient data for volatility calculation"""
        from alert_service import FuelEventClassifier

        classifier = FuelEventClassifier()
        classifier.add_fuel_reading("TRUCK001", 75.0)
        classifier.add_fuel_reading("TRUCK001", 74.0)

        volatility = classifier.get_sensor_volatility("TRUCK001")
        assert volatility == 0.0

    def test_get_sensor_volatility_stable(self):
        """Should calculate low volatility for stable readings"""
        from alert_service import FuelEventClassifier

        classifier = FuelEventClassifier()
        # Add stable readings (small variations)
        for i in range(10):
            classifier.add_fuel_reading("TRUCK001", 75.0 + (i % 2) * 0.5)

        volatility = classifier.get_sensor_volatility("TRUCK001")
        assert volatility < 1.0  # Should be very low

    def test_get_sensor_volatility_unstable(self):
        """Should calculate high volatility for erratic readings"""
        from alert_service import FuelEventClassifier

        classifier = FuelEventClassifier()
        # Add erratic readings
        readings = [75, 50, 80, 45, 90, 30, 85]
        for r in readings:
            classifier.add_fuel_reading("TRUCK001", float(r))

        volatility = classifier.get_sensor_volatility("TRUCK001")
        assert volatility > 10.0  # Should be high

    def test_register_fuel_drop_buffers_drop(self):
        """Should buffer drop for recovery check"""
        from alert_service import FuelEventClassifier

        classifier = FuelEventClassifier()
        # Add some stable history first
        for i in range(10):
            classifier.add_fuel_reading("TRUCK001", 75.0 - i * 0.1)

        result = classifier.register_fuel_drop(
            truck_id="TRUCK001",
            fuel_before=75.0,
            fuel_after=55.0,
            tank_capacity_gal=200.0,
            truck_status="STOPPED",
        )

        # Should buffer the drop (return None)
        assert result is None
        assert "TRUCK001" in classifier._pending_drops

    def test_history_limit(self):
        """Should limit history per truck to max_history_per_truck"""
        from alert_service import FuelEventClassifier

        classifier = FuelEventClassifier()
        max_history = classifier._max_history_per_truck

        # Add more than max readings
        for i in range(max_history + 10):
            classifier.add_fuel_reading("TRUCK001", 75.0 - i * 0.1)

        assert len(classifier._fuel_history["TRUCK001"]) == max_history


class TestPendingFuelDrop:
    """Test PendingFuelDrop data class"""

    def test_pending_fuel_drop_creation(self):
        """Should create PendingFuelDrop with all fields"""
        from alert_service import PendingFuelDrop
        from datetime import datetime, timezone

        drop = PendingFuelDrop(
            truck_id="TRUCK001",
            drop_timestamp=datetime.now(timezone.utc),
            fuel_before=80.0,
            fuel_after=60.0,
            drop_pct=20.0,
            drop_gal=40.0,
            location="Highway 101",
            truck_status="STOPPED",
        )

        assert drop.truck_id == "TRUCK001"
        assert drop.drop_pct == 20.0
        assert drop.drop_gal == 40.0
        assert drop.location == "Highway 101"

    def test_pending_fuel_drop_age_minutes(self):
        """Should calculate age in minutes correctly"""
        from alert_service import PendingFuelDrop
        from datetime import datetime, timezone, timedelta

        # Create drop from 5 minutes ago
        five_min_ago = datetime.now(timezone.utc) - timedelta(minutes=5)

        drop = PendingFuelDrop(
            truck_id="TRUCK001",
            drop_timestamp=five_min_ago,
            fuel_before=80.0,
            fuel_after=60.0,
            drop_pct=20.0,
            drop_gal=40.0,
        )

        age = drop.age_minutes()
        assert 4.5 < age < 5.5  # Should be approximately 5 minutes
