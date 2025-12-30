"""
🧪 Test ECU Validation Feature (v6.2.0)

Quick test to verify ECU validation against physics-based model works correctly.

Usage:
    python test_ecu_validation.py
"""

import logging

from estimator import FuelEstimator

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_ecu_validation():
    """Test ECU validation with sample data"""
    print("\n" + "=" * 70)
    print("🧪 TESTING ECU VALIDATION v6.2.0")
    print("=" * 70)

    # Create estimator
    estimator = FuelEstimator(
        truck_id="TEST001", capacity_liters=454, config={"Q_r": 0.05, "Q_L_moving": 2.5}
    )

    # Load calibration (or use defaults)
    calibrated = estimator.load_calibrated_params()
    if calibrated:
        print("✅ Calibration loaded successfully")
    else:
        print("ℹ️  Using default calibration parameters")

    print(
        f"   Baseline: {estimator.baseline_consumption:.4f} %/min, "
        f"Load Factor: {estimator.load_factor:.4f}, "
        f"Altitude Factor: {estimator.altitude_factor:.6f}\n"
    )

    # Test scenarios
    scenarios = [
        {
            "name": "Healthy ECU - Highway",
            "ecu_lph": 42.0,
            "dt_hours": 0.25,
            "engine_load_pct": 65.0,
            "altitude_change_m": 50.0,
        },
        {
            "name": "Healthy ECU - City",
            "ecu_lph": 28.0,
            "dt_hours": 0.25,
            "engine_load_pct": 45.0,
            "altitude_change_m": 10.0,
        },
        {
            "name": "Faulty ECU - Too High",
            "ecu_lph": 95.0,  # Suspiciously high
            "dt_hours": 0.25,
            "engine_load_pct": 50.0,
            "altitude_change_m": 0.0,
        },
        {
            "name": "Faulty ECU - Too Low",
            "ecu_lph": 8.0,  # Suspiciously low for moving
            "dt_hours": 0.25,
            "engine_load_pct": 70.0,
            "altitude_change_m": 100.0,
        },
        {
            "name": "Idle Condition",
            "ecu_lph": 3.5,
            "dt_hours": 0.5,
            "engine_load_pct": 0.0,
            "altitude_change_m": 0.0,
        },
    ]

    for i, scenario in enumerate(scenarios, 1):
        print(f"\n📊 Test {i}: {scenario['name']}")
        print("-" * 70)

        validation = estimator.validate_ecu_consumption(
            ecu_consumption_lph=scenario["ecu_lph"],
            dt_hours=scenario["dt_hours"],
            engine_load_pct=scenario["engine_load_pct"],
            altitude_change_m=scenario["altitude_change_m"],
            threshold_pct=30.0,
        )

        print(f"   ECU Reading:      {validation['ecu_lph']} LPH")
        print(f"   Physics Model:    {validation['model_lph']} LPH")
        print(f"   Deviation:        {validation['deviation_pct']}%")
        print(f"   Status:           {validation['status']}")
        print(f"   Valid:            {'✅ Yes' if validation['valid'] else '❌ No'}")
        print(f"   Message:          {validation['message']}")

        # Visual indicator
        if validation["status"] == "OK":
            print("   Result:           🟢 ECU HEALTHY")
        elif validation["status"] == "WARNING":
            print("   Result:           🟡 ECU SUSPICIOUS")
        elif validation["status"] == "CRITICAL":
            print("   Result:           🔴 ECU POSSIBLY FAULTY")

    print("\n" + "=" * 70)
    print("✅ ECU Validation Tests Complete")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    test_ecu_validation()
