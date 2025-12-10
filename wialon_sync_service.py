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


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.3.1: CIRCUIT BREAKER FOR RESILIENCE
# ═══════════════════════════════════════════════════════════════════════════════


class CircuitBreaker:
    """
    Simple circuit breaker to prevent cascade failures

    States:
    - CLOSED: Normal operation, requests go through
    - OPEN: Failures exceeded threshold, requests blocked
    - HALF_OPEN: Testing if service recovered
    """

    def __init__(self, failure_threshold: int = 3, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "CLOSED"

    def record_failure(self):
        """Record a failure and potentially open the circuit"""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.failure_threshold:
            self.state = "OPEN"
            logger.warning(
                f"🔴 Circuit breaker OPEN after {self.failures} failures. Will retry in {self.recovery_timeout}s"
            )

    def record_success(self):
        """Record success and reset the circuit"""
        if self.state != "CLOSED":
            logger.info(f"🟢 Circuit breaker CLOSED - service recovered")
        self.failures = 0
        self.state = "CLOSED"

    def can_proceed(self) -> bool:
        """Check if request should proceed"""
        if self.state == "CLOSED":
            return True

        if self.state == "OPEN":
            # Check if recovery timeout has passed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = "HALF_OPEN"
                logger.info("🟡 Circuit breaker HALF_OPEN - testing recovery")
                return True
            return False

        # HALF_OPEN: allow one request through
        return True


# Global circuit breaker for Wialon
wialon_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=60)


def sync_cycle(reader: WialonReader):
    """
    Single sync cycle using batch query optimization

    🔧 FIX v3.9.3: Use batch query instead of 39 individual queries
    This reduces sync time from ~10s to ~1s

    🆕 v5.3.1: Added circuit breaker for resilience
    """
    # Check circuit breaker
    if not wialon_circuit_breaker.can_proceed():
        logger.warning(
            f"⏸️ Sync skipped - circuit breaker OPEN. Will retry in {wialon_circuit_breaker.recovery_timeout - (time.time() - wialon_circuit_breaker.last_failure_time):.0f}s"
        )
        return

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

        # Success! Reset circuit breaker
        wialon_circuit_breaker.record_success()

    except Exception as e:
        logger.error(f"❌ Batch query error: {e}")
        wialon_circuit_breaker.record_failure()

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
