#!/usr/bin/env python3
"""
🚀 FAST COVERAGE RUNNER - Target 90% on Main Modules
====================================================

Ejecuta tests rápidos y genera reporte de cobertura.
Enfocado en módulos principales del backend.

Author: Fuel Analytics Team
Date: December 28, 2025
"""

import json
import subprocess
import sys
import time
from pathlib import Path

# Módulos principales a testear
MAIN_MODULES = [
    "database_mysql",
    "mpg_engine",
    "alert_service",
    "driver_behavior_engine",
    "dtc_database",
    "predictive_maintenance_v3",
]

# Tests específicos por módulo (más rápidos)
MODULE_TESTS = {
    "database_mysql": "tests/test_database_mysql_comprehensive_90pct.py",
    "mpg_engine": "tests/test_mpg_engine.py tests/test_mpg_engine_100pct.py",
    "alert_service": "tests/test_alert_service.py tests/test_alert_service_100pct.py",
    "driver_behavior_engine": "tests/test_driver_behavior_comprehensive.py",
    "dtc_database": "tests/test_dtc_database_v5_7_6.py",
    "predictive_maintenance_v3": "tests/test_predictive_maintenance_100pct.py",
}

print("=" * 80)
print("🎯 BACKEND COVERAGE ANALYSIS - 90% TARGET")
print("=" * 80)
print()

results = {}

for module in MAIN_MODULES:
    test_files = MODULE_TESTS.get(module, f"tests/test_{module}*.py")

    print(f"📊 Testing {module}...")
    print(f"   Test files: {test_files}")

    start = time.time()

    try:
        # Run pytest with coverage
        cmd = f"python3 -m pytest {test_files} --cov={module} --cov-report=json:coverage_{module}.json -q --tb=no --maxfail=3 --timeout=30 2>&1"

        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=60
        )

        # Try to read coverage
        cov_file = Path(f"coverage_{module}.json")
        if cov_file.exists():
            with open(cov_file) as f:
                data = json.load(f)
                pct = data.get("totals", {}).get("percent_covered", 0)
                results[module] = {
                    "coverage": pct,
                    "status": "✅" if pct >= 90 else "⚠️",
                    "time": time.time() - start,
                }
                print(
                    f"   {results[module]['status']} Coverage: {pct:.1f}% ({time.time() - start:.1f}s)"
                )
        else:
            # Fallback: grep from output
            output = result.stdout + result.stderr
            if "TOTAL" in output:
                # Try to extract percentage
                for line in output.split("\n"):
                    if "TOTAL" in line:
                        try:
                            pct = float(line.split()[-1].rstrip("%"))
                            results[module] = {
                                "coverage": pct,
                                "status": "✅" if pct >= 90 else "⚠️",
                                "time": time.time() - start,
                            }
                            print(
                                f"   {results[module]['status']} Coverage: {pct:.1f}% ({time.time() - start:.1f}s)"
                            )
                        except:
                            pass
                        break

            if module not in results:
                results[module] = {
                    "coverage": 0,
                    "status": "❌",
                    "time": time.time() - start,
                }
                print(f"   ❌ No coverage data ({time.time() - start:.1f}s)")

    except subprocess.TimeoutExpired:
        results[module] = {"coverage": 0, "status": "⏱️", "time": 60}
        print(f"   ⏱️  Timeout (>60s)")

    except Exception as e:
        results[module] = {"coverage": 0, "status": "❌", "time": time.time() - start}
        print(f"   ❌ Error: {str(e)[:50]}")

    print()

# Summary
print("=" * 80)
print("📈 COVERAGE SUMMARY")
print("=" * 80)
print()

total_coverage = 0
count = 0

for module, data in sorted(
    results.items(), key=lambda x: x[1]["coverage"], reverse=True
):
    status = data["status"]
    pct = data["coverage"]
    time_taken = data["time"]

    total_coverage += pct
    count += 1

    print(f"{status} {module:40s} {pct:6.1f}%  ({time_taken:5.1f}s)")

if count > 0:
    avg_coverage = total_coverage / count
    print()
    print("=" * 80)
    print(f"🎯 AVERAGE COVERAGE: {avg_coverage:.1f}%")
    print(f"🎯 TARGET: 90.0%")
    print(f"🎯 STATUS: {'✅ MET' if avg_coverage >= 90 else '⚠️ NEEDS WORK'}")
    print("=" * 80)

# Export results
with open("coverage_summary.json", "w") as f:
    json.dump(
        {
            "results": results,
            "average": avg_coverage if count > 0 else 0,
            "target": 90.0,
            "timestamp": time.time(),
        },
        f,
        indent=2,
    )

print()
print("✅ Results saved to coverage_summary.json")
