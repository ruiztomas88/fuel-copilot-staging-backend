"""
🧪 Test RPM vs ECU Cross-Validation (v6.2.1)

Verifica que el Kalman NO consume combustible cuando rpm=0,
incluso si el ECU reporta consumo erróneo.

Usage:
    python3 test_rpm_ecu_validation.py
"""

import logging

from estimator import FuelEstimator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_rpm_ecu_crossvalidation():
    """Test RPM vs ECU cross-validation"""
    print("\n" + "=" * 70)
    print("🧪 TESTING RPM vs ECU CROSS-VALIDATION v6.2.1")
    print("=" * 70)

    # Create estimator
    estimator = FuelEstimator(
        truck_id="TEST_RPM",
        capacity_liters=454,
        config={"Q_r": 0.05, "Q_L_moving": 2.5},
    )

    # Initialize with 50% fuel
    estimator.initialize(sensor_pct=50.0)
    print(f"\n📊 Initial state: {estimator.level_pct:.1f}% fuel\n")

    # Test scenarios
    scenarios = [
        {
            "name": "Engine OFF, ECU=None (expected: 0 consumption)",
            "rpm": 0,
            "consumption_lph": None,
            "dt_hours": 0.25,
            "expected_consumption": 0.0,
        },
        {
            "name": "Engine OFF, ECU=5.0 LPH (FAULTY - expected: 0 consumption)",
            "rpm": 0,
            "consumption_lph": 5.0,
            "dt_hours": 0.25,
            "expected_consumption": 0.0,
        },
        {
            "name": "Engine IDLE (rpm=800), ECU=2.5 LPH (expected: 2.5 consumption)",
            "rpm": 800,
            "consumption_lph": 2.5,
            "dt_hours": 0.25,
            "expected_consumption": 2.5,
        },
        {
            "name": "Engine RUNNING (rpm=1500), ECU=None (expected: fallback)",
            "rpm": 1500,
            "consumption_lph": None,
            "dt_hours": 0.25,
            "expected_consumption": 15.0,  # City fallback
        },
        {
            "name": "Engine RUNNING (rpm=1800), ECU=42.0 LPH (expected: 42.0 consumption)",
            "rpm": 1800,
            "consumption_lph": 42.0,
            "dt_hours": 0.25,
            "expected_consumption": 42.0,
        },
        {
            "name": "Engine OFF, ECU=0.3 LPH (small leak - expected: 0 consumption)",
            "rpm": 0,
            "consumption_lph": 0.3,  # Below 0.5 threshold
            "dt_hours": 0.25,
            "expected_consumption": 0.0,
        },
    ]

    print("Testing scenarios:")
    print("-" * 70)

    for i, scenario in enumerate(scenarios, 1):
        # Reset to 50% for each test
        estimator.initialize(sensor_pct=50.0)
        initial_level = estimator.level_pct

        print(f"\n{i}. {scenario['name']}")
        print(
            f"   Input: rpm={scenario['rpm']}, consumption_lph={scenario['consumption_lph']}"
        )

        # Run predict
        estimator.predict(
            dt_hours=scenario["dt_hours"],
            consumption_lph=scenario["consumption_lph"],
            rpm=scenario["rpm"],
        )

        # Calculate actual consumption
        fuel_consumed_pct = initial_level - estimator.level_pct
        fuel_consumed_lph = (
            fuel_consumed_pct / 100.0 * estimator.capacity_liters
        ) / scenario["dt_hours"]

        # Check if matches expected
        expected = scenario["expected_consumption"]
        tolerance = 0.1
        passed = abs(fuel_consumed_lph - expected) < tolerance

        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   Result: {fuel_consumed_lph:.2f} LPH (expected {expected:.2f})")
        print(f"   {status}")

        if not passed:
            print(
                f"   ⚠️  FAILURE: Got {fuel_consumed_lph:.2f}, expected {expected:.2f}"
            )

    print("\n" + "=" * 70)
    print("✅ RPM vs ECU Cross-Validation Tests Complete")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_rpm_ecu_crossvalidation()
