#!/usr/bin/env python3
"""
Debug script to investigate why DO9693 shows N/A in our dashboard
but Beyond shows all sensor data correctly.

This will check:
1. Data in truck_sensors table (our processed data)
2. Data in Wialon sensors table (raw data)
3. What wialon_sync is writing
"""
import os
from datetime import datetime, timedelta

import pymysql

# Our local DB
LOCAL_DB = {
    "host": "localhost",
    "port": 3306,
    "user": "fuel_admin",
    "password": os.getenv("MYSQL_PASSWORD", ""),
    "database": "fuel_copilot",
}

# Wialon DB (source)
WIALON_DB = {
    "host": "20.127.200.135",
    "port": 3306,
    "user": "tomas",
    "password": "Tomas2025",
    "database": "wialon_collect",
}


def check_our_truck_sensors():
    """Check what we have in truck_sensors for DO9693"""
    print("\n" + "=" * 80)
    print("1️⃣ CHECKING OUR truck_sensors TABLE FOR DO9693")
    print("=" * 80)

    try:
        conn = pymysql.connect(**LOCAL_DB)
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("SHOW TABLES LIKE 'truck_sensors'")
        if not cursor.fetchone():
            print("❌ Table truck_sensors DOES NOT EXIST!")
            cursor.close()
            conn.close()
            return False

        # Check latest data for DO9693
        cursor.execute(
            """
            SELECT 
                timestamp,
                TIMESTAMPDIFF(SECOND, timestamp, NOW()) as age_seconds,
                oil_pressure_psi,
                coolant_temp_f,
                rpm,
                engine_hours,
                idle_hours,
                def_level_pct
            FROM truck_sensors
            WHERE truck_id = 'DO9693'
            ORDER BY timestamp DESC
            LIMIT 5
        """
        )

        rows = cursor.fetchall()

        if not rows:
            print("❌ NO DATA for DO9693 in truck_sensors!")
            print("\n🔍 Let's check if ANY truck has data:")
            cursor.execute(
                """
                SELECT truck_id, MAX(timestamp) as latest
                FROM truck_sensors
                GROUP BY truck_id
                ORDER BY latest DESC
                LIMIT 10
            """
            )
            any_data = cursor.fetchall()
            if any_data:
                print("✅ Found data for other trucks:")
                for truck_id, ts in any_data:
                    print(f"   {truck_id}: {ts}")
            else:
                print("❌ truck_sensors table is EMPTY!")
        else:
            print(f"✅ Found {len(rows)} records for DO9693:")
            for i, row in enumerate(rows, 1):
                print(f"\n   Record {i}:")
                print(f"   Timestamp: {row[0]}")
                print(f"   Age: {row[1]} seconds ago")
                print(f"   Oil Pressure: {row[2]} psi")
                print(f"   Coolant: {row[3]}°F")
                print(f"   RPM: {row[4]}")
                print(f"   Engine Hours: {row[5]}")
                print(f"   Idle Hours: {row[6]}")
                print(f"   DEF Level: {row[7]}%")

        cursor.close()
        conn.close()
        return len(rows) > 0

    except Exception as e:
        print(f"❌ ERROR checking truck_sensors: {e}")
        return False


def check_wialon_raw_data():
    """Check Wialon sensors table directly (what Beyond reads)"""
    print("\n" + "=" * 80)
    print("2️⃣ CHECKING WIALON sensors TABLE (RAW DATA)")
    print("=" * 80)

    try:
        conn = pymysql.connect(**WIALON_DB)
        cursor = conn.cursor()

        # First, find DO9693's unit_id
        print("\n🔍 Finding unit_id for DO9693...")
        cursor.execute(
            """
            SELECT DISTINCT u
            FROM sensors
            WHERE t > UNIX_TIMESTAMP(NOW() - INTERVAL 1 HOUR)
            ORDER BY t DESC
            LIMIT 20
        """
        )
        unit_ids = cursor.fetchall()
        print(f"   Found {len(unit_ids)} active units in last hour:")
        for uid in unit_ids[:10]:
            print(f"   - Unit ID: {uid[0]}")

        # Check for DO9693 specifically (unit_id might be in tanks.yaml)
        # Let's check recent data for any unit
        print("\n🔍 Checking recent sensor data...")
        cursor.execute(
            """
            SELECT u, p, v, FROM_UNIXTIME(t) as timestamp
            FROM sensors
            WHERE t > UNIX_TIMESTAMP(NOW() - INTERVAL 5 MINUTE)
            AND p IN ('oil_press', 'cool_temp', 'rpm', 'engine_hours', 'def_level', 'fuel_lvl')
            ORDER BY t DESC
            LIMIT 50
        """
        )

        recent_data = cursor.fetchall()
        if recent_data:
            print(f"✅ Found {len(recent_data)} recent sensor readings:")
            current_unit = None
            for unit, param, value, ts in recent_data[:20]:
                if unit != current_unit:
                    print(f"\n   Unit {unit}:")
                    current_unit = unit
                print(f"      {param}: {value} ({ts})")
        else:
            print("❌ NO recent data in Wialon sensors!")

        # Now check specifically for oil_press, cool_temp for all units
        print("\n🔍 Checking what sensors are available...")
        cursor.execute(
            """
            SELECT DISTINCT p
            FROM sensors
            WHERE t > UNIX_TIMESTAMP(NOW() - INTERVAL 1 HOUR)
            ORDER BY p
        """
        )
        sensors = cursor.fetchall()
        print(f"✅ Available sensors ({len(sensors)}):")
        for sensor in sensors:
            print(f"   - {sensor[0]}")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        print(f"❌ ERROR checking Wialon: {e}")
        return False


def check_wialon_sync_mapping():
    """Check if wialon_sync is correctly mapping sensor names"""
    print("\n" + "=" * 80)
    print("3️⃣ CHECKING WIALON SENSOR NAME MAPPING")
    print("=" * 80)

    # Read wialon_reader.py to see mapping
    try:
        with open("wialon_reader.py", "r") as f:
            content = f.read()

        # Find SENSOR_PARAMS
        import re

        match = re.search(r"SENSOR_PARAMS\s*=\s*\{([^}]+)\}", content, re.DOTALL)
        if match:
            print("✅ Found SENSOR_PARAMS mapping:")
            params_str = match.group(1)
            # Extract key mappings
            mappings = re.findall(r'"(\w+)":\s*"(\w+)"', params_str)

            critical_sensors = [
                "oil_press",
                "oil_temp",
                "cool_temp",
                "rpm",
                "engine_hours",
                "idle_hours",
                "def_level",
                "fuel_lvl",
            ]

            print("\n   Critical sensor mappings:")
            for internal, wialon in mappings:
                if any(
                    sensor in internal or sensor in wialon
                    for sensor in critical_sensors
                ):
                    print(f"   ✓ {internal:20} → {wialon}")
        else:
            print("❌ Could not find SENSOR_PARAMS")

    except Exception as e:
        print(f"❌ ERROR: {e}")


def main():
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "DO9693 SENSOR DEBUG - Why N/A?" + " " * 25 + "║")
    print("╚" + "=" * 78 + "╝")

    has_local_data = check_our_truck_sensors()
    has_wialon_data = check_wialon_raw_data()
    check_wialon_sync_mapping()

    print("\n" + "=" * 80)
    print("📊 DIAGNOSIS")
    print("=" * 80)

    if not has_local_data and has_wialon_data:
        print("❌ PROBLEM: Wialon has data but truck_sensors is empty")
        print("   → wialon_sync_enhanced is NOT writing to truck_sensors")
        print("   → OR table doesn't exist")
        print("   → OR sensor name mapping is wrong")
    elif not has_local_data and not has_wialon_data:
        print("❌ PROBLEM: No data in Wialon at all")
        print("   → Check Wialon connection")
    elif has_local_data:
        print("✅ Data exists in truck_sensors")
        print("   → Problem is in API query or frontend")

    print("\n" + "=" * 80)
    print("💡 NEXT STEPS")
    print("=" * 80)
    print("1. If truck_sensors is empty: Check if wialon_sync is running")
    print("2. If sensor names don't match: Update SENSOR_PARAMS in wialon_reader.py")
    print(
        "3. If data exists but API doesn't return it: Fix query in get_fleet_summary()"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()
