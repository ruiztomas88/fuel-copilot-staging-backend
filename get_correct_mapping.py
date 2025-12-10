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

    # Obtener el mapeo correcto de units_map
    cursor.execute('SELECT beyondId, unit FROM units_map ORDER BY beyondId')
    mapping_data = cursor.fetchall()

    print('Mapeo correcto de units_map:')
    correct_mapping = {}
    for row in mapping_data:
        beyond_id = row['beyondId']
        unit_id = row['unit']
        correct_mapping[beyond_id] = unit_id
        print(f'  "{beyond_id}": {unit_id},')

    print(f'\nTotal camiones en units_map: {len(correct_mapping)}')

    cursor.close()
    conn.close()

except Exception as e:
    print(f'Error: {e}')