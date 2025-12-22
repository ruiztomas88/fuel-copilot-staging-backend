"""
Wialon Direct Database Reader
Connects to Wialon MySQL and reads sensor data for 39 trucks every 15-20 seconds

⚠️ TIMEZONE HANDLING:
- Wialon stores epoch timestamps (UTC seconds since 1970-01-01)
- We convert to datetime WITH timezone (UTC)
- NEVER use naive datetime (causes drift/future timestamp bugs)
- All timestamps stored as UTC in our DB

🔒 SECURITY:
- All credentials loaded from environment variables
- Never hardcode passwords in code
"""

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import pymysql
import yaml
from dotenv import load_dotenv
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class WialonConfig:
    """Wialon database configuration - loaded from environment variables"""

    host: str = field(default_factory=lambda: os.getenv("WIALON_DB_HOST", "localhost"))
    port: int = field(default_factory=lambda: int(os.getenv("WIALON_DB_PORT", "3306")))
    user: str = field(default_factory=lambda: os.getenv("WIALON_DB_USER", ""))
    password: str = field(default_factory=lambda: os.getenv("WIALON_DB_PASS", ""))
    database: str = field(
        default_factory=lambda: os.getenv("WIALON_DB_NAME", "wialon_collect")
    )

    # Sensor parameter names in Wialon (based on actual DB structure)
    # Key = our internal name, Value = Wialon 'p' column value
    SENSOR_PARAMS = {
        "fuel_lvl": "fuel_lvl",  # Fuel Level %
        "speed": "speed",  # GPS Speed
        "rpm": "rpm",  # RPM
        "odometer": "odom",  # ✅ Odometer (miles) - verified Dec 22, 2025
        "fuel_rate": "fuel_rate",  # Fuel Rate L/h
        "coolant_temp": "cool_temp",  # Coolant Temperature
        "hdop": "hdop",  # GPS HDOP
        "altitude": "altitude",
        "obd_speed": "obd_speed",  # Engine Speed
        "engine_hours": "engine_hours",  # Engine Hours
        "pwr_ext": "pwr_ext",  # External Power (Voltage)
        "oil_press": "oil_press",  # Oil Pressure (psi)
        # 🆕 NEW SENSORS for improved Kalman accuracy
        "total_fuel_used": "total_fuel_used",  # ECU cumulative fuel counter (gallons)
        "total_idle_fuel": "total_idle_fuel",  # ECU idle fuel counter
        "engine_load": "engine_load",  # Engine load % (indicates effort)
        "ambient_temp": "air_temp",  # Ambient temperature
        # 🆕 v3.12.26: Engine Health sensors from Pacific Track
        "oil_temp": "oil_temp",  # Oil Temperature (°F)
        "def_level": "def_level",  # DEF Level (%) - Fixed: was def_lvl
        "intake_air_temp": "intk_t",  # 🔧 DEC20: Fixed - Wialon truncates to intk_t
        # 🆕 v3.12.28: New sensors for DTC alerts, GPS quality, idle validation
        "dtc": "dtc",  # DTC count (number of active codes)
        "j1939_spn": "j1939_spn",  # 🔧 v5.12.1: J1939 SPN code (Suspect Parameter Number)
        "j1939_fmi": "j1939_fmi",  # 🔧 v5.12.1: J1939 FMI code (Failure Mode Identifier)
        "idle_hours": "idle_hours",  # ECU Idle Hours counter
        "sats": "sats",  # GPS Satellites count
        "pwr_int": "pwr_int",  # GPS tracker internal battery (~3-4V)
        "course": "course",  # GPS Heading/Course (degrees)
        # 🆕 v5.10.0: Driver behavior & MPG cross-validation sensors
        "fuel_economy": "fuel_economy",  # ECU fuel economy (MPG) - for cross-validation
        "gear": "gear",  # Current gear position (1-18) - for heavy foot detection
        "barometer": "barometer",  # Barometric pressure - engine load correlation
        # 🆕 v5.10.1: Full Pacific Track sensor suite
        # Temperatures (Page 2)
        "fuel_temp": "fuel_t",  # 🔧 DEC20: Fixed - Wialon truncates to fuel_t
        "intercooler_temp": "intrclr_t",  # 🔧 DEC20: Fixed - Wialon truncates to intrclr_t
        "turbo_temp": "turbo_temp",  # Turbo temperature (°F) - turbo health
        "trans_temp": "trans_temp",  # Transmission oil temperature (°F)
        # Pressures (Page 2)
        "intake_press": "intake_pressure",  # 🔧 DEC20: Fixed - Wialon uses intake_pressure
        "boost": "intake_pressure",  # 🔧 DEC20: Fixed - alias for intake_pressure
        # Counters (Page 4)
        "pto_hours": "pto_hours",  # PTO Hours counter
        # Brake Info (Page 4) - 🔥 Critical for predictive maintenance
        "brake_app_press": "brake_app_press",  # Brake application pressure (psi)
        "brake_primary_press": "brake_primary_press",  # Primary brake pressure (psi)
        "brake_secondary_press": "brake_secondary_press",  # Secondary brake pressure (psi)
        "brake_switch": "brake_switch",  # Brake pedal switch (0/1)
        "parking_brake": "parking_brake",  # Parking brake status (0/1)
        "abs_status": "abs_status",  # ABS system status
        # RPM High Resolution (Page 3)
        "rpm_hi_res": "rpm_hi_res",  # High resolution RPM
        # Misc (Page 1)
        "seatbelt": "seatbelt",  # Seatbelt status (0/1)
        "vin": "vin",  # Vehicle VIN
        # 🆕 v5.10.1: Device-generated driving events (from accelerometer)
        "harsh_accel": "harsh_accel",  # Harsh acceleration event (threshold: 280mg)
        "harsh_brake": "harsh_brake",  # Harsh braking event (threshold: 320mg)
        "harsh_corner": "harsh_corner",  # Harsh cornering event (threshold: 280mg)
        # 🆕 v5.11.0: Additional sensors found in Wialon (Dec 2025)
        "rssi": "rssi",  # Signal strength indicator (dBm) - GPS tracker health
        "coolant_level": "cool_lvl",  # Coolant level (%) - engine health
        "oil_level": "oil_level",  # Oil level (%) - predictive maintenance
        "gps_locked": "gps_locked",  # GPS lock status (0/1)
        "battery": "battery",  # Device battery level
        "roaming": "roaming",  # Cellular roaming status
        "event_id": "event_id",  # Pacific Track event identifier
        "bus": "bus",  # CAN bus status/identifier
        "mode": "mode",  # Device operation mode
    }


@dataclass
class TruckSensorData:
    """Single truck sensor reading with proper timezone handling"""

    truck_id: str
    unit_id: int
    timestamp: datetime  # ALWAYS timezone-aware (UTC)
    epoch_time: int  # Original epoch for reference

    # Tank specifications (from tanks.yaml)
    capacity_gallons: float
    capacity_liters: float

    # Location data
    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Sensor values
    fuel_lvl: Optional[float] = None
    speed: Optional[float] = None
    rpm: Optional[int] = None
    odometer: Optional[float] = None
    fuel_rate: Optional[float] = None
    coolant_temp: Optional[float] = None
    hdop: Optional[float] = None
    altitude: Optional[float] = None
    pwr_ext: Optional[float] = None
    oil_press: Optional[float] = None
    engine_hours: Optional[float] = None  # Engine hours
    # 🆕 NEW SENSORS for improved accuracy
    total_fuel_used: Optional[float] = None  # ECU cumulative fuel (gallons)
    total_idle_fuel: Optional[float] = None  # ECU idle fuel (gallons)
    engine_load: Optional[float] = None  # Engine load % (0-100)
    ambient_temp: Optional[float] = None  # Ambient temperature °F
    # 🆕 v3.12.26: Engine Health sensors
    oil_temp: Optional[float] = None  # Oil Temperature °F
    def_level: Optional[float] = None  # DEF Level %
    intake_air_temp: Optional[float] = None  # Intake Air Temperature °F
    # 🆕 v3.12.28: New sensors for DTC, GPS quality, idle validation
    dtc: Optional[float] = None  # DTC count (number of active codes)
    j1939_spn: Optional[float] = None  # 🔧 v5.12.1: J1939 SPN code
    j1939_fmi: Optional[float] = None  # 🔧 v5.12.1: J1939 FMI code
    idle_hours: Optional[float] = None  # ECU Idle Hours counter
    sats: Optional[int] = None  # GPS Satellites count
    pwr_int: Optional[float] = None  # GPS tracker internal battery (~3-4V)
    course: Optional[float] = None  # GPS Heading/Course (degrees 0-360)
    # 🆕 v5.10.0: Driver behavior & MPG cross-validation sensors
    fuel_economy: Optional[float] = None  # ECU fuel economy (MPG) - cross-validation
    gear: Optional[int] = None  # Current gear position (1-18)
    barometer: Optional[float] = None  # Barometric pressure (kPa)
    # 🆕 v5.10.1: Full Pacific Track sensor suite
    # Temperatures
    fuel_temp: Optional[float] = None  # Fuel temperature (°F)
    intercooler_temp: Optional[float] = None  # Intercooler temperature (°F)
    turbo_temp: Optional[float] = None  # Turbo temperature (°F)
    trans_temp: Optional[float] = None  # Transmission oil temperature (°F)
    # Pressures
    intake_press: Optional[float] = None  # Intake manifold pressure (kPa)
    boost: Optional[float] = None  # Boost pressure (alias for intake_press)
    # Counters
    pto_hours: Optional[float] = None  # PTO Hours counter
    # Brake Info - 🔥 Critical for brake wear prediction
    brake_app_press: Optional[float] = None  # Brake application pressure (psi)
    brake_primary_press: Optional[float] = None  # Primary brake pressure (psi)
    brake_secondary_press: Optional[float] = None  # Secondary brake pressure (psi)
    brake_switch: Optional[int] = None  # Brake pedal switch (0/1)
    parking_brake: Optional[int] = None  # Parking brake status (0/1)
    abs_status: Optional[int] = None  # ABS system status
    # High Resolution
    rpm_hi_res: Optional[float] = None  # High resolution RPM
    # Misc
    seatbelt: Optional[int] = None  # Seatbelt status (0/1)
    vin: Optional[str] = None  # Vehicle VIN
    # Device-generated driving events
    harsh_accel: Optional[int] = None  # Harsh acceleration event count
    harsh_brake: Optional[int] = None  # Harsh braking event count
    harsh_corner: Optional[int] = None  # Harsh cornering event count
    # 🆕 v5.11.0: Additional sensors (Dec 2025)
    rssi: Optional[int] = None  # Signal strength indicator (dBm)
    coolant_level: Optional[float] = None  # Coolant level (%)
    oil_level: Optional[float] = None  # Oil level (%)
    gps_locked: Optional[int] = None  # GPS lock status (0/1)
    battery: Optional[float] = None  # Device battery level
    roaming: Optional[int] = None  # Cellular roaming status (0/1)
    event_id: Optional[str] = None  # Pacific Track event identifier
    bus: Optional[int] = None  # CAN bus status/identifier
    mode: Optional[int] = None  # Device operation mode

    def __post_init__(self):
        """Ensure timestamp is timezone-aware"""
        if self.timestamp.tzinfo is None:
            # Convert naive datetime to UTC
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)
            logger.warning(f"[{self.truck_id}] Converted naive datetime to UTC")

    @property
    def dtc_code(self) -> Optional[str]:
        """
        🔧 v5.12.1: Combine j1939_spn + j1939_fmi into DTC code format

        Returns DTC code in format "SPN.FMI" (e.g., "100.3")
        Returns None if either SPN or FMI is missing
        """
        if self.j1939_spn is not None and self.j1939_fmi is not None:
            return f"{int(self.j1939_spn)}.{int(self.j1939_fmi)}"
        return None


class WialonReader:
    """
    Reads data directly from Wialon MySQL database

    CRITICAL: Handles timezone conversion properly to avoid drift issues
    """

    def __init__(self, config: WialonConfig, truck_unit_mapping: Dict[str, int]):
        """
        Args:
            config: Wialon database configuration
            truck_unit_mapping: Dict mapping truck_id -> wialon_unit_id
                Example: {"NQ6975": 401961901, "RT9127": 401961902, ...}
        """
        self.config = config
        self.truck_unit_mapping = truck_unit_mapping
        self.connection = None
        # 🔧 v3.10.6: Track connection age for preventive reconnection
        self._connection_created_at: Optional[float] = None
        self._max_connection_age_seconds: int = 3600  # Reconnect every hour

    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=60),
        retry=retry_if_exception_type((pymysql.Error, ConnectionError, TimeoutError)),
        before_sleep=lambda retry_state: logger.warning(
            f"⚠️ Connection attempt {retry_state.attempt_number} failed, retrying in {retry_state.next_action.sleep} seconds..."
        ),
    )
    def _connect_with_retry(self):
        """Internal method with retry logic"""
        return pymysql.connect(
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
            connect_timeout=10,
            read_timeout=30,
            write_timeout=30,
        )

    def connect(self) -> bool:
        """Establish connection to Wialon database with automatic retry"""
        try:
            self.connection = self._connect_with_retry()
            self._connection_created_at = (
                time.time()
            )  # 🔧 v3.10.6: Track connection age
            logger.info(
                f"✅ Connected to Wialon DB: {self.config.host}:{self.config.port}"
            )
            return True
        except Exception as e:
            logger.error(f"❌ Failed to connect to Wialon DB after 5 attempts: {e}")
            return False

    def ensure_connection(self) -> bool:
        """Ensure connection is alive, reconnect if needed

        🔧 v3.10.6: Also handles preventive reconnection for 24/7 stability
        - Checks if connection is stale (older than 1 hour)
        - Tests connection with ping before returning
        - Automatically reconnects on any issue
        """
        try:
            # Check if connection needs preventive refresh (every hour)
            if self.connection is not None and self._connection_created_at is not None:
                connection_age = time.time() - self._connection_created_at
                if connection_age > self._max_connection_age_seconds:
                    logger.info(
                        f"🔄 Connection age {connection_age/60:.1f} min > {self._max_connection_age_seconds/60:.0f} min, refreshing..."
                    )
                    try:
                        self.connection.close()
                    except Exception:
                        pass  # Ignore errors on close
                    self.connection = None

            if self.connection is None:
                return self.connect()

            # Test connection with ping
            self.connection.ping(reconnect=True)
            return True
        except Exception as e:
            logger.warning(f"⚠️ Connection lost, reconnecting: {e}")
            self.connection = None  # Ensure we create fresh connection
            return self.connect()

    def disconnect(self):
        """Close database connection"""
        if self.connection:
            self.connection.close()
            logger.info("Disconnected from Wialon DB")

    def _epoch_to_datetime_utc(self, epoch: int) -> datetime:
        """
        Convert epoch timestamp to timezone-aware UTC datetime

        ⚠️ CRITICAL: This prevents future timestamp bugs

        Args:
            epoch: Unix timestamp (seconds since 1970-01-01 UTC)

        Returns:
            Timezone-aware datetime in UTC
        """
        return datetime.fromtimestamp(epoch, tz=timezone.utc)

    def get_latest_sensor_data(
        self, unit_id: int, max_age_seconds: int = 3600
    ) -> Optional[Dict[str, Any]]:
        """
        Get latest sensor data for a specific unit

        Args:
            unit_id: Wialon unit ID
            max_age_seconds: Maximum age of data to accept (default 1 hour - v3.15.1)

        Returns:
            Dict with sensor values or None if no recent data
        """
        if not self.connection:
            logger.error("Not connected to database")
            return None

        try:
            with self.connection.cursor() as cursor:
                # Calculate cutoff epoch (Python time is always correct/synced)
                cutoff_epoch = int(time.time()) - max_age_seconds

                # Get list of relevant parameters to filter query
                # This prevents "LIMIT" from cutting off important sensors due to noise from other params
                relevant_params = list(self.config.SENSOR_PARAMS.values())
                params_placeholder = ", ".join(["%s"] * len(relevant_params))

                # Query sensors table - get latest reading for this unit
                # CHANGED: Filter by 'm' (epoch) instead of measure_datetime to avoid timezone issues
                # CHANGED: Added IN clause for parameters and increased LIMIT to 2000
                query = f"""
                    SELECT 
                        p as param_name,
                        value,
                        m as epoch_time,
                        from_latitude,
                        from_longitude,
                        measure_datetime
                    FROM sensors
                    WHERE unit = %s
                        AND m >= %s
                        AND p IN ({params_placeholder})
                    ORDER BY m DESC
                    LIMIT 2000
                """

                # Prepare args: unit_id, cutoff_epoch, *relevant_params
                query_args = [unit_id, cutoff_epoch] + relevant_params

                cursor.execute(query, query_args)
                results = cursor.fetchall()

                if not results:
                    return None

                # Get latest timestamp (first row)
                # 🔧 FIX v5.8.0: ALWAYS use epoch_time for timestamp calculation
                # measure_datetime from Wialon is in EST, not UTC!
                # Using epoch_time ensures correct UTC conversion
                latest_epoch = results[0]["epoch_time"]

                # 🐛 DEBUG v6.4.2: Log query result count
                logger.info(
                    f"[{truck_id}/{unit_id}] Query returned {len(results)} rows, latest_epoch: {latest_epoch}"
                )

                # Build sensor dict
                sensor_data = {
                    "epoch_time": latest_epoch,
                    "timestamp": self._epoch_to_datetime_utc(latest_epoch),
                    "latitude": results[0].get("from_latitude"),
                    "longitude": results[0].get("from_longitude"),
                }

                # Extract all sensor parameters (Last Known Value strategy)
                # 1. First pass: Get values from the latest timestamp
                # 🐛 DEBUG: Track which params are found
                params_found = set()
                for row in results:
                    if row["epoch_time"] == latest_epoch:
                        param_name = row.get("param_name")
                        param_value = row.get("value")

                        if param_name and param_value is not None:
                            params_found.add(param_name)
                            # Map Wialon parameter names to our standard names
                            for (
                                our_name,
                                wialon_name,
                            ) in self.config.SENSOR_PARAMS.items():
                                if wialon_name == param_name:
                                    sensor_data[our_name] = param_value
                                    break

                # 🐛 DEBUG v6.4.2: Log ALL params found for LC6799
                if truck_id == "LC6799":
                    logger.info(
                        f"[LC6799] Params at latest_epoch {latest_epoch}: {sorted(params_found)}"
                    )
                    logger.info(f"[LC6799] Total rows in query result: {len(results)}")

                # 🐛 DEBUG: Log if health sensors are missing
                missing_health = []
                if "cool_temp" not in params_found:
                    missing_health.append("cool_temp")
                if "oil_temp" not in params_found:
                    missing_health.append("oil_temp")
                if "def_level" not in params_found:
                    missing_health.append("def_level")
                if "rpm" not in params_found:
                    missing_health.append("rpm")

                if missing_health:
                    logger.warning(
                        f"[Unit {unit_id}] Missing health sensors in query results: {missing_health}. Found params: {sorted(params_found)}"
                    )

                # 2. Second pass: Fill missing values from recent history
                # This handles fragmented packets where sensors arrive with slightly different timestamps

                for row in results:
                    age_sec = latest_epoch - row["epoch_time"]
                    param_name = row.get("param_name")

                    # Determine max age for this parameter
                    # Standard sensors: 15 min (900s)
                    # Fuel Level: 4 hours (14400s) to handle infrequent updates
                    max_age = 900
                    if param_name == "fuel_lvl":
                        max_age = 14400

                    # Skip rows too old relative to latest_epoch
                    if age_sec > max_age:
                        continue

                    param_value = row.get("value")

                    if param_name and param_value is not None:
                        for our_name, wialon_name in self.config.SENSOR_PARAMS.items():
                            # Only fill if not already present
                            if (
                                wialon_name == param_name
                                and our_name not in sensor_data
                            ):
                                sensor_data[our_name] = param_value
                                break

                # 3. Third pass: If fuel_lvl is STILL missing, try a deeper search
                # Some trucks (FM9838, SG5760) send fuel level very infrequently (> 1 hour)
                # The main query LIMIT 2000 might cut off the old fuel packet if there's lots of GPS data
                if "fuel_lvl" not in sensor_data:
                    try:
                        # Look back 12 hours for fuel level specifically
                        deep_cutoff = int(time.time()) - (12 * 3600)
                        fuel_query = """
                            SELECT value
                            FROM sensors
                            WHERE unit = %s
                                AND m >= %s
                                AND p = 'fuel_lvl'
                            ORDER BY m DESC
                            LIMIT 1
                        """
                        cursor.execute(fuel_query, (unit_id, deep_cutoff))
                        fuel_result = cursor.fetchone()

                        if fuel_result and fuel_result["value"] is not None:
                            sensor_data["fuel_lvl"] = fuel_result["value"]
                            # logger.debug(f"[{unit_id}] ⛽ Found deep history fuel level: {fuel_result['value']}%")
                    except Exception as e:
                        logger.warning(f"[{unit_id}] Failed deep fuel search: {e}")

                return sensor_data

        except Exception as e:
            logger.error(f"Error reading sensor data for unit {unit_id}: {e}")
            return None

    def get_all_trucks_data(self) -> List[TruckSensorData]:
        """
        🚀 OPTIMIZED: Read latest sensor data for ALL trucks in ONE query

        Instead of 39 individual queries (slow), this makes 1 batch query
        and processes results in Python. ~10x faster.

        Returns:
            List of TruckSensorData objects with timezone-aware timestamps
        """
        # 🔧 v3.10.6: ALWAYS ensure connection before queries (fixes 24/7 stability)
        if not self.ensure_connection():
            logger.error("❌ Cannot establish database connection")
            return []

        all_data = []
        unit_ids = list(self.truck_unit_mapping.values())
        unit_to_truck = {v: k for k, v in self.truck_unit_mapping.items()}

        if not unit_ids:
            logger.warning("No trucks configured")
            return []

        try:
            with self.connection.cursor() as cursor:
                # Calculate cutoff epoch
                # 🔧 DEC22 2025: Extended to 4 hours for engine health sensors
                # Engine sensors (rpm, coolant, oil temp/press) arrive less frequently
                # than GPS data, especially when truck is idling or moving slowly
                cutoff_epoch = int(time.time()) - 14400  # 4 hours = 14400 seconds

                # Get relevant parameter names
                relevant_params = list(self.config.SENSOR_PARAMS.values())

                # Build placeholders for IN clauses
                unit_placeholders = ", ".join(["%s"] * len(unit_ids))
                param_placeholders = ", ".join(["%s"] * len(relevant_params))

                # 🚀 v3.9.5: OPTIMIZED BATCH QUERY with ROW_NUMBER for top-N per truck
                # This limits data transfer by getting only latest 20 readings per truck per param
                # Falls back to simple query for MySQL < 8.0
                try:
                    query = f"""
                        SELECT unit, param_name, value, epoch_time, from_latitude, from_longitude, measure_datetime
                        FROM (
                            SELECT 
                                unit,
                                p as param_name,
                                value,
                                m as epoch_time,
                                from_latitude,
                                from_longitude,
                                measure_datetime,
                                ROW_NUMBER() OVER (PARTITION BY unit, p ORDER BY m DESC) as rn
                            FROM sensors
                            WHERE unit IN ({unit_placeholders})
                                AND m >= %s
                                AND p IN ({param_placeholders})
                        ) ranked
                        WHERE rn <= 20
                        ORDER BY unit, epoch_time DESC
                    """
                    query_args = unit_ids + [cutoff_epoch] + relevant_params
                    cursor.execute(query, query_args)
                    results = cursor.fetchall()
                except Exception as e:
                    # Fallback for MySQL < 8.0 (no ROW_NUMBER)
                    if "ROW_NUMBER" in str(e) or "syntax" in str(e).lower():
                        logger.warning("ROW_NUMBER not supported, using fallback query")
                        query = f"""
                            SELECT 
                                unit,
                                p as param_name,
                                value,
                                m as epoch_time,
                                from_latitude,
                                from_longitude,
                                measure_datetime
                            FROM sensors
                            WHERE unit IN ({unit_placeholders})
                                AND m >= %s
                                AND p IN ({param_placeholders})
                            ORDER BY unit, m DESC
                            LIMIT 5000
                        """
                        query_args = unit_ids + [cutoff_epoch] + relevant_params
                        cursor.execute(query, query_args)
                        results = cursor.fetchall()
                    else:
                        raise

                if not results:
                    logger.warning("No sensor data found for any truck")
                    return []

                # Group results by unit_id
                from collections import defaultdict

                unit_data = defaultdict(list)
                for row in results:
                    unit_data[row["unit"]].append(row)

                # 🔧 v5.8.3: DEEP SEARCH for fuel_lvl - some trucks send fuel level very infrequently
                # The main query uses 1-hour cutoff which may miss fuel_lvl data
                # This secondary query extends to 4 hours specifically for fuel_lvl
                fuel_cutoff_epoch = int(time.time()) - 14400  # 4 hours
                try:
                    fuel_query = f"""
                        SELECT unit, 'fuel_lvl' as param_name, value, m as epoch_time
                        FROM sensors
                        WHERE unit IN ({unit_placeholders})
                            AND m >= %s
                            AND m < %s
                            AND p = 'fuel_lvl'
                        ORDER BY m DESC
                    """
                    # Get fuel_lvl data between 1h-4h ago (not already in main query)
                    fuel_query_args = unit_ids + [fuel_cutoff_epoch, cutoff_epoch]
                    cursor.execute(fuel_query, fuel_query_args)
                    fuel_results = cursor.fetchall()

                    # Add fuel_lvl data to unit_data if not already present
                    for row in fuel_results:
                        unit_id = row["unit"]
                        # Check if this truck already has fuel_lvl data
                        has_fuel_lvl = any(
                            r.get("param_name") == "fuel_lvl"
                            for r in unit_data.get(unit_id, [])
                        )
                        if not has_fuel_lvl:
                            unit_data[unit_id].append(row)
                            logger.debug(
                                f"[{unit_id}] ⛽ Deep fuel_lvl found: {row['value']}% (age={(int(time.time()) - row['epoch_time'])/60:.0f}min)"
                            )
                except Exception as fuel_e:
                    logger.warning(f"Deep fuel_lvl search failed: {fuel_e}")

                # 🔧 v5.12.1: DEEP SEARCH for j1939_spn and j1939_fmi (DTC codes)
                # These sensors update VERY infrequently (only when DTCs change)
                # Extend search to 48 hours to capture active DTCs
                dtc_cutoff_epoch = int(time.time()) - 172800  # 48 hours
                try:
                    dtc_query = f"""
                        SELECT unit, p as param_name, value, m as epoch_time
                        FROM sensors
                        WHERE unit IN ({unit_placeholders})
                            AND m >= %s
                            AND p IN ('j1939_spn', 'j1939_fmi')
                        ORDER BY m DESC
                    """
                    dtc_query_args = unit_ids + [dtc_cutoff_epoch]
                    cursor.execute(dtc_query, dtc_query_args)
                    dtc_results = cursor.fetchall()

                    # Add j1939_spn and j1939_fmi data to unit_data if not already present
                    for row in dtc_results:
                        unit_id = row["unit"]
                        param = row["param_name"]
                        # Check if this truck already has this DTC sensor
                        has_sensor = any(
                            r.get("param_name") == param
                            for r in unit_data.get(unit_id, [])
                        )
                        if not has_sensor:
                            unit_data[unit_id].append(row)
                            hours_ago = (int(time.time()) - row["epoch_time"]) / 3600
                            logger.debug(
                                f"[{unit_id}] 🔍 Deep {param} found: {row['value']} (age={hours_ago:.1f}h)"
                            )
                except Exception as dtc_e:
                    logger.warning(f"Deep DTC search failed: {dtc_e}")

                # Process each truck's data
                trucks_with_data = set()
                for unit_id, rows in unit_data.items():
                    truck_id = unit_to_truck.get(unit_id)
                    if not truck_id:
                        continue

                    if not rows:
                        continue

                    # Get latest timestamp for this truck
                    # 🔧 FIX v5.8.0: ALWAYS use epoch_time for timestamp calculation
                    # measure_datetime from Wialon is in EST, not UTC!
                    latest_epoch = rows[0]["epoch_time"]

                    # Build sensor dict for this truck
                    sensor_data = {
                        "epoch_time": latest_epoch,
                        "timestamp": self._epoch_to_datetime_utc(latest_epoch),
                        "latitude": rows[0].get("from_latitude"),
                        "longitude": rows[0].get("from_longitude"),
                    }

                    # Extract sensor values (Last Known Value strategy)
                    for row in rows:
                        age_sec = latest_epoch - row["epoch_time"]
                        param_name = row.get("param_name")

                        # Determine max age for this parameter
                        max_age = 900  # 15 min default
                        if param_name == "fuel_lvl":
                            max_age = 14400  # 4 hours for fuel level
                        elif param_name in ("j1939_spn", "j1939_fmi"):
                            max_age = (
                                172800  # 48 hours for DTC sensors (update infrequently)
                            )
                        elif param_name in (
                            "cool_temp",
                            "oil_temp",
                            "rpm",
                            "engine_load",
                            "oil_press",
                            "def_level",
                        ):
                            max_age = 14400  # 🔧 DEC22: 4 hours for health sensors (update less frequently than GPS)

                        if age_sec > max_age:
                            continue

                        param_value = row.get("value")
                        if param_name and param_value is not None:
                            for (
                                our_name,
                                wialon_name,
                            ) in self.config.SENSOR_PARAMS.items():
                                if (
                                    wialon_name == param_name
                                    and our_name not in sensor_data
                                ):
                                    sensor_data[our_name] = param_value
                                    break

                    # Create TruckSensorData object
                    try:
                        truck_config = TRUCK_CONFIG.get(truck_id, {})
                        capacity_gallons = truck_config.get("capacity_gallons", 200)
                        capacity_liters = truck_config.get("capacity_liters", 757.08)

                        # 🔧 v5.12.1: Combine j1939_spn + j1939_fmi into dtc_code format
                        # Wialon stores these as separate sensors, we need to combine them
                        dtc_code_combined = None
                        if sensor_data.get("j1939_spn") and sensor_data.get(
                            "j1939_fmi"
                        ):
                            spn = int(sensor_data["j1939_spn"])
                            fmi = int(sensor_data["j1939_fmi"])
                            dtc_code_combined = f"{spn}.{fmi}"
                            logger.debug(
                                f"🔍 {truck_id}: Combined DTC = {dtc_code_combined} (SPN={spn}, FMI={fmi})"
                            )

                        truck_data = TruckSensorData(
                            truck_id=truck_id,
                            unit_id=unit_id,
                            timestamp=sensor_data["timestamp"],
                            epoch_time=sensor_data["epoch_time"],
                            capacity_gallons=capacity_gallons,
                            capacity_liters=capacity_liters,
                            latitude=sensor_data.get("latitude"),
                            longitude=sensor_data.get("longitude"),
                            fuel_lvl=sensor_data.get("fuel_lvl"),
                            speed=sensor_data.get("speed"),
                            rpm=sensor_data.get("rpm"),
                            odometer=sensor_data.get("odometer"),
                            fuel_rate=sensor_data.get("fuel_rate"),
                            coolant_temp=sensor_data.get("coolant_temp"),
                            hdop=sensor_data.get("hdop"),
                            altitude=sensor_data.get("altitude"),
                            pwr_ext=sensor_data.get("pwr_ext"),
                            oil_press=sensor_data.get("oil_press"),
                            engine_hours=sensor_data.get("engine_hours"),
                            total_fuel_used=sensor_data.get("total_fuel_used"),
                            total_idle_fuel=sensor_data.get("total_idle_fuel"),
                            engine_load=sensor_data.get("engine_load"),
                            ambient_temp=sensor_data.get("ambient_temp"),
                            # 🆕 v3.12.26: Engine Health sensors
                            oil_temp=sensor_data.get("oil_temp"),
                            def_level=sensor_data.get("def_level"),
                            intake_air_temp=sensor_data.get("intake_air_temp"),
                            # 🆕 v3.12.28 / v5.12.1: DTC sensors (j1939_spn + j1939_fmi)
                            dtc=sensor_data.get("dtc"),
                            j1939_spn=sensor_data.get("j1939_spn"),
                            j1939_fmi=sensor_data.get("j1939_fmi"),
                            idle_hours=sensor_data.get("idle_hours"),
                            sats=sensor_data.get("sats"),
                            pwr_int=sensor_data.get("pwr_int"),
                            course=sensor_data.get("course"),
                        )
                        all_data.append(truck_data)
                        trucks_with_data.add(truck_id)
                        logger.debug(f"✓ {truck_id}: epoch={latest_epoch}")
                    except Exception as e:
                        logger.error(
                            f"Error creating TruckSensorData for {truck_id}: {e}"
                        )

                # Log trucks without data
                all_trucks = set(self.truck_unit_mapping.keys())
                trucks_without_data = all_trucks - trucks_with_data
                for truck_id in trucks_without_data:
                    logger.warning(f"⚠️  {truck_id}: No recent data")

                logger.info(
                    f"📊 Read data for {len(all_data)}/{len(self.truck_unit_mapping)} trucks [BATCH]"
                )
                return all_data

        except Exception as e:
            # 🔧 v3.10.6: Handle connection errors specifically for 24/7 stability
            error_str = str(e)
            if (
                "InterfaceError" in type(e).__name__
                or "connection" in error_str.lower()
                or "(0, '')" in error_str
            ):
                logger.warning(
                    f"⚠️ Connection lost during query, attempting reconnect..."
                )
                # Force reconnection on next attempt
                self.connection = None
                if self.ensure_connection():
                    logger.info("✅ Reconnected successfully, retry on next poll cycle")
                else:
                    logger.error("❌ Failed to reconnect to Wialon DB")
            else:
                logger.error(f"Batch query error: {e}")
                import traceback

                traceback.print_exc()
            return []

    def test_connection(self) -> bool:
        """Test database connection and query a sample unit"""
        if not self.connect():
            return False

        try:
            # Test with NQ6975 (usually has recent data)
            test_truck = "NQ6975"
            test_unit = self.truck_unit_mapping.get(test_truck)

            if not test_unit:
                logger.error(f"{test_truck} not found in mapping")
                return False

            logger.info(f"Testing with {test_truck} (unit_id={test_unit})...")

            data = self.get_latest_sensor_data(test_unit, max_age_seconds=600)  # 10 min
            if data:
                logger.info(f"✅ Test successful!")
                logger.info(f"   Timestamp: {data['timestamp']}")
                logger.info(f"   Epoch: {data['epoch_time']}")
                logger.info(
                    f"   Sensors found: {', '.join([k for k in data.keys() if k not in ['timestamp', 'epoch_time', 'latitude', 'longitude']])}"
                )

                # Show some sensor values
                if "fuel_lvl" in data:
                    logger.info(f"   Fuel Level: {data['fuel_lvl']}%")
                if "speed" in data:
                    logger.info(f"   Speed: {data['speed']} mph")
                if "rpm" in data:
                    logger.info(f"   RPM: {data['rpm']}")

                return True
            else:
                logger.error(
                    "❌ No data returned (check if truck has data in last 10 min)"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Test failed: {e}")
            import traceback

            traceback.print_exc()
            return False
        finally:
            self.disconnect()


# Load truck configuration from database units_map table
def load_truck_config_from_db() -> Dict[str, Dict]:
    """
    Load truck configuration from Wialon units_map table

    Returns:
        Dict with truck_id -> {unit_id, capacity_gallons, capacity_liters}
    """
    try:
        # Connect to Wialon DB to get mapping
        conn = pymysql.connect(
            host=os.getenv("WIALON_DB_HOST", "localhost"),
            port=int(os.getenv("WIALON_DB_PORT", "3306")),
            user=os.getenv("WIALON_DB_USER", "wialon_user"),
            password=os.getenv("WIALON_DB_PASS", ""),
            database=os.getenv("WIALON_DB_NAME", "wialon"),
            charset="utf8mb4",
            connect_timeout=5,
            cursorclass=pymysql.cursors.DictCursor,
        )

        cursor = conn.cursor()

        # Get mapping from units_map table
        cursor.execute(
            "SELECT beyondId, unit, fuel_capacity FROM units_map ORDER BY beyondId"
        )
        units_data = cursor.fetchall()

        trucks = {}
        for row in units_data:
            beyond_id = row["beyondId"]
            unit_id = row["unit"]
            fuel_capacity = row.get("fuel_capacity", 200)  # Default 200 gallons

            trucks[beyond_id] = {
                "unit_id": unit_id,
                "capacity_gallons": fuel_capacity,
                "capacity_liters": fuel_capacity * 3.78541,  # Convert gallons to liters
            }

        cursor.close()
        conn.close()

        logger.info(
            f"✅ Loaded configuration for {len(trucks)} trucks from units_map table"
        )
        return trucks

    except Exception as e:
        logger.error(f"❌ Failed to load truck config from database: {e}")
        # Fallback to tanks.yaml if database fails
        return load_truck_config()


# Load truck configuration from tanks.yaml (fallback)
def load_truck_config(yaml_path: str = "tanks.yaml") -> Dict[str, Dict]:
    """
    Load truck configuration from tanks.yaml

    Returns:
        Dict with truck_id -> {unit_id, capacity_gallons, capacity_liters, mpg}
    """
    yaml_file = Path(yaml_path)
    if not yaml_file.exists():
        logger.error(f"❌ tanks.yaml not found at {yaml_path}")
        return {}

    with open(yaml_file, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    trucks = config.get("trucks", {})
    logger.info(f"✅ Loaded configuration for {len(trucks)} trucks from tanks.yaml")
    return trucks


# 🔧 FIX v6.4.2: Load configuration directly from tanks.yaml (units_map has duplicates/errors)
# Load configuration - use tanks.yaml as source of truth
TRUCK_CONFIG = load_truck_config()

# Extract unit ID mapping
TRUCK_UNIT_MAPPING = {
    truck_id: config["unit_id"] for truck_id, config in TRUCK_CONFIG.items()
}


if __name__ == "__main__":
    """Test the Wialon reader"""
    print("=" * 70)

    def get_truck_fuel_history(
        self, truck_id: str, hours_back: int = 24, limit: int = 100
    ) -> List[Dict]:
        """
        Get historical fuel level readings for a specific truck.

        Args:
            truck_id: Truck identifier (e.g., 'PC1280')
            hours_back: How many hours back to fetch data (default 24)
            limit: Maximum number of readings to return (default 100)

        Returns:
            List of dicts with keys: timestamp, fuel_pct, epoch_time
            Sorted chronologically (oldest first)

        🆕 v5.12.0: Added for multi-refuel detection - processes all gaps
        """
        if not self.ensure_connection():
            logger.error("❌ Cannot establish database connection")
            return []

        unit_id = self.truck_unit_mapping.get(truck_id)
        if not unit_id:
            logger.error(f"❌ Truck {truck_id} not found in mapping")
            return []

        try:
            with self.connection.cursor() as cursor:
                cutoff_epoch = int(time.time()) - (hours_back * 3600)
                fuel_param = self.config.SENSOR_PARAMS.get("fuel_lvl", "fuel_lvl")

                query = """
                    SELECT measure_datetime, value, m as epoch_time
                    FROM sensors
                    WHERE unit = %s
                      AND p = %s
                      AND m >= %s
                    ORDER BY m ASC
                    LIMIT %s
                """
                cursor.execute(query, (unit_id, fuel_param, cutoff_epoch, limit))
                results = cursor.fetchall()

                history = []
                for row in results:
                    # Convert measure_datetime to timezone-aware UTC
                    dt = row["measure_datetime"]
                    if dt.tzinfo is None:
                        dt = pytz.utc.localize(dt)
                    elif dt.tzinfo != pytz.utc:
                        dt = dt.astimezone(pytz.utc)

                    history.append(
                        {
                            "timestamp": dt,
                            "fuel_pct": float(row["value"]) if row["value"] else None,
                            "epoch_time": int(row["epoch_time"]),
                        }
                    )

                logger.info(
                    f"📊 Retrieved {len(history)} fuel readings for {truck_id} (last {hours_back}h)"
                )
                return history

        except Exception as e:
            logger.error(f"❌ Error fetching fuel history for {truck_id}: {e}")
            return []


if __name__ == "__main__":
    print("WIALON DATABASE READER - CONNECTION TEST")
    print("=" * 70)

    config = WialonConfig()
    reader = WialonReader(config, TRUCK_UNIT_MAPPING)

    # Test connection
    success = reader.test_connection()

    if success:
        print("\n✅ Wialon reader is working correctly!")
        print("   Next steps:")
        print("   1. Verify TRUCK_UNIT_MAPPING has correct unit IDs")
        print("   2. Adjust SENSOR_PARAMS for your Wialon setup")
        print("   3. Run fuel_copilot_service.py for continuous processing")
    else:
        print("\n❌ Connection test failed")
        print("   Troubleshooting:")
        print("   1. Verify hostname/port are correct")
        print("   2. Check database name (currently 'wialon')")
        print("   3. Verify table structure (messages, message_params)")
        print("   4. Check firewall allows connection to 20.127.200.135:3306")
