import pymysql

conn = pymysql.connect(
    host="localhost",
    user="fuel_admin",
    password="FuelCopilot2025!",
    database="fuel_copilot",
)

cursor = conn.cursor()

# Check actual table structure
cursor.execute("DESCRIBE mpg_baseline")
print("mpg_baseline columns:")
for row in cursor.fetchall():
    print(f"  {row[0]} - {row[1]}")

cursor.close()
conn.close()
