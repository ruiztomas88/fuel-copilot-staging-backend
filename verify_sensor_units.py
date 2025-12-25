"""
Verify if total_fuel_used sensor is in liters or gallons
Check typical values to determine if conversion is needed
"""

import os

import pymysql
from dotenv import load_dotenv

load_dotenv()

# Connect to Wialon DB
conn = pymysql.connect(
    host=os.getenv("WIALON_DB_HOST"),
    user=os.getenv("WIALON_DB_USER"),
    password=os.getenv("WIALON_DB_PASS"),
    database=os.getenv("WIALON_DB_NAME"),
    port=int(os.getenv("WIALON_DB_PORT", 3306)),
)

try:
    cursor = conn.cursor()

    # First, get unit IDs for our trucks
    truck_query = """
    SELECT unit, beyondId FROM units_map 
    WHERE beyondId IN ('JC1282', 'RH1522', 'KW1620', 'FLD1410')
    """
    cursor.execute(truck_query)
    truck_map = {row[1]: row[0] for row in cursor.fetchall()}

    if not truck_map:
        print("No trucks found in units_map")
        exit(1)

    unit_ids = list(truck_map.values())
    print(f"Found trucks: {truck_map}")

    # Get recent total_fuel_used values
    placeholders = ",".join(["%s"] * len(unit_ids))
    query = f"""
    SELECT u.beyondId, s.p, s.value, FROM_UNIXTIME(s.m) as timestamp
    FROM sensors s
    JOIN units_map u ON s.unit = u.unit
    WHERE s.unit IN ({placeholders})
      AND s.p IN ('total_fuel_used', 'fuel_rate')
      AND s.m > UNIX_TIMESTAMP(NOW() - INTERVAL 2 HOUR)
    ORDER BY u.beyondId, s.p, s.m DESC
    LIMIT 30
    """

    cursor.execute(query, unit_ids)
    rows = cursor.fetchall()

    print("\n" + "=" * 80)
    print("SENSOR UNIT VERIFICATION")
    print("=" * 80)
    print("\nRecent sensor values (last 2 hours):\n")
    print(f"{'Truck':<10} {'Sensor':<20} {'Value':<15} {'Timestamp'}")
    print("-" * 80)

    for row in rows:
        truck, param, value, ts = row
        print(f"{truck:<10} {param:<20} {value:<15.2f} {ts}")

    # Analysis
    print("\n" + "=" * 80)
    print("ANALYSIS:")
    print("=" * 80)
    print("\nExpected values:")
    print(
        "  - total_fuel_used in GALLONS: typically 50,000 - 200,000 (lifetime counter)"
    )
    print("  - total_fuel_used in LITERS: typically 180,000 - 750,000")
    print("  - fuel_rate in L/h: 0.5 - 15 L/h (confirmed metric)")
    print("  - fuel_rate in gal/h: 0.13 - 4 gal/h")
    print(
        "\n✅ If total_fuel_used > 300,000 → it's in LITERS, needs ÷3.78541 conversion"
    )
    print("✅ If total_fuel_used < 300,000 → it's in GALLONS, no conversion needed")
    print("=" * 80)

except Exception as e:
    print(f"Error: {e}")
finally:
    conn.close()
