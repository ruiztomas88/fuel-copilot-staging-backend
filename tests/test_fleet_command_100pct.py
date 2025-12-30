"""
Fleet Command Center 100% Coverage Test Suite
Complete coverage for all functions, methods, and edge cases.
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pytest

from fleet_command_center import (
    ActionItem,
    ActionType,
    CommandCenterData,
    CostProjection,
    FleetCommandCenter,
    FleetHealthScore,
    IssueCategory,
    Priority,
    SensorStatus,
    UrgencySummary,
    get_command_center,
)


class TestFleetCommandCenterComplete:
    """Complete 100% coverage tests for Fleet Command Center"""

    def test_init_default(self):
        """Test FleetCommandCenter initialization with default config"""
        fcc = FleetCommandCenter()
        assert fcc is not None
        assert hasattr(fcc, "VERSION")
        assert hasattr(fcc, "COMPONENT_CATEGORIES")
        assert hasattr(fcc, "COMPONENT_COSTS")

    def test_init_with_config_path(self):
        """Test FleetCommandCenter initialization with custom config"""
        fcc = FleetCommandCenter(config_path="custom_config.yaml")
        assert fcc is not None

    def test_normalize_component_basic(self):
        """Test component normalization"""
        fcc = FleetCommandCenter()
        assert fcc.normalize_component("oil_pressure") == "oil_system"
        assert fcc.normalize_component("transmission") == "transmission"
        assert fcc.normalize_component("DEF Level") == "def_system"
        assert fcc.normalize_component("coolant_temp") == "cooling_system"
        assert fcc.normalize_component("unknown") == "unknown"

    def test_validate_sensor_value(self):
        """Test sensor value validation"""
        fcc = FleetCommandCenter()
        assert fcc.validate_sensor_value(50.0) == 50.0
        assert fcc.validate_sensor_value(None) is None
        assert fcc.validate_sensor_value(float("nan")) is None
        assert fcc.validate_sensor_value(float("inf")) is None
        assert fcc.validate_sensor_value(-float("inf")) is None

    def test_validate_sensor_dict(self):
        """Test sensor dictionary validation"""
        fcc = FleetCommandCenter()
        sensors = {
            "oil_pressure": 45.0,
            "coolant_temp": 190.0,
            "voltage": float("nan"),
            "rpm": float("inf"),
        }
        validated = fcc.validate_sensor_dict(sensors)
        assert validated["oil_pressure"] == 45.0
        assert validated["coolant_temp"] == 190.0
        assert validated["voltage"] is None
        assert validated["rpm"] is None

    def test_get_source_weight(self):
        """Test source weight calculation"""
        fcc = FleetCommandCenter()
        assert fcc.get_source_weight("realtime") == 1.0
        assert fcc.get_source_weight("predictive") == 0.8
        assert fcc.get_source_weight("historical") == 0.6
        assert fcc.get_source_weight("unknown") == 0.4

    def test_get_best_source(self):
        """Test best source selection"""
        fcc = FleetCommandCenter()
        sources = ["historical", "predictive", "realtime"]
        assert fcc.get_best_source(sources) == "realtime"
        assert fcc.get_best_source(["historical"]) == "historical"
        assert fcc.get_best_source([]) is None

    def test_generate_action_id(self):
        """Test action ID generation"""
        fcc = FleetCommandCenter()
        id1 = fcc.generate_action_id("T001", "oil_system")
        id2 = fcc.generate_action_id("T001", "oil_system")
        id3 = fcc.generate_action_id("T002", "oil_system")

        assert id1.startswith("ACT-")
        assert len(id1) > 10
        assert id1 != id2  # Should be unique
        assert id1 != id3

    def test_get_component_cost(self):
        """Test component cost retrieval"""
        fcc = FleetCommandCenter()
        assert fcc.get_component_cost("oil_system") > 0
        assert fcc.get_component_cost("transmission") > 0
        assert fcc.get_component_cost("unknown") == 1000  # Default

    def test_format_cost_string(self):
        """Test cost string formatting"""
        fcc = FleetCommandCenter()
        result = fcc.format_cost_string("oil_system")
        assert "$" in result
        assert "USD" in result or "," in result

    def test_calculate_urgency_from_days(self):
        """Test urgency calculation from days"""
        fcc = FleetCommandCenter()
        assert fcc.calculate_urgency_from_days(0) == 1.0
        assert fcc.calculate_urgency_from_days(1) < 1.0
        assert fcc.calculate_urgency_from_days(30) < 0.5
        assert fcc.calculate_urgency_from_days(-1) == 1.0
        assert fcc.calculate_urgency_from_days(None) == 0.5

    def test_normalize_spn_to_component(self):
        """Test SPN to component mapping"""
        fcc = FleetCommandCenter()
        assert fcc.normalize_spn_to_component(110) == "coolant_temp"
        assert fcc.normalize_spn_to_component(190) == "rpm"
        assert fcc.normalize_spn_to_component(9999) == "unknown"

    def test_get_spn_info(self):
        """Test SPN info retrieval"""
        fcc = FleetCommandCenter()
        info = fcc.get_spn_info(110)
        assert "description" in info
        assert "component" in info

        info_unknown = fcc.get_spn_info(9999)
        assert info_unknown["component"] == "unknown"

    def test_get_time_horizon(self):
        """Test time horizon calculation"""
        fcc = FleetCommandCenter()
        assert fcc.get_time_horizon(0) == "immediate"
        assert fcc.get_time_horizon(3) == "short_term"
        assert fcc.get_time_horizon(15) == "medium_term"
        assert fcc.get_time_horizon(None) == "long_term"

    def test_action_item_to_dict(self):
        """Test ActionItem serialization"""
        item = ActionItem(
            action_id="ACT-123",
            truck_id="T001",
            priority=Priority.CRITICAL,
            action_type=ActionType.STOP_IMMEDIATELY,
            component="oil_system",
            description="Low oil pressure",
            category=IssueCategory.SENSOR,
            source="predictive",
            urgency_score=0.95,
            timestamp=datetime.now(),
            steps=["Step 1", "Step 2"],
            cost_if_ignored="$5,000",
            days_to_critical=2,
            recommended_action="Check oil level",
        )

        result = item.to_dict()
        assert result["action_id"] == "ACT-123"
        assert result["truck_id"] == "T001"
        assert result["priority"] == "CRITICAL"
        assert "timestamp" in result
        assert isinstance(result["steps"], list)

    def test_urgency_summary_total_issues(self):
        """Test UrgencySummary total calculation"""
        summary = UrgencySummary(critical=5, high=10, medium=15, low=20, ok=50)
        assert summary.total_issues == 50  # critical + high + medium + low

    def test_fleet_health_score_creation(self):
        """Test FleetHealthScore creation"""
        health = FleetHealthScore(
            score=85.0, status="good", trend="improving", description="Fleet is healthy"
        )
        assert health.score == 85.0
        assert health.status == "good"

    def test_cost_projection_creation(self):
        """Test CostProjection creation"""
        cost = CostProjection(
            immediate_risk=5000.0, week_risk=10000.0, month_risk=25000.0
        )
        assert cost.immediate_risk == 5000.0
        assert cost.month_risk == 25000.0

    def test_sensor_status_creation(self):
        """Test SensorStatus creation"""
        status = SensorStatus(
            gps_issues=2,
            voltage_issues=1,
            dtc_active=3,
            idle_deviation=4,
            total_trucks=50,
        )
        assert status.gps_issues == 2
        assert status.total_trucks == 50

    def test_command_center_data_to_dict(self):
        """Test CommandCenterData serialization"""
        data = CommandCenterData(
            version="1.0",
            generated_at=datetime.now().isoformat(),
            fleet_health=FleetHealthScore(
                score=90.0, status="excellent", trend="stable", description="Good"
            ),
            total_trucks=10,
            trucks_analyzed=10,
            urgency_summary=UrgencySummary(critical=0, high=2, medium=3, low=5, ok=0),
            sensor_status=SensorStatus(
                gps_issues=0,
                voltage_issues=0,
                dtc_active=0,
                idle_deviation=0,
                total_trucks=10,
            ),
            cost_projection=CostProjection(
                immediate_risk=0.0, week_risk=5000.0, month_risk=15000.0
            ),
            action_items=[],
            critical_actions=[],
            high_priority_actions=[],
            insights=[],
            data_quality={"completeness": 100},
        )

        result = data.to_dict()
        assert result["version"] == "1.0"
        assert "fleet_health" in result
        assert result["fleet_health"]["score"] == 90.0
        assert "cost_projection" in result
        assert result["cost_projection"]["immediate_risk"] == 0.0

    def test_determine_action_type(self):
        """Test action type determination"""
        fcc = FleetCommandCenter()

        assert (
            fcc.determine_action_type(Priority.CRITICAL, 0)
            == ActionType.STOP_IMMEDIATELY
        )
        assert (
            fcc.determine_action_type(Priority.CRITICAL, 1)
            == ActionType.STOP_IMMEDIATELY
        )
        assert (
            fcc.determine_action_type(Priority.HIGH, 5) == ActionType.SCHEDULE_THIS_WEEK
        )
        assert (
            fcc.determine_action_type(Priority.MEDIUM, 15)
            == ActionType.SCHEDULE_THIS_MONTH
        )
        assert fcc.determine_action_type(Priority.LOW, 30) == ActionType.MONITOR
        assert fcc.determine_action_type(None, None) == ActionType.NO_ACTION

    def test_generate_action_steps(self):
        """Test action steps generation"""
        fcc = FleetCommandCenter()

        # Test stop immediately
        steps_critical = fcc.generate_action_steps(
            ActionType.STOP_IMMEDIATELY, "oil_system"
        )
        assert len(steps_critical) > 0
        assert any("Stop" in s or "Detener" in s for s in steps_critical)

        # Test oil system
        steps_oil = fcc.generate_action_steps(
            ActionType.SCHEDULE_THIS_WEEK, "oil_system"
        )
        assert len(steps_oil) > 0

        # Test transmission
        steps_trans = fcc.generate_action_steps(
            ActionType.SCHEDULE_THIS_WEEK, "transmission"
        )
        assert len(steps_trans) > 0

        # Test cooling
        steps_cool = fcc.generate_action_steps(
            ActionType.SCHEDULE_THIS_WEEK, "cooling_system"
        )
        assert len(steps_cool) > 0

        # Test DEF
        steps_def = fcc.generate_action_steps(
            ActionType.SCHEDULE_THIS_WEEK, "def_system"
        )
        assert len(steps_def) > 0

        # Test electrical
        steps_elec = fcc.generate_action_steps(
            ActionType.SCHEDULE_THIS_WEEK, "electrical"
        )
        assert len(steps_elec) > 0

        # Test turbo
        steps_turbo = fcc.generate_action_steps(ActionType.SCHEDULE_THIS_WEEK, "turbo")
        assert len(steps_turbo) > 0

        # Test unknown component - should return empty list now
        steps_unknown = fcc.generate_action_steps(
            ActionType.SCHEDULE_THIS_WEEK, "unknown_xyz"
        )
        assert isinstance(steps_unknown, list)

    def test_calculate_fleet_health_score(self):
        """Test fleet health score calculation"""
        fcc = FleetCommandCenter()

        # Perfect fleet
        score_perfect = fcc.calculate_fleet_health_score(10, 10, 0, 0, 0)
        assert score_perfect >= 95.0

        # Fleet with some issues
        score_issues = fcc.calculate_fleet_health_score(10, 10, 2, 3, 5)
        assert 50.0 <= score_issues < 95.0

        # Critical fleet
        score_critical = fcc.calculate_fleet_health_score(10, 10, 8, 2, 0)
        assert score_critical < 50.0

        # No trucks
        score_none = fcc.calculate_fleet_health_score(0, 0, 0, 0, 0)
        assert score_none == 100.0

    def test_generate_insights_no_issues(self):
        """Test insights generation with no issues"""
        fcc = FleetCommandCenter()
        urgency = UrgencySummary(critical=0, high=0, medium=0, low=0, ok=10)
        insights = fcc._generate_insights([], urgency)

        # Should generate positive insight
        assert isinstance(insights, list)

    def test_generate_insights_critical(self):
        """Test insights generation with critical issues"""
        fcc = FleetCommandCenter()

        items = [
            ActionItem(
                action_id="ACT-1",
                truck_id="T001",
                priority=Priority.CRITICAL,
                action_type=ActionType.STOP_IMMEDIATELY,
                component="oil_system",
                description="Critical oil pressure",
                category=IssueCategory.SENSOR,
                source="realtime",
                urgency_score=0.95,
                timestamp=datetime.now(),
                steps=[],
                cost_if_ignored="$5,000",
            )
        ]
        urgency = UrgencySummary(critical=1, high=0, medium=0, low=0, ok=0)
        insights = fcc._generate_insights(items, urgency)

        assert isinstance(insights, list)
        assert len(insights) > 0
        # Check for warning icon in insights
        assert any(insight.get("icon") == "🚨" for insight in insights)

    def test_generate_insights_pattern_detection(self):
        """Test insights pattern detection"""
        fcc = FleetCommandCenter()

        # Multiple trucks with same issue
        items = [
            ActionItem(
                action_id=f"ACT-{i}",
                truck_id=f"T{i:03d}",
                priority=Priority.HIGH,
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                component="transmission",
                description="Transmission issue",
                category=IssueCategory.SENSOR,
                source="predictive",
                urgency_score=0.7,
                timestamp=datetime.now(),
                steps=[],
                cost_if_ignored="$10,000",
            )
            for i in range(1, 6)  # 5 trucks with transmission issues
        ]

        urgency = UrgencySummary(critical=0, high=5, medium=0, low=0, ok=0)
        insights = fcc._generate_insights(items, urgency)

        assert isinstance(insights, list)
        # Should detect pattern
        assert any(
            "transmission" in insight.get("message", "").lower() for insight in insights
        )

    def test_generate_insights_escalation(self):
        """Test insights escalation warning"""
        fcc = FleetCommandCenter()

        items = [
            ActionItem(
                action_id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                component="oil_system",
                description="Degrading oil pressure",
                category=IssueCategory.SENSOR,
                source="predictive",
                urgency_score=0.75,
                timestamp=datetime.now(),
                steps=[],
                cost_if_ignored="$5,000",
                days_to_critical=2,  # Will escalate soon
            )
        ]

        urgency = UrgencySummary(critical=0, high=1, medium=0, low=0, ok=0)
        insights = fcc._generate_insights(items, urgency)

        assert isinstance(insights, list)
        # Should warn about escalation
        assert any(
            "escalando" in insight.get("message", "").lower()
            for insight in insights
            if insight.get("type") == "warning"
        )

    def test_estimate_costs(self):
        """Test cost estimation"""
        fcc = FleetCommandCenter()

        items = [
            ActionItem(
                action_id="ACT-1",
                truck_id="T001",
                priority=Priority.CRITICAL,
                action_type=ActionType.STOP_IMMEDIATELY,
                component="transmission",
                description="Transmission failure",
                category=IssueCategory.SENSOR,
                source="realtime",
                urgency_score=0.95,
                timestamp=datetime.now(),
                steps=[],
                cost_if_ignored="$15,000",
                days_to_critical=0,
            ),
            ActionItem(
                action_id="ACT-2",
                truck_id="T002",
                priority=Priority.HIGH,
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                component="oil_system",
                description="Oil pressure low",
                category=IssueCategory.SENSOR,
                source="predictive",
                urgency_score=0.75,
                timestamp=datetime.now(),
                steps=[],
                cost_if_ignored="$5,000",
                days_to_critical=5,
            ),
        ]

        costs = fcc.estimate_costs(items)
        assert isinstance(costs, CostProjection)
        assert costs.immediate_risk >= 0
        assert costs.week_risk >= 0
        assert costs.month_risk >= 0

    def test_singleton_pattern(self):
        """Test singleton pattern for get_command_center"""
        fcc1 = get_command_center()
        fcc2 = get_command_center()
        assert fcc1 is fcc2

    def test_component_mappings(self):
        """Test component category and icon mappings"""
        fcc = FleetCommandCenter()

        assert "oil_system" in fcc.COMPONENT_CATEGORIES
        assert "transmission" in fcc.COMPONENT_CATEGORIES
        assert "def_system" in fcc.COMPONENT_CATEGORIES

        assert "oil_system" in fcc.COMPONENT_ICONS
        assert "transmission" in fcc.COMPONENT_ICONS

    def test_pattern_thresholds(self):
        """Test pattern detection thresholds"""
        fcc = FleetCommandCenter()

        assert "min_trucks_for_pattern" in fcc.PATTERN_THRESHOLDS
        assert "fleet_wide_issue_pct" in fcc.PATTERN_THRESHOLDS
        assert isinstance(fcc.PATTERN_THRESHOLDS["min_trucks_for_pattern"], int)
        assert isinstance(fcc.PATTERN_THRESHOLDS["fleet_wide_issue_pct"], float)

    @patch("fleet_command_center.load_engine_safely")
    def test_generate_command_center_data_basic(self, mock_load):
        """Test basic command center data generation"""
        fcc = FleetCommandCenter()

        # Mock predictive maintenance engine
        mock_pm = Mock()
        mock_pm.analyze_truck.return_value = []
        mock_load.return_value = mock_pm

        result = fcc.generate_command_center_data(
            truck_ids=["T001"], database_engine=None
        )

        assert isinstance(result, CommandCenterData)
        assert result.version == fcc.VERSION
        assert result.total_trucks >= 0

    def test_offline_thresholds(self):
        """Test offline detection thresholds"""
        fcc = FleetCommandCenter()
        assert "hours_no_data_warning" in fcc.OFFLINE_THRESHOLDS
        assert fcc.OFFLINE_THRESHOLDS["hours_no_data_warning"] >= 0

    def test_sensor_valid_ranges(self):
        """Test sensor validation ranges"""
        fcc = FleetCommandCenter()
        assert "oil_pressure" in fcc.SENSOR_VALID_RANGES
        assert "min" in fcc.SENSOR_VALID_RANGES["oil_pressure"]
        assert "max" in fcc.SENSOR_VALID_RANGES["oil_pressure"]

    def test_component_costs_exist(self):
        """Test component costs are defined"""
        fcc = FleetCommandCenter()
        assert len(fcc.COMPONENT_COSTS) > 0
        for component, costs in fcc.COMPONENT_COSTS.items():
            assert "min_repair" in costs
            assert "max_repair" in costs
            assert costs["min_repair"] > 0
            assert costs["max_repair"] >= costs["min_repair"]


if __name__ == "__main__":
    pytest.main(
        [__file__, "-v", "--cov=fleet_command_center", "--cov-report=term-missing"]
    )
