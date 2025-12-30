#!/usr/bin/env python3
"""
Script to run specific failed tests
"""
import subprocess
import sys

# Tests que fallaron en el primer run
failed_tests = [
    "tests/test_fleet_complete.py",
    "tests/test_fleet_command_methods.py",
    "tests/test_fuel_estimator.py",
    "tests/test_gps_notifications.py",
    "tests/test_high_impact.py",
    "tests/test_http_endpoints_massive.py",
    "tests/test_idle_engine.py",
    "tests/test_loss_analysis_v6_3_0.py",
    "tests/test_lstm_maintenance.py",
    "tests/test_ml_integration.py",
    "tests/test_ml_router.py",
    "tests/test_mpg_baseline_service.py",
    "tests/test_mpg_baseline_v5_7_6.py",
    "tests/test_new_algorithms.py",
    "tests/test_predictive_complete.py",
    "tests/test_predictive_engine_core.py",
    "tests/test_predictive_maintenance_simple.py",
    "tests/test_realtime_predictive_engine.py",
    "tests/test_routers_comprehensive.py",
    "tests/test_truck_repository.py",
    "tests/test_v7_1_comprehensive.py",
    "tests/test_wialon_comprehensive.py",
    "tests/test_wialon_reader.py",
]


def main():
    print(f"Running {len(failed_tests)} failed tests...")

    cmd = ["python3", "-m", "pytest", *failed_tests, "-v", "--tb=short", "-x"]

    result = subprocess.run(cmd, cwd="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
