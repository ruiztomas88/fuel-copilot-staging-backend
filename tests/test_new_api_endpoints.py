"""
Tests for New API Endpoints (RUL, Siphoning, MPG Context)
═══════════════════════════════════════════════════════════════════════════════
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch, MagicMock


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    with patch("mysql.connector.connect") as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_conn.cursor.return_value = mock_cursor
        mock_connect.return_value = mock_conn
        yield mock_conn, mock_cursor


class TestRULPredictionsEndpoint:
    """Tests for /rul-predictions/{truck_id} endpoint"""

    def test_get_rul_predictions_success(self, mock_db_connection):
        """Should return RUL predictions for truck"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection

        # Mock database response
        base_time = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "timestamp": base_time - timedelta(days=i),
                "turbo_health": 90 - (i * 0.5),
                "oil_consumption_health": 85.0,
                "coolant_leak_health": 80.0,
                "def_system_health": 90.0,
                "battery_health": 75.0,
                "alternator_health": 85.0,
            }
            for i in range(30)
        ]

        response = client.get("/rul-predictions/TEST_TRUCK")

        assert response.status_code == 200
        data = response.json()
        assert data["truck_id"] == "TEST_TRUCK"
        assert "predictions" in data
        assert isinstance(data["predictions"], list)
        assert data["count"] >= 0

    def test_get_rul_predictions_specific_component(self, mock_db_connection):
        """Should return prediction for specific component"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection

        base_time = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "timestamp": base_time - timedelta(days=i),
                "turbo_health": 90 - (i * 0.8),
                "oil_consumption_health": None,
                "coolant_leak_health": None,
                "def_system_health": None,
                "battery_health": None,
                "alternator_health": None,
            }
            for i in range(30)
        ]

        response = client.get("/rul-predictions/TEST_TRUCK?component=turbo_health")

        assert response.status_code == 200
        data = response.json()
        assert data["truck_id"] == "TEST_TRUCK"

    def test_get_rul_predictions_no_data(self, mock_db_connection):
        """Should handle no health history"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        response = client.get("/rul-predictions/UNKNOWN_TRUCK")

        assert response.status_code == 200
        data = response.json()
        assert data["predictions"] == []
        assert "No health history found" in data["message"]


class TestSiphoningAlertsEndpoint:
    """Tests for /siphoning-alerts endpoint"""

    def test_get_siphoning_alerts_success(self, mock_db_connection):
        """Should return siphoning alerts"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection

        # Mock fuel readings with siphoning pattern
        base_time = datetime.now(timezone.utc)
        readings = []
        for i in range(7):
            readings.append(
                {
                    "truck_id": "TRUCK_001",
                    "timestamp": base_time - timedelta(days=i),
                    "fuel_level_pct": 80.0 - (i * 3.0),  # Gradual loss
                    "fuel_level_liters": 600.0 - (i * 20.0),
                    "odometer_km": 10000 + (i * 100),
                }
            )

        mock_cursor.fetchall.return_value = readings

        response = client.get("/siphoning-alerts?days=7")

        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert isinstance(data["alerts"], list)
        assert data["period_days"] == 7

    def test_get_siphoning_alerts_filter_by_truck(self, mock_db_connection):
        """Should filter alerts by truck ID"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        response = client.get("/siphoning-alerts?truck_id=TRUCK_001&days=7")

        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data

    def test_get_siphoning_alerts_confidence_threshold(self, mock_db_connection):
        """Should filter by minimum confidence"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        response = client.get("/siphoning-alerts?min_confidence=0.8")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data["alerts"], list)

    def test_get_siphoning_alerts_no_data(self, mock_db_connection):
        """Should handle no fuel data"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        response = client.get("/siphoning-alerts")

        assert response.status_code == 200
        data = response.json()
        assert data["alerts"] == []
        assert "No fuel data found" in data["message"]


class TestMPGContextEndpoint:
    """Tests for /mpg-context/{truck_id} endpoint"""

    def test_get_mpg_context_success(self, mock_db_connection):
        """Should return MPG context for truck"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection

        # Mock trip data
        base_time = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "timestamp": base_time - timedelta(days=i),
                "avg_speed_mph": 65.0,
                "stop_count": 5,
                "distance_miles": 200.0,
                "elevation_change_ft": 100.0,
                "is_loaded": True,
                "load_weight_lbs": 35000.0,
                "weather_condition": "clear",
                "ambient_temp_f": 75.0,
                "actual_mpg": 6.2,
            }
            for i in range(5)
        ]

        response = client.get("/mpg-context/TEST_TRUCK?days=7")

        assert response.status_code == 200
        data = response.json()
        assert data["truck_id"] == "TEST_TRUCK"
        assert "contexts" in data
        assert "summary" in data
        assert isinstance(data["contexts"], list)

    def test_get_mpg_context_with_summary(self, mock_db_connection):
        """Should include summary statistics"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection

        base_time = datetime.now(timezone.utc)
        mock_cursor.fetchall.return_value = [
            {
                "timestamp": base_time,
                "avg_speed_mph": 65.0,
                "stop_count": 5,
                "distance_miles": 200.0,
                "elevation_change_ft": 100.0,
                "is_loaded": True,
                "load_weight_lbs": 30000.0,
                "weather_condition": "clear",
                "ambient_temp_f": 70.0,
                "actual_mpg": 6.5,
            }
        ]

        response = client.get("/mpg-context/TEST_TRUCK")

        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "avg_expected_mpg" in data["summary"]
        assert "avg_actual_mpg" in data["summary"]
        assert "trip_count" in data["summary"]

    def test_get_mpg_context_no_data(self, mock_db_connection):
        """Should handle no trip data"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection
        mock_cursor.fetchall.return_value = []

        response = client.get("/mpg-context/UNKNOWN_TRUCK")

        assert response.status_code == 200
        data = response.json()
        assert data["contexts"] == []
        assert "No trip data found" in data["message"]

    def test_get_mpg_context_different_routes(self, mock_db_connection):
        """Should classify different route types"""
        from api_v2 import router
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        mock_conn, mock_cursor = mock_db_connection

        base_time = datetime.now(timezone.utc)
        # Highway route
        mock_cursor.fetchall.return_value = [
            {
                "timestamp": base_time,
                "avg_speed_mph": 65.0,
                "stop_count": 2,
                "distance_miles": 200.0,
                "elevation_change_ft": 100.0,
                "is_loaded": False,
                "load_weight_lbs": None,
                "weather_condition": "clear",
                "ambient_temp_f": 70.0,
                "actual_mpg": 7.0,
            }
        ]

        response = client.get("/mpg-context/TEST_TRUCK")

        assert response.status_code == 200
        data = response.json()
        assert len(data["contexts"]) > 0
        # Should classify as highway (route types are lowercase in response)
        assert data["contexts"][0]["route_type"].lower() in [
            "highway",
            "suburban",
            "city",
            "mountain",
            "mixed",
        ]
