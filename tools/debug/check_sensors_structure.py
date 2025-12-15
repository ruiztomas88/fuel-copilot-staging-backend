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

    # Verificar estructura de la tabla
    cursor.execute('DESCRIBE sensors')
    columns = cursor.fetchall()
    print('Columnas en tabla sensors:')
    for col in columns:
        field = col['Field']
        col_type = col['Type']
        print(f'  {field}: {col_type}')

    # Verificar algunos datos de ejemplo
    cursor.execute('SELECT n, p, m, value, from_latitude, from_longitude FROM sensors LIMIT 3')
    sample_data = cursor.fetchall()
    print(f'\nEjemplo de datos ({len(sample_data)} filas):')
    for row in sample_data:
        n_val = row.get('n')
        p_val = row.get('p')
        m_val = row.get('m')
        val = row.get('value')
        print(f'  n: {n_val}, p: {p_val}, m: {m_val}, value: {val}')

    # Verificar valores únicos en columna n (nombres de camiones)
    cursor.execute('SELECT DISTINCT n FROM sensors LIMIT 10')
    truck_names = cursor.fetchall()
    names = [row['n'] for row in truck_names]
    print(f'\nNombres de camiones únicos: {names}')

    # Verificar valores únicos en columna p (parámetros)
    cursor.execute('SELECT DISTINCT p FROM sensors LIMIT 20')
    params = cursor.fetchall()
    param_list = [row['p'] for row in params]
    print(f'\nParámetros únicos: {param_list}')

    cursor.close()
    conn.close()

except Exception as e:
    print(f'Error: {e}')