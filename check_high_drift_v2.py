import pymysql

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor()

print("=" * 80)
print("TRUCKS WITH DRIFT >5% (LATEST READING)")
print("=" * 80)

cursor.execute("""
    SELECT 
        truck_id,
        timestamp_utc,
        sensor_pct,
        estimated_pct,
        drift_pct
    FROM (
        SELECT *,
               ROW_NUMBER() OVER (PARTITION BY truck_id ORDER BY timestamp_utc DESC) as rn
        FROM fuel_metrics
        WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 24 HOUR)
          AND ABS(drift_pct) > 5.0
    ) latest
    WHERE rn = 1
    ORDER BY ABS(drift_pct) DESC
""")

rows = cursor.fetchall()
if rows:
    print(f"\n{'Truck':<10} {'Last Update':<20} {'Sensor':<10} {'Kalman':<10} {'Drift':<10}")
    print("-" * 70)
    for row in rows:
        truck_id, ts, sensor, kalman, drift = row
        sensor_str = f"{sensor:.1f}%" if sensor else "None"
        kalman_str = f"{kalman:.1f}%" if kalman else "None"
        drift_str = f"{drift:.1f}%" if drift else "None"
        alert = "🚨" if abs(drift) > 10 else "⚠️"
        print(f"{alert} {truck_id:<10} {str(ts):<20} {sensor_str:<10} {kalman_str:<10} {drift_str:<10}")
    
    # Count by severity
    critical = sum(1 for r in rows if abs(r[4]) > 10)
    high = sum(1 for r in rows if 5 < abs(r[4]) <= 10)
    print(f"\n📊 Summary: {critical} CRITICAL (>10%), {high} HIGH (5-10%)")
else:
    print("\n✅ No trucks with drift >5% in last 24 hours")

cursor.close()
conn.close()
