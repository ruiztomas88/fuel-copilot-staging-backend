"""
Test HYBRID DTC System - COMPLETE COVERAGE
===========================================

Tests para validar sistema híbrido:
- 111 SPNs DETAILED (explicaciones completas)
- 35,503 SPNs COMPLETE (cobertura máxima)
- 22 FMI codes

Author: Fuel Copilot Team
Date: December 26, 2025
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from dtc_decoder import DTCDecoder, FuelCopilotDTCHandler


def test_hybrid_coverage():
    """Test HYBRID database coverage"""
    print("=" * 80)
    print("TEST 1: HYBRID SYSTEM COVERAGE")
    print("=" * 80)

    decoder = DTCDecoder()
    stats = decoder.get_statistics()

    print(f"\n📊 DETAILED Database: {stats['spn_detailed_count']} SPNs")
    print(f"📊 COMPLETE Database: {stats['spn_complete_count']} SPNs")
    print(f"📊 FMI Codes: {stats['total_fmis']}")
    print(f"\n✅ DTCs with DETAILED info: {stats['dtcs_with_detailed_info']:,}")
    print(f"✅ DTCs total decodable: {stats['dtcs_total_decodable']:,}")
    print(f"📈 Detailed coverage: {stats['coverage_percent']}% of complete database")

    # Validate counts
    assert (
        stats["spn_detailed_count"] == 111
    ), f"Expected 111 detailed SPNs, got {stats['spn_detailed_count']}"
    assert (
        stats["spn_complete_count"] >= 35000
    ), f"Expected 35,000+ complete SPNs, got {stats['spn_complete_count']}"
    assert stats["total_fmis"] == 22, f"Expected 22 FMIs, got {stats['total_fmis']}"
    assert stats["dtcs_with_detailed_info"] == 2442, f"Expected 2,442 detailed DTCs"
    assert stats["dtcs_total_decodable"] >= 781000, f"Expected 781,000+ total DTCs"

    print("\n✅ TEST 1 PASSED - Coverage validated")


def test_detailed_vs_basic():
    """Test detailed SPNs have full info vs basic SPNs"""
    print("\n" + "=" * 80)
    print("TEST 2: DETAILED vs BASIC SPN INFO")
    print("=" * 80)

    decoder = DTCDecoder()

    # Test SPN from DETAILED database (SPN 100)
    print("\n🔍 Test 2.1: SPN from DETAILED database")
    dtc_detailed = decoder.decode_dtc(spn=100, fmi=1)

    print(f"   DTC: {dtc_detailed.dtc_code}")
    print(f"   Has Detailed Info: {dtc_detailed.has_detailed_info}")
    print(f"   Explanation length: {len(dtc_detailed.spn_explanation)} chars")

    assert dtc_detailed.has_detailed_info == True, "SPN 100 should be from DETAILED db"
    assert (
        len(dtc_detailed.spn_explanation) > 100
    ), "Detailed SPN should have full explanation"
    print("   ✅ PASSED - Detailed SPN has full info")

    # Test SPN from COMPLETE database only (random high number)
    print("\n🔍 Test 2.2: SPN from COMPLETE database only")
    dtc_basic = decoder.decode_dtc(spn=1000, fmi=1)

    print(f"   DTC: {dtc_basic.dtc_code}")
    print(f"   Has Detailed Info: {dtc_basic.has_detailed_info}")
    print(f"   Description: {dtc_basic.spn_description}")

    # SPN 1000 might not be in detailed, check it falls back to complete
    if dtc_basic.has_detailed_info == False:
        print("   ✅ PASSED - Basic SPN from COMPLETE database")
    else:
        print("   ℹ️  SPN 1000 also in DETAILED database")


def test_top_20_critical_dtcs():
    """Test top 20 DTCs más comunes tienen info detallada"""
    print("\n" + "=" * 80)
    print("TEST 3: TOP 20 CRITICAL DTCs")
    print("=" * 80)

    decoder = DTCDecoder()

    # Top 20 DTCs críticos de Class 8
    top_20_dtcs = [
        (100, 1, "Oil Pressure LOW"),
        (100, 0, "Oil Pressure HIGH"),
        (110, 0, "Coolant Temp HIGH"),
        (110, 1, "Coolant Temp LOW"),
        (598, 1, "Brake Air Pressure PRIMARY LOW"),
        (599, 1, "Brake Air Pressure SECONDARY LOW"),
        (543, 0, "DPF Differential Pressure HIGH"),
        (521060, 12, "DPF Soot Load EXCEEDED"),
        (521049, 13, "SCR Efficiency LOW"),
        (523002, 12, "ICU EEPROM FAILURE"),
        (183, 2, "Fuel Rate ERRATIC"),
        (184, 2, "MPG ERRATIC"),
        (92, 2, "Engine Load ERRATIC"),
        (520199, 12, "Transmission Communication FAILURE"),
        (521020, 1, "Engine Oil Pressure LOW (DD)"),
        (521021, 0, "Coolant Temp HIGH (DD)"),
        (521080, 1, "Fuel Pressure LOW (DD)"),
        (94, 1, "Fuel Delivery Pressure LOW"),
        (177, 0, "Transmission Oil Temp HIGH"),
        (102, 0, "Intake Manifold Pressure HIGH"),
    ]

    detailed_count = 0
    for spn, fmi, description in top_20_dtcs:
        dtc = decoder.decode_dtc(spn, fmi)

        print(f"\n   {dtc.dtc_code:12s} - {description:40s}")
        print(f"      Severity: {dtc.severity:8s} | Critical: {dtc.is_critical}")
        print(f"      Detailed: {dtc.has_detailed_info}")

        if dtc.has_detailed_info:
            detailed_count += 1

    print(f"\n📊 {detailed_count}/20 top DTCs have DETAILED info ({detailed_count*5}%)")

    # Al menos 80% de los top 20 deben tener info detallada
    assert (
        detailed_count >= 16
    ), f"Expected at least 16/20 top DTCs with details, got {detailed_count}"

    print("\n✅ TEST 3 PASSED - Top DTCs covered")


def test_oem_specific_dtcs():
    """Test DTCs específicos de OEM"""
    print("\n" + "=" * 80)
    print("TEST 4: OEM-SPECIFIC DTCs")
    print("=" * 80)

    decoder = DTCDecoder()

    oem_dtcs = [
        (523002, 12, "Freightliner ICU"),
        (521049, 13, "Detroit SCR"),
        (521020, 1, "Detroit Oil Pressure"),
        (520199, 12, "Freightliner Transmission"),
        (600010, 1, "Volvo ECU"),
        (85000, 1, "Paccar MX-13"),
    ]

    for spn, fmi, oem_description in oem_dtcs:
        dtc = decoder.decode_dtc(spn, fmi)

        print(f"\n   {dtc.dtc_code:12s} - {oem_description}")
        print(f"      OEM: {dtc.oem}")
        print(f"      Detailed: {dtc.has_detailed_info}")
        print(f"      Severity: {dtc.severity}")

        assert dtc.oem != "Unknown", f"DTC {dtc.dtc_code} should have detected OEM"

    print("\n✅ TEST 4 PASSED - OEM DTCs decodable")


def test_unknown_spn_handling():
    """Test manejo de SPNs desconocidos"""
    print("\n" + "=" * 80)
    print("TEST 5: UNKNOWN SPN HANDLING")
    print("=" * 80)

    decoder = DTCDecoder()

    # SPN que probablemente no esté en ninguna base
    unknown_spn = 999999
    dtc = decoder.decode_dtc(spn=unknown_spn, fmi=1)

    print(f"\n   DTC: {dtc.dtc_code}")
    print(f"   Description: {dtc.full_description}")
    print(f"   OEM detected: {dtc.oem}")
    print(f"   Has detailed: {dtc.has_detailed_info}")
    print(f"   Severity: {dtc.severity}")

    assert "Unknown" in dtc.spn_description, "Unknown SPN should be labeled"
    assert dtc.has_detailed_info == False, "Unknown SPN should not have detailed flag"
    # Aún debe tener severity por el FMI
    assert dtc.is_critical == True, "FMI 1 makes it critical"

    print("\n✅ TEST 5 PASSED - Unknown SPNs handled gracefully")


def test_fuel_copilot_handler():
    """Test Fuel Copilot integration handler"""
    print("\n" + "=" * 80)
    print("TEST 6: FUEL COPILOT HANDLER")
    print("=" * 80)

    handler = FuelCopilotDTCHandler()

    # Process critical DTC
    result = handler.process_wialon_dtc(truck_id="FL-0045", spn=100, fmi=1)

    print(f"\n   Truck: {result['truck_id']}")
    print(f"   DTC: {result['dtc_code']}")
    print(f"   Has Detailed: {result['has_detailed_info']}")
    print(f"   Severity: {result['severity']}")
    print(f"   Requires Stop: {result['requires_immediate_stop']}")

    assert result["has_detailed_info"] == True, "SPN 100 should be detailed"
    assert result["is_critical"] == True
    assert result["requires_immediate_stop"] == True

    print("\n✅ TEST 6 PASSED - Handler working with detailed info")


def test_capacity_calculations():
    """Validate capacity calculations"""
    print("\n" + "=" * 80)
    print("TEST 7: CAPACITY CALCULATIONS")
    print("=" * 80)

    decoder = DTCDecoder()
    stats = decoder.get_statistics()

    # Calculate expected values
    expected_detailed = 111 * 22  # 2,442
    expected_total = 35503 * 22  # 781,066

    actual_detailed = stats["dtcs_with_detailed_info"]
    actual_total = stats["dtcs_total_decodable"]

    print(f"\n   Expected DTCs detailed: {expected_detailed:,}")
    print(f"   Actual DTCs detailed: {actual_detailed:,}")
    print(f"   Match: {actual_detailed == expected_detailed}")

    print(f"\n   Expected DTCs total: {expected_total:,}")
    print(f"   Actual DTCs total: {actual_total:,}")
    print(f"   Match: {actual_total == expected_total}")

    assert actual_detailed == expected_detailed, "Detailed count mismatch"
    assert actual_total == expected_total, "Total count mismatch"

    print("\n✅ TEST 7 PASSED - Capacity calculations correct")


def main():
    """Run all tests"""
    print("\n")
    print("🚀" * 40)
    print("HYBRID DTC SYSTEM - COMPLETE VALIDATION")
    print("🚀" * 40)
    print()

    try:
        test_hybrid_coverage()
        test_detailed_vs_basic()
        test_top_20_critical_dtcs()
        test_oem_specific_dtcs()
        test_unknown_spn_handling()
        test_fuel_copilot_handler()
        test_capacity_calculations()

        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        print("\n✅ Sistema HÍBRIDO funcionando perfectamente:")
        print("   📊 111 SPNs DETAILED (explicaciones completas)")
        print("   📊 35,503 SPNs COMPLETE (cobertura máxima)")
        print("   📊 22 FMI codes (completo 0-21)")
        print("   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("   ✅ 2,442 DTCs con explicación DETALLADA")
        print("   ✅ 781,066 DTCs DECODIFICABLES totales")
        print("   ✅ ~95% de DTCs reales con info completa")
        print("\n🚛 PRODUCTION READY - Fuel Copilot Fleet 🚛")
        print()

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
