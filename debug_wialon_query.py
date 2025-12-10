import pymysql
from dotenv import load_dotenv
import os
import time

load_dotenv()

# Configuración de Wialon
WIALON_CONFIG = {
    "host": os.getenv("WIALON_DB_HOST", "localhost"),
    "port": int(os.getenv("WIALON_DB_PORT", "3306")),
    "user": os.getenv("WIALON_DB_USER", "wialon_user"),
    "password": os.getenv("WIALON_DB_PASS", ""),
    "database": os.getenv("WIALON_DB_NAME", "wialon"),
}

# Mapeo de camiones (solo algunos para prueba)
TRUCK_UNIT_MAPPING = {
    "NQ6975": 401961901,
    "RT9127": 401961902,
    "RT9128": 401961903,
}

# Parámetros de sensores relevantes
SENSOR_PARAMS = {
    "speed": "speed",
    "rpm": "obd_speed",
    "fuel_lvl": "fuel_lvl",
    "fuel_rate": "fuel_rate",
    "odometer": "odometer",
    "altitude": "altitude",
    "latitude": "latitude",
    "longitude": "longitude",
    "engine_hours": "engine_hours",
    "hdop": "hdop",
    "coolant_temp": "cool_temp",
    "total_fuel_used": "total_fuel_used",
    "pwr_ext": "pwr_ext",
    "engine_load": "engine_load",
    "oil_press": "oil_press",
    "oil_temp": "oil_temp",
    "def_level": "def_level",
    "intake_air_temp": "intake_air_temp",
}

try:
    # Conectar a Wialon DB
    conn = pymysql.connect(
        host=WIALON_CONFIG["host"],
        port=WIALON_CONFIG["port"],
        user=WIALON_CONFIG["user"],
        password=WIALON_CONFIG["password"],
        database=WIALON_CONFIG["database"],
        charset='utf8mb4',
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,
    )

    cursor = conn.cursor()

    # Probar la consulta que está fallando
    for truck_id, unit_id in TRUCK_UNIT_MAPPING.items():
        print(f"\n🔍 Probando consulta para {truck_id} (unit_id: {unit_id})")

        try:
            # Calcular cutoff epoch (1 hora atrás)
            cutoff_epoch = int(time.time()) - 3600
            print(f"Cutoff epoch: {cutoff_epoch}")

            # Obtener parámetros relevantes
            relevant_params = list(SENSOR_PARAMS.values())
            params_placeholder = ", ".join(["%s"] * len(relevant_params))

            # Consulta del método get_latest_sensor_data
            query = f"""
                SELECT
                    p as param_name,
                    value,
                    m as epoch_time,
                    from_latitude,
                    from_longitude,
                    measure_datetime
                FROM sensors
                WHERE unit = %s
                    AND m >= %s
                    AND p IN ({params_placeholder})
                ORDER BY m DESC
                LIMIT 2000
            """

            # Preparar argumentos
            query_args = [unit_id, cutoff_epoch] + relevant_params
            print(f"Query args: {query_args}")

            # Ejecutar consulta
            cursor.execute(query, query_args)
            results = cursor.fetchall()

            print(f"✅ Consulta exitosa: {len(results)} filas encontradas")

            if results:
                # Mostrar algunos resultados
                latest_epoch = results[0]["epoch_time"]
                print(f"Último timestamp: {latest_epoch}")
                print(f"Parámetros encontrados: {set(row['param_name'] for row in results[:10])}")

        except Exception as e:
            print(f"❌ Error en consulta: {e}")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"❌ Error de conexión: {e}")