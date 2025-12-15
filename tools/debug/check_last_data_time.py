"""
Ver último timestamp de datos para FF7702, JB6858, RT9127
"""
import pymysql
import time
from datetime import datetime

conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password="Tomas2025",
    database="wialon_collect",
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

print("=" * 80)
print("🕐 LAST DATA TIMESTAMP CHECK")
print("=" * 80)
print()

trucks = {
    'FF7702': 401989385,
    'JB6858': 402007354,
    'RT9127': 401905963,
}

cursor = conn.cursor()

now_epoch = int(time.time())
one_hour_ago = now_epoch - 3600

print(f"NOW: {datetime.fromtimestamp(now_epoch)} (epoch: {now_epoch})")
print(f"1 HOUR AGO: {datetime.fromtimestamp(one_hour_ago)} (epoch: {one_hour_ago})")
print()

for truck_id, unit_id in trucks.items():
    # Get latest data timestamp
    query = """
        SELECT 
            MAX(m) as last_epoch,
            FROM_UNIXTIME(MAX(m)) as last_datetime,
            %s - MAX(m) as seconds_ago,
            COUNT(*) as total_records
        FROM sensors
        WHERE unit = %s
    """
    cursor.execute(query, (now_epoch, unit_id))
    result = cursor.fetchone()
    
    print(f"📊 {truck_id} (unit {unit_id}):")
    
    if result['last_epoch']:
        seconds_ago = result['seconds_ago']
        print(f"   Last data: {result['last_datetime']} ({seconds_ago}s ago)")
        print(f"   Total records: {result['total_records']}")
        
        if seconds_ago <= 3600:
            print(f"   ✅ Within 1-hour window (WialonSync will read it)")
        else:
            print(f"   ❌ OUTSIDE 1-hour window - WialonSync will skip it!")
            print(f"      Needs data from last hour to be processed")
    else:
        print(f"   ❌ NO DATA AT ALL in sensors table")
    
    print()

conn.close()

print("=" * 80)
print("💡 WialonSync only reads data from last 1 hour (3600 seconds)")
print("   If truck has no data in that window, shows 'No data from Wialon'")
print("=" * 80)
