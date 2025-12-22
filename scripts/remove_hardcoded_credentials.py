#!/usr/bin/env python3
"""
Automated script to remove hardcoded credentials from all Python files
Security Fix - Dec 22 2025
"""
import re
import os
from pathlib import Path

# Files to process with their connection type
FILES_TO_FIX = {
    # Local DB connections
    'check_high_drift_v2.py': 'local',
    'check_table_structure.py': 'local',
    'check_lc6799_now.py': 'local',
    'check_high_drift.py': 'local',
    'check_lc6799_refuels.py': 'local',
    'check_sensors_cache.py': 'local',
    'check_lc6799_mr7679.py': 'local',
    'add_missing_fuel_metrics_columns.py': 'local',
    'check_duplicates.py': 'local',
    'add_refuel_type.py': 'local',
    'check_lc6799_db.py': 'local',
    'migrate_schema.py': 'local',
    'quick_test_columns.py': 'local',
    'check_missing_tables.py': 'local',
    'fix_refuel_events_schema.py': 'local',
    'insert_test_dtcs.py': 'local',
    'check_metrics_tables.py': 'local',
    'run_add_idle_columns.py': 'local',
    'check_lc6799_mr7679_v2.py': 'local',
    'check_mpg_values.py': 'local',
    'check_lc6799_final.py': 'local',
    'add_idle_gph_column.py': 'local',
    'verify_sensors.py': 'local',
    'test_dtc_detection.py': 'local',
    
    # Wialon DB connections
    'check_do9693_wialon_sensors.py': 'wialon',
    'check_units_map_structure.py': 'wialon',
    'check_params_lh1141.py': 'wialon',
    'sync_units_map.py': 'wialon',
    
    # Dual connections
    'compare_wialon_vs_our_db.py': 'dual',
    
    # Tools directory
    'tools/debug/check_recent_idle_data.py': 'local',
    'tools/debug/check_trucks_no_fuel_lvl.py': 'wialon',
    'tools/debug/check_idle_live.py': 'wialon',
    'tools/debug/check_fuel_rate_wialon.py': 'wialon',
    'tools/debug/check_fuel_rate_per_truck.py': 'wialon',
    'tools/debug/check_idle_vm.py': 'wialon',
    'tools/debug/check_last_data_time.py': 'wialon',
    'tools/debug/check_three_trucks.py': 'wialon',
}

# Patterns to find and replace
LOCAL_PATTERNS = [
    (
        r"conn\s*=\s*pymysql\.connect\(\s*host\s*=\s*['\"]localhost['\"],\s*(?:port\s*=\s*\d+,\s*)?user\s*=\s*['\"]fuel_admin['\"],\s*password\s*=\s*['\"]FuelCopilot2025!['\"],\s*database\s*=\s*['\"]fuel_copilot['\"]\s*\)",
        "conn = pymysql.connect(**get_local_db_config())"
    ),
    (
        r"pymysql\.connect\(\s*host\s*=\s*['\"]localhost['\"],\s*user\s*=\s*['\"]fuel_admin['\"],\s*password\s*=\s*['\"]FuelCopilot2025!['\"],\s*database\s*=\s*['\"]fuel_copilot['\"]\s*\)",
        "pymysql.connect(**get_local_db_config())"
    ),
]

WIALON_PATTERNS = [
    (
        r"conn\s*=\s*pymysql\.connect\(\s*host\s*=\s*['\"]20\.127\.200\.135['\"],\s*(?:port\s*=\s*\d+,\s*)?user\s*=\s*['\"]tomas['\"],\s*password\s*=\s*['\"]Tomas2025['\"],\s*database\s*=\s*['\"]wialon_collect['\"]\s*(?:,\s*cursorclass\s*=\s*[^)]+)?\)",
        "conn = pymysql.connect(**get_wialon_db_config())"
    ),
]


def add_import_if_needed(content: str, import_type: str) -> str:
    """Add config import if not already present"""
    if 'from config import' in content:
        # Import already exists, update it
        if import_type == 'local' and 'get_local_db_config' not in content:
            content = content.replace(
                'from config import',
                'from config import get_local_db_config,'
            )
        elif import_type == 'wialon' and 'get_wialon_db_config' not in content:
            content = content.replace(
                'from config import',
                'from config import get_wialon_db_config,'
            )
        elif import_type == 'dual':
            if 'get_local_db_config' not in content or 'get_wialon_db_config' not in content:
                content = content.replace(
                    'from config import',
                    'from config import get_local_db_config, get_wialon_db_config,'
                )
    else:
        # Add new import after pymysql import
        if import_type == 'local':
            import_line = 'from config import get_local_db_config\n'
        elif import_type == 'wialon':
            import_line = 'from config import get_wialon_db_config\n'
        else:  # dual
            import_line = 'from config import get_local_db_config, get_wialon_db_config\n'
        
        # Add after pymysql import
        content = re.sub(
            r'(import pymysql\n)',
            r'\1' + import_line,
            content,
            count=1
        )
    
    return content


def fix_file(filepath: Path, conn_type: str) -> bool:
    """Fix hardcoded credentials in a single file"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # Apply patterns based on connection type
        if conn_type in ['local', 'dual']:
            for pattern, replacement in LOCAL_PATTERNS:
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
        
        if conn_type in ['wialon', 'dual']:
            for pattern, replacement in WIALON_PATTERNS:
                content = re.sub(pattern, replacement, content, flags=re.MULTILINE | re.DOTALL)
        
        # Add import if content changed
        if content != original_content:
            content = add_import_if_needed(content, conn_type)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"✅ Fixed: {filepath}")
            return True
        else:
            print(f"⏭️  Skipped (no changes): {filepath}")
            return False
            
    except Exception as e:
        print(f"❌ Error fixing {filepath}: {e}")
        return False


def main():
    """Main execution"""
    root = Path(__file__).parent.parent  # Go up to backend root
    fixed_count = 0
    
    print("=" * 80)
    print("🔒 AUTOMATED CREDENTIAL REMOVAL")
    print("=" * 80)
    
    for filename, conn_type in FILES_TO_FIX.items():
        filepath = root / filename
        
        if not filepath.exists():
            print(f"⚠️  Not found: {filepath}")
            continue
        
        if fix_file(filepath, conn_type):
            fixed_count += 1
    
    print("\n" + "=" * 80)
    print(f"✅ Fixed {fixed_count} files")
    print("=" * 80)
    print("\n⚠️  IMPORTANT: Set these environment variables:")
    print("   export MYSQL_PASSWORD='FuelCopilot2025!'")
    print("   export WIALON_MYSQL_PASSWORD='Tomas2025'")
    print("\nOr add them to .env file (already done)")


if __name__ == "__main__":
    main()
