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
    """Large time gap reduces consumption (capped)"""
    est = make_estimator(50.0)
    initial_L = est.L
    assert initial_L is not None

    # 2.5 hour gap - consumption may be capped
    est.predict(dt_hours=2.5, consumption_lph=20.0)

    # Should consume something (capped max)
    assert est.L is not None
    assert est.L < initial_L  # Some consumption happened


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
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
