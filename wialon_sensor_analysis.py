import pymysql

# Connect to Wialon DB
conn = pymysql.connect(
    host='20.127.200.135',
    port=3306,
    user='tomas',
    password='Tomas2025',
    database='wialon_collect',
    cursorclass=pymysql.cursors.DictCursor
)

print("=" * 100)
print("WIALON SENSORS TABLE ANALYSIS")
print("=" * 100)
print()

# 1. Get all unique sensor parameters for last 24 hours
print("1. ALL AVAILABLE SENSOR PARAMETERS (last 24h):")
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT p, n, COUNT(*) as count, 
               AVG(value) as avg_value,
               MAX(measure_datetime) as last_seen
        FROM sensors 
        WHERE measure_datetime >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        GROUP BY p, n
        ORDER BY count DESC
        LIMIT 100
    """)
    all_sensors = cursor.fetchall()
    
    print(f"   Total unique parameters: {len(all_sensors)}")
    print()
    print(f"   {'Parameter (p)':25} {'Name (n)':40} {'Count':10} {'Avg':12} {'Last Seen'}")
    print("   " + "-" * 110)
    for sensor in all_sensors:
        avg_val = f"{sensor['avg_value']:.2f}" if sensor['avg_value'] is not None else "N/A"
        last = sensor['last_seen'].strftime("%H:%M:%S") if sensor['last_seen'] else "N/A"
        n_val = (sensor['n'] or 'NULL')[:40]
        print(f"   {sensor['p']:25} {n_val:40} {sensor['count']:10,} {avg_val:12} {last}")

print()
print()

# 2. Check critical sensors
print("2. CRITICAL SENSORS STATUS:")
critical = ['gear', 'odom', 'odometer', 'fuel_lvl', 'fuel_level', 'fuel_rate', 
            'rpm', 'engine_hours', 'speed', 'engine_load', 'coolant_temp']

with conn.cursor() as cursor:
    for param in critical:
        cursor.execute(f"""
            SELECT COUNT(*) as count, 
                   AVG(value) as avg_value,
                   MAX(measure_datetime) as last_seen
            FROM sensors 
            WHERE p = '{param}' 
            AND measure_datetime >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
        """)
        result = cursor.fetchone()
        
        if result and result['count'] > 0:
            avg = f"{result['avg_value']:.2f}" if result['avg_value'] else "N/A"
            last = result['last_seen'].strftime("%Y-%m-%d %H:%M:%S") if result['last_seen'] else "N/A"
            print(f"   ✓ {param:20} - {result['count']:8,} readings, avg={avg:10}, last={last}")
        else:
            print(f"   ✗ {param:20} - NOT FOUND in last 24h")

print()
print()

# 3. LC6799 specific data
print("3. LC6799 (unit=402033131) - Last 30 sensor readings:")
with conn.cursor() as cursor:
    cursor.execute("""
        SELECT p, n, value, text_value, measure_datetime 
        FROM sensors 
        WHERE unit = 402033131
        AND measure_datetime >= DATE_SUB(NOW(), INTERVAL 2 HOUR)
        ORDER BY measure_datetime DESC
        LIMIT 30
    """)
    samples = cursor.fetchall()
    
    if samples:
        print(f"   Found {len(samples)} recent readings:")
        print()
        print(f"   {'Time':12} {'Parameter':20} {'Value':15} {'Name'}")
        print("   " + "-" * 80)
        for s in samples:
            val = s['value'] if s['value'] is not None else s['text_value']
            time = s['measure_datetime'].strftime("%H:%M:%S") if s['measure_datetime'] else "N/A"
            n_val = (s['n'] or '')[:30]
            print(f"   {time:12} {s['p']:20} {str(val):15} {n_val}")
    else:
        print("   ✗ No recent data for LC6799")

print()
print()

# 4. units_map table
print("4. UNITS_MAP - Truck ID to Unit ID mapping:")
with conn.cursor() as cursor:
    cursor.execute("SELECT * FROM units_map LIMIT 10")
    units = cursor.fetchall()
    
    if units:
        print(f"   Sample of {len(units)} units:")
        for u in units:
            print(f"   {u}")
    else:
        print("   ✗ No data in units_map")

conn.close()

print()
print("=" * 100)
print("ANALYSIS COMPLETE")
print("=" * 100)
