"""
Verify sensor fixes - check if previously NULL sensors now have data
"""
import os

import time

import mysql.connector

print("⏳ Waiting 30 seconds for new sync cycle with fixes...")
time.sleep(30)

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password=os.getenv("DB_PASSWORD"),
    database="fuel_copilot",
)

cursor = conn.cursor(dictionary=True)

print("\n" + "=" * 80)
print("✅ VERIFYING SENSOR FIXES FOR CO0681")
print("=" * 80)

query = """
    SELECT 
        truck_id,
        timestamp,
        -- Previously NULL sensors
        engine_hours,
        idle_hours,
        total_fuel_used_gal,
        total_idle_fuel_gal,
        fuel_temp_f,
        intercooler_temp_f,
        gear,
        altitude_ft,
        brake_active,
        intake_pressure_bar,
        -- Already working sensors (for reference)
        odometer_mi,
        speed_mph,
        rpm,
        fuel_level_pct,
        coolant_temp_f,
        oil_pressure_psi
    FROM truck_sensors_cache
    WHERE truck_id = 'CO0681'
"""

cursor.execute(query)
row = cursor.fetchone()

if row:
    print(f"\n🚛 CO0681 at {row['timestamp']}")
    print("-" * 80)

    # Check previously NULL sensors
    fixes = []
    still_null = []

    previously_null_sensors = {
        "engine_hours": row["engine_hours"],
        "idle_hours": row["idle_hours"],
        "total_fuel_used_gal": row["total_fuel_used_gal"],
        "total_idle_fuel_gal": row["total_idle_fuel_gal"],
        "fuel_temp_f": row["fuel_temp_f"],
        "intercooler_temp_f": row["intercooler_temp_f"],
        "gear": row["gear"],
        "altitude_ft": row["altitude_ft"],
        "brake_active": row["brake_active"],
        "intake_pressure_bar": row["intake_pressure_bar"],
    }

    print("\n📊 PREVIOUSLY NULL SENSORS:")
    for sensor, value in previously_null_sensors.items():
        if value is not None and value != 0:
            print(f"  ✅ {sensor:30s} = {value}")
            fixes.append(sensor)
        else:
            print(f"  ⚠️  {sensor:30s} = NULL/0")
            still_null.append(sensor)

    # Show working sensors for reference
    print("\n✅ ALREADY WORKING SENSORS (reference):")
    working = {
        "odometer_mi": row["odometer_mi"],
        "speed_mph": row["speed_mph"],
        "rpm": row["rpm"],
        "fuel_level_pct": row["fuel_level_pct"],
        "coolant_temp_f": row["coolant_temp_f"],
        "oil_pressure_psi": row["oil_pressure_psi"],
    }

    for sensor, value in working.items():
        if value is not None and value != 0:
            print(f"  ✅ {sensor:30s} = {value}")

    print("\n" + "=" * 80)
    print(f"📈 RESULTS:")
    print(f"  ✅ Fixed: {len(fixes)}/10 sensors")
    print(f"  ⚠️  Still NULL: {len(still_null)}/10 sensors")

    if fixes:
        print(f"\n✅ SUCCESSFULLY FIXED:")
        for sensor in fixes:
            print(f"  - {sensor}")

    if still_null:
        print(f"\n⚠️  STILL NULL (may not be available in Wialon for this truck):")
        for sensor in still_null:
            print(f"  - {sensor}")
else:
    print("❌ No data found for CO0681")

cursor.close()
conn.close()

print("\n" + "=" * 80)
