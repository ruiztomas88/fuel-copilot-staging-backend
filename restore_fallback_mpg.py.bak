#!/usr/bin/env python3
"""
Restore Fallback MPG - Temporary solution after MPG reset

After resetting mpg_current to NULL, trucks show "N.A" until they accumulate
enough data (5 miles + 0.75 gallons). This script restores fallback MPG (5.7)
for MOVING trucks to provide immediate display values.

The wialon_sync service will overwrite these values as soon as real MPG is calculated.

Usage:
    python restore_fallback_mpg.py

Author: Fuel Copilot Team
Date: December 22, 2025
"""

import mysql.connector
from datetime import datetime

# Database config
DB_CONFIG = {
    "host": "localhost",
    "user": "fuel_admin",
    "password": "FuelCopilot2025!",
    "database": "fuel_copilot"
}

FALLBACK_MPG = 5.7  # Fleet average from MPGConfig


def restore_fallback_mpg():
    """Restore fallback MPG for trucks showing NULL"""
    
    print(f"🔧 Restoring fallback MPG ({FALLBACK_MPG}) for trucks without data...")
    print(f"Timestamp: {datetime.now()}")
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # Update NULL mpg_current to fallback for recent MOVING trucks
        update_query = """
            UPDATE fuel_metrics 
            SET mpg_current = %s
            WHERE mpg_current IS NULL 
              AND timestamp_utc >= NOW() - INTERVAL 2 HOUR
              AND truck_status = 'MOVING'
        """
        
        cursor.execute(update_query, (FALLBACK_MPG,))
        rows_updated = cursor.rowcount
        conn.commit()
        
        print(f"✅ Updated {rows_updated} records with fallback MPG")
        
        # Show distribution
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT truck_id) as trucks,
                COUNT(*) as records,
                AVG(mpg_current) as avg_mpg,
                MIN(mpg_current) as min_mpg,
                MAX(mpg_current) as max_mpg
            FROM fuel_metrics
            WHERE timestamp_utc >= NOW() - INTERVAL 1 HOUR
              AND mpg_current IS NOT NULL
        """)
        
        result = cursor.fetchone()
        if result:
            print(f"\n📊 Current MPG distribution (last hour):")
            print(f"   Trucks: {result[0]}")
            print(f"   Records: {result[1]}")
            print(f"   Average: {result[2]:.2f} MPG")
            print(f"   Range: {result[3]:.2f} - {result[4]:.2f} MPG")
        
        print(f"\n✅ Done! Dashboard should now show {FALLBACK_MPG} MPG for trucks without data")
        print(f"ℹ️  These values will be replaced with real MPG as trucks accumulate data (5mi + 0.75gal)")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    restore_fallback_mpg()
