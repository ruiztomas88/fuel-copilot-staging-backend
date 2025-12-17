"""
Tests for Alert Service - Fuel Event Classification v5.9.0

Tests cover:
- FuelEventClassifier
- PendingFuelDrop
- Sensor volatility tracking
- Recovery window logic
- Theft detection
- Refuel detection
"""

import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from dataclasses import dataclass

from alert_service import (
    FuelEventClassifier,
    PendingFuelDrop,
    get_fuel_classifier,
)


class TestPendingFuelDrop:
    """Tests for PendingFuelDrop dataclass"""

    def test_creation(self):
        """Should create pending drop"""
        now = datetime.now(timezone.utc)
        drop = PendingFuelDrop(
            truck_id="T001",
            drop_timestamp=now,
            fuel_before=80.0,
            fuel_after=50.0,
            drop_pct=30.0,
            drop_gal=60.0,
            location="Highway 95",
            truck_status="STOPPED",
        )

        assert drop.truck_id == "T001"
        assert drop.fuel_before == 80.0
        assert drop.drop_pct == 30.0

    def test_age_minutes(self):
        """Should calculate age in minutes"""
        past = datetime.now(timezone.utc) - timedelta(minutes=10)
        drop = PendingFuelDrop(
            truck_id="T001",
            drop_timestamp=past,
            fuel_before=80.0,
            fuel_after=50.0,
            drop_pct=30.0,
            drop_gal=60.0,
            location=None,
            truck_status="UNKNOWN",
        )

        age = drop.age_minutes()

        assert 9 <= age <= 11  # Allow small timing variance


class TestFuelEventClassifier:
    """Tests for FuelEventClassifier"""

    @pytest.fixture
    def classifier(self):
        return FuelEventClassifier()

    def test_creation_defaults(self, classifier):
        """Should create with default thresholds"""
        assert classifier.drop_threshold_pct > 0
        assert classifier.refuel_threshold_pct > 0
        assert classifier.recovery_window_minutes > 0

    def test_default_thresholds_from_env(self, classifier):
        """Should use env-based defaults"""
        # Thresholds come from env vars with defaults
        assert classifier.drop_threshold_pct == float(
            os.getenv("DROP_THRESHOLD_PCT", "10.0")
        )
        assert classifier.recovery_window_minutes == int(
            os.getenv("RECOVERY_WINDOW_MINUTES", "10")
        )


class TestFuelReadingTracking:
    """Tests for fuel reading tracking"""

    @pytest.fixture
    def classifier(self):
        return FuelEventClassifier()

    def test_add_fuel_reading(self, classifier):
        """Should track fuel reading"""
        classifier.add_fuel_reading("T001", 75.0)

        assert "T001" in classifier._fuel_history
        assert len(classifier._fuel_history["T001"]) == 1

    def test_multiple_readings(self, classifier):
        """Should track multiple readings"""
        classifier.add_fuel_reading("T001", 75.0)
        classifier.add_fuel_reading("T001", 74.5)
        classifier.add_fuel_reading("T001", 74.0)

        assert len(classifier._fuel_history["T001"]) == 3

    def test_readings_per_truck(self, classifier):
        """Should track readings per truck separately"""
        classifier.add_fuel_reading("T001", 75.0)
        classifier.add_fuel_reading("T002", 80.0)

        assert len(classifier._fuel_history["T001"]) == 1
        assert len(classifier._fuel_history["T002"]) == 1


class TestSensorVolatility:
    """Tests for sensor volatility calculation"""

    @pytest.fixture
    def classifier(self):
        return FuelEventClassifier()

    def test_volatility_insufficient_data(self, classifier):
        """Should return 0 for insufficient data"""
        classifier.add_fuel_reading("T001", 75.0)

        volatility = classifier.get_sensor_volatility("T001")

        assert volatility == 0.0

    def test_volatility_stable_sensor(self, classifier):
        """Should return low volatility for stable readings"""
        for _ in range(10):
            classifier.add_fuel_reading("T001", 75.0)

        volatility = classifier.get_sensor_volatility("T001")

        assert volatility == 0.0  # All same value

    def test_volatility_unstable_sensor(self, classifier):
        """Should return higher volatility for varying readings"""
        readings = [75.0, 70.0, 80.0, 72.0, 78.0, 71.0, 79.0, 73.0, 77.0, 74.0]
        for r in readings:
            classifier.add_fuel_reading("T001", r)

        volatility = classifier.get_sensor_volatility("T001")

        assert volatility > 0

    def test_volatility_unknown_truck(self, classifier):
        """Should return 0 for unknown truck"""
        volatility = classifier.get_sensor_volatility("UNKNOWN")

        assert volatility == 0.0


class TestFuelDropRegistration:
    """Tests for fuel drop registration"""

    @pytest.fixture
    def classifier(self):
        return FuelEventClassifier()

    def test_register_normal_drop(self, classifier):
        """Should buffer normal drop for monitoring"""
        result = classifier.register_fuel_drop(
            truck_id="T001",
            fuel_before=80.0,
            fuel_after=70.0,
            tank_capacity_gal=200.0,
            truck_status="STOPPED",
        )

        assert result is None  # Buffered, waiting
        assert "T001" in classifier._pending_drops

    def test_register_extreme_drop_theft(self, classifier):
        """Should immediately classify extreme drop as theft"""
        result = classifier.register_fuel_drop(
            truck_id="T001",
            fuel_before=80.0,
            fuel_after=40.0,  # 40% drop
            tank_capacity_gal=200.0,
            truck_status="STOPPED",
        )

        assert result == "IMMEDIATE_THEFT"


class TestRecoveryCheck:
    """Tests for recovery check logic"""

    @pytest.fixture
    def classifier(self):
        return FuelEventClassifier()

    def test_check_recovery_no_pending(self, classifier):
        """Should return None if no pending drop"""
        result = classifier.check_recovery("T001", 75.0)

        assert result is None

    def test_check_recovery_too_soon(self, classifier):
        """Should return None if not enough time passed"""
        classifier.register_fuel_drop(
            truck_id="T001",
            fuel_before=80.0,
            fuel_after=70.0,
            tank_capacity_gal=200.0,
            truck_status="STOPPED",
        )

        # Check immediately (< recovery window)
        result = classifier.check_recovery("T001", 70.0)

        assert result is None  # Still waiting

    def test_check_recovery_sensor_issue(self, classifier):
        """Should classify as sensor issue if fuel recovered"""
        # Manually create old pending drop
        classifier._pending_drops["T001"] = PendingFuelDrop(
            truck_id="T001",
            drop_timestamp=datetime.now(timezone.utc) - timedelta(minutes=30),
            fuel_before=80.0,
            fuel_after=70.0,
            drop_pct=10.0,
            drop_gal=20.0,
            location=None,
            truck_status="STOPPED",
        )

        # Fuel recovered to near-original
        result = classifier.check_recovery("T001", 79.0)

        assert result is not None
        assert result["classification"] == "SENSOR_ISSUE"

    def test_check_recovery_theft_confirmed(self, classifier):
        """Should classify as theft if fuel stayed low"""
        classifier._pending_drops["T001"] = PendingFuelDrop(
            truck_id="T001",
            drop_timestamp=datetime.now(timezone.utc) - timedelta(minutes=10),
            fuel_before=80.0,
            fuel_after=60.0,
            drop_pct=20.0,
            drop_gal=40.0,
            location=None,
            truck_status="STOPPED",
        )

        # Fuel still at drop level
        result = classifier.check_recovery("T001", 60.0)

        assert result is not None
        assert result["classification"] == "THEFT_CONFIRMED"


class TestProcessFuelReading:
    """Tests for main process_fuel_reading method"""

    @pytest.fixture
    def classifier(self):
        return FuelEventClassifier()

    def test_detect_refuel(self, classifier):
        """Should detect refuel events"""
        result = classifier.process_fuel_reading(
            truck_id="T001",
            last_fuel_pct=50.0,
            current_fuel_pct=90.0,  # +40% increase
            tank_capacity_gal=200.0,
        )

        assert result is not None
        assert result["classification"] == "REFUEL"

    def test_detect_drop(self, classifier):
        """Should detect and buffer drops"""
        result = classifier.process_fuel_reading(
            truck_id="T001",
            last_fuel_pct=80.0,
            current_fuel_pct=70.0,  # 10% drop
            tank_capacity_gal=200.0,
            truck_status="STOPPED",
        )

        assert result is not None
        assert result["classification"] == "PENDING_VERIFICATION"

    def test_no_event_normal_consumption(self, classifier):
        """Should return None for normal consumption"""
        result = classifier.process_fuel_reading(
            truck_id="T001",
            last_fuel_pct=80.0,
            current_fuel_pct=79.0,  # 1% normal consumption
            tank_capacity_gal=200.0,
        )

        assert result is None


class TestGetPendingDrops:
    """Tests for get_pending_drops method"""

    @pytest.fixture
    def classifier(self):
        return FuelEventClassifier()

    def test_get_pending_empty(self, classifier):
        """Should return empty list when none pending"""
        result = classifier.get_pending_drops()

        assert result == []

    def test_get_pending_with_drops(self, classifier):
        """Should return pending drops"""
        classifier.register_fuel_drop(
            truck_id="T001",
            fuel_before=80.0,
            fuel_after=70.0,
            tank_capacity_gal=200.0,
            truck_status="STOPPED",
        )

        result = classifier.get_pending_drops()

        assert len(result) == 1
        assert result[0].truck_id == "T001"


class TestForceClassifyPending:
    """Tests for force_classify_pending method"""

    @pytest.fixture
    def classifier(self):
        return FuelEventClassifier()

    def test_force_classify_no_pending(self, classifier):
        """Should return None if no pending drop"""
        result = classifier.force_classify_pending("T001", 75.0)

        assert result is None

    def test_force_classify_with_pending(self, classifier):
        """Should classify pending drop immediately"""
        classifier._pending_drops["T001"] = PendingFuelDrop(
            truck_id="T001",
            drop_timestamp=datetime.now(timezone.utc),
            fuel_before=80.0,
            fuel_after=60.0,
            drop_pct=20.0,
            drop_gal=40.0,
            location=None,
            truck_status="STOPPED",
        )

        result = classifier.force_classify_pending("T001", 60.0)

        assert result is not None


class TestGetFuelClassifierSingleton:
    """Tests for get_fuel_classifier singleton"""

    def test_returns_instance(self):
        """Should return classifier instance"""
        classifier = get_fuel_classifier()

        assert isinstance(classifier, FuelEventClassifier)

    def test_returns_same_instance(self):
        """Should return same instance on multiple calls"""
        c1 = get_fuel_classifier()
        c2 = get_fuel_classifier()

        assert c1 is c2


class TestClassifierThresholds:
    """Tests for classifier threshold values"""

    def test_default_drop_threshold(self):
        """Should have reasonable drop threshold"""
        classifier = FuelEventClassifier()

        assert 3.0 <= classifier.drop_threshold_pct <= 15.0

    def test_default_refuel_threshold(self):
        """Should have reasonable refuel threshold"""
        classifier = FuelEventClassifier()

        assert 5.0 <= classifier.refuel_threshold_pct <= 20.0

    def test_default_recovery_window(self):
        """Should have reasonable recovery window"""
        classifier = FuelEventClassifier()

        assert 5 <= classifier.recovery_window_minutes <= 30


class TestVolatilityThreshold:
    """Tests for sensor volatility threshold"""

    def test_volatility_threshold_exists(self):
        """Should have volatility threshold"""
        classifier = FuelEventClassifier()

        assert hasattr(classifier, "sensor_volatility_threshold")
        assert classifier.sensor_volatility_threshold > 0


class TestRecoveryTolerance:
    """Tests for recovery tolerance"""

    def test_recovery_tolerance_exists(self):
        """Should have recovery tolerance"""
        classifier = FuelEventClassifier()

        assert hasattr(classifier, "recovery_tolerance_pct")
        assert classifier.recovery_tolerance_pct > 0


class TestFuelDropFields:
    """Tests for PendingFuelDrop fields"""

    def test_all_required_fields(self):
        """Should have all required fields"""
        now = datetime.now(timezone.utc)
        drop = PendingFuelDrop(
            truck_id="T001",
            drop_timestamp=now,
            fuel_before=80.0,
            fuel_after=60.0,
            drop_pct=20.0,
            drop_gal=40.0,
            location="Test Location",
            truck_status="STOPPED",
        )

        assert drop.truck_id is not None
        assert drop.drop_timestamp is not None
        assert drop.fuel_before is not None
        assert drop.fuel_after is not None
        assert drop.drop_pct is not None
        assert drop.drop_gal is not None

    def test_optional_location(self):
        """Location can be None"""
        now = datetime.now(timezone.utc)
        drop = PendingFuelDrop(
            truck_id="T001",
            drop_timestamp=now,
            fuel_before=80.0,
            fuel_after=60.0,
            drop_pct=20.0,
            drop_gal=40.0,
            location=None,
            truck_status="STOPPED",
        )

        assert drop.location is None


class TestClassificationResults:
    """Tests for classification result formats"""

    @pytest.fixture
    def classifier(self):
        return FuelEventClassifier()

    def test_refuel_result_format(self, classifier):
        """Refuel result should have required fields"""
        result = classifier.process_fuel_reading(
            truck_id="T001",
            last_fuel_pct=50.0,
            current_fuel_pct=90.0,
            tank_capacity_gal=200.0,
        )

        assert "classification" in result
        assert "truck_id" in result
        assert "increase_pct" in result

    def test_pending_result_format(self, classifier):
        """Pending verification should have required fields"""
        result = classifier.process_fuel_reading(
            truck_id="T001",
            last_fuel_pct=80.0,
            current_fuel_pct=70.0,
            tank_capacity_gal=200.0,
            truck_status="STOPPED",
        )

        assert "classification" in result
        assert "truck_id" in result


class TestMultipleTrucks:
    """Tests for handling multiple trucks"""

    @pytest.fixture
    def classifier(self):
        return FuelEventClassifier()

    def test_independent_pending_drops(self, classifier):
        """Each truck should have independent pending drops"""
        classifier.register_fuel_drop("T001", 80.0, 70.0, 200.0, "STOPPED")
        classifier.register_fuel_drop("T002", 90.0, 80.0, 200.0, "STOPPED")

        assert "T001" in classifier._pending_drops
        assert "T002" in classifier._pending_drops
        assert classifier._pending_drops["T001"].fuel_before == 80.0
        assert classifier._pending_drops["T002"].fuel_before == 90.0

    def test_independent_volatility_tracking(self, classifier):
        """Each truck should have independent volatility"""
        for _ in range(10):
            classifier.add_fuel_reading("T001", 75.0)

        for v in [70.0, 80.0, 65.0, 85.0, 60.0]:
            classifier.add_fuel_reading("T002", v)

        v1 = classifier.get_sensor_volatility("T001")
        v2 = classifier.get_sensor_volatility("T002")

        assert v1 < v2  # T001 stable, T002 volatile


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
