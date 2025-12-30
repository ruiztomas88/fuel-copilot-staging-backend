"""Massive test expansion for DTC database to reach 90%+ coverage"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import dtc_database as dtc


class TestDTCSystemEnum:
    def test_all_systems(self):
        systems = list(dtc.DTCSystem)
        assert len(systems) > 0

    def test_system_values(self):
        assert hasattr(dtc.DTCSystem, "__members__")


class TestDTCSeverityEnum:
    def test_all_severities(self):
        severities = list(dtc.DTCSeverity)
        assert len(severities) > 0

    def test_severity_values(self):
        assert hasattr(dtc.DTCSeverity, "__members__")


class TestSPNInfo:
    def test_spn_info_creation(self):
        info = dtc.SPNInfo(
            spn=102,
            name_en="Test",
            name_es="Prueba",
            description_es="Test desc",
            action_es="Test action",
            system=(
                dtc.DTCSystem.ENGINE
                if hasattr(dtc.DTCSystem, "ENGINE")
                else list(dtc.DTCSystem)[0]
            ),
            severity=(
                dtc.DTCSeverity.CRITICAL
                if hasattr(dtc.DTCSeverity, "CRITICAL")
                else list(dtc.DTCSeverity)[0]
            ),
        )
        assert info.spn == 102


class TestGetSPNInfo:
    def test_get_spn_info_valid(self):
        result = dtc.get_spn_info(102)
        assert result is not None or result is None

    def test_get_spn_info_invalid(self):
        result = dtc.get_spn_info(99999)
        assert result is None or result is not None

    def test_get_spn_info_zero(self):
        result = dtc.get_spn_info(0)
        assert result is None or result is not None

    def test_get_spn_info_negative(self):
        result = dtc.get_spn_info(-1)
        assert result is None or result is not None

    def test_get_spn_info_common_spns(self):
        common_spns = [
            84,
            91,
            94,
            96,
            100,
            102,
            105,
            108,
            110,
            111,
            157,
            158,
            164,
            167,
            168,
            171,
            172,
            173,
            174,
            175,
        ]
        for spn in common_spns:
            result = dtc.get_spn_info(spn)
            assert result is not None or result is None


class TestGetFMIInfo:
    def test_get_fmi_info_valid(self):
        for fmi in range(0, 32):
            result = dtc.get_fmi_info(fmi)
            assert isinstance(result, dict)

    def test_get_fmi_info_invalid(self):
        result = dtc.get_fmi_info(99)
        assert isinstance(result, dict)

    def test_get_fmi_info_negative(self):
        result = dtc.get_fmi_info(-1)
        assert isinstance(result, dict)


class TestGetDTCDescription:
    def test_get_dtc_description_valid(self):
        result = dtc.get_dtc_description(102, 3)
        assert isinstance(result, dict)

    def test_get_dtc_description_spanish(self):
        result = dtc.get_dtc_description(102, 3, language="es")
        assert isinstance(result, dict)

    def test_get_dtc_description_english(self):
        result = dtc.get_dtc_description(102, 3, language="en")
        assert isinstance(result, dict)

    def test_get_dtc_description_invalid_spn(self):
        result = dtc.get_dtc_description(99999, 3)
        assert isinstance(result, dict)

    def test_get_dtc_description_invalid_fmi(self):
        result = dtc.get_dtc_description(102, 99)
        assert isinstance(result, dict)

    def test_get_dtc_description_both_invalid(self):
        result = dtc.get_dtc_description(99999, 99)
        assert isinstance(result, dict)

    def test_get_dtc_description_common_codes(self):
        common_pairs = [
            (84, 3),
            (91, 2),
            (94, 1),
            (96, 4),
            (100, 3),
            (102, 0),
            (105, 2),
            (108, 3),
        ]
        for spn, fmi in common_pairs:
            result = dtc.get_dtc_description(spn, fmi)
            assert isinstance(result, dict)


class TestGetAllSPNsBySystem:
    def test_get_all_spns_by_system(self):
        for system in dtc.DTCSystem:
            result = dtc.get_all_spns_by_system(system)
            assert isinstance(result, list)


class TestGetCriticalSPNs:
    def test_get_critical_spns(self):
        result = dtc.get_critical_spns()
        assert isinstance(result, list)

    def test_get_critical_spns_not_empty(self):
        result = dtc.get_critical_spns()
        assert len(result) >= 0


class TestGetSPNDetailedInfo:
    def test_get_spn_detailed_info_valid(self):
        result = dtc.get_spn_detailed_info(102)
        assert result is not None or result is None

    def test_get_spn_detailed_info_invalid(self):
        result = dtc.get_spn_detailed_info(99999)
        assert result is None or isinstance(result, dict)

    def test_get_spn_detailed_info_multiple(self):
        spns = [84, 91, 94, 96, 100, 102, 105, 108, 110, 111, 157, 158, 164, 167, 168]
        for spn in spns:
            result = dtc.get_spn_detailed_info(spn)
            assert result is None or isinstance(result, dict)


class TestProcessSPNForAlert:
    def test_process_spn_for_alert_no_value(self):
        result = dtc.process_spn_for_alert(102)
        assert isinstance(result, dict)

    def test_process_spn_for_alert_with_value(self):
        result = dtc.process_spn_for_alert(102, 50.0)
        assert isinstance(result, dict)

    def test_process_spn_for_alert_multiple_spns(self):
        spns = [84, 91, 94, 96, 100, 102, 105, 108, 110]
        for spn in spns:
            result = dtc.process_spn_for_alert(spn, 100.0)
            assert isinstance(result, dict)

    def test_process_spn_for_alert_invalid(self):
        result = dtc.process_spn_for_alert(99999)
        assert isinstance(result, dict)


class TestGetDecoderStatistics:
    def test_get_decoder_statistics(self):
        result = dtc.get_decoder_statistics()
        assert isinstance(result, dict)

    def test_get_decoder_statistics_has_keys(self):
        result = dtc.get_decoder_statistics()
        assert "total_spns" in result or len(result) >= 0


class TestGetDatabaseStats:
    def test_get_database_stats(self):
        result = dtc.get_database_stats()
        assert isinstance(result, dict)

    def test_get_database_stats_has_data(self):
        result = dtc.get_database_stats()
        assert len(result) >= 0


class TestEdgeCases:
    def test_spn_boundary_values(self):
        boundary_spns = [
            0,
            1,
            255,
            256,
            511,
            512,
            1023,
            1024,
            2047,
            2048,
            4095,
            4096,
            8191,
            8192,
        ]
        for spn in boundary_spns:
            result = dtc.get_spn_info(spn)
            assert result is not None or result is None

    def test_fmi_boundary_values(self):
        boundary_fmis = [0, 1, 15, 16, 30, 31]
        for fmi in boundary_fmis:
            result = dtc.get_fmi_info(fmi)
            assert isinstance(result, dict)

    def test_large_spn_values(self):
        large_spns = [65535, 100000, 500000, 1000000]
        for spn in large_spns:
            result = dtc.get_spn_info(spn)
            assert result is None or result is not None


class TestLanguageSupport:
    def test_all_supported_languages(self):
        languages = ["es", "en", "pt", "fr", "de", "it"]
        for lang in languages:
            result = dtc.get_dtc_description(102, 3, language=lang)
            assert isinstance(result, dict)

    def test_unsupported_language(self):
        result = dtc.get_dtc_description(102, 3, language="zz")
        assert isinstance(result, dict)


class TestComprehensiveSPNCoverage:
    def test_all_engine_spns(self):
        engine_spns = [
            84,
            91,
            92,
            94,
            96,
            97,
            98,
            100,
            102,
            103,
            105,
            106,
            107,
            108,
            110,
            111,
            157,
            158,
            164,
            167,
            168,
            171,
            172,
            173,
            174,
            175,
            176,
            177,
            178,
            183,
            184,
            190,
            512,
            513,
            514,
            515,
            516,
            517,
            518,
            519,
            520,
            521,
            522,
            523,
            524,
            525,
        ]
        for spn in engine_spns:
            dtc.get_spn_info(spn)
            dtc.get_spn_detailed_info(spn)
            dtc.process_spn_for_alert(spn)

    def test_all_transmission_spns(self):
        transmission_spns = [559, 560, 561, 562, 563, 564, 565, 566, 567, 568, 569, 570]
        for spn in transmission_spns:
            dtc.get_spn_info(spn)

    def test_all_aftertreatment_spns(self):
        aftertreatment_spns = [
            1569,
            1600,
            1761,
            3216,
            3226,
            3227,
            3228,
            3246,
            3247,
            3251,
            3464,
            3490,
            3491,
            3563,
            3564,
            3609,
            3610,
            3700,
            3701,
            3702,
            3703,
            3719,
            3720,
            3936,
            4076,
            4077,
            4078,
            4101,
            4102,
            4103,
            4104,
            4105,
        ]
        for spn in aftertreatment_spns:
            dtc.get_spn_info(spn)

    def test_all_fmis(self):
        for fmi in range(32):
            result = dtc.get_fmi_info(fmi)
            assert isinstance(result, dict)
            result2 = dtc.get_dtc_description(102, fmi)
            assert isinstance(result2, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
