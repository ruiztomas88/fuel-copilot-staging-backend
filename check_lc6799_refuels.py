import pymysql

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor()

print("=" * 80)
print("LC6799 REFUEL EVENTS - LAST 30 DAYS")
print("=" * 80)

cursor.execute("""
    SELECT 
        id,
        timestamp_utc,
        fuel_before,
        fuel_after,
        gallons_added,
        refuel_type,
        confidence,
        validated
    FROM refuel_events
    WHERE truck_id = 'LC6799'
      AND timestamp_utc > DATE_SUB(NOW(), INTERVAL 30 DAY)
    ORDER BY timestamp_utc DESC
""")

refuels = cursor.fetchall()
if refuels:
    print(f"\n✅ Found {len(refuels)} refuel(s) for LC6799:")
    print(f"\n{'ID':<6} {'Timestamp':<20} {'Before':<10} {'After':<10} {'Gallons':<10} {'Type':<15}")
    print("-" * 80)
    for row in refuels:
        id, ts, before, after, gal, rtype, conf, valid = row
        print(f"{id:<6} {str(ts):<20} {before:>6.1f}%   {after:>6.1f}%   {gal:>6.1f} gal  {rtype or 'N/A':<15}")
else:
    print("\n❌ NO refuel events found for LC6799 in last 30 days")
    print("   This explains why frontend shows 'No refuel events'")

# Check the jump we saw in fuel_metrics
print("\n" + "=" * 80)
print("FUEL JUMP DETECTION (from fuel_metrics)")
print("=" * 80)

cursor.execute("""
    SELECT 
        timestamp_utc,
        sensor_pct,
        estimated_pct,
        drift_pct
    FROM fuel_metrics
    WHERE truck_id = 'LC6799'
      AND DATE(timestamp_utc) = '2025-12-20'
      AND TIME(timestamp_utc) BETWEEN '18:20:00' AND '18:30:00'
    ORDER BY timestamp_utc
""")

jump_data = cursor.fetchall()
if jump_data:
    print("\nData around 18:25 (when we saw the jump):")
    for row in jump_data:
        ts, sensor, est, drift = row
        print(f"   {ts}: Sensor={sensor:.1f}%, Kalman={est:.1f}%, Drift={drift:.1f}%")
else:
    print("\n⚠️ No data found around 18:25")

cursor.close()
conn.close()
