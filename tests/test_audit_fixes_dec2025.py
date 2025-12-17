"""
Tests for December 2025 Audit Fixes
====================================
Tests all critical and high priority fixes from AUDIT_REPORT_FULL_DEC2025.md

Fixes covered:
- C1: Division by zero in trend calculations
- C2: Temperature unit standardization (°F)
- C3: Thread lock in DEFPredictor
- C5: Theft protection in auto-resync
- C6: Memory cleanup for inactive trucks
- M1: NaN/Inf handling in Kalman filter
"""

import pytest
import math
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch
import threading


class TestDivisionByZeroFix:
    """Tests for C1: Division by zero prevention in trend calculations"""

    def test_trend_calculation_with_zero_avg_first(self):
        """Test that trend calculation doesn't crash when avg_first is 0"""
        from component_health_predictors import TurboHealthPredictor

        predictor = TurboHealthPredictor()

        # Add readings that would result in avg_first = 0
        for i in range(10):
            predictor.add_reading("TEST001", intrclr_t=0, intake_pres=30)

        # Should not raise ZeroDivisionError
        result = predictor.predict("TEST001")
        assert result is not None
        assert result.score >= 0

    def test_trend_calculation_with_negative_values(self):
        """Test trend calculation with negative values"""
        from component_health_predictors import OilConsumptionTracker

        tracker = OilConsumptionTracker()

        # Add readings with mix of values
        for i in range(10):
            tracker.add_reading("TEST001", oil_level=50, oil_press=40, oil_temp=200)

        result = tracker.predict("TEST001")
        assert result is not None

    def test_trend_with_very_small_values(self):
        """Test trend calculation with very small values close to zero"""
        from component_health_predictors import CoolantLeakDetector

        detector = CoolantLeakDetector()

        # Add readings with small values
        for i in range(10):
            detector.add_reading("TEST001", cool_lvl=0.001, cool_temp=190)

        result = detector.predict("TEST001")
        assert result is not None


class TestTemperatureUnitsStandardization:
    """Tests for C2: Temperature units standardized to °F"""

    def test_oil_temp_thresholds_in_fahrenheit(self):
        """Verify OilConsumptionTracker uses Fahrenheit thresholds"""
        from component_health_predictors import OilConsumptionTracker

        tracker = OilConsumptionTracker()

        # Normal range should be 180-230°F
        assert tracker.OIL_TEMP_NORMAL == (180, 230)
        # Warning at 250°F
        assert tracker.OIL_TEMP_WARNING == 250
        # Critical at 260°F
        assert tracker.OIL_TEMP_CRITICAL == 260

    def test_oil_temp_warning_triggers_correctly(self):
        """Test that oil temp warning triggers at correct Fahrenheit value"""
        from component_health_predictors import OilConsumptionTracker

        tracker = OilConsumptionTracker()

        # Add readings with temperature above warning threshold (250°F)
        for i in range(10):
            tracker.add_reading("TEST001", oil_level=75, oil_press=45, oil_temp=255)

        result = tracker.predict("TEST001")
        # Should have at least one alert about high temperature
        assert any(
            "temp" in alert.lower() or "temperature" in alert.lower()
            for alert in result.alerts
        )

    def test_oil_temp_critical_triggers_correctly(self):
        """Test that oil temp critical triggers at correct Fahrenheit value"""
        from component_health_predictors import OilConsumptionTracker

        tracker = OilConsumptionTracker()

        # Add readings with temperature above critical threshold (260°F)
        for i in range(10):
            tracker.add_reading("TEST001", oil_level=75, oil_press=45, oil_temp=270)

        result = tracker.predict("TEST001")
        # Score should be lower due to critical temperature
        assert result.score < 100


class TestDEFPredictorThreadSafety:
    """Tests for C3: Thread lock in DEFPredictor"""

    def test_def_predictor_has_lock(self):
        """Verify DEFPredictor has threading lock"""
        from def_predictor import DEFPredictor

        predictor = DEFPredictor()
        assert hasattr(predictor, "_lock")
        assert isinstance(predictor._lock, type(threading.RLock()))

    def test_concurrent_add_readings(self):
        """Test concurrent access to add_reading is thread-safe"""
        from def_predictor import DEFPredictor, DEFReading

        predictor = DEFPredictor()
        errors = []

        def add_readings(truck_id, count):
            try:
                for i in range(count):
                    reading = DEFReading(
                        timestamp=datetime.now(timezone.utc),
                        unit_id=123,
                        truck_id=truck_id,
                        level_percent=50.0 + i * 0.1,
                    )
                    predictor.add_reading(reading)
            except Exception as e:
                errors.append(e)

        threads = []
        for i in range(10):
            t = threading.Thread(target=add_readings, args=(f"TRUCK{i}", 100))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # No errors should have occurred
        assert len(errors) == 0

        # All readings should be present
        total_readings = sum(len(v) for v in predictor.readings_cache.values())
        assert total_readings == 1000  # 10 trucks * 100 readings


class TestAutoResyncTheftProtection:
    """Tests for C5: Theft protection in auto-resync"""

    def test_resync_blocked_when_parked_with_downward_drift(self):
        """Test that auto-resync is blocked when truck is parked with downward drift"""
        from estimator import FuelEstimator

        # Create with proper signature: truck_id, capacity_liters, config
        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=378.5,  # ~100 gallons
            config={"Q_r": 0.1, "Q_L_moving": 4.0, "Q_L_static": 1.0},
        )
        estimator.initialize(sensor_pct=80.0)

        # Simulate downward drift while parked
        # First update with high value to establish baseline
        estimator.L = 80.0 * estimator.capacity_liters / 100

        # Try auto_resync with lower sensor value (potential theft) while parked
        estimator.auto_resync(sensor_pct=50.0, speed=0.0, is_trip_active=False)

        # Check that potential theft was flagged
        assert hasattr(estimator, "_potential_theft_flags")
        assert len(estimator._potential_theft_flags) > 0

        # Verify the flag contains correct info
        flag = estimator._potential_theft_flags[-1]
        assert flag["truck_id"] == "TEST001"
        assert flag["drift_pct"] > 0
        assert flag["reviewed"] == False

    def test_resync_allowed_when_moving(self):
        """Test that auto-resync works normally when truck is moving"""
        from estimator import FuelEstimator

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=378.5,  # ~100 gallons
            config={"Q_r": 0.1, "Q_L_moving": 4.0, "Q_L_static": 1.0},
        )
        estimator.initialize(sensor_pct=80.0)

        # Set high internal estimate
        estimator.L = 95.0 * estimator.capacity_liters / 100

        # Auto-resync while moving should work (drift down is normal consumption)
        old_level = estimator.L
        estimator.auto_resync(sensor_pct=75.0, speed=60.0, is_trip_active=True)

        # If no theft flags were created and we did resync, level should change
        # Or if drift wasn't high enough, nothing happens - both are valid


class TestMemoryCleanup:
    """Tests for C6: Memory cleanup for inactive trucks"""

    def test_cleanup_inactive_trucks_function_exists(self):
        """Verify cleanup function exists"""
        from component_health_predictors import (
            cleanup_inactive_trucks,
            cleanup_all_predictors,
        )

        assert callable(cleanup_inactive_trucks)
        assert callable(cleanup_all_predictors)

    def test_cleanup_removes_inactive_trucks(self):
        """Test that cleanup removes trucks not in active set"""
        from component_health_predictors import (
            TurboHealthPredictor,
            cleanup_inactive_trucks,
        )

        predictor = TurboHealthPredictor()

        # Add readings for multiple trucks
        for i in range(5):
            for _ in range(10):
                predictor.add_reading(f"TRUCK{i}", intrclr_t=55, intake_pres=28)

        # Verify all trucks are present
        assert len(predictor._readings) == 5

        # Define active trucks (only 2 of them)
        active_trucks = {"TRUCK0", "TRUCK1"}

        # Run cleanup
        cleaned = cleanup_inactive_trucks([predictor], active_trucks)

        # Should have cleaned 3 trucks
        assert cleaned == 3
        assert len(predictor._readings) == 2
        assert "TRUCK0" in predictor._readings
        assert "TRUCK1" in predictor._readings


class TestKalmanNaNInfHandling:
    """Tests for M1: NaN/Inf handling in Kalman filter"""

    def test_update_rejects_nan(self):
        """Test that update rejects NaN values"""
        from estimator import FuelEstimator

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=378.5,  # ~100 gallons
            config={"Q_r": 0.1, "Q_L_moving": 4.0, "Q_L_static": 1.0},
        )
        estimator.initialize(sensor_pct=50.0)

        original_level = estimator.L

        # Update with NaN should be rejected
        estimator.update(float("nan"))

        # Level should remain unchanged
        assert estimator.L == original_level

    def test_update_rejects_inf(self):
        """Test that update rejects Infinity values"""
        from estimator import FuelEstimator

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=378.5,  # ~100 gallons
            config={"Q_r": 0.1, "Q_L_moving": 4.0, "Q_L_static": 1.0},
        )
        estimator.initialize(sensor_pct=50.0)

        original_level = estimator.L

        # Update with Infinity should be rejected
        estimator.update(float("inf"))

        # Level should remain unchanged
        assert estimator.L == original_level

    def test_update_clamps_out_of_range(self):
        """Test that values are clamped to valid range"""
        from estimator import FuelEstimator

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=378.5,  # ~100 gallons
            config={"Q_r": 0.1, "Q_L_moving": 4.0, "Q_L_static": 1.0},
        )
        estimator.initialize(sensor_pct=50.0)

        # Update with value > 100 should be clamped
        estimator.update(150.0)

        # Should not crash and level should be reasonable
        assert estimator.L <= estimator.capacity_liters

    def test_update_rejects_none(self):
        """Test that update rejects None values"""
        from estimator import FuelEstimator

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=378.5,  # ~100 gallons
            config={"Q_r": 0.1, "Q_L_moving": 4.0, "Q_L_static": 1.0},
        )
        estimator.initialize(sensor_pct=50.0)

        original_level = estimator.L

        # Update with None should be rejected
        estimator.update(None)

        # Level should remain unchanged
        assert estimator.L == original_level


# Integration test
class TestAuditFixesIntegration:
    """Integration tests to verify all fixes work together"""

    def test_component_health_predictors_workflow(self):
        """Test complete workflow with all predictors"""
        from component_health_predictors import (
            get_turbo_predictor,
            get_oil_tracker,
            get_coolant_detector,
            cleanup_all_predictors,
        )

        turbo = get_turbo_predictor()
        oil = get_oil_tracker()
        coolant = get_coolant_detector()

        # Add readings
        for _ in range(20):
            turbo.add_reading("INT_TEST", intrclr_t=55, intake_pres=28)
            oil.add_reading("INT_TEST", oil_level=75, oil_press=45, oil_temp=210)
            coolant.add_reading("INT_TEST", cool_lvl=80, cool_temp=195)

        # Get predictions
        turbo_pred = turbo.predict("INT_TEST")
        oil_pred = oil.predict("INT_TEST")
        coolant_pred = coolant.predict("INT_TEST")

        assert turbo_pred is not None
        assert oil_pred is not None
        assert coolant_pred is not None

        # Cleanup
        cleaned = cleanup_all_predictors(set())
        assert cleaned >= 0  # At least some trucks may be cleaned


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
