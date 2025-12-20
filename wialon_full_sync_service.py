#!/usr/bin/env python3
"""
Wialon Full Data Sync Service
Syncs ALL data from Wialon database to local fuel_copilot cache:
- Sensors (every 30s)
- Trips (every 60s)
- Speeding events (every 60s)
- Ignition events (every 60s)
"""

import logging
import sys
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

import pymysql
from pymysql.cursors import DictCursor

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("wialon_sync.log"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Database configurations
WIALON_CONFIG = {
    "host": "20.127.200.135",
    "port": 3306,
    "user": "wialonro",
    "password": "KjmAqwertY1#2024!@Wialon",
    "database": "wialon_collect",
    "charset": "utf8mb4",
    "connect_timeout": 10,
    "read_timeout": 30,
    "write_timeout": 30,
}

LOCAL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "root",
    "password": "tomas",
    "database": "fuel_copilot",
    "charset": "utf8mb4",
    "connect_timeout": 5,
}


class WialonFullSyncService:
    """Service to sync all Wialon data to local database"""

    def __init__(self):
        self.last_sensor_sync = None
        self.last_trips_sync = None
        self.last_events_sync = None
        self.sync_count = 0

    def get_wialon_connection(self):
        """Create connection to Wialon database"""
        try:
            conn = pymysql.connect(**WIALON_CONFIG, cursorclass=DictCursor)
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to Wialon DB: {e}")
            raise

    def get_local_connection(self):
        """Create connection to local database"""
        try:
            conn = pymysql.connect(**LOCAL_CONFIG, cursorclass=DictCursor)
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to local DB: {e}")
            raise

    def sync_sensors(self):
        """Sync sensor data from Wialon (every 30s)"""
        wialon_conn = None
        local_conn = None

        try:
            logger.info("🔄 Starting sensor sync...")
            wialon_conn = self.get_wialon_connection()
            local_conn = self.get_local_connection()

            with wialon_conn.cursor() as wialon_cursor:
                # Get latest sensor data for each truck (Last Known Value strategy)
                query = """
                    SELECT 
                        unit,
                        MAX(CASE WHEN parameter = 'oil_press' THEN value END) as oil_pressure,
                        MAX(CASE WHEN parameter = 'oil_temp' THEN value END) as oil_temp,
                        MAX(CASE WHEN parameter = 'coolant_temp' THEN value END) as coolant_temp,
                        MAX(CASE WHEN parameter = 'def_level' THEN value END) as def_level,
                        MAX(CASE WHEN parameter = 'def_temp' THEN value END) as def_temp,
                        MAX(CASE WHEN parameter = 'def_quality' THEN value END) as def_quality,
                        MAX(CASE WHEN parameter = 'rpm' THEN value END) as rpm,
                        MAX(CASE WHEN parameter = 'throttle_pos' THEN value END) as throttle_position,
                        MAX(CASE WHEN parameter = 'turbo_press' THEN value END) as turbo_pressure,
                        MAX(CASE WHEN parameter = 'intake_manifold_temp' THEN value END) as intake_temp,
                        MAX(CASE WHEN parameter = 'fuel_rate' THEN value END) as fuel_rate,
                        MAX(CASE WHEN parameter = 'fuel_press' THEN value END) as fuel_pressure,
                        MAX(CASE WHEN parameter = 'fuel_temp' THEN value END) as fuel_temp,
                        MAX(CASE WHEN parameter = 'dpf_diff_press' THEN value END) as dpf_pressure,
                        MAX(CASE WHEN parameter = 'dpf_soot_level' THEN value END) as dpf_soot_level,
                        MAX(CASE WHEN parameter = 'dpf_ash_level' THEN value END) as dpf_ash_level,
                        MAX(CASE WHEN parameter = 'dpf_status' THEN value END) as dpf_status,
                        MAX(CASE WHEN parameter = 'egr_valve_pos' THEN value END) as egr_position,
                        MAX(CASE WHEN parameter = 'egr_temp' THEN value END) as egr_temp,
                        MAX(CASE WHEN parameter = 'ambient_air_temp' THEN value END) as ambient_temp,
                        MAX(CASE WHEN parameter = 'barometric_press' THEN value END) as barometric_pressure,
                        MAX(CASE WHEN parameter = 'battery_volt' THEN value END) as battery_voltage,
                        MAX(CASE WHEN parameter = 'alternator_status' THEN value END) as alternator_status,
                        MAX(CASE WHEN parameter = 'speed' THEN value END) as vehicle_speed,
                        MAX(CASE WHEN parameter = 'odometer' THEN value END) as odometer,
                        MAX(CASE WHEN parameter = 'engine_hours' THEN value END) as engine_hours,
                        MAX(CASE WHEN parameter = 'idle_hours' THEN value END) as idle_hours,
                        MAX(CASE WHEN parameter = 'lat' THEN value END) as latitude,
                        MAX(CASE WHEN parameter = 'lon' THEN value END) as longitude,
                        MAX(CASE WHEN parameter = 'altitude' THEN value END) as altitude,
                        MAX(CASE WHEN parameter = 'direction' THEN value END) as heading,
                        MAX(CASE WHEN parameter = 'transmission_oil_temp' THEN value END) as transmission_temp,
                        MAX(CASE WHEN parameter = 'transmission_oil_press' THEN value END) as transmission_pressure,
                        MAX(CASE WHEN parameter = 'trans_gear' THEN value END) as current_gear,
                        MAX(timestamp) as last_update
                    FROM sensors
                    WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                    GROUP BY unit
                """

                wialon_cursor.execute(query)
                sensors_data = wialon_cursor.fetchall()

                logger.info(
                    f"📊 Retrieved {len(sensors_data)} trucks from Wialon sensors"
                )

                # Batch upsert to local database
                with local_conn.cursor() as local_cursor:
                    upsert_query = """
                        INSERT INTO truck_sensors_cache (
                            truck_id, oil_pressure_psi, oil_temp_f, coolant_temp_f,
                            def_level_pct, def_temp_f, def_quality,
                            rpm, throttle_position_pct, turbo_pressure_psi, intake_temp_f,
                            fuel_rate_gph, fuel_pressure_psi, fuel_temp_f,
                            dpf_pressure_psi, dpf_soot_pct, dpf_ash_pct, dpf_status,
                            egr_position_pct, egr_temp_f,
                            ambient_temp_f, barometric_pressure_psi,
                            battery_voltage_v, alternator_status,
                            speed_mph, odometer_mi, engine_hours, idle_hours,
                            latitude, longitude, altitude_ft, heading_deg,
                            transmission_temp_f, transmission_pressure_psi, current_gear,
                            last_update, cache_timestamp
                        ) VALUES (
                            %(unit)s, %(oil_pressure)s, %(oil_temp)s, %(coolant_temp)s,
                            %(def_level)s, %(def_temp)s, %(def_quality)s,
                            %(rpm)s, %(throttle_position)s, %(turbo_pressure)s, %(intake_temp)s,
                            %(fuel_rate)s, %(fuel_pressure)s, %(fuel_temp)s,
                            %(dpf_pressure)s, %(dpf_soot_level)s, %(dpf_ash_level)s, %(dpf_status)s,
                            %(egr_position)s, %(egr_temp)s,
                            %(ambient_temp)s, %(barometric_pressure)s,
                            %(battery_voltage)s, %(alternator_status)s,
                            %(vehicle_speed)s, %(odometer)s, %(engine_hours)s, %(idle_hours)s,
                            %(latitude)s, %(longitude)s, %(altitude)s, %(heading)s,
                            %(transmission_temp)s, %(transmission_pressure)s, %(current_gear)s,
                            %(last_update)s, NOW()
                        )
                        ON DUPLICATE KEY UPDATE
                            oil_pressure_psi = VALUES(oil_pressure_psi),
                            oil_temp_f = VALUES(oil_temp_f),
                            coolant_temp_f = VALUES(coolant_temp_f),
                            def_level_pct = VALUES(def_level_pct),
                            def_temp_f = VALUES(def_temp_f),
                            def_quality = VALUES(def_quality),
                            rpm = VALUES(rpm),
                            throttle_position_pct = VALUES(throttle_position_pct),
                            turbo_pressure_psi = VALUES(turbo_pressure_psi),
                            intake_temp_f = VALUES(intake_temp_f),
                            fuel_rate_gph = VALUES(fuel_rate_gph),
                            fuel_pressure_psi = VALUES(fuel_pressure_psi),
                            fuel_temp_f = VALUES(fuel_temp_f),
                            dpf_pressure_psi = VALUES(dpf_pressure_psi),
                            dpf_soot_pct = VALUES(dpf_soot_pct),
                            dpf_ash_pct = VALUES(dpf_ash_pct),
                            dpf_status = VALUES(dpf_status),
                            egr_position_pct = VALUES(egr_position_pct),
                            egr_temp_f = VALUES(egr_temp_f),
                            ambient_temp_f = VALUES(ambient_temp_f),
                            barometric_pressure_psi = VALUES(barometric_pressure_psi),
                            battery_voltage_v = VALUES(battery_voltage_v),
                            alternator_status = VALUES(alternator_status),
                            speed_mph = VALUES(speed_mph),
                            odometer_mi = VALUES(odometer_mi),
                            engine_hours = VALUES(engine_hours),
                            idle_hours = VALUES(idle_hours),
                            latitude = VALUES(latitude),
                            longitude = VALUES(longitude),
                            altitude_ft = VALUES(altitude_ft),
                            heading_deg = VALUES(heading_deg),
                            transmission_temp_f = VALUES(transmission_temp_f),
                            transmission_pressure_psi = VALUES(transmission_pressure_psi),
                            current_gear = VALUES(current_gear),
                            last_update = VALUES(last_update),
                            cache_timestamp = NOW()
                    """

                    local_cursor.executemany(upsert_query, sensors_data)
                    local_conn.commit()

                    logger.info(f"✅ Synced {len(sensors_data)} trucks' sensor data")

            self.last_sensor_sync = datetime.now()

        except Exception as e:
            logger.error(f"❌ Sensor sync failed: {e}", exc_info=True)
        finally:
            if wialon_conn:
                wialon_conn.close()
            if local_conn:
                local_conn.close()

    def sync_trips(self):
        """Sync trip data from Wialon (every 60s)
        
        🔧 FIX v6.4.3: Updated to use existing 'trips' table (not 'truck_trips')
        - Local 'trips' table columns: truck_id, start_time, end_time, distance_mi, 
          duration_minutes, avg_speed_mph, max_speed_mph
        - Wialon 'trips' table columns: unit, from_timestamp, to_timestamp, 
          distance_miles, avg_speed, max_speed
        """
        wialon_conn = None
        local_conn = None

        try:
            logger.info("🔄 Starting trips sync...")
            wialon_conn = self.get_wialon_connection()
            local_conn = self.get_local_connection()

            with wialon_conn.cursor() as wialon_cursor:
                # Get trips from last 7 days
                # 🔧 FIX v6.4.2: Removed non-existent columns: driver, harsh_accel_count, harsh_brake_count, speeding_count
                # 🔧 FIX v6.4.3: Map Wialon columns to local 'trips' table columns
                query = """
                    SELECT 
                        unit as truck_id,
                        from_timestamp as start_time,
                        to_timestamp as end_time,
                        TIMESTAMPDIFF(MINUTE, from_timestamp, to_timestamp) as duration_minutes,
                        distance_miles as distance_mi,
                        avg_speed as avg_speed_mph,
                        max_speed as max_speed_mph,
                        from_latitude as start_latitude,
                        from_longitude as start_longitude,
                        to_latitude as end_latitude,
                        to_longitude as end_longitude
                    FROM trips
                    WHERE from_timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                    ORDER BY from_timestamp DESC
                """

                wialon_cursor.execute(query)
                trips_data = wialon_cursor.fetchall()

                logger.info(f"📊 Retrieved {len(trips_data)} trips from last 7 days")

                if trips_data:
                    # Batch upsert to local database
                    with local_conn.cursor() as local_cursor:
                        # 🔧 FIX v6.4.3: Use existing 'trips' table with correct column names
                        upsert_query = """
                            INSERT INTO trips (
                                truck_id, start_time, end_time, duration_minutes,
                                distance_mi, avg_speed_mph, max_speed_mph,
                                start_latitude, start_longitude, end_latitude, end_longitude,
                                created_at
                            ) VALUES (
                                %(truck_id)s, %(start_time)s, %(end_time)s, %(duration_minutes)s,
                                %(distance_mi)s, %(avg_speed_mph)s, %(max_speed_mph)s,
                                %(start_latitude)s, %(start_longitude)s, %(end_latitude)s, %(end_longitude)s,
                                NOW()
                            )
                            ON DUPLICATE KEY UPDATE
                                end_time = VALUES(end_time),
                                duration_minutes = VALUES(duration_minutes),
                                distance_mi = VALUES(distance_mi),
                                avg_speed_mph = VALUES(avg_speed_mph),
                                max_speed_mph = VALUES(max_speed_mph),
                                end_latitude = VALUES(end_latitude),
                                end_longitude = VALUES(end_longitude)
                        """

                        local_cursor.executemany(upsert_query, trips_data)
                        local_conn.commit()

                        logger.info(f"✅ Synced {len(trips_data)} trips to local 'trips' table")

            self.last_trips_sync = datetime.now()

        except Exception as e:
            logger.error(f"❌ Trips sync failed: {e}", exc_info=True)
        finally:
            if wialon_conn:
                wialon_conn.close()
            if local_conn:
                local_conn.close()

    def sync_speeding_events(self):
        """Sync speeding events from Wialon (every 60s)"""
        wialon_conn = None
        local_conn = None

        try:
            logger.info("🔄 Starting speeding events sync...")
            wialon_conn = self.get_wialon_connection()
            local_conn = self.get_local_connection()

            with wialon_conn.cursor() as wialon_cursor:
                # Get speeding events from last 7 days
                query = """
                    SELECT 
                        unit,
                        from_timestamp,
                        to_timestamp,
                        TIMESTAMPDIFF(SECOND, from_timestamp, to_timestamp) / 60.0 as duration_minutes,
                        max_speed,
                        `limit` as speed_limit,
                        (max_speed - `limit`) as speed_over_limit,
                        distance_miles,
                        driver,
                        CASE 
                            WHEN (max_speed - `limit`) <= 5 THEN 'minor'
                            WHEN (max_speed - `limit`) <= 15 THEN 'moderate'
                            ELSE 'severe'
                        END as severity,
                        lat,
                        lon
                    FROM speedings
                    WHERE from_timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                    ORDER BY from_timestamp DESC
                """

                wialon_cursor.execute(query)
                speeding_data = wialon_cursor.fetchall()

                logger.info(
                    f"📊 Retrieved {len(speeding_data)} speeding events from last 7 days"
                )

                if speeding_data:
                    # Batch upsert to local database
                    with local_conn.cursor() as local_cursor:
                        upsert_query = """
                            INSERT INTO truck_speeding_events (
                                truck_id, start_time, end_time, duration_minutes,
                                max_speed, speed_limit, speed_over_limit, distance_miles,
                                driver_name, severity, latitude, longitude,
                                created_at
                            ) VALUES (
                                %(unit)s, %(from_timestamp)s, %(to_timestamp)s, %(duration_minutes)s,
                                %(max_speed)s, %(speed_limit)s, %(speed_over_limit)s, %(distance_miles)s,
                                %(driver)s, %(severity)s, %(lat)s, %(lon)s,
                                NOW()
                            )
                            ON DUPLICATE KEY UPDATE
                                duration_minutes = VALUES(duration_minutes),
                                max_speed = VALUES(max_speed),
                                speed_limit = VALUES(speed_limit),
                                speed_over_limit = VALUES(speed_over_limit),
                                distance_miles = VALUES(distance_miles),
                                driver_name = VALUES(driver_name),
                                severity = VALUES(severity),
                                latitude = VALUES(latitude),
                                longitude = VALUES(longitude)
                        """

                        local_cursor.executemany(upsert_query, speeding_data)
                        local_conn.commit()

                        logger.info(f"✅ Synced {len(speeding_data)} speeding events")

            self.last_events_sync = datetime.now()

        except Exception as e:
            logger.error(f"❌ Speeding events sync failed: {e}", exc_info=True)
        finally:
            if wialon_conn:
                wialon_conn.close()
            if local_conn:
                local_conn.close()

    def sync_ignition_events(self):
        """Sync ignition events from Wialon (every 60s)"""
        wialon_conn = None
        local_conn = None

        try:
            logger.info("🔄 Starting ignition events sync...")
            wialon_conn = self.get_wialon_connection()
            local_conn = self.get_local_connection()

            with wialon_conn.cursor() as wialon_cursor:
                # Get ignition events from last 7 days
                query = """
                    SELECT 
                        unit,
                        timestamp,
                        state,
                        CASE 
                            WHEN state = 1 THEN 'on'
                            ELSE 'off'
                        END as event_type,
                        hours,
                        switches,
                        lat,
                        lon
                    FROM ignitions
                    WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                    ORDER BY timestamp DESC
                """

                wialon_cursor.execute(query)
                ignition_data = wialon_cursor.fetchall()

                logger.info(
                    f"📊 Retrieved {len(ignition_data)} ignition events from last 7 days"
                )

                if ignition_data:
                    # Batch upsert to local database
                    with local_conn.cursor() as local_cursor:
                        upsert_query = """
                            INSERT INTO truck_ignition_events (
                                truck_id, event_time, event_type, state,
                                engine_hours, switch_count, latitude, longitude,
                                created_at
                            ) VALUES (
                                %(unit)s, %(timestamp)s, %(event_type)s, %(state)s,
                                %(hours)s, %(switches)s, %(lat)s, %(lon)s,
                                NOW()
                            )
                            ON DUPLICATE KEY UPDATE
                                event_type = VALUES(event_type),
                                state = VALUES(state),
                                engine_hours = VALUES(engine_hours),
                                switch_count = VALUES(switch_count),
                                latitude = VALUES(latitude),
                                longitude = VALUES(longitude)
                        """

                        local_cursor.executemany(upsert_query, ignition_data)
                        local_conn.commit()

                        logger.info(f"✅ Synced {len(ignition_data)} ignition events")

        except Exception as e:
            logger.error(f"❌ Ignition events sync failed: {e}", exc_info=True)
        finally:
            if wialon_conn:
                wialon_conn.close()
            if local_conn:
                local_conn.close()

    def run_sync_cycle(self):
        """Run one complete sync cycle"""
        self.sync_count += 1
        logger.info(f"\n{'='*60}")
        logger.info(
            f"🔄 Sync Cycle #{self.sync_count} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.info(f"{'='*60}")

        # Sync sensors every cycle (30s)
        self.sync_sensors()

        # Sync trips/events every 2nd cycle (60s)
        if self.sync_count % 2 == 0:
            self.sync_trips()
            self.sync_speeding_events()
            self.sync_ignition_events()

        logger.info(f"\n✅ Sync cycle #{self.sync_count} completed")
        logger.info(
            f"   Last sensor sync: {self.last_sensor_sync.strftime('%H:%M:%S') if self.last_sensor_sync else 'Never'}"
        )
        logger.info(
            f"   Last trips sync: {self.last_trips_sync.strftime('%H:%M:%S') if self.last_trips_sync else 'Never'}"
        )
        logger.info(
            f"   Last events sync: {self.last_events_sync.strftime('%H:%M:%S') if self.last_events_sync else 'Never'}"
        )

    def start(self):
        """Start the continuous sync service"""
        logger.info("🚀 Starting Wialon Full Sync Service")
        logger.info(
            f"   Wialon DB: {WIALON_CONFIG['host']}:{WIALON_CONFIG['port']}/{WIALON_CONFIG['database']}"
        )
        logger.info(
            f"   Local DB: {LOCAL_CONFIG['host']}:{LOCAL_CONFIG['port']}/{LOCAL_CONFIG['database']}"
        )
        logger.info(f"   Sensors: Every 30 seconds")
        logger.info(f"   Trips/Events: Every 60 seconds")
        logger.info(f"{'='*60}\n")

        while True:
            try:
                self.run_sync_cycle()
                time.sleep(30)  # Sleep 30 seconds between cycles
            except KeyboardInterrupt:
                logger.info("\n🛑 Received shutdown signal")
                break
            except Exception as e:
                logger.error(f"❌ Unexpected error in sync cycle: {e}", exc_info=True)
                logger.info("⏸️  Waiting 30 seconds before retry...")
                time.sleep(30)

        logger.info("👋 Wialon Full Sync Service stopped")


def main():
    """Main entry point"""
    service = WialonFullSyncService()
    service.start()


if __name__ == "__main__":
    main()
