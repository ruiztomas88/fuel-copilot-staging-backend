#!/usr/bin/env python3
"""
Script para verificar sensores disponibles en Wialon para camiones específicos
Revisa qué parámetros/sensores están reportando los camiones en las últimas 24 horas
"""

import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import pymysql
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Configuración de Wialon DB
WIALON_CONFIG = {
    "host": os.getenv("WIALON_DB_HOST", "localhost"),
    "port": int(os.getenv("WIALON_DB_PORT", "3306")),
    "user": os.getenv("WIALON_DB_USER", ""),
    "password": os.getenv("WIALON_DB_PASS", ""),
    "database": os.getenv("WIALON_DB_NAME", "wialon_collect"),
}

# Camiones a verificar (truck_id: IMEI para referencia)
TRUCKS_TO_CHECK = {
    "JB8004": "350857128626198",
    "JC1282": "862464060342057",
    "MJ9547": "862464060362188",
    "FF7702": "869842053805839",
    "CO0681": "862464060388811",
    "JB6858": "869842053779737",
    "PC1280": "862464060327850",
    "VD3579": "350857128626156",
    "OG2033": "350857128626156",
    "YM6023": "862464068474415",
    "DO9356": "862464060342040",
    "OM7769": "862464060338782",
    "JR7099": "862464060311904",
    "LH1141": None,  # Sin IMEI proporcionado
}

# Sensores que YA estamos usando en el sistema
CURRENT_SENSORS = {
    "fuel_lvl",  # Nivel de combustible %
    "speed",  # Velocidad GPS
    "rpm",  # RPM del motor
    "odom",  # Odómetro
    "fuel_rate",  # Tasa de combustible L/h
    "cool_temp",  # Temperatura del refrigerante
    "hdop",  # GPS HDOP
    "altitude",  # Altitud
    "obd_speed",  # Velocidad OBD
    "engine_hours",  # Horas del motor
    "pwr_ext",  # Voltaje externo
    "oil_press",  # Presión de aceite
    "total_fuel_used",  # Combustible total usado (ECU)
    "total_idle_fuel",  # Combustible en idle (ECU)
    "engine_load",  # Carga del motor %
    "air_temp",  # Temperatura ambiente
    "oil_temp",  # Temperatura del aceite
    "def_level",  # Nivel de DEF %
    "intake_air_temp",  # Temperatura del aire de admisión
}


def get_unit_id_from_truck_id(cursor, truck_id: str) -> int:
    """Obtener unit_id desde el beyond ID (truck_id)"""
    query = """
        SELECT unit
        FROM units_map 
        WHERE beyondId = %s
        LIMIT 1
    """
    cursor.execute(query, (truck_id,))
    result = cursor.fetchone()

    if result:
        return result["unit"]
    return None


def get_available_sensors(cursor, unit_id: int, hours: int = 24) -> dict:
    """
    Obtener todos los parámetros/sensores disponibles para un camión en las últimas X horas

    Returns:
        Dict con {sensor_name: {'count': int, 'last_value': float, 'last_time': datetime}}
    """
    cutoff_time = int((datetime.now(timezone.utc) - timedelta(hours=hours)).timestamp())

    # Query para obtener todos los parámetros únicos con su último valor
    query = """
        SELECT 
            p AS param_name,
            COUNT(*) as cnt,
            MAX(value) as last_val,
            MAX(m) as last_ts
        FROM sensors
        WHERE unit = %s
        AND m >= %s
        GROUP BY p
        ORDER BY cnt DESC
    """

    cursor.execute(query, (unit_id, cutoff_time))
    results = cursor.fetchall()

    sensors = {}
    for row in results:
        param_name = row["param_name"]
        sensors[param_name] = {
            "count": row["cnt"],
            "last_value": row["last_val"],
            "last_time": datetime.fromtimestamp(row["last_ts"], tz=timezone.utc),
        }

    return sensors


def main():
    print("=" * 80)
    print("ANÁLISIS DE SENSORES DISPONIBLES EN WIALON")
    print("=" * 80)
    print(
        f"Base de datos: {WIALON_CONFIG['host']}:{WIALON_CONFIG['port']}/{WIALON_CONFIG['database']}"
    )
    print(f"Período de análisis: Últimas 24 horas")
    print("=" * 80)
    print()

    try:
        # Conectar a Wialon DB
        conn = pymysql.connect(
            host=WIALON_CONFIG["host"],
            port=WIALON_CONFIG["port"],
            user=WIALON_CONFIG["user"],
            password=WIALON_CONFIG["password"],
            database=WIALON_CONFIG["database"],
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10,
        )
        cursor = conn.cursor()
        print("✅ Conexión a Wialon DB establecida\n")

        # Analizar cada camión
        new_sensors_found = defaultdict(list)  # sensor -> [trucks that have it]

        for truck_id, imei in TRUCKS_TO_CHECK.items():
            print(f"\n{'='*80}")
            print(f"🚛 Camión: {truck_id} (IMEI: {imei or 'N/A'})")
            print(f"{'='*80}")

            # Obtener unit_id
            unit_id = get_unit_id_from_truck_id(cursor, truck_id)

            if not unit_id:
                print(f"❌ No se encontró unit_id para truck_id {truck_id}")
                print(f"   Verifica que el truck_id esté en la tabla units_map")
                continue

            print(f"✅ Unit ID: {unit_id}")

            # Obtener sensores disponibles
            sensors = get_available_sensors(cursor, unit_id, hours=24)

            if not sensors:
                print(f"⚠️  No hay datos de sensores en las últimas 24 horas")
                continue

            print(f"\n📊 Sensores encontrados: {len(sensors)}")
            print(
                f"{'Sensor':<25} {'Lecturas':<12} {'Último Valor':<15} {'Última Actualización'}"
            )
            print("-" * 80)

            # Clasificar sensores
            new_sensors = []
            existing_sensors = []

            for sensor_name, data in sorted(
                sensors.items(), key=lambda x: x[1]["count"], reverse=True
            ):
                is_new = sensor_name not in CURRENT_SENSORS
                marker = "🆕 NUEVO" if is_new else "✅ Ya usado"

                if is_new:
                    new_sensors.append(sensor_name)
                    new_sensors_found[sensor_name].append(truck_id)
                else:
                    existing_sensors.append(sensor_name)

                # Formatear último valor
                try:
                    last_val = (
                        f"{float(data['last_value']):.2f}"
                        if data["last_value"]
                        else "NULL"
                    )
                except (ValueError, TypeError) as e:
                    last_val = str(data["last_value"])[:12]

                # Formatear última actualización
                last_time = data["last_time"].strftime("%Y-%m-%d %H:%M:%S")

                print(
                    f"{sensor_name:<25} {data['count']:<12} {last_val:<15} {last_time}  {marker}"
                )

            # Resumen para este camión
            print(f"\n📈 RESUMEN para {truck_id}:")
            print(f"   - Sensores existentes: {len(existing_sensors)}")
            print(f"   - Sensores NUEVOS: {len(new_sensors)}")

            if new_sensors:
                print(f"\n🆕 SENSORES NUEVOS detectados:")
                for sensor in new_sensors:
                    print(f"      • {sensor}")

        # Resumen global
        print(f"\n\n{'='*80}")
        print("📊 RESUMEN GLOBAL - SENSORES NUEVOS DETECTADOS")
        print(f"{'='*80}")

        if new_sensors_found:
            print(
                f"\nSe encontraron {len(new_sensors_found)} tipos de sensores nuevos:\n"
            )

            for sensor_name, trucks in sorted(
                new_sensors_found.items(), key=lambda x: len(x[1]), reverse=True
            ):
                print(f"🆕 {sensor_name}")
                print(f"   Disponible en {len(trucks)} camiones: {', '.join(trucks)}")
                print()

            print("\n💡 RECOMENDACIÓN:")
            print("   1. Revisa qué sensores son útiles para tu análisis")
            print(
                "   2. Agrega los nuevos sensores a SENSOR_PARAMS en wialon_reader.py"
            )
            print(
                "   3. Actualiza TruckSensorData dataclass para incluir los nuevos campos"
            )
            print("   4. Modifica la tabla sensor_data en MySQL si es necesario")
        else:
            print("✅ No se encontraron sensores nuevos.")
            print(
                "   Todos los sensores activos ya están siendo procesados por el sistema."
            )

        cursor.close()
        conn.close()

    except pymysql.Error as e:
        print(f"\n❌ Error de base de datos: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error inesperado: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
