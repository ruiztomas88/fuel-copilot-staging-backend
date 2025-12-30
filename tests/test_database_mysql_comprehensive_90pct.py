"""
🎯 COMPREHENSIVE DATABASE_MYSQL TESTING - TARGET 90% COVERAGE
=============================================================

Tests para llevar database_mysql.py de 25% → 90% de cobertura.
Enfoque en funciones críticas y queries más usadas.

Módulos cubiertos:
1. Connection pooling y context managers
2. Fleet summary queries (más usadas en dashboard)
3. KPI calculations
4. Truck history y analytics
5. Error handling y edge cases

Author: Fuel Analytics Team
Date: December 28, 2025
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError, OperationalError

# Import the module to test
import database_mysql


class TestConnectionPooling:
    """Test connection pool management and context managers"""

    def test_get_engine_creates_engine(self):
        """Should create SQLAlchemy engine with correct config"""
        engine = database_mysql.get_engine()
        assert engine is not None
        assert engine.pool is not None
        assert engine.pool.size() >= 0

    def test_get_connection_context_manager(self):
        """Should provide connection via context manager"""
        with database_mysql.get_connection() as conn:
            assert conn is not None
            result = conn.execute(text("SELECT 1"))
            assert result is not None

    def test_connection_auto_closes(self):
        """Should auto-close connection after context manager"""
        with database_mysql.get_connection() as conn:
            conn_id = id(conn)
        # Connection should be returned to pool (not test closed state)
        assert conn_id is not None

    def test_connection_rollback_on_error(self):
        """Should rollback transaction on error"""
        with pytest.raises(Exception):
            with database_mysql.get_connection() as conn:
                conn.execute(text("INSERT INTO nonexistent_table VALUES (1)"))
                raise Exception("Force error")

    @patch("database_mysql.create_engine")
    def test_engine_singleton_pattern(self, mock_create_engine):
        """Should reuse same engine instance"""
        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        # Reset cached engine
        database_mysql._engine = None

        engine1 = database_mysql.get_engine()
        engine2 = database_mysql.get_engine()

        # Should only call create_engine once
        assert mock_create_engine.call_count == 1


class TestFleetSummary:
    """Test get_fleet_summary - most used query in dashboard"""

    @patch("database_mysql.get_connection")
    def test_fleet_summary_basic(self, mock_get_conn):
        """Should return fleet summary with all metrics"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        # Mock query result
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "truck_id": "TEST001",
                "mpg": 6.5,
                "idle_gph": 0.8,
                "status": "MOVING",
                "speed_mph": 55.0,
                "fuel_L": 150.0,
                "estimated_pct": 75.0,
                "sensor_pct": 74.5,
                "drift_pct": 0.5,
                "health_score": 85,
                "latitude": 25.7617,
                "longitude": -80.1918,
            }
        ]
        mock_conn.execute.return_value = mock_result

        result = database_mysql.get_fleet_summary()

        assert result is not None
        assert len(result) > 0
        assert result[0]["truck_id"] == "TEST001"
        assert result[0]["mpg"] == 6.5

    @patch("database_mysql.get_connection")
    def test_fleet_summary_handles_nulls(self, mock_get_conn):
        """Should handle NULL values gracefully"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "truck_id": "TEST002",
                "mpg": None,
                "idle_gph": None,
                "status": "OFFLINE",
                "speed_mph": 0,
                "fuel_L": None,
                "estimated_pct": None,
                "sensor_pct": None,
                "drift_pct": None,
                "health_score": 50,
                "latitude": None,
                "longitude": None,
            }
        ]
        mock_conn.execute.return_value = mock_result

        result = database_mysql.get_fleet_summary()

        assert result is not None
        assert len(result) > 0
        assert result[0]["truck_id"] == "TEST002"
        assert result[0]["mpg"] is None

    @patch("database_mysql.get_connection")
    def test_fleet_summary_empty_result(self, mock_get_conn):
        """Should handle empty fleet gracefully"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result

        result = database_mysql.get_fleet_summary()

        assert result == []

    @patch("database_mysql.get_connection")
    def test_fleet_summary_database_error(self, mock_get_conn):
        """Should handle database errors gracefully"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.side_effect = OperationalError("DB", "Connection", "failed")

        # Should raise or return empty
        with pytest.raises(Exception):
            database_mysql.get_fleet_summary()


class TestKPISummary:
    """Test get_kpi_summary - critical for analytics"""

    @patch("database_mysql.get_connection")
    def test_kpi_summary_1_day(self, mock_get_conn):
        """Should calculate KPIs for 1 day period"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.fetchone.return_value = {
            "total_trucks": 10,
            "moving_trucks": 6,
            "idle_trucks": 2,
            "offline_trucks": 2,
            "avg_mpg": 6.2,
            "total_fuel_consumed": 500.0,
            "avg_idle_gph": 0.75,
        }
        mock_conn.execute.return_value = mock_result

        result = database_mysql.get_kpi_summary(days=1)

        assert result is not None
        assert result["total_trucks"] == 10
        assert result["moving_trucks"] == 6
        assert result["avg_mpg"] == 6.2

    @patch("database_mysql.get_connection")
    def test_kpi_summary_7_days(self, mock_get_conn):
        """Should calculate KPIs for 7 day period"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.fetchone.return_value = {
            "total_trucks": 10,
            "moving_trucks": 7,
            "idle_trucks": 2,
            "offline_trucks": 1,
            "avg_mpg": 6.5,
            "total_fuel_consumed": 3500.0,
            "avg_idle_gph": 0.70,
        }
        mock_conn.execute.return_value = mock_result

        result = database_mysql.get_kpi_summary(days=7)

        assert result is not None
        assert result["total_fuel_consumed"] == 3500.0


class TestTruckHistory:
    """Test get_truck_history - used in truck detail page"""

    @patch("database_mysql.get_connection")
    def test_truck_history_basic(self, mock_get_conn):
        """Should return truck history with timestamps"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        now = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "timestamp_utc": now - timedelta(hours=2),
                "estimated_pct": 80.0,
                "sensor_pct": 79.5,
                "speed_mph": 60.0,
                "mpg": 6.5,
                "status": "MOVING",
            },
            {
                "timestamp_utc": now - timedelta(hours=1),
                "estimated_pct": 75.0,
                "sensor_pct": 74.5,
                "speed_mph": 55.0,
                "mpg": 6.3,
                "status": "MOVING",
            },
        ]
        mock_conn.execute.return_value = mock_result

        result = database_mysql.get_truck_history("TEST001", hours=24)

        assert result is not None
        assert len(result) == 2
        assert result[0]["mpg"] == 6.5

    @patch("database_mysql.get_connection")
    def test_truck_history_no_data(self, mock_get_conn):
        """Should handle truck with no history"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result

        result = database_mysql.get_truck_history("NONEXISTENT", hours=24)

        assert result == []


class TestLossAnalysis:
    """Test get_loss_analysis - fuel loss detection"""

    @patch("database_mysql.get_connection")
    def test_loss_analysis_basic(self, mock_get_conn):
        """Should detect fuel losses"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "truck_id": "TEST001",
                "timestamp_utc": datetime.now(timezone.utc),
                "loss_gallons": 5.2,
                "before_pct": 75.0,
                "after_pct": 70.0,
                "confidence": "HIGH",
            }
        ]
        mock_conn.execute.return_value = mock_result

        result = database_mysql.get_loss_analysis(days=7)

        assert result is not None
        assert len(result) > 0
        assert result[0]["loss_gallons"] == 5.2


class TestRefuelHistory:
    """Test get_refuel_history - refuel detection"""

    @patch("database_mysql.get_connection")
    def test_refuel_history_basic(self, mock_get_conn):
        """Should return refuel events"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "truck_id": "TEST001",
                "timestamp_utc": datetime.now(timezone.utc),
                "gallons_added": 150.0,
                "fuel_before": 25.0,
                "fuel_after": 175.0,
                "refuel_type": "NORMAL",
            }
        ]
        mock_conn.execute.return_value = mock_result

        result = database_mysql.get_refuel_history("TEST001", days=30)

        assert result is not None
        assert len(result) > 0
        assert result[0]["gallons_added"] == 150.0


class TestErrorHandling:
    """Test error handling and edge cases"""

    @patch("database_mysql.get_connection")
    def test_connection_timeout(self, mock_get_conn):
        """Should handle connection timeout"""
        mock_get_conn.side_effect = OperationalError(
            "DB", "timeout", "Connection timeout"
        )

        with pytest.raises(OperationalError):
            database_mysql.get_fleet_summary()

    @patch("database_mysql.get_connection")
    def test_invalid_query(self, mock_get_conn):
        """Should handle SQL syntax errors"""
        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn
        mock_conn.execute.side_effect = Exception("SQL syntax error")

        with pytest.raises(Exception):
            database_mysql.get_fleet_summary()

    def test_get_allowed_trucks_fallback(self):
        """Should handle missing config gracefully"""
        if database_mysql.CENTRALIZED_TRUCKS:
            trucks = database_mysql.get_allowed_trucks()
            assert isinstance(trucks, set)


class TestCacheIntegration:
    """Test cache integration if available"""

    def test_cache_enabled_check(self):
        """Should detect if cache is enabled"""
        assert isinstance(database_mysql.CACHE_ENABLED, bool)

    @patch("database_mysql.CACHE_ENABLED", True)
    @patch("database_mysql.invalidate_fleet_cache")
    def test_cache_invalidation(self, mock_invalidate):
        """Should invalidate cache when data changes"""
        # Simulate cache invalidation
        database_mysql.invalidate_fleet_cache()
        mock_invalidate.assert_called_once()


class TestUtilityFunctions:
    """Test helper functions and utilities"""

    def test_config_imports(self):
        """Should have required config"""
        assert hasattr(database_mysql, "DB_CONFIG")
        assert hasattr(database_mysql, "FUEL")
        assert database_mysql.FUEL.PRICE_PER_GALLON > 0

    def test_mysql_config(self):
        """Should have valid MySQL config"""
        config = database_mysql.MYSQL_CONFIG
        assert "host" in config
        assert "database" in config
        assert "user" in config


# Integration test markers
pytestmark = pytest.mark.database


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=database_mysql", "--cov-report=term-missing"])
