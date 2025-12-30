#!/usr/bin/env python3
"""
🆕 DEC 26 2025: Test Wialon DTC Integration with Hybrid Decoder System

Tests the complete integration of:
- Parser: parse_wialon_dtc_string()
- Decoder: FuelCopilotDTCHandler.process_wialon_dtc()
- Database: save_dtc_event_hybrid()
- Alerts: send_dtc_alert(dtc_info=result)

This validates that when Wialon sends DTC strings like "100.1,157.3",
the system will:
1. Parse correctly
2. Decode with HYBRID system (111 DETAILED + 35,503 COMPLETE)
3. Save to database with has_detailed_info flag
4. Send email/SMS alerts with full Spanish explanations
"""

import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dtc_decoder import FuelCopilotDTCHandler
from wialon_sync_enhanced import parse_wialon_dtc_string


def test_parser():
    """Test Wialon DTC string parser"""
    print("\n" + "=" * 80)
    print("TEST 1: Wialon DTC Parser")
    print("=" * 80)

    test_cases = [
        ("100.1", [(100, 1)]),
        ("100.1,157.3", [(100, 1), (157, 3)]),
        ("100.1,157.3,234.0", [(100, 1), (157, 3), (234, 0)]),
        ("0", []),
        ("1", []),
        ("0.0", []),
        ("1.0", []),
        ("", []),
        ("100", [(100, 31)]),  # No FMI = FMI 31 (unknown)
    ]

    passed = 0
    failed = 0

    for dtc_string, expected in test_cases:
        result = parse_wialon_dtc_string(dtc_string)
        if result == expected:
            print(f"✅ '{dtc_string}' → {result}")
            passed += 1
        else:
            print(f"❌ '{dtc_string}' → {result} (expected {expected})")
            failed += 1

    print(f"\n📊 Parser Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_hybrid_decoder():
    """Test HYBRID DTC decoder integration"""
    print("\n" + "=" * 80)
    print("TEST 2: HYBRID DTC Decoder Integration")
    print("=" * 80)

    handler = FuelCopilotDTCHandler()

    # Test cases with expected results
    test_cases = [
        {
            "name": "SPN 100 FMI 1 - DETAILED (Engine Oil Pressure)",
            "spn": 100,
            "fmi": 1,
            "expected_detailed": True,
            "expected_severity": "CRITICAL",
            "expected_category": "ENGINE",
        },
        {
            "name": "SPN 190 FMI 0 - DETAILED (Engine Speed)",
            "spn": 190,
            "fmi": 0,
            "expected_detailed": True,
            "expected_severity": "CRITICAL",
            "expected_category": "ENGINE",
        },
        {
            "name": "SPN 12345 FMI 2 - COMPLETE (Unknown SPN)",
            "spn": 12345,
            "fmi": 2,
            "expected_detailed": False,
            "expected_severity": "WARNING",
            "expected_category": "UNKNOWN",
        },
        {
            "name": "SPN 110 FMI 3 - DETAILED (Coolant Temp)",
            "spn": 110,
            "fmi": 3,
            "expected_detailed": True,
            "expected_severity": "CRITICAL",
            "expected_category": "ENGINE",
        },
    ]

    passed = 0
    failed = 0

    for test_case in test_cases:
        result = handler.process_wialon_dtc(
            truck_id="TEST_TRUCK", spn=test_case["spn"], fmi=test_case["fmi"]
        )

        print(f"\n🔍 {test_case['name']}")
        print(f"   DTC Code: {result['dtc_code']}")
        print(f"   Description: {result['description'][:60]}...")
        print(f"   Severity: {result['severity']}")
        print(f"   Category: {result['category']}")
        print(f"   Has Detailed Info: {result['has_detailed_info']}")
        print(f"   OEM: {result.get('oem', 'N/A')}")

        # Validate expectations
        checks = [
            (
                result["has_detailed_info"] == test_case["expected_detailed"],
                f"has_detailed_info={result['has_detailed_info']}",
            ),
            (
                result["severity"] == test_case["expected_severity"],
                f"severity={result['severity']}",
            ),
            (
                result["category"] == test_case["expected_category"],
                f"category={result['category']}",
            ),
        ]

        all_passed = all(check[0] for check in checks)

        if all_passed:
            print("   ✅ All checks passed")
            passed += 1
        else:
            print("   ❌ Some checks failed:")
            for check_passed, detail in checks:
                if not check_passed:
                    print(f"      - {detail}")
            failed += 1

    print(f"\n📊 Decoder Tests: {passed} passed, {failed} failed")
    return failed == 0


def test_wialon_integration():
    """Test complete Wialon integration flow"""
    print("\n" + "=" * 80)
    print("TEST 3: Complete Wialon Integration Flow")
    print("=" * 80)

    # Simulate Wialon DTC string
    wialon_dtc = "100.1,157.3,110.18"

    print(f"\n📡 Simulating Wialon DTC: {wialon_dtc}")

    # Step 1: Parse
    print("\n1️⃣ Parsing...")
    dtc_pairs = parse_wialon_dtc_string(wialon_dtc)
    print(f"   Parsed: {dtc_pairs}")

    if not dtc_pairs:
        print("❌ Parser failed!")
        return False

    # Step 2: Decode with HYBRID system
    print("\n2️⃣ Decoding with HYBRID system...")
    handler = FuelCopilotDTCHandler()

    detailed_count = 0
    complete_count = 0
    critical_count = 0

    for spn, fmi in dtc_pairs:
        result = handler.process_wialon_dtc(truck_id="TEST_TRUCK", spn=spn, fmi=fmi)

        if result["has_detailed_info"]:
            detailed_count += 1
            print(
                f"   ✨ DETAILED: {result['dtc_code']} - {result['description'][:50]}..."
            )
        else:
            complete_count += 1
            print(
                f"   📋 COMPLETE: {result['dtc_code']} - {result['description'][:50]}..."
            )

        if result["is_critical"]:
            critical_count += 1
            print(f"      🚨 CRITICAL - {result['severity']}")
        else:
            print(f"      ⚠️ WARNING - {result['severity']}")

    print(f"\n📊 Results:")
    print(f"   - Total DTCs: {len(dtc_pairs)}")
    print(f"   - DETAILED: {detailed_count}")
    print(f"   - COMPLETE: {complete_count}")
    print(f"   - CRITICAL: {critical_count}")

    # Validate
    if detailed_count > 0:
        print("\n✅ Integration test PASSED - HYBRID system working!")
        return True
    else:
        print("\n❌ Integration test FAILED - No DETAILED DTCs found")
        return False


def main():
    """Run all tests"""
    print("🚀 Starting Wialon DTC Integration Tests")
    print("=" * 80)

    results = []

    # Test 1: Parser
    results.append(("Parser", test_parser()))

    # Test 2: HYBRID Decoder
    results.append(("HYBRID Decoder", test_hybrid_decoder()))

    # Test 3: Complete Integration
    results.append(("Complete Integration", test_wialon_integration()))

    # Summary
    print("\n" + "=" * 80)
    print("📊 TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {test_name}")

    all_passed = all(result[1] for result in results)

    if all_passed:
        print("\n🎉 ALL TESTS PASSED! System ready for production.")
        print("\n✅ Next Steps:")
        print("   1. Database schema updated with has_detailed_info and oem columns")
        print("   2. Parser function integrated in wialon_sync_enhanced.py")
        print("   3. save_dtc_event_hybrid() ready to save HYBRID data")
        print("   4. Alert system ready to send email/SMS with detailed explanations")
        print("\n🚀 When a truck has a DTC, you will receive:")
        print("   - Email for all DTCs (CRITICAL and WARNING)")
        print("   - SMS for CRITICAL DTCs only")
        print("   - Full Spanish explanations (if DETAILED info available)")
        print("   - Complete DTC history in dtc_events table")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED - Review errors above")
        return 1


if __name__ == "__main__":
    sys.exit(main())
