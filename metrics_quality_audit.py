"""
METRICS ANALYSIS - Find data quality issues
1. Check impossible mileage values
2. Check recent data vs old data (DB was reset 2-3 days ago)
3. Verify cost calculations
4. Check MPG calculations
"""
import os

from datetime import datetime, timedelta

import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password=os.getenv("DB_PASSWORD"),
    database="fuel_copilot",
)

cursor = conn.cursor(dictionary=True)

print("\n" + "=" * 80)
print("🔍 METRICS DATA QUALITY AUDIT")
print("=" * 80)

# 1. Check fleet_summary for impossible values
print("\n📊 FLEET_SUMMARY ANALYSIS:")
print("-" * 80)

query = """
    SELECT 
        truck_id,
        total_miles_driven,
        total_fuel_consumed_gal,
        avg_mpg,
        cost_per_mile,
        last_update
    FROM fleet_summary
    ORDER BY total_miles_driven DESC
    LIMIT 20
"""

cursor.execute(query)
rows = cursor.fetchall()

if rows:
    print(
        f"{'Truck':<10} {'Miles':>12} {'Fuel(gal)':>12} {'MPG':>8} {'$/mi':>8} {'Last Update'}"
    )
    print("-" * 80)

    suspicious = []
    for row in rows:
        miles = row["total_miles_driven"] or 0
        fuel = row["total_fuel_consumed_gal"] or 0
        mpg = row["avg_mpg"] or 0
        cost = row["cost_per_mile"] or 0

        # Flag suspicious values
        flags = []
        if miles > 100000:  # Impossible in 2-3 days
            flags.append("🔴 MILES_TOO_HIGH")
        if mpg > 15:  # Class 8 trucks max ~8 MPG
            flags.append("🔴 MPG_TOO_HIGH")
        if mpg < 2 and mpg > 0:
            flags.append("🔴 MPG_TOO_LOW")
        if cost > 5:  # Typical $1.50-$2.50/mi
            flags.append("🔴 COST_TOO_HIGH")

        flag_str = " ".join(flags) if flags else "✓"

        print(
            f"{row['truck_id']:<10} {miles:>12.0f} {fuel:>12.1f} {mpg:>8.2f} ${cost:>7.2f} {str(row['last_update'])[:19]} {flag_str}"
        )

        if flags:
            suspicious.append((row["truck_id"], flags))

    if suspicious:
        print(f"\n⚠️  Found {len(suspicious)} trucks with suspicious metrics")
else:
    print("  No data in fleet_summary")

# 2. Check daily_truck_metrics for recent data
print("\n\n📅 DAILY_TRUCK_METRICS - Last 7 Days:")
print("-" * 80)

query = """
    SELECT 
        metric_date,
        COUNT(DISTINCT truck_id) as truck_count,
        SUM(miles_driven) as total_miles,
        SUM(fuel_consumed_gal) as total_fuel,
        AVG(avg_mpg) as avg_mpg
    FROM daily_truck_metrics
    WHERE metric_date >= CURDATE() - INTERVAL 7 DAY
    GROUP BY metric_date
    ORDER BY metric_date DESC
"""

cursor.execute(query)
rows = cursor.fetchall()

if rows:
    print(f"{'Date':<12} {'Trucks':>8} {'Miles':>12} {'Fuel(gal)':>12} {'Avg MPG':>10}")
    print("-" * 80)
    for row in rows:
        print(
            f"{str(row['metric_date']):<12} {row['truck_count']:>8} {row['total_miles'] or 0:>12.1f} {row['total_fuel'] or 0:>12.1f} {row['avg_mpg'] or 0:>10.2f}"
        )
else:
    print("  No daily metrics data")

# 3. Check for corrupted odometer data (199727756 miles mentioned)
print("\n\n🔴 CORRUPTED ODOMETER CHECK:")
print("-" * 80)

query = """
    SELECT 
        truck_id,
        odometer_mi,
        timestamp
    FROM truck_sensors_cache
    WHERE odometer_mi > 1000000
    ORDER BY odometer_mi DESC
    LIMIT 10
"""

cursor.execute(query)
rows = cursor.fetchall()

if rows:
    print(f"{'Truck':<10} {'Odometer (mi)':>15} {'Timestamp'}")
    print("-" * 80)
    for row in rows:
        print(f"{row['truck_id']:<10} {row['odometer_mi']:>15.1f} {row['timestamp']}")
    print(f"\n🔥 CRITICAL: {len(rows)} trucks with IMPOSSIBLE odometer values!")
else:
    print("  ✓ No corrupted odometer values found")

# 4. Check when DB was last reset (oldest timestamp)
print("\n\n📅 DATABASE AGE CHECK:")
print("-" * 80)

query = """
    SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest, COUNT(*) as total
    FROM truck_sensors_cache
"""

cursor.execute(query)
row = cursor.fetchone()

if row and row["oldest"]:
    age_days = (row["newest"] - row["oldest"]).total_seconds() / 86400
    print(f"  Oldest record: {row['oldest']}")
    print(f"  Newest record: {row['newest']}")
    print(f"  Data span: {age_days:.1f} days")
    print(f"  Total records: {row['total']}")

    if age_days > 5:
        print(
            f"\n  ⚠️  Data is {age_days:.0f} days old - older than expected (DB reset 2-3 days ago)"
        )
else:
    print("  No data in truck_sensors_cache")

# 5. Check MPG distribution
print("\n\n📈 MPG DISTRIBUTION (from truck_sensors_cache):")
print("-" * 80)

# We need to calculate MPG from available data
query = """
    SELECT 
        truck_id,
        odometer_mi,
        total_fuel_used_gal,
        engine_hours
    FROM truck_sensors_cache
    WHERE odometer_mi IS NOT NULL 
        AND total_fuel_used_gal IS NOT NULL
        AND odometer_mi > 0
        AND total_fuel_used_gal > 0
    LIMIT 20
"""

cursor.execute(query)
rows = cursor.fetchall()

if rows:
    print(
        f"{'Truck':<10} {'Odometer':>12} {'Fuel Used':>12} {'Calc MPG':>10} {'Status'}"
    )
    print("-" * 80)
    for row in rows:
        odo = row["odometer_mi"]
        fuel = row["total_fuel_used_gal"]

        # Calculate lifetime MPG
        mpg = odo / fuel if fuel > 0 else 0

        # Flag unrealistic MPG
        if mpg > 15:
            status = "🔴 TOO HIGH"
        elif mpg < 2:
            status = "🔴 TOO LOW"
        elif 4 <= mpg <= 8:
            status = "✓ REALISTIC"
        else:
            status = "⚠️  BORDERLINE"

        print(f"{row['truck_id']:<10} {odo:>12.1f} {fuel:>12.1f} {mpg:>10.2f} {status}")
else:
    print("  No trucks with both odometer and fuel data")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("✅ ANALYSIS COMPLETE")
print("=" * 80)
