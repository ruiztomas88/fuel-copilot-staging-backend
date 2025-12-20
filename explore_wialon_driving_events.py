#!/usr/bin/env python3
"""
Explorar tablas en Wialon para encontrar datos de:
- Aceleraciones bruscas
- Frenadas bruscas
- Exceso de velocidad
- Eventos de conducción
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
print("🔍 EXPLORACIÓN DE TABLAS EN WIALON")
print("=" * 80)

try:
    conn = pymysql.connect(**WIALON_CONFIG)
    cursor = conn.cursor()

    # Listar todas las tablas
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    print(f"\n📋 Tablas encontradas ({len(tables)}):")
    for table in sorted(tables):
        print(f"  - {table}")

    # Buscar tablas que puedan contener eventos de conducción
    potential_tables = [
        t
        for t in tables
        if any(
            keyword in t.lower()
            for keyword in ["event", "alert", "violation", "driver", "harsh", "speed"]
        )
    ]

    if potential_tables:
        print(
            f"\n⚡ Tablas potenciales con eventos de conducción ({len(potential_tables)}):"
        )
        for table in potential_tables:
            print(f"  - {table}")

    # Explorar estructura de tablas principales
    interesting_tables = ["sensors", "trips", "units_map"]

    # Agregar tablas que puedan tener eventos
    for table in tables:
        if (
            "event" in table.lower()
            or "alert" in table.lower()
            or "violation" in table.lower()
        ):
            if table not in interesting_tables:
                interesting_tables.append(table)

    for table in interesting_tables[:10]:  # Limitar a 10 tablas
        if table in tables:
            print(f"\n{'=' * 80}")
            print(f"📊 Tabla: {table}")
            print(f"{'=' * 80}")

            cursor.execute(f"DESCRIBE {table}")
            columns = cursor.fetchall()
            print(f"Columnas ({len(columns)}):")
            for col in columns:
                col_name = col[0]
                col_type = col[1]
                print(f"  - {col_name:30} {col_type}")

            # Contar registros
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"\nTotal registros: {count:,}")

            # Muestra de datos si tiene pocos registros o es relevante
            if count > 0 and count < 100000:  # Solo si no es masiva
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                sample = cursor.fetchall()
                if sample:
                    print(f"\nMuestra de datos (primeras 3 filas):")
                    for i, row in enumerate(sample, 1):
                        print(f"\n  Fila {i}:")
                        for j, col in enumerate(columns):
                            print(f"    {col[0]}: {row[j]}")

    # Buscar en sensors si hay parámetros de aceleración
    print(f"\n{'=' * 80}")
    print("🔍 BUSCANDO SENSORES DE ACELERACIÓN/FRENADO EN sensors")
    print(f"{'=' * 80}")

    cursor.execute(
        """
        SELECT DISTINCT p 
        FROM sensors 
        WHERE p LIKE '%accel%' OR p LIKE '%brake%' OR p LIKE '%harsh%' 
           OR p LIKE '%speed%' OR p LIKE '%violation%'
        ORDER BY p
    """
    )

    params = cursor.fetchall()
    if params:
        print(f"\nParámetros encontrados ({len(params)}):")
        for param in params:
            print(f"  - {param[0]}")

            # Contar cuántos registros tiene cada parámetro
            cursor.execute("SELECT COUNT(*) FROM sensors WHERE p = %s", (param[0],))
            count = cursor.fetchone()[0]
            print(f"    → {count:,} registros")

            # Muestra de valores
            cursor.execute(
                """
                SELECT unit, value, m, from_latitude, from_longitude 
                FROM sensors 
                WHERE p = %s 
                ORDER BY m DESC 
                LIMIT 3
            """,
                (param[0],),
            )
            samples = cursor.fetchall()
            for sample in samples:
                print(
                    f"      Unit: {sample[0]}, Valor: {sample[1]}, Timestamp: {sample[2]}"
                )
    else:
        print("\n❌ No se encontraron parámetros relacionados con aceleración/frenado")

    cursor.close()
    conn.close()
    print("\n" + "=" * 80)
    print("✅ Exploración completada")
    print("=" * 80)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
    exit(1)
