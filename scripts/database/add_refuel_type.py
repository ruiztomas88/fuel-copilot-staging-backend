import os
import pymysql

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password=os.getenv("DB_PASSWORD"),
    database='fuel_copilot'
)
cursor = conn.cursor()
cursor.execute('ALTER TABLE refuel_events ADD COLUMN refuel_type VARCHAR(50) DEFAULT "NORMAL"')
conn.commit()
print('✅ Added refuel_type column')
cursor.close()
conn.close()
