#!/usr/bin/env python3
"""
Compare MPG calculation: current vs avg_24h

Producción usa mpg_current (valor actual EMA-smoothed)
Nuestro sistema usa avg_mpg_24h (promedio 24 horas)

Esto explica las diferencias en el dashboard.
"""

import os

import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    database="fuel_copilot_local",
)

cursor = conn.cursor(dictionary=True)

print("\n" + "=" * 100)
print("MPG COMPARISON: Current vs 24h Average")
print("=" * 100)

# Get current mpg_current for each truck
query_current = """
    SELECT 
        truck_id,
        mpg_current,
        created_at
    FROM fuel_metrics
    WHERE created_at > DATE_SUB(NOW(), INTERVAL 5 MINUTE)
      AND truck_id IN ('CO0681', 'JB6858', 'JC1282', 'JP3281', 'SG5760')
    ORDER BY truck_id, created_at DESC
"""

cursor.execute(query_current)
current_mpg = {}
for row in cursor.fetchall():
    truck_id = row["truck_id"]
    if truck_id not in current_mpg:
        current_mpg[truck_id] = row["mpg_current"]

# Get 24h average for each truck
query_avg = """
    SELECT 
        truck_id,
        AVG(mpg_current) as avg_mpg_24h
    FROM fuel_metrics
    WHERE created_at > DATE_SUB(NOW(), INTERVAL 24 HOUR)
      AND truck_status = 'MOVING'
      AND mpg_current > 3.5 AND mpg_current < 12
      AND truck_id IN ('CO0681', 'JB6858', 'JC1282', 'JP3281', 'SG5760')
    GROUP BY truck_id
"""

cursor.execute(query_avg)
avg_24h = {}
for row in cursor.fetchall():
    avg_24h[row["truck_id"]] = row["avg_mpg_24h"]

print(f"\n{'Truck':<10} {'Current MPG':>12} {'24h Avg MPG':>12} {'Diff':>10} {'Notes'}")
print("-" * 100)

for truck_id in ["CO0681", "JB6858", "JC1282", "JP3281", "SG5760"]:
    curr = current_mpg.get(truck_id)
    avg = avg_24h.get(truck_id)

    if curr and avg:
        diff_pct = ((curr - avg) / avg) * 100
        note = "✅ Current used" if abs(diff_pct) < 5 else "⚠️  24h avg differs"
    elif curr and not avg:
        diff_pct = 0
        note = "⚠️  No 24h MOVING data"
    else:
        diff_pct = 0
        note = "❌ No current data"

    curr_str = f"{curr:.2f}" if curr else "N/A"
    avg_str = f"{avg:.2f}" if avg else "N/A"
    diff_str = f"{diff_pct:+.1f}%" if curr and avg else "-"

    print(f"{truck_id:<10} {curr_str:>12} {avg_str:>12} {diff_str:>10} {note}")

print("\n" + "=" * 100)
print("🔍 ANALYSIS:")
print("=" * 100)
print("\n1. PRODUCCIÓN muestra: mpg_current (MPG actual, EMA smoothed)")
print("   - Valores: CO0681=6.7, JC1282=6.7, JP3281=7.4, SG5760=6.0")
print("\n2. NUESTRO SISTEMA muestra: avg_mpg_24h (promedio últimas 24 horas)")
print("   - Valores: CO0681=4.0, JC1282=6.9, JP3281=7.8, SG5760=4.6")
print("\n3. SOLUCIÓN:")
print("   - Cambiar database.py línea 697 de:")
print("     mpg_val = avg_mpg_24h if avg_mpg_24h else mpg_current")
print("   - A:")
print("     mpg_val = mpg_current if mpg_current else avg_mpg_24h")
print("\n   Esto alineará nuestro dashboard con producción (mostrar valor actual)")
print("=" * 100)

cursor.close()
conn.close()
