"""
Alert Service Comprehensive Coverage Test
Target: Bring alert_service.py from 33.63% to 90%+
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from alert_service import (
    FuelEventClassifier,
    PendingFuelDrop,
    get_fuel_classifier,
    send_low_fuel_alert,
    send_theft_alert,
)


class TestFuelEventClassifierComplete:
    """Comprehensive tests for FuelEventClassifier"""

    def setup_method(self):
        """Setup for each test"""
        self.classifier = FuelEventClassifier()

    def test_add_fuel_reading(self):
        """Test adding fuel readings for history"""
        self.classifier.add_fuel_reading("T001", 80.0)
        self.classifier.add_fuel_reading("T001", 79.5)
        self.classifier.add_fuel_reading("T001", 80.2)

        assert "T001" in self.classifier._fuel_history
        assert len(self.classifier._fuel_history["T001"]) == 3

    def test_get_sensor_volatility_low(self):
        """Test volatility calculation with stable readings"""
        for val in [80.0, 80.1, 79.9, 80.2, 80.0]:
            self.classifier.add_fuel_reading("T001", val)

        volatility = self.classifier.get_sensor_volatility("T001")
        assert volatility < 1.0  # Low volatility

    def test_get_sensor_volatility_high(self):
        """Test volatility calculation with erratic readings"""
        for val in [80.0, 70.0, 90.0, 65.0, 85.0, 75.0]:
            self.classifier.add_fuel_reading("T002", val)

        volatility = self.classifier.get_sensor_volatility("T002")
        assert volatility > 5.0  # High volatility

    def test_register_fuel_drop_normal(self):
        """Test registering a normal fuel drop"""
        result = self.classifier.register_fuel_drop(
            truck_id="T003",
            fuel_before=80.0,
            fuel_after=70.0,
            location="Highway 101",
            truck_status="MOVING",
        )

        # Should be buffered (None returned)
        assert result is None or result == "IMMEDIATE_THEFT"
        assert "T003" in self.classifier._pending_drops

    def test_register_extreme_theft(self):
        """Test extreme drop while stopped (immediate theft)"""
        result = self.classifier.register_fuel_drop(
            truck_id="T004",
            fuel_before=90.0,
            fuel_after=45.0,  # 45% drop
            location="Parking Lot",
            truck_status="STOPPED",
        )

        assert result == "IMMEDIATE_THEFT"

    def test_check_recovery_sensor_issue(self):
        """Test recovery check - sensor issue path"""
        now = datetime.now(timezone.utc)
        self.classifier._pending_drops["T005"] = PendingFuelDrop(
            truck_id="T005",
            drop_timestamp=now - timedelta(minutes=15),
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="MOVING",
        )

        # Fuel recovered
        result = self.classifier.check_recovery("T005", 79.0)

        assert result is not None
        assert result["classification"] == "SENSOR_ISSUE"

    def test_check_recovery_refuel_after_drop(self):
        """Test recovery check - refuel after drop"""
        now = datetime.now(timezone.utc)
        self.classifier._pending_drops["T006"] = PendingFuelDrop(
            truck_id="T006",
            drop_timestamp=now - timedelta(minutes=15),
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="MOVING",
        )

        # Fuel increased (refueled)
        result = self.classifier.check_recovery("T006", 90.0)

        assert result is not None
        assert result["classification"] == "REFUEL_AFTER_DROP"

    def test_check_recovery_theft_confirmed(self):
        """Test recovery check - theft confirmed"""
        now = datetime.now(timezone.utc)
        self.classifier._pending_drops["T007"] = PendingFuelDrop(
            truck_id="T007",
            drop_timestamp=now - timedelta(minutes=15),
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="STOPPED",
        )

        # Fuel stayed low
        result = self.classifier.check_recovery("T007", 66.0)

        assert result is not None
        assert result["classification"] == "THEFT_CONFIRMED"

    def test_check_recovery_too_soon(self):
        """Test check recovery called too early"""
        now = datetime.now(timezone.utc)
        self.classifier._pending_drops["T008"] = PendingFuelDrop(
            truck_id="T008",
            drop_timestamp=now - timedelta(minutes=1),
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="MOVING",
        )

        result = self.classifier.check_recovery("T008", 79.0)
        assert result is None  # Still waiting

    def test_cleanup_stale_drops(self):
        """Test cleanup of old pending drops"""
        now = datetime.now(timezone.utc)

        # Add very old drop
        self.classifier._pending_drops["T_OLD"] = PendingFuelDrop(
            truck_id="T_OLD",
            drop_timestamp=now - timedelta(hours=25),
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="MOVING",
        )

        # Add recent drop
        self.classifier._pending_drops["T_NEW"] = PendingFuelDrop(
            truck_id="T_NEW",
            drop_timestamp=now - timedelta(minutes=5),
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="MOVING",
        )

        self.classifier.cleanup_stale_drops(max_age_hours=24.0)

        assert "T_OLD" not in self.classifier._pending_drops
        assert "T_NEW" in self.classifier._pending_drops


class TestGlobalFunctions:
    """Test module-level functions"""

    def test_get_fuel_classifier(self):
        """Test singleton accessor"""
        classifier1 = get_fuel_classifier()
        classifier2 = get_fuel_classifier()

        assert classifier1 is classifier2  # Same instance


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=alert_service", "--cov-report=term-missing"])
