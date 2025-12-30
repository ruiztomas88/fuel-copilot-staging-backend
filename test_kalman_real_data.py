"""
🧪 Kalman Filter v6.1.0 - Real Data End-to-End Test

Tests estimator.py with actual database data from truck_sensors_cache table.

Usage:
    python test_kalman_real_data.py --truck CO0681 --days 7
    python test_kalman_real_data.py --truck CO0681 --date 2025-12-20

Author: Fuel Copilot Team
Date: December 29, 2025
"""

import argparse
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import mysql.connector
import numpy as np

from config import get_local_db_config
from estimator import COMMON_CONFIG, FuelEstimator

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def get_real_sensor_data(
    truck_id: str, start_date: datetime, end_date: datetime
) -> List[Dict]:
    """Fetch real sensor data from truck_sensors_cache table"""
    db_config = get_local_db_config()

    connection = mysql.connector.connect(
        host=db_config["host"],
        user=db_config["user"],
        password=db_config["password"],
        database=db_config["database"],
        charset="utf8mb4",
    )

    cursor = connection.cursor()

    query = """
        SELECT 
            truck_id,
            last_updated,
            sensor_data
        FROM truck_sensors_cache
        WHERE truck_id = %s
        AND last_updated BETWEEN %s AND %s
        ORDER BY last_updated ASC
    """

    cursor.execute(query, (truck_id, start_date, end_date))
    rows = cursor.fetchall()

    cursor.close()
    connection.close()

    # Parse sensor_data JSON
    samples = []
    for truck_id_db, last_updated, sensor_data_json in rows:
        try:
            sensor_data = (
                json.loads(sensor_data_json)
                if isinstance(sensor_data_json, str)
                else sensor_data_json
            )

            # Extract fuel level from sensor_data
            fuel_level_pct = None
            if isinstance(sensor_data, dict):
                # Try common keys
                for key in [
                    "fuel_lvl",
                    "fuel_level_pct",
                    "fuel_lvl_pct",
                    "fuellvlpct",
                    "fuel_pct",
                ]:
                    if key in sensor_data and sensor_data[key] is not None:
                        fuel_level_pct = float(sensor_data[key])
                        break

            if fuel_level_pct is not None:
                samples.append(
                    {
                        "truck_id": truck_id_db,
                        "timestamp": last_updated,
                        "fuel_level_pct": fuel_level_pct,
                        "sensor_data": sensor_data,
                    }
                )
        except Exception as e:
            logger.warning(f"Error parsing sensor_data: {e}")
            continue

    logger.info(f"✅ Fetched {len(samples)} samples with fuel level data")
    return samples


def test_with_real_data(truck_id: str, samples: List[Dict]):
    """
    Test Kalman filter with real sensor data.

    Since we don't have ground truth, we'll measure:
    1. Kalman smoothness vs sensor noise
    2. Bias detection frequency
    3. Error consistency (innovations should be random)
    """
    if not samples:
        logger.info("⚠️  No samples to process")
        return

    # Initialize Kalman filter
    config = COMMON_CONFIG.copy()
    config["biodiesel_blend_pct"] = 0.0  # Can be changed for testing

    # Assume typical truck capacity (adjust if you know actual capacity)
    capacity_liters = 400.0

    estimator = FuelEstimator(
        truck_id=truck_id, capacity_liters=capacity_liters, config=config
    )

    # Track results
    sensor_readings = []
    kalman_estimates = []
    innovations = []
    bias_detections = 0
    bias_detected_at = []

    # Process samples
    for i, sample in enumerate(samples):
        fuel_pct = sample["fuel_level_pct"]
        timestamp = sample["timestamp"]

        # Update Kalman
        estimator.update(fuel_pct)
        estimate = estimator.get_estimate()

        sensor_readings.append(fuel_pct)
        kalman_estimates.append(estimate["level_pct"])

        if estimate.get("bias_detected", False):
            bias_detections += 1
            bias_detected_at.append(
                {
                    "index": i,
                    "timestamp": timestamp,
                    "magnitude_pct": estimate.get("bias_magnitude_pct", 0.0),
                }
            )

        # Calculate innovation (sensor - kalman)
        if i > 0:
            innovation = fuel_pct - kalman_estimates[i - 1]
            innovations.append(innovation)

    # Analysis
    sensor_readings = np.array(sensor_readings)
    kalman_estimates = np.array(kalman_estimates)
    innovations = np.array(innovations)

    # Metrics
    sensor_std = np.std(sensor_readings)
    kalman_std = np.std(kalman_estimates)
    innovation_mean = np.mean(innovations)
    innovation_std = np.std(innovations)

    # Smoothness ratio (Kalman should be smoother than sensor)
    smoothness_improvement = (sensor_std - kalman_std) / sensor_std * 100

    print("\n" + "=" * 80)
    print(f"📊 REAL DATA ANALYSIS: {truck_id}")
    print("=" * 80)
    print(f"Samples processed: {len(samples)}")
    print(f"Time range: {samples[0]['timestamp']} → {samples[-1]['timestamp']}")
    print()
    print("📈 SENSOR vs KALMAN:")
    print(f"  Sensor std dev: {sensor_std:.2f}%")
    print(f"  Kalman std dev: {kalman_std:.2f}%")
    print(f"  Smoothness improvement: {smoothness_improvement:.1f}%")
    print()
    print("🔍 INNOVATIONS (sensor - kalman):")
    print(f"  Mean: {innovation_mean:.2f}% (should be ~0 if unbiased)")
    print(f"  Std dev: {innovation_std:.2f}%")
    print(f"  Max positive: {np.max(innovations):.2f}%")
    print(f"  Max negative: {np.min(innovations):.2f}%")
    print()
    print(f"🔴 BIAS DETECTIONS:")
    print(
        f"  Total detections: {bias_detections}/{len(samples)} ({bias_detections/len(samples)*100:.1f}%)"
    )

    if bias_detected_at:
        print(f"\n  Top 5 bias events:")
        sorted_bias = sorted(
            bias_detected_at, key=lambda x: abs(x["magnitude_pct"]), reverse=True
        )[:5]
        for event in sorted_bias:
            print(
                f"    - Sample {event['index']} ({event['timestamp']}): {event['magnitude_pct']:.2f}%"
            )

    # Quality checks
    print("\n" + "=" * 80)
    print("✅ QUALITY CHECKS:")
    print("=" * 80)

    checks_passed = 0
    checks_total = 0

    # Check 1: Kalman smoother than sensor
    checks_total += 1
    if smoothness_improvement > 0:
        print(
            f"  ✅ Kalman smoother than sensor ({smoothness_improvement:.1f}% improvement)"
        )
        checks_passed += 1
    else:
        print(f"  ❌ Kalman NOT smoother (improvement: {smoothness_improvement:.1f}%)")

    # Check 2: Innovations unbiased
    checks_total += 1
    if abs(innovation_mean) < 1.0:
        print(f"  ✅ Innovations unbiased (mean={innovation_mean:.2f}%)")
        checks_passed += 1
    else:
        print(f"  ❌ Innovations biased (mean={innovation_mean:.2f}%)")

    # Check 3: Bias detection rate reasonable
    checks_total += 1
    bias_rate = bias_detections / len(samples) * 100
    if bias_rate < 20:
        print(f"  ✅ Bias detection rate reasonable ({bias_rate:.1f}%)")
        checks_passed += 1
    else:
        print(
            f"  ⚠️  High bias detection rate ({bias_rate:.1f}% - check sensor quality)"
        )

    # Check 4: Innovation std reasonable
    checks_total += 1
    if innovation_std < 5.0:
        print(f"  ✅ Innovation std reasonable ({innovation_std:.2f}%)")
        checks_passed += 1
    else:
        print(f"  ⚠️  High innovation std ({innovation_std:.2f}% - noisy sensor)")

    print("\n" + "=" * 80)
    print(f"📋 FINAL SCORE: {checks_passed}/{checks_total} checks passed")
    print("=" * 80)

    if checks_passed == checks_total:
        print("\n🎉 ALL CHECKS PASSED - Kalman filter v6.1.0 working correctly!")
        return True
    else:
        print(
            f"\n⚠️  {checks_total - checks_passed} checks failed - review results above"
        )
        return False


def main():
    parser = argparse.ArgumentParser(description="Test Kalman v6.1.0 with real data")
    parser.add_argument("--truck", type=str, default="CO0681", help="Truck ID")
    parser.add_argument("--days", type=int, default=7, help="Days of historical data")
    parser.add_argument(
        "--date", type=str, help="Specific date (YYYY-MM-DD) instead of days"
    )

    args = parser.parse_args()

    # Determine date range
    if args.date:
        target_date = datetime.strptime(args.date, "%Y-%m-%d")
        start_date = target_date
        end_date = target_date + timedelta(days=1)
    else:
        end_date = datetime.now()
        start_date = end_date - timedelta(days=args.days)

    print("\n" + "=" * 80)
    print("🧪 KALMAN FILTER v6.1.0 - REAL DATA TEST")
    print("=" * 80)
    print(f"Truck: {args.truck}")
    print(
        f"Date range: {start_date.strftime('%Y-%m-%d')} → {end_date.strftime('%Y-%m-%d')}"
    )
    print("=" * 80)

    # Fetch data
    samples = get_real_sensor_data(args.truck, start_date, end_date)

    # Test
    if samples:
        success = test_with_real_data(args.truck, samples)
        exit(0 if success else 1)
    else:
        logger.error("❌ No data found for testing")
        exit(1)


if __name__ == "__main__":
    main()
