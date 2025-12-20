#!/usr/bin/env python3
"""
Explorar tabla speedings en Wialon para eventos de exceso de velocidad
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

print("=" * 80)
print("🚨 TABLA SPEEDINGS - EVENTOS DE EXCESO DE VELOCIDAD")
print("=" * 80)

try:
    conn = pymysql.connect(**WIALON_CONFIG)
    cursor = conn.cursor()

    # Estructura de la tabla
    cursor.execute("DESCRIBE speedings")
    columns = cursor.fetchall()

    print(f"\n📋 Estructura de la tabla ({len(columns)} columnas):")
    for col in columns:
        print(f"  - {col[0]:30} {col[1]}")

    # Contar registros
    cursor.execute("SELECT COUNT(*) FROM speedings")
    total = cursor.fetchone()[0]
    print(f"\n📊 Total de registros: {total:,}")

    # Contar por truck
    cursor.execute(
        """
        SELECT unit, COUNT(*) as eventos
        FROM speedings
        GROUP BY unit
        ORDER BY eventos DESC
        LIMIT 15
    """
    )

    print(f"\n🚛 Top 15 trucks con más eventos de speeding:")
    for row in cursor.fetchall():
        print(f"  Unit {row[0]}: {row[1]:,} eventos")

    # Muestra de datos recientes
    cursor.execute(
        """
        SELECT * FROM speedings
        ORDER BY from_datetime DESC
        LIMIT 5
    """
    )

    samples = cursor.fetchall()

    if samples:
        print(f"\n📝 Últimos 5 eventos de speeding:")
        col_names = [col[0] for col in columns]

        for i, row in enumerate(samples, 1):
            print(f"\n  Evento #{i}:")
            for j, col_name in enumerate(col_names):
                if row[j] is not None:
                    print(f"    {col_name}: {row[j]}")

    # Rango de fechas
    cursor.execute(
        """
        SELECT 
            MIN(from_datetime) as primer_evento,
            MAX(from_datetime) as ultimo_evento,
            DATEDIFF(MAX(from_datetime), MIN(from_datetime)) as dias_cobertura
        FROM speedings
    """
    )

    dates = cursor.fetchone()
    print(f"\n📅 Cobertura temporal:")
    print(f"  Primer evento: {dates[0]}")
    print(f"  Último evento: {dates[1]}")
    print(f"  Días de cobertura: {dates[2]:,}")

    # Estadísticas de velocidad
    cursor.execute(
        """
        SELECT 
            AVG(max_speed) as velocidad_promedio,
            MAX(max_speed) as velocidad_maxima,
            MIN(max_speed) as velocidad_minima
        FROM speedings
        WHERE max_speed IS NOT NULL
    """
    )

    stats = cursor.fetchone()
    if stats[0]:
        print(f"\n📈 Estadísticas de velocidad:")
        print(f"  Promedio: {stats[0]:.2f}")
        print(f"  Máxima: {stats[1]}")
        print(f"  Mínima: {stats[2]}")

    cursor.close()
    conn.close()

    print("\n" + "=" * 80)
    print("✅ Exploración completada")
    print("=" * 80)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
