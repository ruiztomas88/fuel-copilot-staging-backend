"""
Check trucks added today that have no fuel_lvl data in the last 8 hours
These are likely J1708 trucks that don't report fuel sensor data
"""

import pymysql
from datetime import datetime, timedelta
import sys


def check_trucks():
    try:
        # Connect to wialon_collect (use database_pool config)
        conn = pymysql.connect(
            host="20.127.200.135",
            user="tomas",
            password="Tomas2025",
            database="wialon_collect",
            cursorclass=pymysql.cursors.DictCursor,
        )

        print("=" * 60)
        print("CHECKING TRUCKS WITHOUT fuel_lvl DATA (Last 8 hours)")
        print("=" * 60)

        # Get all trucks from units_map
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT beyondId, unit, fuel_capacity 
                FROM units_map 
                ORDER BY beyondId
            """
            )
            all_trucks = cursor.fetchall()

        print(f"\nTotal trucks in database: {len(all_trucks)}")

        # Check fuel_lvl sensor data for each truck in last 8 hours
        trucks_no_data = []
        trucks_with_data = []
        cutoff_time = datetime.now() - timedelta(hours=8)

        print(
            f"Checking for fuel_lvl sensor since: {cutoff_time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )

        for truck in all_trucks:
            truck_id = truck["beyondId"]
            unit = truck["unit"]

            with conn.cursor() as cursor:
                # Check if truck has fuel_lvl sensor readings
                query = """
                    SELECT COUNT(*) as count 
                    FROM sensors 
                    WHERE unit = %s 
                    AND p = 'fuel_lvl'
                    AND value IS NOT NULL 
                    AND value > 0
                    AND to_datetime >= %s
                """
                cursor.execute(query, (unit, cutoff_time))
                result = cursor.fetchone()

                if result["count"] == 0:
                    trucks_no_data.append(truck_id)
                else:
                    trucks_with_data.append(truck_id)

        conn.close()

        # Results
        print(f"✅ Trucks WITH fuel_lvl data: {len(trucks_with_data)}")
        for truck in sorted(trucks_with_data):
            print(f"   - {truck}")

        print(f"\n❌ Trucks WITHOUT fuel_lvl data ({len(trucks_no_data)}):")
        print("   (These are candidates for removal - likely J1708 buses)")
        for truck in sorted(trucks_no_data):
            print(f"   - {truck}")

        # Generate removal SQL
        if trucks_no_data:
            print(f"\n{'=' * 60}")
            print("SQL TO REMOVE TRUCKS WITHOUT fuel_lvl:")
            print("=" * 60)
            print("\n-- Add to tanks.yaml exclusion list:")
            for truck in sorted(trucks_no_data):
                print(f"  # {truck}  # No fuel_lvl - J1708 bus")

            print("\n-- Or delete from Wialon API units list")
            print("-- These trucks should be excluded from fuel monitoring")

        return trucks_no_data

    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        import traceback

        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    trucks_to_remove = check_trucks()

    if trucks_to_remove:
        print(f"\n⚠️  Found {len(trucks_to_remove)} trucks without fuel data")
        print("   These should be removed from monitoring")
    else:
        print("\n✅ All trucks have fuel_lvl data - no action needed")
