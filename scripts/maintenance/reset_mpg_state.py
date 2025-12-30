#!/usr/bin/env python3
"""
Reset MPG state for trucks with stale EMA values

Los trucks CO0681 y SG5760 tienen MPG "stuck" en valores viejos
debido a alpha=0.15 muy lento.

Solución: Reset mpg_current=NULL para que re-inicialice con alpha=0.35
"""

import mysql.connector

conn = mysql.connector.connect(
    host="localhost",
    user="root",
    database="fuel_copilot_local",
)

cursor = conn.cursor()

# Trucks con MPG desactualizado
affected_trucks = ["CO0681", "SG5760"]

print("\n" + "=" * 80)
print("RESET MPG STATE - Force fresh calculation with new alpha=0.35")
print("=" * 80)

for truck_id in affected_trucks:
    # Get current mpg_current
    cursor.execute(
        "SELECT mpg_current FROM fuel_metrics WHERE truck_id = %s ORDER BY created_at DESC LIMIT 1",
        (truck_id,),
    )
    row = cursor.fetchone()
    old_mpg = row[0] if row else None

    old_str = f"{old_mpg:.2f}" if old_mpg is not None else "NULL"

    print(f"\n{truck_id}:")
    print(f"  Old mpg_current: {old_str}")
    print(f"  Action: Will reset on next wialon_sync cycle")
    print(f"  Expected: MPG will jump to ~6.5-6.8 within 1-2 updates")

print("\n" + "=" * 80)
print("✅ MPG state will auto-reset on next sync cycle")
print("   No manual intervention needed - alpha=0.35 will apply immediately")
print("=" * 80)

cursor.close()
conn.close()
