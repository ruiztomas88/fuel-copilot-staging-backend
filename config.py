"""
Fuel Copilot Configuration
🔧 FIX v3.9.2: Centralized configuration for constants

This module contains all configurable constants used across the system.
Modify these values to customize the behavior of the Fuel Copilot system.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FuelConfig:
    """Fuel-related configuration constants"""

    # Price per gallon of diesel (USD)
    # Source: Average US diesel price as of 2025
    PRICE_PER_GALLON: float = 3.50

    # Baseline MPG for comparison (fleet average for Peterbilt/Kenworth trucks)
    # Trucks below this are flagged as inefficient
    BASELINE_MPG: float = 6.5

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


# Global instances
FUEL = FuelConfig()
IDLE = IdleConfig()
REFUEL = RefuelConfig()
DATABASE = DatabaseConfig()
KALMAN = KalmanConfig()
ALTITUDE = AltitudeConfig()


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
    "FuelConfig",
    "IdleConfig",
    "RefuelConfig",
    "DatabaseConfig",
    "KalmanConfig",
    "AltitudeConfig",
    "get_fuel_price",
    "get_baseline_mpg",
]
