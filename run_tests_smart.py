#!/usr/bin/env python3
"""
Run tests in batches with timeout to identify hanging tests
"""
import signal
import subprocess
import sys
import time
from pathlib import Path


def run_test_batch(test_files, timeout=120):
    """Run a batch of tests with timeout"""
    cmd = [
        "python3",
        "-m",
        "pytest",
        *test_files,
        "-q",
        "--tb=no",
        "-x",
        "--ignore=tests/test_additional_coverage.py",
        "--ignore=tests/test_ai_audit_features.py",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend",
        )
        return True, result.returncode, result.stdout + result.stderr
    except subprocess.TimeoutExpired:
        return False, -1, f"TIMEOUT after {timeout}s"


def main():
    tests_dir = Path("/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/tests")
    test_files = sorted([f for f in tests_dir.glob("test_*.py")])

    # Exclude problematic files
    exclude = ["test_additional_coverage.py", "test_ai_audit_features.py"]
    test_files = [f for f in test_files if f.name not in exclude]

    print(f"Found {len(test_files)} test files")

    # Run in batches of 10
    batch_size = 10
    hanging_tests = []
    failed_batches = []

    for i in range(0, len(test_files), batch_size):
        batch = test_files[i : i + batch_size]
        batch_names = [f.name for f in batch]

        print(f"\n{'='*80}")
        print(
            f"Batch {i//batch_size + 1}/{(len(test_files)-1)//batch_size + 1}: {batch_names[0]} ... {batch_names[-1]}"
        )
        print(f"{'='*80}")

        success, code, output = run_test_batch(batch, timeout=60)

        if not success:
            print(f"⏱️  TIMEOUT - Testing individually...")
            # Test each file individually to find the culprit
            for test_file in batch:
                print(f"  Testing {test_file.name}...", end=" ")
                success_individual, code_individual, _ = run_test_batch(
                    [test_file], timeout=30
                )
                if not success_individual:
                    print(f"⏱️  HANGS")
                    hanging_tests.append(test_file.name)
                elif code_individual != 0:
                    print(f"❌ FAILS")
                else:
                    print(f"✅ PASS")
        elif code != 0:
            print(f"❌ Batch has failures")
            failed_batches.append((batch_names, output[-500:]))
        else:
            print(f"✅ Batch passed")

    # Summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")

    if hanging_tests:
        print(f"\n⏱️  HANGING TESTS ({len(hanging_tests)}):")
        for test in hanging_tests:
            print(f"  - {test}")

    if failed_batches:
        print(f"\n❌ FAILED BATCHES ({len(failed_batches)}):")
        for names, _ in failed_batches:
            print(f"  - {names[0]} ... {names[-1]}")

    return 0 if not hanging_tests else 1


if __name__ == "__main__":
    sys.exit(main())
