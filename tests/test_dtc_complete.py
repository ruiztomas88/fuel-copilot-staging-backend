"""
Test DTC Decoder - Complete System (SPN + FMI)
===============================================

Tests para el sistema completo de decodificación DTC

Author: Fuel Copilot Team
Date: December 26, 2025
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dtc_decoder import DTCDecoder, FuelCopilotDTCHandler


def test_basic_dtc_decoding():
    """Test basic DTC decoding (SPN + FMI)"""
    print("=" * 80)
    print("TEST 1: BASIC DTC DECODING (SPN + FMI)")
    print("=" * 80)

    decoder = DTCDecoder()

    # Test critical DTC
    print("\n🔍 Test 1.1: Critical DTC (Oil Pressure Low)")
    dtc = decoder.decode_dtc(spn=100, fmi=1)
    print(f"   DTC Code: {dtc.dtc_code}")
    print(f"   Description: {dtc.full_description}")
    print(f"   Severity: {dtc.severity}")
    print(f"   Critical: {dtc.is_critical}")
    print(f"   Action: {dtc.action_required}")

    assert dtc.dtc_code == "100-1", f"Expected '100-1', got '{dtc.dtc_code}'"
    assert dtc.is_critical == True, "Should be critical"
    assert dtc.severity == "CRITICAL", f"Expected CRITICAL, got {dtc.severity}"
    assert "Engine Oil Pressure" in dtc.full_description
    assert "Low" in dtc.full_description
    print("   ✅ PASSED")

    # Test your ICU SPN
    print("\n🔍 Test 1.2: Your ICU SPN (523002-12)")
    dtc = decoder.decode_dtc(spn=523002, fmi=12)
    print(f"   DTC Code: {dtc.dtc_code}")
    print(f"   Description: {dtc.full_description}")
    print(f"   Critical: {dtc.is_critical}")

    assert dtc.dtc_code == "523002-12"
    assert dtc.is_critical == True
    assert "ICU" in dtc.full_description or "EEPROM" in dtc.full_description
    print("   ✅ PASSED")

    # Test moderate severity
    print("\n🔍 Test 1.3: Moderate Severity (Fuel Rate Erratic)")
    dtc = decoder.decode_dtc(spn=183, fmi=2)
    print(f"   DTC Code: {dtc.dtc_code}")
    print(f"   Severity: {dtc.severity}")
    print(f"   Critical: {dtc.is_critical}")

    # FMI 2 is HIGH, but SPN 183 has priority 1 (CRITICAL)
    # So overall should be CRITICAL
    assert dtc.severity in ["CRITICAL", "HIGH"]
    print("   ✅ PASSED")

    # Test unknown SPN with critical FMI
    print("\n🔍 Test 1.4: Unknown SPN with Critical FMI")
    dtc = decoder.decode_dtc(spn=999999, fmi=1)
    print(f"   DTC Code: {dtc.dtc_code}")
    print(f"   Description: {dtc.full_description}")
    print(f"   Critical: {dtc.is_critical}")

    assert "Unknown" in dtc.spn_description
    assert dtc.is_critical == True, "FMI 1 is CRITICAL, so DTC should be critical"
    print("   ✅ PASSED")

    # Test unknown FMI
    print("\n🔍 Test 1.5: Known SPN with Unknown FMI")
    dtc = decoder.decode_dtc(spn=100, fmi=99)
    print(f"   DTC Code: {dtc.dtc_code}")
    print(f"   FMI Description: {dtc.fmi_description}")

    assert "Unknown" in dtc.fmi_description
    print("   ✅ PASSED")

    print("\n✅ TEST 1 COMPLETED")


def test_severity_logic():
    """Test severity determination logic"""
    print("\n" + "=" * 80)
    print("TEST 2: SEVERITY LOGIC")
    print("=" * 80)

    decoder = DTCDecoder()

    test_cases = [
        # (spn, fmi, expected_severity, expected_critical)
        (100, 1, "CRITICAL", True),  # SPN priority 1 + FMI CRITICAL
        (100, 13, "CRITICAL", True),  # SPN priority 1 + FMI MODERATE → CRITICAL wins
        (183, 0, "CRITICAL", True),  # SPN priority 1 + FMI CRITICAL
        (96, 2, "HIGH", False),  # SPN priority 3 + FMI HIGH → HIGH
        (96, 15, "LOW", False),  # SPN priority 3 + FMI LOW → LOW
    ]

    for spn, fmi, expected_severity, expected_critical in test_cases:
        dtc = decoder.decode_dtc(spn, fmi)
        print(f"\n   DTC {dtc.dtc_code}:")
        print(f"   Expected: {expected_severity}, Critical: {expected_critical}")
        print(f"   Got: {dtc.severity}, Critical: {dtc.is_critical}")

        assert (
            dtc.severity == expected_severity
        ), f"DTC {dtc.dtc_code}: expected {expected_severity}, got {dtc.severity}"
        assert (
            dtc.is_critical == expected_critical
        ), f"DTC {dtc.dtc_code}: expected critical={expected_critical}, got {dtc.is_critical}"
        print(f"   ✅ PASSED")

    print("\n✅ TEST 2 COMPLETED")


def test_fuel_copilot_handler():
    """Test Fuel Copilot integration handler"""
    print("\n" + "=" * 80)
    print("TEST 3: FUEL COPILOT HANDLER")
    print("=" * 80)

    handler = FuelCopilotDTCHandler()

    # Process critical DTC
    print("\n🔍 Test 3.1: Process Critical DTC")
    result = handler.process_wialon_dtc(truck_id="FL-0045", spn=100, fmi=1)

    print(f"   Truck: {result['truck_id']}")
    print(f"   DTC: {result['dtc_code']}")
    print(f"   Severity: {result['severity']}")
    print(f"   Requires Driver Alert: {result['requires_driver_alert']}")
    print(f"   Requires Immediate Stop: {result['requires_immediate_stop']}")
    print(f"\n   Alert Message:")
    print(f"   {result['alert_message']}")

    assert result["truck_id"] == "FL-0045"
    assert result["dtc_code"] == "100-1"
    assert result["is_critical"] == True
    assert result["requires_driver_alert"] == True
    assert result["requires_immediate_stop"] == True
    print("   ✅ PASSED")

    # Process non-critical DTC
    print("\n🔍 Test 3.2: Process Non-Critical DTC")
    result = handler.process_wialon_dtc(truck_id="FL-0045", spn=96, fmi=15)

    print(f"   DTC: {result['dtc_code']}")
    print(f"   Critical: {result['is_critical']}")
    print(f"   Requires Driver Alert: {result['requires_driver_alert']}")

    assert result["is_critical"] == False
    assert result["requires_driver_alert"] == False
    print("   ✅ PASSED")

    # Get truck summary
    print("\n🔍 Test 3.3: Get Truck DTC Summary")
    summary = handler.get_truck_dtc_summary("FL-0045")

    print(f"   Total DTCs: {summary['total_dtcs']}")
    print(f"   Critical: {summary['critical_count']}")
    print(f"   High: {summary['high_count']}")
    print(f"   Requires Attention: {summary['requires_immediate_attention']}")

    assert summary["total_dtcs"] >= 2
    assert summary["critical_count"] >= 1
    assert summary["requires_immediate_attention"] == True
    print("   ✅ PASSED")

    print("\n✅ TEST 3 COMPLETED")


def test_dtc_string_parsing():
    """Test DTC string parsing"""
    print("\n" + "=" * 80)
    print("TEST 4: DTC STRING PARSING")
    print("=" * 80)

    decoder = DTCDecoder()

    test_strings = [
        "100-1",
        "523002-12",
        "183-2",
    ]

    for dtc_str in test_strings:
        print(f"\n   Parsing: {dtc_str}")
        dtc = decoder.parse_dtc_string(dtc_str)

        assert dtc is not None, f"Failed to parse {dtc_str}"
        assert dtc.dtc_code == dtc_str, f"Expected {dtc_str}, got {dtc.dtc_code}"
        print(f"   ✅ {dtc.full_description}")

    # Test invalid format
    print("\n   Testing invalid format:")
    dtc = decoder.parse_dtc_string("invalid")
    assert dtc is None, "Should return None for invalid format"
    print("   ✅ Correctly returned None")

    print("\n✅ TEST 4 COMPLETED")


def test_all_fmi_codes():
    """Test all 22 FMI codes"""
    print("\n" + "=" * 80)
    print("TEST 5: ALL FMI CODES (0-21)")
    print("=" * 80)

    decoder = DTCDecoder()

    critical_fmis = [0, 1, 12]  # Known critical FMIs

    print("\n   Testing all FMI codes with SPN 100:")
    for fmi in range(22):
        dtc = decoder.decode_dtc(spn=100, fmi=fmi)
        fmi_info = decoder.decode_fmi(fmi)

        print(f"\n   FMI {fmi}: {fmi_info.description}")
        print(f"      Severity: {fmi_info.severity}")
        print(f"      Type: {fmi_info.type}")

        if fmi in critical_fmis:
            assert fmi_info.is_critical(), f"FMI {fmi} should be critical"
            assert dtc.is_critical, f"DTC 100-{fmi} should be critical"

    print("\n✅ TEST 5 COMPLETED")


def test_statistics():
    """Test decoder statistics"""
    print("\n" + "=" * 80)
    print("TEST 6: DECODER STATISTICS")
    print("=" * 80)

    decoder = DTCDecoder()
    stats = decoder.get_statistics()

    print(f"\n   Total SPNs: {stats['total_spns']}")
    print(f"   Total FMIs: {stats['total_fmis']}")
    print(f"   Critical SPNs: {stats['critical_spns']}")
    print(f"   Critical FMIs: {stats['critical_fmis']}")

    assert stats["total_spns"] > 0, "Should have SPNs loaded"
    assert stats["total_fmis"] == 22, f"Should have 22 FMIs, got {stats['total_fmis']}"
    assert (
        stats["critical_fmis"] == 3
    ), f"Should have 3 critical FMIs (0,1,12), got {stats['critical_fmis']}"

    print("\n✅ TEST 6 COMPLETED")


def main():
    """Run all tests"""
    print("\n")
    print("🚀" * 40)
    print("DTC DECODER COMPLETE SYSTEM - TESTS (SPN + FMI)")
    print("🚀" * 40)
    print()

    try:
        test_basic_dtc_decoding()
        test_severity_logic()
        test_fuel_copilot_handler()
        test_dtc_string_parsing()
        test_all_fmi_codes()
        test_statistics()

        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        print("\n✅ El sistema DTC completo (SPN + FMI) está funcionando correctamente")
        print("✅ 22 FMI codes cargados y validados")
        print("✅ Severity logic funciona correctamente")
        print("✅ Fuel Copilot handler listo para producción")
        print("\n📝 Next Steps:")
        print("   1. Integrar en wialon_sync_enhanced.py")
        print("   2. Actualizar dtc_database.py para usar nuevo sistema")
        print("   3. Actualizar frontend para mostrar DTC completo")
        print()

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
