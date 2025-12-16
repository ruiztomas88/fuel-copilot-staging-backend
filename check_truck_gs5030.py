#!/usr/bin/env python3
"""
Check if truck GS5030 has data in the database
"""

import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_mysql import get_mysql_connection

def check_truck():
    truck_id = "GS5030"
    print(f"=" * 60)
    print(f"CHECKING TRUCK: {truck_id}")
    print(f"=" * 60)
    
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Check fuel_metrics table
        print("\n📊 1. fuel_metrics table:")
        cursor.execute("""
            SELECT COUNT(*) as count, 
                   MIN(timestamp_utc) as first_record,
                   MAX(timestamp_utc) as last_record
            FROM fuel_metrics 
            WHERE truck_id = %s
        """, (truck_id,))
        result = cursor.fetchone()
        print(f"   Records: {result['count']}")
        print(f"   First record: {result['first_record']}")
        print(f"   Last record: {result['last_record']}")
        
        # 2. Check sensors table (Wialon raw data)
        print("\n📡 2. sensors table (Wialon raw):")
        cursor.execute("""
            SELECT COUNT(*) as count,
                   FROM_UNIXTIME(MIN(m)) as first_record,
                   FROM_UNIXTIME(MAX(m)) as last_record
            FROM sensors 
            WHERE n = %s
        """, (truck_id,))
        result = cursor.fetchone()
        print(f"   Records: {result['count']}")
        print(f"   First record: {result['first_record']}")
        print(f"   Last record: {result['last_record']}")
        
        # 3. Get latest sensor data
        print("\n📡 3. Latest sensor data (last 5 records):")
        cursor.execute("""
            SELECT n as truck_id, 
                   FROM_UNIXTIME(m) as timestamp,
                   param, val
            FROM sensors 
            WHERE n = %s
            ORDER BY m DESC
            LIMIT 5
        """, (truck_id,))
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"   {row['timestamp']} | {row['param']}: {row['val']}")
        else:
            print("   ❌ No sensor records found!")
            
        # 4. Check unit_id mapping
        print("\n🔗 4. Check unit_id (401927766) in sensors:")
        cursor.execute("""
            SELECT COUNT(*) as count,
                   FROM_UNIXTIME(MAX(m)) as last_record
            FROM sensors 
            WHERE unit = 401927766
        """)
        result = cursor.fetchone()
        print(f"   Records with unit_id 401927766: {result['count']}")
        print(f"   Last record: {result['last_record']}")
        
        # 5. Check what name is stored for that unit
        cursor.execute("""
            SELECT DISTINCT n as truck_name
            FROM sensors 
            WHERE unit = 401927766
            LIMIT 5
        """)
        rows = cursor.fetchall()
        if rows:
            print(f"   Truck names for unit 401927766: {[r['truck_name'] for r in rows]}")
        
        cursor.close()
        conn.close()
        
        print("\n" + "=" * 60)
        print("DIAGNOSIS:")
        print("=" * 60)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    check_truck()
