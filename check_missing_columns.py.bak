"""
Script para verificar qué columnas existen en fuel_metrics
y cuáles faltan en la query
"""
import os
os.environ['MYSQL_PASSWORD'] = 'FuelCopilot2025!'

from database_mysql import get_sqlalchemy_engine
from sqlalchemy import text

print("=" * 80)
print("🔍 VERIFICANDO COLUMNAS EN fuel_metrics")
print("=" * 80)

engine = get_sqlalchemy_engine()

with engine.connect() as conn:
    # Get all columns from fuel_metrics
    columns_query = text("""
        SELECT COLUMN_NAME
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = 'fuel_metrics'
        AND TABLE_SCHEMA = DATABASE()
        ORDER BY ORDINAL_POSITION
    """)
    
    result = conn.execute(columns_query).fetchall()
    existing_columns = {row[0] for row in result}
    
    print(f"\n✅ Columnas que SÍ existen en fuel_metrics ({len(existing_columns)}):")
    for col in sorted(existing_columns):
        print(f"   - {col}")

# Columns that the query tries to select
query_columns = [
    'truck_id',
    'timestamp_utc',
    'truck_status',
    'latitude',
    'longitude',
    'speed_mph',
    'estimated_liters',
    'estimated_pct',
    'sensor_pct',
    'sensor_liters',
    'consumption_gph',
    'idle_method',
    'mpg_current',
    'rpm',
    'odometer_mi',
    'anchor_type',
    'anchor_detected',
    'refuel_gallons',  # ❌ ESTA NO EXISTE
    'refuel_events_total',  # ❌ ESTA NO EXISTE
    'data_age_min',
    'idle_mode',
    'drift_pct',
    'drift_warning',
    'flags',
    'altitude_ft',
    'coolant_temp_f',
    'battery_voltage',
    'sats',
    'pwr_int',
    'gps_quality',
    'dtc',
    'dtc_code',
    'terrain_factor',
    'idle_hours_ecu',
]

missing_columns = [col for col in query_columns if col not in existing_columns]

if missing_columns:
    print(f"\n❌ Columnas que la query intenta usar pero NO EXISTEN ({len(missing_columns)}):")
    for col in missing_columns:
        print(f"   - {col}")

    print(f"\n💡 SOLUCIÓN:")
    print(f"   Hay que eliminar estas columnas de la query en database_mysql.py")
    print(f"   Función: get_latest_truck_data() línea ~168")
else:
    print(f"\n✅ Todas las columnas de la query existen!")
