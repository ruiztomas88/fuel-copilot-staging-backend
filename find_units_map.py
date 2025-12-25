"""
Buscar tabla units_map en las bases de datos disponibles
"""
import os
import pymysql

# Try fuel_copilot first
print("Buscando units_map...\n")

dbs_to_check = [
    {
        'name': 'fuel_copilot',
        'host': 'localhost',
        'user': 'fuel_admin',
        "password": os.getenv("MYSQL_PASSWORD", ""),
        'database': 'fuel_copilot'
    },
    {
        'name': 'wialon_collect',
        'host': '20.127.200.135',
        'user': 'tomas',
        'password': 'Tomas2025',
        'database': 'wialon_collect'
    }
]

for db_config in dbs_to_check:
    try:
        conn = pymysql.connect(
            host=db_config['host'],
            user=db_config['user'],
            password=db_config['password'],
            database=db_config['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor,
        )
        
        cursor = conn.cursor()
        
        # Check if units_map exists
        cursor.execute("SHOW TABLES LIKE 'units_map'")
        result = cursor.fetchone()
        
        if result:
            print(f"✅ units_map FOUND in {db_config['name']} ({db_config['host']})")
            
            # Show structure
            cursor.execute("DESCRIBE units_map")
            print("\n   Columns:")
            for col in cursor.fetchall():
                print(f"     - {col['Field']} ({col['Type']})")
            
            # Show sample data
            cursor.execute("SELECT * FROM units_map LIMIT 3")
            print("\n   Sample data:")
            for row in cursor.fetchall():
                print(f"     {row}")
            
            # Check for our trucks
            cursor.execute("SELECT * FROM units_map WHERE beyondId IN ('FF7702', 'JB6858', 'RT9127')")
            our_trucks = cursor.fetchall()
            if our_trucks:
                print(f"\n   ✅ FF7702, JB6858, RT9127:")
                for row in our_trucks:
                    print(f"     {row}")
            else:
                print(f"\n   ❌ FF7702, JB6858, RT9127 NOT FOUND")
            
            print()
        else:
            print(f"❌ units_map NOT in {db_config['name']}")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Error checking {db_config['name']}: {e}\n")
