"""
Migration: Add Wialon sensor columns v6.3.0
Date: December 16, 2025

Adds columns for all new Wialon sensors to enable:
- Better predictive maintenance (oil, intake sensors)
- Improved cost tracking (DEF, idle fuel)
- Enhanced driver behavior (gear, brake)

Usage: python migrations/add_wialon_sensors_v6_3_0.py
"""

import pymysql
import sys
import os

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
    """Check if a column exists"""
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


def run_migration():
    """Run the migration"""
    print("=" * 70)
    print("🚀 Migration v6.3.0: Add Wialon Sensor Columns")
    print("=" * 70)

    conn = get_connection()
    cursor = conn.cursor()

    # All new columns to add
    new_columns = [
        # Priority 1: Predictive Maintenance
        ("engine_load_pct", "FLOAT DEFAULT NULL COMMENT 'Engine load percentage (0-100)'"),
        ("oil_pressure_psi", "FLOAT DEFAULT NULL COMMENT 'Oil pressure in PSI'"),
        ("oil_temp_f", "FLOAT DEFAULT NULL COMMENT 'Oil temperature in Fahrenheit'"),
        ("oil_level_pct", "FLOAT DEFAULT NULL COMMENT 'Oil level percentage'"),
        ("intake_pressure_psi", "FLOAT DEFAULT NULL COMMENT 'Intake manifold pressure PSI'"),
        ("intake_temp_f", "FLOAT DEFAULT NULL COMMENT 'Intake air temperature F'"),
        
        # Priority 2: Cost Tracking
        ("def_level_pct", "FLOAT DEFAULT NULL COMMENT 'DEF/AdBlue level percentage'"),
        ("total_idle_fuel_gal", "FLOAT DEFAULT NULL COMMENT 'Cumulative idle fuel used (gallons)'"),
        ("fuel_temp_f", "FLOAT DEFAULT NULL COMMENT 'Fuel temperature F'"),
        ("ambient_temp_f", "FLOAT DEFAULT NULL COMMENT 'Ambient/outside temperature F'"),
        
        # Priority 3: Driver Behavior
        ("gear_position", "TINYINT DEFAULT NULL COMMENT 'Current gear position (0-18)'"),
        ("brake_active", "TINYINT(1) DEFAULT NULL COMMENT 'Brake pedal active (0/1)'"),
        ("pto_hours", "FLOAT DEFAULT NULL COMMENT 'Power take-off hours'"),
        
        # Priority 4: Safety/Other
        ("backup_battery_v", "FLOAT DEFAULT NULL COMMENT 'Backup battery voltage'"),
        ("barometric_pressure", "FLOAT DEFAULT NULL COMMENT 'Barometric pressure (inHg)'"),
        
        # Already should exist but let's ensure
        ("battery_voltage", "FLOAT DEFAULT NULL COMMENT 'Main battery voltage'"),
        ("idle_gph", "FLOAT DEFAULT NULL COMMENT 'Idle fuel consumption GPH'"),
        ("gps_fix_quality", "TINYINT DEFAULT NULL COMMENT 'GPS fix quality (0-3)'"),
    ]

    try:
        print("\n📊 Adding columns to fuel_metrics...")
        added = 0
        skipped = 0

        for col_name, col_def in new_columns:
            if column_exists(cursor, "fuel_metrics", col_name):
                print(f"   ⏭️  {col_name} - already exists")
                skipped += 1
            else:
                try:
                    cursor.execute(f"ALTER TABLE fuel_metrics ADD COLUMN {col_name} {col_def}")
                    conn.commit()
                    print(f"   ✅ {col_name} - added")
                    added += 1
                except Exception as e:
                    print(f"   ❌ {col_name} - error: {e}")

        # Add useful indexes
        print("\n📊 Adding indexes...")
        indexes = [
            ("idx_engine_load", "engine_load_pct"),
            ("idx_def_level", "def_level_pct"),
            ("idx_oil_pressure", "oil_pressure_psi"),
            ("idx_gear", "gear_position"),
        ]
        
        for idx_name, col_name in indexes:
            try:
                cursor.execute(f"CREATE INDEX {idx_name} ON fuel_metrics({col_name})")
                conn.commit()
                print(f"   ✅ Index {idx_name}")
            except Exception as e:
                if "Duplicate" in str(e):
                    print(f"   ⏭️  Index {idx_name} - already exists")
                else:
                    print(f"   ⚠️  Index {idx_name} - {e}")

        print("\n" + "=" * 70)
        print(f"✅ Migration complete! Added: {added}, Skipped: {skipped}")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ Migration failed: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    run_migration()
