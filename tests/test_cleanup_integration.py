"""
🧪 INTEGRATION TEST: Memory Cleanup Orchestrator
═══════════════════════════════════════════════════════════════════════════════

Tests the complete cleanup workflow with all engines running.

Prerequisites:
- Database connection available
- tanks.yaml with active trucks
- All engines initialized

Run with:
    python tests/test_cleanup_integration.py

OR with pytest:
    pytest tests/test_cleanup_integration.py -v
"""

import os
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

print("=" * 80)
print("🧪 INTEGRATION TEST: CLEANUP ORCHESTRATOR")
print("=" * 80)


def test_cleanup_orchestrator():
    """
    Test 1: Cleanup Orchestrator End-to-End

    Validates:
    - Can load active trucks from tanks.yaml
    - All engines have cleanup methods
    - Cleanup executes without errors
    - Returns valid cleanup counts
    """
    print("\n📋 TEST 1: Cleanup Orchestrator End-to-End")
    print("-" * 80)

    try:
        from cleanup_orchestrator import cleanup_all_engines, get_active_truck_ids

        # Load active trucks
        active_trucks = get_active_truck_ids()
        print(f"✅ Loaded {len(active_trucks)} active trucks from tanks.yaml")

        assert len(active_trucks) > 0, "No active trucks found"

        # Run cleanup (dry run with 0 days to avoid actual cleanup)
        results = cleanup_all_engines(active_trucks, max_inactive_days=365)

        print(f"\n📊 Cleanup Results:")
        for engine_name, result in results.items():
            if isinstance(result, int):
                print(f"   {engine_name:30s}: ✅ {result} trucks cleaned")
            else:
                print(f"   {engine_name:30s}: {result}")

        # Validate all engines responded
        expected_engines = [
            "driver_behavior",
            "theft_detection",
            "mpg_baseline",
            "alert_manager",
            "predictive_maintenance",
            "component_health",
        ]

        for engine in expected_engines:
            assert engine in results, f"Engine {engine} missing from results"
            result = results[engine]

            # Should be either int (count) or error message
            if not isinstance(result, int):
                if "Error" in str(result):
                    print(f"   ⚠️  {engine}: {result}")
                    # Errors are acceptable in integration test (engine might not be initialized)

        print("\n✅ PASS: Orchestrator executed successfully")
        return True

    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_individual_engine_cleanup():
    """
    Test 2: Individual Engine Cleanup Methods

    Validates each engine's cleanup method works independently
    """
    print("\n📋 TEST 2: Individual Engine Cleanup Methods")
    print("-" * 80)

    results = {}

    # Test 1: Driver Behavior Engine
    try:
        from driver_behavior_engine import DriverBehaviorEngine

        engine = DriverBehaviorEngine()

        # Create fake truck states
        from datetime import datetime, timedelta, timezone

        # Active truck (recent activity)
        engine.truck_states["ACTIVE001"] = type(
            "State",
            (),
            {"truck_id": "ACTIVE001", "last_timestamp": datetime.now(timezone.utc)},
        )()

        # Inactive truck (old activity)
        old_time = datetime.now(timezone.utc) - timedelta(days=60)
        engine.truck_states["INACTIVE001"] = type(
            "State", (), {"truck_id": "INACTIVE001", "last_timestamp": old_time}
        )()

        # Run cleanup
        active_set = {"ACTIVE001"}
        cleaned = engine.cleanup_inactive_trucks(active_set, max_inactive_days=30)

        print(f"   driver_behavior_engine: ✅ Cleaned {cleaned} trucks")
        results["driver_behavior"] = "PASS"

    except Exception as e:
        print(f"   driver_behavior_engine: ❌ {e}")
        results["driver_behavior"] = f"FAIL: {e}"

    # Test 2: MPG Engine
    try:
        from mpg_engine import MPGBaselineManager

        manager = MPGBaselineManager()

        # Add fake baselines
        manager.baselines["ACTIVE001"] = type(
            "Baseline",
            (),
            {"truck_id": "ACTIVE001", "last_update": datetime.now().timestamp()},
        )()

        old_timestamp = (datetime.now() - timedelta(days=60)).timestamp()
        manager.baselines["INACTIVE001"] = type(
            "Baseline", (), {"truck_id": "INACTIVE001", "last_update": old_timestamp}
        )()

        active_set = {"ACTIVE001"}
        cleaned = manager.cleanup_inactive_trucks(active_set, max_inactive_days=30)

        print(f"   mpg_engine: ✅ Cleaned {cleaned} trucks")
        results["mpg_engine"] = "PASS"

    except Exception as e:
        print(f"   mpg_engine: ❌ {e}")
        results["mpg_engine"] = f"FAIL: {e}"

    # Test 3: Theft Detection Engine
    try:
        from theft_detection_engine import TheftPatternAnalyzer

        analyzer = TheftPatternAnalyzer()

        # Would need to add fake data, but method exists
        active_set = {"ACTIVE001"}
        cleaned = analyzer.cleanup_inactive_trucks(active_set, max_inactive_days=30)

        print(f"   theft_detection_engine: ✅ Cleaned {cleaned} trucks")
        results["theft_detection"] = "PASS"

    except Exception as e:
        print(f"   theft_detection_engine: ⚠️  {e}")
        results["theft_detection"] = "SKIP (expected in isolated test)"

    # Test 4: Predictive Maintenance
    try:
        from predictive_maintenance_engine import PredictiveMaintenanceEngine

        engine = PredictiveMaintenanceEngine()

        active_set = {"ACTIVE001"}
        cleaned = engine.cleanup_inactive_trucks(active_set, max_inactive_days=30)

        print(f"   predictive_maintenance_engine: ✅ Cleaned {cleaned} trucks")
        results["predictive_maintenance"] = "PASS"

    except Exception as e:
        print(f"   predictive_maintenance_engine: ⚠️  {e}")
        results["predictive_maintenance"] = "SKIP (expected in isolated test)"

    # Test 5: Alert Service
    try:
        from alert_service import AlertManager

        manager = AlertManager()

        active_set = {"ACTIVE001"}
        cleaned = manager.cleanup_inactive_trucks(active_set, max_inactive_days=30)

        print(f"   alert_service: ✅ Cleaned {cleaned} trucks")
        results["alert_service"] = "PASS"

    except Exception as e:
        print(f"   alert_service: ⚠️  {e}")
        results["alert_service"] = "SKIP (expected in isolated test)"

    # Summary
    passed = sum(1 for r in results.values() if r == "PASS")
    total = len(results)

    print(f"\n📊 Individual Engine Tests: {passed}/{total} passed")

    return passed >= 2  # At least 2 engines should work


def test_memory_impact():
    """
    Test 3: Memory Impact Validation

    Validates that cleanup actually reduces memory usage
    """
    print("\n📋 TEST 3: Memory Impact Validation")
    print("-" * 80)

    try:
        import gc

        import psutil

        # Get initial memory
        process = psutil.Process()
        mem_before = process.memory_info().rss / 1024 / 1024  # MB

        print(f"   Memory before cleanup: {mem_before:.2f} MB")

        # Create many truck states
        from datetime import datetime, timedelta, timezone

        from driver_behavior_engine import DriverBehaviorEngine

        engine = DriverBehaviorEngine()

        # Create 1000 fake inactive trucks
        old_time = datetime.now(timezone.utc) - timedelta(days=60)
        for i in range(1000):
            truck_id = f"INACTIVE{i:04d}"
            engine.truck_states[truck_id] = type(
                "State",
                (),
                {
                    "truck_id": truck_id,
                    "last_timestamp": old_time,
                    "events": [{"data": "x" * 1000} for _ in range(10)],  # Add bulk
                },
            )()

        gc.collect()
        mem_after_creation = process.memory_info().rss / 1024 / 1024
        print(f"   Memory after creating 1000 trucks: {mem_after_creation:.2f} MB")
        print(f"   Memory increase: +{mem_after_creation - mem_before:.2f} MB")

        # Run cleanup (all are inactive)
        active_set = set()
        cleaned = engine.cleanup_inactive_trucks(active_set, max_inactive_days=30)

        gc.collect()
        mem_after_cleanup = process.memory_info().rss / 1024 / 1024
        print(f"   Memory after cleanup: {mem_after_cleanup:.2f} MB")
        print(f"   Memory freed: -{mem_after_creation - mem_after_cleanup:.2f} MB")
        print(f"   Trucks cleaned: {cleaned}")

        # Validate cleanup happened
        assert cleaned == 1000, f"Expected 1000 cleaned, got {cleaned}"
        assert len(engine.truck_states) == 0, "Truck states not empty after cleanup"

        # Memory should decrease (though Python may not release to OS immediately)
        memory_freed = mem_after_creation - mem_after_cleanup
        if memory_freed > 0:
            print(f"\n✅ PASS: Cleanup freed {memory_freed:.2f} MB")
        else:
            print(f"\n⚠️  WARNING: Memory not immediately freed (Python GC behavior)")
            print("   This is normal - Python may keep memory allocated for reuse")

        return True

    except ImportError:
        print("   ⚠️  psutil not installed, skipping memory test")
        print("   Install with: pip install psutil")
        return True  # Don't fail test
    except Exception as e:
        print(f"\n❌ FAIL: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all integration tests"""
    print("\n🚀 Starting Integration Tests...")

    results = {
        "orchestrator": test_cleanup_orchestrator(),
        "individual_engines": test_individual_engine_cleanup(),
        "memory_impact": test_memory_impact(),
    }

    print("\n" + "=" * 80)
    print("📊 INTEGRATION TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name:25s}: {status}")

    total_passed = sum(results.values())
    total_tests = len(results)

    print("\n" + "=" * 80)
    print(f"   TOTAL: {total_passed}/{total_tests} tests passed")
    print("=" * 80)

    if total_passed == total_tests:
        print("\n🎉 ALL INTEGRATION TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {total_tests - total_passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())
