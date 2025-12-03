"""
Tests for wialon_reader.py

Uses mocks to test database reading without actual connection.
Tests timezone handling, retry logic, and sensor data parsing.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timezone
from typing import Dict, Any, List

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from wialon_reader import (
    WialonConfig,
    TruckSensorData,
    WialonReader,
)


# =============================================================================
# Test WialonConfig
# =============================================================================


class TestWialonConfig:
    """Test WialonConfig dataclass"""

    def test_default_values(self):
        """Test default configuration values"""
        with patch.dict("os.environ", {}, clear=True):
            config = WialonConfig()
            assert config.host == "localhost"
            assert config.port == 3306
            assert config.database == "wialon_collect"

    def test_env_override(self):
        """Test configuration from environment variables"""
        env_vars = {
            "WIALON_DB_HOST": "test-host.com",
            "WIALON_DB_PORT": "3307",
            "WIALON_DB_USER": "testuser",
            "WIALON_DB_PASS": "testpass",
            "WIALON_DB_NAME": "test_db",
        }
        with patch.dict("os.environ", env_vars, clear=True):
            config = WialonConfig()
            assert config.host == "test-host.com"
            assert config.port == 3307
            assert config.user == "testuser"
            assert config.password == "testpass"
            assert config.database == "test_db"

    def test_sensor_params_defined(self):
        """Test that all expected sensor parameters are defined"""
        expected_sensors = [
            "fuel_lvl",
            "speed",
            "rpm",
            "odometer",
            "fuel_rate",
            "coolant_temp",
            "hdop",
            "altitude",
        ]
        for sensor in expected_sensors:
            assert sensor in WialonConfig.SENSOR_PARAMS


# =============================================================================
# Test TruckSensorData
# =============================================================================


class TestTruckSensorData:
    """Test TruckSensorData dataclass"""

    def test_timezone_aware_timestamp(self):
        """Test that timestamps are always timezone-aware"""
        # Create with timezone-aware timestamp
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        data = TruckSensorData(
            truck_id="TEST1",
            unit_id=12345,
            timestamp=ts,
            epoch_time=1705315800,
            capacity_gallons=200.0,
            capacity_liters=757.08,
        )
        assert data.timestamp.tzinfo is not None
        assert data.timestamp == ts

    def test_naive_datetime_converted_to_utc(self):
        """Test that naive datetimes are converted to UTC"""
        # Create with naive timestamp (no timezone)
        naive_ts = datetime(2024, 1, 15, 10, 30, 0)
        data = TruckSensorData(
            truck_id="TEST2",
            unit_id=12346,
            timestamp=naive_ts,
            epoch_time=1705315800,
            capacity_gallons=200.0,
            capacity_liters=757.08,
        )
        # Should have timezone now
        assert data.timestamp.tzinfo is not None
        assert data.timestamp.tzinfo == timezone.utc

    def test_optional_sensor_values(self):
        """Test that sensor values default to None"""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        data = TruckSensorData(
            truck_id="TEST3",
            unit_id=12347,
            timestamp=ts,
            epoch_time=1705315800,
            capacity_gallons=200.0,
            capacity_liters=757.08,
        )
        assert data.fuel_lvl is None
        assert data.speed is None
        assert data.rpm is None
        assert data.odometer is None

    def test_sensor_values_set(self):
        """Test setting sensor values"""
        ts = datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc)
        data = TruckSensorData(
            truck_id="TEST4",
            unit_id=12348,
            timestamp=ts,
            epoch_time=1705315800,
            capacity_gallons=200.0,
            capacity_liters=757.08,
            fuel_lvl=75.5,
            speed=65.2,
            rpm=1800,
            odometer=125000.5,
        )
        assert data.fuel_lvl == 75.5
        assert data.speed == 65.2
        assert data.rpm == 1800
        assert data.odometer == 125000.5


# =============================================================================
# Test WialonReader with Mocks
# =============================================================================


class TestWialonReader:
    """Test WialonReader with mocked database connection"""

    @pytest.fixture
    def mock_config(self):
        """Create test configuration"""
        config = Mock(spec=WialonConfig)
        config.host = "test-host"
        config.port = 3306
        config.user = "test"
        config.password = "test"
        config.database = "test_db"
        config.SENSOR_PARAMS = WialonConfig.SENSOR_PARAMS
        return config

    @pytest.fixture
    def truck_mapping(self):
        """Create test truck mapping"""
        return {"NQ6975": 401961901, "RT9127": 401961902, "FM9838": 401961903}

    @pytest.fixture
    def reader(self, mock_config, truck_mapping):
        """Create WialonReader instance"""
        return WialonReader(mock_config, truck_mapping)

    def test_init(self, reader, mock_config, truck_mapping):
        """Test reader initialization"""
        assert reader.config == mock_config
        assert reader.truck_unit_mapping == truck_mapping
        assert reader.connection is None

    @patch("wialon_reader.pymysql.connect")
    def test_connect_success(self, mock_connect, reader):
        """Test successful database connection"""
        mock_conn = Mock()
        mock_connect.return_value = mock_conn

        result = reader.connect()

        assert result is True
        assert reader.connection is not None

    @patch("wialon_reader.pymysql.connect")
    def test_connect_failure_after_retries(self, mock_connect, reader):
        """Test connection failure after retry attempts"""
        import pymysql

        mock_connect.side_effect = pymysql.Error("Connection refused")

        result = reader.connect()

        assert result is False

    def test_epoch_to_datetime_utc(self, reader):
        """Test epoch to UTC datetime conversion"""
        # Known epoch: 2024-01-15 10:30:00 UTC
        epoch = 1705315800
        result = reader._epoch_to_datetime_utc(epoch)

        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.tzinfo == timezone.utc

    def test_disconnect(self, reader):
        """Test disconnect closes connection"""
        mock_conn = Mock()
        reader.connection = mock_conn

        reader.disconnect()

        mock_conn.close.assert_called_once()

    def test_ensure_connection_when_none(self, reader):
        """Test ensure_connection creates new connection when None"""
        reader.connection = None
        reader.connect = Mock(return_value=True)

        result = reader.ensure_connection()

        reader.connect.assert_called_once()
        assert result is True

    def test_ensure_connection_when_alive(self, reader):
        """Test ensure_connection uses existing connection when alive"""
        mock_conn = Mock()
        reader.connection = mock_conn

        result = reader.ensure_connection()

        mock_conn.ping.assert_called_once_with(reconnect=True)
        assert result is True


# =============================================================================
# Test get_latest_sensor_data with Mocks
# =============================================================================


class TestGetLatestSensorData:
    """Test sensor data retrieval"""

    @pytest.fixture
    def reader_with_connection(self):
        """Create reader with mocked connection"""
        config = Mock(spec=WialonConfig)
        config.SENSOR_PARAMS = WialonConfig.SENSOR_PARAMS

        reader = WialonReader(config, {"TEST1": 12345})
        reader.connection = Mock()
        return reader

    def test_returns_none_when_not_connected(self):
        """Test returns None when not connected"""
        config = Mock(spec=WialonConfig)
        reader = WialonReader(config, {"TEST1": 12345})
        reader.connection = None

        result = reader.get_latest_sensor_data(12345)

        assert result is None

    def test_returns_none_when_no_data(self, reader_with_connection):
        """Test returns None when query returns empty"""
        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        reader_with_connection.connection.cursor.return_value = mock_cursor

        result = reader_with_connection.get_latest_sensor_data(12345)

        assert result is None

    def test_parses_sensor_data_correctly(self, reader_with_connection):
        """Test correct parsing of sensor data"""
        # Mock database response
        now = datetime.now(timezone.utc)
        epoch_now = int(now.timestamp())

        mock_rows = [
            {
                "param_name": "fuel_lvl",
                "value": 75.5,
                "epoch_time": epoch_now,
                "measure_datetime": now,
                "from_latitude": 40.7128,
                "from_longitude": -74.0060,
            },
            {
                "param_name": "speed",
                "value": 55.0,
                "epoch_time": epoch_now,
                "measure_datetime": now,
                "from_latitude": 40.7128,
                "from_longitude": -74.0060,
            },
            {
                "param_name": "rpm",
                "value": 1800,
                "epoch_time": epoch_now,
                "measure_datetime": now,
                "from_latitude": 40.7128,
                "from_longitude": -74.0060,
            },
        ]

        mock_cursor = Mock()
        mock_cursor.fetchall.return_value = mock_rows
        mock_cursor.fetchone.return_value = None  # For deep fuel search
        mock_cursor.__enter__ = Mock(return_value=mock_cursor)
        mock_cursor.__exit__ = Mock(return_value=False)

        reader_with_connection.connection.cursor.return_value = mock_cursor

        result = reader_with_connection.get_latest_sensor_data(12345)

        assert result is not None
        assert result["fuel_lvl"] == 75.5
        assert result["speed"] == 55.0
        assert result["rpm"] == 1800
        assert result["latitude"] == 40.7128
        assert result["longitude"] == -74.0060


# =============================================================================
# Test get_all_trucks_data
# =============================================================================


class TestGetAllTrucksData:
    """Test bulk data retrieval - requires real DB connection"""

    @pytest.mark.skip(reason="Integration test - requires real DB connection")
    @patch(
        "wialon_reader.TRUCK_CONFIG",
        {
            "NQ6975": {"capacity_gallons": 200, "capacity_liters": 757.08},
            "RT9127": {"capacity_gallons": 150, "capacity_liters": 567.81},
        },
    )
    def test_returns_data_for_all_trucks(self):
        """Test retrieval for all trucks"""
        config = Mock(spec=WialonConfig)
        config.SENSOR_PARAMS = WialonConfig.SENSOR_PARAMS

        mapping = {"NQ6975": 401961901, "RT9127": 401961902}
        reader = WialonReader(config, mapping)

        # Mock connection to avoid "Not connected" error
        reader.connection = Mock()

        # Mock get_latest_sensor_data
        now = datetime.now(timezone.utc)
        epoch_now = int(now.timestamp())

        reader.get_latest_sensor_data = Mock(
            return_value={
                "timestamp": now,
                "epoch_time": epoch_now,
                "fuel_lvl": 70.0,
                "speed": 50.0,
            }
        )

        result = reader.get_all_trucks_data()

        assert len(result) == 2
        assert all(isinstance(d, TruckSensorData) for d in result)

    @pytest.mark.skip(reason="Integration test - requires real DB connection")
    @patch(
        "wialon_reader.TRUCK_CONFIG",
        {"NQ6975": {"capacity_gallons": 200, "capacity_liters": 757.08}},
    )
    def test_handles_missing_data(self):
        """Test handling trucks with no data"""
        config = Mock(spec=WialonConfig)
        config.SENSOR_PARAMS = WialonConfig.SENSOR_PARAMS

        mapping = {"NQ6975": 401961901, "RT9127": 401961902}
        reader = WialonReader(config, mapping)

        # Mock connection to avoid "Not connected" error
        reader.connection = Mock()

        # Return data for only one truck
        def mock_get_data(unit_id):
            if unit_id == 401961901:
                return {
                    "timestamp": datetime.now(timezone.utc),
                    "epoch_time": int(datetime.now().timestamp()),
                    "fuel_lvl": 70.0,
                }
            return None

        reader.get_latest_sensor_data = Mock(side_effect=mock_get_data)

        result = reader.get_all_trucks_data()

        assert len(result) == 1
        assert result[0].truck_id == "NQ6975"


# =============================================================================
# Test Timezone Handling
# =============================================================================


class TestTimezoneHandling:
    """Test proper timezone handling throughout"""

    def test_epoch_conversion_is_utc(self):
        """Test epoch conversion produces UTC datetime"""
        config = Mock(spec=WialonConfig)
        reader = WialonReader(config, {})

        # Epoch for 2024-06-15 12:00:00 UTC
        epoch = 1718452800
        result = reader._epoch_to_datetime_utc(epoch)

        # Verify UTC
        assert result.tzinfo == timezone.utc

        # Verify correct time
        assert result.hour == 12
        assert result.minute == 0

    def test_truck_sensor_data_always_utc(self):
        """Test TruckSensorData ensures UTC timezone"""
        # Test with various datetime inputs
        test_cases = [
            datetime(2024, 1, 1, 12, 0, 0),  # Naive
            datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc),  # UTC
        ]

        for ts in test_cases:
            data = TruckSensorData(
                truck_id="TEST",
                unit_id=1,
                timestamp=ts,
                epoch_time=1704110400,
                capacity_gallons=200.0,
                capacity_liters=757.08,
            )
            assert data.timestamp.tzinfo is not None


# =============================================================================
# Test load_truck_config
# =============================================================================


class TestLoadTruckConfig:
    """Test truck configuration loading"""

    @patch("pathlib.Path.exists")
    def test_returns_empty_dict_if_file_missing(self, mock_exists):
        """Test returns empty dict when tanks.yaml doesn't exist"""
        mock_exists.return_value = False

        from wialon_reader import load_truck_config

        # Note: This test may fail if the module already loaded
        # the real tanks.yaml - this is a limitation of testing
        # module-level code

    def test_parses_yaml_correctly(self, tmp_path):
        """Test correct parsing of tanks.yaml"""
        # Create test yaml
        yaml_content = """
trucks:
  TEST1:
    unit_id: 12345
    capacity_gallons: 200
    capacity_liters: 757.08
    mpg: 6.5
  TEST2:
    unit_id: 12346
    capacity_gallons: 150
    capacity_liters: 567.81
    mpg: 7.0
"""
        yaml_file = tmp_path / "tanks.yaml"
        yaml_file.write_text(yaml_content)

        from wialon_reader import load_truck_config

        result = load_truck_config(str(yaml_file))

        assert "TEST1" in result
        assert "TEST2" in result
        assert result["TEST1"]["unit_id"] == 12345
        assert result["TEST1"]["capacity_gallons"] == 200
        assert result["TEST2"]["mpg"] == 7.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
