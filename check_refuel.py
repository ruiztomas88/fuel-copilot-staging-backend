#!/usr/bin/env python3
"""Check refuel detection for MR7679"""
import sys

sys.path.insert(0, "/Users/tomasruiz/Desktop/Fuel-Analytics-Backend")

from datetime import datetime, timedelta

from sqlalchemy import text

from database_mysql import get_db_connection

print("🔍 Checking refuel events for MR7679...\n")

with get_db_connection() as conn:
    # Get last refuel events
    result = conn.execute(
        text(
            """
        SELECT truck_id, refuel_time, before_pct, after_pct, gallons_added, confidence 
        FROM refuel_events 
        WHERE truck_id = 'MR7679' 
        ORDER BY refuel_time DESC 
        LIMIT 5
    """
        )
    )

    refuels = result.fetchall()
    if not refuels:
        print("❌ No refuels found for MR7679")
    else:
        print("📊 Last 5 refuels for MR7679:")
        for row in refuels:
            print(
                f"  {row[1]}: {row[3]}% (was {row[2]}%) - {row[4]} gal - conf: {row[5]}%"
            )

    # Check fuel_metrics for sudden fuel increase
    print("\n🔍 Checking fuel_metrics for sudden jumps...\n")
    result = conn.execute(
        text(
            """
        SELECT timestamp_utc, estimated_pct, sensor_pct, truck_status
        FROM fuel_metrics 
        WHERE truck_id = 'MR7679' 
        ORDER BY timestamp_utc DESC 
        LIMIT 10
    """
        )
    )

    metrics = list(result.fetchall())
    print("Recent fuel_metrics:")
    for row in metrics[:5]:
        print(f"  {row[0]}: est={row[1]}%, sensor={row[2]}%, status={row[3]}")

    # Check for fuel increase
    if len(metrics) >= 2:
        prev = metrics[0]
        curr = metrics[1]
        fuel_change = float(prev[1] or 0) - float(curr[1] or 0)
        print(f"\n📈 Fuel change: {fuel_change:.1f}% (was {curr[1]}% -> {prev[1]}%)")
        if fuel_change < -5:
            print(f"⚠️ LARGE FUEL INCREASE detected: {abs(fuel_change):.1f}% increase")

print("\n✅ Check complete")
