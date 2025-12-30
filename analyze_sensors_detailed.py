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
print("ANÁLISIS DETALLADO DE SENSORES - JB6858")
print("=" * 80)

unit_id = 401016899  # JB6858

with conn.cursor() as cursor:
    # Get all sensor data for JB6858
    cursor.execute(
        """
        SELECT sensor_id, n, p, type, value, counter, text_value, 
               measure_datetime, updateTime
        FROM sensors 
        WHERE unit = %s 
        ORDER BY measure_datetime DESC 
        LIMIT 50
    """,
        (unit_id,),
    )

    sensors = cursor.fetchall()

    print(f"\n📊 Total registros: {len(sensors)}")
    print(f"Último update: {sensors[0]['measure_datetime'] if sensors else 'N/A'}")

    # Group by sensor_id to see all sensors
    sensor_map = {}
    for s in sensors:
        sid = s["sensor_id"]
        if sid not in sensor_map:
            sensor_map[sid] = {
                "name": s["n"] or s["p"] or "Unknown",
                "type": s["type"],
                "values": [],
                "last_update": s["measure_datetime"],
            }

        value = s["value"] or s["counter"] or s["text_value"]
        if value is not None:
            sensor_map[sid]["values"].append(value)

    print("\n" + "=" * 80)
    print("SENSORES ENCONTRADOS:")
    print("=" * 80)

    for sid, info in sorted(
        sensor_map.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999
    ):
        latest = info["values"][0] if info["values"] else "N/A"
        print(f"\n📌 Sensor ID: {sid}")
        print(f"   Nombre: {info['name']}")
        print(f"   Type: {info['type']}")
        print(f"   Valor: {latest}")
        print(f"   Lecturas: {len(info['values'])}")
        print(f"   Último update: {info['last_update']}")

    # Check units_map to see sensor definitions
    print("\n" + "=" * 80)
    print("DEFINICIONES DE SENSORES (units_map):")
    print("=" * 80)

    cursor.execute(
        """
        SELECT * FROM units_map 
        WHERE unit_id = %s
        LIMIT 1
    """,
        (unit_id,),
    )

    unit_info = cursor.fetchone()
    if unit_info:
        print(f"\nUnidad JB6858 (ID: {unit_id}):")
        for key, value in unit_info.items():
            if value is not None and key not in ["id"]:
                # If it's JSON, try to parse it
                if isinstance(value, str) and (
                    value.startswith("{") or value.startswith("[")
                ):
                    try:
                        parsed = json.loads(value)
                        print(f"\n{key}:")
                        print(json.dumps(parsed, indent=2))
                    except:
                        print(f"{key}: {value[:200]}...")
                else:
                    print(f"{key}: {value}")

    # Check if there's a sensor configuration table
    print("\n" + "=" * 80)
    cursor.execute("SHOW TABLES")
    tables = [list(t.values())[0] for t in cursor.fetchall()]

    print("\nBuscando definiciones de sensores en otras tablas...")

    for table in tables:
        if "config" in table.lower() or "definition" in table.lower():
            print(f"\n📋 Tabla: {table}")
            try:
                cursor.execute(f"DESCRIBE {table}")
                cols = cursor.fetchall()
                print(f"   Columnas: {', '.join([c['Field'] for c in cols])}")

                # Try to get data related to our unit
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                sample = cursor.fetchall()
                if sample:
                    print(f"   Sample data:")
                    for row in sample[:1]:
                        for k, v in row.items():
                            if v is not None:
                                print(f"     {k}: {str(v)[:100]}")
            except Exception as e:
                print(f"   Error: {e}")

conn.close()

print("\n" + "=" * 80)
print("ANÁLISIS COMPLETADO")
print("=" * 80)
