"""
Comprehensive tests for driver_behavior_engine
Target: 77% -> 89%+ coverage (119 missed lines)
Firmas correctas: cross_validate_mpg(truck_id), calculate_heavy_foot_score(truck_id, period_hours, total_driving_hours)
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

# Add parent directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from driver_behavior_engine import (
    BehaviorConfig,
    BehaviorType,
    DriverBehaviorEngine,
    SeverityLevel,
)


class TestProcessReading:
    """Test process_reading method - core detection logic"""

    def test_hard_acceleration_detection(self):
        """Should detect hard acceleration from speed delta"""
        engine = DriverBehaviorEngine()
        ts_start = datetime.now(timezone.utc)
        ts_end = ts_start + timedelta(seconds=3)

        # Initial reading
        events1 = engine.process_reading("T1", ts_start, speed=30.0)
        assert len(events1) == 0

        # Accelerate from 30 to 55 mph in 3 sec = 8.3 mph/s (severe)
        events2 = engine.process_reading("T1", ts_end, speed=55.0)

        accel_events = [
            e for e in events2 if e.behavior_type == BehaviorType.HARD_ACCELERATION
        ]
        assert len(accel_events) > 0

    def test_hard_braking_detection(self):
        """Should detect hard braking from speed delta"""
        engine = DriverBehaviorEngine()
        ts_start = datetime.now(timezone.utc)
        ts_end = ts_start + timedelta(seconds=3)

        engine.process_reading("T1", ts_start, speed=65.0)

        # Brake from 65 to 30 mph in 3 sec = -11.6 mph/s (severe)
        events = engine.process_reading("T1", ts_end, speed=30.0)

        brake_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_BRAKING
        ]
        assert len(brake_events) > 0

    def test_high_rpm_detection(self):
        """Should detect excessive RPM"""
        engine = DriverBehaviorEngine()
        ts1 = datetime.now(timezone.utc)

        # First reading at high RPM
        events1 = engine.process_reading("T1", ts1, speed=60.0, rpm=2400)
        assert len(events1) == 0  # No duration yet

        # Continue at high RPM for 6 seconds
        ts2 = ts1 + timedelta(seconds=6)
        events2 = engine.process_reading("T1", ts2, speed=60.0, rpm=2400)

        rpm_events = [
            e for e in events2 if e.behavior_type == BehaviorType.EXCESSIVE_RPM
        ]
        assert len(rpm_events) > 0
        assert rpm_events[0].value >= 2400

    def test_device_harsh_events(self):
        """Should process device-detected harsh events from accelerometer"""
        engine = DriverBehaviorEngine()
        ts = datetime.now(timezone.utc)

        events = engine.process_reading(
            "T1", ts, speed=55.0, device_harsh_accel=2, device_harsh_brake=1
        )

        accel_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_ACCELERATION
        ]
        brake_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_BRAKING
        ]

        assert len(accel_events) == 1
        assert len(brake_events) == 1
        assert accel_events[0].context["source"] == "device_accelerometer"

    def test_skip_large_time_gap(self):
        """Should skip processing if time gap is too large"""
        engine = DriverBehaviorEngine()
        ts1 = datetime.now(timezone.utc)
        ts2 = ts1 + timedelta(minutes=10)  # 10 min gap > 5 min threshold

        engine.process_reading("T1", ts1, speed=50.0)
        events = engine.process_reading("T1", ts2, speed=60.0)

        # Should not detect acceleration despite speed change
        assert len(events) == 0


class TestHeavyFootScore:
    """Test calculate_heavy_foot_score method"""

    def test_perfect_driver(self):
        """Perfect driver should get A grade"""
        engine = DriverBehaviorEngine()

        # Only process one or two readings with normal speed
        ts = datetime.now(timezone.utc)
        engine.process_reading("T1", ts, speed=55.0, rpm=1500)

        score = engine.calculate_heavy_foot_score(
            "T1", period_hours=1.0, total_driving_hours=1.0
        )

        # With no aggressive events, score should be high
        assert score.grade in ["A", "B"]
        assert score.hard_accel_count == 0

    def test_aggressive_driver(self):
        """Aggressive driver should get low score"""
        engine = DriverBehaviorEngine()
        ts_base = datetime.now(timezone.utc)

        # Simulate 20 hard acceleration events
        for i in range(20):
            ts = ts_base + timedelta(seconds=i * 10)
            ts2 = ts + timedelta(seconds=3)
            engine.process_reading("T2", ts, speed=30.0)
            engine.process_reading("T2", ts2, speed=55.0)  # 25mph in 3sec = ~8.3 mph/s

        score = engine.calculate_heavy_foot_score(
            "T2", period_hours=1.0, total_driving_hours=1.0
        )

        assert score.score < 70
        assert score.grade in ["D", "F"]
        assert score.hard_accel_count >= 15

    def test_score_breakdown(self):
        """Should provide detailed breakdown"""
        engine = DriverBehaviorEngine()
        score = engine.calculate_heavy_foot_score(
            "T3", period_hours=8.0, total_driving_hours=6.0
        )

        assert hasattr(score, "acceleration_score")
        assert hasattr(score, "braking_score")
        assert hasattr(score, "rpm_score")
        assert hasattr(score, "gear_score")
        assert hasattr(score, "speed_score")
        assert score.total_fuel_waste_gal >= 0

    def test_fuel_waste_accumulation(self):
        """Should accumulate fuel waste correctly"""
        engine = DriverBehaviorEngine()
        ts_base = datetime.now(timezone.utc)

        # 5 hard accelerations
        for i in range(5):
            ts = ts_base + timedelta(seconds=i * 10)
            ts2 = ts + timedelta(seconds=3)
            engine.process_reading("T4", ts, speed=30.0)
            engine.process_reading("T4", ts2, speed=55.0)

        score = engine.calculate_heavy_foot_score("T4")

        assert score.total_fuel_waste_gal > 0
        assert score.fuel_waste_breakdown["hard_acceleration"] > 0


class TestMPGCrossValidation:
    """Test cross_validate_mpg method"""

    def test_requires_minimum_samples(self):
        """Should return None if insufficient samples"""
        engine = DriverBehaviorEngine()
        ts = datetime.now(timezone.utc)

        # Only 2 readings (need 5)
        engine.process_reading("T1", ts, fuel_economy=6.5, kalman_mpg=6.3)
        engine.process_reading(
            "T1", ts + timedelta(seconds=5), fuel_economy=6.4, kalman_mpg=6.2
        )

        result = engine.cross_validate_mpg("T1")

        assert result is None

    def test_validation_with_agreement(self):
        """Should validate when Kalman and ECU agree"""
        engine = DriverBehaviorEngine()
        ts_base = datetime.now(timezone.utc)

        # Add 10 samples with similar values
        for i in range(10):
            ts = ts_base + timedelta(seconds=i * 5)
            engine.process_reading(
                "T2", ts, speed=55.0, fuel_economy=6.5, kalman_mpg=6.3
            )

        result = engine.cross_validate_mpg("T2")

        assert result is not None
        assert result.is_valid is True
        assert abs(result.difference_pct) < 10
        assert "validated" in result.recommendation.lower()

    def test_validation_kalman_higher(self):
        """Should warn if Kalman consistently higher than ECU"""
        engine = DriverBehaviorEngine()
        ts_base = datetime.now(timezone.utc)

        # Kalman overestimating
        for i in range(10):
            ts = ts_base + timedelta(seconds=i * 5)
            engine.process_reading(
                "T3", ts, speed=55.0, fuel_economy=5.0, kalman_mpg=7.0
            )

        result = engine.cross_validate_mpg("T3")

        assert result is not None
        assert result.is_valid is False
        assert result.kalman_mpg > result.ecu_mpg
        assert "higher" in result.recommendation.lower()

    def test_validation_kalman_lower(self):
        """Should warn if Kalman consistently lower than ECU"""
        engine = DriverBehaviorEngine()
        ts_base = datetime.now(timezone.utc)

        # Kalman underestimating
        for i in range(10):
            ts = ts_base + timedelta(seconds=i * 5)
            engine.process_reading(
                "T4", ts, speed=55.0, fuel_economy=7.0, kalman_mpg=5.0
            )

        result = engine.cross_validate_mpg("T4")

        assert result is not None
        assert result.is_valid is False
        assert result.kalman_mpg < result.ecu_mpg
        assert "lower" in result.recommendation.lower()


class TestBehaviorState:
    """Test state persistence across readings"""

    def test_state_persistence(self):
        """State should persist across readings"""
        engine = DriverBehaviorEngine()
        ts1 = datetime.now(timezone.utc)
        ts2 = ts1 + timedelta(seconds=5)

        engine.process_reading("T1", ts1, speed=50.0, rpm=1800)
        engine.process_reading("T1", ts2, speed=55.0, rpm=1850)

        state = engine.truck_states["T1"]
        assert state.last_speed == 55.0
        assert state.last_rpm == 1850

    def test_independent_truck_states(self):
        """Different trucks should have independent states"""
        engine = DriverBehaviorEngine()
        ts = datetime.now(timezone.utc)

        engine.process_reading("T1", ts, speed=50.0)
        engine.process_reading("T2", ts, speed=65.0)

        assert engine.truck_states["T1"].last_speed == 50.0
        assert engine.truck_states["T2"].last_speed == 65.0

    def test_daily_reset(self):
        """Should reset counters at midnight"""
        engine = DriverBehaviorEngine()
        ts_yesterday = datetime.now(timezone.utc) - timedelta(days=1)
        ts_today = datetime.now(timezone.utc)

        # Simulate events yesterday
        engine.process_reading("T1", ts_yesterday, device_harsh_accel=5)

        # Force daily reset
        engine._check_daily_reset()

        # Process today - should have reset
        state = engine.truck_states["T1"]
        # After reset, new day started
        assert engine._last_daily_reset.date() == ts_today.date()


class TestFleetAnalysis:
    """Test get_fleet_behavior_summary"""

    def test_summary_with_memory_data(self):
        """Should generate summary from in-memory data"""
        engine = DriverBehaviorEngine()
        ts_base = datetime.now(timezone.utc)

        # Add data for 2 trucks
        for i in range(10):
            ts = ts_base + timedelta(seconds=i * 10)
            ts2 = ts + timedelta(seconds=3)
            engine.process_reading("T1", ts, speed=30.0)
            engine.process_reading("T1", ts2, speed=55.0)
            engine.process_reading("T2", ts, speed=40.0)
            engine.process_reading("T2", ts2, speed=50.0)

        summary = engine.get_fleet_behavior_summary()

        assert "fleet_size" in summary
        assert summary["fleet_size"] == 2
        assert isinstance(summary, dict)

    def test_summary_from_database(self):
        """Should fall back to database if no memory data"""
        engine = DriverBehaviorEngine()

        # No in-memory data
        assert len(engine.truck_states) == 0

        summary = engine.get_fleet_behavior_summary()

        # Should have returned database summary or empty summary
        assert isinstance(summary, dict)
        assert "fleet_size" in summary


class TestConfigValidation:
    """Test BehaviorConfig dataclass"""

    def test_default_config(self):
        """Should use default config values"""
        engine = DriverBehaviorEngine()

        assert engine.config.accel_moderate_threshold > 0
        assert engine.config.rpm_excessive > 0
        assert engine.config.fuel_waste_hard_accel_gal > 0

    def test_custom_config(self):
        """Should accept custom config"""
        custom_config = BehaviorConfig(
            accel_moderate_threshold=3.0,
            rpm_excessive=2000,
            fuel_waste_hard_accel_gal=0.05,
        )

        engine = DriverBehaviorEngine(config=custom_config)

        assert engine.config.accel_moderate_threshold == 3.0
        assert engine.config.rpm_excessive == 2000
        assert engine.config.fuel_waste_hard_accel_gal == 0.05


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_none_values(self):
        """Should handle None sensor values gracefully"""
        engine = DriverBehaviorEngine()
        ts = datetime.now(timezone.utc)

        events = engine.process_reading("T1", ts, speed=None, rpm=None)

        # Should not crash
        assert isinstance(events, list)

    def test_zero_speed(self):
        """Should handle zero speed (stopped truck)"""
        engine = DriverBehaviorEngine()
        ts = datetime.now(timezone.utc)

        events = engine.process_reading("T1", ts, speed=0.0, rpm=800)

        assert isinstance(events, list)

    def test_negative_rpm(self):
        """Should handle invalid RPM values"""
        engine = DriverBehaviorEngine()
        ts = datetime.now(timezone.utc)

        # RPM check: if rpm is not None and rpm > 0
        events = engine.process_reading("T1", ts, speed=50.0, rpm=-100)

        # Should ignore negative RPM
        assert isinstance(events, list)
