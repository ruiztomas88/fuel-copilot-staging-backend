#!/usr/bin/env python3
"""
🧪 Test Multi-Refuel Detection for PC1280 (Dec 17, 2025)

This script validates the fix for missed refuel events.

Background:
- PC1280 had TWO refuels on Dec 17:
  1. Morning (02:49): 6% → 65% (+58.4 gallons)
  2. Evening (22:25): 44% → 100% (+56.0 gallons)

- Old algorithm detected ONLY the first refuel
- New algorithm should detect BOTH

Test Process:
1. Fetch fuel history from Wialon for PC1280 on Dec 17
2. Run detect_multiple_refuels() function
3. Verify BOTH refuels are detected
4. Show timestamps, gallons, and percentages for each

Expected Output:
✅ Refuel #1: 02:49:51 UTC - 6.0% → 65.2% (+58.4 gal)
✅ Refuel #2: 22:25:55 UTC - 43.6% → 99.6% (+56.0 gal)
"""

import os
import sys
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wialon_reader import WialonReader, WialonConfig, TRUCK_UNIT_MAPPING, TRUCK_CONFIG
from wialon_sync_enhanced import detect_multiple_refuels, StateManager


def test_pc1280_dec17():
    """Test multi-refuel detection for PC1280 on December 17, 2025"""
    print("=" * 80)
    print("🧪 TESTING MULTI-REFUEL DETECTION - PC1280 (Dec 17, 2025)")
    print("=" * 80)

    truck_id = "PC1280"
    truck_config = TRUCK_CONFIG.get(truck_id, {})
    tank_capacity = truck_config.get("capacity_gallons", 200)

    print(f"\n📋 Test Configuration:")
    print(f"   Truck: {truck_id}")
    print(f"   Tank Capacity: {tank_capacity} gallons")
    print(f"   Test Date: December 17, 2025")

    # Initialize Wialon reader
    config = WialonConfig()
    reader = WialonReader(config, TRUCK_UNIT_MAPPING)

    if not reader.ensure_connection():
        print("\n❌ ERROR: Cannot connect to Wialon database")
        return False

    print("\n✅ Connected to Wialon database")

    # Fetch fuel history for Dec 17 (24 hours from midnight UTC)
    # We need to get data specifically for Dec 17, so we'll use a custom query
    # since get_truck_fuel_history uses hours_back from now

    import pymysql

    try:
        unit_id = TRUCK_UNIT_MAPPING.get(truck_id)
        if not unit_id:
            print(f"\n❌ ERROR: Truck {truck_id} not found in mapping")
            return False

        # Dec 17, 2025 in UTC: 00:00 to 23:59
        start_time = datetime(2025, 12, 17, 0, 0, 0, tzinfo=timezone.utc)
        end_time = datetime(2025, 12, 17, 23, 59, 59, tzinfo=timezone.utc)
        start_epoch = int(start_time.timestamp())
        end_epoch = int(end_time.timestamp())

        with reader.connection.cursor() as cursor:
            query = """
                SELECT measure_datetime, value, m as epoch_time
                FROM sensors
                WHERE unit = %s
                  AND p = 'fuel_lvl'
                  AND m >= %s
                  AND m <= %s
                ORDER BY m ASC
            """
            cursor.execute(query, (unit_id, start_epoch, end_epoch))
            results = cursor.fetchall()

            if not results:
                print(f"\n⚠️  WARNING: No fuel data found for {truck_id} on Dec 17")
                return False

            print(f"\n📊 Retrieved {len(results)} fuel readings from Wialon")

            # Convert to fuel_history format
            import pytz

            fuel_history = []
            for row in results:
                dt = row["measure_datetime"]
                if dt.tzinfo is None:
                    dt = pytz.utc.localize(dt)
                elif dt.tzinfo != pytz.utc:
                    dt = dt.astimezone(pytz.utc)

                fuel_history.append(
                    {
                        "timestamp": dt,
                        "fuel_pct": float(row["value"]) if row["value"] else None,
                        "epoch_time": int(row["epoch_time"]),
                    }
                )

            # Show first few and last few readings
            print("\n📝 Sample Readings:")
            print("   First 3:")
            for i, reading in enumerate(fuel_history[:3]):
                ts = reading["timestamp"].strftime("%H:%M:%S")
                pct = reading["fuel_pct"]
                gal = (pct / 100) * tank_capacity if pct else 0
                print(f"   [{i + 1}] {ts} | {pct:5.1f}% | {gal:5.1f} gal")

            print("   ...")
            print("   Last 3:")
            for i, reading in enumerate(fuel_history[-3:]):
                ts = reading["timestamp"].strftime("%H:%M:%S")
                pct = reading["fuel_pct"]
                gal = (pct / 100) * tank_capacity if pct else 0
                idx = len(fuel_history) - 3 + i + 1
                print(f"   [{idx}] {ts} | {pct:5.1f}% | {gal:5.1f} gal")

            # Initialize state manager and estimator
            state_manager = StateManager()
            estimator = state_manager.get_estimator(truck_id)

            # Run multi-refuel detection
            print(f"\n🔍 Running Multi-Refuel Detection...")
            print(f"   Algorithm: detect_multiple_refuels()")
            print(f"   Min Jump: 10% AND 5 gallons")
            print(f"   Time Gap: 5 min to 96 hours")

            refuels = detect_multiple_refuels(
                fuel_history=fuel_history,
                estimator=estimator,
                tank_capacity_gal=tank_capacity,
                truck_id=truck_id,
            )

            # Analyze results
            print(f"\n📊 RESULTS:")
            print(f"   Refuels Detected: {len(refuels)}")

            if len(refuels) == 0:
                print("\n❌ FAILED: No refuels detected")
                print("   Expected: 2 refuels (02:49 and 22:25)")
                return False

            print("\n   Details:")
            for i, refuel in enumerate(refuels, 1):
                ts = refuel["timestamp"].strftime("%Y-%m-%d %H:%M:%S UTC")
                prev_pct = refuel["prev_pct"]
                new_pct = refuel["new_pct"]
                increase_pct = refuel["increase_pct"]
                increase_gal = refuel["increase_gal"]
                gap_min = refuel["time_gap_hours"] * 60

                print(f"\n   Refuel #{i}:")
                print(f"      Time: {ts}")
                print(
                    f"      Before: {prev_pct:.1f}% ({prev_pct/100*tank_capacity:.1f} gal)"
                )
                print(
                    f"      After: {new_pct:.1f}% ({new_pct/100*tank_capacity:.1f} gal)"
                )
                print(f"      Added: +{increase_pct:.1f}% (+{increase_gal:.1f} gal)")
                print(f"      Gap: {gap_min:.1f} minutes")

            # Validation
            print("\n" + "=" * 80)
            print("✅ VALIDATION:")
            print("=" * 80)

            expected_refuels = [
                {"hour": 2, "min_gallons": 50, "description": "Morning refuel (02:49)"},
                {
                    "hour": 22,
                    "min_gallons": 50,
                    "description": "Evening refuel (22:25)",
                },
            ]

            detected_hours = [r["timestamp"].hour for r in refuels]
            detected_gallons = [r["increase_gal"] for r in refuels]

            success = True

            for expected in expected_refuels:
                hour = expected["hour"]
                min_gal = expected["min_gallons"]
                desc = expected["description"]

                # Check if there's a refuel within 2 hours of expected time
                found = False
                for i, r in enumerate(refuels):
                    if (
                        abs(r["timestamp"].hour - hour) <= 2
                        and r["increase_gal"] >= min_gal
                    ):
                        found = True
                        print(f"   ✅ {desc}: DETECTED")
                        print(
                            f"      Refuel #{i + 1}: {r['timestamp'].strftime('%H:%M')} (+{r['increase_gal']:.1f} gal)"
                        )
                        break

                if not found:
                    print(f"   ❌ {desc}: NOT DETECTED")
                    success = False

            print("\n" + "=" * 80)
            if success and len(refuels) == 2:
                print("✅ TEST PASSED: Both refuels detected correctly!")
                print("=" * 80)
                return True
            elif len(refuels) == 1:
                print("❌ TEST FAILED: Only 1 refuel detected (should be 2)")
                print("=" * 80)
                return False
            elif len(refuels) > 2:
                print(f"⚠️  TEST WARNING: {len(refuels)} refuels detected (expected 2)")
                print("   May include false positives - review details above")
                print("=" * 80)
                return True
            else:
                print("❌ TEST FAILED: Missing expected refuels")
                print("=" * 80)
                return False

    except Exception as e:
        print(f"\n❌ ERROR during test: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_pc1280_dec17()
    sys.exit(0 if success else 1)
