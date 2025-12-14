"""
Tests for alert_service v5.7.6 features: idle deviation and GPS quality alerts
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

from alert_service import (
    AlertType,
    AlertPriority,
    Alert,
    AlertManager,
    send_idle_deviation_alert,
    send_gps_quality_alert,
)


class TestAlertTypes:
    """Test new alert types exist"""

    def test_idle_deviation_type_exists(self):
        """Verify IDLE_DEVIATION alert type exists"""
        assert AlertType.IDLE_DEVIATION.value == "idle_deviation"

    def test_gps_quality_type_exists(self):
        """Verify GPS_QUALITY alert type exists"""
        assert AlertType.GPS_QUALITY.value == "gps_quality"


class TestAlertManagerIdleDeviation:
    """Test idle deviation alert functionality"""

    @pytest.fixture
    def manager(self):
        """Create AlertManager instance"""
        return AlertManager()

    def test_alert_idle_deviation_high_priority(self, manager):
        """Test high deviation (>25%) triggers HIGH priority"""
        with patch.object(manager, "send_alert", return_value=True) as mock_send:
            result = manager.alert_idle_deviation(
                truck_id="T001",
                calculated_hours=30.0,
                ecu_hours=20.0,
                deviation_pct=50.0,
            )

            assert result is True
            mock_send.assert_called_once()
            alert = mock_send.call_args[0][0]
            assert alert.priority == AlertPriority.HIGH
            assert alert.alert_type == AlertType.IDLE_DEVIATION
            assert "T001" in alert.truck_id

    def test_alert_idle_deviation_medium_priority(self, manager):
        """Test moderate deviation (15-25%) triggers MEDIUM priority"""
        with patch.object(manager, "send_alert", return_value=True) as mock_send:
            result = manager.alert_idle_deviation(
                truck_id="T002",
                calculated_hours=23.0,
                ecu_hours=20.0,
                deviation_pct=15.0,
            )

            assert result is True
            mock_send.assert_called_once()
            alert = mock_send.call_args[0][0]
            assert alert.priority == AlertPriority.MEDIUM

    def test_alert_idle_deviation_message_format(self, manager):
        """Test message contains expected information"""
        with patch.object(manager, "send_alert", return_value=True) as mock_send:
            manager.alert_idle_deviation(
                truck_id="T003",
                calculated_hours=25.5,
                ecu_hours=20.0,
                deviation_pct=27.5,
            )

            alert = mock_send.call_args[0][0]
            assert "25.5h" in alert.message
            assert "20.0h" in alert.message
            assert "+27.5%" in alert.message

    def test_alert_idle_deviation_details(self, manager):
        """Test alert details contain correct data"""
        with patch.object(manager, "send_alert", return_value=True) as mock_send:
            manager.alert_idle_deviation(
                truck_id="T004",
                calculated_hours=18.0,
                ecu_hours=15.0,
                deviation_pct=20.0,
            )

            alert = mock_send.call_args[0][0]
            assert alert.details["calculated_idle_hours"] == "18.0h"
            assert alert.details["ecu_idle_hours"] == "15.0h"
            assert alert.details["deviation_pct"] == "+20.0%"


class TestAlertManagerGPSQuality:
    """Test GPS quality alert functionality"""

    @pytest.fixture
    def manager(self):
        """Create AlertManager instance"""
        return AlertManager()

    def test_alert_gps_quality_critical(self, manager):
        """Test critical GPS (<4 sats) triggers HIGH priority"""
        with patch.object(manager, "send_alert", return_value=True) as mock_send:
            result = manager.alert_gps_quality(
                truck_id="T001",
                satellites=3,
                quality_level="CRITICAL",
                estimated_accuracy_m=50.0,
            )

            assert result is True
            mock_send.assert_called_once()
            alert = mock_send.call_args[0][0]
            assert alert.priority == AlertPriority.HIGH
            assert alert.alert_type == AlertType.GPS_QUALITY

    def test_alert_gps_quality_poor(self, manager):
        """Test poor GPS (4-6 sats) triggers MEDIUM priority"""
        with patch.object(manager, "send_alert", return_value=True) as mock_send:
            result = manager.alert_gps_quality(
                truck_id="T002",
                satellites=5,
                quality_level="POOR",
                estimated_accuracy_m=20.0,
            )

            assert result is True
            alert = mock_send.call_args[0][0]
            assert alert.priority == AlertPriority.MEDIUM

    def test_alert_gps_quality_message_format(self, manager):
        """Test message contains satellite count and quality"""
        with patch.object(manager, "send_alert", return_value=True) as mock_send:
            manager.alert_gps_quality(
                truck_id="T003",
                satellites=4,
                quality_level="POOR",
                estimated_accuracy_m=25.0,
            )

            alert = mock_send.call_args[0][0]
            assert "Satellites: 4" in alert.message
            assert "POOR" in alert.message
            assert "25m" in alert.message

    def test_alert_gps_quality_no_accuracy(self, manager):
        """Test alert works without accuracy data"""
        with patch.object(manager, "send_alert", return_value=True) as mock_send:
            result = manager.alert_gps_quality(
                truck_id="T004",
                satellites=3,
                quality_level="CRITICAL",
                estimated_accuracy_m=None,
            )

            assert result is True
            alert = mock_send.call_args[0][0]
            assert "accuracy" not in alert.message.lower() or "N/A" in str(
                alert.details
            )


class TestConvenienceFunctions:
    """Test convenience wrapper functions"""

    @patch("alert_service.get_alert_manager")
    def test_send_idle_deviation_alert(self, mock_get_manager):
        """Test send_idle_deviation_alert convenience function"""
        mock_manager = MagicMock()
        mock_manager.alert_idle_deviation.return_value = True
        mock_get_manager.return_value = mock_manager

        result = send_idle_deviation_alert(
            truck_id="T001",
            calculated_hours=20.0,
            ecu_hours=15.0,
            deviation_pct=33.3,
        )

        assert result is True
        mock_manager.alert_idle_deviation.assert_called_once_with(
            "T001", 20.0, 15.0, 33.3
        )

    @patch("alert_service.get_alert_manager")
    def test_send_gps_quality_alert(self, mock_get_manager):
        """Test send_gps_quality_alert convenience function"""
        mock_manager = MagicMock()
        mock_manager.alert_gps_quality.return_value = True
        mock_get_manager.return_value = mock_manager

        result = send_gps_quality_alert(
            truck_id="T002",
            satellites=4,
            quality_level="POOR",
            estimated_accuracy_m=30.0,
        )

        assert result is True
        mock_manager.alert_gps_quality.assert_called_once_with("T002", 4, "POOR", 30.0)


class TestAlertFormatting:
    """Test alert message formatting"""

    @pytest.fixture
    def manager(self):
        return AlertManager()

    def test_idle_deviation_emoji(self, manager):
        """Test idle deviation uses correct emoji"""
        with patch.object(manager, "send_alert", return_value=True) as mock_send:
            manager.alert_idle_deviation(
                truck_id="T001",
                calculated_hours=20.0,
                ecu_hours=15.0,
                deviation_pct=33.3,
            )

            alert = mock_send.call_args[0][0]
            assert "⏱️" in alert.message

    def test_gps_quality_emoji(self, manager):
        """Test GPS quality uses correct emoji"""
        with patch.object(manager, "send_alert", return_value=True) as mock_send:
            manager.alert_gps_quality(
                truck_id="T001",
                satellites=3,
                quality_level="CRITICAL",
            )

            alert = mock_send.call_args[0][0]
            assert "📡" in alert.message
