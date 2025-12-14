"""
Tests for Load Factor and Weather Factor Integration (v5.7.10)

Tests cover:
1. calculate_load_factor function
2. calculate_weather_mpg_factor function
3. Integration with Kalman predict (load adjustment)
4. Integration with MPG display (weather adjustment)
"""

import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mpg_engine import (
    calculate_load_factor,
    calculate_weather_mpg_factor,
    get_load_adjusted_consumption,
    get_weather_adjusted_mpg,
)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST LOAD FACTOR
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateLoadFactor:
    """Tests for calculate_load_factor function"""

    def test_zero_load_returns_half(self):
        """0% engine load = 0.5 factor (50% consumption)"""
        result = calculate_load_factor(0)
        assert result == 0.5

    def test_full_load_returns_one(self):
        """100% engine load = 1.0 factor (100% consumption)"""
        result = calculate_load_factor(100)
        assert result == 1.0

    def test_medium_load(self):
        """50% engine load = 0.75 factor"""
        result = calculate_load_factor(50)
        assert result == 0.75

    def test_none_returns_one(self):
        """None engine load = 1.0 (no adjustment)"""
        result = calculate_load_factor(None)
        assert result == 1.0

    def test_negative_clamped_to_zero(self):
        """Negative values clamped to 0%"""
        result = calculate_load_factor(-10)
        assert result == 0.5  # Same as 0%

    def test_over_100_clamped(self):
        """Values > 100 clamped to 100%"""
        result = calculate_load_factor(150)
        assert result == 1.0  # Same as 100%

    def test_typical_idle_load(self):
        """~20% load during idle = ~0.6 factor"""
        result = calculate_load_factor(20)
        assert result == 0.6

    def test_highway_cruise_load(self):
        """~40-60% load during cruise"""
        result = calculate_load_factor(40)
        assert result == 0.7

        result = calculate_load_factor(60)
        assert result == 0.8

    def test_uphill_load(self):
        """~80% load going uphill"""
        result = calculate_load_factor(80)
        assert result == 0.9


class TestGetLoadAdjustedConsumption:
    """Tests for get_load_adjusted_consumption helper"""

    def test_basic_adjustment(self):
        """Test basic load adjustment calculation"""
        result = get_load_adjusted_consumption(
            base_consumption_lph=10.0,
            engine_load_pct=50,
        )

        assert result["base_consumption_lph"] == 10.0
        assert result["load_factor"] == 0.75
        assert result["adjusted_consumption_lph"] == 7.5
        assert result["adjustment_applied"] is True

    def test_no_load_data(self):
        """Test when engine load is None"""
        result = get_load_adjusted_consumption(
            base_consumption_lph=10.0,
            engine_load_pct=None,
        )

        assert result["load_factor"] == 1.0
        assert result["adjusted_consumption_lph"] == 10.0
        assert result["adjustment_applied"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# TEST WEATHER FACTOR
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateWeatherMpgFactor:
    """Tests for calculate_weather_mpg_factor function"""

    def test_optimal_temperature_70f(self):
        """70°F = optimal = 1.0 factor"""
        result = calculate_weather_mpg_factor(70)
        assert result == 1.0

    def test_optimal_range_60f(self):
        """60°F = optimal = 1.0 factor"""
        result = calculate_weather_mpg_factor(60)
        assert result == 1.0

    def test_none_returns_one(self):
        """None temperature = 1.0 (no adjustment)"""
        result = calculate_weather_mpg_factor(None)
        assert result == 1.0

    def test_very_cold_10f(self):
        """10°F = very cold = 0.88 factor (12% worse)"""
        result = calculate_weather_mpg_factor(10)
        assert result == 0.88

    def test_cold_25f(self):
        """25°F = cold = ~0.90 factor"""
        result = calculate_weather_mpg_factor(25)
        # Linear interpolation between 20°F (0.88) and 32°F (0.92)
        assert 0.88 < result < 0.92

    def test_freezing_32f(self):
        """32°F = cool = 0.92 factor"""
        result = calculate_weather_mpg_factor(32)
        assert result == 0.92

    def test_cool_40f(self):
        """40°F = cool = ~0.94 factor"""
        result = calculate_weather_mpg_factor(40)
        # Linear interpolation between 32°F (0.92) and 50°F (0.96)
        assert 0.92 < result < 0.96

    def test_warm_85f(self):
        """85°F = warm = ~0.985 factor"""
        result = calculate_weather_mpg_factor(85)
        # Linear interpolation between 75°F (1.0) and 95°F (0.97)
        assert 0.97 < result < 1.0

    def test_hot_100f(self):
        """100°F = hot = ~0.96 factor"""
        result = calculate_weather_mpg_factor(100)
        # Linear interpolation between 95°F (0.97) and 110°F (0.94)
        assert 0.94 < result < 0.97

    def test_extreme_heat_115f(self):
        """115°F = extreme heat = 0.94 factor"""
        result = calculate_weather_mpg_factor(115)
        assert result == 0.94


class TestGetWeatherAdjustedMpg:
    """Tests for get_weather_adjusted_mpg helper"""

    def test_optimal_no_adjustment(self):
        """In optimal temperature, no adjustment needed"""
        result = get_weather_adjusted_mpg(
            base_mpg=6.0,
            ambient_temp_f=70,
        )

        assert result["base_mpg"] == 6.0
        assert result["weather_factor"] == 1.0
        assert result["adjusted_mpg"] == 6.0
        assert result["weather_category"] == "OPTIMAL"
        assert result["adjustment_applied"] is True

    def test_cold_weather_adjustment(self):
        """Cold weather reduces expected MPG"""
        result = get_weather_adjusted_mpg(
            base_mpg=6.0,
            ambient_temp_f=20,
        )

        assert result["base_mpg"] == 6.0
        assert result["weather_factor"] == 0.88
        # 6.0 * 0.88 = 5.28
        assert result["adjusted_mpg"] == 5.28
        assert result["weather_category"] == "COLD"

    def test_hot_weather_adjustment(self):
        """Hot weather slightly reduces expected MPG"""
        result = get_weather_adjusted_mpg(
            base_mpg=6.0,
            ambient_temp_f=100,
        )

        assert result["weather_category"] == "HOT"
        # Factor should be around 0.96
        assert result["adjusted_mpg"] < 6.0

    def test_no_temperature_data(self):
        """When temperature is None, no adjustment"""
        result = get_weather_adjusted_mpg(
            base_mpg=6.0,
            ambient_temp_f=None,
        )

        assert result["weather_factor"] == 1.0
        assert result["adjusted_mpg"] == 6.0
        assert result["weather_category"] == "UNKNOWN"
        assert result["adjustment_applied"] is False


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestLoadFactorKalmanIntegration:
    """Tests for load_factor integration with Kalman predict"""

    def test_consumption_reduced_at_low_load(self):
        """Low engine load should reduce predicted consumption"""
        base_consumption = 20.0  # L/h at full load

        # At 20% load
        load_factor = calculate_load_factor(20)
        adjusted = base_consumption * load_factor

        # Should be 20 * 0.6 = 12 L/h
        assert adjusted == 12.0
        assert adjusted < base_consumption

    def test_consumption_same_at_full_load(self):
        """Full engine load keeps consumption the same"""
        base_consumption = 20.0

        load_factor = calculate_load_factor(100)
        adjusted = base_consumption * load_factor

        assert adjusted == 20.0
        assert adjusted == base_consumption

    def test_consumption_halved_at_idle(self):
        """Idle (0% load) halves the consumption"""
        base_consumption = 20.0

        load_factor = calculate_load_factor(0)
        adjusted = base_consumption * load_factor

        assert adjusted == 10.0
        assert adjusted == base_consumption / 2


class TestWeatherFactorMpgIntegration:
    """Tests for weather_factor integration with MPG display"""

    def test_cold_weather_mpg_interpretation(self):
        """In cold weather, same raw MPG represents better-than-expected performance"""
        raw_mpg = 5.5  # Actual measured MPG
        ambient_temp = 20  # Cold

        weather_factor = calculate_weather_mpg_factor(ambient_temp)
        # Weather factor = 0.88 (we expect 12% worse MPG in cold)

        # What would this MPG be in optimal conditions?
        # If we're getting 5.5 MPG in conditions where we expect 12% worse,
        # then in optimal conditions this truck would get:
        optimal_equivalent = raw_mpg / weather_factor

        # 5.5 / 0.88 = 6.25 MPG (better than it looks!)
        assert optimal_equivalent > raw_mpg
        assert round(optimal_equivalent, 2) == 6.25

    def test_optimal_weather_no_change(self):
        """In optimal weather, MPG is what it appears to be"""
        raw_mpg = 6.0
        ambient_temp = 70  # Optimal

        weather_factor = calculate_weather_mpg_factor(ambient_temp)
        optimal_equivalent = raw_mpg / weather_factor

        # Should be the same
        assert optimal_equivalent == raw_mpg

    def test_hot_weather_mpg_interpretation(self):
        """In hot weather, MPG represents slightly better-than-expected"""
        raw_mpg = 5.8
        ambient_temp = 100  # Hot

        weather_factor = calculate_weather_mpg_factor(ambient_temp)
        # Factor ~0.96 (expect 4% worse)

        optimal_equivalent = raw_mpg / weather_factor

        # Should be slightly higher (truck doing better than expected)
        assert optimal_equivalent > raw_mpg


class TestLoadAndWeatherCombined:
    """Test combined load and weather factors"""

    def test_both_factors_independent(self):
        """Load factor affects consumption, weather factor affects MPG display"""
        # Load factor reduces consumption prediction
        base_consumption = 20.0
        engine_load = 50
        load_factor = calculate_load_factor(engine_load)
        adjusted_consumption = base_consumption * load_factor

        assert adjusted_consumption == 15.0  # 20 * 0.75

        # Weather factor adjusts MPG display
        raw_mpg = 5.5
        ambient_temp = 30  # Cold
        weather_factor = calculate_weather_mpg_factor(ambient_temp)
        weather_adjusted_mpg = raw_mpg / weather_factor

        # Both can be applied independently
        assert load_factor < 1.0  # Reduces consumption
        assert weather_factor < 1.0  # Indicates MPG is better than it looks

    def test_factors_with_sensor_unavailable(self):
        """System works when sensors are unavailable"""
        # No engine load sensor
        load_factor = calculate_load_factor(None)
        assert load_factor == 1.0  # No adjustment

        # No ambient temp sensor
        weather_factor = calculate_weather_mpg_factor(None)
        assert weather_factor == 1.0  # No adjustment

        # System continues to work normally
        base_consumption = 20.0
        adjusted = base_consumption * load_factor
        assert adjusted == 20.0


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES AND BOUNDARY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Edge cases and boundary conditions"""

    def test_load_factor_boundary_values(self):
        """Test boundary values for load factor"""
        # Just above 0
        assert calculate_load_factor(0.001) >= 0.5  # Essentially 0

        # Just below 100
        assert calculate_load_factor(99.999) <= 1.0  # Essentially 100

        # Exactly 0 and 100
        assert calculate_load_factor(0) == 0.5
        assert calculate_load_factor(100) == 1.0

    def test_weather_factor_boundary_values(self):
        """Test boundary values for weather factor"""
        # At boundaries of optimal range
        assert calculate_weather_mpg_factor(50) == 1.0  # Start of optimal
        assert calculate_weather_mpg_factor(75) == 1.0  # End of optimal

        # Just outside optimal
        assert calculate_weather_mpg_factor(49.9) < 1.0  # Cool side
        assert calculate_weather_mpg_factor(75.1) < 1.0  # Warm side

    def test_extreme_temperatures(self):
        """Test extreme temperature values"""
        # Arctic cold
        result = calculate_weather_mpg_factor(-40)
        assert result == 0.88  # Capped at very cold

        # Desert heat
        result = calculate_weather_mpg_factor(130)
        assert result == 0.94  # Capped at extreme heat

    def test_factor_precision(self):
        """Test that factors have appropriate precision"""
        load_factor = calculate_load_factor(33.333)
        # Should be rounded to 3 decimal places
        assert len(str(load_factor).split(".")[-1]) <= 3

        weather_factor = calculate_weather_mpg_factor(45.5)
        # Weather factor is also calculated with reasonable precision
        assert isinstance(weather_factor, float)
