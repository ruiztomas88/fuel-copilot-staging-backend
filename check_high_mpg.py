import os

import pymysql

# Connect to database
conn = pymysql.connect(
    host="localhost",
    user="root",
    password=os.getenv("MYSQL_ROOT_PASSWORD", "FuelCopilot2025!"),
    database="fuel_copilot",
)

cursor = conn.cursor()

# Check trucks with MPG > 8
cursor.execute(
    """
    SELECT truck_id, mpg_current, baseline_mpg, sample_count, last_updated
    FROM mpg_baseline
    WHERE mpg_current > 8
    ORDER BY mpg_current DESC
"""
)

print("🔴 Trucks with MPG > 8:")
print("=" * 80)
for row in cursor.fetchall():
    truck_id, mpg_current, baseline_mpg, sample_count, last_updated = row
    print(
        f"{truck_id}: {mpg_current:.2f} MPG (baseline: {baseline_mpg:.2f}, samples: {sample_count}, updated: {last_updated})"
    )

# Check recent trip data for these trucks
print("\n📊 Recent trip deltas for high MPG trucks:")
print("=" * 80)
cursor.execute(
    """
    SELECT truck_id, distance_miles, fuel_consumed_gallons, 
           distance_miles/fuel_consumed_gallons as mpg,
           start_time, end_time
    FROM trip_data
    WHERE truck_id IN (
        SELECT truck_id FROM mpg_baseline WHERE mpg_current > 8
    )
    AND distance_miles > 0 AND fuel_consumed_gallons > 0
    ORDER BY start_time DESC
    LIMIT 20
"""
)

for row in cursor.fetchall():
    truck_id, miles, fuel, mpg, start, end = row
    print(
        f"{truck_id}: {miles:.1f}mi ÷ {fuel:.2f}gal = {mpg:.2f} MPG ({start} → {end})"
    )

cursor.close()
conn.close()
