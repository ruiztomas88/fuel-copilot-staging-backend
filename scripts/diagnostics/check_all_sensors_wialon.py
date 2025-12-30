#!/usr/bin/env python3
"""
Revisar TODOS los sensores únicos disponibles en Wialon
para encontrar si existe gear/transmission o cualquier sensor relacionado
"""
from collections import defaultdict

import pymysql

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

    print("=" * 80)
    print("TODOS LOS SENSORES ÚNICOS DISPONIBLES EN WIALON")
    print("=" * 80)

    # Obtener todos los sensores únicos
    cursor.execute(
        """
        SELECT DISTINCT sensor_id, n as name, p as parameter, type
        FROM sensors
        WHERE n IS NOT NULL AND n != ''
        ORDER BY CAST(sensor_id AS UNSIGNED)
    """
    )

    all_sensors = cursor.fetchall()

    print(f"\n✅ Total de sensores únicos: {len(all_sensors)}\n")

    # Agrupar por sensor_id para ver nombres alternativos
    sensors_by_id = defaultdict(set)
    for s in all_sensors:
        sensors_by_id[s["sensor_id"]].add((s["name"], s["parameter"], s["type"]))

    print("LISTADO COMPLETO DE SENSORES:")
    print("-" * 80)
    for sensor_id in sorted(
        sensors_by_id.keys(), key=lambda x: int(x) if x.isdigit() else 999
    ):
        variations = sensors_by_id[sensor_id]
        print(f"\nID {sensor_id}:")
        for name, param, stype in sorted(variations):
            print(f"  - Nombre: '{name}' | Parámetro: '{param}' | Tipo: {stype}")

    # Búsqueda específica de GEAR/TRANSMISSION
    print("\n" + "=" * 80)
    print("BÚSQUEDA ESPECÍFICA: GEAR / TRANSMISSION")
    print("=" * 80)

    cursor.execute(
        """
        SELECT DISTINCT sensor_id, n as name, p as parameter, type
        FROM sensors
        WHERE LOWER(n) LIKE '%gear%' 
           OR LOWER(p) LIKE '%gear%'
           OR LOWER(n) LIKE '%trans%'
           OR LOWER(p) LIKE '%trans%'
           OR LOWER(n) LIKE '%shift%'
           OR LOWER(p) LIKE '%shift%'
        ORDER BY sensor_id
    """
    )

    gear_sensors = cursor.fetchall()

    if gear_sensors:
        print(f"✅ ENCONTRADOS {len(gear_sensors)} sensores relacionados con GEAR:\n")
        for s in gear_sensors:
            print(f"  Sensor ID: {s['sensor_id']}")
            print(f"  Nombre: {s['name']}")
            print(f"  Parámetro: {s['parameter']}")
            print(f"  Tipo: {s['type']}\n")

        # Ver cuántos trucks tienen este sensor
        for s in gear_sensors:
            cursor.execute(
                """
                SELECT COUNT(DISTINCT unit) as truck_count
                FROM sensors
                WHERE sensor_id = %s
            """,
                (s["sensor_id"],),
            )
            count = cursor.fetchone()["truck_count"]
            print(f"  → Sensor {s['sensor_id']} disponible en {count} trucks")
    else:
        print("❌ NO se encontraron sensores relacionados con GEAR/TRANSMISSION")

    # Búsqueda de sensores similares (speed, rpm, etc)
    print("\n" + "=" * 80)
    print("SENSORES RELACIONADOS QUE PODRÍAN AYUDAR A CALCULAR GEAR:")
    print("=" * 80)

    cursor.execute(
        """
        SELECT DISTINCT sensor_id, n as name, p as parameter
        FROM sensors
        WHERE LOWER(n) LIKE '%speed%'
           OR LOWER(n) LIKE '%rpm%'
           OR LOWER(p) LIKE '%speed%'
           OR LOWER(p) LIKE '%rpm%'
        ORDER BY sensor_id
    """
    )

    related = cursor.fetchall()
    print(f"✅ Sensores de Speed/RPM disponibles ({len(related)}):\n")
    for s in related:
        print(f"  ID {s['sensor_id']}: {s['name']} (param: {s['parameter']})")

    # Contar trucks con cada sensor
    print("\n" + "=" * 80)
    print("DISPONIBILIDAD DE SENSORES CLAVE POR TRUCK:")
    print("=" * 80)

    key_sensors = {
        "30": "Odometer",
        "37": "RPM",
        "22": "GPS Speed",
        "18": "Fuel Level",
        "19": "Fuel Rate",
    }

    for sid, sname in key_sensors.items():
        cursor.execute(
            """
            SELECT COUNT(DISTINCT unit) as truck_count
            FROM sensors
            WHERE sensor_id = %s
        """,
            (sid,),
        )
        count = cursor.fetchone()["truck_count"]
        print(f"  {sname} (ID {sid}): {count} trucks")

finally:
    conn.close()
