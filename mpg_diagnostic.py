"""
MPG DIAGNOSTIC - Analyze current MPG calculations
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
print("🔍 MPG CALCULATION DIAGNOSTIC")
print("=" * 80)

# Check mpg_baseline table
print("\n📊 MPG BASELINE DATA:")
print("-" * 80)

query = """
    SELECT 
        truck_id,
        mpg_current,
        mpg_ema_smoothed,
        total_miles_accumulated,
        total_fuel_accumulated,
        last_update
    FROM mpg_baseline
    ORDER BY mpg_current DESC
    LIMIT 20
"""

cursor.execute(query)
rows = cursor.fetchall()

if rows:
    print(
        f"{'Truck':<10} {'MPG Cur':>8} {'MPG EMA':>8} {'Miles':>10} {'Fuel(gal)':>10} {'Last Update'}"
    )
    print("-" * 80)

    for row in rows:
        truck = row["truck_id"]
        mpg_cur = row["mpg_current"] or 0
        mpg_ema = row["mpg_ema_smoothed"] or 0
        miles = row["total_miles_accumulated"] or 0
        fuel = row["total_fuel_accumulated"] or 0

        # Flag unrealistic
        flag = ""
        if mpg_cur > 12:
            flag = "🔴 TOO HIGH"
        elif mpg_cur < 2 and mpg_cur > 0:
            flag = "🔴 TOO LOW"
        elif 4 <= mpg_cur <= 8:
            flag = "✓ OK"

        print(
            f"{truck:<10} {mpg_cur:>8.2f} {mpg_ema:>8.2f} {miles:>10.1f} {fuel:>10.1f} {str(row['last_update'])[:19]} {flag}"
        )

    # Calculate lifetime MPG from accumulated data
    print("\n💡 LIFETIME MPG (from accumulated data):")
    print("-" * 80)
    print(f"{'Truck':<10} {'Calc MPG':>10} {'Status'}")
    print("-" * 80)

    for row in rows:
        truck = row["truck_id"]
        miles = row["total_miles_accumulated"] or 0
        fuel = row["total_fuel_accumulated"] or 0

        if fuel > 0:
            lifetime_mpg = miles / fuel

            if lifetime_mpg > 12:
                status = "🔴 IMPOSSIBLE"
            elif lifetime_mpg < 2:
                status = "🔴 TOO LOW"
            elif 4 <= lifetime_mpg <= 8:
                status = "✓ REALISTIC"
            else:
                status = "⚠️  BORDERLINE"

            print(f"{truck:<10} {lifetime_mpg:>10.2f} {status}")
else:
    print("  No data in mpg_baseline")

# Check trucks with total_fuel_used for raw calculation
print("\n\n📊 RAW ECU DATA (for trucks with total_fuel_used):")
print("-" * 80)

query2 = """
    SELECT 
        truck_id,
        odometer_mi,
        total_fuel_used_gal
    FROM truck_sensors_cache
    WHERE total_fuel_used_gal IS NOT NULL
        AND total_fuel_used_gal > 0
    ORDER BY truck_id
"""

cursor.execute(query2)
rows2 = cursor.fetchall()

if rows2:
    print(
        f"{'Truck':<10} {'Odometer':>15} {'Total Fuel':>15} {'Lifetime MPG':>12} {'Status'}"
    )
    print("-" * 80)

    for row in rows2:
        truck = row["truck_id"]
        odo = row["odometer_mi"] or 0
        fuel = row["total_fuel_used_gal"] or 0

        if fuel > 0 and odo > 0:
            raw_mpg = odo / fuel

            if raw_mpg > 15:
                status = "🔴 IMPOSSIBLE"
            elif raw_mpg < 2:
                status = "🔴 TOO LOW"
            elif 4 <= raw_mpg <= 8:
                status = "✓ REALISTIC"
            else:
                status = "⚠️  BORDERLINE"

            print(f"{truck:<10} {odo:>15.1f} {fuel:>15.1f} {raw_mpg:>12.2f} {status}")
        else:
            odo_str = f"{odo:.1f}" if odo > 0 else "NULL"
            print(f"{truck:<10} {odo_str:>15} {fuel:>15.1f} {'N/A':>12} (no odometer)")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("✅ DIAGNOSTIC COMPLETE")
print("=" * 80)
