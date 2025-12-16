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
        analyzer.add_confirmed_theft("CO0681", datetime.now() - timedelta(days=5), 30.0, 85.0)
        analyzer.add_confirmed_theft("CO0681", datetime.now() - timedelta(days=10), 25.0, 80.0)
        
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
