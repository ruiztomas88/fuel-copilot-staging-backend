import json
from datetime import datetime, timedelta

import pymysql

# Connect to Wialon DB
conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password="Tomas2025",
    database="wialon_collect",
    cursorclass=pymysql.cursors.DictCursor,
)

print("=" * 80)
print("ANÁLISIS DE SENSORES WIALON - JB6858")
print("=" * 80)

# Get JB6858 unit_id from tanks.yaml (401016899)
unit_id = 401016899

with conn.cursor() as cursor:
    # First, let's see what tables we have
    cursor.execute("SHOW TABLES")
    tables = cursor.fetchall()
    print("\nTablas disponibles en wialon_collect:")
    for table in tables:
        print(f"  - {list(table.values())[0]}")

    print("\n" + "=" * 80)

    # Check if we have a messages table
    cursor.execute("SHOW TABLES LIKE '%message%'")
    msg_tables = cursor.fetchall()

    if msg_tables:
        table_name = list(msg_tables[0].values())[0]
        print(f"\nEncontrada tabla de mensajes: {table_name}")

        # Get schema
        cursor.execute(f"DESCRIBE {table_name}")
        schema = cursor.fetchall()
        print(f"\nEsquema de {table_name}:")
        for col in schema:
            print(
                f"  {col['Field']:20} {col['Type']:20} {col['Null']:5} {col['Key']:5}"
            )

        # Get recent messages for JB6858
        print(f"\n" + "=" * 80)
        print(f"Últimos 5 mensajes de JB6858 (unit_id={unit_id}):")
        print("=" * 80)

        cursor.execute(
            f"""
            SELECT * FROM {table_name} 
            WHERE unit_id = %s 
            ORDER BY server_time DESC 
            LIMIT 5
        """,
            (unit_id,),
        )

        messages = cursor.fetchall()

        if messages:
            for i, msg in enumerate(messages, 1):
                print(f"\nMensaje {i}:")
                print(
                    f"  Timestamp: {msg.get('server_time', msg.get('timestamp', 'N/A'))}"
                )

                # Print all non-null fields
                for key, value in msg.items():
                    if value is not None and key not in ["id", "unit_id"]:
                        if isinstance(value, (dict, list)):
                            print(f"  {key}: {json.dumps(value, indent=4)}")
                        else:
                            print(f"  {key}: {value}")
        else:
            print(f"  ❌ No se encontraron mensajes para unit_id={unit_id}")

    # Try to find sensor_readings or params table
    print("\n" + "=" * 80)
    cursor.execute("SHOW TABLES LIKE '%sensor%'")
    sensor_tables = cursor.fetchall()

    cursor.execute("SHOW TABLES LIKE '%param%'")
    param_tables = cursor.fetchall()

    print("\nTablas de sensores/parámetros:")
    all_tables = list(sensor_tables) + list(param_tables)
    for table in all_tables:
        table_name = list(table.values())[0]
        print(f"\n  📊 {table_name}")

        # Get schema
        cursor.execute(f"DESCRIBE {table_name}")
        schema = cursor.fetchall()
        print(f"  Columnas:")
        for col in schema:
            print(f"    {col['Field']:20} {col['Type']:20}")

        # Try to get data for JB6858
        try:
            # Try both unit_id and unit column names
            try:
                cursor.execute(
                    f"""
                    SELECT * FROM {table_name} 
                    WHERE unit = %s 
                    ORDER BY measure_datetime DESC 
                    LIMIT 10
                """,
                    (unit_id,),
                )
            except:
                cursor.execute(
                    f"""
                    SELECT * FROM {table_name} 
                    WHERE unit_id = %s 
                    ORDER BY timestamp DESC 
                    LIMIT 10
                """,
                    (unit_id,),
                )

            data = cursor.fetchall()
            if data:
                print(f"  ✅ {len(data)} registros encontrados para JB6858")
                print(f"  Sensores disponibles:")

                # Group by sensor name
                sensors_found = {}
                for row in data:
                    sensor_name = row.get("sensor_id") or row.get("n") or row.get("p")
                    if sensor_name:
                        value = (
                            row.get("value")
                            or row.get("counter")
                            or row.get("text_value")
                        )
                        if sensor_name not in sensors_found:
                            sensors_found[sensor_name] = []
                        sensors_found[sensor_name].append(value)

                for sensor, values in sorted(sensors_found.items()):
                    latest = values[0] if values else "N/A"
                    print(f"    📌 {sensor}: {latest}")
            else:
                print(f"  ❌ No datos para JB6858")
        except Exception as e:
            print(f"  ⚠️  Error consultando: {e}")

conn.close()

print("\n" + "=" * 80)
print("ANÁLISIS COMPLETADO")
print("=" * 80)
