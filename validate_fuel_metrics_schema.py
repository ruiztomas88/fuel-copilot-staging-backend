#!/usr/bin/env python3
"""
Validar que los nombres de columnas en fuel_metrics coincidan con el INSERT
"""

# Columnas en la tabla fuel_metrics (de la base de datos)
db_columns = [
    "id",  # auto_increment
    "timestamp_utc",
    "truck_id",
    "carrier_id",
    "truck_status",
    "latitude",
    "longitude",
    "speed_mph",
    "estimated_liters",
    "estimated_gallons",
    "estimated_pct",
    "sensor_pct",
    "sensor_liters",
    "sensor_gallons",
    "consumption_lph",
    "consumption_gph",
    "mpg_current",
    "rpm",
    "engine_hours",
    "odometer_mi",
    "altitude_ft",
    "hdop",
    "coolant_temp_f",
    "idle_gph",
    "idle_method",
    "idle_mode",
    "drift_pct",
    "drift_warning",
    "anchor_detected",
    "anchor_type",
    "data_age_min",
    "oil_pressure_psi",
    "oil_temp_f",
    "battery_voltage",
    "engine_load_pct",
    "def_level_pct",
    "ambient_temp_f",
    "intake_air_temp_f",
    "trans_temp_f",
    "fuel_temp_f",
    "intercooler_temp_f",
    "intake_press_kpa",
    "retarder_level",
    "sats",
    "pwr_int",
    "terrain_factor",
    "gps_quality",
    "idle_hours_ecu",
    "dtc",
    "dtc_code",
    "created_at",  # auto_generated
]

# Columnas que INSERT wialon_sync_enhanced.py (de la query INSERT)
insert_columns = [
    "timestamp_utc",
    "truck_id",
    "carrier_id",
    "truck_status",
    "latitude",
    "longitude",
    "speed_mph",
    "estimated_liters",
    "estimated_gallons",
    "estimated_pct",
    "sensor_pct",
    "sensor_liters",
    "sensor_gallons",
    "consumption_lph",
    "consumption_gph",
    "mpg_current",
    "rpm",
    "engine_hours",
    "odometer_mi",
    "altitude_ft",
    "hdop",
    "coolant_temp_f",
    "idle_gph",
    "idle_method",
    "idle_mode",
    "drift_pct",
    "drift_warning",
    "anchor_detected",
    "anchor_type",
    "data_age_min",
    "oil_pressure_psi",
    "oil_temp_f",
    "battery_voltage",
    "engine_load_pct",
    "def_level_pct",
    "ambient_temp_f",
    "intake_air_temp_f",
    "trans_temp_f",
    "fuel_temp_f",
    "intercooler_temp_f",
    "intake_press_kpa",
    "retarder_level",
    "sats",
    "pwr_int",
    "terrain_factor",
    "gps_quality",
    "idle_hours_ecu",
    "dtc",
    "dtc_code",
]

print("=" * 80)
print("🔍 VALIDACIÓN DE ESQUEMA fuel_metrics")
print("=" * 80)

# Columnas auto-generadas que no se insertan
auto_columns = ["id", "created_at"]
insertable_db_columns = [c for c in db_columns if c not in auto_columns]

# Verificar que todas las columnas insertables estén en el INSERT
missing_in_insert = set(insertable_db_columns) - set(insert_columns)
if missing_in_insert:
    print("\n❌ ERROR: Columnas en DB que NO se están insertando:")
    for col in sorted(missing_in_insert):
        print(f"   - {col}")
else:
    print("\n✅ Todas las columnas de la DB se están insertando correctamente")

# Verificar que no haya columnas en el INSERT que no existan en DB
extra_in_insert = set(insert_columns) - set(insertable_db_columns)
if extra_in_insert:
    print("\n❌ ERROR: Columnas en INSERT que NO existen en la DB:")
    for col in sorted(extra_in_insert):
        print(f"   - {col}")
    print(
        "\n⚠️  ACCIÓN REQUERIDA: Eliminar estas columnas del INSERT o agregarlas a la tabla"
    )
else:
    print("✅ No hay columnas extras en el INSERT")

print("\n" + "=" * 80)
print(f"📊 Resumen:")
print(f"   • Columnas en DB (insertables): {len(insertable_db_columns)}")
print(f"   • Columnas en INSERT: {len(insert_columns)}")
print(f"   • Columnas faltantes: {len(missing_in_insert)}")
print(f"   • Columnas extras: {len(extra_in_insert)}")
print("=" * 80)

if not missing_in_insert and not extra_in_insert:
    print("\n✅ ¡ESQUEMA PERFECTO! Todo coincide.")
else:
    print("\n❌ HAY PROBLEMAS DE CONSISTENCIA")
    exit(1)
