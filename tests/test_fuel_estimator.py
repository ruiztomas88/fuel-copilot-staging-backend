"""
Unit Tests for FuelEstimator v3.5.0

Tests validate:
- Kalman filter prediction
- Adaptive noise calculation
- ECU consumption
- Emergency reset
- Anchor detection
- Refuel handling
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone

# Add parent directory to path to import main module
sys.path.insert(0, str(Path(__file__).parent.parent))

from estimator import FuelEstimator, COMMON_CONFIG


class MockTanksConfig:
    """Mock TanksConfig for testing"""

    def __init__(self):
        self.trucks = {"TEST": {"capacity_liters": 757.0}}

    def get_capacity(self, truck_id: str) -> float:
        return self.trucks.get(truck_id, {}).get("capacity_liters", 757.0)

    def get_refuel_factor(self, truck_id: str, default: float = 1.0) -> float:
        return 1.0


def make_estimator(initial_pct: float = 66.0):
    """Factory function to create test estimator"""
    config = {**COMMON_CONFIG, "capacity_liters": 757.0}
    tanks_config = MockTanksConfig()
    est = FuelEstimator(
        truck_id="TEST", capacity_liters=757.0, config=config, tanks_config=tanks_config
    )
    est.initialize(sensor_pct=initial_pct)  # Start at specified %
    return est


# ============================================================================
# 1. BASIC KALMAN OPERATIONS
# ============================================================================


def test_initialization():
    """Estimator initializes correctly"""
    est = make_estimator(50.0)

    assert est.initialized is True
    assert est.level_pct == 50.0
    assert abs(est.level_liters - 378.5) < 1.0  # 50% of 757L


def test_predict_consumes_fuel():
    """Predict step consumes fuel based on rate"""
    est = make_estimator(50.0)
    initial_L = est.L

    # Consume 20 L/h for 1 minute
    est.predict(dt_hours=1 / 60, consumption_lph=20.0)

    # Should consume 20 * (1/60) = 0.333L
    consumed = initial_L - est.L
    assert 0.30 < consumed < 0.37


def test_update_corrects_estimate():
    """Update step corrects estimate toward sensor"""
    est = make_estimator(50.0)

    # Predict some consumption
    est.predict(dt_hours=1 / 60, consumption_lph=20.0)

    # Update with sensor reading
    est.update(49.5)

    # Should be closer to sensor now
    assert abs(est.level_pct - 49.5) < 1.0


def test_kalman_gain_bounded():
    """Kalman gain is bounded to prevent over-correction"""
    est = make_estimator(50.0)

    # Run many cycles
    for _ in range(100):
        est.predict(1 / 60, 15.0)
        est.update(est.level_pct - 0.1)

    estimate = est.get_estimate()
    K = estimate["kalman_gain"]

    # K should be bounded (typically 0-30%)
    assert K <= 0.30


# ============================================================================
# 2. ADAPTIVE NOISE
# ============================================================================


def test_static_has_low_noise():
    """Static truck has low measurement noise"""
    est = make_estimator(50.0)

    Q_L = est.calculate_adaptive_noise(
        speed=0.0,
        altitude=500.0,
        timestamp=datetime.now(timezone.utc),
    )

    assert Q_L == 1.0  # Base noise for static


def test_moving_has_higher_noise():
    """Moving truck has higher measurement noise"""
    est = make_estimator(50.0)

    Q_L = est.calculate_adaptive_noise(
        speed=55.0,
        altitude=500.0,
        timestamp=datetime.now(timezone.utc),
    )

    assert Q_L >= 2.0  # Moving noise


def test_acceleration_increases_noise():
    """Acceleration increases noise (slosh)"""
    est = make_estimator(50.0)

    # Set initial speed
    est.last_speed = 30.0

    # Calculate noise with acceleration
    Q_L = est.calculate_adaptive_noise(
        speed=60.0,  # +30 mph in 15s = 2 mph/s
        altitude=500.0,
        timestamp=datetime.now(timezone.utc),
    )

    assert Q_L >= 3.0  # Higher noise due to acceleration


def test_engine_load_affects_noise():
    """High engine load increases noise"""
    est = make_estimator(50.0)

    Q_L_low = est.calculate_adaptive_noise(
        speed=55.0,
        altitude=500.0,
        timestamp=datetime.now(timezone.utc),
        engine_load=20,  # Low load
    )

    est.last_speed = None  # Reset

    Q_L_high = est.calculate_adaptive_noise(
        speed=55.0,
        altitude=500.0,
        timestamp=datetime.now(timezone.utc),
        engine_load=85,  # High load
    )

    assert Q_L_high > Q_L_low


# ============================================================================
# 3. ECU CONSUMPTION
# ============================================================================


def test_ecu_first_reading_returns_none():
    """First ECU reading initializes counter, returns None"""
    est = make_estimator(50.0)

    result = est.calculate_ecu_consumption(
        total_fuel_used=1000.0,
        dt_hours=15 / 3600,
    )

    assert result is None
    assert est.last_total_fuel_used == 1000.0


def test_ecu_calculates_consumption():
    """ECU calculates consumption from delta"""
    est = make_estimator(50.0)

    # Initialize
    est.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

    # Second reading
    result = est.calculate_ecu_consumption(
        total_fuel_used=1000.1,  # +0.1 gal
        dt_hours=15 / 3600,  # 15 seconds = 0.00417 hours
    )

    # 0.1 gal / (15/3600) h = 24 GPH = ~90.8 L/h
    assert result is not None
    assert 85 < result < 95


def test_ecu_rejects_counter_reset():
    """ECU handles counter reset gracefully"""
    est = make_estimator(50.0)

    # Initialize with high value
    est.calculate_ecu_consumption(total_fuel_used=50000.0, dt_hours=15 / 3600)

    # Counter resets (new < old)
    result = est.calculate_ecu_consumption(
        total_fuel_used=100.0,  # Reset!
        dt_hours=15 / 3600,
    )

    assert result is None


def test_ecu_degradation():
    """ECU degrades after multiple failures"""
    est = make_estimator(50.0)

    # Cause multiple failures
    for _ in range(6):
        est._record_ecu_failure("test")

    assert est.ecu_degraded is True


# ============================================================================
# 4. EMERGENCY RESET
# ============================================================================


def test_emergency_reset_triggers_on_high_drift():
    """Emergency reset triggers on >30% drift after >2h gap"""
    est = make_estimator(80.0)  # Start at 80%

    # Simulate drift by manipulating L
    est.L = est.capacity_liters * 0.40  # Model thinks 40%

    # Sensor says 80% after 3 hour gap
    reset = est.check_emergency_reset(
        sensor_pct=80.0,
        time_gap_hours=3.0,
        truck_status="MOVING",
    )

    assert reset is True
    assert abs(est.level_pct - 80.0) < 1.0  # Reset to sensor


def test_no_reset_on_small_drift():
    """No reset on normal drift"""
    est = make_estimator(50.0)

    # Small drift (5%)
    est.L = est.capacity_liters * 0.45  # Model thinks 45%

    reset = est.check_emergency_reset(
        sensor_pct=50.0,
        time_gap_hours=3.0,
    )

    assert reset is False


def test_no_reset_on_short_gap():
    """No reset on short time gap"""
    est = make_estimator(80.0)

    est.L = est.capacity_liters * 0.40  # 40% drift

    reset = est.check_emergency_reset(
        sensor_pct=80.0,
        time_gap_hours=0.5,  # Only 30 minutes
    )

    assert reset is False


# ============================================================================
# 5. REFUEL HANDLING
# ============================================================================


def test_refuel_detection():
    """Large fuel increase indicates refuel"""
    est = make_estimator(20.0)  # Low fuel

    # Simulate refuel detection via update with large jump
    est.update(90.0)  # Sensor jumps to 90%

    # Estimator should follow sensor with high confidence
    assert est.level_pct > 50.0  # Should move toward sensor
    # Note: actual refuel detection is in main loop, not estimator


# ============================================================================
# 6. DRIFT TRACKING
# ============================================================================


def test_drift_calculated():
    """Drift is calculated after update"""
    est = make_estimator(50.0)

    # Create drift by predicting without accurate consumption
    for _ in range(10):
        est.predict(1 / 60, 15.0)

    # Update with sensor
    est.update(50.0)  # Sensor still at 50%

    estimate = est.get_estimate()

    # Should have some drift
    assert estimate["drift_pct"] != 0


def test_drift_warning():
    """Drift warning triggers above threshold"""
    est = make_estimator(50.0)

    # Create significant drift
    for _ in range(100):
        est.predict(1 / 60, 30.0)  # High consumption

    # Update with original sensor
    est.update(50.0)

    estimate = est.get_estimate()

    # Drift should be significant
    if abs(estimate["drift_pct"]) > 7.5:  # Default threshold
        assert estimate["drift_warning"] is True


# ============================================================================
# 7. GAP HANDLING
# ============================================================================


def test_large_gap_no_consumption():
    """Large time gap is skipped to prevent wild estimations"""
    est = make_estimator(50.0)
    initial_L = est.L
    assert initial_L is not None

    # 2.5 hour gap - should be skipped (> 1.0 hour threshold)
    est.predict(dt_hours=2.5, consumption_lph=20.0)

    # Level should remain unchanged (gap skipped)
    assert est.L is not None
    assert est.L == initial_L  # No consumption - gap was skipped


def test_normal_gap_consumes():
    """Normal time gap applies consumption"""
    est = make_estimator(50.0)
    initial_L = est.L
    assert initial_L is not None

    # 30 minute gap (normal)
    est.predict(dt_hours=0.5, consumption_lph=20.0)

    # Should consume 20 * 0.5 = 10L
    assert est.L is not None
    consumed = initial_L - est.L
    assert 9.0 < consumed < 11.0


# ============================================================================
# 8. EDGE CASES
# ============================================================================


def test_zero_time_delta():
    """Zero time delta doesn't change fuel"""
    est = make_estimator(50.0)
    initial_L = est.L

    est.predict(dt_hours=0.0, consumption_lph=20.0)

    assert est.L == initial_L


def test_very_low_fuel():
    """Works correctly at very low fuel"""
    est = make_estimator(5.0)  # 5%

    est.predict(1 / 60, 15.0)
    est.update(4.9)

    assert est.L is not None and est.L > 0
    assert est.level_pct > 0


def test_full_tank():
    """Works correctly at full tank"""
    est = make_estimator(100.0)

    est.predict(1 / 60, 15.0)
    est.update(99.9)

    assert est.level_pct < 100


def test_get_estimate_returns_all_fields():
    """get_estimate returns all expected fields"""
    est = make_estimator(50.0)

    estimate = est.get_estimate()

    assert "level_liters" in estimate
    assert "level_pct" in estimate
    assert "consumption_lph" in estimate
    assert "drift_pct" in estimate
    assert "drift_warning" in estimate
    assert "kalman_gain" in estimate
    assert "is_moving" in estimate
    assert "ecu_consumption_available" in estimate


# ============================================================================
# 8. DYNAMIC K CLAMP TESTS v5.8.2
# ============================================================================


class TestDynamicKClamp:
    """
    Tests for dynamic Kalman gain clamping based on uncertainty (P).

    v5.8.2: K max now varies based on P:
    - P > 5.0 (low confidence): k_max = 0.50
    - P > 2.0 (medium confidence): k_max = 0.35
    - P <= 2.0 (high confidence): k_max = 0.20
    """

    def test_high_uncertainty_allows_large_corrections(self):
        """When P is high (>5), allow larger corrections (up to 0.50)"""
        est = make_estimator(50.0)
        # Set high P (low confidence)
        est.P = 10.0

        # Large measurement deviation
        est.update(70.0)  # Jump from 50% to 70%

        # Should allow larger correction due to high P
        # With P=10, k_max=0.50, so correction should be substantial
        assert est.level_pct > 55.0  # Should move significantly toward measurement
        assert est.level_pct < 70.0  # But not all the way

    def test_medium_uncertainty_limits_corrections(self):
        """When P is medium (2-5), limit corrections to 0.35"""
        est = make_estimator(50.0)
        # Set medium P
        est.P = 3.0

        est.update(70.0)

        # Should have moderate correction
        assert est.level_pct > 52.0
        assert est.level_pct < 65.0

    def test_high_confidence_limits_corrections(self):
        """When P is low (<2), limit corrections to 0.20"""
        est = make_estimator(50.0)
        # Set low P (high confidence)
        est.P = 1.0

        # Use smaller deviation to avoid triggering auto-resync (15% drift threshold)
        est.update(58.0)  # 8% deviation instead of 20%

        # Should have small correction due to high confidence in current state
        # K = P / (P + R) clamped to 0.20 max
        # Innovation = 58% - 50% = 8%
        # Correction = K * innovation ≈ 0.20 * 8% = 1.6%
        assert est.level_pct > 50.0  # Should move toward reading
        assert est.level_pct < 54.0  # But limited due to high confidence

    def test_k_clamp_preserves_stability(self):
        """K clamping should prevent wild oscillations"""
        est = make_estimator(50.0)
        est.P = 5.0  # Medium confidence

        # Simulate noisy sensor readings
        readings = [50.0, 55.0, 48.0, 60.0, 45.0, 53.0]
        prev_level = est.level_pct

        for reading in readings:
            est.update(reading)
            # Level should change smoothly, not jump wildly
            change = abs(est.level_pct - prev_level)
            assert change < 15.0  # No single update should change more than 15%
            prev_level = est.level_pct

    def test_p_decreases_after_consistent_readings(self):
        """P should decrease (confidence increase) after consistent readings"""
        est = make_estimator(50.0)
        est.P = 5.0

        # Send consistent readings
        for _ in range(5):
            est.update(50.0)

        # P should be lower (higher confidence)
        assert est.P < 5.0


# ============================================================================
# 9. SENSOR QUALITY TESTS v5.8.2
# ============================================================================


class TestSensorQuality:
    """Tests for sensor quality factor updates"""

    def test_update_sensor_quality_returns_factor(self):
        """update_sensor_quality returns quality factor"""
        est = make_estimator(50.0)

        factor = est.update_sensor_quality(
            satellites=12, voltage=14.0, is_engine_running=True
        )

        # Should return a factor between 0.5 and 1.0
        assert 0.5 <= factor <= 1.0

    def test_low_satellites_affects_quality(self):
        """Low satellite count affects sensor quality"""
        est = make_estimator(50.0)

        # Good satellites
        factor_good = est.update_sensor_quality(satellites=12)

        # Bad satellites
        factor_bad = est.update_sensor_quality(satellites=3)

        # Lower satellites should give lower or equal quality
        assert factor_bad <= factor_good

    def test_low_voltage_affects_quality(self):
        """Low voltage affects sensor quality"""
        est = make_estimator(50.0)

        # Good voltage
        factor_good = est.update_sensor_quality(voltage=14.0, is_engine_running=True)

        # Bad voltage
        factor_bad = est.update_sensor_quality(voltage=10.0, is_engine_running=True)

        # Lower voltage should give lower quality
        assert factor_bad <= factor_good


# ============================================================================
# 10. ADAPTIVE Q_R TESTS v5.8.2
# ============================================================================


class TestAdaptiveQr:
    """Tests for adaptive process noise (Q_r) updates"""

    def test_update_adaptive_q_r_parked(self):
        """Parked truck gets low Q_r"""
        est = make_estimator(50.0)

        est.update_adaptive_Q_r(speed=0, rpm=0, consumption_lph=0)

        # Q_r should be set (not None)
        assert hasattr(est, "Q_r")
        assert est.Q_r >= 0

    def test_update_adaptive_q_r_moving(self):
        """Moving truck gets appropriate Q_r"""
        est = make_estimator(50.0)

        est.update_adaptive_Q_r(speed=60, rpm=1500, consumption_lph=20)

        assert hasattr(est, "Q_r")
        assert est.Q_r >= 0

    def test_update_adaptive_q_r_idle(self):
        """Idling truck gets idle-appropriate Q_r"""
        est = make_estimator(50.0)

        est.update_adaptive_Q_r(speed=0, rpm=700, consumption_lph=2)

        assert hasattr(est, "Q_r")
        assert est.Q_r >= 0


# ============================================================================
# 11. REFUEL RESET TESTS v5.8.2
# ============================================================================


class TestRefuelReset:
    """Tests for refuel detection reset"""

    def test_apply_refuel_reset_updates_level(self):
        """Refuel reset updates fuel level"""
        est = make_estimator(30.0)  # Start at 30%

        est.apply_refuel_reset(
            new_fuel_pct=80.0, timestamp=datetime.now(timezone.utc), gallons_added=100
        )

        assert est.level_pct == 80.0
        assert est.recent_refuel == True

    def test_apply_refuel_reset_resets_drift(self):
        """Refuel reset clears drift"""
        est = make_estimator(50.0)
        est.drift_pct = 5.0  # Simulate drift

        est.apply_refuel_reset(
            new_fuel_pct=90.0, timestamp=datetime.now(timezone.utc), gallons_added=80
        )

        assert est.drift_pct == 0.0
        assert est.drift_warning == False


# ============================================================================
# 12. AUTO RESYNC TESTS v5.8.2
# ============================================================================


class TestAutoResync:
    """Tests for automatic resync on extreme drift"""

    def test_auto_resync_on_extreme_drift(self):
        """Auto resync triggers on extreme drift"""
        est = make_estimator(50.0)

        # Create extreme drift by updating with very different value
        # and checking if resync happens
        est.update(70.0)  # 20% difference - should trigger resync

        # After resync, level should be close to sensor
        assert abs(est.level_pct - 70.0) < 2.0

    def test_no_resync_on_small_drift(self):
        """No resync on small drift"""
        est = make_estimator(50.0)

        # Small drift shouldn't trigger resync
        est.update(51.0)  # Only 1% difference

        # Level should have moved somewhat but not fully resynced
        assert est.level_pct < 51.0  # Not fully at sensor level


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])


# ============================================================================
# 13. ADAPTIVE Q_r AND KALMAN CONFIDENCE TESTS
# ============================================================================


class TestAdaptiveQr:
    """Tests for adaptive Q_r calculation"""

    def test_parked_low_noise(self):
        """Parked status should have very low process noise (v5.8.5: more conservative)"""
        from estimator import calculate_adaptive_Q_r

        Q_r = calculate_adaptive_Q_r("PARKED", 0.0)
        assert Q_r == 0.005  # v5.8.5: reduced from 0.01

    def test_stopped_low_noise(self):
        """Stopped status should have low process noise (v5.8.5: more conservative)"""
        from estimator import calculate_adaptive_Q_r

        Q_r = calculate_adaptive_Q_r("STOPPED", 0.0)
        assert Q_r == 0.02  # v5.8.5: reduced from 0.05

    def test_idle_scales_with_consumption(self):
        """Idle noise should scale with consumption"""
        from estimator import calculate_adaptive_Q_r

        Q_r_low = calculate_adaptive_Q_r("IDLE", 0.0)
        Q_r_high = calculate_adaptive_Q_r("IDLE", 10.0)
        assert Q_r_high > Q_r_low

    def test_moving_higher_noise(self):
        """Moving status should have higher process noise"""
        from estimator import calculate_adaptive_Q_r

        Q_r_moving = calculate_adaptive_Q_r("MOVING", 10.0)
        Q_r_parked = calculate_adaptive_Q_r("PARKED", 0.0)
        assert Q_r_moving > Q_r_parked


class TestKalmanConfidence:
    """Tests for Kalman confidence conversion"""

    def test_high_confidence(self):
        """Low P should give high confidence"""
        from estimator import get_kalman_confidence

        result = get_kalman_confidence(0.3)
        assert result["level"] == "HIGH"
        assert result["score"] == 95
        assert result["color"] == "green"

    def test_medium_confidence(self):
        """Medium P should give medium confidence"""
        from estimator import get_kalman_confidence

        result = get_kalman_confidence(1.0)
        assert result["level"] == "MEDIUM"
        assert result["score"] == 75
        assert result["color"] == "yellow"

    def test_low_confidence(self):
        """Higher P should give low confidence"""
        from estimator import get_kalman_confidence

        result = get_kalman_confidence(3.0)
        assert result["level"] == "LOW"
        assert result["score"] == 50
        assert result["color"] == "orange"

    def test_very_low_confidence(self):
        """Very high P should give very low confidence"""
        from estimator import get_kalman_confidence

        result = get_kalman_confidence(10.0)
        assert result["level"] == "VERY_LOW"
        assert result["score"] == 25
        assert result["color"] == "red"


# ============================================================================
# 14. DYNAMIC KALMAN GAIN TESTS v5.8.3
# ============================================================================


class TestDynamicKalmanGain:
    """Tests for dynamic Kalman gain based on uncertainty"""

    def test_high_uncertainty_allows_larger_correction(self):
        """High P (low confidence) should allow larger K"""
        est = make_estimator(50.0)

        # Set high uncertainty
        est.P = 10.0

        # Update should use larger K clamp (0.50)
        est.update(60.0)  # Large sensor difference

        # Should have moved significantly toward sensor
        assert est.level_pct > 52.0  # More than minimal correction

    def test_low_uncertainty_limits_correction(self):
        """Low P (high confidence) should limit K"""
        est = make_estimator(50.0)

        # Set low uncertainty (high confidence)
        est.P = 0.5

        initial_pct = est.level_pct

        # Update with large difference
        est.update(60.0)

        # Should not have moved too much (K clamped to 0.20)
        correction = abs(est.level_pct - initial_pct)
        assert correction < 3.0  # Limited correction

    def test_medium_uncertainty_moderate_correction(self):
        """Medium P should use moderate K"""
        est = make_estimator(50.0)

        # Set medium uncertainty
        est.P = 3.0

        initial_pct = est.level_pct

        # Update
        est.update(55.0)

        # Should be moderate correction
        correction = abs(est.level_pct - initial_pct)
        assert 0.5 < correction < 4.0


# ============================================================================
# 15. KALMAN CONFIDENCE IN OUTPUT v5.8.3
# ============================================================================


class TestKalmanConfidenceInOutput:
    """Tests for kalman_confidence in get_estimate output"""

    def test_kalman_confidence_in_estimate(self):
        """get_estimate should include kalman_confidence"""
        est = make_estimator(50.0)

        estimate = est.get_estimate()

        assert "kalman_confidence" in estimate
        assert "level" in estimate["kalman_confidence"]
        assert "score" in estimate["kalman_confidence"]

    def test_confidence_level_high_when_stable(self):
        """Confidence should be HIGH after stable readings"""
        est = make_estimator(50.0)
        est.P = 0.3  # Very low P = high confidence

        estimate = est.get_estimate()

        assert estimate["kalman_confidence"]["level"] == "HIGH"
        assert estimate["kalman_confidence"]["score"] == 95

    def test_confidence_level_low_after_reset(self):
        """Confidence should be LOW after emergency reset"""
        est = make_estimator(50.0)
        est.P = 8.0  # High P = low confidence

        estimate = est.get_estimate()

        assert estimate["kalman_confidence"]["level"] in ["LOW", "VERY_LOW"]


# ============================================================================
# 16. UPDATE ADAPTIVE Q_r TESTS v5.8.3
# ============================================================================


class TestUpdateAdaptiveQr:
    """Tests for update_adaptive_Q_r method"""

    def test_parked_status(self):
        """Parked truck should have low Q_r (v5.8.5: more conservative)"""
        est = make_estimator(50.0)

        est.update_adaptive_Q_r(speed=0, rpm=0)

        assert est.Q_r == 0.005  # v5.8.5: reduced from 0.01

    def test_idle_status(self):
        """Idle truck should have low-medium Q_r (v5.8.5: more conservative)"""
        est = make_estimator(50.0)

        est.update_adaptive_Q_r(speed=1, rpm=700)

        assert est.Q_r == 0.02  # v5.8.5: reduced from 0.05

    def test_stopped_status(self):
        """Stopped (engine on, not moving) should have medium Q_r (v5.8.5: more conservative)"""
        est = make_estimator(50.0)

        est.update_adaptive_Q_r(speed=2, rpm=1000)

        assert est.Q_r == 0.02  # v5.8.5: reduced from 0.05

    def test_moving_status(self):
        """Moving truck should have higher Q_r"""
        est = make_estimator(50.0)

        est.update_adaptive_Q_r(speed=50, rpm=1500, consumption_lph=20.0)

        # v5.8.5: MOVING uses 0.05 + (consumption/50)*0.1 = 0.05 + 0.04 = 0.09
        assert est.Q_r >= 0.09  # Adjusted from 0.1

    def test_moving_scales_with_consumption(self):
        """Moving Q_r should scale with consumption"""
        est = make_estimator(50.0)

        est.update_adaptive_Q_r(speed=50, rpm=1500, consumption_lph=10.0)
        Q_r_low = est.Q_r

        est.update_adaptive_Q_r(speed=50, rpm=1500, consumption_lph=30.0)
        Q_r_high = est.Q_r

        assert Q_r_high > Q_r_low


# ============================================================================
# 17. SENSOR QUALITY UPDATE TESTS v5.8.3
# ============================================================================


class TestSensorQualityUpdate:
    """Tests for update_sensor_quality method"""

    def test_sensor_quality_returns_factor(self):
        """update_sensor_quality should return quality factor"""
        est = make_estimator(50.0)

        factor = est.update_sensor_quality(satellites=10, voltage=14.0)

        assert factor <= 1.0
        assert factor > 0.0

    def test_low_satellites_degrades_quality(self):
        """Few satellites should reduce quality factor"""
        est = make_estimator(50.0)

        factor_good = est.update_sensor_quality(satellites=12, voltage=14.0)
        factor_poor = est.update_sensor_quality(satellites=3, voltage=14.0)

        # Poor GPS should have lower or equal factor
        assert factor_poor <= factor_good

    def test_low_voltage_degrades_quality(self):
        """Low voltage should reduce quality factor"""
        est = make_estimator(50.0)

        factor_good = est.update_sensor_quality(satellites=10, voltage=14.0)
        factor_poor = est.update_sensor_quality(satellites=10, voltage=11.0)

        # Low voltage should have lower or equal factor
        assert factor_poor <= factor_good

    def test_sensor_diagnostics(self):
        """get_sensor_diagnostics should return quality info"""
        est = make_estimator(50.0)

        est.update_sensor_quality(satellites=8, voltage=13.5)

        diagnostics = est.get_sensor_diagnostics()

        assert "combined_quality_factor" in diagnostics
        assert "current_Q_L" in diagnostics
        assert "modules_available" in diagnostics
