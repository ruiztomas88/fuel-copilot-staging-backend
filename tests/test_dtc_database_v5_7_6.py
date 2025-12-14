"""
Tests for J1939 DTC Database v5.7.6
═══════════════════════════════════════════════════════════════════════════════

Test coverage for DTC database lookups and descriptions.
"""

import pytest

from dtc_database import (
    DTCSystem,
    DTCSeverity,
    SPNInfo,
    SPN_DATABASE,
    FMI_DESCRIPTIONS,
    get_spn_info,
    get_fmi_info,
    get_dtc_description,
    get_all_spns_by_system,
    get_critical_spns,
    get_database_stats,
)


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE STRUCTURE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDatabaseStructure:
    """Test database structure and completeness"""

    def test_spn_database_not_empty(self):
        """Should have SPNs in database"""
        assert len(SPN_DATABASE) > 0
        assert len(SPN_DATABASE) >= 30  # Minimum expected SPNs

    def test_fmi_descriptions_complete(self):
        """Should have FMI descriptions for common values"""
        # Standard FMI codes 0-21 and 31
        standard_fmis = [
            0,
            1,
            2,
            3,
            4,
            5,
            6,
            7,
            8,
            9,
            10,
            11,
            12,
            13,
            14,
            15,
            16,
            17,
            18,
            19,
            20,
            21,
            31,
        ]
        for fmi in standard_fmis:
            assert fmi in FMI_DESCRIPTIONS

    def test_all_spns_have_required_fields(self):
        """All SPNs should have required fields"""
        for spn, info in SPN_DATABASE.items():
            assert isinstance(info, SPNInfo)
            assert info.spn == spn
            assert info.name_en != ""
            assert info.name_es != ""
            assert isinstance(info.system, DTCSystem)
            assert isinstance(info.severity, DTCSeverity)
            assert info.description_es != ""
            assert info.action_es != ""


# ═══════════════════════════════════════════════════════════════════════════════
# SPN LOOKUP TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestSPNLookup:
    """Test SPN lookup functions"""

    def test_get_known_spn(self):
        """Should return info for known SPN"""
        info = get_spn_info(100)  # Engine Oil Pressure
        assert info is not None
        assert info.spn == 100
        assert "Oil" in info.name_en or "Aceite" in info.name_es

    def test_get_unknown_spn(self):
        """Should return None for unknown SPN"""
        info = get_spn_info(99999)
        assert info is None

    def test_critical_spn_has_critical_severity(self):
        """Critical SPNs should have CRITICAL severity"""
        # SPN 100 = Engine Oil Pressure - should be critical
        info = get_spn_info(100)
        assert info is not None
        assert info.severity == DTCSeverity.CRITICAL

    def test_spn_system_classification(self):
        """SPNs should be correctly classified by system"""
        # SPN 100 = Engine Oil Pressure
        info = get_spn_info(100)
        assert info.system == DTCSystem.ENGINE

        # SPN 1761 = DEF Tank Level
        info = get_spn_info(1761)
        assert info.system == DTCSystem.AFTERTREATMENT

        # SPN 127 = Transmission Oil Pressure
        info = get_spn_info(127)
        assert info.system == DTCSystem.TRANSMISSION


# ═══════════════════════════════════════════════════════════════════════════════
# FMI LOOKUP TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFMILookup:
    """Test FMI lookup functions"""

    def test_get_known_fmi(self):
        """Should return info for known FMI"""
        info = get_fmi_info(0)
        assert "en" in info
        assert "es" in info
        assert "severity" in info

    def test_fmi_0_is_critical(self):
        """FMI 0 (Above Normal - Most Severe) should be critical"""
        info = get_fmi_info(0)
        assert info["severity"] == DTCSeverity.CRITICAL

    def test_fmi_2_is_warning(self):
        """FMI 2 (Erratic Data) should be warning"""
        info = get_fmi_info(2)
        assert info["severity"] == DTCSeverity.WARNING

    def test_unknown_fmi_returns_default(self):
        """Unknown FMI should return default info"""
        info = get_fmi_info(99)
        assert "desconocido" in info["es"].lower() or "unknown" in info["en"].lower()

    def test_fmi_has_spanish_description(self):
        """FMI should have Spanish descriptions"""
        for fmi, info in FMI_DESCRIPTIONS.items():
            assert "es" in info
            assert len(info["es"]) > 0


# ═══════════════════════════════════════════════════════════════════════════════
# DTC DESCRIPTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDTCDescription:
    """Test full DTC description generation"""

    def test_get_description_known_dtc(self):
        """Should generate full description for known DTC"""
        desc = get_dtc_description(100, 4)  # Oil Pressure - Voltage Low

        assert desc["code"] == "SPN100.FMI4"
        assert desc["spn"] == 100
        assert desc["fmi"] == 4
        assert "component" in desc
        assert "failure_mode" in desc
        assert "action" in desc
        assert desc["system"] == "ENGINE"

    def test_description_spanish_by_default(self):
        """Should return Spanish descriptions by default"""
        desc = get_dtc_description(100, 4, language="es")
        assert "Presión" in desc["component"] or "Aceite" in desc["component"]

    def test_description_english(self):
        """Should return English descriptions when requested"""
        desc = get_dtc_description(100, 4, language="en")
        assert "Oil" in desc["component"] or "Pressure" in desc["component"]

    def test_description_unknown_spn(self):
        """Should handle unknown SPN gracefully"""
        desc = get_dtc_description(99999, 0)
        assert "Desconocido" in desc["component"] or "Unknown" in desc["component"]
        assert desc["severity"] == "critical"  # FMI 0 is critical

    def test_severity_uses_highest(self):
        """Should use highest severity between SPN and FMI"""
        # SPN 96 (Fuel Level) is INFO, but FMI 0 is CRITICAL
        desc = get_dtc_description(96, 0)
        assert desc["severity"] == "critical"


# ═══════════════════════════════════════════════════════════════════════════════
# SYSTEM CLASSIFICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestSystemClassification:
    """Test system-based lookups"""

    def test_get_spns_by_system_engine(self):
        """Should get ENGINE SPNs"""
        engine_spns = get_all_spns_by_system(DTCSystem.ENGINE)
        assert len(engine_spns) > 0
        for info in engine_spns:
            assert info.system == DTCSystem.ENGINE

    def test_get_spns_by_system_aftertreatment(self):
        """Should get AFTERTREATMENT SPNs"""
        at_spns = get_all_spns_by_system(DTCSystem.AFTERTREATMENT)
        assert len(at_spns) > 0
        # DEF/SCR/DPF related codes
        spn_numbers = [info.spn for info in at_spns]
        assert 1761 in spn_numbers or 3031 in spn_numbers  # DEF related

    def test_get_spns_by_system_transmission(self):
        """Should get TRANSMISSION SPNs"""
        trans_spns = get_all_spns_by_system(DTCSystem.TRANSMISSION)
        assert len(trans_spns) > 0

    def test_get_critical_spns(self):
        """Should return list of critical SPNs"""
        critical = get_critical_spns()
        assert len(critical) > 0
        # Verify they are actually critical
        for spn in critical:
            info = get_spn_info(spn)
            assert info.severity == DTCSeverity.CRITICAL


# ═══════════════════════════════════════════════════════════════════════════════
# DATABASE STATS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDatabaseStats:
    """Test database statistics"""

    def test_stats_structure(self):
        """Should return stats with expected structure"""
        stats = get_database_stats()

        assert "total_spns" in stats
        assert "total_fmis" in stats
        assert "by_system" in stats
        assert "by_severity" in stats

    def test_stats_counts(self):
        """Stats should have correct counts"""
        stats = get_database_stats()

        assert stats["total_spns"] == len(SPN_DATABASE)
        assert stats["total_fmis"] == len(FMI_DESCRIPTIONS)

    def test_severity_distribution(self):
        """Should have SPNs of each severity"""
        stats = get_database_stats()

        # Should have at least some critical and warning SPNs
        assert stats["by_severity"]["CRITICAL"] > 0
        assert stats["by_severity"]["WARNING"] > 0


# ═══════════════════════════════════════════════════════════════════════════════
# SPANISH CONTENT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestSpanishContent:
    """Test Spanish language content"""

    def test_all_spns_have_spanish_names(self):
        """All SPNs should have Spanish names"""
        for spn, info in SPN_DATABASE.items():
            assert info.name_es != "", f"SPN {spn} missing Spanish name"
            # Should not be same as English (translated)
            assert info.name_es != info.name_en, f"SPN {spn} has untranslated name"

    def test_all_spns_have_spanish_descriptions(self):
        """All SPNs should have Spanish descriptions"""
        for spn, info in SPN_DATABASE.items():
            assert info.description_es != "", f"SPN {spn} missing Spanish description"

    def test_all_spns_have_spanish_actions(self):
        """All SPNs should have Spanish action recommendations"""
        for spn, info in SPN_DATABASE.items():
            assert info.action_es != "", f"SPN {spn} missing Spanish action"

    def test_critical_actions_have_warning_icons(self):
        """Critical SPNs should have warning icons in actions"""
        for spn, info in SPN_DATABASE.items():
            if info.severity == DTCSeverity.CRITICAL:
                # Should have ⛔ or ⚠️ icon
                assert (
                    "⛔" in info.action_es or "⚠️" in info.action_es
                ), f"Critical SPN {spn} missing warning icon"


# ═══════════════════════════════════════════════════════════════════════════════
# REAL-WORLD DTC EXAMPLES
# ═══════════════════════════════════════════════════════════════════════════════


class TestRealWorldExamples:
    """Test with real-world DTC codes"""

    def test_common_dtc_100_4(self):
        """SPN100.FMI4 = Oil Pressure - Voltage Low (Common critical)"""
        desc = get_dtc_description(100, 4)
        assert desc["severity"] == "critical"
        assert "PARAR" in desc["action"] or "aceite" in desc["action"].lower()

    def test_common_dtc_157_3(self):
        """SPN157.FMI3 = Fuel Rail Pressure - Voltage High"""
        desc = get_dtc_description(157, 3)
        assert desc["severity"] == "critical"
        assert (
            "combustible" in desc["action"].lower()
            or "fuel" in desc["component"].lower()
        )

    def test_common_dtc_3031_2(self):
        """SPN3031.FMI2 = DEF Quality - Erratic"""
        desc = get_dtc_description(3031, 2)
        assert "DEF" in desc["component"]

    def test_common_dtc_110_0(self):
        """SPN110.FMI0 = Coolant Temp - Above Normal (Overheating)"""
        desc = get_dtc_description(110, 0)
        assert desc["severity"] == "critical"
        assert (
            "refrigerante" in desc["component"].lower()
            or "coolant" in desc["component"].lower()
        )
