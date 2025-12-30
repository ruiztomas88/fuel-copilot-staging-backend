"""
Comprehensive testing for all advanced services
Tests HealthAnalyzer, DEFPredictor, PatternAnalyzer
"""

import sys
from decimal import Decimal
from datetime import datetime
from src.config_helper import get_db_config
from src.repositories.truck_repository import TruckRepository
from src.repositories.sensor_repository import SensorRepository
from src.repositories.def_repository import DEFRepository
from src.repositories.dtc_repository import DTCRepository
from src.services.health_analyzer_adapted import HealthAnalyzer
from src.services.def_predictor_adapted import DEFPredictor
from src.services.pattern_analyzer_adapted import PatternAnalyzer

def test_health_analyzer():
    """Test HealthAnalyzer service."""
    print("\n" + "="*80)
    print("TESTING HealthAnalyzer")
    print("="*80)
    
    analyzer = HealthAnalyzer()
    
    # Test 1: Truck risk score with critical conditions
    print("\n--- Test 1: Truck with CRITICAL conditions ---")
    sensor_data = {
        'coolant_temp_f': 235,  # Critical
        'oil_pressure_psi': 12,  # Critical
        'battery_voltage': 11.2  # Low
    }
    result = analyzer.calculate_truck_risk_score(
        truck_id="TEST001",
        sensor_data=sensor_data,
        dtc_count=5,
        fuel_level=8,
        days_offline=10
    )
    print(f"Risk Score: {result['risk_score']}")
    print(f"Risk Level: {result['risk_level']}")
    print(f"Factors: {result['contributing_factors']}")
    assert result['risk_level'] == 'CRITICAL', "Should be CRITICAL"
    assert result['risk_score'] >= 75, "Score should be >= 75"
    print("✅ Test 1 PASSED")
    
    # Test 2: Truck risk score with normal conditions
    print("\n--- Test 2: Truck with NORMAL conditions ---")
    sensor_data = {
        'coolant_temp_f': 195,
        'oil_pressure_psi': 45,
        'battery_voltage': 12.8
    }
    result = analyzer.calculate_truck_risk_score(
        truck_id="TEST002",
        sensor_data=sensor_data,
        dtc_count=0,
        fuel_level=60,
        days_offline=0
    )
    print(f"Risk Score: {result['risk_score']}")
    print(f"Risk Level: {result['risk_level']}")
    assert result['risk_level'] == 'LOW', "Should be LOW"
    assert result['risk_score'] < 25, "Score should be < 25"
    print("✅ Test 2 PASSED")
    
    # Test 3: Fleet health score
    print("\n--- Test 3: Fleet health calculation ---")
    health = analyzer.calculate_fleet_health_score(
        total_trucks=27,
        active_trucks=20,
        trucks_with_issues=5,
        trucks_with_dtcs=8,
        trucks_low_fuel=3
    )
    print(f"Fleet Health Score: {health['health_score']}")
    print(f"Health Level: {health['health_level']}")
    print(f"Active: {health['active_trucks']}/{health['total_trucks']}")
    assert 0 <= health['health_score'] <= 100, "Score must be 0-100"
    print("✅ Test 3 PASSED")
    
    # Test 4: Fleet insights
    print("\n--- Test 4: Fleet insights generation ---")
    insights = analyzer.get_fleet_insights(health)
    print(f"Generated {len(insights)} insights:")
    for insight in insights:
        print(f"  - {insight}")
    assert len(insights) > 0, "Should generate insights"
    print("✅ Test 4 PASSED")
    
    print("\n✅✅✅ ALL HealthAnalyzer tests PASSED\n")
    return True

def test_def_predictor():
    """Test DEFPredictor service."""
    print("\n" + "="*80)
    print("TESTING DEFPredictor")
    print("="*80)
    
    predictor = DEFPredictor()
    
    # Test 1: Critical DEF level (< 5%)
    print("\n--- Test 1: CRITICAL DEF level ---")
    result = predictor.predict_def_depletion(
        truck_id="TEST001",
        current_level_pct=4.0,
        daily_miles=300,
        avg_mpg=6.5,
        avg_consumption_gph=15
    )
    print(f"Status: {result['status']}")
    print(f"Current Level: {result['current_level_pct']}%")
    print(f"Days until derate: {result['days_until_derate']}")
    assert result['status'] == 'CRITICAL', "Should be CRITICAL"
    print("✅ Test 1 PASSED")
    
    # Test 2: Warning DEF level
    print("\n--- Test 2: WARNING DEF level ---")
    result = predictor.predict_def_depletion(
        truck_id="TEST002",
        current_level_pct=12.0,
        daily_miles=200,
        avg_mpg=7.0
    )
    print(f"Status: {result['status']}")
    print(f"Days until derate: {result['days_until_derate']}")
    assert result['status'] in ['WARNING', 'NOTICE'], "Should be WARNING or NOTICE"
    print("✅ Test 2 PASSED")
    
    # Test 3: OK DEF level
    print("\n--- Test 3: OK DEF level ---")
    result = predictor.predict_def_depletion(
        truck_id="TEST003",
        current_level_pct=80.0,
        daily_miles=150
    )
    print(f"Status: {result['status']}")
    print(f"Days until derate: {result['days_until_derate']}")
    assert result['status'] == 'OK', "Should be OK"
    print("✅ Test 3 PASSED")
    
    # Test 4: Low DEF trucks filtering
    print("\n--- Test 4: Low DEF trucks filtering ---")
    trucks_data = [
        {'truck_id': 'T1', 'def_level_pct': 3.0, 'avg_mpg': 6.5},
        {'truck_id': 'T2', 'def_level_pct': 25.0, 'avg_mpg': 7.0},
        {'truck_id': 'T3', 'def_level_pct': 8.0, 'avg_mpg': 6.8},
        {'truck_id': 'T4', 'def_level_pct': 50.0, 'avg_mpg': 7.2},
    ]
    low_def = predictor.get_low_def_trucks(trucks_data, threshold_pct=15)
    print(f"Found {len(low_def)} trucks below 15%:")
    for truck in low_def:
        print(f"  - {truck['truck_id']}: {truck['current_level_pct']}%")
    assert len(low_def) == 2, "Should find 2 trucks"
    assert low_def[0]['truck_id'] == 'T1', "Should be sorted by level"
    print("✅ Test 4 PASSED")
    
    print("\n✅✅✅ ALL DEFPredictor tests PASSED\n")
    return True

def test_pattern_analyzer():
    """Test PatternAnalyzer service."""
    print("\n" + "="*80)
    print("TESTING PatternAnalyzer")
    print("="*80)
    
    analyzer = PatternAnalyzer()
    
    # Test 1: Detect correlations (cooling failure)
    print("\n--- Test 1: Cooling failure correlation ---")
    sensor_data = {
        'coolant_temp_f': 235,
        'oil_pressure_psi': 20
    }
    dtc_codes = ['P0217', 'P0218']
    correlations = analyzer.detect_correlations(
        truck_id="TEST001",
        sensor_data=sensor_data,
        dtc_codes=dtc_codes
    )
    print(f"Found {len(correlations)} correlations:")
    for corr in correlations:
        print(f"  - {corr['pattern']}: {corr['description']}")
    assert len(correlations) > 0, "Should detect cooling failure"
    print("✅ Test 1 PASSED")
    
    # Test 2: Overheating syndrome
    print("\n--- Test 2: Overheating syndrome ---")
    sensor_data = {
        'coolant_temp_f': 230,
        'oil_temp_f': 260,
        'trans_temp_f': 240
    }
    correlations = analyzer.detect_correlations(
        truck_id="TEST002",
        sensor_data=sensor_data,
        dtc_codes=[]
    )
    print(f"Found {len(correlations)} correlations:")
    for corr in correlations:
        print(f"  - {corr['pattern']}: {corr['severity']}")
    overheating = any(c['pattern'] == 'widespread_overheating' for c in correlations)
    assert overheating, "Should detect overheating syndrome"
    print("✅ Test 2 PASSED")
    
    # Test 3: Fleet patterns (overheating affecting many trucks)
    print("\n--- Test 3: Fleet-wide overheating pattern ---")
    trucks_sensors = [
        {'truck_id': f'T{i}', 'coolant_temp_f': 235, 'oil_temp_f': 260}
        for i in range(10)  # 10 trucks with high temps
    ]
    # Add 5 normal trucks
    trucks_sensors.extend([
        {'truck_id': f'N{i}', 'coolant_temp_f': 195, 'oil_temp_f': 200}
        for i in range(5)
    ])
    
    dtc_data = [{'truck_id': f'T{i}', 'dtc_code': 'P0217'} for i in range(8)]
    
    patterns = analyzer.detect_fleet_patterns(trucks_sensors, dtc_data)
    print(f"Found {len(patterns)} fleet patterns:")
    for p in patterns:
        print(f"  - {p['pattern_type']}: {p['affected_count']} trucks ({p['severity']})")
    assert len(patterns) > 0, "Should detect fleet patterns"
    print("✅ Test 3 PASSED")
    
    # Test 4: Systemic issues extraction
    print("\n--- Test 4: Systemic issues extraction ---")
    if patterns:
        systemic = analyzer.get_systemic_issues(patterns)
        print(f"Extracted {len(systemic)} systemic issues:")
        for issue in systemic:
            print(f"  - {issue['description']}")
        assert len(systemic) > 0, "Should extract systemic issues"
    print("✅ Test 4 PASSED")
    
    print("\n✅✅✅ ALL PatternAnalyzer tests PASSED\n")
    return True

def test_real_data():
    """Test with real database data."""
    print("\n" + "="*80)
    print("TESTING with REAL DATABASE DATA")
    print("="*80)
    
    try:
        db_config = get_db_config()
        truck_repo = TruckRepository(db_config)
        sensor_repo = SensorRepository(db_config)
        def_repo = DEFRepository(db_config)
        dtc_repo = DTCRepository(db_config)
        
        # Get one truck
        trucks = truck_repo.get_all_trucks()
        if not trucks:
            print("⚠️ No trucks found in database")
            return False
            
        test_truck = trucks[0]
        truck_id = test_truck['truck_id']
        print(f"\nTesting with truck: {truck_id}")
        
        # Test HealthAnalyzer with real data
        print("\n--- HealthAnalyzer with real data ---")
        analyzer = HealthAnalyzer()
        sensors = sensor_repo.get_truck_sensors(truck_id)
        dtcs = dtc_repo.get_active_dtcs(truck_id)
        
        risk = analyzer.calculate_truck_risk_score(
            truck_id=truck_id,
            sensor_data=sensors or {},
            dtc_count=len(dtcs),
            fuel_level=test_truck.get('fuel_level'),
            days_offline=0
        )
        print(f"Risk Score: {risk['risk_score']} ({risk['risk_level']})")
        print(f"Factors: {len(risk['contributing_factors'])}")
        print("✅ HealthAnalyzer works with real data")
        
        # Test DEFPredictor with real data
        print("\n--- DEFPredictor with real data ---")
        predictor = DEFPredictor()
        def_level = def_repo.get_def_level(truck_id)
        if def_level:
            prediction = predictor.predict_def_depletion(
                truck_id=truck_id,
                current_level_pct=def_level,
                avg_mpg=test_truck.get('mpg')
            )
            print(f"DEF Status: {prediction['status']}")
            print(f"Days until derate: {prediction['days_until_derate']}")
            print("✅ DEFPredictor works with real data")
        else:
            print("⚠️ No DEF data available")
        
        # Test PatternAnalyzer with real fleet data
        print("\n--- PatternAnalyzer with real fleet ---")
        pattern_analyzer = PatternAnalyzer()
        all_sensors = sensor_repo.get_all_sensors_for_fleet()
        fleet_dtcs = dtc_repo.get_fleet_dtcs()
        
        patterns = pattern_analyzer.detect_fleet_patterns(all_sensors, fleet_dtcs)
        print(f"Detected {len(patterns)} fleet patterns")
        for p in patterns[:3]:  # Show first 3
            print(f"  - {p['pattern_type']}: {p['affected_count']} trucks")
        print("✅ PatternAnalyzer works with real data")
        
        print("\n✅✅✅ ALL REAL DATA tests PASSED\n")
        return True
        
    except Exception as e:
        print(f"\n❌ Real data test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run all tests."""
    print("\n" + "="*80)
    print("COMPREHENSIVE ADVANCED SERVICES TEST SUITE")
    print("="*80)
    
    results = {}
    
    try:
        results['HealthAnalyzer'] = test_health_analyzer()
    except Exception as e:
        print(f"\n❌ HealthAnalyzer tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        results['HealthAnalyzer'] = False
    
    try:
        results['DEFPredictor'] = test_def_predictor()
    except Exception as e:
        print(f"\n❌ DEFPredictor tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        results['DEFPredictor'] = False
    
    try:
        results['PatternAnalyzer'] = test_pattern_analyzer()
    except Exception as e:
        print(f"\n❌ PatternAnalyzer tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        results['PatternAnalyzer'] = False
    
    try:
        results['RealData'] = test_real_data()
    except Exception as e:
        print(f"\n❌ Real data tests FAILED: {e}")
        import traceback
        traceback.print_exc()
        results['RealData'] = False
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    for test, passed_flag in results.items():
        status = "✅ PASSED" if passed_flag else "❌ FAILED"
        print(f"{test:30} {status}")
    
    print("\n" + "="*80)
    print(f"TOTAL: {passed}/{total} test suites passed")
    coverage = (passed / total * 100) if total > 0 else 0
    print(f"COVERAGE: {coverage:.1f}%")
    print("="*80 + "\n")
    
    return passed == total

if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
