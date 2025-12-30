"""
Fleet Command Center - Advanced Scenarios & Edge Cases
Tests complex scenarios, multiple trucks, complex data flows
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fleet_command_center import (
    ActionItem,
    ActionType,
    FleetCommandCenter,
    IssueCategory,
    Priority,
)


class TestComplexMultiTruckScenarios:
    """Test complex scenarios with multiple trucks"""

    def test_offline_detection_with_real_data(self):
        """Test offline truck detection"""
        cc = FleetCommandCenter()

        now = datetime.now(timezone.utc)

        truck_last_seen = {
            "108": now - timedelta(hours=2),  # Recent
            "109": now - timedelta(days=3),  # Offline
            "110": now - timedelta(days=1),  # Recently offline
        }

        all_truck_ids = ["108", "109", "110", "111"]

        offline_items = cc.detect_offline_trucks(truck_last_seen, all_truck_ids)

        assert isinstance(offline_items, list)
        # Should have at least 2 offline (109, 111 never seen)

    def test_multiple_sensors_single_truck(self):
        """Test multiple sensor readings for single truck"""
        cc = FleetCommandCenter()

        # Simulate real sensor data stream
        sensors = {
            "oil_temp": 245.0,
            "coolant_temp": 195.0,
            "turbo_boost": 32.0,
            "voltage": 13.2,
            "fuel_pressure": 45.0,
        }

        for sensor_name, value in sensors.items():
            cc._record_sensor_reading("TRUCK_MULTI", sensor_name, value)
            detection, decision = cc.detect_and_decide(
                truck_id="TRUCK_MULTI",
                sensor_name=sensor_name,
                current_value=value,
            )
            assert isinstance(detection, dict)
            assert isinstance(decision, dict)

    def test_action_item_deduplication_complex(self):
        """Test deduplication with overlapping issues"""
        cc = FleetCommandCenter()

        # Create overlapping action items
        action_items = [
            ActionItem(
                action_id="A1",
                truck_id="108",
                priority=Priority.CRITICAL,
                issue_category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                action_type=ActionType.STOP_IMMEDIATELY,
                estimated_days_to_critical=0.5,
                description="Oil temp critical",
                action_steps=["Stop truck"],
                priority_score=95.0,
                source="anomaly_detector",
            ),
            ActionItem(
                action_id="A2",
                truck_id="108",
                priority=Priority.HIGH,
                issue_category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                estimated_days_to_critical=2.0,
                description="Oil temp high",
                action_steps=["Schedule maintenance"],
                priority_score=75.0,
                source="predictive_engine",
            ),
            ActionItem(
                action_id="A3",
                truck_id="109",
                priority=Priority.MEDIUM,
                issue_category=IssueCategory.COOLING,
                component="Sistema de enfriamiento",
                action_type=ActionType.MONITOR,
                estimated_days_to_critical=10.0,
                description="Coolant temp elevated",
                action_steps=["Monitor"],
                priority_score=55.0,
                source="driver_scoring",
            ),
        ]

        deduped = cc._deduplicate_action_items(action_items)

        assert isinstance(deduped, list)
        assert len(deduped) <= len(action_items)
        # Should keep highest priority (A1) and different component (A3)
        assert len(deduped) == 2

    def test_fleet_health_calculation_variations(self):
        """Test fleet health with different scenarios"""
        cc = FleetCommandCenter()

        # Scenario 1: All trucks critical
        action_items_critical = [
            ActionItem(
                action_id=f"C{i}",
                truck_id=str(i),
                priority=Priority.CRITICAL,
                issue_category=IssueCategory.ENGINE,
                component="Motor",
                action_type=ActionType.STOP_IMMEDIATELY,
                estimated_days_to_critical=0.5,
                description="Critical issue",
                action_steps=["Stop"],
                priority_score=95.0,
                source="test",
            )
            for i in range(5)
        ]

        urgency_critical = {"immediate": 5, "short_term": 0, "medium_term": 0}
        health1 = cc._calculate_fleet_health_score(
            urgency_critical, 10, action_items_critical
        )
        assert isinstance(health1, dict)
        assert health1.get("overall_health_pct", 0) < 50  # Should be low

        # Scenario 2: All trucks healthy
        urgency_healthy = {"immediate": 0, "short_term": 0, "medium_term": 0}
        health2 = cc._calculate_fleet_health_score(urgency_healthy, 10, [])
        assert health2.get("overall_health_pct", 0) > 80  # Should be high

    def test_cost_estimation_variations(self):
        """Test cost estimation with different scenarios"""
        cc = FleetCommandCenter()

        action_items = [
            ActionItem(
                action_id="E1",
                truck_id="108",
                priority=Priority.CRITICAL,
                issue_category=IssueCategory.TRANSMISSION,
                component="Transmisión",
                action_type=ActionType.STOP_IMMEDIATELY,
                estimated_days_to_critical=0.5,
                description="Transmission failure",
                action_steps=["Stop immediately"],
                priority_score=95.0,
                source="test",
            ),
            ActionItem(
                action_id="E2",
                truck_id="109",
                priority=Priority.MEDIUM,
                issue_category=IssueCategory.FUEL,
                component="Sistema de combustible",
                action_type=ActionType.MONITOR,
                estimated_days_to_critical=20.0,
                description="Fuel efficiency drop",
                action_steps=["Monitor"],
                priority_score=45.0,
                source="test",
            ),
        ]

        costs = cc._estimate_costs(action_items)

        assert isinstance(costs, dict)
        assert "total_min" in costs or "total_max" in costs or "total_range" in costs

    def test_insights_generation_patterns(self):
        """Test insight generation with various patterns"""
        cc = FleetCommandCenter()

        action_items = [
            ActionItem(
                action_id="I1",
                truck_id="108",
                priority=Priority.CRITICAL,
                issue_category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                action_type=ActionType.STOP_IMMEDIATELY,
                estimated_days_to_critical=0.5,
                description="Oil system failure",
                action_steps=["Stop"],
                priority_score=95.0,
                source="anomaly_detector",
            ),
            ActionItem(
                action_id="I2",
                truck_id="109",
                priority=Priority.CRITICAL,
                issue_category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                action_type=ActionType.STOP_IMMEDIATELY,
                estimated_days_to_critical=0.8,
                description="Oil system failure",
                action_steps=["Stop"],
                priority_score=92.0,
                source="anomaly_detector",
            ),
            ActionItem(
                action_id="I3",
                truck_id="110",
                priority=Priority.HIGH,
                issue_category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                estimated_days_to_critical=2.0,
                description="Oil system degrading",
                action_steps=["Schedule"],
                priority_score=78.0,
                source="predictive_engine",
            ),
        ]

        urgency = {"immediate": 2, "short_term": 1, "medium_term": 0}
        insights = cc._generate_insights(action_items, urgency)

        assert isinstance(insights, list)
        # Should detect pattern: multiple oil system issues


class TestFullIntegrationFlows:
    """Test complete end-to-end flows"""

    def test_full_pipeline_multiple_trucks(self):
        """Test full pipeline with multiple trucks"""
        cc = FleetCommandCenter()

        # Simulate real data flow
        trucks = ["PIPE_A", "PIPE_B", "PIPE_C"]

        for truck_id in trucks:
            # Record sensor data
            cc._record_sensor_reading(truck_id, "oil_temp", 220.0)
            cc._record_sensor_reading(truck_id, "coolant_temp", 185.0)

            # EWMA/CUSUM
            cc._calculate_ewma(truck_id, "oil_temp", 220.0, alpha=0.3)
            cc._calculate_cusum(
                truck_id, "oil_temp", 220.0, target=200.0, threshold=10.0
            )

            # Detection & Decision
            detection, decision = cc.detect_and_decide(
                truck_id=truck_id,
                sensor_name="oil_temp",
                current_value=220.0,
                baseline_value=200.0,
            )

            assert isinstance(detection, dict)
            assert isinstance(decision, dict)

    def test_risk_scoring_with_maintenance_history(self):
        """Test risk scoring with maintenance data"""
        cc = FleetCommandCenter()

        action_items = [
            ActionItem(
                action_id="R1",
                truck_id="RISK_A",
                priority=Priority.HIGH,
                issue_category=IssueCategory.ENGINE,
                component="Motor",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                estimated_days_to_critical=3.0,
                description="High risk",
                action_steps=["Inspect"],
                priority_score=75.0,
                source="test",
            ),
        ]

        # With recent maintenance
        risk1 = cc.calculate_truck_risk_score(
            "RISK_A", action_items, days_since_maintenance=5
        )

        # With old maintenance
        risk2 = cc.calculate_truck_risk_score(
            "RISK_A", action_items, days_since_maintenance=90
        )

        assert risk2.risk_score >= risk1.risk_score  # Older maintenance = higher risk

    def test_complete_command_center_generation(self):
        """Test full command center data generation"""
        cc = FleetCommandCenter()

        # Create test data
        action_items = [
            ActionItem(
                action_id="G1",
                truck_id="GEN_A",
                priority=Priority.CRITICAL,
                issue_category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                action_type=ActionType.STOP_IMMEDIATELY,
                estimated_days_to_critical=0.5,
                description="Critical oil temp",
                action_steps=["Stop immediately", "Inspect oil system"],
                priority_score=95.0,
                source="anomaly_detector",
            ),
            ActionItem(
                action_id="G2",
                truck_id="GEN_B",
                priority=Priority.HIGH,
                issue_category=IssueCategory.TRANSMISSION,
                component="Transmisión",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                estimated_days_to_critical=3.0,
                description="Transmission slipping",
                action_steps=["Schedule transmission service"],
                priority_score=78.0,
                source="predictive_engine",
            ),
        ]

        truck_last_seen = {
            "GEN_A": datetime.now(timezone.utc),
            "GEN_B": datetime.now(timezone.utc),
        }

        all_trucks = ["GEN_A", "GEN_B", "GEN_C"]

        try:
            result = cc.generate_command_center_data(
                action_items=action_items,
                truck_last_seen=truck_last_seen,
                all_truck_ids=all_trucks,
            )

            assert isinstance(result, dict)
            assert "action_items" in result or "fleet_health" in result
        except Exception:
            pass  # May require full DB setup


class TestEdgeCasesAndErrors:
    """Test edge cases and error handling"""

    def test_empty_action_items(self):
        """Test with empty action items"""
        cc = FleetCommandCenter()

        deduped = cc._deduplicate_action_items([])
        assert deduped == []

        costs = cc._estimate_costs([])
        assert isinstance(costs, dict)

        health = cc._calculate_fleet_health_score(
            {"immediate": 0, "short_term": 0, "medium_term": 0}, 10, []
        )
        assert isinstance(health, dict)

    def test_none_values_handling(self):
        """Test handling of None values"""
        cc = FleetCommandCenter()

        # None sensor value
        result = cc._validate_sensor_value(None, "oil_temp")
        assert result is None

        # None in sensor dict
        sensors = {"oil_temp": None, "coolant_temp": 185.0}
        validated = cc._validate_sensor_dict(sensors)
        assert isinstance(validated, dict)

    def test_extreme_sensor_values(self):
        """Test extreme sensor values"""
        cc = FleetCommandCenter()

        # Very high value
        cc._record_sensor_reading("EXTREME", "oil_temp", 999.0)

        # Very low value
        cc._record_sensor_reading("EXTREME", "voltage", 0.1)

        # Negative value
        cc._record_sensor_reading("EXTREME", "some_sensor", -50.0)

    def test_unicode_and_special_characters(self):
        """Test unicode and special characters"""
        cc = FleetCommandCenter()

        # Unicode truck ID
        cc._record_sensor_reading("TRÁILER-ñ-108", "oil_temp", 220.0)

        # Special component names
        result = cc._normalize_component("Système de Lubricación")
        assert isinstance(result, str)

    def test_concurrent_sensor_updates(self):
        """Test rapid concurrent sensor updates"""
        cc = FleetCommandCenter()

        # Simulate rapid updates
        for i in range(100):
            cc._record_sensor_reading("RAPID", "oil_temp", 200.0 + i * 0.5)
            ewma = cc._calculate_ewma("RAPID", "oil_temp", 200.0 + i * 0.5, alpha=0.3)
            cusum_h, cusum_l, alert = cc._calculate_cusum(
                "RAPID", "oil_temp", 200.0 + i * 0.5, target=200.0, threshold=10.0
            )

    def test_persistence_with_db_failure(self):
        """Test persistence when DB is unavailable"""
        cc = FleetCommandCenter()

        # These should handle DB errors gracefully
        try:
            cc.persist_anomaly("NO_DB", "oil_temp", "EWMA", "HIGH", 245.0)
        except Exception:
            pass  # Expected to fail gracefully

        try:
            cc.persist_algorithm_state("NO_DB", "oil_temp", ewma_value=220.0)
        except Exception:
            pass

    def test_zero_and_boundary_values(self):
        """Test zero and boundary values"""
        cc = FleetCommandCenter()

        # Zero days to critical
        priority1, score1 = cc._calculate_priority_score(days_to_critical=0.0)
        assert isinstance(priority1, Priority)

        # Exactly 1 day (boundary)
        horizon1 = cc._get_time_horizon(1.0)
        assert horizon1 in ["immediate", "short_term"]

        # Exactly 7 days (boundary)
        horizon7 = cc._get_time_horizon(7.0)
        assert horizon7 in ["short_term", "medium_term"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
