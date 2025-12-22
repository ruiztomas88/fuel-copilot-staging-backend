#!/usr/bin/env python3
"""Check exact timestamps of DO9693 sensors to see when ECU stopped"""
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

    # DO9693 unit_id = 402055528
    unit_id = 402055528

    print("\n" + "=" * 80)
    print("🔍 ÚLTIMOS TIMESTAMPS POR SENSOR - DO9693 (unit_id: 402055528)")
    print("=" * 80)

    critical_sensors = [
        "rpm",
        "oil_press",
        "cool_temp",
        "engine_hours",
        "fuel_lvl",
        "def_level",
        "engine_load",
        "oil_temp",
        "speed",
        "rssi",
        "pwr_ext",
        "course",
    ]

    for sensor in critical_sensors:
        cursor.execute(
            """
            SELECT p, value, measure_datetime, 
                   TIMESTAMPDIFF(MINUTE, measure_datetime, NOW()) as mins_ago
            FROM sensors
            WHERE unit = %s AND p = %s
            ORDER BY measure_datetime DESC
            LIMIT 1
        """,
            (unit_id, sensor),
        )

        row = cursor.fetchone()
        if row:
            param, value, ts, mins_ago = row
            icon = "✅" if mins_ago < 5 else "⏰" if mins_ago < 30 else "❌"
            print(f"{icon} {param:15} = {value:>10} | {ts} ({mins_ago} min ago)")
        else:
            print(f"❌ {sensor:15} = NO DATA")

    print("\n" + "=" * 80)
    print("📊 CONCLUSIÓN")
    print("=" * 80)

    # Check if ECU is down
    cursor.execute(
        """
        SELECT MIN(TIMESTAMPDIFF(MINUTE, measure_datetime, NOW())) as min_age
        FROM sensors
        WHERE unit = %s AND p IN ('rpm', 'oil_press', 'cool_temp')
        ORDER BY measure_datetime DESC
        LIMIT 1
    """,
        (unit_id,),
    )

    ecu_age = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT MIN(TIMESTAMPDIFF(MINUTE, measure_datetime, NOW())) as min_age
        FROM sensors
        WHERE unit = %s AND p IN ('speed', 'rssi', 'pwr_ext')
        ORDER BY measure_datetime DESC
        LIMIT 1
    """,
        (unit_id,),
    )

    gps_age = cursor.fetchone()[0]

    if ecu_age and ecu_age > 30:
        print(f"❌ ECU DATA: {ecu_age} minutos sin actualizar")
        print("   → J1939/OBD conexión caída")
    else:
        print(f"✅ ECU DATA: {ecu_age} minutos (OK)")

    if gps_age and gps_age < 5:
        print(f"✅ GPS/CELULAR DATA: {gps_age} minutos (OK)")
    else:
        print(f"⏰ GPS/CELULAR DATA: {gps_age} minutos")

    if ecu_age and gps_age and ecu_age > 30 and gps_age < 5:
        print("\n🔥 DIAGNÓSTICO: ECU desconectado pero telemática funcionando")
        print("   Posibles causas:")
        print("   - Cable J1939 desconectado")
        print("   - ECU en modo sleep")
        print("   - OBD port issue")
        print("   - Telemática configurada solo para GPS")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
