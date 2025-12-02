"""
Wialon Sync Service - Decoupled Data Fetcher
Fetches data from Remote Wialon DB and saves to Local JSON Cache.
This decouples the fetching process from the main processing loop, preventing lag.
"""

import time
import json
import os
import logging
from datetime import datetime, timezone
from pathlib import Path
from wialon_reader import WialonReader, WialonConfig, TRUCK_UNIT_MAPPING

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.FileHandler("wialon_sync.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

# Cache Directory
CACHE_DIR = Path("data/truck_cache")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def save_to_cache(truck_id: str, sensor_data: dict):
    """
    Save sensor data to local JSON cache
    """
    try:
        file_path = CACHE_DIR / f"{truck_id}.json"

        # Convert datetime to ISO string for JSON serialization
        data_to_save = sensor_data.copy()
        if isinstance(data_to_save.get("timestamp"), datetime):
            data_to_save["timestamp"] = data_to_save["timestamp"].isoformat()

        # Add sync timestamp
        data_to_save["synced_at"] = datetime.now(timezone.utc).isoformat()

        with open(file_path, "w") as f:
            json.dump(data_to_save, f, indent=2)

        return True
    except Exception as e:
        logger.error(f"Error saving cache for {truck_id}: {e}")
        return False


def sync_cycle(reader: WialonReader):
    """
    Single sync cycle using batch query optimization

    🔧 FIX v3.9.3: Use batch query instead of 39 individual queries
    This reduces sync time from ~10s to ~1s
    """
    cycle_start = time.time()

    logger.info("=" * 50)
    logger.info(
        f"🔄 SYNC CYCLE - {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}"
    )

    trucks_updated = 0

    try:
        # 🚀 BATCH QUERY: Fetch all trucks data in ONE query
        all_trucks_data = reader.get_all_trucks_data()

        for truck_data in all_trucks_data:
            try:
                # Convert TruckSensorData to dict for caching
                sensor_data = {
                    "epoch_time": truck_data.epoch_time,
                    "timestamp": truck_data.timestamp,
                    "fuel_lvl": truck_data.fuel_lvl,
                    "speed": truck_data.speed,
                    "rpm": truck_data.rpm,
                    "odometer": truck_data.odometer,
                    "fuel_rate": truck_data.fuel_rate,
                    "coolant_temp": truck_data.coolant_temp,
                    "hdop": truck_data.hdop,
                    "altitude": truck_data.altitude,
                    "pwr_ext": truck_data.pwr_ext,
                    "oil_press": truck_data.oil_press,
                    "total_fuel_used": truck_data.total_fuel_used,
                    "total_idle_fuel": truck_data.total_idle_fuel,
                    "engine_load": truck_data.engine_load,
                    "ambient_temp": truck_data.ambient_temp,
                    "capacity_gallons": truck_data.capacity_gallons,
                    "capacity_liters": truck_data.capacity_liters,
                }

                if save_to_cache(truck_data.truck_id, sensor_data):
                    trucks_updated += 1

            except Exception as e:
                logger.error(f"Error processing {truck_data.truck_id}: {e}")

        # Log trucks without data
        trucks_with_data = {td.truck_id for td in all_trucks_data}
        trucks_without_data = set(TRUCK_UNIT_MAPPING.keys()) - trucks_with_data
        for truck_id in trucks_without_data:
            logger.warning(f"⚠️ {truck_id}: No data from Wialon")

    except Exception as e:
        logger.error(f"Batch query error: {e}")

    cycle_duration = time.time() - cycle_start
    logger.info(
        f"⏱️ Cycle completed in {cycle_duration:.2f}s. Updated: {trucks_updated}/{len(TRUCK_UNIT_MAPPING)} [BATCH]"
    )


def main():
    logger.info("🚀 WIALON SYNC SERVICE STARTING")
    logger.info(f"📂 Cache directory: {CACHE_DIR.absolute()}")

    # Initialize Wialon Reader
    wialon_config = WialonConfig()
    reader = WialonReader(wialon_config, TRUCK_UNIT_MAPPING)

    if not reader.connect():
        logger.error("❌ Failed to connect to Remote Wialon DB")
        return

    try:
        while True:
            sync_cycle(reader)

            # Sleep for 30 seconds (minus cycle duration to keep steady cadence)
            # But ensure at least 5s sleep
            time.sleep(30)

            # Keep connection alive
            reader.connection.ping(reconnect=True)

    except KeyboardInterrupt:
        logger.info("Stopping...")
    finally:
        reader.disconnect()


if __name__ == "__main__":
    main()
