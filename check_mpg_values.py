import mysql.connector

conn = mysql.connector.connect(
    host='localhost',
    user='fuel_admin',
    password=os.getenv("DB_PASSWORD"),
    database='fuel_copilot'
)
cursor = conn.cursor(dictionary=True)

# Check MPG values in last 24h
cursor.execute("""
    SELECT truck_id, mpg_current, estimated_gallons, odometer_mi, timestamp_utc 
    FROM fuel_metrics 
    WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR) 
        AND mpg_current IS NOT NULL
    ORDER BY mpg_current DESC 
    LIMIT 25
""")
import os

rows = cursor.fetchall()

print('\n=== TOP 25 MPG VALUES (Last 24h) ===\n')
for r in rows:
    odom = r['odometer_mi'] if r['odometer_mi'] else 0
    print(f"{r['truck_id']:8} {r['mpg_current']:6.2f} MPG  (gallons={r['estimated_gallons']:5.1f}, odom={odom:7.1f})")

# Check average MPG
cursor.execute("""
    SELECT 
        AVG(mpg_current) as avg_mpg,
        MIN(mpg_current) as min_mpg,
        MAX(mpg_current) as max_mpg,
        COUNT(*) as total_records
    FROM fuel_metrics 
    WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        AND mpg_current IS NOT NULL
        AND mpg_current > 0
""")

stats = cursor.fetchone()
print(f"\n=== MPG STATISTICS (Last 7 days) ===")
print(f"Average: {stats['avg_mpg']:.2f} MPG")
print(f"Min: {stats['min_mpg']:.2f} MPG")
print(f"Max: {stats['max_mpg']:.2f} MPG")
print(f"Total records: {stats['total_records']}")

cursor.close()
conn.close()
