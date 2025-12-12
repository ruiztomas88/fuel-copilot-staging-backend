"""
Fuel Copilot Configuration
🔧 FIX v3.9.2: Centralized configuration for constants
🆕 v5.4.2: Added get_allowed_trucks() for centralized fleet filtering

This module contains all configurable constants used across the system.
Modify these values to customize the behavior of the Fuel Copilot system.
"""

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Set

import yaml

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# FLEET FILTERING - CENTRALIZED TRUCK LIST
# ═══════════════════════════════════════════════════════════════════════════════

_cached_allowed_trucks: Optional[Set[str]] = None


def get_allowed_trucks() -> Set[str]:
    """
    🆕 v5.4.2: Centralized function to get allowed truck IDs from tanks.yaml.

    This is THE SINGLE SOURCE OF TRUTH for which trucks to show in all endpoints.
    Use this function instead of hardcoding truck lists.

    Returns:
        Set of truck IDs (e.g., {"VD3579", "JC1282", ...})

    Example:
        from config import get_allowed_trucks
        allowed = get_allowed_trucks()
        if truck_id in allowed:
            # process truck
    """
    global _cached_allowed_trucks

    # Return cached value if available
    if _cached_allowed_trucks is not None:
        return _cached_allowed_trucks

    try:
        tanks_path = Path(__file__).parent / "tanks.yaml"
        if tanks_path.exists():
            with open(tanks_path, "r", encoding="utf-8") as f:
                tanks_config = yaml.safe_load(f)
                if tanks_config and "trucks" in tanks_config:
                    _cached_allowed_trucks = set(tanks_config["trucks"].keys())
                    logger.info(
                        f"✅ Loaded {len(_cached_allowed_trucks)} trucks from tanks.yaml"
                    )
                    return _cached_allowed_trucks
    except Exception as e:
        logger.warning(f"⚠️ Could not load tanks.yaml: {e}")

    # Fallback: hardcoded list (same as database_mysql.py)
    logger.warning("⚠️ Using hardcoded fallback truck list")
    _cached_allowed_trucks = {
        "VD3579",
        "JC1282",
        "JC9352",
        "NQ6975",
        "GP9677",
        "JB8004",
        "FM2416",
        "FM3679",
        "FM9838",
        "JB6858",
        "JP3281",
        "JR7099",
        "RA9250",
        "RH1522",
        "RR1272",
        "BV6395",
        "CO0681",
        "CS8087",
        "DR6664",
        "DO9356",
        "DO9693",
        "FS7166",
        "MA8159",
        "MO0195",
        "PC1280",
        "RD5229",
        "RR3094",
        "RT9127",
        "SG5760",
        "YM6023",
        "MJ9547",
        "FM3363",
        "GC9751",
        "LV1422",
        "LC6799",
        "RC6625",
        "FF7702",
        "OG2033",
        "OS3717",
        "EM8514",
        "MR7679",
        "OM7769",
        "LH1141",
    }
    return _cached_allowed_trucks


def reload_allowed_trucks() -> Set[str]:
    """
    Force reload of allowed trucks from tanks.yaml.
    Use this after modifying tanks.yaml to update the cache.
    """
    global _cached_allowed_trucks
    _cached_allowed_trucks = None
    return get_allowed_trucks()


@dataclass(frozen=True)
class FuelConfig:
    """Fuel-related configuration constants"""

    # Price per gallon of diesel (USD)
    # Source: Average US diesel price as of 2025
    PRICE_PER_GALLON: float = 3.50

    # Baseline MPG for comparison (fleet average for Peterbilt/Kenworth trucks)
    # Based on fleet analysis: 30 trucks, 42K records, avg 5.72 MPG (v3.12.31)
    BASELINE_MPG: float = 5.7

    # Minimum MPG to consider valid (filters noise)
    MIN_VALID_MPG: float = 3.5

    # Maximum MPG to consider valid (filters noise/errors)
    MAX_VALID_MPG: float = 12.0


@dataclass(frozen=True)
class IdleConfig:
    """Idle detection configuration"""

    # Minimum GPH to consider idle (filters noise)
    MIN_IDLE_GPH: float = 0.1

    # Maximum GPH for valid idle (anything higher is likely moving)
    MAX_IDLE_GPH: float = 5.0

    # Speed threshold for "stopped" status (mph)
    STOPPED_SPEED_THRESHOLD: float = 5.0


@dataclass(frozen=True)
class RefuelConfig:
    """Refuel detection configuration"""

    # Minimum gallons to consider a refuel event
    MIN_REFUEL_GALLONS: float = 5.0

    # Minimum % jump to trigger refuel detection
    MIN_JUMP_PCT: float = 10.0

    # Maximum % jump (above this is sensor recovery, not refuel)
    MAX_JUMP_PCT: float = 95.0


@dataclass(frozen=True)
class DatabaseConfig:
    """MySQL database configuration"""

    HOST: str = os.getenv("MYSQL_HOST", "localhost")
    PORT: int = int(os.getenv("MYSQL_PORT", "3306"))
    USER: str = os.getenv("MYSQL_USER", "fuel_admin")
    PASSWORD: str = os.getenv("MYSQL_PASSWORD", "FuelCopilot2025!")
    DATABASE: str = os.getenv("MYSQL_DATABASE", "fuel_copilot")
    CHARSET: str = "utf8mb4"

    # Connection pool settings
    POOL_SIZE: int = 10
    MAX_OVERFLOW: int = 5
    POOL_RECYCLE: int = 3600  # 1 hour in seconds


@dataclass(frozen=True)
class KalmanConfig:
    """Kalman filter configuration"""

    # Process noise (controls smoothing aggressiveness)
    PROCESS_NOISE: float = 0.05

    # Measurement noise (controls trust in sensor)
    MEASUREMENT_NOISE: float = 2.0

    # Initial estimate uncertainty
    INITIAL_UNCERTAINTY: float = 10.0


@dataclass(frozen=True)
class AltitudeConfig:
    """Altitude-related configuration"""

    # Threshold for high altitude penalty (feet)
    HIGH_ALTITUDE_FT: float = 3000.0

    # MPG penalty per 1000 ft above threshold (%)
    PENALTY_PER_1000FT: float = 3.0


@dataclass(frozen=True)
class TimezoneConfig:
    """Timezone configuration for consistent time handling"""

    # System timezone (database stores in this timezone)
    SYSTEM_TZ: str = "America/New_York"

    # Display timezone for reports
    DISPLAY_TZ: str = "America/New_York"

    # UTC offset for manual calculations (hours)
    UTC_OFFSET_HOURS: int = -5  # EST (changes with DST)

    # Data freshness thresholds (minutes)
    STALE_DATA_MINUTES: int = 15
    OFFLINE_THRESHOLD_MINUTES: int = 60


# Global instances
FUEL = FuelConfig()
IDLE = IdleConfig()
REFUEL = RefuelConfig()
DATABASE = DatabaseConfig()
KALMAN = KalmanConfig()
ALTITUDE = AltitudeConfig()
TIMEZONE = TimezoneConfig()


# Convenience functions for backward compatibility
def get_fuel_price() -> float:
    """Get current fuel price per gallon"""
    return FUEL.PRICE_PER_GALLON


def get_baseline_mpg() -> float:
    """Get baseline MPG for efficiency comparisons"""
    return FUEL.BASELINE_MPG


# Export all for easy importing
__all__ = [
    "FUEL",
    "IDLE",
    "REFUEL",
    "DATABASE",
    "KALMAN",
    "ALTITUDE",
    "TIMEZONE",
    "FuelConfig",
    "IdleConfig",
    "RefuelConfig",
    "DatabaseConfig",
    "KalmanConfig",
    "AltitudeConfig",
    "TimezoneConfig",
    "get_fuel_price",
    "get_baseline_mpg",
    "get_allowed_trucks",
    "reload_allowed_trucks",
]
