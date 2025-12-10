import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

try:
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

    # Verificar valores únicos en columna unit
    cursor.execute('SELECT DISTINCT unit FROM sensors LIMIT 20')
    units = cursor.fetchall()
    unit_list = [row['unit'] for row in units]
    print(f'Valores únicos en columna unit: {unit_list}')

    # Verificar relación entre unit y n (nombre del camión)
    cursor.execute('SELECT DISTINCT unit, n FROM sensors WHERE n IS NOT NULL AND unit IS NOT NULL LIMIT 20')
    relations = cursor.fetchall()
    print(f'\nRelación unit -> nombre de camión:')
    for row in relations:
        unit_val = row['unit']
        n_val = row['n']
        print(f'  unit: {unit_val}, n: {n_val}')

    # Verificar si nuestros unit_ids existen
    our_units = [401961901, 401961902, 401961903]
    for unit_id in our_units:
        cursor.execute('SELECT COUNT(*) as count FROM sensors WHERE unit = %s', (unit_id,))
        result = cursor.fetchone()
        count = result['count']
        print(f'unit {unit_id}: {count} registros')

    cursor.close()
    conn.close()

except Exception as e:
    print(f'Error: {e}')