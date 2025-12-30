import pymysql

conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password="Tomas2025",
    database="wialon_collect",
    cursorclass=pymysql.cursors.DictCursor,
)

unit_id = 401016899  # JB6858

print("=" * 80)
print("BUSCANDO ODOMETER Y GEAR EN OTRAS TABLAS")
print("=" * 80)

with conn.cursor() as cursor:
    # Check counters table (might have odometer)
    print("\n📊 Tabla: counters")
    cursor.execute("DESCRIBE counters")
    cols = cursor.fetchall()
    print("Columnas:", [c["Field"] for c in cols])

    try:
        cursor.execute(
            """
            SELECT * FROM counters 
            WHERE unit = %s 
            ORDER BY measure_datetime DESC 
            LIMIT 5
        """,
            (unit_id,),
        )

        data = cursor.fetchall()
        if data:
            print(f"\n✅ {len(data)} registros encontrados")
            for i, row in enumerate(data[:2], 1):
                print(f"\nRegistro {i}:")
                for key, value in row.items():
                    if value is not None:
                        print(f"  {key}: {value}")
        else:
            print("❌ No data")
    except Exception as e:
        print(f"Error: {e}")

    # Check trips table (might have mileage)
    print("\n" + "=" * 80)
    print("📊 Tabla: trips")
    cursor.execute("DESCRIBE trips")
    cols = cursor.fetchall()
    print("Columnas:", [c["Field"] for c in cols])

    try:
        cursor.execute(
            """
            SELECT * FROM trips 
            WHERE unit = %s 
            ORDER BY to_datetime DESC 
            LIMIT 3
        """,
            (unit_id,),
        )

        data = cursor.fetchall()
        if data:
            print(f"\n✅ {len(data)} registros encontrados")
            for i, row in enumerate(data[:1], 1):
                print(f"\nViaje {i}:")
                for key, value in row.items():
                    if (
                        value is not None
                        and "distance" in str(key).lower()
                        or "mileage" in str(key).lower()
                        or "odom" in str(key).lower()
                    ):
                        print(f"  ⭐ {key}: {value}")
                    elif value is not None:
                        print(f"  {key}: {value}")
        else:
            print("❌ No data")
    except Exception as e:
        print(f"Error: {e}")

    # Check if there's a messages or raw_data table
    print("\n" + "=" * 80)
    cursor.execute("SHOW TABLES")
    tables = [list(t.values())[0] for t in cursor.fetchall()]

    print("\nBuscando tablas con 'message', 'raw', 'data', 'position'...")
    relevant_tables = [
        t
        for t in tables
        if any(
            word in t.lower()
            for word in ["message", "raw", "data", "position", "track"]
        )
    ]

    if relevant_tables:
        print(f"Encontradas: {relevant_tables}")
        for table in relevant_tables[:3]:  # Solo las primeras 3
            print(f"\n📋 {table}:")
            try:
                cursor.execute(f"DESCRIBE {table}")
                cols = cursor.fetchall()
                col_names = [c["Field"] for c in cols]
                print(f"  Columnas ({len(col_names)}): {', '.join(col_names[:15])}")

                # Try to get sample data
                cursor.execute(f"SELECT * FROM {table} LIMIT 1")
                sample = cursor.fetchone()
                if sample:
                    print(f"  Sample (primeras cols):")
                    for k, v in list(sample.items())[:10]:
                        print(f"    {k}: {v}")
            except Exception as e:
                print(f"  Error: {e}")
    else:
        print("No se encontraron tablas relevantes")

conn.close()

print("\n" + "=" * 80)
print("BÚSQUEDA COMPLETADA")
print("=" * 80)
