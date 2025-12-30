"""
🔍 Diagnóstico FF7702 - Comparar nombres de sensores en Wialon vs código
Similar al test DTC pero para sensores generales
"""

import sys
import os

# Add parent directory to path to import wialon_reader
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wialon_reader import WialonReader, TRUCK_UNIT_MAPPING, WialonConfig
from datetime import datetime, timedelta
import pytz

# SENSOR_PARAMS está dentro de WialonConfig
SENSOR_PARAMS = WialonConfig.SENSOR_PARAMS

print("=" * 80)
print("🔍 DIAGNÓSTICO DE SENSORES - FF7702")
print("=" * 80)

# Verificar que FF7702 esté en el mapping
if "FF7702" not in TRUCK_UNIT_MAPPING:
    print("❌ FF7702 no está en TRUCK_UNIT_MAPPING")
    sys.exit(1)

unit_id = TRUCK_UNIT_MAPPING["FF7702"]
print(f"\n✅ FF7702 → unit_id: {unit_id}")

# Crear reader
db_config = WialonConfig()  # Usa variables de entorno
reader = WialonReader(db_config, TRUCK_UNIT_MAPPING)

# Sensores que el usuario menciona
target_sensors = ["idle_hours", "barometer", "coolant_temp", "rpm"]

print(f"\n📋 Sensores mencionados por el usuario:")
for sensor in target_sensors:
    if sensor in SENSOR_PARAMS:
        wialon_name = SENSOR_PARAMS[sensor]
        print(f"   {sensor:20s} → busca '{wialon_name}' en Wialon")
    else:
        print(f"   {sensor:20s} → ❌ NO está en SENSOR_PARAMS")

# Intentar leer datos de FF7702
print(f"\n📊 Intentando leer datos de FF7702...")
try:
    # Usar el método correcto get_all_trucks_data
    truck_data = reader.get_all_trucks_data(["FF7702"])

    if "FF7702" in truck_data and truck_data["FF7702"]:
        data = truck_data["FF7702"]
        print(f"\n✅ Datos recibidos para FF7702:")
        print(f"   Timestamp: {data.timestamp}")
        print(f"   Fuel Level: {data.fuel_lvl}")
        print(f"   Speed: {data.speed}")
        print(f"   RPM: {data.rpm}")
        print(f"   Coolant Temp: {data.coolant_temp}")
        print(f"   Idle Hours: {getattr(data, 'idle_hours', 'N/A')}")
        print(f"   Barometer: {getattr(data, 'barometer', 'N/A')}")

        # Ver todos los atributos disponibles
        print(f"\n📋 Todos los campos del objeto TruckSensorData:")
        for attr in dir(data):
            if not attr.startswith("_"):
                value = getattr(data, attr)
                if value is not None and not callable(value):
                    print(f"   {attr:30s} = {value}")
    else:
        print(f"❌ No se recibieron datos para FF7702")

except Exception as e:
    print(f"❌ Error al leer datos: {e}")
    import traceback

    traceback.print_exc()

# Ahora hacer query directa a Wialon para ver qué sensores tiene FF7702
print(f"\n{'='*80}")
print(f"📊 QUERY DIRECTA A WIALON - Sensores disponibles para FF7702")
print(f"{'='*80}")

import pymysql

try:
    # Conectar usando el config del reader
    conn = pymysql.connect(
        host=reader.config.host,
        port=reader.config.port,
        user=reader.config.user,
        password=reader.config.password,
        database=reader.config.database,
    )
    cursor = conn.cursor()

    # Ver todos los sensores únicos de FF7702
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
    print(f"\n   Total sensores en Wialon: {len(all_sensors)}")

    # Buscar específicamente los que menciona el usuario
    print(f"\n🎯 Buscando sensores específicos:")
    for sensor in target_sensors:
        wialon_name = SENSOR_PARAMS.get(sensor, sensor)
        if sensor in all_sensors:
            print(f"   ✅ {sensor:20s} - EXISTE en Wialon (nombre exacto)")
        elif wialon_name in all_sensors:
            print(f"   ✅ {sensor:20s} - Existe como '{wialon_name}' en Wialon")
        else:
            # Buscar similares
            similar = [
                s
                for s in all_sensors
                if sensor.lower().replace("_", "") in s.lower().replace("_", "")
            ]
            if similar:
                print(f"   ⚠️ {sensor:20s} - NO exacto. Similares: {similar}")
            else:
                print(f"   ❌ {sensor:20s} - NO encontrado en Wialon")

    # Ver últimos valores
    print(f"\n📈 Últimos valores (última hora):")
    utc_now = datetime.now(pytz.UTC)
    start_time = utc_now - timedelta(hours=1)

    for sensor in target_sensors:
        wialon_name = SENSOR_PARAMS.get(sensor, sensor)
        # Intentar con nombre mapeado primero
        cursor.execute(
            """
            SELECT value, measure_datetime
            FROM sensors
            WHERE unit = %s AND p = %s
            AND measure_datetime >= %s
            ORDER BY measure_datetime DESC
            LIMIT 1
        """,
            (unit_id, wialon_name, start_time),
        )

        result = cursor.fetchone()
        if result:
            value, timestamp = result
            age_seconds = (utc_now - timestamp.replace(tzinfo=pytz.UTC)).total_seconds()
            age_minutes = age_seconds / 60
            print(
                f"   ✅ {sensor:20s} ({wialon_name:20s}) = {value:10.2f}  (hace {age_minutes:.1f} min)"
            )
        else:
            # Intentar con nombre directo
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
                age_seconds = (
                    utc_now - timestamp.replace(tzinfo=pytz.UTC)
                ).total_seconds()
                age_minutes = age_seconds / 60
                print(
                    f"   ⚠️ {sensor:20s} (nombre directo)       = {value:10.2f}  (hace {age_minutes:.1f} min)"
                )
                print(
                    f"      → PROBLEMA: Código busca '{wialon_name}' pero existe como '{sensor}'"
                )
            else:
                print(f"   ❌ {sensor:20s} - Sin datos recientes")

    # Listar TODOS los sensores para análisis completo
    print(f"\n{'='*80}")
    print(f"📋 LISTA COMPLETA DE SENSORES EN WIALON PARA FF7702:")
    print(f"{'='*80}")
    for i, sensor in enumerate(all_sensors, 1):
        in_params = "✅" if sensor in SENSOR_PARAMS.values() else "❌"
        print(f"   {i:2d}. {in_params} {sensor}")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Error en query directa: {e}")
    import traceback

    traceback.print_exc()

print(f"\n{'='*80}")
print(f"🔍 DIAGNÓSTICO COMPLETADO")
print(f"{'='*80}")
