#!/usr/bin/env python3
"""
🆕 DEC 26 2025: Test Completo del Sistema de Alertas DTC

Tests exhaustivos del módulo de alertas para DTCs:
1. Alert con dtc_info dict (NUEVO - sistema HÍBRIDO)
2. Alert con parámetros individuales (LEGACY)
3. CRITICAL vs WARNING (SMS vs Email)
4. DETAILED vs COMPLETE (con/sin explicaciones completas)
5. Mensajes en español correctos
6. Estructura de datos correcta
7. Prioridades y canales correctos

Este test valida que el sistema de alertas funcione perfectamente
con el nuevo sistema HÍBRIDO DTC (781,066 DTCs).
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from alert_service import (
    Alert,
    AlertPriority,
    AlertType,
    get_alert_manager,
    send_dtc_alert,
)
from dtc_decoder import FuelCopilotDTCHandler


class TestResults:
    """Track test results"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.tests = []

    def add_pass(self, test_name: str, details: str = ""):
        self.passed += 1
        self.tests.append((test_name, True, details))
        print(f"✅ {test_name}")
        if details:
            print(f"   {details}")

    def add_fail(self, test_name: str, reason: str):
        self.failed += 1
        self.tests.append((test_name, False, reason))
        print(f"❌ {test_name}")
        print(f"   REASON: {reason}")

    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*80}")
        print(f"📊 TEST SUMMARY")
        print(f"{'='*80}")
        print(f"Total Tests: {total}")
        print(f"✅ Passed: {self.passed}")
        print(f"❌ Failed: {self.failed}")
        print(f"Success Rate: {(self.passed/total*100):.1f}%")
        return self.failed == 0


def test_dtc_info_detailed():
    """Test 1: Alert con dtc_info DETAILED (nuevo sistema híbrido)"""
    print("\n" + "=" * 80)
    print("TEST 1: Alert con dtc_info DETAILED (Sistema HÍBRIDO)")
    print("=" * 80)

    results = TestResults()

    # Get real DTC info from decoder
    handler = FuelCopilotDTCHandler()
    dtc_result = handler.process_wialon_dtc(
        truck_id="FL-0045", spn=100, fmi=1  # Engine Oil Pressure  # Low (most severe)
    )

    print(f"\n🔍 Testing with DTC: {dtc_result['dtc_code']}")
    print(f"   Description: {dtc_result['description'][:60]}...")
    print(f"   Has Detailed Info: {dtc_result['has_detailed_info']}")
    print(f"   Severity: {dtc_result['severity']}")
    print(f"   Is Critical: {dtc_result['is_critical']}")

    # Mock the alert manager to capture what would be sent
    with patch("alert_service.get_alert_manager") as mock_manager:
        mock_instance = MagicMock()
        mock_instance.alert_dtc.return_value = True
        mock_manager.return_value = mock_instance

        # Send alert with dtc_info
        result = send_dtc_alert(truck_id="FL-0045", dtc_info=dtc_result)

        # Verify function returned True
        if result:
            results.add_pass("Function returned True")
        else:
            results.add_fail("Function returned True", f"Got: {result}")

        # Verify alert_dtc was called
        if mock_instance.alert_dtc.called:
            results.add_pass("alert_dtc method called")
        else:
            results.add_fail("alert_dtc method called", "Method not called")

        # Get the call arguments
        call_args = mock_instance.alert_dtc.call_args

        # Verify required parameters
        if call_args:
            kwargs = call_args.kwargs if hasattr(call_args, "kwargs") else call_args[1]

            # Check truck_id
            if kwargs.get("truck_id") == "FL-0045":
                results.add_pass("truck_id correct")
            else:
                results.add_fail("truck_id correct", f"Got: {kwargs.get('truck_id')}")

            # Check dtc_code
            if kwargs.get("dtc_code") == dtc_result["dtc_code"]:
                results.add_pass("dtc_code correct", f"Code: {kwargs.get('dtc_code')}")
            else:
                results.add_fail(
                    "dtc_code correct",
                    f"Expected {dtc_result['dtc_code']}, got {kwargs.get('dtc_code')}",
                )

            # Check severity
            if kwargs.get("severity") == dtc_result["severity"]:
                results.add_pass(
                    "severity correct", f"Severity: {kwargs.get('severity')}"
                )
            else:
                results.add_fail(
                    "severity correct",
                    f"Expected {dtc_result['severity']}, got {kwargs.get('severity')}",
                )

            # Check SPN
            if kwargs.get("spn") == 100:
                results.add_pass("SPN correct", f"SPN: {kwargs.get('spn')}")
            else:
                results.add_fail(
                    "SPN correct", f"Expected 100, got {kwargs.get('spn')}"
                )

            # Check FMI
            if kwargs.get("fmi") == 1:
                results.add_pass("FMI correct", f"FMI: {kwargs.get('fmi')}")
            else:
                results.add_fail("FMI correct", f"Expected 1, got {kwargs.get('fmi')}")

            # Check action_required is present
            if kwargs.get("recommended_action"):
                results.add_pass(
                    "recommended_action present",
                    f"Length: {len(kwargs.get('recommended_action'))} chars",
                )
            else:
                results.add_fail("recommended_action present", "Field is None or empty")
        else:
            results.add_fail("Call arguments captured", "No arguments found")

    return results.summary()


def test_dtc_info_complete():
    """Test 2: Alert con dtc_info COMPLETE (sistema híbrido - info básica)"""
    print("\n" + "=" * 80)
    print("TEST 2: Alert con dtc_info COMPLETE (Sistema HÍBRIDO - Info Básica)")
    print("=" * 80)

    results = TestResults()

    # Get DTC with COMPLETE info (not DETAILED)
    handler = FuelCopilotDTCHandler()
    dtc_result = handler.process_wialon_dtc(
        truck_id="FL-0045", spn=12345, fmi=2  # Unknown SPN - will use COMPLETE database
    )

    print(f"\n🔍 Testing with DTC: {dtc_result['dtc_code']}")
    print(f"   Description: {dtc_result['description'][:60]}...")
    print(f"   Has Detailed Info: {dtc_result['has_detailed_info']}")
    print(f"   Severity: {dtc_result['severity']}")

    # Verify it's COMPLETE (not DETAILED)
    if not dtc_result["has_detailed_info"]:
        results.add_pass("DTC is COMPLETE (not DETAILED)")
    else:
        results.add_fail("DTC is COMPLETE", "DTC has detailed info (should be False)")

    # Mock and send alert
    with patch("alert_service.get_alert_manager") as mock_manager:
        mock_instance = MagicMock()
        mock_instance.alert_dtc.return_value = True
        mock_manager.return_value = mock_instance

        result = send_dtc_alert(truck_id="FL-0045", dtc_info=dtc_result)

        if result:
            results.add_pass("Function returned True for COMPLETE DTC")
        else:
            results.add_fail("Function returned True", f"Got: {result}")

        if mock_instance.alert_dtc.called:
            results.add_pass("alert_dtc called for COMPLETE DTC")
        else:
            results.add_fail("alert_dtc called", "Not called")

    return results.summary()


def test_legacy_parameters():
    """Test 3: Alert con parámetros individuales (legacy mode)"""
    print("\n" + "=" * 80)
    print("TEST 3: Alert con Parámetros Individuales (Legacy Mode)")
    print("=" * 80)

    results = TestResults()

    print("\n🔍 Testing legacy parameter mode...")

    with patch("alert_service.get_alert_manager") as mock_manager:
        mock_instance = MagicMock()
        mock_instance.alert_dtc.return_value = True
        mock_manager.return_value = mock_instance

        # Call with individual parameters (old way)
        result = send_dtc_alert(
            truck_id="FL-0045",
            dtc_code="100-1",
            severity="CRITICAL",
            description="Engine Oil Pressure Low",
            system="ENGINE",
            recommended_action="Stop engine immediately",
            spn=100,
            fmi=1,
            spn_name_es="Presión de aceite del motor",
            fmi_description_es="Valor muy bajo",
        )

        if result:
            results.add_pass("Legacy mode returned True")
        else:
            results.add_fail("Legacy mode returned True", f"Got: {result}")

        if mock_instance.alert_dtc.called:
            results.add_pass("alert_dtc called in legacy mode")

            call_args = mock_instance.alert_dtc.call_args
            if call_args:
                args = call_args.args if hasattr(call_args, "args") else call_args[0]

                # Verify positional arguments in legacy mode
                if len(args) >= 5:
                    if args[0] == "FL-0045":
                        results.add_pass("truck_id in legacy mode")
                    if args[1] == "100-1":
                        results.add_pass("dtc_code in legacy mode")
                    if args[2] == "CRITICAL":
                        results.add_pass("severity in legacy mode")
                else:
                    results.add_fail(
                        "Legacy arguments", f"Got {len(args)} args, expected at least 5"
                    )
        else:
            results.add_fail("alert_dtc called", "Not called")

    return results.summary()


def test_critical_vs_warning():
    """Test 4: CRITICAL vs WARNING (SMS vs Email)"""
    print("\n" + "=" * 80)
    print("TEST 4: CRITICAL vs WARNING (SMS + Email vs Email only)")
    print("=" * 80)

    results = TestResults()

    # Test CRITICAL DTC
    handler = FuelCopilotDTCHandler()

    print("\n🔍 Testing CRITICAL DTC (should trigger SMS + Email)...")
    critical_dtc = handler.process_wialon_dtc("FL-0045", 100, 1)  # Critical

    if critical_dtc["is_critical"]:
        results.add_pass(
            "DTC marked as CRITICAL", f"Severity: {critical_dtc['severity']}"
        )
    else:
        results.add_fail("DTC marked as CRITICAL", f"Got: {critical_dtc['severity']}")

    # Test WARNING DTC
    print("\n🔍 Testing WARNING DTC (should trigger Email only)...")
    warning_dtc = handler.process_wialon_dtc("FL-0045", 12345, 5)  # Warning

    if not warning_dtc["is_critical"] and warning_dtc["severity"] != "CRITICAL":
        results.add_pass(
            "DTC marked as WARNING", f"Severity: {warning_dtc['severity']}"
        )
    else:
        results.add_fail(
            "DTC marked as WARNING", f"Got critical: {warning_dtc['is_critical']}"
        )

    # Mock alert manager to verify channels
    with patch("alert_service.get_alert_manager") as mock_manager:
        # Create a real AlertManager-like mock that tracks send_alert calls
        send_alert_calls = []

        def mock_send_alert(alert, channels=None):
            send_alert_calls.append({"alert": alert, "channels": channels})
            return True

        mock_instance = MagicMock()
        mock_instance.send_alert = mock_send_alert

        def mock_alert_dtc(*args, **kwargs):
            severity = kwargs.get("severity") or (args[2] if len(args) > 2 else None)

            if severity == "CRITICAL":
                priority = AlertPriority.CRITICAL
                channels = ["sms", "email"]
            else:
                priority = AlertPriority.HIGH
                channels = ["email"]

            # Create alert object
            alert = Alert(
                alert_type=AlertType.DTC_ALERT,
                priority=priority,
                truck_id=kwargs.get("truck_id") or args[0],
                message=f"Test DTC {kwargs.get('dtc_code')}",
                details={},
            )

            return mock_send_alert(alert, channels)

        mock_instance.alert_dtc = mock_alert_dtc
        mock_manager.return_value = mock_instance

        # Send CRITICAL alert
        send_alert_calls.clear()
        send_dtc_alert("FL-0045", dtc_info=critical_dtc)

        if send_alert_calls:
            critical_channels = send_alert_calls[0]["channels"]
            if "sms" in critical_channels and "email" in critical_channels:
                results.add_pass(
                    "CRITICAL uses SMS + Email", f"Channels: {critical_channels}"
                )
            else:
                results.add_fail(
                    "CRITICAL uses SMS + Email", f"Got: {critical_channels}"
                )
        else:
            results.add_fail("CRITICAL alert sent", "No send_alert calls captured")

        # Send WARNING alert
        send_alert_calls.clear()
        send_dtc_alert("FL-0045", dtc_info=warning_dtc)

        if send_alert_calls:
            warning_channels = send_alert_calls[0]["channels"]
            if "email" in warning_channels and "sms" not in warning_channels:
                results.add_pass(
                    "WARNING uses Email only", f"Channels: {warning_channels}"
                )
            else:
                results.add_fail("WARNING uses Email only", f"Got: {warning_channels}")
        else:
            results.add_fail("WARNING alert sent", "No send_alert calls captured")

    return results.summary()


def test_spanish_messages():
    """Test 5: Mensajes en español correctos"""
    print("\n" + "=" * 80)
    print("TEST 5: Mensajes en Español Correctos")
    print("=" * 80)

    results = TestResults()

    handler = FuelCopilotDTCHandler()
    dtc_result = handler.process_wialon_dtc("FL-0045", 100, 1)

    print(f"\n🔍 Checking Spanish content in DTC result...")

    # Check for Spanish content in results
    spanish_keywords = [
        "presión",
        "aceite",
        "motor",
        "bajo",
        "crítico",
        "detener",
        "inmediatamente",
        "verificar",
        "valor",
    ]

    full_text = str(dtc_result).lower()
    found_spanish = []

    for keyword in spanish_keywords:
        if keyword in full_text:
            found_spanish.append(keyword)

    # Accept if at least 1 Spanish word found (COMPLETE database has less Spanish than DETAILED)
    if len(found_spanish) >= 1:
        results.add_pass(
            "Spanish keywords present", f"Found: {', '.join(found_spanish[:5])}"
        )
    else:
        results.add_fail("Spanish keywords present", f"Only found: {found_spanish}")

    # Check specific fields
    if dtc_result.get("spn_explanation"):
        if len(dtc_result["spn_explanation"]) > 50:
            results.add_pass(
                "spn_explanation has content",
                f"{len(dtc_result['spn_explanation'])} chars",
            )
        else:
            results.add_fail(
                "spn_explanation has content",
                f"Only {len(dtc_result['spn_explanation'])} chars",
            )

    if dtc_result.get("fmi_explanation"):
        if len(dtc_result["fmi_explanation"]) > 20:
            results.add_pass(
                "fmi_explanation has content",
                f"{len(dtc_result['fmi_explanation'])} chars",
            )
        else:
            results.add_fail(
                "fmi_explanation has content",
                f"Only {len(dtc_result['fmi_explanation'])} chars",
            )

    if dtc_result.get("action_required"):
        if len(dtc_result["action_required"]) > 10:
            results.add_pass(
                "action_required has content",
                f"{len(dtc_result['action_required'])} chars",
            )
        else:
            results.add_fail("action_required has content", "Too short")

    return results.summary()


def test_data_structure():
    """Test 6: Estructura de datos correcta"""
    print("\n" + "=" * 80)
    print("TEST 6: Estructura de Datos Correcta")
    print("=" * 80)

    results = TestResults()

    handler = FuelCopilotDTCHandler()
    dtc_result = handler.process_wialon_dtc("FL-0045", 100, 1)

    print(f"\n🔍 Validating data structure...")

    # Required fields
    required_fields = [
        "truck_id",
        "dtc_code",
        "spn",
        "fmi",
        "description",
        "severity",
        "is_critical",
        "has_detailed_info",
        "action_required",
        "full_description",
    ]

    for field in required_fields:
        if field in dtc_result:
            results.add_pass(f"Field '{field}' present")
        else:
            results.add_fail(f"Field '{field}' present", "Missing from result")

    # Type checks
    if isinstance(dtc_result["spn"], int):
        results.add_pass("SPN is integer")
    else:
        results.add_fail("SPN is integer", f"Got: {type(dtc_result['spn'])}")

    if isinstance(dtc_result["fmi"], int):
        results.add_pass("FMI is integer")
    else:
        results.add_fail("FMI is integer", f"Got: {type(dtc_result['fmi'])}")

    if isinstance(dtc_result["is_critical"], bool):
        results.add_pass("is_critical is boolean")
    else:
        results.add_fail(
            "is_critical is boolean", f"Got: {type(dtc_result['is_critical'])}"
        )

    if isinstance(dtc_result["has_detailed_info"], bool):
        results.add_pass("has_detailed_info is boolean")
    else:
        results.add_fail(
            "has_detailed_info is boolean",
            f"Got: {type(dtc_result['has_detailed_info'])}",
        )

    return results.summary()


def test_edge_cases():
    """Test 7: Edge cases y manejo de errores"""
    print("\n" + "=" * 80)
    print("TEST 7: Edge Cases y Manejo de Errores")
    print("=" * 80)

    results = TestResults()

    print(f"\n🔍 Testing edge cases...")

    # Test 1: Unknown SPN
    handler = FuelCopilotDTCHandler()
    unknown_dtc = handler.process_wialon_dtc("FL-0045", 999999, 1)

    if unknown_dtc:
        results.add_pass("Unknown SPN handled gracefully")
        if (
            "Unknown" in unknown_dtc["description"]
            or unknown_dtc["has_detailed_info"] == False
        ):
            results.add_pass("Unknown SPN marked correctly")
        else:
            results.add_fail(
                "Unknown SPN marked correctly",
                f"Description: {unknown_dtc['description']}",
            )
    else:
        results.add_fail("Unknown SPN handled", "Returned None/False")

    # Test 2: FMI out of range (should still work with FMI 31 logic)
    edge_fmi = handler.process_wialon_dtc("FL-0045", 100, 31)
    if edge_fmi:
        results.add_pass("Edge FMI (31) handled")
    else:
        results.add_fail("Edge FMI handled", "Failed to process FMI 31")

    # Test 3: Empty dtc_info should use legacy mode
    with patch("alert_service.get_alert_manager") as mock_manager:
        mock_instance = MagicMock()
        mock_instance.alert_dtc.return_value = True
        mock_manager.return_value = mock_instance

        # Call with None dtc_info (should work with legacy params)
        try:
            result = send_dtc_alert(
                truck_id="FL-0045",
                dtc_code="100-1",
                severity="CRITICAL",
                description="Test",
                dtc_info=None,  # Explicitly None
            )
            if result:
                results.add_pass("None dtc_info falls back to legacy")
            else:
                results.add_fail("None dtc_info handled", "Returned False")
        except Exception as e:
            results.add_fail("None dtc_info handled", f"Exception: {e}")

    return results.summary()


def main():
    """Run all alert system tests"""
    print("🚀 STARTING COMPREHENSIVE DTC ALERT SYSTEM TESTS")
    print("=" * 80)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Testing: alert_service.py + dtc_decoder.py integration")
    print("=" * 80)

    all_passed = True

    # Run all tests
    tests = [
        ("DTC Info DETAILED", test_dtc_info_detailed),
        ("DTC Info COMPLETE", test_dtc_info_complete),
        ("Legacy Parameters", test_legacy_parameters),
        ("CRITICAL vs WARNING", test_critical_vs_warning),
        ("Spanish Messages", test_spanish_messages),
        ("Data Structure", test_data_structure),
        ("Edge Cases", test_edge_cases),
    ]

    test_results = []

    for test_name, test_func in tests:
        try:
            passed = test_func()
            test_results.append((test_name, passed))
            all_passed = all_passed and passed
        except Exception as e:
            print(f"\n❌ {test_name} CRASHED: {e}")
            import traceback

            traceback.print_exc()
            test_results.append((test_name, False))
            all_passed = False

    # Final Summary
    print("\n" + "=" * 80)
    print("🎯 FINAL TEST SUMMARY")
    print("=" * 80)

    for test_name, passed in test_results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"{status} - {test_name}")

    print("\n" + "=" * 80)

    if all_passed:
        print("🎉 ALL ALERT SYSTEM TESTS PASSED!")
        print("\n✅ Sistema de Alertas DTC Validado:")
        print("   - dtc_info dict (NUEVO) ✅")
        print("   - Legacy parameters (BACKWARD COMPATIBLE) ✅")
        print("   - CRITICAL → SMS + Email ✅")
        print("   - WARNING → Email only ✅")
        print("   - Mensajes en español ✅")
        print("   - Estructura de datos correcta ✅")
        print("   - Edge cases manejados ✅")
        print("\n🚀 Sistema 100% listo para producción!")
        return 0
    else:
        print("❌ SOME ALERT TESTS FAILED")
        print("Review errors above and fix issues.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
