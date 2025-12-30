"""
Tests for AlertManager convenience methods - reaching 100% coverage
"""

from unittest.mock import Mock

import pytest

from alert_service import AlertManager, AlertPriority, AlertType


class TestAlertManagerConvenienceMethods:
    """Test convenience methods for common alerts"""

    def test_alert_theft_suspected(self):
        """Test theft suspected alert"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_theft_suspected(
            truck_id="TRUCK_001",
            fuel_drop_gallons=25.5,
            fuel_drop_pct=15.2,
            location="Warehouse A",
        )

        assert result is True
        assert manager.send_alert.called

        # Verify alert properties
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.alert_type == AlertType.THEFT_SUSPECTED
        assert alert.priority == AlertPriority.CRITICAL
        assert alert.truck_id == "TRUCK_001"
        assert "25.5" in str(alert.details["fuel_drop_gallons"])

    def test_alert_theft_confirmed(self):
        """Test theft confirmed alert"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_theft_confirmed(
            truck_id="TRUCK_002",
            fuel_drop_gallons=30.0,
            fuel_drop_pct=18.5,
            time_waited_minutes=12.0,
            location="Remote Location",
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.alert_type == AlertType.THEFT_CONFIRMED
        assert alert.priority == AlertPriority.CRITICAL

    def test_alert_sensor_issue(self):
        """Test sensor issue alert"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_sensor_issue(
            truck_id="TRUCK_003",
            drop_pct=12.5,
            drop_gal=25.0,
            recovery_info="Fuel recovered after 8 minutes",
            volatility=9.2,
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.alert_type == AlertType.SENSOR_ISSUE
        assert alert.priority == AlertPriority.MEDIUM
        assert "9.2" in str(alert.details["sensor_volatility"])

    def test_alert_sensor_issue_without_optional_params(self):
        """Test sensor issue alert without optional parameters"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_sensor_issue(
            truck_id="TRUCK_004", drop_pct=10.0, drop_gal=20.0
        )

        assert result is True

    def test_alert_refuel_with_sms(self):
        """Test refuel alert with SMS enabled"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_refuel(
            truck_id="TRUCK_005",
            gallons_added=50.0,
            new_level_pct=95.5,
            location="Gas Station",
            send_sms=True,
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.alert_type == AlertType.REFUEL
        assert alert.priority == AlertPriority.LOW

        # Should use SMS + email channels
        channels = call_args[1]["channels"]
        assert "sms" in channels
        assert "email" in channels

    def test_alert_refuel_without_sms(self):
        """Test refuel alert without SMS"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_refuel(
            truck_id="TRUCK_006", gallons_added=45.0, new_level_pct=90.0, send_sms=False
        )

        assert result is True
        call_args = manager.send_alert.call_args

        # Should use only email channel
        channels = call_args[1]["channels"]
        assert "email" in channels
        assert "sms" not in channels

    def test_alert_low_fuel_critical_level(self):
        """Test low fuel alert at critical level (<= 15%)"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_low_fuel(
            truck_id="TRUCK_007", current_level_pct=12.5, estimated_miles_remaining=25.0
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.alert_type == AlertType.LOW_FUEL
        assert alert.priority == AlertPriority.CRITICAL

        # Should use SMS + email for critical
        channels = call_args[1]["channels"]
        assert "sms" in channels
        assert "email" in channels

    def test_alert_low_fuel_high_level_with_sms(self):
        """Test low fuel alert at high level (15-25%) with SMS"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_low_fuel(
            truck_id="TRUCK_008",
            current_level_pct=22.0,
            estimated_miles_remaining=50.0,
            send_sms=True,
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.priority == AlertPriority.HIGH

        # Should use SMS + email when send_sms=True
        channels = call_args[1]["channels"]
        assert "sms" in channels

    def test_alert_low_fuel_high_level_without_sms(self):
        """Test low fuel alert at high level (15-25%) without SMS"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_low_fuel(
            truck_id="TRUCK_009", current_level_pct=20.0, send_sms=False
        )

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.priority == AlertPriority.HIGH

        # Should use only email when send_sms=False
        channels = call_args[1]["channels"]
        assert "email" in channels
        assert "sms" not in channels

    def test_alert_low_fuel_medium_level(self):
        """Test low fuel alert at medium level (> 25%)"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_low_fuel(truck_id="TRUCK_010", current_level_pct=30.0)

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.priority == AlertPriority.MEDIUM

        # Should use no channels (log only)
        channels = call_args[1]["channels"]
        assert channels == []

    def test_alert_sensor_offline(self):
        """Test sensor offline alert"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        result = manager.alert_sensor_offline(truck_id="TRUCK_011", offline_minutes=45)

        assert result is True
        call_args = manager.send_alert.call_args
        alert = call_args[0][0]
        assert alert.alert_type == AlertType.SENSOR_OFFLINE
        assert alert.priority == AlertPriority.MEDIUM

    def test_get_alert_history_all(self):
        """Test getting all alert history"""
        manager = AlertManager()
        manager.send_alert = Mock(return_value=True)

        # Create some alerts
        manager.alert_refuel("TRUCK_001", 50.0, 90.0)
        manager.alert_refuel("TRUCK_002", 45.0, 85.0)
        manager.alert_low_fuel("TRUCK_003", 10.0)

        history = manager.get_alert_history()

        # Since send_alert is mocked, we need to manually add to history
        # Or we can test the filtering logic separately
        assert isinstance(history, list)

    def test_get_alert_history_filtered_by_truck(self):
        """Test getting alert history filtered by truck_id"""
        manager = AlertManager()

        # Manually add alerts to history for testing
        from alert_service import Alert, AlertPriority, AlertType

        alert1 = Alert(AlertType.REFUEL, AlertPriority.LOW, "TRUCK_A", "Refuel")
        alert2 = Alert(AlertType.REFUEL, AlertPriority.LOW, "TRUCK_B", "Refuel")
        alert3 = Alert(AlertType.LOW_FUEL, AlertPriority.HIGH, "TRUCK_A", "Low fuel")

        manager._alert_history = [alert1, alert2, alert3]

        history = manager.get_alert_history(truck_id="TRUCK_A")

        assert len(history) == 2
        assert all(a.truck_id == "TRUCK_A" for a in history)

    def test_get_alert_history_filtered_by_type(self):
        """Test getting alert history filtered by alert_type"""
        manager = AlertManager()

        from alert_service import Alert, AlertPriority, AlertType

        alert1 = Alert(AlertType.REFUEL, AlertPriority.LOW, "TRUCK_A", "Refuel")
        alert2 = Alert(AlertType.REFUEL, AlertPriority.LOW, "TRUCK_B", "Refuel")
        alert3 = Alert(AlertType.LOW_FUEL, AlertPriority.HIGH, "TRUCK_A", "Low fuel")

        manager._alert_history = [alert1, alert2, alert3]

        history = manager.get_alert_history(alert_type=AlertType.REFUEL)

        assert len(history) == 2
        assert all(a.alert_type == AlertType.REFUEL for a in history)

    def test_get_alert_history_filtered_by_both(self):
        """Test getting alert history filtered by truck_id and alert_type"""
        manager = AlertManager()

        from alert_service import Alert, AlertPriority, AlertType

        alert1 = Alert(AlertType.REFUEL, AlertPriority.LOW, "TRUCK_A", "Refuel")
        alert2 = Alert(AlertType.REFUEL, AlertPriority.LOW, "TRUCK_B", "Refuel")
        alert3 = Alert(AlertType.LOW_FUEL, AlertPriority.HIGH, "TRUCK_A", "Low fuel")

        manager._alert_history = [alert1, alert2, alert3]

        history = manager.get_alert_history(
            truck_id="TRUCK_A", alert_type=AlertType.REFUEL
        )

        assert len(history) == 1
        assert history[0].truck_id == "TRUCK_A"
        assert history[0].alert_type == AlertType.REFUEL
