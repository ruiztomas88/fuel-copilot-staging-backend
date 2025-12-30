"""
Check exact odometer sensor name in Wialon database
"""

import os
from collections import defaultdict

import pymysql
from dotenv import load_dotenv

load_dotenv()

# Connect to Wialon
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

# Get a sample truck unit ID (DO9693 from recent diagnostics)
# Try multiple trucks to find one with data
test_trucks = [
    ("DO9693", 401961878),
    ("RA9250", 401961879),
    ("JR7099", 401961880),
    ("LC6799", 401961883),
]

for truck_name, unit_id in test_trucks:
    # Check if truck has recent data
    check_query = """
        SELECT COUNT(*) as total
        FROM sensors
        WHERE unit = %s
            AND m >= %s
        LIMIT 1
    """
    cutoff = int(__import__("time").time()) - (2 * 3600)  # Last 2 hours
    cursor.execute(check_query, (unit_id, cutoff))
    result = cursor.fetchone()

    if result and result["total"] > 0:
        print(f"\n✅ Found active truck: {truck_name} (unit_id={unit_id})")
        print(f"   Records in last 2h: {result['total']}")
        break
else:
    print(f"\n❌ No active trucks found in last 2 hours!")
    cursor.close()
    conn.close()
    exit(1)

print(f"\n🔍 SEARCHING FOR ODOMETER SENSOR IN WIALON")
print(f"Truck Unit ID: {unit_id}")
print("=" * 70)

# Search for all parameter names that might be odometer
cutoff = int(__import__("time").time()) - (24 * 3600)  # Last 24 hours

# First, check if we have ANY data for this truck
check_query = """
    SELECT COUNT(*) as total, MIN(m) as oldest, MAX(m) as newest
    FROM sensors
    WHERE unit = %s
        AND m >= %s
"""
cursor.execute(check_query, (unit_id, cutoff))
check_result = cursor.fetchone()
print(f"\n📊 DATA CHECK:")
print(f"  Total records: {check_result['total']}")
if check_result["total"] > 0:
    oldest_age_h = (int(__import__("time").time()) - check_result["oldest"]) / 3600
    newest_age_min = (int(__import__("time").time()) - check_result["newest"]) / 60
    print(f"  Oldest record: {oldest_age_h:.1f} hours ago")
    print(f"  Newest record: {newest_age_min:.1f} minutes ago")

query = """
    SELECT DISTINCT p as param_name
    FROM sensors
    WHERE unit = %s
        AND m >= %s
    ORDER BY p
"""

cursor.execute(query, (unit_id, cutoff))
all_params = cursor.fetchall()

print(f"\n📋 ALL PARAMETERS FOR TRUCK {unit_id} (last 24h):")
print("-" * 70)
params_list = [row["param_name"] for row in all_params]
for i, param in enumerate(sorted(params_list), 1):
    print(f"  {i:3d}. {param}")

# Search for odometer-like names
print(f"\n🎯 SEARCHING FOR ODOMETER-LIKE PARAMETERS:")
print("-" * 70)

odometer_keywords = ["odom", "odo", "mile", "distance", "km"]
matches = []

for row in all_params:
    param = row["param_name"].lower()
    if any(keyword in param for keyword in odometer_keywords):
        matches.append(row["param_name"])

if matches:
    print(f"✅ FOUND {len(matches)} ODOMETER-LIKE PARAMETERS:")
    for match in matches:
        # Get a sample value
        sample_query = """
            SELECT value, m as epoch_time
            FROM sensors
            WHERE unit = %s
                AND p = %s
                AND m >= %s
            ORDER BY m DESC
            LIMIT 1
        """
        cursor.execute(sample_query, (unit_id, match, cutoff))
        sample = cursor.fetchone()

        if sample:
            value = sample["value"]
            age_min = (int(__import__("time").time()) - sample["epoch_time"]) / 60
            print(f"  ✓ {match}: {value} (age: {age_min:.0f} min)")
        else:
            print(f"  ✓ {match}: (no recent data)")
else:
    print("❌ NO ODOMETER-LIKE PARAMETERS FOUND")
    print("\n💡 Checking if Beyond shows odometer from a different source...")
    print("   (possibly calculated from GPS or another sensor)")

# Also check for total distance parameters
print(f"\n🔍 SEARCHING FOR DISTANCE/TOTAL PARAMETERS:")
print("-" * 70)

distance_keywords = ["dist", "total", "trip"]
dist_matches = []

for row in all_params:
    param = row["param_name"].lower()
    if any(keyword in param for keyword in distance_keywords):
        dist_matches.append(row["param_name"])

if dist_matches:
    print(f"✅ FOUND {len(dist_matches)} DISTANCE-LIKE PARAMETERS:")
    for match in dist_matches:
        # Get a sample value
        sample_query = """
            SELECT value, m as epoch_time
            FROM sensors
            WHERE unit = %s
                AND p = %s
                AND m >= %s
            ORDER BY m DESC
            LIMIT 1
        """
        cursor.execute(sample_query, (unit_id, match, cutoff))
        sample = cursor.fetchone()

        if sample:
            value = sample["value"]
            age_min = (int(__import__("time").time()) - sample["epoch_time"]) / 60
            print(f"  ✓ {match}: {value} (age: {age_min:.0f} min)")
        else:
            print(f"  ✓ {match}: (no recent data)")

cursor.close()
conn.close()

print("\n" + "=" * 70)
print("✅ ANALYSIS COMPLETE")
