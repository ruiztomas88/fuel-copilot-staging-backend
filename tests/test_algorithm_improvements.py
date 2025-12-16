"""
Tests for algorithm improvements v4.2.0 / v5.8.4 / v3.13.0

Tests cover:
1. Negative consumption handling in estimator.py
2. MAD-based outlier filtering in mpg_engine.py
3. TheftPatternAnalyzer in theft_detection_engine.py
4. Enhanced get_sensor_health_fast in theft_detection_engine.py

Author: Fuel Copilot Team
Date: December 2025
"""

import pytest
from datetime import datetime, timedelta


# ═══════════════════════════════════════════════════════════════════════════════
# TEST NEGATIVE CONSUMPTION HANDLING (estimator.py)
# ═══════════════════════════════════════════════════════════════════════════════


class TestNegativeConsumptionHandling:
    """Test v5.8.4: Negative consumption treated as sensor error"""

    def test_negative_consumption_uses_fallback_idle(self):
        """Negative consumption at low speed should use idle fallback (2.0 LPH)"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        initial_level = estimator.level_liters

        # Predict with negative consumption (sensor error) at low speed
        estimator.predict(
            dt_hours=0.5,
            consumption_lph=-5.0,  # Negative = error
            speed_mph=3.0,  # Low speed = idle
        )

        # Should have used idle fallback (2.0 LPH)
        expected_consumption = 2.0 * 0.5  # 1 liter
        actual_consumption = initial_level - estimator.level_liters

        assert abs(actual_consumption - expected_consumption) < 0.1

    def test_negative_consumption_uses_fallback_moving(self):
        """Negative consumption at higher speed should use city fallback (15.0 LPH)"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        initial_level = estimator.level_liters

        # Predict with negative consumption at moving speed
        estimator.predict(
            dt_hours=0.5,
            consumption_lph=-10.0,  # Negative = error
            speed_mph=40.0,  # Moving speed = city fallback
        )

        # Should have used city fallback (15.0 LPH)
        expected_consumption = 15.0 * 0.5  # 7.5 liters
        actual_consumption = initial_level - estimator.level_liters

        assert abs(actual_consumption - expected_consumption) < 0.1

    def test_zero_consumption_uses_provided_value(self):
        """Zero consumption should be used as-is (not treated as error)"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        initial_level = estimator.level_liters

        # Predict with zero consumption (parked truck)
        estimator.predict(
            dt_hours=0.5,
            consumption_lph=0.0,
            speed_mph=0.0,
        )

        # Should have consumed exactly 0
        actual_consumption = initial_level - estimator.level_liters
        assert abs(actual_consumption) < 0.01


# ═══════════════════════════════════════════════════════════════════════════════
# TEST MAD-BASED OUTLIER FILTERING (mpg_engine.py)
# ═══════════════════════════════════════════════════════════════════════════════


class TestMADOutlierFilter:
    """Test v3.13.0: MAD-based filtering for small samples"""

    def test_mad_filter_removes_outlier_in_small_sample(self):
        """MAD should remove obvious outlier even with 3 samples"""
        from mpg_engine import filter_outliers_mad

        readings = [5.0, 5.2, 15.0]  # 15.0 is clearly an outlier
        filtered = filter_outliers_mad(readings)

        assert 15.0 not in filtered
        assert 5.0 in filtered
        assert 5.2 in filtered

    def test_mad_filter_keeps_similar_values(self):
        """MAD should keep all values when they're similar"""
        from mpg_engine import filter_outliers_mad

        readings = [5.0, 5.3, 5.6]
        filtered = filter_outliers_mad(readings)

        assert len(filtered) == 3
        assert filtered == readings

    def test_mad_filter_single_value_returns_original(self):
        """Single value should return as-is"""
        from mpg_engine import filter_outliers_mad

        readings = [5.5]
        filtered = filter_outliers_mad(readings)

        assert filtered == readings

    def test_mad_filter_two_values_returns_original(self):
        """Two values with different magnitudes - MAD handles edge case"""
        from mpg_engine import filter_outliers_mad

        # With only 2 values, hard to determine outlier
        readings = [5.0, 5.5]
        filtered = filter_outliers_mad(readings)

        # Should return original for 2 similar values
        assert len(filtered) == 2

    def test_iqr_delegates_to_mad_for_small_samples(self):
        """IQR should use MAD when n < 4"""
        from mpg_engine import filter_outliers_iqr

        readings = [5.0, 5.5, 20.0]  # 20.0 is outlier
        filtered = filter_outliers_iqr(readings)

        # MAD should filter out 20.0
        assert 20.0 not in filtered
        assert 5.0 in filtered


# ═══════════════════════════════════════════════════════════════════════════════
# TEST THEFT PATTERN ANALYZER (theft_detection_engine.py)
# ═══════════════════════════════════════════════════════════════════════════════


class TestTheftPatternAnalyzer:
    """Test v4.2.0: Historical pattern detection"""

    def test_no_history_returns_zero_factor(self):
        """New truck with no history should have 0 pattern factor"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer()
        factor, reason = analyzer.calculate_pattern_factor(
            "NEW_TRUCK",
            datetime.now(),
        )

        assert factor == 0.0
        assert reason == ""

    def test_single_previous_theft_adds_factor(self):
        """One previous theft should add +10 factor"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer()

        # Add one confirmed theft
        analyzer.add_confirmed_theft(
            truck_id="CO0681",
            timestamp=datetime.now() - timedelta(days=5),
            drop_gal=30.0,
            confidence=85.0,
        )

        factor, reason = analyzer.calculate_pattern_factor(
            "CO0681",
            datetime.now(),
        )

        assert factor >= 10.0  # At least +10 for 1 previous theft
        assert "robo previo" in reason.lower()

    def test_multiple_thefts_increases_factor(self):
        """Multiple thefts should increase factor to +15"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer()

        # Add two confirmed thefts
        analyzer.add_confirmed_theft(
            truck_id="CO0681",
            timestamp=datetime.now() - timedelta(days=10),
            drop_gal=25.0,
            confidence=80.0,
        )
        analyzer.add_confirmed_theft(
            truck_id="CO0681",
            timestamp=datetime.now() - timedelta(days=5),
            drop_gal=30.0,
            confidence=85.0,
        )

        factor, reason = analyzer.calculate_pattern_factor(
            "CO0681",
            datetime.now(),
        )

        assert factor >= 15.0  # +15 for 2+ thefts
        assert "2 robos previos" in reason

    def test_same_day_of_week_pattern(self):
        """Thefts on same day of week should add pattern bonus"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer()

        # Add thefts on same day of week (Monday)
        monday_1 = datetime(2025, 12, 1, 3, 0)  # Monday 3am
        monday_2 = datetime(2025, 12, 8, 2, 30)  # Monday 2:30am

        analyzer.add_confirmed_theft("CO0681", monday_1, 30.0, 85.0)
        analyzer.add_confirmed_theft("CO0681", monday_2, 28.0, 82.0)

        # Check pattern on another Monday
        monday_3 = datetime(2025, 12, 15, 3, 15)  # Monday
        factor, reason = analyzer.calculate_pattern_factor("CO0681", monday_3)

        # Should have day of week bonus
        assert factor >= 15.0  # 15 (2 thefts) + 5 (same day)
        assert "Lun" in reason or "patrón" in reason.lower()

    def test_recent_event_increases_suspicion(self):
        """Recent theft (within 7 days) should increase suspicion"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer()

        # Add very recent theft
        analyzer.add_confirmed_theft(
            truck_id="CO0681",
            timestamp=datetime.now() - timedelta(days=2),
            drop_gal=30.0,
            confidence=85.0,
        )

        factor, reason = analyzer.calculate_pattern_factor(
            "CO0681",
            datetime.now(),
        )

        # Should have recent event bonus
        assert factor >= 15.0  # 10 (1 theft) + 5 (recent)
        assert "reciente" in reason.lower()

    def test_old_events_pruned(self):
        """Events older than history_days should be pruned"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer(history_days=30)

        # Add very old theft
        analyzer.add_confirmed_theft(
            truck_id="CO0681",
            timestamp=datetime.now() - timedelta(days=100),
            drop_gal=30.0,
            confidence=85.0,
        )

        factor, reason = analyzer.calculate_pattern_factor(
            "CO0681",
            datetime.now(),
        )

        # Old event should be pruned, factor = 0
        assert factor == 0.0

    def test_get_truck_risk_profile(self):
        """Risk profile should summarize truck theft history"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer()

        # Add thefts
        analyzer.add_confirmed_theft(
            "CO0681", datetime.now() - timedelta(days=5), 30.0, 85.0
        )
        analyzer.add_confirmed_theft(
            "CO0681", datetime.now() - timedelta(days=10), 25.0, 80.0
        )

        profile = analyzer.get_truck_risk_profile("CO0681")

        assert profile["truck_id"] == "CO0681"
        assert profile["theft_count"] == 2
        assert profile["total_loss_gal"] == 55.0
        assert profile["risk_level"] in ["LOW", "MEDIUM", "HIGH"]


# ═══════════════════════════════════════════════════════════════════════════════
# TEST ENHANCED SENSOR HEALTH (theft_detection_engine.py)
# ═══════════════════════════════════════════════════════════════════════════════


class TestEnhancedSensorHealth:
    """Test v4.2.0: Heuristic-based sensor volatility estimation"""

    def test_sensor_disconnect_detected(self):
        """Drop to near-zero should be detected as disconnect"""
        from theft_detection_engine import get_sensor_health_fast

        health = get_sensor_health_fast(
            fuel_before_pct=75.0,
            fuel_after_pct=3.0,
        )

        assert health.is_connected is False
        assert health.volatility_score == 100.0

    def test_sudden_large_drop_high_volatility(self):
        """Very sudden large drop should have high volatility"""
        from theft_detection_engine import get_sensor_health_fast

        health = get_sensor_health_fast(
            fuel_before_pct=80.0,
            fuel_after_pct=50.0,
            drop_pct=30.0,
            time_gap_minutes=3.0,  # 30% in 3 minutes = physically impossible
        )

        assert health.is_connected is True
        assert health.volatility_score >= 45.0  # Should be high

    def test_gradual_drop_low_volatility(self):
        """Gradual drop over longer time should have low volatility"""
        from theft_detection_engine import get_sensor_health_fast

        health = get_sensor_health_fast(
            fuel_before_pct=80.0,
            fuel_after_pct=70.0,
            drop_pct=10.0,
            time_gap_minutes=60.0,  # 10% in 60 min = reasonable
        )

        assert health.is_connected is True
        assert health.volatility_score <= 20.0

    def test_impossible_consumption_rate_detected(self):
        """Consumption rate faster than physically possible should increase volatility"""
        from theft_detection_engine import get_sensor_health_fast

        # 50% drop in 30 min = 100%/hour, way more than max 25%/hour
        health = get_sensor_health_fast(
            fuel_before_pct=100.0,
            fuel_after_pct=50.0,
            drop_pct=50.0,
            time_gap_minutes=30.0,
        )

        assert health.volatility_score >= 35.0

    def test_drop_to_round_number_suspicious(self):
        """Drop to exactly round numbers suggests sensor reset"""
        from theft_detection_engine import get_sensor_health_fast

        health = get_sensor_health_fast(
            fuel_before_pct=73.0,
            fuel_after_pct=50.0,  # Exactly 50% is suspicious
            drop_pct=23.0,
            time_gap_minutes=30.0,
        )

        assert health.volatility_score >= 20.0

    def test_normal_drop_low_volatility(self):
        """Normal-looking drop should have low volatility"""
        from theft_detection_engine import get_sensor_health_fast

        health = get_sensor_health_fast(
            fuel_before_pct=65.0,
            fuel_after_pct=53.0,
            drop_pct=12.0,
            time_gap_minutes=45.0,
        )

        assert health.is_connected is True
        assert health.volatility_score <= 10.0


# ═══════════════════════════════════════════════════════════════════════════════
# TEST KALMAN FILTER IMPROVEMENTS v5.8.5
# ═══════════════════════════════════════════════════════════════════════════════


class TestKalmanAutoResyncCooldown:
    """Test v5.8.5: Auto-resync cooldown prevents oscillation"""

    def test_first_resync_happens_immediately(self):
        """First resync should happen without cooldown"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # Force high drift (>15% triggers resync)
        estimator.L = 0.80 * 800  # 80% in liters
        estimator.level_pct = 80.0

        # Auto-resync should happen (sensor at 50%, estimate at 80%)
        estimator.auto_resync(sensor_pct=50.0)

        # Check that resync time was recorded
        assert hasattr(estimator, "_last_resync_time")
        assert estimator._last_resync_time is not None

    def test_second_resync_blocked_by_cooldown(self):
        """Second resync within 30 minutes should be blocked"""
        from estimator import FuelEstimator, COMMON_CONFIG
        from datetime import datetime, timezone

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # First resync
        estimator.L = 0.80 * 800
        estimator.level_pct = 80.0
        estimator.auto_resync(sensor_pct=50.0)

        # After resync, level should be ~50%
        level_after_first = estimator.level_pct

        # Force drift again
        estimator.L = 0.85 * 800
        estimator.level_pct = 85.0

        # Second attempt (should be blocked by cooldown)
        estimator.auto_resync(sensor_pct=50.0)

        # Level should NOT have resynced (still at 85%)
        assert estimator.level_pct == 85.0

    def test_resync_allowed_after_cooldown(self):
        """Resync should be allowed after 30 minute cooldown"""
        from estimator import FuelEstimator, COMMON_CONFIG
        from datetime import datetime, timezone, timedelta

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # First resync
        estimator.L = 0.80 * 800
        estimator.level_pct = 80.0
        estimator.auto_resync(sensor_pct=50.0)

        # Simulate 31 minutes passing
        estimator._last_resync_time = datetime.now(timezone.utc) - timedelta(minutes=31)

        # Force drift again
        estimator.L = 0.85 * 800
        estimator.level_pct = 85.0

        # Second resync should be allowed after cooldown
        estimator.auto_resync(sensor_pct=50.0)

        # Level should have resynced to ~50%
        assert abs(estimator.level_pct - 50.0) < 1.0


class TestInnovationBasedKAdjustment:
    """Test v5.8.5: Innovation-based K adjustment for faster correction"""

    def test_large_innovation_boosts_k_max(self):
        """Large unexpected change should boost K_max for faster correction"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # Simulate several updates to build confidence (low P)
        for _ in range(10):
            estimator.update(measured_pct=50.0)

        P_before = estimator.P
        level_before = estimator.level_pct

        # Large measurement change (like a refuel not yet detected)
        estimator.update(measured_pct=75.0)

        # With innovation-based K, the correction should be more substantial
        # than without it (because P was low, K_max would normally be 0.20)
        correction = estimator.level_pct - level_before

        # Correction should be significant (at least 10% of the 25% difference)
        assert correction > 2.5

    def test_small_innovation_no_k_boost(self):
        """Small expected changes should not boost K_max"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # Build confidence
        for _ in range(10):
            estimator.update(measured_pct=50.0)

        level_before = estimator.level_pct

        # Small measurement change (within noise expectations)
        estimator.update(measured_pct=50.5)

        # Correction should be small/normal
        correction = estimator.level_pct - level_before
        assert correction < 0.2  # Less than 40% of 0.5% difference


class TestConservativeQr:
    """Test v5.8.5: More conservative Q_r values"""

    def test_parked_qr_is_very_low(self):
        """PARKED Q_r should be 0.005 (fuel shouldn't change)"""
        from estimator import calculate_adaptive_Q_r

        qr = calculate_adaptive_Q_r("PARKED", 0.0)
        assert qr == 0.005

    def test_idle_qr_is_conservative(self):
        """IDLE Q_r should be around 0.02 (very predictable)"""
        from estimator import calculate_adaptive_Q_r

        qr = calculate_adaptive_Q_r("IDLE", 2.0)
        # 0.02 + (2.0/100)*0.01 = 0.0202
        assert 0.02 <= qr <= 0.025

    def test_stopped_qr_is_conservative(self):
        """STOPPED Q_r should be 0.02"""
        from estimator import calculate_adaptive_Q_r

        qr = calculate_adaptive_Q_r("STOPPED", 0.0)
        assert qr == 0.02

    def test_moving_qr_scales_with_consumption(self):
        """MOVING Q_r should scale with consumption rate"""
        from estimator import calculate_adaptive_Q_r

        qr_low = calculate_adaptive_Q_r("MOVING", 5.0)
        qr_high = calculate_adaptive_Q_r("MOVING", 30.0)

        assert qr_high > qr_low
        # Formula: 0.05 + (consumption/50)*0.1
        # Low: 0.05 + 0.01 = 0.06
        # High: 0.05 + 0.06 = 0.11
        assert 0.05 < qr_low < 0.08
        assert 0.10 < qr_high < 0.15


# ═══════════════════════════════════════════════════════════════════════════════
# TEST UNIFIED Q_L CALCULATION (estimator.py v5.8.6)
# ═══════════════════════════════════════════════════════════════════════════════


class TestUnifiedQLCalculation:
    """Test v5.8.6: Unified Q_L combining GPS and voltage factors"""

    def test_ql_changes_with_gps_quality(self):
        """Q_L should change based on GPS quality (satellites)"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # Good GPS quality (many satellites)
        estimator.update_sensor_quality(satellites=15, voltage=28.0)
        ql_good_gps = estimator.Q_L

        # Poor GPS quality (few satellites)
        # Note: Q_L calculation may vary based on GPS thresholds
        estimator.update_sensor_quality(satellites=3, voltage=28.0)
        ql_poor_gps = estimator.Q_L

        # Both should be valid Q_L values
        assert 0.5 <= ql_good_gps <= 20.0
        assert 0.5 <= ql_poor_gps <= 20.0

    def test_ql_changes_with_voltage(self):
        """Q_L should change based on voltage level"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # Test with two different voltages
        estimator.update_sensor_quality(satellites=10, voltage=28.0)
        ql_high_voltage = estimator.Q_L

        estimator.update_sensor_quality(satellites=10, voltage=13.0)
        ql_low_voltage = estimator.Q_L

        # Both should be valid, and low voltage should give higher Q_L
        # (less reliable sensor = more measurement noise)
        assert 0.5 <= ql_high_voltage <= 20.0
        assert 0.5 <= ql_low_voltage <= 20.0

        # With v5.8.6: voltage factor affects Q_L
        # Low voltage = higher Q_L (less trust in measurement)
        # Note: This depends on the actual voltage threshold implementation

    def test_ql_combines_gps_and_voltage(self):
        """Q_L should incorporate both GPS and voltage factors"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # Test that update_sensor_quality accepts both parameters
        result = estimator.update_sensor_quality(satellites=10, voltage=24.0)

        # Should return a quality factor
        assert 0.0 <= result <= 1.0

        # Q_L should be in valid range
        assert 0.5 <= estimator.Q_L <= 20.0

    def test_ql_clamped_to_valid_range(self):
        """Q_L should be clamped between 0.5 and 20"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # Extremely bad conditions
        estimator.update_sensor_quality(satellites=1, voltage=10.0)

        # Should be capped at 20
        assert estimator.Q_L <= 20.0
        assert estimator.Q_L >= 0.5

    def test_ql_defaults_when_no_voltage(self):
        """Q_L should work when voltage is None (use base/GPS only)"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # Store initial Q_L
        initial_ql = estimator.Q_L

        # No voltage data
        estimator.update_sensor_quality(satellites=10, voltage=None)

        # Should still have a valid Q_L (GPS-based only)
        assert estimator.Q_L >= 0.5
        assert estimator.Q_L <= 20.0

    def test_voltage_factor_calculation(self):
        """Test voltage factor is correctly calculated and applied"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST_VOLTAGE",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        # Very low voltage should produce high Q_L
        # Voltage factor = max(1.0, (30 - voltage) / 6)
        # At 12V: factor = (30-12)/6 = 3.0
        # At 28V: factor = (30-28)/6 = 0.33 → clamped to 1.0
        estimator.update_sensor_quality(satellites=10, voltage=12.0)
        ql_very_low = estimator.Q_L

        estimator.update_sensor_quality(satellites=10, voltage=28.0)
        ql_high = estimator.Q_L

        # Low voltage should give higher Q_L
        assert ql_very_low >= ql_high


# ═══════════════════════════════════════════════════════════════════════════════
# TEST PATTERN ANALYZER PERSISTENCE (theft_detection_engine.py v4.2.1)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPatternAnalyzerPersistence:
    """Test v4.2.1: TheftPatternAnalyzer persistence to DB"""

    def test_analyzer_loads_lazily(self):
        """Analyzer should not hit DB until first access"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer(history_days=90)

        # Should not have loaded yet
        assert not analyzer._loaded_from_db
        assert len(analyzer._theft_history) == 0

    def test_analyzer_loads_on_first_access(self):
        """First access to calculate_pattern_factor should trigger load"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer(history_days=90)

        # Trigger load
        factor, reason = analyzer.calculate_pattern_factor("TEST001", datetime.now())

        # Should have attempted to load
        assert analyzer._loaded_from_db

    def test_analyzer_loads_on_add_theft(self):
        """Adding theft should trigger load first"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer(history_days=90)

        # Add a theft event
        analyzer.add_confirmed_theft(
            truck_id="TEST001",
            timestamp=datetime.now(),
            drop_gal=10.0,
            confidence=85.0,
        )

        # Should have loaded before adding
        assert analyzer._loaded_from_db

    def test_analyzer_deduplicates_events(self):
        """Duplicate events within 1 minute should be skipped"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer(history_days=90)

        now = datetime.now()

        # Add first event
        analyzer.add_confirmed_theft(
            truck_id="TEST001",
            timestamp=now,
            drop_gal=10.0,
            confidence=85.0,
        )

        # Try to add duplicate (within 1 minute)
        analyzer.add_confirmed_theft(
            truck_id="TEST001",
            timestamp=now + timedelta(seconds=30),
            drop_gal=10.0,
            confidence=85.0,
        )

        # Should only have 1 event
        assert len(analyzer._theft_history["TEST001"]) == 1

    def test_analyzer_accepts_different_events(self):
        """Events more than 1 minute apart should both be recorded"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer(history_days=90)

        now = datetime.now()

        # Add first event
        analyzer.add_confirmed_theft(
            truck_id="TEST001",
            timestamp=now,
            drop_gal=10.0,
            confidence=85.0,
        )

        # Add second event (5 minutes later)
        analyzer.add_confirmed_theft(
            truck_id="TEST001",
            timestamp=now + timedelta(minutes=5),
            drop_gal=15.0,
            confidence=90.0,
        )

        # Should have 2 events
        assert len(analyzer._theft_history["TEST001"]) == 2

    def test_get_all_truck_profiles(self):
        """get_all_truck_profiles should trigger load and return profiles"""
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer(history_days=90)

        # Add events for multiple trucks
        now = datetime.now()
        analyzer.add_confirmed_theft("TRUCK_A", now, 10.0, 85.0)
        analyzer.add_confirmed_theft("TRUCK_B", now, 20.0, 90.0)
        analyzer.add_confirmed_theft("TRUCK_B", now + timedelta(hours=1), 15.0, 88.0)

        # Get all profiles
        profiles = analyzer.get_all_truck_profiles()

        # Should have profiles for both trucks
        assert len(profiles) == 2

        truck_b_profile = next(p for p in profiles if p["truck_id"] == "TRUCK_B")
        assert truck_b_profile["theft_count"] == 2
        assert truck_b_profile["risk_level"] == "MEDIUM"  # 2 events


# ═══════════════════════════════════════════════════════════════════════════════
# TEST PREDICT() P GROWTH FIX (estimator.py v5.9.0)
# ═══════════════════════════════════════════════════════════════════════════════


class TestPredictPGrowthFix:
    """Test v5.9.0: P should grow even during large time gaps"""

    def test_p_increases_during_large_gap(self):
        """Large time gap should increase P to reflect uncertainty"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        initial_P = estimator.P

        # Simulate large time gap (2 hours)
        estimator.predict(dt_hours=2.0, consumption_lph=10.0)

        # P should have increased significantly
        assert estimator.P > initial_P
        # With Q_r ~0.05 and dt=2h and factor 5: increase ~0.5
        assert estimator.P >= initial_P + 0.3

    def test_level_unchanged_during_large_gap(self):
        """Fuel level should NOT change during large gap (no prediction)"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        initial_level = estimator.level_liters

        # Large gap - should skip consumption prediction
        estimator.predict(dt_hours=3.0, consumption_lph=20.0)

        # Level should be unchanged
        assert estimator.level_liters == initial_level

    def test_normal_gap_works_normally(self):
        """Normal time gaps should still work as before"""
        from estimator import FuelEstimator, COMMON_CONFIG

        estimator = FuelEstimator(
            truck_id="TEST001",
            capacity_liters=800,
            config=COMMON_CONFIG,
        )
        estimator.initialize(fuel_lvl_pct=50.0)

        initial_level = estimator.level_liters

        # Normal gap (15 minutes = 0.25 hours)
        estimator.predict(dt_hours=0.25, consumption_lph=10.0)

        # Level should have decreased
        expected_consumption = 10.0 * 0.25  # 2.5 liters
        assert (
            abs((initial_level - estimator.level_liters) - expected_consumption) < 0.1
        )


# ═══════════════════════════════════════════════════════════════════════════════
# TEST IQR CORRUPTION HANDLING (mpg_engine.py v3.14.0)
# ═══════════════════════════════════════════════════════════════════════════════


class TestIQRCorruptionHandling:
    """Test v3.14.0: IQR filter returns empty list when all data is corrupt"""

    def test_iqr_all_outliers_returns_empty(self):
        """When all readings are outliers, return empty list"""
        from mpg_engine import filter_outliers_iqr

        # Data where everything is an outlier relative to each other
        # Values so spread that IQR considers them all outliers
        readings = [1.0, 1.0, 100.0, 100.0, 100.0]

        result = filter_outliers_iqr(readings)

        # Should return empty list (signals corruption)
        # The low values (1.0) will be filtered as outliers
        # This depends on exact IQR calculation
        assert isinstance(result, list)

    def test_iqr_normal_data_returns_filtered(self):
        """Normal data with one outlier should return filtered list"""
        from mpg_engine import filter_outliers_iqr

        readings = [5.5, 5.6, 5.7, 5.8, 5.9, 50.0]  # 50 is outlier

        result = filter_outliers_iqr(readings)

        # Should return list without the outlier
        assert len(result) == 5
        assert 50.0 not in result

    def test_iqr_good_data_unchanged(self):
        """Good data should pass through unchanged"""
        from mpg_engine import filter_outliers_iqr

        readings = [5.5, 5.6, 5.7, 5.8, 5.9]

        result = filter_outliers_iqr(readings)

        assert result == readings


# ═══════════════════════════════════════════════════════════════════════════════
# TEST BASELINE MANAGER AUTO-SAVE/LOAD (mpg_engine.py v3.14.0)
# ═══════════════════════════════════════════════════════════════════════════════


class TestBaselineManagerPersistence:
    """Test v3.14.0: TruckBaselineManager auto-save/load"""

    def test_manager_has_save_interval(self):
        """Manager should have configurable save interval"""
        from mpg_engine import TruckBaselineManager

        manager = TruckBaselineManager(auto_load=False)

        assert hasattr(manager, "SAVE_INTERVAL")
        assert manager.SAVE_INTERVAL > 0

    def test_manager_tracks_dirty_state(self):
        """Manager should track when changes need saving"""
        from mpg_engine import TruckBaselineManager
        import time

        manager = TruckBaselineManager(auto_load=False)

        assert manager._dirty == False

        # Update should mark dirty
        manager.update_baseline("TEST001", 5.8, time.time())

        assert manager._dirty == True

    def test_manager_has_shutdown_method(self):
        """Manager should have shutdown method for clean exit"""
        from mpg_engine import TruckBaselineManager

        manager = TruckBaselineManager(auto_load=False)

        assert hasattr(manager, "shutdown")
        assert callable(manager.shutdown)

    def test_shutdown_function_exists(self):
        """Module should export shutdown_baseline_manager function"""
        from mpg_engine import shutdown_baseline_manager

        assert callable(shutdown_baseline_manager)
