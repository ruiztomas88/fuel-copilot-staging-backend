import os
"""Check actual structure of truck_sensors_cache table"""
import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="fuel_admin",
    password=os.getenv("DB_PASSWORD"),
    database="fuel_copilot"
)
cursor = conn.cursor()

cursor.execute("DESCRIBE truck_sensors_cache")
columns = cursor.fetchall()

print("="*70)
print("truck_sensors_cache Table Structure:")
print("="*70)
for col in columns:
    print(f"{col[0]:30s} {col[1]:20s} {col[2]:5s} {col[3]:5s}")

cursor.close()
conn.close()
