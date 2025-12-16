#!/usr/bin/env python3
"""
Quick API Test Script
Run this locally or on the VM to test if endpoints return correct data.
"""

import sys
import json

def test_local():
    """Test endpoints by importing modules directly"""
    print("=" * 60)
    print("FUEL ANALYTICS API - QUICK TEST")
    print("=" * 60)
    
    # Test 1: Cost Per Mile
    print("\n📊 TEST 1: Cost Per Mile Endpoint")
    print("-" * 40)
    try:
        from cost_per_mile_engine import CostPerMileEngine
        from database_mysql import get_fleet_summary_for_cost
        
        cpm = CostPerMileEngine()
        trucks_data = get_fleet_summary_for_cost(days=30)
        
        if not trucks_data:
            print("⚠️  No truck data returned from database")
        else:
            print(f"✅ Got data for {len(trucks_data)} trucks")
            report = cpm.generate_cost_report(trucks_data, period_days=30)
            
            # Check what the response would look like
            response = {
                "status": "success",
                "generated_at": report.get("period", {}).get("end", ""),
                "data": report,
            }
            
            cost = response["data"].get("cost_per_mile", {}).get("fleet_average", 0)
            print(f"✅ Fleet average cost per mile: ${cost:.2f}")
            
            if cost == 0:
                print("⚠️  Cost is $0.00 - checking breakdown...")
                breakdown = report.get("cost_per_mile", {}).get("breakdown", {})
                print(f"   Breakdown: {json.dumps(breakdown, indent=2)}")
            
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # Test 2: Command Center Dashboard
    print("\n🎯 TEST 2: Command Center Dashboard")
    print("-" * 40)
    try:
        from fleet_command_center import FleetCommandCenter, get_command_center
        
        cc = get_command_center()
        data = cc.generate_command_center_data()
        data_dict = data.to_dict()
        
        health = data_dict.get("fleet_health", {})
        print(f"✅ Fleet health score: {health.get('score', 'N/A')}/100")
        
        sensor = data_dict.get("sensor_status", {})
        print(f"✅ Sensor health: {sensor.get('healthy', 'N/A')}% healthy")
        print(f"   Voltage issues: {sensor.get('voltage_issues', 'N/A')}")
        print(f"   Signal issues: {sensor.get('signal_issues', 'N/A')}")
        
        urgency = data_dict.get("urgency_summary", {})
        print(f"✅ Urgency summary:")
        print(f"   Critical: {urgency.get('critical', 0)}")
        print(f"   High: {urgency.get('high', 0)}")
        print(f"   Medium: {urgency.get('medium', 0)}")
        print(f"   Low: {urgency.get('low', 0)}")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 3: Battery Voltage Query
    print("\n🔋 TEST 3: Battery Voltage Data")
    print("-" * 40)
    try:
        from database_mysql import get_sensor_health_summary
        
        health = get_sensor_health_summary()
        print(f"✅ Sensor health summary:")
        print(f"   Total trucks: {health.get('total_trucks', 0)}")
        print(f"   Trucks with voltage data: {health.get('trucks_with_voltage_data', 0)}")
        print(f"   Voltage issues: {health.get('voltage_issues', 0)}")
        print(f"   Min voltage: {health.get('min_voltage', 'N/A')}V")
        print(f"   Max voltage: {health.get('max_voltage', 'N/A')}V")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 4: Driver Behavior Scores
    print("\n👤 TEST 4: Driver Behavior Scores")
    print("-" * 40)
    try:
        from driver_behavior_engine import get_behavior_engine
        
        engine = get_behavior_engine()
        summary = engine.get_fleet_behavior_summary()
        
        if "error" in summary:
            print(f"⚠️  {summary['error']}")
        else:
            print(f"✅ Fleet behavior summary:")
            print(f"   Fleet size: {summary.get('fleet_size', 0)}")
            print(f"   Average score: {summary.get('average_score', 0)}")
            print(f"   Needs work count: {summary.get('needs_work_count', 0)}")
            
            scores = summary.get('behavior_scores', {})
            if scores:
                print(f"✅ Behavior scores:")
                print(f"   Acceleration: {scores.get('acceleration', 100)}")
                print(f"   Braking: {scores.get('braking', 100)}")
                print(f"   RPM Mgmt: {scores.get('rpm_mgmt', 100)}")
                print(f"   Gear Usage: {scores.get('gear_usage', 100)}")
                print(f"   Speed Control: {scores.get('speed_control', 100)}")
            else:
                print("⚠️  No behavior_scores in response (old version?)")
                
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    test_local()
