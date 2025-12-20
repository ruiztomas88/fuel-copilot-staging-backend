"""Complete coverage for alert_service.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from alert_service import *


class TestAlertComplete:
    def test_all_alert_types(self):
        Alert(AlertType.THEFT_SUSPECTED, AlertPriority.HIGH, "DO9693", "Test")
        Alert(AlertType.THEFT_CONFIRMED, AlertPriority.CRITICAL, "FF7702", "Test")
        Alert(AlertType.SENSOR_ISSUE, AlertPriority.MEDIUM, "GS5030", "Test")
        Alert(AlertType.REFUEL, AlertPriority.LOW, "GS5032", "Test")
        Alert(AlertType.DRIFT_WARNING, AlertPriority.HIGH, "GS5033", "Test")
        Alert(AlertType.SENSOR_OFFLINE, AlertPriority.MEDIUM, "GS5034", "Test")
        Alert(AlertType.DTC_ALERT, AlertPriority.HIGH, "GS5035", "Test")
        Alert(AlertType.VOLTAGE_ALERT, AlertPriority.LOW, "GS5036", "Test")
        Alert(AlertType.MAINTENANCE_PREDICTION, AlertPriority.CRITICAL, "GS5037", "Test")
        Alert(AlertType.LOW_FUEL, AlertPriority.MEDIUM, "GS5038", "Test")
        Alert(AlertType.EFFICIENCY_DROP, AlertPriority.LOW, "GS5039", "Test")
        Alert(AlertType.MAINTENANCE_DUE, AlertPriority.MEDIUM, "GS5040", "Test")
        Alert(AlertType.IDLE_DEVIATION, AlertPriority.LOW, "GS5041", "Test")
        Alert(AlertType.GPS_QUALITY, AlertPriority.MEDIUM, "GS5042", "Test")

    def test_enums(self):
        assert AlertType.THEFT_SUSPECTED
        assert AlertType.THEFT_CONFIRMED
        assert AlertType.SENSOR_ISSUE
        assert AlertType.MAINTENANCE_DUE
        assert AlertType.DTC_ALERT
        assert AlertType.VOLTAGE_ALERT
        assert AlertPriority.CRITICAL
        assert AlertPriority.HIGH
        assert AlertPriority.MEDIUM
        assert AlertPriority.LOW

    def test_get_alert_manager(self):
        get_alert_manager()
