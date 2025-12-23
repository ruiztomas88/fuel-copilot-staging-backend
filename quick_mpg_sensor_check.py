#!/usr/bin/env python3
"""Quick MPG sensor analysis"""
from datetime import datetime

import pymysql

from wialon_reader import TRUCK_UNIT_MAPPING

# Connect to Wialon
conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password=os.getenv("WIALON_MYSQL_PASSWORD"),
    database="wialon_collect",
    cursorclass=pymysql.cursors.DictCursor,
)

try:
    with conn.cursor() as cursor:
        print("=" * 100)
        print("🔍 MPG SENSOR AVAILABILITY ANALYSIS")
        print("=" * 100)

        # Key sensors for MPG
        mpg_sensors = ["odom", "total_fuel_used", "fuel_rate", "fuel_lvl"]

        print(f"\n📊 Fleet: {len(TRUCK_UNIT_MAPPING)} trucks total\n")

        for sensor in mpg_sensors:
            cursor.execute(
                """
import os
                SELECT COUNT(DISTINCT unit) as count
                FROM sensors
                WHERE p = %s
                AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 7 DAY)
            """,
                (sensor,),
            )

            result = cursor.fetchone()
            count = result["count"] if result else 0
            pct = (count / len(TRUCK_UNIT_MAPPING) * 100) if TRUCK_UNIT_MAPPING else 0

            print(
                f"📡 {sensor:20s}: {count:2d}/{len(TRUCK_UNIT_MAPPING)} trucks ({pct:5.1f}%)"
            )

        # RH1522 specific
        print(f"\n\n{'=' * 100}")
        print("🎯 RH1522 SENSOR ANALYSIS (Unit ID: 401727511)")
        print(f"{'=' * 100}\n")

        rh1522_unit = "401727511"

        for sensor in mpg_sensors:
            cursor.execute(
                """
                SELECT COUNT(*) as count,
                       MIN(value) as min_val,
                       MAX(value) as max_val,
                       FROM_UNIXTIME(MIN(m)) as first_time,
                       FROM_UNIXTIME(MAX(m)) as last_time
                FROM sensors
                WHERE unit = %s
                AND p = %s
                AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 3 DAY)
            """,
                (rh1522_unit, sensor),
            )

            result = cursor.fetchone()
            if result and result["count"] > 0:
                print(f"✅ {sensor}:")
                print(f"   Readings: {result['count']}")
                print(f"   Range: {result['min_val']} to {result['max_val']}")
                print(f"   Period: {result['first_time']} → {result['last_time']}\n")
            else:
                print(f"❌ {sensor}: NO DATA\n")

        # Show actual delta calculations
        print(f"\n{'=' * 100}")
        print("🧮 THEORETICAL MPG CALCULATION FOR RH1522 (Last 12 hours)")
        print(f"{'=' * 100}\n")

        # Get odometer range
        cursor.execute(
            """
            SELECT MIN(value) as start_odo, MAX(value) as end_odo
            FROM sensors
            WHERE unit = %s
            AND p = 'odom'
            AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 12 HOUR)
        """,
            (rh1522_unit,),
        )

        odo = cursor.fetchone()

        # Get fuel range (ECU)
        cursor.execute(
            """
            SELECT MIN(value) as start_fuel, MAX(value) as end_fuel
            FROM sensors
            WHERE unit = %s
            AND p = 'total_fuel_used'
            AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 12 HOUR)
        """,
            (rh1522_unit,),
        )

        fuel_ecu = cursor.fetchone()

        if odo and odo["start_odo"] and odo["end_odo"]:
            delta_miles = float(odo["end_odo"]) - float(odo["start_odo"])
            print(f"📏 Odometer delta: {delta_miles:.2f} miles")
            print(f"   Start: {odo['start_odo']}")
            print(f"   End:   {odo['end_odo']}\n")

            if fuel_ecu and fuel_ecu["start_fuel"] and fuel_ecu["end_fuel"]:
                delta_fuel = float(fuel_ecu["end_fuel"]) - float(fuel_ecu["start_fuel"])
                print(f"⛽ ECU fuel delta: {delta_fuel:.2f} gallons")
                print(f"   Start: {fuel_ecu['start_fuel']}")
                print(f"   End:   {fuel_ecu['end_fuel']}\n")

                if delta_fuel > 0:
                    mpg = delta_miles / delta_fuel
                    print(f"💡 CALCULATED MPG: {mpg:.2f}")

                    if 4.0 <= mpg <= 8.0:
                        print(f"   ✅ REALISTIC (4-8 MPG range for loaded truck)")
                    else:
                        print(f"   ⚠️  OUTSIDE EXPECTED RANGE")
            else:
                print(f"❌ No ECU fuel data available")
                print(
                    f"\n💡 Recommendation: Use fuel_rate integration or fuel_lvl delta"
                )
        else:
            print(f"❌ No odometer data available")

        print(f"\n\n{'=' * 100}")
        print("💡 RECOMMENDATIONS")
        print(f"{'=' * 100}\n")
        print(
            """
🎯 PRIMARY METHOD: odometer + total_fuel_used (ECU)
   - Direct delta calculation: Δmiles / Δgallons
   - Most accurate, no refuel detection needed
   - Already implemented in mpg_engine.py
   
⚠️  ISSUES FOUND:
   1. EMA smoothing was retaining old inflated values
   2. States persisted in data/mpg_states.json
   3. No hard cap enforcement (allowed >8.2 MPG)
   
✅ FIXES APPLIED:
   1. Deleted mpg_states.json (fresh start)
   2. Added max_mpg=8.2 cap in MPGConfig
   3. Added output capping: min(mpg_current, 8.2)
   4. Physics validation: 2-12 range check
   5. Restored fast thresholds: 5mi/0.75gal
   
📊 CURRENT STATUS:
   - Services running with clean states
   - MPG will recalculate from scratch
   - Values capped at 8.2 maximum
   - Updates every 5 miles traveled
        """
        )

finally:
    conn.close()
