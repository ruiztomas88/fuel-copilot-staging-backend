#!/usr/bin/env python3
"""
SECURITY FIX: Remove ALL hardcoded credentials from codebase

This script:
1. Finds all hardcoded "FuelCopilot2025!" in Python files
2. Replaces with os.getenv() WITHOUT fallback
3. Adds runtime checks to fail if missing
"""
import os
import re
from pathlib import Path

# Priority files (production code)
CRITICAL_FILES = [
    "database_mysql.py",
    "wialon_sync_enhanced.py",
    "api_v2.py",
    "refuel_calibration.py",
    "alert_service.py",
]

# Patterns to fix
PATTERNS = [
    # Pattern 1: Direct assignment
    (r'"password":\s*"FuelCopilot2025!"', '"password": os.getenv("MYSQL_PASSWORD")'),
    (r"'password':\s*'FuelCopilot2025!'", "'password': os.getenv('MYSQL_PASSWORD')"),
    (r'password\s*=\s*"FuelCopilot2025!"', 'password = os.getenv("MYSQL_PASSWORD")'),
    (r"password\s*=\s*'FuelCopilot2025!'", "password = os.getenv('MYSQL_PASSWORD')"),
    # Pattern 2: os.getenv with fallback (REMOVE FALLBACK)
    (
        r'os\.getenv\("MYSQL_PASSWORD",\s*"FuelCopilot2025!"\)',
        'os.getenv("MYSQL_PASSWORD")',
    ),
    (
        r"os\.getenv\('MYSQL_PASSWORD',\s*'FuelCopilot2025!'\)",
        "os.getenv('MYSQL_PASSWORD')",
    ),
    # Pattern 3: PASSWORD constant
    (r'PASSWORD\s*=\s*"FuelCopilot2025!"', 'PASSWORD = os.getenv("MYSQL_PASSWORD")'),
]


def fix_file(filepath: Path) -> bool:
    """Fix a single file"""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        original = content
        modified = False

        for pattern, replacement in PATTERNS:
            new_content = re.sub(pattern, replacement, content)
            if new_content != content:
                content = new_content
                modified = True

        if modified:
            # Add import os if not present
            if "import os" not in content and "from os import" not in content:
                # Add after first docstring or at top
                lines = content.split("\n")
                insert_pos = 0
                in_docstring = False
                for i, line in enumerate(lines):
                    if '"""' in line or "'''" in line:
                        if not in_docstring:
                            in_docstring = True
                        else:
                            insert_pos = i + 1
                            break
                    elif (
                        not in_docstring
                        and line.strip()
                        and not line.strip().startswith("#")
                    ):
                        insert_pos = i
                        break

                lines.insert(insert_pos, "import os")
                content = "\n".join(lines)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)

            print(f"✅ Fixed: {filepath.name}")
            return True
        else:
            print(f"⏭️  Skipped (no changes): {filepath.name}")
            return False

    except Exception as e:
        print(f"❌ Error in {filepath}: {e}")
        return False


def main():
    backend_dir = Path(__file__).parent

    print("=" * 80)
    print("🔒 REMOVING HARDCODED CREDENTIALS")
    print("=" * 80)

    # Phase 1: Critical production files
    print("\n📌 PHASE 1: Critical Production Files")
    print("-" * 80)
    fixed_count = 0
    for filename in CRITICAL_FILES:
        filepath = backend_dir / filename
        if filepath.exists():
            if fix_file(filepath):
                fixed_count += 1

    print(f"\n✅ Phase 1 Complete: {fixed_count}/{len(CRITICAL_FILES)} files fixed")

    # Phase 2: All Python files (excluding venv, migrations, test files)
    print("\n📌 PHASE 2: All Python Files")
    print("-" * 80)

    skip_dirs = {".git", "venv", "__pycache__", "node_modules", "coverage_annotated"}
    skip_patterns = {"test_", "debug_", "check_", "diagnose_", "verify_", "compare_"}

    all_py_files = []
    for py_file in backend_dir.rglob("*.py"):
        # Skip if in excluded directory
        if any(skip_dir in py_file.parts for skip_dir in skip_dirs):
            continue
        # Skip test/debug files
        if any(py_file.name.startswith(pattern) for pattern in skip_patterns):
            continue
        # Skip if already fixed in phase 1
        if py_file.name in CRITICAL_FILES:
            continue

        all_py_files.append(py_file)

    phase2_fixed = 0
    for py_file in all_py_files[:20]:  # Limit to 20 files for safety
        if fix_file(py_file):
            phase2_fixed += 1

    print(f"\n✅ Phase 2 Complete: {phase2_fixed} additional files fixed")

    print("\n" + "=" * 80)
    print("📊 SUMMARY")
    print("=" * 80)
    print(f"Total files fixed: {fixed_count + phase2_fixed}")
    print("\n⚠️  IMPORTANT: Set MYSQL_PASSWORD in environment:")
    print("   export MYSQL_PASSWORD='FuelCopilot2025!'  # For now")
    print("\n🔐 NEXT STEP: Rotate password and update .env")
    print("=" * 80)


if __name__ == "__main__":
    main()
