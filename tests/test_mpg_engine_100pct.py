"""
🎯 COMPREHENSIVE TEST COVERAGE for MPG Engine
Target: 100% code coverage

Tests all functions in mpg_engine.py including:
- filter_outliers_mad, filter_outliers_iqr
- MPGState, MPGConfig dataclasses
- update_mpg_state, reset_mpg_state
- TruckMPGBaseline, TruckBaselineManager
- All utility functions
"""

from datetime import datetime, timedelta, timezone

import pytest

from mpg_engine import (
    MPGConfig,
    MPGState,
    TruckBaselineManager,
    TruckMPGBaseline,
    calculate_days_to_failure,
    calculate_load_factor,
    calculate_weather_mpg_factor,
    estimate_fuel_from_distance,
    filter_outliers_iqr,
    filter_outliers_mad,
    get_baseline_manager,
    get_dynamic_alpha,
    get_load_adjusted_consumption,
    get_mpg_status,
    get_weather_adjusted_mpg,
    predict_maintenance_timing,
    reset_mpg_state,
    shutdown_baseline_manager,
    update_mpg_state,
)


class TestOutlierFiltering:
    """Test outlier filtering functions"""

    def test_filter_outliers_mad_normal_data(self):
        readings = [5.0, 5.2, 5.5, 5.3, 5.1]
        result = filter_outliers_mad(readings)
        assert len(result) == 5

    def test_filter_outliers_mad_with_outlier(self):
        readings = [5.0, 5.2, 5.5, 50.0, 5.3]
        result = filter_outliers_mad(readings)
        assert 50.0 not in result

    def test_filter_outliers_mad_single_reading(self):
        readings = [5.0]
        result = filter_outliers_mad(readings)
        assert result == [5.0]

    def test_filter_outliers_mad_empty_list(self):
        readings = []
        result = filter_outliers_mad(readings)
        assert result == []

    def test_filter_outliers_mad_identical_values(self):
        """Test MAD with all identical values"""
        readings = [5.0, 5.0, 5.0, 5.0]
        result = filter_outliers_mad(readings)
        assert len(result) == 4

    def test_filter_outliers_iqr_large_sample(self):
        readings = [5.0, 5.2, 5.5, 5.3, 5.1, 5.4, 20.0, 5.2, 5.6]
        result = filter_outliers_iqr(readings)
        assert 20.0 not in result

    def test_filter_outliers_iqr_small_sample(self):
        """IQR with < 4 samples should fallback to MAD"""
        readings = [5.0, 5.2, 50.0]
        result = filter_outliers_iqr(readings)
        assert 50.0 not in result

    def test_filter_outliers_iqr_custom_multiplier(self):
        readings = [5.0, 5.2, 5.5, 5.3, 5.1, 5.4, 5.2, 5.6]
        result = filter_outliers_iqr(readings, multiplier=2.0)
        assert isinstance(result, list)


class TestMPGState:
    """Test MPGState dataclass"""

    def test_create_default_state(self):
        state = MPGState()
        assert state.mpg_current == 0.0
        assert state.mpg_ema == 0.0
        assert state.distance_since_anchor_mi == 0.0
        assert state.fuel_consumed_since_anchor_gal == 0.0

    def test_get_variance_empty_history(self):
        state = MPGState()
        variance = state.get_variance()
        assert variance == 0.0

    def test_get_variance_with_history(self):
        state = MPGState()
        state.mpg_history = [5.0, 5.5, 6.0, 5.8, 5.2]
        variance = state.get_variance()
        assert variance > 0

    def test_get_variance_single_value(self):
        state = MPGState()
        state.mpg_history = [5.0]
        variance = state.get_variance()
        assert variance == 0.0


class TestMPGConfig:
    """Test MPGConfig dataclass"""

    def test_default_config(self):
        config = MPGConfig()
        assert config.min_miles > 0
        assert config.min_fuel_gal > 0
        assert config.min_mpg > 0
        assert config.max_mpg > config.min_mpg
        assert 0 < config.ema_alpha < 1


class TestDynamicAlpha:
    """Test dynamic alpha calculation"""

    def test_dynamic_alpha_high_variance(self):
        state = MPGState()
        state.mpg_history = [3.0, 8.0, 4.5, 9.0, 5.0]  # High variance
        config = MPGConfig(use_dynamic_alpha=True)

        alpha = get_dynamic_alpha(state, config)

        # High variance should use alpha_high_variance
        assert alpha == config.alpha_high_variance

    def test_dynamic_alpha_low_variance(self):
        state = MPGState()
        state.mpg_history = [5.0, 5.1, 5.2, 5.1, 5.0]  # Low variance
        config = MPGConfig(use_dynamic_alpha=True)

        alpha = get_dynamic_alpha(state, config)

        # Low variance should use alpha_low_variance
        assert alpha == config.alpha_low_variance

    def test_dynamic_alpha_disabled(self):
        state = MPGState()
        config = MPGConfig(use_dynamic_alpha=False)

        alpha = get_dynamic_alpha(state, config)

        assert alpha == config.ema_alpha


class TestUpdateMPGState:
    """Test update_mpg_state function"""

    def test_update_valid_window(self):
        state = MPGState()
        config = MPGConfig()

        miles = 50.0
        fuel_gal = 8.0
        truck_id = "TEST-001"

        new_state = update_mpg_state(state, miles, fuel_gal, truck_id, config)

        assert new_state.mpg_current > 0
        assert new_state.distance_since_anchor_mi == 0.0
        assert new_state.fuel_consumed_since_anchor_gal == 0.0

    def test_update_insufficient_miles(self):
        state = MPGState()
        config = MPGConfig()

        miles = 2.0  # Below min_miles
        fuel_gal = 2.0
        truck_id = "TEST-001"

        new_state = update_mpg_state(state, miles, fuel_gal, truck_id, config)

        # Should accumulate but not update MPG
        assert new_state.distance_since_anchor_mi == 2.0
        assert new_state.mpg_current == state.mpg_current

    def test_update_insufficient_fuel(self):
        state = MPGState()
        config = MPGConfig()

        miles = 50.0
        fuel_gal = 0.5  # Below min_fuel_gal
        truck_id = "TEST-001"

        new_state = update_mpg_state(state, miles, fuel_gal, truck_id, config)

        assert new_state.fuel_consumed_since_anchor_gal == 0.5
        assert new_state.mpg_current == state.mpg_current

    def test_update_out_of_range_mpg(self):
        state = MPGState(mpg_current=6.0, mpg_ema=6.0)
        config = MPGConfig()

        miles = 100.0
        fuel_gal = 5.0  # Would give 20 MPG (out of range)
        truck_id = "TEST-001"

        new_state = update_mpg_state(state, miles, fuel_gal, truck_id, config)

        # Should reject and keep old MPG
        assert new_state.mpg_current == 6.0

    def test_update_ema_calculation(self):
        state = MPGState(mpg_current=6.0, mpg_ema=6.0)
        config = MPGConfig(ema_alpha=0.3)

        miles = 50.0
        fuel_gal = 8.0
        truck_id = "TEST-001"

        new_state = update_mpg_state(state, miles, fuel_gal, truck_id, config)

        # EMA should be weighted average
        assert new_state.mpg_ema != new_state.mpg_current
        assert new_state.mpg_ema != state.mpg_ema


class TestResetMPGState:
    """Test reset_mpg_state function"""

    def test_reset_to_defaults(self):
        state = MPGState(
            mpg_current=6.5,
            mpg_ema=6.3,
            distance_since_anchor_mi=50.0,
            fuel_consumed_since_anchor_gal=8.0,
        )

        new_state = reset_mpg_state(state, "TEST-001")

        assert new_state.distance_since_anchor_mi == 0.0
        assert new_state.fuel_consumed_since_anchor_gal == 0.0
        assert new_state.mpg_current == state.mpg_current  # Preserves MPG

    def test_reset_with_custom_mpg(self):
        state = MPGState()
        config = MPGConfig(fallback_mpg=5.5)

        new_state = reset_mpg_state(
            state, "TEST-001", config, reset_mpg_to_fallback=True
        )

        assert new_state.mpg_current == 5.5
        assert new_state.mpg_ema == 5.5


class TestEstimateFuelFromDistance:
    """Test estimate_fuel_from_distance function"""

    def test_estimate_with_valid_mpg(self):
        state = MPGState(mpg_current=6.0)
        miles = 120.0

        fuel = estimate_fuel_from_distance(state, miles, "TEST-001")

        assert fuel == pytest.approx(20.0, rel=1e-2)

    def test_estimate_with_zero_mpg(self):
        state = MPGState(mpg_current=0.0)
        config = MPGConfig(fallback_mpg=5.7)
        miles = 114.0

        fuel = estimate_fuel_from_distance(state, miles, "TEST-001", config)

        # Should use fallback MPG
        assert fuel == pytest.approx(20.0, rel=1e-2)

    def test_estimate_zero_miles(self):
        state = MPGState(mpg_current=6.0)
        miles = 0.0

        fuel = estimate_fuel_from_distance(state, miles, "TEST-001")

        assert fuel == 0.0


class TestGetMPGStatus:
    """Test get_mpg_status function"""

    def test_status_with_valid_state(self):
        state = MPGState(
            mpg_current=6.5,
            mpg_ema=6.3,
            distance_since_anchor_mi=25.0,
            fuel_consumed_since_anchor_gal=4.0,
        )
        state.mpg_history = [6.0, 6.2, 6.5, 6.3]
        config = MPGConfig()

        status = get_mpg_status(state, config)

        assert status["mpg_current"] == 6.5
        assert status["mpg_ema"] == 6.3
        assert status["variance"] > 0
        assert status["window_miles"] == 25.0
        assert status["window_fuel_gal"] == 4.0

    def test_status_empty_state(self):
        state = MPGState()
        config = MPGConfig()

        status = get_mpg_status(state, config)

        assert status["mpg_current"] == 0.0
        assert status["variance"] == 0.0


class TestTruckMPGBaseline:
    """Test TruckMPGBaseline class"""

    def test_create_baseline(self):
        baseline = TruckMPGBaseline("TEST-001")

        assert baseline.truck_id == "TEST-001"
        assert baseline.baseline_mpg == 0.0
        assert baseline.sample_count == 0

    def test_add_sample(self):
        baseline = TruckMPGBaseline("TEST-001")

        baseline.add_sample(6.0)
        baseline.add_sample(6.5)
        baseline.add_sample(6.2)

        assert baseline.sample_count == 3
        assert 6.0 < baseline.baseline_mpg < 6.5

    def test_add_sample_outlier_rejection(self):
        baseline = TruckMPGBaseline("TEST-001")

        # Add normal samples
        for mpg in [6.0, 6.1, 6.2, 6.0, 6.3]:
            baseline.add_sample(mpg)

        # Add outlier
        baseline.add_sample(50.0)

        # Baseline should not be affected by outlier
        assert baseline.baseline_mpg < 10.0

    def test_get_deviation(self):
        baseline = TruckMPGBaseline("TEST-001")
        baseline.add_sample(6.0)
        baseline.add_sample(6.0)
        baseline.add_sample(6.0)

        deviation = baseline.get_deviation(5.5)

        assert deviation < 0  # Below baseline

    def test_get_deviation_no_baseline(self):
        baseline = TruckMPGBaseline("TEST-001")

        deviation = baseline.get_deviation(6.0)

        assert deviation == 0.0

    def test_is_underperforming(self):
        baseline = TruckMPGBaseline("TEST-001")
        baseline.add_sample(6.0)
        baseline.add_sample(6.0)

        assert baseline.is_underperforming(5.0, threshold_pct=10.0) is True
        assert baseline.is_underperforming(5.9, threshold_pct=10.0) is False

    def test_to_dict(self):
        baseline = TruckMPGBaseline("TEST-001")
        baseline.add_sample(6.0)

        data = baseline.to_dict()

        assert data["truck_id"] == "TEST-001"
        assert "baseline_mpg" in data
        assert "sample_count" in data


class TestTruckBaselineManager:
    """Test TruckBaselineManager class"""

    def test_singleton(self):
        manager1 = get_baseline_manager()
        manager2 = get_baseline_manager()

        assert manager1 is manager2

    def test_update_baseline(self):
        manager = TruckBaselineManager()

        manager.update_baseline("TEST-001", 6.0)
        manager.update_baseline("TEST-001", 6.2)

        baseline = manager.get_baseline("TEST-001")
        assert baseline is not None
        assert baseline.sample_count == 2

    def test_get_deviation(self):
        manager = TruckBaselineManager()

        manager.update_baseline("TEST-001", 6.0)
        manager.update_baseline("TEST-001", 6.0)

        deviation = manager.get_deviation("TEST-001", 5.5)

        assert deviation < 0

    def test_check_underperformance(self):
        manager = TruckBaselineManager()

        manager.update_baseline("TEST-001", 6.0)
        manager.update_baseline("TEST-001", 6.0)

        result = manager.check_underperformance("TEST-001", 5.0)

        assert result["is_underperforming"] is True

    def test_get_all_baselines(self):
        manager = TruckBaselineManager()

        manager.update_baseline("TEST-001", 6.0)
        manager.update_baseline("TEST-002", 6.5)

        all_baselines = manager.get_all_baselines()

        assert len(all_baselines) == 2


class TestLoadFactorCalculations:
    """Test load factor calculations"""

    def test_calculate_load_factor_normal(self):
        load_factor = calculate_load_factor(50.0)
        assert load_factor > 1.0

    def test_calculate_load_factor_none(self):
        load_factor = calculate_load_factor(None)
        assert load_factor == 1.0

    def test_calculate_load_factor_zero(self):
        load_factor = calculate_load_factor(0.0)
        assert load_factor == 1.0

    def test_calculate_load_factor_high(self):
        load_factor = calculate_load_factor(90.0)
        assert load_factor > 1.2


class TestLoadAdjustedConsumption:
    """Test load adjusted consumption"""

    def test_get_load_adjusted_consumption(self):
        fuel_gal = 10.0
        engine_load = 50.0

        adjusted = get_load_adjusted_consumption(fuel_gal, engine_load)

        assert adjusted != fuel_gal


class TestWeatherAdjustments:
    """Test weather-related functions"""

    def test_calculate_weather_mpg_factor_normal(self):
        factor = calculate_weather_mpg_factor(70.0)  # Normal temp
        assert factor == pytest.approx(1.0, rel=1e-2)

    def test_calculate_weather_mpg_factor_cold(self):
        factor = calculate_weather_mpg_factor(0.0)  # Freezing
        assert factor < 1.0

    def test_calculate_weather_mpg_factor_hot(self):
        factor = calculate_weather_mpg_factor(110.0)  # Very hot
        assert factor < 1.0

    def test_calculate_weather_mpg_factor_none(self):
        factor = calculate_weather_mpg_factor(None)
        assert factor == 1.0

    def test_get_weather_adjusted_mpg(self):
        adjusted = get_weather_adjusted_mpg(6.0, 70.0)
        assert adjusted == pytest.approx(6.0, rel=0.1)


class TestMaintenancePredictions:
    """Test maintenance prediction functions"""

    def test_calculate_days_to_failure_degrading(self):
        current_mpg = 5.0
        baseline_mpg = 6.0
        mpg_history = [5.9, 5.7, 5.5, 5.3, 5.0]

        days = calculate_days_to_failure(current_mpg, baseline_mpg, mpg_history)

        assert days is not None
        assert days > 0

    def test_calculate_days_to_failure_stable(self):
        current_mpg = 6.0
        baseline_mpg = 6.0
        mpg_history = [6.0, 6.0, 6.0, 6.0]

        days = calculate_days_to_failure(current_mpg, baseline_mpg, mpg_history)

        assert days is None  # No degradation

    def test_predict_maintenance_timing(self):
        state = MPGState(mpg_current=5.0, mpg_ema=5.0)
        state.mpg_history = [5.9, 5.7, 5.5, 5.3, 5.0]
        baseline_mpg = 6.0

        prediction = predict_maintenance_timing(state, baseline_mpg, "TEST-001")

        assert "days_to_warning" in prediction or "stable" in prediction


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_negative_miles(self):
        state = MPGState()
        config = MPGConfig()

        new_state = update_mpg_state(state, -10.0, 2.0, "TEST-001", config)

        # Should handle gracefully
        assert isinstance(new_state, MPGState)

    def test_negative_fuel(self):
        state = MPGState()
        config = MPGConfig()

        new_state = update_mpg_state(state, 50.0, -5.0, "TEST-001", config)

        assert isinstance(new_state, MPGState)

    def test_shutdown_baseline_manager(self):
        # Should not crash
        shutdown_baseline_manager()
