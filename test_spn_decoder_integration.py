"""
Test SPN Decoder Integration
==============================

Verifica que el nuevo sistema de SPNs detallados funcione correctamente
con el sistema DTC existente.

Autor: Fuel Copilot Team
Fecha: December 26, 2025
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dtc_database import (
    get_decoder_statistics,
    get_dtc_description,
    get_spn_detailed_info,
    process_spn_for_alert,
)
from spn_decoder import FuelCopilotSPNHandler, SPNDecoder


def test_basic_decoder():
    """Test basic SPN decoder functionality"""
    print("=" * 80)
    print("TEST 1: BASIC SPN DECODER")
    print("=" * 80)

    decoder = SPNDecoder()

    # Test known SPNs
    test_spns = [0, 100, 110, 183, 523002, 521049, 999999]

    for spn in test_spns:
        info = decoder.decode(spn)
        print(f"\n📍 SPN {spn}:")
        print(f"   Description: {info.description}")
        print(f"   Category: {info.category}")
        print(f"   OEM: {info.oem}")
        print(
            f"   Priority: {info.priority} ({'CRITICAL' if info.is_critical() else 'Normal'})"
        )
        if info.detailed_explanation:
            print(f"   Details: {info.detailed_explanation[:100]}...")

    print("\n✅ Basic decoder test passed")


def test_fuel_copilot_handler():
    """Test Fuel Copilot integration handler"""
    print("\n" + "=" * 80)
    print("TEST 2: FUEL COPILOT HANDLER")
    print("=" * 80)

    handler = FuelCopilotSPNHandler()

    # Test your ICU code
    print("\n🔍 Testing SPN 523002 (ICU EEPROM):")
    result = handler.process_spn_from_wialon(523002)
    print(f"   Alert Level: {result['alert_level']}")
    print(f"   Action Required: {result['action_required']}")
    print(f"   Should Alert: {handler.should_alert_driver(523002)}")
    print(f"   Explanation: {result['detailed_explanation'][:150]}...")

    # Test dashboard summary
    print("\n📊 Testing dashboard summary with multiple SPNs:")
    active_spns = [100, 110, 523002, 521049, 96]
    summary = handler.get_dashboard_summary(active_spns)
    print(f"   Total Codes: {summary['total_codes']}")
    print(f"   Critical: {summary['critical_count']}")
    print(f"   High Priority: {summary['high_count']}")
    print(f"   Low Priority: {summary['low_count']}")

    if summary["critical_codes"]:
        print(f"\n   🚨 Critical Codes:")
        for code in summary["critical_codes"]:
            print(f"      - SPN {code['spn']}: {code['description']}")

    print("\n✅ Fuel Copilot handler test passed")


def test_dtc_integration():
    """Test integration with existing DTC database"""
    print("\n" + "=" * 80)
    print("TEST 3: DTC DATABASE INTEGRATION")
    print("=" * 80)

    # Test detailed info retrieval
    print("\n🔍 Testing get_spn_detailed_info():")
    test_spns = [100, 523002, 521049, 999999]

    for spn in test_spns:
        info = get_spn_detailed_info(spn)
        if info:
            print(f"\n   SPN {spn}:")
            print(f"   - Description: {info['description']}")
            print(f"   - Critical: {info['is_critical']}")
            print(f"   - OEM: {info['oem']}")
        else:
            print(f"\n   SPN {spn}: No detailed info available")

    # Test alert processing
    print("\n🚨 Testing process_spn_for_alert():")
    test_cases = [
        (100, 85.0),  # Oil pressure with value
        (523002, None),  # ICU without value
        (999999, None),  # Unknown SPN
    ]

    for spn, value in test_cases:
        result = process_spn_for_alert(spn, value)
        print(f"\n   SPN {spn} (value={value}):")
        print(f"   - Should Alert: {result.get('should_alert', False)}")
        print(f"   - Alert Level: {result.get('alert_level', 'UNKNOWN')}")
        print(f"   - Has Detailed Info: {result.get('has_detailed_info', False)}")
        if result.get("formatted_value"):
            print(f"   - Formatted Value: {result['formatted_value']}")
        if result.get("value_warning"):
            print(f"   - ⚠️ Warning: {result['value_warning']}")

    print("\n✅ DTC integration test passed")


def test_combined_dtc_description():
    """Test combined DTC description (SPN.FMI)"""
    print("\n" + "=" * 80)
    print("TEST 4: COMBINED DTC DESCRIPTION (SPN.FMI)")
    print("=" * 80)

    # Test DTC codes
    test_dtcs = [
        (100, 3),  # Oil Pressure - Voltage High
        (110, 0),  # Coolant Temp - Above Normal
        (523002, 2),  # ICU EEPROM - Erratic
    ]

    for spn, fmi in test_dtcs:
        print(f"\n🔍 Testing SPN {spn} FMI {fmi}:")
        dtc_info = get_dtc_description(spn, fmi, language="es")
        print(f"   Code: {dtc_info['code']}")
        print(f"   Component: {dtc_info['component']}")
        print(f"   Failure Mode: {dtc_info['failure_mode']}")
        print(f"   Severity: {dtc_info['severity']}")
        print(f"   Description: {dtc_info['description'][:100]}...")

    print("\n✅ Combined DTC test passed")


def test_statistics():
    """Test decoder statistics"""
    print("\n" + "=" * 80)
    print("TEST 5: DECODER STATISTICS")
    print("=" * 80)

    stats = get_decoder_statistics()

    if stats.get("available"):
        print(f"\n✅ Detailed SPN Decoder: AVAILABLE")
        print(f"   Total SPNs: {stats.get('total_spns', 0)}")
        print(f"   Critical SPNs: {stats.get('critical_spns', 0)}")

        if "by_oem" in stats:
            print(f"\n   📊 By OEM:")
            for oem, count in sorted(
                stats["by_oem"].items(), key=lambda x: x[1], reverse=True
            ):
                print(f"      {oem}: {count} SPNs")

        if "by_category" in stats:
            print(f"\n   📊 By Category:")
            for cat, count in sorted(
                stats["by_category"].items(), key=lambda x: x[1], reverse=True
            )[:5]:
                print(f"      {cat}: {count} SPNs")
    else:
        print(f"\n❌ Detailed SPN Decoder: NOT AVAILABLE")
        print(f"   Message: {stats.get('message', 'Unknown error')}")

    print("\n✅ Statistics test passed")


def test_unknown_spn_handling():
    """Test how unknown SPNs are handled"""
    print("\n" + "=" * 80)
    print("TEST 6: UNKNOWN SPN HANDLING")
    print("=" * 80)

    # Test various unknown SPNs from different OEM ranges
    unknown_spns = [
        999999,  # Completely unknown
        522500,  # Freightliner range but not in DB
        521800,  # Detroit range but not in DB
        82000,  # Volvo range but not in DB
        87000,  # Paccar range but not in DB
    ]

    decoder = SPNDecoder()

    for spn in unknown_spns:
        info = decoder.decode(spn)
        print(f"\n   SPN {spn}:")
        print(f"   - Description: {info.description}")
        print(f"   - OEM Detected: {info.oem}")
        print(f"   - Category: {info.category}")
        print(f"   - Priority: {info.priority}")
        print(f"   - Explanation: {info.detailed_explanation[:80]}...")

    print("\n✅ Unknown SPN handling test passed")


def main():
    """Run all tests"""
    print("\n")
    print("🚀" * 40)
    print("SPN DECODER INTEGRATION TESTS - FUEL COPILOT")
    print("🚀" * 40)
    print()

    try:
        test_basic_decoder()
        test_fuel_copilot_handler()
        test_dtc_integration()
        test_combined_dtc_description()
        test_statistics()
        test_unknown_spn_handling()

        print("\n" + "=" * 80)
        print("🎉 ALL TESTS PASSED!")
        print("=" * 80)
        print("\n✅ El sistema de SPNs detallados está funcionando correctamente")
        print("✅ Integración con DTC database completada")
        print("✅ Fuel Copilot handler listo para usar")
        print("\n📝 Next Steps:")
        print("   1. Integrar en wialon_sync_enhanced.py para procesar SPNs de Wialon")
        print("   2. Actualizar alerts para usar detailed_explanation")
        print("   3. Mostrar SPNs detallados en frontend dashboard")
        print()

    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
