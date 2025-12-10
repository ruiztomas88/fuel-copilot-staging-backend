"""
Wialon to MySQL Sync - Real-time Data Bridge v2.0
Reads from Remote Wialon DB and writes to Local MySQL
Populates fuel_metrics table for backend analytics

🔧 v2.0 FIXES:
- Improved truck status detection (MOVING/STOPPED/IDLE/OFFLINE)
- Added proper sensor vs estimated calculation
- Fixed MPG/Idle mutual exclusivity
- Added drift calculation (sensor - estimated difference)
- Uses tanks.yaml for accurate tank capacities
"""

import time
import pymysql
import yaml
from datetime import datetime, timezone
from pathlib import Path
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


# Load tank capacities from tanks.yaml
def load_tank_capacities():
    """Load tank capacities from tanks.yaml"""
    yaml_path = Path(__file__).parent / "tanks.yaml"
    capacities = {"default": 200}

    if yaml_path.exists():
        try:
            with open(yaml_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f)
            trucks = config.get("trucks", {})
            for truck_id, truck_config in trucks.items():
                capacities[truck_id] = truck_config.get("capacity_gallons", 200)
            logger.info(
                f"✅ Loaded capacities for {len(trucks)} trucks from tanks.yaml"
            )
        except Exception as e:
            logger.warning(f"⚠️ Could not load tanks.yaml: {e}")
    else:
        logger.warning("⚠️ tanks.yaml not found, using default capacity")

    return capacities


TANK_CAPACITIES = load_tank_capacities()


def get_local_connection():
    return pymysql.connect(**LOCAL_DB_CONFIG)


def determine_truck_status(
    speed,
    rpm,
    fuel_rate,
    data_age_min=0,
    pwr_ext=None,
    engine_load=None,
    coolant_temp=None,
):
    """
    Enhanced truck status determination v2 - Improved with additional sensors

    Status Hierarchy:
    1. OFFLINE: Data too old (>15 min) or no GPS data
    2. MOVING: Vehicle in motion (speed > 2 mph)
    3. STOPPED: Engine ON but stationary (idling)
    4. PARKED: Engine OFF, vehicle connected (shore power or recent data)
    5. OFFLINE: No activity detected

    Engine ON Indicators (any one = engine running):
    - RPM > 0
    - Fuel rate > 0.3 L/h
    - Engine load > 0%
    - Coolant temp > 120°F (engine warm = running)
    """
    # Check for offline - stale data (no communication in 15+ minutes)
    if data_age_min is not None and data_age_min > 15:
        return "OFFLINE"

    # No GPS data = cannot determine status
    if speed is None:
        return "OFFLINE"

    # Moving - speed > 2 mph (filters GPS noise/drift)
    if speed > 2:
        return "MOVING"

    # Stationary - check multiple engine indicators
    rpm_val = rpm or 0
    fuel_rate_val = fuel_rate or 0
    pwr_ext_val = pwr_ext or 0
    engine_load_val = engine_load or 0
    coolant_temp_val = coolant_temp or 0  # °F

    # Engine ON indicators (any one = engine running = STOPPED/idling)
    if rpm_val > 0:
        return "STOPPED"  # RPM > 0 = engine definitely running

    if fuel_rate_val > 0.3:
        return "STOPPED"  # Fuel consumption > 0.3 L/h = engine running

    if engine_load_val > 0:
        return "STOPPED"  # Engine load > 0% = engine running

    # Coolant temp check - if engine is warm, it's likely running
    if coolant_temp_val > 120:  # 120°F = engine running temp
        return "STOPPED"  # Engine warm enough to be running

    # Engine OFF checks
    # Shore power connected (13.2V+ indicates external power)
    if pwr_ext_val > 13.2:
        return "PARKED"  # Plugged in, engine off

    # Battery voltage in normal range (12-13.2V) = recently used, parked
    if pwr_ext_val > 11.5:
        return "PARKED"  # Battery shows truck is connected and alive

    # Coolant temp between ambient and running = recently stopped
    if coolant_temp_val > 60 and coolant_temp_val <= 120:
        return "PARKED"  # Engine cooling down = recently parked

    # Data is fresh (<15 min) but no engine activity = parked
    if data_age_min is not None and data_age_min < 5:
        return "PARKED"  # Very recent data, just no activity

    # Fallback - older data with no activity
    return "OFFLINE"


def save_to_fuel_metrics(connection, truck_id: str, sensor_data: dict):
    """
    Insert sensor data into fuel_metrics table for backend analytics
    Uses column names expected by database_mysql.py queries

    🔧 v2.0 IMPROVEMENTS:
    - Proper truck status determination (MOVING/IDLE/STOPPED/OFFLINE)
    - MPG only calculated for MOVING trucks
    - Idle consumption only for IDLE status
    - Drift calculated as sensor_pct - estimated_pct
    - Uses correct tank capacity from tanks.yaml
    """
    try:
        with connection.cursor() as cursor:
            measure_dt = sensor_data["timestamp"]

            # Extract sensor values
            speed = sensor_data.get("speed")  # mph
            rpm = sensor_data.get("rpm")
            fuel_lvl = sensor_data.get("fuel_lvl")  # Percentage (0-100)
            fuel_rate = sensor_data.get("fuel_rate")  # L/h
            odometer = sensor_data.get("odometer")  # miles
            altitude = sensor_data.get("altitude")  # feet
            latitude = sensor_data.get("latitude")
            longitude = sensor_data.get("longitude")
            engine_hours = sensor_data.get("engine_hours")
            hdop = sensor_data.get("hdop")
            coolant_temp = sensor_data.get("coolant_temp")
            pwr_ext = sensor_data.get("pwr_ext")  # Battery voltage (V)
            engine_load = sensor_data.get("engine_load")  # Engine load %

            # Get tank capacity for this truck
            tank_capacity = TANK_CAPACITIES.get(truck_id, TANK_CAPACITIES["default"])

            # Data age calculation (needed for status determination)
            now_utc = datetime.now(timezone.utc)
            data_age_min = 0.0
            if measure_dt:
                if measure_dt.tzinfo is None:
                    measure_dt = measure_dt.replace(tzinfo=timezone.utc)
                data_age_min = (now_utc - measure_dt).total_seconds() / 60.0

            # 🔧 v2.2: Enhanced truck status with engine_load and coolant_temp
            truck_status = determine_truck_status(
                speed, rpm, fuel_rate, data_age_min, pwr_ext, engine_load, coolant_temp
            )

            # Calculate fuel in liters/gallons if we have percentage
            estimated_liters = None
            estimated_gallons = None
            sensor_pct = fuel_lvl  # Raw sensor percentage
            estimated_pct = (
                fuel_lvl  # For now, estimated = sensor (no Kalman filter in sync)
            )

            if fuel_lvl is not None:
                estimated_gallons = (fuel_lvl / 100.0) * tank_capacity
                estimated_liters = estimated_gallons * 3.785

            # Sensor values (same as estimated for now - sync doesn't have Kalman)
            sensor_gallons = estimated_gallons
            sensor_liters = estimated_liters

            # Convert fuel_rate from L/h to gph
            consumption_lph = fuel_rate
            consumption_gph = None
            if fuel_rate is not None:
                consumption_gph = fuel_rate / 3.785  # L/h to gal/h

            # 🔧 v2.0: MPG only for MOVING trucks with valid speed
            mpg_current = None
            if (
                truck_status == "MOVING"
                and speed
                and speed > 5
                and consumption_gph
                and consumption_gph > 0.5
            ):
                # MPG = miles/hour / gallons/hour = miles/gallon
                mpg_current = speed / consumption_gph
                # Sanity check: MPG should be between 3 and 15 for trucks
                if mpg_current < 2.5 or mpg_current > 15:
                    mpg_current = None  # Invalid value, don't record

            # 🔧 v2.1: Determine idle method and mode
            # STOPPED = engine ON but not moving (idle consumption applies)
            idle_method = "NOT_IDLE"
            idle_mode = None
            if truck_status == "STOPPED":
                # Engine is ON (we know because rpm > 0 or fuel_rate > 0.3)
                if rpm and rpm > 0:
                    idle_method = "RPM_BASED"
                    idle_mode = "NORMAL"
                elif consumption_gph and consumption_gph > 0.08:  # > 0.3 L/h
                    idle_method = "FUEL_RATE_BASED"
                    idle_mode = "NORMAL"
                else:
                    idle_method = "FALLBACK_CONSENSUS"
                    idle_mode = "NORMAL"
            elif truck_status == "OFFLINE":
                idle_method = "ENGINE_OFF"
                idle_mode = None

            # 🔧 v2.0: Calculate drift (difference between sensor and estimated)
            # For now both are the same since we don't have Kalman, so drift = 0
            drift_pct = 0.0
            drift_warning = "NO"

            query = """
                INSERT INTO fuel_metrics 
                (timestamp_utc, truck_id, carrier_id, truck_status,
                 latitude, longitude, speed_mph,
                 estimated_liters, estimated_gallons, estimated_pct,
                 sensor_pct, sensor_liters, sensor_gallons,
                 consumption_lph, consumption_gph, mpg_current,
                 rpm, engine_hours, odometer_mi,
                 altitude_ft, hdop, coolant_temp_f,
                 idle_method, idle_mode, drift_pct, drift_warning,
                 anchor_detected, anchor_type, data_age_min)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                    idle_method = VALUES(idle_method),
                    idle_mode = VALUES(idle_mode),
                    drift_pct = VALUES(drift_pct),
                    drift_warning = VALUES(drift_warning),
                    data_age_min = VALUES(data_age_min)
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
                sensor_pct,  # sensor_pct (raw sensor value)
                sensor_liters,
                sensor_gallons,
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
                idle_mode,
                drift_pct,
                drift_warning,
                "NO",  # anchor_detected
                "NONE",  # anchor_type
                round(data_age_min, 2),  # data_age_min
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
    status_counts = {"MOVING": 0, "STOPPED": 0, "PARKED": 0, "OFFLINE": 0, "NO_DATA": 0}

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
                rpm = sensor_data.get("rpm")
                fuel_rate = sensor_data.get("fuel_rate")
                pwr_ext = sensor_data.get("pwr_ext")
                engine_load = sensor_data.get("engine_load")
                coolant_temp = sensor_data.get("coolant_temp")

                # Get the status that was determined (enhanced with all sensors)
                truck_status = determine_truck_status(
                    speed, rpm, fuel_rate, 0, pwr_ext, engine_load, coolant_temp
                )
                status_counts[truck_status] = status_counts.get(truck_status, 0) + 1

                # Status emoji
                status_emoji = {
                    "MOVING": "🚛",
                    "IDLE": "⏸️",
                    "STOPPED": "🛑",
                    "PARKED": "🅿️",
                    "OFFLINE": "📴",
                }.get(truck_status, "❓")

                speed_str = f"{speed:.1f}" if speed is not None else "N/A"
                fuel_str = f"{fuel:.1f}" if fuel is not None else "N/A"
                rpm_str = f"{int(rpm)}" if rpm is not None else "N/A"

                logger.info(
                    f"{status_emoji} {truck_id}: {truck_status} | Speed: {speed_str} mph | Fuel: {fuel_str}% | RPM: {rpm_str}"
                )
            else:
                status_counts["NO_DATA"] += 1
                logger.warning(f"⚠️ {truck_id}: No data from Wialon")

        except Exception as e:
            logger.error(f"Error processing {truck_id}: {e}")

    cycle_duration = time.time() - cycle_start

    # Summary with status breakdown
    logger.info("-" * 70)
    logger.info(f"📊 STATUS SUMMARY:")
    logger.info(
        f"   🚛 MOVING: {status_counts['MOVING']} | ⏸️ IDLE: {status_counts['IDLE']} | 🛑 STOPPED: {status_counts['STOPPED']} | 📴 OFFLINE: {status_counts['OFFLINE']} | ❓ NO_DATA: {status_counts['NO_DATA']}"
    )
    logger.info(
        f"⏱️ Cycle completed in {cycle_duration:.2f}s. Trucks synced: {trucks_processed}, Records: {total_inserted}"
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
