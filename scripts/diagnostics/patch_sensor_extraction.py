#!/usr/bin/env python3
"""
🔧 SENSOR EXTRACTION PATCH
Adds new sensor extraction to process_truck() before returning metrics.

This patch inserts code before the final return statement to extract:
- gear (J1939 decode)
- engine_brake_active
- obd_speed_mph
- oil_level_pct
- barometric_pressure_inhg
- pto_hours
- accel_rate_mpss, harsh_accel, harsh_brake (calculated)
"""

import re
from datetime import datetime
from pathlib import Path

TARGET = Path("wialon_sync_enhanced.py")
BACKUP = TARGET.with_suffix(
    f".py.backup_sensor_extraction_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
)


def apply_patch():
    print("=" * 70)
    print("🔧 SENSOR EXTRACTION PATCH")
    print("=" * 70)

    if not TARGET.exists():
        print(f"❌ ERROR: {TARGET} not found")
        return 1

    print(f"📦 Creating backup: {BACKUP.name}")
    content = TARGET.read_text()
    BACKUP.write_text(content)

    # Find the line "# Return complete metrics"
    # Insert extraction code BEFORE it

    marker = "    # Return complete metrics\n    return {"

    if marker not in content:
        print("❌ ERROR: Marker '# Return complete metrics' not found")
        return 1

    # Code to insert
    extraction_code = """    # 🆕 DEC 30 2025: Extract new sensors for behavior tracking
    gear_raw = sensor_data.get("gear")
    gear_decoded = None
    if gear_raw is not None:
        # Decode J1939 gear (0=no data, 31=Neutral, 1-18=gears, -1/251=Reverse)
        from api_v2 import decode_j1939_gear
        gear_decoded = decode_j1939_gear(gear_raw)
    
    # Engine brake active (binary)
    engine_brake_active = int(sensor_data.get("engine_brake", 0))
    
    # OBD speed (from ECU, often more accurate than GPS at low speeds)
    obd_speed_mph = sensor_data.get("obd_speed")
    
    # Oil level percentage (from ECU sensor)
    oil_level_pct = sensor_data.get("oil_lvl")  # Note: "oil_lvl" not "oil_level"
    
    # Barometric pressure (for altitude corrections)
    barometric_pressure_inhg = sensor_data.get("barometer")
    
    # PTO hours (Power Take-Off tracking)
    pto_hours = sensor_data.get("pto_hours")
    
    # 🆕 DEC 30 2025: Calculate acceleration/braking from speed deltas
    accel_rate_mpss = None
    harsh_accel = False
    harsh_brake = False
    
    if speed is not None and speed >= 0:
        accel_rate_mpss, harsh_accel, harsh_brake = calculate_acceleration(
            truck_id=truck_id,
            current_speed=speed,
            current_time=timestamp
        )

    # Return complete metrics
    return {"""

    # Replace marker with new code
    new_content = content.replace(marker, extraction_code)

    # Verify change was applied
    if "# 🆕 DEC 30 2025: Extract new sensors for behavior tracking" not in new_content:
        print("❌ ERROR: Patch failed to apply")
        return 1

    # Add new fields to the return dict (after line with "mpg_status": mpg_status,)
    mpg_status_marker = '        "mpg_status": mpg_status,\n    }'

    if mpg_status_marker in new_content:
        new_fields = """        "mpg_status": mpg_status,
        # 🆕 DEC 30 2025: New sensor data
        "gear": gear_decoded,
        "engine_brake_active": engine_brake_active,
        "obd_speed_mph": obd_speed_mph,
        "oil_level_pct": oil_level_pct,
        "barometric_pressure_inhg": barometric_pressure_inhg,
        "pto_hours": pto_hours,
        # 🆕 DEC 30 2025: Behavior tracking
        "accel_rate_mpss": accel_rate_mpss,
        "harsh_accel": 1 if harsh_accel else 0,
        "harsh_brake": 1 if harsh_brake else 0,
    }"""

        new_content = new_content.replace(mpg_status_marker, new_fields)

    # Save patched file
    print("💾 Saving patched file...")
    TARGET.write_text(new_content)

    # Validate
    print("\n🔍 Validating...")
    checks = [
        (
            "Extract new sensors for behavior tracking" in new_content,
            "Extraction code added",
        ),
        ("gear_decoded = decode_j1939_gear" in new_content, "Gear decode function"),
        ("calculate_acceleration(" in new_content, "Acceleration calculation"),
        ('"gear": gear_decoded' in new_content, "Gear in return dict"),
        (
            '"harsh_accel": 1 if harsh_accel' in new_content,
            "Harsh accel in return dict",
        ),
    ]

    all_passed = True
    for check, name in checks:
        status = "✅" if check else "❌"
        print(f"   {status} {name}")
        if not check:
            all_passed = False

    if not all_passed:
        print("\n❌ VALIDATION FAILED")
        return 1

    print("\n" + "=" * 70)
    print("✅ SENSOR EXTRACTION PATCH COMPLETED")
    print("=" * 70)
    print(f"\n💾 Backup: {BACKUP.name}")
    print("\n📋 Next: Restart wialon_sync and check data")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(apply_patch())
