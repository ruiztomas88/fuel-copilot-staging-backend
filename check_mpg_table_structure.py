#!/usr/bin/env python3
import os

import pymysql

conn = pymysql.connect(
    host="localhost",
    user="fuel_admin",
    password=os.getenv("MYSQL_PASSWORD"),
    database="fuel_copilot",
    cursorclass=pymysql.cursors.DictCursor,
)

try:
    with conn.cursor() as cursor:
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()

        print("\n📋 TABLES IN fuel_copilot:")
        for table in tables:
            print(f"  - {list(table.values())[0]}")

        # Check if mpg_baseline exists
        cursor.execute("SHOW TABLES LIKE 'mpg%'")
        mpg_tables = cursor.fetchall()

        if mpg_tables:
            print("\n📊 MPG TABLES:")
            for table in mpg_tables:
                table_name = list(table.values())[0]
                print(f"\n  Table: {table_name}")
                cursor.execute(f"DESCRIBE {table_name}")
                columns = cursor.fetchall()
                for col in columns:
                    print(f"    - {col['Field']} ({col['Type']})")

                # Show sample data
                cursor.execute(f"SELECT * FROM {table_name} LIMIT 5")
                rows = cursor.fetchall()
                print(f"    Sample data ({len(rows)} rows):")
                for row in rows:
                    print(f"      {row}")
        else:
            print("\n⚠️ No MPG tables found")

finally:
    conn.close()
