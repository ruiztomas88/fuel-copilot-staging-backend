"""
Database fixtures for testing
"""

from unittest.mock import MagicMock, patch

import pytest
from mysql.connector import pooling


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = None
    mock_cursor.rowcount = 0
    return mock_conn


@pytest.fixture
def mock_db_pool():
    """Mock database connection pool"""
    mock_pool = MagicMock(spec=pooling.MySQLConnectionPool)
    mock_conn = MagicMock()
    mock_cursor = MagicMock()
    mock_conn.cursor.return_value = mock_cursor
    mock_cursor.fetchall.return_value = []
    mock_cursor.fetchone.return_value = None
    mock_pool.get_connection.return_value = mock_conn
    return mock_pool


@pytest.fixture
def sample_truck_row():
    """Sample truck data row from database"""
    return {
        "truck_id": "RA1234",
        "unit_id": 1234,
        "truck_status": "MOVING",
        "speed_mph": 65.5,
        "fuel_pct": 75.3,
        "fuel_gallons": 150.6,
        "mpg_current": 6.2,
        "consumption_lph": 15.5,
        "rpm": 1450,
        "coolant_temp_f": 195,
        "oil_pressure_psi": 45,
        "last_updated": "2025-12-25 10:30:00",
    }


@pytest.fixture
def sample_sensor_row():
    """Sample sensor data row"""
    return {
        "truck_id": "RA1234",
        "sensor_name": "Oil Pressure",
        "sensor_value": 45.5,
        "unit": "PSI",
        "timestamp": "2025-12-25 10:30:00",
        "is_valid": True,
    }


@pytest.fixture
def sample_dtc_row():
    """Sample DTC row"""
    return {
        "truck_id": "RA1234",
        "dtc_code": "P0128",
        "description": "Coolant Thermostat Temperature Below Regulating Temperature",
        "status": "active",
        "first_seen": "2025-12-24 08:00:00",
        "last_seen": "2025-12-25 10:30:00",
        "count": 5,
    }
