#!/usr/bin/env python3
"""
Buscar específicamente odometer y gear en tabla sensors
Y comparar frecuencia de actualización entre sensors y trips
"""
from datetime import datetime

import pymysql

# Conexión a Wialon
conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password="Tomas2025",
    database="wialon_collect",
    cursorclass=pymysql.cursors.DictCursor,
)

try:
    cursor = conn.cursor()

    # Buscar JB6858 unit ID
    print("=" * 80)
    print("BUSCANDO UNIT ID DE JB6858")
    print("=" * 80)
    cursor.execute("SELECT DISTINCT unit FROM sensors LIMIT 10")
    units = cursor.fetchall()
    print(f"Primeras 10 units: {[u['unit'] for u in units]}")

    # Asumir que JB6858 es 401016899 (del análisis anterior)
    unit_id = 401016899
    print(f"\nUsando unit_id: {unit_id}")

    # 1. BUSCAR TODOS LOS SENSORES CON "ODO" O "GEAR" EN EL NOMBRE
    print("\n" + "=" * 80)
    print("1. BÚSQUEDA EN SENSORS: ODOMETER")
    print("=" * 80)

    cursor.execute(
        """
        SELECT sensor_id, n as name, p as parameter, type, value, counter, 
               measure_datetime
        FROM sensors 
        WHERE unit = %s 
        AND (LOWER(n) LIKE '%%odo%%' OR LOWER(p) LIKE '%%odo%%'
             OR LOWER(n) LIKE '%%mile%%' OR LOWER(p) LIKE '%%mile%%')
        ORDER BY sensor_id
    """,
        (unit_id,),
    )

    odometer_sensors = cursor.fetchall()
    if odometer_sensors:
        print(
            f"✅ Encontrados {len(odometer_sensors)} sensores relacionados con odometer:"
        )
        for s in odometer_sensors:
            print(f"\n  Sensor ID: {s['sensor_id']}")
            print(f"  Nombre: {s['name']}")
            print(f"  Parámetro: {s['parameter']}")
            print(f"  Tipo: {s['type']}")
            print(f"  Valor: {s['value']}")
            print(f"  Counter: {s['counter']}")
            print(f"  Última actualización: {s['measure_datetime']}")
    else:
        print("❌ NO encontrado odometer en tabla sensors")

    # 2. BUSCAR GEAR
    print("\n" + "=" * 80)
    print("2. BÚSQUEDA EN SENSORS: GEAR")
    print("=" * 80)

    cursor.execute(
        """
        SELECT sensor_id, n as name, p as parameter, type, value, counter,
               measure_datetime
        FROM sensors 
        WHERE unit = %s 
        AND (LOWER(n) LIKE '%%gear%%' OR LOWER(p) LIKE '%%gear%%'
             OR LOWER(n) LIKE '%%trans%%' OR LOWER(p) LIKE '%%trans%%')
        ORDER BY sensor_id
    """,
        (unit_id,),
    )

    gear_sensors = cursor.fetchall()
    if gear_sensors:
        print(f"✅ Encontrados {len(gear_sensors)} sensores relacionados con gear:")
        for s in gear_sensors:
            print(f"\n  Sensor ID: {s['sensor_id']}")
            print(f"  Nombre: {s['name']}")
            print(f"  Parámetro: {s['parameter']}")
            print(f"  Tipo: {s['type']}")
            print(f"  Valor: {s['value']}")
            print(f"  Counter: {s['counter']}")
            print(f"  Última actualización: {s['measure_datetime']}")
    else:
        print("❌ NO encontrado gear en tabla sensors")

    # 3. COMPARAR FRECUENCIA DE ACTUALIZACIÓN
    print("\n" + "=" * 80)
    print("3. COMPARACIÓN DE FRECUENCIA DE ACTUALIZACIÓN")
    print("=" * 80)

    # Última actualización en SENSORS
    cursor.execute(
        """
        SELECT MAX(measure_datetime) as last_update
        FROM sensors
        WHERE unit = %s
    """,
        (unit_id,),
    )
    sensors_last = cursor.fetchone()

    # Última actualización en TRIPS
    cursor.execute(
        """
        SELECT MAX(measure_datetime) as last_update
        FROM trips
        WHERE unit = %s
    """,
        (unit_id,),
    )
    trips_last = cursor.fetchone()

    print(f"\n📊 SENSORS última actualización: {sensors_last['last_update']}")
    print(f"📊 TRIPS última actualización: {trips_last['last_update']}")

    # Contar registros de las últimas 24 horas
    cursor.execute(
        """
        SELECT COUNT(*) as count
        FROM sensors
        WHERE unit = %s
        AND measure_datetime >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
    """,
        (unit_id,),
    )
    sensors_count = cursor.fetchone()["count"]

    cursor.execute(
        """
        SELECT COUNT(*) as count
        FROM trips
        WHERE unit = %s
        AND measure_datetime >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
    """,
        (unit_id,),
    )
    trips_count = cursor.fetchone()["count"]

    print(f"\n📈 Actualizaciones en últimas 24 horas:")
    print(f"   SENSORS: {sensors_count} registros")
    print(f"   TRIPS: {trips_count} registros")

    # Ver ejemplo de timestamps en SENSORS
    print("\n" + "=" * 80)
    print("4. TIMESTAMPS RECIENTES EN SENSORS (últimos 10)")
    print("=" * 80)
    cursor.execute(
        """
        SELECT sensor_id, n, measure_datetime
        FROM sensors
        WHERE unit = %s
        ORDER BY measure_datetime DESC
        LIMIT 10
    """,
        (unit_id,),
    )
    recent_sensors = cursor.fetchall()
    for s in recent_sensors:
        print(f"  {s['measure_datetime']} - Sensor {s['sensor_id']} ({s['n']})")

    # Ver ejemplo de timestamps en TRIPS
    print("\n" + "=" * 80)
    print("5. TIMESTAMPS RECIENTES EN TRIPS (últimos 10)")
    print("=" * 80)
    cursor.execute(
        """
        SELECT odometer, measure_datetime, distance_miles, state
        FROM trips
        WHERE unit = %s
        ORDER BY measure_datetime DESC
        LIMIT 10
    """,
        (unit_id,),
    )
    recent_trips = cursor.fetchall()
    for t in recent_trips:
        print(
            f"  {t['measure_datetime']} - Odometer: {t['odometer']}, Distance: {t['distance_miles']} mi, State: {t['state']}"
        )

    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)
    print(
        f"✅ SENSORS se actualiza cada: ~{1440 / sensors_count if sensors_count > 0 else 'N/A'} minutos (basado en 24h)"
    )
    print(
        f"✅ TRIPS se actualiza cada: ~{1440 / trips_count if trips_count > 0 else 'N/A'} minutos (basado en 24h)"
    )

    if sensors_count > trips_count:
        print(
            f"\n🏆 SENSORS es {sensors_count / trips_count if trips_count > 0 else 'N/A'}x MÁS FRECUENTE que TRIPS"
        )
    else:
        print(
            f"\n🏆 TRIPS es {trips_count / sensors_count if sensors_count > 0 else 'N/A'}x MÁS FRECUENTE que SENSORS"
        )

finally:
    conn.close()
