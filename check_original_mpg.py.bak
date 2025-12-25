"""
Check the ORIGINAL MPG values from the first day of data collection
to see what values the logic was calculating BEFORE the cleanup
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

def check_original_mpg():
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    # Find first date with MPG data
    cursor.execute("""
        SELECT MIN(timestamp_utc) as first_date 
        FROM fuel_metrics 
        WHERE mpg_current IS NOT NULL
    """)
    first_date = cursor.fetchone()[0]
    print(f"📅 Primer registro MPG: {first_date}")
    
    # Get first day stats (before any cleanup or capping)
    first_day_end = first_date + timedelta(days=1)
    
    cursor.execute("""
        SELECT 
            truck_id,
            AVG(mpg_current) as avg_mpg,
            MIN(mpg_current) as min_mpg,
            MAX(mpg_current) as max_mpg,
            COUNT(*) as records
        FROM fuel_metrics
        WHERE timestamp_utc >= %s AND timestamp_utc < %s
            AND mpg_current IS NOT NULL
        GROUP BY truck_id
        ORDER BY avg_mpg DESC
        LIMIT 20
    """, (first_date, first_day_end))
    
    first_day_data = cursor.fetchall()
    
    print(f"\n📊 MPG del primer día ({first_date.date()}):")
    print(f"{'Truck':<12} {'Avg MPG':>8} {'Min':>6} {'Max':>6} {'Records':>8}")
    print("-" * 50)
    
    for truck_id, avg_mpg, min_mpg, max_mpg, records in first_day_data:
        print(f"{truck_id:<12} {avg_mpg:>8.2f} {min_mpg:>6.2f} {max_mpg:>6.2f} {records:>8}")
    
    # Overall stats for first day
    cursor.execute("""
        SELECT 
            AVG(mpg_current) as avg_mpg,
            MIN(mpg_current) as min_mpg,
            MAX(mpg_current) as max_mpg,
            COUNT(DISTINCT truck_id) as trucks,
            COUNT(*) as total_records
        FROM fuel_metrics
        WHERE timestamp_utc >= %s AND timestamp_utc < %s
            AND mpg_current IS NOT NULL
    """, (first_date, first_day_end))
    
    avg_mpg, min_mpg, max_mpg, trucks, total_records = cursor.fetchone()
    
    print(f"\n{'='*50}")
    print(f"RESUMEN PRIMER DÍA:")
    print(f"  Promedio flota: {avg_mpg:.2f} MPG")
    print(f"  Rango: {min_mpg:.2f} - {max_mpg:.2f} MPG")
    print(f"  Trucks: {trucks}")
    print(f"  Records: {total_records}")
    print(f"{'='*50}")
    
    # Check if there were values > 8.5 originally
    cursor.execute("""
        SELECT COUNT(*) 
        FROM fuel_metrics
        WHERE timestamp_utc >= %s AND timestamp_utc < %s
            AND mpg_current > 8.5
    """, (first_date, first_day_end))
    
    high_mpg_count = cursor.fetchone()[0]
    
    if high_mpg_count > 0:
        print(f"\n⚠️  NOTA: El primer día tenía {high_mpg_count} registros con MPG > 8.5")
        print(f"   Esto significa que la lógica SÍ calculaba valores altos (no solo capeo)")
    else:
        print(f"\n✅ El primer día NO tenía valores > 8.5")
        print(f"   La lógica original calculaba valores realistas")
    
    # Check recent data BEFORE cleanup (we need to look at created_at timestamps)
    print(f"\n\n📅 Ahora veamos datos RECIENTES (últimas 24h):")
    print(f"   Para ver si la lógica actual calcula valores altos...")
    
    cursor.execute("""
        SELECT 
            truck_id,
            mpg_current,
            timestamp_utc,
            created_at
        FROM fuel_metrics
        WHERE mpg_current = 8.5
        ORDER BY created_at DESC
        LIMIT 10
    """)
    
    recent_capped = cursor.fetchall()
    
    if recent_capped:
        print(f"\n🔍 Registros con MPG exactamente = 8.5 (posiblemente capeados):")
        print(f"{'Truck':<12} {'MPG':>6} {'Data Time':<20} {'Created':<20}")
        print("-" * 70)
        for truck_id, mpg, ts, created in recent_capped:
            print(f"{truck_id:<12} {mpg:>6.2f} {ts!s:<20} {created!s:<20}")
    
    conn.close()

if __name__ == "__main__":
    check_original_mpg()
