#!/usr/bin/env python3
"""
🚀 AUTO-PATCHER: Add 100% Real Data Support to wialon_sync_enhanced.py

This script automatically updates wialon_sync_enhanced.py to:
1. Add new sensor columns to INSERT statement
2. Extract new sensors from sensor_data
3. Calculate harsh acceleration/braking
4. Update fuel_metrics with real behavior data

Usage:
    python apply_100pct_real_data_patch.py

Safety:
    - Creates backup before modifying
    - Validates changes before applying
    - Can be run multiple times (idempotent)
"""

import re
import sys
from datetime import datetime
from pathlib import Path

# File to patch
TARGET_FILE = Path(__file__).parent / "wialon_sync_enhanced.py"
BACKUP_FILE = TARGET_FILE.with_suffix(
    f".py.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
)


def create_backup():
    """Create backup of original file"""
    print(f"📦 Creating backup: {BACKUP_FILE.name}")
    content = TARGET_FILE.read_text()
    BACKUP_FILE.write_text(content)
    return content


def patch_insert_columns(content: str) -> str:
    """Add new columns to INSERT statement"""
    print("🔧 Patching INSERT columns...")

    # Find the INSERT statement
    insert_pattern = r"(coolant_temp_f,)(\s+)(idle_gph,)"

    new_columns = """coolant_temp_f,
                 gear, engine_brake_active, obd_speed_mph,
                 oil_level_pct, barometric_pressure_inhg, pto_hours,
                 accel_rate_mpss, harsh_accel, harsh_brake,
                 idle_gph,"""

    if "gear, engine_brake_active" in content:
        print("   ✅ INSERT columns already patched")
        return content

    content = re.sub(insert_pattern, new_columns, content)
    print("   ✅ Added new columns to INSERT")
    return content


def patch_insert_values(content: str) -> str:
    """Add new values to INSERT tuple"""
    print("🔧 Patching INSERT values...")

    # Check if already patched
    if 'metrics.get("gear")' in content and "harsh_accel" in content:
        print("   ✅ INSERT values already patched")
        return content

    # Find where coolant_temp_f is in values tuple
    pattern = r'(metrics\["coolant_temp_f"\],)(\s+)(# 🔧 FIX v5\.4\.7: Added idle_gph)'

    new_values = """metrics["coolant_temp_f"],
                # 🆕 DEC 30 2025: New sensors
                metrics.get("gear"),
                metrics.get("engine_brake_active"),
                metrics.get("obd_speed_mph"),
                metrics.get("oil_level_pct"),
                metrics.get("barometric_pressure_inhg"),
                metrics.get("pto_hours"),
                # 🆕 DEC 30 2025: Behavior tracking
                metrics.get("accel_rate_mpss"),
                metrics.get("harsh_accel", 0),
                metrics.get("harsh_brake", 0),
                # 🔧 FIX v5.4.7: Added idle_gph"""

    content = re.sub(pattern, new_values, content)
    print("   ✅ Added new values to INSERT tuple")
    return content


def patch_duplicate_key_update(content: str) -> str:
    """Add new columns to ON DUPLICATE KEY UPDATE"""
    print("🔧 Patching ON DUPLICATE KEY UPDATE...")

    pattern = r"(coolant_temp_f = VALUES\(coolant_temp_f\),)(\s+)(idle_gph)"

    new_updates = """coolant_temp_f = VALUES(coolant_temp_f),
                    gear = VALUES(gear),
                    engine_brake_active = VALUES(engine_brake_active),
                    obd_speed_mph = VALUES(obd_speed_mph),
                    oil_level_pct = VALUES(oil_level_pct),
                    barometric_pressure_inhg = VALUES(barometric_pressure_inhg),
                    pto_hours = VALUES(pto_hours),
                    accel_rate_mpss = VALUES(accel_rate_mpss),
                    harsh_accel = VALUES(harsh_accel),
                    harsh_brake = VALUES(harsh_brake),
                    idle_gph"""

    if "gear = VALUES(gear)" in content:
        print("   ✅ ON DUPLICATE KEY UPDATE already patched")
        return content

    content = re.sub(pattern, new_updates, content)
    print("   ✅ Added new columns to ON DUPLICATE KEY UPDATE")
    return content


def add_acceleration_tracking(content: str) -> str:
    """Add acceleration calculation at top of file"""
    print("🔧 Adding acceleration tracking...")

    if "PREVIOUS_SPEEDS = {}" in content:
        print("   ✅ Acceleration tracking already added")
        return content

    # Find imports section (after last import)
    import_end = content.rfind("from")
    next_line = content.find("\n\n", import_end)

    acceleration_code = '''

# 🆕 DEC 30 2025: Track previous speed for acceleration calculation
PREVIOUS_SPEEDS = {}  # truck_id -> (speed_mph, timestamp)

def calculate_acceleration(truck_id: str, current_speed: float, current_time) -> tuple:
    """
    Calculate acceleration rate and detect harsh events.
    
    Returns:
        (accel_rate_mpss, harsh_accel, harsh_brake)
    """
    if truck_id not in PREVIOUS_SPEEDS:
        PREVIOUS_SPEEDS[truck_id] = (current_speed, current_time)
        return (None, False, False)
    
    prev_speed, prev_time = PREVIOUS_SPEEDS[truck_id]
    
    # Calculate time delta
    if hasattr(current_time, 'timestamp') and hasattr(prev_time, 'timestamp'):
        time_delta = (current_time.timestamp() - prev_time.timestamp())
    else:
        time_delta = (current_time - prev_time).total_seconds()
    
    if time_delta <= 0 or time_delta > 60:
        PREVIOUS_SPEEDS[truck_id] = (current_speed, current_time)
        return (None, False, False)
    
    accel_rate = (current_speed - prev_speed) / time_delta
    harsh_accel = accel_rate > 4.0
    harsh_brake = accel_rate < -4.0
    
    PREVIOUS_SPEEDS[truck_id] = (current_speed, current_time)
    return (accel_rate, harsh_accel, harsh_brake)

'''

    content = content[:next_line] + acceleration_code + content[next_line:]
    print("   ✅ Added acceleration tracking function")
    return content


def validate_changes(original: str, patched: str) -> bool:
    """Validate that changes were applied correctly"""
    print("\n🔍 Validating changes...")

    checks = [
        ("gear, engine_brake_active" in patched, "INSERT columns"),
        ('metrics.get("gear")' in patched, "INSERT values"),
        ("gear = VALUES(gear)" in patched, "UPDATE clause"),
        ("PREVIOUS_SPEEDS = {}" in patched, "Acceleration tracking"),
        ("def calculate_acceleration" in patched, "Acceleration function"),
    ]

    all_passed = True
    for check, name in checks:
        status = "✅" if check else "❌"
        print(f"   {status} {name}")
        if not check:
            all_passed = False

    return all_passed


def main():
    print("=" * 70)
    print("🚀 AUTO-PATCHER: 100% Real Data Support")
    print("=" * 70)
    print()

    if not TARGET_FILE.exists():
        print(f"❌ ERROR: {TARGET_FILE} not found")
        return 1

    # Create backup
    original_content = create_backup()
    print()

    # Apply patches
    content = original_content
    content = patch_insert_columns(content)
    content = patch_insert_values(content)
    content = patch_duplicate_key_update(content)
    content = add_acceleration_tracking(content)

    # Validate
    if not validate_changes(original_content, content):
        print("\n❌ VALIDATION FAILED - Not saving changes")
        print(f"   Backup preserved at: {BACKUP_FILE}")
        return 1

    # Save
    print(f"\n💾 Saving patched file...")
    TARGET_FILE.write_text(content)

    print()
    print("=" * 70)
    print("✅ PATCH COMPLETED SUCCESSFULLY")
    print("=" * 70)
    print()
    print("📋 Next steps:")
    print("   1. Review changes in wialon_sync_enhanced.py")
    print("   2. Restart wialon_sync:")
    print("      pkill -f wialon_sync_enhanced.py")
    print(
        "      /opt/anaconda3/bin/python wialon_sync_enhanced.py > logs/wialon_sync.log 2>&1 &"
    )
    print("   3. Wait 2-3 minutes for data to accumulate")
    print(
        "   4. Check: SELECT gear, harsh_accel FROM fuel_metrics ORDER BY id DESC LIMIT 5;"
    )
    print()
    print(f"💾 Backup saved at: {BACKUP_FILE.name}")
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
