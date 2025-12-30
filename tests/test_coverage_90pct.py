"""
Test Suite to Achieve 90% Coverage - Dec 28, 2025
================================================

Target modules:
- alert_service.py: 51.87% → 90%
- database_mysql.py: 25.32% → 90%
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import mysql.connector
import pytest


class TestAlertServiceCoverage90:
    """Tests to increase alert_service coverage to 90%"""

    def test_check_fuel_alerts_all_types(self):
        """Test all alert types in check_fuel_alerts"""
        from alert_service import AlertManager, check_fuel_alerts

        # Mock connection
        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        truck_id = "TEST123"

        # Test with theft alert
        result = check_fuel_alerts(
            truck_id=truck_id,
            sensor_pct=50.0,
            estimated_pct=80.0,  # Big diff = theft potential
            sensor_gal=100.0,
            estimated_gal=160.0,
            drift_pct=-30.0,
            truck_status="STOPPED",
            timestamp_utc=datetime.now(),
            connection=mock_conn,
        )
        assert result is not None

    def test_send_refuel_alert(self):
        """Test send_refuel_alert function"""
        from alert_service import send_refuel_alert

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        result = send_refuel_alert(
            truck_id="TEST123",
            before_pct=30.0,
            after_pct=95.0,
            gallons_added=130.0,
            timestamp_utc=datetime.now(),
            connection=mock_conn,
        )
        assert result == True

    def test_send_theft_alert(self):
        """Test send_theft_alert function"""
        from alert_service import send_theft_alert

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        result = send_theft_alert(
            truck_id="TEST123",
            before_pct=80.0,
            after_pct=30.0,
            gallons_lost=100.0,
            timestamp_utc=datetime.now(),
            connection=mock_conn,
            confidence=0.95,
        )
        assert result == True

    def test_send_low_fuel_alert(self):
        """Test send_low_fuel_alert function"""
        from alert_service import send_low_fuel_alert

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        result = send_low_fuel_alert(
            truck_id="TEST123",
            fuel_pct=15.0,
            fuel_gal=30.0,
            timestamp_utc=datetime.now(),
            connection=mock_conn,
        )
        assert result == True

    def test_send_drift_alert(self):
        """Test send_drift_alert function"""
        from alert_service import send_drift_alert

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        result = send_drift_alert(
            truck_id="TEST123",
            drift_pct=12.0,
            sensor_pct=50.0,
            estimated_pct=62.0,
            timestamp_utc=datetime.now(),
            connection=mock_conn,
        )
        assert result == True

    def test_send_sensor_fault_alert(self):
        """Test send_sensor_fault_alert function"""
        from alert_service import send_sensor_fault_alert

        mock_conn = Mock()
        result = send_sensor_fault_alert(
            truck_id="TEST123",
            fault_type="STUCK",
            timestamp_utc=datetime.now(),
            connection=mock_conn,
        )
        assert result == True

    def test_alert_manager_send_alert(self):
        """Test AlertManager send_alert method"""
        from alert_service import AlertManager

        mock_conn = Mock()
        manager = AlertManager(mock_conn)

        result = manager.send_alert(
            truck_id="TEST123",
            alert_type="CRITICAL",
            message="Test alert",
            severity="high",
            data={"test": "data"},
        )
        assert result == True

    def test_alert_manager_rate_limiting(self):
        """Test AlertManager rate limiting"""
        from alert_service import AlertManager

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        # Return recent alert to trigger rate limit
        mock_cursor.fetchone.return_value = {"last_sent": datetime.now()}

        manager = AlertManager(mock_conn)
        result = manager.check_rate_limit("TEST123", "THEFT")
        assert result == False

    def test_alert_manager_get_alert_history(self):
        """Test AlertManager get_alert_history"""
        from alert_service import AlertManager

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "truck_id": "TEST123",
                "alert_type": "THEFT",
                "created_at": datetime.now(),
            }
        ]

        manager = AlertManager(mock_conn)
        history = manager.get_alert_history("TEST123", hours=24)
        assert len(history) > 0


class TestDatabaseMySQLCoverage90:
    """Tests to increase database_mysql coverage to 90%"""

    def test_get_fuel_metrics_period_1h(self):
        """Test get_fuel_metrics with 1h period"""
        from database_mysql import get_fuel_metrics

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {
                "timestamp_utc": datetime.now(),
                "sensor_pct": 75.0,
                "estimated_pct": 75.5,
                "truck_status": "MOVING",
            }
        ]

        result = get_fuel_metrics(mock_conn, "TEST123", period_hours=1)
        assert len(result) > 0

    def test_get_fuel_metrics_period_6h(self):
        """Test get_fuel_metrics with 6h period"""
        from database_mysql import get_fuel_metrics

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = get_fuel_metrics(mock_conn, "TEST123", period_hours=6)
        assert isinstance(result, list)

    def test_get_fuel_metrics_period_12h(self):
        """Test get_fuel_metrics with 12h period"""
        from database_mysql import get_fuel_metrics

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = get_fuel_metrics(mock_conn, "TEST123", period_hours=12)
        assert isinstance(result, list)

    def test_get_fuel_metrics_period_24h(self):
        """Test get_fuel_metrics with 24h period"""
        from database_mysql import get_fuel_metrics

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = get_fuel_metrics(mock_conn, "TEST123", period_hours=24)
        assert isinstance(result, list)

    def test_get_fuel_metrics_period_168h(self):
        """Test get_fuel_metrics with 168h (7 days) period"""
        from database_mysql import get_fuel_metrics

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = get_fuel_metrics(mock_conn, "TEST123", period_hours=168)
        assert isinstance(result, list)

    def test_get_fuel_metrics_period_720h(self):
        """Test get_fuel_metrics with 720h (30 days) period"""
        from database_mysql import get_fuel_metrics

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        result = get_fuel_metrics(mock_conn, "TEST123", period_hours=720)
        assert isinstance(result, list)

    def test_get_theft_events(self):
        """Test get_theft_events function"""
        from database_mysql import get_theft_events

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "truck_id": "TEST123",
                "theft_time": datetime.now(),
                "gallons_lost": 50.0,
                "confidence": 0.95,
            }
        ]

        result = get_theft_events(mock_conn, "TEST123", days=7)
        assert len(result) > 0

    def test_get_refuel_events(self):
        """Test get_refuel_events function"""
        from database_mysql import get_refuel_events

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "truck_id": "TEST123",
                "refuel_time": datetime.now(),
                "gallons_added": 100.0,
            }
        ]

        result = get_refuel_events(mock_conn, "TEST123", days=7)
        assert len(result) > 0

    def test_get_driver_scorecard(self):
        """Test get_driver_scorecard function"""
        from database_mysql import get_driver_scorecard

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {
            "avg_mpg": 6.5,
            "avg_idle_pct": 15.0,
            "total_miles": 500.0,
            "total_fuel": 77.0,
        }

        result = get_driver_scorecard(mock_conn, "TEST123", days=30)
        assert result is not None
        assert "avg_mpg" in result

    def test_get_fleet_summary(self):
        """Test get_fleet_summary function"""
        from database_mysql import get_fleet_summary

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {
                "truck_id": "TEST123",
                "avg_fuel_pct": 75.0,
                "total_miles": 500.0,
                "avg_mpg": 6.5,
            }
        ]

        result = get_fleet_summary(mock_conn, days=7)
        assert len(result) > 0

    def test_get_fuel_loss_analysis(self):
        """Test get_fuel_loss_analysis function"""
        from database_mysql import get_fuel_loss_analysis

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchone.return_value = {
            "total_thefts": 5,
            "total_gallons_lost": 250.0,
            "avg_loss_per_event": 50.0,
        }

        result = get_fuel_loss_analysis(mock_conn, "TEST123", days=30)
        assert result is not None

    def test_get_maintenance_alerts(self):
        """Test get_maintenance_alerts function"""
        from database_mysql import get_maintenance_alerts

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "truck_id": "TEST123",
                "alert_type": "SENSOR_FAULT",
                "created_at": datetime.now(),
            }
        ]

        result = get_maintenance_alerts(mock_conn, "TEST123", days=30)
        assert len(result) > 0

    def test_save_alert(self):
        """Test save_alert function"""
        from database_mysql import save_alert

        mock_conn = Mock()
        mock_cursor = Mock()
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        result = save_alert(
            conn=mock_conn,
            truck_id="TEST123",
            alert_type="THEFT",
            message="Test alert",
            severity="high",
            data={"test": "data"},
        )
        assert result == True


class TestIntegrationCoverage90:
    """Integration tests with real connections"""

    @pytest.fixture
    def real_connection(self):
        """Get real database connection"""
        try:
            from truck_mapping import MYSQL_CONFIG

            from database_mysql import get_db_connection

            conn = get_db_connection(MYSQL_CONFIG)
            yield conn
            conn.close()
        except Exception as e:
            pytest.skip(f"Database not available: {e}")

    def test_real_get_fuel_metrics_multi_period(self, real_connection):
        """Test get_fuel_metrics with real connection across multiple periods"""
        from database_mysql import get_fuel_metrics

        # Get LC6799 (we know it exists from refuel analysis)
        truck_id = "LC6799"

        for hours in [1, 6, 12, 24, 168, 720]:
            result = get_fuel_metrics(real_connection, truck_id, period_hours=hours)
            assert isinstance(result, list)

    def test_real_fleet_summary(self, real_connection):
        """Test get_fleet_summary with real connection"""
        from database_mysql import get_fleet_summary

        result = get_fleet_summary(real_connection, days=7)
        assert isinstance(result, list)

    def test_real_refuel_events(self, real_connection):
        """Test get_refuel_events with real connection"""
        from database_mysql import get_refuel_events

        # Use JC1282 (we know it has refuels from earlier analysis)
        result = get_refuel_events(real_connection, "JC1282", days=7)
        assert isinstance(result, list)
