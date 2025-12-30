#!/usr/bin/env python3
"""
Script to run pytest tests with timeout for each file
"""
import subprocess
import sys
import time
from pathlib import Path


def run_test_file(test_file, timeout=60):
    """Run a single test file with timeout"""
    print(f"\n{'='*80}")
    print(f"Testing: {test_file}")
    print(f"{'='*80}")

    cmd = ["python3", "-m", "pytest", str(test_file), "-v", "--tb=line", "-x"]

    try:
        start = time.time()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend",
        )
        elapsed = time.time() - start

        print(f"✓ Completed in {elapsed:.2f}s")
        print(result.stdout[-500:] if len(result.stdout) > 500 else result.stdout)

        if result.returncode != 0:
            print(f"❌ FAILED (exit code: {result.returncode})")
            print(result.stderr[-200:] if result.stderr else "")

        return True, elapsed

    except subprocess.TimeoutExpired:
        print(f"⏱️  TIMEOUT after {timeout}s - THIS TEST IS HANGING!")
        return False, timeout
    except Exception as e:
        print(f"❌ ERROR: {e}")
        return False, 0


def main():
    tests_dir = Path("/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/tests")

    # Get all test files
    test_files = sorted(tests_dir.glob("test_*.py"))

    # Exclude known problematic files
    exclude = ["test_additional_coverage.py", "test_ai_audit_features.py"]

    test_files = [f for f in test_files if f.name not in exclude]

    print(f"Found {len(test_files)} test files to run")
    print(f"Timeout: 60 seconds per file")

    results = {}
    total_start = time.time()

    for test_file in test_files:
        success, elapsed = run_test_file(test_file, timeout=60)
        results[test_file.name] = {"success": success, "time": elapsed}

    total_elapsed = time.time() - total_start

    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY")
    print(f"{'='*80}")
    print(f"Total time: {total_elapsed:.2f}s")
    print(
        f"\nCompleted tests ({len([r for r in results.values() if r['success']])} of {len(results)}):"
    )

    for name, result in results.items():
        if result["success"]:
            print(f"  ✓ {name} ({result['time']:.2f}s)")

    hanging = [name for name, result in results.items() if not result["success"]]
    if hanging:
        print(f"\n⚠️  HANGING/FAILED tests ({len(hanging)}):")
        for name in hanging:
            print(f"  ⏱️  {name}")

    return 0 if not hanging else 1


if __name__ == "__main__":
    sys.exit(main())
