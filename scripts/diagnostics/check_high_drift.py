import pymysql
from datetime import datetime

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password=os.getenv("DB_PASSWORD"),
    database='fuel_copilot'
)
cursor = conn.cursor()

print("=" * 80)
print("TRUCKS WITH HIGH DRIFT (>5%) - LAST 24 HOURS")
print("=" * 80)

# Get latest reading per truck with high drift
cursor.execute("""
    SELECT 
        truck_id,
        MAX(timestamp_utc) as last_update,
        sensor_pct,
        estimated_pct,
        drift_pct
    FROM fuel_metrics
    WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 24 HOUR)
      AND ABS(drift_pct) > 5.0
    GROUP BY truck_id
    ORDER BY ABS(drift_pct) DESC
    LIMIT 20
""")
import os

rows = cursor.fetchall()
if rows:
    print(f"\n{'Truck':<10} {'Last Update':<20} {'Sensor':<10} {'Kalman':<10} {'Drift':<10}")
    print("-" * 70)
    for row in rows:
        truck_id, last_update, sensor, kalman, drift = row
        sensor_str = f"{sensor:.1f}%" if sensor else "None"
        kalman_str = f"{kalman:.1f}%" if kalman else "None"
        drift_str = f"{drift:.1f}%" if drift else "None"
        print(f"{truck_id:<10} {str(last_update):<20} {sensor_str:<10} {kalman_str:<10} {drift_str:<10}")
else:
    print("\n✅ No trucks with drift >5% in last 24 hours")

print("\n" + "=" * 80)
print("TRUCKS WITH DRIFT >10% (CRITICAL)")
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
    ) latest
    WHERE rn = 1 AND ABS(drift_pct) > 10.0
    ORDER BY ABS(drift_pct) DESC
""")

critical = cursor.fetchall()
if critical:
    print(f"\n⚠️ Found {len(critical)} truck(s) with CRITICAL drift >10%:")
    for row in critical:
        truck_id, ts, sensor, kalman, drift = row
        print(f"   🚨 {truck_id}: Sensor={sensor:.1f}%, Kalman={kalman:.1f}%, Drift={drift:.1f}%")
else:
    print("\n✅ No trucks with drift >10%")

cursor.close()
conn.close()
