#!/usr/bin/env python3
"""
🔍 AUDITORÍA: Consistencia de nombres de sensores en todo el programa

Verifica que todos los archivos usen los mismos nombres de sensores
que están configurados en wialon_sync_enhanced.py
"""
import os
import re
from collections import defaultdict

# Archivos principales a auditar
files_to_check = [
    "wialon_sync_enhanced.py",
    "api_v2.py",
    "fleet_command_center.py",
    "predictive_maintenance_engine.py",
    "theft_detection_engine.py",
    "driver_behavior_engine.py",
    "alert_service.py",
    "truck_health_monitor.py",
    "engine_health_engine.py",
    "wialon_data_loader.py",
    "models.py",
]

# Nombres oficiales de sensores (los que deberían usarse)
OFFICIAL_SENSOR_NAMES = {
    # Combustible
    "fuel_lvl": "Nivel de combustible (%)",
    "fuel_rate": "Consumo de combustible (GPH)",
    "fuel_temp": "Temperatura del combustible",
    "total_fuel_used": "Combustible total usado",
    "total_idle_fuel": "Combustible usado en idle",
    # Movimiento
    "speed": "Velocidad (MPH)",
    "rpm": "RPM del motor",
    "odometer_mi": "Odómetro en millas",
    # Motor
    "engine_hours": "Horas de motor",
    "idle_hours": "Horas en idle",
    "engine_load": "Carga del motor (%)",
    # Temperaturas
    "coolant_temp": "Temperatura refrigerante",
    "oil_temp": "Temperatura aceite motor",
    "trans_temp": "Temperatura transmisión",
    "ambient_temp": "Temperatura ambiente",
    "intake_air_temp": "Temperatura aire admisión",
    "intercooler_temp": "Temperatura intercooler",
    # Presiones
    "oil_press": "Presión de aceite",
    "intake_press": "Presión admisión (boost)",
    "turbo_pressure_psi": "Presión turbo (PSI)",
    "dpf_pressure_psi": "Presión DPF (PSI)",
    # Otros
    "def_level": "Nivel DEF (%)",
    "dtc": "Códigos diagnóstico",
    "alternator_status": "Estado alternador",
    "mpg": "MPG calculado por ECU",
    # GPS
    "latitude": "Latitud GPS",
    "longitude": "Longitud GPS",
    "altitude": "Altitud",
    "sats": "Satélites GPS",
    "hdop": "Precisión GPS (HDOP)",
}

# Nombres DEPRECADOS que NO deberían usarse
DEPRECATED_NAMES = {
    "odom": "odometer_mi",  # Cambió a odometer_mi
    "boost": "turbo_pressure_psi",  # Cambió a turbo_pressure_psi
    "turbo_press": "turbo_pressure_psi",  # Cambió a turbo_pressure_psi
    "dpf_press": "dpf_pressure_psi",  # Cambió a dpf_pressure_psi
    "dpf_diff_press": "dpf_pressure_psi",  # Cambió a dpf_pressure_psi
    "alternator": "alternator_status",  # Cambió a alternator_status
    "odometer": "odometer_mi",  # Usar específico odometer_mi
}

print("=" * 100)
print("🔍 AUDITORÍA DE CONSISTENCIA DE NOMBRES DE SENSORES")
print("=" * 100)

sensor_usage = defaultdict(lambda: {"files": set(), "count": 0})
deprecated_usage = defaultdict(lambda: {"files": set(), "lines": []})

for filename in files_to_check:
    if not os.path.exists(filename):
        continue

    with open(filename, "r") as f:
        lines = f.readlines()

    for line_num, line in enumerate(lines, 1):
        # SKIP líneas que son queries SQL o acceso a columnas de DB (no sensores)
        if "SELECT" in line or "FROM" in line or 't["' in line or 'row["' in line:
            continue

        # Buscar accesos a sensores
        # Patrones: sensor_data.get('fuel_lvl'), data.get("speed")
        matches = re.findall(r"sensor_data\.get\([\"\']([\w_]+)[\"\']\)", line)
        matches += re.findall(r"data\.get\([\"\']([\w_]+)[\"\']\)", line)

        for match in matches:
            # Verificar si es un sensor oficial
            if match in OFFICIAL_SENSOR_NAMES:
                sensor_usage[match]["files"].add(filename)
                sensor_usage[match]["count"] += 1

            # Verificar si es un nombre deprecado
            elif match in DEPRECATED_NAMES:
                deprecated_usage[match]["files"].add(filename)
                deprecated_usage[match]["lines"].append(
                    (filename, line_num, line.strip())
                )

# ============================================================================
# REPORTE
# ============================================================================

print("\n" + "=" * 100)
print("📊 PARTE 1: SENSORES OFICIALES EN USO")
print("=" * 100)

print(f"\nTotal de sensores diferentes encontrados: {len(sensor_usage)}")

# Agrupar por categoría
categories = {
    "Combustible": [
        "fuel_lvl",
        "fuel_rate",
        "fuel_temp",
        "total_fuel_used",
        "total_idle_fuel",
    ],
    "Movimiento": ["speed", "rpm", "odometer_mi"],
    "Motor": ["engine_hours", "idle_hours", "engine_load"],
    "Temperaturas": [
        "coolant_temp",
        "oil_temp",
        "trans_temp",
        "ambient_temp",
        "intake_air_temp",
        "intercooler_temp",
    ],
    "Presiones": [
        "oil_press",
        "intake_press",
        "turbo_pressure_psi",
        "dpf_pressure_psi",
    ],
    "Otros": ["def_level", "dtc", "alternator_status", "mpg"],
    "GPS": ["latitude", "longitude", "altitude", "sats", "hdop"],
}

for category, sensors in categories.items():
    found_in_category = [s for s in sensors if s in sensor_usage]
    if found_in_category:
        print(f"\n📁 {category}:")
        for sensor in found_in_category:
            info = sensor_usage[sensor]
            description = OFFICIAL_SENSOR_NAMES.get(sensor, "Sin descripción")
            print(
                f"  ✅ {sensor:25} → usado {info['count']:3}x en {len(info['files'])} archivos - {description}"
            )

# Sensores oficiales NO usados
unused_official = set(OFFICIAL_SENSOR_NAMES.keys()) - set(sensor_usage.keys())
if unused_official:
    print(f"\n⚠️  SENSORES OFICIALES NO USADOS ({len(unused_official)}):")
    for sensor in sorted(unused_official):
        print(f"  - {sensor:25} → {OFFICIAL_SENSOR_NAMES[sensor]}")

# ============================================================================
# NOMBRES DEPRECADOS (PROBLEMA!)
# ============================================================================

if deprecated_usage:
    print("\n" + "=" * 100)
    print("❌ PARTE 2: NOMBRES DEPRECADOS ENCONTRADOS (DEBEN CORREGIRSE)")
    print("=" * 100)

    for old_name, info in sorted(deprecated_usage.items()):
        new_name = DEPRECATED_NAMES[old_name]
        print(f"\n⚠️  '{old_name}' → debe cambiarse a '{new_name}'")
        print(f"   Encontrado en {len(info['files'])} archivo(s):")
        for filename in sorted(info["files"]):
            print(f"     • {filename}")

        # Mostrar primeras 3 líneas como ejemplo
        print(f"   Ejemplos:")
        for filename, line_num, line in info["lines"][:3]:
            print(f"     L{line_num}: {line[:80]}")
else:
    print("\n" + "=" * 100)
    print("✅ PARTE 2: NO HAY NOMBRES DEPRECADOS - TODO CORRECTO")
    print("=" * 100)

# ============================================================================
# VERIFICACIÓN DE ARCHIVOS CRÍTICOS
# ============================================================================

print("\n" + "=" * 100)
print("📋 PARTE 3: VERIFICACIÓN POR ARCHIVO CRÍTICO")
print("=" * 100)

for filename in files_to_check:
    if not os.path.exists(filename):
        print(f"\n⚠️  {filename}: NO EXISTE")
        continue

    # Contar sensores usados en este archivo
    sensors_in_file = [
        s for s, info in sensor_usage.items() if filename in info["files"]
    ]
    deprecated_in_file = [
        s for s, info in deprecated_usage.items() if filename in info["files"]
    ]

    status = "✅" if not deprecated_in_file else "⚠️"
    print(f"\n{status} {filename}:")
    print(f"   Sensores oficiales: {len(sensors_in_file)}")
    if sensors_in_file:
        print(f"   Usa: {', '.join(sorted(sensors_in_file)[:10])}")
    if deprecated_in_file:
        print(f"   ⚠️  Nombres deprecados: {', '.join(deprecated_in_file)}")

# ============================================================================
# RECOMENDACIONES
# ============================================================================

print("\n" + "=" * 100)
print("💡 RECOMENDACIONES")
print("=" * 100)

if deprecated_usage:
    print("\n⚠️  ACCIÓN REQUERIDA:")
    print("   Reemplazar los siguientes nombres deprecados:")
    for old_name, new_name in DEPRECATED_NAMES.items():
        if old_name in deprecated_usage:
            count = sum(1 for _, info in deprecated_usage.items() if old_name in info)
            print(f"     • '{old_name}' → '{new_name}'")
else:
    print("\n✅ TODO CORRECTO:")
    print("   • Todos los archivos usan nombres de sensores consistentes")
    print("   • No hay nombres deprecados en uso")
    print("   • El programa está streamlined con nomenclatura única")

print("\n" + "=" * 100)
print("✅ AUDITORÍA COMPLETADA")
print("=" * 100)
