"""Check LC6799 data in database"""
import mysql.connector
from datetime import datetime, timezone
import os

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "fuel_admin"),
    password=os.getenv("DB_PASSWORD"),  # 🔒 Security fix: No hardcoded credentials
    database=os.getenv("DB_NAME", "fuel_copilot")
)
cursor = conn.cursor(dictionary=True)

# Check latest update for LC6799 in truck_sensors_cache
cursor.execute("""
    SELECT timestamp, oil_pressure_psi, fuel_lvl_pct, rpm, 
           coolant_temp_f, oil_temp_f, engine_load_pct, def_level_pct
    FROM truck_sensors_cache
    WHERE truck_id = 'LC6799'
    ORDER BY timestamp DESC
    LIMIT 1
""")
result = cursor.fetchone()

print("="*70)
print("LC6799 Latest Data in truck_sensors_cache:")
print("="*70)

if result:
    for key, value in result.items():
        print(f"{key:20s}: {value}")
    
    # Check how recent it is
    ts = result['timestamp']
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    age_seconds = (datetime.now(timezone.utc) - ts).total_seconds()
    print(f"\nData age: {age_seconds:.0f} seconds ({age_seconds/60:.1f} minutes)")
else:
    print("ERROR: No data found for LC6799!")

cursor.close()
conn.close()
