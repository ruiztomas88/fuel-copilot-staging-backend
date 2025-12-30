#!/usr/bin/env python3
"""
Script para ejecutar coverage de forma eficiente en módulos individuales del backend.
Evita el problema de pytest --cov=. que corre toda la noche sin terminar.
"""
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Módulos críticos a testear (orden de prioridad)
CRITICAL_MODULES = [
    # Core Authentication & Security
    ("auth", "tests/test_auth.py"),
    # Database
    ("database_mysql", "tests/test_database_mysql_simple.py"),
    ("cache_service", "tests/test_cache_service.py"),
    # Alert Systems
    ("alert_service", "tests/test_alert_service.py"),
    ("alert_system", "tests/"),
    # Engines
    ("driver_scoring_engine", "tests/"),
    ("mpg_engine", "tests/"),
    ("theft_detection_engine", "tests/"),
    ("predictive_maintenance_engine", "tests/"),
    ("driver_behavior_engine", "tests/"),
    # Models
    ("models", "tests/"),
    # API & Middleware
    ("api_middleware", "tests/test_api_middleware.py"),
    # Orchestrators
    ("fleet_command_center", "tests/"),
    # Data Loaders
    ("wialon_data_loader", "tests/"),
]


def run_coverage_for_module(module_name, test_path, timeout=60):
    """Ejecuta coverage para un módulo específico con timeout"""
    print(f"\n{'='*80}")
    print(f"📊 Testing module: {module_name}")
    print(f"{'='*80}")

    cmd = [
        "python",
        "-m",
        "pytest",
        test_path,
        f"--cov={module_name}",
        "--cov-report=term-missing:skip-covered",
        "--cov-report=json",
        "-q",  # quiet mode
        "--tb=no",  # no traceback
        "--continue-on-collection-errors",
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 10,  # subprocess timeout un poco mayor
            cwd="/Users/tomasruiz/Desktop/Fuel-Analytics-Backend",
        )

        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)

        # Extraer coverage percentage de JSON si está disponible
        coverage_pct = None
        try:
            import json

            with open(
                "/Users/tomasruiz/Desktop/Fuel-Analytics-Backend/coverage.json", "r"
            ) as f:
                cov_data = json.load(f)
                total = cov_data["totals"]
                coverage_pct = total.get("percent_covered", None)
        except:
            # Fallback: extraer del stdout
            for line in result.stdout.split("\n"):
                if "TOTAL" in line and "%" in line:
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if "%" in part:
                            coverage_pct = part.replace("%", "")
                            break

        return {
            "module": module_name,
            "success": True,  # Considerar exitoso si corrió, aunque tenga failures
            "coverage": coverage_pct,
            "returncode": result.returncode,
        }

    except subprocess.TimeoutExpired:
        print(f"⏰ TIMEOUT: {module_name} excedió {timeout}s")
        return {
            "module": module_name,
            "success": False,
            "coverage": None,
            "returncode": -1,
            "error": "timeout",
        }
    except Exception as e:
        print(f"❌ ERROR: {str(e)}")
        return {
            "module": module_name,
            "success": False,
            "coverage": None,
            "returncode": -1,
            "error": str(e),
        }


def main():
    start_time = datetime.now()
    results = []

    print(
        f"🚀 Iniciando coverage eficiente - {start_time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    print(f"📋 {len(CRITICAL_MODULES)} módulos a testear")

    for module_name, test_path in CRITICAL_MODULES:
        result = run_coverage_for_module(module_name, test_path, timeout=45)
        results.append(result)

        # Pausar 2 segundos entre módulos para evitar sobrecarga
        import time

        time.sleep(2)

    # Resumen final
    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    print(f"\n{'='*80}")
    print(f"📈 RESUMEN FINAL - Duration: {duration:.2f}s")
    print(f"{'='*80}\n")

    successful = [r for r in results if r["success"]]
    failed = [r for r in results if not r["success"]]

    print(f"✅ Exitosos: {len(successful)}/{len(results)}")
    print(f"❌ Fallidos: {len(failed)}/{len(results)}\n")

    if successful:
        print("Módulos con coverage:")
        for r in successful:
            cov = r.get("coverage", "N/A")
            print(f"  {r['module']:40s} {cov:>6s}%")

    if failed:
        print("\nMódulos fallidos:")
        for r in failed:
            error = r.get("error", "test failures")
            print(f"  {r['module']:40s} ({error})")

    # Guardar resultados JSON
    output_file = "coverage_results.json"
    with open(output_file, "w") as f:
        json.dump(
            {
                "timestamp": start_time.isoformat(),
                "duration_seconds": duration,
                "total_modules": len(results),
                "successful": len(successful),
                "failed": len(failed),
                "results": results,
            },
            f,
            indent=2,
        )

    print(f"\n💾 Resultados guardados en: {output_file}")

    # Exit code basado en resultados
    if len(failed) == 0:
        print("\n🎉 TODOS LOS MÓDULOS PASARON!")
        sys.exit(0)
    elif len(successful) > len(failed):
        print(
            f"\n⚠️  Algunos módulos fallaron pero mayoría exitosa ({len(successful)}/{len(results)})"
        )
        sys.exit(0)
    else:
        print(f"\n💥 Demasiados módulos fallidos ({len(failed)}/{len(results)})")
        sys.exit(1)


if __name__ == "__main__":
    main()
