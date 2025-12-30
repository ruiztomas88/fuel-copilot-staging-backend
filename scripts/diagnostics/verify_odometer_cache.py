"""
Verify odometer in truck_sensors_cache for CO0681
"""
import os

import time

import mysql.connector

# Wait for new sync cycle
print("⏳ Waiting 20 seconds for new sync cycle...")
time.sleep(20)

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password=os.getenv("DB_PASSWORD"),
    database="fuel_copilot",
)

cursor = conn.cursor(dictionary=True)

print("\n" + "=" * 70)
print("✅ CHECKING ODOMETER IN truck_sensors_cache")
print("=" * 70)

# Check CO0681
query = """
    SELECT truck_id, odometer_mi, speed_mph, engine_hours, timestamp
    FROM truck_sensors_cache
    WHERE truck_id = 'CO0681'
"""

cursor.execute(query)
row = cursor.fetchone()

if row:
    print(f"\n🚛 CO0681:")
    print(f"  Odometer: {row['odometer_mi']} mi")
    print(f"  Engine Hours: {row['engine_hours']} hr")
    print(f"  Speed: {row['speed_mph']} mph")
    print(f"  Last Update: {row['timestamp']}")

    if row["odometer_mi"] and row["odometer_mi"] > 0:
        print(f"\n✅ ODOMETER FIXED! Value: {row['odometer_mi']:.1f} mi")
        print(f"   Beyond shows: 48434 mi")
        print(
            f"   Match: {'✅ YES' if abs(row['odometer_mi'] - 48434) < 100 else '⚠️ Different'}"
        )
    else:
        print(f"\n⚠️  Odometer still NULL or 0")
else:
    print("❌ No data found for CO0681 in truck_sensors_cache")

# Check all trucks odometer status
print("\n" + "=" * 70)
print("📊 ODOMETER STATUS FOR ALL TRUCKS:")
print("=" * 70)

query2 = """
    SELECT truck_id, odometer_mi, timestamp
    FROM truck_sensors_cache
    ORDER BY timestamp DESC
    LIMIT 15
"""

cursor.execute(query2)
rows = cursor.fetchall()

null_count = 0
ok_count = 0

for row in rows:
    if row["odometer_mi"] and row["odometer_mi"] > 0:
        print(f"  ✅ {row['truck_id']:10s}: {row['odometer_mi']:10.1f} mi")
        ok_count += 1
    else:
        print(f"  ❌ {row['truck_id']:10s}: NULL/0")
        null_count += 1

print(f"\nSummary: {ok_count} trucks with odometer, {null_count} without")

cursor.close()
conn.close()

print("\n" + "=" * 70)
