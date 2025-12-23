"""
Script para verificar tablas faltantes en fuel_copilot database
"""
import os
import pymysql

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password=os.getenv("DB_PASSWORD"),
    database='fuel_copilot'
)

cursor = conn.cursor()

tables_to_check = [
    'trip_data',
    'cost_per_mile_history',
    'utilization_metrics',
    'dtc_events',
    'fuel_metrics'
]

print("=" * 60)
print("VERIFICACIÓN DE TABLAS")
print("=" * 60)

for table in tables_to_check:
    try:
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f'✅ {table:30} {count:>10} registros')
    except Exception as e:
        print(f'❌ {table:30} NO EXISTE')

print("\n" + "=" * 60)
print("VERIFICACIÓN DE DTCs ACTIVOS")
print("=" * 60)

cursor.execute('SELECT COUNT(*) FROM dtc_events WHERE cleared_at IS NULL')
active_dtcs = cursor.fetchone()[0]
print(f'DTCs activos (cleared_at IS NULL): {active_dtcs}')

cursor.execute('SELECT COUNT(*) FROM dtc_events')
total_dtcs = cursor.fetchone()[0]
print(f'Total DTCs en tabla: {total_dtcs}')

cursor.close()
conn.close()
