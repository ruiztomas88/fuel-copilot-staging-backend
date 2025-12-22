"""
Find odometer sensor for CO0681 (unit_id: 401956896)
Beyond shows: Odometer: 48434 mi
"""

import os

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

unit_id = 401956896  # CO0681

print(f"\n🔍 SEARCHING FOR ODOMETER SENSOR")
print(f"Truck: CO0681, Unit ID: {unit_id}")
print(f"Beyond shows: Odometer = 48434 mi")
print("=" * 70)

# Get all parameters for this truck in last 4 hours
cutoff = int(__import__("time").time()) - (4 * 3600)

query = """
    SELECT DISTINCT p as param_name
    FROM sensors
    WHERE unit = %s
        AND m >= %s
    ORDER BY p
"""
cursor.execute(query, (unit_id, cutoff))
all_params = cursor.fetchall()

if not all_params:
    print("❌ No recent data in last 4h. Trying last 24 hours...")
    cutoff = int(__import__("time").time()) - (24 * 3600)
    cursor.execute(query, (unit_id, cutoff))
    all_params = cursor.fetchall()

params_list = sorted([row["param_name"] for row in all_params])

print(f"\n📊 DATA CHECK:")
check_query = """
    SELECT COUNT(*) as total, MAX(m) as newest
    FROM sensors
    WHERE unit = %s AND m >= %s
"""
cursor.execute(check_query, (unit_id, cutoff))
check = cursor.fetchone()
if check["total"] > 0:
    newest_age_min = (int(__import__("time").time()) - check["newest"]) / 60
    print(f"  Total records: {check['total']}")
    print(f"  Newest record: {newest_age_min:.1f} minutes ago")

print(f"\n🎯 SEARCHING FOR ODOMETER (value ≈ 48434 mi or 77950 km):")
print("-" * 70)

odometer_candidates = []

for param in params_list:
    val_query = """
        SELECT value, m as epoch_time
        FROM sensors
        WHERE unit = %s
            AND p = %s
            AND m >= %s
        ORDER BY m DESC
        LIMIT 1
    """
    cursor.execute(val_query, (unit_id, param, cutoff))
    result = cursor.fetchone()

    if result and result["value"] is not None:
        try:
            value = float(result["value"])
            age_min = (int(__import__("time").time()) - result["epoch_time"]) / 60

            # Check if close to expected odometer value
            # 48434 mi or ~77950 km or engine hours ~16472
            is_candidate = False
            reason = ""

            if 45000 <= value <= 50000:  # Miles
                is_candidate = True
                reason = f"MILES (target: 48434)"
                odometer_candidates.append((param, value, "miles"))
            elif 75000 <= value <= 80000:  # Kilometers
                is_candidate = True
                reason = f"KILOMETERS (48434mi ≈ {48434*1.60934:.0f}km)"
                odometer_candidates.append((param, value, "km"))
            elif 15000 <= value <= 17000:  # Engine hours (16472 from Beyond)
                is_candidate = True
                reason = f"ENGINE HOURS (target: 16472)"
                odometer_candidates.append((param, value, "hours"))
            elif value > 10000:  # Any large number
                is_candidate = True
                reason = f"LARGE VALUE (> 10k)"

            if is_candidate:
                print(
                    f"  ⭐ {param:30s} = {value:15.1f} ({reason}) - age: {age_min:.0f}min"
                )
        except:
            pass

if odometer_candidates:
    print(f"\n✅ FOUND {len(odometer_candidates)} ODOMETER CANDIDATES:")
    for param, value, unit in odometer_candidates:
        print(f"   {param} = {value:.1f} {unit}")
else:
    print(f"\n❌ NO VALUES MATCHING EXPECTED ODOMETER RANGE")

print(f"\n📋 ALL PARAMETERS ({len(params_list)} total):")
print("-" * 70)

for i, param in enumerate(params_list, 1):
    val_query = """
        SELECT value, m as epoch_time
        FROM sensors
        WHERE unit = %s
            AND p = %s
            AND m >= %s
        ORDER BY m DESC
        LIMIT 1
    """
    cursor.execute(val_query, (unit_id, param, cutoff))
    result = cursor.fetchone()

    if result:
        value = result["value"]
        age_min = (int(__import__("time").time()) - result["epoch_time"]) / 60
        print(f"  {i:3d}. {param:30s} = {str(value):>15s} (age: {age_min:4.0f}min)")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("✅ SEARCH COMPLETE")
