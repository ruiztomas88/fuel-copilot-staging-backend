"""
Final diagnostic - Compare Wialon sensors vs our database for DO9693
"""
import os
import pymysql
import sys

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Connect to Wialon
wialon_conn = pymysql.connect(
    host="20.127.200.135",
    port=3306,
    user="tomas",
    password=os.getenv("WIALON_MYSQL_PASSWORD"),
    database="wialon_collect",
    cursorclass=pymysql.cursors.DictCursor
)

# Connect to our local DB
local_conn = pymysql.connect(
    host="localhost",
    port=3306,
    user="fuel_admin",
    password=os.getenv("DB_PASSWORD"),
    database="fuel_copilot",
    cursorclass=pymysql.cursors.DictCursor
)

print("="*100)
print("WIALON vs FUEL_COPILOT SENSOR COMPARISON FOR DO9693")
print("="*100)

with wialon_conn.cursor() as w_cursor, local_conn.cursor() as l_cursor:
    # Find DO9693 in Wialon
    w_cursor.execute("SELECT * FROM units_map WHERE beyondId = 'DO9693'")
    wialon_unit = w_cursor.fetchone()
    
    if not wialon_unit:
        print("\nDO9693 not found in Wialon units_map!")
        print("Checking all available trucks...")
        w_cursor.execute("SELECT beyondId FROM units_map ORDER BY beyondId")
        all_trucks = [r['beyondId'] for r in w_cursor.fetchall()]
        print(f"Available trucks ({len(all_trucks)}): {', '.join(all_trucks[:20])}...")
        sys.exit(1)
    
    unit_id = wialon_unit['unit']
    print(f"\nDO9693 found in Wialon:")
    print(f"  Unit ID: {unit_id}")
    print(f"  Fuel Capacity: {wialon_unit['fuel_capacity']} gal")
    print(f"  Carrier: {wialon_unit['carrier_id']}")
    
    # Get latest sensors from Wialon
    print("\n" + "="*100)
    print("WIALON SENSORS (last 30 records):")
    print("="*100)
    
    w_cursor.execute(f"""
        SELECT p as param, n as name, value, type, 
               m as epoch, FROM_UNIXTIME(m) as timestamp
        FROM sensors
        WHERE unit = {unit_id}
        ORDER BY m DESC
        LIMIT 30
    """)
    
    wialon_sensors = w_cursor.fetchall()
    
    if not wialon_sensors:
        print(f"\nNo sensor data found for unit {unit_id} in Wialon!")
    else:
        latest_ts = wialon_sensors[0]['timestamp']
        print(f"\nLatest sensor data from: {latest_ts}")
        print(f"Total sensors: {len(wialon_sensors)}\n")
        
        sensor_dict = {}
        for s in wialon_sensors:
            param = s['param']
            if param not in sensor_dict:  # Keep first (most recent)
                sensor_dict[param] = s
                ts_str = str(s['timestamp']) if s['timestamp'] else 'N/A'
                print(f"{param:25s} | {s['name']:35s} | {s['value']:>10} | {ts_str}")
    
    # Get latest data from our database
    print("\n" + "="*100)
    print("OUR DATABASE (fuel_metrics - latest record):")
    print("="*100)
    
    l_cursor.execute("""
        SELECT * FROM fuel_metrics 
        WHERE truck_id = 'DO9693'
        ORDER BY timestamp_utc DESC 
        LIMIT 1
    """)
    
    our_data = l_cursor.fetchone()
    
    if not our_data:
        print("\nDO9693 not found in our fuel_metrics table!")
    else:
        print(f"\nLatest record from: {our_data['timestamp_utc']}")
        print(f"Data age: {our_data.get('data_age_min', 'N/A')} minutes")
        print("\nKey fields:")
        key_fields = [
            'truck_status', 'speed_mph', 'rpm', 'odometer_mi', 'engine_hours',
            'sensor_pct', 'sensor_gallons', 'estimated_pct', 'estimated_gallons',
            'fuel_level_raw', 'fuel_level_filtered',
            'consumption_gph', 'mpg_current', 'idle_mode', 'idle_gph',
            'coolant_temp_f', 'oil_pressure_psi', 'battery_voltage'
        ]
        
        for field in key_fields:
            value = our_data.get(field, 'MISSING')
            print(f"  {field:25s}: {value}")
    
    # COMPARISON
    print("\n" + "="*100)
    print("COMPARISON & DIAGNOSIS:")
    print("="*100)
    
    if wialon_sensors and our_data:
        issues = []
        
        # Check if we have fuel sensor in Wialon
        fuel_sensors = [s for s in wialon_sensors if 'fuel' in s['param'].lower() or 'fuel' in s['name'].lower()]
        if fuel_sensors:
            print(f"\n Wialon HAS fuel sensors: {[f['param'] for f in fuel_sensors]}")
            if our_data.get('sensor_pct') is None:
                issues.append("We are NOT saving fuel sensor data from Wialon")
        else:
            print("\n Wialon has NO fuel sensors for this truck!")
            issues.append("DO9693 may not have fuel sensor configured in Wialon")
        
        # Check speed
        speed_sensors = [s for s in wialon_sensors if 'speed' in s['param'].lower()]
        if speed_sensors:
            print(f" Wialon HAS speed sensors: {[s['param'] for s in speed_sensors]}")
            if our_data.get('speed_mph') is None:
                issues.append("We are NOT saving speed data from Wialon")
        
        # Check RPM
        rpm_sensors = [s for s in wialon_sensors if 'rpm' in s['param'].lower()]
        if rpm_sensors:
            print(f" Wialon HAS RPM sensors: {[s['param'] for s in rpm_sensors]}")
            if our_data.get('rpm') is None:
                issues.append("We are NOT saving RPM data from Wialon")
        
        if issues:
            print("\n" + "!"*100)
            print("ISSUES FOUND:")
            for i, issue in enumerate(issues, 1):
                print(f"{i}. {issue}")
            print("!"*100)
        else:
            print("\n All sensors appear to be mapped correctly!")

wialon_conn.close()
local_conn.close()

print("\n" + "="*100)
