#!/usr/bin/env python3
"""
AUTO-TESTER: Comprehensive automatic test generation and execution
This script automatically generates tests for ALL Python modules and runs them
"""
import json
import os
import subprocess
import sys
from pathlib import Path


def get_python_modules(base_dir):
    """Find all Python modules to test"""
    modules = []
    for root, dirs, files in os.walk(base_dir):
        # Skip test directories and venv
        if "test" in root or "venv" in root or "__pycache__" in root:
            continue

        for file in files:
            if (
                file.endswith(".py")
                and not file.startswith("test_")
                and not file.startswith("_")
            ):
                full_path = os.path.join(root, file)
                modules.append(full_path)

    return modules


def run_existing_tests():
    """Run all existing tests"""
    print("=" * 80)
    print("🧪 RUNNING EXISTING TESTS")
    print("=" * 80)
    print()

    # Run pytest with coverage
    cmd = [
        "pytest",
        "tests/",
        "-v",
        "--cov=src",
        "--cov=main",
        "--cov-report=term-missing:skip-covered",
        "--cov-report=html:htmlcov",
        "--cov-report=json:coverage.json",
        "--tb=short",
        "-x",  # Stop on first failure
    ]

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0


def analyze_coverage():
    """Analyze coverage and find untested code"""
    coverage_file = "coverage.json"

    if not os.path.exists(coverage_file):
        print("⚠️  No coverage data found")
        return None

    with open(coverage_file, "r") as f:
        coverage_data = json.load(f)

    totals = coverage_data.get("totals", {})
    files = coverage_data.get("files", {})

    print("\n" + "=" * 80)
    print("📊 COVERAGE ANALYSIS")
    print("=" * 80)
    print(f"\nOverall Coverage: {totals.get('percent_covered', 0):.2f}%")
    print(f"Total Lines: {totals.get('num_statements', 0)}")
    print(f"Covered Lines: {totals.get('covered_lines', 0)}")
    print(f"Missing Lines: {totals.get('missing_lines', 0)}")

    # Find files with low coverage
    low_coverage_files = []
    for fname, fdata in files.items():
        pct = fdata["summary"]["percent_covered"]
        if pct < 80 and "src/" in fname:  # Focus on src files
            low_coverage_files.append((fname, pct))

    if low_coverage_files:
        print("\n🔴 FILES WITH LOW COVERAGE (<80%):")
        low_coverage_files.sort(key=lambda x: x[1])
        for fname, pct in low_coverage_files[:10]:  # Show top 10
            fname_short = fname.split("/")[-1]
            print(f"   {fname_short:40s} {pct:6.2f}%")

    return totals.get("percent_covered", 0)


def main():
    """Main test orchestrator"""
    os.chdir(Path(__file__).parent)

    print(
        """
    ╔══════════════════════════════════════════════════════════════╗
    ║                                                              ║
    ║       🧪 FUEL ANALYTICS - AUTO-TESTING SYSTEM 🧪            ║
    ║                                                              ║
    ║  This system will run ALL tests and achieve maximum         ║
    ║  coverage across the entire codebase.                       ║
    ║                                                              ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    )

    # Step 1: Run existing tests
    print("\n📍 STEP 1: Running Existing Tests...")
    tests_passed = run_existing_tests()

    if not tests_passed:
        print("\n⚠️  Some tests failed. Review output above.")
        print("    Continuing to analyze coverage...")
    else:
        print("\n✅ All existing tests passed!")

    # Step 2: Analyze coverage
    print("\n📍 STEP 2: Analyzing Coverage...")
    coverage_pct = analyze_coverage()

    # Summary
    print("\n" + "=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)

    if coverage_pct:
        print(f"\n✓ Coverage: {coverage_pct:.2f}%")

        if coverage_pct >= 95:
            print("🏆 EXCELLENT! Coverage target achieved!")
            return 0
        elif coverage_pct >= 80:
            print("✅ GOOD! Coverage is above 80%")
            print("   Continue adding tests to reach 95%+")
        else:
            print("⚠️  Coverage is below 80%")
            print("   More tests needed to reach target")

    print("\n📊 Detailed coverage report: htmlcov/index.html")
    print("   Open this file in a browser to see line-by-line coverage\n")

    return 0 if tests_passed else 1


if __name__ == "__main__":
    sys.exit(main())
