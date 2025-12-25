"""
Example 3: Fleet Analytics by Make/Model/Year

Compare performance across different truck types
"""

import os

import pymysql
from dotenv import load_dotenv

from truck_specs_engine import get_truck_specs_engine

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("MYSQL_HOST", "localhost"),
    "user": os.getenv("MYSQL_USER", "root"),
    "password": os.getenv("MYSQL_PASSWORD"),
    "database": os.getenv("MYSQL_DATABASE", "fuel_copilot_local"),
    "port": int(os.getenv("MYSQL_PORT", 3306)),
}


def get_actual_mpg_by_truck(days: int = 7) -> dict:
    """Get actual MPG performance from last N days"""
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    query = """
        SELECT 
            truck_id,
            AVG(mpg_current) as avg_mpg,
            COUNT(*) as readings
        FROM fuel_metrics
        WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s DAY)
            AND mpg_current IS NOT NULL
            AND mpg_current BETWEEN 3.5 AND 9.0
        GROUP BY truck_id
        HAVING readings > 100
    """

    cursor.execute(query, (days,))
    results = cursor.fetchall()

    cursor.close()
    conn.close()

    return {row["truck_id"]: row["avg_mpg"] for row in results}


def analyze_fleet_by_make():
    """Compare expected vs actual MPG by manufacturer"""
    engine = get_truck_specs_engine()
    actual_mpg = get_actual_mpg_by_truck(days=7)

    by_make = {}

    for truck_id, specs in engine._specs_cache.items():
        make = specs.make

        if make not in by_make:
            by_make[make] = {
                "trucks": [],
                "expected_mpg": [],
                "actual_mpg": [],
                "deviations": [],
            }

        by_make[make]["trucks"].append(truck_id)
        by_make[make]["expected_mpg"].append(specs.baseline_mpg_loaded)

        if truck_id in actual_mpg:
            actual = actual_mpg[truck_id]
            by_make[make]["actual_mpg"].append(actual)
            deviation = (
                (actual - specs.baseline_mpg_loaded) / specs.baseline_mpg_loaded
            ) * 100
            by_make[make]["deviations"].append(deviation)

    # Print analysis
    print("📊 Fleet Performance Analysis (Last 7 Days)\n")
    print(
        f"{'Make':<15} {'Trucks':<8} {'Expected':<10} {'Actual':<10} {'Deviation':<12} {'Status'}"
    )
    print("=" * 75)

    for make, data in sorted(by_make.items()):
        if not data["actual_mpg"]:
            continue

        count = len(data["actual_mpg"])
        expected_avg = sum(data["expected_mpg"]) / len(data["expected_mpg"])
        actual_avg = sum(data["actual_mpg"]) / count
        deviation_avg = sum(data["deviations"]) / count

        if deviation_avg >= 0:
            status = "✅ EXCEEDS"
        elif deviation_avg >= -10:
            status = "✓ GOOD"
        elif deviation_avg >= -20:
            status = "⚠️ WARNING"
        else:
            status = "🚨 CRITICAL"

        print(
            f"{make:<15} {count:<8} {expected_avg:<10.2f} {actual_avg:<10.2f} {deviation_avg:+11.1f}% {status}"
        )


def find_underperformers(min_deviation_pct: float = -15.0):
    """Find specific trucks underperforming their baseline"""
    engine = get_truck_specs_engine()
    actual_mpg = get_actual_mpg_by_truck(days=7)

    underperformers = []

    for truck_id, actual in actual_mpg.items():
        specs = engine.get_specs(truck_id)
        if specs:
            expected = specs.baseline_mpg_loaded
            deviation = ((actual - expected) / expected) * 100

            if deviation < min_deviation_pct:
                underperformers.append(
                    {
                        "truck_id": truck_id,
                        "make": specs.make,
                        "model": specs.model,
                        "year": specs.year,
                        "expected": expected,
                        "actual": actual,
                        "deviation": deviation,
                    }
                )

    # Sort by worst deviation
    underperformers.sort(key=lambda x: x["deviation"])

    print(f"\n\n🔍 Trucks performing >{abs(min_deviation_pct)}% below baseline:\n")
    print(
        f"{'Truck':<10} {'Make/Model':<30} {'Year':<6} {'Expected':<10} {'Actual':<10} {'Gap'}"
    )
    print("=" * 85)

    for truck in underperformers:
        print(
            f"{truck['truck_id']:<10} {truck['make']} {truck['model']:<20} {truck['year']:<6} "
            f"{truck['expected']:<10.2f} {truck['actual']:<10.2f} {truck['deviation']:+.1f}%"
        )


if __name__ == "__main__":
    analyze_fleet_by_make()
    find_underperformers(min_deviation_pct=-15.0)
