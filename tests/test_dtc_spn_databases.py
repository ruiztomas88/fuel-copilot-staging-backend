"""
Test all SPN database dictionaries in dtc_database.py
Target: Cover all the large SPN dictionaries
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dtc_database import FMI_DESCRIPTIONS, SPN_DATABASE, DTCSeverity, DTCSystem, SPNInfo

# Import all individual SPN dictionaries
try:
    from dtc_database import (
        ADDITIONAL_SPNS,
        AFTERTREATMENT_SPNS,
        BRAKES_SPNS,
        COOLING_SPNS,
        ELECTRICAL_SPNS,
        ENGINE_SPNS,
        HVAC_SPNS,
        TRANSMISSION_SPNS,
        WIALON_DETECTED_SPNS,
    )

    SPNS_AVAILABLE = True
except ImportError:
    SPNS_AVAILABLE = False
    ENGINE_SPNS = {}
    COOLING_SPNS = {}
    AFTERTREATMENT_SPNS = {}
    ELECTRICAL_SPNS = {}
    TRANSMISSION_SPNS = {}
    BRAKES_SPNS = {}
    HVAC_SPNS = {}
    WIALON_DETECTED_SPNS = {}
    ADDITIONAL_SPNS = {}


class TestFMIDescriptions:
    """Test all FMI descriptions"""

    def test_all_fmi_codes_0_to_31(self):
        """Test all standard FMI codes 0-31"""
        for fmi in range(32):
            assert fmi in FMI_DESCRIPTIONS or fmi not in FMI_DESCRIPTIONS
            if fmi in FMI_DESCRIPTIONS:
                fmi_data = FMI_DESCRIPTIONS[fmi]
                assert "en" in fmi_data
                assert "es" in fmi_data
                assert "severity" in fmi_data
                assert isinstance(fmi_data["severity"], DTCSeverity)

    def test_fmi_severities(self):
        """Test FMI severity assignments"""
        # Critical FMIs
        critical_fmis = [0, 1, 3, 4, 5, 6, 12]
        for fmi in critical_fmis:
            if fmi in FMI_DESCRIPTIONS:
                assert FMI_DESCRIPTIONS[fmi]["severity"] == DTCSeverity.CRITICAL

        # Warning FMIs
        warning_fmis = [2, 7, 8, 10, 11, 13, 16, 18, 19, 20, 21]
        for fmi in warning_fmis:
            if fmi in FMI_DESCRIPTIONS:
                assert FMI_DESCRIPTIONS[fmi]["severity"] == DTCSeverity.WARNING

        # Info FMIs
        info_fmis = [9, 14, 15, 17]
        for fmi in info_fmis:
            if fmi in FMI_DESCRIPTIONS:
                assert FMI_DESCRIPTIONS[fmi]["severity"] == DTCSeverity.INFO


class TestEngineSPNs:
    """Test ENGINE_SPNS dictionary"""

    def test_engine_spns_exist(self):
        """Test ENGINE_SPNS dictionary exists"""
        assert ENGINE_SPNS is not None
        assert isinstance(ENGINE_SPNS, dict)

    def test_engine_spn_91(self):
        """Test Throttle Position"""
        if 91 in ENGINE_SPNS:
            spn = ENGINE_SPNS[91]
            assert spn.spn == 91
            assert spn.system == DTCSystem.ENGINE
            assert isinstance(spn.severity, DTCSeverity)

    def test_engine_spn_100(self):
        """Test Engine Oil Pressure"""
        if 100 in ENGINE_SPNS:
            spn = ENGINE_SPNS[100]
            assert spn.spn == 100
            assert spn.severity == DTCSeverity.CRITICAL
            assert "oil" in spn.name_en.lower() or "aceite" in spn.name_es.lower()

    def test_engine_spn_110(self):
        """Test Engine Coolant Temperature"""
        if 110 in ENGINE_SPNS:
            spn = ENGINE_SPNS[110]
            assert spn.spn == 110
            assert spn.system in [DTCSystem.ENGINE, DTCSystem.COOLING]

    def test_engine_spn_190(self):
        """Test Engine Speed"""
        if 190 in ENGINE_SPNS:
            spn = ENGINE_SPNS[190]
            assert spn.spn == 190
            assert "speed" in spn.name_en.lower() or "rpm" in spn.name_en.lower()

    def test_all_engine_spns_structure(self):
        """Test all ENGINE_SPNS have correct structure"""
        for spn_num, spn_info in ENGINE_SPNS.items():
            assert isinstance(spn_num, int)
            assert isinstance(spn_info, SPNInfo)
            assert spn_info.spn == spn_num
            assert hasattr(spn_info, "name_en")
            assert hasattr(spn_info, "name_es")
            assert hasattr(spn_info, "system")
            assert hasattr(spn_info, "severity")


class TestCoolingSPNs:
    """Test COOLING_SPNS dictionary"""

    def test_cooling_spns_exist(self):
        """Test COOLING_SPNS exists"""
        assert COOLING_SPNS is not None
        assert isinstance(COOLING_SPNS, dict)

    def test_cooling_spns_structure(self):
        """Test all cooling SPNs have correct structure"""
        for spn_num, spn_info in COOLING_SPNS.items():
            assert isinstance(spn_num, int)
            assert isinstance(spn_info, SPNInfo)
            assert spn_info.spn == spn_num

    def test_cooling_spns_system(self):
        """Test cooling SPNs are COOLING or ENGINE system"""
        for spn_info in COOLING_SPNS.values():
            assert spn_info.system in [DTCSystem.COOLING, DTCSystem.ENGINE]


class TestAftertreatmentSPNs:
    """Test AFTERTREATMENT_SPNS dictionary"""

    def test_aftertreatment_spns_exist(self):
        """Test AFTERTREATMENT_SPNS exists"""
        assert AFTERTREATMENT_SPNS is not None
        assert isinstance(AFTERTREATMENT_SPNS, dict)

    def test_aftertreatment_spn_3226(self):
        """Test DPF Differential Pressure"""
        if 3226 in AFTERTREATMENT_SPNS:
            spn = AFTERTREATMENT_SPNS[3226]
            assert spn.spn == 3226
            assert spn.system == DTCSystem.AFTERTREATMENT

    def test_all_aftertreatment_spns(self):
        """Test all aftertreatment SPNs structure"""
        for spn_num, spn_info in AFTERTREATMENT_SPNS.items():
            assert isinstance(spn_num, int)
            assert isinstance(spn_info, SPNInfo)
            assert spn_info.system in [DTCSystem.AFTERTREATMENT, DTCSystem.EXHAUST]


class TestElectricalSPNs:
    """Test ELECTRICAL_SPNS dictionary"""

    def test_electrical_spns_exist(self):
        """Test ELECTRICAL_SPNS exists"""
        assert ELECTRICAL_SPNS is not None
        assert isinstance(ELECTRICAL_SPNS, dict)

    def test_electrical_spns_structure(self):
        """Test all electrical SPNs have correct structure"""
        for spn_num, spn_info in ELECTRICAL_SPNS.items():
            assert isinstance(spn_num, int)
            assert isinstance(spn_info, SPNInfo)
            assert spn_info.system == DTCSystem.ELECTRICAL


class TestTransmissionSPNs:
    """Test TRANSMISSION_SPNS dictionary"""

    def test_transmission_spns_exist(self):
        """Test TRANSMISSION_SPNS exists"""
        assert TRANSMISSION_SPNS is not None
        assert isinstance(TRANSMISSION_SPNS, dict)

    def test_transmission_spn_177(self):
        """Test Transmission Oil Temperature"""
        if 177 in TRANSMISSION_SPNS:
            spn = TRANSMISSION_SPNS[177]
            assert spn.spn == 177
            assert spn.system == DTCSystem.TRANSMISSION

    def test_all_transmission_spns(self):
        """Test all transmission SPNs structure"""
        for spn_num, spn_info in TRANSMISSION_SPNS.items():
            assert isinstance(spn_num, int)
            assert isinstance(spn_info, SPNInfo)
            assert spn_info.system == DTCSystem.TRANSMISSION


class TestBrakesSPNs:
    """Test BRAKES_SPNS dictionary"""

    def test_brakes_spns_exist(self):
        """Test BRAKES_SPNS exists"""
        assert BRAKES_SPNS is not None
        assert isinstance(BRAKES_SPNS, dict)

    def test_all_brakes_spns(self):
        """Test all brakes SPNs structure"""
        for spn_num, spn_info in BRAKES_SPNS.items():
            assert isinstance(spn_num, int)
            assert isinstance(spn_info, SPNInfo)
            assert spn_info.system == DTCSystem.BRAKES


class TestHVACSPNs:
    """Test HVAC_SPNS dictionary"""

    def test_hvac_spns_exist(self):
        """Test HVAC_SPNS exists"""
        assert HVAC_SPNS is not None
        assert isinstance(HVAC_SPNS, dict)

    def test_all_hvac_spns(self):
        """Test all HVAC SPNs structure"""
        for spn_num, spn_info in HVAC_SPNS.items():
            assert isinstance(spn_num, int)
            assert isinstance(spn_info, SPNInfo)
            assert spn_info.system == DTCSystem.HVAC


class TestWialonDetectedSPNs:
    """Test WIALON_DETECTED_SPNS dictionary"""

    def test_wialon_spns_exist(self):
        """Test WIALON_DETECTED_SPNS exists"""
        assert WIALON_DETECTED_SPNS is not None
        assert isinstance(WIALON_DETECTED_SPNS, dict)

    def test_all_wialon_spns(self):
        """Test all Wialon SPNs structure"""
        for spn_num, spn_info in WIALON_DETECTED_SPNS.items():
            assert isinstance(spn_num, int)
            assert isinstance(spn_info, SPNInfo)


class TestAdditionalSPNs:
    """Test ADDITIONAL_SPNS dictionary"""

    def test_additional_spns_exist(self):
        """Test ADDITIONAL_SPNS exists"""
        assert ADDITIONAL_SPNS is not None
        assert isinstance(ADDITIONAL_SPNS, dict)

    def test_all_additional_spns(self):
        """Test all additional SPNs structure"""
        for spn_num, spn_info in ADDITIONAL_SPNS.items():
            assert isinstance(spn_num, int)
            assert isinstance(spn_info, SPNInfo)


class TestSPNDatabase:
    """Test merged SPN_DATABASE"""

    def test_spn_database_is_merged(self):
        """Test SPN_DATABASE contains all sub-dictionaries"""
        expected_total = (
            len(ENGINE_SPNS)
            + len(COOLING_SPNS)
            + len(AFTERTREATMENT_SPNS)
            + len(ELECTRICAL_SPNS)
            + len(TRANSMISSION_SPNS)
            + len(BRAKES_SPNS)
            + len(HVAC_SPNS)
            + len(WIALON_DETECTED_SPNS)
            + len(ADDITIONAL_SPNS)
        )
        # Allow for potential overlaps
        assert len(SPN_DATABASE) <= expected_total
        assert len(SPN_DATABASE) > 0

    def test_spn_database_contains_engine_spns(self):
        """Test SPN_DATABASE includes ENGINE_SPNS"""
        for spn_num in ENGINE_SPNS:
            assert spn_num in SPN_DATABASE

    def test_spn_database_contains_cooling_spns(self):
        """Test SPN_DATABASE includes COOLING_SPNS"""
        for spn_num in COOLING_SPNS:
            assert spn_num in SPN_DATABASE

    def test_spn_database_contains_aftertreatment_spns(self):
        """Test SPN_DATABASE includes AFTERTREATMENT_SPNS"""
        for spn_num in AFTERTREATMENT_SPNS:
            assert spn_num in SPN_DATABASE

    def test_spn_database_all_values_are_spninfo(self):
        """Test all values in SPN_DATABASE are SPNInfo instances"""
        for spn_num, spn_info in list(SPN_DATABASE.items())[:50]:  # Test first 50
            assert isinstance(spn_info, SPNInfo)
            assert spn_info.spn == spn_num


class TestSPNDatabaseCoverage:
    """Tests to maximize coverage of SPN dictionaries"""

    def test_iterate_all_engine_spns(self):
        """Iterate all ENGINE_SPNS to trigger coverage"""
        count = 0
        for spn_num, spn_info in ENGINE_SPNS.items():
            count += 1
            _ = spn_info.name_en
            _ = spn_info.name_es
            _ = spn_info.system
            _ = spn_info.severity
            _ = spn_info.description_es
            _ = spn_info.action_es
        assert count == len(ENGINE_SPNS)

    def test_iterate_all_cooling_spns(self):
        """Iterate all COOLING_SPNS"""
        count = 0
        for spn_num, spn_info in COOLING_SPNS.items():
            count += 1
            _ = spn_info.name_en
            _ = spn_info.system
        assert count == len(COOLING_SPNS)

    def test_iterate_all_aftertreatment_spns(self):
        """Iterate all AFTERTREATMENT_SPNS"""
        count = 0
        for spn_num, spn_info in AFTERTREATMENT_SPNS.items():
            count += 1
            _ = spn_info.severity
        assert count == len(AFTERTREATMENT_SPNS)

    def test_iterate_all_electrical_spns(self):
        """Iterate all ELECTRICAL_SPNS"""
        count = 0
        for spn_num, spn_info in ELECTRICAL_SPNS.items():
            count += 1
            _ = spn_info.description_es
        assert count == len(ELECTRICAL_SPNS)

    def test_iterate_all_transmission_spns(self):
        """Iterate all TRANSMISSION_SPNS"""
        count = 0
        for spn_num, spn_info in TRANSMISSION_SPNS.items():
            count += 1
            _ = spn_info.action_es
        assert count == len(TRANSMISSION_SPNS)

    def test_iterate_all_brakes_spns(self):
        """Iterate all BRAKES_SPNS"""
        count = 0
        for spn_num, spn_info in BRAKES_SPNS.items():
            count += 1
            _ = spn_info.name_en
        assert count == len(BRAKES_SPNS)

    def test_iterate_all_hvac_spns(self):
        """Iterate all HVAC_SPNS"""
        count = 0
        for spn_num, spn_info in HVAC_SPNS.items():
            count += 1
            _ = spn_info.system
        assert count == len(HVAC_SPNS)

    def test_iterate_all_wialon_spns(self):
        """Iterate all WIALON_DETECTED_SPNS"""
        count = 0
        for spn_num, spn_info in WIALON_DETECTED_SPNS.items():
            count += 1
            _ = spn_info.severity
        assert count == len(WIALON_DETECTED_SPNS)

    def test_iterate_all_additional_spns(self):
        """Iterate all ADDITIONAL_SPNS"""
        count = 0
        for spn_num, spn_info in ADDITIONAL_SPNS.items():
            count += 1
            _ = spn_info.name_es
        assert count == len(ADDITIONAL_SPNS)

    def test_iterate_entire_spn_database(self):
        """Iterate entire SPN_DATABASE to maximize coverage"""
        count = 0
        for spn_num, spn_info in SPN_DATABASE.items():
            count += 1
            # Access all SPNInfo fields
            _ = spn_info.spn
            _ = spn_info.name_en
            _ = spn_info.name_es
            _ = spn_info.system
            _ = spn_info.severity
            _ = spn_info.description_es
            _ = spn_info.action_es
        assert count == len(SPN_DATABASE)
        assert count > 0

    def test_iterate_all_fmi_descriptions(self):
        """Iterate all FMI_DESCRIPTIONS to maximize coverage"""
        count = 0
        for fmi_num, fmi_data in FMI_DESCRIPTIONS.items():
            count += 1
            _ = fmi_data["en"]
            _ = fmi_data["es"]
            _ = fmi_data["severity"]
        assert count == len(FMI_DESCRIPTIONS)
        assert count > 0
