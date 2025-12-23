#!/usr/bin/env python3
"""
COMPREHENSIVE SENSOR ANALYSIS FOR MPG CALCULATION
Analyze all available sensors from Wialon to determine best MPG calculation strategy
"""
import os
from collections import defaultdict
from datetime import datetime, timedelta

import pymysql


def analyze_sensors():
    """Analyze sensor coverage and quality for MPG calculation"""

    conn = pymysql.connect(
        host="20.127.200.135",
        port=3306,
        user="tomas",
        password=os.getenv("WIALON_MYSQL_PASSWORD"),
        database="wialon_collect",
        cursorclass=pymysql.cursors.DictCursor,
    )

    try:
        with conn.cursor() as cursor:
            # Get list of all trucks
            cursor.execute("SELECT DISTINCT unit FROM sensors ORDER BY unit")
            trucks = [row["unit"] for row in cursor.fetchall()]

            print("=" * 100)
            print("🔍 COMPREHENSIVE SENSOR ANALYSIS FOR MPG CALCULATION")
            print("=" * 100)
            print(f"\n📊 Total trucks in Wialon: {len(trucks)}")
            print(
                f"🎯 Target MPG range for loaded Class 8 trucks (44k lbs): 4.0 - 8.0 MPG"
            )
            print(f"⚙️  Required sensors for accurate MPG:")
            print(f"   1. Distance: odometer (odom) - CRITICAL")
            print(
                f"   2. Fuel consumed: total_fuel_used OR fuel_rate integration - CRITICAL"
            )
            print(f"   3. Fuel level: fuel_lvl (for refuel detection) - IMPORTANT")
            print(f"   4. Weight: Not available (assume loaded ~44k lbs)")

            # Analyze key sensors for MPG
            mpg_sensors = {
                "odom": "Odometer - Distance traveled",
                "total_fuel_used": "ECU Total Fuel Used - Most accurate",
                "fuel_rate": "Fuel consumption rate (gal/h)",
                "fuel_lvl": "Tank fuel level % - For refuel detection",
                "engine_hours": "Engine runtime hours",
                "speed": "Vehicle speed",
                "rpm": "Engine RPM",
            }

            sensor_coverage = {}
            sensor_sample_data = {}

            for sensor_name, description in mpg_sensors.items():
                print(f"\n{'=' * 100}")
                print(f"📡 SENSOR: {sensor_name} - {description}")
                print(f"{'=' * 100}")

                # Check how many trucks have this sensor with recent data
                cursor.execute(
                    """
                    SELECT unit, p, m
                    FROM sensors
                    WHERE p = %s
                    AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 7 DAY)
                    ORDER BY m DESC
                    LIMIT 10
                """,
                    (sensor_name,),
                )

                recent_data = cursor.fetchall()

                # Get total count
                cursor.execute(
                    """
                    SELECT COUNT(DISTINCT unit) as truck_count
                    FROM sensors
                    WHERE p = %s
                    AND m > UNIX_TIMESTAMP(NOW() - INTERVAL 7 DAY)
                """,
                    (sensor_name,),
                )

                count_result = cursor.fetchone()
                truck_count = count_result["truck_count"] if count_result else 0
                coverage_pct = (truck_count / len(trucks) * 100) if trucks else 0

                sensor_coverage[sensor_name] = {
                    "truck_count": truck_count,
                    "coverage_pct": coverage_pct,
                    "sample_data": recent_data[:5],
                }

                print(
                    f"   ✅ Coverage: {truck_count}/{len(trucks)} trucks ({coverage_pct:.1f}%)"
                )

                if recent_data:
                    print(f"   📋 Sample data (last 5 readings):")
                    for row in recent_data[:5]:
                        timestamp = datetime.fromtimestamp(row["m"])
                        print(
                            f"      {row['unit']}: {row['p']} = (timestamp: {timestamp})"
                        )
                else:
                    print(f"   ⚠️  NO RECENT DATA (last 7 days)")

            # Analyze data quality for specific trucks
            print(f"\n\n{'=' * 100}")
            print("🎯 DETAILED ANALYSIS: RH1522 (showed 10.3 MPG)")
            print(f"{'=' * 100}")

            test_truck = "RH1522"
            cursor.execute(
                """
                SELECT p, COUNT(*) as reading_count,
                       FROM_UNIXTIME(MIN(t)) as first_reading,
                       FROM_UNIXTIME(MAX(t)) as last_reading
                FROM params
                WHERE nm = %s
                AND t > UNIX_TIMESTAMP(NOW() - INTERVAL 3 DAY)
                GROUP BY p
                ORDER BY reading_count DESC
            """,
                (test_truck,),
            )

            truck_sensors = cursor.fetchall()
            print(f"\n📊 Sensors available for {test_truck} (last 3 days):")
            for sensor in truck_sensors:
                print(f"   {sensor['p']}: {sensor['reading_count']} readings")
                print(
                    f"      First: {sensor['first_reading']}, Last: {sensor['last_reading']}"
                )

            # Calculate theoretical MPG using available data
            print(f"\n\n{'=' * 100}")
            print("🧮 MPG CALCULATION FEASIBILITY ANALYSIS")
            print(f"{'=' * 100}")

            methods = []

            # Method 1: odom + total_fuel_used (ECU)
            odom_coverage = sensor_coverage.get("odom", {}).get("coverage_pct", 0)
            fuel_ecu_coverage = sensor_coverage.get("total_fuel_used", {}).get(
                "coverage_pct", 0
            )

            if odom_coverage > 0 and fuel_ecu_coverage > 0:
                overlap = min(odom_coverage, fuel_ecu_coverage)
                methods.append(
                    {
                        "name": "Method 1: Odometer Delta + ECU Fuel Delta",
                        "accuracy": "⭐⭐⭐⭐⭐ HIGHEST",
                        "coverage": f"{overlap:.1f}%",
                        "description": "Most accurate - both from ECU",
                        "formula": "MPG = Δodometer_miles / Δtotal_fuel_gal",
                        "pros": [
                            "Direct ECU readings",
                            "No fuel level sensor errors",
                            "Cumulative counters",
                        ],
                        "cons": ["Lower coverage", "Requires ECU support"],
                    }
                )

            # Method 2: odom + fuel_rate integration
            fuel_rate_coverage = sensor_coverage.get("fuel_rate", {}).get(
                "coverage_pct", 0
            )
            if odom_coverage > 0 and fuel_rate_coverage > 0:
                overlap = min(odom_coverage, fuel_rate_coverage)
                methods.append(
                    {
                        "name": "Method 2: Odometer Delta + Fuel Rate Integration",
                        "accuracy": "⭐⭐⭐⭐ HIGH",
                        "coverage": f"{overlap:.1f}%",
                        "description": "Integrate gal/h over time",
                        "formula": "MPG = Δodometer_miles / Σ(fuel_rate_gph × Δtime_h)",
                        "pros": ["High coverage", "Real-time consumption"],
                        "cons": [
                            "Requires time integration",
                            "Sampling errors possible",
                        ],
                    }
                )

            # Method 3: odom + fuel_lvl tank sensor
            fuel_lvl_coverage = sensor_coverage.get("fuel_lvl", {}).get(
                "coverage_pct", 0
            )
            if odom_coverage > 0 and fuel_lvl_coverage > 0:
                overlap = min(odom_coverage, fuel_lvl_coverage)
                methods.append(
                    {
                        "name": "Method 3: Odometer Delta + Tank Level Delta",
                        "accuracy": "⭐⭐⭐ MEDIUM",
                        "coverage": f"{overlap:.1f}%",
                        "description": "Calculate from % tank changes",
                        "formula": "MPG = Δodometer_miles / (Δfuel_lvl% × tank_capacity_gal)",
                        "pros": ["Available on most trucks", "Simple calculation"],
                        "cons": [
                            "Tank sloshing errors",
                            "Sensor calibration issues",
                            "Refuel detection needed",
                        ],
                    }
                )

            print("\n📋 AVAILABLE MPG CALCULATION METHODS:")
            print("=" * 100)
            for i, method in enumerate(methods, 1):
                print(f"\n{i}. {method['name']}")
                print(f"   Accuracy: {method['accuracy']}")
                print(f"   Coverage: {method['coverage']} of fleet")
                print(f"   Formula:  {method['formula']}")
                print(f"   Description: {method['description']}")
                print(f"   ✅ Pros:")
                for pro in method["pros"]:
                    print(f"      • {pro}")
                print(f"   ⚠️  Cons:")
                for con in method["cons"]:
                    print(f"      • {con}")

            # Recommendations
            print(f"\n\n{'=' * 100}")
            print("💡 RECOMMENDATIONS FOR MPG CALCULATION")
            print(f"{'=' * 100}")

            print("\n🎯 HYBRID APPROACH (Recommended):")
            print(
                """
   1. PRIMARY: Method 1 (odom + total_fuel_used)
      - Use for trucks with ECU fuel counter
      - Highest accuracy, no refuel detection needed
      - Currently covers ~{:.1f}% of fleet
      
   2. SECONDARY: Method 2 (odom + fuel_rate integration)
      - Fallback for trucks without total_fuel_used
      - Integrate fuel_rate over time: Σ(gph × hours)
      - Covers ~{:.1f}% of fleet
      
   3. TERTIARY: Method 3 (odom + fuel_lvl)
      - Last resort for remaining trucks
      - Requires refuel detection and tank capacity
      - Must filter out refueling events
      - Most error-prone
      
   4. VALIDATION LAYER:
      - Physics check: 4.0 <= MPG <= 8.0 for loaded trucks
      - Delta limits: max 500 mi/day, max 100 gal/day
      - Outlier rejection: IQR method on rolling window
      - Refuel detection: fuel_lvl jumps > 15% in < 30 min
      
   5. DATA QUALITY:
      - Minimum window: 5 miles + 0.75 gallons
      - EMA smoothing: α=0.4 for noise reduction
      - Reset on refuel or extended idle (>24h)
      
   6. WEIGHT CONSIDERATION:
      - No weight sensor available
      - Assume loaded: 44,000 lbs (worst case MPG)
      - Could add manual truck type field (flatbed/reefer/dry van)
            """.format(
                    (
                        min(odom_coverage, fuel_ecu_coverage)
                        if odom_coverage and fuel_ecu_coverage
                        else 0
                    ),
                    (
                        min(odom_coverage, fuel_rate_coverage)
                        if odom_coverage and fuel_rate_coverage
                        else 0
                    ),
                )
            )

    finally:
        conn.close()


if __name__ == "__main__":
    analyze_sensors()
