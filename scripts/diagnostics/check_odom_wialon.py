#!/usr/bin/env python3
"""
Verificar cobertura de odómetro en Wialon para camiones MOVING
"""
import time
from datetime import datetime

import pymysql

print("Conectando a Wialon...")
conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password="Tomas2025",
    database="wialon_collect",
    cursorclass=pymysql.cursors.DictCursor,
    connect_timeout=15,
)
print("✅ Conexión exitosa\n")

cursor = conn.cursor()
cutoff = int(time.time()) - (24 * 3600)

trucks = [("MR7679", 401961893), ("CO0681", 401961886), ("DO9693", 401961877)]

print("=" * 90)
print("🔍 ANÁLISIS DE ODÓMETRO EN WIALON - ÚLTIMAS 24 HORAS")
print("=" * 90)

for truck_id, unit_id in trucks:
    print(f"\n🚛 {truck_id} (unit {unit_id}):")

    # Total de registros MOVING
    cursor.execute(
        """
        SELECT COUNT(*) as total 
        FROM sensors 
        WHERE unit = %s 
            AND m >= %s 
            AND p = "speed" 
            AND value > 10
    """,
        (unit_id, cutoff),
    )
    moving = cursor.fetchone()["total"]

    # Registros con odómetro
    cursor.execute(
        """
        SELECT COUNT(*) as odom 
        FROM sensors 
        WHERE unit = %s 
            AND m >= %s 
            AND p = "odom" 
            AND value > 0
    """,
        (unit_id, cutoff),
    )
    odom = cursor.fetchone()["odom"]

    pct = (odom / moving * 100) if moving > 0 else 0

    print(f"   Registros MOVING (speed>10): {moving:,}")
    print(f"   Registros con odómetro:      {odom:,}")
    print(f"   Cobertura:                   {pct:.1f}%")

    # Muestra de valores recientes
    if odom > 0:
        cursor.execute(
            """
            SELECT value, FROM_UNIXTIME(m) as ts 
            FROM sensors 
            WHERE unit = %s 
                AND m >= %s 
                AND p = "odom" 
            ORDER BY m DESC 
            LIMIT 3
        """,
            (unit_id, cutoff),
        )
        samples = cursor.fetchall()
        print(f"   Últimos 3 valores:")
        for s in samples:
            print(f"      {s['ts']}: {s['value']:,.1f} mi")
    else:
        print(f"   ❌ NO HAY DATOS DE ODÓMETRO")

conn.close()
print("\n" + "=" * 90)
print("✅ Análisis completado")
print("=" * 90)
