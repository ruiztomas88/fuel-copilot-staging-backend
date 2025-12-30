#!/usr/bin/env python3
"""
Script to fix ALL failing tests systematically
"""
import re
import subprocess
import sys


def get_failing_tests():
    """Run tests and get list of failing tests"""
    cmd = [
        "python3",
        "-m",
        "pytest",
        "tests/",
        "--ignore=tests/test_additional_coverage.py",
        "--ignore=tests/test_ai_audit_features.py",
        "--ignore=tests/test_lstm_maintenance.py",
        "--ignore=tests/test_ml_integration.py",
        "--ignore=tests/test_ml_router.py",
        "-v",
        "--tb=no",
        "-q",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend",
    )

    # Extract failed test names
    failed_tests = []
    for line in result.stdout.split("\n"):
        if "FAILED" in line or "ERROR" in line:
            # Extract test name
            match = re.search(r"(tests/[^ ]+::[^ ]+)", line)
            if match:
                failed_tests.append(match.group(1))

    return failed_tests, result.stdout


if __name__ == "__main__":
    failed, output = get_failing_tests()

    print(f"Found {len(failed)} failing tests:")
    for test in failed[:50]:  # First 50
        print(f"  - {test}")

    # Get summary
    for line in output.split("\n"):
        if "failed" in line.lower() or "passed" in line.lower():
            if "==" in line:
                print(f"\n{line}")
