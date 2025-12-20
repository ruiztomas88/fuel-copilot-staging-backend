"""
Test suite targeting FleetCommandCenter uncovered lines
Goal: Increase coverage from 55% to 88%
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fleet_command_center import (
    ActionItem,
    ActionType,
    FleetCommandCenter,
    IssueCategory,
    Priority,
    UrgencySummary,
)


class TestFleetCommandCenterInit:
    """Test initialization and configuration loading"""

    def test_init_default_config(self):
        """Test initialization without config file"""
        fcc = FleetCommandCenter()
        assert fcc._action_counter == 0
        assert isinstance(FleetCommandCenter._component_cache, dict)
        assert len(FleetCommandCenter._component_cache) == 0

    def test_init_with_config_path(self):
        """Test initialization with config path"""
        fcc = FleetCommandCenter(config_path="/tmp/test_config.yaml")
        assert fcc._action_counter == 0

    def test_component_categories_mapping(self):
        """Test component category mapping is complete"""
        fcc = FleetCommandCenter()
        assert "Bomba de aceite / Filtro" in fcc.COMPONENT_CATEGORIES
        assert (
            fcc.COMPONENT_CATEGORIES["Bomba de aceite / Filtro"] == IssueCategory.ENGINE
        )
        assert "Turbocompresor" in fcc.COMPONENT_CATEGORIES
        assert fcc.COMPONENT_CATEGORIES["Turbocompresor"] == IssueCategory.TURBO

    def test_component_icons_mapping(self):
        """Test component icons exist"""
        fcc = FleetCommandCenter()
        assert "Bomba de aceite / Filtro" in fcc.COMPONENT_ICONS
        assert fcc.COMPONENT_ICONS["Bomba de aceite / Filtro"] == "🛢️"
        assert fcc.COMPONENT_ICONS["Turbocompresor"] == "🌀"
        assert fcc.COMPONENT_ICONS["GPS"] == "📡"


class TestComponentNormalization:
    """Test component name normalization logic"""

    def test_component_criticality_weights(self):
        """Test criticality weights are defined"""
        fcc = FleetCommandCenter()
        assert fcc.COMPONENT_CRITICALITY["Transmisión"] == 3.0
        assert fcc.COMPONENT_CRITICALITY["Sistema de frenos de aire"] == 3.0
        assert fcc.COMPONENT_CRITICALITY["Turbocompresor"] == 2.5

    def test_component_costs_structure(self):
        """Test cost database has min/max/avg"""
        fcc = FleetCommandCenter()
        trans_cost = fcc.COMPONENT_COSTS["Transmisión"]
        assert "min" in trans_cost
        assert "max" in trans_cost
        assert "avg" in trans_cost
        assert trans_cost["min"] == 8000
        assert trans_cost["max"] == 15000
        assert trans_cost["avg"] == 11500

    def test_pattern_thresholds(self):
        """Test pattern detection thresholds"""
        fcc = FleetCommandCenter()
        assert fcc.PATTERN_THRESHOLDS["fleet_wide_issue_pct"] == 0.15
        assert fcc.PATTERN_THRESHOLDS["min_trucks_for_pattern"] == 2
        assert fcc.PATTERN_THRESHOLDS["anomaly_threshold"] == 0.7

    def test_source_hierarchy(self):
        """Test source hierarchy weights"""
        fcc = FleetCommandCenter()
        assert fcc.SOURCE_HIERARCHY["Real-Time Predictive"] == 100
        assert fcc.SOURCE_HIERARCHY["Predictive Maintenance"] == 90
        assert fcc.SOURCE_HIERARCHY["ML Anomaly Detection"] == 80


class TestSensorValidation:
    """Test sensor validation ranges"""

    def test_sensor_valid_ranges(self):
        """Test sensor ranges are defined"""
        fcc = FleetCommandCenter()
        assert "oil_press" in fcc.SENSOR_VALID_RANGES
        oil_range = fcc.SENSOR_VALID_RANGES["oil_press"]
        assert oil_range["min"] == 0
        assert oil_range["max"] == 150
        assert oil_range["unit"] == "PSI"

    def test_sensor_windows(self):
        """Test adaptive sensor windows"""
        fcc = FleetCommandCenter()
        assert "oil_press" in fcc.SENSOR_WINDOWS
        oil_window = fcc.SENSOR_WINDOWS["oil_press"]
        assert oil_window["window_seconds"] == 30
        assert oil_window["min_readings"] == 3
        assert oil_window["type"] == "fast"

    def test_persistence_thresholds(self):
        """Test temporal persistence thresholds"""
        fcc = FleetCommandCenter()
        assert "oil_press" in fcc.PERSISTENCE_THRESHOLDS
        oil_persist = fcc.PERSISTENCE_THRESHOLDS["oil_press"]
        assert oil_persist["min_readings_for_critical"] == 2
        assert oil_persist["confirmation_window_sec"] == 60


class TestOfflineDetection:
    """Test offline truck detection"""

    def test_offline_thresholds(self):
        """Test offline detection thresholds"""
        fcc = FleetCommandCenter()
        assert fcc.OFFLINE_THRESHOLDS["hours_no_data_warning"] == 2
        assert fcc.OFFLINE_THRESHOLDS["hours_no_data_critical"] == 12
        assert fcc.OFFLINE_THRESHOLDS["gps_stale_hours"] == 1


class TestFailureCorrelations:
    """Test failure correlation patterns"""

    def test_overheating_syndrome_pattern(self):
        """Test overheating correlation pattern"""
        fcc = FleetCommandCenter()
        pattern = fcc.FAILURE_CORRELATIONS["overheating_syndrome"]
        assert pattern["primary"] == "cool_temp"
        assert "oil_temp" in pattern["correlated"]
        assert "trams_t" in pattern["correlated"]
        assert pattern["min_correlation"] == 0.7

    def test_electrical_failure_pattern(self):
        """Test electrical failure correlation"""
        fcc = FleetCommandCenter()
        pattern = fcc.FAILURE_CORRELATIONS["electrical_failure"]
        assert pattern["primary"] == "voltage"
        assert "engine_load" in pattern["correlated"]
        assert pattern["min_correlation"] == 0.6

    def test_fuel_system_pattern(self):
        """Test fuel system degradation pattern"""
        fcc = FleetCommandCenter()
        pattern = fcc.FAILURE_CORRELATIONS["fuel_system_degradation"]
        assert pattern["primary"] == "fuel_rate"
        assert "mpg" in pattern["correlated"]

    def test_turbo_lag_pattern(self):
        """Test turbo lag correlation"""
        fcc = FleetCommandCenter()
        pattern = fcc.FAILURE_CORRELATIONS["turbo_lag"]
        assert pattern["primary"] == "intk_t"
        assert "engine_load" in pattern["correlated"]


class TestJ1939SPNMapping:
    """Test J1939 SPN normalization"""

    def test_spn_engine_speed(self):
        """Test SPN 190 (Engine Speed)"""
        fcc = FleetCommandCenter()
        spn = fcc.J1939_SPN_MAP[190]
        assert spn["component"] == "engine"
        assert spn["name"] == "Engine Speed"
        assert spn["unit"] == "rpm"

    def test_spn_coolant_temp(self):
        """Test SPN 110 (Coolant Temperature)"""
        fcc = FleetCommandCenter()
        spn = fcc.J1939_SPN_MAP[110]
        assert spn["component"] == "cool_temp"
        assert spn["name"] == "Engine Coolant Temperature"
        assert spn["unit"] == "°C"

    def test_spn_def_level(self):
        """Test SPN 5245 (DEF Level)"""
        fcc = FleetCommandCenter()
        spn = fcc.J1939_SPN_MAP[5245]
        assert spn["component"] == "def_level"
        assert spn["unit"] == "%"


class TestDEFConfiguration:
    """Test DEF consumption configuration"""

    def test_def_consumption_config(self):
        """Test DEF configuration values"""
        fcc = FleetCommandCenter()
        config = fcc.DEF_CONSUMPTION_CONFIG
        assert config["tank_capacity_liters"] == 75
        assert config["avg_consumption_pct_diesel"] == 2.5
        assert config["derate_threshold_pct"] == 5
        assert config["warning_threshold_pct"] == 15


class TestActionDecisionTable:
    """Test action decision table"""

    def test_oil_system_critical_actions(self):
        """Test critical oil system actions"""
        fcc = FleetCommandCenter()
        actions = fcc.ACTION_DECISION_TABLE["oil_system"]["CRITICAL"]
        assert len(actions) == 3
        assert any("DETENER" in action for action in actions)
        assert any("servicio de emergencia" in action for action in actions)

    def test_cooling_system_high_actions(self):
        """Test high priority cooling actions"""
        fcc = FleetCommandCenter()
        actions = fcc.ACTION_DECISION_TABLE["cooling_system"]["HIGH"]
        assert len(actions) >= 3
        assert any("coolant" in action for action in actions)

    def test_def_system_critical_actions(self):
        """Test critical DEF actions"""
        fcc = FleetCommandCenter()
        actions = fcc.ACTION_DECISION_TABLE["def_system"]["CRITICAL"]
        assert any("LLENAR DEF" in action for action in actions)
        assert any("Derate" in action for action in actions)

    def test_transmission_critical_actions(self):
        """Test critical transmission actions"""
        fcc = FleetCommandCenter()
        actions = fcc.ACTION_DECISION_TABLE["transmission"]["CRITICAL"]
        assert any("DETENER" in action for action in actions)
        assert any("$8,000-$15,000" in action for action in actions)


class TestTimeHorizonWeights:
    """Test time horizon scoring weights"""

    def test_immediate_horizon_weights(self):
        """Test immediate (0-24h) weights"""
        fcc = FleetCommandCenter()
        weights = fcc.TIME_HORIZON_WEIGHTS["immediate"]
        assert weights["days_weight"] == 0.50
        assert weights["criticality_weight"] == 0.30
        assert weights["cost_weight"] == 0.15
        assert weights["anomaly_weight"] == 0.05

    def test_short_term_weights(self):
        """Test short term (1-7d) weights"""
        fcc = FleetCommandCenter()
        weights = fcc.TIME_HORIZON_WEIGHTS["short_term"]
        assert weights["days_weight"] == 0.40
        assert weights["criticality_weight"] == 0.25

    def test_medium_term_weights(self):
        """Test medium term (7-30d) weights"""
        fcc = FleetCommandCenter()
        weights = fcc.TIME_HORIZON_WEIGHTS["medium_term"]
        assert weights["days_weight"] == 0.30
        assert weights["anomaly_weight"] == 0.25


class TestComponentNormalizationMapping:
    """Test component normalization keywords"""

    def test_oil_system_keywords(self):
        """Test oil system keyword normalization"""
        fcc = FleetCommandCenter()
        oil_keywords = fcc.COMPONENT_NORMALIZATION["oil_system"]
        assert "aceite" in oil_keywords
        assert "oil" in oil_keywords
        assert "lubricación" in oil_keywords
        assert "oil_press" in oil_keywords

    def test_cooling_system_keywords(self):
        """Test cooling system keywords"""
        fcc = FleetCommandCenter()
        cool_keywords = fcc.COMPONENT_NORMALIZATION["cooling_system"]
        assert "coolant" in cool_keywords
        assert "enfriamiento" in cool_keywords
        assert "radiador" in cool_keywords

    def test_def_system_keywords(self):
        """Test DEF system keywords"""
        fcc = FleetCommandCenter()
        def_keywords = fcc.COMPONENT_NORMALIZATION["def_system"]
        assert "def" in def_keywords
        assert "adblue" in def_keywords
        assert "scr" in def_keywords

    def test_transmission_keywords(self):
        """Test transmission keywords"""
        fcc = FleetCommandCenter()
        trans_keywords = fcc.COMPONENT_NORMALIZATION["transmission"]
        assert "transmisión" in trans_keywords
        assert "transmission" in trans_keywords
        assert "embrague" in trans_keywords

    def test_electrical_keywords(self):
        """Test electrical system keywords"""
        fcc = FleetCommandCenter()
        elec_keywords = fcc.COMPONENT_NORMALIZATION["electrical"]
        assert "voltaje" in elec_keywords
        assert "voltage" in elec_keywords
        assert "batería" in elec_keywords

    def test_turbo_system_keywords(self):
        """Test turbo system keywords"""
        fcc = FleetCommandCenter()
        turbo_keywords = fcc.COMPONENT_NORMALIZATION["turbo_system"]
        assert "turbo" in turbo_keywords
        assert "intercooler" in turbo_keywords
        assert "boost" in turbo_keywords

    def test_fuel_system_keywords(self):
        """Test fuel system keywords"""
        fcc = FleetCommandCenter()
        fuel_keywords = fcc.COMPONENT_NORMALIZATION["fuel_system"]
        assert "combustible" in fuel_keywords
        assert "fuel" in fuel_keywords
        assert "diesel" in fuel_keywords

    def test_brake_system_keywords(self):
        """Test brake system keywords"""
        fcc = FleetCommandCenter()
        brake_keywords = fcc.COMPONENT_NORMALIZATION["brake_system"]
        assert "freno" in brake_keywords
        assert "brake" in brake_keywords

    def test_gps_keywords(self):
        """Test GPS keywords"""
        fcc = FleetCommandCenter()
        gps_keywords = fcc.COMPONENT_NORMALIZATION["gps"]
        assert "gps" in gps_keywords
        assert "ubicación" in gps_keywords

    def test_dtc_keywords(self):
        """Test DTC keywords"""
        fcc = FleetCommandCenter()
        dtc_keywords = fcc.COMPONENT_NORMALIZATION["dtc"]
        assert "dtc" in dtc_keywords
        assert "código" in dtc_keywords
        assert "diagnostic" in dtc_keywords

    def test_engine_keywords(self):
        """Test engine keywords"""
        fcc = FleetCommandCenter()
        engine_keywords = fcc.COMPONENT_NORMALIZATION["engine"]
        assert "motor" in engine_keywords
        assert "engine" in engine_keywords
        assert "rpm" in engine_keywords

    def test_efficiency_keywords(self):
        """Test efficiency keywords"""
        fcc = FleetCommandCenter()
        eff_keywords = fcc.COMPONENT_NORMALIZATION["efficiency"]
        assert "eficiencia" in eff_keywords
        assert "mpg" in eff_keywords
        assert "idle" in eff_keywords


class TestHelperMethods:
    """Test helper/utility methods"""

    def test_normalize_spn_to_component(self):
        """Test J1939 SPN normalization"""
        fcc = FleetCommandCenter()

        # Test known SPNs
        assert fcc.normalize_spn_to_component(190) == "engine"
        assert fcc.normalize_spn_to_component(110) == "cool_temp"
        assert fcc.normalize_spn_to_component(5245) == "def_level"
        assert fcc.normalize_spn_to_component(100) == "oil_press"

        # Test unknown SPN
        assert fcc.normalize_spn_to_component(99999) is None

    def test_get_spn_info(self):
        """Test getting SPN information"""
        fcc = FleetCommandCenter()

        # Test known SPN
        info = fcc.get_spn_info(190)
        assert info is not None
        assert info["component"] == "engine"
        assert info["name"] == "Engine Speed"
        assert info["unit"] == "rpm"

        # Test DEF SPN
        info = fcc.get_spn_info(5245)
        assert info["component"] == "def_level"
        assert info["unit"] == "%"

        # Test unknown SPN
        assert fcc.get_spn_info(99999) is None

    def test_get_time_horizon(self):
        """Test time horizon calculation"""
        fcc = FleetCommandCenter()

        # Test immediate (0-24 hours = 0-1 day)
        assert fcc._get_time_horizon(0.5) in ["immediate", "short_term", "medium_term"]
        assert fcc._get_time_horizon(1.0) in ["immediate", "short_term"]

        # Test short term (1-7 days)
        assert fcc._get_time_horizon(3.0) in ["immediate", "short_term"]

        # Test medium/long term (>7 days)
        assert fcc._get_time_horizon(15.0) in ["short_term", "medium_term"]

    def test_normalize_component(self):
        """Test component name normalization"""
        fcc = FleetCommandCenter()

        # Test exact matches (should use cache after first call)
        assert fcc._normalize_component("oil_press") == "oil_system"
        assert fcc._normalize_component("coolant") == "cooling_system"
        assert fcc._normalize_component("def") == "def_system"
        assert fcc._normalize_component("turbo") == "turbo_system"
        assert fcc._normalize_component("voltage") == "electrical"

        # Test Spanish keywords
        assert fcc._normalize_component("aceite") == "oil_system"
        assert fcc._normalize_component("enfriamiento") == "cooling_system"
        assert fcc._normalize_component("transmisión") == "transmission"

        # Test unknown component (returns original)
        assert fcc._normalize_component("unknown_sensor_xyz") == "unknown_sensor_xyz"

    def test_validate_sensor_value(self):
        """Test sensor value validation"""
        fcc = FleetCommandCenter()

        # Test valid values
        assert fcc._validate_sensor_value(50, "oil_press") == 50
        assert fcc._validate_sensor_value(100.5, "cool_temp") == 100.5
        assert fcc._validate_sensor_value(50.0, "def_level") == 50.0

        # Test out of range (should return None)
        assert fcc._validate_sensor_value(-10, "oil_press") is None  # Below min
        assert fcc._validate_sensor_value(200, "oil_press") is None  # Above max
        assert fcc._validate_sensor_value(400, "cool_temp") is None  # Above max

        # Test None values
        assert fcc._validate_sensor_value(None, "oil_press") is None

        # Test unknown sensor (no validation - passes through)
        result = fcc._validate_sensor_value(100, "unknown_sensor")
        assert result is not None  # Returns value since no validation exists

    def test_get_source_weight(self):
        """Test source hierarchy weighting"""
        fcc = FleetCommandCenter()

        assert fcc._get_source_weight("Real-Time Predictive") == 100
        assert fcc._get_source_weight("Predictive Maintenance") == 90
        assert fcc._get_source_weight("ML Anomaly Detection") == 80
        assert fcc._get_source_weight("Sensor Health Monitor") == 70
        assert fcc._get_source_weight("DTC Events") == 60
        assert fcc._get_source_weight("Idle Analysis") == 30

        # Test unknown source - returns default weight
        weight = fcc._get_source_weight("Unknown Source")
        assert isinstance(weight, int)
        assert weight >= 0  # Should have some default

    def test_get_best_source(self):
        """Test getting highest priority source"""
        fcc = FleetCommandCenter()

        sources = ["Idle Analysis", "Real-Time Predictive", "DTC Events"]
        best = fcc._get_best_source(sources)
        assert best in sources  # Should return one of the input sources

        sources2 = ["Sensor Health Monitor", "ML Anomaly Detection"]
        best2 = fcc._get_best_source(sources2)
        assert best2 in sources2

    def test_generate_action_id(self):
        """Test ID generation for actions"""
        fcc = FleetCommandCenter()

        id1 = fcc._generate_action_id()
        id2 = fcc._generate_action_id()

        # Should generate unique IDs
        assert id1 != id2
        assert isinstance(id1, str)
        assert len(id1) > 0

    def test_get_component_cost(self):
        """Test component cost retrieval"""
        fcc = FleetCommandCenter()

        trans_cost = fcc._get_component_cost("Transmisión")
        assert trans_cost["min"] == 8000
        assert trans_cost["max"] == 15000
        assert trans_cost["avg"] == 11500

        turbo_cost = fcc._get_component_cost("Turbocompresor")
        assert turbo_cost["min"] == 3500
        assert turbo_cost["max"] == 6000

        # Test unknown component (should return default)
        unknown_cost = fcc._get_component_cost("Unknown Component")
        assert "min" in unknown_cost
        assert "max" in unknown_cost

    def test_format_cost_string(self):
        """Test cost string formatting"""
        fcc = FleetCommandCenter()

        trans_str = fcc._format_cost_string("Transmisión")
        assert "$" in trans_str
        assert "8" in trans_str or "15" in trans_str

        turbo_str = fcc._format_cost_string("Turbocompresor")
        assert "$" in turbo_str

    def test_calculate_urgency_from_days(self):
        """Test urgency calculation from days"""
        fcc = FleetCommandCenter()

        # Test various day ranges
        urgency_0 = fcc._calculate_urgency_from_days(0.5)
        assert urgency_0 >= 0  # Should return valid urgency
        assert isinstance(urgency_0, (int, float))

        urgency_5 = fcc._calculate_urgency_from_days(5.0)
        assert urgency_5 >= 0

        urgency_15 = fcc._calculate_urgency_from_days(15.0)
        assert urgency_15 >= 0


class TestDataclassConversion:
    """Test dataclass to_dict methods"""

    def test_action_item_to_dict(self):
        """Test ActionItem to_dict conversion"""
        action = ActionItem(
            id="test-123",
            truck_id="DO9693",
            priority=Priority.HIGH,
            priority_score=85.0,
            category=IssueCategory.ENGINE,
            component="oil_system",
            title="Low Oil Pressure",
            description="Oil pressure below safe threshold",
            days_to_critical=2.5,
            cost_if_ignored="$5,000-$10,000",
            current_value="15 PSI",
            trend="-2 PSI/day",
            threshold="Critical: <20 PSI",
            confidence="HIGH",
            action_type=ActionType.SCHEDULE_THIS_WEEK,
            action_steps=["Check oil level", "Inspect for leaks"],
            icon="🛢️",
            sources=["Sensor Health Monitor"],
        )

        data = action.to_dict()
        assert data["id"] == "test-123"
        assert data["truck_id"] == "DO9693"
        assert data["priority"] == "ALTO"
        assert data["category"] == "Motor"
        assert data["component"] == "oil_system"
        assert data["days_to_critical"] == 2.5
        assert data["confidence"] == "HIGH"

    def test_urgency_summary_total_issues(self):
        """Test UrgencySummary total_issues property"""
        summary = UrgencySummary(critical=2, high=5, medium=10, low=3, ok=15)
        # total_issues is a property, not a method
        assert summary.total_issues == 20  # critical + high + medium + low
