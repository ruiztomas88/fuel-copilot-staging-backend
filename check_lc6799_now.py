import mysql.connector
from datetime import datetime, timezone

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password="FuelCopilot2025!",
    database="fuel_copilot"
)
cursor = conn.cursor(dictionary=True)

cursor.execute("""
    SELECT timestamp, oil_pressure_psi, fuel_level_pct, rpm, 
           coolant_temp_f, oil_temp_f, engine_load_pct
    FROM truck_sensors_cache
    WHERE truck_id = 'LH1141'
    ORDER BY timestamp DESC
    LIMIT 1
""")
r = cursor.fetchone()

print(f"\nLH1141 Current Data:")
print(f"  Timestamp: {r['timestamp']}")
print(f"  oil_pressure: {r['oil_pressure_psi']}")
print(f"  fuel_level: {r['fuel_level_pct']}")
print(f"  rpm: {r['rpm']}")
print(f"  coolant_temp: {r['coolant_temp_f']}")
print(f"  oil_temp: {r['oil_temp_f']}")
print(f"  engine_load: {r['engine_load_pct']}")

# Check age
ts = r['timestamp']
if ts.tzinfo is None:
    ts = ts.replace(tzinfo=timezone.utc)
age_sec = (datetime.now(timezone.utc) - ts).total_seconds()
print(f"  Age: {age_sec:.0f} seconds\n")

cursor.close()
conn.close()
