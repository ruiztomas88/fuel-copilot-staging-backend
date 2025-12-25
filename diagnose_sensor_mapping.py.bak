#!/usr/bin/env python3
"""
🔍 DIAGNOSTIC: Sensor Mapping Issues
=============================================

This script diagnoses why trucks show N/A for most sensors by:
1. Checking what sensors are ACTUALLY in Wialon DB
2. Comparing with SENSOR_PARAMS mapping in wialon_reader.py
3. Identifying missing/misnamed sensors

Run this to fix sensor mapping issues.
"""
from collections import defaultdict
from datetime import datetime, timedelta

import pymysql

# Wialon DB config
WIALON_DB = {
    "host": "remotemysql.com",
    "port": 3306,
    "user": "hKmaDjYB0j",
    "password": "FuelCopilot2025!",
    "database": "hKmaDjYB0j",
}

# Our expected sensors from wialon_reader.py SENSOR_PARAMS
EXPECTED_SENSORS = {
    "fuel_lvl",
    "speed",
    "rpm",
    "odom",
    "fuel_rate",
    "cool_temp",
    "hdop",
    "altitude",
    "obd_speed",
    "engine_hours",
    "pwr_ext",
    "oil_press",
    "total_fuel_used",
    "total_idle_fuel",
    "engine_load",
    "air_temp",
    "oil_temp",
    "def_level",
    "intk_t",  # Truncated names
    "dtc",
    "j1939_spn",
    "j1939_fmi",
    "idle_hours",
    "sats",
    "pwr_int",
    "course",
    "fuel_economy",
    "gear",
    "barometer",
    "fuel_t",
    "intrclr_t",
    "turbo_temp",
    "trans_temp",  # Truncated names
    "intake_pressure",
    "pto_hours",
    "brake_app_press",
    "brake_primary_press",
    "brake_secondary_press",
    "brake_switch",
    "parking_brake",
    "abs_status",
    "rpm_hi_res",
    "seatbelt",
    "vin",
    "harsh_accel",
    "harsh_brake",
    "harsh_corner",
    "rssi",
    "cool_lvl",
    "oil_level",
    "gps_locked",
    "battery",
    "roaming",
    "event_id",
    "bus",
    "mode",
}


def diagnose_sensors():
    """Check what sensors are actually available vs expected"""

    print("=" * 80)
    print("🔍 SENSOR MAPPING DIAGNOSTIC")
    print("=" * 80)

    try:
        conn = pymysql.connect(**WIALON_DB)
        cursor = conn.cursor()

        # Get recent data (last 24 hours)
        cutoff = datetime.now() - timedelta(hours=24)
        cutoff_epoch = int(cutoff.timestamp())

        print(f"\n📊 Analyzing sensors from last 24 hours (since {cutoff})...")

        # Query to find all unique sensor names in use
        query = """
        SELECT DISTINCT p 
        FROM sensors 
        WHERE t > %s 
        AND p IS NOT NULL 
        AND p != ''
        ORDER BY p
        """

        cursor.execute(query, (cutoff_epoch,))
        actual_sensors = {row[0] for row in cursor.fetchall()}

        print(f"\n✅ Found {len(actual_sensors)} unique sensors in Wialon DB\n")

        # Analysis
        print("=" * 80)
        print("📋 SENSOR ANALYSIS")
        print("=" * 80)

        # 1. Sensors we expect but DON'T have
        missing = EXPECTED_SENSORS - actual_sensors
        if missing:
            print(
                f"\n❌ MISSING SENSORS ({len(missing)}) - Expected but NOT in Wialon:"
            )
            for sensor in sorted(missing):
                print(f"   - {sensor}")

        # 2. Sensors we HAVE but DON'T expect
        unknown = actual_sensors - EXPECTED_SENSORS
        if unknown:
            print(f"\n⚠️  UNMAPPED SENSORS ({len(unknown)}) - In Wialon but NOT mapped:")
            for sensor in sorted(unknown):
                print(f"   - {sensor}")

        # 3. Sensors we have AND expect (GOOD!)
        matched = actual_sensors & EXPECTED_SENSORS
        if matched:
            print(f"\n✅ MAPPED SENSORS ({len(matched)}) - Working correctly:")
            for sensor in sorted(matched):
                print(f"   - {sensor}")

        # 4. Check specific critical sensors
        print("\n" + "=" * 80)
        print("🔥 CRITICAL SENSOR CHECK")
        print("=" * 80)

        critical_sensors = {
            "fuel_lvl": "Fuel Level %",
            "fuel_rate": "Fuel Rate (GPH)",
            "speed": "Speed (MPH)",
            "rpm": "Engine RPM",
            "engine_hours": "Engine Hours",
            "total_fuel_used": "Total Fuel Used (ECU)",
            "cool_temp": "Coolant Temperature",
            "oil_press": "Oil Pressure",
        }

        print("\nStatus of critical sensors:")
        for sensor, description in critical_sensors.items():
            status = "✅ FOUND" if sensor in actual_sensors else "❌ MISSING"
            print(f"   {status:12} {sensor:20} → {description}")

        # 5. Sample data for a truck
        print("\n" + "=" * 80)
        print("📦 SAMPLE DATA (First Truck)")
        print("=" * 80)

        sample_query = """
        SELECT DISTINCT u, p, v 
        FROM sensors 
        WHERE t > %s 
        AND p IS NOT NULL
        LIMIT 50
        """

        cursor.execute(sample_query, (cutoff_epoch,))
        rows = cursor.fetchall()

        if rows:
            current_truck = None
            for unit_id, param, value in rows[:20]:
                if unit_id != current_truck:
                    print(f"\n🚛 Unit ID: {unit_id}")
                    current_truck = unit_id

                mapped = "✅" if param in EXPECTED_SENSORS else "⚠️"
                print(f"   {mapped} {param:25} = {value}")

        # 6. Recommendations
        print("\n" + "=" * 80)
        print("💡 RECOMMENDATIONS")
        print("=" * 80)

        if missing:
            print(
                "\n1. Update wialon_reader.py SENSOR_PARAMS to remove missing sensors"
            )
            print("   These sensors were expected but aren't in Wialon:")
            for sensor in sorted(missing)[:5]:
                print(f"   - Remove or comment out: '{sensor}'")

        if unknown:
            print("\n2. Add unmapped sensors to wialon_reader.py SENSOR_PARAMS")
            print("   These sensors exist in Wialon but aren't mapped:")
            for sensor in sorted(unknown)[:10]:
                print(f"   - Add: '{sensor}': '{sensor}'")

        print("\n3. Check sensor name variations:")
        print("   - Wialon may truncate long names (e.g., intake_air_temp → intk_t)")
        print("   - Check for underscores vs no underscores")
        print("   - Check for abbreviations (temp → t, level → lvl, etc.)")

        cursor.close()
        conn.close()

        print("\n" + "=" * 80)
        print("✅ DIAGNOSTIC COMPLETE")
        print("=" * 80)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    diagnose_sensors()
