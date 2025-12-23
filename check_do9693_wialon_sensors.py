"""
Quick diagnostic to check DO9693 sensors in Wialon database
"""
import os
import pymysql
import sys
from datetime import datetime, timedelta

# Fix encoding for Windows console
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Wialon DB connection
wialon_conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password=os.getenv("WIALON_MYSQL_PASSWORD"),
    database="wialon_collect",
    cursorclass=pymysql.cursors.DictCursor
)

print("=" * 80)
print("WIALON DATABASE DIAGNOSTIC FOR DO9693")
print("=" * 80)

# First, find the unit_id for DO9693
with wialon_conn.cursor() as cursor:
    cursor.execute("SHOW TABLES")
    tables = [t[list(t.keys())[0]] for t in cursor.fetchall()]
    print(f"\nAvailable tables: {len(tables)}")
    for table in tables[:20]:
        print(f"   - {table}")
    
    # Look for units table
    if 'units' in tables or 'wialon_units' in tables:
        table_name = 'units' if 'units' in tables else 'wialon_units'
        cursor.execute(f"SELECT * FROM {table_name} WHERE name LIKE '%DO9693%' OR nm LIKE '%DO9693%' LIMIT 1")
        unit = cursor.fetchone()
        if unit:
            print(f"\nFound unit: {unit}")
        else:
            # Try to find any units
            cursor.execute(f"DESCRIBE {table_name}")
            cols = cursor.fetchall()
            print(f"\nColumns in {table_name}:")
            for col in cols:
                print(f"   - {col}")
            
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
            units = cursor.fetchall()
            print(f"\nSample units:")
            for u in units:
                print(f"   {u}")
    
    # Look for messages/data table
    data_tables = [t for t in tables if 'message' in t.lower() or 'data' in t.lower() or 'sensor' in t.lower()]
    print(f"\nData tables: {data_tables}")
    
    # Check the most recent data
    if data_tables:
        for dt in data_tables[:3]:
            print(f"\nChecking {dt}:")
            cursor.execute(f"DESCRIBE {dt}")
            cols = [c['Field'] for c in cursor.fetchall()]
            print(f"   Columns: {', '.join(cols[:10])}...")
            
            cursor.execute(f"SELECT * FROM {dt} LIMIT 10")
            recent = cursor.fetchall()
            print(f"   Found {len(recent)} records")
            if recent:
                print(f"   Sample record keys: {list(recent[0].keys())}")
                for r in recent[:3]:
                    print(f"   {r}")

wialon_conn.close()
