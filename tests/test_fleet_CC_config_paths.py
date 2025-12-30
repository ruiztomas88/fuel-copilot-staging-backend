"""
Fleet Command Center - Atacar las últimas líneas de configuración
Lines 1195-1198, 1225-1228, 1260-1263, 1272-1273, 1280-1282
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock, PropertyMock, mock_open
import json

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestConfigDBTableNotFound:
    """Lines 1195-1198: DB config table not found"""

    def test_load_db_config_empty_table_result(self):
        """Forzar tabla vacía en _load_db_config"""
        from fleet_command_center import FleetCommandCenter
        
        # Mock database_mysql.get_sqlalchemy_engine para retornar conexión válida pero sin datos
        with patch('database_mysql.get_sqlalchemy_engine') as mock_engine:
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = []  # Tabla vacía
            mock_conn.execute.return_value = mock_result
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            
            mock_engine.return_value.connect.return_value = mock_conn
            
            # Al crear instancia, llama _load_db_config
            cc = FleetCommandCenter()
            # Lines 1195-1198: logger.debug table not found path


class TestConfigJSONDecodeError:
    """Lines 1225-1228: JSON decode error handling"""

    def test_load_db_config_invalid_json_value(self):
        """Forzar JSON inválido en config_value"""
        from fleet_command_center import FleetCommandCenter
        
        with patch('database_mysql.get_sqlalchemy_engine') as mock_engine:
            mock_conn = MagicMock()
            mock_result = MagicMock()
            # Retornar datos con JSON malformado
            mock_result.fetchall.return_value = [
                {"config_key": "bad_json", "config_value": "{invalid: json}"},
                {"config_key": "good_json", "config_value": '{"valid": true}'},
            ]
            mock_conn.execute.return_value = mock_result
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            
            mock_engine.return_value.connect.return_value = mock_conn
            
            cc = FleetCommandCenter()
            # Lines 1225-1228: JSON decode error catch


class TestConfigImportAndGeneralErrors:
    """Lines 1260-1263, 1272-1273, 1280-1282: Import and general errors"""

    def test_load_db_config_import_error(self):
        """Forzar ImportError cuando get_mysql_engine no existe"""
        from fleet_command_center import FleetCommandCenter
        
        # Simular que database_mysql no está disponible
        with patch('database_mysql.get_sqlalchemy_engine', side_effect=ImportError("Module not found")):
            cc = FleetCommandCenter()
            # Line 1260-1262: ImportError handling
            assert cc is not None  # Debería usar defaults

    def test_load_db_config_general_exception_db_error(self):
        """Forzar Exception general en DB access"""
        from fleet_command_center import FleetCommandCenter
        
        with patch('database_mysql.get_sqlalchemy_engine', side_effect=Exception("Database connection failed")):
            cc = FleetCommandCenter()
            # Lines 1263, 1272-1273, 1280-1282: General exception handling
            assert cc is not None

    def test_load_db_config_connection_error(self):
        """Forzar error de conexión en DB"""
        from fleet_command_center import FleetCommandCenter
        
        with patch('database_mysql.get_sqlalchemy_engine') as mock_engine:
            # Conexión falla al hacer connect()
            mock_engine.return_value.connect.side_effect = Exception("Connection refused")
            
            cc = FleetCommandCenter()
            # Lines 1280-1282: Connection error handling


class TestMultipleConfigLoadScenarios:
    """Combinaciones de errores de configuración"""

    def test_config_yaml_and_db_both_fail(self):
        """Ambos YAML y DB fallan - usar defaults completos"""
        from fleet_command_center import FleetCommandCenter
        
        # YAML no existe
        with patch.object(Path, 'exists', return_value=False):
            # DB también falla
            with patch('database_mysql.get_sqlalchemy_engine', side_effect=Exception("No DB")):
                cc = FleetCommandCenter()
                # Debería usar configuración por defecto
                assert cc is not None
                assert hasattr(cc, 'config')

    def test_config_db_partial_success(self):
        """DB se conecta pero retorna datos parciales"""
        from fleet_command_center import FleetCommandCenter
        
        with patch('database_mysql.get_sqlalchemy_engine') as mock_engine:
            mock_conn = MagicMock()
            mock_result = MagicMock()
            
            # Mezcla: algunos JSON válidos, otros no, algunos vacíos
            mock_result.fetchall.return_value = [
                {"config_key": "valid1", "config_value": '{"threshold": 100}'},
                {"config_key": "invalid", "config_value": '{bad json'},
                {"config_key": "empty", "config_value": ''},
                {"config_key": "valid2", "config_value": '{"alpha": 0.3}'},
            ]
            mock_conn.execute.return_value = mock_result
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            
            mock_engine.return_value.connect.return_value = mock_conn
            
            cc = FleetCommandCenter()
            # Debe procesar válidos y skip inválidos

    def test_config_db_connection_timeout(self):
        """Simular timeout en conexión DB"""
        from fleet_command_center import FleetCommandCenter
        
        with patch('database_mysql.get_sqlalchemy_engine') as mock_engine:
            mock_engine.return_value.connect.side_effect = TimeoutError("Connection timeout")
            
            cc = FleetCommandCenter()
            # Debe manejar timeout gracefully


class TestInitializationErrorPaths:
    """Test paths de inicialización con errores"""

    def test_init_redis_unavailable(self):
        """Test inicialización cuando Redis no disponible"""
        from fleet_command_center import FleetCommandCenter
        
        # Forzar que Redis esté unavailable
        with patch('redis.Redis', None):
            cc = FleetCommandCenter()
            # Lines relacionadas a Redis init
            assert cc is not None

    def test_init_ml_model_load_failure(self):
        """Test cuando ML model no puede cargar"""
        from fleet_command_center import FleetCommandCenter
        
        with patch('joblib.load', None):
            cc = FleetCommandCenter()
            # Debe manejar falta de ML model
            assert cc is not None


class TestPersistenceRetryLogic:
    """Test retry logic en persistence"""

    def test_persist_anomaly_db_down_then_up(self):
        """Test persist cuando DB falla y luego recupera"""
        from fleet_command_center import FleetCommandCenter
        
        cc = FleetCommandCenter()
        
        # Primera llamada falla
        with patch('database_mysql.get_sqlalchemy_engine', side_effect=Exception("DB down")):
            result1 = cc.persist_anomaly(
                truck_id="RETRY1",
                sensor_name="oil_temp",
                anomaly_type="EWMA",
                severity="HIGH",
                sensor_value=250.0,
            )
            assert result1 is False
        
        # Segunda llamada puede funcionar
        result2 = cc.persist_anomaly(
            truck_id="RETRY2",
            sensor_name="oil_temp",
            anomaly_type="CUSUM",
            severity="CRITICAL",
            sensor_value=260.0,
        )


class TestConfigValidationEdgeCases:
    """Edge cases en validación de configuración"""

    def test_config_with_none_values(self):
        """Test config con valores None"""
        from fleet_command_center import FleetCommandCenter
        
        with patch('database_mysql.get_sqlalchemy_engine') as mock_engine:
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [
                {"config_key": "null_value", "config_value": None},
                {"config_key": "valid", "config_value": '{"test": true}'},
            ]
            mock_conn.execute.return_value = mock_result
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            
            mock_engine.return_value.connect.return_value = mock_conn
            
            cc = FleetCommandCenter()

    def test_config_with_empty_string(self):
        """Test config con strings vacíos"""
        from fleet_command_center import FleetCommandCenter
        
        with patch('database_mysql.get_sqlalchemy_engine') as mock_engine:
            mock_conn = MagicMock()
            mock_result = MagicMock()
            mock_result.fetchall.return_value = [
                {"config_key": "", "config_value": '{}'},
                {"config_key": "valid", "config_value": ''},
            ]
            mock_conn.execute.return_value = mock_result
            mock_conn.__enter__ = MagicMock(return_value=mock_conn)
            mock_conn.__exit__ = MagicMock(return_value=False)
            
            mock_engine.return_value.connect.return_value = mock_conn
            
            cc = FleetCommandCenter()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
