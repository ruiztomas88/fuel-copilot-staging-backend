"""
Database Cleanup Script - December 22, 2025

Fixes:
1. Remove corrupted odometer records (>10M miles)
2. Truncate tables for fresh start
3. Reset MPG calculations

Usage:
    python cleanup_database_dec22.py
"""

import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

# Database connection
conn = pymysql.connect(
    host=os.getenv("LOCAL_DB_HOST", "localhost"),
    user=os.getenv("LOCAL_DB_USER", "fuel_admin"),
    password=os.getenv("LOCAL_DB_PASSWORD", "FuelCopilot2025!"),
    database=os.getenv("LOCAL_DB_NAME", "fuel_copilot"),
    charset="utf8mb4",
)

cursor = conn.cursor()

print("=" * 80)
print("🔧 DATABASE CLEANUP - December 22, 2025")
print("=" * 80)

# Step 1: Count corrupted records
print("\n📊 Step 1: Analyzing corrupted data...")
cursor.execute(
    """
    SELECT COUNT(*) as corrupted_count 
    FROM fuel_metrics 
    WHERE odometer_mi > 10000000
"""
)
corrupted_count = cursor.fetchone()[0]
print(f"   Found {corrupted_count} records with corrupted odometer (>10M miles)")

# Step 2: Show affected trucks
cursor.execute(
    """
    SELECT truck_id, COUNT(*) as count, MAX(odometer_mi) as max_odom
    FROM fuel_metrics 
    WHERE odometer_mi > 10000000
    GROUP BY truck_id
    ORDER BY count DESC
"""
)
print("\n   Affected trucks:")
for row in cursor.fetchall():
    print(f"   - {row[0]}: {row[1]} records, max={row[2]:,.0f} miles")

# Step 3: Count total records
cursor.execute("SELECT COUNT(*) FROM fuel_metrics")
total_records = cursor.fetchone()[0]
print(f"\n   Total records in fuel_metrics: {total_records:,}")

# Ask for confirmation
print("\n" + "=" * 80)
print("⚠️  WARNING: This will DELETE ALL DATA and start fresh!")
print("=" * 80)
print("\nWhat will be deleted:")
print("  - All fuel_metrics records")
print("  - All daily_truck_metrics records")
print("  - All refuel_events records")
print("  - truck_sensors_cache will be KEPT (current snapshot)")
print("\n")

response = input("Type 'YES' to proceed with cleanup: ")

if response != "YES":
    print("\n❌ Cleanup cancelled.")
    conn.close()
    exit(0)

print("\n🗑️  Step 4: Truncating tables...")

# Truncate in correct order (respecting foreign keys)
tables = ["refuel_events", "daily_truck_metrics", "fuel_metrics"]

for table in tables:
    try:
        cursor.execute(f"TRUNCATE TABLE {table}")
        conn.commit()
        print(f"   ✅ {table} truncated")
    except Exception as e:
        print(f"   ❌ Error truncating {table}: {e}")
        conn.rollback()

print("\n✅ Database cleanup completed!")
print("\n" + "=" * 80)
print("📋 NEXT STEPS:")
print("=" * 80)
print("1. Restart services: .\\start-services.ps1")
print("2. Wait 5 minutes for data collection")
print("3. Verify MPG values are in 4.0-8.0 range")
print("4. Check frontend metrics tab")
print("=" * 80)

conn.close()
