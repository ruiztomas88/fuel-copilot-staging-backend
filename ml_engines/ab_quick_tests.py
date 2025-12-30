"""
🧪 A/B QUICK TESTS
==================

Tests rápidos de A/B sin dependencias de base de datos.
Usa datos simulados para validar que los algoritmos funcionan correctamente.
"""

import logging
from datetime import datetime, timedelta

from ab_testing_framework import ABTestingEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_quick_tests():
    """Tests rápidos con datos simulados"""

    logger.info("\n" + "=" * 80)
    logger.info("🧪 A/B QUICK TESTS - Simulated Data")
    logger.info("=" * 80 + "\n")

    engine = ABTestingEngine()

    # ========================================================================
    # TEST 1: MPG ADAPTATIVO
    # ========================================================================

    logger.info("1️⃣ Testing MPG Adaptativo...")

    # Test highway driving
    highway_result = engine.test_mpg_comparison(
        truck_id="TEST_HW001",
        distance_miles=100,
        fuel_consumed_gal=15.0,
        avg_speed_mph=65,
        stop_count=2,
        test_name="Highway Driving",
    )

    logger.info(
        f"   Highway: {highway_result.current_mpg:.2f} → {highway_result.new_mpg:.2f} ({highway_result.new_condition})"
    )
    assert highway_result.new_condition == "highway", "Should detect highway"

    # Test city driving
    city_result = engine.test_mpg_comparison(
        truck_id="TEST_CITY001",
        distance_miles=20,
        fuel_consumed_gal=5.0,
        avg_speed_mph=20,
        stop_count=25,
        test_name="City Driving",
    )

    logger.info(
        f"   City: {city_result.current_mpg:.2f} → {city_result.new_mpg:.2f} ({city_result.new_condition})"
    )
    assert city_result.new_condition == "city", "Should detect city"

    # Test mixed driving
    mixed_result = engine.test_mpg_comparison(
        truck_id="TEST_MIX001",
        distance_miles=50,
        fuel_consumed_gal=10.0,
        avg_speed_mph=40,
        stop_count=10,
        test_name="Mixed Driving",
    )

    logger.info(
        f"   Mixed: {mixed_result.current_mpg:.2f} → {mixed_result.new_mpg:.2f} ({mixed_result.new_condition})"
    )

    # ========================================================================
    # TEST 2: KALMAN FILTER
    # ========================================================================

    logger.info("\n2️⃣ Testing Extended Kalman Filter...")

    # Simular consumo gradual con sensor bias
    kalman_readings = []
    true_fuel = 80.0  # Start at 80%
    sensor_bias = -2.0  # Sensor lee 2% menos

    for i in range(20):
        true_fuel -= 0.5  # Consume 0.5% cada reading
        sensor_reading = true_fuel + sensor_bias
        kalman_readings.append((sensor_reading, 5.0))  # 5 GPH consumption

    kalman_result = engine.test_kalman_comparison(
        truck_id="TEST_KF001",
        capacity_liters=500,
        initial_fuel_pct=80.0,
        readings=kalman_readings,
        test_name="Fuel Consumption with Sensor Bias",
    )

    logger.info(
        f"   Linear: {kalman_result.linear_fuel_pct:.1f}%, "
        f"EKF: {kalman_result.ekf_fuel_pct:.1f}%, "
        f"Variance Improvement: {kalman_result.variance_improvement_pct:+.1f}%"
    )
    logger.info(
        f"   Bias Detected: {kalman_result.bias_detected} (sensor_bias: {kalman_result.ekf_sensor_bias:.2f}%)"
    )

    # ========================================================================
    # TEST 3: THEFT DETECTION
    # ========================================================================

    logger.info("\n3️⃣ Testing Enhanced Theft Detection...")

    # Scenario 1: Clear theft (20% drop while parked at night)
    theft_readings_clear = [
        {
            "sensor_fuel_pct": 80.0,
            "speed_mph": 0,
            "truck_status": "STOPPED",
            "timestamp": datetime.now() - timedelta(minutes=10),
            "odometer_mi": 50000,
            "latitude": 39.7392,
            "longitude": -104.9903,
        },
        {
            "sensor_fuel_pct": 60.0,  # 20% drop
            "speed_mph": 0,
            "truck_status": "STOPPED",
            "timestamp": datetime.now(),
            "odometer_mi": 50000,
            "latitude": 39.7392,
            "longitude": -104.9903,
        },
    ]

    theft_result = engine.test_theft_detection_comparison(
        truck_id="TEST_THEFT001",
        readings=theft_readings_clear,
        test_name="Clear Theft Scenario",
    )

    if theft_result:
        logger.info(
            f"   Drop: {theft_result.drop_magnitude_pct:.1f}%, "
            f"Current Detected: {theft_result.current_detected}, "
            f"New Detected: {theft_result.new_detected} (confidence: {theft_result.new_confidence_score:.2f})"
        )
        assert theft_result.new_detected, "Should detect clear theft"

    # Scenario 2: Normal consumption (gradual decrease while moving)
    normal_readings = [
        {
            "sensor_fuel_pct": 80.0 - i * 0.5,
            "speed_mph": 60,
            "truck_status": "MOVING",
            "timestamp": datetime.now() - timedelta(minutes=60 - i * 3),
            "odometer_mi": 50000 + i * 5,
            "latitude": 39.7392 + i * 0.01,
            "longitude": -104.9903,
        }
        for i in range(20)
    ]

    normal_result = engine.test_theft_detection_comparison(
        truck_id="TEST_NORMAL001",
        readings=normal_readings,
        test_name="Normal Consumption",
    )

    if normal_result:
        logger.info(
            f"   Normal: Drop={normal_result.drop_magnitude_pct:.1f}%, "
            f"Detected: {normal_result.new_detected}"
        )

    # ========================================================================
    # SUMMARY
    # ========================================================================

    logger.info("\n" + "=" * 80)
    engine.print_summary()

    # Validate results
    passed = 0
    total = 5

    if highway_result.new_condition == "highway":
        passed += 1
    if city_result.new_condition == "city":
        passed += 1
    if kalman_result.bias_detected:
        passed += 1
    if theft_result and theft_result.new_detected:
        passed += 1
    if normal_result and not normal_result.new_detected:
        passed += 1

    logger.info(f"\n✅ Quick Tests: {passed}/{total} passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    import sys

    exit_code = run_quick_tests()

    if exit_code == 0:
        print("\n🎉 ALL QUICK TESTS PASSED!")
    else:
        print("\n⚠️  SOME TESTS FAILED")

    sys.exit(exit_code)
