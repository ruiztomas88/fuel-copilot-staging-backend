#!/usr/bin/env python
"""Quick test of column fixes"""
import pymysql

print("=" * 80)
print("🧪 TESTING COLUMN FIXES")
print("=" * 80)

# Test 1: Verificar que intake_air_temp_f existe
print("\n1️⃣ Testing intake_air_temp_f column...")
conn = pymysql.connect(
    host='localhost',
    user='fuel_admin',
    password=os.getenv("DB_PASSWORD"),
    database='fuel_copilot'
)
cursor = conn.cursor()

# Test alias query
query = """
import os
SELECT 
    truck_id,
    intake_air_temp_f as intake_temp_f
FROM fuel_metrics
WHERE timestamp_utc > NOW() - INTERVAL 1 HOUR
LIMIT 5
"""
cursor.execute(query)
results = cursor.fetchall()
print(f"   ✅ intake_air_temp_f AS intake_temp_f: OK ({len(results)} rows)")

# Test 2: Verificar idle_hours_ecu
print("\n2️⃣ Testing idle_hours_ecu column...")
query2 = """
SELECT 
    truck_id,
    idle_hours_ecu as idle_hours,
    engine_hours
FROM fuel_metrics
WHERE timestamp_utc > NOW() - INTERVAL 1 HOUR
LIMIT 5
"""
cursor.execute(query2)
results2 = cursor.fetchall()
print(f"   ✅ idle_hours_ecu AS idle_hours: OK ({len(results2)} rows)")

# Test 3: Test get_sensor_health_summary function
print("\n3️⃣ Testing get_sensor_health_summary()...")
from database_mysql import get_sensor_health_summary
summary = get_sensor_health_summary()
print(f"   ✅ Total trucks: {summary.get('total_trucks', 0)}")
print(f"   ✅ Voltage issues: {summary.get('trucks_with_voltage_issues', 0)}")
print(f"   ✅ Intake temp issues: {summary.get('trucks_with_intake_temp_high', 0)}")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("✅ ALL COLUMN FIXES VERIFIED - READY TO TEST COMMAND CENTER")
print("=" * 80)
