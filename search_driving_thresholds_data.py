#!/usr/bin/env python3
"""
Buscar en Wialon los datos correspondientes a los umbrales configurados:
- Driving Acceleration Threshold (280 mg)
- Driving Braking Threshold (320 mg)
- Driving Cornering Threshold (280 mg)
- Speed Over (105 km/h)

Revisar qué sensores/eventos existen para estos thresholds.
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
print("🔍 AUDITORÍA DE SENSORES CONFIGURADOS EN PROGRAMA vs WIALON")
print("=" * 80)

# Sensores que nuestro programa está intentando leer (de wialon_reader.py)
OUR_SENSORS = {
    "fuel_lvl": "fuel_lvl",
    "speed": "speed",
    "rpm": "rpm",
    "odometer": "odom",  # ← ESTO ES LO QUE EL PROGRAMA BUSCA
    "fuel_rate": "fuel_rate",
    "coolant_temp": "cool_temp",
    "hdop": "hdop",
    "altitude": "altitude",
    "engine_hours": "engine_hours",
    "pwr_ext": "pwr_ext",
    "oil_press": "oil_press",
    "total_fuel_used": "total_fuel_used",
    "total_idle_fuel": "total_idle_fuel",
    "engine_load": "engine_load",
    "ambient_temp": "air_temp",
    "oil_temp": "oil_temp",
    "def_level": "def_level",
    "intake_air_temp": "intk_t",
    "dtc": "dtc",
    "j1939_spn": "j1939_spn",
    "j1939_fmi": "j1939_fmi",
    "idle_hours": "idle_hours",
    "sats": "sats",
    "pwr_int": "pwr_int",
    "course": "course",
    "fuel_economy": "fuel_economy",
    "gear": "gear",
    "barometer": "barometer",
    "fuel_temp": "fuel_t",
    "intercooler_temp": "intrclr_t",
    "turbo_temp": "turbo_temp",
    "trans_temp": "trans_temp",
    "intake_press": "intake_pressure",
    "pto_hours": "pto_hours",
    "brake_app_press": "brake_app_press",
    "brake_primary_press": "brake_primary_press",
    "brake_secondary_press": "brake_secondary_press",
    "brake_switch": "brake_switch",
    "parking_brake": "parking_brake",
    "abs_status": "abs_status",
    "rpm_hi_res": "rpm_hi_res",
    "seatbelt": "seatbelt",
    "vin": "vin",
    # 🎯 ESTOS SON LOS QUE IMPORTAN PARA TU CONFIGURACIÓN:
    "harsh_accel": "harsh_accel",  # ← Acceleration Threshold 280mg
    "harsh_brake": "harsh_brake",  # ← Braking Threshold 320mg
    "harsh_corner": "harsh_corner",  # ← Cornering Threshold 280mg
    "rssi": "rssi",
    "coolant_level": "cool_lvl",
    "oil_level": "oil_level",
    "gps_locked": "gps_locked",
    "battery": "battery",
    "roaming": "roaming",
    "event_id": "event_id",
    "bus": "bus",
    "mode": "mode",
}

try:
    conn = pymysql.connect(**WIALON_CONFIG)
    cursor = conn.cursor()

    print(f"\n📋 Sensores configurados en nuestro programa: {len(OUR_SENSORS)}")
    print("=" * 80)

    # Verificar cuáles existen en Wialon
    print("\n🔍 Verificando existencia de cada sensor en Wialon (tabla sensors):")
    print("=" * 80)

    found = []
    missing = []

    # Categorías especiales
    driving_events = ["harsh_accel", "harsh_brake", "harsh_corner"]
    speed_related = ["speed", "fuel_economy"]

    for our_name, wialon_param in sorted(OUR_SENSORS.items()):
        cursor.execute(
            """
            SELECT COUNT(*) as total,
                   MIN(m) as first_timestamp,
                   MAX(m) as last_timestamp,
                   COUNT(DISTINCT unit) as trucks_count
            FROM sensors
            WHERE p = %s
        """,
            (wialon_param,),
        )

        result = cursor.fetchone()
        total = result[0]

        # Marcar categoría
        category = ""
        if our_name in driving_events:
            category = " 🎯 DRIVING EVENT"
        elif our_name in speed_related:
            category = " 🚗 SPEED"
        elif "temp" in our_name.lower():
            category = " 🌡️  TEMP"
        elif "press" in our_name.lower():
            category = " 📊 PRESSURE"
        elif "brake" in our_name.lower():
            category = " 🛑 BRAKE"

        if total > 0:
            found.append(our_name)
            # Calcular rango de fechas
            from datetime import datetime, timezone

            first_dt = datetime.fromtimestamp(result[1], tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )
            last_dt = datetime.fromtimestamp(result[2], tz=timezone.utc).strftime(
                "%Y-%m-%d"
            )

            status = f"✅ {our_name:25} → {wialon_param:20}"
            stats = f"{total:,} registros | {result[3]} trucks | {first_dt} → {last_dt}"
            print(f"{status:60}{category:20} | {stats}")
        else:
            missing.append(our_name)
            print(f"❌ {our_name:25} → {wialon_param:20}{category:20} | NO EXISTE")

    print("\n" + "=" * 80)
    print(f"📊 RESUMEN:")
    print(f"  ✅ Sensores encontrados: {len(found)} / {len(OUR_SENSORS)}")
    print(f"  ❌ Sensores faltantes: {len(missing)}")
    print("=" * 80)

    # Enfoque en los eventos de conducción
    print("\n" + "=" * 80)
    print("🎯 ANÁLISIS DE EVENTOS DE CONDUCCIÓN (tu configuración)")
    print("=" * 80)

    for event_name in driving_events:
        wialon_param = OUR_SENSORS[event_name]

        print(f"\n{'='*80}")
        print(f"📊 {event_name.upper().replace('_', ' ')}")
        print(f"{'='*80}")

        cursor.execute(
            """
            SELECT COUNT(*) as total FROM sensors WHERE p = %s
        """,
            (wialon_param,),
        )

        total = cursor.fetchone()[0]

        if total == 0:
            print(f"❌ No hay datos para '{wialon_param}'")
            print(
                "⚠️  Este threshold está configurado pero no se están reportando eventos"
            )
            continue

        print(f"✅ Total de eventos: {total:,}")

        # Top trucks con más eventos
        cursor.execute(
            """
            SELECT unit, COUNT(*) as count
            FROM sensors
            WHERE p = %s
            GROUP BY unit
            ORDER BY count DESC
            LIMIT 10
        """,
            (wialon_param,),
        )

        print(f"\n🚛 Top 10 trucks con más eventos:")
        for row in cursor.fetchall():
            print(f"  Unit {row[0]}: {row[1]:,} eventos")

        # Últimos eventos
        cursor.execute(
            """
            SELECT unit, value, from_datetime, from_latitude, from_longitude
            FROM sensors
            WHERE p = %s
            ORDER BY m DESC
            LIMIT 5
        """,
            (wialon_param,),
        )

        print(f"\n📝 Últimos 5 eventos:")
        for row in cursor.fetchall():
            print(
                f"  {row[2]} | Unit: {row[0]} | Valor: {row[1]} | GPS: {row[3]:.4f},{row[4]:.4f}"
            )

    # Verificar tabla speedings
    print("\n" + "=" * 80)
    print("🚨 TABLA SPEEDINGS (Speed Over 105 km/h)")
    print("=" * 80)

    cursor.execute("SELECT COUNT(*) FROM speedings")
    speedings_total = cursor.fetchone()[0]

    print(f"Total de eventos de speeding: {speedings_total:,}")

    if speedings_total > 0:
        cursor.execute(
            """
            SELECT unit, COUNT(*) as count
            FROM speedings
            GROUP BY unit
            ORDER BY count DESC
            LIMIT 10
        """
        )

        print(f"\n🚛 Top 10 trucks con más speeding:")
        for row in cursor.fetchall():
            print(f"  Unit {row[0]}: {row[1]:,} eventos")

        # Últimos eventos
        cursor.execute(
            """
            SELECT unit, max_speed, limit, from_datetime
            FROM speedings
            ORDER BY from_datetime DESC
            LIMIT 5
        """
        )

        print(f"\n📝 Últimos 5 eventos de speeding:")
        for row in cursor.fetchall():
            excess = row[1] - row[2]
            print(
                f"  {row[3]} | Unit: {row[0]} | Velocidad: {row[1]} mph | Límite: {row[2]} mph | Exceso: {excess} mph"
            )

    # ¿Qué más hay en sensors que no estamos usando?
    print("\n" + "=" * 80)
    print("🔍 SENSORES EN WIALON QUE NO ESTAMOS USANDO")
    print("=" * 80)

    cursor.execute(
        """
        SELECT DISTINCT p, COUNT(*) as total
        FROM sensors
        GROUP BY p
        ORDER BY total DESC
    """
    )

    all_wialon_params = cursor.fetchall()
    used_params = set(OUR_SENSORS.values())

    unused = []
    for param, count in all_wialon_params:
        if param not in used_params:
            unused.append((param, count))

    if unused:
        print(
            f"\n📋 Parámetros en Wialon NO usados por nuestro programa ({len(unused)}):"
        )
        for param, count in sorted(unused, key=lambda x: x[1], reverse=True)[:20]:
            print(f"  - {param:30} {count:,} registros")

    cursor.close()
    conn.close()

    print("\n" + "=" * 80)
    print("✅ Auditoría completada")
    print("=" * 80)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
"""
Buscar datos de eventos de conducción basados en los umbrales configurados:
- Driving Acceleration Threshold: 280 mg
- Driving Braking Threshold: 320 mg  
- Driving Cornering Threshold: 280 mg
- Report Speed Over: 105 km/h
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
print("🔍 BUSCANDO DATOS DE EVENTOS DE CONDUCCIÓN EN WIALON")
print("=" * 80)
print("\nUmbrales configurados:")
print("  • Aceleración: > 280 mg")
print("  • Frenado: > 320 mg")
print("  • Cornering: > 280 mg")
print("  • Velocidad: > 105 km/h")
print("=" * 80)

try:
    conn = pymysql.connect(**WIALON_CONFIG)
    cursor = conn.cursor()

    # 1. Buscar en TODAS las tablas por columnas relevantes
    print("\n🔍 PASO 1: Explorando todas las tablas...")
    cursor.execute("SHOW TABLES")
    tables = [row[0] for row in cursor.fetchall()]

    for table in tables:
        # Obtener columnas de cada tabla
        cursor.execute(f"DESCRIBE {table}")
        columns = cursor.fetchall()
        col_names = [col[0] for col in columns]

        # Buscar columnas que puedan contener eventos de conducción
        relevant_cols = [
            c
            for c in col_names
            if any(
                keyword in c.lower()
                for keyword in [
                    "accel",
                    "brake",
                    "corner",
                    "turn",
                    "harsh",
                    "event",
                    "violation",
                    "driving",
                ]
            )
        ]

        if relevant_cols:
            print(f"\n📋 Tabla: {table}")
            print(f"   Columnas relevantes: {', '.join(relevant_cols)}")

            # Contar registros
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"   Total registros: {count:,}")

            if count > 0 and count < 1000000:
                # Muestra de datos
                cursor.execute(f"SELECT * FROM {table} LIMIT 3")
                samples = cursor.fetchall()
                if samples:
                    print(f"\n   Muestra de datos:")
                    for i, row in enumerate(samples[:2], 1):
                        print(f"\n   Fila {i}:")
                        for j, col in enumerate(columns):
                            if row[j] is not None:
                                print(f"     {col[0]}: {row[j]}")

    # 2. Buscar en sensors por parámetros 'p' relacionados
    print("\n" + "=" * 80)
    print("🔍 PASO 2: Buscando parámetros en tabla sensors...")
    print("=" * 80)

    keywords = [
        "accel",
        "brake",
        "corner",
        "turn",
        "harsh",
        "threshold",
        "mg",
        "g-force",
        "lateral",
    ]

    for keyword in keywords:
        cursor.execute(
            f"""
            SELECT DISTINCT p, COUNT(*) as total
            FROM sensors
            WHERE p LIKE %s
            GROUP BY p
            ORDER BY total DESC
        """,
            (f"%{keyword}%",),
        )

        results = cursor.fetchall()
        if results:
            print(f"\n📊 Parámetros con '{keyword}':")
            for param, count in results:
                print(f"  - {param:50} → {count:,} registros")

                # Muestra de valores
                cursor.execute(
                    """
                    SELECT unit, value, text_value, from_datetime
                    FROM sensors
                    WHERE p = %s
                    ORDER BY from_datetime DESC
                    LIMIT 3
                """,
                    (param,),
                )

                samples = cursor.fetchall()
                for sample in samples:
                    txt_val = f" | Text: {sample[2]}" if sample[2] else ""
                    print(
                        f"      {sample[3]} | Unit: {sample[0]} | Value: {sample[1]}{txt_val}"
                    )

    # 3. Buscar en nombres de sensores (columna 'n')
    print("\n" + "=" * 80)
    print("🔍 PASO 3: Buscando en nombres de sensores...")
    print("=" * 80)

    for keyword in keywords:
        cursor.execute(
            f"""
            SELECT DISTINCT n, COUNT(*) as total
            FROM sensors
            WHERE n LIKE %s
            GROUP BY n
            ORDER BY total DESC
        """,
            (f"%{keyword}%",),
        )

        results = cursor.fetchall()
        if results:
            print(f"\n📊 Nombres con '{keyword}':")
            for name, count in results:
                print(f"  - {name:50} → {count:,} registros")

    # 4. Buscar valores numéricos cerca de los umbrales configurados
    print("\n" + "=" * 80)
    print("🔍 PASO 4: Buscando valores cercanos a umbrales (280-320 mg)...")
    print("=" * 80)

    cursor.execute(
        """
        SELECT DISTINCT p, n, COUNT(*) as total
        FROM sensors
        WHERE value BETWEEN 200 AND 400
        AND (p LIKE '%accel%' OR p LIKE '%brake%' OR p LIKE '%corner%'
             OR p LIKE '%g%' OR p LIKE '%force%' OR p LIKE '%harsh%')
        GROUP BY p, n
        ORDER BY total DESC
        LIMIT 10
    """
    )

    results = cursor.fetchall()
    if results:
        print(f"\nParámetros con valores en rango 200-400:")
        for param, name, count in results:
            print(f"  - p={param}, n={name} → {count:,} registros")
    else:
        print("  ❌ No se encontraron valores en ese rango")

    # 5. Buscar eventos en text_value
    print("\n" + "=" * 80)
    print("🔍 PASO 5: Buscando eventos en text_value...")
    print("=" * 80)

    cursor.execute(
        """
        SELECT DISTINCT text_value, COUNT(*) as total
        FROM sensors
        WHERE text_value IS NOT NULL
        AND text_value != ''
        AND (text_value LIKE '%accel%' 
             OR text_value LIKE '%brake%'
             OR text_value LIKE '%corner%'
             OR text_value LIKE '%harsh%'
             OR text_value LIKE '%event%')
        GROUP BY text_value
        ORDER BY total DESC
        LIMIT 20
    """
    )

    results = cursor.fetchall()
    if results:
        print(f"\nTextos encontrados ({len(results)}):")
        for text, count in results:
            print(f"  - {text:60} → {count:,} registros")

            # Muestra de eventos
            cursor.execute(
                """
                SELECT unit, p, n, from_datetime
                FROM sensors
                WHERE text_value = %s
                ORDER BY from_datetime DESC
                LIMIT 2
            """,
                (text,),
            )
            samples = cursor.fetchall()
            for sample in samples:
                print(f"      {sample[3]} | Unit: {sample[0]} | p={sample[1]}")
    else:
        print("  ❌ No se encontraron textos relacionados")

    # 6. Explorar tabla counters (puede tener contadores de eventos)
    if "counters" in tables:
        print("\n" + "=" * 80)
        print("🔍 PASO 6: Explorando tabla counters...")
        print("=" * 80)

        cursor.execute("DESCRIBE counters")
        cols = cursor.fetchall()
        print(f"\nEstructura ({len(cols)} columnas):")
        for col in cols:
            print(f"  - {col[0]:30} {col[1]}")

        cursor.execute("SELECT COUNT(*) FROM counters")
        count = cursor.fetchone()[0]
        print(f"\nTotal registros: {count:,}")

        if count > 0:
            cursor.execute("SELECT * FROM counters LIMIT 5")
            samples = cursor.fetchall()
            print("\nMuestra de datos:")
            for i, row in enumerate(samples, 1):
                print(f"\n  Fila {i}:")
                for j, col in enumerate(cols):
                    if row[j] is not None:
                        print(f"    {col[0]}: {row[j]}")

    cursor.close()
    conn.close()

    print("\n" + "=" * 80)
    print("✅ Búsqueda completada")
    print("=" * 80)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
    exit(1)
