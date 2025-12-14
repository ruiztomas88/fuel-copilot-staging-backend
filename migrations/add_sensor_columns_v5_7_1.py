"""
Migration: Add sensor columns for ML and diagnostics
Version: v5.7.1
Date: December 13, 2025

Run this script on the VM to add new columns and tables.
Usage: python migrations/add_sensor_columns_v5_7_1.py
"""

import pymysql
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_db_config


def get_connection():
    """Get database connection"""
    config = get_db_config()
    return pymysql.connect(
        host=config.get("host", "localhost"),
        port=config.get("port", 3306),
        user=config.get("user", "fuel_admin"),
        password=config.get("password", ""),
        database=config.get("database", "fuel_copilot"),
        charset="utf8mb4",
    )


def column_exists(cursor, table: str, column: str) -> bool:
    """Check if a column exists in a table"""
    cursor.execute(
        """
        SELECT COUNT(*) FROM information_schema.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = %s 
        AND COLUMN_NAME = %s
        """,
        (table, column),
    )
    return cursor.fetchone()[0] > 0


def table_exists(cursor, table: str) -> bool:
    """Check if a table exists"""
    cursor.execute(
        """
        SELECT COUNT(*) FROM information_schema.TABLES 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = %s
        """,
        (table,),
    )
    return cursor.fetchone()[0] > 0


def index_exists(cursor, table: str, index_name: str) -> bool:
    """Check if an index exists"""
    cursor.execute(
        """
        SELECT COUNT(*) FROM information_schema.STATISTICS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = %s 
        AND INDEX_NAME = %s
        """,
        (table, index_name),
    )
    return cursor.fetchone()[0] > 0


def run_migration():
    """Run the migration"""
    print("=" * 60)
    print("🚀 Migration v5.7.1: Add sensor columns for ML")
    print("=" * 60)

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # ================================================================
        # 1. Add new columns to fuel_metrics
        # ================================================================
        print("\n📊 Adding columns to fuel_metrics...")

        new_columns = [
            ("sats", "TINYINT UNSIGNED DEFAULT NULL COMMENT 'GPS satellites count'"),
            ("pwr_int", "FLOAT DEFAULT NULL COMMENT 'Internal/battery voltage (V)'"),
            ("terrain_factor", "FLOAT DEFAULT 1.0 COMMENT 'Terrain consumption adjustment'"),
            ("gps_quality", "VARCHAR(20) DEFAULT NULL COMMENT 'GPS quality level'"),
            ("idle_hours_ecu", "FLOAT DEFAULT NULL COMMENT 'ECU idle hours counter'"),
        ]

        for col_name, col_def in new_columns:
            if column_exists(cursor, "fuel_metrics", col_name):
                print(f"   ⏭️  Column '{col_name}' already exists, skipping")
            else:
                cursor.execute(f"ALTER TABLE fuel_metrics ADD COLUMN {col_name} {col_def}")
                print(f"   ✅ Added column '{col_name}'")

        # ================================================================
        # 2. Create dtc_events table
        # ================================================================
        print("\n📊 Creating dtc_events table...")

        if table_exists(cursor, "dtc_events"):
            print("   ⏭️  Table 'dtc_events' already exists, skipping")
        else:
            cursor.execute("""
                CREATE TABLE dtc_events (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    timestamp_utc DATETIME NOT NULL,
                    truck_id VARCHAR(20) NOT NULL,
                    carrier_id VARCHAR(50) DEFAULT 'skylord',
                    dtc_code VARCHAR(20) NOT NULL COMMENT 'Full DTC code (e.g., SPN123.FMI4)',
                    spn INT COMMENT 'Suspect Parameter Number',
                    fmi INT COMMENT 'Failure Mode Identifier',
                    severity VARCHAR(20) DEFAULT 'WARNING',
                    system VARCHAR(50) DEFAULT 'UNKNOWN',
                    description TEXT,
                    raw_value VARCHAR(100),
                    resolved_at DATETIME DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_truck_time (truck_id, timestamp_utc),
                    INDEX idx_dtc_code (dtc_code),
                    INDEX idx_severity (severity),
                    INDEX idx_unresolved (resolved_at, truck_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            print("   ✅ Created table 'dtc_events'")

        # ================================================================
        # 3. Create voltage_events table
        # ================================================================
        print("\n📊 Creating voltage_events table...")

        if table_exists(cursor, "voltage_events"):
            print("   ⏭️  Table 'voltage_events' already exists, skipping")
        else:
            cursor.execute("""
                CREATE TABLE voltage_events (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    timestamp_utc DATETIME NOT NULL,
                    truck_id VARCHAR(20) NOT NULL,
                    voltage FLOAT NOT NULL,
                    status VARCHAR(20) NOT NULL,
                    is_engine_running BOOLEAN DEFAULT FALSE,
                    rpm INT DEFAULT NULL,
                    message TEXT,
                    resolved_at DATETIME DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_truck_time (truck_id, timestamp_utc),
                    INDEX idx_status (status),
                    INDEX idx_unresolved (resolved_at, truck_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            print("   ✅ Created table 'voltage_events'")

        # ================================================================
        # 4. Create gps_quality_events table
        # ================================================================
        print("\n📊 Creating gps_quality_events table...")

        if table_exists(cursor, "gps_quality_events"):
            print("   ⏭️  Table 'gps_quality_events' already exists, skipping")
        else:
            cursor.execute("""
                CREATE TABLE gps_quality_events (
                    id BIGINT AUTO_INCREMENT PRIMARY KEY,
                    timestamp_utc DATETIME NOT NULL,
                    truck_id VARCHAR(20) NOT NULL,
                    satellites TINYINT UNSIGNED NOT NULL,
                    quality VARCHAR(20) NOT NULL,
                    estimated_accuracy_m FLOAT,
                    duration_minutes INT DEFAULT NULL,
                    location_lat DOUBLE DEFAULT NULL,
                    location_lon DOUBLE DEFAULT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_truck_time (truck_id, timestamp_utc),
                    INDEX idx_quality (quality)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """)
            print("   ✅ Created table 'gps_quality_events'")

        # ================================================================
        # 5. Add indexes for ML queries
        # ================================================================
        print("\n📊 Adding ML indexes to fuel_metrics...")

        ml_indexes = [
            ("idx_mpg_analysis", "truck_id, timestamp_utc, mpg_current, speed_mph"),
            ("idx_idle_analysis", "truck_id, timestamp_utc, idle_gph, rpm, truck_status"),
            ("idx_drift_analysis", "truck_id, timestamp_utc, drift_pct, sensor_pct, estimated_pct"),
        ]

        for idx_name, idx_cols in ml_indexes:
            if index_exists(cursor, "fuel_metrics", idx_name):
                print(f"   ⏭️  Index '{idx_name}' already exists, skipping")
            else:
                try:
                    cursor.execute(f"CREATE INDEX {idx_name} ON fuel_metrics ({idx_cols})")
                    print(f"   ✅ Created index '{idx_name}'")
                except Exception as e:
                    print(f"   ⚠️  Could not create index '{idx_name}': {e}")

        # Commit all changes
        conn.commit()

        print("\n" + "=" * 60)
        print("✅ Migration completed successfully!")
        print("=" * 60)

        # Show summary
        print("\n📋 Summary:")
        print("   - 5 new columns in fuel_metrics")
        print("   - 3 new tables (dtc_events, voltage_events, gps_quality_events)")
        print("   - 3 new indexes for ML queries")

    except Exception as e:
        conn.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
