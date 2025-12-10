import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

try:
    # Conectar a Wialon DB
    conn = pymysql.connect(
        host=os.getenv('WIALON_DB_HOST', 'localhost'),
        port=int(os.getenv('WIALON_DB_PORT', '3306')),
        user=os.getenv('WIALON_DB_USER', 'wialon_user'),
        password=os.getenv('WIALON_DB_PASS', ''),
        database=os.getenv('WIALON_DB_NAME', 'wialon'),
        charset='utf8mb4',
        connect_timeout=5,
        cursorclass=pymysql.cursors.DictCursor,
    )

    cursor = conn.cursor()

    # Verificar datos de sensores por camión
    cursor.execute('''
        SELECT n as truck, p as sensor, COUNT(*) as readings,
               MAX(m) as last_epoch, FROM_UNIXTIME(MAX(m)) as last_time
        FROM sensors
        WHERE m >= UNIX_TIMESTAMP() - 3600
        GROUP BY n, p
        ORDER BY n, p
        LIMIT 20
    ''')
    results = cursor.fetchall()

    print('Datos de sensores en Wialon (última hora):')
    current_truck = None
    for row in results:
        if current_truck != row['truck']:
            print(f'{row["truck"]}:')
            current_truck = row['truck']
        print(f'  {row["sensor"]}: {row["readings"]} lecturas (última: {row["last_time"]})')

    cursor.close()
    conn.close()

except Exception as e:
    print(f'Error: {e}')