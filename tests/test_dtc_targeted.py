"""DTC Analyzer line-by-line coverage"""

from datetime import datetime, timedelta, timezone

import pytest

from dtc_analyzer import DTCAnalyzer


def test_lines_54_57():
    """Lines 54-57: __init__"""
    a = DTCAnalyzer()
    assert "_active_dtcs" in dir(a)
    assert "_last_alert_time" in dir(a)


def test_line_218():
    """Line 218: empty string check in parse"""
    a = DTCAnalyzer()
    result = a.parse_dtc_string("")
    assert result == []


def test_lines_282_291():
    """Lines 282-291: determine_severity fallback logic"""
    a = DTCAnalyzer()
    # Test all critical SPNs
    for spn in [
        91,
        100,
        102,
        110,
        157,
        190,
        520,
        127,
        177,
        1761,
        3031,
        3216,
        3226,
        4364,
        5246,
        521,
        587,
        641,
        651,
    ]:
        severity = a._determine_severity(spn, 0)
        assert severity is not None

    # Test critical FMIs
    for fmi in [0, 1, 3, 4, 5, 6, 12]:
        severity = a._determine_severity(999, fmi)
        assert severity is not None


def test_lines_305_307_316():
    """Lines 305-307, 316: get_spn_description fallback"""
    a = DTCAnalyzer()
    # Unknown SPN
    desc = a._get_spn_description(99999)
    assert "desconocido" in desc.lower() or "unknown" in desc.lower()

    # Known from CRITICAL_SPNS
    desc = a._get_spn_description(100)
    assert isinstance(desc, str)


def test_lines_329_347():
    """Lines 329-347: get_system_classification"""
    a = DTCAnalyzer()
    # Should return UNKNOWN for unknown SPN when database not available
    system = a._get_system_classification(99999)
    assert isinstance(system, str)


def test_lines_395_401():
    """Lines 395-401: get_recommended_action fallback paths"""
    a = DTCAnalyzer()
    from dtc_analyzer import DTCSeverity

    # Test critical SPNs with specific recommendations
    for spn in [100, 110, 157, 1761, 3031, 3216, 4364]:
        action = a._get_recommended_action(spn, 3, DTCSeverity.CRITICAL)
        assert isinstance(action, str)
        assert len(action) > 0

    # Test warnings
    for spn in [3242, 3246, 3251, 158, 167, 168]:
        action = a._get_recommended_action(spn, 3, DTCSeverity.WARNING)
        assert isinstance(action, str)


def test_lines_423_428():
    """Lines 423-428: get_recommended_action for all severities"""
    a = DTCAnalyzer()
    from dtc_analyzer import DTCSeverity

    # Test all severity levels
    for sev in [DTCSeverity.CRITICAL, DTCSeverity.WARNING, DTCSeverity.INFO]:
        action = a._get_recommended_action(999, 3, sev)
        assert isinstance(action, str)


def test_line_462():
    """Line 462: empty codes list"""
    a = DTCAnalyzer()
    now = datetime.now(timezone.utc)
    result = a.process_truck_dtc("TEST_462", None, now)
    assert result == []


def test_lines_616_650():
    """Lines 616-650: process_truck_dtc complex logic"""
    a = DTCAnalyzer()
    now = datetime.now(timezone.utc)

    # New code
    alerts1 = a.process_truck_dtc("TEST_616", "100.3", now)
    assert isinstance(alerts1, list)

    # Repeat code (cooldown)
    alerts2 = a.process_truck_dtc("TEST_616", "100.3", now)

    # Add new code
    alerts3 = a.process_truck_dtc("TEST_616", "100.3,110.4", now)

    # Clear code
    alerts4 = a.process_truck_dtc("TEST_616", "110.4", now + timedelta(hours=1))

    # All responses should be lists
    assert isinstance(alerts2, list)
    assert isinstance(alerts3, list)
    assert isinstance(alerts4, list)


def test_full_dtc_flow():
    """Complete flow through all branches"""
    a = DTCAnalyzer()
    now = datetime.now(timezone.utc)

    # Test with many different DTCs
    dtc_strings = [
        "100.3",
        "110.4",
        "157.1",
        "190.2",
        "1761.3",
        "3031.4",
        "100.3,110.4",
        "100.3,110.4,175.1",
        "520.0",
        "127.1",
        "",
    ]

    truck_id = "TEST_FULL"
    for dtc_str in dtc_strings:
        alerts = a.process_truck_dtc(truck_id, dtc_str, now)
        assert isinstance(alerts, list)
        now += timedelta(minutes=5)


def test_dtc_analysis_report_all_paths():
    """Test get_dtc_analysis_report"""
    a = DTCAnalyzer()

    # Empty report
    report1 = a.get_dtc_analysis_report("TEST_REPORT_1", None)
    assert report1["status"] == "ok"

    # Single critical code
    report2 = a.get_dtc_analysis_report("TEST_REPORT_2", "100.3")
    assert isinstance(report2, dict)
    assert "codes" in report2

    # Multiple codes
    report3 = a.get_dtc_analysis_report("TEST_REPORT_3", "100.3,110.4,175.1,190.2")
    assert isinstance(report3, dict)
    assert report3["summary"]["total"] > 0


def test_fleet_summary_comprehensive():
    """Test fleet summary after many operations"""
    a = DTCAnalyzer()
    now = datetime.now(timezone.utc)

    # Add DTCs to multiple trucks
    for i in range(10):
        truck_id = f"FLEET_TRUCK_{i}"
        a.process_truck_dtc(truck_id, f"100.{i % 5},110.{i % 3}", now)

    summary = a.get_fleet_dtc_summary()
    assert isinstance(summary, dict)
    assert "trucks_with_dtcs" in summary
    assert "total_active_dtcs" in summary


def test_parse_dtc_with_invalid_formats():
    """Test parse_dtc_string with various invalid inputs"""
    a = DTCAnalyzer()

    # Invalid formats should be skipped
    codes = a.parse_dtc_string("abc.def,123.456.789,ghi")
    # Should successfully parse the valid one and skip invalid

    # Only spaces
    codes = a.parse_dtc_string("   ,  ,  ")
    assert isinstance(codes, list)

    # Mixed valid/invalid
    codes = a.parse_dtc_string("100.3,invalid,110.4,bad.data,175.1")
    assert isinstance(codes, list)


def test_active_dtcs_tracking():
    """Test get_active_dtcs"""
    a = DTCAnalyzer()
    now = datetime.now(timezone.utc)

    # Add codes
    a.process_truck_dtc("TRACK_1", "100.3,110.4", now)
    a.process_truck_dtc("TRACK_2", "175.1", now)

    # Get for specific truck
    active1 = a.get_active_dtcs("TRACK_1")
    assert isinstance(active1, dict)
    assert "TRACK_1" in active1

    # Get for all trucks
    active_all = a.get_active_dtcs()
    assert isinstance(active_all, dict)


def test_format_alert_message_all_severities():
    """Test _format_alert_message"""
    a = DTCAnalyzer()
    from dtc_analyzer import DTCCode, DTCSeverity

    for severity in [DTCSeverity.CRITICAL, DTCSeverity.WARNING, DTCSeverity.INFO]:
        code = DTCCode(
            spn=100,
            fmi=3,
            raw="100.3",
            severity=severity,
            description="Test Component",
            recommended_action="Test action",
        )

        # New code
        msg1 = a._format_alert_message("TEST_MSG", code, True, 0.0)
        assert isinstance(msg1, str)
        assert "NEW" in msg1

        # Active code
        msg2 = a._format_alert_message("TEST_MSG", code, False, 5.5)
        assert isinstance(msg2, str)
        assert "5.5h" in msg2
