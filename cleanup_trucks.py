import pymysql
import os

# Connection details for wialon_collect
conn = pymysql.connect(
    host=os.getenv('WIALON_DB_HOST', 'localhost'),
    user=os.getenv('WIALON_DB_USER', 'fuel_admin'),
    password=os.getenv('WIALON_DB_PASS', 'FuelCopilot2025!'),
    database='wialon_collect',
    charset='utf8mb4'
)

# Read the SQL file
with open('cleanup_extra_trucks.sql', 'r') as f:
    sql = f.read()

# Execute the SQL
with conn.cursor() as cursor:
    # Split the SQL into statements (since there are multiple SELECT and DELETE)
    statements = sql.split(';')
    for statement in statements:
        statement = statement.strip()
        if statement:
            print(f"Executing: {statement[:50]}...")
            cursor.execute(statement)
            if statement.upper().startswith('SELECT'):
                results = cursor.fetchall()
                print(f"Results: {results}")

conn.commit()
conn.close()

print("Cleanup completed.")