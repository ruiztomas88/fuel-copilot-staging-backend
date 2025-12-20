"""
Comprehensive tests for WialonDataLoader
Target: 32% -> 89%+ coverage (211 missed lines)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import yaml


@pytest.fixture
def mock_mysql():
    """Mock mysql.connector"""
    with patch('wialon_data_loader.mysql') as mock:
        yield mock


@pytest.fixture
def temp_tanks_config():
    """Create temporary tanks.yaml"""
    config = {
        "trucks": {
            "FF7702": {"unit_id": 1234, "capacity_liters": 757},
            "DO9693": {"unit_id": 5678, "capacity_liters": 757},
        }
    }
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        yield f.name
    Path(f.name).unlink(missing_ok=True)


class TestWialonDataLoaderInit:
    """Test initialization and configuration"""

    def test_init_loads_tanks_config(self, temp_tanks_config):
        """Should load tanks configuration on init"""
        from wialon_data_loader import WialonDataLoader
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        assert 1234 in loader._truck_mapping
        assert loader._truck_mapping[1234] == "FF7702"
        assert 5678 in loader._truck_mapping
        assert loader._truck_mapping[5678] == "DO9693"

    def test_init_with_missing_config(self):
        """Should handle missing config file gracefully"""
        from wialon_data_loader import WialonDataLoader
        
        loader = WialonDataLoader(tanks_config_path="nonexistent.yaml")
        assert len(loader._truck_mapping) == 0

    def test_get_truck_id(self, temp_tanks_config):
        """Should map unit_id to truck_id"""
        from wialon_data_loader import WialonDataLoader
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        assert loader.get_truck_id(1234) == "FF7702"
        assert loader.get_truck_id(5678) == "DO9693"
        assert loader.get_truck_id(9999) == "UNIT_9999"

    def test_get_unit_id(self, temp_tanks_config):
        """Should map truck_id to unit_id"""
        from wialon_data_loader import WialonDataLoader
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        assert loader.get_unit_id("FF7702") == 1234
        assert loader.get_unit_id("DO9693") == 5678
        assert loader.get_unit_id("UNKNOWN") is None


class TestWialonConnection:
    """Test database connection management"""

    @patch('mysql.connector.connect')
    def test_connect_success(self, mock_connect, temp_tanks_config):
        """Should connect successfully"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        result = loader.connect()
        
        assert result is True
        assert loader.is_connected() is True
        mock_connect.assert_called_once()

    @patch('mysql.connector.connect')
    def test_connect_failure(self, mock_connect, temp_tanks_config):
        """Should handle connection failure"""
        from wialon_data_loader import WialonDataLoader
        
        mock_connect.side_effect = Exception("Connection failed")
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        result = loader.connect()
        
        assert result is False
        assert loader.is_connected() is False

    @patch('mysql.connector.connect')
    def test_disconnect(self, mock_connect, temp_tanks_config):
        """Should disconnect properly"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        loader.disconnect()
        
        assert loader.is_connected() is False
        mock_conn.close.assert_called_once()

    @patch('mysql.connector.connect')
    def test_is_connected_checks_ping(self, mock_connect, temp_tanks_config):
        """Should ping database to check connection"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        # Successful ping
        mock_conn.ping.return_value = None
        assert loader.is_connected() is True
        
        # Failed ping
        mock_conn.ping.side_effect = Exception("Lost connection")
        assert loader.is_connected() is False


class TestWialonCaching:
    """Test caching functionality"""

    def test_cache_key_generation(self, temp_tanks_config):
        """Should generate unique cache keys"""
        from wialon_data_loader import WialonDataLoader, DataType
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        key1 = loader._get_cache_key(DataType.DEF_LEVELS, days=30)
        key2 = loader._get_cache_key(DataType.DEF_LEVELS, days=7)
        key3 = loader._get_cache_key(DataType.SENSOR_DATA, sensor="fuel", days=30)
        
        assert key1 != key2
        assert key1 != key3
        assert "def_levels" in key1

    def test_set_and_get_cache(self, temp_tanks_config):
        """Should cache and retrieve data"""
        from wialon_data_loader import WialonDataLoader
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        test_data = [{"id": 1}, {"id": 2}]
        cache_key = "test_key"
        
        loader._set_cache(cache_key, test_data, ttl_minutes=5)
        retrieved = loader._get_from_cache(cache_key)
        
        assert retrieved == test_data

    def test_cache_expiration(self, temp_tanks_config):
        """Should expire old cache entries"""
        from wialon_data_loader import WialonDataLoader
        from datetime import datetime, timedelta
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        test_data = [{"id": 1}]
        cache_key = "test_key"
        
        # Set with very short TTL
        loader._set_cache(cache_key, test_data, ttl_minutes=0)
        
        # Manually expire
        with loader._lock:
            loader._cache[cache_key].expires_at = datetime.now() - timedelta(minutes=1)
        
        retrieved = loader._get_from_cache(cache_key)
        assert retrieved is None

    def test_clear_cache(self, temp_tanks_config):
        """Should clear all cache entries"""
        from wialon_data_loader import WialonDataLoader
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        loader._set_cache("key1", [1, 2, 3])
        loader._set_cache("key2", [4, 5, 6])
        
        assert len(loader._cache) == 2
        
        loader.clear_cache()
        
        assert len(loader._cache) == 0

    def test_get_cache_status(self, temp_tanks_config):
        """Should return cache status"""
        from wialon_data_loader import WialonDataLoader
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        loader._set_cache("key1", [1, 2, 3])
        loader._set_cache("key2", [4, 5])
        
        status = loader.get_cache_status()
        
        assert status["entries"] == 2
        assert status["total_records"] == 5
        assert "key1" in status["details"]
        assert status["details"]["key1"]["records"] == 3


class TestWialonDataLoading:
    """Test data loading methods"""

    @patch('mysql.connector.connect')
    def test_load_def_data_success(self, mock_connect, temp_tanks_config):
        """Should load DEF data from database"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        # Setup connection
        mock_cursor.fetchone.return_value = (1,)  # For connection test
        mock_connect.return_value = mock_conn
        
        # Setup DEF data query
        def_rows = [
            {"timestamp": datetime.now(), "unit_id": 1234, "def_level": 75.5, "odometer": 50000, "engine_hours": 1500},
            {"timestamp": datetime.now(), "unit_id": 5678, "def_level": 60.2, "odometer": 45000, "engine_hours": 1400},
        ]
        
        mock_cursor.fetchall.side_effect = [(1,), def_rows]  # First for test, second for data
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        result = loader.load_def_data(days=30)
        
        assert len(result) == 2
        assert result[0]["truck_id"] == "FF7702"
        assert result[1]["truck_id"] == "DO9693"

    @patch('mysql.connector.connect')
    def test_load_def_data_uses_cache(self, mock_connect, temp_tanks_config):
        """Should use cached DEF data"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        # Pre-populate cache
        cached_data = [{"id": 1, "cached": True}]
        from wialon_data_loader import DataType
        cache_key = loader._get_cache_key(DataType.DEF_LEVELS, days=30)
        loader._set_cache(cache_key, cached_data)
        
        result = loader.load_def_data(days=30, force_refresh=False)
        
        assert result == cached_data
        # Should not connect to database
        mock_connect.assert_not_called()

    @patch('mysql.connector.connect')
    def test_load_sensor_data_generic(self, mock_connect, temp_tanks_config):
        """Should load generic sensor data"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        
        sensor_rows = [
            {"timestamp": datetime.now(), "unit_id": 1234, "fuel_lvl": 50.5, "odometer": 50000, "engine_hours": 1500, "lat": 25.5, "lon": -100.5},
        ]
        
        mock_cursor.fetchall.side_effect = [(1,), sensor_rows]
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        result = loader.load_sensor_data("fuel_lvl", days=30)
        
        assert len(result) == 1
        assert result[0]["truck_id"] == "FF7702"

    @patch('mysql.connector.connect')
    def test_load_sensor_data_with_unit_filter(self, mock_connect, temp_tanks_config):
        """Should filter by specific unit_id"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        
        mock_cursor.fetchall.side_effect = [(1,), []]
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        result = loader.load_sensor_data("oil_press", days=30, unit_id=1234)
        
        assert isinstance(result, list)

    @patch('mysql.connector.connect')
    def test_load_events(self, mock_connect, temp_tanks_config):
        """Should load events"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        
        event_rows = [
            {"timestamp": datetime.now(), "unit_id": 1234, "event_id": 10, "event_value": "test", "lat": 25, "lon": -100, "speed": 50},
        ]
        
        mock_cursor.fetchall.side_effect = [(1,), event_rows]
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        result = loader.load_events(days=30)
        
        assert len(result) == 1
        assert result[0]["truck_id"] == "FF7702"

    @patch('mysql.connector.connect')
    def test_load_events_with_filter(self, mock_connect, temp_tanks_config):
        """Should filter events by ID"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        mock_cursor.fetchall.side_effect = [(1,), []]
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        result = loader.load_events(event_ids=[24, 25], days=30)
        
        assert isinstance(result, list)

    @patch('mysql.connector.connect')
    def test_load_speedings(self, mock_connect, temp_tanks_config):
        """Should load speeding records"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        
        speeding_rows = [
            {"timestamp": datetime.now(), "unit_id": 1234, "max_speed": 75, "duration_seconds": 120, "distance_meters": 500, "lat": 25, "lon": -100},
        ]
        
        mock_cursor.fetchall.side_effect = [(1,), speeding_rows]
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        result = loader.load_speedings(days=30)
        
        assert len(result) == 1
        assert result[0]["truck_id"] == "FF7702"

    @patch('mysql.connector.connect')
    def test_load_dtc_events(self, mock_connect, temp_tanks_config):
        """Should load DTC events"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        
        # Two fetchall calls: one for events, one for sensor data
        dtc_sensor_rows = [
            {"timestamp": datetime.now(), "unit_id": 1234, "j1939_spn": 94, "j1939_fmi": 1, "engine_hours": 1500},
        ]
        
        mock_cursor.fetchall.side_effect = [(1,), [], dtc_sensor_rows]
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        result = loader.load_dtc_events(days=30)
        
        assert isinstance(result, list)

    @patch('mysql.connector.connect')
    def test_load_not_connected(self, mock_connect, temp_tanks_config):
        """Should return empty list if not connected"""
        from wialon_data_loader import WialonDataLoader
        
        mock_connect.side_effect = Exception("No connection")
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        result = loader.load_def_data(days=30)
        assert result == []
        
        result = loader.load_sensor_data("fuel", days=30)
        assert result == []
        
        result = loader.load_events(days=30)
        assert result == []
        
        result = loader.load_speedings(days=30)
        assert result == []


class TestWialonSubscriptions:
    """Test subscription/notification system"""

    def test_subscribe_to_data_type(self, temp_tanks_config):
        """Should register subscriber callback"""
        from wialon_data_loader import WialonDataLoader, DataType
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        callback = Mock()
        loader.subscribe(DataType.DEF_LEVELS, callback)
        
        assert DataType.DEF_LEVELS in loader._subscribers
        assert callback in loader._subscribers[DataType.DEF_LEVELS]

    def test_notify_subscribers(self, temp_tanks_config):
        """Should notify all subscribers"""
        from wialon_data_loader import WialonDataLoader, DataType
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        callback1 = Mock()
        callback2 = Mock()
        
        loader.subscribe(DataType.DEF_LEVELS, callback1)
        loader.subscribe(DataType.DEF_LEVELS, callback2)
        
        test_data = [{"test": "data"}]
        loader._notify_subscribers(DataType.DEF_LEVELS, test_data)
        
        callback1.assert_called_once_with(test_data)
        callback2.assert_called_once_with(test_data)

    def test_notify_handles_callback_errors(self, temp_tanks_config):
        """Should handle errors in callbacks gracefully"""
        from wialon_data_loader import WialonDataLoader, DataType
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        failing_callback = Mock(side_effect=Exception("Callback error"))
        working_callback = Mock()
        
        loader.subscribe(DataType.EVENTS, failing_callback)
        loader.subscribe(DataType.EVENTS, working_callback)
        
        loader._notify_subscribers(DataType.EVENTS, [])
        
        # Working callback should still be called
        working_callback.assert_called_once()


class TestWialonInventory:
    """Test data inventory functionality"""

    @patch('mysql.connector.connect')
    def test_get_data_inventory_not_connected(self, mock_connect, temp_tanks_config):
        """Should handle no connection"""
        from wialon_data_loader import WialonDataLoader
        
        mock_connect.side_effect = Exception("No connection")
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        
        inventory = loader.get_data_inventory()
        
        assert "error" in inventory

    @patch('mysql.connector.connect')
    def test_get_data_inventory_success(self, mock_connect, temp_tanks_config):
        """Should return inventory data"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.side_effect = [(1,), (100,), (200,), (50,), (80,), (120,), (90,), (150,), (180,), (500,)]
        mock_cursor.fetchall.return_value = [(24, 50), (25, 30)]
        mock_connect.return_value = mock_conn
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        inventory = loader.get_data_inventory()
        
        assert "connection" in inventory
        assert "sensors" in inventory
        assert "events" in inventory
        assert inventory["trucks_configured"] == 2


class TestWialonAllDataLoading:
    """Test load_all_for_analytics"""

    @patch('mysql.connector.connect')
    def test_load_all_for_analytics(self, mock_connect, temp_tanks_config):
        """Should load all data types"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_connect.return_value = mock_conn
        
        # Return different data for each query
        mock_cursor.fetchall.side_effect = [
            (1,),  # Connection test
            [{"unit_id": 1234, "def_level": 75}],  # DEF
            [{"unit_id": 1234, "fuel_lvl": 50}],  # Fuel
            [{"unit_id": 1234, "oil_press": 40}],  # Oil
            [{"unit_id": 1234, "cool_temp": 180}],  # Coolant
            [],  # Events query 1
            [],  # Events query 2
            [],  # Speedings
            [], [], []  # DTC events/sensor
        ]
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        results = loader.load_all_for_analytics(days=30)
        
        assert "def_readings" in results
        assert "fuel_readings" in results
        assert "oil_pressure_readings" in results
        assert "coolant_temp_readings" in results
        assert "events" in results
        assert "speedings" in results
        assert "dtc_records" in results


class TestWialonErrorHandling:
    """Test error handling"""

    @patch('mysql.connector.connect')
    def test_load_def_data_query_error(self, mock_connect, temp_tanks_config):
        """Should handle query errors gracefully"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_cursor.execute.side_effect = [None, Exception("Query error")]
        mock_connect.return_value = mock_conn
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        result = loader.load_def_data(days=30, force_refresh=True)
        
        assert result == []

    @patch('mysql.connector.connect')
    def test_disconnect_with_error(self, mock_connect, temp_tanks_config):
        """Should handle disconnect errors"""
        from wialon_data_loader import WialonDataLoader
        
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (1,)
        mock_conn.close.side_effect = Exception("Close error")
        mock_connect.return_value = mock_conn
        
        loader = WialonDataLoader(tanks_config_path=temp_tanks_config)
        loader.connect()
        
        # Should not raise exception
        loader.disconnect()
        
        assert loader.is_connected() is False
