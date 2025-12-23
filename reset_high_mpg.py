"""
Reset MPG for trucks with invalid high values
"""
import os

import pymysql

conn = pymysql.connect(
    host="localhost",
    user="fuel_admin",
    password=os.getenv("DB_PASSWORD"),
    database="fuel_copilot",
)

cursor = conn.cursor()

# Find trucks with MPG > 8
cursor.execute(
    """
    SELECT truck_id, mpg_current, baseline_mpg, last_updated
    FROM mpg_baseline
    WHERE mpg_current > 8.0
    ORDER BY mpg_current DESC
"""
)

trucks_to_reset = cursor.fetchall()

print(f"🔴 Found {len(trucks_to_reset)} trucks with MPG > 8.0:")
for row in trucks_to_reset:
    truck_id, mpg, baseline, updated = row
    print(f"  {truck_id}: {mpg:.2f} MPG (baseline: {baseline:.2f}, updated: {updated})")

if trucks_to_reset:
    print("\n🔧 Resetting these trucks to baseline MPG...")

    for row in trucks_to_reset:
        truck_id, mpg, baseline, _ = row

        # Reset mpg_current to baseline (6.39 from tanks.yaml)
        cursor.execute(
            """
            UPDATE mpg_baseline
            SET mpg_current = baseline_mpg,
                last_updated = NOW()
            WHERE truck_id = %s
        """,
            (truck_id,),
        )

        print(f"  ✅ {truck_id}: {mpg:.2f} → {baseline:.2f} MPG")

    conn.commit()
    print(f"\n✅ Reset {len(trucks_to_reset)} trucks")
else:
    print("\n✅ No trucks need reset")

cursor.close()
conn.close()
