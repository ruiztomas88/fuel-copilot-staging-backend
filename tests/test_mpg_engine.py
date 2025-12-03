"""
Tests for MPG Engine

Run with: pytest tests/test_mpg_engine.py -v
"""

import pytest
from mpg_engine import (
    MPGState,
    MPGConfig,
    update_mpg_state,
    reset_mpg_state,
    estimate_fuel_from_distance,
    get_mpg_status,
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
        """Test default configuration values - v3.10.7 updated"""
        config = MPGConfig()
        assert config.min_miles == 10.0  # v3.10.7: Increased for reliable MPG
        assert config.min_fuel_gal == 1.5  # v3.10.7: Increased for sufficient sample
        assert config.min_mpg == 3.5  # Physical min for Class 8
        assert config.max_mpg == 9.0  # Physical max for Class 8
        assert config.ema_alpha == 0.4  # v3.10.7: Reduced for smoother readings
        assert config.fallback_mpg == 5.8

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
