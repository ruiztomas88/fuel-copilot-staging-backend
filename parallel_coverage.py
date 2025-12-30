#!/usr/bin/env python3
"""
Ejecuta coverage de TODOS los módulos backend en paralelo
Genera reporte JSON con resultados completos
"""

import concurrent.futures
import json
import subprocess
import sys
from datetime import datetime

# Todos los módulos Python del backend
ALL_MODULES = [
    ("auth", "tests/test_auth.py"),
    ("database_mysql", "tests/test_database_mysql*.py"),
    ("cache_service", "tests/test_cache_service.py"),
    ("alert_service", "tests/test_alert*.py"),
    ("driver_scoring_engine", "tests/test_driver_scoring*.py"),
    ("mpg_engine", "tests/test_mpg_engine.py"),
    ("theft_detection_engine", "tests/test_siphon*.py tests/test_theft*.py"),
    (
        "predictive_maintenance_engine",
        "tests/test_predictive_maintenance*.py tests/test_pm*.py",
    ),
    (
        "driver_behavior_engine",
        "tests/test_driver_behavior*.py tests/test_driver_coaching.py",
    ),
    ("idle_engine", "tests/test_idle*.py"),
    ("gamification_engine", "tests/test_gamification*.py"),
    ("api_middleware", "tests/test_api_middleware.py"),
    ("wialon_data_loader", "tests/test_wialon*.py"),
    ("fleet_command_center", "tests/test_fleet_command*.py"),
    ("models", "tests/test_models*.py"),
]


def run_coverage_for_module(module_info):
    """Ejecuta coverage para un módulo"""
    module_name, test_pattern = module_info

    cmd = f"python -m pytest {test_pattern} --cov={module_name} --cov-report=term-missing:skip-covered -q --tb=no 2>&1"

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=60,
            cwd="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend",
        )

        # Parse coverage percentage
        coverage_pct = None
        for line in result.stdout.split("\n"):
            if "TOTAL" in line and "%" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if "%" in part:
                        try:
                            coverage_pct = int(part.replace("%", ""))
                        except:
                            pass
                        break

        # Parse test counts
        tests_passed = 0
        tests_failed = 0
        for line in result.stdout.split("\n"):
            if " passed" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "passed":
                        try:
                            tests_passed = int(parts[i - 1])
                        except:
                            pass
            if " failed" in line:
                parts = line.split()
                for i, part in enumerate(parts):
                    if part == "failed":
                        try:
                            tests_failed = int(parts[i - 1])
                        except:
                            pass

        return {
            "module": module_name,
            "coverage_pct": coverage_pct,
            "tests_passed": tests_passed,
            "tests_failed": tests_failed,
            "status": "success" if coverage_pct is not None else "no_data",
        }

    except subprocess.TimeoutExpired:
        return {
            "module": module_name,
            "coverage_pct": None,
            "tests_passed": 0,
            "tests_failed": 0,
            "status": "timeout",
        }
    except Exception as e:
        return {
            "module": module_name,
            "coverage_pct": None,
            "tests_passed": 0,
            "tests_failed": 0,
            "status": "error",
            "error": str(e),
        }


def main():
    print("=" * 80)
    print("🚀 PARALLEL BACKEND COVERAGE - All Modules")
    print("=" * 80)
    print(f"\nProcessing {len(ALL_MODULES)} modules in parallel...")
    print()

    start_time = datetime.now()

    # Execute in parallel (max 4 workers to avoid overloading)
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        results = list(executor.map(run_coverage_for_module, ALL_MODULES))

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    # Sort by coverage percentage
    results_with_coverage = [r for r in results if r["coverage_pct"] is not None]
    results_with_coverage.sort(key=lambda x: x["coverage_pct"], reverse=True)

    results_no_coverage = [r for r in results if r["coverage_pct"] is None]

    # Print results
    print("=" * 80)
    print("📊 RESULTS")
    print("=" * 80)
    print()

    if results_with_coverage:
        print("✅ Modules with Coverage Data:")
        print()
        for r in results_with_coverage:
            status_icon = (
                "✅"
                if r["coverage_pct"] >= 80
                else "⚠️" if r["coverage_pct"] >= 60 else "❌"
            )
            print(
                f"  {r['module']:40s} {r['coverage_pct']:>3d}%  ({r['tests_passed']} passed, {r['tests_failed']} failed)  {status_icon}"
            )
        print()

    if results_no_coverage:
        print("⚠️  Modules without Coverage Data:")
        print()
        for r in results_no_coverage:
            print(
                f"  {r['module']:40s} {r['status']:>15s}  ({r['tests_passed']} passed, {r['tests_failed']} failed)"
            )
        print()

    # Summary statistics
    total_modules = len(results)
    modules_with_data = len(results_with_coverage)
    modules_80_plus = len([r for r in results_with_coverage if r["coverage_pct"] >= 80])
    avg_coverage = (
        sum(r["coverage_pct"] for r in results_with_coverage)
        / len(results_with_coverage)
        if results_with_coverage
        else 0
    )

    print("=" * 80)
    print("📈 SUMMARY")
    print("=" * 80)
    print(f"  Total modules tested:        {total_modules}")
    print(f"  Modules with coverage data:  {modules_with_data}")
    print(f"  Modules ≥80% coverage:       {modules_80_plus}")
    print(f"  Average coverage:            {avg_coverage:.1f}%")
    print(f"  Execution time:              {duration:.1f}s")
    print("=" * 80)

    # Save JSON report
    report = {
        "timestamp": start_time.isoformat(),
        "duration_seconds": duration,
        "total_modules": total_modules,
        "modules_with_coverage": modules_with_data,
        "modules_80_plus": modules_80_plus,
        "average_coverage": round(avg_coverage, 2),
        "results": results,
    }

    output_file = "parallel_coverage_results.json"
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)

    print(f"\n💾 Full report saved to: {output_file}\n")

    return 0 if modules_80_plus >= (total_modules * 0.8) else 1


if __name__ == "__main__":
    sys.exit(main())
