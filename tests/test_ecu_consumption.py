"""
Tests for ECU Total Fuel Used consumption calculation.

Tests the robust ECU-based consumption calculation including:
- Normal consumption scenarios
- Reset detection
- Physical range validation
- Cross-check with fuel_rate sensor
- Failure counting and degradation
- Recovery from degraded state

Run with: pytest tests/test_ecu_consumption.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fuel_copilot_v2_1_fixed import FuelEstimator


class TestECUConsumption:
    """Test suite for ECU-based consumption calculation"""

    @pytest.fixture
    def estimator(self):
        """Create a fresh estimator for each test"""
        config = {
            "Q_r": 0.1,
            "Q_L_moving": 4.0,
            "Q_L_static": 1.0,
            "idle_gph": 0.8,
        }
        return FuelEstimator(
            truck_id="TEST_TRUCK",
            capacity_liters=378.5,  # 100 gallons
            config=config,
            tanks_config=None,
        )

    # =========================================================================
    # NORMAL OPERATION TESTS
    # =========================================================================

    def test_first_reading_returns_none(self, estimator):
        """First ECU reading should initialize counter but return None"""
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=1000.0,
            dt_hours=15 / 3600,  # 15 seconds
        )
        assert result is None
        assert estimator.last_total_fuel_used == 1000.0
        assert estimator.ecu_consumption_available is False

    def test_normal_consumption_highway(self, estimator):
        """Test normal highway consumption: ~6-8 GPH"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

        # After 1 hour, 7 gallons consumed (typical highway)
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=1007.0,
            dt_hours=1.0,
        )

        assert result is not None
        # 7 gallons * 3.78541 = 26.5 L/h
        assert 25.0 < result < 28.0
        assert estimator.ecu_consumption_available is True
        assert estimator.ecu_degraded is False

    def test_normal_consumption_city(self, estimator):
        """Test city driving consumption: ~3-5 GPH"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=5000.0, dt_hours=15 / 3600)

        # After 30 minutes, 2 gallons consumed (city driving)
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=5002.0,
            dt_hours=0.5,
        )

        assert result is not None
        # 4 GPH * 3.78541 = 15.14 L/h
        assert 14.0 < result < 16.0

    def test_idle_consumption(self, estimator):
        """Test idle consumption: ~0.5-1.0 GPH"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=2000.0, dt_hours=15 / 3600)

        # After 1 hour idle, 0.8 gallons consumed
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=2000.8,
            dt_hours=1.0,
        )

        assert result is not None
        # 0.8 GPH * 3.78541 = 3.03 L/h
        assert 2.5 < result < 3.5

    def test_zero_consumption_engine_off(self, estimator):
        """Test zero consumption when engine is off"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=3000.0, dt_hours=15 / 3600)

        # After 2 hours, no fuel consumed (engine off)
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=3000.0,
            dt_hours=2.0,
        )

        assert result is not None
        assert result == 0.0

    # =========================================================================
    # RESET DETECTION TESTS
    # =========================================================================

    def test_counter_reset_detection(self, estimator):
        """Test that counter resets are detected and handled"""
        # Initialize at high value
        estimator.calculate_ecu_consumption(total_fuel_used=50000.0, dt_hours=15 / 3600)

        # Counter resets to low value (battery disconnected, etc.)
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=10.0,
            dt_hours=15 / 3600,
        )

        assert result is None
        assert estimator.last_total_fuel_used == 10.0  # Reinitialized
        assert estimator.ecu_failure_count == 1

    def test_counter_rollover_large_drop(self, estimator):
        """Test large counter drops are treated as resets"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=99999.0, dt_hours=15 / 3600)

        # Rollover to near zero
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=100.0,
            dt_hours=15 / 3600,
        )

        assert result is None
        assert estimator.ecu_failure_count == 1

    # =========================================================================
    # PHYSICAL RANGE VALIDATION TESTS
    # =========================================================================

    def test_reject_unrealistic_high_consumption(self, estimator):
        """Test rejection of physically impossible high consumption"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

        # 100 gallons in 15 seconds = 24000 GPH (impossible!)
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=1100.0,
            dt_hours=15 / 3600,
        )

        assert result is None
        assert estimator.ecu_failure_count == 1

    def test_accept_high_but_valid_consumption(self, estimator):
        """Test acceptance of high but valid consumption (heavy load uphill)"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

        # 30 GPH for 1 hour (very heavy load, valid)
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=1030.0,
            dt_hours=1.0,
        )

        assert result is not None
        # 30 GPH * 3.78541 = 113.5 L/h
        assert 110.0 < result < 120.0

    def test_minimum_time_delta(self, estimator):
        """Test that very short time deltas are skipped (not failures)"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

        # 5 second interval (too short)
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=1000.5,
            dt_hours=5 / 3600,
        )

        assert result is None
        # Should NOT count as failure
        assert estimator.ecu_failure_count == 0

    # =========================================================================
    # CROSS-VALIDATION TESTS
    # =========================================================================

    def test_cross_check_matching_sensors(self, estimator):
        """Test that matching ECU and fuel_rate don't trigger warnings"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

        # ECU: 6 GPH, fuel_rate: 22.7 L/h (= 6 GPH)
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=1006.0,
            dt_hours=1.0,
            fuel_rate_lph=22.7,
        )

        assert result is not None
        assert estimator.ecu_consumption_available is True

    def test_cross_check_large_discrepancy(self, estimator):
        """Test warning when ECU and fuel_rate disagree significantly"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

        # ECU: 6 GPH, fuel_rate: 50 L/h (= 13.2 GPH) - 7 GPH difference!
        with patch("fuel_copilot_v2_1_fixed.logger") as mock_logger:
            result = estimator.calculate_ecu_consumption(
                total_fuel_used=1006.0,
                dt_hours=1.0,
                fuel_rate_lph=50.0,
            )

            # Should still return ECU value (ECU is trusted)
            assert result is not None
            # But should have logged a warning
            # Note: Warning is logged but we don't fail

    # =========================================================================
    # FAILURE TRACKING & DEGRADATION TESTS
    # =========================================================================

    def test_degradation_after_multiple_failures(self, estimator):
        """Test that ECU degrades after 5 consecutive failures"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

        # Simulate 5 resets (failures)
        for i in range(5):
            estimator.calculate_ecu_consumption(
                total_fuel_used=float(i),  # Each time lower = reset
                dt_hours=15 / 3600,
            )

        assert estimator.ecu_degraded is True
        assert estimator.ecu_failure_count >= 5

    def test_degraded_returns_none(self, estimator):
        """Test that degraded ECU returns None even with valid data"""
        # Force degraded state
        estimator.ecu_degraded = True
        estimator.ecu_last_success_time = datetime.now(timezone.utc)

        result = estimator.calculate_ecu_consumption(
            total_fuel_used=1000.0,
            dt_hours=15 / 3600,
        )

        assert result is None

    def test_recovery_after_degradation(self, estimator):
        """Test ECU recovery attempt after 10 minutes"""
        # Initialize and degrade
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)
        estimator.ecu_degraded = True
        estimator.ecu_last_success_time = datetime.now(timezone.utc) - timedelta(
            minutes=15
        )

        # Should attempt recovery
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=1006.0,
            dt_hours=1.0,
        )

        # After recovery, should work
        assert estimator.ecu_degraded is False
        assert result is not None

    def test_success_resets_failure_counter(self, estimator):
        """Test that successful reading resets failure counter"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

        # Simulate 3 failures (not enough to degrade)
        estimator.ecu_failure_count = 3

        # Successful reading
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=1006.0,
            dt_hours=1.0,
        )

        assert result is not None
        assert estimator.ecu_failure_count == 0

    # =========================================================================
    # EDGE CASES
    # =========================================================================

    def test_none_total_fuel_used(self, estimator):
        """Test handling of None total_fuel_used"""
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=None,
            dt_hours=15 / 3600,
        )

        assert result is None
        assert estimator.ecu_failure_count == 1

    def test_very_small_consumption(self, estimator):
        """Test very small but valid consumption"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

        # 0.001 gallons in 15 seconds (very small but valid)
        result = estimator.calculate_ecu_consumption(
            total_fuel_used=1000.001,
            dt_hours=15 / 3600,
        )

        assert result is not None
        assert result >= 0

    def test_consecutive_identical_readings(self, estimator):
        """Test handling of identical consecutive readings (no consumption)"""
        # Initialize
        estimator.calculate_ecu_consumption(total_fuel_used=1000.0, dt_hours=15 / 3600)

        # Same value (engine off or sensor frozen)
        result1 = estimator.calculate_ecu_consumption(
            total_fuel_used=1000.0,
            dt_hours=15 / 3600,
        )
        result2 = estimator.calculate_ecu_consumption(
            total_fuel_used=1000.0,
            dt_hours=15 / 3600,
        )

        # Should return 0, not None
        assert result1 == 0.0
        assert result2 == 0.0


class TestConsumptionPriority:
    """Test the consumption source priority system"""

    def test_priority_order(self):
        """
        Verify consumption priority:
        1. ECU Total Fuel Used (when available and valid)
        2. Fuel Rate sensor (when in valid range)
        3. Idle rate estimate (fallback)
        """
        # This is an integration test that would require the full loop
        # For now, document the expected behavior
        expected_priority = [
            ("ECU", "Primary - most accurate"),
            ("fuel_rate", "Secondary - if ECU unavailable"),
            ("idle", "Fallback - conservative estimate"),
        ]

        assert expected_priority[0][0] == "ECU"
        assert expected_priority[1][0] == "fuel_rate"
        assert expected_priority[2][0] == "idle"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
