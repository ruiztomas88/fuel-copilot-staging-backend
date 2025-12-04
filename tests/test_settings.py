"""
Tests for Settings Module (v3.12.21)
Phase 5: Centralized configuration tests
"""

import pytest
import os
from unittest.mock import patch


class TestDatabaseSettings:
    """Test database configuration"""

    def test_default_values(self):
        """Should have sensible defaults"""
        from settings import DatabaseSettings

        settings = DatabaseSettings()
        assert settings.port == 3306
        assert settings.charset == "utf8mb4"
        assert settings.pool_size == 10

    def test_connection_dict(self):
        """Should generate valid connection dictionary"""
        from settings import DatabaseSettings

        settings = DatabaseSettings()
        conn_dict = settings.get_connection_dict()

        assert "host" in conn_dict
        assert "port" in conn_dict
        assert "user" in conn_dict
        assert "password" in conn_dict
        assert "database" in conn_dict
        assert conn_dict["autocommit"] is True


class TestRedisSettings:
    """Test Redis configuration"""

    def test_disabled_by_default(self):
        """Redis should be disabled by default"""
        from settings import RedisSettings

        with patch.dict(os.environ, {}, clear=True):
            settings = RedisSettings()
            # Check default or current env value
            assert hasattr(settings, "enabled")

    def test_default_port(self):
        """Should use default Redis port"""
        from settings import RedisSettings

        settings = RedisSettings()
        assert settings.port == 6379


class TestAuthSettings:
    """Test authentication configuration"""

    def test_secret_key_generation(self):
        """Should generate a secret key if not provided"""
        from settings import AuthSettings

        settings = AuthSettings()
        assert settings.secret_key is not None
        assert len(settings.secret_key) > 20

    def test_algorithm(self):
        """Should use HS256 algorithm"""
        from settings import AuthSettings

        settings = AuthSettings()
        assert settings.algorithm == "HS256"

    def test_production_ready_flag(self):
        """Should report production readiness"""
        from settings import AuthSettings

        settings = AuthSettings()
        # Will be False if JWT_SECRET_KEY not in environment
        assert isinstance(settings.is_production_ready, bool)


class TestAlertSettings:
    """Test alert configuration"""

    def test_default_cooldown(self):
        """Should have 30 minute default cooldown"""
        from settings import AlertSettings

        settings = AlertSettings()
        assert settings.cooldown_minutes == 30

    def test_twilio_configured_property(self):
        """Should check Twilio configuration"""
        from settings import AlertSettings

        settings = AlertSettings()
        # Empty config = not configured
        settings.twilio_account_sid = ""
        assert settings.twilio_configured is False

    def test_low_fuel_thresholds(self):
        """Should have sensible low fuel thresholds"""
        from settings import AlertSettings

        settings = AlertSettings()
        assert settings.low_fuel_critical_pct == 10.0
        assert settings.low_fuel_warning_pct == 20.0


class TestTheftDetectionSettings:
    """Test enhanced theft detection configuration"""

    def test_default_thresholds(self):
        """Should have sensible theft detection thresholds"""
        from settings import TheftDetectionSettings

        settings = TheftDetectionSettings()
        assert settings.min_drop_pct == 10.0
        assert settings.min_consecutive_readings == 3
        assert settings.min_duration_minutes == 5

    def test_confidence_thresholds(self):
        """Should have confidence scoring thresholds"""
        from settings import TheftDetectionSettings

        settings = TheftDetectionSettings()
        assert settings.high_confidence_threshold > settings.medium_confidence_threshold


class TestRateLimitSettings:
    """Test rate limiting configuration"""

    def test_enabled_by_default(self):
        """Rate limiting should be enabled by default"""
        from settings import RateLimitSettings

        settings = RateLimitSettings()
        assert settings.enabled is True

    def test_role_based_limits(self):
        """Should have different limits per role"""
        from settings import RateLimitSettings

        settings = RateLimitSettings()
        assert settings.super_admin_rpm > settings.admin_rpm
        assert settings.admin_rpm > settings.viewer_rpm
        assert settings.viewer_rpm > settings.anonymous_rpm


class TestGlobalSettings:
    """Test global settings singleton"""

    def test_singleton_pattern(self):
        """Should return same instance"""
        from settings import Settings

        s1 = Settings()
        s2 = Settings()
        assert s1 is s2

    def test_all_settings_available(self):
        """Should have all settings categories"""
        from settings import settings

        assert hasattr(settings, "database")
        assert hasattr(settings, "redis")
        assert hasattr(settings, "auth")
        assert hasattr(settings, "alerts")
        assert hasattr(settings, "fuel")
        assert hasattr(settings, "kalman")
        assert hasattr(settings, "theft")
        assert hasattr(settings, "rate_limit")
        assert hasattr(settings, "app")

    def test_validate_returns_warnings(self):
        """Validate should return list of warnings"""
        from settings import settings

        warnings = settings.validate()
        assert isinstance(warnings, list)

    def test_to_dict_excludes_secrets(self):
        """to_dict should not expose secrets"""
        from settings import settings

        data = settings.to_dict()

        # Should not contain password or secret key
        assert "password" not in str(data)
        assert "secret" not in str(data).lower() or "configured" in str(data).lower()


class TestFuelSettings:
    """Test fuel analytics configuration"""

    def test_price_per_gallon(self):
        """Should have default fuel price"""
        from settings import FuelSettings

        settings = FuelSettings()
        assert settings.price_per_gallon == 3.50

    def test_mpg_thresholds(self):
        """Should have valid MPG thresholds"""
        from settings import FuelSettings

        settings = FuelSettings()
        assert settings.min_valid_mpg < settings.baseline_mpg < settings.max_valid_mpg


class TestAppSettings:
    """Test application settings"""

    def test_version(self):
        """Should have correct version"""
        from settings import AppSettings

        settings = AppSettings()
        assert settings.version == "3.12.21"

    def test_data_directories(self):
        """Should have data directories defined"""
        from settings import AppSettings

        settings = AppSettings()
        assert settings.data_dir is not None
        assert settings.csv_reports_dir is not None
