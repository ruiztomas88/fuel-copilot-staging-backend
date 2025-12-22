#!/usr/bin/env python3
"""
Check Wialon database directly for DO9693 sensors
Compare with what Beyond shows vs what we have
"""
from datetime import datetime

import pymysql

WIALON_DB = {
    "host": "20.127.200.135",
    "port": 3306,
    "user": "tomas",
    "password": "Tomas2025",
    "database": "wialon_collect",
}


def check_wialon_structure():
    """First understand Wialon DB structure"""
    print("=" * 80)
    print("📊 WIALON DATABASE STRUCTURE")
    print("=" * 80)

    try:
        conn = pymysql.connect(**WIALON_DB)
        cursor = conn.cursor()

        # List tables
        cursor.execute("SHOW TABLES")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"\n✅ Found {len(tables)} tables:")
        for t in tables:
            print(f"   - {t}")

        # Check structure of each table
        for table in tables:
            print(f"\n📋 Structure of {table}:")
            cursor.execute(f"DESCRIBE {table}")
            cols = cursor.fetchall()
            for col in cols:
                print(f"   {col[0]:25} {col[1]:20} {col[2]:5}")

            # Show row count
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   → Total rows: {count:,}")

            # Sample data
            if count > 0:
                cursor.execute(f"SELECT * FROM {table} LIMIT 2")
                samples = cursor.fetchall()
                print(f"   → Sample: {samples[0] if samples else 'None'}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ ERROR: {e}")


def find_do9693_unit_id():
    """Find DO9693's unit_id in Wialon"""
    print("\n" + "=" * 80)
    print("🔍 SEARCHING FOR DO9693 UNIT_ID")
    print("=" * 80)

    try:
        conn = pymysql.connect(**WIALON_DB)
        cursor = conn.cursor()

        # Wialon typically has a units or trucks mapping table
        # Let's search all tables for DO9693
        cursor.execute("SHOW TABLES")
        tables = [t[0] for t in cursor.fetchall()]

        for table in tables:
            try:
                cursor.execute(f"DESCRIBE {table}")
                cols = [c[0] for c in cursor.fetchall()]

                # Look for columns that might contain truck_id
                search_cols = [
                    c
                    for c in cols
                    if "name" in c.lower() or "id" in c.lower() or "truck" in c.lower()
                ]

                if search_cols:
                    # Try to find DO9693
                    for col in search_cols:
                        try:
                            cursor.execute(
                                f"SELECT * FROM {table} WHERE {col} LIKE '%DO9693%' OR {col} LIKE '%9693%' LIMIT 5"
                            )
                            results = cursor.fetchall()
                            if results:
                                print(f"\n✅ Found in {table}.{col}:")
                                for r in results:
                                    print(f"   {r}")
                        except:
                            pass
            except:
                pass

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ ERROR: {e}")


def check_recent_sensor_data():
    """Check recent sensor data for all units"""
    print("\n" + "=" * 80)
    print("📡 RECENT SENSOR DATA (Last 10 minutes)")
    print("=" * 80)

    try:
        conn = pymysql.connect(**WIALON_DB)
        cursor = conn.cursor()

        # Common Wialon sensor table patterns
        possible_tables = ["sensors", "sensor_data", "messages", "avl_unit_messages"]

        for table in possible_tables:
            try:
                cursor.execute(f"SHOW TABLES LIKE '{table}'")
                if cursor.fetchone():
                    print(f"\n✅ Checking {table}:")
                    cursor.execute(f"DESCRIBE {table}")
                    cols = [c[0] for c in cursor.fetchall()]
                    print(f"   Columns: {', '.join(cols[:10])}")

                    # Try to get recent data
                    cursor.execute(f"SELECT * FROM {table} ORDER BY RAND() LIMIT 3")
                    samples = cursor.fetchall()
                    print(f"   Sample data:")
                    for s in samples[:2]:
                        print(f"      {s}")
            except Exception as e:
                print(f"   ⚠️ {table}: {e}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ ERROR: {e}")


if __name__ == "__main__":
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "WIALON DATABASE INVESTIGATION - DO9693" + " " * 18 + "║")
    print("╚" + "=" * 78 + "╝")

    check_wialon_structure()
    find_do9693_unit_id()
    check_recent_sensor_data()

    print("\n" + "=" * 80)
    print("💡 NEXT: Compare with wialon_reader.py sensor mapping")
    print("=" * 80)
