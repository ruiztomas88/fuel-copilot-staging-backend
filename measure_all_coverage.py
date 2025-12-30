"""Medir cobertura de TODOS los módulos principales"""
import subprocess
import sys

modules = {
    "Fleet Command Center": ("fleet_command_center", "tests/test_fleet_command_center_coverage.py"),
    "Database MySQL": ("database_mysql", "tests/test_database_mysql_real_90pct.py"),
    "Predictive Maintenance v3": ("predictive_maintenance_v3", "tests/test_predictive_maintenance_simple.py"),
    "Theft Detection": ("theft_detection_engine", "tests/test_theft_detection.py"),
    "Engine Health": ("engine_health_engine", "tests/test_engine_health_notifications.py"),
    "Wialon Sync": ("wialon_sync_enhanced", None),
    "Main API": ("main", None),
}

results = []
for name, (module, test_file) in modules.items():
    if test_file:
        cmd = f"/opt/anaconda3/bin/python -m pytest {test_file} --cov={module} --cov-report=term --tb=no -q 2>&1"
    else:
        cmd = f"/opt/anaconda3/bin/python -m pytest tests/ --cov={module} --cov-report=term --tb=no -q 2>&1"
    
    try:
        output = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.STDOUT)
        # Parse coverage
        for line in output.split('\n'):
            if module in line and '%' in line:
                parts = line.split()
                if len(parts) >= 4:
                    stmts = parts[1]
                    miss = parts[2]
                    cover = parts[3]
                    results.append(f"{name:30} {stmts:>6} stmts  {cover:>7} coverage")
                    break
    except:
        results.append(f"{name:30} {'ERROR':>6}       {'N/A':>7}")

print("\n" + "="*70)
print("COBERTURA DE MÓDULOS PRINCIPALES - Fuel Analytics Backend")
print("="*70)
for r in sorted(results, reverse=True):
    print(r)
print("="*70)
