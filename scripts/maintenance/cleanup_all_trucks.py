import pymysql
import os

# Connection details for fuel_copilot
_password = os.getenv("MYSQL_PASSWORD")
if not _password:
    raise ValueError("MYSQL_PASSWORD environment variable required")

conn = pymysql.connect(
    host=os.getenv("MYSQL_HOST", "localhost"),
    user=os.getenv("MYSQL_USER", "fuel_admin"),
    password=_password,
    database=os.getenv("MYSQL_DATABASE", "fuel_copilot"),
    charset="utf8mb4",
)

# Read the SQL file
with open("cleanup_all_extra_trucks.sql", "r", encoding="utf-8") as f:
    sql = f.read()

# Execute the SQL
with conn.cursor() as cursor:
    # Split the SQL into statements
    statements = sql.split(";")
    for statement in statements:
        statement = statement.strip()
        if statement and not statement.startswith("--"):
            print(f"Executing: {statement[:50]}...")
            cursor.execute(statement)
            if statement.upper().startswith("SELECT"):
                results = cursor.fetchall()
                print(f"Results: {results}")

conn.commit()
conn.close()

print("Cleanup completed.")
