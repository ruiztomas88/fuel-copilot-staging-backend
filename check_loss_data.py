import pymysql

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)

cursor = conn.cursor()

# Datos 24h
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN truck_status='STOPPED' AND consumption_gph > 0.1 THEN 1 END) as idle_count,
        COUNT(CASE WHEN truck_status='MOVING' THEN 1 END) as moving_count
    FROM fuel_metrics 
    WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 24 HOUR)
""")

row = cursor.fetchone()
print(f"Datos 24h: {row[0]} total, {row[1]} idle, {row[2]} moving")

# Verificar si hay datos recientes
cursor.execute("""
    SELECT MAX(timestamp_utc) as last_update,
           COUNT(DISTINCT truck_id) as truck_count
    FROM fuel_metrics
""")

row = cursor.fetchone()
print(f"Última actualización: {row[0]}")
print(f"Camiones con datos: {row[1]}")

cursor.close()
conn.close()
