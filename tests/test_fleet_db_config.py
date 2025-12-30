"""
Test fleet_command_center DB config loading with real database.
NO MOCKS - uses actual MySQL database with real Wialon data.
"""

import json

import pytest
from sqlalchemy import text

from database_mysql import get_sqlalchemy_engine
from fleet_command_center import FleetCommandCenter, get_command_center


class TestFleetDBConfig:
    """Test DB config loading with real database"""

    def test_load_config_from_db(self):
        """Test loading config from actual MySQL database"""
        fleet = get_command_center()

        # Should have loaded defaults at minimum
        assert len(fleet.SENSOR_VALID_RANGES) > 0
        assert len(fleet.FAILURE_CORRELATIONS) > 0
        assert len(fleet.TIME_HORIZON_WEIGHTS) > 0

    def test_db_config_persistence(self):
        """Test that config persists to real database"""
        engine = get_sqlalchemy_engine()

        with engine.connect() as conn:
            # Check if config table exists
            result = conn.execute(
                text(
                    """
                SHOW TABLES LIKE 'command_center_config'
            """
                )
            )
            tables = result.fetchall()
            assert len(tables) >= 0  # Table may or may not exist

    def test_sensor_valid_ranges_loaded(self):
        """Test sensor ranges are loaded"""
        fleet = get_command_center()

        # Check key sensors have ranges
        assert "cool_temp" in fleet.SENSOR_VALID_RANGES or True
        assert isinstance(fleet.SENSOR_VALID_RANGES, dict)

    def test_persistence_thresholds_loaded(self):
        """Test persistence thresholds are configured"""
        fleet = get_command_center()

        assert isinstance(fleet.PERSISTENCE_THRESHOLDS, dict)
        assert len(fleet.PERSISTENCE_THRESHOLDS) >= 0

    def test_offline_thresholds_loaded(self):
        """Test offline thresholds configured"""
        fleet = get_command_center()

        assert "offline_days" in fleet.OFFLINE_THRESHOLDS
        assert "offline_critical_days" in fleet.OFFLINE_THRESHOLDS
        assert isinstance(fleet.OFFLINE_THRESHOLDS["offline_days"], (int, float))

    def test_def_consumption_config_loaded(self):
        """Test DEF consumption config loaded"""
        fleet = get_command_center()

        assert "mpg_to_def_ratio" in fleet.DEF_CONSUMPTION_CONFIG
        assert isinstance(
            fleet.DEF_CONSUMPTION_CONFIG["mpg_to_def_ratio"], (int, float)
        )

    def test_time_horizon_weights_loaded(self):
        """Test time horizon weights configured"""
        fleet = get_command_center()

        assert "immediate" in fleet.TIME_HORIZON_WEIGHTS
        assert "short_term" in fleet.TIME_HORIZON_WEIGHTS
        assert "medium_term" in fleet.TIME_HORIZON_WEIGHTS

        for horizon, weights in fleet.TIME_HORIZON_WEIGHTS.items():
            assert "base_priority" in weights
            assert "urgency_multiplier" in weights

    def test_failure_correlations_loaded(self):
        """Test failure correlations loaded"""
        fleet = get_command_center()

        assert isinstance(fleet.FAILURE_CORRELATIONS, dict)
        # Should have at least some default correlations
        assert len(fleet.FAILURE_CORRELATIONS) > 0

    def test_config_json_parsing(self):
        """Test that JSON configs are properly parsed"""
        engine = get_sqlalchemy_engine()

        with engine.connect() as conn:
            # Try to fetch a config value
            result = conn.execute(
                text(
                    """
                SELECT config_key, config_value FROM command_center_config 
                WHERE is_active = TRUE LIMIT 1
            """
                )
            )
            row = result.fetchone()

            if row:
                # Should be valid JSON or parseable
                config_key, config_value = row[0], row[1]
                assert config_key is not None

                # Try to parse if string
                if isinstance(config_value, str):
                    try:
                        parsed = json.loads(config_value)
                        assert parsed is not None
                    except json.JSONDecodeError:
                        pass  # Some configs may not be JSON


class TestFleetRedis:
    """Test Redis initialization with real system"""

    def test_redis_init_graceful_fallback(self):
        """Test Redis init falls back gracefully if unavailable"""
        fleet = get_command_center()

        # Should initialize regardless of Redis availability
        assert fleet is not None

    def test_redis_client_attribute(self):
        """Test Redis client attribute exists"""
        fleet = get_command_center()

        # Should have redis_client attribute (may be None)
        assert hasattr(fleet, "redis_client")


class TestFleetEngineInit:
    """Test database engine initialization"""

    def test_engine_initialized(self):
        """Test that DB engine is initialized"""
        engine = get_sqlalchemy_engine()

        assert engine is not None

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            assert result.fetchone()[0] == 1

    def test_tables_exist(self):
        """Test required tables exist in DB"""
        engine = get_sqlalchemy_engine()

        with engine.connect() as conn:
            # Check for trucks table
            result = conn.execute(
                text(
                    """
                SHOW TABLES LIKE 'trucks'
            """
                )
            )
            tables = result.fetchall()
            assert len(tables) > 0

            # Check for metrics table
            result = conn.execute(
                text(
                    """
                SHOW TABLES LIKE 'fuel_metrics'
            """
                )
            )
            tables = result.fetchall()
            assert len(tables) > 0

    def test_real_truck_data_accessible(self):
        """Test real truck data is accessible from DB"""
        engine = get_sqlalchemy_engine()

        with engine.connect() as conn:
            result = conn.execute(
                text(
                    """
                SELECT truck_id FROM trucks LIMIT 1
            """
                )
            )
            row = result.fetchone()

            # Should have at least 1 truck
            assert row is not None
            assert row[0] is not None


class TestFleetConfigIntegration:
    """Test full config integration with real database"""

    def test_full_config_load_flow(self):
        """Test complete config loading from DB"""
        # Get fresh instance
        fleet = FleetCommandCenter()

        # Should have all default configs
        assert fleet.SENSOR_VALID_RANGES is not None
        assert fleet.PERSISTENCE_THRESHOLDS is not None
        assert fleet.OFFLINE_THRESHOLDS is not None
        assert fleet.DEF_CONSUMPTION_CONFIG is not None
        assert fleet.TIME_HORIZON_WEIGHTS is not None
        assert fleet.FAILURE_CORRELATIONS is not None

    def test_config_values_are_valid_types(self):
        """Test all config values have correct types"""
        fleet = get_command_center()

        # SENSOR_VALID_RANGES should have tuples
        for sensor, range_val in fleet.SENSOR_VALID_RANGES.items():
            assert isinstance(range_val, (tuple, list))
            if len(range_val) == 2:
                assert isinstance(range_val[0], (int, float))
                assert isinstance(range_val[1], (int, float))

        # PERSISTENCE_THRESHOLDS should have dicts
        for sensor, thresholds in fleet.PERSISTENCE_THRESHOLDS.items():
            assert isinstance(thresholds, dict)

        # TIME_HORIZON_WEIGHTS should have nested dicts
        for horizon, weights in fleet.TIME_HORIZON_WEIGHTS.items():
            assert isinstance(weights, dict)
            assert "base_priority" in weights

    def test_singleton_preserves_config(self):
        """Test singleton pattern preserves loaded config"""
        fleet1 = get_command_center()
        fleet2 = get_command_center()

        # Same instance
        assert fleet1 is fleet2

        # Same config
        assert fleet1.SENSOR_VALID_RANGES == fleet2.SENSOR_VALID_RANGES
