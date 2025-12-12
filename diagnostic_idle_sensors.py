#!/usr/bin/env python3
"""
🔍 DIAGNOSTIC: Check what idle-related sensors we actually have from Wialon

This script queries the actual Wialon DB to see:
1. Do we have fuel_rate sensor? (in sensor_data table)
2. Do we have total_idle_fuel counter? (in sensor_data table)
3. What values are they returning?
4. Are they NULL/missing for all trucks?

Run this to understand the ACTUAL data availability before building solutions.
"""

import os
import sys
import pymysql
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Wialon DB connection
WIALON_HOST = os.getenv("WIALON_DB_HOST", "20.127.200.135")
WIALON_DB = os.getenv("WIALON_DB_NAME", "wialon_collect")
WIALON_USER = os.getenv("WIALON_DB_USER", "tomas")
WIALON_PASS = os.getenv("WIALON_DB_PASS", "")

def check_idle_sensors():
    """Check what idle-related sensors we have in Wialon"""
    
    conn = pymysql.connect(
        host=WIALON_HOST,
        user=WIALON_USER,
        password=WIALON_PASS,
        database=WIALON_DB,
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    
    try:
        print("=" * 80)
        print("🔍 WIALON IDLE SENSOR DIAGNOSTIC")
        print("=" * 80)
        print()
        
        # Get sample trucks
        sample_trucks = ["VD3579", "JC1282", "FF7702", "JB6858", "RT9127"]
        
        # Get sample of what params exist in Wialon
        with conn.cursor() as cursor:
            query = """
                SELECT p as param_name, COUNT(*) as count
                FROM sensors
                WHERE m > UNIX_TIMESTAMP(NOW() - INTERVAL 24 HOUR)
                GROUP BY p
                ORDER BY count DESC
                LIMIT 20
            """
            cursor.execute(query)
            params = cursor.fetchall()
            
            print("\n📊 Available Parameters in Wialon (last 24h):")
            print("-" * 80)
            for row in params:
                print(f"  {row['param_name']:30s} {row['count']:,} samples")
            
            # Check if our target params exist
            param_names = [p['param_name'] for p in params]
            
            has_fuel_rate = 'fuel_rate' in param_names
            has_idle_fuel = 'total_idle_fuel' in param_names
            has_rpm = 'rpm' in param_names
            
            print("\n" + "=" * 80)
            print("💡 TARGET SENSORS STATUS")
            print("=" * 80)
            print(f"  fuel_rate:          {'✅ EXISTS' if has_fuel_rate else '❌ NOT FOUND'}")
            print(f"  total_idle_fuel:    {'✅ EXISTS' if has_idle_fuel else '❌ NOT FOUND'}")
            print(f"  rpm:                {'✅ EXISTS' if has_rpm else '❌ NOT FOUND'}")
            
        print("\n" + "=" * 80)
        print("📋 RECOMMENDATION")
        print("=" * 80)
        
        if has_fuel_rate:
            print("\n✅ fuel_rate sensor EXISTS in Wialon")
            print("   → Use it directly for idle consumption")
            print("   → No Kalman filter needed - sensor is direct from ECU")
        elif has_idle_fuel:
            print("\n✅ total_idle_fuel counter EXISTS in Wialon")
            print("   → Calculate delta: (total_idle_fuel_now - prev) / time_delta")
            print("   → Very accurate (±0.1% from ECU)")
        elif has_rpm:
            print("\n⚠️  Only RPM available")
            print("   → Need to estimate idle from RPM + engine_load")
            print("   → Less accurate but workable")
        else:
            print("\n❌ NO idle-related sensors found")
            print("   → Contact Pacific Track to enable:")
            print("      - fuel_rate (preferred)")
            print("      - total_idle_fuel (alternative)")
            print("      - rpm + engine_load (minimum)")
        
        return params
        
    finally:
        conn.close()

if __name__ == "__main__":
    check_idle_sensors()
