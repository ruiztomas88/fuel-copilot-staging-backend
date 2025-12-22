"""
Check odometer sensor name using VD3579 (unit_id: 401849345)
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

unit_id = 401849345  # VD3579

print(f"\n🔍 SEARCHING FOR ODOMETER SENSOR")
print(f"Truck: VD3579, Unit ID: {unit_id}")
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
    print("❌ No recent data for VD3579. Trying last 24 hours...")
    cutoff = int(__import__("time").time()) - (24 * 3600)
    cursor.execute(query, (unit_id, cutoff))
    all_params = cursor.fetchall()

print(f"\n📋 ALL PARAMETERS ({len(all_params)} found):")
print("-" * 70)
params_list = sorted([row["param_name"] for row in all_params])

# Look for any param with value > 10000 (likely odometer in miles or km)
print("\n🎯 PARAMETERS WITH VALUES > 10,000 (likely odometer):")
print("-" * 70)

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

            # Highlight likely odometer (> 10000)
            if value > 10000:
                print(f"  ⭐ {param:30s} = {value:15.1f} (age: {age_min:4.0f}min)")
        except:
            pass

print("\n📋 ALL PARAMETERS WITH CURRENT VALUES:")
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
        print(f"  {i:3d}. {param:30s} = {str(value):15s} (age: {age_min:4.0f}min)")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("✅ SEARCH COMPLETE")
