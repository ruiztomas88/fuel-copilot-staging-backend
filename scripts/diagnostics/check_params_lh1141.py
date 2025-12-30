import mysql.connector
import time

conn = mysql.connector.connect(
    host='20.127.200.135',
    user='tomas',
    password=os.getenv("WIALON_MYSQL_PASSWORD"),
    database='wialon_collect'
)
cursor = conn.cursor(dictionary=True)

cutoff = int(time.time()) - 7200  # Last 2 hours

# Get ALL distinct parameter names
cursor.execute("""
    SELECT DISTINCT p
    FROM sensors 
    WHERE unit=401967076 
        AND m >= %s 
    ORDER BY p
""", [cutoff])
import os

all_params = cursor.fetchall()

print(f"\n=== ALL PARAMETERS for LH1141 in last 30 min ===")
print(f"Total: {len(all_params)} distinct parameters\n")
for p in all_params:
    print(f"  '{p['p']}'")

# Now specifically check for engine sensors
engine_params = ['rpm', 'cool_temp', 'oil_temp', 'oil_press', 'engine_load', 'def_level']
print(f"\n=== Checking for specific engine params ===")
for param in engine_params:
    cursor.execute("""
        SELECT COUNT(*) as cnt, MAX(m) as latest_epoch
        FROM sensors 
        WHERE unit=401967076 AND p=%s AND m >= %s
    """, [param, cutoff])
    result = cursor.fetchone()
    if result['cnt'] > 0:
        age = int(time.time()) - result['latest_epoch']
        print(f"  {param}: {result['cnt']} rows, latest {age}s ago")
    else:
        print(f"  {param}: NOT FOUND")

cursor.close()
conn.close()
