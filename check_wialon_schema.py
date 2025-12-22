#!/usr/bin/env python3
"""Check actual Wialon database schema"""
import pymysql

WIALON_DB = {
    "host": "20.127.200.135",
    "port": 3306,
    "user": "tomas",
    "password": "Tomas2025",
    "database": "wialon_collect",
}

try:
    conn = pymysql.connect(**WIALON_DB)
    cursor = conn.cursor()

    print("📊 WIALON DATABASE TABLES:")
    print("=" * 80)
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    for table in tables:
        print(f"   ✓ {table[0]}")

    print("\n" + "=" * 80)
    print("📋 STRUCTURE OF MAIN TABLES:")
    print("=" * 80)

    for table in tables:
        table_name = table[0]
        print(f"\n{table_name}:")
        cursor.execute(f"DESCRIBE {table_name}")
        columns = cursor.fetchall()
        for col in columns:
            print(f"   {col[0]:20} {col[1]}")

        # Show sample data
        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
        sample = cursor.fetchall()
        if sample:
            print(f"   Sample data: {len(sample)} rows")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ ERROR: {e}")
