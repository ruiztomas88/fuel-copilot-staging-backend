#!/usr/bin/env python3
"""Revisar estructura y datos de tabla sensors en Wialon"""
from datetime import datetime

import pymysql

WIALON_DB = {
    "host": "20.127.200.135",
    "port": 3306,
    "user": "tomas",
    "password": "Tomas2025",
    "database": "wialon_collect",
}


def check_sensors_structure():
    """Ver estructura de tabla sensors"""
    print("=" * 80)
    print("📋 ESTRUCTURA DE TABLA 'sensors'")
    print("=" * 80)

    conn = pymysql.connect(**WIALON_DB)
    cursor = conn.cursor()

    cursor.execute("DESCRIBE sensors")
    columns = cursor.fetchall()
    print("\nColumnas:")
    for col in columns:
        print(f"  {col[0]:20} {col[1]:20} {col[2]}")

    cursor.close()
    conn.close()


def check_units_map():
    """Ver mapeo de trucks a unit_ids"""
    print("\n" + "=" * 80)
    print("🗺️ TABLA units_map (truck_id → unit_id)")
    print("=" * 80)

    conn = pymysql.connect(**WIALON_DB)
    cursor = conn.cursor()

    cursor.execute("DESCRIBE units_map")
    columns = cursor.fetchall()
    print("\nColumnas:")
    for col in columns:
        print(f"  {col[0]:20} {col[1]:20}")

    print("\n🔍 Buscando DO9693...")
    cursor.execute("SELECT * FROM units_map WHERE beyondId = 'DO9693'")
    result = cursor.fetchone()

    if result:
        print(f"✅ ENCONTRADO: {result}")
        return result
    else:
        print("❌ NO encontrado. Mostrando todos los trucks:")
        cursor.execute("SELECT * FROM units_map ORDER BY beyondId LIMIT 20")
        all_units = cursor.fetchall()
        for u in all_units:
            print(f"  {u}")

    cursor.close()
    conn.close()
    return result


def check_recent_sensors(unit_id=None):
    """Ver datos recientes en tabla sensors"""
    print("\n" + "=" * 80)
    print("📊 DATOS RECIENTES EN TABLA sensors")
    print("=" * 80)

    conn = pymysql.connect(**WIALON_DB)
    cursor = conn.cursor()

    if unit_id:
        query = f"""
            SELECT unit, p, value, measure_datetime
            FROM sensors
            WHERE unit = {unit_id}
              AND measure_datetime > NOW() - INTERVAL 30 MINUTE
            ORDER BY measure_datetime DESC
            LIMIT 100
        """
        print(f"\n🔍 Sensores para unit_id={unit_id} (DO9693) - últimos 30 minutos:")
    else:
        query = """
            SELECT unit, p, value, measure_datetime
            FROM sensors
            WHERE measure_datetime > NOW() - INTERVAL 30 MINUTE
            ORDER BY measure_datetime DESC
            LIMIT 50
        """
        print("\n🔍 Últimos 50 sensores (todos los trucks):")

    cursor.execute(query)
    results = cursor.fetchall()

    if results:
        print(f"✅ {len(results)} lecturas encontradas:\n")
        current_unit = None
        sensor_values = {}
        for unit, param, value, ts in results:
            if param not in sensor_values:
                sensor_values[param] = value
                print(f"  {param:40} = {value:15}  ({ts})")
    else:
        print("❌ Sin datos recientes")

    # Ver qué sensores están disponibles
    print("\n" + "=" * 80)
    print("📋 TIPOS DE SENSORES DISPONIBLES (últimas 24h)")
    print("=" * 80)

    cursor.execute(
        """
        SELECT DISTINCT p, COUNT(*) as count
        FROM sensors
        WHERE measure_datetime > NOW() - INTERVAL 24 HOUR
        GROUP BY p
        ORDER BY count DESC
    """
    )
    sensor_types = cursor.fetchall()

    print(f"\n✅ {len(sensor_types)} tipos de sensores activos:\n")
    for param, count in sensor_types:
        print(f"  {param:40} ({count:,} lecturas)")

    cursor.close()
    conn.close()


def main():
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 20 + "WIALON SENSORS AUDIT" + " " * 34 + "║")
    print("╚" + "=" * 78 + "╝\n")

    try:
        # 1. Ver estructura
        check_sensors_structure()

        # 2. Encontrar unit_id de DO9693
        unit_info = check_units_map()

        # 3. Ver datos recientes
        if unit_info:
            unit_id = unit_info[1] if len(unit_info) > 1 else unit_info[0]
            check_recent_sensors(unit_id)
        else:
            check_recent_sensors()

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
