"""
Check database structure first
"""
import os

import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password=os.getenv("DB_PASSWORD"),
    database="fuel_copilot",
)

cursor = conn.cursor(dictionary=True)

print("\n" + "=" * 80)
print("📊 DATABASE STRUCTURE CHECK")
print("=" * 80)

# List all tables
cursor.execute("SHOW TABLES")
tables = [row[list(row.keys())[0]] for row in cursor.fetchall()]

print(f"\n✓ Found {len(tables)} tables:")
for table in sorted(tables):
    print(f"  - {table}")

# Check structure of key tables
key_tables = [
    "fleet_summary",
    "daily_truck_metrics",
    "truck_sensors_cache",
    "fuel_metrics",
]

for table in key_tables:
    if table in tables:
        print(f"\n📋 {table} columns:")
        cursor.execute(f"DESCRIBE {table}")
        cols = cursor.fetchall()
        for col in cols:
            print(
                f"  - {col['Field']:30s} {col['Type']:20s} {col['Null']:5s} {col['Key']}"
            )

cursor.close()
conn.close()
