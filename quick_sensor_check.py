"""
Quick sensor check - simplified version
"""

import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password="FuelCopilot2025!",
    database="fuel_copilot",
)

cursor = conn.cursor(dictionary=True)

print("\n" + "=" * 80)
print("🔍 QUICK SENSOR CHECK - truck_sensors_cache")
print("=" * 80)

# Simple query - just count and show sample
query = """
    SELECT 
        truck_id,
        odometer_mi,
        fuel_level_pct,
        coolant_temp_f,
        oil_pressure_psi,
        engine_hours,
        timestamp
    FROM truck_sensors_cache
    ORDER BY timestamp DESC
    LIMIT 20
"""

cursor.execute(query)
rows = cursor.fetchall()

print(f"\n📊 LATEST 20 TRUCKS:")
print("-" * 80)
print(
    f"{'Truck':<10} {'Odometer':<12} {'Fuel%':<8} {'Coolant':<10} {'Oil psi':<10} {'Hours':<10}"
)
print("-" * 80)

for row in rows:
    truck = row["truck_id"]
    odo = f"{row['odometer_mi']:.1f}" if row["odometer_mi"] else "NULL"
    fuel = f"{row['fuel_level_pct']:.1f}%" if row["fuel_level_pct"] else "NULL"
    cool = f"{row['coolant_temp_f']:.0f}°F" if row["coolant_temp_f"] else "NULL"
    oil = f"{row['oil_pressure_psi']:.0f}" if row["oil_pressure_psi"] else "NULL"
    hours = f"{row['engine_hours']:.0f}" if row["engine_hours"] else "NULL"

    print(f"{truck:<10} {odo:<12} {fuel:<8} {cool:<10} {oil:<10} {hours:<10}")

# Count stats
cursor.execute("SELECT COUNT(*) as total FROM truck_sensors_cache")
total = cursor.fetchone()["total"]

cursor.execute(
    "SELECT COUNT(*) as with_odo FROM truck_sensors_cache WHERE odometer_mi IS NOT NULL AND odometer_mi > 0"
)
with_odo = cursor.fetchone()["with_odo"]

cursor.execute(
    "SELECT COUNT(*) as with_fuel FROM truck_sensors_cache WHERE fuel_level_pct IS NOT NULL"
)
with_fuel = cursor.fetchone()["with_fuel"]

cursor.execute(
    "SELECT COUNT(*) as with_coolant FROM truck_sensors_cache WHERE coolant_temp_f IS NOT NULL"
)
with_coolant = cursor.fetchone()["with_coolant"]

print("\n" + "=" * 80)
print(f"📈 STATISTICS:")
print("-" * 80)
print(f"Total trucks in cache: {total}")
print(f"With odometer: {with_odo} ({with_odo/total*100:.0f}%)")
print(f"With fuel level: {with_fuel} ({with_fuel/total*100:.0f}%)")
print(f"With coolant temp: {with_coolant} ({with_coolant/total*100:.0f}%)")
print("=" * 80)

cursor.close()
conn.close()
