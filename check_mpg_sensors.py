"""
Quick check: How many trucks have total_fuel_used sensor?
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
print("🔍 SENSOR AVAILABILITY FOR MPG CALCULATION")
print("=" * 80)

query = """
    SELECT 
        truck_id,
        odometer_mi,
        total_fuel_used_gal,
        engine_hours,
        fuel_level_pct
    FROM truck_sensors_cache
    ORDER BY truck_id
"""

cursor.execute(query)
rows = cursor.fetchall()

has_odo = 0
has_fuel_used = 0
has_both = 0
has_neither = 0

print(f"\n{'Truck':<10} {'Odometer':>12} {'Total Fuel':>15} {'Status'}")
print("-" * 80)

for row in rows:
    truck = row["truck_id"]
    odo = row["odometer_mi"]
    fuel = row["total_fuel_used_gal"]

    has_o = odo is not None and odo > 0
    has_f = fuel is not None and fuel > 0

    if has_o:
        has_odo += 1
    if has_f:
        has_fuel_used += 1
    if has_o and has_f:
        has_both += 1
    if not has_o and not has_f:
        has_neither += 1

    if has_o and has_f:
        status = "✅ BOTH (BEST)"
    elif has_f:
        status = "✓ FUEL ONLY (GOOD)"
    elif has_o:
        status = "⚠️  ODO ONLY"
    else:
        status = "❌ NEITHER"

    odo_str = f"{odo:.1f}" if odo else "NULL"
    fuel_str = f"{fuel:.1f}" if fuel else "NULL"

    print(f"{truck:<10} {odo_str:>12} {fuel_str:>15} {status}")

total = len(rows)
print("\n" + "=" * 80)
print(f"📊 SUMMARY ({total} trucks total):")
print(f"  ✅ Has BOTH sensors: {has_both} ({has_both/total*100:.0f}%)")
print(f"  ✓  Has total_fuel_used: {has_fuel_used} ({has_fuel_used/total*100:.0f}%)")
print(
    f"  ⚠️  Has odometer only: {has_odo - has_both} ({(has_odo-has_both)/total*100:.0f}%)"
)
print(f"  ❌ Has NEITHER: {has_neither} ({has_neither/total*100:.0f}%)")
print("=" * 80)

print(f"\n💡 MPG CALCULATION CAPABILITY:")
print(
    f"  - Can use ECU delta method: {has_fuel_used} trucks ({has_fuel_used/total*100:.0f}%)"
)
print(
    f"  - Need fuel_rate accumulation: {has_neither} trucks ({has_neither/total*100:.0f}%)"
)

cursor.close()
conn.close()
