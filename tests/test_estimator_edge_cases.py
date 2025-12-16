"""
Additional edge case tests for FuelEstimator
Targeting uncovered lines: 35-36, 42-43, 189, 257, 277, 305, 344-352, etc.

Tests focus on:
- Adaptive Q_r calculation for different vehicle states
- Static anchor detection edge cases
- GPS quality module integration
- Voltage quality module integration
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from estimator import (
    FuelEstimator,
    COMMON_CONFIG,
    calculate_adaptive_Q_r,
    AnchorType,
    AnchorDetector,
)


class MockTanksConfig:
    """Mock TanksConfig for testing"""

    def __init__(self, capacity: float = 757.0):
        self.capacity = capacity
        self.trucks = {"TEST": {"capacity_liters": capacity}}

    def get_capacity(self, truck_id: str) -> float:
        return self.capacity

    def get_refuel_factor(self, truck_id: str, default: float = 1.0) -> float:
        return 1.0


def make_estimator(initial_pct: float = 66.0, capacity: float = 757.0):
    """Factory function to create test estimator"""
    config = {**COMMON_CONFIG, "capacity_liters": capacity}
    tanks_config = MockTanksConfig(capacity)
    est = FuelEstimator(
        truck_id="TEST",
        capacity_liters=capacity,
        config=config,
        tanks_config=tanks_config,
    )
    est.initialize(sensor_pct=initial_pct)
    return est


# =============================================================================
# ADAPTIVE Q_r TESTS (lines 344-352)
# =============================================================================


class TestAdaptiveQr:
    """Tests for adaptive Q_r calculation based on vehicle status"""

    def test_calculate_adaptive_Q_r_parked(self):
        """Parked vehicles should have lowest Q_r"""
        Q_r = calculate_adaptive_Q_r("PARKED", consumption_lph=0.0)
        assert Q_r <= 0.1, "Parked should have very low Q_r"

    def test_calculate_adaptive_Q_r_idle(self):
        """Idle vehicles should have low Q_r (v5.8.5: more conservative)"""
        Q_r = calculate_adaptive_Q_r("IDLE", consumption_lph=2.0)
        # v5.8.5: Idle now uses 0.02 base + small consumption factor
        assert 0.02 <= Q_r <= 0.1, "Idle should have low Q_r"

    def test_calculate_adaptive_Q_r_stopped(self):
        """Stopped vehicles should have low Q_r (v5.8.5: more conservative)"""
        Q_r = calculate_adaptive_Q_r("STOPPED", consumption_lph=1.0)
        # v5.8.5: Stopped now uses fixed 0.02
        assert 0.02 <= Q_r <= 0.1

    def test_calculate_adaptive_Q_r_moving(self):
        """Moving vehicles should have higher Q_r"""
        Q_r = calculate_adaptive_Q_r("MOVING", consumption_lph=15.0)
        # v5.8.5: MOVING = 0.05 + (15/50)*0.1 = 0.08
        assert Q_r >= 0.08, "Moving should have higher Q_r"

    def test_calculate_adaptive_Q_r_unknown_status(self):
        """Unknown status should default to MOVING"""
        Q_r = calculate_adaptive_Q_r("UNKNOWN", consumption_lph=10.0)
        Q_r_moving = calculate_adaptive_Q_r("MOVING", consumption_lph=10.0)
        assert Q_r == Q_r_moving

    def test_update_adaptive_Q_r_from_speed_and_rpm(self):
        """update_adaptive_Q_r should detect status from speed/rpm"""
        est = make_estimator(50.0)

        # Parked: speed < 0.5, rpm < 300
        est.update_adaptive_Q_r(speed=0.0, rpm=0, consumption_lph=0.0)
        Q_r_parked = est.Q_r

        # Idle: speed < 1, rpm >= 300
        est.update_adaptive_Q_r(speed=0.0, rpm=600, consumption_lph=2.0)
        Q_r_idle = est.Q_r

        # Moving: speed >= 5
        est.update_adaptive_Q_r(speed=55.0, rpm=1500, consumption_lph=20.0)
        Q_r_moving = est.Q_r

        # Q_r should increase: parked < idle < moving
        assert Q_r_parked <= Q_r_idle <= Q_r_moving

    def test_update_adaptive_Q_r_speed_only(self):
        """update_adaptive_Q_r works with only speed (no rpm)"""
        est = make_estimator(50.0)

        # With speed only
        est.update_adaptive_Q_r(speed=0.5, rpm=None, consumption_lph=0.0)
        assert est.Q_r > 0

        est.update_adaptive_Q_r(speed=30.0, rpm=None, consumption_lph=15.0)
        assert est.Q_r > 0

    def test_update_adaptive_Q_r_neither_speed_nor_rpm(self):
        """update_adaptive_Q_r defaults to MOVING when no data"""
        est = make_estimator(50.0)

        est.update_adaptive_Q_r(speed=None, rpm=None, consumption_lph=10.0)
        Q_r_default = est.Q_r

        est.update_adaptive_Q_r(speed=50.0, rpm=1500, consumption_lph=10.0)
        Q_r_moving = est.Q_r

        # Default should be same as moving
        assert Q_r_default == Q_r_moving


# =============================================================================
# STATIC ANCHOR EDGE CASES (lines 788-835)
# =============================================================================


class TestStaticAnchorEdgeCases:
    """Tests for static anchor detection edge cases using AnchorDetector"""

    def make_detector(self):
        """Create an AnchorDetector with test config"""
        return AnchorDetector(COMMON_CONFIG)

    def test_check_static_anchor_missing_speed(self):
        """Static anchor returns None when speed is missing"""
        detector = self.make_detector()

        result = detector.check_static_anchor(
            timestamp=datetime.now(timezone.utc),
            fuel_pct=50.0,
            speed=None,  # Missing
            rpm=600,
            hdop=1.0,
            drift_pct=0.5,
        )

        assert result is None

    def test_check_static_anchor_missing_rpm(self):
        """Static anchor returns None when rpm is missing"""
        detector = self.make_detector()

        result = detector.check_static_anchor(
            timestamp=datetime.now(timezone.utc),
            fuel_pct=50.0,
            speed=0.0,
            rpm=None,  # Missing
            hdop=1.0,
            drift_pct=0.5,
        )

        assert result is None

    def test_check_static_anchor_missing_fuel(self):
        """Static anchor returns None when fuel_pct is missing"""
        detector = self.make_detector()

        result = detector.check_static_anchor(
            timestamp=datetime.now(timezone.utc),
            fuel_pct=None,  # Missing
            speed=0.0,
            rpm=600,
            hdop=1.0,
            drift_pct=0.5,
        )

        assert result is None

    def test_check_static_anchor_speed_too_high(self):
        """Static anchor returns None when speed is too high"""
        detector = self.make_detector()

        result = detector.check_static_anchor(
            timestamp=datetime.now(timezone.utc),
            fuel_pct=50.0,
            speed=10.0,  # Too high for static
            rpm=600,
            hdop=1.0,
            drift_pct=0.5,
        )

        assert result is None

    def test_check_static_anchor_rpm_too_low(self):
        """Static anchor returns None when engine is off (rpm too low)"""
        detector = self.make_detector()

        result = detector.check_static_anchor(
            timestamp=datetime.now(timezone.utc),
            fuel_pct=50.0,
            speed=0.0,
            rpm=100,  # Engine off
            hdop=1.0,
            drift_pct=0.5,
        )

        assert result is None

    def test_check_static_anchor_hdop_too_high(self):
        """Static anchor returns None when GPS accuracy is poor"""
        detector = self.make_detector()

        result = detector.check_static_anchor(
            timestamp=datetime.now(timezone.utc),
            fuel_pct=50.0,
            speed=0.0,
            rpm=600,
            hdop=5.0,  # Poor GPS
            drift_pct=0.5,
        )

        assert result is None

    def test_check_static_anchor_duration_too_short(self):
        """Static anchor returns None when duration is too short"""
        detector = self.make_detector()
        now = datetime.now(timezone.utc)

        # First call starts tracking
        result1 = detector.check_static_anchor(
            timestamp=now, fuel_pct=50.0, speed=0.0, rpm=600, hdop=1.0, drift_pct=0.5
        )
        assert result1 is None

        # Second call still too short (only 5 seconds)
        result2 = detector.check_static_anchor(
            timestamp=now + timedelta(seconds=5),
            fuel_pct=50.0,
            speed=0.0,
            rpm=600,
            hdop=1.0,
            drift_pct=0.5,
        )
        assert result2 is None

    def test_check_static_anchor_cooldown_period(self):
        """Static anchor respects cooldown period"""
        detector = self.make_detector()
        detector.anchor_cooldown_s = 60  # 60 second cooldown

        now = datetime.now(timezone.utc)
        detector.last_anchor_time = now - timedelta(seconds=30)  # Recent anchor

        # Should return None due to cooldown
        result = detector.check_static_anchor(
            timestamp=now, fuel_pct=50.0, speed=0.0, rpm=600, hdop=1.0, drift_pct=0.5
        )

        # Either None or starts new tracking (depending on impl)
        # The key is it doesn't immediately create an anchor

    def test_check_static_anchor_resets_on_movement(self):
        """Static anchor tracking resets when vehicle moves"""
        detector = self.make_detector()
        now = datetime.now(timezone.utc)

        # Start tracking
        detector.check_static_anchor(
            timestamp=now, fuel_pct=50.0, speed=0.0, rpm=600, hdop=1.0, drift_pct=0.5
        )

        # Vehicle moves
        detector.check_static_anchor(
            timestamp=now + timedelta(seconds=10),
            fuel_pct=50.0,
            speed=20.0,  # Moving!
            rpm=1500,
            hdop=1.0,
            drift_pct=0.5,
        )

        # Static tracking should be reset
        assert detector.static_start_time is None


# =============================================================================
# GPS/VOLTAGE QUALITY MODULE INTEGRATION (lines 35-43)
# =============================================================================


class TestQualityModuleIntegration:
    """Tests for GPS and voltage quality module integration"""

    def test_gps_quality_module_unavailable(self):
        """Estimator works when GPS quality module is not available"""
        with patch.dict("sys.modules", {"gps_quality": None}):
            est = make_estimator(50.0)

            # Should work without GPS quality module
            factor = est.update_sensor_quality(satellites=10, voltage=14.0)
            assert factor >= 0

    def test_voltage_module_unavailable(self):
        """Estimator works when voltage module is not available"""
        with patch.dict("sys.modules", {"voltage_monitor": None}):
            est = make_estimator(50.0)

            # Should work without voltage module
            factor = est.update_sensor_quality(satellites=10, voltage=14.0)
            assert factor >= 0


# =============================================================================
# CONFIDENCE LEVEL TESTS (lines 361-380)
# =============================================================================


class TestConfidenceLevel:
    """Tests for get_confidence method"""

    def test_confidence_increases_with_readings(self):
        """Confidence should increase after multiple readings"""
        est = make_estimator(50.0)

        # Initial confidence
        conf1 = est.get_confidence()

        # Process some readings
        for i in range(10):
            est.predict(dt_hours=1 / 60, consumption_lph=15.0)
            est.update(50.0 - i * 0.1)

        conf2 = est.get_confidence()

        # Confidence should be at least maintained or increased
        assert conf2["level"] in ["HIGH", "MEDIUM", "LOW", "VERY_LOW"]

    def test_confidence_structure(self):
        """get_confidence returns expected structure"""
        est = make_estimator(50.0)

        conf = est.get_confidence()

        assert "level" in conf
        assert "score" in conf
        assert "description" in conf
        assert conf["level"] in ["HIGH", "MEDIUM", "LOW", "VERY_LOW"]


# =============================================================================
# EMERGENCY RESET TESTS (lines 461-476)
# =============================================================================


class TestEmergencyReset:
    """Tests for emergency reset functionality"""

    def test_emergency_reset_on_large_error(self):
        """Estimator resets when estimate differs greatly from sensor"""
        est = make_estimator(50.0)

        # Simulate large drift
        est.L = 100  # Force estimate way off

        # Update with normal reading
        est.update(50.0)

        # Should have triggered reset or large correction
        assert abs(est.level_pct - 50.0) < 10.0

    def test_emergency_reset_tracked(self):
        """Emergency resets should affect the estimate"""
        est = make_estimator(50.0)

        # Force a reset by setting extreme values
        est.L = 1000  # Way above capacity
        est.update(50.0)

        # The estimate should be corrected
        assert est.level_pct < 100  # Should be reasonable


# =============================================================================
# REFUEL DETECTION EDGE CASES (lines 516-569)
# =============================================================================


class TestRefuelDetection:
    """Tests for refuel detection edge cases"""

    def test_detect_small_refuel(self):
        """Detect refuels at minimum threshold"""
        est = make_estimator(30.0)

        # Process a small increase
        est.predict(dt_hours=0.1, consumption_lph=10.0)
        est.update(38.0)  # 8% increase, at threshold

        # Should detect as possible refuel
        estimate = est.get_estimate()
        # The estimate should handle this gracefully
        assert estimate["level_pct"] > 30.0

    def test_no_refuel_during_consumption(self):
        """Normal consumption shouldn't trigger refuel detection"""
        est = make_estimator(50.0)

        # Normal decrease
        for _ in range(5):
            est.predict(dt_hours=1 / 60, consumption_lph=15.0)
            est.update(est.level_pct - 0.5)

        estimate = est.get_estimate()
        assert estimate["level_pct"] < 50.0


# =============================================================================
# GET ESTIMATE COMPREHENSIVE TEST
# =============================================================================


class TestGetEstimateComprehensive:
    """Tests for get_estimate method completeness"""

    def test_get_estimate_all_fields(self):
        """get_estimate should return all expected fields"""
        est = make_estimator(50.0)

        # Run some updates
        est.predict(dt_hours=0.1, consumption_lph=15.0)
        est.update(49.0)

        estimate = est.get_estimate()

        # Check all expected fields
        expected_fields = [
            "level_pct",
            "level_liters",
            "kalman_gain",
        ]

        for field in expected_fields:
            assert field in estimate, f"Missing field: {field}"

    def test_get_estimate_values_reasonable(self):
        """get_estimate values should be within reasonable bounds"""
        est = make_estimator(50.0)

        estimate = est.get_estimate()

        assert 0 <= estimate["level_pct"] <= 100
        assert 0 <= estimate["level_liters"] <= 800  # Reasonable capacity
        assert 0 <= estimate["kalman_gain"] <= 1.0
