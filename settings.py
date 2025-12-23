"""
Fuel Copilot Settings v3.12.21
Centralized configuration from environment variables

This replaces all hardcoded values across the application.
All sensitive data MUST come from environment variables.
"""

import os
import secrets
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def _get_env(key: str, default: str = "", required: bool = False) -> str:
    """Get environment variable with optional requirement enforcement."""
    value = os.getenv(key, default)
    if required and not value:
        raise ValueError(f"Required environment variable {key} is not set!")
    return value


def _get_env_int(key: str, default: int) -> int:
    """Get integer environment variable."""
    return int(os.getenv(key, str(default)))


def _get_env_float(key: str, default: float) -> float:
    """Get float environment variable."""
    return float(os.getenv(key, str(default)))


def _get_env_bool(key: str, default: bool = False) -> bool:
    """Get boolean environment variable."""
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


def _get_env_list(key: str, default: str = "", separator: str = ",") -> List[str]:
    """Get list from comma-separated environment variable."""
    value = os.getenv(key, default)
    return [item.strip() for item in value.split(separator) if item.strip()]


# =============================================================================
# DATABASE SETTINGS
# =============================================================================
@dataclass
class DatabaseSettings:
    """MySQL database configuration - ALL from environment."""

    host: str = field(default_factory=lambda: _get_env("MYSQL_HOST", "localhost"))
    port: int = field(default_factory=lambda: _get_env_int("MYSQL_PORT", 3306))
    user: str = field(default_factory=lambda: _get_env("MYSQL_USER", "fuel_admin"))
    password: str = field(default_factory=lambda: _get_env("MYSQL_PASSWORD", ""))
    database: str = field(
        default_factory=lambda: _get_env("MYSQL_DATABASE", "fuel_copilot")
    )
    charset: str = "utf8mb4"

    # Connection pool
    pool_size: int = field(default_factory=lambda: _get_env_int("MYSQL_POOL_SIZE", 10))
    max_overflow: int = field(
        default_factory=lambda: _get_env_int("MYSQL_MAX_OVERFLOW", 5)
    )
    pool_recycle: int = field(
        default_factory=lambda: _get_env_int("MYSQL_POOL_RECYCLE", 3600)
    )

    def get_connection_dict(self) -> Dict:
        """Return connection dictionary for pymysql."""
        return {
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "password": self.password,
            "database": self.database,
            "charset": self.charset,
            "autocommit": True,
        }


# =============================================================================
# REDIS SETTINGS
# =============================================================================
@dataclass
class RedisSettings:
    """
    Redis cache configuration.

    🆕 v3.12.21: Redis now enabled by default for better performance.
    Set REDIS_ENABLED=false to disable if Redis is not available.
    """

    enabled: bool = field(default_factory=lambda: _get_env_bool("REDIS_ENABLED", True))
    host: str = field(default_factory=lambda: _get_env("REDIS_HOST", "localhost"))
    port: int = field(default_factory=lambda: _get_env_int("REDIS_PORT", 6379))
    password: Optional[str] = field(
        default_factory=lambda: _get_env("REDIS_PASSWORD") or None
    )
    ssl: bool = field(default_factory=lambda: _get_env_bool("REDIS_SSL", False))
    db: int = field(default_factory=lambda: _get_env_int("REDIS_DB", 0))

    # TTL settings (seconds)
    default_ttl: int = field(
        default_factory=lambda: _get_env_int("REDIS_DEFAULT_TTL", 300)
    )
    fleet_summary_ttl: int = field(
        default_factory=lambda: _get_env_int("REDIS_FLEET_TTL", 30)
    )
    truck_detail_ttl: int = field(
        default_factory=lambda: _get_env_int("REDIS_TRUCK_TTL", 60)
    )


# =============================================================================
# JWT/AUTH SETTINGS
# =============================================================================
@dataclass
class AuthSettings:
    """Authentication configuration."""

    # JWT - MUST be set in production!
    secret_key: str = field(
        default_factory=lambda: (
            _get_env("JWT_SECRET_KEY") or secrets.token_urlsafe(32)
        )
    )
    algorithm: str = "HS256"
    token_expire_hours: int = field(
        default_factory=lambda: _get_env_int("JWT_EXPIRE_HOURS", 168)
    )

    # Password hashing
    password_salt: str = field(
        default_factory=lambda: _get_env("PASSWORD_SALT", "fuel-copilot-salt")
    )

    @property
    def is_production_ready(self) -> bool:
        """Check if JWT secret is properly configured."""
        return bool(os.getenv("JWT_SECRET_KEY"))


# =============================================================================
# ALERT SETTINGS
# =============================================================================
@dataclass
class AlertSettings:
    """Alert and notification configuration."""

    # Twilio SMS
    twilio_account_sid: str = field(
        default_factory=lambda: _get_env("TWILIO_ACCOUNT_SID", "")
    )
    twilio_auth_token: str = field(
        default_factory=lambda: _get_env("TWILIO_AUTH_TOKEN", "")
    )
    twilio_from_number: str = field(
        default_factory=lambda: _get_env("TWILIO_FROM_NUMBER", "")
    )
    twilio_to_numbers: List[str] = field(
        default_factory=lambda: _get_env_list("TWILIO_TO_NUMBERS")
    )
    twilio_whatsapp_from: str = field(
        default_factory=lambda: _get_env("TWILIO_WHATSAPP_FROM", "")
    )

    # SMTP Email
    smtp_server: str = field(
        default_factory=lambda: _get_env("SMTP_SERVER", "smtp-mail.outlook.com")
    )
    smtp_port: int = field(default_factory=lambda: _get_env_int("SMTP_PORT", 587))
    smtp_user: str = field(default_factory=lambda: _get_env("SMTP_USER", ""))
    smtp_password: str = field(default_factory=lambda: _get_env("SMTP_PASSWORD", ""))
    alert_email_to: str = field(default_factory=lambda: _get_env("ALERT_EMAIL_TO", ""))

    # Unified cooldown (in minutes)
    cooldown_minutes: int = field(
        default_factory=lambda: _get_env_int("ALERT_COOLDOWN_MINUTES", 30)
    )
    refuel_cooldown_minutes: int = field(
        default_factory=lambda: _get_env_int("REFUEL_COOLDOWN_MINUTES", 30)
    )

    # Thresholds
    low_fuel_critical_pct: float = field(
        default_factory=lambda: _get_env_float("LOW_FUEL_CRITICAL_PCT", 10.0)
    )
    low_fuel_warning_pct: float = field(
        default_factory=lambda: _get_env_float("LOW_FUEL_WARNING_PCT", 20.0)
    )
    theft_min_confidence: float = field(
        default_factory=lambda: _get_env_float("THEFT_MIN_CONFIDENCE", 0.7)
    )
    theft_min_gallons: float = field(
        default_factory=lambda: _get_env_float("THEFT_MIN_GALLONS", 10.0)
    )

    # Low fuel SMS enabled
    low_fuel_sms_enabled: bool = field(
        default_factory=lambda: _get_env_bool("LOW_FUEL_SMS_ENABLED", True)
    )

    @property
    def twilio_configured(self) -> bool:
        """Check if Twilio is properly configured."""
        return bool(
            self.twilio_account_sid
            and self.twilio_auth_token
            and self.twilio_from_number
        )

    @property
    def smtp_configured(self) -> bool:
        """Check if SMTP is properly configured."""
        return bool(self.smtp_user and self.smtp_password and self.alert_email_to)


# =============================================================================
# CARRIER/MULTI-TENANT SETTINGS
# =============================================================================
@dataclass
class CarrierSettings:
    """Multi-tenant carrier configuration."""

    default_carrier_id: str = field(
        default_factory=lambda: _get_env("DEFAULT_CARRIER_ID", "skylord")
    )

    # Tank capacities file
    tank_capacities_file: Path = field(
        default_factory=lambda: Path(__file__).parent / "tanks.yaml"
    )
    default_tank_capacity: float = field(
        default_factory=lambda: _get_env_float("DEFAULT_TANK_CAPACITY", 200.0)
    )


# =============================================================================
# FUEL ANALYTICS SETTINGS
# =============================================================================
@dataclass
class FuelSettings:
    """Fuel analytics configuration."""

    # Pricing
    price_per_gallon: float = field(
        default_factory=lambda: _get_env_float("FUEL_PRICE_PER_GALLON", 3.50)
    )

    # Efficiency baselines (v3.12.31: Updated based on 42K records fleet analysis)
    # Fleet avg: 5.72 MPG | Highway: 6.7 MPG | City: 4.2 MPG
    baseline_mpg: float = field(
        default_factory=lambda: _get_env_float("BASELINE_MPG", 5.7)
    )
    min_valid_mpg: float = field(
        default_factory=lambda: _get_env_float("MIN_VALID_MPG", 3.5)
    )
    max_valid_mpg: float = field(
        default_factory=lambda: _get_env_float("MAX_VALID_MPG", 12.0)
    )

    # Idle thresholds
    min_idle_gph: float = field(
        default_factory=lambda: _get_env_float("MIN_IDLE_GPH", 0.1)
    )
    max_idle_gph: float = field(
        default_factory=lambda: _get_env_float("MAX_IDLE_GPH", 5.0)
    )
    stopped_speed_threshold: float = field(
        default_factory=lambda: _get_env_float("STOPPED_SPEED_THRESHOLD", 5.0)
    )

    # Refuel detection
    # 🔧 v5.19.1: Reduced thresholds to catch more refuels (was 5.0 gal / 10.0%)
    # Many trucks do partial refuels (10-15 gal) that were being missed
    min_refuel_gallons: float = field(
        default_factory=lambda: _get_env_float("MIN_REFUEL_GALLONS", 3.0)
    )
    min_refuel_jump_pct: float = field(
        default_factory=lambda: _get_env_float("MIN_REFUEL_JUMP_PCT", 8.0)
    )
    max_refuel_jump_pct: float = field(
        default_factory=lambda: _get_env_float("MAX_REFUEL_JUMP_PCT", 95.0)
    )


# =============================================================================
# KALMAN FILTER SETTINGS
# =============================================================================
@dataclass
class KalmanSettings:
    """Kalman filter configuration."""

    process_noise: float = field(
        default_factory=lambda: _get_env_float("KALMAN_PROCESS_NOISE", 0.1)
    )
    measurement_noise_moving: float = field(
        default_factory=lambda: _get_env_float("KALMAN_NOISE_MOVING", 4.0)
    )
    measurement_noise_static: float = field(
        default_factory=lambda: _get_env_float("KALMAN_NOISE_STATIC", 1.0)
    )
    max_drift_pct: float = field(
        default_factory=lambda: _get_env_float("KALMAN_MAX_DRIFT_PCT", 7.5)
    )
    emergency_drift_threshold: float = field(
        default_factory=lambda: _get_env_float("KALMAN_EMERGENCY_DRIFT", 30.0)
    )


# =============================================================================
# THEFT DETECTION SETTINGS (Enhanced #10)
# =============================================================================
@dataclass
class TheftDetectionSettings:
    """Enhanced theft detection configuration."""

    # Basic thresholds
    min_drop_pct: float = field(
        default_factory=lambda: _get_env_float("THEFT_MIN_DROP_PCT", 10.0)
    )
    min_drop_gallons: float = field(
        default_factory=lambda: _get_env_float("THEFT_MIN_DROP_GALLONS", 10.0)
    )

    # Enhanced detection criteria
    min_consecutive_readings: int = field(
        default_factory=lambda: _get_env_int("THEFT_MIN_READINGS", 3)
    )
    min_duration_minutes: int = field(
        default_factory=lambda: _get_env_int("THEFT_MIN_DURATION_MINUTES", 5)
    )
    max_speed_for_theft: float = field(
        default_factory=lambda: _get_env_float("THEFT_MAX_SPEED", 2.0)
    )

    # Noise filtering
    sensor_noise_tolerance_pct: float = field(
        default_factory=lambda: _get_env_float("THEFT_NOISE_TOLERANCE", 2.0)
    )
    temperature_adjustment_enabled: bool = field(
        default_factory=lambda: _get_env_bool("THEFT_TEMP_ADJUSTMENT", True)
    )

    # Confidence scoring
    high_confidence_threshold: float = field(
        default_factory=lambda: _get_env_float("THEFT_HIGH_CONFIDENCE", 0.85)
    )
    medium_confidence_threshold: float = field(
        default_factory=lambda: _get_env_float("THEFT_MEDIUM_CONFIDENCE", 0.6)
    )


# =============================================================================
# RATE LIMITING SETTINGS (#31)
# =============================================================================
@dataclass
class RateLimitSettings:
    """API rate limiting configuration."""

    enabled: bool = field(
        default_factory=lambda: _get_env_bool("RATE_LIMIT_ENABLED", True)
    )

    # Requests per minute by role
    super_admin_rpm: int = field(
        default_factory=lambda: _get_env_int("RATE_LIMIT_SUPER_ADMIN", 1000)
    )
    admin_rpm: int = field(
        default_factory=lambda: _get_env_int("RATE_LIMIT_ADMIN", 300)
    )
    viewer_rpm: int = field(
        default_factory=lambda: _get_env_int("RATE_LIMIT_VIEWER", 100)
    )
    anonymous_rpm: int = field(
        default_factory=lambda: _get_env_int("RATE_LIMIT_ANONYMOUS", 30)
    )

    # Burst allowance
    burst_multiplier: float = field(
        default_factory=lambda: _get_env_float("RATE_LIMIT_BURST", 1.5)
    )


# =============================================================================
# WIALON SETTINGS
# =============================================================================
@dataclass
class WialonSettings:
    """Wialon API configuration."""

    api_url: str = field(
        default_factory=lambda: _get_env(
            "WIALON_API_URL", "https://hst-api.wialon.com/wialon/ajax.html"
        )
    )
    token: str = field(default_factory=lambda: _get_env("WIALON_TOKEN", ""))
    sync_interval_seconds: int = field(
        default_factory=lambda: _get_env_int("WIALON_SYNC_INTERVAL", 30)
    )


# =============================================================================
# APPLICATION SETTINGS
# =============================================================================
@dataclass
class AppSettings:
    """General application settings."""

    debug: bool = field(default_factory=lambda: _get_env_bool("DEBUG", False))
    log_level: str = field(default_factory=lambda: _get_env("LOG_LEVEL", "INFO"))
    version: str = "4.0.0"  # 🆕 v4.0.0: Redis caching, distributed rate limiting

    # Data directories
    data_dir: Path = field(default_factory=lambda: Path(__file__).parent / "data")
    csv_reports_dir: Path = field(
        default_factory=lambda: Path(__file__).parent / "data" / "csv_reports"
    )

    # Timezone
    system_tz: str = field(
        default_factory=lambda: _get_env("SYSTEM_TZ", "America/New_York")
    )
    display_tz: str = field(
        default_factory=lambda: _get_env("DISPLAY_TZ", "America/New_York")
    )


# =============================================================================
# GLOBAL SETTINGS INSTANCE
# =============================================================================
class Settings:
    """Global settings container - singleton pattern."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        """Initialize all settings."""
        self.database = DatabaseSettings()
        self.redis = RedisSettings()
        self.auth = AuthSettings()
        self.alerts = AlertSettings()
        self.carrier = CarrierSettings()
        self.fuel = FuelSettings()
        self.kalman = KalmanSettings()
        self.theft = TheftDetectionSettings()
        self.rate_limit = RateLimitSettings()
        self.wialon = WialonSettings()
        self.app = AppSettings()

    def validate(self) -> List[str]:
        """Validate settings and return list of warnings."""
        warnings = []

        if not self.auth.is_production_ready:
            warnings.append(
                "⚠️ JWT_SECRET_KEY not set - using random key (sessions won't persist)"
            )

        if not self.database.password:
            warnings.append("⚠️ MYSQL_PASSWORD not set")

        if not self.alerts.twilio_configured:
            warnings.append("ℹ️ Twilio not configured - SMS alerts disabled")

        if not self.alerts.smtp_configured:
            warnings.append("ℹ️ SMTP not configured - Email alerts disabled")

        if not self.redis.enabled:
            warnings.append("ℹ️ Redis disabled - using in-memory caching")

        return warnings

    def to_dict(self) -> Dict:
        """Export settings as dictionary (for debugging, excludes secrets)."""
        return {
            "version": self.app.version,
            "debug": self.app.debug,
            "database_host": self.database.host,
            "redis_enabled": self.redis.enabled,
            "redis_host": self.redis.host if self.redis.enabled else None,
            "auth_configured": self.auth.is_production_ready,
            "twilio_configured": self.alerts.twilio_configured,
            "smtp_configured": self.alerts.smtp_configured,
            "rate_limit_enabled": self.rate_limit.enabled,
        }


# Create global settings instance
settings = Settings()


# For backward compatibility
def get_settings() -> Settings:
    """Get global settings instance."""
    return settings


# Export commonly used settings
DATABASE = settings.database
REDIS = settings.redis
AUTH = settings.auth
ALERTS = settings.alerts
FUEL = settings.fuel
KALMAN = settings.kalman
THEFT = settings.theft
RATE_LIMIT = settings.rate_limit
APP = settings.app
