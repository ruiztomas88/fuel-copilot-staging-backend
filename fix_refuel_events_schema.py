#!/usr/bin/env python
"""
Fix refuel_events table schema - agregar columnas faltantes que wialon_sync necesita
"""
import pymysql

print("=" * 80)
print("🔧 FIXING refuel_events TABLE SCHEMA")
print("=" * 80)

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor()

# Ver columnas actuales
cursor.execute("SHOW COLUMNS FROM refuel_events")
current_cols = [row[0] for row in cursor.fetchall()]
print(f"\n📋 Columnas actuales ({len(current_cols)}):")
for col in current_cols:
    print(f"  - {col}")

# Columnas que el código espera insertar
required_cols = {
    'timestamp_utc': 'DATETIME NOT NULL',
    'carrier_id': 'VARCHAR(50)',
    'latitude': 'DECIMAL(10, 6)',
    'longitude': 'DECIMAL(10, 6)',
    'validated': 'TINYINT DEFAULT 0',
    'fuel_before': 'DECIMAL(10, 2)',  # Ya existe como before_pct
    'fuel_after': 'DECIMAL(10, 2)',   # Ya existe as after_pct
}

# Agregar columnas faltantes
added = []
for col_name, col_type in required_cols.items():
    if col_name not in current_cols:
        # Mapear nombres si ya existen con otro nombre
        if col_name == 'fuel_before' and 'before_pct' in current_cols:
            print(f"  ✅ {col_name} -> usando before_pct existente")
            continue
        if col_name == 'fuel_after' and 'after_pct' in current_cols:
            print(f"  ✅ {col_name} -> usando after_pct existente")
            continue
        if col_name == 'timestamp_utc' and 'refuel_time' in current_cols:
            print(f"  ✅ {col_name} -> usando refuel_time existente")
            continue
            
        try:
            alter_sql = f"ALTER TABLE refuel_events ADD COLUMN {col_name} {col_type}"
            cursor.execute(alter_sql)
            print(f"  ✅ Added: {col_name} ({col_type})")
            added.append(col_name)
        except Exception as e:
            print(f"  ❌ Error adding {col_name}: {e}")

conn.commit()

if added:
    print(f"\n✅ Added {len(added)} columns to refuel_events")
else:
    print("\n✅ All columns already exist or mapped")

# Ver columnas finales
cursor.execute("SHOW COLUMNS FROM refuel_events")
final_cols = [row[0] for row in cursor.fetchall()]
print(f"\n📋 Columnas finales ({len(final_cols)}):")
for col in final_cols:
    print(f"  - {col}")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("✅ refuel_events TABLE SCHEMA UPDATED")
print("=" * 80)
print("\n💡 Ahora wialon_sync_enhanced.py podrá insertar refuels correctamente")
print("   Reinicia wialon_sync para que empiece a detectar refuels")
