"""
Reset MPG values to force recalculation with Wednesday's working config
"""
import pymysql

DB_CONFIG = {
    'host': 'localhost',
    'user': 'fuel_admin',
    'password': 'FuelCopilot2025!',
    'database': 'fuel_copilot',
    'charset': 'utf8mb4'
}

def reset_mpg():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Set all MPG values > 9.0 to NULL to force recalculation
    print("🔧 Resetting inflated MPG values (>9.0) to NULL...")
    cursor.execute("""
        UPDATE fuel_metrics 
        SET mpg_current = NULL 
        WHERE mpg_current > 9.0
    """)
    
    count = cursor.rowcount
    conn.commit()
    
    print(f"✅ Reset {count} inflated MPG records")
    print(f"   System will recalculate with Wednesday's config:")
    print(f"   - min_miles: 5.0")
    print(f"   - min_fuel_gal: 0.75")
    print(f"   - max_mpg: 9.0")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    reset_mpg()
