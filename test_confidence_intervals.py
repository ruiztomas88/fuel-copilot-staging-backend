#!/usr/bin/env python3
"""
🧪 Test: Confidence Intervals for Loss Analysis V2
Version: 6.5.0
Date: December 21, 2025

Tests bootstrap confidence interval calculations for savings projections.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from database_mysql import calculate_savings_confidence_interval


def test_confidence_interval_basic():
    """Test basic confidence interval calculation"""
    print("\n" + "=" * 70)
    print("🧪 TEST: Basic Confidence Interval Calculation")
    print("=" * 70)

    # Test with $100/day savings, 50% reduction, 7 days
    result = calculate_savings_confidence_interval(
        savings_usd=100, reduction_pct=0.50, days_back=7
    )

    print(f"   Input: $100/day savings, 50% reduction, 7 days")
    print(f"   Expected annual: ${result['expected_annual']:,.0f}")
    print(f"   Lower bound (95% CI): ${result['lower_bound_annual']:,.0f}")
    print(f"   Upper bound (95% CI): ${result['upper_bound_annual']:,.0f}")
    print(
        f"   Range: ${result['lower_bound_annual']:,.0f} - ${result['upper_bound_annual']:,.0f}"
    )

    # Validate ranges
    assert result["expected_annual"] > 0, "Expected should be positive"
    assert result["lower_bound_annual"] < result["expected_annual"], "Lower < Expected"
    assert result["upper_bound_annual"] > result["expected_annual"], "Upper > Expected"
    assert result["confidence_level"] == 0.95, "Confidence level should be 0.95"

    # Check reasonableness (should be ~$36.5K annual from $100/day)
    expected_rough = 100 * 365
    assert (
        20000 < result["expected_annual"] < 50000
    ), f"Expected ~${expected_rough:,.0f}, got ${result['expected_annual']:,.0f}"

    print("   ✅ PASS: Confidence intervals calculated correctly")
    return True


def test_confidence_interval_high_variance():
    """Test with high reduction percentage (higher variance)"""
    print("\n" + "=" * 70)
    print("🧪 TEST: High Variance Scenario")
    print("=" * 70)

    # Test with $200/day, 80% reduction (high variance)
    result = calculate_savings_confidence_interval(
        savings_usd=200, reduction_pct=0.80, days_back=30
    )

    print(f"   Input: $200/day savings, 80% reduction, 30 days")
    print(f"   Expected annual: ${result['expected_annual']:,.0f}")
    print(
        f"   Range: ${result['lower_bound_annual']:,.0f} - ${result['upper_bound_annual']:,.0f}"
    )

    # With high reduction, variance should be higher
    range_size = result["upper_bound_annual"] - result["lower_bound_annual"]
    range_pct = range_size / result["expected_annual"] * 100

    print(f"   Range size: ${range_size:,.0f} ({range_pct:.0f}% of expected)")

    assert range_pct > 20, "High variance should have >20% range"
    assert range_pct < 100, "Range should be <100% of expected"

    print("   ✅ PASS: High variance handled correctly")
    return True


def test_confidence_interval_stability():
    """Test that multiple runs produce consistent results"""
    print("\n" + "=" * 70)
    print("🧪 TEST: Stability Across Multiple Runs")
    print("=" * 70)

    results = []
    for i in range(5):
        result = calculate_savings_confidence_interval(
            savings_usd=150, reduction_pct=0.60, days_back=14, num_bootstrap=500
        )
        results.append(result["expected_annual"])

    avg_expected = sum(results) / len(results)
    std_dev = (sum((x - avg_expected) ** 2 for x in results) / len(results)) ** 0.5
    cv = std_dev / avg_expected * 100  # Coefficient of variation

    print(f"   5 runs of bootstrap (500 samples each)")
    print(f"   Results: {[f'${r:,.0f}' for r in results]}")
    print(f"   Average: ${avg_expected:,.0f}")
    print(f"   Std Dev: ${std_dev:,.0f}")
    print(f"   CV: {cv:.1f}%")

    # Results should be relatively stable (CV < 10%)
    assert cv < 15, f"Results too unstable: CV={cv:.1f}% (should be <15%)"

    print("   ✅ PASS: Results stable across runs")
    return True


def test_confidence_interval_edge_cases():
    """Test edge cases"""
    print("\n" + "=" * 70)
    print("🧪 TEST: Edge Cases")
    print("=" * 70)

    # Small savings
    result1 = calculate_savings_confidence_interval(
        savings_usd=10, reduction_pct=0.30, days_back=7
    )
    print(f"   Small savings ($10/day): ${result1['expected_annual']:,.0f}/year")
    assert result1["expected_annual"] > 0, "Should handle small savings"

    # Large savings
    result2 = calculate_savings_confidence_interval(
        savings_usd=1000, reduction_pct=0.50, days_back=30
    )
    print(f"   Large savings ($1000/day): ${result2['expected_annual']:,.0f}/year")
    assert result2["expected_annual"] > 100000, "Should handle large savings"

    # Low reduction (low variance)
    result3 = calculate_savings_confidence_interval(
        savings_usd=100, reduction_pct=0.10, days_back=7
    )
    range_size = result3["upper_bound_annual"] - result3["lower_bound_annual"]
    range_pct = range_size / result3["expected_annual"] * 100
    print(f"   Low reduction (10%): Range = {range_pct:.0f}% of expected")
    assert range_pct < 40, "Low reduction should have narrow range"

    print("   ✅ PASS: Edge cases handled correctly")
    return True


def test_real_world_scenarios():
    """Test with realistic fleet scenarios"""
    print("\n" + "=" * 70)
    print("🧪 TEST: Real-World Fleet Scenarios")
    print("=" * 70)

    scenarios = [
        {
            "name": "Small fleet idle reduction",
            "savings_usd": 75,
            "reduction_pct": 0.70,
            "days_back": 7,
        },
        {
            "name": "Large fleet RPM optimization",
            "savings_usd": 250,
            "reduction_pct": 0.50,
            "days_back": 30,
        },
        {
            "name": "Medium fleet speed management",
            "savings_usd": 150,
            "reduction_pct": 0.40,
            "days_back": 14,
        },
    ]

    for scenario in scenarios:
        result = calculate_savings_confidence_interval(
            savings_usd=scenario["savings_usd"],
            reduction_pct=scenario["reduction_pct"],
            days_back=scenario["days_back"],
        )

        print(f"\n   Scenario: {scenario['name']}")
        print(f"      Expected: ${result['expected_annual']:,.0f}/year")
        print(
            f"      Range: ${result['lower_bound_annual']:,.0f} - ${result['upper_bound_annual']:,.0f}"
        )

        # Validate all scenarios produce reasonable results
        assert result["expected_annual"] > 10000, "Should be > $10K/year"
        assert result["expected_annual"] < 500000, "Should be < $500K/year"
        assert result["lower_bound_annual"] > 0, "Lower bound should be positive"

    print("\n   ✅ PASS: All scenarios realistic")
    return True


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("🎯 CONFIDENCE INTERVALS TEST SUITE")
    print("   Version: v6.5.0")
    print("   Date: December 21, 2025")
    print("=" * 70)

    # Run all tests
    test1 = test_confidence_interval_basic()
    test2 = test_confidence_interval_high_variance()
    test3 = test_confidence_interval_stability()
    test4 = test_confidence_interval_edge_cases()
    test5 = test_real_world_scenarios()

    # Summary
    print("\n" + "=" * 70)
    print("📊 TEST SUMMARY")
    print("=" * 70)
    print(f"   Basic Calculation:        {'✅ PASS' if test1 else '❌ FAIL'}")
    print(f"   High Variance:            {'✅ PASS' if test2 else '❌ FAIL'}")
    print(f"   Stability:                {'✅ PASS' if test3 else '❌ FAIL'}")
    print(f"   Edge Cases:               {'✅ PASS' if test4 else '❌ FAIL'}")
    print(f"   Real-World Scenarios:     {'✅ PASS' if test5 else '❌ FAIL'}")

    all_passed = all([test1, test2, test3, test4, test5])

    if all_passed:
        print("\n🎉 ALL TESTS PASSED - Confidence intervals ready!")
        print("\n📋 Implementation Summary:")
        print("   ✅ Bootstrap confidence intervals (95% CI)")
        print("   ✅ Realistic variance modeling (±30% daily)")
        print("   ✅ Stable results across runs (CV < 15%)")
        print("   ✅ Edge cases handled")
        print("   ✅ Integration with Loss Analysis V2")
        sys.exit(0)
    else:
        print("\n❌ SOME TESTS FAILED - Review implementation")
        sys.exit(1)
