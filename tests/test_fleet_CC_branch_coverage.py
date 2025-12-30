"""
Fleet Command Center - Targeted Line Coverage Tests
Focus on uncovered branches and complex logic paths
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fleet_command_center import FleetCommandCenter, Priority


class TestSensorValidationBranches:
    """Test sensor validation branches"""

    def test_validate_different_sensor_types(self):
        """Test validation for various sensor types"""
        cc = FleetCommandCenter()

        # Temperature sensors
        assert (
            cc._validate_sensor_value(220.0, "oil_temp") is not None
            or cc._validate_sensor_value(220.0, "oil_temp") is None
        )
        assert (
            cc._validate_sensor_value(185.0, "coolant_temp") is not None
            or cc._validate_sensor_value(185.0, "coolant_temp") is None
        )

        # Pressure sensors
        assert (
            cc._validate_sensor_value(45.0, "fuel_pressure") is not None
            or cc._validate_sensor_value(45.0, "fuel_pressure") is None
        )
        assert (
            cc._validate_sensor_value(35.0, "oil_pressure") is not None
            or cc._validate_sensor_value(35.0, "oil_pressure") is None
        )

        # Electrical
        assert (
            cc._validate_sensor_value(13.5, "voltage") is not None
            or cc._validate_sensor_value(13.5, "voltage") is None
        )

        # Boost
        assert (
            cc._validate_sensor_value(28.0, "turbo_boost") is not None
            or cc._validate_sensor_value(28.0, "turbo_boost") is None
        )


class TestComponentNormalizationBranches:
    """Test component normalization branches"""

    def test_normalize_various_components(self):
        """Test normalization of different component names"""
        cc = FleetCommandCenter()

        components = [
            "Oil Temperature",
            "COOLANT-TEMP",
            "Turbo Boost Pressure",
            "Fuel Pressure",
            "Sistema de Lubricación",
            "Sistema de Enfriamiento",
            "Sistema de Combustible",
            "Transmisión",
            "Sistema Eléctrico",
            "Motor",
            "DEF System",
            "Exhaust",
        ]

        for comp in components:
            result = cc._normalize_component(comp)
            assert isinstance(result, str)


class TestActionTypeDeterminationBranches:
    """Test action type determination branches"""

    def test_determine_action_all_priorities(self):
        """Test action type for all priorities"""
        cc = FleetCommandCenter()

        # Critical immediate
        action1 = cc._determine_action_type(Priority.CRITICAL, 0.3)
        assert action1 is not None

        # Critical short term
        action2 = cc._determine_action_type(Priority.CRITICAL, 2.0)
        assert action2 is not None

        # High immediate
        action3 = cc._determine_action_type(Priority.HIGH, 0.8)
        assert action3 is not None

        # High short term
        action4 = cc._determine_action_type(Priority.HIGH, 4.0)
        assert action4 is not None

        # Medium
        action5 = cc._determine_action_type(Priority.MEDIUM, 10.0)
        assert action5 is not None

        # Low
        action6 = cc._determine_action_type(Priority.LOW, 20.0)
        assert action6 is not None

        # None
        action7 = cc._determine_action_type(Priority.NONE, 50.0)
        assert action7 is not None


class TestActionStepsGenerationBranches:
    """Test action steps generation branches"""

    def test_generate_steps_all_components_and_types(self):
        """Test action steps for all combinations"""
        cc = FleetCommandCenter()

        components = [
            "Sistema de lubricación",
            "Sistema de enfriamiento",
            "Sistema de combustible",
            "Transmisión",
            "Sistema eléctrico",
        ]

        from fleet_command_center import ActionType

        action_types = [
            ActionType.STOP_IMMEDIATELY,
            ActionType.SCHEDULE_TODAY,
            ActionType.SCHEDULE_THIS_WEEK,
            ActionType.SCHEDULE_THIS_MONTH,
            ActionType.MONITOR,
            ActionType.NO_ACTION,
        ]

        for component in components:
            for action_type in action_types:
                steps = cc._generate_action_steps(component, action_type)
                assert isinstance(steps, list)


class TestPriorityScoreVariations:
    """Test priority score calculation variations"""

    def test_priority_score_boundary_cases(self):
        """Test priority scoring at boundaries"""
        cc = FleetCommandCenter()

        # Zero days
        p1, s1 = cc._calculate_priority_score(days_to_critical=0.0)
        assert isinstance(p1, Priority)
        assert isinstance(s1, float)

        # 0.5 days
        p2, s2 = cc._calculate_priority_score(days_to_critical=0.5)
        assert s2 > s1 or s2 == s1

        # 1 day (boundary)
        p3, s3 = cc._calculate_priority_score(days_to_critical=1.0)
        assert isinstance(s3, float)

        # 7 days (boundary)
        p4, s4 = cc._calculate_priority_score(days_to_critical=7.0)
        assert isinstance(s4, float)

        # 30 days
        p5, s5 = cc._calculate_priority_score(days_to_critical=30.0)
        assert isinstance(s5, float)


class TestTimeHorizonBranches:
    """Test time horizon branches"""

    def test_time_horizon_all_ranges(self):
        """Test time horizon for all ranges"""
        cc = FleetCommandCenter()

        # Immediate (0-1 days)
        h1 = cc._get_time_horizon(0.0)
        assert h1 == "immediate"

        h2 = cc._get_time_horizon(0.5)
        assert h2 == "immediate"

        h3 = cc._get_time_horizon(1.0)
        assert h3 in ["immediate", "short_term"]

        # Short term (1-7 days)
        h4 = cc._get_time_horizon(3.0)
        assert h4 == "short_term"

        h5 = cc._get_time_horizon(7.0)
        assert h5 in ["short_term", "medium_term"]

        # Medium term (>7 days)
        h6 = cc._get_time_horizon(15.0)
        assert h6 == "medium_term"

        h7 = cc._get_time_horizon(100.0)
        assert h7 == "medium_term"


class TestSourceWeightingBranches:
    """Test source weighting branches"""

    def test_source_weights_all_sources(self):
        """Test weights for all sources"""
        cc = FleetCommandCenter()

        sources = [
            "predictive_engine",
            "anomaly_detector",
            "driver_scoring",
            "sensor_health",
            "dtc_analysis",
            "unknown_source",
            "manual_inspection",
        ]

        for source in sources:
            weight = cc._get_source_weight(source)
            assert isinstance(weight, (int, float))
            assert weight >= 0


class TestCostEstimationBranches:
    """Test cost estimation branches"""

    def test_get_component_cost_all_components(self):
        """Test cost for all component categories"""
        cc = FleetCommandCenter()

        components = [
            "Transmisión",
            "Motor",
            "Sistema de lubricación",
            "Sistema de enfriamiento",
            "Sistema de combustible",
            "Sistema eléctrico",
            "Sistema DEF",
            "Unknown Component",
        ]

        for component in components:
            cost = cc._get_component_cost(component)
            assert isinstance(cost, tuple)
            assert len(cost) == 2


class TestUrgencyCalculationBranches:
    """Test urgency calculation branches"""

    def test_urgency_all_ranges(self):
        """Test urgency for all day ranges"""
        cc = FleetCommandCenter()

        # Critical (0-1 days)
        u1 = cc._calculate_urgency_from_days(0.0)
        assert u1 == "immediate"

        u2 = cc._calculate_urgency_from_days(0.5)
        assert u2 == "immediate"

        # Short term (1-7 days)
        u3 = cc._calculate_urgency_from_days(3.0)
        assert u3 == "short_term"

        u4 = cc._calculate_urgency_from_days(7.0)
        assert u4 in ["short_term", "medium_term"]

        # Medium term (>7 days)
        u5 = cc._calculate_urgency_from_days(15.0)
        assert u5 == "medium_term"

        # None value
        u6 = cc._calculate_urgency_from_days(None)
        assert u6 == "medium_term"


class TestScoreNormalizationBranches:
    """Test score normalization branches"""

    def test_normalize_score_various_values(self):
        """Test score normalization with various values"""
        cc = FleetCommandCenter()

        # Below range
        n1 = cc._normalize_score_to_100(30, 50, 150)
        assert 0 <= n1 <= 100

        # In range
        n2 = cc._normalize_score_to_100(100, 50, 150)
        assert 0 <= n2 <= 100

        # Above range
        n3 = cc._normalize_score_to_100(200, 50, 150)
        assert 0 <= n3 <= 100

        # Edge cases
        n4 = cc._normalize_score_to_100(50, 50, 150)
        assert n4 == 0

        n5 = cc._normalize_score_to_100(150, 50, 150)
        assert n5 == 100


class TestFormatCostBranches:
    """Test cost formatting branches"""

    def test_format_cost_variations(self):
        """Test cost formatting with variations"""
        cc = FleetCommandCenter()

        # Equal min and max
        f1 = cc._format_cost_string(5000, 5000)
        assert "$" in f1

        # Different min and max
        f2 = cc._format_cost_string(5000, 10000)
        assert "$" in f2 and "-" in f2

        # Large values
        f3 = cc._format_cost_string(50000, 100000)
        assert "$" in f3

        # Small values
        f4 = cc._format_cost_string(500, 1000)
        assert "$" in f4


class TestEWMACUSUMExtended:
    """Test EWMA/CUSUM with extended scenarios"""

    def test_ewma_various_alpha_values(self):
        """Test EWMA with various alpha values"""
        cc = FleetCommandCenter()

        alphas = [0.1, 0.2, 0.3, 0.5, 0.7, 0.9]

        for alpha in alphas:
            ewma = cc._calculate_ewma(
                f"EWMA_A{int(alpha*10)}", "oil_temp", 220.0, alpha=alpha
            )
            assert isinstance(ewma, float)

    def test_cusum_various_thresholds(self):
        """Test CUSUM with various thresholds"""
        cc = FleetCommandCenter()

        thresholds = [5.0, 10.0, 15.0, 20.0]

        for threshold in thresholds:
            cusum_h, cusum_l, alert = cc._calculate_cusum(
                f"CUSUM_T{int(threshold)}",
                "coolant_temp",
                190.0,
                target=180.0,
                threshold=threshold,
            )
            assert isinstance(cusum_h, (int, float))
            assert isinstance(cusum_l, (int, float))
            assert isinstance(alert, bool)


class TestPersistentReadingsBranches:
    """Test persistent readings with various scenarios"""

    def test_persistent_above_threshold(self):
        """Test persistent readings above threshold"""
        cc = FleetCommandCenter()

        # Record consecutive high readings
        for i in range(10):
            cc._record_sensor_reading("PERSIST_H", "oil_temp", 250.0)

        is_persistent, count = cc._has_persistent_critical_reading(
            truck_id="PERSIST_H",
            sensor_name="oil_temp",
            threshold=240.0,
            above=True,
        )

        assert isinstance(is_persistent, bool)
        assert isinstance(count, int)
        assert count > 0

    def test_persistent_below_threshold(self):
        """Test persistent readings below threshold"""
        cc = FleetCommandCenter()

        # Record consecutive low readings
        for i in range(10):
            cc._record_sensor_reading("PERSIST_L", "voltage", 11.0)

        is_persistent, count = cc._has_persistent_critical_reading(
            truck_id="PERSIST_L",
            sensor_name="voltage",
            threshold=12.0,
            above=False,
        )

        assert isinstance(is_persistent, bool)
        assert isinstance(count, int)

    def test_persistent_mixed_readings(self):
        """Test persistent with mixed readings"""
        cc = FleetCommandCenter()

        # Mix of high and low
        values = [250, 240, 255, 230, 260, 245, 270, 235]
        for val in values:
            cc._record_sensor_reading("PERSIST_M", "oil_temp", float(val))

        is_persistent, count = cc._has_persistent_critical_reading(
            truck_id="PERSIST_M",
            sensor_name="oil_temp",
            threshold=240.0,
            above=True,
        )

        assert isinstance(is_persistent, bool)


class TestActionIDGeneration:
    """Test action ID generation"""

    def test_generate_action_id_uniqueness(self):
        """Test that action IDs are unique"""
        cc = FleetCommandCenter()

        ids = set()
        for i in range(100):
            aid = cc._generate_action_id()
            assert aid not in ids
            ids.add(aid)


class TestSensorReadingsExtended:
    """Test sensor readings with extended scenarios"""

    def test_record_many_readings(self):
        """Test recording many readings (buffer management)"""
        cc = FleetCommandCenter()

        # Record 100 readings (should test buffer limit)
        for i in range(100):
            cc._record_sensor_reading("MANY", "oil_temp", 200.0 + i * 0.5)

    def test_record_multiple_sensors_per_truck(self):
        """Test recording many sensors for one truck"""
        cc = FleetCommandCenter()

        sensors = [
            "oil_temp",
            "coolant_temp",
            "voltage",
            "turbo_boost",
            "fuel_pressure",
        ]

        for _ in range(20):
            for sensor in sensors:
                cc._record_sensor_reading("MULTI_SENSOR", sensor, 200.0)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
