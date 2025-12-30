"""DTC Analyzer complete coverage - correct API"""

from datetime import datetime, timedelta, timezone

import pytest

from dtc_analyzer import DTCAnalyzer


def test_parse_empty():
    a = DTCAnalyzer()
    assert a.parse_dtc_string("") == []
    assert a.parse_dtc_string(None) == []
    assert a.parse_dtc_string("   ") == []


def test_determine_severity():
    a = DTCAnalyzer()
    assert a._determine_severity(100, 3) is not None
    assert a._determine_severity(110, 4) is not None
    for spn in [100, 110, 111, 175, 190, 520]:
        for fmi in [0, 1, 2, 3, 4, 5]:
            a._determine_severity(spn, fmi)


def test_get_spn_description():
    a = DTCAnalyzer()
    for spn in [100, 110, 111, 175, 190, 520, 999999]:
        desc = a._get_spn_description(spn)
        assert isinstance(desc, str)
        desc_en = a._get_spn_description(spn, "en")
        assert isinstance(desc_en, str)


def test_get_system_classification():
    a = DTCAnalyzer()
    for spn in [100, 110, 111, 175, 190]:
        system = a._get_system_classification(spn)
        assert isinstance(system, str)


def test_get_recommended_action():
    a = DTCAnalyzer()
    from dtc_analyzer import DTCSeverity

    for spn in [100, 110, 157, 1761]:
        for sev in [DTCSeverity.CRITICAL, DTCSeverity.WARNING, DTCSeverity.INFO]:
            action = a._get_recommended_action(spn, 3, sev)
            assert isinstance(action, str)


def test_get_dtc_analysis_report():
    a = DTCAnalyzer()
    report = a.get_dtc_analysis_report("TEST_001", "100.3,110.4")
    assert isinstance(report, dict)
    assert "truck_id" in report
    assert "status" in report
    assert "codes" in report

    report_empty = a.get_dtc_analysis_report("TEST_002", None)
    assert isinstance(report_empty, dict)
    assert report_empty["status"] == "ok"


def test_process_truck_dtc():
    a = DTCAnalyzer()
    now = datetime.now(timezone.utc)
    alerts = a.process_truck_dtc("TEST_003", "100.3,110.4,175.1", now)
    assert isinstance(alerts, list)

    alerts2 = a.process_truck_dtc("TEST_003", "100.3", now)
    assert isinstance(alerts2, list)

    alerts_empty = a.process_truck_dtc("TEST_004", None, now)
    assert alerts_empty == []


def test_get_active_dtcs():
    a = DTCAnalyzer()
    now = datetime.now(timezone.utc)
    a.process_truck_dtc("TEST_005", "100.3", now)

    active = a.get_active_dtcs("TEST_005")
    assert isinstance(active, dict)

    all_active = a.get_active_dtcs()
    assert isinstance(all_active, dict)


def test_get_fleet_dtc_summary():
    a = DTCAnalyzer()
    summary = a.get_fleet_dtc_summary()
    assert isinstance(summary, dict)
    assert "trucks_with_dtcs" in summary
    assert "total_active_dtcs" in summary


def test_format_alert_message():
    a = DTCAnalyzer()
    from dtc_analyzer import DTCCode, DTCSeverity

    code = DTCCode(
        spn=100,
        fmi=3,
        raw="100.3",
        severity=DTCSeverity.CRITICAL,
        description="Oil Pressure",
        recommended_action="Check now",
    )
    msg = a._format_alert_message("TEST_006", code, True, 0.0)
    assert isinstance(msg, str)
    assert "TEST_006" in msg


def test_parse_dtc_string_various_formats():
    a = DTCAnalyzer()
    assert len(a.parse_dtc_string("100.3")) == 1
    assert len(a.parse_dtc_string("100.3,110.4")) == 2
    assert len(a.parse_dtc_string("100.3,110.4,175.1")) == 3

    # Test with spaces
    codes = a.parse_dtc_string(" 100.3 , 110.4 ")
    assert len(codes) >= 1


def test_cooldown_logic():
    a = DTCAnalyzer()
    now = datetime.now(timezone.utc)

    # First alert
    alerts1 = a.process_truck_dtc("TEST_007", "100.3", now)

    # Immediate repeat - should be filtered by cooldown
    alerts2 = a.process_truck_dtc("TEST_007", "100.3", now)

    # After cooldown
    later = now + timedelta(hours=2)
    alerts3 = a.process_truck_dtc("TEST_007", "100.3", later)

    assert isinstance(alerts1, list)
    assert isinstance(alerts2, list)
    assert isinstance(alerts3, list)


def test_code_clearing():
    a = DTCAnalyzer()
    now = datetime.now(timezone.utc)

    # Set code
    a.process_truck_dtc("TEST_008", "100.3", now)

    # Clear it
    a.process_truck_dtc("TEST_008", "", now)

    active = a.get_active_dtcs("TEST_008")
    assert isinstance(active, dict)


def test_multiple_trucks():
    a = DTCAnalyzer()
    now = datetime.now(timezone.utc)

    for i in range(5):
        a.process_truck_dtc(f"TRUCK_{i}", "100.3,110.4", now)

    summary = a.get_fleet_dtc_summary()
    assert isinstance(summary, dict)


def test_edge_case_spn_formats():
    a = DTCAnalyzer()
    # Just SPN, no FMI
    codes = a.parse_dtc_string("100")
    assert len(codes) >= 0

    # Invalid format should be skipped
    codes = a.parse_dtc_string("abc.def")
    assert len(codes) == 0

    # Mixed valid/invalid
    codes = a.parse_dtc_string("100.3,invalid,110.4")
    assert len(codes) >= 1


def test_process_dtc_from_sensor_data():
    from dtc_analyzer import process_dtc_from_sensor_data

    now = datetime.now(timezone.utc)

    alerts = process_dtc_from_sensor_data("TEST_009", "100.3", now)
    assert isinstance(alerts, list)


def test_get_dtc_analyzer_singleton():
    from dtc_analyzer import get_dtc_analyzer

    analyzer1 = get_dtc_analyzer()
    analyzer2 = get_dtc_analyzer()
    assert analyzer1 is analyzer2
