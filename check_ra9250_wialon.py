#!/usr/bin/env python3
"""
Análisis específico de RA9250 - Comparación Wialon vs Dashboard
"""
import os
from datetime import datetime

import pymysql
from dotenv import load_dotenv

load_dotenv()


def analyze_ra9250():
    print("\n" + "=" * 80)
    print("🔬 ANÁLISIS ESPECÍFICO: RA9250")
    print("=" * 80)

    # Conectar a Wialon DB
    print("\n📡 WIALON DATABASE (Fuente de verdad)")
    print("-" * 80)

    wialon_conn = pymysql.connect(
        host="20.127.200.135",
        port=3306,
        user="tomas",
        password=os.getenv("WIALON_DB_PASS"),
        database="wialon_collect",
        charset="utf8mb4",
    )

    cursor = wialon_conn.cursor(pymysql.cursors.DictCursor)

    # Buscar unit de RA9250
    cursor.execute(
        """
        SELECT id, name FROM units WHERE name LIKE '%RA9250%'
    """
    )
    unit = cursor.fetchone()

    if not unit:
        print("❌ RA9250 NO encontrado en Wialon")
        return

    print(f"✅ Unit encontrado: {unit['name']} (ID: {unit['id']})")

    # Último mensaje
    cursor.execute(
        """
        SELECT 
            FROM_UNIXTIME(time) as timestamp,
            TIMESTAMPDIFF(MINUTE, FROM_UNIXTIME(time), NOW()) as age_min,
            speed,
            lat,
            lon
        FROM messages
        WHERE unit_id = %s
        ORDER BY time DESC
        LIMIT 1
    """,
        (unit["id"],),
    )

    msg = cursor.fetchone()

    if msg:
        print(f"\n📍 Último mensaje:")
        print(f"   Timestamp: {msg['timestamp']}")
        print(f"   Age: {msg['age_min']} min")
        print(f"   Speed: {msg['speed']} km/h ({msg['speed'] * 0.621371:.1f} mph)")
        print(f"   Location: {msg['lat']}, {msg['lon']}")

        if msg["age_min"] > 15:
            print(f"   ⚠️  Data > 15 min → debería aparecer OFFLINE")
        else:
            print(f"   ✅ Data < 15 min → debería aparecer activo")
            if msg["speed"] > 3:
                print(f"   ✅ Speed > 3 km/h → debería ser MOVING")

    cursor.close()
    wialon_conn.close()

    # Conectar a local DB
    print(f"\n📊 FUEL_METRICS (Dashboard DB)")
    print("-" * 80)

    local_conn = pymysql.connect(
        host="localhost",
        port=3306,
        user="fuel_admin",
        password="FuelCopilot2025!",
        database="fuel_copilot",
        charset="utf8mb4",
    )

    cursor = local_conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute(
        """
        SELECT 
            timestamp_utc,
            TIMESTAMPDIFF(MINUTE, timestamp_utc, NOW()) as age_min,
            truck_status,
            speed_mph,
            rpm,
            fuel_rate_lh,
            data_age_min
        FROM fuel_metrics
        WHERE truck_id = 'RA9250'
        ORDER BY timestamp_utc DESC
        LIMIT 1
    """
    )

    local = cursor.fetchone()

    if not local:
        print("❌ RA9250 NO encontrado en fuel_metrics")
        print("   → wialon_sync NO está procesando este truck")
        cursor.close()
        local_conn.close()
        return

    print(f"✅ Registro en fuel_metrics:")
    print(f"   Timestamp: {local['timestamp_utc']}")
    print(f"   Age desde NOW: {local['age_min']} min")
    print(f"   data_age_min (guardado): {local['data_age_min']}")
    print(f"   Status: {local['truck_status']}")
    print(f"   Speed: {local['speed_mph']} mph")
    print(f"   RPM: {local['rpm']}")

    # Comparación
    print(f"\n⚖️  COMPARACIÓN:")
    print("-" * 80)

    if msg and local:
        wialon_age = msg["age_min"]
        local_age = local["age_min"]
        diff = abs(wialon_age - local_age)

        print(f"Wialon age: {wialon_age} min")
        print(f"Local age: {local_age} min")
        print(f"Diferencia: {diff} min")

        if diff > 5:
            print(f"\n❌ PROBLEMA: Sync retrasado > 5 min")
        else:
            print(f"\n✅ Sincronización OK")

        # Verificar status
        wialon_speed_mph = msg["speed"] * 0.621371

        print(f"\nStatus Analysis:")
        print(f"   Wialon speed: {wialon_speed_mph:.1f} mph")
        print(f"   Local speed: {local['speed_mph']} mph")
        print(f"   Local status: {local['truck_status']}")

        # Determinar status esperado
        if local_age > 15:
            expected = "OFFLINE"
        elif wialon_speed_mph > 2:
            expected = "MOVING"
        elif local["rpm"] and local["rpm"] > 0:
            expected = "STOPPED"
        else:
            expected = "PARKED"

        print(f"   Status esperado: {expected}")

        if local["truck_status"] != expected:
            print(
                f"\n❌ MISMATCH: Status guardado ({local['truck_status']}) != esperado ({expected})"
            )
        else:
            print(f"\n✅ Status correcto")

    cursor.close()
    local_conn.close()


if __name__ == "__main__":
    analyze_ra9250()
