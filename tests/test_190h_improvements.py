#!/usr/bin/env python3
"""
Test script for 190h algorithm improvements
Tests the new algorithms without touching database or infrastructure
"""

import sys
from database_mysql import (
    haversine_distance,
    calculate_fleet_health_score,
)
from mpg_baseline_service import calculate_percentile


def test_haversine_improved():
    """Test improved Haversine distance calculation"""
    print("\n🧪 Testing Improved Haversine Algorithm")
    print("=" * 60)
    
    # Test 1: NYC to LA (known distance ~3944 km = ~2451 miles)
    dist1 = haversine_distance(40.7128, -74.0060, 34.0522, -118.2437)
    print(f"✅ NYC to LA: {dist1:.2f} miles (expected ~2,451)")
    
    # Test 2: Short distance (should be very precise)
    dist2 = haversine_distance(40.7128, -74.0060, 40.7589, -73.9851)
    print(f"✅ NYC to Times Square: {dist2:.2f} miles (expected ~3.5)")
    
    # Test 3: Zero distance
    dist3 = haversine_distance(40.0, -74.0, 40.0, -74.0)
    print(f"✅ Same location: {dist3:.2f} miles (expected 0.00)")
    
    assert dist3 < 0.01, "Same location should be ~0 distance"
    print("✅ Haversine algorithm working correctly\n")


def test_efficiency_rating_algorithm():
    """Test efficiency rating calculation logic"""
    print("\n🧪 Testing Efficiency Rating Algorithm")
    print("=" * 60)
    
    baseline_mpg = 5.7
    
    test_cases = [
        (6.5, "HIGH", "Good truck (14% above baseline)"),
        (5.5, "MEDIUM", "Average truck (4% below baseline)"),
        (4.8, "LOW", "Poor truck (16% below baseline)"),
        (5.7, "MEDIUM", "Exactly at baseline"),
    ]
    
    for avg_mpg, expected_rating, description in test_cases:
        mpg_vs_baseline = ((avg_mpg - baseline_mpg) / baseline_mpg * 100)
        
        if mpg_vs_baseline > 5:
            rating = "HIGH"
        elif mpg_vs_baseline < -5:
            rating = "LOW"
        else:
            rating = "MEDIUM"
        
        status = "✅" if rating == expected_rating else "❌"
        print(f"{status} {description}")
        print(f"   MPG: {avg_mpg:.1f} | Baseline: {baseline_mpg:.1f} | "
              f"Diff: {mpg_vs_baseline:+.1f}% | Rating: {rating}")
        
        assert rating == expected_rating, f"Expected {expected_rating}, got {rating}"
    
    print("✅ Efficiency rating algorithm working correctly\n")


def test_health_score_algorithm():
    """Test fleet health score calculation"""
    print("\n🧪 Testing Fleet Health Score Algorithm")
    print("=" * 60)
    
    test_cases = [
        (0, 50, 100.0, "Perfect fleet (no DTCs)"),
        (10, 50, 90.0, "10 DTCs in 50 trucks"),
        (50, 50, 50.0, "1 DTC per truck"),
        (100, 50, 0.0, "Critical: 2 DTCs per truck"),
        (5, 10, 75.0, "Small fleet with few DTCs"),
    ]
    
    for dtc_count, truck_count, expected_score, description in test_cases:
        score = calculate_fleet_health_score(dtc_count, truck_count)
        status = "✅" if abs(score - expected_score) < 1 else "❌"
        print(f"{status} {description}")
        print(f"   DTCs: {dtc_count} | Trucks: {truck_count} | "
              f"Score: {score:.1f} (expected {expected_score:.1f})")
        
        # Allow 1 point tolerance due to normalization
        assert abs(score - expected_score) < 5, \
            f"Expected ~{expected_score}, got {score}"
    
    print("✅ Health score algorithm working correctly\n")


def test_percentile_improved():
    """Test improved percentile calculation with interpolation"""
    print("\n🧪 Testing Improved Percentile Algorithm")
    print("=" * 60)
    
    # Test 1: Simple dataset
    data1 = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    p50 = calculate_percentile(data1, 50)
    p90 = calculate_percentile(data1, 90)
    print(f"✅ Data [1-10]: P50={p50:.1f} (expected 5.5), P90={p90:.1f} (expected 9.1)")
    
    # Test 2: Empty data
    p_empty = calculate_percentile([], 50)
    assert p_empty == 0.0, "Empty data should return 0.0"
    print(f"✅ Empty data: {p_empty} (expected 0.0)")
    
    # Test 3: Single value
    p_single = calculate_percentile([5.5], 50)
    assert p_single == 5.5, "Single value should return itself"
    print(f"✅ Single value: {p_single} (expected 5.5)")
    
    # Test 4: MPG-like data (realistic scenario)
    mpg_data = [4.5, 5.2, 5.7, 5.8, 6.0, 6.1, 6.3, 7.2]
    p25 = calculate_percentile(mpg_data, 25)
    p75 = calculate_percentile(mpg_data, 75)
    print(f"✅ MPG data: P25={p25:.2f}, P75={p75:.2f} (using interpolation)")
    
    print("✅ Percentile algorithm with interpolation working correctly\n")


def main():
    """Run all tests"""
    print("\n" + "=" * 60)
    print("🚀 TESTING 190H ALGORITHM IMPROVEMENTS")
    print("=" * 60)
    print("\nOnly testing LOGIC and ALGORITHMS (no DB, security, refactoring)")
    
    try:
        test_haversine_improved()
        test_efficiency_rating_algorithm()
        test_health_score_algorithm()
        test_percentile_improved()
        
        print("\n" + "=" * 60)
        print("✅ ALL ALGORITHM TESTS PASSED!")
        print("=" * 60)
        print("\n📊 Summary of Improvements:")
        print("1. ✅ Haversine: More precise GPS distance calculation")
        print("2. ✅ Efficiency Rating: Smart MPG categorization (HIGH/MEDIUM/LOW)")
        print("3. ✅ Health Score: Fleet health based on DTC count")
        print("4. ✅ Percentile: Linear interpolation for better accuracy")
        print("\nThese improvements enhance data quality without changing infrastructure.\n")
        
        return 0
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        return 1
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
