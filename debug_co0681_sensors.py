#!/usr/bin/env python3
"""
Debug script - verificar qué sensores tiene CO0681 en Wialon
"""

import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

# Wialon DB connection
wialon_config = {
    "host": os.getenv("WIALON_DB_HOST", "20.127.200.135"),
    "user": os.getenv("WIALON_DB_USER", "tomas"),
    "password": os.getenv("WIALON_DB_PASS", "Tomas2025"),
    "database": "wialon_collect",
    "port": 3306,
}

try:
    conn = pymysql.connect(**wialon_config)
    cursor = conn.cursor()

    # Get unit_id for CO0681
    cursor.execute(
        "SELECT beyondId, unit FROM units_map WHERE beyondId LIKE '%CO0681%' OR beyondId LIKE '%C00681%' OR beyondId LIKE '%CO681%'"
    )
    units = cursor.fetchall()

    if not units:
        print("❌ No se encontró unidad CO0681 en Wialon")
        print("\nBuscando todas las unidades con 'CO' o '681':")
        cursor.execute(
            "SELECT id, nm FROM units WHERE nm LIKE '%CO%' OR nm LIKE '%681%' LIMIT 20"
        )
        for unit_id, name in cursor.fetchall():
            print(f"  {unit_id}: {name}")
        exit(1)

    unit_id, unit_name = units[0]
    print(f"✅ Encontrada unidad: {unit_name} (ID: {unit_id})")

    # Get latest messages with sensor data
    print(f"\n📊 Últimos mensajes con sensores para {unit_name}:")
    cursor.execute(
        """
        SELECT t, p, v 
        FROM wialon_collect.messages 
        WHERE unit_id = %s 
        AND p IN ('oil_lvl', 'oil_level', 'gear', 'pto_hours', 'barometer', 'air_temp', 'cool_lvl')
        AND t > UNIX_TIMESTAMP(NOW() - INTERVAL 24 HOUR)
        ORDER BY t DESC 
        LIMIT 50
    """,
        (unit_id,),
    )

    results = cursor.fetchall()

    if results:
        print(f"\n✅ Encontrados {len(results)} mensajes recientes:")
        sensors_found = {}
        for timestamp, param, value in results:
            if param not in sensors_found:
                sensors_found[param] = value
                from datetime import datetime

                dt = datetime.fromtimestamp(timestamp)
                print(f"  {param:20} = {value:15} (última: {dt})")

        # Check what's in sensors table
        print(f"\n📋 Sensores configurados en tabla 'sensors' para este unit:")
        cursor.execute(
            """
            SELECT s.id, s.nm, s.p 
            FROM sensors s 
            WHERE s.unit_id = %s 
            AND s.p IN ('oil_lvl', 'oil_level', 'gear', 'pto_hours', 'barometer', 'air_temp', 'cool_lvl')
            ORDER BY s.p
        """,
            (unit_id,),
        )

        sensor_configs = cursor.fetchall()
        if sensor_configs:
            print(f"✅ Configurados {len(sensor_configs)} sensores:")
            for sensor_id, sensor_name, param in sensor_configs:
                print(f"  ID {sensor_id:3}: {sensor_name:30} (param: {param})")
        else:
            print("❌ No hay sensores configurados")

    else:
        print(f"❌ No hay mensajes recientes con estos sensores")

        # Check ALL parameters available for this unit
        print(f"\n🔍 Todos los parámetros disponibles últimas 24h:")
        cursor.execute(
            """
            SELECT DISTINCT p, COUNT(*) as count, MAX(v) as last_value
            FROM wialon_collect.messages 
            WHERE unit_id = %s 
            AND t > UNIX_TIMESTAMP(NOW() - INTERVAL 24 HOUR)
            GROUP BY p
            ORDER BY count DESC
            LIMIT 50
        """,
            (unit_id,),
        )

        all_params = cursor.fetchall()
        for param, count, last_val in all_params:
            print(f"  {param:25} ({count:5} msgs) = {last_val}")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback

    traceback.print_exc()
