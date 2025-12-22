#!/usr/bin/env python
"""
Diagnóstico completo del sistema - verificar TODAS las funcionalidades
"""
from datetime import datetime

import pymysql
from config import get_local_db_config

print("=" * 80)
print("🔍 DIAGNÓSTICO COMPLETO DEL SISTEMA")
print("=" * 80)

conn = pymysql.connect(**get_local_db_config())
cursor = conn.cursor()

# 1. FUEL_METRICS - datos básicos
print("\n1️⃣ FUEL_METRICS")
cursor.execute(
    """
    SELECT 
        COUNT(*) as total,
        COUNT(DISTINCT truck_id) as trucks,
        MAX(timestamp_utc) as latest,
        MIN(timestamp_utc) as oldest
    FROM fuel_metrics
"""
)
row = cursor.fetchone()
print(f"   Total records: {row[0]:,}")
print(f"   Trucks: {row[1]}")
print(f"   Latest: {row[2]}")
print(f"   Oldest: {row[3]}")

# Verificar columnas críticas
cursor.execute(
    """
    SELECT 
        COUNT(CASE WHEN rpm IS NOT NULL AND rpm > 0 THEN 1 END) as has_rpm,
        COUNT(CASE WHEN speed_mph IS NOT NULL THEN 1 END) as has_speed,
        COUNT(CASE WHEN consumption_gph IS NOT NULL AND consumption_gph > 0 THEN 1 END) as has_consumption,
        COUNT(CASE WHEN altitude_ft IS NOT NULL THEN 1 END) as has_altitude,
        COUNT(CASE WHEN coolant_temp_f IS NOT NULL AND coolant_temp_f > 0 THEN 1 END) as has_coolant,
        COUNT(*) as total
    FROM fuel_metrics
    WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 24 HOUR)
"""
)
row = cursor.fetchone()
total = row[5]
print(f"\n   📊 Datos últimas 24h ({total:,} records):")
print(f"      RPM: {row[0]:,} ({row[0]/total*100:.1f}%)")
print(f"      Speed: {row[1]:,} ({row[1]/total*100:.1f}%)")
print(f"      Consumption: {row[2]:,} ({row[2]/total*100:.1f}%)")
print(f"      Altitude: {row[3]:,} ({row[3]/total*100:.1f}%)")
print(f"      Coolant: {row[4]:,} ({row[4]/total*100:.1f}%)")

# 2. DTCs
print("\n2️⃣ DTCs")
cursor.execute("SELECT COUNT(*) FROM dtc_events")
total_dtcs = cursor.fetchone()[0]
cursor.execute("SELECT COUNT(*) FROM dtc_events WHERE status = 'ACTIVE'")
active_dtcs = cursor.fetchone()[0]
print(f"   Total DTCs: {total_dtcs}")
print(f"   Active DTCs: {active_dtcs}")

if active_dtcs > 0:
    cursor.execute(
        """
        SELECT truck_id, dtc_code, severity, component
        FROM dtc_events
        WHERE status = 'ACTIVE'
        ORDER BY timestamp_utc DESC
        LIMIT 5
    """
    )
    print("\n   🔴 Top 5 Active DTCs:")
    for row in cursor.fetchall():
        print(f"      {row[0]}: {row[1]} ({row[2]}) - {row[3]}")

# 3. REFUEL_EVENTS
print("\n3️⃣ REFUEL_EVENTS")
cursor.execute("SELECT COUNT(*) FROM refuel_events")
refuels = cursor.fetchone()[0]
print(f"   Total refuels: {refuels}")

if refuels > 0:
    cursor.execute(
        """
        SELECT SUM(gallons_added), COUNT(DISTINCT truck_id)
        FROM refuel_events
        WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 7 DAY)
    """
    )
    row = cursor.fetchone()
    print(f"   Last 7 days: {row[0] or 0:.1f} gallons, {row[1] or 0} trucks")

# 4. LOSS ANALYSIS Test
print("\n4️⃣ LOSS ANALYSIS")
cursor.execute(
    """
    SELECT 
        COUNT(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN 1 END) as idle_events,
        SUM(CASE WHEN truck_status = 'STOPPED' AND consumption_gph > 0.3 THEN consumption_gph ELSE 0 END) as idle_gph,
        COUNT(CASE WHEN rpm > 1800 AND truck_status = 'MOVING' THEN 1 END) as high_rpm_events,
        COUNT(CASE WHEN speed_mph > 70 AND truck_status = 'MOVING' THEN 1 END) as overspeed_events,
        COUNT(CASE WHEN altitude_ft > 3000 AND truck_status = 'MOVING' THEN 1 END) as high_alt_events,
        COUNT(CASE WHEN coolant_temp_f > 220 THEN 1 END) as overheat_events
    FROM fuel_metrics
    WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 1 DAY)
"""
)
row = cursor.fetchone()
print(f"   Idle events (>0.3 GPH stopped): {row[0]:,}")
print(f"   Total idle GPH: {row[1]:.1f}")
print(f"   High RPM events (>1800): {row[2]:,}")
print(f"   Overspeeding (>70 mph): {row[3]:,}")
print(f"   High altitude (>3000 ft): {row[4]:,}")
print(f"   Overheating (>220°F): {row[5]:,}")

# 5. TABLAS FALTANTES
print("\n5️⃣ TABLAS CRÍTICAS")
critical_tables = ["daily_truck_metrics", "trip_data", "fleet_summary"]
cursor.execute("SHOW TABLES")
existing = [row[0] for row in cursor.fetchall()]

for table in critical_tables:
    exists = table in existing
    if exists:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"   ✅ {table}: {count:,} rows")
    else:
        print(f"   ❌ {table}: MISSING")

cursor.close()
conn.close()

print("\n" + "=" * 80)
print("✅ DIAGNÓSTICO COMPLETADO")
print("=" * 80)
