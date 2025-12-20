import pymysql
from datetime import datetime

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor(pymysql.cursors.DictCursor)

cursor.execute("""
    SELECT truck_id, timestamp, data_age_seconds,
           rpm, speed_mph, odometer_mi, fuel_level_pct
    FROM truck_sensors_cache
    WHERE timestamp > DATE_SUB(NOW(), INTERVAL 5 MINUTE)
    ORDER BY timestamp DESC
    LIMIT 10
""")

results = cursor.fetchall()
print('=' * 60)
print('ÚLTIMAS ACTUALIZACIONES truck_sensors_cache')
print('=' * 60)

if results:
    for r in results:
        print(f"{r['truck_id']}: {r['timestamp']} | RPM={r['rpm']}, Speed={r['speed_mph']}, Odom={r['odometer_mi']}")
    print(f'\n✅ Total actualizaciones recientes: {len(results)}')
else:
    print('❌ NO HAY ACTUALIZACIONES RECIENTES')

conn.close()
