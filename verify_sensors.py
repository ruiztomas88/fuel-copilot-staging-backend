import pymysql

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password=os.getenv("DB_PASSWORD"),
    database='fuel_copilot'
)

cur = conn.cursor()

# Verificar totales
cur.execute('''
    SELECT 
        COUNT(*) as total,
        COUNT(odometer_mi) as with_odometer,
        COUNT(def_temp_f) as with_def_temp,
        MAX(last_updated) as last_update
    FROM truck_sensors_cache
''')
import os
result = cur.fetchone()
print(f'📊 Total registros: {result[0]}')
print(f'   Con odometer: {result[1]}')
print(f'   Con DEF temp: {result[2]}')
print(f'   Última actualización: {result[3]}')

# Ver ejemplos
print('\n🚛 Primeros 3 trucks:')
cur.execute('''
    SELECT truck_id, odometer_mi, def_level_pct, dpf_soot_pct, transmission_temp_f
    FROM truck_sensors_cache 
    LIMIT 3
''')
for row in cur.fetchall():
    print(f'   Truck {row[0]}: Odometer={row[1]}, DEF={row[2]}%, DPF Soot={row[3]}%, Trans Temp={row[4]}°F')

conn.close()
