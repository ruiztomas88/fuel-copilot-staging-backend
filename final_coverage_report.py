#!/usr/bin/env python3
"""
Genera reporte final de coverage backend - RAPIDO
Solo módulos críticos con tiempos optimizados
"""

import subprocess
import sys

MODULES = [
    ("auth", "tests/test_auth.py"),
    ("database_mysql", "tests/test_database_mysql*.py"),
    ("cache_service", "tests/test_cache_service.py"),
    ("mpg_engine", "tests/test_mpg_engine.py"),
    ("driver_scoring_engine", "tests/test_driver_scoring*.py"),
    ("alert_service", "tests/test_alert_service.py tests/test_alert_advanced.py"),
    (
        "predictive_maintenance_engine",
        "tests/test_predictive_maintenance*.py tests/test_pm*.py",
    ),
    ("models", "tests/test_models*.py"),
]

print("=" * 80)
print("📊 BACKEND COVERAGE REPORT - Critical Modules")
print("=" * 80)
print()

total_tested = 0
total_passed = 0

for module, test_pattern in MODULES:
    try:
        cmd = f"python -m pytest {test_pattern} --cov={module} --cov-report=term-missing:skip-covered -q --tb=no 2>&1"
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )

        # Extract coverage percentage
        coverage_pct = "N/A"
        for line in result.stdout.split("\n"):
            if "TOTAL" in line and "%" in line:
                parts = line.split()
                for part in parts:
                    if "%" in part:
                        coverage_pct = part
                        break

        # Extract test results
        test_info = ""
        for line in result.stdout.split("\n"):
            if " passed" in line:
                test_info = line.strip()
                break

        status = (
            "✅"
            if coverage_pct != "N/A" and int(coverage_pct.replace("%", "")) >= 80
            else "⚠️"
        )
        print(f"{module:40s} {coverage_pct:>6s}  {status}")

        total_tested += 1
        if coverage_pct != "N/A" and int(coverage_pct.replace("%", "")) >= 80:
            total_passed += 1

    except subprocess.TimeoutExpired:
        print(f"{module:40s} TIMEOUT ⏰")
    except Exception as e:
        print(f"{module:40s} ERROR ❌")

print()
print("=" * 80)
print(f"Summary: {total_passed}/{total_tested} modules with ≥80% coverage")
print("=" * 80)
