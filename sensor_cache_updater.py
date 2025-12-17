"""
Sensor Cache Updater Service
=============================
Updates truck_sensors_cache table every 30 seconds with latest Wialon data.
This allows fast dashboard queries instead of expensive Wialon queries on every request.

Run as background service:
    python sensor_cache_updater.py

Or with systemd/supervisor for auto-restart.
"""

import pymysql
import time
import os
import yaml
import logging
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from typing import Dict, List, Any, Optional

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Database configurations
WIALON_CONFIG = {
    "host": os.getenv("WIALON_DB_HOST", "20.127.200.135"),
    "port": int(os.getenv("WIALON_DB_PORT", "3306")),
    "database": os.getenv("WIALON_DB_NAME", "wialon_collect"),
    "user": os.getenv("WIALON_DB_USER", "tomas"),
    "password": os.getenv("WIALON_DB_PASS", "Tomas2025"),
    "connect_timeout": 30,
}

FUEL_COPILOT_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": os.getenv("MYSQL_USER", "fuel_admin"),
    "password": os.getenv("MYSQL_PASSWORD", "FuelCopilot2025!"),
    "database": "fuel_copilot",
}

UPDATE_INTERVAL = 30  # seconds


def load_truck_config() -> Dict[str, Dict]:
    """Load truck configuration from tanks.yaml"""
    tanks_path = Path(__file__).parent / "tanks.yaml"
    try:
        with open(tanks_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
            return config.get("trucks", {})
    except Exception as e:
        logger.error(f"Failed to load tanks.yaml: {e}")
        return {}


def get_sensor_data_from_wialon(unit_id: int) -> Optional[Dict[str, Any]]:
    """
    Get latest sensor data for a unit from Wialon.
    Uses same logic as the API endpoint (Last Known Value strategy).
    """
    try:
        conn = pymysql.connect(**WIALON_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        cutoff_epoch = int(time.time()) - 3600  # Last hour

        query = """
            SELECT 
                p as param_name,
                value,
                m as epoch_time,
                from_latitude as latitude,
                from_longitude as longitude
            FROM sensors
            WHERE unit = %s
                AND m >= %s
            ORDER BY m DESC
            LIMIT 2000
        """

        cursor.execute(query, (unit_id, cutoff_epoch))
        results = cursor.fetchall()
        cursor.close()
        conn.close()

        if not results:
            return None

        # Get latest timestamp and GPS
        latest_epoch = results[0]["epoch_time"]
        latitude = results[0].get("latitude")
        longitude = results[0].get("longitude")

        # Build sensor dict using Last Known Value strategy
        sensor_dict = {}
        for row in results:
            param = row["param_name"]
            value = row["value"]

            # Only use values from latest timestamp first
            if row["epoch_time"] == latest_epoch and param and value is not None:
                sensor_dict[param] = value

        # Fill missing values from recent history (within 15 minutes)
        for row in results:
            age_sec = latest_epoch - row["epoch_time"]
            if age_sec > 900:  # 15 minutes
                break

            param = row["param_name"]
            value = row["value"]

            if param and value is not None and param not in sensor_dict:
                sensor_dict[param] = value

        # Calculate data age
        data_age_seconds = int(time.time()) - latest_epoch

        return {
            "epoch_time": latest_epoch,
            "data_age_seconds": data_age_seconds,
            "latitude": latitude,
            "longitude": longitude,
            "sensors": sensor_dict,
        }

    except Exception as e:
        logger.error(f"Error reading sensor data for unit {unit_id}: {e}")
        return None


def update_sensor_cache():
    """Update truck_sensors_cache table with latest data from Wialon"""
    truck_config = load_truck_config()

    if not truck_config:
        logger.warning("No trucks configured in tanks.yaml")
        return

    conn = pymysql.connect(**FUEL_COPILOT_CONFIG)
    cursor = conn.cursor()

    updated_count = 0
    error_count = 0

    for truck_id, config in truck_config.items():
        unit_id = config.get("unit_id")
        if not unit_id:
            continue

        try:
            # Get sensor data from Wialon
            data = get_sensor_data_from_wialon(unit_id)

            if not data:
                logger.debug(f"No recent data for {truck_id}")
                continue

            sensors = data["sensors"]
            epoch_time = data["epoch_time"]
            timestamp = datetime.fromtimestamp(epoch_time, tz=timezone.utc)

            # Helper function to get sensor value
            def get_val(key, default=None):
                val = sensors.get(key, default)
                return val if val is not None else default

            # Build INSERT/UPDATE query
            upsert_sql = """
                INSERT INTO truck_sensors_cache (
                    truck_id, unit_id, timestamp, wialon_epoch,
                    oil_pressure_psi, oil_temp_f, oil_level_pct,
                    def_level_pct,
                    engine_load_pct, rpm, coolant_temp_f, coolant_level_pct,
                    gear, brake_active,
                    intake_pressure_bar, intake_temp_f, intercooler_temp_f,
                    fuel_temp_f, fuel_level_pct, fuel_rate_gph,
                    ambient_temp_f, barometric_pressure_inhg,
                    voltage, backup_voltage,
                    engine_hours, idle_hours, pto_hours,
                    total_idle_fuel_gal, total_fuel_used_gal,
                    dtc_count, dtc_code,
                    latitude, longitude, speed_mph, altitude_ft, odometer_mi,
                    data_age_seconds
                ) VALUES (
                    %s, %s, %s, %s,
                    %s, %s, %s,
                    %s,
                    %s, %s, %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s,
                    %s, %s,
                    %s, %s,
                    %s, %s, %s, %s,
                    %s
                )
                ON DUPLICATE KEY UPDATE
                    unit_id = VALUES(unit_id),
                    timestamp = VALUES(timestamp),
                    wialon_epoch = VALUES(wialon_epoch),
                    oil_pressure_psi = VALUES(oil_pressure_psi),
                    oil_temp_f = VALUES(oil_temp_f),
                    oil_level_pct = VALUES(oil_level_pct),
                    def_level_pct = VALUES(def_level_pct),
                    engine_load_pct = VALUES(engine_load_pct),
                    rpm = VALUES(rpm),
                    coolant_temp_f = VALUES(coolant_temp_f),
                    coolant_level_pct = VALUES(coolant_level_pct),
                    gear = VALUES(gear),
                    brake_active = VALUES(brake_active),
                    intake_pressure_bar = VALUES(intake_pressure_bar),
                    intake_temp_f = VALUES(intake_temp_f),
                    intercooler_temp_f = VALUES(intercooler_temp_f),
                    fuel_temp_f = VALUES(fuel_temp_f),
                    fuel_level_pct = VALUES(fuel_level_pct),
                    fuel_rate_gph = VALUES(fuel_rate_gph),
                    ambient_temp_f = VALUES(ambient_temp_f),
                    barometric_pressure_inhg = VALUES(barometric_pressure_inhg),
                    voltage = VALUES(voltage),
                    backup_voltage = VALUES(backup_voltage),
                    engine_hours = VALUES(engine_hours),
                    idle_hours = VALUES(idle_hours),
                    pto_hours = VALUES(pto_hours),
                    total_idle_fuel_gal = VALUES(total_idle_fuel_gal),
                    total_fuel_used_gal = VALUES(total_fuel_used_gal),
                    dtc_count = VALUES(dtc_count),
                    dtc_code = VALUES(dtc_code),
                    latitude = VALUES(latitude),
                    longitude = VALUES(longitude),
                    speed_mph = VALUES(speed_mph),
                    altitude_ft = VALUES(altitude_ft),
                    odometer_mi = VALUES(odometer_mi),
                    data_age_seconds = VALUES(data_age_seconds)
            """

            cursor.execute(
                upsert_sql,
                (
                    truck_id,
                    unit_id,
                    timestamp,
                    epoch_time,
                    # Oil
                    get_val("oil_press"),
                    get_val("oil_temp"),
                    get_val("oil_lvl"),
                    # DEF
                    get_val("def_level"),
                    # Engine
                    get_val("engine_load"),
                    get_val("rpm"),
                    get_val("cool_temp"),
                    get_val("cool_lvl"),
                    # Transmission & Brakes
                    get_val("gear"),
                    1 if get_val("brake_switch") else 0,
                    # Air Intake
                    get_val("intake_pressure"),
                    get_val("intk_t"),
                    get_val("intrclr_t"),
                    # Fuel
                    get_val("fuel_t"),
                    get_val("fuel_lvl"),
                    get_val("fuel_rate"),
                    # Environmental
                    get_val("ambient_temp"),
                    get_val("barometer"),
                    # Electrical
                    get_val("pwr_ext"),
                    get_val("pwr_int"),
                    # Operational
                    get_val("engine_hours"),
                    get_val("idle_hours"),
                    get_val("pto_hours"),
                    get_val("total_idle_fuel"),
                    get_val("total_fuel_used"),
                    # DTC
                    get_val("dtc"),
                    get_val("dtc_code"),
                    # GPS
                    data.get("latitude"),
                    data.get("longitude"),
                    get_val("speed"),
                    get_val("altitude"),
                    get_val("odometer"),  # Odometer in miles
                    # Metadata
                    data["data_age_seconds"],
                ),
            )

            updated_count += 1

        except Exception as e:
            logger.error(f"Error updating cache for {truck_id}: {e}")
            error_count += 1

    conn.commit()
    cursor.close()
    conn.close()

    logger.info(f"✅ Updated {updated_count} trucks, {error_count} errors")


def main():
    """Main service loop"""
    logger.info("🚀 Starting Sensor Cache Updater Service")
    logger.info(f"Update interval: {UPDATE_INTERVAL} seconds")

    iteration = 0

    while True:
        try:
            iteration += 1
            start_time = time.time()

            logger.info(f"--- Iteration {iteration} ---")
            update_sensor_cache()

            elapsed = time.time() - start_time
            logger.info(f"Update completed in {elapsed:.2f}s")

            # Sleep for remaining time
            sleep_time = max(0, UPDATE_INTERVAL - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

        except KeyboardInterrupt:
            logger.info("🛑 Service stopped by user")
            break
        except Exception as e:
            logger.error(f"Error in main loop: {e}", exc_info=True)
            time.sleep(UPDATE_INTERVAL)


if __name__ == "__main__":
    main()
