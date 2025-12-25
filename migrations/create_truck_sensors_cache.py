"""
Migration: Create truck_sensors_cache table
============================================
Creates a cache table for real-time sensor data from Wialon.
This table is updated every 30 seconds by the sync service,
allowing fast dashboard queries instead of hitting Wialon directly.

Run with: python migrations/create_truck_sensors_cache.py
"""

import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": os.getenv("MYSQL_USER", "fuel_admin"),
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": "fuel_copilot",
}


def create_sensors_cache_table():
    """Create truck_sensors_cache table"""
    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    # Drop existing table if exists (for migration)
    cursor.execute("DROP TABLE IF EXISTS truck_sensors_cache;")

    # Create new table with all sensor fields
    create_sql = """
    CREATE TABLE truck_sensors_cache (
        truck_id VARCHAR(20) PRIMARY KEY,
        unit_id INT NOT NULL,
        timestamp DATETIME NOT NULL,
        wialon_epoch INT NOT NULL,
        
        -- Oil System
        oil_pressure_psi DECIMAL(10,2),
        oil_temp_f DECIMAL(10,2),
        oil_level_pct DECIMAL(10,2),
        
        -- DEF
        def_level_pct DECIMAL(10,2),
        
        -- Engine
        engine_load_pct DECIMAL(10,2),
        rpm INT,
        coolant_temp_f DECIMAL(10,2),
        coolant_level_pct DECIMAL(10,2),
        
        -- Transmission & Brakes
        gear INT,
        brake_active BOOLEAN,
        
        -- Air Intake
        intake_pressure_bar DECIMAL(10,4),
        intake_temp_f DECIMAL(10,2),
        intercooler_temp_f DECIMAL(10,2),
        
        -- Fuel
        fuel_temp_f DECIMAL(10,2),
        fuel_level_pct DECIMAL(10,2),
        fuel_rate_gph DECIMAL(10,4),
        
        -- Environmental
        ambient_temp_f DECIMAL(10,2),
        barometric_pressure_inhg DECIMAL(10,4),
        
        -- Electrical
        voltage DECIMAL(10,2),
        backup_voltage DECIMAL(10,2),
        
        -- Operational Counters
        engine_hours DECIMAL(12,2),
        idle_hours DECIMAL(12,2),
        pto_hours DECIMAL(12,2),
        total_idle_fuel_gal DECIMAL(12,2),
        total_fuel_used_gal DECIMAL(12,2),
        
        -- DTC
        dtc_count INT,
        dtc_code VARCHAR(50),
        
        -- GPS
        latitude DECIMAL(11,8),
        longitude DECIMAL(11,8),
        speed_mph DECIMAL(10,2),
        altitude_ft DECIMAL(10,2),
        
        -- Metadata
        data_age_seconds INT COMMENT 'Age of data in seconds',
        last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
        
        INDEX idx_timestamp (timestamp),
        INDEX idx_last_updated (last_updated),
        INDEX idx_data_age (data_age_seconds)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    COMMENT='Real-time sensor cache updated every 30 seconds from Wialon';
    """

    cursor.execute(create_sql)
    conn.commit()

    print("✅ Created truck_sensors_cache table")

    # Show structure
    cursor.execute("DESCRIBE truck_sensors_cache;")
    columns = cursor.fetchall()
    print("\nTable structure:")
    for col in columns:
        print(f"  {col[0]}: {col[1]}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    print("Creating truck_sensors_cache table...")
    create_sensors_cache_table()
    print("\n✅ Migration complete!")
