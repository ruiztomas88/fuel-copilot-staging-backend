#!/usr/bin/env python3
"""
Generate coverage report by module
"""
import json
import subprocess
from pathlib import Path

# Core modules to test
MODULES = {
    "driver_scoring_engine": [
        "tests/test_driver_scoring.py",
        "tests/test_driver_scoring_integration.py",
    ],
    "dtc_analyzer": ["tests/test_dtc_analyzer.py", "tests/test_dtc_database*.py"],
    "predictive_maintenance_engine": ["tests/test_predictive_maintenance.py"],
    "mpg_engine": ["tests/test_mpg_engine.py", "tests/test_mpg_context.py"],
    "estimator": ["tests/test_fuel_estimator.py", "tests/test_estimator_edge_cases.py"],
    "alert_service": ["tests/test_alert*.py"],
    "mpg_baseline_service": ["tests/test_mpg_baseline*.py"],
    "voltage_monitor": ["tests/test_voltage*.py"],
    "theft_detection_service": ["tests/test_theft*.py"],
    "gamification_engine": ["tests/test_gamification*.py"],
    "siphon_detector": ["tests/test_siphon*.py"],
}


def get_coverage(module, test_patterns):
    """Get coverage for a module"""
    # Expand patterns
    test_files = []
    tests_dir = Path("tests")
    for pattern in test_patterns:
        if "*" in pattern:
            test_files.extend(tests_dir.glob(pattern.replace("tests/", "")))
        else:
            test_files.append(Path(pattern))

    test_files = [str(f) for f in test_files if f.exists()]

    if not test_files:
        return None, 0, 0, 0

    cmd = [
        "python3",
        "-m",
        "pytest",
        f"--cov={module}",
        "--cov-report=json",
        *test_files,
        "-q",
        "--tb=no",
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend",
    )

    # Parse JSON coverage
    try:
        with open("/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/coverage.json") as f:
            data = json.load(f)

        # Find module in files
        for file_path, file_data in data["files"].items():
            if module in file_path:
                summary = file_data["summary"]
                return (
                    summary["percent_covered"],
                    summary["num_statements"],
                    summary["covered_lines"],
                    summary["missing_lines"],
                )
    except:
        pass

    # Fallback: parse output
    for line in result.stdout.split("\n"):
        if module in line and "%" in line:
            parts = line.split()
            for i, part in enumerate(parts):
                if "%" in part:
                    return float(part.replace("%", "")), 0, 0, 0

    return None, 0, 0, 0


def main():
    print("=" * 80)
    print("COVERAGE REPORT BY MODULE")
    print("=" * 80)

    results = {}

    for module, tests in MODULES.items():
        print(f"\nTesting {module}...", end=" ")
        coverage, statements, covered, missing = get_coverage(module, tests)

        if coverage is not None:
            results[module] = {
                "coverage": coverage,
                "statements": statements,
                "covered": covered,
                "missing": missing,
            }
            print(f"{coverage:.2f}%")
        else:
            print("ERROR")

    # Summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"{'Module':<40} {'Coverage':>10} {'Status':>10}")
    print("-" * 80)

    total_coverage = (
        sum(r["coverage"] for r in results.values()) / len(results) if results else 0
    )

    for module, data in sorted(
        results.items(), key=lambda x: x[1]["coverage"], reverse=True
    ):
        status = (
            "✅" if data["coverage"] >= 80 else "⚠️" if data["coverage"] >= 60 else "❌"
        )
        print(f"{module:<40} {data['coverage']:>9.2f}% {status:>10}")

    print("-" * 80)
    print(f"{'AVERAGE':<40} {total_coverage:>9.2f}%")
    print("=" * 80)


if __name__ == "__main__":
    main()
