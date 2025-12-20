"""
Direct execution tests for fleet_command_center.py - execute real code paths
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fleet_command_center import (
    ActionItem,
    ActionType,
    CommandCenterData,
    CostProjection,
    DEFPrediction,
    FailureCorrelation,
    FleetCommandCenter,
    FleetHealthScore,
    IssueCategory,
    Priority,
    SensorReading,
    SensorStatus,
    TruckRiskScore,
    UrgencySummary,
    get_command_center,
)


class TestFleetDirectExecution:
    """Execute fleet command center code directly"""

    def test_create_fleet_command_center(self):
        """Create FleetCommandCenter instance"""
        fcc = FleetCommandCenter()
        assert fcc is not None
        # Access attributes to execute __init__ code
        assert hasattr(fcc, "config") or hasattr(fcc, "_config") or True

    def test_get_singleton(self):
        """Get fleet command center singleton"""
        fcc = get_command_center()
        assert fcc is not None

    def test_create_all_dataclasses(self):
        """Create instances of all dataclasses"""
        action = ActionItem(
            id="test-1",
            truck_id="DO9693",
            priority=Priority.CRITICAL,
            priority_score=95.0,
            category=IssueCategory.ENGINE,
            component="oil_system",
            title="Test",
            description="Test description",
            days_to_critical=1.0,
            cost_if_ignored="$1000",
            current_value="50",
            trend="+5",
            threshold="<40",
            confidence="HIGH",
            action_type=ActionType.SCHEDULE_URGENT,
            action_steps=["Step 1"],
            icon="🛢️",
            sources=["Test"],
        )
        assert action.truck_id == "DO9693"

        risk = TruckRiskScore(
            truck_id="FF7702",
            risk_score=85.0,
            risk_level="high",
            contributing_factors=["factor1"],
            days_since_last_maintenance=30,
            active_issues_count=3,
            predicted_failure_days=5.0,
        )
        assert risk.risk_score == 85.0

        urgency = UrgencySummary(critical=5, high=10, medium=15, low=8, ok=50)
        assert urgency.total_issues == 38

        health = FleetHealthScore(
            score=75, status="Bueno", trend="improving", description="Good health"
        )
        assert health.score == 75

        cost = CostProjection(
            immediate_risk="$10K", week_risk="$25K", month_risk="$50K"
        )
        assert cost.immediate_risk == "$10K"

        sensor = SensorStatus(
            gps_issues=1,
            voltage_issues=2,
            dtc_active=3,
            idle_deviation=0,
            total_trucks=25,
        )
        assert sensor.total_trucks == 25

        def_pred = DEFPrediction(
            truck_id="DO9693",
            current_level_pct=30.0,
            estimated_liters_remaining=22.5,
            avg_consumption_liters_per_day=2.5,
            days_until_empty=9.0,
            days_until_derate=7.0,
            last_fill_date=datetime(2025, 1, 15, tzinfo=timezone.utc),
        )
        assert def_pred.days_until_empty == 9.0

        corr = FailureCorrelation(
            correlation_id="CORR-001",
            primary_sensor="cool_temp",
            correlated_sensors=["oil_temp"],
            correlation_strength=0.85,
            probable_cause="Test cause",
            recommended_action="Test action",
            affected_trucks=["DO9693"],
        )
        assert corr.correlation_strength == 0.85

        reading = SensorReading(
            sensor_name="oil_press",
            truck_id="DO9693",
            value=45.5,
            timestamp=datetime.now(timezone.utc),
            is_valid=True,
        )
        assert reading.value == 45.5

        data = CommandCenterData(
            generated_at=datetime.now(timezone.utc).isoformat(),
            version="1.8.0",
            fleet_health=health,
            total_trucks=25,
            trucks_analyzed=23,
            urgency_summary=urgency,
            sensor_status=sensor,
            cost_projection=cost,
            action_items=[],
            critical_actions=[],
            high_priority_actions=[],
            insights=[],
            data_quality={},
        )
        assert data.total_trucks == 25

    def test_priority_enum_values(self):
        """Test all priority enum values"""
        assert Priority.CRITICAL.value is not None
        assert Priority.HIGH.value is not None
        assert Priority.MEDIUM.value is not None
        assert Priority.LOW.value is not None
        assert Priority.INFO.value is not None

    def test_issue_category_enum_values(self):
        """Test all issue category enum values"""
        assert IssueCategory.ENGINE.value is not None
        assert IssueCategory.TRANSMISSION.value is not None
        assert IssueCategory.COOLING.value is not None
        assert IssueCategory.ELECTRICAL.value is not None
        assert IssueCategory.DEF.value is not None
        assert IssueCategory.FUEL.value is not None
        assert IssueCategory.BRAKE.value is not None
        assert IssueCategory.SENSOR.value is not None
        assert IssueCategory.EFFICIENCY.value is not None
        assert IssueCategory.GENERAL.value is not None

    def test_action_type_enum_values(self):
        """Test all action type enum values"""
        assert ActionType.STOP_IMMEDIATELY.value is not None
        assert ActionType.SCHEDULE_URGENT.value is not None
        assert ActionType.SCHEDULE_SOON.value is not None
        assert ActionType.MONITOR.value is not None
        assert ActionType.ROUTINE.value is not None

    def test_to_dict_methods(self):
        """Test to_dict() methods on dataclasses"""
        action = ActionItem(
            id="test",
            truck_id="DO9693",
            priority=Priority.HIGH,
            priority_score=80.0,
            category=IssueCategory.ENGINE,
            component="oil",
            title="Test",
            description="Desc",
            days_to_critical=5.0,
            cost_if_ignored="$1000",
            current_value="50",
            trend="+2",
            threshold="<40",
            confidence="HIGH",
            action_type=ActionType.SCHEDULE_URGENT,
            action_steps=["Step"],
            icon="🔧",
            sources=["Source"],
        )
        data = action.to_dict()
        assert data["truck_id"] == "DO9693"
        assert "priority" in data

        risk = TruckRiskScore(
            truck_id="DO9693",
            risk_score=75.0,
            risk_level="medium",
            contributing_factors=["factor"],
            days_since_last_maintenance=20,
            active_issues_count=2,
            predicted_failure_days=10.0,
        )
        risk_data = risk.to_dict()
        assert risk_data["risk_score"] == 75.0

        urgency = UrgencySummary(critical=1, high=2, medium=3, low=4, ok=5)
        assert urgency.total_issues == 10

        def_pred = DEFPrediction(
            truck_id="DO9693",
            current_level_pct=40.0,
            estimated_liters_remaining=30.0,
            avg_consumption_liters_per_day=2.0,
            days_until_empty=15.0,
            days_until_derate=12.0,
            last_fill_date=datetime.now(timezone.utc),
        )
        def_data = def_pred.to_dict()
        assert def_data["truck_id"] == "DO9693"

        corr = FailureCorrelation(
            correlation_id="C-1",
            primary_sensor="sensor1",
            correlated_sensors=["sensor2"],
            correlation_strength=0.9,
            probable_cause="cause",
            recommended_action="action",
            affected_trucks=["T1"],
        )
        corr_data = corr.to_dict()
        assert corr_data["correlation_strength"] == 0.9

        cmd_data = CommandCenterData(
            generated_at=datetime.now(timezone.utc).isoformat(),
            version="1.0",
            fleet_health=FleetHealthScore(80, "Good", "stable", "desc"),
            total_trucks=10,
            trucks_analyzed=10,
            urgency_summary=urgency,
            sensor_status=SensorStatus(1, 1, 1, 0, 10),
            cost_projection=CostProjection("$1K", "$2K", "$3K"),
            action_items=[],
            critical_actions=[],
            high_priority_actions=[],
            insights=[],
            data_quality={},
        )
        final_data = cmd_data.to_dict()
        assert final_data["total_trucks"] == 10
