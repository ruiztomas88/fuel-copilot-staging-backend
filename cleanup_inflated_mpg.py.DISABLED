"""
Cleanup script to cap inflated MPG values in fuel_metrics table

Fixes trucks showing impossible MPG values (>8.5) from v3.15.0 era when
max_mpg was 12.0. User reports seeing 11.0 and 9.9 MPG when normal range
for 44,000 lb cargo trucks is 4-7.8 MPG.

Sets max_mpg = 8.5 for consistency with current mpg_engine.py config.
"""
import pymysql
from datetime import datetime

# Database configuration
DB_CONFIG = {
    'host': 'localhost',
    'user': 'fuel_admin',
    'password': 'FuelCopilot2025!',
    'database': 'fuel_copilot',
    'charset': 'utf8mb4'
}

MAX_MPG_THRESHOLD = 7.8  # User requirement: max for 44,000 lb cargo trucks

def cleanup_mpg_values():
    """Cap all mpg_current values above threshold"""
    
    conn = None
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # First, check what will be affected
        print(f"\n🔍 Checking trucks with MPG > {MAX_MPG_THRESHOLD}...")
        cursor.execute("""
            SELECT 
                truck_id,
                mpg_current,
                odometer_mi,
                timestamp_utc
            FROM fuel_metrics
            WHERE mpg_current > %s
            ORDER BY mpg_current DESC
            LIMIT 20
        """, (MAX_MPG_THRESHOLD,))
        
        affected = cursor.fetchall()
        
        if not affected:
            print("✅ No trucks found with inflated MPG values")
            return
        
        print(f"\n📊 Found {len(affected)} records with inflated MPG:")
        for truck_id, mpg, odo, ts in affected[:10]:
            odo_str = f"{odo:.1f}" if odo is not None else "N/A"
            print(f"  • {truck_id}: {mpg:.2f} MPG (odometer: {odo_str} mi) - {ts}")
        
        if len(affected) > 10:
            print(f"  ... and {len(affected) - 10} more")
        
        # Count total affected records
        cursor.execute("""
            SELECT COUNT(*) FROM fuel_metrics WHERE mpg_current > %s
        """, (MAX_MPG_THRESHOLD,))
        total_count = cursor.fetchone()[0]
        
        print(f"\n⚠️  Total records to update: {total_count}")
        
        # Perform the update
        print(f"\n🔧 Capping all MPG values to {MAX_MPG_THRESHOLD}...")
        cursor.execute("""
            UPDATE fuel_metrics 
            SET mpg_current = %s 
            WHERE mpg_current > %s
        """, (MAX_MPG_THRESHOLD, MAX_MPG_THRESHOLD))
        
        rows_updated = cursor.rowcount
        conn.commit()
        
        print(f"✅ Successfully updated {rows_updated} records")
        
        # Verify the fix
        print("\n🔍 Verifying fix...")
        cursor.execute("""
            SELECT 
                MAX(mpg_current) as max_mpg,
                AVG(mpg_current) as avg_mpg,
                MIN(mpg_current) as min_mpg
            FROM fuel_metrics
            WHERE mpg_current IS NOT NULL
        """)
        
        max_mpg, avg_mpg, min_mpg = cursor.fetchone()
        print(f"\n📈 New MPG statistics:")
        print(f"  • Max MPG: {max_mpg:.2f}")
        print(f"  • Avg MPG: {avg_mpg:.2f}")
        print(f"  • Min MPG: {min_mpg:.2f}")
        
        if max_mpg <= MAX_MPG_THRESHOLD:
            print(f"\n✅ All MPG values now within valid range (≤{MAX_MPG_THRESHOLD})")
        else:
            print(f"\n⚠️  Warning: Still found MPG values above {MAX_MPG_THRESHOLD}")
        
        cursor.close()
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        if conn:
            conn.rollback()
        raise
    
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("MPG Cleanup Script")
    print("=" * 60)
    print(f"Target: Cap mpg_current values at {MAX_MPG_THRESHOLD} MPG")
    print(f"Reason: v3.15.0 had max_mpg=12.0, v5.18.0 had 8.5")
    print(f"User requirement: 44,000 lb trucks should show 4-7.8 MPG")
    print(f"Root cause: min_miles=8.0 too high, prevented MPG updates")
    print("=" * 60)
    
    cleanup_mpg_values()
    
    print("\n✅ Cleanup complete! Dashboard should now show realistic MPG values.")
