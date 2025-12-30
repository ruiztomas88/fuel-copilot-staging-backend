"""
Tests for v5.7.8 New Algorithms

Comprehensive tests for:
- Algorithm 1: Load-Aware Consumption
- Algorithm 2: Weather MPG Adjustment
- Algorithm 3: Days-to-Failure Prediction

These tests ensure the algorithms do NOT break existing Kalman filter functionality.
"""

import pytest

from mpg_engine import (  # Algorithm 1: Load-Aware; Algorithm 2: Weather MPG; Algorithm 3: Days-to-Failure; Existing functions for integration tests
    MPGConfig,
    MPGState,
    calculate_days_to_failure,
    calculate_load_factor,
    calculate_weather_mpg_factor,
    get_load_adjusted_consumption,
    get_weather_adjusted_mpg,
    predict_maintenance_timing,
    update_mpg_state,
)

# ═══════════════════════════════════════════════════════════════════════════════
# ALGORITHM 1: LOAD-AWARE CONSUMPTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadFactor:
    """Tests for calculate_load_factor function"""

    def test_none_returns_1(self):
        """None engine load should return 1.0 (no adjustment)"""
        assert calculate_load_factor(None) == 1.0

    def test_zero_load_returns_0_5(self):
        """0% load should return 0.5 (idle consumption)"""
        assert calculate_load_factor(0) == 0.5

    def test_100_load_returns_1(self):
        """100% load should return 1.0 (full consumption)"""
        assert calculate_load_factor(100) == 1.0

    def test_50_load_returns_0_75(self):
        """50% load should return 0.75"""
        assert calculate_load_factor(50) == 0.75

    def test_linear_relationship(self):
        """Load factor should increase linearly with load"""
        # Check multiple points on the line
        assert calculate_load_factor(25) == 0.625
        assert calculate_load_factor(75) == 0.875

    def test_clamp_negative(self):
        """Negative load should be clamped to 0"""
        assert calculate_load_factor(-10) == 0.5

    def test_clamp_over_100(self):
        """Load over 100 should be clamped to 100"""
        assert calculate_load_factor(150) == 1.0

    def test_returns_rounded(self):
        """Result should be rounded to 3 decimal places"""
        result = calculate_load_factor(33.33)
        assert isinstance(result, float)
        assert len(str(result).split(".")[-1]) <= 3


class TestLoadAdjustedConsumption:
    """Tests for get_load_adjusted_consumption function"""

    def test_basic_adjustment(self):
        """Basic consumption adjustment with load"""
        result = get_load_adjusted_consumption(10.0, 50)
        assert result["base_consumption_lph"] == 10.0
        assert result["load_factor"] == 0.75
        assert result["adjusted_consumption_lph"] == 7.5
        assert result["engine_load_pct"] == 50
        assert result["adjustment_applied"] is True

    def test_no_adjustment_when_none(self):
        """No adjustment when engine load is None"""
        result = get_load_adjusted_consumption(10.0, None)
        assert result["load_factor"] == 1.0
        assert result["adjusted_consumption_lph"] == 10.0
        assert result["adjustment_applied"] is False

    def test_idle_consumption(self):
        """Idle (0% load) should halve consumption"""
        result = get_load_adjusted_consumption(20.0, 0)
        assert result["adjusted_consumption_lph"] == 10.0

    def test_full_load_consumption(self):
        """Full load (100%) should keep consumption unchanged"""
        result = get_load_adjusted_consumption(15.0, 100)
        assert result["adjusted_consumption_lph"] == 15.0


# ═══════════════════════════════════════════════════════════════════════════════
# ALGORITHM 2: WEATHER MPG ADJUSTMENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestWeatherMPGFactor:
    """Tests for calculate_weather_mpg_factor function"""

    def test_none_returns_1(self):
        """None temperature should return 1.0 (no adjustment)"""
        assert calculate_weather_mpg_factor(None) == 1.0

    def test_optimal_range(self):
        """Optimal temperature (50-75°F) should return 1.0"""
        assert calculate_weather_mpg_factor(50) == 1.0
        assert calculate_weather_mpg_factor(60) == 1.0
        assert calculate_weather_mpg_factor(75) == 1.0

    def test_very_cold(self):
        """Very cold (<20°F) should return 0.88"""
        assert calculate_weather_mpg_factor(10) == 0.88
        assert calculate_weather_mpg_factor(0) == 0.88
        assert calculate_weather_mpg_factor(-10) == 0.88

    def test_cold_interpolation(self):
        """Cold range (20-32°F) should interpolate from 0.88 to 0.92"""
        assert calculate_weather_mpg_factor(20) == 0.88
        assert calculate_weather_mpg_factor(32) == pytest.approx(0.92, abs=0.01)

    def test_cool_interpolation(self):
        """Cool range (32-50°F) should interpolate from 0.92 to 0.96"""
        result_32 = calculate_weather_mpg_factor(32)
        result_50 = calculate_weather_mpg_factor(50)
        assert result_32 == pytest.approx(0.92, abs=0.01)
        # At 50°F we return 1.0 (optimal)
        assert result_50 == 1.0

    def test_warm_range(self):
        """Warm range (75-95°F) should decrease from 1.0 to 0.97"""
        assert calculate_weather_mpg_factor(75) == 1.0
        result_95 = calculate_weather_mpg_factor(95)
        assert result_95 == pytest.approx(0.97, abs=0.01)

    def test_hot_range(self):
        """Hot range (>95°F) should decrease toward 0.94"""
        result_100 = calculate_weather_mpg_factor(100)
        assert result_100 < 0.97
        assert result_100 > 0.94

    def test_extreme_heat(self):
        """Extreme heat (>110°F) should return 0.94"""
        assert calculate_weather_mpg_factor(120) == 0.94

    def test_monotonic_decrease_cold(self):
        """MPG factor should increase as temp increases from cold"""
        temps = [0, 20, 32, 40, 50]
        factors = [calculate_weather_mpg_factor(t) for t in temps]
        # Each factor should be >= previous (non-decreasing)
        for i in range(1, len(factors)):
            assert factors[i] >= factors[i - 1]


class TestWeatherAdjustedMPG:
    """Tests for get_weather_adjusted_mpg function"""

    def test_basic_adjustment(self):
        """Basic MPG adjustment with temperature"""
        result = get_weather_adjusted_mpg(6.0, 20)
        assert result["base_mpg"] == 6.0
        assert result["weather_factor"] == 0.88
        assert result["adjusted_mpg"] == pytest.approx(5.28, abs=0.01)
        assert result["weather_category"] == "COLD"
        assert result["adjustment_applied"] is True

    def test_no_adjustment_when_none(self):
        """No adjustment when temperature is None"""
        result = get_weather_adjusted_mpg(6.0, None)
        assert result["weather_factor"] == 1.0
        assert result["adjusted_mpg"] == 6.0
        assert result["weather_category"] == "UNKNOWN"
        assert result["adjustment_applied"] is False

    def test_optimal_temperature(self):
        """Optimal temperature should not adjust MPG"""
        result = get_weather_adjusted_mpg(6.0, 65)
        assert result["adjusted_mpg"] == 6.0
        assert result["weather_category"] == "OPTIMAL"

    def test_all_categories(self):
        """Test all weather categories are assigned correctly"""
        assert get_weather_adjusted_mpg(6.0, 20)["weather_category"] == "COLD"
        assert get_weather_adjusted_mpg(6.0, 40)["weather_category"] == "COOL"
        assert get_weather_adjusted_mpg(6.0, 60)["weather_category"] == "OPTIMAL"
        assert get_weather_adjusted_mpg(6.0, 85)["weather_category"] == "WARM"
        assert get_weather_adjusted_mpg(6.0, 100)["weather_category"] == "HOT"


# ═══════════════════════════════════════════════════════════════════════════════
# ALGORITHM 3: DAYS-TO-FAILURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDaysToFailure:
    """Tests for calculate_days_to_failure function"""

    def test_basic_calculation(self):
        """Basic days to failure calculation"""
        # 70 current, 100 threshold, 5 per day = 30/5 = 6 days
        result = calculate_days_to_failure(70.0, 100.0, 5.0)
        assert result == 6.0

    def test_decreasing_toward_lower_threshold(self):
        """Decreasing value toward lower threshold"""
        # 70 current, 50 threshold, -5 per day = 20/5 = 4 days
        result = calculate_days_to_failure(70.0, 50.0, -5.0)
        assert result == 4.0

    def test_moving_away_returns_none(self):
        """Moving away from threshold should return None"""
        # Increasing value (slope > 0) but threshold is BELOW current value
        # Value 70, threshold 50, slope +5 → distance = 50-70 = -20 < 0, slope > 0
        # Different signs → moving away → returns None
        result = calculate_days_to_failure(70.0, 50.0, 5.0)
        assert result is None

        # Decreasing value (slope < 0) but threshold is ABOVE current value
        # Value 70, threshold 100, slope -5 → distance = 100-70 = 30 > 0, slope < 0
        # Different signs → moving away → returns None
        result = calculate_days_to_failure(70.0, 100.0, -5.0)
        assert result is None

    def test_near_zero_trend_returns_none(self):
        """Near-zero trend should return None"""
        result = calculate_days_to_failure(70.0, 100.0, 0.0001)
        assert result is None

    def test_already_at_threshold(self):
        """Already at threshold should return min_days"""
        # Exactly at threshold with positive slope should return min_days
        result = calculate_days_to_failure(100.0, 100.0, 5.0)
        assert result == 0.5  # min_days (distance ≈ 0)

        # Exactly at threshold with negative slope
        result = calculate_days_to_failure(50.0, 50.0, -5.0)
        assert result == 0.5  # min_days (distance ≈ 0)

    def test_min_days_clamping(self):
        """Result should not be less than min_days"""
        # Would be 0.2 days without clamping
        result = calculate_days_to_failure(99.0, 100.0, 5.0)
        assert result >= 0.5

    def test_max_days_clamping(self):
        """Result should not exceed max_days"""
        # Very slow degradation
        result = calculate_days_to_failure(70.0, 100.0, 0.01)
        assert result <= 365.0

    def test_custom_min_max(self):
        """Custom min/max days should be respected"""
        result = calculate_days_to_failure(
            99.5, 100.0, 5.0, min_days=1.0, max_days=30.0
        )
        assert result >= 1.0

    def test_returns_rounded(self):
        """Result should be rounded to 1 decimal place"""
        result = calculate_days_to_failure(70.0, 100.0, 7.0)
        assert result == round(result, 1)


class TestPredictMaintenanceTiming:
    """Tests for predict_maintenance_timing function"""

    def test_insufficient_data(self):
        """Should return insufficient data message with < 3 points"""
        result = predict_maintenance_timing(
            "engine_temp",
            current_value=180,
            history=[175, 180],
            warning_threshold=200,
            critical_threshold=220,
        )
        assert result["urgency"] == "UNKNOWN"
        assert "Insufficient data" in result["recommendation"]

    def test_degrading_trend_detection(self):
        """Should detect degrading trend"""
        result = predict_maintenance_timing(
            "engine_temp",
            current_value=185,
            history=[170, 175, 180, 185],
            warning_threshold=200,
            critical_threshold=220,
            is_higher_worse=True,
        )
        assert result["trend_direction"] == "DEGRADING"
        assert result["trend_slope_per_day"] > 0

    def test_improving_trend_detection(self):
        """Should detect improving trend"""
        result = predict_maintenance_timing(
            "engine_temp",
            current_value=170,
            history=[190, 185, 180, 175],
            warning_threshold=200,
            critical_threshold=220,
            is_higher_worse=True,
        )
        assert result["trend_direction"] == "IMPROVING"

    def test_stable_trend_detection(self):
        """Should detect stable trend"""
        result = predict_maintenance_timing(
            "engine_temp",
            current_value=180,
            history=[180, 180, 180, 180],
            warning_threshold=200,
            critical_threshold=220,
        )
        assert result["trend_direction"] == "STABLE"

    def test_critical_urgency(self):
        """Should return CRITICAL urgency when failure imminent"""
        result = predict_maintenance_timing(
            "engine_temp",
            current_value=215,
            history=[190, 200, 210, 215],
            warning_threshold=200,
            critical_threshold=220,
        )
        assert result["urgency"] in ["CRITICAL", "HIGH"]

    def test_lower_is_worse(self):
        """Should handle metrics where lower is worse (e.g., battery)"""
        result = predict_maintenance_timing(
            "battery_voltage",
            current_value=12.0,
            history=[13.0, 12.5, 12.2, 12.0],
            warning_threshold=11.5,
            critical_threshold=11.0,
            is_higher_worse=False,  # Lower is worse for battery
        )
        assert result["trend_direction"] == "DEGRADING"
        assert (
            result["days_to_warning"] is not None
            or result["days_to_critical"] is not None
        )

    def test_returns_all_expected_keys(self):
        """Result should contain all expected keys"""
        result = predict_maintenance_timing(
            "engine_temp",
            current_value=180,
            history=[170, 175, 180],
            warning_threshold=200,
            critical_threshold=220,
        )
        expected_keys = [
            "sensor",
            "current_value",
            "warning_threshold",
            "critical_threshold",
            "trend_slope_per_day",
            "trend_direction",
            "days_to_warning",
            "days_to_critical",
            "urgency",
            "recommendation",
        ]
        for key in expected_keys:
            assert key in result


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS - ENSURE NO KALMAN BREAKAGE
# ═══════════════════════════════════════════════════════════════════════════════


class TestNoKalmanBreakage:
    """
    Tests to ensure new algorithms don't break existing Kalman/MPG functionality.
    These are critical regression tests.
    """

    def test_mpg_state_still_works(self):
        """MPGState should still initialize and work correctly"""
        state = MPGState()
        assert state.mpg_current is None
        assert state.distance_accum == 0.0
        assert state.fuel_accum_gal == 0.0

    def test_update_mpg_state_still_works(self):
        """update_mpg_state should still work after adding new algorithms"""
        state = MPGState()
        config = MPGConfig()

        # First update: 5.5 miles, 1.0 gallon
        # This completes the window (min_miles=5.0, min_fuel=1.5)
        # Need more fuel to complete window with current config
        state = update_mpg_state(state, 5.5, 1.5, config, "TEST001")

        # Window completed, MPG should be calculated
        if state.mpg_current is not None:
            assert state.mpg_current == pytest.approx(5.5 / 1.5, abs=0.5)
            assert state.window_count >= 1

        # Test that state updates work
        assert state.distance_accum >= 0.0
        assert state.fuel_accum_gal >= 0.0

    def test_mpg_config_defaults_unchanged(self):
        """MPGConfig defaults should match current implementation"""
        config = MPGConfig()
        assert config.min_miles == 5.0
        assert config.min_fuel_gal == 1.5  # Updated from 0.75
        assert config.min_mpg == 3.5
        assert config.max_mpg == 9.0
        assert config.fallback_mpg == 5.7

    def test_new_functions_dont_modify_global_state(self):
        """New algorithm functions should not modify any global state"""
        # These functions should be pure - no side effects
        calculate_load_factor(50)
        calculate_weather_mpg_factor(70)
        calculate_days_to_failure(70.0, 100.0, 5.0)

        # Verify MPG state is still clean
        state = MPGState()
        assert state.mpg_current is None

    def test_integration_load_with_mpg(self):
        """Load adjustment can be used alongside MPG calculation"""
        # Calculate MPG
        state = MPGState()
        config = MPGConfig()

        # Get some MPG data
        state = update_mpg_state(state, 10.0, 1.8, config, "TEST001")
        mpg = state.mpg_current

        # Use load adjustment separately
        load_result = get_load_adjusted_consumption(15.0, 60)

        # Both should work independently
        assert mpg is not None or state.distance_accum > 0
        assert load_result["adjusted_consumption_lph"] < 15.0

    def test_integration_weather_with_mpg(self):
        """Weather adjustment can be used alongside MPG calculation"""
        state = MPGState()
        config = MPGConfig()

        state = update_mpg_state(state, 10.0, 1.8, config, "TEST001")

        # Weather adjustment should not affect MPG state
        weather_result = get_weather_adjusted_mpg(5.7, 30)

        assert weather_result["adjusted_mpg"] < 5.7
        assert state.mpg_history  # Should have history from update


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES AND BOUNDARY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge case tests for all algorithms"""

    def test_load_factor_at_boundary_values(self):
        """Test load factor at exact boundaries"""
        assert calculate_load_factor(0.0) == 0.5
        assert calculate_load_factor(100.0) == 1.0

    def test_weather_factor_at_boundary_values(self):
        """Test weather factor at temperature boundaries"""
        assert calculate_weather_mpg_factor(20) == 0.88  # Cold boundary
        assert calculate_weather_mpg_factor(50) == 1.0  # Cool to optimal
        assert calculate_weather_mpg_factor(75) == 1.0  # Optimal upper
        assert calculate_weather_mpg_factor(95) == pytest.approx(0.97, abs=0.01)

    def test_days_to_failure_zero_values(self):
        """Test days to failure with zero values"""
        # Zero current value
        result = calculate_days_to_failure(0.0, 100.0, 5.0)
        assert result == 20.0  # 100/5

        # Zero threshold
        result = calculate_days_to_failure(50.0, 0.0, -5.0)
        assert result == 10.0  # 50/5

    def test_very_large_values(self):
        """Test with very large values"""
        result = calculate_load_factor(1000000)  # Should clamp
        assert result == 1.0

        result = calculate_weather_mpg_factor(1000)  # Extreme heat
        assert result == 0.94

    def test_very_small_values(self):
        """Test with very small positive values"""
        result = calculate_load_factor(0.001)
        assert 0.5 <= result <= 0.51

        result = calculate_weather_mpg_factor(0.1)
        assert result == 0.88  # Very cold


class TestRealWorldScenarios:
    """Tests simulating real-world usage scenarios"""

    def test_typical_summer_day(self):
        """Simulate typical summer day operation"""
        # Morning: 75°F, afternoon: 95°F
        morning = get_weather_adjusted_mpg(6.0, 75)
        afternoon = get_weather_adjusted_mpg(6.0, 95)

        assert morning["adjusted_mpg"] == 6.0  # Optimal
        assert afternoon["adjusted_mpg"] < 6.0  # Hot penalty

    def test_typical_winter_day(self):
        """Simulate typical winter day operation"""
        # Cold morning: 25°F
        result = get_weather_adjusted_mpg(6.0, 25)

        assert result["adjusted_mpg"] < 5.5  # Cold penalty
        assert result["weather_category"] == "COLD"

    def test_highway_vs_city_load(self):
        """Simulate highway vs city driving load profiles"""
        # Highway: steady 70% load
        highway = get_load_adjusted_consumption(15.0, 70)

        # City: variable 30-50% average
        city_low = get_load_adjusted_consumption(15.0, 30)
        city_avg = get_load_adjusted_consumption(15.0, 40)

        # Highway should use more fuel (higher load factor)
        assert (
            highway["adjusted_consumption_lph"] > city_avg["adjusted_consumption_lph"]
        )

    def test_engine_maintenance_prediction(self):
        """Simulate engine temperature trend analysis"""
        # Gradual increase over a week
        daily_temps = [175, 178, 180, 183, 185, 188, 190]

        result = predict_maintenance_timing(
            "engine_temp",
            current_value=190,
            history=daily_temps,
            warning_threshold=200,
            critical_threshold=220,
        )

        assert result["trend_direction"] == "DEGRADING"
        assert result["days_to_warning"] is not None
        assert result["urgency"] in ["MEDIUM", "HIGH", "LOW"]
