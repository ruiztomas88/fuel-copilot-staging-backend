#!/usr/bin/env python3
"""
Validar columnas de la tabla trips en Wialon
"""
import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

WIALON_CONFIG = {
    "host": os.getenv("WIALON_DB_HOST", "20.127.200.135"),
    "port": int(os.getenv("WIALON_DB_PORT", "3306")),
    "database": os.getenv("WIALON_DB_NAME", "wialon_collect"),
    "user": os.getenv("WIALON_DB_USER", "tomas"),
    "password": os.getenv("WIALON_DB_PASS", "Tomas2025"),
}

# Columnas que usa nuestro código
REQUIRED_COLUMNS = [
    "unit",
    "from_datetime",
    "to_datetime",
    "from_timestamp",
    "to_timestamp",
    "distance_miles",
    "avg_speed",
    "max_speed",
    "odometer",
    "driver",
    "harsh_accel_count",
    "harsh_brake_count",
    "speeding_count",
]

print("=" * 80)
print("🔍 VALIDACIÓN DE TABLA trips EN WIALON")
print("=" * 80)

try:
    conn = pymysql.connect(**WIALON_CONFIG)
    cursor = conn.cursor()

    # Obtener estructura de la tabla
    cursor.execute("DESCRIBE trips")
    columns = cursor.fetchall()

    existing_columns = [col[0] for col in columns]

    print(f"\n✅ Conexión exitosa a Wialon: {WIALON_CONFIG['database']}")
    print(f"\n📋 Columnas en la tabla trips ({len(existing_columns)}):")
    for col in columns:
        col_name = col[0]
        col_type = col[1]
        print(f"  - {col_name:30} {col_type}")

    # Verificar columnas requeridas
    print("\n" + "=" * 80)
    print("🔍 VALIDACIÓN DE COLUMNAS REQUERIDAS:")
    print("=" * 80)

    missing = []
    found = []

    for req_col in REQUIRED_COLUMNS:
        if req_col in existing_columns:
            found.append(req_col)
            print(f"  ✅ {req_col}")
        else:
            missing.append(req_col)
            print(f"  ❌ {req_col} - FALTA")

    print("\n" + "=" * 80)
    print(f"📊 RESUMEN:")
    print(f"  • Columnas existentes: {len(existing_columns)}")
    print(f"  • Columnas requeridas: {len(REQUIRED_COLUMNS)}")
    print(f"  • Encontradas: {len(found)}")
    print(f"  • Faltantes: {len(missing)}")
    print("=" * 80)

    if missing:
        print(f"\n❌ FALTAN {len(missing)} COLUMNAS:")
        for col in missing:
            print(f"   - {col}")
        print("\n⚠️  El código podría fallar al intentar usar estas columnas")
    else:
        print("\n✅ ¡PERFECTO! Todas las columnas requeridas existen")

    # Verificar datos de ejemplo
    print("\n" + "=" * 80)
    print("📊 MUESTRA DE DATOS (últimos 3 trips):")
    print("=" * 80)

    cursor.execute(
        """
        SELECT unit, from_datetime, to_datetime, distance_miles, 
               driver, harsh_accel_count, harsh_brake_count, speeding_count
        FROM trips
        ORDER BY from_datetime DESC
        LIMIT 3
    """
    )

    sample = cursor.fetchall()
    if sample:
        for row in sample:
            print(f"\nUnit: {row[0]}")
            print(f"  Período: {row[1]} → {row[2]}")
            print(f"  Distancia: {row[3]} mi")
            print(f"  Conductor: {row[4] or 'N/A'}")
            print(
                f"  Eventos: accel={row[5] or 0}, brake={row[6] or 0}, speed={row[7] or 0}"
            )
    else:
        print("⚠️  No hay datos en la tabla trips")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    exit(1)

print("\n" + "=" * 80)
