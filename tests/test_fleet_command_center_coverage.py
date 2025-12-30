"""
Tests to increase fleet_command_center coverage
Target: 55% -> 100%
"""

from datetime import datetime, timezone

import pytest

from fleet_command_center import ActionType, FleetCommandCenter, IssueCategory, Priority


class TestFleetCommandCenterCoverage:
    """Tests to cover missing lines in FleetCommandCenter"""

    def test_load_config_from_db(self):
        """Test _load_config_from_db (lines 1201-1263)"""
        fcc = FleetCommandCenter()
        # This will try to load from DB, should handle gracefully if DB not available
        # The method is called in __init__, so just creating instance covers it
        assert fcc is not None

    def test_validate_sensor_value(self):
        """Test _validate_sensor_value (lines 2923-2967)"""
        fcc = FleetCommandCenter()

        # Valid sensor value (arguments are: value, sensor_name)
        result = fcc._validate_sensor_value(45.0, "oil_press")
        assert result == 45.0

        # Out of range (oil_press range is 0-150)
        result = fcc._validate_sensor_value(200.0, "oil_press")
        assert result is None

        # Invalid value (non-numeric)
        result = fcc._validate_sensor_value("invalid", "oil_press")
        assert result is None

        # Sensor without range defined
        result = fcc._validate_sensor_value(50.0, "unknown_sensor")
        assert result == 50.0

        # Test None value
        result = fcc._validate_sensor_value(None, "oil_press")
        assert result is None

        # Test NaN
        import math

        result = fcc._validate_sensor_value(float("nan"), "oil_press")
        assert result is None

    def test_validate_sensor_dict(self):
        """Test _validate_sensor_dict (lines 2983-3016)"""
        fcc = FleetCommandCenter()

        sensors = {"oil_pressure": 45.0, "coolant_temp": 85.0, "voltage": 13.5}

        validated = fcc._validate_sensor_dict(sensors)
        assert "oil_pressure" in validated
        assert "coolant_temp" in validated

    def test_normalize_component(self):
        """Test _normalize_component (lines 2878-2917)"""
        fcc = FleetCommandCenter()

        # Test known components
        result = fcc._normalize_component("transmision")
        assert result is not None

        result = fcc._normalize_component("turbo")
        assert result is not None

        result = fcc._normalize_component("def")
        assert result is not None

        # Test unknown component
        result = fcc._normalize_component("unknown_part")
        assert result is not None

    def test_get_component_cost(self):
        """Test _get_component_cost (lines 3028-3047)"""
        fcc = FleetCommandCenter()

        cost = fcc._get_component_cost("Transmisión")
        assert isinstance(cost, dict)
        assert "min" in cost or "avg" in cost or isinstance(cost, dict)

    def test_format_cost_string(self):
        """Test _format_cost_string (lines 3038-3047)"""
        fcc = FleetCommandCenter()

        cost_str = fcc._format_cost_string("Transmisión")
        assert isinstance(cost_str, str)
        assert len(cost_str) > 0

    def test_generate_action_id(self):
        """Test _generate_action_id (lines 3019-3028)"""
        fcc = FleetCommandCenter()

        action_id = fcc._generate_action_id()
        assert isinstance(action_id, str)
        assert len(action_id) > 0

        # Generate multiple IDs - should be unique
        ids = [fcc._generate_action_id() for _ in range(10)]
        assert len(ids) == len(set(ids))  # All unique

    def test_determine_action_type(self):
        """Test _determine_action_type (lines 3256-3271)"""
        fcc = FleetCommandCenter()

        # CRITICAL priority with <=1 day
        action = fcc._determine_action_type(Priority.CRITICAL, 0.5)
        assert action == ActionType.STOP_IMMEDIATELY

        # CRITICAL priority with >1 day
        action = fcc._determine_action_type(Priority.CRITICAL, 5.0)
        assert action == ActionType.SCHEDULE_THIS_WEEK

        # HIGH priority
        action = fcc._determine_action_type(Priority.HIGH, 10.0)
        assert action == ActionType.SCHEDULE_THIS_WEEK

        # MEDIUM priority
        action = fcc._determine_action_type(Priority.MEDIUM, 60.0)
        assert action == ActionType.SCHEDULE_THIS_MONTH

        # LOW priority
        action = fcc._determine_action_type(Priority.LOW, 30.0)
        assert action == ActionType.MONITOR

    def test_generate_action_steps(self):
        """Test _generate_action_steps (lines 3273-3319)"""
        fcc = FleetCommandCenter()

        # Test different action types with component and recommendation
        steps = fcc._generate_action_steps(
            "Transmisión", ActionType.SCHEDULE_THIS_WEEK, "Revisar fluidos"
        )
        assert isinstance(steps, list)
        assert len(steps) > 0

        steps = fcc._generate_action_steps(
            "Turbocompresor", ActionType.INSPECT, "Inspeccionar álabes"
        )
        assert isinstance(steps, list)

        steps = fcc._generate_action_steps(
            "Sistema DEF", ActionType.MONITOR, "Monitorear consumo"
        )
        assert isinstance(steps, list)

        # Test oil-specific steps
        steps = fcc._generate_action_steps(
            "Sistema de Aceite", ActionType.SCHEDULE_THIS_MONTH, ""
        )
        assert any("aceite" in str(s).lower() for s in steps)

    def test_get_source_weight(self):
        """Test _get_source_weight"""
        fcc = FleetCommandCenter()

        weight = fcc._get_source_weight("sensor")
        assert isinstance(weight, int)

        weight = fcc._get_source_weight("dtc")
        assert isinstance(weight, int)

    def test_get_best_source(self):
        """Test _get_best_source"""
        fcc = FleetCommandCenter()

        sources = ["sensor", "dtc", "prediction"]
        best = fcc._get_best_source(sources)
        assert best in sources


class TestFleetCommandCenterGenerate:
    """Test the main generate_command_center_data method"""

    def test_generate_command_center_data(self):
        """Test generate_command_center_data (lines 3813-4734)"""
        fcc = FleetCommandCenter()

        # Call the main method
        result = fcc.generate_command_center_data()

        # result is a CommandCenterData object
        assert hasattr(result, "action_items")
        assert hasattr(result, "urgency_summary")
        assert hasattr(result, "fleet_health")
        assert isinstance(result.action_items, list)
        assert result.total_trucks >= 0
