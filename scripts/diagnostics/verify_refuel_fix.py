#!/usr/bin/env python3
"""
verify_refuel_fix.py - Verify refuel immediate save fix is working
🔧 v5.17.1: Monitor refuel detection and verify immediate saves to database
"""
import time
from datetime import datetime, timedelta

import pymysql

# Database config
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "tomas2117",
    "database": "fuel_copilot",
    "charset": "utf8mb4",
    "port": 3306,
}


def check_recent_refuels(minutes=30):
    """Check for refuels detected in fuel_metrics and verify they were saved"""
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cutoff_time = datetime.now() - timedelta(minutes=minutes)

    print(f"\n🔍 Checking refuels in last {minutes} minutes...")
    print(f"   Cutoff: {cutoff_time}")
    print("=" * 80)

    # Find refuel detections in fuel_metrics
    cursor.execute(
        """
        SELECT 
            truck_id,
            timestamp_utc,
            sensor_pct,
            kalman_pct,
            drift_pct,
            refuel_detected,
            refuel_event
        FROM fuel_metrics
        WHERE timestamp_utc >= %s
          AND refuel_detected = 'YES'
        ORDER BY truck_id, timestamp_utc
    """,
        (cutoff_time,),
    )

    detections = cursor.fetchall()

    if not detections:
        print("✅ No refuels detected (nothing to verify)")
        cursor.close()
        conn.close()
        return True

    print(f"\n📊 Found {len(detections)} refuel detection(s) in fuel_metrics:")
    print()

    all_saved = True
    for det in detections:
        truck_id = det["truck_id"]
        ts = det["timestamp_utc"]
        sensor = det["sensor_pct"]
        kalman = det["kalman_pct"]
        drift = det["drift_pct"]

        print(f"🚛 [{truck_id}] @ {ts}")
        print(f"   Sensor: {sensor:.1f}%, Kalman: {kalman:.1f}%, Drift: {drift:.1f}%")

        # Check if it was saved to refuel_events
        cursor.execute(
            """
            SELECT 
                id,
                timestamp_utc,
                fuel_before,
                fuel_after,
                gallons_added,
                refuel_type
            FROM refuel_events
            WHERE truck_id = %s
              AND ABS(TIMESTAMPDIFF(SECOND, timestamp_utc, %s)) <= 120
            ORDER BY ABS(TIMESTAMPDIFF(SECOND, timestamp_utc, %s))
            LIMIT 1
        """,
            (truck_id, ts, ts),
        )

        saved = cursor.fetchone()

        if saved:
            print(f"   ✅ SAVED to refuel_events:")
            print(f"      ID: {saved['id']}")
            print(f"      Time: {saved['timestamp_utc']}")
            print(f"      {saved['fuel_before']:.1f}% → {saved['fuel_after']:.1f}%")
            print(f"      +{saved['gallons_added']:.1f} gal")
            print(f"      Type: {saved['refuel_type']}")
        else:
            print(f"   ❌ NOT SAVED to refuel_events!")
            all_saved = False

        print()

    cursor.close()
    conn.close()

    if all_saved:
        print("=" * 80)
        print("✅ SUCCESS: All detected refuels were saved to database")
        print("=" * 80)
    else:
        print("=" * 80)
        print("❌ FAILURE: Some refuels were detected but NOT saved")
        print("=" * 80)

    return all_saved


def monitor_live(check_interval_seconds=60):
    """Monitor refuel detection in real-time"""
    print("\n🔄 Starting live monitoring...")
    print(f"   Checking every {check_interval_seconds} seconds")
    print("   Press Ctrl+C to stop")
    print()

    try:
        while True:
            check_recent_refuels(minutes=5)
            print(f"\n⏳ Waiting {check_interval_seconds} seconds...\n")
            time.sleep(check_interval_seconds)
    except KeyboardInterrupt:
        print("\n\n👋 Monitoring stopped")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "live":
        monitor_live()
    else:
        # Single check of last 30 minutes
        check_recent_refuels(minutes=30)
        print("\n💡 Run with 'live' argument to monitor continuously:")
        print("   python verify_refuel_fix.py live")
