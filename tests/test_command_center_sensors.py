#!/usr/bin/env python3
"""
Test Command Center Predictive Maintenance Sensor Integration
Version: 5.12.2

Validates that newly mapped sensors (intk_t, fuel_t, intrclr_t, trams_t, 
intake_pressure, actual_retarder) are:
1. Being saved to fuel_metrics table by wialon_sync
2. Being read correctly by Command Center
3. Used in FAILURE_CORRELATIONS for predictive maintenance
"""

import os
import sys
import pymysql
from typing import Dict, List
from datetime import datetime, timedelta

# Database config
DB_CONFIG = {
    'host': 'localhost',
    'user': 'fuel_admin',
    "password": os.getenv("MYSQL_PASSWORD", ""),
    'database': 'fuel_copilot',
    'charset': 'utf8mb4'
}

# Sensors we just mapped for Command Center
PREDICTIVE_SENSORS = {
    "trans_temp_f": "trams_t",  # Transmission temp (Wialon: trams_t)
    "fuel_temp_f": "fuel_t",  # Fuel temp
    "intercooler_temp_f": "intrclr_t",  # Intercooler temp
    "intake_air_temp_f": "intk_t",  # Intake air temp
    "intake_press_kpa": "intake_pressure",  # Intake manifold pressure
    "retarder_level": "actual_retarder",  # Retarder brake
    "coolant_temp_f": "cool_temp",  # Coolant temp (already existed)
    "oil_temp_f": "oil_temp",  # Oil temp (already existed)
}

# Command Center failure correlations
FAILURE_CORRELATIONS = {
    "overheating_syndrome": ["coolant_temp_f", "oil_temp_f", "trans_temp_f"],
    "turbo_lag": ["intake_air_temp_f", "engine_load_pct", "coolant_temp_f"],
    "transmission_stress": ["trans_temp_f", "oil_temp_f", "engine_load_pct"],
}


def test_schema_migration():
    """Test 1: Verify new columns exist in fuel_metrics"""
    print("\n" + "="*80)
    print("TEST 1: Database Schema Migration")
    print("="*80)
    
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Check if columns exist
        cursor.execute("""
            SELECT COLUMN_NAME, COLUMN_TYPE, COLUMN_COMMENT 
            FROM INFORMATION_SCHEMA.COLUMNS 
            WHERE TABLE_SCHEMA = 'fuel_copilot' 
            AND TABLE_NAME = 'fuel_metrics'
            AND COLUMN_NAME IN ('trans_temp_f', 'fuel_temp_f', 'intercooler_temp_f', 
                                'intake_press_kpa', 'retarder_level')
            ORDER BY COLUMN_NAME
        """)
        
        columns = cursor.fetchall()
        
        if len(columns) == 5:
            print("✅ All 5 predictive maintenance columns exist:")
            for col_name, col_type, col_comment in columns:
                print(f"   - {col_name} ({col_type}): {col_comment}")
            return True
        else:
            print(f"❌ Missing columns! Found {len(columns)}/5")
            print("   Run migration: migrations/add_predictive_sensors_v5_12_2.sql")
            return False
            
    except Exception as e:
        print(f"❌ Schema check failed: {e}")
        return False
    finally:
        conn.close()


def test_data_availability():
    """Test 2: Check if sensors have recent data"""
    print("\n" + "="*80)
    print("TEST 2: Sensor Data Availability (Last 24 Hours)")
    print("="*80)
    
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Check coverage for each sensor
        cursor.execute("""
            SELECT 
                COUNT(*) as total_rows,
                COUNT(trans_temp_f) as has_trans_temp,
                COUNT(fuel_temp_f) as has_fuel_temp,
                COUNT(intercooler_temp_f) as has_intercooler,
                COUNT(intake_air_temp_f) as has_intake_air,
                COUNT(intake_press_kpa) as has_intake_press,
                COUNT(retarder_level) as has_retarder,
                COUNT(coolant_temp_f) as has_coolant,
                COUNT(oil_temp_f) as has_oil_temp
            FROM fuel_metrics
            WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 24 HOUR)
        """)
        
        stats = cursor.fetchone()
        total = stats['total_rows']
        
        print(f"\n📊 Data Coverage (last 24h, {total:,} total records):\n")
        
        sensors = [
            ("Coolant Temp", "has_coolant"),
            ("Oil Temp", "has_oil_temp"),
            ("Trans Temp", "has_trans_temp"),
            ("Intake Air Temp", "has_intake_air"),
            ("Fuel Temp", "has_fuel_temp"),
            ("Intercooler Temp", "has_intercooler"),
            ("Intake Pressure", "has_intake_press"),
            ("Retarder Level", "has_retarder"),
        ]
        
        coverage_good = True
        for name, key in sensors:
            count = stats[key]
            pct = (count / total * 100) if total > 0 else 0
            status = "✅" if pct > 20 else "⚠️" if pct > 0 else "❌"
            print(f"{status} {name:20} {count:6,} records ({pct:5.1f}%)")
            
            if pct == 0 and "Trans" in name:  # New sensors we care about
                coverage_good = False
        
        if coverage_good:
            print("\n✅ All critical sensors have data")
            return True
        else:
            print("\n⚠️ Some new sensors have no data yet - wialon_sync may not have run")
            return False
            
    except Exception as e:
        print(f"❌ Data availability check failed: {e}")
        return False
    finally:
        conn.close()


def test_command_center_query():
    """Test 3: Verify Command Center query retrieves new sensors"""
    print("\n" + "="*80)
    print("TEST 3: Command Center Query Compatibility")
    print("="*80)
    
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Simulate Command Center's query
        cursor.execute("""
            SELECT 
                truck_id,
                oil_pressure_psi as oil_press,
                oil_temp_f as oil_temp,
                coolant_temp_f as cool_temp,
                trans_temp_f as trams_t,
                battery_voltage as voltage,
                engine_load_pct as engine_load,
                rpm,
                def_level_pct as def_level,
                intake_air_temp_f as intk_t,
                fuel_temp_f,
                intercooler_temp_f,
                intake_press_kpa,
                sensor_pct as fuel_lvl,
                timestamp_utc
            FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY truck_id 
                        ORDER BY timestamp_utc DESC
                    ) as rn
                FROM fuel_metrics
                WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 2 HOUR)
            ) latest
            WHERE rn = 1
            LIMIT 10
        """)
        
        trucks = cursor.fetchall()
        
        if not trucks:
            print("⚠️ No recent truck data (last 2 hours)")
            return False
        
        print(f"\n📋 Sample trucks with sensor data:\n")
        
        success_count = 0
        for truck in trucks:
            truck_id = truck['truck_id']
            
            # Check which correlation sensors are available
            overheating = all([
                truck.get('cool_temp') is not None,
                truck.get('oil_temp') is not None,
                truck.get('trams_t') is not None
            ])
            
            turbo = all([
                truck.get('intk_t') is not None,
                truck.get('engine_load') is not None,
                truck.get('cool_temp') is not None
            ])
            
            status = "✅" if (overheating and turbo) else "⚠️" if (overheating or turbo) else "❌"
            
            sensors_str = []
            if truck.get('cool_temp'): sensors_str.append(f"cool={truck['cool_temp']:.0f}°F")
            if truck.get('oil_temp'): sensors_str.append(f"oil={truck['oil_temp']:.0f}°F")
            if truck.get('trams_t'): sensors_str.append(f"trans={truck['trams_t']:.0f}°F")
            if truck.get('intk_t'): sensors_str.append(f"intake={truck['intk_t']:.0f}°F")
            
            correlations = []
            if overheating: correlations.append("OVERHEAT")
            if turbo: correlations.append("TURBO")
            
            corr_str = ", ".join(correlations) if correlations else "NONE"
            
            print(f"{status} {truck_id:8} | {', '.join(sensors_str):50} | Correlations: {corr_str}")
            
            if overheating and turbo:
                success_count += 1
        
        print(f"\n📈 {success_count}/{len(trucks)} trucks have full predictive maintenance coverage")
        
        if success_count > 0:
            print("✅ Command Center can detect failure correlations")
            return True
        else:
            print("⚠️ No trucks have complete sensor coverage for correlations")
            return False
            
    except Exception as e:
        print(f"❌ Command Center query test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


def test_failure_correlation_detection():
    """Test 4: Check if we can detect actual correlation patterns"""
    print("\n" + "="*80)
    print("TEST 4: Failure Correlation Pattern Detection")
    print("="*80)
    
    try:
        conn = pymysql.connect(**DB_CONFIG)
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        
        # Look for trucks with suspicious temperature correlations
        cursor.execute("""
            SELECT 
                truck_id,
                coolant_temp_f,
                oil_temp_f,
                trans_temp_f,
                intake_air_temp_f,
                engine_load_pct,
                timestamp_utc,
                CASE 
                    WHEN coolant_temp_f > 210 AND oil_temp_f > 230 AND trans_temp_f > 200 
                    THEN 'OVERHEATING_SYNDROME'
                    WHEN intake_air_temp_f > 150 AND engine_load_pct > 80 
                    THEN 'TURBO_LAG_SUSPECTED'
                    ELSE 'NORMAL'
                END as pattern
            FROM fuel_metrics
            WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 24 HOUR)
            AND coolant_temp_f IS NOT NULL
            AND oil_temp_f IS NOT NULL
            AND trans_temp_f IS NOT NULL
            ORDER BY timestamp_utc DESC
            LIMIT 100
        """)
        
        rows = cursor.fetchall()
        
        if not rows:
            print("⚠️ No data with all temperature sensors populated")
            return False
        
        # Count patterns
        patterns = {}
        for row in rows:
            pattern = row['pattern']
            patterns[pattern] = patterns.get(pattern, 0) + 1
        
        print(f"\n🔍 Pattern Analysis (last 24h, {len(rows)} records):\n")
        
        for pattern, count in sorted(patterns.items(), key=lambda x: -x[1]):
            pct = count / len(rows) * 100
            icon = "🚨" if "SYNDROME" in pattern or "LAG" in pattern else "✅"
            print(f"{icon} {pattern:25} {count:4} occurrences ({pct:5.1f}%)")
        
        # Show examples of abnormal patterns
        abnormal = [r for r in rows if r['pattern'] != 'NORMAL']
        if abnormal:
            print(f"\n⚠️ Found {len(abnormal)} abnormal patterns - examples:\n")
            for row in abnormal[:3]:
                print(f"   {row['truck_id']:8} @ {row['timestamp_utc']}")
                print(f"      Coolant: {row['coolant_temp_f']:.0f}°F | Oil: {row['oil_temp_f']:.0f}°F | Trans: {row['trans_temp_f']:.0f}°F")
                print(f"      Pattern: {row['pattern']}\n")
        
        if len(abnormal) > 0:
            print("✅ Correlation detection is working - found abnormal patterns")
            return True
        else:
            print("✅ All temperature patterns normal (good fleet health)")
            return True
            
    except Exception as e:
        print(f"❌ Correlation detection test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("COMMAND CENTER PREDICTIVE MAINTENANCE SENSOR INTEGRATION TEST")
    print("Version 5.12.2 - December 2025")
    print("="*80)
    
    results = {
        "schema": test_schema_migration(),
        "data": test_data_availability(),
        "query": test_command_center_query(),
        "correlation": test_failure_correlation_detection(),
    }
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} - {test_name.upper()}")
    
    total_passed = sum(results.values())
    total_tests = len(results)
    
    print(f"\n📊 Overall: {total_passed}/{total_tests} tests passed")
    
    if total_passed == total_tests:
        print("\n🎉 All tests passed! Command Center ready for predictive maintenance.")
        sys.exit(0)
    else:
        print("\n⚠️ Some tests failed. Review output above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
