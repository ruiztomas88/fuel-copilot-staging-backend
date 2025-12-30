#!/usr/bin/env python3
"""Check sensors table structure"""
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

    print("📋 ESTRUCTURA DE TABLA sensors:")
    cursor.execute("DESCRIBE sensors")
    for row in cursor.fetchall():
        print(f"   {row[0]:20} {row[1]:20} {row[2]:5}")

    print("\n📊 SAMPLE DATA:")
    cursor.execute("SELECT * FROM sensors LIMIT 3")
    cols = [desc[0] for desc in cursor.description]
    print("   Columns:", cols)

    for row in cursor.fetchall():
        print("   Row:", row)

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ ERROR: {e}")
