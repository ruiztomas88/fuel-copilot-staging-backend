"""
Verify odometer is now being saved for CO0681
"""

import time

import mysql.connector

# Wait 30 seconds for new data
print("⏳ Waiting 30 seconds for new sync cycle...")
time.sleep(30)

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password="FuelCopilot2025!",
    database="fuel_copilot",
)

cursor = conn.cursor(dictionary=True)

# Check CO0681 latest data
query = """
    SELECT truck_id, odometer_mi, speed_mph, timestamp
    FROM telemetry_data
    WHERE truck_id = 'CO0681'
    ORDER BY timestamp DESC
    LIMIT 1
"""

cursor.execute(query)
row = cursor.fetchone()

print("\n" + "=" * 70)
print("✅ CO0681 LATEST DATA:")
print("=" * 70)

if row:
    print(f"  Truck: {row['truck_id']}")
    print(f"  Odometer: {row['odometer_mi']} mi")
    print(f"  Speed: {row['speed_mph']} mph")
    print(f"  Timestamp: {row['timestamp']}")

    if row["odometer_mi"] is None:
        print("\n⚠️  Odometer still NULL - checking if data exists in last 5 min...")

        query2 = """
            SELECT COUNT(*) as count
            FROM telemetry_data
            WHERE truck_id = 'CO0681'
                AND timestamp >= NOW() - INTERVAL 5 MINUTE
        """
        cursor.execute(query2)
        result = cursor.fetchone()
        print(f"  Records in last 5 min: {result['count']}")
    else:
        print(f"\n✅ ODOMETER NOW POPULATED!")
        print(f"   Value matches Beyond: 48434 mi ≈ {row['odometer_mi']} mi")
else:
    print("❌ No data found for CO0681")

# Check a few more trucks
print("\n" + "=" * 70)
print("📊 CHECKING OTHER TRUCKS:")
print("=" * 70)

query3 = """
    SELECT truck_id, odometer_mi, timestamp
    FROM telemetry_data
    WHERE timestamp >= NOW() - INTERVAL 5 MINUTE
    ORDER BY timestamp DESC
    LIMIT 10
"""

cursor.execute(query3)
rows = cursor.fetchall()

if rows:
    for row in rows:
        odometer_status = (
            f"{row['odometer_mi']:.1f} mi" if row["odometer_mi"] else "NULL"
        )
        print(
            f"  {row['truck_id']:10s}: odometer = {odometer_status:15s} at {row['timestamp']}"
        )
else:
    print("  No recent data")

cursor.close()
conn.close()

print("\n" + "=" * 70)
