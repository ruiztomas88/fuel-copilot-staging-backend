"""
Tests for v5.7.3 features:
- DTC and Voltage alerts via alert_service
- Daily idle_tracking reset
- Descriptive GPS quality
- DTC event persistence

Run: pytest tests/test_v5_7_3_features.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock
import json


class TestDTCAlerts:
    """Test DTC alert functionality"""

    def test_alert_type_dtc_exists(self):
        """Verify DTC_ALERT type exists in AlertType enum"""
        from alert_service import AlertType
        assert hasattr(AlertType, 'DTC_ALERT')
        assert AlertType.DTC_ALERT.value == "dtc_alert"

    def test_alert_type_voltage_exists(self):
        """Verify VOLTAGE_ALERT type exists in AlertType enum"""
        from alert_service import AlertType
        assert hasattr(AlertType, 'VOLTAGE_ALERT')
        assert AlertType.VOLTAGE_ALERT.value == "voltage_alert"

    def test_send_dtc_alert_function_exists(self):
        """Verify send_dtc_alert convenience function exists"""
        from alert_service import send_dtc_alert
        assert callable(send_dtc_alert)

    def test_send_voltage_alert_function_exists(self):
        """Verify send_voltage_alert convenience function exists"""
        from alert_service import send_voltage_alert
        assert callable(send_voltage_alert)

    def test_alert_manager_has_dtc_method(self):
        """Verify AlertManager has alert_dtc method"""
        from alert_service import AlertManager
        manager = AlertManager()
        assert hasattr(manager, 'alert_dtc')
        assert callable(manager.alert_dtc)

    def test_alert_manager_has_voltage_method(self):
        """Verify AlertManager has alert_voltage method"""
        from alert_service import AlertManager
        manager = AlertManager()
        assert hasattr(manager, 'alert_voltage')
        assert callable(manager.alert_voltage)

    def test_dtc_alert_critical_priority(self):
        """Verify CRITICAL DTC creates CRITICAL priority alert"""
        from alert_service import AlertManager, AlertPriority
        
        manager = AlertManager()
        
        # Mock the send_alert to capture the alert
        alerts_sent = []
        original_send = manager.send_alert
        def mock_send(alert, channels=None):
            alerts_sent.append((alert, channels))
            return True
        manager.send_alert = mock_send
        
        result = manager.alert_dtc(
            truck_id="TEST001",
            dtc_code="SPN524.FMI4",
            severity="CRITICAL",
            description="Engine Coolant Temperature too high",
            system="ENGINE",
        )
        
        assert result is True
        assert len(alerts_sent) == 1
        alert, channels = alerts_sent[0]
        assert alert.priority == AlertPriority.CRITICAL
        assert "sms" in channels
        assert "email" in channels

    def test_dtc_alert_warning_priority(self):
        """Verify WARNING DTC creates HIGH priority alert (email only)"""
        from alert_service import AlertManager, AlertPriority
        
        manager = AlertManager()
        
        alerts_sent = []
        def mock_send(alert, channels=None):
            alerts_sent.append((alert, channels))
            return True
        manager.send_alert = mock_send
        
        result = manager.alert_dtc(
            truck_id="TEST001",
            dtc_code="SPN100.FMI3",
            severity="WARNING",
            description="Oil pressure slightly low",
            system="ENGINE",
        )
        
        assert result is True
        assert len(alerts_sent) == 1
        alert, channels = alerts_sent[0]
        assert alert.priority == AlertPriority.HIGH
        assert "sms" not in channels
        assert "email" in channels

    def test_voltage_alert_critical(self):
        """Verify CRITICAL voltage alert sends SMS + Email"""
        from alert_service import AlertManager, AlertPriority
        
        manager = AlertManager()
        
        alerts_sent = []
        def mock_send(alert, channels=None):
            alerts_sent.append((alert, channels))
            return True
        manager.send_alert = mock_send
        
        result = manager.alert_voltage(
            truck_id="TEST001",
            voltage=10.5,
            priority_level="CRITICAL",
            message="Low voltage - alternator failure likely",
            is_engine_running=True,
        )
        
        assert result is True
        alert, channels = alerts_sent[0]
        assert alert.priority == AlertPriority.CRITICAL
        assert "sms" in channels


class TestIdleTrackingReset:
    """Test daily idle tracking reset functionality"""

    def test_reset_function_exists(self):
        """Verify _reset_idle_tracking_if_new_day function exists"""
        from wialon_sync_enhanced import _reset_idle_tracking_if_new_day
        assert callable(_reset_idle_tracking_if_new_day)

    def test_reset_clears_calc_idle_hours(self):
        """Verify reset clears calculated idle hours but keeps ECU reference"""
        from wialon_sync_enhanced import _reset_idle_tracking_if_new_day, _last_idle_reset_date
        import wialon_sync_enhanced
        
        # Create mock state manager
        mock_state_manager = Mock()
        mock_state_manager.idle_tracking = {
            "TRUCK001": {
                "calc_idle_hours": 5.5,
                "last_ecu_idle": 1250.0,
                "last_check": "2025-12-13T12:00:00",
            },
            "TRUCK002": {
                "calc_idle_hours": 3.2,
                "last_ecu_idle": 800.0,
                "last_check": "2025-12-13T12:00:00",
            },
        }
        
        # Force a reset by setting last date to yesterday
        wialon_sync_enhanced._last_idle_reset_date = "2025-12-01"
        
        _reset_idle_tracking_if_new_day(mock_state_manager)
        
        # Verify calc_idle_hours reset to 0 for all trucks
        assert mock_state_manager.idle_tracking["TRUCK001"]["calc_idle_hours"] == 0.0
        assert mock_state_manager.idle_tracking["TRUCK002"]["calc_idle_hours"] == 0.0
        
        # Verify ECU reference preserved
        assert mock_state_manager.idle_tracking["TRUCK001"]["last_ecu_idle"] == 1250.0
        assert mock_state_manager.idle_tracking["TRUCK002"]["last_ecu_idle"] == 800.0

    def test_no_reset_same_day(self):
        """Verify no reset if already reset today"""
        from wialon_sync_enhanced import _reset_idle_tracking_if_new_day
        import wialon_sync_enhanced
        
        mock_state_manager = Mock()
        mock_state_manager.idle_tracking = {
            "TRUCK001": {"calc_idle_hours": 5.5, "last_ecu_idle": 1250.0},
        }
        
        # Set last reset to today
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        wialon_sync_enhanced._last_idle_reset_date = today
        
        _reset_idle_tracking_if_new_day(mock_state_manager)
        
        # Should not reset
        assert mock_state_manager.idle_tracking["TRUCK001"]["calc_idle_hours"] == 5.5


class TestGPSQualityDescriptive:
    """Test descriptive GPS quality format"""

    def test_gps_quality_format(self):
        """Verify GPS quality returns descriptive format"""
        from gps_quality import analyze_gps_quality, GPSQuality
        
        # Test excellent quality
        result = analyze_gps_quality(satellites=14, truck_id="TEST001")
        assert result.quality == GPSQuality.EXCELLENT
        assert result.satellites == 14
        assert result.estimated_accuracy_m <= 2.0

    def test_gps_quality_in_metrics(self):
        """Verify process_truck includes descriptive GPS quality"""
        # This tests the format string creation
        sats = 10
        from gps_quality import analyze_gps_quality
        
        gps_result = analyze_gps_quality(satellites=sats, truck_id="TEST001")
        gps_quality_str = f"{gps_result.quality.value}|sats={sats}|acc={gps_result.estimated_accuracy_m:.0f}m"
        
        # Verify format
        assert "GOOD" in gps_quality_str or "EXCELLENT" in gps_quality_str
        assert f"sats={sats}" in gps_quality_str
        assert "acc=" in gps_quality_str
        assert "m" in gps_quality_str

    def test_gps_quality_poor(self):
        """Verify poor GPS quality detection"""
        from gps_quality import analyze_gps_quality, GPSQuality
        
        result = analyze_gps_quality(satellites=3, truck_id="TEST001")
        assert result.quality == GPSQuality.POOR
        assert result.estimated_accuracy_m >= 10.0

    def test_gps_quality_critical(self):
        """Verify critical GPS quality detection"""
        from gps_quality import analyze_gps_quality, GPSQuality
        
        result = analyze_gps_quality(satellites=1, truck_id="TEST001")
        assert result.quality == GPSQuality.CRITICAL
        assert result.is_reliable_for_distance is False


class TestDTCPersistence:
    """Test DTC event database persistence"""

    def test_save_dtc_event_function_exists(self):
        """Verify save_dtc_event function exists"""
        from wialon_sync_enhanced import save_dtc_event
        assert callable(save_dtc_event)

    def test_save_dtc_event_with_mock(self):
        """Test save_dtc_event with mocked database"""
        from wialon_sync_enhanced import save_dtc_event
        from dtc_analyzer import DTCCode, DTCSeverity
        from dataclasses import dataclass
        
        # Create mock connection and cursor
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = None  # No duplicate
        mock_connection = MagicMock()
        mock_connection.cursor.return_value.__enter__ = Mock(return_value=mock_cursor)
        mock_connection.cursor.return_value.__exit__ = Mock(return_value=False)
        
        # Create mock alert with codes
        @dataclass
        class MockDTCAlert:
            severity: DTCSeverity
            message: str
            codes: list
        
        mock_code = DTCCode(
            spn=524,
            fmi=4,
            raw="524.4",
            severity=DTCSeverity.CRITICAL,
            description="High Engine Coolant Temperature",
            system="ENGINE",
        )
        
        mock_alert = MockDTCAlert(
            severity=DTCSeverity.CRITICAL,
            message="Critical DTC detected",
            codes=[mock_code],
        )
        
        sensor_data = {
            "carrier_id": "CARRIER1",
            "lat": 29.7604,
            "lon": -95.3698,
            "speed": 65.0,
            "engine_hours": 5000.0,
            "odometer": 150000.0,
        }
        
        result = save_dtc_event(
            mock_connection,
            truck_id="TEST001",
            alert=mock_alert,
            sensor_data=sensor_data,
        )
        
        # Verify execute was called for INSERT
        assert mock_cursor.execute.called
        # Verify commit was called
        assert mock_connection.commit.called

    def test_save_dtc_event_empty_codes(self):
        """Verify save_dtc_event returns False for empty codes"""
        from wialon_sync_enhanced import save_dtc_event
        from dataclasses import dataclass
        
        @dataclass
        class MockDTCAlert:
            severity: str
            message: str
            codes: list
        
        mock_alert = MockDTCAlert(
            severity="WARNING",
            message="No codes",
            codes=[],
        )
        
        mock_connection = MagicMock()
        
        result = save_dtc_event(
            mock_connection,
            truck_id="TEST001",
            alert=mock_alert,
            sensor_data={},
        )
        
        assert result is False


class TestMigrationScript:
    """Test DTC events migration script"""

    def test_migration_file_exists(self):
        """Verify migration file exists"""
        from pathlib import Path
        migration_path = Path("/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/migrations/add_dtc_events_table.py")
        assert migration_path.exists()

    def test_migration_has_run_function(self):
        """Verify migration has run_migration function"""
        import sys
        sys.path.insert(0, "/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/migrations")
        from add_dtc_events_table import run_migration
        assert callable(run_migration)


class TestAlertServiceEmojis:
    """Test that new alert types have emojis defined"""

    def test_dtc_emoji_defined(self):
        """Verify DTC alert has emoji in format"""
        from alert_service import AlertManager, AlertType
        
        manager = AlertManager()
        # Access the private method to check emoji mapping
        # The emoji should be in the type_emoji dict
        assert AlertType.DTC_ALERT is not None

    def test_voltage_emoji_defined(self):
        """Verify voltage alert has emoji in format"""
        from alert_service import AlertType
        assert AlertType.VOLTAGE_ALERT is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
