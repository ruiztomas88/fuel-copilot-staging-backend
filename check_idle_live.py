"""
🔍 LIVE IDLE DIAGNOSTIC - Check why idle is using fallback

Queries the database for current idle readings and shows which method is being used
"""

import pymysql
from datetime import datetime, timedelta
from config import get_allowed_trucks

# Database connection
conn = pymysql.connect(
    host="127.0.0.1",
    port=3306,
    user="fuel_copilot",
    password="Fc2024Secure!",
    database="fuel_copilot",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

allowed_trucks = list(get_allowed_trucks())

print("=" * 80)
print("🔍 LIVE IDLE CONSUMPTION ANALYSIS")
print("=" * 80)
print()

# Get recent idle readings from last 15 minutes
query = """
    SELECT 
        truck_id,
        timestamp_utc,
        truck_status,
        rpm,
        idle_gph,
        idle_method,
        idle_mode,
        TIMESTAMPDIFF(MINUTE, timestamp_utc, NOW()) as age_minutes
    FROM sensor_data
    WHERE truck_id IN (%s)
        AND truck_status = 'STOPPED'
        AND timestamp_utc > DATE_SUB(NOW(), INTERVAL 15 MINUTE)
    ORDER BY truck_id, timestamp_utc DESC
""" % ','.join(['%s'] * len(allowed_trucks))

cursor = conn.cursor()
cursor.execute(query, allowed_trucks)
rows = cursor.fetchall()

# Group by truck (get latest per truck)
trucks_data = {}
for row in rows:
    truck_id = row['truck_id']
    if truck_id not in trucks_data:
        trucks_data[truck_id] = row

print(f"📊 CURRENT IDLE STATUS (Last 15 minutes)")
print("-" * 80)

for truck_id in sorted(allowed_trucks):
    if truck_id in trucks_data:
        data = trucks_data[truck_id]
        age = data['age_minutes']
        
        # Color code based on method
        if data['idle_method'] == 'SENSOR_FUEL_RATE':
            status = "✅ SENSOR"
        elif data['idle_method'] == 'ECU_IDLE_COUNTER':
            status = "✅ ECU"
        elif data['idle_method'] == 'FALLBACK_CONSENSUS':
            status = "⚠️  FALLBACK"
        else:
            status = f"❓ {data['idle_method']}"
        
        print(f"{truck_id}  {data['idle_gph']:.2f} GPH  {status}  "
              f"(RPM: {data['rpm'] or 'N/A'}, {age}min ago)")
    else:
        print(f"{truck_id}  -- GPH  ❌ NO DATA (not stopped in last 15min)")

print()
print("=" * 80)

# Check if fuel_rate sensor is being received
print()
print("🔬 CHECKING WIALON FUEL_RATE SENSOR (last 5 minutes)")
print("-" * 80)

wialon_conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password="Tomas2025",
    database="wialon_collect",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

wialon_cursor = wialon_conn.cursor()

for truck_id in sorted(allowed_trucks):
    # Get truck unit ID
    unit_map = {
        "RT9127": 2201,
        "RT9129": 2202,
        "RT9134": 2203,
        "RT9135": 2204,
    }
    
    unit_id = unit_map.get(truck_id)
    if not unit_id:
        continue
    
    query = """
        SELECT 
            p as param,
            value,
            FROM_UNIXTIME(m) as timestamp,
            TIMESTAMPDIFF(SECOND, FROM_UNIXTIME(m), NOW()) as age_seconds
        FROM sensors
        WHERE unit = %s
            AND p IN ('fuel_rate', 'rpm')
            AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 5 MINUTE)
        ORDER BY p, m DESC
        LIMIT 10
    """
    
    wialon_cursor.execute(query, (unit_id,))
    sensor_rows = wialon_cursor.fetchall()
    
    if sensor_rows:
        fuel_rate_found = False
        rpm_found = False
        
        for row in sensor_rows:
            if row['param'] == 'fuel_rate':
                fuel_rate_found = True
                lph = row['value']
                gph = lph / 3.78541
                age = row['age_seconds']
                print(f"{truck_id}  fuel_rate: {lph:.2f} LPH ({gph:.2f} GPH)  {age}s ago  ✅")
                break
        
        if not fuel_rate_found:
            print(f"{truck_id}  fuel_rate: NOT FOUND in last 5min  ❌")
        
        for row in sensor_rows:
            if row['param'] == 'rpm':
                rpm_found = True
                rpm = row['value']
                age = row['age_seconds']
                status = "idle" if rpm < 1000 else "running"
                print(f"{truck_id}  rpm: {rpm:.0f} ({status})  {age}s ago")
                break
    else:
        print(f"{truck_id}  NO SENSOR DATA in last 5min  ❌")

print()
print("=" * 80)
print()
print("💡 INTERPRETATION:")
print("  ✅ SENSOR = Using fuel_rate directly (best accuracy)")
print("  ⚠️  FALLBACK = fuel_rate not available or out of range")
print()
print("🔧 If seeing FALLBACK:")
print("  1. Check if fuel_rate sensor exists in Wialon (above)")
print("  2. Check if backend was restarted after code update")
print("  3. Check backend logs for 'fuel_rate X.XX LPH out of range'")

conn.close()
wialon_conn.close()
