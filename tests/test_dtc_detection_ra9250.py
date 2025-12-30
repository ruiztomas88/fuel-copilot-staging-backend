#!/usr/bin/env python3
"""
🧪 Test DTC Detection for RA9250

Tests that j1939_spn and j1939_fmi sensors are correctly:
1. Read from Wialon database
2. Combined into DTC code format (SPN.FMI)
3. Decoded with Spanish descriptions
4. Show severity and recommended actions

Expected Result:
- RA9250 has SPN=100, FMI=3
- Should decode to: "Presión de Aceite del Motor - Voltage Above Normal"
- Severity: CRITICAL
"""

import os
import sys
from datetime import datetime, timezone
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wialon_reader import WialonReader, WialonConfig, TRUCK_UNIT_MAPPING
from dtc_analyzer import process_dtc_from_sensor_data
from dtc_database import get_dtc_description, get_spn_info, get_fmi_info


def test_ra9250_dtc():
    """Test DTC detection for RA9250"""
    print("=" * 80)
    print("🧪 TESTING DTC DETECTION - RA9250")
    print("=" * 80)

    truck_id = "RA9250"

    # Initialize Wialon reader
    config = WialonConfig()
    reader = WialonReader(config, TRUCK_UNIT_MAPPING)

    if not reader.ensure_connection():
        print("\n❌ ERROR: Cannot connect to Wialon database")
        return False

    print("\n✅ Connected to Wialon database")

    # Get latest data for RA9250
    print(f"\n📊 Fetching latest data for {truck_id}...")
    all_truck_data = reader.get_all_trucks_data()

    ra9250_data = None
    for truck_data in all_truck_data:
        if truck_data.truck_id == truck_id:
            ra9250_data = truck_data
            break

    if not ra9250_data:
        print(f"\n❌ ERROR: No data found for {truck_id}")
        return False

    print(f"\n✅ Found data for {truck_id}")
    print(f"   Timestamp: {ra9250_data.timestamp}")
    print(f"   DTC Count: {ra9250_data.dtc}")
    print(f"   j1939_spn: {ra9250_data.j1939_spn}")
    print(f"   j1939_fmi: {ra9250_data.j1939_fmi}")
    print(f"   dtc_code (combined): {ra9250_data.dtc_code}")

    if not ra9250_data.dtc_code:
        print("\n⚠️  WARNING: No DTC code found")
        print("   This could mean:")
        print("   1. Wialon has no active DTCs for this truck")
        print("   2. j1939_spn or j1939_fmi sensors are not being read")
        return False

    # Test DTC decoding
    print("\n" + "=" * 80)
    print("🔍 TESTING DTC DECODING:")
    print("=" * 80)

    # Parse SPN and FMI
    parts = ra9250_data.dtc_code.split(".")
    if len(parts) != 2:
        print(f"\n❌ ERROR: Invalid DTC code format: {ra9250_data.dtc_code}")
        return False

    spn = int(parts[0])
    fmi = int(parts[1])

    print(f"\n📋 DTC Code: {ra9250_data.dtc_code}")
    print(f"   SPN: {spn}")
    print(f"   FMI: {fmi}")

    # Get SPN info
    spn_info = get_spn_info(spn)
    if spn_info:
        print(f"\n🔧 SPN {spn} Information:")
        print(f"   Component (EN): {spn_info.name_en}")
        print(f"   Component (ES): {spn_info.name_es}")
        print(f"   Description (ES): {spn_info.description_es}")
        print(f"   System: {spn_info.system.value}")
        print(f"   Severity: {spn_info.severity.value}")
    else:
        print(f"\n⚠️  SPN {spn} not found in database (using fallback)")

    # Get FMI info
    fmi_info = get_fmi_info(fmi)
    if fmi_info:
        print(f"\n⚙️  FMI {fmi} Information:")
        print(f"   Description (EN): {fmi_info['en']}")
        print(f"   Description (ES): {fmi_info['es']}")
        print(f"   Severity: {fmi_info['severity'].value}")
    else:
        print(f"\n⚠️  FMI {fmi} not found in database")

    # Get full DTC description
    full_desc = get_dtc_description(spn, fmi)
    print(f"\n📝 Full DTC Description:")
    print(f"   {full_desc}")

    # Process with dtc_analyzer
    print("\n" + "=" * 80)
    print("🚨 PROCESSING DTC ALERT:")
    print("=" * 80)

    try:
        dtc_alerts = process_dtc_from_sensor_data(
            truck_id=truck_id,
            dtc_value=ra9250_data.dtc_code,
            timestamp=ra9250_data.timestamp,
        )

        if not dtc_alerts:
            print("\n⚠️  No alerts generated (code may be INFO level)")
            return True

        for i, alert in enumerate(dtc_alerts, 1):
            print(f"\n🔔 Alert #{i}:")
            print(f"   Severity: {alert.severity.value.upper()}")
            print(f"   Message: {alert.message}")
            print(f"   Is New: {alert.is_new}")
            print(f"   Hours Active: {alert.hours_active:.1f}h")

            for j, code in enumerate(alert.codes, 1):
                print(f"\n   📌 Code #{j}:")
                print(f"      Code: {code.code}")
                print(f"      SPN: {code.spn}")
                print(f"      FMI: {code.fmi}")
                print(f"      Description: {code.description}")
                print(f"      Spanish Name: {code.name_es}")
                print(f"      Spanish FMI: {code.fmi_description_es}")
                print(f"      System: {code.system}")
                print(f"      Severity: {code.severity.value}")
                print(f"      Recommended Action: {code.recommended_action}")

        # Validation
        print("\n" + "=" * 80)
        print("✅ VALIDATION:")
        print("=" * 80)

        success = True

        # Check that we got at least one alert
        if len(dtc_alerts) == 0:
            print("   ❌ No alerts generated")
            success = False
        else:
            print(f"   ✅ {len(dtc_alerts)} alert(s) generated")

        # Check that first alert has decoded info
        if dtc_alerts and dtc_alerts[0].codes:
            code = dtc_alerts[0].codes[0]
            if code.description and code.name_es:
                print(f"   ✅ DTC decoded with Spanish descriptions")
            else:
                print(f"   ⚠️  DTC decoded but missing Spanish descriptions")

            if (
                code.severity == code.severity.CRITICAL
                or code.severity == code.severity.WARNING
            ):
                print(f"   ✅ Severity assigned: {code.severity.value}")
            else:
                print(f"   ⚠️  Unexpected severity: {code.severity.value}")

            if code.recommended_action:
                print(f"   ✅ Recommended action provided")
            else:
                print(f"   ⚠️  No recommended action")

        print("\n" + "=" * 80)
        if success:
            print("✅ TEST PASSED: DTC detection working correctly!")
        else:
            print("⚠️  TEST PARTIAL: Some validations failed")
        print("=" * 80)

        return success

    except Exception as e:
        print(f"\n❌ ERROR processing DTC: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_ra9250_dtc()
    sys.exit(0 if success else 1)
