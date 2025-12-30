#!/usr/bin/env python3
"""
Fast test execution - run tests and collect results
"""
import subprocess
import sys
from pathlib import Path

# Tests that are known to be fast (pure unit tests)
FAST_TESTS = [
    "test_settings.py",
    "test_timezone_utils.py",
    "test_terrain_factor.py",
    "test_terrain_mpg.py",
    "test_siphon_detector.py",
    "test_rul_predictor.py",
    "test_gps_quality.py",
    "test_gamification_engine.py",
    "test_fleet_utilization_engine.py",
    "test_cost_per_mile_engine.py",
    "test_mpg_context.py",
    "test_load_weather_factors.py",
    "test_voltage_monitor.py",
    "test_voltage_history.py",
    "test_input_validation.py",
    "test_structured_logging.py",
    "test_ecu_consumption.py",
]

# Tests that might be slow (integration, DB, API)
SKIP_TESTS = [
    "test_additional_coverage.py",
    "test_ai_audit_features.py",
    "test_api_endpoints.py",
    "test_api_endpoints_extended.py",
    "test_api_v2_endpoints_massive.py",
    "test_dashboard_endpoints.py",
    "test_main_api.py",
    "test_main_endpoints_complete.py",
    "test_bugfixes_v3_9_1.py",
    "test_critical_startup.py",
    "test_enabled_routers_coverage.py",
    "test_http_endpoints_massive.py",
    "test_routers_comprehensive.py",
    "test_coverage_boost.py",
]


def run_tests(test_files):
    """Run tests and return stats"""
    cmd = [
        "python3",
        "-m",
        "pytest",
        *[f"tests/{f}" for f in test_files],
        "-q",
        "--tb=no",
        "-x",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend",
    )

    # Parse output
    output = result.stdout + result.stderr
    lines = output.strip().split("\n")

    for line in lines:
        if "passed" in line:
            print(line)
            return result.returncode == 0

    print(output[-200:])
    return False


def main():
    tests_dir = Path("/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/tests")
    all_tests = sorted([f.name for f in tests_dir.glob("test_*.py")])

    # Filter tests
    tests_to_run = [t for t in all_tests if t not in SKIP_TESTS]

    print(
        f"Running {len(tests_to_run)} test files (skipping {len(SKIP_TESTS)} integration tests)"
    )
    print("=" * 80)

    # Run fast tests first
    fast_to_run = [t for t in FAST_TESTS if t in tests_to_run]
    print(f"\n1. Running {len(fast_to_run)} fast unit tests...")
    run_tests(fast_to_run)

    # Run remaining tests
    remaining = [t for t in tests_to_run if t not in FAST_TESTS]
    print(f"\n2. Running {len(remaining)} remaining tests...")
    run_tests(remaining)

    print("\n" + "=" * 80)
    print("Running ALL tests together for final count...")
    print("=" * 80)
    run_tests(tests_to_run)


if __name__ == "__main__":
    sys.exit(main())
