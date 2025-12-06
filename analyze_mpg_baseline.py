#!/usr/bin/env python3
"""
MPG Baseline Analysis
Analyzes actual MPG data from the fleet to determine optimal baselines.

Run on VM: python analyze_mpg_baseline.py
"""

import os
import pymysql
from dotenv import load_dotenv
from datetime import datetime, timedelta
from collections import defaultdict

load_dotenv()

def get_connection():
    return pymysql.connect(
        host=os.getenv("LOCAL_DB_HOST", "localhost"),
        port=int(os.getenv("LOCAL_DB_PORT", 3306)),
        user=os.getenv("LOCAL_DB_USER", "fuel_admin"),
        password=os.getenv("LOCAL_DB_PASS", ""),
        database=os.getenv("LOCAL_DB_NAME", "fuel_copilot"),
        cursorclass=pymysql.cursors.DictCursor,
    )

def analyze_mpg():
    conn = get_connection()
    
    print("=" * 70)
    print("📊 MPG BASELINE ANALYSIS")
    print("=" * 70)
    
    try:
        with conn.cursor() as cursor:
            # Check how much data we have
            cursor.execute("""
                SELECT 
                    COUNT(*) as total_records,
                    COUNT(DISTINCT truck_id) as trucks,
                    MIN(timestamp_utc) as first_record,
                    MAX(timestamp_utc) as last_record,
                    COUNT(CASE WHEN mpg_current IS NOT NULL AND mpg_current > 0 AND mpg_current < 20 THEN 1 END) as valid_mpg_records
                FROM fuel_metrics
            """)
            overview = cursor.fetchone()
            
            print(f"\n📈 DATA OVERVIEW:")
            print(f"   Total records: {overview['total_records']:,}")
            print(f"   Trucks: {overview['trucks']}")
            print(f"   Date range: {overview['first_record']} to {overview['last_record']}")
            print(f"   Valid MPG records: {overview['valid_mpg_records']:,}")
            
            if overview['valid_mpg_records'] < 100:
                print("\n⚠️  Not enough valid MPG data yet. Need at least 100 records.")
                print("   MPG tracking requires trucks to be MOVING with valid fuel consumption.")
                return
            
            # Analyze MPG by truck
            print(f"\n{'='*70}")
            print("🚛 MPG BY TRUCK (last 30 days, MOVING status only):")
            print(f"{'='*70}")
            
            cursor.execute("""
                SELECT 
                    truck_id,
                    COUNT(*) as samples,
                    AVG(mpg_current) as avg_mpg,
                    MIN(mpg_current) as min_mpg,
                    MAX(mpg_current) as max_mpg,
                    STDDEV(mpg_current) as std_mpg,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mpg_current) OVER (PARTITION BY truck_id) as median_mpg
                FROM fuel_metrics
                WHERE mpg_current IS NOT NULL 
                  AND mpg_current > 2  -- Filter out noise (unrealistically low)
                  AND mpg_current < 15 -- Filter out noise (unrealistically high for semi trucks)
                  AND truck_status = 'MOVING'
                  AND timestamp_utc >= NOW() - INTERVAL 30 DAY
                GROUP BY truck_id
                HAVING samples >= 10
                ORDER BY avg_mpg DESC
            """)
            truck_mpg = cursor.fetchall()
            
            if not truck_mpg:
                # Try without the PERCENTILE function (MySQL 5.7 compatibility)
                cursor.execute("""
                    SELECT 
                        truck_id,
                        COUNT(*) as samples,
                        AVG(mpg_current) as avg_mpg,
                        MIN(mpg_current) as min_mpg,
                        MAX(mpg_current) as max_mpg,
                        STDDEV(mpg_current) as std_mpg
                    FROM fuel_metrics
                    WHERE mpg_current IS NOT NULL 
                      AND mpg_current > 2
                      AND mpg_current < 15
                      AND truck_status = 'MOVING'
                      AND timestamp_utc >= NOW() - INTERVAL 30 DAY
                    GROUP BY truck_id
                    HAVING samples >= 10
                    ORDER BY avg_mpg DESC
                """)
                truck_mpg = cursor.fetchall()
            
            if not truck_mpg:
                print("\n⚠️  No valid MPG data for MOVING trucks in the last 30 days.")
                print("   Trying with all available data...")
                
                cursor.execute("""
                    SELECT 
                        truck_id,
                        COUNT(*) as samples,
                        AVG(mpg_current) as avg_mpg,
                        MIN(mpg_current) as min_mpg,
                        MAX(mpg_current) as max_mpg,
                        STDDEV(mpg_current) as std_mpg
                    FROM fuel_metrics
                    WHERE mpg_current IS NOT NULL 
                      AND mpg_current > 2
                      AND mpg_current < 15
                    GROUP BY truck_id
                    HAVING samples >= 5
                    ORDER BY avg_mpg DESC
                """)
                truck_mpg = cursor.fetchall()
            
            if truck_mpg:
                print(f"\n{'Truck':<12} {'Samples':>8} {'Avg MPG':>10} {'Min':>8} {'Max':>8} {'StdDev':>8}")
                print("-" * 60)
                
                all_avgs = []
                for row in truck_mpg:
                    std = row['std_mpg'] or 0
                    print(f"{row['truck_id']:<12} {row['samples']:>8} {row['avg_mpg']:>10.2f} {row['min_mpg']:>8.2f} {row['max_mpg']:>8.2f} {std:>8.2f}")
                    all_avgs.append(row['avg_mpg'])
                
                # Fleet average
                fleet_avg = sum(all_avgs) / len(all_avgs) if all_avgs else 0
                
                print("-" * 60)
                print(f"{'FLEET AVG':<12} {'':<8} {fleet_avg:>10.2f}")
            else:
                print("\n❌ No MPG data available for analysis.")
                return
            
            # Analyze by speed range
            print(f"\n{'='*70}")
            print("🚗 MPG BY SPEED RANGE:")
            print(f"{'='*70}")
            
            cursor.execute("""
                SELECT 
                    CASE 
                        WHEN speed_mph < 30 THEN '0-30 mph (City)'
                        WHEN speed_mph BETWEEN 30 AND 50 THEN '30-50 mph (Mixed)'
                        WHEN speed_mph BETWEEN 50 AND 65 THEN '50-65 mph (Highway)'
                        ELSE '65+ mph (Fast Highway)'
                    END as speed_range,
                    COUNT(*) as samples,
                    AVG(mpg_current) as avg_mpg
                FROM fuel_metrics
                WHERE mpg_current IS NOT NULL 
                  AND mpg_current > 2
                  AND mpg_current < 15
                  AND speed_mph IS NOT NULL
                  AND speed_mph > 0
                  AND truck_status = 'MOVING'
                GROUP BY speed_range
                ORDER BY MIN(speed_mph)
            """)
            speed_mpg = cursor.fetchall()
            
            if speed_mpg:
                print(f"\n{'Speed Range':<25} {'Samples':>10} {'Avg MPG':>10}")
                print("-" * 50)
                for row in speed_mpg:
                    print(f"{row['speed_range']:<25} {row['samples']:>10} {row['avg_mpg']:>10.2f}")
            
            # Consumption rate analysis
            print(f"\n{'='*70}")
            print("⛽ CONSUMPTION RATE ANALYSIS:")
            print(f"{'='*70}")
            
            cursor.execute("""
                SELECT 
                    truck_id,
                    AVG(consumption_gph) as avg_gph,
                    AVG(CASE WHEN truck_status = 'MOVING' THEN consumption_gph END) as moving_gph,
                    AVG(CASE WHEN truck_status IN ('STOPPED', 'IDLE') THEN consumption_gph END) as idle_gph
                FROM fuel_metrics
                WHERE consumption_gph IS NOT NULL 
                  AND consumption_gph > 0
                  AND consumption_gph < 20  -- Filter outliers
                  AND timestamp_utc >= NOW() - INTERVAL 30 DAY
                GROUP BY truck_id
                ORDER BY truck_id
            """)
            consumption = cursor.fetchall()
            
            if consumption:
                print(f"\n{'Truck':<12} {'Avg GPH':>10} {'Moving GPH':>12} {'Idle GPH':>10}")
                print("-" * 50)
                for row in consumption:
                    moving = row['moving_gph'] or 0
                    idle = row['idle_gph'] or 0
                    print(f"{row['truck_id']:<12} {row['avg_gph']:>10.2f} {moving:>12.2f} {idle:>10.2f}")
            
            # Recommendations
            print(f"\n{'='*70}")
            print("📋 RECOMMENDATIONS:")
            print(f"{'='*70}")
            
            if truck_mpg and fleet_avg > 0:
                print(f"\n   Current fleet average MPG: {fleet_avg:.2f}")
                print(f"\n   Suggested baseline values for config:")
                print(f"   - MPG_BASELINE_HIGHWAY: {min(fleet_avg + 1, 8.0):.1f}")
                print(f"   - MPG_BASELINE_CITY: {max(fleet_avg - 1.5, 4.0):.1f}")
                print(f"   - MPG_BASELINE_MIXED: {fleet_avg:.1f}")
                
                # Identify best and worst performers
                if len(truck_mpg) >= 2:
                    best = truck_mpg[0]
                    worst = truck_mpg[-1]
                    print(f"\n   🏆 Best performer: {best['truck_id']} ({best['avg_mpg']:.2f} MPG)")
                    print(f"   ⚠️  Needs attention: {worst['truck_id']} ({worst['avg_mpg']:.2f} MPG)")
            
    finally:
        conn.close()

if __name__ == "__main__":
    analyze_mpg()
