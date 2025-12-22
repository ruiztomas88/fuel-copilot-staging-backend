#!/usr/bin/env python3
"""Check if DO9693 has sent NEW data in last 10 minutes"""
from datetime import datetime

import pymysql

WIALON_DB = {
    "host": "20.127.200.135",
    "port": 3306,
    "user": "tomas",
    "password": "Tomas2025",
    "database": "wialon_collect",
}

try:
    conn = pymysql.connect(**WIALON_DB)
    cursor = conn.cursor()

    unit_id = 402055528  # DO9693

    print("\n" + "=" * 80)
    print(f"⏰ VERIFICANDO DATOS NUEVOS - DO9693 - {datetime.now()}")
    print("=" * 80)

    # Check last 10 minutes (convert NOW() to UTC)
    cursor.execute(
        """
        SELECT p, value, measure_datetime,
               TIMESTAMPDIFF(MINUTE, measure_datetime, UTC_TIMESTAMP()) as mins_ago
        FROM sensors
        WHERE unit = %s
          AND measure_datetime > DATE_SUB(UTC_TIMESTAMP(), INTERVAL 10 MINUTE)
        ORDER BY measure_datetime DESC
        LIMIT 20
    """,
        (unit_id,),
    )

    recent = cursor.fetchall()

    if recent:
        print(f"✅ Encontrados {len(recent)} sensores actualizados en últimos 10 min:")
        for sensor, val, ts, age in recent:
            print(f"   {sensor:15} = {val:>10} | {ts} ({age} min ago)")
    else:
        print("❌ NO hay datos nuevos en últimos 10 minutos")
        print("\n🔍 Verificando últimos datos (sin límite de tiempo):")

        cursor.execute(
            """
            SELECT p, value, measure_datetime,
                   TIMESTAMPDIFF(MINUTE, measure_datetime, UTC_TIMESTAMP()) as mins_ago
            FROM sensors
            WHERE unit = %s
            ORDER BY measure_datetime DESC
            LIMIT 10
        """,
            (unit_id,),
        )

        last_data = cursor.fetchall()
        print(f"\nÚltimos 10 sensores recibidos:")
        for sensor, val, ts, age in last_data:
            print(f"   {sensor:15} = {val:>10} | {ts} ({age} min ago)")

    # Check if truck is transmitting at all
    cursor.execute(
        """
        SELECT MAX(measure_datetime) as last_transmission,
               TIMESTAMPDIFF(MINUTE, MAX(measure_datetime), UTC_TIMESTAMP()) as mins_ago
        FROM sensors
        WHERE unit = %s
    """,
        (unit_id,),
    )

    last_tx, age = cursor.fetchone()

    print("\n" + "=" * 80)
    print("📊 ESTADO DE TRANSMISIÓN")
    print("=" * 80)
    print(f"Última transmisión: {last_tx}")
    print(f"Edad: {age} minutos")

    if age < 5:
        print("✅ ACTIVO - Transmitiendo normalmente")
    elif age < 30:
        print("⏰ RECIENTE - Última transmisión hace menos de 30 min")
    elif age < 180:
        print("⚠️  STALE - Última transmisión hace 30min-3h (como ahora)")
    else:
        print("❌ INACTIVO - Sin transmisión por más de 3 horas")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
