from datetime import datetime, timedelta

import pymysql

# Connect to Wialon DB
conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password="Tomas2025",
    database="fuel_copilot_wialon",
    cursorclass=pymysql.cursors.DictCursor,
)

# Get LC6799 unit_id
unit_id = 402033131

# Query last 10 minutes
query = """
    SELECT timestamp, sensor_name, sensor_value 
    FROM sensor_readings 
    WHERE unit_id = %s 
    AND timestamp >= DATE_SUB(NOW(), INTERVAL 10 MINUTE)
    ORDER BY timestamp DESC
    LIMIT 200
"""

with conn.cursor() as cursor:
    cursor.execute(query, (unit_id,))
    results = cursor.fetchall()

    print(f"Total readings for LC6799 in last 10 min: {len(results)}")
    print()

    # Group by sensor_name
    sensors = {}
    for row in results:
        sensor = row["sensor_name"]
        if sensor not in sensors:
            sensors[sensor] = []
        sensors[sensor].append((row["timestamp"], row["sensor_value"]))

    print("Sensors reporting:")
    for sensor, values in sorted(sensors.items()):
        last_value = values[0][1] if values else None
        count = len(values)
        print(f"  {sensor}: {count} readings, latest={last_value}")

    # Check specific sensors
    print()
    print("CRITICAL SENSORS:")
    for sensor in ["gear", "odometer", "speed", "fuel_lvl", "rpm"]:
        if sensor in sensors:
            latest = sensors[sensor][0]
            print(f"  ✓ {sensor}: {latest[1]} (at {latest[0]})")
        else:
            print(f"  ✗ {sensor}: NOT FOUND")

conn.close()
