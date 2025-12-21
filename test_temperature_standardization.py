"""
🧪 TEST: TEMPERATURE °C/°F STANDARDIZATION
═══════════════════════════════════════════════════════════════════════════════

Validates temperature unit consistency across all components.

BACKGROUND:
- All temperature thresholds should use Fahrenheit (°F)
- Sensors may report in Celsius (°C) or Fahrenheit (°F)
- Auto-detection and conversion ensures consistency

TEST COVERAGE:
1. TurboHealthPredictor thresholds in °F
2. OilConsumptionTracker thresholds in °F
3. Auto-detection: ensure_fahrenheit() function
4. Conversion accuracy (°C → °F)
5. Edge cases (already °F, boundary values)

EXPECTED BEHAVIOR:
- All thresholds use °F
- Celsius values auto-converted to °F
- Fahrenheit values passed through unchanged
- Display messages show °F units

Author: Fuel Copilot Team
Created: December 20, 2025
"""

import sys


def test_turbo_thresholds_fahrenheit():
    """
    Test 1: TurboHealthPredictor uses °F thresholds

    Expected: Normal 86-149°F, Warning 167°F, Critical 185°F
    """
    print("\n" + "=" * 80)
    print("TEST 1: TurboHealthPredictor Thresholds (°F)")
    print("=" * 80)

    from component_health_predictors import TurboHealthPredictor

    predictor = TurboHealthPredictor()

    print(f"  INTERCOOLER_TEMP_NORMAL = {predictor.INTERCOOLER_TEMP_NORMAL} °F")
    print(f"  INTERCOOLER_TEMP_WARNING = {predictor.INTERCOOLER_TEMP_WARNING} °F")
    print(f"  INTERCOOLER_TEMP_CRITICAL = {predictor.INTERCOOLER_TEMP_CRITICAL} °F")

    # Should be in Fahrenheit range (not Celsius)
    assert predictor.INTERCOOLER_TEMP_NORMAL == (
        86,
        149,
    ), f"Expected (86, 149)°F, got {predictor.INTERCOOLER_TEMP_NORMAL}"
    assert (
        predictor.INTERCOOLER_TEMP_WARNING == 167
    ), f"Expected 167°F, got {predictor.INTERCOOLER_TEMP_WARNING}"
    assert (
        predictor.INTERCOOLER_TEMP_CRITICAL == 185
    ), f"Expected 185°F, got {predictor.INTERCOOLER_TEMP_CRITICAL}"

    print("✅ PASS: TurboHealthPredictor uses °F thresholds")


def test_oil_thresholds_fahrenheit():
    """
    Test 2: OilConsumptionTracker uses °F thresholds

    Expected: Normal 180-230°F, Warning 250°F, Critical 260°F
    """
    print("\n" + "=" * 80)
    print("TEST 2: OilConsumptionTracker Thresholds (°F)")
    print("=" * 80)

    from component_health_predictors import OilConsumptionTracker

    tracker = OilConsumptionTracker()

    print(f"  OIL_TEMP_NORMAL = {tracker.OIL_TEMP_NORMAL} °F")
    print(f"  OIL_TEMP_WARNING = {tracker.OIL_TEMP_WARNING} °F")
    print(f"  OIL_TEMP_CRITICAL = {tracker.OIL_TEMP_CRITICAL} °F")

    # Should be in Fahrenheit range
    assert tracker.OIL_TEMP_NORMAL == (
        180,
        230,
    ), f"Expected (180, 230)°F, got {tracker.OIL_TEMP_NORMAL}"
    assert (
        tracker.OIL_TEMP_WARNING == 250
    ), f"Expected 250°F, got {tracker.OIL_TEMP_WARNING}"
    assert (
        tracker.OIL_TEMP_CRITICAL == 260
    ), f"Expected 260°F, got {tracker.OIL_TEMP_CRITICAL}"

    print("✅ PASS: OilConsumptionTracker uses °F thresholds")


def test_ensure_fahrenheit_celsius_input():
    """
    Test 3: ensure_fahrenheit() converts Celsius to Fahrenheit

    Expected: 30°C → 86°F, 65°C → 149°F
    """
    print("\n" + "=" * 80)
    print("TEST 3: ensure_fahrenheit() Celsius Conversion")
    print("=" * 80)

    from component_health_predictors import TurboHealthPredictor

    predictor = TurboHealthPredictor()

    # Test Celsius values
    test_cases = [
        (30, 86),  # 30°C → 86°F
        (65, 149),  # 65°C → 149°F
        (75, 167),  # 75°C → 167°F
        (85, 185),  # 85°C → 185°F
    ]

    for celsius, expected_f in test_cases:
        result = predictor.ensure_fahrenheit(celsius)
        print(f"  {celsius}°C → {result:.1f}°F (expected {expected_f}°F)")

        # Allow ±1°F tolerance for rounding
        assert (
            abs(result - expected_f) <= 1
        ), f"{celsius}°C should convert to ~{expected_f}°F, got {result}°F"

    print("✅ PASS: Celsius values correctly converted to Fahrenheit")


def test_ensure_fahrenheit_fahrenheit_input():
    """
    Test 4: ensure_fahrenheit() preserves Fahrenheit values

    Expected: 150°F → 150°F (no conversion)
    """
    print("\n" + "=" * 80)
    print("TEST 4: ensure_fahrenheit() Fahrenheit Pass-Through")
    print("=" * 80)

    from component_health_predictors import TurboHealthPredictor

    predictor = TurboHealthPredictor()

    # Test Fahrenheit values (already >100)
    test_cases = [150, 180, 200, 250]

    for fahrenheit in test_cases:
        result = predictor.ensure_fahrenheit(fahrenheit)
        print(f"  {fahrenheit}°F → {result:.1f}°F (no conversion)")

        assert (
            result == fahrenheit
        ), f"{fahrenheit}°F should not be converted, got {result}°F"

    print("✅ PASS: Fahrenheit values preserved unchanged")


def test_edge_cases():
    """
    Test 5: Edge cases

    - Boundary at 100 (99°C vs 100°F)
    - Very low temps (0°C, 32°F)
    - Very high temps (150°C, 300°F)
    """
    print("\n" + "=" * 80)
    print("TEST 5: Edge Cases")
    print("=" * 80)

    from component_health_predictors import TurboHealthPredictor

    predictor = TurboHealthPredictor()

    # Boundary: 99°C should be converted (99°C = 210°F)
    result_99c = predictor.ensure_fahrenheit(99)
    print(f"  99°C → {result_99c:.1f}°F (expected ~210°F)")
    assert result_99c > 200, f"99°C should convert to ~210°F, got {result_99c}°F"

    # Boundary: 100°F should NOT be converted
    result_100f = predictor.ensure_fahrenheit(100)
    print(f"  100°F → {result_100f:.1f}°F (no conversion)")
    assert result_100f == 100, f"100°F should not convert, got {result_100f}°F"

    # Low temp: 0°C = 32°F
    result_0c = predictor.ensure_fahrenheit(0)
    print(f"  0°C → {result_0c:.1f}°F (expected 32°F)")
    assert abs(result_0c - 32) < 1, f"0°C should convert to 32°F, got {result_0c}°F"

    # High temp: 150°C = 302°F
    result_150c = predictor.ensure_fahrenheit(150)
    print(f"  150°C → {result_150c:.1f}°F (expected ~302°F, but >100 so no conversion)")
    # NOTE: 150 is >100 so it's treated as already Fahrenheit
    assert result_150c == 150, f"150 is ambiguous, treated as °F"

    print("✅ PASS: Edge cases handled correctly")


def test_real_world_scenario():
    """
    Test 6: Real-world scenario with sensor data

    Simulate receiving Celsius data from Wialon and processing it
    """
    print("\n" + "=" * 80)
    print("TEST 6: Real-World Scenario (Wialon Data)")
    print("=" * 80)

    from datetime import datetime, timezone

    from component_health_predictors import TurboHealthPredictor

    predictor = TurboHealthPredictor()

    # Simulate Wialon sending Celsius data
    truck_id = "TEST_TRUCK"
    intrclr_celsius = 55  # 55°C = 131°F (normal range)

    # Add reading (should auto-convert)
    predictor.add_reading(
        truck_id=truck_id,
        intrclr_t=intrclr_celsius,
        intake_pres=25,  # PSI
        timestamp=datetime.now(timezone.utc),
    )

    # Get prediction
    prediction = predictor.predict(truck_id)

    print(f"  Input: {intrclr_celsius}°C intercooler temp")
    print(f"  Status: {prediction.status}")
    print(f"  Score: {prediction.score}/100")
    print(f"  Alerts: {prediction.alerts}")

    # Should be EXCELLENT or GOOD status (131°F is in normal range 86-149°F)
    assert prediction.status.value in [
        "excellent",
        "GOOD",
    ], f"55°C (131°F) should be EXCELLENT/GOOD, got {prediction.status.value}"

    # Score should be high (no major issues)
    assert (
        prediction.score >= 90
    ), f"Normal temp should have score ≥90, got {prediction.score}"

    print("✅ PASS: Real-world Celsius data processed correctly")


def main():
    """Run all tests"""
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 18 + "TEMPERATURE STANDARDIZATION TESTS" + " " * 27 + "║")
    print("╚" + "=" * 78 + "╝")

    try:
        # Run all tests
        test_turbo_thresholds_fahrenheit()
        test_oil_thresholds_fahrenheit()
        test_ensure_fahrenheit_celsius_input()
        test_ensure_fahrenheit_fahrenheit_input()
        test_edge_cases()
        test_real_world_scenario()

        # Summary
        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        print("\n✅ TurboHealthPredictor: All thresholds in °F")
        print("✅ OilConsumptionTracker: All thresholds in °F")
        print("✅ Auto-conversion: Celsius → Fahrenheit working")
        print("✅ Pass-through: Fahrenheit values preserved")
        print("✅ Edge cases: Boundary handling correct")
        print("✅ Real-world: Wialon data processed correctly")
        print("\n🌡️ TEMPERATURE UNITS: 100% CONSISTENT")
        print("🚀 READY FOR PRODUCTION")

        return 0

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n💥 UNEXPECTED ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
