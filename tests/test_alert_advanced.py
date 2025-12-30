"""
Tests for remaining AlertManager convenience methods - final push to 100%
"""

from unittest.mock import Mock

import pytest

from alert_service import AlertManager, AlertPriority, AlertType


class TestAlertManagerAdvancedMethods:
    """Test advanced alert methods (DTC, Voltage, Idle, Maintenance, GPS)"""

    def test_alert_dtc_critical_with_full_details(self):
        """Test DTC alert with CRITICAL severity and full Spanish details"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_dtc(
            truck_id="TRUCK_001",
            dtc_code="P0420",
            spn="639",
            fmi="2",
            severity="CRITICAL",
            system="AFTERTREATMENT",
            description="Catalyst System Efficiency Below Threshold",
            spn_name_es="Sistema Catalizador",
            fmi_description_es="Eficiencia por debajo del umbral",
            recommended_action="Reemplazar catalizador inmediatamente",
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.alert_type == AlertType.DTC_ALERT
        assert alert.priority == AlertPriority.CRITICAL
        channels = call_args[1]["channels"]
        assert "sms" in channels
        assert "email" in channels

    def test_alert_dtc_warning_without_spanish(self):
        """Test DTC alert with WARNING severity without Spanish details"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_dtc(
            truck_id="TRUCK_002",
            dtc_code="P0101",
            severity="WARNING",
            system="ENGINE",
            description="Mass Air Flow Circuit Range/Performance",
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.priority == AlertPriority.HIGH
        channels = call_args[1]["channels"]
        assert "email" in channels
        assert "sms" not in channels

    def test_alert_voltage_critical_engine_running(self):
        """Test voltage alert CRITICAL priority with engine running"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_voltage(
            truck_id="TRUCK_003",
            voltage=10.5,
            priority_level="CRITICAL",
            message="Voltage critically low - alternator failure suspected",
            is_engine_running=True,
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.alert_type == AlertType.VOLTAGE_ALERT
        assert alert.priority == AlertPriority.CRITICAL
        assert "10.5V" in alert.details["voltage"]
        assert "Running" in alert.details["engine_status"]

    def test_alert_voltage_warning_engine_off(self):
        """Test voltage alert WARNING priority with engine off"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_voltage(
            truck_id="TRUCK_004",
            voltage=11.8,
            priority_level="WARNING",
            message="Battery voltage low",
            is_engine_running=False,
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.priority == AlertPriority.HIGH
        assert "Off" in alert.details["engine_status"]

    def test_alert_idle_deviation_high_deviation(self):
        """Test idle deviation alert with > 25% deviation"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_idle_deviation(
            truck_id="TRUCK_005",
            calculated_hours=150.5,
            ecu_hours=190.0,
            deviation_pct=-26.2,
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.alert_type == AlertType.IDLE_DEVIATION
        assert alert.priority == AlertPriority.HIGH

    def test_alert_idle_deviation_medium_deviation(self):
        """Test idle deviation alert with < 25% deviation"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_idle_deviation(
            truck_id="TRUCK_006",
            calculated_hours=100.0,
            ecu_hours=115.0,
            deviation_pct=-15.0,
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.priority == AlertPriority.MEDIUM

    def test_alert_maintenance_prediction_critical_urgency(self):
        """Test maintenance prediction alert with CRITICAL urgency"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_maintenance_prediction(
            truck_id="TRUCK_007",
            sensor="battery_voltage",
            current_value=11.2,
            threshold=10.5,
            days_to_failure=2.5,
            urgency="CRITICAL",
            unit="V",
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.alert_type == AlertType.MAINTENANCE_PREDICTION
        assert alert.priority == AlertPriority.CRITICAL
        channels = call_args[1]["channels"]
        assert "sms" in channels

    def test_alert_maintenance_prediction_high_urgency(self):
        """Test maintenance prediction alert with HIGH urgency"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_maintenance_prediction(
            truck_id="TRUCK_008",
            sensor="coolant_temp_f",
            current_value=215.0,
            threshold=230.0,
            days_to_failure=4.0,
            urgency="HIGH",
            unit="°F",
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.priority == AlertPriority.HIGH

    def test_alert_maintenance_prediction_medium_urgency(self):
        """Test maintenance prediction alert with MEDIUM urgency"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_maintenance_prediction(
            truck_id="TRUCK_009",
            sensor="oil_pressure_psi",
            current_value=35.0,
            threshold=30.0,
            days_to_failure=6.0,
            urgency="MEDIUM",
            unit=" PSI",
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.priority == AlertPriority.MEDIUM

    def test_alert_maintenance_prediction_very_soon_days(self):
        """Test maintenance prediction with days < 3 (should be CRITICAL)"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_maintenance_prediction(
            truck_id="TRUCK_010",
            sensor="brake_air_psi",
            current_value=105.0,
            threshold=100.0,
            days_to_failure=1.5,
            urgency="HIGH",  # Even if urgency is HIGH, days < 3 makes it CRITICAL
            unit=" PSI",
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.priority == AlertPriority.CRITICAL
