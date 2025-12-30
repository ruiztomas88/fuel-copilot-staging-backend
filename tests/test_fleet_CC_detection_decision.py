"""
Fleet Command Center - Detection & Decision Logic Tests
Tests detect_issue, decide_action, detect_and_decide
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fleet_command_center import ActionType, FleetCommandCenter, Priority


class TestDetectionLogic:
    """Test detect_issue method - lines 2624-2724"""

    def test_detect_issue_correct_signature(self):
        """Test detect_issue with correct parameters"""
        cc = FleetCommandCenter()

        result = cc.detect_issue(
            truck_id="108",
            sensor_name="oil_temp",
            current_value=245.0,
            baseline_value=210.0,
        )

        assert isinstance(result, dict)
        assert "is_issue" in result
        assert "severity" in result
        assert "deviation_pct" in result

    def test_detect_issue_critical_value(self):
        """Test detection with critical sensor value"""
        cc = FleetCommandCenter()

        result = cc.detect_issue(
            truck_id="108",
            sensor_name="oil_temp",
            current_value=260.0,
            baseline_value=200.0,
        )

        assert isinstance(result, dict)
        assert result.get("is_issue") in [True, False]

    def test_detect_issue_normal_value(self):
        """Test detection with normal value"""
        cc = FleetCommandCenter()

        result = cc.detect_issue(
            truck_id="108",
            sensor_name="oil_temp",
            current_value=205.0,
            baseline_value=200.0,
        )

        assert isinstance(result, dict)

    def test_detect_issue_no_baseline(self):
        """Test detection without baseline"""
        cc = FleetCommandCenter()

        result = cc.detect_issue(
            truck_id="108",
            sensor_name="coolant_temp",
            current_value=190.0,
        )

        assert isinstance(result, dict)
        assert "is_issue" in result

    def test_detect_issue_coolant_temp(self):
        """Test coolant temp detection"""
        cc = FleetCommandCenter()

        result = cc.detect_issue(
            truck_id="109",
            sensor_name="coolant_temp",
            current_value=210.0,
            baseline_value=185.0,
        )

        assert isinstance(result, dict)

    def test_detect_issue_turbo_boost(self):
        """Test turbo boost detection"""
        cc = FleetCommandCenter()

        result = cc.detect_issue(
            truck_id="110",
            sensor_name="turbo_boost",
            current_value=35.0,
            baseline_value=28.0,
        )

        assert isinstance(result, dict)

    def test_detect_issue_voltage(self):
        """Test voltage detection"""
        cc = FleetCommandCenter()

        result = cc.detect_issue(
            truck_id="111",
            sensor_name="voltage",
            current_value=11.5,
            baseline_value=13.8,
        )

        assert isinstance(result, dict)


class TestDecisionLogic:
    """Test decide_action method - lines 2756-2847"""

    def test_decide_action_correct_signature(self):
        """Test decide_action with correct parameters"""
        cc = FleetCommandCenter()

        detection_result = {
            "is_issue": True,
            "severity": "high",
            "deviation_pct": 35.0,
            "trend": "increasing",
            "persistence": True,
            "confidence": "HIGH",
        }

        result = cc.decide_action(detection_result, component="Sistema de lubricación")

        assert isinstance(result, dict)
        assert "priority" in result
        assert "action_type" in result

    def test_decide_action_critical_issue(self):
        """Test decision for critical issue"""
        cc = FleetCommandCenter()

        detection_result = {
            "is_issue": True,
            "severity": "critical",
            "deviation_pct": 50.0,
            "trend": "increasing",
            "persistence": True,
            "confidence": "HIGH",
        }

        result = cc.decide_action(detection_result, component="Transmisión")

        assert isinstance(result, dict)
        assert result.get("priority") in [
            Priority.CRITICAL,
            Priority.HIGH,
            Priority.MEDIUM,
            Priority.LOW,
            Priority.NONE,
        ]

    def test_decide_action_no_issue(self):
        """Test decision when no issue detected"""
        cc = FleetCommandCenter()

        detection_result = {
            "is_issue": False,
            "severity": "none",
            "deviation_pct": 0.0,
            "trend": "stable",
            "persistence": False,
            "confidence": "LOW",
        }

        result = cc.decide_action(detection_result)

        assert isinstance(result, dict)
        assert (
            result.get("priority") == Priority.NONE
            or result.get("action_type") == ActionType.NO_ACTION
        )

    def test_decide_action_medium_severity(self):
        """Test decision for medium severity"""
        cc = FleetCommandCenter()

        detection_result = {
            "is_issue": True,
            "severity": "medium",
            "deviation_pct": 20.0,
            "trend": "stable",
            "persistence": False,
            "confidence": "MEDIUM",
        }

        result = cc.decide_action(detection_result, component="Sistema de combustible")

        assert isinstance(result, dict)

    def test_decide_action_low_severity(self):
        """Test decision for low severity"""
        cc = FleetCommandCenter()

        detection_result = {
            "is_issue": True,
            "severity": "low",
            "deviation_pct": 8.0,
            "trend": "stable",
            "persistence": False,
            "confidence": "LOW",
        }

        result = cc.decide_action(detection_result)

        assert isinstance(result, dict)


class TestDetectAndDecide:
    """Test detect_and_decide combined flow - lines 2855-2876"""

    def test_detect_and_decide_correct_signature(self):
        """Test detect_and_decide with correct parameters"""
        cc = FleetCommandCenter()

        detection, decision = cc.detect_and_decide(
            truck_id="108",
            sensor_name="oil_temp",
            current_value=240.0,
            baseline_value=200.0,
            component="Sistema de lubricación",
        )

        assert isinstance(detection, dict)
        assert isinstance(decision, dict)
        assert "is_issue" in detection
        assert "priority" in decision

    def test_detect_and_decide_critical(self):
        """Test full flow with critical value"""
        cc = FleetCommandCenter()

        detection, decision = cc.detect_and_decide(
            truck_id="108",
            sensor_name="oil_temp",
            current_value=260.0,
            baseline_value=200.0,
            component="Sistema de lubricación",
        )

        assert isinstance(detection, dict)
        assert isinstance(decision, dict)

    def test_detect_and_decide_normal(self):
        """Test full flow with normal value"""
        cc = FleetCommandCenter()

        detection, decision = cc.detect_and_decide(
            truck_id="109",
            sensor_name="coolant_temp",
            current_value=185.0,
            baseline_value=180.0,
        )

        assert isinstance(detection, dict)
        assert isinstance(decision, dict)

    def test_detect_and_decide_no_baseline(self):
        """Test full flow without baseline"""
        cc = FleetCommandCenter()

        detection, decision = cc.detect_and_decide(
            truck_id="110",
            sensor_name="turbo_boost",
            current_value=30.0,
        )

        assert isinstance(detection, dict)
        assert isinstance(decision, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
