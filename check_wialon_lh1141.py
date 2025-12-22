import time

import mysql.connector

from config import get_wialon_db_config

# Convert pymysql config to mysql.connector format
wialon_config = get_wialon_db_config()
conn = mysql.connector.connect(
    host=wialon_config["host"],
    user=wialon_config["user"],
    password=wialon_config["password"],
    database=wialon_config["database"],
)
cursor = conn.cursor(dictionary=True)

cutoff = int(time.time()) - 1800  # Last 30 minutes

cursor.execute(
    """
    SELECT DISTINCT p
    FROM sensors 
    WHERE unit=401967076 
        AND m >= %s 
    ORDER BY p
""",
    [cutoff],
)

params = cursor.fetchall()

print(f"\nAll parameters for LH1141 (unit 401967076) in last 30 min:")
print(f"Total distinct parameters: {len(params)}")
print("\nParameter names:")
for p in params:
    print(f"  - {p['p']}")

# Now get actual values for engine-related params
cursor.execute(
    """
    SELECT p, value, m 
    FROM sensors 
    WHERE unit=401967076 
        AND m >= %s 
        AND p LIKE '%temp%' OR p LIKE '%rpm%' OR p LIKE '%press%' OR p LIKE '%load%' OR p LIKE '%def%' OR p LIKE '%cool%' OR p LIKE '%oil%'
    ORDER BY m DESC 
    LIMIT 30
""",
    [cutoff],
)

engine_data = cursor.fetchall()
print(f"\nEngine-related sensor data:")
for r in engine_data[:20]:
    print(f"  {r['p']}: {r['value']} (epoch {r['m']})")

cursor.close()
conn.close()
