"""
Migration: Create Wialon sync tables for driver behavior and trips
===================================================================
Creates cache tables for all Wialon data:
- truck_trips: Trip history with distance, speed, duration
- truck_speeding_events: Speeding violations for driver scoring
- truck_ignition_events: Engine on/off events

Run with: python migrations/create_wialon_sync_tables.py
"""

import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": os.getenv("MYSQL_USER", "fuel_admin"),
    "password": os.getenv("MYSQL_PASSWORD", "FuelCopilot2025!"),
    "database": "fuel_copilot",
}


def create_trips_table():
    """Create truck_trips table"""
    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS truck_trips;")

    create_sql = """
    CREATE TABLE truck_trips (
        id INT AUTO_INCREMENT PRIMARY KEY,
        truck_id VARCHAR(20) NOT NULL,
        unit_id INT NOT NULL,
        
        -- Trip timing
        start_time DATETIME NOT NULL,
        end_time DATETIME NOT NULL,
        duration_minutes INT,
        
        -- Trip location
        start_latitude DECIMAL(11,8),
        start_longitude DECIMAL(11,8),
        end_latitude DECIMAL(11,8),
        end_longitude DECIMAL(11,8),
        
        -- Trip metrics
        distance_miles DECIMAL(10,2),
        max_speed_mph INT,
        avg_speed_mph INT,
        odometer_miles DECIMAL(12,2),
        
        -- Driver behavior (calculated from events)
        speeding_count INT DEFAULT 0,
        harsh_braking_count INT DEFAULT 0,
        harsh_acceleration_count INT DEFAULT 0,
        
        -- Metadata
        wialon_from_timestamp BIGINT,
        wialon_to_timestamp BIGINT,
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        INDEX idx_truck_id (truck_id),
        INDEX idx_start_time (start_time),
        INDEX idx_end_time (end_time),
        INDEX idx_truck_time (truck_id, start_time),
        UNIQUE KEY unique_trip (truck_id, wialon_from_timestamp)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    COMMENT='Trip history synced from Wialon trips table';
    """

    cursor.execute(create_sql)
    conn.commit()
    print("✅ Created truck_trips table")

    cursor.close()
    conn.close()


def create_speeding_events_table():
    """Create truck_speeding_events table"""
    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS truck_speeding_events;")

    create_sql = """
    CREATE TABLE truck_speeding_events (
        id INT AUTO_INCREMENT PRIMARY KEY,
        truck_id VARCHAR(20) NOT NULL,
        unit_id INT NOT NULL,
        
        -- Event timing
        start_time DATETIME NOT NULL,
        end_time DATETIME NOT NULL,
        duration_seconds INT,
        
        -- Event location
        start_latitude DECIMAL(11,8),
        start_longitude DECIMAL(11,8),
        end_latitude DECIMAL(11,8),
        end_longitude DECIMAL(11,8),
        
        -- Speeding details
        max_speed_mph INT,
        last_speed_mph INT,
        speed_limit_mph INT,
        speed_over_limit_mph INT COMMENT 'How much over the limit',
        distance_miles DECIMAL(10,2),
        
        -- Severity classification
        severity VARCHAR(20) COMMENT 'minor, moderate, severe',
        
        -- Metadata
        wialon_from_timestamp BIGINT,
        wialon_to_timestamp BIGINT,
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        INDEX idx_truck_id (truck_id),
        INDEX idx_start_time (start_time),
        INDEX idx_severity (severity),
        INDEX idx_truck_time (truck_id, start_time),
        UNIQUE KEY unique_event (truck_id, wialon_from_timestamp)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    COMMENT='Speeding events synced from Wialon speedings table';
    """

    cursor.execute(create_sql)
    conn.commit()
    print("✅ Created truck_speeding_events table")

    cursor.close()
    conn.close()


def create_ignition_events_table():
    """Create truck_ignition_events table"""
    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    cursor.execute("DROP TABLE IF EXISTS truck_ignition_events;")

    create_sql = """
    CREATE TABLE truck_ignition_events (
        id INT AUTO_INCREMENT PRIMARY KEY,
        truck_id VARCHAR(20) NOT NULL,
        unit_id INT NOT NULL,
        
        -- Event timing
        start_time DATETIME NOT NULL,
        end_time DATETIME,
        duration_hours DECIMAL(10,2),
        
        -- Event location
        start_latitude DECIMAL(11,8),
        start_longitude DECIMAL(11,8),
        end_latitude DECIMAL(11,8),
        end_longitude DECIMAL(11,8),
        
        -- Ignition details
        state INT COMMENT '1=on, 0=off',
        type INT,
        switches INT COMMENT 'Number of on/off cycles',
        
        -- Metadata
        wialon_from_timestamp BIGINT,
        wialon_to_timestamp BIGINT,
        synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        
        INDEX idx_truck_id (truck_id),
        INDEX idx_start_time (start_time),
        INDEX idx_state (state),
        INDEX idx_truck_time (truck_id, start_time),
        UNIQUE KEY unique_event (truck_id, wialon_from_timestamp)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    COMMENT='Ignition events synced from Wialon ignitions table';
    """

    cursor.execute(create_sql)
    conn.commit()
    print("✅ Created truck_ignition_events table")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    print("Creating Wialon sync tables...")
    create_trips_table()
    create_speeding_events_table()
    create_ignition_events_table()
    print("\n✅ All tables created!")
    print("\nNext steps:")
    print("1. Run: python wialon_full_sync_service.py (to populate tables)")
    print("2. Tables will auto-update every 30 seconds with new data")
