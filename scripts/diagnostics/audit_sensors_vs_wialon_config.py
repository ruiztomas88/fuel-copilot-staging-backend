#!/usr/bin/env python3
"""
🔍 AUDITORÍA COMPLETA: Sensores que usa el programa VS configuración de Wialon

Compara:
1. Sensores que lee wialon_sync_enhanced.py
2. Configuraciones de umbrales que pusiste en Wialon
3. Datos disponibles en tabla sensors de Wialon
"""
import os
from collections import defaultdict

import pymysql
from dotenv import load_dotenv

load_dotenv()

WIALON_CONFIG = {
    "host": "20.127.200.135",
    "port": 3306,
    "database": "wialon_collect",
    "user": "tomas",
    "password": "Tomas2025",
}

# Sensores que ACTUALMENTE usa wialon_sync_enhanced.py (del análisis de código)
SENSORS_USED_BY_PROGRAM = {
    "altitude": "Altitud para ajuste de terreno",
    "ambient_temp": "Temperatura ambiente",
    "coolant_temp": "Temperatura refrigerante (alertas)",
    "def_level": "Nivel de DEF (diesel exhaust fluid)",
    "dtc": "Códigos de diagnóstico (alertas)",
    "dtc_code": "Código DTC específico",
    "engine_hours": "Horas de motor (mantenimiento)",
    "engine_load": "Carga del motor",
    "fuel_lvl": "Nivel de combustible (PRINCIPAL)",
    "fuel_rate": "Consumo de combustible (GPH)",
    "fuel_temp": "Temperatura del combustible",
    "hdop": "Precisión GPS",
    "idle_hours": "Horas en idle",
    "intake_air_temp": "Temperatura aire admisión",
    "intake_press": "Presión de admisión (turbo)",
    "intercooler_temp": "Temperatura intercooler",
    "latitude": "Ubicación GPS",
    "longitude": "Ubicación GPS",
    "mpg": "MPG calculado por ECU",
    "odometer": "Odómetro (millas)",
    "oil_press": "Presión de aceite (alertas)",
    "oil_temp": "Temperatura aceite",
    "rpm": "RPM del motor",
    "sats": "Satélites GPS visibles",
    "speed": "Velocidad (MPH)",
    "total_fuel_used": "Combustible total usado",
    "total_idle_fuel": "Combustible usado en idle",
    "trans_temp": "Temperatura transmisión (alertas)",
}

# Configuraciones que pusiste en Wialon (de la imagen)
WIALON_CONFIGS = {
    "Engine Idle Timer (min)": "5 minutos",
    "Report Towing Detection": "Enable",
    "Engine On Periodic Timer (s)": "60 segundos",
    "Temp Alert High 1": "105°C",
    "Driving Acceleration Threshold (mg)": "280 mg",
    "Driving Braking Threshold (mg)": "320 mg",
    "Driving Cornering Threshold (mg)": "280 mg",
    "Report Speed Over (km/h)": "105 km/h",
    "Battery Low Threshold (10 mV)": "1150",
}

print("=" * 100)
print("🔍 AUDITORÍA COMPLETA: SENSORES DEL PROGRAMA VS CONFIGURACIÓN DE WIALON")
print("=" * 100)

try:
    conn = pymysql.connect(**WIALON_CONFIG)
    cursor = conn.cursor()

    # ====================================================================
    # PARTE 1: ¿Qué sensores está usando el programa?
    # ====================================================================
    print("\n" + "=" * 100)
    print("📋 PARTE 1: SENSORES QUE USA wialon_sync_enhanced.py")
    print("=" * 100)

    print(
        f"\nTotal de sensores diferentes que lee el programa: {len(SENSORS_USED_BY_PROGRAM)}\n"
    )
    for i, (sensor, description) in enumerate(
        sorted(SENSORS_USED_BY_PROGRAM.items()), 1
    ):
        print(f"{i:2}. {sensor:25} → {description}")

    # ====================================================================
    # PARTE 2: ¿Existen estos sensores en Wialon?
    # ====================================================================
    print("\n" + "=" * 100)
    print("📊 PARTE 2: VERIFICANDO SI ESTOS SENSORES EXISTEN EN WIALON")
    print("=" * 100)

    sensor_stats = {}

    for sensor_name in SENSORS_USED_BY_PROGRAM.keys():
        # Buscar en columna 'p' (parámetro)
        cursor.execute(
            """
            SELECT COUNT(*) as total,
                   COUNT(DISTINCT unit) as trucks,
                   MAX(from_datetime) as ultimo_registro
            FROM sensors
            WHERE p = %s
        """,
            (sensor_name,),
        )

        result = cursor.fetchone()
        total_registros = result[0] if result else 0
        trucks_con_dato = result[1] if result else 0
        ultimo_registro = result[2] if result else None

        sensor_stats[sensor_name] = {
            "total": total_registros,
            "trucks": trucks_con_dato,
            "ultimo": ultimo_registro,
            "existe": total_registros > 0,
        }

    # Mostrar resultados
    print("\n✅ SENSORES QUE EXISTEN EN WIALON:")
    existe_count = 0
    for sensor, stats in sorted(sensor_stats.items()):
        if stats["existe"]:
            existe_count += 1
            print(
                f"  ✅ {sensor:25} → {stats['total']:,} registros, {stats['trucks']} trucks, último: {stats['ultimo']}"
            )

    print(f"\n❌ SENSORES QUE NO EXISTEN EN WIALON (PROBLEMA!!):")
    falta_count = 0
    for sensor, stats in sorted(sensor_stats.items()):
        if not stats["existe"]:
            falta_count += 1
            uso = SENSORS_USED_BY_PROGRAM[sensor]
            print(f"  ❌ {sensor:25} → {uso}")

    print(
        f"\n📊 Resumen: {existe_count}/{len(SENSORS_USED_BY_PROGRAM)} sensores existen en Wialon"
    )

    # ====================================================================
    # PARTE 3: Configuraciones de Wialon vs Sensores disponibles
    # ====================================================================
    print("\n" + "=" * 100)
    print("⚙️  PARTE 3: CONFIGURACIONES DE WIALON QUE PUSISTE")
    print("=" * 100)

    print("\nConfiguraciones activas en Wialon:")
    for config, valor in WIALON_CONFIGS.items():
        print(f"  • {config:45} = {valor}")

    # ====================================================================
    # PARTE 4: ¿Hay sensores de aceleración/frenado/speeding?
    # ====================================================================
    print("\n" + "=" * 100)
    print("🚨 PARTE 4: BUSCANDO DATOS DE CONDUCCIÓN (ACELERACIÓN/FRENADO/SPEEDING)")
    print("=" * 100)

    # Buscar parámetros relacionados
    driving_keywords = [
        "accel%",
        "brake%",
        "harsh%",
        "corner%",
        "speed%",
        "violation%",
        "g_force%",
        "threshold%",
    ]

    found_params = []
    for keyword in driving_keywords:
        cursor.execute(
            """
            SELECT DISTINCT p, COUNT(*) as total
            FROM sensors
            WHERE p LIKE %s
            GROUP BY p
            ORDER BY total DESC
        """,
            (keyword,),
        )

        results = cursor.fetchall()
        found_params.extend(results)

    if found_params:
        print(
            f"\n✅ Parámetros de conducción encontrados en sensors ({len(found_params)}):"
        )
        for param, count in found_params:
            print(f"  - {param:40} → {count:,} registros")
    else:
        print(
            "\n❌ NO se encontraron parámetros de aceleración/frenado en tabla sensors"
        )
        print(
            "   ⚠️  Los umbrales que configuraste NO se están reportando como sensores!"
        )

    # ====================================================================
    # PARTE 5: Tabla speedings (excesos de velocidad)
    # ====================================================================
    print("\n" + "=" * 100)
    print("🚨 PARTE 5: TABLA SPEEDINGS (EXCESOS DE VELOCIDAD)")
    print("=" * 100)

    cursor.execute("SELECT COUNT(*) FROM speedings")
    speedings_count = cursor.fetchone()[0]

    if speedings_count > 0:
        cursor.execute(
            """
            SELECT 
                COUNT(*) as eventos,
                COUNT(DISTINCT unit) as trucks,
                MIN(from_datetime) as primer_evento,
                MAX(from_datetime) as ultimo_evento,
                AVG(max_speed) as velocidad_promedio,
                AVG(max_speed - `limit`) as exceso_promedio
            FROM speedings
        """
        )

        stats = cursor.fetchone()
        print(f"\n✅ TABLA speedings tiene datos:")
        print(f"  • Total eventos: {stats[0]:,}")
        print(f"  • Trucks involucrados: {stats[1]}")
        print(f"  • Período: {stats[2]} → {stats[3]}")
        print(f"  • Velocidad promedio: {stats[4]:.1f} mph")
        print(f"  • Exceso promedio: {stats[5]:.1f} mph sobre el límite")

        # Top speeders
        cursor.execute(
            """
            SELECT unit, COUNT(*) as eventos
            FROM speedings
            GROUP BY unit
            ORDER BY eventos DESC
            LIMIT 5
        """
        )

        print(f"\n  Top 5 trucks con más speeding:")
        for unit, eventos in cursor.fetchall():
            print(f"    - Unit {unit}: {eventos} eventos")
    else:
        print(
            "\n⚠️  Tabla speedings está VACÍA - no hay eventos de speeding registrados"
        )

    # ====================================================================
    # PARTE 6: RECOMENDACIONES
    # ====================================================================
    print("\n" + "=" * 100)
    print("💡 PARTE 6: RECOMENDACIONES")
    print("=" * 100)

    print("\n📊 RESUMEN:")
    print(f"  • Sensores que usa el programa: {len(SENSORS_USED_BY_PROGRAM)}")
    print(f"  • Sensores que existen en Wialon: {existe_count}")
    print(f"  • Sensores FALTANTES: {falta_count}")
    print(f"  • Configuraciones de umbrales: {len(WIALON_CONFIGS)}")
    print(f"  • Eventos de speeding en BD: {speedings_count:,}")

    print("\n🎯 CONCLUSIONES:")

    if falta_count > 0:
        print(
            f"\n  ⚠️  HAY {falta_count} SENSORES QUE EL PROGRAMA BUSCA PERO NO EXISTEN:"
        )
        print(
            "     → El programa podría fallar o tener valores NULL para estos sensores"
        )
        print("     → Revisar si los nombres de sensores cambiaron en Wialon")

    print("\n  ✅ DATOS DE SPEEDING:")
    if speedings_count > 0:
        print("     → Tabla speedings tiene datos - puedes implementar alertas")
        print("     → Configuración 'Report Speed Over' SÍ está funcionando")
    else:
        print("     → Tabla speedings VACÍA - verificar configuración en Wialon")

    print("\n  ❌ DATOS DE ACELERACIÓN/FRENADO:")
    if not found_params:
        print("     → NO hay datos de harsh accel/brake en tabla sensors")
        print(
            "     → Configuraste umbrales pero Wialon NO los está reportando como sensores"
        )
        print("     → Soluciones:")
        print("        1. Verificar en Wialon si hay tabla dedicada para eventos")
        print("        2. Crear reportes personalizados para extraer estos datos")
        print("        3. Calcular manualmente desde cambios de velocidad")

    cursor.close()
    conn.close()

    print("\n" + "=" * 100)
    print("✅ AUDITORÍA COMPLETADA")
    print("=" * 100)

except Exception as e:
    print(f"\n❌ ERROR: {e}")
    import traceback

    traceback.print_exc()
