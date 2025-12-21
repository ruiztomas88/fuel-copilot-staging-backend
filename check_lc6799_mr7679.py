import pymysql
from datetime import datetime, timedelta

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor()

trucks = ['LC6799', 'MR7679']
today = datetime.now().date()

for truck_id in trucks:
    print("=" * 80)
    print(f"{truck_id} - FUEL DATA TODAY ({today})")
    print("=" * 80)
    
    cursor.execute("""
        SELECT timestamp_utc, sensor_pct, kalman_pct, drift_pct
        FROM fuel_metrics
        WHERE truck_id = %s
          AND DATE(timestamp_utc) = %s
        ORDER BY timestamp_utc ASC
    """, (truck_id, today))
    
    rows = cursor.fetchall()
    if not rows:
        print(f"  ⚠️ NO DATA for {truck_id} today!")
        continue
    
    print(f"  {'Timestamp':<20} {'Sensor %':<10} {'Kalman %':<10} {'Drift %':<10}")
    print("-" * 60)
    
    prev_sensor = None
    for row in rows:
        ts, sensor, kalman, drift = row
        sensor_str = f"{sensor:.1f}%" if sensor is not None else "None"
        kalman_str = f"{kalman:.1f}%" if kalman is not None else "None"
        drift_str = f"{drift:.1f}%" if drift is not None else "None"
        
        # Detect potential refuel (big jump in sensor)
        jump_str = ""
        if prev_sensor is not None and sensor is not None:
            jump = sensor - prev_sensor
            if jump > 10:
                jump_str = f" 🚨 JUMP: +{jump:.1f}% (+{jump*2:.0f} gal)"
        
        print(f"  {ts} {sensor_str:<10} {kalman_str:<10} {drift_str:<10}{jump_str}")
        prev_sensor = sensor
    
    # Check last 48 hours for context
    print(f"\n  LAST 48 HOURS (for context):")
    print("-" * 60)
    cursor.execute("""
        SELECT timestamp_utc, sensor_pct, kalman_pct, drift_pct
        FROM fuel_metrics
        WHERE truck_id = %s
          AND timestamp_utc > DATE_SUB(NOW(), INTERVAL 48 HOUR)
        ORDER BY timestamp_utc ASC
    """, (truck_id,))
    
    last_48h = cursor.fetchall()
    if last_48h:
        print(f"  Total records: {len(last_48h)}")
        first = last_48h[0]
        last = last_48h[-1]
        print(f"  First: {first[0]} - Sensor={first[1]:.1f}%, Kalman={first[2]:.1f}%")
        print(f"  Last:  {last[0]} - Sensor={last[1]:.1f}%, Kalman={last[2]:.1f}%, Drift={last[3]:.1f}%")
    
    print()

cursor.close()
conn.close()
