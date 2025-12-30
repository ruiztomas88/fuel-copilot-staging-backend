import pymysql
import os
from dotenv import load_dotenv

load_dotenv()

WIALON_CONFIG = {
    "host": os.getenv("WIALON_DB_HOST", "20.127.200.135"),
    "port": int(os.getenv("WIALON_DB_PORT", "3306")),
    "database": os.getenv("WIALON_DB_NAME", "wialon_collect"),
    "user": os.getenv("WIALON_DB_USER", "tomas"),
    "password": os.getenv("WIALON_DB_PASS", "Tomas2025"),
}

conn = pymysql.connect(**WIALON_CONFIG)
cur = conn.cursor()

# Ver estructura de la tabla
cur.execute("SHOW COLUMNS FROM sensors")
print("Estructura de tabla sensors:\n")
for row in cur.fetchall():
    print(f"   {row[0]} ({row[1]})")

print("\nSensores disponibles para GS5030 (unit=21):\n")
cutoff = "UNIX_TIMESTAMP() - 3600"
cur.execute(f"""
    SELECT DISTINCT p as param_name
    FROM sensors 
    WHERE unit = 21 
    AND p IS NOT NULL
    AND p != ''
    AND m >= UNIX_TIMESTAMP() - 3600
    ORDER BY p
""")

rows = cur.fetchall()
if rows:
    for row in rows:
        print(f"   - {row[0]}")
else:
    print("   NO HAY DATOS RECIENTES (ultima hora)")
    
print("\nVerificando si hay datos mas antiguos...")
cur.execute("""
    SELECT COUNT(*), MAX(m), MIN(m)
    FROM sensors 
    WHERE unit = 21 
""")
result = cur.fetchone()
print(f"   Total registros: {result[0]}")
if result[1]:
    from datetime import datetime
    print(f"   Ultimo timestamp: {datetime.fromtimestamp(result[1])}")
    print(f"   Primer timestamp: {datetime.fromtimestamp(result[2])}")

conn.close()
