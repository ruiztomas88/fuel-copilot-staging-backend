#!/usr/bin/env python3
"""
final_validation.py - Validación Final de Implementación
═══════════════════════════════════════════════════════════════════════════════
Script para verificar que TODOS los cambios del roadmap están funcionando
"""

import subprocess
import sys
import time

import requests


def run_command(cmd, description):
    """Ejecutar comando y mostrar resultado"""
    print(f"\n🔍 {description}...")
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=30
        )
        if result.returncode == 0:
            print(f"   ✅ PASS")
            return True
        else:
            print(f"   ❌ FAIL: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"   ⚠️  ERROR: {e}")
        return False


def check_endpoint(url, description, expected_keys=None):
    """Verificar endpoint HTTP"""
    print(f"\n🌐 {description}...")
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if expected_keys:
                for key in expected_keys:
                    if key not in data and key not in str(data):
                        print(f"   ⚠️  Missing key: {key}")
                        return False
            print(f"   ✅ PASS (200 OK)")
            return True
        else:
            print(f"   ❌ FAIL: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"   ⚠️  ERROR: {e}")
        return False


def main():
    """Validación completa"""
    print("=" * 80)
    print("🎯 FUEL COPILOT - FINAL VALIDATION")
    print("=" * 80)

    passed = 0
    failed = 0

    # 1. Módulos de Seguridad
    print("\n" + "=" * 80)
    print("1️⃣  SECURITY MODULES")
    print("=" * 80)

    if run_command(
        "python -c 'from db_config import get_connection; print(\"OK\")'",
        "db_config module",
    ):
        passed += 1
    else:
        failed += 1

    if run_command(
        "python -c 'from sql_safe import whitelist_table; print(\"OK\")'",
        "sql_safe module",
    ):
        passed += 1
    else:
        failed += 1

    if run_command(
        "python db_config.py 2>&1 | grep -q 'Connection successful'",
        "Database connection",
    ):
        passed += 1
    else:
        failed += 1

    # 2. Algoritmos
    print("\n" + "=" * 80)
    print("2️⃣  ALGORITHM IMPROVEMENTS")
    print("=" * 80)

    if run_command(
        "python -c 'from algorithm_improvements import AdaptiveMPGEngine; print(\"OK\")'",
        "Adaptive MPG engine",
    ):
        passed += 1
    else:
        failed += 1

    if run_command(
        "python -c 'from algorithm_improvements import ExtendedKalmanFuelEstimator; print(\"OK\")'",
        "Extended Kalman Filter",
    ):
        passed += 1
    else:
        failed += 1

    if run_command(
        "python -c 'from algorithm_improvements import EnhancedTheftDetector; print(\"OK\")'",
        "Enhanced Theft Detector",
    ):
        passed += 1
    else:
        failed += 1

    # 3. API Endpoints
    print("\n" + "=" * 80)
    print("3️⃣  API ENDPOINTS")
    print("=" * 80)

    base_url = "http://localhost:8000/fuelAnalytics"

    if check_endpoint(f"{base_url}/api/fleet", "Fleet endpoint", ["total_trucks"]):
        passed += 1
    else:
        failed += 1

    if check_endpoint(
        f"{base_url}/api/kpis?days=7",
        "KPIs endpoint",
        ["total_moving_hours", "total_idle_hours"],
    ):
        passed += 1
    else:
        failed += 1

    if check_endpoint(
        f"{base_url}/api/truck-costs?days=7",
        "Truck costs endpoint",
        ["truckId", "totalMiles", "costPerMile"],
    ):
        passed += 1
    else:
        failed += 1

    if check_endpoint(
        f"{base_url}/api/truck-utilization?days=7",
        "Truck utilization endpoint",
        ["truckId", "activeHours", "idleHours"],
    ):
        passed += 1
    else:
        failed += 1

    # 4. Bare Excepts Fixed
    print("\n" + "=" * 80)
    print("4️⃣  BARE EXCEPT FIXES")
    print("=" * 80)

    files_to_check = [
        "fleet_command_center.py",
        "wialon_sync_enhanced.py",
        "wialon_api_client.py",
        "benchmarking_engine.py",
        "driver_scoring_engine.py",
    ]

    for file in files_to_check:
        # Check que no tiene 'except:' sin tipo
        if run_command(
            f"! grep -q '^[[:space:]]*except:[[:space:]]*$' {file}",
            f"No bare except in {file}",
        ):
            passed += 1
        else:
            failed += 1

    # 5. Integration Tests
    print("\n" + "=" * 80)
    print("5️⃣  INTEGRATION TESTS")
    print("=" * 80)

    if run_command(
        "python integration_tests.py 2>&1 | grep -q 'ALL TESTS PASSED'",
        "Integration test suite",
    ):
        passed += 1
    else:
        failed += 1

    # Summary
    print("\n" + "=" * 80)
    print("📊 VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total:  {passed + failed}")
    print(f"Success Rate: {passed / (passed + failed) * 100:.1f}%")

    if failed == 0:
        print("\n🎉 ALL VALIDATIONS PASSED - READY FOR PRODUCTION!")
        print("\n✅ Roadmap completamente implementado:")
        print("   • Seguridad (db_config, sql_safe)")
        print("   • Bare excepts corregidos")
        print("   • Algoritmos mejorados (MPG, EKF, Theft)")
        print("   • Nuevos endpoints (costs, utilization)")
        print("   • Tests de integración")
        return 0
    else:
        print(f"\n⚠️  {failed} VALIDATIONS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
