"""
Tests for MPG Engine

Run with: pytest tests/test_mpg_engine.py -v
"""

import pytest

from mpg_engine import (
    MPGConfig,
    MPGState,
    estimate_fuel_from_distance,
    get_mpg_status,
    reset_mpg_state,
    update_mpg_state,
)


class TestMPGState:
    """Test MPGState dataclass"""

    def test_initial_state(self):
        """Test default initialization"""
        state = MPGState()
        assert state.distance_accum == 0.0
        assert state.fuel_accum_gal == 0.0
        assert state.mpg_current is None
        assert state.window_count == 0
        assert state.total_discarded == 0
        assert state.total_accepted == 0


class TestMPGConfig:
    """Test MPGConfig validation"""

    def test_default_config(self):
        """Test default configuration values - v3.12.18 updated"""
        config = MPGConfig()
        assert config.min_miles == 5.0  # v3.12.18: Reduced from 10.0 for faster updates
        assert (
            config.min_fuel_gal == 1.5
        )  # v3.12.18: Increased from 0.75 to reduce sensor noise
        assert config.min_mpg == 3.8  # Physical min for Class 8 - updated
        assert config.max_mpg == 8.2  # Physical max for Class 8 - updated
        assert config.ema_alpha == 0.4  # v3.10.7: Reduced for smoother readings
        assert config.fallback_mpg == 5.7  # v4.0: Updated fallback

    def test_invalid_min_mpg_greater_than_max(self):
        """Should raise error if min_mpg >= max_mpg"""
        with pytest.raises(ValueError, match="min_mpg must be less than max_mpg"):
            MPGConfig(min_mpg=8.0, max_mpg=7.0)

    def test_invalid_ema_alpha(self):
        """Should raise error if ema_alpha out of range"""
        with pytest.raises(ValueError, match="ema_alpha must be between 0 and 1"):
            MPGConfig(ema_alpha=1.5)


class TestUpdateMPGState:
    """Test MPG state update logic"""

    def test_accumulation_below_threshold(self):
        """Accumulate data without calculating MPG"""
        state = MPGState()
        config = MPGConfig(min_miles=12.0, min_fuel_gal=1.8)

        # Add 6 miles / 1 gallon (below threshold)
        state = update_mpg_state(
            state, delta_miles=6.0, delta_gallons=1.0, config=config
        )

        assert state.distance_accum == 6.0
        assert state.fuel_accum_gal == 1.0
        assert state.mpg_current is None  # Not calculated yet
        assert state.window_count == 0

    def test_first_mpg_calculation(self):
        """Calculate MPG when window threshold reached"""
        state = MPGState()
        config = MPGConfig(min_miles=10.0, min_fuel_gal=1.5)

        # Add 60 miles / 10 gallons → 6.0 MPG
        state = update_mpg_state(
            state, delta_miles=60.0, delta_gallons=10.0, config=config
        )

        assert state.mpg_current == pytest.approx(6.0, rel=1e-3)
        assert state.window_count == 1
        assert state.distance_accum == 0.0  # Reset after calculation
        assert state.fuel_accum_gal == 0.0
        assert state.total_accepted == 1
        assert state.total_discarded == 0

    def test_ema_smoothing(self):
        """Test EMA smoothing over multiple windows"""
        state = MPGState()
        config = MPGConfig(min_miles=10.0, min_fuel_gal=1.5, ema_alpha=0.6)

        # First window: 60mi / 10gal = 6.0 MPG
        state = update_mpg_state(state, 60.0, 10.0, config)
        first_mpg = state.mpg_current
        assert first_mpg == pytest.approx(6.0, rel=1e-3)

        # Second window: 70mi / 10gal = 7.0 MPG
        state = update_mpg_state(state, 70.0, 10.0, config)
        second_mpg = state.mpg_current

        # EMA: 0.6 * 7.0 + 0.4 * 6.0 = 6.6
        expected = 0.6 * 7.0 + 0.4 * 6.0
        assert second_mpg == pytest.approx(expected, rel=1e-3)
        assert state.window_count == 2

    def test_discard_unrealistic_high_mpg(self):
        """Discard MPG > max_mpg"""
        state = MPGState()
        config = MPGConfig(min_miles=10.0, min_fuel_gal=1.0, max_mpg=7.9)

        # 100mi / 5gal = 20 MPG (impossible for Class 8)
        state = update_mpg_state(state, 100.0, 5.0, config)

        assert state.mpg_current is None  # Discarded
        assert state.total_discarded == 1
        assert state.total_accepted == 0
        assert state.distance_accum == 0.0  # Still reset window

    def test_discard_unrealistic_low_mpg(self):
        """Discard MPG < min_mpg"""
        state = MPGState()
        config = MPGConfig(min_miles=10.0, min_fuel_gal=1.0, min_mpg=4.8)

        # 10mi / 10gal = 1.0 MPG (too low)
        state = update_mpg_state(state, 10.0, 10.0, config)

        assert state.mpg_current is None
        assert state.total_discarded == 1

    def test_negative_deltas_forced_to_zero(self):
        """Negative deltas should be forced to 0 (sensor glitch protection)"""
        state = MPGState()
        config = MPGConfig()

        state = update_mpg_state(
            state, delta_miles=-10.0, delta_gallons=-5.0, config=config
        )

        assert state.distance_accum == 0.0
        assert state.fuel_accum_gal == 0.0

    def test_mpg_preserved_after_invalid_window(self):
        """Valid MPG should be preserved even if next window is invalid"""
        state = MPGState()
        config = MPGConfig(min_miles=10.0, min_fuel_gal=1.0)

        # First window: valid 6.0 MPG
        state = update_mpg_state(state, 60.0, 10.0, config)
        assert state.mpg_current == pytest.approx(6.0, rel=1e-3)

        # Second window: invalid 20 MPG
        state = update_mpg_state(state, 100.0, 5.0, config)

        # Should still have 6.0 MPG (not overwritten)
        assert state.mpg_current == pytest.approx(6.0, rel=1e-3)


class TestResetMPGState:
    """Test MPG state reset"""

    def test_reset_clears_accumulator(self):
        """Reset should clear accumulators"""
        state = MPGState(distance_accum=50.0, fuel_accum_gal=8.0, mpg_current=6.5)

        state = reset_mpg_state(state, reason="refuel", truck_id="TEST")

        assert state.distance_accum == 0.0
        assert state.fuel_accum_gal == 0.0
        # MPG should be preserved
        assert state.mpg_current == 6.5


class TestEstimateFuelFromDistance:
    """Test fuel estimation function"""

    def test_estimate_10_miles(self):
        """Estimate fuel for 10 miles"""
        config = MPGConfig(fallback_mpg=5.8)
        fuel = estimate_fuel_from_distance(10.0, config)

        # 10 miles / 5.8 MPG = 1.724 gallons
        expected = 10.0 / 5.8
        assert fuel == pytest.approx(expected, rel=1e-3)

    def test_estimate_zero_distance(self):
        """Zero distance should return zero fuel"""
        fuel = estimate_fuel_from_distance(0.0)
        assert fuel == 0.0

    def test_estimate_negative_distance(self):
        """Negative distance should return zero"""
        fuel = estimate_fuel_from_distance(-10.0)
        assert fuel == 0.0


class TestGetMPGStatus:
    """Test MPG status reporting"""

    def test_status_not_ready(self):
        """Status when no MPG calculated yet"""
        state = MPGState()
        config = MPGConfig()

        status = get_mpg_status(state, config)

        assert status["status"] == "NOT_READY"
        assert status["mpg_current"] is None
        assert status["windows_completed"] == 0

    def test_status_good(self):
        """Status for normal MPG"""
        state = MPGState(mpg_current=6.5, window_count=10, total_accepted=10)
        config = MPGConfig()

        status = get_mpg_status(state, config)

        assert status["status"] == "GOOD"
        assert status["mpg_current"] == 6.5
        assert status["windows_completed"] == 10
        assert status["acceptance_rate"] == 1.0

    def test_status_excellent(self):
        """Status for optimal MPG"""
        state = MPGState(mpg_current=7.8, window_count=5)
        config = MPGConfig(max_mpg=7.9)

        status = get_mpg_status(state, config)

        assert status["status"] == "EXCELLENT"

    def test_status_poor(self):
        """Status for low MPG"""
        state = MPGState(mpg_current=5.0, window_count=5)
        config = MPGConfig(min_mpg=4.8)

        status = get_mpg_status(state, config)

        assert status["status"] == "POOR"

    def test_acceptance_rate_calculation(self):
        """Test acceptance rate calculation"""
        state = MPGState(mpg_current=6.0, total_accepted=8, total_discarded=2)
        config = MPGConfig()

        status = get_mpg_status(state, config)

        # 8 accepted / 10 total = 0.8
        assert status["acceptance_rate"] == pytest.approx(0.8, rel=1e-3)


class TestIntegrationScenarios:
    """Integration tests for real-world scenarios"""

    def test_full_cycle_multiple_windows(self):
        """Test complete cycle over multiple windows"""
        state = MPGState()
        # Disable dynamic alpha for predictable test results
        config = MPGConfig(
            min_miles=10.0, min_fuel_gal=1.5, ema_alpha=0.7, use_dynamic_alpha=False
        )

        # Window 1: 55mi / 10gal = 5.5 MPG
        state = update_mpg_state(state, 55.0, 10.0, config)
        assert state.mpg_current == pytest.approx(5.5, rel=1e-3)

        # Window 2: 65mi / 10gal = 6.5 MPG
        state = update_mpg_state(state, 65.0, 10.0, config)
        # EMA: 0.7 * 6.5 + 0.3 * 5.5 = 6.2
        assert state.mpg_current == pytest.approx(6.2, rel=1e-3)

        # Window 3: 75mi / 10gal = 7.5 MPG
        state = update_mpg_state(state, 75.0, 10.0, config)
        # EMA: 0.7 * 7.5 + 0.3 * 6.2 = 7.11
        assert state.mpg_current == pytest.approx(7.11, rel=1e-3)

        assert state.window_count == 3
        assert state.total_accepted == 3
        assert state.total_discarded == 0

    def test_mixed_valid_invalid_windows(self):
        """Test handling of mix of valid and invalid windows"""
        state = MPGState()
        config = MPGConfig(min_miles=10.0, min_fuel_gal=1.0)

        # Valid window
        state = update_mpg_state(state, 60.0, 10.0, config)
        assert state.mpg_current == pytest.approx(6.0, rel=1e-3)

        # Invalid window (too high)
        state = update_mpg_state(state, 100.0, 5.0, config)
        assert state.mpg_current == pytest.approx(6.0, rel=1e-3)  # Unchanged

        # Another valid window
        state = update_mpg_state(state, 70.0, 10.0, config)
        # EMA with 7.0 MPG
        assert state.mpg_current == pytest.approx(6.6, rel=1e-3)

        assert state.window_count == 2  # Only valid windows counted
        assert state.total_accepted == 2
        assert state.total_discarded == 1


class TestIQROutlierFilter:
    """Test IQR outlier rejection"""

    def test_filter_outliers_basic(self):
        """Should remove obvious outliers"""
        from mpg_engine import filter_outliers_iqr

        readings = [5.0, 5.5, 6.0, 15.0, 5.2]  # 15 is outlier
        filtered = filter_outliers_iqr(readings)
        assert 15.0 not in filtered
        assert len(filtered) < len(readings)

    def test_filter_not_enough_data(self):
        """
        🔧 v3.13.0: With < 4 readings, now uses MAD filter instead of returning original.
        MAD filter should still catch obvious outliers like 15.0 among [5.0, 5.5]
        """
        from mpg_engine import filter_outliers_iqr

        readings = [5.0, 15.0, 5.5]
        filtered = filter_outliers_iqr(readings)
        # MAD should filter out 15.0 as an outlier (it's far from median 5.5)
        assert 15.0 not in filtered
        assert 5.0 in filtered
        assert 5.5 in filtered

    def test_filter_very_small_data_no_outliers(self):
        """With < 4 similar readings, MAD should keep them all"""
        from mpg_engine import filter_outliers_iqr

        readings = [5.0, 5.2, 5.5]
        filtered = filter_outliers_iqr(readings)
        assert filtered == readings  # All similar, no outliers

    def test_filter_no_outliers(self):
        """Should return all data if no outliers"""
        from mpg_engine import filter_outliers_iqr

        readings = [5.0, 5.5, 6.0, 5.8, 5.2]
        filtered = filter_outliers_iqr(readings)
        assert len(filtered) == len(readings)


class TestDynamicAlpha:
    """Test dynamic EMA alpha calculation"""

    def test_dynamic_alpha_disabled(self):
        """Should use static alpha when disabled"""
        from mpg_engine import get_dynamic_alpha

        state = MPGState()
        config = MPGConfig(ema_alpha=0.5, use_dynamic_alpha=False)
        alpha = get_dynamic_alpha(state, config)
        assert alpha == 0.5

    def test_dynamic_alpha_low_variance(self):
        """Should use higher alpha when variance is low"""
        from mpg_engine import get_dynamic_alpha

        state = MPGState()
        state.mpg_history = [6.0, 6.1, 5.9, 6.0, 6.05]  # Low variance
        config = MPGConfig(
            use_dynamic_alpha=True,
            alpha_high_variance=0.3,
            alpha_low_variance=0.6,
            variance_threshold=0.25,
        )
        alpha = get_dynamic_alpha(state, config)
        assert alpha == 0.6  # High alpha for low variance

    def test_dynamic_alpha_high_variance(self):
        """Should use lower alpha when variance is high"""
        from mpg_engine import get_dynamic_alpha

        state = MPGState()
        state.mpg_history = [4.0, 7.0, 5.0, 8.0, 4.5]  # High variance
        config = MPGConfig(
            use_dynamic_alpha=True,
            alpha_high_variance=0.3,
            alpha_low_variance=0.6,
            variance_threshold=0.25,
        )
        alpha = get_dynamic_alpha(state, config)
        assert alpha == 0.3  # Low alpha for high variance


class TestMPGStateHistory:
    """Test MPG state history tracking"""

    def test_add_to_history(self):
        """Should add values to history"""
        state = MPGState(max_history_size=5)
        state.add_to_history(6.0)
        state.add_to_history(6.5)
        assert len(state.mpg_history) == 2
        assert 6.0 in state.mpg_history
        assert 6.5 in state.mpg_history

    def test_history_max_size(self):
        """Should maintain max size"""
        state = MPGState(max_history_size=3)
        for val in [5.0, 5.5, 6.0, 6.5, 7.0]:
            state.add_to_history(val)
        assert len(state.mpg_history) == 3
        assert state.mpg_history == [6.0, 6.5, 7.0]  # Oldest removed

    def test_get_variance_not_enough_data(self):
        """Should return 0 with < 3 values"""
        state = MPGState()
        state.mpg_history = [6.0, 6.5]
        assert state.get_variance() == 0.0

    def test_get_variance_calculation(self):
        """Should calculate variance correctly"""
        state = MPGState()
        state.mpg_history = [5.0, 6.0, 7.0, 6.0]  # mean=6.0, variance=0.5
        variance = state.get_variance()
        assert variance == pytest.approx(0.5, rel=0.1)


class TestTruckMPGBaseline:
    """Test per-truck MPG baseline"""

    def test_baseline_initial_state(self):
        """Should start with fleet average"""
        from mpg_engine import TruckMPGBaseline

        baseline = TruckMPGBaseline(truck_id="T101")
        assert baseline.baseline_mpg == 5.7
        assert baseline.confidence == "LOW"
        assert baseline.sample_count == 0

    def test_baseline_update(self):
        """Should update baseline with new observations"""
        import time

        from mpg_engine import TruckMPGBaseline

        baseline = TruckMPGBaseline(truck_id="T101")
        baseline.update(6.5, time.time())
        assert baseline.baseline_mpg == 6.5
        assert baseline.sample_count == 1
        # Note: min_observed starts at 5.7 (fleet average) and is updated with min()
        # First update sets max but min stays at initial if value > initial
        assert baseline.max_observed == 6.5

    def test_baseline_confidence_levels(self):
        """Should update confidence based on sample count"""
        import time

        from mpg_engine import TruckMPGBaseline

        baseline = TruckMPGBaseline(truck_id="T101")

        # LOW confidence (< 20 samples)
        for _ in range(19):
            baseline.update(6.0, time.time())
        assert baseline.confidence == "LOW"

        # MEDIUM confidence (>= 20 samples)
        baseline.update(6.0, time.time())
        assert baseline.confidence == "MEDIUM"

        # HIGH confidence (>= 50 samples)
        for _ in range(30):
            baseline.update(6.0, time.time())
        assert baseline.confidence == "HIGH"

    def test_baseline_skip_invalid_mpg(self):
        """Should skip MPG values outside valid range"""
        import time

        from mpg_engine import TruckMPGBaseline

        baseline = TruckMPGBaseline(truck_id="T101")
        baseline.update(6.0, time.time())  # Valid
        baseline.update(50.0, time.time())  # Invalid - too high
        baseline.update(1.0, time.time())  # Invalid - too low
        assert baseline.sample_count == 1
        assert baseline.baseline_mpg == 6.0

    def test_baseline_deviation(self):
        """Should calculate deviation from baseline"""
        import time

        from mpg_engine import TruckMPGBaseline

        baseline = TruckMPGBaseline(truck_id="T101")

        # Add enough samples to have valid baseline
        for mpg in [6.0, 6.1, 5.9, 6.0, 6.2]:
            baseline.update(mpg, time.time())

        deviation = baseline.get_deviation(6.0)
        assert deviation["status"] == "NORMAL"
        assert abs(deviation["z_score"]) < 1.0

    def test_baseline_deviation_insufficient_data(self):
        """Should return insufficient data status"""
        from mpg_engine import TruckMPGBaseline

        baseline = TruckMPGBaseline(truck_id="T101")
        deviation = baseline.get_deviation(6.0)
        assert deviation["status"] == "INSUFFICIENT_DATA"

    def test_baseline_std_dev_property(self):
        """Should calculate standard deviation"""
        import time

        from mpg_engine import TruckMPGBaseline

        baseline = TruckMPGBaseline(truck_id="T101")

        # Add samples with known std dev
        for mpg in [5.0, 6.0, 7.0, 6.0, 6.0]:
            baseline.update(mpg, time.time())

        std_dev = baseline.std_dev
        assert std_dev > 0.1
        assert std_dev < 2.0


class TestMPGConfigValidation:
    """Test MPG config validation"""

    def test_invalid_min_miles(self):
        """Should raise error for non-positive min_miles"""
        with pytest.raises(ValueError, match="min_miles must be positive"):
            MPGConfig(min_miles=0)

    def test_invalid_min_fuel_gal(self):
        """Should raise error for non-positive min_fuel_gal"""
        with pytest.raises(ValueError, match="min_fuel_gal must be positive"):
            MPGConfig(min_fuel_gal=-1)

    def test_invalid_negative_min_miles(self):
        """Should raise error for negative min_miles"""
        with pytest.raises(ValueError, match="min_miles must be positive"):
            MPGConfig(min_miles=-5)


class TestTruckBaselineManager:
    """Test TruckBaselineManager functionality"""

    def test_manager_get_or_create(self):
        """Should get or create baseline for truck"""
        import time

        from mpg_engine import TruckBaselineManager

        manager = TruckBaselineManager()
        baseline = manager.get_or_create("T101")
        assert baseline.truck_id == "T101"
        assert baseline.sample_count == 0

        # Update baseline
        baseline.update(6.0, time.time())

        # Get same baseline
        baseline2 = manager.get_or_create("T101")
        assert baseline2.truck_id == "T101"
        assert baseline2.sample_count == 1

    def test_manager_get_summary(self):
        """Should return summary of all baselines"""
        import time

        from mpg_engine import TruckBaselineManager

        manager = TruckBaselineManager()

        # Create multiple baselines
        for truck_id in ["T101", "T102", "T103"]:
            baseline = manager.get_or_create(truck_id)
            for mpg in [5.5, 6.0, 6.5]:
                baseline.update(mpg, time.time())

        summary = manager.get_fleet_summary()
        assert summary["trucks"] == 3
        assert summary["avg_baseline"] > 0
        assert len(summary["baselines"]) == 3

    def test_manager_save_load(self, tmp_path):
        """Should save and load baselines to/from file"""
        import time

        from mpg_engine import TruckBaselineManager

        # Create and populate manager
        manager1 = TruckBaselineManager()
        baseline1 = manager1.get_or_create("T101")
        baseline1.update(6.0, time.time())
        baseline1.update(6.5, time.time())

        # Save to temp file
        filepath = tmp_path / "baselines.json"
        manager1.save_to_file(str(filepath))

        # Load into new manager
        manager2 = TruckBaselineManager()
        manager2.load_from_file(str(filepath))

        # Verify data loaded
        baseline2 = manager2.get_or_create("T101")
        assert baseline2.sample_count == 2
        assert baseline2.baseline_mpg > 0

    def test_manager_load_nonexistent_file(self, tmp_path):
        """Should handle loading from nonexistent file gracefully"""
        from mpg_engine import TruckBaselineManager

        manager = TruckBaselineManager()
        filepath = tmp_path / "nonexistent.json"

        # Should not raise error
        manager.load_from_file(str(filepath))
        assert manager.get_fleet_summary()["trucks"] == 0

    def test_baseline_to_dict_from_dict(self):
        """Should serialize and deserialize baseline"""
        import time

        from mpg_engine import TruckMPGBaseline

        # Create and update baseline
        baseline1 = TruckMPGBaseline(truck_id="T101")
        baseline1.update(6.0, time.time())
        baseline1.update(6.5, time.time())

        # Serialize
        data = baseline1.to_dict()
        assert data["truck_id"] == "T101"
        assert data["sample_count"] == 2

        # Deserialize
        baseline2 = TruckMPGBaseline.from_dict(data)
        assert baseline2.truck_id == "T101"
        assert baseline2.sample_count == 2
        # Check approximately equal (rounding differences)
        assert abs(baseline2.baseline_mpg - baseline1.baseline_mpg) < 0.01

    def test_global_baseline_manager(self):
        """Should get global baseline manager singleton"""
        from mpg_engine import get_baseline_manager, shutdown_baseline_manager

        manager1 = get_baseline_manager()
        manager2 = get_baseline_manager()

        # Should be same instance
        assert manager1 is manager2

        # Shutdown should work
        shutdown_baseline_manager()

    def test_baseline_deviation_statuses(self):
        """Should return correct deviation statuses"""
        import time

        from mpg_engine import TruckMPGBaseline

        baseline = TruckMPGBaseline(truck_id="T101")

        # Add stable samples around 6.0
        for _ in range(15):
            baseline.update(6.0, time.time())

        # Test NORMAL (same value as baseline)
        dev_normal = baseline.get_deviation(6.0)
        assert dev_normal["status"] == "NORMAL"

        # Test small deviation
        dev_small = baseline.get_deviation(6.1)
        assert dev_small["status"] in ["NORMAL", "NOTABLE"]

        # Test extreme deviation
        dev_extreme = baseline.get_deviation(2.0)
        assert dev_extreme["status"] in ["ANOMALY", "CRITICAL"]
        assert dev_extreme["z_score"] < -1.0
