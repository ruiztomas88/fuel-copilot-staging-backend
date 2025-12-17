"""
🔍 WIALON SENSOR AVAILABILITY REPORT
═════════════════════════════════════════════════════════════════════════════

Analiza qué sensores reporta Wialon en las últimas 18 horas para los camiones
listados en tanks.yaml.

Conecta a:
1. Base de datos Wialon REMOTA (20.127.200.135) - fuente de datos
2. Base de datos Fuel Copilot LOCAL - datos procesados
"""

import pymysql
import yaml
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path

# Configuración MySQL (Wialon DB - Remoto)
WIALON_DB_CONFIG = {
    "host": "20.127.200.135",
    "port": 3306,
    "user": "tomas",
    "password": "Tomas2025",
    "database": "wialon_collect",
}

# Configuración MySQL (Fuel Copilot DB - Local)
LOCAL_DB_CONFIG = {
    "host": "localhost",
    "user": "fuel_admin",
    "password": "FuelCopilot2025!",
    "database": "fuel_copilot",
}


def load_tanks_yaml():
    """Cargar lista de camiones desde tanks.yaml"""
    yaml_path = Path(__file__).parent / "tanks.yaml"
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    # Extraer truck_ids y unit_ids
    trucks = []
    for truck_id, config in data.get("trucks", {}).items():
        unit_id = config.get("unit_id")
        trucks.append(
            {"truck_id": truck_id, "unit_id": str(unit_id) if unit_id else None}
        )

    return trucks


def get_wialon_db_structure():
    """Explorar estructura de base de datos Wialon"""
    conn = pymysql.connect(**WIALON_DB_CONFIG)
    cursor = conn.cursor()

    # Listar todas las tablas
    cursor.execute("SHOW TABLES")
    tables = [t[0] for t in cursor.fetchall()]

    print(f"\n📊 Base de datos: wialon_collect")
    print(f"   Total de tablas: {len(tables)}\n")

    table_info = {}

    for table_name in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        count = cursor.fetchone()[0]

        cursor.execute(f"DESCRIBE {table_name}")
        columns = [col[0] for col in cursor.fetchall()]

        table_info[table_name] = {"count": count, "columns": columns}

        print(f"   📋 {table_name}: {count:,} registros")
        if count > 0:
            print(f"      Columnas: {', '.join(columns[:8])}")
            if len(columns) > 8:
                print(f"              ... y {len(columns) - 8} más")

    cursor.close()
    conn.close()

    return table_info


def query_wialon_sensors(trucks):
    """Consultar sensores de Wialon para los camiones especificados"""
    conn = pymysql.connect(**WIALON_DB_CONFIG)
    cursor = conn.cursor()

    # Extraer unit_ids
    unit_ids = [t["unit_id"] for t in trucks if t["unit_id"]]

    print(f"\n🔍 Buscando datos para {len(unit_ids)} unidades:")
    for t in trucks[:5]:
        print(f"   - {t['truck_id']}: unit_id={t['unit_id']}")
    if len(trucks) > 5:
        print(f"   ... y {len(trucks) - 5} más")

    # Calcular timestamp últimas 18 horas
    cutoff = datetime.now() - timedelta(hours=18)
    cutoff_unix = int(cutoff.timestamp())

    print(f"\n   Buscando datos después de: {cutoff.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Unix timestamp > {cutoff_unix}\n")

    # Intentar varias tablas comunes en Wialon
    sensor_data = {}

    # Tabla 1: messages (datos de telemetría)
    try:
        print("   📡 Consultando tabla 'messages'...")
        query = """
            SELECT unit_id, param, value, time
            FROM messages
            WHERE unit_id IN %s
              AND time > %s
            LIMIT 1000
        """
        cursor.execute(query, (unit_ids, cutoff_unix))
        rows = cursor.fetchall()

        if rows:
            print(f"   ✅ Encontrados {len(rows)} mensajes")
            for row in rows[:5]:
                print(f"      - unit_id={row[0]}, param={row[1]}, value={row[2]}")
        else:
            print("   ⚠️ No se encontraron mensajes recientes")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Tabla 2: avl_data
    try:
        print("\n   📡 Consultando tabla 'avl_data'...")
        cursor.execute("SELECT * FROM avl_data LIMIT 1")
        sample = cursor.fetchone()
        if sample:
            print(f"   Ejemplo de registro: {sample[:5]}")
    except Exception as e:
        print(f"   ❌ Tabla no existe o error: {e}")

    # Tabla 3: params o parameters
    for table_name in ["params", "parameters", "sensors"]:
        try:
            cursor.execute(f"SELECT * FROM {table_name} LIMIT 1")
            print(f"\n   ✅ Tabla '{table_name}' existe")
        except:
            pass

    cursor.close()
    conn.close()

    return sensor_data


def get_fuel_copilot_sensors(trucks):
    """Ver qué sensores tienen datos en truck_sensors_cache (DB local)"""
    try:
        conn = pymysql.connect(**LOCAL_DB_CONFIG)
    except Exception as e:
        print(f"\n⚠️ No se pudo conectar a DB local: {e}")
        print("   (Normal si estás en Mac y la DB está en la VM)")
        return {}

    cursor = conn.cursor()

    # Obtener todas las columnas de truck_sensors_cache
    cursor.execute("DESCRIBE truck_sensors_cache")
    all_columns = [col[0] for col in cursor.fetchall()]

    # Excluir columnas de metadata
    excluded = ["truck_id", "last_updated", "created_at"]
    sensor_columns = [col for col in all_columns if col not in excluded]

    # Para cada camión, revisar qué sensores tienen valores no NULL
    cutoff = datetime.now() - timedelta(hours=18)

    truck_sensor_status = {}
    truck_ids = [t["truck_id"] for t in trucks]

    for truck_id in truck_ids:
        query = f"""
            SELECT {', '.join(sensor_columns)}, last_updated
            FROM truck_sensors_cache
            WHERE truck_id = %s
              AND last_updated > %s
            ORDER BY last_updated DESC
            LIMIT 1
        """

        cursor.execute(query, (truck_id, cutoff))
        row = cursor.fetchone()

        if row:
            active_sensors = {}
            for i, col_name in enumerate(sensor_columns):
                value = row[i]
                if value is not None:
                    active_sensors[col_name] = value

            truck_sensor_status[truck_id] = {
                "active_sensors": active_sensors,
                "last_updated": row[-1],
            }

    cursor.close()
    conn.close()

    return truck_sensor_status


def main():
    print("=" * 80)
    print("🔍 WIALON SENSOR AVAILABILITY REPORT")
    print("=" * 80)

    # Cargar camiones desde tanks.yaml
    print("\n📋 Cargando camiones desde tanks.yaml...")
    trucks = load_tanks_yaml()
    print(f"   Encontrados: {len(trucks)} camiones")

    # Explorar estructura de Wialon DB
    print("\n" + "=" * 80)
    print("🌐 EXPLORANDO BASE DE DATOS WIALON REMOTA")
    print("   Host: 20.127.200.135:3306")
    print("   Database: wialon_collect")
    print("=" * 80)

    try:
        table_info = get_wialon_db_structure()

        # Consultar datos de sensores
        print("\n" + "=" * 80)
        print("📊 CONSULTANDO DATOS DE SENSORES")
        print("=" * 80)

        sensor_data = query_wialon_sensors(trucks)

    except Exception as e:
        print(f"\n❌ Error conectando a Wialon DB: {e}")
        return

    # Revisar DB local
    print("\n" + "=" * 80)
    print("💾 CONSULTANDO DB LOCAL (truck_sensors_cache)")
    print("=" * 80)

    fuel_data = get_fuel_copilot_sensors(trucks)

    if fuel_data:
        print(f"\n✅ Datos encontrados para {len(fuel_data)} camiones:")

        # Consolidar sensores activos
        sensor_usage = defaultdict(int)

        for truck_id, data in sorted(fuel_data.items()):
            active = data["active_sensors"]
            sensor_usage_count = len(active)

            if sensor_usage_count > 0:
                print(f"\n   🚛 {truck_id}: {sensor_usage_count} sensores activos")
                for sensor in active.keys():
                    sensor_usage[sensor] += 1

        # Resumen
        print("\n" + "=" * 80)
        print("📊 RESUMEN: SENSORES ACTIVOS EN FLOTA")
        print("=" * 80)

        total_trucks = len(fuel_data)
        print(f"\nSensores con datos (% de flota):\n")

        for sensor, count in sorted(
            sensor_usage.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / total_trucks) * 100
            bar = "█" * int(percentage / 5)
            print(
                f"   {sensor:30s} │ {bar:20s} │ {count:2d}/{total_trucks} ({percentage:5.1f}%)"
            )

    print("\n" + "=" * 80)
    print("✅ REPORTE COMPLETO")
    print("=" * 80)


if __name__ == "__main__":
    main()
