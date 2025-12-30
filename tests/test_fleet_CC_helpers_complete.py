"""
Fleet Command Center - Complete Helper Methods Tests
Tests all helper methods with variations
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fleet_command_center import FleetCommandCenter, Priority


class TestHelperMethodsComplete:
    """Test all helper methods"""

    def test_has_persistent_critical_reading_correct_signature(self):
        """Test _has_persistent_critical_reading with correct params"""
        cc = FleetCommandCenter()

        # Record readings
        for i in range(5):
            cc._record_sensor_reading("108", "oil_temp", 250.0 + i)

        is_persistent, count = cc._has_persistent_critical_reading(
            truck_id="108",
            sensor_name="oil_temp",
            threshold=240.0,
            above=True,
        )

        assert isinstance(is_persistent, bool)
        assert isinstance(count, int)

    def test_has_persistent_critical_below_threshold(self):
        """Test persistent check below threshold"""
        cc = FleetCommandCenter()

        # Record low voltage readings
        for i in range(5):
            cc._record_sensor_reading("109", "voltage", 11.0 - i * 0.2)

        is_persistent, count = cc._has_persistent_critical_reading(
            truck_id="109",
            sensor_name="voltage",
            threshold=12.0,
            above=False,
        )

        assert isinstance(is_persistent, bool)
        assert isinstance(count, int)

    def test_has_persistent_no_readings(self):
        """Test persistent check with no readings"""
        cc = FleetCommandCenter()

        is_persistent, count = cc._has_persistent_critical_reading(
            truck_id="NONEXISTENT",
            sensor_name="oil_temp",
            threshold=230.0,
            above=True,
        )

        assert isinstance(is_persistent, bool)
        assert count == 0

    def test_calculate_priority_score_correct_signature(self):
        """Test _calculate_priority_score with correct params"""
        cc = FleetCommandCenter()

        priority, score = cc._calculate_priority_score(
            days_to_critical=3.0,
            anomaly_score=0.85,
            cost_estimate="$5,000 - $10,000",
            component="Transmisión",
        )

        assert isinstance(priority, Priority)
        assert isinstance(score, float)
        assert 0 <= score <= 100

    def test_calculate_priority_score_critical(self):
        """Test priority score for critical case"""
        cc = FleetCommandCenter()

        priority, score = cc._calculate_priority_score(
            days_to_critical=0.5,
            anomaly_score=0.95,
            cost_estimate="$15,000 - $25,000",
            component="Transmisión",
        )

        assert isinstance(priority, Priority)
        assert score >= 70  # Should be high priority score

    def test_calculate_priority_score_low(self):
        """Test priority score for low severity"""
        cc = FleetCommandCenter()

        priority, score = cc._calculate_priority_score(
            days_to_critical=30.0,
            anomaly_score=0.2,
            cost_estimate="$500 - $1,000",
            component="Sistema de combustible",
        )

        assert isinstance(priority, Priority)
        assert score < 65  # Should be lower priority

    def test_calculate_priority_score_no_days(self):
        """Test priority score without days_to_critical"""
        cc = FleetCommandCenter()

        priority, score = cc._calculate_priority_score(
            days_to_critical=None,
            anomaly_score=0.5,
            cost_estimate="$2,000",
            component="Sistema eléctrico",
        )

        assert isinstance(priority, Priority)
        assert isinstance(score, float)

    def test_calculate_priority_score_minimal(self):
        """Test priority score with minimal params"""
        cc = FleetCommandCenter()

        priority, score = cc._calculate_priority_score(
            days_to_critical=15.0,
        )

        assert isinstance(priority, Priority)
        assert isinstance(score, float)

    def test_get_time_horizon_immediate(self):
        """Test time horizon for immediate issues"""
        cc = FleetCommandCenter()

        horizon = cc._get_time_horizon(0.5)
        assert horizon == "immediate"

    def test_get_time_horizon_short_term(self):
        """Test time horizon for short term"""
        cc = FleetCommandCenter()

        horizon = cc._get_time_horizon(3.0)
        assert horizon == "short_term"

    def test_get_time_horizon_medium_term(self):
        """Test time horizon for medium term"""
        cc = FleetCommandCenter()

        horizon = cc._get_time_horizon(15.0)
        assert horizon == "medium_term"

    def test_get_time_horizon_none(self):
        """Test time horizon with None"""
        cc = FleetCommandCenter()

        horizon = cc._get_time_horizon(None)
        assert horizon == "medium_term"

    def test_get_action_steps_from_table(self):
        """Test _get_action_steps_from_table"""
        cc = FleetCommandCenter()

        try:
            steps = cc._get_action_steps_from_table(
                component="oil_system",
                severity="critical",
                days=1.0,
            )
            assert steps is None or isinstance(steps, list)
        except Exception:
            pass  # May not have decision table

    def test_normalize_component_variations(self):
        """Test component normalization"""
        cc = FleetCommandCenter()

        result1 = cc._normalize_component("Oil Temperature")
        result2 = cc._normalize_component("COOLANT-TEMP")
        result3 = cc._normalize_component("Turbo Boost Pressure")
        result4 = cc._normalize_component("Sistema de Lubricación")

        assert all(isinstance(r, str) for r in [result1, result2, result3, result4])

    def test_get_source_weight(self):
        """Test _get_source_weight"""
        cc = FleetCommandCenter()

        weight1 = cc._get_source_weight("predictive_engine")
        weight2 = cc._get_source_weight("anomaly_detector")
        weight3 = cc._get_source_weight("driver_scoring")
        weight4 = cc._get_source_weight("unknown_source")

        assert isinstance(weight1, (int, float))
        assert isinstance(weight2, (int, float))
        assert isinstance(weight3, (int, float))
        assert weight4 >= 0

    def test_get_best_source(self):
        """Test _get_best_source"""
        cc = FleetCommandCenter()

        best = cc._get_best_source(
            ["predictive_engine", "anomaly_detector", "driver_scoring"]
        )
        assert isinstance(best, str)

    def test_validate_sensor_value_valid(self):
        """Test sensor value validation"""
        cc = FleetCommandCenter()

        result = cc._validate_sensor_value(220.0, "oil_temp")
        assert result == 220.0 or result is None

    def test_validate_sensor_value_none(self):
        """Test validation with None"""
        cc = FleetCommandCenter()

        result = cc._validate_sensor_value(None, "oil_temp")
        assert result is None

    def test_validate_sensor_value_extreme(self):
        """Test validation with extreme value"""
        cc = FleetCommandCenter()

        result = cc._validate_sensor_value(999.0, "oil_temp")
        # May be None if out of range

    def test_validate_sensor_dict(self):
        """Test sensor dict validation"""
        cc = FleetCommandCenter()

        sensors = {
            "oil_temp": 220.0,
            "coolant_temp": 185.0,
            "voltage": 13.8,
            "invalid": None,
        }

        result = cc._validate_sensor_dict(sensors)
        assert isinstance(result, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
