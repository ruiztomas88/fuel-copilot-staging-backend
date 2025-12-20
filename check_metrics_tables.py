import pymysql

conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password='FuelCopilot2025!',
    database='fuel_copilot'
)
cursor = conn.cursor()
cursor.execute('SHOW TABLES')
all_tables = [row[0] for row in cursor.fetchall()]

print(f"Total tables: {len(all_tables)}\n")

# Check for specific tables
targets = ['daily_truck_metrics', 'truck_metrics', 'fleet_metrics']
for table in targets:
    exists = table in all_tables
    print(f"{table}: {'✅ EXISTS' if exists else '❌ MISSING'}")

# Show tables with 'metric' or 'daily'
print("\n📋 Tables with 'metric' or 'daily' in name:")
for table in sorted(all_tables):
    if 'metric' in table.lower() or 'daily' in table.lower():
        cursor.execute(f'SELECT COUNT(*) FROM {table}')
        count = cursor.fetchone()[0]
        print(f"  - {table}: {count} rows")

cursor.close()
conn.close()
