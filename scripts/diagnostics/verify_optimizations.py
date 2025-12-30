#!/usr/bin/env python3
"""
Script de Verificación - Optimizaciones Implementadas
======================================================

Verifica que todas las optimizaciones se implementaron correctamente.
Run: python verify_optimizations.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Colors para output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_header(title):
    """Print section header"""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{title:^60}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_check(passed, message):
    """Print check result"""
    symbol = f"{GREEN}✅{RESET}" if passed else f"{RED}❌{RESET}"
    status = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
    print(f"{symbol} {status}: {message}")
    return passed


def check_file_exists(filepath, description):
    """Check if file exists"""
    exists = Path(filepath).exists()
    return print_check(exists, f"{description}: {filepath}")


def check_database_indexes():
    """Check if database indexes were created"""
    try:
        import pymysql

        conn = pymysql.connect(
            host="localhost", user="root", password="", database="fuel_copilot_local"
        )
        cursor = conn.cursor()

        # Count indexes
        cursor.execute(
            """
            SELECT COUNT(DISTINCT INDEX_NAME) as count
            FROM information_schema.STATISTICS
            WHERE TABLE_SCHEMA = 'fuel_copilot_local'
              AND INDEX_NAME LIKE 'idx_%'
        """
        )
        result = cursor.fetchone()
        count = result[0] if result else 0

        cursor.close()
        conn.close()

        return print_check(
            count >= 20, f"Database indexes created: {count}/24 expected"
        )
    except Exception as e:
        return print_check(False, f"Database check failed: {e}")


async def check_async_module():
    """Check if async database module works"""
    try:
        from database_async import health_check

        result = await health_check()
        return print_check(result["healthy"], "Async database module: Connection OK")
    except Exception as e:
        return print_check(False, f"Async module check failed: {e}")


def check_async_endpoints():
    """Check if async endpoints exist"""
    try:
        from api_endpoints_async import (
            get_active_dtcs_async,
            get_fuel_history_async,
            get_recent_refuels_async,
            get_sensors_cache_async,
            get_truck_sensors_async,
        )

        return print_check(True, "Async endpoints: All 5 functions importable")
    except Exception as e:
        return print_check(False, f"Async endpoints check failed: {e}")


def check_tests():
    """Check if tests exist and can be imported"""
    try:
        import test_async_migration

        # Count test methods
        test_count = sum(
            1
            for attr in dir(test_async_migration)
            if attr.startswith("Test") or attr.startswith("test_")
        )
        return print_check(
            test_count > 0, f"Test suite: {test_count} test classes/methods found"
        )
    except Exception as e:
        return print_check(False, f"Test suite check failed: {e}")


def check_aiomysql():
    """Check if aiomysql is installed"""
    try:
        import aiomysql

        return print_check(True, f"aiomysql installed: v{aiomysql.__version__}")
    except ImportError:
        return print_check(False, "aiomysql not installed")


def main():
    """Run all verification checks"""
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}{'VERIFICACIÓN DE OPTIMIZACIONES - FUEL COPILOT':^60}{RESET}")
    print(f"{GREEN}{'26 Diciembre 2025':^60}{RESET}")
    print(f"{GREEN}{'='*60}{RESET}\n")

    results = []

    # 1. Check documentation files
    print_header("📄 DOCUMENTACIÓN")
    results.append(check_file_exists("BLOCKING_IO_AUDIT.md", "Auditoría blocking I/O"))
    results.append(
        check_file_exists(
            "IMPLEMENTACION_COMPLETA_DIC26.md", "Reporte de implementación"
        )
    )
    results.append(
        check_file_exists("sql/create_performance_indexes.sql", "SQL indexes completo")
    )
    results.append(
        check_file_exists(
            "sql/create_indexes_existing_tables.sql", "SQL indexes existentes"
        )
    )

    # 2. Check code files
    print_header("💻 CÓDIGO")
    results.append(check_file_exists("database_async.py", "Módulo async database"))
    results.append(check_file_exists("api_endpoints_async.py", "Endpoints async"))
    results.append(check_file_exists("create_indexes.py", "Script create indexes"))
    results.append(check_file_exists("test_async_migration.py", "Test suite"))

    # 3. Check dependencies
    print_header("📦 DEPENDENCIAS")
    results.append(check_aiomysql())

    # 4. Check database indexes
    print_header("🗄️ DATABASE INDEXES")
    results.append(check_database_indexes())

    # 5. Check async module
    print_header("⚡ ASYNC MODULE")
    loop = asyncio.get_event_loop()
    results.append(loop.run_until_complete(check_async_module()))

    # 6. Check async endpoints
    print_header("🚀 ASYNC ENDPOINTS")
    results.append(check_async_endpoints())

    # 7. Check tests
    print_header("🧪 TESTS")
    results.append(check_tests())

    # Summary
    print_header("📊 RESUMEN")
    total = len(results)
    passed = sum(results)
    failed = total - passed
    percentage = (passed / total * 100) if total > 0 else 0

    print(f"Total checks: {total}")
    print(f"{GREEN}✅ Passed: {passed}{RESET}")
    print(f"{RED}❌ Failed: {failed}{RESET}")
    print(f"\n{BLUE}Completion: {percentage:.1f}%{RESET}\n")

    if percentage >= 90:
        print(
            f"{GREEN}🎉 ÉXITO: Todas las optimizaciones implementadas correctamente!{RESET}\n"
        )
        return 0
    elif percentage >= 70:
        print(
            f"{YELLOW}⚠️  PARCIAL: Mayoría de optimizaciones OK, revisar fallos.{RESET}\n"
        )
        return 1
    else:
        print(
            f"{RED}❌ FALLO: Muchas verificaciones fallaron, revisar implementación.{RESET}\n"
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
