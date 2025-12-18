"""
🔍 CHECK FF7702 sensors - Ver qué sensores existen en Wialon vs lo que esperamos
"""

import sys
import pymysql
from datetime import datetime, timedelta
import pytz

# Database config - hardcoded
db_config = {
    "host": "20.127.200.135",
    "user": "read_user",
    "password": "R34d0nly!2024$Secure",
    "database": "wialon_collect",
    "port": 3306,
}

# Buscar unit_id de FF7702
print("🔍 Buscando unit_id de FF7702...")
conn = pymysql.connect(**db_config)
cursor = conn.cursor()

cursor.execute("SELECT beyondId, unit FROM units_map WHERE beyondId = 'FF7702'")
result = cursor.fetchone()

if not result:
    print("❌ FF7702 no encontrado en units_map")
    sys.exit(1)

truck_id, unit_id = result
print(f"✅ FF7702 → unit_id: {unit_id}")

# Ver todos los sensores disponibles
print(f"\n📊 Sensores disponibles en Wialon para FF7702:")
cursor.execute(
    """
    SELECT DISTINCT p
    FROM sensors
    WHERE unit = %s
    ORDER BY p
""",
    (unit_id,),
)

all_sensors = [row[0] for row in cursor.fetchall()]
print(f"\n   Total sensores: {len(all_sensors)}")

# Sensores que el usuario dice que reporta Wialon
target_sensors = ["idle_hours", "barometer", "coolant_temp", "rpm"]
print(f"\n🎯 Buscando sensores específicos: {target_sensors}")

for sensor in target_sensors:
    if sensor in all_sensors:
        print(f"   ✅ {sensor} - EXISTE en Wialon")
    else:
        # Buscar variantes
        variants = [
            s
            for s in all_sensors
            if sensor.lower().replace("_", "") in s.lower().replace("_", "")
        ]
        if variants:
            print(f"   ⚠️ {sensor} - NO existe exacto, pero hay variantes: {variants}")
        else:
            print(f"   ❌ {sensor} - NO existe")

# Ver últimos valores de estos sensores
print(f"\n📈 Últimos valores (última hora):")
utc_now = datetime.now(pytz.UTC)
start_time = utc_now - timedelta(hours=1)

for sensor in all_sensors:
    cursor.execute(
        """
        SELECT value, measure_datetime
        FROM sensors
        WHERE unit = %s AND p = %s
        AND measure_datetime >= %s
        ORDER BY measure_datetime DESC
        LIMIT 1
    """,
        (unit_id, sensor, start_time),
    )

    result = cursor.fetchone()
    if result:
        value, timestamp = result
        age_seconds = (utc_now - timestamp.replace(tzinfo=pytz.UTC)).total_seconds()
        age_minutes = age_seconds / 60
        print(f"   {sensor:30s} = {value:10.2f}  (hace {age_minutes:.1f} min)")

# Revisar SENSOR_PARAMS en wialon_reader.py
print(f"\n🔧 Comparando con SENSOR_PARAMS en código:")
from wialon_reader import SENSOR_PARAMS

for sensor in target_sensors:
    if sensor in SENSOR_PARAMS:
        mapped_name = SENSOR_PARAMS[sensor]
        print(f"   ✅ {sensor:20s} → mapeado como '{mapped_name}'")
        if mapped_name not in all_sensors:
            print(f"      ⚠️ PERO '{mapped_name}' NO existe en Wialon!")
    else:
        print(f"   ❌ {sensor:20s} → NO está en SENSOR_PARAMS")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("📋 LISTA COMPLETA DE SENSORES EN WIALON:")
print("=" * 80)
for i, sensor in enumerate(all_sensors, 1):
    in_params = "✅" if sensor in SENSOR_PARAMS.values() else "❌"
    print(f"   {i:2d}. {in_params} {sensor}")
