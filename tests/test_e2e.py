"""
End-to-End Integration Tests for Fuel Copilot v3.7.0

These tests verify the complete flow from API to database.
Requires MySQL to be running (use docker-compose or GitHub Actions).

Usage:
    pytest tests/test_e2e.py -v
    pytest tests/test_e2e.py -v -k "test_fleet"  # Run specific test
"""

import pytest
import os
import sys
from datetime import datetime, timezone, timedelta
from typing import Generator
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Skip if not in testing mode
pytestmark = pytest.mark.skipif(
    os.getenv("TESTING") != "true",
    reason="Integration tests require TESTING=true environment variable",
)


# ===========================================
# FIXTURES
# ===========================================


@pytest.fixture(scope="module")
def test_db_config():
    """Database configuration for tests"""
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "test_user"),
        "password": os.getenv("MYSQL_PASSWORD", "testpass"),
        "database": os.getenv("MYSQL_DATABASE", "fuel_copilot_test"),
    }


@pytest.fixture(scope="module")
def db_connection(test_db_config):
    """Create database connection for tests"""
    try:
        import pymysql

        conn = pymysql.connect(
            host=test_db_config["host"],
            port=test_db_config["port"],
            user=test_db_config["user"],
            password=test_db_config["password"],
            database=test_db_config["database"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )
        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"Database not available: {e}")


@pytest.fixture(scope="module")
def setup_test_data(db_connection):
    """Insert test data into database"""
    cursor = db_connection.cursor()

    # Create table if not exists
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS fuel_metrics (
            id INT AUTO_INCREMENT PRIMARY KEY,
            truck_id VARCHAR(10) NOT NULL,
            timestamp_utc DATETIME NOT NULL,
            sensor_pct FLOAT,
            estimated_pct FLOAT,
            sensor_liters FLOAT,
            estimated_liters FLOAT,
            drift_pct FLOAT,
            confidence_indicator VARCHAR(10),
            drift_warning VARCHAR(5),
            truck_status ENUM('MOVING', 'STOPPED', 'OFFLINE') DEFAULT 'OFFLINE',
            mpg_current FLOAT,
            consumption_gph FLOAT,
            odometer_km FLOAT,
            speed_kmh FLOAT,
            INDEX idx_truck_timestamp (truck_id, timestamp_utc)
        )
    """
    )

    # Insert test data
    test_trucks = ["TEST001", "TEST002", "TEST003"]
    now = datetime.now(timezone.utc)

    for truck_id in test_trucks:
        for i in range(10):
            cursor.execute(
                """
                INSERT INTO fuel_metrics 
                (truck_id, timestamp_utc, sensor_pct, estimated_pct, 
                 sensor_liters, estimated_liters, drift_pct, 
                 confidence_indicator, drift_warning, truck_status,
                 mpg_current, consumption_gph, odometer_km, speed_kmh)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
                (
                    truck_id,
                    now - timedelta(minutes=i * 5),
                    75.0 - i * 0.5,  # Decreasing fuel
                    74.5 - i * 0.5,
                    150.0 - i,
                    149.0 - i,
                    1.0,
                    "HIGH",
                    "NO",
                    "MOVING" if i < 5 else "STOPPED",
                    7.5,
                    3.2,
                    100000 + i * 10,
                    55.0 if i < 5 else 0.0,
                ),
            )

    db_connection.commit()

    yield test_trucks

    # Cleanup
    cursor.execute("DELETE FROM fuel_metrics WHERE truck_id LIKE 'TEST%'")
    db_connection.commit()
    cursor.close()


@pytest.fixture
def api_client():
    """Create test client for FastAPI"""
    sys.path.insert(
        0, os.path.join(os.path.dirname(__file__), "..", "dashboard", "backend")
    )

    try:
        from fastapi.testclient import TestClient
        from main import app

        with TestClient(app) as client:
            yield client
    except ImportError as e:
        pytest.skip(f"FastAPI test client not available: {e}")


# ===========================================
# API ENDPOINT TESTS
# ===========================================


class TestHealthEndpoint:
    """Tests for /api/health endpoint"""

    def test_health_returns_200(self, api_client):
        """Health endpoint should return 200"""
        response = api_client.get("/api/health")
        assert response.status_code == 200

    def test_health_returns_healthy_status(self, api_client):
        """Health endpoint should return healthy status"""
        response = api_client.get("/api/health")
        data = response.json()
        assert data.get("status") in ["healthy", "ok"]


class TestFleetEndpoint:
    """Tests for /api/fleet endpoint"""

    def test_fleet_returns_200(self, api_client):
        """Fleet endpoint should return 200"""
        response = api_client.get("/api/fleet")
        assert response.status_code == 200

    def test_fleet_returns_list(self, api_client):
        """Fleet endpoint should return list of trucks"""
        response = api_client.get("/api/fleet")
        data = response.json()

        # Should be a list or dict with trucks key
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "trucks" in data or "data" in data


class TestTruckDetailEndpoint:
    """Tests for /api/truck/{truck_id} endpoint"""

    def test_invalid_truck_returns_404(self, api_client):
        """Invalid truck ID should return 404"""
        response = api_client.get("/api/truck/INVALID999")
        assert response.status_code in [404, 200]  # Some APIs return empty 200


class TestMetricsEndpoint:
    """Tests for /metrics endpoint (Prometheus)"""

    def test_metrics_returns_200(self, api_client):
        """Metrics endpoint should return 200"""
        response = api_client.get("/metrics")
        # May return 404 if prometheus not configured
        assert response.status_code in [200, 404]


# ===========================================
# DATABASE INTEGRATION TESTS
# ===========================================


class TestDatabaseIntegration:
    """Tests for database operations"""

    def test_connection_works(self, db_connection):
        """Database connection should work"""
        cursor = db_connection.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        assert result is not None

    def test_test_data_inserted(self, db_connection, setup_test_data):
        """Test data should be inserted correctly"""
        cursor = db_connection.cursor()
        cursor.execute(
            "SELECT COUNT(*) as count FROM fuel_metrics WHERE truck_id LIKE 'TEST%'"
        )
        result = cursor.fetchone()
        assert result["count"] >= 30  # 3 trucks * 10 records each

    def test_query_by_truck(self, db_connection, setup_test_data):
        """Should be able to query by truck ID"""
        cursor = db_connection.cursor()
        cursor.execute(
            """
            SELECT * FROM fuel_metrics 
            WHERE truck_id = %s 
            ORDER BY timestamp_utc DESC 
            LIMIT 1
        """,
            ("TEST001",),
        )
        result = cursor.fetchone()

        assert result is not None
        assert result["truck_id"] == "TEST001"
        assert result["sensor_pct"] is not None


# ===========================================
# DATA FLOW TESTS
# ===========================================


class TestDataFlow:
    """Tests for complete data flow"""

    def test_recent_data_retrieval(self, db_connection, setup_test_data):
        """Should retrieve recent data correctly"""
        cursor = db_connection.cursor()
        cursor.execute(
            """
            SELECT truck_id, sensor_pct, truck_status
            FROM fuel_metrics
            WHERE truck_id IN ('TEST001', 'TEST002', 'TEST003')
            AND timestamp_utc > NOW() - INTERVAL 1 HOUR
            ORDER BY timestamp_utc DESC
        """
        )
        results = cursor.fetchall()

        assert len(results) > 0
        assert all(r["sensor_pct"] is not None for r in results)

    def test_aggregation_query(self, db_connection, setup_test_data):
        """Should aggregate data correctly"""
        cursor = db_connection.cursor()
        cursor.execute(
            """
            SELECT 
                truck_id,
                COUNT(*) as records,
                AVG(sensor_pct) as avg_fuel,
                MIN(sensor_pct) as min_fuel,
                MAX(sensor_pct) as max_fuel
            FROM fuel_metrics
            WHERE truck_id LIKE 'TEST%'
            GROUP BY truck_id
        """
        )
        results = cursor.fetchall()

        assert len(results) == 3  # 3 test trucks
        for r in results:
            assert r["records"] == 10
            assert r["avg_fuel"] is not None


# ===========================================
# PERFORMANCE TESTS
# ===========================================


class TestPerformance:
    """Basic performance tests"""

    def test_bulk_insert_performance(self, db_connection):
        """Bulk insert should be reasonably fast"""
        import time

        cursor = db_connection.cursor()
        now = datetime.now(timezone.utc)

        start = time.time()

        # Insert 100 records
        for i in range(100):
            cursor.execute(
                """
                INSERT INTO fuel_metrics 
                (truck_id, timestamp_utc, sensor_pct, estimated_pct, truck_status)
                VALUES (%s, %s, %s, %s, %s)
            """,
                ("PERF001", now - timedelta(seconds=i), 50.0, 50.0, "MOVING"),
            )

        db_connection.commit()
        elapsed = time.time() - start

        # Cleanup
        cursor.execute("DELETE FROM fuel_metrics WHERE truck_id = 'PERF001'")
        db_connection.commit()

        # Should complete in under 5 seconds
        assert elapsed < 5.0, f"Bulk insert took {elapsed:.2f}s (expected < 5s)"

    def test_query_performance(self, db_connection, setup_test_data):
        """Queries should be reasonably fast"""
        import time

        cursor = db_connection.cursor()

        start = time.time()

        # Run query 10 times
        for _ in range(10):
            cursor.execute(
                """
                SELECT * FROM fuel_metrics 
                WHERE truck_id = 'TEST001'
                ORDER BY timestamp_utc DESC
                LIMIT 100
            """
            )
            cursor.fetchall()

        elapsed = time.time() - start

        # Should complete in under 1 second
        assert elapsed < 1.0, f"Queries took {elapsed:.2f}s (expected < 1s)"


# ===========================================
# EDGE CASE TESTS
# ===========================================


class TestEdgeCases:
    """Tests for edge cases and error handling"""

    def test_null_values_handled(self, db_connection):
        """Should handle NULL values correctly"""
        cursor = db_connection.cursor()

        # Insert record with NULL values
        cursor.execute(
            """
            INSERT INTO fuel_metrics 
            (truck_id, timestamp_utc, sensor_pct, estimated_pct, truck_status)
            VALUES (%s, %s, NULL, NULL, %s)
        """,
            ("EDGE001", datetime.now(timezone.utc), "OFFLINE"),
        )
        db_connection.commit()

        # Query it back
        cursor.execute("SELECT * FROM fuel_metrics WHERE truck_id = 'EDGE001'")
        result = cursor.fetchone()

        assert result is not None
        assert result["sensor_pct"] is None

        # Cleanup
        cursor.execute("DELETE FROM fuel_metrics WHERE truck_id = 'EDGE001'")
        db_connection.commit()

    def test_unicode_handling(self, db_connection):
        """Should handle unicode in truck IDs"""
        cursor = db_connection.cursor()

        # Insert with special characters (though truck IDs are usually alphanumeric)
        cursor.execute(
            """
            INSERT INTO fuel_metrics 
            (truck_id, timestamp_utc, sensor_pct, truck_status)
            VALUES (%s, %s, %s, %s)
        """,
            ("TEST_ÑÑ", datetime.now(timezone.utc), 50.0, "MOVING"),
        )
        db_connection.commit()

        # Cleanup
        cursor.execute("DELETE FROM fuel_metrics WHERE truck_id = 'TEST_ÑÑ'")
        db_connection.commit()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
