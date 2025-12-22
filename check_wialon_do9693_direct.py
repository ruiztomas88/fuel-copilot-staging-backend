#!/usr/bin/env python3
"""
Consulta DIRECTA a Wialon para verificar sensores de DO9693
Esto es lo que Beyond lee - la fuente de verdad
"""
from datetime import datetime

import pymysql

WIALON_DB = {
    "host": "20.127.200.135",
    "port": 3306,
    "user": "tomas",
    "password": "Tomas2025",
    "database": "wialon_collect",
}


def find_do9693_unit_id():
    """Primero necesitamos encontrar el unit_id de DO9693"""
    print("\n" + "=" * 80)
    print("🔍 PASO 1: Buscando unit_id de DO9693 en Wialon")
    print("=" * 80)

    try:
        conn = pymysql.connect(**WIALON_DB)
        cursor = conn.cursor()

        # Ver todas las tablas disponibles
        cursor.execute("SHOW TABLES")
        tables = [t[0] for t in cursor.fetchall()]
        print(f"\n📋 Tablas en wialon_collect: {', '.join(tables)}\n")

        # Buscar en cada tabla posible
        for table in ["units", "wln_units", "devices", "trucks"]:
            try:
                cursor.execute(f"SHOW TABLES LIKE '{table}'")
                if cursor.fetchone():
                    print(f"✓ Revisando tabla {table}...")
                    cursor.execute(f"DESCRIBE {table}")
                    columns = [col[0] for col in cursor.fetchall()]
                    print(f"  Columnas: {', '.join(columns[:10])}...")

                    # Buscar DO9693
                    for name_col in ["name", "truck_id", "device_name", "nm"]:
                        if name_col in columns:
                            cursor.execute(
                                f"SELECT * FROM {table} WHERE {name_col} LIKE '%DO9693%' LIMIT 5"
                            )
                            results = cursor.fetchall()
                            if results:
                                print(f"\n  🎯 ENCONTRADO en {table}.{name_col}!")
                                for row in results:
                                    print(f"     {row}")
                                return results[0] if results else None
            except Exception as e:
                print(f"  ⚠️ Error en {table}: {e}")

        cursor.close()
        conn.close()
        return None

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return None


def check_sensors_table_structure():
    """Ver estructura de tabla sensors"""
    print("\n" + "=" * 80)
    print("📊 PASO 2: Estructura de tabla 'sensors' en Wialon")
    print("=" * 80)

    try:
        conn = pymysql.connect(**WIALON_DB)
        cursor = conn.cursor()

        # Verificar si existe tabla sensors
        cursor.execute("SHOW TABLES LIKE '%sensor%'")
        sensor_tables = cursor.fetchall()
        print(f"\n📋 Tablas con 'sensor': {sensor_tables}\n")

        # Si no hay tabla sensors, buscar otras
        if not sensor_tables:
            cursor.execute("SHOW TABLES")
            all_tables = [t[0] for t in cursor.fetchall()]
            print(f"📋 TODAS las tablas: {all_tables}\n")

            # Buscar tablas que podrían tener datos de sensores
            for table in all_tables:
                if any(
                    keyword in table.lower()
                    for keyword in ["data", "message", "reading", "value"]
                ):
                    print(f"\n🔍 Revisando {table}:")
                    cursor.execute(f"DESCRIBE {table}")
                    columns = cursor.fetchall()
                    for col in columns[:15]:
                        print(f"   {col[0]:25} {col[1]}")

                    # Sample data
                    cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                    sample = cursor.fetchall()
                    if sample:
                        print(f"   Sample ({len(sample)} rows):")
                        for row in sample[:2]:
                            print(f"     {str(row)[:100]}...")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ ERROR: {e}")


def check_raw_sensor_data():
    """Intentar consultar datos raw de sensores"""
    print("\n" + "=" * 80)
    print("📊 PASO 3: Buscando datos de sensores para cualquier truck")
    print("=" * 80)

    try:
        conn = pymysql.connect(**WIALON_DB)
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Intentar queries comunes
        queries = [
            # Query 1: Formato típico Wialon
            """SELECT * FROM messages 
               WHERE tm > UNIX_TIMESTAMP(NOW() - INTERVAL 10 MINUTE)
               LIMIT 10""",
            # Query 2: Si hay tabla params
            """SELECT * FROM params 
               WHERE param_name IN ('engine_rpm', 'oil_pressure', 'coolant_temp')
               LIMIT 10""",
            # Query 3: Si hay tabla telemetry
            """SELECT * FROM telemetry 
               ORDER BY timestamp DESC 
               LIMIT 10""",
        ]

        for i, query in enumerate(queries, 1):
            try:
                print(f"\n🔍 Query {i}:")
                print(f"   {query[:80]}...")
                cursor.execute(query)
                results = cursor.fetchall()

                if results:
                    print(f"   ✅ {len(results)} resultados!")
                    print(f"   Primera fila: {results[0]}")
                    return results
                else:
                    print(f"   ⚠️ Sin resultados")

            except Exception as e:
                print(f"   ❌ Error: {e}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"❌ ERROR: {e}")


def main():
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 15 + "AUDITORÍA DIRECTA WIALON - DO9693" + " " * 28 + "║")
    print("╚" + "=" * 78 + "╝")

    # Paso 1: Encontrar unit_id
    unit_info = find_do9693_unit_id()

    # Paso 2: Ver estructura de sensores
    check_sensors_table_structure()

    # Paso 3: Ver datos raw
    check_raw_sensor_data()

    print("\n" + "=" * 80)
    print("💡 DIAGNÓSTICO")
    print("=" * 80)
    print("Si Beyond muestra datos pero nosotros no:")
    print("1. Beyond podría estar usando API REST de Wialon (no SQL)")
    print("2. Credenciales SQL podrían no tener acceso a tabla correcta")
    print("3. Estructura de DB podría ser diferente a la esperada")
    print("=" * 80)


if __name__ == "__main__":
    main()
