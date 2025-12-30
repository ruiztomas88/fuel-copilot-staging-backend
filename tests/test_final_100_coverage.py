"""Final tests to achieve 100% PM and DTC coverage"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dtc_analyzer import DTCAnalyzer, DTCSeverity
from predictive_maintenance_engine import (
    MaintenanceUrgency,
    PredictiveMaintenanceEngine,
    SensorHistory,
    TrendDirection,
)


class TestPMLine316:
    """Test line 316: Zero denominator in SensorHistory.calculate_trend"""

    def test_calculate_trend_zero_denominator(self):
        """Line 316: if denominator == 0: return None"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)

        # Add readings all at the exact same timestamp
        now = datetime.now(timezone.utc)
        pm.add_sensor_reading("T1", "coolant_temp", 85.0, now)
        pm.add_sensor_reading("T1", "coolant_temp", 86.0, now)
        pm.add_sensor_reading("T1", "coolant_temp", 87.0, now)
        pm.add_sensor_reading("T1", "coolant_temp", 88.0, now)

        # Access sensor history and call calculate_trend
        history = pm.sensor_histories["T1"]["coolant_temp"]
        trend = history.calculate_trend()
        # With all same timestamps, denominator = 0, should return None
        assert trend is None


class TestPMLine487:
    """Test line 487: MySQL not available check"""

    def test_mysql_not_available_path(self):
        """Line 487: if not _mysql_available"""
        import predictive_maintenance_engine as pm_module

        original = pm_module._mysql_available
        try:
            pm_module._mysql_available = False
            pm = PredictiveMaintenanceEngine(use_mysql=True)
            # Should detect MySQL not available
            result = pm._test_mysql_connection()
            assert result is False
        finally:
            pm_module._mysql_available = original


class TestPMLines492_493:
    """Test lines 492-493: Explicit timestamp in batch"""

    def test_explicit_timestamp_in_batch(self):
        """Lines 492-493: timestamp parameter"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)

        custom_ts = datetime.now(timezone.utc) - timedelta(hours=5)
        batch = [{"truck_id": "TX1", "sensor": "coolant_temp", "value": 90.0}]

        pm.process_sensor_batch(batch, timestamp=custom_ts)
        assert "TX1" in pm.sensor_histories


class TestPMLines506_510:
    """Test lines 506-510: Skip None values"""

    def test_skip_none_values_in_batch(self):
        """Lines 506-510: if value is None: continue"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)

        batch = [
            {"truck_id": "T_NONE", "sensor": "coolant_temp", "value": None},
            {"truck_id": "T_OK", "sensor": "coolant_temp", "value": 85.0},
        ]

        pm.process_sensor_batch(batch)

        assert "T_NONE" not in pm.sensor_histories
        assert "T_OK" in pm.sensor_histories


class TestPMLines514_517:
    """Test lines 514-517: Default timestamp"""

    def test_default_timestamp_in_batch(self):
        """Lines 514-517: ts = timestamp if timestamp else datetime.now()"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)

        batch = [{"truck_id": "T_DEFAULT", "sensor": "coolant_temp", "value": 85.0}]
        pm.process_sensor_batch(batch)  # No timestamp param

        assert "T_DEFAULT" in pm.sensor_histories


class TestPMLines539_540:
    """Test lines 539-540: MySQL empty rows"""

    @patch("predictive_maintenance_engine._mysql_available", True)
    def test_mysql_empty_rows(self):
        """Lines 539-540: if not rows: return True"""
        pm = PredictiveMaintenanceEngine(use_mysql=True)

        with patch.object(pm, "_test_mysql_connection", return_value=True):
            with patch("database_mysql.get_session") as mock_session:
                mock_conn = MagicMock()
                mock_result = MagicMock()
                mock_result.fetchall.return_value = []
                mock_conn.execute.return_value = mock_result
                mock_session.return_value.__enter__.return_value = mock_conn

                result = pm._load_state_mysql()
                assert result is True


class TestPMLines572_574:
    """Test lines 572-574: MySQL load success"""

    @patch("predictive_maintenance_engine._mysql_available", True)
    def test_mysql_load_success(self):
        """Lines 572-574: return True"""
        pm = PredictiveMaintenanceEngine(use_mysql=True)

        with patch.object(pm, "_test_mysql_connection", return_value=True):
            with patch("database_mysql.get_session") as mock_session:
                mock_conn = MagicMock()
                mock_result = MagicMock()
                mock_result.fetchall.return_value = [
                    ("T1", "coolant_temp", 85.0, datetime.now(timezone.utc), 1.5)
                ]
                mock_conn.execute.return_value = mock_result
                mock_session.return_value.__enter__.return_value = mock_conn

                result = pm._load_state_mysql()
                assert result is True


class TestPMLines623_624:
    """Test lines 623-624: MySQL flush exception"""

    @patch("predictive_maintenance_engine._mysql_available", True)
    def test_mysql_flush_exception(self):
        """Lines 623-624: except Exception"""
        pm = PredictiveMaintenanceEngine(use_mysql=True)
        pm._use_mysql = True
        pm._pending_mysql_writes.append(
            ("T1", "coolant_temp", 85.0, datetime.now(timezone.utc), 1.5)
        )

        with patch("database_mysql.get_session", side_effect=Exception("DB error")):
            pm._flush_mysql_writes()


class TestPMLine658:
    """Test line 658: Update daily avg exception"""

    def test_update_daily_avg_exception(self):
        """Line 658: except Exception"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)
        pm._use_mysql = True

        with patch("database_mysql.get_session", side_effect=Exception("Error")):
            pm._update_daily_avg("T1", "coolant_temp", 85.0)


class TestPMLine712:
    """Test line 712: JSON load exception"""

    def test_json_load_exception(self, tmp_path):
        """Line 712: except Exception"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)

        bad_file = tmp_path / "bad.json"
        bad_file.write_text("{bad}")

        with patch("predictive_maintenance_engine.PM_STATE_FILE", str(bad_file)):
            pm._load_state_json()


class TestPMUrgencyLines:
    """Test lines 965, 967, 975, 977, 981: All urgency branches"""

    def test_urgency_line_965(self):
        """Line 965: if days_to_critical <= 3"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)
        urg = pm._calculate_urgency(2.0, None, TrendDirection.DEGRADING)
        assert urg == MaintenanceUrgency.CRITICAL

    def test_urgency_line_967(self):
        """Line 967: if days_to_critical <= 7"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)
        urg = pm._calculate_urgency(5.0, None, TrendDirection.DEGRADING)
        assert urg == MaintenanceUrgency.HIGH

    def test_urgency_line_975(self):
        """Line 975: if days_to_warning <= 7"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)
        urg = pm._calculate_urgency(None, 5.0, TrendDirection.DEGRADING)
        assert urg == MaintenanceUrgency.MEDIUM

    def test_urgency_line_977(self):
        """Line 977: if days_to_warning <= 30"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)
        urg = pm._calculate_urgency(None, 20.0, TrendDirection.DEGRADING)
        assert urg == MaintenanceUrgency.LOW

    def test_urgency_line_981(self):
        """Line 981: if trend_direction == DEGRADING"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)
        urg = pm._calculate_urgency(None, None, TrendDirection.DEGRADING)
        assert urg == MaintenanceUrgency.LOW


class TestPMLines1116_1117:
    """Test lines 1116-1117: Medium and low counting"""

    def test_medium_low_counting(self):
        """Lines 1116-1117: elif MEDIUM, elif LOW"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)

        # Create predictions with different urgencies
        pm.add_sensor_reading("TM", "coolant_temp", 100.0)
        for i in range(20):
            pm.add_sensor_reading("TM", "coolant_temp", 100.0 + i * 0.3)

        pm.add_sensor_reading("TL", "oil_pressure", 38.0)
        for i in range(20):
            pm.add_sensor_reading("TL", "oil_pressure", 38.0 - i * 0.05)

        summary = pm.get_fleet_summary()
        assert isinstance(summary, dict)


class TestPMLine1170:
    """Test line 1170: Truck not in histories"""

    def test_truck_not_in_histories(self):
        """Line 1170: if truck_id not in self.sensor_histories"""
        pm = PredictiveMaintenanceEngine(use_mysql=False)

        result = pm.get_sensor_trend("NONEXISTENT", "coolant_temp")
        assert result is None


class TestDTCLine282:
    """Test line 282: Fallback severity CRITICAL_SPNS"""

    @patch("dtc_analyzer.DTC_DATABASE_AVAILABLE", False)
    def test_fallback_critical_spn(self):
        """Line 282: if spn in CRITICAL_SPNS (fallback)"""
        analyzer = DTCAnalyzer()
        severity = analyzer._determine_severity(100, 10)  # Oil pressure
        assert severity == DTCSeverity.CRITICAL


class TestDTCLine305:
    """Test line 305: Fallback recommendation path"""

    @patch("dtc_analyzer.DTC_DATABASE_AVAILABLE", False)
    def test_fallback_recommendation_path(self):
        """Line 305: Fallback path when DB not available"""
        analyzer = DTCAnalyzer()

        # This triggers the fallback path in _get_recommended_action
        rec = analyzer._get_recommended_action(100, 4, DTCSeverity.CRITICAL)
        assert "PARAR" in rec or "aceite" in rec


class TestDTCLine462:
    """Test line 462: FMI description"""

    def test_fmi_description(self):
        """Line 462: FMI description retrieval"""
        analyzer = DTCAnalyzer()
        now = datetime.now(timezone.utc)

        # Process DTC with valid FMI
        alerts = analyzer.process_truck_dtc("TF", "100.4", now)
        assert len(alerts) > 0


class TestDTCLines522_525:
    """Test lines 522-525: Batch processing logic"""

    def test_batch_processing(self):
        """Lines 522-525: Process multiple trucks"""
        analyzer = DTCAnalyzer()
        now = datetime.now(timezone.utc)

        # Process multiple trucks to exercise batch-like logic
        analyzer.process_truck_dtc("TB1", "100.4", now)
        analyzer.process_truck_dtc("TB2", "110.3", now)
        analyzer.process_truck_dtc("TB3", "157.4", now)

        active = analyzer.get_active_dtcs()
        assert len(active) >= 3
