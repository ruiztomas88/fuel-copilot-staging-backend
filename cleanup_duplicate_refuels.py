#!/usr/bin/env python3
"""
Cleanup Duplicate Refuel Events
v3.12.30 - Run this ONCE on the VM to remove duplicate refuel records

Duplicates are identified by:
- Same truck_id
- Same timestamp_utc (within 1 minute)
- Same fuel_after (within 2%)

Keeps the first record (lowest id), deletes the rest.
"""

import os
import pymysql
from dotenv import load_dotenv
from datetime import timedelta

load_dotenv()


def get_connection():
    return pymysql.connect(
        host=os.getenv("LOCAL_DB_HOST", "localhost"),
        port=int(os.getenv("LOCAL_DB_PORT", 3306)),
        user=os.getenv("LOCAL_DB_USER", "fuel_admin"),
        password=os.getenv("LOCAL_DB_PASS", ""),
        database=os.getenv("LOCAL_DB_NAME", "fuel_copilot"),
        cursorclass=pymysql.cursors.DictCursor,
    )


def find_duplicates(cursor):
    """Find duplicate refuel events"""
    # Get all refuels ordered by truck, time, id
    query = """
        SELECT id, truck_id, timestamp_utc, gallons_added, fuel_before, fuel_after
        FROM refuel_events
        ORDER BY truck_id, timestamp_utc, id
    """
    cursor.execute(query)
    all_refuels = cursor.fetchall()

    duplicates_to_delete = []
    seen = {}  # Key: (truck_id, timestamp_rounded, fuel_after_rounded)

    for refuel in all_refuels:
        truck_id = refuel["truck_id"]
        ts = refuel["timestamp_utc"]
        fuel_after = refuel["fuel_after"] or 0

        # Round timestamp to nearest minute
        ts_rounded = ts.replace(second=0, microsecond=0)

        # Round fuel_after to nearest 2%
        fuel_after_rounded = round(fuel_after / 2) * 2

        key = (truck_id, ts_rounded, fuel_after_rounded)

        if key in seen:
            # This is a duplicate - mark for deletion
            duplicates_to_delete.append(
                {
                    "id": refuel["id"],
                    "truck_id": truck_id,
                    "timestamp": ts,
                    "gallons": refuel["gallons_added"],
                    "fuel_after": fuel_after,
                    "original_id": seen[key]["id"],
                    "original_gallons": seen[key]["gallons"],
                }
            )
        else:
            # First occurrence - keep it
            seen[key] = {
                "id": refuel["id"],
                "gallons": refuel["gallons_added"],
            }

    return duplicates_to_delete


def main():
    print("=" * 60)
    print("🔍 Scanning for duplicate refuel events...")
    print("=" * 60)

    conn = get_connection()

    try:
        with conn.cursor() as cursor:
            duplicates = find_duplicates(cursor)

            if not duplicates:
                print("✅ No duplicates found!")
                return

            print(f"\n⚠️  Found {len(duplicates)} duplicate refuel(s):\n")

            for dup in duplicates:
                print(f"  🗑️  ID {dup['id']}: {dup['truck_id']} @ {dup['timestamp']}")
                print(f"      +{dup['gallons']:.1f} gal → {dup['fuel_after']:.1f}%")
                print(
                    f"      (duplicate of ID {dup['original_id']}: +{dup['original_gallons']:.1f} gal)"
                )
                print()

            # Confirm deletion
            response = (
                input(f"Delete these {len(duplicates)} duplicate(s)? [y/N]: ")
                .strip()
                .lower()
            )

            if response == "y":
                ids_to_delete = [dup["id"] for dup in duplicates]
                placeholders = ", ".join(["%s"] * len(ids_to_delete))
                delete_query = f"DELETE FROM refuel_events WHERE id IN ({placeholders})"
                cursor.execute(delete_query, ids_to_delete)
                conn.commit()
                print(f"\n✅ Deleted {len(duplicates)} duplicate refuel event(s)")
            else:
                print("\n❌ Cancelled - no changes made")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
