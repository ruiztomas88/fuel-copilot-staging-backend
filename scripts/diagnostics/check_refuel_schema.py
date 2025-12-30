import pymysql

from config import get_local_db_config

conn = pymysql.connect(**get_local_db_config())
cursor = conn.cursor()

print("=" * 80)
print("REFUEL_EVENTS TABLE SCHEMA")
print("=" * 80)
cursor.execute("DESCRIBE refuel_events")
for row in cursor.fetchall():
    print(f"  {row[0]:<20} {row[1]:<20} {row[2]:<10}")

print("\n" + "=" * 80)
print("RECENT REFUELS (Last 7 days)")
print("=" * 80)
cursor.execute(
    """
    SELECT truck_id, timestamp_utc, fuel_before, fuel_after, gallons_added
    FROM refuel_events
    WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 7 DAY)
    ORDER BY timestamp_utc DESC
    LIMIT 10
"""
)
for row in cursor.fetchall():
    print(
        f"  {row[0]:<10} {row[1]} {row[2]:>6.1f}% → {row[3]:>6.1f}% (+{row[4]:>6.1f} gal)"
    )

cursor.close()
conn.close()
