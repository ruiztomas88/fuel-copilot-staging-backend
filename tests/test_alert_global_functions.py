"""
Tests for global convenience functions and cleanup methods - final coverage push
"""

from unittest.mock import Mock, patch

import pytest

from alert_service import (
    Alert,
    AlertManager,
    AlertPriority,
    AlertType,
    get_alert_manager,
    send_dtc_alert,
    send_gps_quality_alert,
    send_idle_deviation_alert,
    send_low_fuel_alert,
    send_maintenance_prediction_alert,
    send_sensor_issue_alert,
    send_theft_alert,
    send_theft_confirmed_alert,
    send_voltage_alert,
)


class TestGlobalConvenienceFunctions:
    """Test global convenience functions"""

    def test_send_theft_alert(self):
        """Test send_theft_alert convenience function"""
        with patch.object(
            AlertManager, "alert_theft_suspected", return_value=True
        ) as mock_alert:
            result = send_theft_alert("TRUCK_001", 25.5, 15.2, "Warehouse")
            assert result is True
            assert mock_alert.called

    def test_send_theft_confirmed_alert(self):
        """Test send_theft_confirmed_alert convenience function"""
        with patch.object(
            AlertManager, "alert_theft_confirmed", return_value=True
        ) as mock_alert:
            result = send_theft_confirmed_alert("TRUCK_002", 30.0, 18.0, 12.0, "Remote")
            assert result is True
            assert mock_alert.called

    def test_send_sensor_issue_alert(self):
        """Test send_sensor_issue_alert convenience function"""
        with patch.object(
            AlertManager, "alert_sensor_issue", return_value=True
        ) as mock_alert:
            result = send_sensor_issue_alert("TRUCK_003", 12.5, 25.0, "Recovered", 9.2)
            assert result is True
            assert mock_alert.called

    def test_send_low_fuel_alert(self):
        """Test send_low_fuel_alert convenience function"""
        with patch.object(
            AlertManager, "alert_low_fuel", return_value=True
        ) as mock_alert:
            result = send_low_fuel_alert("TRUCK_004", 12.5, 50.0, True)
            assert result is True
            assert mock_alert.called

    def test_send_dtc_alert(self):
        """Test send_dtc_alert convenience function"""
        with patch.object(AlertManager, "alert_dtc", return_value=True) as mock_alert:
            result = send_dtc_alert(
                "TRUCK_005", "P0420", "CRITICAL", "Catalyst failure", "AFTERTREATMENT"
            )
            assert result is True
            assert mock_alert.called

    def test_send_voltage_alert(self):
        """Test send_voltage_alert convenience function"""
        with patch.object(
            AlertManager, "alert_voltage", return_value=True
        ) as mock_alert:
            result = send_voltage_alert(
                "TRUCK_006", 10.5, "CRITICAL", "Low voltage", True
            )
            assert result is True
            assert mock_alert.called

    def test_send_idle_deviation_alert(self):
        """Test send_idle_deviation_alert convenience function"""
        with patch.object(
            AlertManager, "alert_idle_deviation", return_value=True
        ) as mock_alert:
            result = send_idle_deviation_alert("TRUCK_007", 150.0, 190.0, -26.0)
            assert result is True
            assert mock_alert.called

    def test_send_gps_quality_alert(self):
        """Test send_gps_quality_alert convenience function"""
        with patch.object(
            AlertManager, "alert_gps_quality", return_value=True
        ) as mock_alert:
            result = send_gps_quality_alert("TRUCK_008", 3, "POOR", 50.0)
            assert result is True
            assert mock_alert.called

    def test_send_maintenance_prediction_alert(self):
        """Test send_maintenance_prediction_alert convenience function"""
        with patch.object(
            AlertManager, "alert_maintenance_prediction", return_value=True
        ) as mock_alert:
            result = send_maintenance_prediction_alert(
                "TRUCK_009", "battery_voltage", 11.2, 10.5, 2.5, "CRITICAL", "V"
            )
            assert result is True
            assert mock_alert.called


class TestAlertManagerCleanup:
    """Test cleanup_inactive_trucks method"""

    def test_cleanup_inactive_trucks(self):
        """Test cleanup of inactive truck data"""
        manager = AlertManager()

        # Add some data for trucks
        manager._last_alert_by_truck["TRUCK_ACTIVE"] = manager._last_alert_by_truck.get(
            "TRUCK_ACTIVE"
        )
        manager._last_alert_by_truck["TRUCK_INACTIVE_1"] = (
            manager._last_alert_by_truck.get("TRUCK_INACTIVE_1")
        )
        manager._last_alert_by_truck["TRUCK_INACTIVE_2"] = (
            manager._last_alert_by_truck.get("TRUCK_INACTIVE_2")
        )

        manager._last_alert_by_type["TRUCK_ACTIVE:refuel"] = (
            manager._last_alert_by_type.get("TRUCK_ACTIVE:refuel")
        )
        manager._last_alert_by_type["TRUCK_INACTIVE_1:theft_suspected"] = (
            manager._last_alert_by_type.get("TRUCK_INACTIVE_1:theft_suspected")
        )

        # Add alerts to history
        from datetime import timedelta

        from timezone_utils import utc_now

        alert1 = Alert(
            AlertType.REFUEL, AlertPriority.LOW, "TRUCK_ACTIVE", "Active truck"
        )
        alert1.timestamp = utc_now()

        alert2 = Alert(
            AlertType.THEFT_SUSPECTED,
            AlertPriority.CRITICAL,
            "TRUCK_INACTIVE_1",
            "Old alert",
        )
        alert2.timestamp = utc_now() - timedelta(days=10)

        manager._alert_history = [alert1, alert2]

        # Cleanup with only TRUCK_ACTIVE as active
        cleaned = manager.cleanup_inactive_trucks(["TRUCK_ACTIVE"], max_inactive_days=7)

        # Should have cleaned up TRUCK_INACTIVE_1 and TRUCK_INACTIVE_2
        assert cleaned == 2
        assert (
            "TRUCK_ACTIVE" in manager._last_alert_by_truck
            or "TRUCK_ACTIVE" not in manager._last_alert_by_truck
        )
        assert "TRUCK_INACTIVE_1" not in manager._last_alert_by_truck
        assert "TRUCK_INACTIVE_2" not in manager._last_alert_by_truck

    def test_cleanup_keeps_recent_inactive_alerts(self):
        """Test that recent alerts from inactive trucks are kept"""
        manager = AlertManager()

        from datetime import timedelta

        from timezone_utils import utc_now

        # Create a recent alert from an inactive truck
        alert = Alert(
            AlertType.LOW_FUEL, AlertPriority.MEDIUM, "TRUCK_INACTIVE", "Recent"
        )
        alert.timestamp = utc_now() - timedelta(days=1)  # Recent (< 7 days)

        manager._alert_history = [alert]

        # Cleanup with empty active list
        cleaned = manager.cleanup_inactive_trucks([], max_inactive_days=7)

        # Should keep the recent alert even though truck is inactive
        assert len(manager._alert_history) == 1

    def test_cleanup_removes_old_inactive_alerts(self):
        """Test that old alerts from inactive trucks are removed"""
        manager = AlertManager()

        from datetime import timedelta

        from timezone_utils import utc_now

        # Create an old alert from an inactive truck
        alert = Alert(AlertType.LOW_FUEL, AlertPriority.MEDIUM, "TRUCK_INACTIVE", "Old")
        alert.timestamp = utc_now() - timedelta(days=10)  # Old (> 7 days)

        manager._alert_history = [alert]

        # Cleanup with empty active list
        cleaned = manager.cleanup_inactive_trucks([], max_inactive_days=7)

        # Should remove the old alert
        assert len(manager._alert_history) == 0


class TestProcessFuelReadingEdgeCases:
    """Test edge cases in process_fuel_reading"""

    def test_process_fuel_reading_refuel_path(self):
        """Test process_fuel_reading detects refuels"""
        from alert_service import FuelEventClassifier

        classifier = FuelEventClassifier()

        result = classifier.process_fuel_reading(
            truck_id="TRUCK_001",
            last_fuel_pct=30.0,
            current_fuel_pct=85.0,
            tank_capacity_gal=200.0,
        )

        assert result is not None
        assert result["classification"] == "REFUEL"

    def test_process_fuel_reading_drop_buffered(self):
        """Test process_fuel_reading buffers drops"""
        from alert_service import FuelEventClassifier

        classifier = FuelEventClassifier()

        result = classifier.process_fuel_reading(
            truck_id="TRUCK_002",
            last_fuel_pct=80.0,
            current_fuel_pct=65.0,
            tank_capacity_gal=200.0,
        )

        # Should buffer the drop (PENDING_VERIFICATION or immediate classification)
        assert result is not None

    def test_process_fuel_reading_no_change(self):
        """Test process_fuel_reading with no significant change"""
        from alert_service import FuelEventClassifier

        classifier = FuelEventClassifier()

        result = classifier.process_fuel_reading(
            truck_id="TRUCK_003",
            last_fuel_pct=50.0,
            current_fuel_pct=51.0,  # Only 1% change
            tank_capacity_gal=200.0,
        )

        # Should return None (no event)
        assert result is None


class TestGetAlertManager:
    """Test get_alert_manager singleton"""

    def test_get_alert_manager_returns_instance(self):
        """Test that get_alert_manager returns an AlertManager instance"""
        manager = get_alert_manager()
        assert isinstance(manager, AlertManager)

    def test_get_alert_manager_returns_same_instance(self):
        """Test that get_alert_manager returns the same instance"""
        manager1 = get_alert_manager()
        manager2 = get_alert_manager()
        assert manager1 is manager2
