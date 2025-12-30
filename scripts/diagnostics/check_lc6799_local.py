import pymysql

conn = pymysql.connect(
    host="localhost",
    user="root",
    password="",
    database="fuel_copilot_local",
    cursorclass=pymysql.cursors.DictCursor,
)

with conn.cursor() as cursor:
    # Get latest record for LC6799
    cursor.execute(
        """
        SELECT * FROM fuel_metrics 
        WHERE truck_id = 'LC6799' 
        ORDER BY timestamp_utc DESC 
        LIMIT 1
    """
    )
    result = cursor.fetchone()

    if result:
        print("Latest LC6799 data:")
        print(f'  timestamp: {result["timestamp_utc"]}')
        print(f'  speed: {result.get("speed_mph")}')
        print(f'  odometer: {result.get("odometer_mi")}')
        print(f'  rpm: {result.get("rpm")}')
        print(f'  fuel_pct: {result.get("sensor_pct")}')
        print(f'  truck_status: {result.get("truck_status")}')
        print()

        # Check for gear column
        if "gear" in result:
            print(f'  gear: {result.get("gear")} ✓ Column exists')
        else:
            print("  gear: Column NOT in fuel_metrics table ✗")

        print()
        print("Sensor values:")
        for key in [
            "speed_mph",
            "odometer_mi",
            "rpm",
            "engine_hours",
            "coolant_temp_f",
            "fuel_lvl",
        ]:
            value = result.get(key)
            status = "✓" if value is not None else "✗ NULL"
            print(f"  {key}: {value} {status}")
    else:
        print("No data for LC6799")

    # Check if truck_sensors_cache has more data
    print()
    print("=" * 60)
    print("Checking truck_sensors_cache table:")
    cursor.execute(
        """
        SELECT * FROM truck_sensors_cache 
        WHERE truck_id = 'LC6799' 
        LIMIT 1
    """
    )
    cache_result = cursor.fetchone()

    if cache_result:
        print("LC6799 sensors cache:")
        for key, value in cache_result.items():
            if value is not None and key not in [
                "id",
                "truck_id",
                "unit_id",
                "updated_at",
            ]:
                print(f"  {key}: {value}")
    else:
        print("No cache data for LC6799")

conn.close()
