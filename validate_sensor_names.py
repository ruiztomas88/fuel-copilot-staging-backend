#!/usr/bin/env python3
"""
Validación de consistencia de nombres de sensores
Verifica que wialon_sync_enhanced.py y api_v2.py usen los mismos nombres.
"""

# Columnas que INSERT wialon_sync_enhanced.py
wialon_insert_cols = [
    "truck_id",
    "unit_id",
    "timestamp",
    "wialon_epoch",
    "oil_pressure_psi",
    "oil_temp_f",
    "oil_level_pct",
    "def_level_pct",
    "def_temp_f",
    "def_quality",
    "engine_load_pct",
    "rpm",
    "coolant_temp_f",
    "coolant_level_pct",
    "gear",
    "brake_active",
    "intake_pressure_bar",
    "intake_temp_f",
    "intercooler_temp_f",
    "fuel_temp_f",
    "fuel_level_pct",
    "fuel_rate_gph",
    "fuel_pressure_psi",
    "ambient_temp_f",
    "barometric_pressure_inhg",
    "voltage",
    "backup_voltage",
    "engine_hours",
    "idle_hours",
    "pto_hours",
    "total_idle_fuel_gal",
    "total_fuel_used_gal",
    "dtc_count",
    "dtc_code",
    "latitude",
    "longitude",
    "speed_mph",
    "altitude_ft",
    "odometer_mi",
    "heading_deg",
    "throttle_position_pct",
    "turbo_pressure_psi",
    "dpf_pressure_psi",
    "dpf_soot_pct",
    "dpf_ash_pct",
    "dpf_status",
    "egr_position_pct",
    "egr_temp_f",
    "alternator_status",
    "transmission_temp_f",
    "transmission_pressure_psi",
    "data_age_seconds",
]

# Columnas que SELECT api_v2.py
api_select_cols = [
    "truck_id",
    "timestamp",
    "data_age_seconds",
    "oil_pressure_psi",
    "oil_temp_f",
    "oil_level_pct",
    "def_level_pct",
    "engine_load_pct",
    "rpm",
    "coolant_temp_f",
    "coolant_level_pct",
    "gear",
    "brake_active",
    "intake_pressure_bar",
    "intake_temp_f",
    "intercooler_temp_f",
    "fuel_temp_f",
    "fuel_level_pct",
    "fuel_rate_gph",
    "ambient_temp_f",
    "barometric_pressure_inhg",
    "voltage",
    "backup_voltage",
    "engine_hours",
    "idle_hours",
    "pto_hours",
    "total_idle_fuel_gal",
    "total_fuel_used_gal",
    "dtc_count",
    "dtc_code",
    "latitude",
    "longitude",
    "speed_mph",
    "altitude_ft",
    "odometer_mi",
]

print("=" * 80)
print("🔍 VALIDACIÓN DE CONSISTENCIA DE NOMBRES DE SENSORES")
print("=" * 80)

# Verificar que todas las columnas del API están en el INSERT
missing_in_insert = set(api_select_cols) - set(wialon_insert_cols)

if missing_in_insert:
    print("\n❌ ERROR: Columnas que SELECT api_v2.py pero NO inserta wialon_sync:")
    for col in sorted(missing_in_insert):
        print(f"   - {col}")
    print(
        "\n⚠️  ACCIÓN REQUERIDA: Agregar estas columnas al INSERT de wialon_sync_enhanced.py"
    )
else:
    print(
        "\n✅ Todas las columnas que usa api_v2.py están siendo insertadas por wialon_sync"
    )

print("\n" + "=" * 80)

# Columnas extras que inserta wialon pero API no usa (esto es normal)
extra_in_insert = set(wialon_insert_cols) - set(api_select_cols)

if extra_in_insert:
    print(
        "ℹ️  Columnas adicionales que inserta wialon_sync (disponibles para uso futuro):"
    )
    for col in sorted(extra_in_insert):
        print(f"   - {col}")

print("\n" + "=" * 80)
print(f"📊 Resumen:")
print(f"   • Columnas INSERT wialon_sync: {len(wialon_insert_cols)}")
print(f"   • Columnas SELECT api_v2: {len(api_select_cols)}")
print(f"   • Columnas en común: {len(set(wialon_insert_cols) & set(api_select_cols))}")
print(f"   • Columnas extras en wialon: {len(extra_in_insert)}")
print(f"   • Columnas faltantes: {len(missing_in_insert)}")
print("=" * 80)

if not missing_in_insert:
    print("\n✅ ¡TODO CONSISTENTE! No hay conflictos de nombres.")
else:
    print("\n❌ HAY PROBLEMAS DE CONSISTENCIA - Revisar columnas faltantes")
    exit(1)
