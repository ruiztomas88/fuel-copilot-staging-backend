"""
Tests for Truck Health Monitor - Statistical Analysis for Predictive Maintenance

Tests cover:
- SensorStats and TruckHealthReport data classes
- Z-score calculations
- Shapiro-Wilk normality test
- Nelson Rules (1, 2, 5, 7)
- TruckHealthMonitor main functionality
- Alert generation and severity levels
- Fleet health summary
- State persistence
"""

import pytest
import sys
import json
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import statistics
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from truck_health_monitor import (
    SensorType,
    AlertSeverity,
    NelsonRule,
    SensorStats,
    TruckHealthReport,
    HealthAlert,
    SENSOR_RANGES,
    calculate_z_score,
    shapiro_wilk_test,
    NelsonRulesChecker,
    TruckHealthMonitor,
    integrate_with_truck_data,
    SCIPY_AVAILABLE,
)


# =============================================================================
# Test Enums
# =============================================================================


class TestEnums:
    """Test enum definitions"""

    def test_sensor_types(self):
        """Test SensorType enum values"""
        assert SensorType.OIL_TEMP.value == "oil_temp"
        assert SensorType.COOLANT_TEMP.value == "coolant_temp"
        assert SensorType.BATTERY_VOLTAGE.value == "battery_voltage"
        assert SensorType.OIL_PRESSURE.value == "oil_pressure"

    def test_alert_severity(self):
        """Test AlertSeverity enum values"""
        assert AlertSeverity.NORMAL.value == "NORMAL"
        assert AlertSeverity.WATCH.value == "WATCH"
        assert AlertSeverity.WARNING.value == "WARNING"
        assert AlertSeverity.CRITICAL.value == "CRITICAL"

    def test_nelson_rules(self):
        """Test NelsonRule enum values"""
        assert "outlier" in NelsonRule.RULE_1_OUTLIER.value.lower()
        assert "shift" in NelsonRule.RULE_2_SHIFT.value.lower()
        assert "trend" in NelsonRule.RULE_5_TREND.value.lower()
        assert "stuck" in NelsonRule.RULE_7_STRATIFICATION.value.lower()


# =============================================================================
# Test Sensor Configuration
# =============================================================================


class TestSensorConfig:
    """Test sensor configuration constants"""

    def test_sensor_ranges_defined(self):
        """Test all sensor ranges are defined"""
        assert SensorType.OIL_TEMP in SENSOR_RANGES
        assert SensorType.COOLANT_TEMP in SENSOR_RANGES
        assert SensorType.BATTERY_VOLTAGE in SENSOR_RANGES
        assert SensorType.OIL_PRESSURE in SENSOR_RANGES

    def test_sensor_ranges_have_required_keys(self):
        """Test sensor ranges have min, max, unit"""
        for sensor_type, config in SENSOR_RANGES.items():
            assert "min" in config, f"{sensor_type} missing min"
            assert "max" in config, f"{sensor_type} missing max"
            assert "unit" in config, f"{sensor_type} missing unit"
            assert "name" in config, f"{sensor_type} missing name"

    def test_coolant_temp_range(self):
        """Test coolant temp has reasonable range"""
        config = SENSOR_RANGES[SensorType.COOLANT_TEMP]
        assert config["min"] >= 100  # Not too cold
        assert config["max"] <= 300  # Not too hot
        assert config["unit"] == "°F"

    def test_battery_voltage_range(self):
        """Test battery voltage has reasonable range"""
        config = SENSOR_RANGES[SensorType.BATTERY_VOLTAGE]
        assert config["min"] >= 10  # Low battery
        assert config["max"] <= 16  # Overcharging
        assert config["unit"] == "V"


# =============================================================================
# Test Z-Score Calculation
# =============================================================================


class TestZScoreCalculation:
    """Test z-score calculation function"""

    def test_z_score_exact_mean(self):
        """Test z-score is 0 when value equals mean"""
        z = calculate_z_score(value=100, mean=100, std=10)
        assert z == 0.0

    def test_z_score_one_std_above(self):
        """Test z-score is 1 when value is 1 std above mean"""
        z = calculate_z_score(value=110, mean=100, std=10)
        assert z == 1.0

    def test_z_score_one_std_below(self):
        """Test z-score is -1 when value is 1 std below mean"""
        z = calculate_z_score(value=90, mean=100, std=10)
        assert z == -1.0

    def test_z_score_three_std(self):
        """Test z-score is 3 when value is 3 std above mean"""
        z = calculate_z_score(value=130, mean=100, std=10)
        assert z == 3.0

    def test_z_score_zero_std(self):
        """Test z-score returns None when std is 0"""
        z = calculate_z_score(value=100, mean=100, std=0)
        assert z is None

    def test_z_score_fractional(self):
        """Test z-score with fractional values"""
        z = calculate_z_score(value=105, mean=100, std=10)
        assert z == 0.5


# =============================================================================
# Test Shapiro-Wilk Test
# =============================================================================


class TestShapiroWilkTest:
    """Test Shapiro-Wilk normality test"""

    def test_insufficient_data(self):
        """Test returns True with insufficient data"""
        is_normal, p_value = shapiro_wilk_test([1, 2])
        assert is_normal is True
        assert p_value is None

    @pytest.mark.skipif(not SCIPY_AVAILABLE, reason="scipy not installed")
    def test_normal_distribution(self):
        """Test detects normal distribution"""
        # Generate normal data
        random.seed(42)
        data = [random.gauss(100, 10) for _ in range(100)]

        is_normal, p_value = shapiro_wilk_test(data)

        # Should not reject normality for truly normal data
        assert bool(is_normal) is True
        assert p_value is not None
        assert p_value > 0.05

    @pytest.mark.skipif(not SCIPY_AVAILABLE, reason="scipy not installed")
    def test_non_normal_distribution(self):
        """Test detects non-normal distribution"""
        # Generate clearly non-normal data (bimodal)
        data = [10] * 50 + [100] * 50

        is_normal, p_value = shapiro_wilk_test(data)

        # Should reject normality for bimodal data
        assert bool(is_normal) is False
        assert p_value is not None
        assert p_value < 0.05


# =============================================================================
# Test Nelson Rules Checker
# =============================================================================


class TestNelsonRulesChecker:
    """Test Nelson Rules implementation"""

    def test_rule_1_detects_outlier(self):
        """Rule 1: Point > 3σ from mean should be detected"""
        mean = 100
        std = 10
        # Last value is 4σ above mean
        values = [100, 100, 100, 100, 140]  # 140 = 100 + 4*10

        result = NelsonRulesChecker.check_rule_1(values, mean, std)
        assert result is True

    def test_rule_1_no_outlier(self):
        """Rule 1: Normal values should not trigger"""
        mean = 100
        std = 10
        values = [95, 100, 105, 98, 102]  # All within 1σ

        result = NelsonRulesChecker.check_rule_1(values, mean, std)
        assert result is False

    def test_rule_1_exactly_3_sigma(self):
        """Rule 1: Exactly 3σ should NOT trigger (need > 3σ)"""
        mean = 100
        std = 10
        values = [100, 100, 100, 100, 130]  # 130 = 100 + 3*10 exactly

        result = NelsonRulesChecker.check_rule_1(values, mean, std)
        assert result is False  # Need > 3σ, not >= 3σ

    def test_rule_2_detects_shift_above(self):
        """Rule 2: 9+ points above mean should be detected"""
        mean = 100
        values = [101, 102, 103, 104, 105, 106, 107, 108, 109]  # All > 100

        result = NelsonRulesChecker.check_rule_2(values, mean)
        assert result is True

    def test_rule_2_detects_shift_below(self):
        """Rule 2: 9+ points below mean should be detected"""
        mean = 100
        values = [99, 98, 97, 96, 95, 94, 93, 92, 91]  # All < 100

        result = NelsonRulesChecker.check_rule_2(values, mean)
        assert result is True

    def test_rule_2_no_shift(self):
        """Rule 2: Mixed values should not trigger"""
        mean = 100
        values = [101, 99, 101, 99, 101, 99, 101, 99, 101]  # Alternating

        result = NelsonRulesChecker.check_rule_2(values, mean)
        assert result is False

    def test_rule_2_insufficient_data(self):
        """Rule 2: Less than 9 points should not trigger"""
        mean = 100
        values = [101, 102, 103, 104, 105]  # Only 5 points

        result = NelsonRulesChecker.check_rule_2(values, mean)
        assert result is False

    def test_rule_5_detects_trend_above(self):
        """Rule 5: 2 of 3 points > 2σ above mean should trigger"""
        mean = 100
        std = 10
        values = [100, 125, 123]  # Two of last three > 2σ (>120)

        result = NelsonRulesChecker.check_rule_5(values, mean, std)
        assert result is True

    def test_rule_5_detects_trend_below(self):
        """Rule 5: 2 of 3 points > 2σ below mean should trigger"""
        mean = 100
        std = 10
        values = [100, 75, 77]  # Two of last three < -2σ (<80)

        result = NelsonRulesChecker.check_rule_5(values, mean, std)
        assert result is True

    def test_rule_5_no_trend(self):
        """Rule 5: Normal variation should not trigger"""
        mean = 100
        std = 10
        values = [100, 105, 95]  # All within 2σ

        result = NelsonRulesChecker.check_rule_5(values, mean, std)
        assert result is False

    def test_rule_7_detects_stuck_sensor(self):
        """Rule 7: 15+ points within 1σ should detect stuck sensor"""
        mean = 100
        std = 10
        # All values within 1σ (90-110)
        values = [
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
        ]

        result = NelsonRulesChecker.check_rule_7(values, mean, std)
        assert result is True

    def test_rule_7_normal_variation(self):
        """Rule 7: Normal variation should not trigger"""
        mean = 100
        std = 10
        # Some values outside 1σ
        values = [
            100,
            100,
            100,
            115,
            100,
            100,
            100,
            85,
            100,
            100,
            100,
            100,
            100,
            100,
            100,
        ]

        result = NelsonRulesChecker.check_rule_7(values, mean, std)
        assert result is False

    def test_check_all_rules_empty(self):
        """Test check_all_rules with empty values"""
        violations = NelsonRulesChecker.check_all_rules([], 100, 10)
        assert violations == []

    def test_check_all_rules_zero_std(self):
        """Test check_all_rules with zero std"""
        violations = NelsonRulesChecker.check_all_rules([100, 100, 100], 100, 0)
        assert violations == []


# =============================================================================
# Test SensorStats Data Class
# =============================================================================


class TestSensorStats:
    """Test SensorStats data class"""

    def test_creation(self):
        """Test SensorStats creation"""
        stats = SensorStats(
            sensor_type=SensorType.COOLANT_TEMP,
            truck_id="TEST1",
            window_name="week",
            mean=190.0,
            std=8.0,
            min_val=170.0,
            max_val=210.0,
            sample_count=100,
        )

        assert stats.sensor_type == SensorType.COOLANT_TEMP
        assert stats.truck_id == "TEST1"
        assert stats.mean == 190.0

    def test_severity_normal(self):
        """Test severity is NORMAL for low z-score"""
        stats = SensorStats(
            sensor_type=SensorType.COOLANT_TEMP,
            truck_id="TEST1",
            window_name="week",
            mean=190.0,
            std=8.0,
            min_val=170.0,
            max_val=210.0,
            sample_count=100,
            z_score=0.5,
        )

        assert stats.severity == AlertSeverity.NORMAL

    def test_severity_watch(self):
        """Test severity is WATCH for z-score 1-2"""
        stats = SensorStats(
            sensor_type=SensorType.COOLANT_TEMP,
            truck_id="TEST1",
            window_name="week",
            mean=190.0,
            std=8.0,
            min_val=170.0,
            max_val=210.0,
            sample_count=100,
            z_score=1.5,
        )

        assert stats.severity == AlertSeverity.WATCH

    def test_severity_warning(self):
        """Test severity is WARNING for z-score 2-3"""
        stats = SensorStats(
            sensor_type=SensorType.COOLANT_TEMP,
            truck_id="TEST1",
            window_name="week",
            mean=190.0,
            std=8.0,
            min_val=170.0,
            max_val=210.0,
            sample_count=100,
            z_score=2.5,
        )

        assert stats.severity == AlertSeverity.WARNING

    def test_severity_critical(self):
        """Test severity is CRITICAL for z-score > 3"""
        stats = SensorStats(
            sensor_type=SensorType.COOLANT_TEMP,
            truck_id="TEST1",
            window_name="week",
            mean=190.0,
            std=8.0,
            min_val=170.0,
            max_val=210.0,
            sample_count=100,
            z_score=3.5,
        )

        assert stats.severity == AlertSeverity.CRITICAL

    def test_severity_negative_z(self):
        """Test severity with negative z-score"""
        stats = SensorStats(
            sensor_type=SensorType.COOLANT_TEMP,
            truck_id="TEST1",
            window_name="week",
            mean=190.0,
            std=8.0,
            min_val=170.0,
            max_val=210.0,
            sample_count=100,
            z_score=-2.8,  # Negative but absolute > 2
        )

        assert stats.severity == AlertSeverity.WARNING

    def test_to_dict(self):
        """Test to_dict serialization"""
        stats = SensorStats(
            sensor_type=SensorType.COOLANT_TEMP,
            truck_id="TEST1",
            window_name="week",
            mean=190.0,
            std=8.0,
            min_val=170.0,
            max_val=210.0,
            sample_count=100,
            current_value=195.0,
            z_score=0.625,
            nelson_violations=[NelsonRule.RULE_2_SHIFT],
        )

        d = stats.to_dict()

        assert d["sensor_type"] == "coolant_temp"
        assert d["truck_id"] == "TEST1"
        assert d["mean"] == 190.0
        assert d["severity"] == "NORMAL"
        assert len(d["nelson_violations"]) == 1


# =============================================================================
# Test HealthAlert Data Class
# =============================================================================


class TestHealthAlert:
    """Test HealthAlert data class"""

    def test_creation(self):
        """Test HealthAlert creation"""
        alert = HealthAlert(
            truck_id="TEST1",
            sensor_type=SensorType.COOLANT_TEMP,
            severity=AlertSeverity.WARNING,
            message="Test alert",
            z_score=2.5,
            current_value=210.0,
            expected_range=(174.0, 206.0),
            nelson_violations=[],
        )

        assert alert.truck_id == "TEST1"
        assert alert.severity == AlertSeverity.WARNING
        assert alert.z_score == 2.5

    def test_to_dict(self):
        """Test to_dict serialization"""
        alert = HealthAlert(
            truck_id="TEST1",
            sensor_type=SensorType.COOLANT_TEMP,
            severity=AlertSeverity.CRITICAL,
            message="High temp!",
            z_score=3.5,
            current_value=220.0,
            expected_range=(174.0, 206.0),
            nelson_violations=[NelsonRule.RULE_1_OUTLIER],
        )

        d = alert.to_dict()

        assert d["truck_id"] == "TEST1"
        assert d["sensor_type"] == "coolant_temp"
        assert d["severity"] == "CRITICAL"
        assert d["z_score"] == 3.5
        assert len(d["nelson_violations"]) == 1


# =============================================================================
# Test TruckHealthMonitor - Main Class
# =============================================================================


class TestTruckHealthMonitor:
    """Test TruckHealthMonitor main class"""

    @pytest.fixture
    def monitor(self, tmp_path):
        """Create monitor with temp directory"""
        return TruckHealthMonitor(data_dir=str(tmp_path / "health_stats"))

    def test_init(self, monitor):
        """Test monitor initialization"""
        assert monitor._sensor_cache == {}
        assert monitor._alert_history == []

    def test_record_single_reading(self, monitor):
        """Test recording a single sensor reading"""
        ts = datetime.now(timezone.utc)
        alerts = monitor.record_sensor_data(
            truck_id="TEST1",
            timestamp=ts,
            coolant_temp=190.0,
        )

        # First reading shouldn't generate alerts (not enough data)
        assert len(alerts) == 0

        # Data should be cached
        assert "TEST1" in monitor._sensor_cache
        assert "coolant_temp" in monitor._sensor_cache["TEST1"]

    def test_record_multiple_readings(self, monitor):
        """Test recording multiple readings"""
        ts = datetime.now(timezone.utc)

        for i in range(30):
            monitor.record_sensor_data(
                truck_id="TEST1",
                timestamp=ts - timedelta(minutes=15 * i),
                coolant_temp=190.0 + random.gauss(0, 5),
            )

        assert len(monitor._sensor_cache["TEST1"]["coolant_temp"]) == 30

    def test_reject_out_of_range_values(self, monitor):
        """Test that out-of-range values are rejected"""
        ts = datetime.now(timezone.utc)

        # Coolant temp way too high (should be < 250°F typically)
        monitor.record_sensor_data(
            truck_id="TEST1",
            timestamp=ts,
            coolant_temp=500.0,  # Impossible value
        )

        # Should not be recorded
        assert "coolant_temp" not in monitor._sensor_cache.get("TEST1", {})

    def test_anomaly_detection(self, monitor):
        """Test anomaly detection generates alerts"""
        ts = datetime.now(timezone.utc)

        # Build up history with normal values
        for i in range(50):
            monitor.record_sensor_data(
                truck_id="TEST1",
                timestamp=ts - timedelta(minutes=15 * i),
                coolant_temp=190.0 + random.gauss(0, 5),
            )

        # Now inject anomaly
        alerts = monitor.record_sensor_data(
            truck_id="TEST1",
            timestamp=ts,
            coolant_temp=240.0,  # Very high!
        )

        # Should generate an alert
        assert len(alerts) >= 1
        assert any(
            a.severity in [AlertSeverity.WARNING, AlertSeverity.CRITICAL]
            for a in alerts
        )

    def test_stuck_sensor_detection(self, monitor):
        """Test stuck sensor detection (Rule 7)"""
        ts = datetime.now(timezone.utc)

        # Record exactly the same value many times
        for i in range(50):
            monitor.record_sensor_data(
                truck_id="STUCK_TEST",
                timestamp=ts - timedelta(minutes=15 * i),
                coolant_temp=185.0,  # Exactly the same every time
            )

        # Check health report
        report = monitor.get_truck_health_report("STUCK_TEST")

        # Should detect stuck sensor
        assert report is not None
        assert report.health_score < 100  # Deducted for stuck sensor

    def test_health_report_generation(self, monitor):
        """Test health report generation"""
        ts = datetime.now(timezone.utc)

        # Build up history
        for i in range(100):
            monitor.record_sensor_data(
                truck_id="TEST1",
                timestamp=ts - timedelta(minutes=15 * i),
                coolant_temp=190.0 + random.gauss(0, 8),
                battery_voltage=12.5 + random.gauss(0, 0.3),
            )

        report = monitor.get_truck_health_report("TEST1")

        assert report is not None
        assert report.truck_id == "TEST1"
        assert 0 <= report.health_score <= 100
        assert "coolant_temp" in report.sensor_stats
        assert "battery_voltage" in report.sensor_stats

    def test_health_report_windows(self, monitor):
        """Test health report includes multiple time windows"""
        ts = datetime.now(timezone.utc)

        # Build up 30 days of history
        for i in range(30 * 24 * 4):  # 15-min intervals for 30 days
            monitor.record_sensor_data(
                truck_id="TEST1",
                timestamp=ts - timedelta(minutes=15 * i),
                coolant_temp=190.0 + random.gauss(0, 8),
            )

        report = monitor.get_truck_health_report("TEST1")

        assert report is not None
        coolant_stats = report.sensor_stats.get("coolant_temp", {})

        # Should have day, week, month windows
        assert "day" in coolant_stats
        assert "week" in coolant_stats
        assert "month" in coolant_stats

    def test_health_report_to_dict(self, monitor):
        """Test health report serialization"""
        ts = datetime.now(timezone.utc)

        for i in range(50):
            monitor.record_sensor_data(
                truck_id="TEST1",
                timestamp=ts - timedelta(minutes=15 * i),
                coolant_temp=190.0 + random.gauss(0, 8),
            )

        report = monitor.get_truck_health_report("TEST1")
        d = report.to_dict()

        assert d["truck_id"] == "TEST1"
        assert "health_score" in d
        assert "sensors" in d
        assert "alerts" in d
        assert "recommendations" in d

    def test_fleet_summary(self, monitor):
        """Test fleet health summary"""
        ts = datetime.now(timezone.utc)

        # Add data for multiple trucks
        for truck_id in ["TRUCK1", "TRUCK2", "TRUCK3"]:
            for i in range(50):
                monitor.record_sensor_data(
                    truck_id=truck_id,
                    timestamp=ts - timedelta(minutes=15 * i),
                    coolant_temp=190.0 + random.gauss(0, 8),
                )

        summary = monitor.get_fleet_health_summary()

        assert summary["total_trucks"] == 3
        assert "truck_scores" in summary
        assert len(summary["truck_scores"]) == 3

    def test_get_alerts_for_truck(self, monitor):
        """Test getting alerts for specific truck"""
        ts = datetime.now(timezone.utc)

        # Build history
        for i in range(50):
            monitor.record_sensor_data(
                truck_id="TEST1",
                timestamp=ts - timedelta(minutes=15 * i),
                coolant_temp=190.0 + random.gauss(0, 5),
            )

        # Trigger alert
        monitor.record_sensor_data(
            truck_id="TEST1",
            timestamp=ts,
            coolant_temp=250.0,  # Anomaly
        )

        alerts = monitor.get_alerts_for_truck("TEST1", hours=24)

        assert len(alerts) >= 1


# =============================================================================
# Test State Persistence
# =============================================================================


class TestStatePersistence:
    """Test state save/load functionality"""

    def test_save_and_load_state(self, tmp_path):
        """Test saving and loading state"""
        # Create monitor and add data
        monitor1 = TruckHealthMonitor(data_dir=str(tmp_path / "health"))
        ts = datetime.now(timezone.utc)

        for i in range(10):
            monitor1.record_sensor_data(
                truck_id="TEST1",
                timestamp=ts - timedelta(minutes=15 * i),
                coolant_temp=190.0 + i,
            )

        # Save state
        save_path = str(tmp_path / "state.json")
        monitor1.save_state(save_path)

        assert Path(save_path).exists()

        # Create new monitor and load state
        monitor2 = TruckHealthMonitor(data_dir=str(tmp_path / "health2"))
        monitor2.load_state(save_path)

        # Verify data was loaded
        assert "TEST1" in monitor2._sensor_cache
        assert len(monitor2._sensor_cache["TEST1"]["coolant_temp"]) == 10

    def test_load_nonexistent_state(self, tmp_path):
        """Test loading from nonexistent file"""
        monitor = TruckHealthMonitor(data_dir=str(tmp_path / "health"))

        # Should not raise error
        monitor.load_state(str(tmp_path / "nonexistent.json"))

        # State should remain empty
        assert monitor._sensor_cache == {}


# =============================================================================
# Test Integration Helper
# =============================================================================


class TestIntegration:
    """Test integration with WialonReader data"""

    def test_integrate_with_truck_data(self, tmp_path):
        """Test integrate_with_truck_data helper"""
        monitor = TruckHealthMonitor(data_dir=str(tmp_path / "health"))

        # Create mock TruckSensorData
        mock_data = Mock()
        mock_data.truck_id = "TEST1"
        mock_data.timestamp = datetime.now(timezone.utc)
        mock_data.coolant_temp = 190.0
        mock_data.pwr_ext = 12.5
        mock_data.oil_press = 45.0

        # Should not raise
        alerts = integrate_with_truck_data(monitor, mock_data)

        assert isinstance(alerts, list)


# =============================================================================
# Test Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_truck_report(self, tmp_path):
        """Test report for truck with no data"""
        monitor = TruckHealthMonitor(data_dir=str(tmp_path / "health"))

        report = monitor.get_truck_health_report("NONEXISTENT")

        assert report is None

    def test_timezone_handling(self, tmp_path):
        """Test naive datetime is converted to UTC"""
        monitor = TruckHealthMonitor(data_dir=str(tmp_path / "health"))

        # Pass naive datetime (use recent date so it won't be pruned)
        naive_ts = datetime.now().replace(
            tzinfo=None
        )  # Remove timezone to make it naive

        monitor.record_sensor_data(
            truck_id="TEST1",
            timestamp=naive_ts,
            coolant_temp=190.0,
        )

        # Verify data was recorded and has timezone
        assert "TEST1" in monitor._sensor_cache
        assert "coolant_temp" in monitor._sensor_cache["TEST1"]
        assert len(monitor._sensor_cache["TEST1"]["coolant_temp"]) == 1

        stored_ts, _ = monitor._sensor_cache["TEST1"]["coolant_temp"][0]
        assert stored_ts.tzinfo is not None

    def test_old_data_pruning(self, tmp_path):
        """Test that data older than 30 days is pruned"""
        monitor = TruckHealthMonitor(data_dir=str(tmp_path / "health"))

        # Add old data
        old_ts = datetime.now(timezone.utc) - timedelta(days=35)
        monitor._sensor_cache["TEST1"] = {"coolant_temp": [(old_ts, 190.0)]}

        # Add new data (which should trigger pruning)
        new_ts = datetime.now(timezone.utc)
        monitor.record_sensor_data(
            truck_id="TEST1",
            timestamp=new_ts,
            coolant_temp=195.0,
        )

        # Old data should be pruned, only new data remains
        assert len(monitor._sensor_cache["TEST1"]["coolant_temp"]) == 1
        stored_ts, _ = monitor._sensor_cache["TEST1"]["coolant_temp"][0]
        assert stored_ts == new_ts

    def test_multiple_sensors_same_reading(self, tmp_path):
        """Test recording multiple sensors in one call"""
        monitor = TruckHealthMonitor(data_dir=str(tmp_path / "health"))
        ts = datetime.now(timezone.utc)

        monitor.record_sensor_data(
            truck_id="TEST1",
            timestamp=ts,
            coolant_temp=190.0,
            battery_voltage=12.5,
            oil_pressure=45.0,
        )

        assert "coolant_temp" in monitor._sensor_cache["TEST1"]
        assert "battery_voltage" in monitor._sensor_cache["TEST1"]
        assert "oil_pressure" in monitor._sensor_cache["TEST1"]


# =============================================================================
# Test Recommendations
# =============================================================================


class TestRecommendations:
    """Test recommendation generation"""

    def test_healthy_truck_recommendation(self, tmp_path):
        """Test recommendations for healthy truck"""
        monitor = TruckHealthMonitor(data_dir=str(tmp_path / "health"))
        ts = datetime.now(timezone.utc)

        # Normal data
        for i in range(50):
            monitor.record_sensor_data(
                truck_id="HEALTHY",
                timestamp=ts - timedelta(minutes=15 * i),
                coolant_temp=190.0 + random.gauss(0, 5),
            )

        report = monitor.get_truck_health_report("HEALTHY")

        assert report is not None
        assert report.health_score >= 90
        # Should have positive recommendation
        assert any("normal" in r.lower() or "✅" in r for r in report.recommendations)

    def test_critical_recommendation(self, tmp_path):
        """Test recommendations for truck with critical issues"""
        monitor = TruckHealthMonitor(data_dir=str(tmp_path / "health"))
        ts = datetime.now(timezone.utc)

        # Build normal history
        for i in range(50):
            monitor.record_sensor_data(
                truck_id="CRITICAL",
                timestamp=ts - timedelta(minutes=15 * (i + 1)),
                coolant_temp=190.0 + random.gauss(0, 5),
            )

        # Add critical reading
        monitor.record_sensor_data(
            truck_id="CRITICAL",
            timestamp=ts,
            coolant_temp=250.0,  # Critical!
        )

        report = monitor.get_truck_health_report("CRITICAL")

        assert report is not None
        assert report.health_score < 90
        # Should recommend inspection
        assert any(
            "inspection" in r.lower() or "urgent" in r.lower()
            for r in report.recommendations
        )


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
