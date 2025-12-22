"""
Check MPG window completion for moving trucks
"""
import pymysql
from datetime import datetime, timedelta

DB_CONFIG = {
    'host': 'localhost',
    'user': 'fuel_admin',
    'password': 'FuelCopilot2025!',
    'database': 'fuel_copilot',
    'charset': 'utf8mb4'
}

def check_mpg_updates():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Get trucks that are MOVING (speed > 20 mph)
    cursor.execute("""
        SELECT 
            truck_id,
            speed_mph,
            mpg_current,
            odometer_mi,
            timestamp_utc,
            TIMESTAMPDIFF(MINUTE, timestamp_utc, NOW()) as minutes_ago
        FROM fuel_metrics
        WHERE truck_status = 'MOVING'
            AND speed_mph > 20
            AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
        ORDER BY timestamp_utc DESC
        LIMIT 20
    """)
    
    moving_trucks = cursor.fetchall()
    
    print(f"\n📊 Trucks MOVING (últimos 30 min, speed > 20 mph):")
    print(f"{'Truck':<12} {'Speed':>6} {'MPG':>6} {'Odometer':>10} {'Min Ago':>8}")
    print("-" * 60)
    
    for truck_id, speed, mpg, odo, ts, min_ago in moving_trucks:
        odo_str = f"{odo:.1f}" if odo else "N/A"
        mpg_str = f"{mpg:.2f}" if mpg else "N/A"
        print(f"{truck_id:<12} {speed:>6.1f} {mpg_str:>6} {odo_str:>10} {min_ago:>8}")
    
    # Check how many unique MPG values there are (if all 7.8, it's capped)
    cursor.execute("""
        SELECT 
            COUNT(DISTINCT mpg_current) as unique_mpg_values,
            COUNT(*) as total_moving_records
        FROM fuel_metrics
        WHERE truck_status = 'MOVING'
            AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
            AND mpg_current IS NOT NULL
    """)
    
    unique_vals, total_recs = cursor.fetchone()
    
    print(f"\n📈 Diversidad de MPG (últimos 30 min):")
    print(f"  Valores únicos: {unique_vals}")
    print(f"  Total records: {total_recs}")
    
    if unique_vals <= 3:
        print(f"  ⚠️  MUY POCA DIVERSIDAD - posible capeo artificial")
    
    # Check distribution of MPG values
    cursor.execute("""
        SELECT 
            mpg_current,
            COUNT(*) as count
        FROM fuel_metrics
        WHERE truck_status = 'MOVING'
            AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
            AND mpg_current IS NOT NULL
        GROUP BY mpg_current
        ORDER BY count DESC
        LIMIT 10
    """)
    
    mpg_dist = cursor.fetchall()
    
    print(f"\n📊 Distribución de MPG (últimos 30 min):")
    print(f"{'MPG':>6} {'Count':>8}")
    print("-" * 20)
    for mpg, count in mpg_dist:
        print(f"{mpg:>6.2f} {count:>8}")
    
    conn.close()

if __name__ == "__main__":
    check_mpg_updates()
