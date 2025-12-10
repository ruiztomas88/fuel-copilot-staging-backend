import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

try:
    # Conectar a fuel_copilot
    conn = pymysql.connect(
        host=os.getenv('LOCAL_DB_HOST', 'localhost'),
        port=int(os.getenv('LOCAL_DB_PORT', '3306')),
        user=os.getenv('LOCAL_DB_USER', 'fuel_admin'),
        password=os.getenv('LOCAL_DB_PASS', ''),
        database=os.getenv('LOCAL_DB_NAME', 'fuel_copilot'),
        charset='utf8mb4',
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,
    )

    cursor = conn.cursor()

    # Verificar fuel_metrics
    cursor.execute('SELECT COUNT(*) as total, COUNT(DISTINCT truck_id) as trucks FROM fuel_metrics WHERE timestamp_utc >= NOW() - INTERVAL 1 HOUR')
    result = cursor.fetchone()
    print(f'Fuel metrics (última hora): {result["total"]} registros de {result["trucks"]} camiones')

    # Verificar estado de camiones
    cursor.execute('''
        SELECT
            CASE
                WHEN speed_mph > 5 THEN 'MOVING'
                WHEN speed_mph <= 5 AND speed_mph >= 0 THEN 'STOPPED'
                ELSE 'UNKNOWN'
            END as status,
            COUNT(*) as count
        FROM fuel_metrics
        WHERE timestamp_utc >= NOW() - INTERVAL 1 HOUR
        GROUP BY
            CASE
                WHEN speed_mph > 5 THEN 'MOVING'
                WHEN speed_mph <= 5 AND speed_mph >= 0 THEN 'STOPPED'
                ELSE 'UNKNOWN'
            END
    ''')
    results = cursor.fetchall()
    print('Estado de camiones en fuel_copilot (última hora):')
    for row in results:
        print(f'  {row["status"]}: {row["count"]} registros')

    cursor.close()
    conn.close()

except Exception as e:
    print(f'Error: {e}')