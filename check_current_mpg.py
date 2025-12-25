"""Check current MPG and consumption values"""

import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

conn = pymysql.connect(
    host="localhost",
    user=os.getenv("DB_USER"),
    password=os.getenv("DB_PASS"),
    database="fuel_copilot_local",
    port=int(os.getenv("DB_PORT", 3307)),
)

cursor = conn.cursor()

# Get recent MPG and consumption values
query = """
SELECT truck_id, mpg_instantaneous, consumption_gph, idle_gph, timestamp
FROM daily_metrics
WHERE timestamp > DATE_SUB(NOW(), INTERVAL 7 DAY)
  AND truck_id IN ("JC1282", "RH1522", "KW1620", "FLD1410")
  AND mpg_instantaneous IS NOT NULL
ORDER BY timestamp DESC
LIMIT 20
"""

cursor.execute(query)
rows = cursor.fetchall()

print("\n" + "=" * 100)
print("CURRENT MPG AND CONSUMPTION VALUES (Last 7 days)")
print("=" * 100)
print(f'{"Truck":<10} {"MPG":<10} {"Consumption":<15} {"Idle GPH":<12} {"Timestamp"}')
print("-" * 100)

for row in rows:
    truck, mpg, consumption, idle, ts = row
    idle_str = f"{idle:.2f}" if idle else "N/A"
    print(f"{truck:<10} {mpg:<10.2f} {consumption:<15.2f} {idle_str:<12} {ts}")

print("\n" + "=" * 100)
print("EXPECTED VALUES for heavy-duty loaded trucks:")
print("  MPG: 4.5 - 6.0 (NOT 7.8-8.2)")
print("  Consumption: 10-15 gph highway, 15-25 gph loaded hills")
print("  Idle: 0.6 - 1.5 gph (NOT 0.16-0.65)")
print("=" * 100)

conn.close()
