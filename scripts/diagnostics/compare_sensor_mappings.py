#!/usr/bin/env python3
"""
Comparación de mapeos de sensores Wialon:
sensor_cache_updater.py vs wialon_sync_enhanced.py
"""

# Mapeos de sensor_cache_updater.py (ORIGINAL - CORRECTO)
sensor_cache_mappings = {
    "oil_press": "oil_pressure_psi",
    "oil_temp": "oil_temp_f",
    "oil_lvl": "oil_level_pct",
    "def_level": "def_level_pct",
    "def_temp": "def_temp_f",
    "def_quality": "def_quality",
    "engine_load": "engine_load_pct",
    "rpm": "rpm",
    "cool_temp": "coolant_temp_f",
    "cool_lvl": "coolant_level_pct",
    "gear": "gear",
    "brake_switch": "brake_active",
    "intake_pressure": "intake_pressure_bar",
    "intk_t": "intake_temp_f",
    "intrclr_t": "intercooler_temp_f",
    "fuel_t": "fuel_temp_f",
    "fuel_lvl": "fuel_level_pct",
    "fuel_rate": "fuel_rate_gph",
    "fuel_press": "fuel_pressure_psi",
    "ambient_temp": "ambient_temp_f",
    "barometer": "barometric_pressure_inhg",
    "pwr_ext": "voltage",
    "pwr_int": "backup_voltage",
    "engine_hours": "engine_hours",
    "idle_hours": "idle_hours",
    "pto_hours": "pto_hours",
    "total_idle_fuel": "total_idle_fuel_gal",
    "total_fuel_used": "total_fuel_used_gal",
    "dtc": "dtc_count",
    "dtc_code": "dtc_code",
    "speed": "speed_mph",
    "altitude": "altitude_ft",
    "odom": "odometer_mi",  # ⚠️ IMPORTANTE: Wialon usa 'odom' no 'odometer'
    "course": "heading_deg",  # ⚠️ IMPORTANTE: Wialon usa 'course' no 'heading'
    "throttle_pos": "throttle_position_pct",
    "turbo_press": "turbo_pressure_psi",  # ⚠️ IMPORTANTE: Wialon usa 'turbo_press' no 'boost'
    "dpf_press": "dpf_pressure_psi",  # ⚠️ sensor_cache usa 'dpf_press'
    "dpf_soot": "dpf_soot_pct",
    "dpf_ash": "dpf_ash_pct",
    "dpf_status": "dpf_status",
    "egr_pos": "egr_position_pct",
    "egr_temp": "egr_temp_f",
    "alternator_status": "alternator_status",
    "trans_temp": "transmission_temp_f",
    "trans_press": "transmission_pressure_psi",
}

# Mapeos que usa actualmente wialon_sync_enhanced.py
wialon_sync_mappings = {
    "oil_press": "oil_pressure_psi",
    "oil_temp": "oil_temp_f",
    "oil_lvl": "oil_level_pct",
    "def_level": "def_level_pct",
    "def_temp": "def_temp_f",
    "def_quality": "def_quality",
    "engine_load": "engine_load_pct",
    "rpm": "rpm",
    "cool_temp": "coolant_temp_f",
    "cool_lvl": "coolant_level_pct",
    "gear": "gear",
    "brake_switch": "brake_active",
    "intake_pressure": "intake_pressure_bar",
    "intk_t": "intake_temp_f",
    "intrclr_t": "intercooler_temp_f",
    "fuel_t": "fuel_temp_f",
    "fuel_lvl": "fuel_level_pct",
    "fuel_rate": "fuel_rate_gph",
    "fuel_press": "fuel_pressure_psi",
    "ambient_temp": "ambient_temp_f",
    "barometer": "barometric_pressure_inhg",
    "pwr_ext": "voltage",
    "pwr_int": "backup_voltage",
    "engine_hours": "engine_hours",
    "idle_hours": "idle_hours",
    "pto_hours": "pto_hours",
    "total_idle_fuel": "total_idle_fuel_gal",
    "total_fuel_used": "total_fuel_used_gal",
    "dtc": "dtc_count",
    "dtc_code": "dtc_code",
    "speed": "speed_mph",
    "altitude": "altitude_ft",
    "odometer": "odometer_mi",  # ❌ INCORRECTO: debería ser 'odom'
    "course": "heading_deg",
    "throttle_pos": "throttle_position_pct",
    "boost": "turbo_pressure_psi",  # ❌ INCORRECTO: debería ser 'turbo_press'
    "dpf_diff_press": "dpf_pressure_psi",  # ❌ DIFERENTE: sensor_cache usa 'dpf_press'
    "dpf_soot": "dpf_soot_pct",
    "dpf_ash": "dpf_ash_pct",
    "dpf_status": "dpf_status",
    "egr_pos": "egr_position_pct",
    "egr_temp": "egr_temp_f",
    "alternator": "alternator_status",  # ❌ INCORRECTO: debería ser 'alternator_status'
    "trans_temp": "transmission_temp_f",
    "trans_press": "transmission_pressure_psi",
}

print("=" * 80)
print("🔍 COMPARACIÓN DE MAPEOS DE SENSORES WIALON")
print("=" * 80)

errors = []

for wialon_key, db_col in sensor_cache_mappings.items():
    # Buscar qué key usa wialon_sync para la misma columna DB
    wialon_sync_key = None
    for key, col in wialon_sync_mappings.items():
        if col == db_col:
            wialon_sync_key = key
            break

    if wialon_sync_key != wialon_key:
        errors.append(
            {
                "db_column": db_col,
                "correct_wialon_key": wialon_key,
                "current_wialon_key": wialon_sync_key or "MISSING",
            }
        )

if errors:
    print("\n❌ ERRORES ENCONTRADOS:\n")
    for err in errors:
        print(f"Columna DB: {err['db_column']}")
        print(f"  ✅ Correcto (sensor_cache): {err['correct_wialon_key']}")
        print(f"  ❌ Actual (wialon_sync):    {err['current_wialon_key']}")
        print()

    print("=" * 80)
    print(f"\n❌ TOTAL: {len(errors)} inconsistencias encontradas")
    print(
        "\n⚠️  ACCIÓN REQUERIDA: Actualizar wialon_sync_enhanced.py con los nombres correctos"
    )
else:
    print("\n✅ ¡TODOS LOS MAPEOS SON CONSISTENTES!")

print("=" * 80)
