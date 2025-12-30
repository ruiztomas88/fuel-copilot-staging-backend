#!/usr/bin/env python3
"""Check actual Wialon database schema"""
import pymysql

from config import get_wialon_db_config
from sql_security import safe_describe, validate_table_name

try:
    conn = pymysql.connect(**get_wialon_db_config())
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

        # Use safe DESCRIBE
        try:
            cursor.execute(safe_describe(table_name))
            columns = cursor.fetchall()
            for col in columns:
                print(f"   {col[0]:20} {col[1]}")
        except Exception as e:
            print(f"   ⚠️ Could not describe table: {e}")
            continue

        # Use parameterized query for sample data
        cursor.execute(
            "SELECT * FROM "
            + validate_table_name(table_name, allow_wialon=True)
            + " LIMIT 3"
        )
        sample = cursor.fetchall()
        if sample:
            print(f"   Sample data: {len(sample)} rows")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ ERROR: {e}")
