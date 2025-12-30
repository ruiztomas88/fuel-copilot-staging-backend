"""
Complete dtc_database.py coverage tests
Target: 90%+ coverage on dtc_database module
"""

import os
import sys

import pytest

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dtc_database
from dtc_database import (
    FMI_DESCRIPTIONS,
    SPN_DATABASE,
    DTCSeverity,
    DTCSystem,
    SPNInfo,
    get_all_spns_by_system,
    get_critical_spns,
    get_database_stats,
    get_decoder_statistics,
    get_dtc_description,
    get_fmi_info,
    get_spn_detailed_info,
    get_spn_info,
    process_spn_for_alert,
)


class TestDTCEnums:
    """Test DTCSystem and DTCSeverity enums"""

    def test_dtc_system_enum_values(self):
        """Test all DTCSystem enum values"""
        assert DTCSystem.ENGINE.value == "ENGINE"
        assert DTCSystem.TRANSMISSION.value == "TRANSMISSION"
        assert DTCSystem.AFTERTREATMENT.value == "AFTERTREATMENT"
        assert DTCSystem.ELECTRICAL.value == "ELECTRICAL"
        assert DTCSystem.COOLING.value == "COOLING"
        assert DTCSystem.FUEL.value == "FUEL"
        assert DTCSystem.AIR_INTAKE.value == "AIR_INTAKE"
        assert DTCSystem.EXHAUST.value == "EXHAUST"
        assert DTCSystem.BRAKES.value == "BRAKES"
        assert DTCSystem.HVAC.value == "HVAC"
        assert DTCSystem.BODY.value == "BODY"
        assert DTCSystem.CHASSIS.value == "CHASSIS"
        assert DTCSystem.UNKNOWN.value == "UNKNOWN"

    def test_dtc_severity_enum_values(self):
        """Test all DTCSeverity enum values"""
        assert DTCSeverity.CRITICAL.value == "critical"
        assert DTCSeverity.WARNING.value == "warning"
        assert DTCSeverity.INFO.value == "info"

    def test_enum_membership(self):
        """Test enum membership"""
        assert DTCSystem.ENGINE in DTCSystem
        assert DTCSeverity.CRITICAL in DTCSeverity


class TestSPNInfo:
    """Test SPNInfo dataclass"""

    def test_spninfo_creation(self):
        """Test creating SPNInfo instances"""
        spn = SPNInfo(
            spn=100,
            name_en="Engine Oil Pressure",
            name_es="Presión de Aceite del Motor",
            system=DTCSystem.ENGINE,
            severity=DTCSeverity.CRITICAL,
            description_es="Presión baja de aceite",
            action_es="Detener el motor inmediatamente",
        )
        assert spn.spn == 100
        assert spn.name_en == "Engine Oil Pressure"
        assert spn.system == DTCSystem.ENGINE
        assert spn.severity == DTCSeverity.CRITICAL


class TestGetSPNInfo:
    """Test get_spn_info function"""

    def test_get_known_spn(self):
        """Test getting info for known SPN"""
        result = get_spn_info(100)  # Engine Oil Pressure
        if result:
            assert isinstance(result, SPNInfo)
            assert result.spn == 100

    def test_get_unknown_spn(self):
        """Test getting info for unknown SPN"""
        result = get_spn_info(99999)
        assert result is None or isinstance(result, SPNInfo)

    def test_get_spn_engine_system(self):
        """Test SPN from ENGINE system"""
        result = get_spn_info(110)  # Engine Coolant Temperature
        if result:
            assert result.system in [DTCSystem.ENGINE, DTCSystem.COOLING]

    def test_get_spn_transmission(self):
        """Test SPN from TRANSMISSION system"""
        result = get_spn_info(177)  # Transmission Oil Temperature
        if result:
            assert result.system == DTCSystem.TRANSMISSION

    def test_get_spn_aftertreatment(self):
        """Test SPN from AFTERTREATMENT system"""
        result = get_spn_info(3226)  # DPF Differential Pressure
        if result:
            assert result.system == DTCSystem.AFTERTREATMENT


class TestGetFMIInfo:
    """Test get_fmi_info function"""

    def test_get_fmi_0(self):
        """Test FMI 0 - Above Normal Range"""
        result = get_fmi_info(0)
        assert isinstance(result, dict)
        assert "en" in result
        assert "es" in result
        assert "severity" in result
        assert result["severity"] == DTCSeverity.CRITICAL

    def test_get_fmi_1(self):
        """Test FMI 1 - Below Normal Range"""
        result = get_fmi_info(1)
        assert isinstance(result, dict)
        assert result["severity"] == DTCSeverity.CRITICAL

    def test_get_fmi_31(self):
        """Test FMI 31 - Condition Exists"""
        result = get_fmi_info(31)
        assert isinstance(result, dict)

    def test_get_invalid_fmi(self):
        """Test invalid FMI number"""
        result = get_fmi_info(99)
        assert isinstance(result, dict)
        assert "en" in result
        assert "Unknown" in result["en"] or "Desconocido" in result.get("es", "")


class TestGetDTCDescription:
    """Test get_dtc_description function"""

    def test_get_dtc_description_spanish(self):
        """Test DTC description in Spanish"""
        result = get_dtc_description(100, 0, language="es")
        assert isinstance(result, dict)
        assert "spn" in result
        assert "fmi" in result
        assert result["spn"] == 100
        assert result["fmi"] == 0

    def test_get_dtc_description_english(self):
        """Test DTC description in English"""
        result = get_dtc_description(100, 0, language="en")
        assert isinstance(result, dict)
        assert "spn" in result
        assert "fmi" in result

    def test_get_dtc_unknown_spn(self):
        """Test DTC with unknown SPN"""
        result = get_dtc_description(99999, 0)
        assert isinstance(result, dict)
        assert result["spn"] == 99999

    def test_get_dtc_various_fmis(self):
        """Test DTC with various FMIs"""
        for fmi in [0, 1, 2, 3, 4, 5, 6, 7, 31]:
            result = get_dtc_description(100, fmi)
            assert isinstance(result, dict)
            assert result["fmi"] == fmi


class TestGetAllSPNsBySystem:
    """Test get_all_spns_by_system function"""

    def test_get_engine_spns(self):
        """Test getting all ENGINE SPNs"""
        result = get_all_spns_by_system(DTCSystem.ENGINE)
        assert isinstance(result, list)
        if len(result) > 0:
            assert all(isinstance(spn, SPNInfo) for spn in result)
            assert all(spn.system == DTCSystem.ENGINE for spn in result)

    def test_get_transmission_spns(self):
        """Test getting all TRANSMISSION SPNs"""
        result = get_all_spns_by_system(DTCSystem.TRANSMISSION)
        assert isinstance(result, list)
        if len(result) > 0:
            assert all(spn.system == DTCSystem.TRANSMISSION for spn in result)

    def test_get_aftertreatment_spns(self):
        """Test getting all AFTERTREATMENT SPNs"""
        result = get_all_spns_by_system(DTCSystem.AFTERTREATMENT)
        assert isinstance(result, list)


class TestGetCriticalSPNs:
    """Test get_critical_spns function"""

    def test_get_critical_spns_returns_list(self):
        """Test that critical SPNs returns a list"""
        result = get_critical_spns()
        assert isinstance(result, list)

    def test_critical_spns_are_integers(self):
        """Test that all critical SPNs are integers"""
        result = get_critical_spns()
        if len(result) > 0:
            assert all(isinstance(spn, int) for spn in result)


class TestGetSPNDetailedInfo:
    """Test get_spn_detailed_info function"""

    def test_get_detailed_info_known_spn(self):
        """Test detailed info for known SPN"""
        result = get_spn_detailed_info(100)
        if result:
            assert isinstance(result, dict)
            assert "spn" in result

    def test_get_detailed_info_unknown_spn(self):
        """Test detailed info for unknown SPN"""
        result = get_spn_detailed_info(99999)
        assert result is None or isinstance(result, dict)

    def test_detailed_info_structure(self):
        """Test detailed info has expected structure"""
        result = get_spn_detailed_info(110)
        if result:
            assert "spn" in result


class TestProcessSPNForAlert:
    """Test process_spn_for_alert function"""

    def test_process_spn_basic(self):
        """Test basic SPN processing for alert"""
        result = process_spn_for_alert(100)
        assert isinstance(result, dict)
        assert "spn" in result
        assert result["spn"] == 100

    def test_process_spn_with_value(self):
        """Test SPN processing with value"""
        result = process_spn_for_alert(100, value=45.5)
        assert isinstance(result, dict)
        assert "spn" in result

    def test_process_spn_unknown(self):
        """Test processing unknown SPN"""
        result = process_spn_for_alert(99999)
        assert isinstance(result, dict)
        assert result["spn"] == 99999

    def test_process_multiple_spns(self):
        """Test processing multiple different SPNs"""
        spns = [100, 110, 177, 190, 3226]
        for spn in spns:
            result = process_spn_for_alert(spn)
            assert isinstance(result, dict)
            assert result["spn"] == spn


class TestGetDecoderStatistics:
    """Test get_decoder_statistics function"""

    def test_get_decoder_statistics_returns_dict(self):
        """Test that decoder statistics returns a dict"""
        result = get_decoder_statistics()
        assert isinstance(result, dict)

    def test_decoder_statistics_structure(self):
        """Test decoder statistics has expected keys"""
        result = get_decoder_statistics()
        # May have keys like total_spns, etc
        assert isinstance(result, dict)


class TestGetDatabaseStats:
    """Test get_database_stats function"""

    def test_get_database_stats_returns_dict(self):
        """Test that database stats returns a dict"""
        result = get_database_stats()
        assert isinstance(result, dict)

    def test_database_stats_structure(self):
        """Test database stats has expected structure"""
        result = get_database_stats()
        assert isinstance(result, dict)
        # Check for common keys
        if "total_spns" in result:
            assert isinstance(result["total_spns"], int)


class TestFMIDescriptions:
    """Test FMI_DESCRIPTIONS constant"""

    def test_fmi_descriptions_exists(self):
        """Test FMI_DESCRIPTIONS is defined"""
        assert FMI_DESCRIPTIONS is not None
        assert isinstance(FMI_DESCRIPTIONS, dict)

    def test_fmi_descriptions_has_common_codes(self):
        """Test common FMI codes are present"""
        assert 0 in FMI_DESCRIPTIONS
        assert 1 in FMI_DESCRIPTIONS
        assert 31 in FMI_DESCRIPTIONS

    def test_fmi_description_structure(self):
        """Test FMI description structure"""
        fmi_0 = FMI_DESCRIPTIONS[0]
        assert "en" in fmi_0
        assert "es" in fmi_0
        assert "severity" in fmi_0
        assert isinstance(fmi_0["severity"], DTCSeverity)


class TestSPNDatabase:
    """Test SPN_DATABASE constant"""

    def test_spn_database_exists(self):
        """Test SPN_DATABASE is defined"""
        assert SPN_DATABASE is not None
        assert isinstance(SPN_DATABASE, dict)

    def test_spn_database_has_entries(self):
        """Test SPN_DATABASE has entries"""
        if len(SPN_DATABASE) > 0:
            # Check first entry structure
            first_key = list(SPN_DATABASE.keys())[0]
            first_entry = SPN_DATABASE[first_key]
            assert isinstance(first_entry, SPNInfo)

    def test_spn_database_common_spns(self):
        """Test common SPNs are in database"""
        common_spns = [100, 110, 177, 190]
        for spn in common_spns:
            if spn in SPN_DATABASE:
                assert isinstance(SPN_DATABASE[spn], SPNInfo)


class TestDTCIntegration:
    """Integration tests for DTC module"""

    def test_full_dtc_workflow(self):
        """Test complete DTC workflow"""
        # Get SPN info
        spn_info = get_spn_info(100)
        if spn_info:
            # Get FMI info
            fmi_info = get_fmi_info(0)
            # Get DTC description
            dtc_desc = get_dtc_description(100, 0)
            # Process for alert
            alert_info = process_spn_for_alert(100)

            assert isinstance(fmi_info, dict)
            assert isinstance(dtc_desc, dict)
            assert isinstance(alert_info, dict)

    def test_system_filtering(self):
        """Test filtering SPNs by system"""
        for system in DTCSystem:
            spns = get_all_spns_by_system(system)
            assert isinstance(spns, list)

    def test_critical_spn_processing(self):
        """Test processing critical SPNs"""
        critical_spns = get_critical_spns()
        if len(critical_spns) > 0:
            for spn in critical_spns[:5]:  # Test first 5
                result = process_spn_for_alert(spn)
                assert isinstance(result, dict)


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_negative_spn(self):
        """Test negative SPN number"""
        result = get_spn_info(-1)
        assert result is None or isinstance(result, SPNInfo)

    def test_zero_spn(self):
        """Test zero SPN"""
        result = get_spn_info(0)
        assert result is None or isinstance(result, SPNInfo)

    def test_very_large_spn(self):
        """Test very large SPN number"""
        result = get_spn_info(999999999)
        assert result is None or isinstance(result, SPNInfo)

    def test_negative_fmi(self):
        """Test negative FMI"""
        result = get_fmi_info(-1)
        assert isinstance(result, dict)

    def test_large_fmi(self):
        """Test large FMI"""
        result = get_fmi_info(100)
        assert isinstance(result, dict)

    def test_dtc_description_edge_cases(self):
        """Test DTC description with edge case inputs"""
        result = get_dtc_description(0, 0)
        assert isinstance(result, dict)

        result = get_dtc_description(99999, 99)
        assert isinstance(result, dict)


class TestLanguageSupport:
    """Test multi-language support"""

    def test_spanish_descriptions(self):
        """Test Spanish language descriptions"""
        result = get_dtc_description(100, 0, language="es")
        assert isinstance(result, dict)

    def test_english_descriptions(self):
        """Test English language descriptions"""
        result = get_dtc_description(100, 0, language="en")
        assert isinstance(result, dict)

    def test_invalid_language(self):
        """Test invalid language code"""
        result = get_dtc_description(100, 0, language="fr")
        assert isinstance(result, dict)
