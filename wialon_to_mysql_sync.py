"""
Wialon to MySQL Sync - Real-time Data Bridge
Reads from Remote Wialon DB and writes to Local MySQL
Populates fuel_metrics table for backend analytics
"""

import time
import pymysql
from datetime import datetime, timezone
import logging
from wialon_reader import WialonReader, WialonConfig, TRUCK_UNIT_MAPPING

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# Local MySQL Config
LOCAL_DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "fuel_admin",
    "password": "FuelCopilot2025!",
    "database": "fuel_copilot",
    "autocommit": True,
}

# Tank capacities (gallons) - from tanks.yaml
TANK_CAPACITIES = {
    "default": 200,  # Most trucks have ~200 gallon tanks
}


def get_local_connection():
    return pymysql.connect(**LOCAL_DB_CONFIG)


def determine_truck_status(speed, rpm):
    """Determine truck status from speed and RPM"""
    if speed is None:
        return "OFFLINE"
    if speed > 2:
        return "MOVING"
    if rpm and rpm > 500:
        return "IDLE"
    return "STOPPED"


def save_to_fuel_metrics(connection, truck_id: str, sensor_data: dict):
    """
    Insert sensor data into fuel_metrics table for backend analytics
    Uses column names expected by database_mysql.py queries
    """
    try:
        with connection.cursor() as cursor:
            measure_dt = sensor_data["timestamp"]

            # Extract sensor values
            speed = sensor_data.get("speed")  # mph
            rpm = sensor_data.get("rpm")
            fuel_lvl = sensor_data.get("fuel_lvl")  # Percentage
            fuel_rate = sensor_data.get("fuel_rate")  # L/h
            odometer = sensor_data.get("odometer")  # miles
            altitude = sensor_data.get("altitude")  # feet
            latitude = sensor_data.get("latitude")
            longitude = sensor_data.get("longitude")
            engine_hours = sensor_data.get("engine_hours")
            hdop = sensor_data.get("hdop")
            coolant_temp = sensor_data.get("coolant_temp")

            # Derived values
            truck_status = determine_truck_status(speed, rpm)
            tank_capacity = TANK_CAPACITIES.get(truck_id, TANK_CAPACITIES["default"])

            # Calculate fuel in liters/gallons if we have percentage
            estimated_liters = None
            estimated_gallons = None
            estimated_pct = fuel_lvl
            if fuel_lvl is not None:
                estimated_gallons = (fuel_lvl / 100.0) * tank_capacity
                estimated_liters = estimated_gallons * 3.785

            # Convert fuel_rate from L/h to gph
            consumption_lph = fuel_rate
            consumption_gph = None
            if fuel_rate is not None:
                consumption_gph = fuel_rate / 3.785  # L/h to gal/h

            # Calculate MPG if moving
            mpg_current = None
            if speed and speed > 5 and consumption_gph and consumption_gph > 0:
                mpg_current = speed / consumption_gph  # mph / gph = mpg

            # Determine idle method
            idle_method = "NOT_IDLE"
            if truck_status == "IDLE":
                idle_method = "RPM_BASED"
            elif truck_status == "STOPPED" and rpm and rpm > 400:
                idle_method = "FALLBACK_CONSENSUS"

            query = """
                INSERT INTO fuel_metrics 
                (timestamp_utc, truck_id, carrier_id, truck_status,
                 latitude, longitude, speed_mph,
                 estimated_liters, estimated_gallons, estimated_pct,
                 sensor_pct, sensor_liters, sensor_gallons,
                 consumption_lph, consumption_gph, mpg_current,
                 rpm, engine_hours, odometer_mi,
                 altitude_ft, hdop, coolant_temp_f,
                 idle_method, drift_pct, drift_warning,
                 anchor_detected, anchor_type)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    truck_status = VALUES(truck_status),
                    latitude = VALUES(latitude),
                    longitude = VALUES(longitude),
                    speed_mph = VALUES(speed_mph),
                    estimated_liters = VALUES(estimated_liters),
                    estimated_gallons = VALUES(estimated_gallons),
                    estimated_pct = VALUES(estimated_pct),
                    sensor_pct = VALUES(sensor_pct),
                    sensor_liters = VALUES(sensor_liters),
                    sensor_gallons = VALUES(sensor_gallons),
                    consumption_lph = VALUES(consumption_lph),
                    consumption_gph = VALUES(consumption_gph),
                    mpg_current = VALUES(mpg_current),
                    rpm = VALUES(rpm),
                    engine_hours = VALUES(engine_hours),
                    odometer_mi = VALUES(odometer_mi),
                    altitude_ft = VALUES(altitude_ft),
                    hdop = VALUES(hdop),
                    coolant_temp_f = VALUES(coolant_temp_f),
                    idle_method = VALUES(idle_method)
            """

            values = (
                measure_dt,
                truck_id,
                "skylord",  # carrier_id
                truck_status,
                latitude,
                longitude,
                speed,  # speed_mph
                estimated_liters,
                estimated_gallons,
                estimated_pct,
                fuel_lvl,  # sensor_pct (same as fuel_lvl)
                estimated_liters,  # sensor_liters
                estimated_gallons,  # sensor_gallons
                consumption_lph,
                consumption_gph,
                mpg_current,
                int(rpm) if rpm else None,
                engine_hours,
                odometer,  # odometer_mi
                altitude,  # altitude_ft
                hdop,
                coolant_temp,  # coolant_temp_f
                idle_method,
                0.0,  # drift_pct
                "NO",  # drift_warning
                "NO",  # anchor_detected
                "AnchorType.NONE",  # anchor_type
            )

            cursor.execute(query, values)
            return cursor.rowcount

    except Exception as e:
        logger.error(f"Error saving to fuel_metrics for truck {truck_id}: {e}")
        return 0


def sync_cycle(reader: WialonReader, local_conn):
    """Single sync cycle"""
    cycle_start = time.time()

    logger.info("=" * 70)
    logger.info(
        f"🔄 SYNC CYCLE - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    )
    logger.info("=" * 70)

    total_inserted = 0
    trucks_processed = 0

    for truck_id, unit_id in TRUCK_UNIT_MAPPING.items():
        try:
            # Get raw data (dict)
            sensor_data = reader.get_latest_sensor_data(unit_id)

            if sensor_data:
                inserted = save_to_fuel_metrics(local_conn, truck_id, sensor_data)
                total_inserted += inserted
                trucks_processed += 1

                # Log status with more detail
                speed = sensor_data.get("speed")
                fuel = sensor_data.get("fuel_lvl")
                status = "🟢" if inserted > 0 else "⚪"
                speed_str = f"{speed:.1f}" if speed is not None else "N/A"
                fuel_str = f"{fuel:.1f}" if fuel is not None else "N/A"
                logger.info(
                    f"{status} {truck_id}: synced (Speed: {speed_str} mph, Fuel: {fuel_str}%)"
                )
            else:
                logger.warning(f"⚠️ {truck_id}: No data from Wialon")

        except Exception as e:
            logger.error(f"Error processing {truck_id}: {e}")

    cycle_duration = time.time() - cycle_start
    logger.info(
        f"⏱️ Cycle completed in {cycle_duration:.2f}s. Trucks: {trucks_processed}, Records: {total_inserted}"
    )
    logger.info("")


def main():
    logger.info("🚀 WIALON TO MYSQL SYNC STARTING")

    # Initialize Wialon Reader
    wialon_config = WialonConfig()
    reader = WialonReader(wialon_config, TRUCK_UNIT_MAPPING)

    if not reader.connect():
        logger.error("❌ Failed to connect to Remote Wialon DB")
        return

    # Connect to Local DB
    try:
        local_conn = get_local_connection()
        logger.info("✅ Connected to Local MySQL")
    except Exception as e:
        logger.error(f"❌ Failed to connect to Local MySQL: {e}")
        return

    try:
        while True:
            sync_cycle(reader, local_conn)
            time.sleep(15)

            # Keep local connection alive
            local_conn.ping(reconnect=True)

    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        reader.disconnect()
        local_conn.close()


if __name__ == "__main__":
    main()
