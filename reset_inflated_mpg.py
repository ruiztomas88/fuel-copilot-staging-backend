"""
Reset MPG for trucks with inflated values > 9.0

This script resets mpg_current to NULL for trucks showing unrealistic MPG values
that were calculated when max_mpg was 12.0. After reset, wialon_sync_enhanced.py
will recalculate MPG with the correct config (max_mpg=9.0).

Usage:
    python reset_inflated_mpg.py

Author: Fuel Copilot Team
Date: December 22, 2025
"""

import mysql.connector
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

# Database connection
DB_CONFIG = {
    'host': 'localhost',
    'user': 'fuel_admin',
    'password': 'FuelCopilot2025!',
    'database': 'fuel_copilot'
}

def reset_inflated_mpg():
    """Reset MPG values > 9.0 to force recalculation"""
    
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()
    
    try:
        # Step 1: Find trucks with inflated MPG
        cursor.execute("""
            SELECT DISTINCT truck_id, MAX(mpg_current) as max_mpg
            FROM fuel_metrics
            WHERE mpg_current > 9.0
            GROUP BY truck_id
            ORDER BY max_mpg DESC
        """)
        
        inflated_trucks = cursor.fetchall()
        
        if not inflated_trucks:
            logger.info("✅ No inflated MPG values found (all ≤ 9.0)")
            return
        
        logger.info(f"🔍 Found {len(inflated_trucks)} trucks with MPG > 9.0:")
        for truck_id, max_mpg in inflated_trucks:
            logger.info(f"   - {truck_id}: {max_mpg:.2f} MPG")
        
        # Step 2: Reset to NULL to force recalculation
        cursor.execute("""
            UPDATE fuel_metrics
            SET mpg_current = NULL
            WHERE mpg_current > 9.0
        """)
        
        rows_updated = cursor.rowcount
        conn.commit()
        
        logger.info(f"✅ Reset {rows_updated} records with MPG > 9.0")
        logger.info("📊 Trucks will recalculate MPG on next sync cycle")
        
        # Step 3: Show current distribution
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN mpg_current IS NULL THEN 'NULL'
                    WHEN mpg_current < 4.0 THEN '< 4.0'
                    WHEN mpg_current < 5.0 THEN '4.0-5.0'
                    WHEN mpg_current < 6.0 THEN '5.0-6.0'
                    WHEN mpg_current < 7.0 THEN '6.0-7.0'
                    WHEN mpg_current < 8.0 THEN '7.0-8.0'
                    WHEN mpg_current < 9.0 THEN '8.0-9.0'
                    ELSE '> 9.0'
                END as mpg_range,
                COUNT(DISTINCT truck_id) as truck_count
            FROM (
                SELECT truck_id, mpg_current
                FROM fuel_metrics
                WHERE truck_id IN (
                    SELECT DISTINCT truck_id 
                    FROM fuel_metrics 
                    WHERE timestamp_utc >= NOW() - INTERVAL 1 HOUR
                )
                ORDER BY timestamp_utc DESC
            ) as latest
            GROUP BY mpg_range
            ORDER BY mpg_range
        """)
        
        distribution = cursor.fetchall()
        logger.info("\n📊 Current MPG distribution (last hour):")
        for mpg_range, count in distribution:
            logger.info(f"   {mpg_range:12s}: {count:3d} trucks")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    reset_inflated_mpg()
