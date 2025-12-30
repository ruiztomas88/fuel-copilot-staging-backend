"""
🔍 Verificar qué está guardado en la base de datos local para FF7702
"""

import pymysql
from datetime import datetime, timedelta

# Conectar a base de datos local
conn = pymysql.connect(
    host="localhost",
    user="root",
    password="your_password",  # Update this
    database="fuel_copilot",
    port=3306,
)

cursor = conn.cursor(pymysql.cursors.DictCursor)

print("=" * 80)
print("🔍 VERIFICAR DATOS LOCAL - FF7702")
print("=" * 80)

# Ver últimos registros de FF7702
cursor.execute(
    """
    SELECT
        truck_id,
        timestamp,
        fuel_level_pct,
        speed_mph,
        rpm,
        coolant_temp_f,
        idle_hours,
        barometer_kpa,
        engine_load_pct
    FROM fuel_monitoring
    WHERE truck_id = 'FF7702'
    ORDER BY timestamp DESC
    LIMIT 10
"""
)

results = cursor.fetchall()

if results:
    print(f"\n✅ Últimos 10 registros de FF7702 en fuel_monitoring:")
    for i, row in enumerate(results, 1):
        print(f"\n   {i}. Timestamp: {row['timestamp']}")
        print(f"      Fuel Level: {row['fuel_level_pct']}")
        print(f"      Speed: {row['speed_mph']}")
        print(f"      RPM: {row['rpm']}")
        print(f"      Coolant Temp: {row['coolant_temp_f']}")
        print(f"      Idle Hours: {row['idle_hours']}")
        print(f"      Barometer: {row['barometer_kpa']}")
        print(f"      Engine Load: {row['engine_load_pct']}")
else:
    print(f"\n❌ No hay registros para FF7702 en fuel_monitoring")

cursor.close()
conn.close()
