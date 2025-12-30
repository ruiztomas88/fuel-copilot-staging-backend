import os
import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password=os.getenv("DB_PASSWORD"),
    database="fuel_copilot",
)
cursor = conn.cursor(dictionary=True)
cursor.execute(
    "SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest FROM truck_sensors_cache"
)
row = cursor.fetchone()
print(f'Oldest: {row["oldest"]}')
print(f'Newest: {row["newest"]}')
age = (row["newest"] - row["oldest"]).total_seconds() / 86400
print(f"Data span: {age:.1f} days")
