#!/usr/bin/env python3
"""
Wialon Full Data Sync Service
Syncs ALL data from Wialon database to local fuel_copilot cache:
- Sensors (every 30s)
- Trips (every 60s)
- Speeding events (every 60s)
- Ignition events (every 60s)
"""

import sys
import time
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
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
                            truck_id, oil_pressure, oil_temp, coolant_temp,
                            def_level, def_temp, def_quality,
                            rpm, throttle_position, turbo_pressure, intake_temp,
                            fuel_rate, fuel_pressure, fuel_temp,
                            dpf_pressure, dpf_soot_level, dpf_ash_level, dpf_status,
                            egr_position, egr_temp,
                            ambient_temp, barometric_pressure,
                            battery_voltage, alternator_status,
                            vehicle_speed, odometer, engine_hours, idle_hours,
                            latitude, longitude, altitude, heading,
                            transmission_temp, transmission_pressure, current_gear,
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
                            oil_pressure = VALUES(oil_pressure),
                            oil_temp = VALUES(oil_temp),
                            coolant_temp = VALUES(coolant_temp),
                            def_level = VALUES(def_level),
                            def_temp = VALUES(def_temp),
                            def_quality = VALUES(def_quality),
                            rpm = VALUES(rpm),
                            throttle_position = VALUES(throttle_position),
                            turbo_pressure = VALUES(turbo_pressure),
                            intake_temp = VALUES(intake_temp),
                            fuel_rate = VALUES(fuel_rate),
                            fuel_pressure = VALUES(fuel_pressure),
                            fuel_temp = VALUES(fuel_temp),
                            dpf_pressure = VALUES(dpf_pressure),
                            dpf_soot_level = VALUES(dpf_soot_level),
                            dpf_ash_level = VALUES(dpf_ash_level),
                            dpf_status = VALUES(dpf_status),
                            egr_position = VALUES(egr_position),
                            egr_temp = VALUES(egr_temp),
                            ambient_temp = VALUES(ambient_temp),
                            barometric_pressure = VALUES(barometric_pressure),
                            battery_voltage = VALUES(battery_voltage),
                            alternator_status = VALUES(alternator_status),
                            vehicle_speed = VALUES(vehicle_speed),
                            odometer = VALUES(odometer),
                            engine_hours = VALUES(engine_hours),
                            idle_hours = VALUES(idle_hours),
                            latitude = VALUES(latitude),
                            longitude = VALUES(longitude),
                            altitude = VALUES(altitude),
                            heading = VALUES(heading),
                            transmission_temp = VALUES(transmission_temp),
                            transmission_pressure = VALUES(transmission_pressure),
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
        """Sync trip data from Wialon (every 60s)"""
        wialon_conn = None
        local_conn = None

        try:
            logger.info("🔄 Starting trips sync...")
            wialon_conn = self.get_wialon_connection()
            local_conn = self.get_local_connection()

            with wialon_conn.cursor() as wialon_cursor:
                # Get trips from last 7 days
                query = """
                    SELECT 
                        unit,
                        from_timestamp,
                        to_timestamp,
                        TIMESTAMPDIFF(SECOND, from_timestamp, to_timestamp) / 3600.0 as duration_hours,
                        distance_miles,
                        avg_speed,
                        max_speed,
                        odometer,
                        driver,
                        harsh_accel_count,
                        harsh_brake_count,
                        speeding_count
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
                        upsert_query = """
                            INSERT INTO truck_trips (
                                truck_id, start_time, end_time, duration_hours,
                                distance_miles, avg_speed, max_speed, odometer,
                                driver_name, harsh_accel_count, harsh_brake_count, speeding_count,
                                created_at
                            ) VALUES (
                                %(unit)s, %(from_timestamp)s, %(to_timestamp)s, %(duration_hours)s,
                                %(distance_miles)s, %(avg_speed)s, %(max_speed)s, %(odometer)s,
                                %(driver)s, %(harsh_accel_count)s, %(harsh_brake_count)s, %(speeding_count)s,
                                NOW()
                            )
                            ON DUPLICATE KEY UPDATE
                                duration_hours = VALUES(duration_hours),
                                distance_miles = VALUES(distance_miles),
                                avg_speed = VALUES(avg_speed),
                                max_speed = VALUES(max_speed),
                                odometer = VALUES(odometer),
                                driver_name = VALUES(driver_name),
                                harsh_accel_count = VALUES(harsh_accel_count),
                                harsh_brake_count = VALUES(harsh_brake_count),
                                speeding_count = VALUES(speeding_count)
                        """

                        local_cursor.executemany(upsert_query, trips_data)
                        local_conn.commit()

                        logger.info(f"✅ Synced {len(trips_data)} trips")

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
