#!/usr/bin/env python3
"""
Check voltage data in fuel_metrics to understand why Command Center shows 0 issues
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_mysql import get_sqlalchemy_engine
from sqlalchemy import text

def check_voltage_data():
    print("=" * 70)
    print("VOLTAGE DATA ANALYSIS - WHY COMMAND CENTER SHOWS 0 ISSUES?")
    print("=" * 70)
    
    engine = get_sqlalchemy_engine()
    
    with engine.connect() as conn:
        # 1. Check if battery_voltage column has data
        print("\n📊 1. Battery Voltage Column Stats (last 24h):")
        result = conn.execute(text("""
            SELECT 
                COUNT(*) as total_records,
                COUNT(battery_voltage) as records_with_voltage,
                SUM(CASE WHEN battery_voltage > 0 THEN 1 ELSE 0 END) as records_with_positive_voltage,
                MIN(battery_voltage) as min_voltage,
                MAX(battery_voltage) as max_voltage,
                AVG(battery_voltage) as avg_voltage
            FROM fuel_metrics
            WHERE timestamp_utc >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 24 HOUR)
        """))
        row = result.fetchone()
        print(f"   Total records (24h): {row[0]:,}")
        print(f"   Records with voltage: {row[1]:,}")
        print(f"   Records with positive voltage: {row[2]:,}")
        print(f"   Min voltage: {row[3]}")
        print(f"   Max voltage: {row[4]}")
        print(f"   Avg voltage: {row[5]:.2f}" if row[5] else "   Avg voltage: NULL")
        
        # 2. Voltage distribution
        print("\n📈 2. Voltage Distribution (last 24h):")
        result = conn.execute(text("""
            SELECT 
                CASE 
                    WHEN battery_voltage IS NULL OR battery_voltage = 0 THEN 'No Data'
                    WHEN battery_voltage < 12.0 THEN '< 12.0V (CRITICAL)'
                    WHEN battery_voltage < 12.2 THEN '12.0-12.2V (LOW)'
                    WHEN battery_voltage <= 14.5 THEN '12.2-14.5V (NORMAL)'
                    WHEN battery_voltage <= 15.0 THEN '14.5-15.0V (HIGH-NORMAL)'
                    ELSE '> 15.0V (TOO HIGH)'
                END as voltage_range,
                COUNT(DISTINCT truck_id) as trucks
            FROM fuel_metrics
            WHERE timestamp_utc >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 24 HOUR)
            GROUP BY voltage_range
            ORDER BY 
                CASE voltage_range
                    WHEN '< 12.0V (CRITICAL)' THEN 1
                    WHEN '12.0-12.2V (LOW)' THEN 2
                    WHEN '12.2-14.5V (NORMAL)' THEN 3
                    WHEN '14.5-15.0V (HIGH-NORMAL)' THEN 4
                    WHEN '> 15.0V (TOO HIGH)' THEN 5
                    ELSE 6
                END
        """))
        for row in result:
            print(f"   {row[0]}: {row[1]} trucks")
            
        # 3. Check latest voltage per truck
        print("\n🔋 3. Trucks with LOW voltage (latest reading):")
        result = conn.execute(text("""
            WITH latest AS (
                SELECT truck_id, battery_voltage,
                       ROW_NUMBER() OVER (PARTITION BY truck_id ORDER BY timestamp_utc DESC) as rn
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 24 HOUR)
                  AND battery_voltage > 0
            )
            SELECT truck_id, battery_voltage
            FROM latest
            WHERE rn = 1 AND battery_voltage < 12.2
            ORDER BY battery_voltage
            LIMIT 10
        """))
        rows = result.fetchall()
        if rows:
            for row in rows:
                print(f"   {row[0]}: {row[1]:.2f}V ⚠️")
        else:
            print("   No trucks with voltage < 12.2V")
            
        # 4. Check if pwr_ext has data (alternative voltage field)
        print("\n🔌 4. Check pwr_ext column (alternative voltage?):")
        result = conn.execute(text("""
            SELECT 
                COUNT(DISTINCT truck_id) as trucks_with_data,
                MIN(pwr_ext) as min_val,
                MAX(pwr_ext) as max_val,
                AVG(pwr_ext) as avg_val
            FROM fuel_metrics
            WHERE timestamp_utc >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 24 HOUR)
              AND pwr_ext IS NOT NULL AND pwr_ext > 0
        """))
        row = result.fetchone()
        print(f"   Trucks with pwr_ext data: {row[0]}")
        print(f"   Min: {row[1]}, Max: {row[2]}, Avg: {row[3]:.2f}" if row[3] else f"   Min: {row[1]}, Max: {row[2]}, Avg: NULL")
        
        # 5. Sample of actual values
        print("\n📋 5. Sample voltage readings (10 random trucks):")
        result = conn.execute(text("""
            WITH latest AS (
                SELECT truck_id, battery_voltage, pwr_ext, timestamp_utc,
                       ROW_NUMBER() OVER (PARTITION BY truck_id ORDER BY timestamp_utc DESC) as rn
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL 24 HOUR)
            )
            SELECT truck_id, battery_voltage, pwr_ext, timestamp_utc
            FROM latest
            WHERE rn = 1
            ORDER BY RAND()
            LIMIT 10
        """))
        for row in result:
            print(f"   {row[0]}: battery={row[1]}V, pwr_ext={row[2]}")

if __name__ == "__main__":
    check_voltage_data()
