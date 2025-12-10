import pymysql
from dotenv import load_dotenv
import os

load_dotenv()

print('Verificando credenciales de conexión a Wialon DB:')
print(f'WIALON_DB_HOST: {os.getenv("WIALON_DB_HOST")}')
print(f'WIALON_DB_PORT: {os.getenv("WIALON_DB_PORT")}')
print(f'WIALON_DB_USER: {os.getenv("WIALON_DB_USER")}')
print(f'WIALON_DB_NAME: {os.getenv("WIALON_DB_NAME")}')

try:
    # Intentar conectar a Wialon DB
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

    # Verificar si podemos hacer una consulta simple
    cursor.execute('SELECT 1 as test')
    result = cursor.fetchone()
    print(f'Conexión a Wialon DB exitosa: {result}')

    # Verificar tabla sensors
    cursor.execute('SHOW TABLES LIKE "sensors"')
    result = cursor.fetchone()
    if result:
        print('Tabla sensors existe')

        # Verificar estructura de la tabla
        cursor.execute('DESCRIBE sensors')
        columns = cursor.fetchall()
        print(f'Tabla sensors tiene {len(columns)} columnas')

        # Verificar datos recientes
        cursor.execute('SELECT COUNT(*) as total FROM sensors WHERE m >= UNIX_TIMESTAMP() - 3600')
        result = cursor.fetchone()
        print(f'Datos en última hora: {result["total"]} registros')

    else:
        print('Tabla sensors NO existe')

    cursor.close()
    conn.close()

except Exception as e:
    print(f'Error conectando a Wialon DB: {e}')