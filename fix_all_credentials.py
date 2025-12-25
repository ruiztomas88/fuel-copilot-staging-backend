#!/usr/bin/env python3
"""
fix_all_credentials.py - Script para corregir TODAS las credenciales hardcodeadas
═══════════════════════════════════════════════════════════════════════════════

AUDITORÍA DIC 25, 2025: Encontradas 28 archivos con credenciales hardcodeadas.

USO:
    python fix_all_credentials.py --scan      # Solo ver
    python fix_all_credentials.py --fix       # Aplicar fixes
"""

import os
import re
import sys
import shutil
from pathlib import Path
from datetime import datetime

# Archivos con credenciales (de la auditoría)
AFFECTED_FILES = [
    "test_command_center_sensors.py", "auto_backup_db.py",
    "check_wialon_sensors_report.py", "auto_update_daily_metrics.py",
    "find_units_map.py", "wialon_to_mysql_sync.py",
    "restore_fallback_mpg.py", "diagnose_data_flow.py",
    "validate_local_trips_table.py", "migrate_add_confidence_columns.py",
    "check_mpg_diversity.py", "test_detailed_record.py",
    "reset_inflated_mpg.py", "migrate_v2.py",
    "check_high_mpg.py", "backup_once.py",
    "cleanup_database_dec22.py", "diagnose_all_trucks.py",
    "debug_do9693_sensors.py", "check_ra9250_wialon.py",
    "test_get_truck_record.py", "reset_mpg_for_recalc.py",
    "check_original_mpg.py", "check_missing_columns.py",
    "fix_missing_tables.py", "test_mysql_direct.py",
    "run_migration.py", "diagnose_sensor_mapping.py",
]

# Patrones a reemplazar
REPLACEMENTS = [
    (r"password\s*=\s*['\"]FuelCopilot2025!['\"]",
     'password=os.getenv("MYSQL_PASSWORD", "")'),
    (r"['\"]password['\"]\s*:\s*['\"]FuelCopilot2025!['\"]",
     '"password": os.getenv("MYSQL_PASSWORD", "")'),
    (r"passwd\s*=\s*['\"]FuelCopilot2025!['\"]",
     'passwd=os.getenv("MYSQL_PASSWORD", "")'),
    (r"-p"${MYSQL_PASSWORD}"",
     '-p"${MYSQL_PASSWORD}"'),
    (r"os\.environ\[['\"]MYSQL_PASSWORD['\"]\]\s*=\s*['\"]FuelCopilot2025!['\"]",
     '# Password should be set via .env file'),
    (r"os\.getenv\(['\"]MYSQL_PASSWORD['\"],\s*['\"]FuelCopilot2025!['\"]",
     'os.getenv("MYSQL_PASSWORD", ""'),
]


def scan_file(filepath: Path) -> list:
    """Escanear archivo por credenciales"""
    findings = []
    try:
        content = filepath.read_text(encoding='utf-8')
    except:
        return []
    
    lines = content.split('\n')
    for i, line in enumerate(lines, 1):
        if 'FuelCopilot2025' in line:
            findings.append({
                'file': filepath,
                'line': i,
                'content': line.strip()[:80]
            })
    return findings


def fix_file(filepath: Path) -> bool:
    """Aplicar fixes a un archivo"""
    try:
        content = filepath.read_text(encoding='utf-8')
    except:
        return False
    
    original = content
    
    # Aplicar reemplazos
    for pattern, replacement in REPLACEMENTS:
        content = re.sub(pattern, replacement, content)
    
    # Agregar import os si no existe
    if 'os.getenv' in content and 'import os' not in content:
        lines = content.split('\n')
        insert_pos = 0
        for i, line in enumerate(lines):
            if line.startswith('import') or line.startswith('from'):
                insert_pos = i
                break
        
        if insert_pos > 0:
            lines.insert(insert_pos, 'import os')
            content = '\n'.join(lines)
    
    if content != original:
        filepath.write_text(content, encoding='utf-8')
        return True
    return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Fix hardcoded credentials')
    parser.add_argument('--scan', action='store_true', help='Only scan')
    parser.add_argument('--fix', action='store_true', help='Apply fixes')
    
    args = parser.parse_args()
    
    if not args.scan and not args.fix:
        args.scan = True
    
    root = Path.cwd()
    
    print(f"🔍 Escaneando: {root}\n")
    
    all_findings = []
    
    # Escanear archivos conocidos + recursivo
    for filepath in root.rglob('*.py'):
        findings = scan_file(filepath)
        all_findings.extend(findings)
    
    # Mostrar findings
    if all_findings:
        print(f"❌ Encontradas {len(all_findings)} credenciales hardcodeadas en {len(set(f['file'] for f in all_findings))} archivos:\n")
        
        files_with_creds = {}
        for f in all_findings:
            fname = f['file'].name
            if fname not in files_with_creds:
                files_with_creds[fname] = []
            files_with_creds[fname].append(f)
        
        for fname, findings in sorted(files_with_creds.items())[:10]:
            print(f"  📄 {fname}: {len(findings)} ocurrencias")
        
        if len(files_with_creds) > 10:
            print(f"  ... y {len(files_with_creds) - 10} archivos más")
    else:
        print("✅ No se encontraron credenciales hardcodeadas!")
        return
    
    # Aplicar fixes
    if args.fix:
        print(f"\n⚙️  Aplicando fixes...")
        
        fixed_files = set()
        
        for f in all_findings:
            filepath = f['file']
            
            if filepath in fixed_files:
                continue
            
            # Backup
            backup = filepath.with_suffix('.py.bak')
            shutil.copy2(filepath, backup)
            
            if fix_file(filepath):
                fixed_files.add(filepath)
                print(f"  ✅ {filepath.name}")
        
        print(f"\n✅ {len(fixed_files)} archivos corregidos!")
        print(f"📦 Backups creados con extensión .bak")
        print("\n⚠️  IMPORTANTE: Asegúrate que tu .env tiene:")
        print("   MYSQL_PASSWORD=FuelCopilot2025!")


if __name__ == "__main__":
    main()
