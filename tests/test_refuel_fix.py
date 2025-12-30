#!/usr/bin/env python
"""
Test refuel detection fix - BUG-006
Verifies that refuels are now properly saved to database
"""

import sys
from datetime import datetime, timezone

import mysql.connector

# Import the function
sys.path.insert(0, "/Users/tomasruiz/Desktop/Fuel-Analytics-Backend")
from wialon_sync_enhanced import save_refuel_event


def test_save_refuel():
    """Test that save_refuel_event properly saves to database"""

    # Connect to local DB
    conn = mysql.connector.connect(
        host="localhost", user="root", password="", database="fuel_copilot_local"
    )

    # Clear any existing test refuels for JC1282 from today
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM refuel_events 
        WHERE truck_id = 'JC1282' 
        AND refuel_time >= CURDATE()
    """
    )
    conn.commit()

    print("🧪 Testing refuel save with fixed column names...")

    # Test refuel 1: Similar to the 103.2 gal refuel from logs
    success1 = save_refuel_event(
        connection=conn,
        truck_id="JC1282",
        timestamp_utc=datetime.now(timezone.utc),
        fuel_before=28.0,
        fuel_after=79.6,
        gallons_added=103.2,
        latitude=None,
        longitude=None,
        refuel_type="DETECTED",
    )

    print(f"✅ Refuel 1 saved: {success1}")

    # Verify it was saved
    cursor.execute(
        """
        SELECT * FROM refuel_events 
        WHERE truck_id = 'JC1282' 
        ORDER BY refuel_time DESC 
        LIMIT 1
    """
    )
    result = cursor.fetchone()

    if result:
        print(f"✅ Found refuel in database:")
        print(f"   ID: {result[0]}")
        print(f"   Truck: {result[1]}")
        print(f"   Time: {result[2]}")
        print(f"   Gallons: {result[3]}")
        print(f"   Before: {result[4]}%")
        print(f"   After: {result[5]}%")
        print(f"   Type: {result[11]}")
    else:
        print("❌ ERROR: Refuel not found in database!")
        return False

    # Test duplicate detection (should fail)
    print("\n🧪 Testing duplicate detection...")
    success2 = save_refuel_event(
        connection=conn,
        truck_id="JC1282",
        timestamp_utc=datetime.now(timezone.utc),
        fuel_before=28.0,
        fuel_after=79.6,
        gallons_added=103.2,  # Same gallons within 2 min window
        latitude=None,
        longitude=None,
        refuel_type="DETECTED",
    )

    print(f"⏭️ Duplicate detection working: {not success2}")

    # Test non-duplicate (different gallons)
    print("\n🧪 Testing non-duplicate (different gallons)...")
    success3 = save_refuel_event(
        connection=conn,
        truck_id="JC1282",
        timestamp_utc=datetime.now(timezone.utc),
        fuel_before=79.6,
        fuel_after=98.0,
        gallons_added=39.7,  # Different gallons - should save
        latitude=None,
        longitude=None,
        refuel_type="DETECTED",
    )

    print(f"✅ Non-duplicate saved: {success3}")

    # Final count
    cursor.execute(
        """
        SELECT COUNT(*) FROM refuel_events 
        WHERE truck_id = 'JC1282' 
        AND refuel_time >= CURDATE()
    """
    )
    count = cursor.fetchone()[0]

    print(f"\n📊 Total refuels saved today for JC1282: {count}")
    print(f"✅ Expected: 2 (first + third)")

    cursor.close()
    conn.close()

    return count == 2


if __name__ == "__main__":
    success = test_save_refuel()
    if success:
        print("\n🎉 ALL TESTS PASSED!")
        sys.exit(0)
    else:
        print("\n❌ TESTS FAILED!")
        sys.exit(1)
