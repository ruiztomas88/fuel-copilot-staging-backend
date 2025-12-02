"""
Wialon to MySQL Sync - Real-time Data Bridge
Reads from Remote Wialon DB and writes to Local MySQL 'wialon_collect.sensors'
Fixes data lag by ensuring local DB has fresh data.
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


def get_local_connection():
    return pymysql.connect(**LOCAL_DB_CONFIG)


def save_to_local_db(connection, truck_id: str, sensor_data: dict):
    """
    Insert sensor data into local fuel_copilot.telemetry_data table
    """
    try:
        with connection.cursor() as cursor:
            # Prepare insert
            measure_dt = sensor_data["timestamp"]

            # Map fields
            # telemetry_data columns: truck_id, timestamp, rpm, speed, fuel_lvl, fuel_rate, engine_hours, odometer, battery_voltage, altitude, hdop

            query = """
                INSERT IGNORE INTO telemetry_data 
                (truck_id, timestamp, rpm, speed, fuel_lvl, fuel_rate, odometer, altitude, hdop)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            values = (
                truck_id,
                measure_dt,
                sensor_data.get("rpm"),
                sensor_data.get("speed"),
                sensor_data.get("fuel_lvl"),
                sensor_data.get("fuel_rate"),
                sensor_data.get("odometer"),
                sensor_data.get("altitude"),
                sensor_data.get("hdop"),
            )

            cursor.execute(query, values)
            return cursor.rowcount

    except Exception as e:
        logger.error(f"Error saving to local DB for truck {truck_id}: {e}")
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
                inserted = save_to_local_db(local_conn, truck_id, sensor_data)
                total_inserted += inserted
                trucks_processed += 1

                # Log status
                status = "🟢" if inserted > 0 else "⚪"
                logger.info(
                    f"{status} {truck_id}: {inserted} records synced (Time: {sensor_data['timestamp'].strftime('%H:%M:%S')})"
                )
            else:
                logger.warning(f"⚠️ {truck_id}: No data from Wialon")

        except Exception as e:
            logger.error(f"Error processing {truck_id}: {e}")

    cycle_duration = time.time() - cycle_start
    logger.info(
        f"⏱️ Cycle completed in {cycle_duration:.2f}s. Total records: {total_inserted}"
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
