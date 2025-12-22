"""
PHASE 1: DATA CLEANUP
Truncate tables with corrupted data and let WialonSync rebuild
"""

import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password="FuelCopilot2025!",
    database="fuel_copilot",
)

cursor = conn.cursor()

print("\n" + "=" * 80)
print("🧹 PHASE 1: DATABASE CLEANUP")
print("=" * 80)

# Tables to clean
tables_to_clean = ["fleet_summary", "daily_truck_metrics", "fuel_metrics"]

# Do NOT clean truck_sensors_cache - it's our main cache, just has some old data
# WialonSync will overwrite with fresh data

print(f"\n⚠️  WARNING: This will DELETE all data from:")
for table in tables_to_clean:
    print(f"   - {table}")

print(f"\n✓ Will KEEP: truck_sensors_cache (will be overwritten with fresh data)")

response = input("\nProceed with cleanup? (yes/no): ")

if response.lower() == "yes":
    for table in tables_to_clean:
        try:
            print(f"\n🧹 Truncating {table}...")
            cursor.execute(f"TRUNCATE TABLE {table}")
            print(f"   ✓ {table} cleaned")
        except Exception as e:
            print(f"   ❌ Error cleaning {table}: {e}")

    conn.commit()

    print("\n" + "=" * 80)
    print("✅ CLEANUP COMPLETE")
    print("=" * 80)
    print("\n📊 Next steps:")
    print("  1. WialonSync will rebuild truck_sensors_cache in ~2 minutes")
    print("  2. Fleet summary will be recalculated from clean data")
    print("  3. Metrics will show realistic values")
    print("\n⏳ Wait 2-3 minutes then check dashboard")
else:
    print("\n❌ Cleanup cancelled")

cursor.close()
conn.close()
