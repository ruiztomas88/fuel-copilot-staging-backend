"""
Check units_map structure and DO9693 mapping
"""
import os
import pymysql
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

wialon_conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password=os.getenv("WIALON_MYSQL_PASSWORD"),
    database="wialon_collect",
    cursorclass=pymysql.cursors.DictCursor
)

with wialon_conn.cursor() as cursor:
    # Get units_map structure
    print("UNITS_MAP TABLE STRUCTURE:")
    print("="*80)
    cursor.execute("DESCRIBE units_map")
    cols = cursor.fetchall()
    for col in cols:
        print(f"  {col['Field']:30s} {col['Type']:20s} {col['Null']:5s} {col['Key']:5s}")
    
    # Get sample records
    print("\nSAMPLE RECORDS (first 5):")
    print("="*80)
    cursor.execute("SELECT * FROM units_map LIMIT 5")
    records = cursor.fetchall()
    for r in records:
        print(f"\n{r}")
    
    # Search for DO9693
    print("\n\nSEARCHING FOR DO9693:")
    print("="*80)
    cursor.execute("SELECT * FROM units_map WHERE unit_name LIKE '%DO9693%' OR truck_id LIKE '%DO9693%'")
    do9693 = cursor.fetchall()
    if do9693:
        for d in do9693:
            print(f"\nFound:")
            for k, v in d.items():
                print(f"  {k}: {v}")
    else:
        print("Not found by name. Checking all records...")
        cursor.execute("SELECT * FROM units_map")
        all_units = cursor.fetchall()
        print(f"\nTotal units in map: {len(all_units)}")
        print("\nFirst 10 units:")
        for u in all_units[:10]:
            print(f"  {u.get('unit_name') or u.get('truck_id') or u.get('unit_id')}: {u}")

wialon_conn.close()
