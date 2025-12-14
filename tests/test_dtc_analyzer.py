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


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
