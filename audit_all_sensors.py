"""
COMPREHENSIVE SENSOR AUDIT
Verifies ALL Wialon sensor mappings and data storage
"""

import os
import time
from collections import defaultdict

import mysql.connector
import pymysql
from dotenv import load_dotenv

load_dotenv()

# Connect to Wialon
wialon_conn = pymysql.connect(
    host=os.getenv("WIALON_DB_HOST"),
    port=int(os.getenv("WIALON_DB_PORT", "3306")),
    user=os.getenv("WIALON_DB_USER"),
    password=os.getenv("WIALON_DB_PASS"),
    database=os.getenv("WIALON_DB_NAME"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

# Connect to local DB
local_conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password=os.getenv("DB_PASSWORD"),
    database="fuel_copilot",
)

print("\n" + "=" * 80)
print("🔍 COMPREHENSIVE SENSOR MAPPING AUDIT")
print("=" * 80)

# Sensor mapping from wialon_reader.py
SENSOR_MAPPING = {
    # Basic sensors
    "fuel_lvl": "fuel_lvl",
    "speed": "speed",
    "rpm": "rpm",
    "odometer": "odom",
    "fuel_rate": "fuel_rate",
    "coolant_temp": "cool_temp",
    "hdop": "hdop",
    "altitude": "altitude",
    "obd_speed": "obd_speed",
    "engine_hours": "engine_hours",
    "pwr_ext": "pwr_ext",
    "oil_press": "oil_press",
    # ECU sensors
    "total_fuel_used": "total_fuel_used",
    "total_idle_fuel": "total_idle_fuel",
    "engine_load": "engine_load",
    "ambient_temp": "air_temp",
    # Engine health
    "oil_temp": "oil_temp",
    "def_level": "def_level",
    "intake_air_temp": "intk_t",
    # DTC
    "dtc": "dtc",
    "j1939_spn": "j1939_spn",
    "j1939_fmi": "j1939_fmi",
    "idle_hours": "idle_hours",
    # GPS
    "sats": "sats",
    "pwr_int": "pwr_int",
    "course": "course",
    # MPG validation
    "fuel_economy": "fuel_economy",
    "gear": "gear",
    "barometer": "barometer",
    # Temperatures
    "fuel_temp": "fuel_t",
    "intercooler_temp": "intrclr_t",
    "turbo_temp": "turbo_temp",
    "trans_temp": "trans_temp",
    # Pressures
    "intake_press": "intake_pressure",
    "boost": "intake_pressure",
    # Counters
    "pto_hours": "pto_hours",
    # Brakes
    "brake_app_press": "brake_app_press",
    "brake_primary_press": "brake_primary_press",
    "brake_secondary_press": "brake_secondary_press",
    "brake_switch": "brake_switch",
    "parking_brake": "parking_brake",
    "abs_status": "abs_status",
    # High res
    "rpm_hi_res": "rpm_hi_res",
    # Misc
    "seatbelt": "seatbelt",
    "vin": "vin",
    # Events
    "harsh_accel": "harsh_accel",
    "harsh_brake": "harsh_brake",
    "harsh_corner": "harsh_corner",
    # Additional
    "rssi": "rssi",
    "coolant_level": "cool_lvl",
    "oil_level": "oil_level",
    "gps_locked": "gps_locked",
    "battery": "battery",
    "roaming": "roaming",
    "event_id": "event_id",
    "bus": "bus",
    "mode": "mode",
}

# Use CO0681 as test truck (we know it has data)
test_unit_id = 401956896  # CO0681
test_truck = "CO0681"

print(f"\n📊 TEST TRUCK: {test_truck} (unit_id: {test_unit_id})")
print("=" * 80)

# Get all parameters from Wialon for this truck (last 4 hours)
cutoff = int(time.time()) - (4 * 3600)

wialon_cursor = wialon_conn.cursor()
query = """
    SELECT DISTINCT p as param_name
    FROM sensors
    WHERE unit = %s
        AND m >= %s
    ORDER BY p
"""
wialon_cursor.execute(query, (test_unit_id, cutoff))
wialon_params = {row["param_name"] for row in wialon_cursor.fetchall()}

print(f"\n✅ Wialon has {len(wialon_params)} parameters for {test_truck}")

# Check mapping status
print("\n" + "=" * 80)
print("🔍 SENSOR MAPPING VALIDATION")
print("=" * 80)

mapped_found = []
mapped_missing = []
unmapped_sensors = []

for our_name, wialon_name in SENSOR_MAPPING.items():
    if wialon_name in wialon_params:
        mapped_found.append((our_name, wialon_name))
    else:
        mapped_missing.append((our_name, wialon_name))

# Find unmapped sensors in Wialon
mapped_wialon_names = set(SENSOR_MAPPING.values())
for param in wialon_params:
    if param not in mapped_wialon_names:
        unmapped_sensors.append(param)

print(f"\n✅ MAPPED & FOUND ({len(mapped_found)}):")
print("-" * 80)
for our_name, wialon_name in sorted(mapped_found):
    # Get current value
    val_query = """
        SELECT value
        FROM sensors
        WHERE unit = %s AND p = %s AND m >= %s
        ORDER BY m DESC
        LIMIT 1
    """
    wialon_cursor.execute(val_query, (test_unit_id, wialon_name, cutoff))
    result = wialon_cursor.fetchone()
    value = result["value"] if result else "N/A"
    print(f"  ✅ {our_name:25s} <- {wialon_name:25s} = {str(value)[:20]}")

print(f"\n⚠️  MAPPED BUT NOT FOUND IN WIALON ({len(mapped_missing)}):")
print("-" * 80)
for our_name, wialon_name in sorted(mapped_missing):
    print(f"  ⚠️  {our_name:25s} <- {wialon_name:25s} (NOT IN WIALON)")

print(f"\n🔍 UNMAPPED SENSORS IN WIALON ({len(unmapped_sensors)}):")
print("-" * 80)
for param in sorted(unmapped_sensors):
    # Get sample value
    val_query = """
        SELECT value
        FROM sensors
        WHERE unit = %s AND p = %s AND m >= %s
        ORDER BY m DESC
        LIMIT 1
    """
    wialon_cursor.execute(val_query, (test_unit_id, param, cutoff))
    result = wialon_cursor.fetchone()
    value = result["value"] if result else "N/A"
    print(f"  🆕 {param:30s} = {str(value)[:30]}")

# Now check truck_sensors_cache to see what's being saved
print("\n" + "=" * 80)
print("💾 DATABASE STORAGE VALIDATION (truck_sensors_cache)")
print("=" * 80)

local_cursor = local_conn.cursor(dictionary=True)

# Get column mapping from truck_sensors_cache
local_cursor.execute("DESCRIBE truck_sensors_cache")
db_columns = {row["Field"] for row in local_cursor.fetchall()}

# Get current data for CO0681
local_cursor.execute(
    """
    SELECT * FROM truck_sensors_cache WHERE truck_id = %s
""",
    (test_truck,),
)
current_data = local_cursor.fetchone()

if not current_data:
    print(f"\n❌ NO DATA FOUND IN truck_sensors_cache for {test_truck}")
else:
    print(f"\n✅ Found data for {test_truck} at {current_data['timestamp']}")

    # Map our sensor names to DB column names
    SENSOR_TO_DB_COLUMN = {
        "oil_press": "oil_pressure_psi",
        "oil_temp": "oil_temp_f",
        "oil_level": "oil_level_pct",
        "def_level": "def_level_pct",
        "engine_load": "engine_load_pct",
        "rpm": "rpm",
        "coolant_temp": "coolant_temp_f",
        "coolant_level": "coolant_level_pct",
        "gear": "gear",
        "brake_switch": "brake_active",
        "intake_press": "intake_pressure_bar",
        "intake_air_temp": "intake_temp_f",
        "intercooler_temp": "intercooler_temp_f",
        "fuel_temp": "fuel_temp_f",
        "fuel_lvl": "fuel_level_pct",
        "fuel_rate": "fuel_rate_gph",
        "ambient_temp": "ambient_temp_f",
        "barometer": "barometric_pressure_inhg",
        "pwr_ext": "voltage",
        "pwr_int": "backup_voltage",
        "engine_hours": "engine_hours",
        "idle_hours": "idle_hours",
        "pto_hours": "pto_hours",
        "total_idle_fuel": "total_idle_fuel_gal",
        "total_fuel_used": "total_fuel_used_gal",
        "dtc": "dtc_count",
        "speed": "speed_mph",
        "altitude": "altitude_ft",
        "odometer": "odometer_mi",
        "course": "heading_deg",
        "trans_temp": "transmission_temp_f",
    }

    print(f"\n📊 STORAGE STATUS:")
    print("-" * 80)

    stored_count = 0
    null_count = 0
    not_in_db_count = 0

    for our_name, wialon_name in sorted(mapped_found):
        db_col = SENSOR_TO_DB_COLUMN.get(our_name)

        if db_col and db_col in db_columns:
            value = current_data.get(db_col)
            if value is not None and value != 0:
                print(f"  ✅ {our_name:25s} -> {db_col:30s} = {str(value)[:20]}")
                stored_count += 1
            else:
                print(f"  ⚠️  {our_name:25s} -> {db_col:30s} = NULL/0")
                null_count += 1
        elif db_col:
            print(f"  ❌ {our_name:25s} -> {db_col:30s} (COLUMN NOT IN DB)")
            not_in_db_count += 1
        else:
            print(f"  ❓ {our_name:25s} -> (NO DB MAPPING DEFINED)")
            not_in_db_count += 1

    print(f"\n📈 SUMMARY:")
    print(f"  ✅ Stored with data: {stored_count}")
    print(f"  ⚠️  Stored but NULL/0: {null_count}")
    print(f"  ❌ Not in database: {not_in_db_count}")

# Test multiple trucks to see sensor availability
print("\n" + "=" * 80)
print("🚛 SENSOR AVAILABILITY ACROSS FLEET")
print("=" * 80)

test_trucks = [
    ("CO0681", 401956896),
    ("DO9693", 402055528),
    ("VD3579", 401849345),
    ("JR7099", 401961904),
    ("RA9250", 402023717),
]

sensor_availability = defaultdict(int)

for truck_id, unit_id in test_trucks:
    query = """
        SELECT DISTINCT p as param_name
        FROM sensors
        WHERE unit = %s AND m >= %s
    """
    wialon_cursor.execute(query, (unit_id, cutoff))
    params = {row["param_name"] for row in wialon_cursor.fetchall()}

    for wialon_name in SENSOR_MAPPING.values():
        if wialon_name in params:
            sensor_availability[wialon_name] += 1

print(f"\nSensor availability (out of {len(test_trucks)} trucks):")
print("-" * 80)

for wialon_name in sorted(
    sensor_availability.keys(), key=lambda x: -sensor_availability[x]
):
    our_names = [k for k, v in SENSOR_MAPPING.items() if v == wialon_name]
    count = sensor_availability[wialon_name]
    pct = (count / len(test_trucks)) * 100
    status = "✅" if count == len(test_trucks) else "⚠️" if count >= 3 else "❌"
    print(
        f"  {status} {wialon_name:25s} ({', '.join(our_names)[:30]:30s}): {count}/{len(test_trucks)} ({pct:.0f}%)"
    )

wialon_cursor.close()
wialon_conn.close()
local_cursor.close()
local_conn.close()

print("\n" + "=" * 80)
print("✅ AUDIT COMPLETE")
print("=" * 80)
