import pymysql
import os

# Connection details for fuel_copilot
conn = pymysql.connect(
    host=os.getenv('MYSQL_HOST', 'localhost'),
    user=os.getenv('MYSQL_USER', 'fuel_admin'),
    password=os.getenv('MYSQL_PASSWORD', 'FuelCopilot2025!'),
    database=os.getenv('MYSQL_DATABASE', 'fuel_copilot'),
    charset='utf8mb4'
)

with conn.cursor() as cursor:
    cursor.execute("SELECT COUNT(*) as total FROM units_map")
    result = cursor.fetchone()
    print(f"Total trucks in units_map: {result[0]}")

    cursor.execute("SELECT beyondId FROM units_map ORDER BY beyondId")
    trucks = cursor.fetchall()
    print("Trucks in units_map:")
    for truck in trucks:
        print(truck[0])

conn.close()