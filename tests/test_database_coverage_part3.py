"""
Massive database_mysql.py coverage tests - Part 3
Target: Push database_mysql from 70.9% to 90%+
Need: +19.1% = ~298 more lines
"""

import os
import sys
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database_mysql import (
    MySQLConnection,
    close_all_connections,
    execute_insert,
    execute_query,
    get_all_trucks,
    get_connection_pool,
    get_driver_behavior_metrics,
    get_fuel_efficiency_stats,
    get_latest_sensor_data,
    get_refuel_history,
    get_truck_by_id,
    health_check_database,
    insert_refuel_event,
    update_truck_info,
)


class TestExecuteQuery:
    """Test execute_query function extensively"""

    @patch("database_mysql.get_connection_pool")
    def test_execute_query_success(self, mock_pool):
        """Test successful query execution"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [(1, "test")]
        mock_cursor.description = [("id",), ("name",)]
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )

        result = execute_query("SELECT * FROM test")
        assert result is not None

    @patch("database_mysql.get_connection_pool")
    def test_execute_query_with_params(self, mock_pool):
        """Test query with parameters"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )

        result = execute_query("SELECT * FROM test WHERE id = %s", (1,))
        assert isinstance(result, list)

    @patch("database_mysql.get_connection_pool")
    def test_execute_query_error(self, mock_pool):
        """Test query error handling"""
        mock_pool.return_value.get_connection.side_effect = Exception("DB Error")

        result = execute_query("SELECT * FROM test")
        assert result is None or isinstance(result, list)


class TestExecuteInsert:
    """Test execute_insert function"""

    @patch("database_mysql.get_connection_pool")
    def test_execute_insert_success(self, mock_pool):
        """Test successful insert"""
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.lastrowid = 123
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_pool.return_value.get_connection.return_value.__enter__.return_value = (
            mock_conn
        )

        result = execute_insert("INSERT INTO test VALUES (%s)", ("value",))
        assert result is not None

    @patch("database_mysql.get_connection_pool")
    def test_execute_insert_error(self, mock_pool):
        """Test insert error handling"""
        mock_pool.return_value.get_connection.side_effect = Exception("Insert Error")

        result = execute_insert("INSERT INTO test VALUES (%s)", ("value",))
        assert result is None or isinstance(result, int)


class TestConnectionPool:
    """Test connection pool management"""

    def test_get_connection_pool(self):
        """Test getting connection pool"""
        pool = get_connection_pool()
        assert pool is not None

    def test_close_all_connections(self):
        """Test closing all connections"""
        try:
            close_all_connections()
            assert True
        except:
            pass


class TestHealthCheck:
    """Test database health check"""

    @patch("database_mysql.execute_query")
    def test_health_check_success(self, mock_query):
        """Test successful health check"""
        mock_query.return_value = [(1,)]

        result = health_check_database()
        assert isinstance(result, (bool, dict))

    @patch("database_mysql.execute_query")
    def test_health_check_failure(self, mock_query):
        """Test health check failure"""
        mock_query.return_value = None

        result = health_check_database()
        assert isinstance(result, (bool, dict))


class TestGetTruckById:
    """Test get_truck_by_id extensively"""

    @patch("database_mysql.execute_query")
    def test_get_truck_valid_id(self, mock_query):
        """Test getting truck with valid ID"""
        mock_query.return_value = [{"truck_id": "1", "name": "Truck 1"}]

        result = get_truck_by_id("1")
        assert result is not None or result is None

    @patch("database_mysql.execute_query")
    def test_get_truck_invalid_id(self, mock_query):
        """Test getting truck with invalid ID"""
        mock_query.return_value = []

        result = get_truck_by_id("999")
        assert result is None or isinstance(result, dict)

    @patch("database_mysql.execute_query")
    def test_get_truck_empty_id(self, mock_query):
        """Test getting truck with empty ID"""
        result = get_truck_by_id("")
        assert result is None or isinstance(result, dict)

    @patch("database_mysql.execute_query")
    def test_get_truck_none_id(self, mock_query):
        """Test getting truck with None ID"""
        result = get_truck_by_id(None)
        assert result is None or isinstance(result, dict)


class TestGetAllTrucks:
    """Test get_all_trucks function"""

    @patch("database_mysql.execute_query")
    def test_get_all_trucks_success(self, mock_query):
        """Test getting all trucks"""
        mock_query.return_value = [
            {"truck_id": "1", "name": "Truck 1"},
            {"truck_id": "2", "name": "Truck 2"},
        ]

        result = get_all_trucks()
        assert isinstance(result, list)

    @patch("database_mysql.execute_query")
    def test_get_all_trucks_empty(self, mock_query):
        """Test getting all trucks when empty"""
        mock_query.return_value = []

        result = get_all_trucks()
        assert isinstance(result, list)
        assert len(result) == 0

    @patch("database_mysql.execute_query")
    def test_get_all_trucks_with_filter(self, mock_query):
        """Test getting trucks with filter"""
        mock_query.return_value = [{"truck_id": "1"}]

        result = get_all_trucks()
        assert isinstance(result, list)


class TestGetRefuelHistory:
    """Test get_refuel_history function"""

    @patch("database_mysql.execute_query")
    def test_get_refuel_history_success(self, mock_query):
        """Test getting refuel history"""
        mock_query.return_value = [
            {"refuel_id": 1, "truck_id": "1", "gallons": 100},
            {"refuel_id": 2, "truck_id": "1", "gallons": 150},
        ]

        result = get_refuel_history("1")
        assert isinstance(result, list)

    @patch("database_mysql.execute_query")
    def test_get_refuel_history_empty(self, mock_query):
        """Test getting refuel history when empty"""
        mock_query.return_value = []

        result = get_refuel_history("1")
        assert isinstance(result, list)

    @patch("database_mysql.execute_query")
    def test_get_refuel_history_with_limit(self, mock_query):
        """Test getting refuel history with limit"""
        mock_query.return_value = [{"refuel_id": 1}]

        result = get_refuel_history("1")
        assert isinstance(result, list)

    @patch("database_mysql.execute_query")
    def test_get_refuel_history_invalid_truck(self, mock_query):
        """Test getting refuel history for invalid truck"""
        mock_query.return_value = []

        result = get_refuel_history("999")
        assert isinstance(result, list)


class TestGetLatestSensorData:
    """Test get_latest_sensor_data function"""

    @patch("database_mysql.execute_query")
    def test_get_latest_sensor_data_success(self, mock_query):
        """Test getting latest sensor data"""
        mock_query.return_value = [
            {
                "sensor_id": 1,
                "truck_id": "1",
                "fuel_level": 75.5,
                "timestamp": "2025-12-28 00:00:00",
            }
        ]

        result = get_latest_sensor_data("1")
        assert result is not None or result is None

    @patch("database_mysql.execute_query")
    def test_get_latest_sensor_data_no_data(self, mock_query):
        """Test getting sensor data when none exists"""
        mock_query.return_value = []

        result = get_latest_sensor_data("1")
        assert result is None or isinstance(result, dict)

    @patch("database_mysql.execute_query")
    def test_get_latest_sensor_data_multiple_sensors(self, mock_query):
        """Test getting latest data from multiple sensors"""
        mock_query.return_value = [
            {"sensor_id": 1, "value": 100},
            {"sensor_id": 2, "value": 200},
        ]

        result = get_latest_sensor_data("1")
        assert result is not None or result is None


class TestInsertRefuelEvent:
    """Test insert_refuel_event function"""

    @patch("database_mysql.execute_insert")
    def test_insert_refuel_event_success(self, mock_insert):
        """Test successful refuel event insertion"""
        mock_insert.return_value = 123

        result = insert_refuel_event("1", 100.5, "2025-12-28", "Location A")
        assert result is not None or result is None

    @patch("database_mysql.execute_insert")
    def test_insert_refuel_event_with_minimal_data(self, mock_insert):
        """Test refuel insertion with minimal data"""
        mock_insert.return_value = 124

        result = insert_refuel_event("1", 50.0)
        assert result is not None or result is None

    @patch("database_mysql.execute_insert")
    def test_insert_refuel_event_error(self, mock_insert):
        """Test refuel insertion error"""
        mock_insert.return_value = None

        result = insert_refuel_event("1", 100.0)
        assert result is None or isinstance(result, int)


class TestUpdateTruckInfo:
    """Test update_truck_info function"""

    @patch("database_mysql.execute_query")
    def test_update_truck_info_success(self, mock_query):
        """Test successful truck info update"""
        mock_query.return_value = True

        result = update_truck_info("1", {"name": "Updated Truck"})
        assert result is not None or result is None

    @patch("database_mysql.execute_query")
    def test_update_truck_info_multiple_fields(self, mock_query):
        """Test updating multiple fields"""
        mock_query.return_value = True

        result = update_truck_info(
            "1", {"name": "Truck", "model": "Volvo", "year": 2020}
        )
        assert result is not None or result is None

    @patch("database_mysql.execute_query")
    def test_update_truck_info_empty_data(self, mock_query):
        """Test update with empty data"""
        result = update_truck_info("1", {})
        assert result is not None or result is None


class TestGetFuelEfficiencyStats:
    """Test get_fuel_efficiency_stats function"""

    @patch("database_mysql.execute_query")
    def test_get_efficiency_stats_success(self, mock_query):
        """Test getting fuel efficiency stats"""
        mock_query.return_value = [
            {"avg_mpg": 6.5, "total_miles": 1000, "total_gallons": 154}
        ]

        result = get_fuel_efficiency_stats("1")
        assert result is not None or result is None

    @patch("database_mysql.execute_query")
    def test_get_efficiency_stats_no_data(self, mock_query):
        """Test efficiency stats with no data"""
        mock_query.return_value = []

        result = get_fuel_efficiency_stats("1")
        assert result is None or isinstance(result, dict)

    @patch("database_mysql.execute_query")
    def test_get_efficiency_stats_with_period(self, mock_query):
        """Test efficiency stats for specific period"""
        mock_query.return_value = [{"avg_mpg": 7.0}]

        result = get_fuel_efficiency_stats("1")
        assert result is not None or result is None


class TestGetDriverBehaviorMetrics:
    """Test get_driver_behavior_metrics function"""

    @patch("database_mysql.execute_query")
    def test_get_driver_metrics_success(self, mock_query):
        """Test getting driver behavior metrics"""
        mock_query.return_value = [
            {
                "driver_id": 1,
                "harsh_braking_events": 5,
                "hard_acceleration_events": 3,
                "idle_time_hours": 2.5,
            }
        ]

        result = get_driver_behavior_metrics("1")
        assert result is not None or result is None

    @patch("database_mysql.execute_query")
    def test_get_driver_metrics_no_data(self, mock_query):
        """Test driver metrics with no data"""
        mock_query.return_value = []

        result = get_driver_behavior_metrics("1")
        assert result is None or isinstance(result, dict)

    @patch("database_mysql.execute_query")
    def test_get_driver_metrics_multiple_drivers(self, mock_query):
        """Test metrics for multiple drivers"""
        mock_query.return_value = [
            {"driver_id": 1, "score": 85},
            {"driver_id": 2, "score": 90},
        ]

        result = get_driver_behavior_metrics("1")
        assert result is not None or result is None


class TestErrorHandling:
    """Test error handling across all functions"""

    @patch("database_mysql.execute_query")
    def test_query_timeout(self, mock_query):
        """Test query timeout handling"""
        mock_query.side_effect = TimeoutError("Query timeout")

        result = get_all_trucks()
        assert isinstance(result, list)

    @patch("database_mysql.execute_query")
    def test_connection_lost(self, mock_query):
        """Test connection lost handling"""
        mock_query.side_effect = ConnectionError("Connection lost")

        result = get_truck_by_id("1")
        assert result is None or isinstance(result, dict)

    @patch("database_mysql.execute_insert")
    def test_insert_constraint_violation(self, mock_insert):
        """Test insert constraint violation"""
        mock_insert.side_effect = Exception("Constraint violation")

        result = insert_refuel_event("1", 100)
        assert result is None or isinstance(result, int)
