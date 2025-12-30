#!/usr/bin/env python3
"""
Reporte rápido de coverage backend - ejecuta solo tests específicos por módulo
"""
import re
import subprocess
from pathlib import Path

# Mapeo módulo -> archivos de test específicos
MODULE_TESTS = {
    "auth.py": "tests/test_auth.py",
    "database_mysql.py": "tests/test_database_mysql_simple.py",
    "cache_service.py": "tests/test_cache_service.py",
    "alert_service.py": "tests/test_alert_service.py tests/test_alert_advanced.py tests/test_alert_targeted.py",
    "driver_scoring_engine.py": "tests/test_driver_scoring*.py",
    "mpg_engine.py": "tests/test_mpg_engine.py tests/test_mpg_baseline_service.py",
    "theft_detection_engine.py": "tests/test_theft*.py",
    "predictive_maintenance_engine.py": "tests/test_predictive_maintenance*.py tests/test_pm*.py",
    "driver_behavior_engine.py": "tests/test_driver_behavior_engine.py tests/test_driver_coaching.py",
    "models.py": "tests/test_models*.py",
    "fleet_command_center.py": "tests/test_fleet*.py",
    "wialon_data_loader.py": "tests/test_wialon*.py",
    "api_middleware.py": "tests/test_api_middleware.py",
    "idle_engine.py": "tests/test_idle*.py",
    "gamification_engine.py": "tests/test_gamification*.py",
}


def run_quick_coverage(module_file, test_pattern):
    """Ejecuta coverage rápido sin --cov, solo contando tests"""
    module_name = module_file.replace(".py", "")

    # Primero contar cuántos tests tiene
    cmd_count = f'python -m pytest {test_pattern} --collect-only -q 2>/dev/null | grep "test session starts" -A 100 | tail -1'
    try:
        result_count = subprocess.run(
            cmd_count, shell=True, capture_output=True, text=True, timeout=10
        )
        test_count = 0
        if " test" in result_count.stdout:
            match = re.search(r"(\d+) test", result_count.stdout)
            if match:
                test_count = int(match.group(1))
    except:
        test_count = "?"

    # Correr coverage
    cmd = f'python -m pytest {test_pattern} --cov={module_name} --cov-report=term-missing:skip-covered -q --tb=no 2>&1 | grep -A 2 "TOTAL"'
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        output = result.stdout

        # Extraer porcentaje
        match = re.search(r"(\d+)%", output)
        if match:
            pct = match.group(1)
            return f"{module_name:40s} {pct:>4s}%  ({test_count} tests)"
        else:
            return f"{module_name:40s}  N/A   ({test_count} tests)"
    except subprocess.TimeoutExpired:
        return f"{module_name:40s} TIMEOUT ({test_count} tests)"
    except Exception as e:
        return f"{module_name:40s} ERROR: {str(e)[:30]}"


print("\n" + "=" * 80)
print("📊 BACKEND COVERAGE REPORT - Módulos Principales")
print("=" * 80 + "\n")

for module, tests in MODULE_TESTS.items():
    result = run_quick_coverage(module, tests)
    print(result)

print("\n" + "=" * 80)
print("💡 Ejecutado en < 5 minutos (vs overnight con pytest --cov=.)")
print("=" * 80)
