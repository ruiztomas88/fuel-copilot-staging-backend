"""
Migration Script v2.0 - Add missing columns for improved sync
Run this on the VM to ensure fuel_metrics table has all required columns

Usage:
    python migrate_v2.py
"""

import os
import pymysql

# Database configuration
DB_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": "fuel_admin",
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": "fuel_copilot",
    "autocommit": True,
}


def migrate():
    """Add missing columns to fuel_metrics table"""
    conn = pymysql.connect(**DB_CONFIG)

    # Columns to add with their definitions
    columns_to_add = [
        (
            "idle_mode",
            "VARCHAR(20) DEFAULT NULL COMMENT 'Idle mode type: NORMAL, HIGH, etc'",
        ),
        ("data_age_min", "FLOAT DEFAULT NULL COMMENT 'Age of data in minutes'"),
    ]

    try:
        with conn.cursor() as cursor:
            # Check existing columns
            cursor.execute("DESCRIBE fuel_metrics")
            existing_columns = {row[0] for row in cursor.fetchall()}
            print(f"📋 Existing columns: {len(existing_columns)}")

            # Add missing columns
            for col_name, col_def in columns_to_add:
                if col_name not in existing_columns:
                    sql = f"ALTER TABLE fuel_metrics ADD COLUMN {col_name} {col_def}"
                    print(f"➕ Adding column: {col_name}")
                    cursor.execute(sql)
                    print(f"   ✅ Added: {col_name}")
                else:
                    print(f"   ℹ️ Already exists: {col_name}")

            # Update anchor_type default value if it has the old enum format
            try:
                cursor.execute(
                    """
                    UPDATE fuel_metrics 
                    SET anchor_type = 'NONE' 
                    WHERE anchor_type = 'AnchorType.NONE'
                """
                )
                print(f"   🔧 Fixed {cursor.rowcount} rows with old anchor_type format")
            except Exception as e:
                print(f"   ⚠️ Could not fix anchor_type: {e}")

            print("\n✅ Migration v2.0 completed successfully!")

    except Exception as e:
        print(f"❌ Migration failed: {e}")
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    print("🔧 Running Migration v2.0...")
    print("=" * 50)
    migrate()
