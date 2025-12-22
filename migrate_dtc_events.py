"""
Migración: Actualizar dtc_events con columnas necesarias para el pull
"""
import pymysql
import os
from config import get_local_db_config

conn = pymysql.connect(**get_local_db_config())

cursor = conn.cursor()

print("=" * 70)
print("MIGRACIÓN: Actualizar dtc_events para wialon_sync_enhanced.py")
print("=" * 70)

# Agregar columnas faltantes
columns_to_add = [
    ("unit_id", "VARCHAR(50)", "AFTER truck_id"),
    ("timestamp_utc", "DATETIME", "AFTER unit_id"),
    ("component", "VARCHAR(100)", "AFTER dtc_code"),
    ("severity", "VARCHAR(20)", "AFTER component"),
    ("status", "VARCHAR(20) DEFAULT 'ACTIVE'", "AFTER severity"),
    ("description", "TEXT", "AFTER status"),
    ("action_required", "TEXT", "AFTER description"),
]

for col_name, col_type, position in columns_to_add:
    try:
        # Check if column exists
        cursor.execute(f"""
            SELECT COUNT(*) 
            FROM information_schema.COLUMNS 
            WHERE TABLE_SCHEMA = 'fuel_copilot' 
            AND TABLE_NAME = 'dtc_events' 
            AND COLUMN_NAME = '{col_name}'
        """)
        
        if cursor.fetchone()[0] == 0:
            # Column doesn't exist, add it
            cursor.execute(f"ALTER TABLE dtc_events ADD COLUMN {col_name} {col_type} {position}")
            print(f"✅ Agregada columna: {col_name}")
        else:
            print(f"⏭️  Columna ya existe: {col_name}")
    except Exception as e:
        print(f"❌ Error agregando {col_name}: {e}")

# Agregar índices útiles
indexes_to_add = [
    ("idx_severity", "severity"),
    ("idx_status", "status"),
    ("idx_timestamp", "timestamp_utc"),
]

for idx_name, idx_col in indexes_to_add:
    try:
        cursor.execute(f"CREATE INDEX {idx_name} ON dtc_events({idx_col})")
        print(f"✅ Agregado índice: {idx_name}")
    except Exception as e:
        if "Duplicate key name" in str(e):
            print(f"⏭️  Índice ya existe: {idx_name}")
        else:
            print(f"❌ Error agregando índice {idx_name}: {e}")

conn.commit()

# Verificar estructura final
cursor.execute("DESCRIBE dtc_events")
columns = cursor.fetchall()

print("\n" + "=" * 70)
print("ESTRUCTURA FINAL DE dtc_events:")
print("=" * 70)
for col in columns:
    print(f"{col[0]:20} {col[1]:20} {col[2]:10} {col[3]}")

cursor.close()
conn.close()

print("\n✅ Migración completada exitosamente")
