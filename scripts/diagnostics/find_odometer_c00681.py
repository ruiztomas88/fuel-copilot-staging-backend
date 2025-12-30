"""
Find odometer sensor for C00681 in Wialon
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

# First, get C00681's unit_id from units_map table
print("\n🔍 SEARCHING FOR C00681 UNIT ID IN units_map")
print("=" * 70)

query = """
    SELECT beyondId, unit
    FROM units_map
    WHERE beyondId LIKE '%00681%'
"""
cursor.execute(query)
result = cursor.fetchone()

if result:
    unit_id = result["unit"]
    print(f"✅ Found C00681: unit_id = {unit_id}, beyondId = {result['beyondId']}")
else:
    print("❌ C00681 not found in units_map")
    cursor.close()
    conn.close()
    exit(1)

print(f"\n📊 ANALYZING UNIT {unit_id} - C00681")
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

print(f"\n📋 ALL PARAMETERS (last 4 hours):")
print("-" * 70)
params_list = sorted([row["param_name"] for row in all_params])

for i, param in enumerate(params_list, 1):
    # Get latest value
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

        # Highlight if value is close to 48434 (the odometer value in Beyond)
        highlight = ""
        if value is not None:
            try:
                val_float = float(value)
                if 48000 <= val_float <= 49000:  # Close to 48434
                    highlight = " ⭐ POSSIBLE ODOMETER"
                elif 77900 <= val_float <= 78000:  # In km (48434 mi ≈ 77950 km)
                    highlight = " ⭐ POSSIBLE ODOMETER (km)"
            except:
                pass

        print(
            f"  {i:3d}. {param:30s} = {str(value):15s} (age: {age_min:4.0f}min){highlight}"
        )
    else:
        print(f"  {i:3d}. {param:30s} = (no recent data)")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("✅ SEARCH COMPLETE")
print("\n💡 Look for parameters with values near 48434 (miles) or 77950 (km)")
