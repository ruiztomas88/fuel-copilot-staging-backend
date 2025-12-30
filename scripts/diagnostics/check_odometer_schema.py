import pymysql

conn = pymysql.connect(
    host="localhost", user="root", password="", database="fuel_copilot_local"
)

with conn.cursor() as cursor:
    # Check fuel_metrics table schema
    cursor.execute("DESCRIBE fuel_metrics")
    columns = cursor.fetchall()

    print("fuel_metrics columns:")
    gear_exists = False
    for col in columns:
        if "gear" in str(col[0]).lower() or "transmission" in str(col[0]).lower():
            print(f"  ✓ {col[0]} ({col[1]})")
            gear_exists = True

    if not gear_exists:
        print("  ✗ No gear/transmission column found")

    print()
    print("Searching for odometer columns:")
    for col in columns:
        if "odom" in str(col[0]).lower() or "mileage" in str(col[0]).lower():
            print(f"  ✓ {col[0]} ({col[1]})")

    # Check if we're storing odometer data
    print()
    print("Checking trucks with odometer data:")
    cursor.execute(
        """
        SELECT truck_id, odometer_mi 
        FROM fuel_metrics 
        WHERE odometer_mi IS NOT NULL 
        ORDER BY timestamp_utc DESC 
        LIMIT 10
    """
    )
    results = cursor.fetchall()

    if results:
        print(f"  Found {len(results)} recent records with odometer:")
        for row in results:
            print(f"    {row[0]}: {row[1]:.1f} mi")
    else:
        print("  ✗ NO trucks have odometer data")

conn.close()
