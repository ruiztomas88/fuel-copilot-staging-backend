#!/usr/bin/env python3
"""
🔍 Wialon Sensor Availability Checker
Verifies which sensors from Pacific Track's list are actually available in Wialon DB

Run: python tools/check_wialon_sensors.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from datetime import datetime, timedelta
from collections import defaultdict

# Wialon DB connection (same as wialon_reader.py)
WIALON_CONFIG = {
    "host": os.getenv("WIALON_DB_HOST", "localhost"),
    "port": int(os.getenv("WIALON_DB_PORT", "3306")),
    "user": os.getenv("WIALON_DB_USER", ""),
    "password": os.getenv("WIALON_DB_PASS", ""),
    "database": os.getenv("WIALON_DB_NAME", "wialon_collect"),
}

# Sensors from Pacific Track PDF that we want to verify
PACIFIC_SENSORS = {
    # NIVEL 1: CRÍTICOS
    "oil_press": "Engine Oil Pressure",
    "cool_temp": "Coolant Temperature",
    "oil_temp": "Engine Oil Temperature",
    "coolant_lvl": "Coolant Level",
    "pwr_ext": "Battery Voltage",
    "battery_voltage": "Battery Voltage (alt)",
    # NIVEL 2: IMPORTANTES
    "def_lvl": "DEF Level",
    "def_level": "DEF Level (alt)",
    "oil_lvl": "Engine Oil Level",
    "oil_level": "Engine Oil Level (alt)",
    "air_temp": "Intake Air Temperature",
    "intake_temp": "Intake Air Temp (alt)",
    "fuel_rate": "Average Fuel Rate",
    "turbo_oil_press": "Turbo Oil Pressure",
    # NIVEL 3: MONITOREO
    "rpm": "RPM Engine",
    "engine_load": "Engine Load Percent",
    "fuel_temp": "Fuel Temperature",
    "intercooler_temp": "Intercooler Temperature",
    # Otros del PDF
    "engine_hours": "Engine Hours",
    "odom": "Vehicle Miles (Odometer)",
    "torque": "Torque Engine",
    "tire_press": "Tire Pressure",
    # Ya usamos estos
    "fuel_lvl": "Fuel Level",
    "speed": "GPS Speed",
}


def check_sensors():
    """Query Wialon DB to see which sensors have data"""

    print("=" * 70)
    print("🔍 WIALON SENSOR AVAILABILITY CHECK")
    print(f"   Checking database: {WIALON_CONFIG['host']}:{WIALON_CONFIG['port']}")
    print("=" * 70)

    try:
        conn = pymysql.connect(
            host=WIALON_CONFIG["host"],
            port=WIALON_CONFIG["port"],
            user=WIALON_CONFIG["user"],
            password=WIALON_CONFIG["password"],
            database=WIALON_CONFIG["database"],
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=30,
        )
        print("✅ Connected to Wialon database\n")

        with conn.cursor() as cursor:
            # 1. Get ALL unique parameter names in the sensors table
            print("📊 Step 1: Finding ALL available sensor parameters...")
            cursor.execute(
                """
                SELECT DISTINCT p as param_name, COUNT(*) as record_count
                FROM sensors
                WHERE m >= UNIX_TIMESTAMP(NOW() - INTERVAL 7 DAY)
                GROUP BY p
                ORDER BY record_count DESC
            """
            )
            all_params = cursor.fetchall()

            print(
                f"\n{'Parameter Name':<30} {'Records (7d)':<15} {'Pacific Match':<20}"
            )
            print("-" * 70)

            found_params = set()
            for row in all_params:
                param = row["param_name"]
                count = row["record_count"]
                found_params.add(param)

                # Check if it matches any Pacific sensor
                pacific_match = PACIFIC_SENSORS.get(param, "")
                if pacific_match:
                    print(f"✅ {param:<28} {count:<15,} {pacific_match}")
                else:
                    print(f"   {param:<28} {count:<15,}")

            # 2. Check which Pacific sensors are MISSING
            print("\n" + "=" * 70)
            print("❌ PACIFIC SENSORS NOT FOUND IN WIALON:")
            print("-" * 70)

            missing = []
            for param, description in PACIFIC_SENSORS.items():
                if param not in found_params:
                    missing.append((param, description))
                    print(f"   {param:<25} ({description})")

            if not missing:
                print("   ✅ All Pacific sensors found!")

            # 3. Sample values for critical sensors
            print("\n" + "=" * 70)
            print("📈 SAMPLE VALUES FOR CRITICAL SENSORS (last 24h):")
            print("-" * 70)

            critical_params = [
                "oil_press",
                "cool_temp",
                "pwr_ext",
                "engine_load",
                "def_lvl",
                "oil_temp",
            ]

            for param in critical_params:
                if param in found_params:
                    cursor.execute(
                        f"""
                        SELECT 
                            MIN(value) as min_val,
                            MAX(value) as max_val,
                            AVG(value) as avg_val,
                            COUNT(*) as count
                        FROM sensors
                        WHERE p = %s
                          AND m >= UNIX_TIMESTAMP(NOW() - INTERVAL 24 HOUR)
                          AND value IS NOT NULL
                          AND value > 0
                    """,
                        (param,),
                    )
                    stats = cursor.fetchone()

                    if stats and stats["count"] > 0:
                        print(
                            f"✅ {param:<15} Min: {stats['min_val']:<10.1f} Max: {stats['max_val']:<10.1f} Avg: {stats['avg_val']:<10.1f} Records: {stats['count']:,}"
                        )
                    else:
                        print(f"⚠️  {param:<15} Found but no valid data in 24h")
                else:
                    print(f"❌ {param:<15} NOT AVAILABLE")

            # 4. Check data per truck for a critical sensor
            print("\n" + "=" * 70)
            print("🚛 DATA BY TRUCK (coolant temp - last 24h):")
            print("-" * 70)

            cursor.execute(
                """
                SELECT 
                    unit,
                    COUNT(*) as records,
                    AVG(value) as avg_temp,
                    MAX(value) as max_temp
                FROM sensors
                WHERE p = 'cool_temp'
                  AND m >= UNIX_TIMESTAMP(NOW() - INTERVAL 24 HOUR)
                  AND value IS NOT NULL
                GROUP BY unit
                ORDER BY records DESC
                LIMIT 10
            """
            )

            truck_data = cursor.fetchall()
            for row in truck_data:
                print(
                    f"   Unit {row['unit']}: {row['records']:>5} records, Avg: {row['avg_temp']:.1f}°F, Max: {row['max_temp']:.1f}°F"
                )

        conn.close()

        # Summary
        print("\n" + "=" * 70)
        print("📋 SUMMARY:")
        print("-" * 70)
        print(f"   Total unique parameters in Wialon: {len(all_params)}")
        print(
            f"   Pacific sensors found: {len(PACIFIC_SENSORS) - len(missing)}/{len(PACIFIC_SENSORS)}"
        )
        print(f"   Pacific sensors missing: {len(missing)}")
        print("=" * 70)

        return found_params

    except Exception as e:
        print(f"❌ Error connecting to Wialon: {e}")
        print(f"   Check WIALON_DB_* environment variables")
        return set()


if __name__ == "__main__":
    check_sensors()
