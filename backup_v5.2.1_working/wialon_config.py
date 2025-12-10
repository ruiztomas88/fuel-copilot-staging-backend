"""
Wialon Database Configuration
Store Wialon connection details for data synchronization

⚠️ SECURITY: Credentials are loaded from environment variables.
Set these in your .env file or system environment:
  - WIALON_DB_HOST
  - WIALON_DB_PORT
  - WIALON_DB_USER
  - WIALON_DB_PASS
  - WIALON_DB_NAME
"""

import os
from dotenv import load_dotenv

# Load .env file if exists
load_dotenv()

WIALON_DB_CONFIG = {
    "host": os.getenv("WIALON_DB_HOST", "localhost"),
    "port": int(os.getenv("WIALON_DB_PORT", "3306")),
    "user": os.getenv("WIALON_DB_USER", ""),
    "password": os.getenv("WIALON_DB_PASS", ""),
    "database": os.getenv("WIALON_DB_NAME", "wialon_collect"),
    "connect_timeout": 15,
}

# Validate required credentials at import time
if not WIALON_DB_CONFIG["host"] or not WIALON_DB_CONFIG["user"]:
    import logging

    logging.warning(
        "⚠️ WIALON credentials not set! Please configure .env file with:\n"
        "  WIALON_DB_HOST=your_host\n"
        "  WIALON_DB_USER=your_user\n"
        "  WIALON_DB_PASS=your_password\n"
        "  WIALON_DB_NAME=your_database"
    )

# Mapeo de sensores de Wialon a nuestro sistema
SENSOR_NAME_MAPPING = {
    # Wialon Name -> Our System Name
    "GPS Speed": "speed",
    "Engine Speed": "rpm",
    "RPM": "rpm",
    "Fuel Level": "fuel_lvl",
    "Fuel Rate": "fuel_rate",
    "Engine Hours": "engine_hours",
    "Odometer": "odometer",
    "Coolant Temperature": "cool_temp",
    "Altitude": "altitude",
    "DOP": "hdop",
    "Oil Pressure": "oil_pressure",
    "Oil Temperature": "oil_temp",
    "Engine Load": "engine_load",
    "Battery": "battery_voltage",
}

# Sensores requeridos para funcionamiento correcto
REQUIRED_SENSORS = [
    "rpm",  # Para detectar engine ON/OFF
    "speed",  # Para detectar movimiento
    "fuel_lvl",  # Para nivel de combustible
    "fuel_rate",  # Para consumo en IDLE
    "engine_hours",  # Para fallback de engine ON
    "odometer",  # Para detectar movimiento por distancia
]
