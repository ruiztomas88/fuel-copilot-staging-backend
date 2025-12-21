import pymysql

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor()

print("=" * 80)
print("CHECKING FOR DUPLICATES")
print("=" * 80)

# Check fuel_metrics duplicates (same truck_id + timestamp_utc)
print("\n1. fuel_metrics - Duplicate (truck_id, timestamp_utc):")
cursor.execute("""
    SELECT truck_id, timestamp_utc, COUNT(*) as cnt
    FROM fuel_metrics
    WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 1 HOUR)
    GROUP BY truck_id, timestamp_utc
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
    LIMIT 10
""")
fm_dups = cursor.fetchall()
if fm_dups:
    print(f"   ⚠️ Found {len(fm_dups)} duplicate entries in last hour:")
    for row in fm_dups:
        print(f"      {row[0]} @ {row[1]} - {row[2]} copies")
else:
    print("   ✅ No duplicates in last hour")

# Check refuel_events duplicates
print("\n2. refuel_events - Duplicate (truck_id, timestamp_utc):")
cursor.execute("""
    SELECT truck_id, timestamp_utc, COUNT(*) as cnt
    FROM refuel_events
    WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 24 HOUR)
    GROUP BY truck_id, timestamp_utc
    HAVING COUNT(*) > 1
    ORDER BY cnt DESC
    LIMIT 10
""")
re_dups = cursor.fetchall()
if re_dups:
    print(f"   ⚠️ Found {len(re_dups)} duplicate refuel events:")
    for row in re_dups:
        print(f"      {row[0]} @ {row[1]} - {row[2]} copies")
else:
    print("   ✅ No duplicate refuels in last 24h")

# Check if VM is inserting data (recent inserts)
print("\n3. Recent activity (last 10 min):")
cursor.execute("""
    SELECT COUNT(*) as recent_records
    FROM fuel_metrics
    WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 10 MINUTE)
""")
recent = cursor.fetchone()[0]
print(f"   📊 {recent} records inserted in last 10 min")

if recent > 0:
    print("   ✅ VM appears to be running and inserting data")
else:
    print("   ⚠️ No recent activity - VM might be stopped")

cursor.close()
conn.close()
