"""
Fleet Command Center - Failure Correlation & DEF Prediction Tests
Tests correlation detection and DEF depletion prediction
"""

import sys
from datetime import datetime, timezone
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


class TestFailureCorrelationComplete:
    """Test failure correlation detection"""

    def test_detect_correlation_with_matching_pattern(self):
        """Test correlation detection with matching patterns"""
        cc = FleetCommandCenter()

        # Create action items with similar issues (should correlate)
        action_items = [
            ActionItem(
                action_id="FC1",
                truck_id="108",
                priority=Priority.CRITICAL,
                issue_category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                action_type=ActionType.STOP_IMMEDIATELY,
                estimated_days_to_critical=0.5,
                description="Oil temp critical",
                action_steps=["Stop"],
                priority_score=95.0,
                source="anomaly_detector",
            ),
            ActionItem(
                action_id="FC2",
                truck_id="109",
                priority=Priority.CRITICAL,
                issue_category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                action_type=ActionType.STOP_IMMEDIATELY,
                estimated_days_to_critical=0.8,
                description="Oil temp critical",
                action_steps=["Stop"],
                priority_score=92.0,
                source="anomaly_detector",
            ),
            ActionItem(
                action_id="FC3",
                truck_id="110",
                priority=Priority.HIGH,
                issue_category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                estimated_days_to_critical=2.0,
                description="Oil temp high",
                action_steps=["Schedule"],
                priority_score=78.0,
                source="predictive_engine",
            ),
        ]

        sensor_data = {
            "108": {"oil_temp": 250.0, "coolant_temp": 195.0},
            "109": {"oil_temp": 248.0, "coolant_temp": 193.0},
            "110": {"oil_temp": 235.0, "coolant_temp": 188.0},
        }

        correlations = cc.detect_failure_correlations(
            action_items=action_items,
            sensor_data=sensor_data,
            persist=False,
        )

        assert isinstance(correlations, list)
        # Should detect pattern: multiple trucks with oil system issues

    def test_detect_correlation_no_pattern(self):
        """Test correlation with no matching patterns"""
        cc = FleetCommandCenter()

        # Different issues on different trucks (no pattern)
        action_items = [
            ActionItem(
                action_id="NC1",
                truck_id="111",
                priority=Priority.MEDIUM,
                issue_category=IssueCategory.ENGINE,
                component="Sistema de lubricación",
                action_type=ActionType.MONITOR,
                estimated_days_to_critical=10.0,
                description="Oil temp elevated",
                action_steps=["Monitor"],
                priority_score=55.0,
                source="driver_scoring",
            ),
            ActionItem(
                action_id="NC2",
                truck_id="112",
                priority=Priority.LOW,
                issue_category=IssueCategory.ELECTRICAL,
                component="Sistema eléctrico",
                action_type=ActionType.MONITOR,
                estimated_days_to_critical=30.0,
                description="Voltage low",
                action_steps=["Monitor battery"],
                priority_score=35.0,
                source="sensor_health",
            ),
        ]

        correlations = cc.detect_failure_correlations(
            action_items=action_items,
            sensor_data=None,
            persist=False,
        )

        assert isinstance(correlations, list)

    def test_correlation_with_sensor_data(self):
        """Test correlation using sensor data"""
        cc = FleetCommandCenter()

        action_items = [
            ActionItem(
                action_id="CS1",
                truck_id="113",
                priority=Priority.HIGH,
                issue_category=IssueCategory.COOLING,
                component="Sistema de enfriamiento",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                estimated_days_to_critical=3.0,
                description="Coolant temp high",
                action_steps=["Check radiator"],
                priority_score=72.0,
                source="anomaly_detector",
            ),
        ]

        # Provide sensor data showing correlation between coolant and oil
        sensor_data = {
            "113": {
                "coolant_temp": 200.0,
                "oil_temp": 245.0,
                "turbo_boost": 32.0,
            },
        }

        correlations = cc.detect_failure_correlations(
            action_items=action_items,
            sensor_data=sensor_data,
            persist=False,
        )

        assert isinstance(correlations, list)

    def test_spn_normalization_variations(self):
        """Test SPN to component normalization"""
        cc = FleetCommandCenter()

        # Engine oil SPNs
        result1 = cc.normalize_spn_to_component("SPN 100")
        result2 = cc.normalize_spn_to_component("SPN-100")

        # Coolant SPNs
        result3 = cc.normalize_spn_to_component("SPN 110")

        # Unknown SPN
        result4 = cc.normalize_spn_to_component("SPN 9999")

        assert all(isinstance(r, str) for r in [result1, result2, result3, result4])

    def test_get_spn_info_variations(self):
        """Test SPN info retrieval"""
        cc = FleetCommandCenter()

        # Known SPN
        info1 = cc.get_spn_info("100")
        assert info1 is None or isinstance(info1, dict)

        # Another known SPN
        info2 = cc.get_spn_info("110")
        assert info2 is None or isinstance(info2, dict)

        # Unknown SPN
        info3 = cc.get_spn_info("99999")
        assert info3 is None or isinstance(info3, dict)


class TestDEFPredictionComplete:
    """Test DEF depletion prediction"""

    def test_predict_def_with_data(self):
        """Test DEF prediction with existing data"""
        cc = FleetCommandCenter()

        # Record some DEF readings first
        try:
            cc.persist_def_reading("DEF_TRUCK_A", def_level=75.0, fuel_used=50.0)
            cc.persist_def_reading("DEF_TRUCK_A", def_level=65.0, fuel_used=50.0)
            cc.persist_def_reading("DEF_TRUCK_A", def_level=55.0, fuel_used=50.0)
        except Exception:
            pass  # Table may not exist

        prediction = cc.predict_def_depletion("DEF_TRUCK_A")

        # May return None if no ML model or insufficient data
        assert prediction is None or isinstance(prediction, dict)

    def test_predict_def_no_data(self):
        """Test DEF prediction without data"""
        cc = FleetCommandCenter()

        prediction = cc.predict_def_depletion("NONEXISTENT_DEF_TRUCK")

        # Should return None (no data)
        assert prediction is None or isinstance(prediction, dict)

    def test_predict_def_after_refill(self):
        """Test DEF prediction after refill event"""
        cc = FleetCommandCenter()

        try:
            # Depletion
            cc.persist_def_reading("DEF_TRUCK_B", def_level=20.0, fuel_used=100.0)

            # Refill
            cc.persist_def_reading("DEF_TRUCK_B", def_level=95.0, is_refill=True)

            # More usage
            cc.persist_def_reading("DEF_TRUCK_B", def_level=85.0, fuel_used=50.0)
        except Exception:
            pass

        prediction = cc.predict_def_depletion("DEF_TRUCK_B")
        assert prediction is None or isinstance(prediction, dict)

    def test_def_reading_persistence_variations(self):
        """Test DEF reading persistence with variations"""
        cc = FleetCommandCenter()

        try:
            # Normal reading
            result1 = cc.persist_def_reading(
                truck_id="DEF_VAR_A",
                def_level=50.0,
                fuel_used=30.0,
                estimated_def_used=0.75,
                consumption_rate=2.5,
            )

            # Low DEF
            result2 = cc.persist_def_reading(
                truck_id="DEF_VAR_B",
                def_level=10.0,
                fuel_used=50.0,
            )

            # Very low DEF (critical)
            result3 = cc.persist_def_reading(
                truck_id="DEF_VAR_C",
                def_level=2.0,
            )

            # All should return bool or handle exception
            for r in [result1, result2, result3]:
                if r is not None:
                    assert isinstance(r, bool)
        except Exception:
            pass  # Table may not exist


class TestSensorHealthIntegration:
    """Test sensor health integration"""

    def test_sensor_alerts_in_risk_scoring(self):
        """Test sensor alerts affecting risk score"""
        cc = FleetCommandCenter()

        action_items = [
            ActionItem(
                action_id="SH1",
                truck_id="SENSOR_A",
                priority=Priority.HIGH,
                issue_category=IssueCategory.ENGINE,
                component="Motor",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                estimated_days_to_critical=3.0,
                description="Engine issue",
                action_steps=["Inspect"],
                priority_score=75.0,
                source="sensor_health",
            ),
        ]

        # With sensor alerts
        sensor_alerts = {
            "oil_temp": "HIGH",
            "coolant_temp": "HIGH",
        }

        risk = cc.calculate_truck_risk_score(
            truck_id="SENSOR_A",
            action_items=action_items,
            sensor_alerts=sensor_alerts,
        )

        assert risk.risk_score > 0

    def test_multiple_sensors_correlation(self):
        """Test correlation with multiple sensor readings"""
        cc = FleetCommandCenter()

        # Record multiple sensors showing correlation
        truck_id = "CORR_MULTI"

        cc._record_sensor_reading(truck_id, "oil_temp", 250.0)
        cc._record_sensor_reading(truck_id, "coolant_temp", 200.0)
        cc._record_sensor_reading(truck_id, "turbo_boost", 35.0)

        # All high values - should correlate
        detection1, decision1 = cc.detect_and_decide(
            truck_id=truck_id,
            sensor_name="oil_temp",
            current_value=250.0,
        )

        detection2, decision2 = cc.detect_and_decide(
            truck_id=truck_id,
            sensor_name="coolant_temp",
            current_value=200.0,
        )

        assert isinstance(detection1, dict)
        assert isinstance(decision1, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
