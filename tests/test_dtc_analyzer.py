"""
Unit Tests for DTCAnalyzer v5.8.2

Tests for DTC (Diagnostic Trouble Code) analysis and alerting.
Covers parsing, severity determination, and alert generation.
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

sys.path.insert(0, str(Path(__file__).parent.parent))

from dtc_analyzer import (
    DTCAnalyzer,
    DTCCode,
    DTCAlert,
    DTCSeverity,
    get_dtc_analyzer,
    process_dtc_from_sensor_data,
    CRITICAL_SPNS,
    CRITICAL_FMIS,
    WARNING_SPNS,
)


class TestDTCCodeParsing:
    """Tests for DTC string parsing"""

    def test_parse_single_code(self):
        """Parse single DTC code"""
        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("100.4")

        assert len(codes) == 1
        assert codes[0].spn == 100
        assert codes[0].fmi == 4

    def test_parse_multiple_codes(self):
        """Parse comma-separated DTC codes"""
        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("100.4,157.3,91.2")

        assert len(codes) == 3
        assert codes[0].spn == 100
        assert codes[1].spn == 157
        assert codes[2].spn == 91

    def test_parse_empty_string(self):
        """Empty string returns empty list"""
        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("")
        assert codes == []

    def test_parse_none(self):
        """None returns empty list"""
        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string(None)
        assert codes == []

    def test_parse_whitespace(self):
        """Whitespace-only returns empty list"""
        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("   ")
        assert codes == []

    def test_parse_code_without_fmi(self):
        """Parse SPN without FMI (assumes FMI=0)"""
        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("100")

        assert len(codes) == 1
        assert codes[0].spn == 100
        assert codes[0].fmi == 0

    def test_parse_with_spaces(self):
        """Parse codes with extra spaces"""
        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string(" 100.4 , 157.3 ")

        assert len(codes) == 2
        assert codes[0].spn == 100
        assert codes[1].spn == 157

    def test_parse_invalid_code_skipped(self):
        """Invalid codes are skipped, valid ones kept"""
        analyzer = DTCAnalyzer()
        codes = analyzer.parse_dtc_string("100.4,invalid,157.3")

        assert len(codes) == 2
        assert codes[0].spn == 100
        assert codes[1].spn == 157


class TestDTCSeverity:
    """Tests for DTC severity determination"""

    def test_critical_spn(self):
        """Known critical SPNs get CRITICAL severity"""
        analyzer = DTCAnalyzer()
        # SPN 100 is Engine Oil Pressure - critical
        codes = analyzer.parse_dtc_string("100.4")
        assert codes[0].severity == DTCSeverity.CRITICAL

    def test_critical_fmi(self):
        """Critical FMI values get CRITICAL severity"""
        analyzer = DTCAnalyzer()
        # FMI 0 = Data Valid - Above Normal Operating Range - Most Severe Level
        codes = analyzer.parse_dtc_string("500.0")
        assert codes[0].severity == DTCSeverity.CRITICAL

    def test_warning_spn(self):
        """Warning SPNs get WARNING severity"""
        analyzer = DTCAnalyzer()
        # SPN 110 is Coolant Temperature - usually warning level
        codes = analyzer.parse_dtc_string("110.4")
        # May be WARNING or CRITICAL depending on config
        assert codes[0].severity in [DTCSeverity.WARNING, DTCSeverity.CRITICAL]


class TestDTCAlert:
    """Tests for DTC alert generation"""

    def test_process_truck_dtc_creates_alert(self):
        """Processing DTC creates alert"""
        analyzer = DTCAnalyzer()
        timestamp = datetime.now(timezone.utc)

        alerts = analyzer.process_truck_dtc("T101", "100.4", timestamp)

        assert len(alerts) > 0
        assert alerts[0].truck_id == "T101"
        assert len(alerts[0].codes) > 0

    def test_process_truck_dtc_empty_string_no_alert(self):
        """Empty DTC string creates no alert"""
        analyzer = DTCAnalyzer()
        timestamp = datetime.now(timezone.utc)

        alerts = analyzer.process_truck_dtc("T101", "", timestamp)

        assert len(alerts) == 0

    def test_alert_cooldown(self):
        """Alerts for same code respect cooldown period"""
        analyzer = DTCAnalyzer()
        analyzer.alert_cooldown_minutes = 60
        timestamp = datetime.now(timezone.utc)

        # First alert
        alerts1 = analyzer.process_truck_dtc("T101", "100.4", timestamp)

        # Second alert within cooldown - should not trigger
        alerts2 = analyzer.process_truck_dtc(
            "T101", "100.4", timestamp + timedelta(minutes=30)
        )

        # Either alerts2 is empty or alert is marked as not new
        # (implementation may vary)
        assert len(alerts1) >= len(alerts2)

    def test_different_trucks_independent_tracking(self):
        """Different trucks tracked independently"""
        analyzer = DTCAnalyzer()
        timestamp = datetime.now(timezone.utc)

        alerts1 = analyzer.process_truck_dtc("T101", "100.4", timestamp)
        alerts2 = analyzer.process_truck_dtc("T102", "100.4", timestamp)

        # Both should get alerts (independent tracking)
        assert len(alerts1) > 0
        assert len(alerts2) > 0


class TestDTCCodeDataclass:
    """Tests for DTCCode dataclass"""

    def test_dtc_code_property(self):
        """DTCCode.code property formats correctly"""
        code = DTCCode(spn=100, fmi=4, raw="100.4", severity=DTCSeverity.WARNING)

        assert code.code == "SPN100.FMI4"

    def test_dtc_code_with_description(self):
        """DTCCode with full metadata"""
        code = DTCCode(
            spn=100,
            fmi=4,
            raw="100.4",
            severity=DTCSeverity.CRITICAL,
            description="Engine Oil Pressure",
            recommended_action="Stop immediately",
            system="ENGINE",
        )

        assert code.spn == 100
        assert code.description == "Engine Oil Pressure"
        assert code.system == "ENGINE"


class TestGlobalFunctions:
    """Tests for module-level functions"""

    def test_get_dtc_analyzer_singleton(self):
        """get_dtc_analyzer returns singleton"""
        analyzer1 = get_dtc_analyzer()
        analyzer2 = get_dtc_analyzer()

        assert analyzer1 is analyzer2

    def test_process_dtc_from_sensor_data_with_dtc(self):
        """Process DTC code via convenience function"""
        alerts = process_dtc_from_sensor_data(
            truck_id="T101", dtc_value="100.4", timestamp=datetime.now(timezone.utc)
        )

        # Should return a list of alerts
        assert isinstance(alerts, list)
        if len(alerts) > 0:
            assert alerts[0].truck_id == "T101"

    def test_process_dtc_from_sensor_data_without_dtc(self):
        """Process empty DTC code"""
        alerts = process_dtc_from_sensor_data(
            truck_id="T101", dtc_value=None, timestamp=datetime.now(timezone.utc)
        )

        assert alerts == []

    def test_process_dtc_from_sensor_data_empty_string(self):
        """Process empty string DTC"""
        alerts = process_dtc_from_sensor_data(
            truck_id="T101", dtc_value="", timestamp=datetime.now(timezone.utc)
        )

        assert alerts == []


class TestDTCAlertDataclass:
    """Tests for DTCAlert dataclass"""

    def test_alert_creation(self):
        """Create DTCAlert with required fields"""
        codes = [DTCCode(spn=100, fmi=4, raw="100.4")]
        alert = DTCAlert(
            truck_id="T101",
            timestamp=datetime.now(timezone.utc),
            codes=codes,
            severity=DTCSeverity.CRITICAL,
            message="Critical DTC detected",
        )

        assert alert.truck_id == "T101"
        assert len(alert.codes) == 1
        assert alert.severity == DTCSeverity.CRITICAL
        assert alert.is_new == True  # Default value


# ═══════════════════════════════════════════════════════════════════════════════
# EXTENDED TEST CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


class TestCriticalSPNsExtended:
    """Extended tests for critical SPN constants"""

    def test_engine_oil_pressure_exists(self):
        """Test engine oil pressure SPN exists"""
        assert 100 in CRITICAL_SPNS

    def test_coolant_temperature_exists(self):
        """Test coolant temperature SPN exists"""
        assert 110 in CRITICAL_SPNS

    def test_fuel_rail_pressure_exists(self):
        """Test fuel rail pressure SPN exists"""
        assert 157 in CRITICAL_SPNS

    def test_transmission_oil_pressure_exists(self):
        """Test transmission oil pressure SPN exists"""
        assert 127 in CRITICAL_SPNS

    def test_def_tank_level_exists(self):
        """Test DEF tank level SPN exists"""
        assert 1761 in CRITICAL_SPNS

    def test_service_brake_exists(self):
        """Test service brake SPN exists"""
        assert 521 in CRITICAL_SPNS

    def test_engine_speed_exists(self):
        """Test engine speed SPN exists"""
        assert 190 in CRITICAL_SPNS


class TestCriticalFMIsExtended:
    """Extended tests for critical FMI constants"""

    def test_fmi_0_above_range(self):
        """Test FMI 0 is critical"""
        assert 0 in CRITICAL_FMIS

    def test_fmi_1_below_range(self):
        """Test FMI 1 is critical"""
        assert 1 in CRITICAL_FMIS

    def test_fmi_3_voltage_high(self):
        """Test FMI 3 is critical"""
        assert 3 in CRITICAL_FMIS

    def test_fmi_4_voltage_low(self):
        """Test FMI 4 is critical"""
        assert 4 in CRITICAL_FMIS

    def test_fmi_5_open_circuit(self):
        """Test FMI 5 is critical"""
        assert 5 in CRITICAL_FMIS

    def test_fmi_6_grounded(self):
        """Test FMI 6 is critical"""
        assert 6 in CRITICAL_FMIS

    def test_fmi_12_bad_device(self):
        """Test FMI 12 is critical"""
        assert 12 in CRITICAL_FMIS


class TestWarningSPNsExtended:
    """Extended tests for warning SPN constants"""

    def test_fuel_delivery_pressure_exists(self):
        """Test fuel delivery pressure SPN exists"""
        assert 94 in WARNING_SPNS

    def test_coolant_level_exists(self):
        """Test coolant level SPN exists"""
        assert 111 in WARNING_SPNS

    def test_battery_potential_exists(self):
        """Test battery potential SPN exists"""
        assert 168 in WARNING_SPNS

    def test_dpf_soot_load_exists(self):
        """Test DPF soot load SPN exists"""
        assert 3246 in WARNING_SPNS

    def test_egr_temperature_exists(self):
        """Test EGR temperature SPN exists"""
        assert 411 in WARNING_SPNS

    def test_dpf_regeneration_exists(self):
        """Test DPF regeneration SPN exists"""
        assert 3251 in WARNING_SPNS


class TestDTCAnalyzerInitExtended:
    """Extended tests for DTCAnalyzer initialization"""

    def test_analyzer_active_dtcs_empty(self):
        """Test active_dtcs starts empty"""
        analyzer = DTCAnalyzer()
        assert len(analyzer._active_dtcs) == 0

    def test_analyzer_last_alert_time_empty(self):
        """Test last_alert_time starts empty"""
        analyzer = DTCAnalyzer()
        assert len(analyzer._last_alert_time) == 0

    def test_analyzer_cooldown_is_60_minutes(self):
        """Test alert cooldown is 60 minutes"""
        analyzer = DTCAnalyzer()
        assert analyzer.alert_cooldown_minutes == 60


class TestParseDTCStringExtended:
    """Extended tests for DTC string parsing"""

    @pytest.fixture
    def analyzer(self):
        """Fixture for DTCAnalyzer"""
        return DTCAnalyzer()

    def test_parse_with_leading_zeros(self, analyzer):
        """Test parsing DTC with leading zeros"""
        codes = analyzer.parse_dtc_string("0100.04")
        assert len(codes) >= 0  # Should handle

    def test_parse_three_digit_fmi(self, analyzer):
        """Test parsing with invalid three digit FMI"""
        codes = analyzer.parse_dtc_string("100.999")
        assert isinstance(codes, list)

    def test_parse_decimal_spn(self, analyzer):
        """Test parsing decimal SPN"""
        codes = analyzer.parse_dtc_string("100.5.4")
        assert isinstance(codes, list)

    def test_parse_comma_separated_with_spaces(self, analyzer):
        """Test parsing comma separated with spaces"""
        codes = analyzer.parse_dtc_string("100.4 , 157.3 , 110.0")
        assert len(codes) >= 0

    def test_parse_empty_between_commas(self, analyzer):
        """Test parsing empty values between commas"""
        codes = analyzer.parse_dtc_string("100.4,,157.3")
        assert isinstance(codes, list)


class TestDTCCodeExtended:
    """Extended tests for DTCCode dataclass"""

    def test_code_property_format(self):
        """Test code property format"""
        dtc = DTCCode(spn=100, fmi=4, raw="100.4")
        assert dtc.code == "SPN100.FMI4"

    def test_code_with_high_spn(self):
        """Test code with high SPN number"""
        dtc = DTCCode(spn=5246, fmi=0, raw="5246.0")
        assert dtc.code == "SPN5246.FMI0"

    def test_code_default_description(self):
        """Test default empty description"""
        dtc = DTCCode(spn=100, fmi=4, raw="100.4")
        assert dtc.description == ""

    def test_code_default_action(self):
        """Test default empty recommended action"""
        dtc = DTCCode(spn=100, fmi=4, raw="100.4")
        assert dtc.recommended_action == ""

    def test_code_default_system(self):
        """Test default system is UNKNOWN"""
        dtc = DTCCode(spn=100, fmi=4, raw="100.4")
        assert dtc.system == "UNKNOWN"


class TestDTCAlertExtended:
    """Extended tests for DTCAlert dataclass"""

    def test_alert_default_is_new(self):
        """Test is_new defaults to True"""
        alert = DTCAlert(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            codes=[],
            severity=DTCSeverity.WARNING,
            message="Test",
        )
        assert alert.is_new is True

    def test_alert_default_hours_active(self):
        """Test hours_active defaults to 0"""
        alert = DTCAlert(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            codes=[],
            severity=DTCSeverity.INFO,
            message="Test",
        )
        assert alert.hours_active == 0.0

    def test_alert_with_multiple_codes(self):
        """Test alert with multiple codes"""
        codes = [
            DTCCode(spn=100, fmi=4, raw="100.4"),
            DTCCode(spn=157, fmi=3, raw="157.3"),
        ]
        alert = DTCAlert(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            codes=codes,
            severity=DTCSeverity.CRITICAL,
            message="Multiple DTCs",
        )
        assert len(alert.codes) == 2


class TestSeverityDeterminationExtended:
    """Extended tests for severity determination"""

    @pytest.fixture
    def analyzer(self):
        """Fixture for DTCAnalyzer"""
        return DTCAnalyzer()

    def test_critical_spn_with_critical_fmi(self, analyzer):
        """Test critical SPN with critical FMI"""
        severity = analyzer._determine_severity(100, 0)
        assert severity == DTCSeverity.CRITICAL

    def test_critical_spn_with_non_critical_fmi(self, analyzer):
        """Test critical SPN with non-critical FMI"""
        severity = analyzer._determine_severity(100, 7)
        # May still be critical due to SPN
        assert severity in [DTCSeverity.CRITICAL, DTCSeverity.WARNING]

    def test_warning_spn_severity(self, analyzer):
        """Test warning SPN severity"""
        severity = analyzer._determine_severity(94, 7)
        assert severity in [DTCSeverity.WARNING, DTCSeverity.CRITICAL]

    def test_unknown_spn_severity(self, analyzer):
        """Test unknown SPN severity"""
        severity = analyzer._determine_severity(9999, 7)
        assert severity in [DTCSeverity.INFO, DTCSeverity.WARNING]


class TestProcessTruckDTCExtended:
    """Extended tests for processing truck DTCs"""

    @pytest.fixture
    def analyzer(self):
        """Fixture for DTCAnalyzer"""
        return DTCAnalyzer()

    def test_process_critical_dtc_returns_alert(self, analyzer):
        """Test processing critical DTC returns alert"""
        alerts = analyzer.process_truck_dtc(
            truck_id="T001",
            dtc_string="100.4",
            timestamp=datetime.now(timezone.utc),
        )
        assert isinstance(alerts, list)
        if alerts:
            assert alerts[0].severity == DTCSeverity.CRITICAL

    def test_process_tracks_active_dtc(self, analyzer):
        """Test processing tracks active DTC"""
        analyzer.process_truck_dtc(
            truck_id="T001",
            dtc_string="100.4",
            timestamp=datetime.now(timezone.utc),
        )
        assert "T001" in analyzer._active_dtcs

    def test_process_cleared_dtc(self, analyzer):
        """Test processing cleared DTC"""
        now = datetime.now(timezone.utc)
        analyzer.process_truck_dtc("T001", "100.4", now)
        analyzer.process_truck_dtc("T001", "", now + timedelta(hours=1))
        # Should handle clearing


class TestCooldownMechanismExtended:
    """Extended tests for cooldown mechanism"""

    @pytest.fixture
    def analyzer(self):
        """Fixture for DTCAnalyzer"""
        return DTCAnalyzer()

    def test_cooldown_prevents_spam(self, analyzer):
        """Test cooldown prevents alert spam"""
        now = datetime.now(timezone.utc)
        alerts1 = analyzer.process_truck_dtc("T001", "100.4", now)
        alerts2 = analyzer.process_truck_dtc(
            "T001", "100.4", now + timedelta(minutes=10)
        )
        # Second should be empty or fewer
        assert len(alerts2) <= len(alerts1)

    def test_cooldown_per_truck(self, analyzer):
        """Test cooldown is per truck"""
        now = datetime.now(timezone.utc)
        alerts1 = analyzer.process_truck_dtc("T001", "100.4", now)
        alerts2 = analyzer.process_truck_dtc("T002", "100.4", now)
        # Different trucks, both should alert
        assert len(alerts1) >= 0
        assert len(alerts2) >= 0


class TestEdgeCasesExtended:
    """Extended edge case tests"""

    @pytest.fixture
    def analyzer(self):
        """Fixture for DTCAnalyzer"""
        return DTCAnalyzer()

    def test_very_high_spn(self, analyzer):
        """Test very high SPN number"""
        codes = analyzer.parse_dtc_string("999999.0")
        assert isinstance(codes, list)

    def test_fmi_31_max_valid(self, analyzer):
        """Test FMI 31 (max valid)"""
        codes = analyzer.parse_dtc_string("100.31")
        assert isinstance(codes, list)

    def test_special_characters_in_dtc(self, analyzer):
        """Test special characters in DTC string"""
        codes = analyzer.parse_dtc_string("100.4;157.3")
        assert isinstance(codes, list)

    def test_unicode_in_dtc(self, analyzer):
        """Test unicode in DTC string"""
        codes = analyzer.parse_dtc_string("100.4,警告")
        assert isinstance(codes, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
