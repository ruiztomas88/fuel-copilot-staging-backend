import os
import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password=os.getenv("DB_PASSWORD"),
    database="fuel_copilot",
)
cursor = conn.cursor(dictionary=True)
cursor.execute("DESCRIBE mpg_baseline")
for row in cursor.fetchall():
    print(f"{row['Field']:30s} {row['Type']}")
cursor.close()
conn.close()
