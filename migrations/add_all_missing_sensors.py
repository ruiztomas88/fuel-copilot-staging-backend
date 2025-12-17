"""
Migration: Add ALL Missing Sensors to truck_sensors_cache
===========================================================
Adds all sensors that Wialon reports but are missing from cache table.

Critical Fix: Ensures EVERYTHING from Wialon reaches the dashboard.

Run with: python migrations/add_all_missing_sensors.py
"""

import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

MYSQL_CONFIG = {
    "host": "localhost",
    "port": 3306,
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD", "tomas"),
    "database": "fuel_copilot",
}


def add_missing_sensors():
    """Add all missing sensor columns to truck_sensors_cache"""
    conn = pymysql.connect(**MYSQL_CONFIG)
    cursor = conn.cursor()

    print("🔧 Adding missing sensor columns to truck_sensors_cache...")

    # List of all columns to add
    columns_to_add = [
        # CRÍTICO - mostrado en dashboard pero usa datos viejos
        ("odometer_mi", "DECIMAL(12,2)", "Odometer in miles"),
        # DEF System (emissions compliance)
        ("def_temp_f", "DECIMAL(10,2)", "DEF temperature F"),
        ("def_quality", "DECIMAL(10,2)", "DEF quality percentage"),
        # Engine Performance
        ("throttle_position_pct", "DECIMAL(10,2)", "Throttle position %"),
        ("turbo_pressure_psi", "DECIMAL(10,2)", "Turbo boost pressure PSI"),
        # Fuel System
        ("fuel_pressure_psi", "DECIMAL(10,2)", "Fuel rail pressure PSI"),
        # DPF (Diesel Particulate Filter) - Critical for emissions
        ("dpf_pressure_psi", "DECIMAL(10,2)", "DPF differential pressure"),
        ("dpf_soot_pct", "DECIMAL(10,2)", "DPF soot load %"),
        ("dpf_ash_pct", "DECIMAL(10,2)", "DPF ash load %"),
        ("dpf_status", "VARCHAR(20)", "DPF status"),
        # EGR (Exhaust Gas Recirculation)
        ("egr_position_pct", "DECIMAL(10,2)", "EGR valve position %"),
        ("egr_temp_f", "DECIMAL(10,2)", "EGR temperature F"),
        # Electrical
        ("alternator_status", "VARCHAR(20)", "Alternator status"),
        # Transmission
        ("transmission_temp_f", "DECIMAL(10,2)", "Transmission oil temp F"),
        ("transmission_pressure_psi", "DECIMAL(10,2)", "Transmission pressure PSI"),
        # GPS
        ("heading_deg", "DECIMAL(10,2)", "GPS heading in degrees"),
    ]

    added_count = 0
    skipped_count = 0

    for col_name, col_type, col_comment in columns_to_add:
        try:
            # Check if column already exists
            check_sql = """
                SELECT COUNT(*) 
                FROM information_schema.COLUMNS 
                WHERE TABLE_SCHEMA = DATABASE()
                AND TABLE_NAME = 'truck_sensors_cache'
                AND COLUMN_NAME = %s
            """
            cursor.execute(check_sql, (col_name,))
            exists = cursor.fetchone()[0] > 0

            if exists:
                print(f"  ⏭️  Skipped: {col_name} (already exists)")
                skipped_count += 1
            else:
                alter_sql = f"""
                    ALTER TABLE truck_sensors_cache 
                    ADD COLUMN {col_name} {col_type} 
                    COMMENT '{col_comment}'
                """
                cursor.execute(alter_sql)
                conn.commit()
                print(f"  ✅ Added: {col_name} ({col_type})")
                added_count += 1
        except Exception as e:
            if "Duplicate column" in str(e):
                print(f"  ⏭️  Skipped: {col_name} (already exists)")
                skipped_count += 1
            else:
                print(f"  ❌ Error adding {col_name}: {e}")

    print(f"\n📊 Summary:")
    print(f"   Added: {added_count} columns")
    print(f"   Skipped: {skipped_count} columns (already exist)")
    print(f"   Total: {added_count + skipped_count} columns processed")

    # Show current table structure
    print("\n📋 Current table structure:")
    cursor.execute("DESCRIBE truck_sensors_cache")
    columns = cursor.fetchall()
    print(f"   Total columns: {len(columns)}")

    # Show new columns
    new_cols = [col for col in columns if col[0] in [c[0] for c in columns_to_add]]
    if new_cols:
        print("\n🆕 Newly added columns:")
        for col in new_cols:
            print(f"   - {col[0]}: {col[1]}")

    cursor.close()
    conn.close()

    print("\n✅ Migration complete!")
    print("\n⚠️  NEXT STEPS:")
    print("   1. Update wialon_full_sync_service.py INSERT query to include new fields")
    print("   2. Update api_v2.py /trucks/{id}/sensors endpoint to return new fields")
    print("   3. Restart wialon_full_sync service in VM")
    print("   4. Verify in dashboard that N/A values are gone")


if __name__ == "__main__":
    add_missing_sensors()
