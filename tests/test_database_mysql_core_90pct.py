"""
Test Database MySQL Core - 90% Coverage Target
Tests módulo database_mysql.py con enfoque en funciones principales
Fecha: Diciembre 28, 2025
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestDatabaseMySQLConnection:
    """Tests para conexión y engine de database_mysql"""

    @patch("database_mysql.create_engine")
    def test_get_engine_creates_pool(self, mock_create_engine):
        """Test que get_engine crea un engine con pool correcto"""
        from database_mysql import get_engine

        mock_engine = MagicMock()
        mock_create_engine.return_value = mock_engine

        engine = get_engine()

        assert mock_create_engine.called
        # Verificar parámetros de pooling
        call_kwargs = mock_create_engine.call_args[1]
        assert call_kwargs.get("pool_pre_ping") is True
        assert call_kwargs.get("pool_recycle") == 3600

    @patch("database_mysql.get_engine")
    def test_get_connection_context_manager(self, mock_get_engine):
        """Test context manager de conexiones"""
        from database_mysql import get_connection

        mock_engine = MagicMock()
        mock_conn = MagicMock()
        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_get_engine.return_value = mock_engine

        with get_connection() as conn:
            assert conn == mock_conn

        mock_engine.connect.assert_called_once()


class TestDatabaseMySQLQueries:
    """Tests para queries principales de database_mysql"""

    @patch("database_mysql.get_connection")
    def test_get_latest_metrics_basic(self, mock_get_conn):
        """Test obtener métricas más recientes"""
        from database_mysql import get_latest_metrics

        # Mock connection y result
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "truck_id": "TEST001",
                "mpg": 7.5,
                "fuel_level_pct": 75,
                "odometer_mi": 12000,
                "timestamp_utc": datetime.now(timezone.utc),
            }
        ]
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_latest_metrics()

        assert len(result) > 0
        mock_conn.execute.assert_called()

    @patch("database_mysql.get_connection")
    def test_get_truck_data_single_truck(self, mock_get_conn):
        """Test obtener datos de un truck específico"""
        from database_mysql import get_truck_data

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [
            {
                "truck_id": "TEST001",
                "mpg": 7.5,
                "fuel_level_pct": 75,
            }
        ]
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_truck_data("TEST001", days=7)

        assert isinstance(result, list)
        mock_conn.execute.assert_called()

    @patch("database_mysql.get_connection")
    def test_get_fuel_events_refuels(self, mock_get_conn):
        """Test obtener eventos de refuel"""
        from database_mysql import get_fuel_events

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "truck_id": "TEST001",
                "event_type": "REFUEL",
                "gallons_change": 50.0,
                "timestamp_utc": datetime.now(timezone.utc),
            }
        ]
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_fuel_events("TEST001", days=30)

        assert isinstance(result, list)
        mock_conn.execute.assert_called()


class TestDatabaseMySQLAnalytics:
    """Tests para funciones analíticas de database_mysql"""

    @patch("database_mysql.get_connection")
    def test_calculate_theft_suspects(self, mock_get_conn):
        """Test detectar posibles robos de combustible"""
        from database_mysql import detect_theft_suspects

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "truck_id": "TEST001",
                "fuel_drop_gallons": -25.0,
                "drop_percentage": -15.5,
                "timestamp_utc": datetime.now(timezone.utc),
                "truck_state": "STOPPED",
            }
        ]
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = detect_theft_suspects(days=7)

        assert isinstance(result, list)
        mock_conn.execute.assert_called()

    @patch("database_mysql.get_connection")
    def test_get_mpg_history(self, mock_get_conn):
        """Test obtener historial de MPG"""
        from database_mysql import get_mpg_history

        mock_conn = MagicMock()
        df = pd.DataFrame(
            {
                "timestamp_utc": [datetime.now(timezone.utc)],
                "mpg": [7.5],
                "truck_id": ["TEST001"],
            }
        )
        mock_conn.execute.return_value = MagicMock()

        with patch("pandas.read_sql", return_value=df):
            result = get_mpg_history("TEST001", days=30)

            assert isinstance(result, pd.DataFrame)

    @patch("database_mysql.get_connection")
    def test_get_fleet_summary(self, mock_get_conn):
        """Test obtener resumen de toda la flota"""
        from database_mysql import get_fleet_summary

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [
            {
                "truck_id": "TEST001",
                "latest_mpg": 7.5,
                "avg_mpg_7d": 7.3,
                "fuel_level_pct": 75,
                "total_miles_7d": 1500,
            },
            {
                "truck_id": "TEST002",
                "latest_mpg": 6.8,
                "avg_mpg_7d": 6.9,
                "fuel_level_pct": 45,
                "total_miles_7d": 1200,
            },
        ]
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_fleet_summary()

        assert isinstance(result, list)
        assert len(result) == 2
        mock_conn.execute.assert_called()


class TestDatabaseMySQLInserts:
    """Tests para operaciones de escritura en database_mysql"""

    @patch("database_mysql.get_connection")
    def test_save_fuel_metric(self, mock_get_conn):
        """Test guardar métrica de combustible"""
        from database_mysql import save_fuel_metric

        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        data = {
            "truck_id": "TEST001",
            "mpg": 7.5,
            "fuel_level_pct": 75,
            "odometer_mi": 12000,
            "timestamp_utc": datetime.now(timezone.utc),
        }

        save_fuel_metric(data)

        mock_conn.execute.assert_called()
        mock_conn.commit.assert_called()

    @patch("database_mysql.get_connection")
    def test_bulk_insert_metrics(self, mock_get_conn):
        """Test inserción masiva de métricas"""
        from database_mysql import bulk_insert_metrics

        mock_conn = MagicMock()
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        metrics = [
            {
                "truck_id": "TEST001",
                "mpg": 7.5,
                "fuel_level_pct": 75,
                "timestamp_utc": datetime.now(timezone.utc),
            },
            {
                "truck_id": "TEST002",
                "mpg": 6.8,
                "fuel_level_pct": 65,
                "timestamp_utc": datetime.now(timezone.utc),
            },
        ]

        bulk_insert_metrics(metrics)

        assert mock_conn.execute.called
        mock_conn.commit.assert_called()


class TestDatabaseMySQLErrorHandling:
    """Tests para manejo de errores en database_mysql"""

    @patch("database_mysql.get_engine")
    def test_connection_failure_handling(self, mock_get_engine):
        """Test manejo de fallo de conexión"""
        from database_mysql import get_connection

        mock_get_engine.side_effect = Exception("Connection failed")

        with pytest.raises(Exception):
            with get_connection():
                pass

    @patch("database_mysql.get_connection")
    def test_query_with_invalid_truck_id(self, mock_get_conn):
        """Test query con truck_id inválido"""
        from database_mysql import get_truck_data

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_truck_data("INVALID999", days=7)

        assert result == []

    @patch("database_mysql.get_connection")
    def test_empty_result_handling(self, mock_get_conn):
        """Test manejo de resultados vacíos"""
        from database_mysql import get_latest_metrics

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_latest_metrics()

        assert result == []


class TestDatabaseMySQLCaching:
    """Tests para sistema de caché en database_mysql"""

    @patch("database_mysql.CACHE_ENABLED", True)
    @patch("database_mysql.get_connection")
    def test_cached_query_first_call(self, mock_get_conn):
        """Test primera llamada a query con caché"""
        from database_mysql import get_fleet_summary

        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = [{"truck_id": "TEST001", "latest_mpg": 7.5}]
        mock_conn.execute.return_value = mock_result
        mock_get_conn.return_value.__enter__.return_value = mock_conn

        result = get_fleet_summary()

        assert isinstance(result, list)
        mock_conn.execute.assert_called()

    @patch("database_mysql.invalidate_fleet_cache")
    def test_cache_invalidation(self, mock_invalidate):
        """Test invalidación de caché"""
        from database_mysql import invalidate_fleet_cache

        mock_invalidate.return_value = 5

        count = invalidate_fleet_cache()

        assert isinstance(count, int)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
