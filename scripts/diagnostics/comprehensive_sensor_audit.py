"""
COMPREHENSIVE SENSOR AUDIT
1. Check all sensors available in Wialon for active trucks
2. Verify mapping in wialon_reader.py
3. Verify data is being saved in truck_sensors_cache
"""

import os
from collections import defaultdict

import pymysql
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    host=os.getenv("WIALON_DB_HOST"),
    port=int(os.getenv("WIALON_DB_PORT", "3306")),
    user=os.getenv("WIALON_DB_USER"),
    password=os.getenv("WIALON_DB_PASS"),
    database=os.getenv("WIALON_DB_NAME"),
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

cursor = conn.cursor()

# Get unit_ids from tanks.yaml trucks
test_units = [
    401956896,  # CO0681 (we know has odom)
    402055528,  # DO9693
    401961904,  # JR7099
    402033131,  # LC6799
    401849345,  # VD3579
]

print("\n" + "=" * 80)
print("🔍 COMPREHENSIVE SENSOR AUDIT - WIALON DATABASE")
print("=" * 80)

# Get ALL distinct parameters across these trucks in last 6 hours
cutoff = int(__import__("time").time()) - (6 * 3600)

query = """
    SELECT DISTINCT p as param_name
    FROM sensors
    WHERE unit IN (%s, %s, %s, %s, %s)
        AND m >= %s
    ORDER BY p
"""

cursor.execute(query, (*test_units, cutoff))
all_params = cursor.fetchall()

wialon_sensors = sorted([row["param_name"] for row in all_params])

print(f"\n📊 FOUND {len(wialon_sensors)} DISTINCT SENSORS IN WIALON (last 6 hours):")
print("-" * 80)

# Read the current mapping from wialon_reader.py
import sys

sys.path.insert(0, r"C:\Users\devteam\Proyectos\fuel-analytics-backend")
from wialon_reader import WialonConfig

mapped_sensors = set(WialonConfig.SENSOR_PARAMS.values())

# Categorize sensors
critical_sensors = []
mapped_ok = []
unmapped = []

for param in wialon_sensors:
    if param in mapped_sensors:
        mapped_ok.append(param)
    else:
        unmapped.append(param)
        # Check if it's a critical sensor
        if any(
            keyword in param.lower()
            for keyword in [
                "fuel",
                "odom",
                "speed",
                "rpm",
                "engine",
                "temp",
                "press",
                "oil",
            ]
        ):
            critical_sensors.append(param)

print("\n✅ MAPPED SENSORS ({} total):".format(len(mapped_ok)))
for i, sensor in enumerate(mapped_ok, 1):
    # Find our internal name
    internal = [k for k, v in WialonConfig.SENSOR_PARAMS.items() if v == sensor]
    print(f"  {i:3d}. {sensor:30s} → {internal[0] if internal else 'UNKNOWN'}")

if unmapped:
    print(f"\n⚠️  UNMAPPED SENSORS ({len(unmapped)} total):")
    for i, sensor in enumerate(unmapped, 1):
        marker = "🔥" if sensor in critical_sensors else "  "
        print(f"  {marker} {i:3d}. {sensor}")

# Now check sample values for key sensors
print("\n" + "=" * 80)
print("📋 SAMPLE VALUES FOR KEY SENSORS (CO0681 - unit 401956896):")
print("=" * 80)

key_sensors = [
    "odom",
    "speed",
    "rpm",
    "fuel_lvl",
    "fuel_rate",
    "total_fuel_used",
    "engine_hours",
    "cool_temp",
    "oil_press",
    "oil_temp",
    "def_level",
]

for sensor in key_sensors:
    query = """
        SELECT value, m as epoch_time
        FROM sensors
        WHERE unit = %s
            AND p = %s
            AND m >= %s
        ORDER BY m DESC
        LIMIT 1
    """
    cursor.execute(query, (401956896, sensor, cutoff))
    result = cursor.fetchone()

    if result:
        value = result["value"]
        age_min = (int(__import__("time").time()) - result["epoch_time"]) / 60
        print(f"  ✓ {sensor:20s}: {str(value):>15s} (age: {age_min:4.0f} min)")
    else:
        print(f"  ✗ {sensor:20s}: NOT FOUND")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("✅ AUDIT COMPLETE")
print("=" * 80)
