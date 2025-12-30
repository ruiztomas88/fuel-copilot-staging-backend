"""
Comprehensive tests for FuelEventClassifier - targeting 100% coverage
"""

from datetime import timedelta

import pytest

from alert_service import FuelEventClassifier, PendingFuelDrop
from timezone_utils import utc_now


class TestFuelEventClassifier:
    """Test FuelEventClassifier functionality"""

    def test_high_sensor_volatility_immediate_classification(self):
        """Test that very high volatility triggers immediate SENSOR_VOLATILE"""
        classifier = FuelEventClassifier()
        truck_id = "TRUCK_VOL_001"

        # Simulate VERY high volatility by adding extremely erratic readings
        # Need volatility > threshold * 1.5 = 8.0 * 1.5 = 12.0
        readings = [30.0, 70.0, 25.0, 75.0, 28.0, 72.0, 26.0, 74.0, 29.0, 73.0]
        for reading in readings:
            classifier.add_fuel_reading(truck_id, reading)

        # Verify volatility is very high
        volatility = classifier.get_sensor_volatility(truck_id)
        assert volatility > classifier.sensor_volatility_threshold * 1.5

        # Register a fuel drop - should classify immediately as SENSOR_VOLATILE
        result = classifier.register_fuel_drop(
            truck_id=truck_id,
            fuel_before=80.0,
            fuel_after=60.0,
            tank_capacity_gal=200.0,
        )

        # Should return SENSOR_VOLATILE since volatility is extreme
        assert result == "SENSOR_VOLATILE"

    def test_extreme_theft_immediate_classification(self):
        """Test that extreme drops while stopped classify as IMMEDIATE_THEFT"""
        classifier = FuelEventClassifier()

        result = classifier.register_fuel_drop(
            truck_id="TRUCK_THEFT_001",
            fuel_before=85.0,
            fuel_after=50.0,  # 35% drop > 30% threshold
            tank_capacity_gal=200.0,
            truck_status="STOPPED",
        )

        assert result == "IMMEDIATE_THEFT"

    def test_pending_drop_recovery_sensor_issue(self):
        """Test that recovered fuel is classified as SENSOR_ISSUE"""
        classifier = FuelEventClassifier()
        truck_id = "TRUCK_REC_001"

        # Register a drop
        classifier.register_fuel_drop(
            truck_id=truck_id,
            fuel_before=90.0,
            fuel_after=75.0,
            tank_capacity_gal=200.0,
        )

        # Verify it's pending
        assert truck_id in classifier._pending_drops

        # Simulate time passing
        pending = classifier._pending_drops[truck_id]
        pending.drop_timestamp = utc_now() - timedelta(minutes=12)

        # Check recovery with fuel restored to near-original
        result = classifier.check_recovery(truck_id, current_fuel_pct=89.0)

        assert result is not None
        assert result["classification"] == "SENSOR_ISSUE"
        assert truck_id not in classifier._pending_drops  # Should be removed

    def test_pending_drop_no_recovery_theft_confirmed(self):
        """Test that non-recovered fuel is classified as THEFT_CONFIRMED"""
        classifier = FuelEventClassifier()
        truck_id = "TRUCK_THEFT_002"

        # Register a drop
        classifier.register_fuel_drop(
            truck_id=truck_id,
            fuel_before=95.0,
            fuel_after=65.0,
            tank_capacity_gal=200.0,
        )

        # Simulate time passing
        pending = classifier._pending_drops[truck_id]
        pending.drop_timestamp = utc_now() - timedelta(minutes=15)

        # Check recovery with fuel still low
        result = classifier.check_recovery(truck_id, current_fuel_pct=66.0)

        assert result is not None
        assert result["classification"] == "THEFT_CONFIRMED"
        assert truck_id not in classifier._pending_drops

    def test_pending_drop_refuel_after_drop(self):
        """Test that refuel after drop is classified as REFUEL_AFTER_DROP"""
        classifier = FuelEventClassifier()
        truck_id = "TRUCK_REF_001"

        # Register a drop
        classifier.register_fuel_drop(
            truck_id=truck_id,
            fuel_before=80.0,
            fuel_after=60.0,
            tank_capacity_gal=200.0,
        )

        # Simulate time passing
        pending = classifier._pending_drops[truck_id]
        pending.drop_timestamp = utc_now() - timedelta(minutes=11)

        # Check recovery with fuel refueled (increased significantly)
        # Need increase > refuel_threshold_pct (8.0%) from fuel_after (60.0)
        # So current_fuel_pct > 68.0
        result = classifier.check_recovery(truck_id, current_fuel_pct=70.0)

        assert result is not None
        assert result["classification"] == "REFUEL_AFTER_DROP"

    def test_check_recovery_not_enough_time(self):
        """Test that check_recovery returns None if not enough time has passed"""
        classifier = FuelEventClassifier()
        truck_id = "TRUCK_TIME_001"

        # Register a drop
        classifier.register_fuel_drop(
            truck_id=truck_id,
            fuel_before=85.0,
            fuel_after=70.0,
            tank_capacity_gal=200.0,
        )

        # Simulate only 5 minutes passing (less than recovery window of 10)
        pending = classifier._pending_drops[truck_id]
        pending.drop_timestamp = utc_now() - timedelta(minutes=5)

        # Check recovery - should return None (not enough time)
        result = classifier.check_recovery(truck_id, current_fuel_pct=85.0)

        assert result is None
        assert truck_id in classifier._pending_drops  # Should still be pending

    def test_check_recovery_no_pending_drop(self):
        """Test that check_recovery returns None if no pending drop exists"""
        classifier = FuelEventClassifier()

        result = classifier.check_recovery("NONEXISTENT_TRUCK", current_fuel_pct=50.0)

        assert result is None

    def test_process_fuel_reading_refuel_detection(self):
        """Test that process_fuel_reading detects refuels"""
        classifier = FuelEventClassifier()
        truck_id = "TRUCK_REFUEL_002"

        result = classifier.process_fuel_reading(
            truck_id=truck_id,
            last_fuel_pct=30.0,
            current_fuel_pct=85.0,  # Large increase
            tank_capacity_gal=200.0,
        )

        assert result is not None
        assert result["classification"] == "REFUEL"
        assert result["increase_pct"] == 55.0

    def test_cleanup_stale_drops(self):
        """Test that cleanup_stale_drops removes old pending drops"""
        classifier = FuelEventClassifier()

        # Create a stale pending drop
        truck_id = "TRUCK_STALE_001"
        classifier.register_fuel_drop(
            truck_id=truck_id,
            fuel_before=95.0,
            fuel_after=75.0,
            tank_capacity_gal=200.0,
        )

        # Make it very old (older than 24 hours)
        pending = classifier._pending_drops[truck_id]
        pending.drop_timestamp = utc_now() - timedelta(hours=30)

        # Cleanup with default 24 hour threshold
        classifier.cleanup_stale_drops()

        # Should be removed
        assert truck_id not in classifier._pending_drops

    def test_cleanup_stale_drops_keeps_recent(self):
        """Test that cleanup_stale_drops keeps recent pending drops"""
        classifier = FuelEventClassifier()

        # Create a recent pending drop
        truck_id = "TRUCK_RECENT_001"
        classifier.register_fuel_drop(
            truck_id=truck_id,
            fuel_before=90.0,
            fuel_after=70.0,
            tank_capacity_gal=200.0,
        )

        # Cleanup
        classifier.cleanup_stale_drops()

        # Should still be there (not stale)
        assert truck_id in classifier._pending_drops

    def test_force_classify_pending(self):
        """Test force_classify_pending for manual intervention"""
        classifier = FuelEventClassifier()
        truck_id = "TRUCK_FORCE_001"

        # Register a drop
        classifier.register_fuel_drop(
            truck_id=truck_id,
            fuel_before=88.0,
            fuel_after=68.0,
            tank_capacity_gal=200.0,
        )

        # Force classification immediately (without waiting for recovery window)
        result = classifier.force_classify_pending(truck_id, current_fuel_pct=69.0)

        assert result is not None
        # Should classify as theft since fuel didn't recover
        assert result["classification"] == "THEFT_CONFIRMED"

    def test_force_classify_pending_no_pending(self):
        """Test force_classify_pending returns None if no pending drop"""
        classifier = FuelEventClassifier()

        result = classifier.force_classify_pending("NONEXISTENT", current_fuel_pct=50.0)

        assert result is None

    def test_get_pending_drops(self):
        """Test get_pending_drops returns all pending drops"""
        classifier = FuelEventClassifier()

        # Create multiple pending drops
        for i in range(3):
            classifier.register_fuel_drop(
                truck_id=f"TRUCK_{i:03d}",
                fuel_before=90.0,
                fuel_after=70.0,
                tank_capacity_gal=200.0,
            )

        pending_list = classifier.get_pending_drops()

        assert len(pending_list) == 3
        assert all(isinstance(p, PendingFuelDrop) for p in pending_list)

    def test_fuel_history_max_limit(self):
        """Test that fuel history is limited to max_history_per_truck"""
        classifier = FuelEventClassifier()
        truck_id = "TRUCK_HIST_001"

        # Add more readings than max
        for i in range(30):
            classifier.add_fuel_reading(truck_id, 50.0 + i)

        # Should only keep last 20
        history = classifier._fuel_history[truck_id]
        assert len(history) == classifier._max_history_per_truck

    def test_sensor_volatility_insufficient_history(self):
        """Test that sensor volatility returns 0 with insufficient history"""
        classifier = FuelEventClassifier()
        truck_id = "TRUCK_NOVOL_001"

        # Add only 3 readings (less than required 5)
        for i in range(3):
            classifier.add_fuel_reading(truck_id, 50.0 + i)

        volatility = classifier.get_sensor_volatility(truck_id)

        assert volatility == 0.0

    def test_sensor_volatility_calculation(self):
        """Test that sensor volatility is calculated correctly"""
        classifier = FuelEventClassifier()
        truck_id = "TRUCK_VOL_002"

        # Add stable readings
        stable_values = [50.0] * 10
        for val in stable_values:
            classifier.add_fuel_reading(truck_id, val)

        volatility = classifier.get_sensor_volatility(truck_id)

        # Should be near 0 for stable values
        assert volatility < 0.1
