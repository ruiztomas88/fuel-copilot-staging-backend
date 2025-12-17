"""
Tests for voltage_history module v5.7.6
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from voltage_history import (
    VoltageStatus,
    VoltageReading,
    VoltageHistoryManager,
    get_voltage_history_manager,
    record_voltage_reading,
    get_voltage_trending,
)


class TestVoltageStatus:
    """Test VoltageStatus enum"""

    def test_all_statuses_exist(self):
        """Verify all voltage status values exist"""
        assert VoltageStatus.CRITICAL_LOW.value == "CRITICAL_LOW"
        assert VoltageStatus.LOW.value == "LOW"
        assert VoltageStatus.NORMAL.value == "NORMAL"
        assert VoltageStatus.HIGH.value == "HIGH"
        assert VoltageStatus.CRITICAL_HIGH.value == "CRITICAL_HIGH"


class TestVoltageReading:
    """Test VoltageReading dataclass"""

    def test_create_reading(self):
        """Test creating a voltage reading"""
        reading = VoltageReading(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            voltage=13.5,
            rpm=800,
            engine_running=True,
            status=VoltageStatus.NORMAL,
        )

        assert reading.truck_id == "T001"
        assert reading.voltage == 13.5
        assert reading.engine_running is True
        assert reading.status == VoltageStatus.NORMAL
        assert reading.source == "fuel_metrics"  # default

    def test_reading_with_custom_source(self):
        """Test reading with custom source"""
        reading = VoltageReading(
            truck_id="T002",
            timestamp=datetime.now(timezone.utc),
            voltage=12.5,
            rpm=None,
            engine_running=False,
            status=VoltageStatus.NORMAL,
            source="voltage_history",
        )

        assert reading.source == "voltage_history"


class TestVoltageHistoryManager:
    """Test VoltageHistoryManager"""

    @pytest.fixture
    def manager(self):
        """Create manager with mocked database"""
        with patch("voltage_history.get_db_connection"):
            return VoltageHistoryManager()

    def test_classify_voltage_engine_off(self, manager):
        """Test voltage classification when engine is off"""
        # Critical low
        assert manager._classify_voltage(11.0, False) == VoltageStatus.CRITICAL_LOW
        # Low
        assert manager._classify_voltage(12.0, False) == VoltageStatus.LOW
        # Normal
        assert manager._classify_voltage(12.5, False) == VoltageStatus.NORMAL
        # High (engine off but reading high = alternator residual)
        assert manager._classify_voltage(13.5, False) == VoltageStatus.HIGH

    def test_classify_voltage_engine_running(self, manager):
        """Test voltage classification when engine is running"""
        # Critical low (alternator not charging)
        assert manager._classify_voltage(12.0, True) == VoltageStatus.CRITICAL_LOW
        # Low (weak charging)
        assert manager._classify_voltage(13.0, True) == VoltageStatus.LOW
        # Normal charging
        assert manager._classify_voltage(14.0, True) == VoltageStatus.NORMAL
        # High (overcharging)
        assert manager._classify_voltage(15.2, True) == VoltageStatus.HIGH
        # Critical high (dangerous)
        assert manager._classify_voltage(16.0, True) == VoltageStatus.CRITICAL_HIGH

    @patch("voltage_history.get_db_connection")
    def test_record_voltage_no_voltage(self, mock_conn, manager):
        """Test recording with None voltage returns False"""
        result = manager.record_voltage("T001", None)
        assert result is False

    @patch("voltage_history.get_db_connection")
    def test_record_voltage_rate_limiting(self, mock_conn, manager):
        """Test rate limiting prevents too frequent recordings"""
        # First recording should work
        mock_cursor = MagicMock()
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        # Simulate successful first record
        manager._last_sample["T001"] = datetime.now(timezone.utc)

        # Second immediate recording should be skipped
        result = manager.record_voltage("T001", 13.5)
        assert result is False  # Rate limited


class TestVoltageClassificationBoundaries:
    """Test voltage classification boundary conditions"""

    @pytest.fixture
    def manager(self):
        with patch("voltage_history.get_db_connection"):
            return VoltageHistoryManager()

    def test_boundary_11_5_engine_off(self, manager):
        """Test 11.5V boundary when engine off"""
        # Exactly 11.5 is LOW, below is CRITICAL_LOW
        assert manager._classify_voltage(11.5, False) == VoltageStatus.LOW
        assert manager._classify_voltage(11.49, False) == VoltageStatus.CRITICAL_LOW

    def test_boundary_12_2_engine_off(self, manager):
        """Test 12.2V boundary when engine off"""
        # Exactly 12.2 is NORMAL, below is LOW
        assert manager._classify_voltage(12.2, False) == VoltageStatus.NORMAL
        assert manager._classify_voltage(12.19, False) == VoltageStatus.LOW

    def test_boundary_13_2_engine_off(self, manager):
        """Test 13.2V boundary when engine off"""
        # Above 13.2 is HIGH when engine off
        assert manager._classify_voltage(13.2, False) == VoltageStatus.NORMAL
        assert manager._classify_voltage(13.21, False) == VoltageStatus.HIGH

    def test_boundary_13_2_engine_running(self, manager):
        """Test 13.2V boundary when engine running"""
        # Exactly 13.2 is NORMAL (threshold is 13.2)
        assert manager._classify_voltage(13.2, True) == VoltageStatus.NORMAL
        assert manager._classify_voltage(13.19, True) == VoltageStatus.LOW

    def test_boundary_15_0_engine_running(self, manager):
        """Test 15.0V boundary when engine running"""
        # Above 15.0 is HIGH
        assert manager._classify_voltage(15.0, True) == VoltageStatus.NORMAL
        assert manager._classify_voltage(15.01, True) == VoltageStatus.HIGH

    def test_boundary_15_5_engine_running(self, manager):
        """Test 15.5V boundary when engine running"""
        # Above 15.5 is CRITICAL_HIGH
        assert manager._classify_voltage(15.5, True) == VoltageStatus.HIGH
        assert manager._classify_voltage(15.51, True) == VoltageStatus.CRITICAL_HIGH


class TestGetTrendingSummary:
    """Test voltage trending summary"""

    @pytest.fixture
    def manager(self):
        with patch("voltage_history.get_db_connection"):
            return VoltageHistoryManager()

    @patch("voltage_history.get_db_connection")
    def test_trending_no_data(self, mock_conn, manager):
        """Test trending with no data"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (None,) * 10  # No data
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        result = manager.get_trending_summary("T001")

        assert result["has_data"] is False
        assert result["truck_id"] == "T001"

    @patch("voltage_history.get_db_connection")
    def test_trending_with_data(self, mock_conn, manager):
        """Test trending with valid data"""
        mock_cursor = MagicMock()
        # Mock: avg, min, max, std, readings, avg_recent, avg_older, low, critical, high
        mock_cursor.fetchone.return_value = (
            13.5,  # avg_voltage
            12.0,  # min_voltage
            14.5,  # max_voltage
            0.5,  # std_voltage
            100,  # readings
            13.2,  # avg_recent
            13.8,  # avg_older
            2,  # low_events
            0,  # critical_events
            1,  # high_events
        )
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        result = manager.get_trending_summary("T001", days_back=30)

        assert result["has_data"] is True
        assert result["avg_voltage"] == 13.5
        assert result["min_voltage"] == 12.0
        assert result["max_voltage"] == 14.5
        assert result["trend"] == "FALLING"  # 13.2 - 13.8 = -0.6
        assert result["battery_health"] == "GOOD"

    @patch("voltage_history.get_db_connection")
    def test_trending_battery_degraded(self, mock_conn, manager):
        """Test trending detects degraded battery"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            12.3,  # avg_voltage (low)
            11.2,  # min_voltage
            13.0,  # max_voltage
            0.8,  # std_voltage
            50,  # readings
            12.0,  # avg_recent (falling)
            12.6,  # avg_older
            8,  # low_events (>5)
            1,  # critical_events
            0,  # high_events
        )
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        result = manager.get_trending_summary("T002")

        assert result["battery_health"] == "DEGRADED"
        assert result["trend"] == "FALLING"

    @patch("voltage_history.get_db_connection")
    def test_trending_battery_critical(self, mock_conn, manager):
        """Test trending detects critical battery"""
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (
            11.8,  # avg_voltage
            10.5,  # min_voltage
            12.5,  # max_voltage
            1.0,  # std_voltage
            30,  # readings
            11.5,  # avg_recent
            12.0,  # avg_older
            15,  # low_events
            5,  # critical_events (>2)
            0,  # high_events
        )
        mock_conn.return_value.__enter__.return_value.cursor.return_value.__enter__.return_value = (
            mock_cursor
        )

        result = manager.get_trending_summary("T003")

        assert result["battery_health"] == "CRITICAL"


class TestConvenienceFunctions:
    """Test convenience wrapper functions"""

    @patch("voltage_history.get_voltage_history_manager")
    def test_record_voltage_reading_function(self, mock_get_manager):
        """Test record_voltage_reading convenience function"""
        mock_manager = MagicMock()
        mock_manager.record_voltage.return_value = True
        mock_get_manager.return_value = mock_manager

        result = record_voltage_reading(
            truck_id="T001",
            voltage=13.5,
            rpm=800,
            truck_status="IDLE",
        )

        assert result is True
        mock_manager.record_voltage.assert_called_once()

    @patch("voltage_history.get_voltage_history_manager")
    def test_get_voltage_trending_function(self, mock_get_manager):
        """Test get_voltage_trending convenience function"""
        mock_manager = MagicMock()
        mock_manager.get_trending_summary.return_value = {"has_data": True}
        mock_get_manager.return_value = mock_manager

        result = get_voltage_trending("T001", days_back=14)

        assert result["has_data"] is True
        mock_manager.get_trending_summary.assert_called_once_with("T001", 14)


class TestSingletonPattern:
    """Test singleton pattern for manager"""

    @patch("voltage_history.get_db_connection")
    def test_singleton_returns_same_instance(self, mock_conn):
        """Test get_voltage_history_manager returns same instance"""
        # Reset singleton
        import voltage_history

        voltage_history._voltage_history_manager = None

        manager1 = get_voltage_history_manager()
        manager2 = get_voltage_history_manager()

        assert manager1 is manager2


# ═══════════════════════════════════════════════════════════════════════════════
# EXTENDED TESTS FOR VOLTAGE HISTORY
# ═══════════════════════════════════════════════════════════════════════════════


class TestVoltageStatusExtended:
    """Extended tests for VoltageStatus"""

    def test_can_iterate_statuses(self):
        """Should iterate all statuses"""
        statuses = list(VoltageStatus)
        assert len(statuses) == 5

    def test_status_from_value(self):
        """Should create status from value"""
        status = VoltageStatus("NORMAL")
        assert status == VoltageStatus.NORMAL

    def test_status_comparison(self):
        """Statuses should be comparable"""
        assert VoltageStatus.NORMAL != VoltageStatus.LOW
        assert VoltageStatus.CRITICAL_LOW != VoltageStatus.CRITICAL_HIGH


class TestVoltageReadingExtended:
    """Extended tests for VoltageReading"""

    def test_reading_with_none_rpm(self):
        """Should handle None rpm"""
        reading = VoltageReading(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            voltage=12.5,
            rpm=None,
            engine_running=False,
            status=VoltageStatus.NORMAL,
        )
        assert reading.rpm is None

    def test_reading_equality(self):
        """Readings with same data should be equal"""
        now = datetime.now(timezone.utc)
        r1 = VoltageReading(
            truck_id="T001",
            timestamp=now,
            voltage=13.5,
            rpm=1500,
            engine_running=True,
            status=VoltageStatus.NORMAL,
        )
        r2 = VoltageReading(
            truck_id="T001",
            timestamp=now,
            voltage=13.5,
            rpm=1500,
            engine_running=True,
            status=VoltageStatus.NORMAL,
        )
        assert r1 == r2

    def test_reading_inequality_voltage(self):
        """Readings with different voltage should differ"""
        now = datetime.now(timezone.utc)
        r1 = VoltageReading(
            truck_id="T001",
            timestamp=now,
            voltage=13.5,
            rpm=1500,
            engine_running=True,
            status=VoltageStatus.NORMAL,
        )
        r2 = VoltageReading(
            truck_id="T001",
            timestamp=now,
            voltage=14.0,
            rpm=1500,
            engine_running=True,
            status=VoltageStatus.NORMAL,
        )
        assert r1 != r2

    def test_reading_preserves_timestamp(self):
        """Timestamp should be preserved"""
        specific = datetime(2025, 6, 15, 10, 30, tzinfo=timezone.utc)
        reading = VoltageReading(
            truck_id="T001",
            timestamp=specific,
            voltage=13.5,
            rpm=1500,
            engine_running=True,
            status=VoltageStatus.NORMAL,
        )
        assert reading.timestamp == specific


class TestVoltageClassificationExtended:
    """Extended tests for voltage classification"""

    @pytest.fixture
    def manager(self):
        with patch("voltage_history.get_db_connection"):
            return VoltageHistoryManager()

    def test_boundary_12_5_engine_on(self, manager):
        """Test boundary at 12.5V engine running"""
        assert manager._classify_voltage(12.49, True) == VoltageStatus.CRITICAL_LOW
        assert manager._classify_voltage(12.5, True) == VoltageStatus.LOW

    def test_boundary_13_2_engine_on(self, manager):
        """Test boundary at 13.2V engine running"""
        status = manager._classify_voltage(13.2, True)
        assert status == VoltageStatus.NORMAL

    def test_boundary_15_0_engine_on(self, manager):
        """Test boundary at 15.0V engine running"""
        status = manager._classify_voltage(15.01, True)
        assert status == VoltageStatus.HIGH

    def test_boundary_15_5_engine_on(self, manager):
        """Test boundary at 15.5V engine running"""
        status = manager._classify_voltage(15.51, True)
        assert status == VoltageStatus.CRITICAL_HIGH

    def test_boundary_11_5_engine_off(self, manager):
        """Test boundary at 11.5V engine off"""
        assert manager._classify_voltage(11.49, False) == VoltageStatus.CRITICAL_LOW
        assert manager._classify_voltage(11.5, False) == VoltageStatus.LOW

    def test_boundary_12_2_engine_off(self, manager):
        """Test boundary at 12.2V engine off"""
        status = manager._classify_voltage(12.2, False)
        assert status == VoltageStatus.NORMAL


class TestVoltageSamplingExtended:
    """Extended tests for sampling logic"""

    @pytest.fixture
    def manager(self):
        with patch("voltage_history.get_db_connection"):
            return VoltageHistoryManager()

    def test_sample_interval_constant(self, manager):
        """Sample interval should be 60 minutes"""
        assert manager.SAMPLE_INTERVAL_MINUTES == 60

    def test_last_sample_tracking(self, manager):
        """Should track last sample per truck"""
        now = datetime.now(timezone.utc)
        manager._last_sample["T001"] = now
        assert manager._last_sample["T001"] == now

    def test_separate_tracking(self, manager):
        """Each truck has separate tracking"""
        now = datetime.now(timezone.utc)
        manager._last_sample["T001"] = now
        manager._last_sample["T002"] = now - timedelta(hours=1)
        assert manager._last_sample["T001"] != manager._last_sample["T002"]


class TestVoltageHistoryTableConfig:
    """Tests for table configuration"""

    @pytest.fixture
    def manager(self):
        with patch("voltage_history.get_db_connection"):
            return VoltageHistoryManager()

    def test_table_name(self, manager):
        """Should have correct table name"""
        assert manager.TABLE_NAME == "voltage_history"


class TestVoltageManagerNoDatabase:
    """Tests for manager when database unavailable"""

    @pytest.fixture
    def manager(self):
        with patch("voltage_history.get_db_connection", return_value=None):
            return VoltageHistoryManager()

    def test_record_returns_false(self, manager):
        """Should return False when no database"""
        result = manager.record_voltage("T001", 13.5)
        assert result is False

    def test_get_history_returns_empty(self, manager):
        """Should return empty list when no database"""
        result = manager.get_history("T001")
        assert result == []


class TestEngineRunningLogic:
    """Tests for engine running detection logic"""

    @pytest.fixture
    def manager(self):
        with patch("voltage_history.get_db_connection"):
            return VoltageHistoryManager()

    def test_high_voltage_engine_on_normal(self, manager):
        """High voltage normal when engine on"""
        status = manager._classify_voltage(14.5, True)
        assert status == VoltageStatus.NORMAL

    def test_high_voltage_engine_off_abnormal(self, manager):
        """High voltage abnormal when engine off"""
        status = manager._classify_voltage(14.5, False)
        assert status == VoltageStatus.HIGH

    def test_battery_voltage_engine_off_normal(self, manager):
        """Battery voltage normal when engine off"""
        status = manager._classify_voltage(12.6, False)
        assert status == VoltageStatus.NORMAL


class TestVoltageReadingFields:
    """Tests for VoltageReading field types"""

    def test_voltage_is_float(self):
        """Voltage should be float"""
        reading = VoltageReading(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            voltage=13.5,
            rpm=1500,
            engine_running=True,
            status=VoltageStatus.NORMAL,
        )
        assert isinstance(reading.voltage, float)

    def test_engine_running_is_bool(self):
        """Engine running should be bool"""
        reading = VoltageReading(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            voltage=13.5,
            rpm=1500,
            engine_running=True,
            status=VoltageStatus.NORMAL,
        )
        assert isinstance(reading.engine_running, bool)

    def test_truck_id_is_string(self):
        """Truck ID should be string"""
        reading = VoltageReading(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            voltage=13.5,
            rpm=1500,
            engine_running=True,
            status=VoltageStatus.NORMAL,
        )
        assert isinstance(reading.truck_id, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
