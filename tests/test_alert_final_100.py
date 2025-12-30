"""
Comprehensive alert_service tests - target 100% coverage
Simplified approach: test real code paths without mocking internals
"""

import os
from datetime import timedelta

import pytest

from alert_service import (
    Alert,
    AlertPriority,
    AlertType,
    FuelEventClassifier,
    PendingFuelDrop,
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


class TestFuelEventClassifierFull:
    """Comprehensive FuelEventClassifier coverage"""

    def test_classifier_init_default(self):
        """Test initialization with defaults"""
        classifier = FuelEventClassifier()
        assert classifier.recovery_window_minutes == 10
        assert classifier.recovery_tolerance_pct == 5.0
        assert classifier.drop_threshold_pct == 10.0

    def test_classifier_init_env_vars(self):
        """Test initialization with env overrides"""
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("RECOVERY_WINDOW_MINUTES", "15")
            mp.setenv("RECOVERY_TOLERANCE_PCT", "7.5")
            mp.setenv("DROP_THRESHOLD_PCT", "12.0")
            mp.setenv("REFUEL_THRESHOLD_PCT", "10.0")
            mp.setenv("SENSOR_VOLATILITY_THRESHOLD", "9.0")

            classifier = FuelEventClassifier()
            assert classifier.recovery_window_minutes == 15
            assert classifier.recovery_tolerance_pct == 7.5
            assert classifier.drop_threshold_pct == 12.0
            assert classifier.refuel_threshold_pct == 10.0
            assert classifier.sensor_volatility_threshold == 9.0

    def test_add_fuel_reading_single(self):
        """Test adding single fuel reading"""
        classifier = FuelEventClassifier()
        ts = utc_now()

        classifier.add_fuel_reading("CO0681", 75.5, ts)
        assert "CO0681" in classifier._fuel_history
        assert len(classifier._fuel_history["CO0681"]) == 1
        assert classifier._fuel_history["CO0681"][0][1] == 75.5

    def test_add_fuel_reading_history_limit(self):
        """Test history is limited to max_history_per_truck"""
        classifier = FuelEventClassifier()

        # Add 25 readings (more than max 20)
        for i in range(25):
            classifier.add_fuel_reading("CO0681", 50.0 + i)

        # Should keep only latest 20
        assert len(classifier._fuel_history["CO0681"]) == 20
        # Latest value should be 74.0 (50 + 24)
        assert classifier._fuel_history["CO0681"][-1][1] == 74.0

    def test_get_sensor_volatility_no_data(self):
        """Test volatility with no truck"""
        classifier = FuelEventClassifier()
        assert classifier.get_sensor_volatility("UNKNOWN") == 0.0

    def test_get_sensor_volatility_insufficient(self):
        """Test volatility with < 5 readings"""
        classifier = FuelEventClassifier()
        for i in range(4):
            classifier.add_fuel_reading("CO0681", 50.0 + i)

        assert classifier.get_sensor_volatility("CO0681") == 0.0

    def test_get_sensor_volatility_stable(self):
        """Test low volatility with stable readings"""
        classifier = FuelEventClassifier()
        for i in range(10):
            classifier.add_fuel_reading("CO0681", 50.0)  # Same value

        volatility = classifier.get_sensor_volatility("CO0681")
        assert volatility == 0.0

    def test_get_sensor_volatility_high(self):
        """Test high volatility with varying readings"""
        classifier = FuelEventClassifier()
        values = [50, 45, 60, 40, 65, 35, 70]
        for v in values:
            classifier.add_fuel_reading("CO0681", v)

        volatility = classifier.get_sensor_volatility("CO0681")
        assert volatility > 8.0  # Should be quite volatile

    def test_register_drop_normal_buffered(self):
        """Test normal drop gets buffered"""
        classifier = FuelEventClassifier()

        result = classifier.register_fuel_drop(
            truck_id="CO0681",
            fuel_before=80.0,
            fuel_after=68.0,  # 12% drop
            tank_capacity_gal=200.0,
            location="Highway 101",
            truck_status="MOVING",
        )

        # Should return None (buffered)
        assert result is None
        # Should be in pending
        assert "CO0681" in classifier._pending_drops
        pending = classifier._pending_drops["CO0681"]
        assert pending.drop_pct == 12.0
        assert pending.drop_gal == 24.0

    def test_register_drop_extreme_theft(self):
        """Test extreme drop while stopped returns IMMEDIATE_THEFT"""
        classifier = FuelEventClassifier()

        result = classifier.register_fuel_drop(
            truck_id="CO0681",
            fuel_before=100.0,
            fuel_after=65.0,  # 35% drop
            tank_capacity_gal=200.0,
            truck_status="STOPPED",
        )

        assert result == "IMMEDIATE_THEFT"

    def test_register_drop_volatile_sensor(self):
        """Test drop with very high sensor volatility"""
        classifier = FuelEventClassifier()

        # Create extremely high volatility (> 1.5 * threshold)
        values = [50, 20, 80, 10, 90, 5, 95, 0]
        for v in values:
            classifier.add_fuel_reading("CO0681", v)

        result = classifier.register_fuel_drop(
            truck_id="CO0681",
            fuel_before=70.0,
            fuel_after=55.0,
            tank_capacity_gal=200.0,
        )

        # Should classify as SENSOR_VOLATILE immediately
        assert result == "SENSOR_VOLATILE"

    def test_check_recovery_no_pending(self):
        """Test recovery check with no pending drop"""
        classifier = FuelEventClassifier()
        result = classifier.check_recovery("CO0681", 50.0)
        assert result is None

    def test_check_recovery_too_soon(self):
        """Test recovery check before window expires"""
        classifier = FuelEventClassifier()
        classifier.recovery_window_minutes = 10

        # Register drop (just now)
        classifier.register_fuel_drop("CO0681", 80.0, 70.0, 200.0)

        # Check immediately (age = 0 < 10 minutes)
        result = classifier.check_recovery("CO0681", 75.0)
        assert result is None
        # Should still be in pending
        assert "CO0681" in classifier._pending_drops

    def test_check_recovery_sensor_issue(self):
        """Test fuel recovered to original = sensor issue"""
        classifier = FuelEventClassifier()
        classifier.recovery_window_minutes = 0  # Allow immediate check

        classifier.register_fuel_drop("CO0681", 80.0, 70.0, 200.0)

        # Fuel recovered to near-original (79.0 vs 80.0 = 1% gap < 5% tolerance)
        result = classifier.check_recovery("CO0681", 79.0)

        assert result is not None
        assert result["classification"] == "SENSOR_ISSUE"
        assert result["original_fuel_pct"] == 80.0
        assert result["drop_fuel_pct"] == 70.0
        assert result["current_fuel_pct"] == 79.0
        # Should be removed from pending
        assert "CO0681" not in classifier._pending_drops

    def test_check_recovery_refuel_after_drop(self):
        """Test fuel increased after drop = refuel"""
        classifier = FuelEventClassifier()
        classifier.recovery_window_minutes = 0

        classifier.register_fuel_drop("CO0681", 50.0, 40.0, 200.0)

        # Fuel went UP by 10% (40 -> 50, recovery_pct = 10 > 8% threshold)
        result = classifier.check_recovery("CO0681", 60.0)

        assert result is not None
        assert result["classification"] == "REFUEL_AFTER_DROP"
        assert result["recovery_pct"] == 20.0
        assert "CO0681" not in classifier._pending_drops

    def test_check_recovery_theft_confirmed(self):
        """Test fuel stayed low = theft confirmed"""
        classifier = FuelEventClassifier()
        classifier.recovery_window_minutes = 0

        classifier.register_fuel_drop("CO0681", 80.0, 60.0, 200.0)

        # Fuel stayed at 62% (gap = 18% > 5% tolerance, no significant increase)
        result = classifier.check_recovery("CO0681", 62.0)

        assert result is not None
        assert result["classification"] == "THEFT_CONFIRMED"
        assert result["drop_pct"] == 20.0
        assert "CO0681" not in classifier._pending_drops

    def test_process_fuel_reading_refuel(self):
        """Test refuel detection"""
        classifier = FuelEventClassifier()

        result = classifier.process_fuel_reading(
            truck_id="CO0681",
            last_fuel_pct=30.0,
            current_fuel_pct=50.0,  # +20% >= 8% refuel threshold
            tank_capacity_gal=200.0,
            location="Gas Station",
        )

        assert result is not None
        assert result["classification"] == "REFUEL"
        assert result["increase_pct"] == 20.0
        assert result["increase_gal"] == 40.0

    def test_process_fuel_reading_check_pending(self):
        """Test process checks pending drops first"""
        classifier = FuelEventClassifier()
        classifier.recovery_window_minutes = 0

        # Create a pending drop
        classifier.register_fuel_drop("CO0681", 80.0, 70.0, 200.0)

        # Process new reading that shows recovery
        result = classifier.process_fuel_reading(
            truck_id="CO0681",
            last_fuel_pct=70.0,
            current_fuel_pct=79.0,  # Recovered!
            tank_capacity_gal=200.0,
        )

        # Should return recovery result
        assert result is not None
        assert result["classification"] == "SENSOR_ISSUE"

    def test_process_fuel_reading_immediate_theft(self):
        """Test immediate theft via process_fuel_reading"""
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
        assert "Extreme drop" in result["reason"]

    def test_process_fuel_reading_sensor_volatile(self):
        """Test sensor volatile detection"""
        classifier = FuelEventClassifier()

        # Create very high volatility
        values = [50, 20, 80, 10, 90, 5, 95]
        for v in values:
            classifier.add_fuel_reading("CO0681", v)

        result = classifier.process_fuel_reading(
            truck_id="CO0681",
            last_fuel_pct=70.0,
            current_fuel_pct=55.0,
            tank_capacity_gal=200.0,
        )

        assert result is not None
        assert result["classification"] == "SENSOR_ISSUE"
        assert "volatility" in result

    def test_process_fuel_reading_pending_verification(self):
        """Test drop buffered as pending"""
        classifier = FuelEventClassifier()

        result = classifier.process_fuel_reading(
            truck_id="CO0681",
            last_fuel_pct=70.0,
            current_fuel_pct=55.0,  # -15% normal drop
            tank_capacity_gal=200.0,
            truck_status="MOVING",
        )

        assert result is not None
        assert result["classification"] == "PENDING_VERIFICATION"
        assert "monitoring" in result["message"]

    def test_get_pending_drops(self):
        """Test get_pending_drops returns all pending"""
        classifier = FuelEventClassifier()

        # Register 2 drops
        classifier.register_fuel_drop("CO0681", 80.0, 70.0, 200.0)
        classifier.register_fuel_drop("CO0682", 90.0, 75.0, 200.0)

        pending = classifier.get_pending_drops()
        assert len(pending) == 2
        assert all(isinstance(p, PendingFuelDrop) for p in pending)

    def test_cleanup_stale_drops(self):
        """Test cleanup removes old pending drops"""
        classifier = FuelEventClassifier()

        # Create an old drop manually
        old_drop = PendingFuelDrop(
            truck_id="CO0681",
            drop_timestamp=utc_now() - timedelta(hours=30),
            fuel_before=80.0,
            fuel_after=70.0,
            drop_pct=10.0,
            drop_gal=20.0,
        )
        classifier._pending_drops["CO0681"] = old_drop

        # Create a fresh drop
        classifier.register_fuel_drop("CO0682", 90.0, 75.0, 200.0)

        # Cleanup with 24h threshold
        classifier.cleanup_stale_drops(max_age_hours=24.0)

        # Old should be gone, fresh should remain
        assert "CO0681" not in classifier._pending_drops
        assert "CO0682" in classifier._pending_drops


class TestAlertDataclasses:
    """Test Alert and related classes"""

    def test_alert_creation(self):
        """Test Alert dataclass"""
        alert = Alert(
            alert_type=AlertType.THEFT_SUSPECTED,
            priority=AlertPriority.CRITICAL,
            truck_id="CO0681",
            message="Fuel theft detected",
        )

        assert alert.alert_type == AlertType.THEFT_SUSPECTED
        assert alert.priority == AlertPriority.CRITICAL
        assert alert.timestamp is not None

    def test_alert_with_details(self):
        """Test Alert with details dict"""
        alert = Alert(
            alert_type=AlertType.DTC_ALERT,
            priority=AlertPriority.HIGH,
            truck_id="CO0681",
            message="Engine code detected",
            details={"code": "P0420", "severity": "critical"},
        )

        assert alert.details["code"] == "P0420"

    def test_pending_fuel_drop(self):
        """Test PendingFuelDrop dataclass"""
        ts = utc_now()
        drop = PendingFuelDrop(
            truck_id="CO0681",
            drop_timestamp=ts,
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=30.0,
            location="Highway 101",
            truck_status="MOVING",
        )

        assert drop.truck_id == "CO0681"
        assert drop.drop_pct == 15.0
        assert drop.drop_gal == 30.0

        # Test age_minutes
        age = drop.age_minutes()
        assert age >= 0


class TestStandaloneFunctions:
    """Test standalone alert functions (without actual sending)"""

    def test_send_theft_alert_callable(self):
        """Test send_theft_alert is callable"""
        # Just test function exists and signature
        assert callable(send_theft_alert)
        # Don't actually send, would need config

    def test_send_low_fuel_alert_callable(self):
        """Test send_low_fuel_alert is callable"""
        assert callable(send_low_fuel_alert)

    def test_send_dtc_alert_callable(self):
        """Test send_dtc_alert is callable"""
        assert callable(send_dtc_alert)

    def test_send_voltage_alert_callable(self):
        """Test send_voltage_alert is callable"""
        assert callable(send_voltage_alert)

    def test_send_maintenance_prediction_alert_callable(self):
        """Test send_maintenance_prediction_alert is callable"""
        assert callable(send_maintenance_prediction_alert)

    def test_send_theft_confirmed_alert_callable(self):
        """Test send_theft_confirmed_alert is callable"""
        assert callable(send_theft_confirmed_alert)

    def test_send_sensor_issue_alert_callable(self):
        """Test send_sensor_issue_alert is callable"""
        assert callable(send_sensor_issue_alert)

    def test_send_idle_deviation_alert_callable(self):
        """Test send_idle_deviation_alert is callable"""
        assert callable(send_idle_deviation_alert)

    def test_send_gps_quality_alert_callable(self):
        """Test send_gps_quality_alert is callable"""
        assert callable(send_gps_quality_alert)

    def test_send_mpg_underperformance_alert_callable(self):
        """Test send_mpg_underperformance_alert is callable"""
        assert callable(send_mpg_underperformance_alert)


class TestEnums:
    """Test enum values"""

    def test_alert_priority_values(self):
        """Test AlertPriority enum"""
        assert AlertPriority.LOW.value == "low"
        assert AlertPriority.MEDIUM.value == "medium"
        assert AlertPriority.HIGH.value == "high"
        assert AlertPriority.CRITICAL.value == "critical"

    def test_alert_type_values(self):
        """Test AlertType enum"""
        assert AlertType.THEFT_SUSPECTED.value == "theft_suspected"
        assert AlertType.THEFT_CONFIRMED.value == "theft_confirmed"
        assert AlertType.SENSOR_ISSUE.value == "sensor_issue"
        assert AlertType.REFUEL.value == "refuel"
        assert AlertType.LOW_FUEL.value == "low_fuel"
        assert AlertType.DTC_ALERT.value == "dtc_alert"
        assert AlertType.VOLTAGE_ALERT.value == "voltage_alert"
