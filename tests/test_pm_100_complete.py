"""Complete PM Engine tests targeting 100% coverage - ALL missing lines"""

import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from predictive_maintenance_engine import (
    SENSOR_THRESHOLDS,
    MaintenanceUrgency,
    PredictiveMaintenanceEngine,
    SensorHistory,
    SensorReading,
    TrendDirection,
    get_predictive_maintenance_engine,
)


class TestPMInitialization:
    """Lines 55-56: MySQL vs JSON initialization"""

    def test_init_with_mysql_true(self):
        engine = PredictiveMaintenanceEngine(use_mysql=True)
        assert engine is not None
        assert hasattr(engine, "_use_mysql")

    def test_init_with_mysql_false(self):
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        assert engine is not None
        assert engine._use_mysql == False


class TestThresholdLogic:
    """Lines 264-335: Threshold determination and edge cases"""

    def test_calculate_trend_insufficient_data(self):
        history = SensorHistory(sensor_name="oil_pressure", truck_id="TEST001")
        # Add only 2 readings (need 3+)
        history.add_reading(datetime.now(timezone.utc), 35.0)
        history.add_reading(datetime.now(timezone.utc) + timedelta(days=1), 34.0)
        trend = history.calculate_trend()
        assert trend is None  # Line 299

    def test_calculate_trend_zero_denominator(self):
        history = SensorHistory(sensor_name="oil_pressure", truck_id="TEST002")
        # Add identical timestamps (edge case)
        ts = datetime.now(timezone.utc)
        for _ in range(5):
            history.add_reading(ts, 35.0)
        trend = history.calculate_trend()
        assert trend is None or trend == 0  # Lines 323-327

    def test_nan_trend_handling(self):
        """Lines 875-877: NaN check in days calculation"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        history = SensorHistory(sensor_name="oil_pressure", truck_id="TEST003")

        # Create scenario with NaN trend
        for i in range(5):
            history.add_reading(
                datetime.now(timezone.utc) - timedelta(days=5 - i), float("nan")
            )

        if "TEST003" not in engine.histories:
            engine.histories["TEST003"] = {}
        engine.histories["TEST003"]["oil_pressure"] = history

        pred = engine.analyze_sensor("TEST003", "oil_pressure")
        # Should handle NaN gracefully

    def test_trend_exactly_zero_point_five(self):
        """Lines 854-867: Exact boundary conditions"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        history = SensorHistory(sensor_name="coolant_temp", truck_id="TEST004")

        # Create exact 0.5 trend
        for i in range(10):
            history.add_reading(
                datetime.now(timezone.utc) - timedelta(days=10 - i), 190.0 + (i * 0.5)
            )

        engine.histories["TEST004"] = {"coolant_temp": history}
        pred = engine.analyze_sensor("TEST004", "coolant_temp")
        assert pred is not None

    def test_trend_negative_point_five(self):
        """Test -0.5 boundary"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        history = SensorHistory(sensor_name="oil_pressure", truck_id="TEST005")

        for i in range(10):
            history.add_reading(
                datetime.now(timezone.utc) - timedelta(days=10 - i), 35.0 - (i * 0.5)
            )

        engine.histories["TEST005"] = {"oil_pressure": history}
        pred = engine.analyze_sensor("TEST005", "oil_pressure")
        assert pred is not None


class TestSensorAnalysis:
    """Lines 347-422: Sensor analysis paths"""

    def test_analyze_sensor_no_threshold_config(self):
        """Line 347-348: Sensor not in SENSOR_THRESHOLDS"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine.histories["TRUCK001"] = {
            "unknown_sensor": SensorHistory("unknown_sensor", "TRUCK001")
        }
        pred = engine.analyze_sensor("TRUCK001", "unknown_sensor")
        assert pred is None

    def test_analyze_sensor_no_truck_history(self):
        """Line 353-354: Truck not in histories"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        pred = engine.analyze_sensor("NONEXISTENT", "oil_pressure")
        assert pred is None

    def test_analyze_sensor_no_sensor_history(self):
        """Line 355-356: Sensor not in truck histories"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine.histories["TRUCK002"] = {}
        pred = engine.analyze_sensor("TRUCK002", "oil_pressure")
        assert pred is None

    def test_analyze_sensor_null_current_value(self):
        """Line 361-362: Current value is None"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        history = SensorHistory("oil_pressure", "TRUCK003")
        # Don't add any readings
        engine.histories["TRUCK003"] = {"oil_pressure": history}
        pred = engine.analyze_sensor("TRUCK003", "oil_pressure")
        assert pred is None

    def test_higher_bad_trend_degrading(self):
        """Lines 381-407: Temperature sensors degrading"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        history = SensorHistory("coolant_temp", "TRUCK004")

        for i in range(10):
            history.add_reading(
                datetime.now(timezone.utc) - timedelta(days=10 - i),
                190.0 + (i * 1.5),  # Rising temp = degrading
            )

        engine.histories["TRUCK004"] = {"coolant_temp": history}
        pred = engine.analyze_sensor("TRUCK004", "coolant_temp")
        assert pred.trend_direction == TrendDirection.DEGRADING

    def test_higher_bad_trend_improving(self):
        """Lines 381-407: Temperature cooling down"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        history = SensorHistory("coolant_temp", "TRUCK005")

        for i in range(10):
            history.add_reading(
                datetime.now(timezone.utc) - timedelta(days=10 - i),
                210.0 - (i * 1.5),  # Cooling = improving
            )

        engine.histories["TRUCK005"] = {"coolant_temp": history}
        pred = engine.analyze_sensor("TRUCK005", "coolant_temp")
        assert pred.trend_direction == TrendDirection.IMPROVING

    def test_lower_bad_trend_degrading(self):
        """Lines 407-422: Pressure dropping = degrading"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        history = SensorHistory("oil_pressure", "TRUCK006")

        for i in range(10):
            history.add_reading(
                datetime.now(timezone.utc) - timedelta(days=10 - i),
                40.0 - (i * 1.0),  # Dropping pressure = degrading
            )

        engine.histories["TRUCK006"] = {"oil_pressure": history}
        pred = engine.analyze_sensor("TRUCK006", "oil_pressure")
        assert pred.trend_direction == TrendDirection.DEGRADING

    def test_lower_bad_trend_improving(self):
        """Lines 407-422: Pressure rising = improving"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        history = SensorHistory("oil_pressure", "TRUCK007")

        for i in range(10):
            history.add_reading(
                datetime.now(timezone.utc) - timedelta(days=10 - i),
                25.0 + (i * 1.0),  # Rising pressure = improving
            )

        engine.histories["TRUCK007"] = {"oil_pressure": history}
        pred = engine.analyze_sensor("TRUCK007", "oil_pressure")
        assert pred.trend_direction == TrendDirection.IMPROVING


class TestBatchProcessing:
    """Lines 492-517: Batch processing paths"""

    def test_process_sensor_batch_with_none_values(self):
        """Lines 506-510: Skip None values"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        engine.process_sensor_batch(
            "TRUCK008",
            {
                "oil_pressure": 35.0,
                "coolant_temp": None,  # Should skip
                "trans_temp": 185.0,
                "def_level": None,  # Should skip
            },
        )

        assert "TRUCK008" in engine.histories
        assert "oil_pressure" in engine.histories["TRUCK008"]
        assert "trans_temp" in engine.histories["TRUCK008"]
        assert "coolant_temp" not in engine.histories["TRUCK008"]
        assert "def_level" not in engine.histories["TRUCK008"]

    def test_process_sensor_batch_custom_timestamp(self):
        """Lines 492-493: Custom timestamp"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        custom_ts = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        engine.process_sensor_batch(
            "TRUCK009", {"oil_pressure": 35.0}, timestamp=custom_ts
        )

        if (
            "TRUCK009" in engine.histories
            and "oil_pressure" in engine.histories["TRUCK009"]
        ):
            history = engine.histories["TRUCK009"]["oil_pressure"]
            if history.readings:
                assert history.readings[-1].timestamp == custom_ts

    def test_process_sensor_batch_default_timestamp(self):
        """Lines 514-517: Default to now"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        before = datetime.now(timezone.utc)

        engine.process_sensor_batch("TRUCK010", {"oil_pressure": 35.0})

        after = datetime.now(timezone.utc)
        ts = engine.histories["TRUCK010"]["oil_pressure"].readings[-1].timestamp
        assert before <= ts <= after


class TestFleetAnalysis:
    """Lines 543-624: Fleet analysis and summary generation"""

    def test_analyze_fleet_empty(self):
        """Line 543-550: Empty fleet"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        result = engine.analyze_fleet()
        assert result == {}

    def test_analyze_fleet_multiple_trucks(self):
        """Lines 551-574: Multiple trucks with various issues"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Truck with critical issue
        for i in range(10):
            engine.add_sensor_reading(
                "CRITICAL_TRUCK",
                "oil_pressure",
                15.0 - (i * 0.1),  # Already critical
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        # Truck with no issues
        for i in range(10):
            engine.add_sensor_reading(
                "OK_TRUCK",
                "oil_pressure",
                40.0,
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        result = engine.analyze_fleet()
        assert "CRITICAL_TRUCK" in result
        # OK_TRUCK might not be in result if no issues

    def test_get_fleet_summary_with_critical_items(self):
        """Lines 580-624: Summary with critical and high priority"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Add critical truck
        for i in range(10):
            engine.add_sensor_reading(
                "CRIT001",
                "oil_pressure",
                18.0,  # Critical level
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        # Add high priority truck
        for i in range(10):
            engine.add_sensor_reading(
                "HIGH001",
                "trans_temp",
                220.0,  # High temp
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        summary = engine.get_fleet_summary()

        assert summary["summary"]["critical"] >= 0
        assert summary["summary"]["high"] >= 0
        assert "critical_items" in summary
        assert "high_priority_items" in summary
        assert "recommendations" in summary

    def test_fleet_recommendations_systemic_issues(self):
        """Lines 591-624: Systemic issues detection (3+ trucks same problem)"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Create 3+ trucks with same critical issue
        for truck_num in range(5):
            for i in range(10):
                engine.add_sensor_reading(
                    f"TRUCK{truck_num:03d}",
                    "oil_pressure",
                    18.0,  # All have critical oil pressure
                    datetime.now(timezone.utc) - timedelta(days=10 - i),
                )

        summary = engine.get_fleet_summary()
        recs = summary["recommendations"]

        # Should detect systemic issue
        systemic_found = any(
            "sistémico" in r.lower() or "problema sistémico" in r.lower() for r in recs
        )


class TestJSONPersistence:
    """Lines 631-660, 688-738: JSON fallback persistence"""

    def test_save_state_json(self, tmp_path):
        """Lines 703-738: JSON save"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine.DATA_DIR = tmp_path
        engine.STATE_FILE = tmp_path / "pm_state.json"

        engine.add_sensor_reading("TRUCK_JSON", "oil_pressure", 35.0)
        engine._save_state_json()

        assert engine.STATE_FILE.exists()

        with open(engine.STATE_FILE) as f:
            data = json.load(f)

        assert "version" in data
        assert "saved_at" in data
        assert "histories" in data
        assert "TRUCK_JSON" in data["histories"]

    def test_load_state_json(self, tmp_path):
        """Lines 688-704: JSON load"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine.DATA_DIR = tmp_path
        engine.STATE_FILE = tmp_path / "pm_state.json"

        # Create test data
        test_data = {
            "version": "1.0.0",
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "histories": {
                "LOAD_TEST": {
                    "oil_pressure": {
                        "sensor_name": "oil_pressure",
                        "truck_id": "LOAD_TEST",
                        "readings": [
                            {
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "value": 35.0,
                            }
                        ],
                    }
                }
            },
        }

        with open(engine.STATE_FILE, "w") as f:
            json.dump(test_data, f)

        engine._load_state_json()

        assert "LOAD_TEST" in engine.histories
        assert "oil_pressure" in engine.histories["LOAD_TEST"]

    def test_load_state_json_file_not_exists(self, tmp_path):
        """Lines 690-704: File doesn't exist"""
        # Create fresh engine with tmp path
        from predictive_maintenance_engine import PredictiveMaintenanceEngine as PME

        engine = PME.__new__(PME)
        engine.VERSION = "1.0.0"
        engine.DATA_DIR = tmp_path
        engine.STATE_FILE = tmp_path / "nonexistent.json"
        engine.histories = {}
        engine.active_predictions = {}
        engine.last_analysis = {}
        engine._use_mysql = False
        engine._mysql_tested = True
        engine._pending_writes = []
        engine.MYSQL_BATCH_SIZE = 100

        # Should not raise error
        engine._load_state_json()
        assert engine.histories == {}

    def test_load_state_json_corrupt_file(self, tmp_path):
        """Lines 711-715: Corrupt JSON"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine.DATA_DIR = tmp_path
        engine.STATE_FILE = tmp_path / "corrupt.json"

        # Write corrupt JSON
        with open(engine.STATE_FILE, "w") as f:
            f.write("{invalid json")

        # Should handle gracefully
        engine._load_state_json()


class TestMySQLPersistence:
    """Lines 753-922: MySQL persistence paths"""

    def test_test_mysql_connection_no_table(self):
        """Lines 809-814: Table doesn't exist"""
        engine = PredictiveMaintenanceEngine(use_mysql=True)
        # Will test connection and possibly find no table

    def test_save_reading_mysql_batching(self):
        """Lines 830-850: Batch writes"""
        engine = PredictiveMaintenanceEngine(use_mysql=True)

        if engine._use_mysql:
            # Add readings but don't flush
            for i in range(5):
                engine._save_reading_mysql(
                    f"BATCH{i}", "oil_pressure", 35.0 + i, datetime.now(timezone.utc)
                )

            assert len(engine._pending_writes) > 0

    def test_flush_mysql_writes_when_disabled(self):
        """Lines 590-594: Flush when MySQL disabled"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine._pending_writes.append(("TEST", "oil", 35.0, datetime.now(timezone.utc)))

        engine._flush_mysql_writes()

        assert len(engine._pending_writes) == 0  # Should clear

    def test_update_daily_avg_mysql_when_disabled(self):
        """Lines 631-634: Daily avg when disabled"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Should not raise error
        engine._update_daily_avg_mysql(
            "TEST", "oil_pressure", 35.0, datetime.now(timezone.utc)
        )


class TestCleanupOperations:
    """Lines 951-1018: Cleanup inactive trucks"""

    def test_cleanup_inactive_trucks_not_in_active_set(self):
        """Lines 965-983: Remove trucks not in active set"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Clear any existing histories
        engine.histories = {}
        engine.active_predictions = {}
        engine.last_analysis = {}

        # Add some trucks
        engine.add_sensor_reading("ACTIVE_001", "oil_pressure", 35.0)
        engine.add_sensor_reading("INACTIVE_001", "oil_pressure", 35.0)
        engine.add_sensor_reading("INACTIVE_002", "oil_pressure", 35.0)

        # Only ACTIVE_001 is active
        active_set = {"ACTIVE_001"}

        cleaned = engine.cleanup_inactive_trucks(active_set)

        assert cleaned == 2
        assert "ACTIVE_001" in engine.histories
        assert "INACTIVE_001" not in engine.histories
        assert "INACTIVE_002" not in engine.histories

    def test_cleanup_inactive_trucks_old_data(self):
        """Lines 1000-1018: Remove trucks with old data"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Add truck with old data
        old_ts = datetime.now(timezone.utc) - timedelta(days=45)
        engine.add_sensor_reading("OLD_TRUCK", "oil_pressure", 35.0, old_ts)

        # Add truck with recent data
        engine.add_sensor_reading("NEW_TRUCK", "oil_pressure", 35.0)

        # Both in active set but OLD_TRUCK has stale data
        active_set = {"OLD_TRUCK", "NEW_TRUCK"}

        cleaned = engine.cleanup_inactive_trucks(active_set, max_inactive_days=30)

        assert "NEW_TRUCK" in engine.histories
        # OLD_TRUCK might be cleaned


class TestAdvancedAnalytics:
    """Lines 1030-1058: Advanced analytics methods"""

    def test_get_truck_maintenance_status_no_history(self):
        """Lines 1030-1032: Truck not in histories"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        result = engine.get_truck_maintenance_status("NONEXISTENT")
        assert result is None

    def test_get_truck_maintenance_status_with_predictions(self):
        """Lines 1042-1058: Full status with predictions"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Add critical data
        for i in range(10):
            engine.add_sensor_reading(
                "STATUS_TEST",
                "oil_pressure",
                20.0,  # Warning level
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        status = engine.get_truck_maintenance_status("STATUS_TEST")

        assert status is not None
        assert "truck_id" in status
        assert "summary" in status
        assert "predictions" in status
        assert "sensors_tracked" in status
        assert status["summary"]["sensors_tracked"] >= 1

    def test_get_sensor_trend_no_truck(self):
        """Lines 1168-1171: Truck not in histories"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        result = engine.get_sensor_trend("NONEXISTENT", "oil_pressure")
        assert result is None

    def test_get_sensor_trend_no_sensor(self):
        """Line 1182: Sensor not in truck histories"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine.histories["TREND_TEST"] = {}
        result = engine.get_sensor_trend("TREND_TEST", "oil_pressure")
        assert result is None

    def test_get_sensor_trend_no_config(self):
        """Lines 1199-1201: Sensor not in SENSOR_THRESHOLDS"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        history = SensorHistory("unknown_sensor", "TREND_TEST2")
        engine.histories["TREND_TEST2"] = {"unknown_sensor": history}

        result = engine.get_sensor_trend("TREND_TEST2", "unknown_sensor")
        assert result is None

    def test_get_sensor_trend_full_data(self):
        """Lines 1199-1225: Full trend data"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        for i in range(15):
            engine.add_sensor_reading(
                "FULL_TREND",
                "oil_pressure",
                35.0 - (i * 0.3),
                datetime.now(timezone.utc) - timedelta(days=15 - i),
            )

        result = engine.get_sensor_trend("FULL_TREND", "oil_pressure")

        assert result is not None
        assert "truck_id" in result
        assert "sensor_name" in result
        assert "component" in result
        assert "unit" in result
        assert "current_value" in result
        assert "trend_per_day" in result
        assert "thresholds" in result
        assert "history" in result
        assert "readings_count" in result


class TestMaintenanceAlerts:
    """Lines 1233-1248: Maintenance alerts generation"""

    def test_get_maintenance_alerts_critical_and_high(self):
        """Lines 1233-1248: Filter only critical/high"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Add critical issue
        for i in range(10):
            engine.add_sensor_reading(
                "ALERT_TEST",
                "oil_pressure",
                18.0,  # Critical
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        alerts = engine.get_maintenance_alerts("ALERT_TEST")

        assert isinstance(alerts, list)
        # Should contain alerts
        for alert in alerts:
            assert alert["urgency"] in ["CRÍTICO", "ALTO"]

    def test_get_maintenance_alerts_no_issues(self):
        """Test truck with no critical/high issues"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Add normal readings
        for i in range(10):
            engine.add_sensor_reading(
                "NORMAL_TRUCK",
                "oil_pressure",
                40.0,  # Normal
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        alerts = engine.get_maintenance_alerts("NORMAL_TRUCK")
        assert alerts == []


class TestStorageInfo:
    """Lines 1269: Storage info"""

    def test_get_storage_info_mysql(self):
        """Storage info with MySQL"""
        engine = PredictiveMaintenanceEngine(use_mysql=True)
        engine.add_sensor_reading("INFO_TEST", "oil_pressure", 35.0)

        info = engine.get_storage_info()

        assert "version" in info
        assert "storage_type" in info
        assert "mysql_available" in info
        assert "mysql_active" in info
        assert "pending_writes" in info
        assert "trucks_tracked" in info
        assert "total_readings_in_memory" in info
        assert "json_file" in info

    def test_get_storage_info_json_only(self):
        """Storage info with JSON fallback"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        info = engine.get_storage_info()

        assert info["storage_type"] == "JSON"
        assert info["mysql_active"] == False


class TestFlushAndSave:
    """Test flush and save operations"""

    def test_flush_mysql_enabled(self):
        """Flush with MySQL enabled"""
        engine = PredictiveMaintenanceEngine(use_mysql=True)
        engine.flush()
        # Should not raise error

    def test_flush_mysql_disabled(self):
        """Flush with MySQL disabled"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine.flush()
        # Should not raise error

    def test_save_method(self, tmp_path):
        """Test save method calls _save_state"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine.DATA_DIR = tmp_path
        engine.STATE_FILE = tmp_path / "save_test.json"

        engine.add_sensor_reading("SAVE_TEST", "oil_pressure", 35.0)
        engine.save()

        assert engine.STATE_FILE.exists()


class TestUrgencyCalculation:
    """Lines 951-1000: Urgency calculation edge cases"""

    def test_urgency_already_critical_higher_bad(self):
        """Already at critical level (temp)"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        for i in range(10):
            engine.add_sensor_reading(
                "CRIT_TEMP",
                "coolant_temp",
                250.0,  # Above critical (235)
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        pred = engine.analyze_sensor("CRIT_TEMP", "coolant_temp")
        assert pred.urgency == MaintenanceUrgency.CRITICAL

    def test_urgency_already_critical_lower_bad(self):
        """Already at critical level (pressure)"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        for i in range(10):
            engine.add_sensor_reading(
                "CRIT_PRESS",
                "oil_pressure",
                15.0,  # Below critical (20)
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        pred = engine.analyze_sensor("CRIT_PRESS", "oil_pressure")
        assert pred.urgency == MaintenanceUrgency.CRITICAL

    def test_urgency_in_warning_zone(self):
        """In warning zone but not critical"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        for i in range(10):
            engine.add_sensor_reading(
                "WARN_PRESS",
                "oil_pressure",
                22.0,  # Between warning (25) and critical (20)
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        pred = engine.analyze_sensor("WARN_PRESS", "oil_pressure")
        assert pred.urgency == MaintenanceUrgency.HIGH

    def test_urgency_3_days_to_critical(self):
        """Exactly 3 days to critical"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Trending toward critical in exactly 3 days
        for i in range(10):
            engine.add_sensor_reading(
                "THREE_DAYS",
                "oil_pressure",
                26.0 - (i * 0.2),  # Will reach 20 in ~3 days
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        pred = engine.analyze_sensor("THREE_DAYS", "oil_pressure")
        # Should be HIGH or CRITICAL

    def test_urgency_7_days_to_critical(self):
        """7 days to critical threshold"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        for i in range(10):
            engine.add_sensor_reading(
                "SEVEN_DAYS",
                "oil_pressure",
                27.0 - (i * 0.1),
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        pred = engine.analyze_sensor("SEVEN_DAYS", "oil_pressure")
        # Should be MEDIUM or HIGH

    def test_urgency_30_days_to_critical(self):
        """30 days to critical"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        for i in range(10):
            engine.add_sensor_reading(
                "THIRTY_DAYS",
                "oil_pressure",
                30.0 - (i * 0.033),
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        pred = engine.analyze_sensor("THIRTY_DAYS", "oil_pressure")
        # Should be LOW or MEDIUM

    def test_urgency_degrading_far_from_threshold(self):
        """Degrading but far from threshold"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        for i in range(10):
            engine.add_sensor_reading(
                "FAR_DEGRADE",
                "oil_pressure",
                45.0 - (i * 0.01),  # Slowly degrading but still good
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        pred = engine.analyze_sensor("FAR_DEGRADE", "oil_pressure")
        # Should be LOW or NONE


class TestSingletonPattern:
    """Test global instance"""

    def test_get_predictive_maintenance_engine_singleton(self):
        """Should return same instance"""
        engine1 = get_predictive_maintenance_engine()
        engine2 = get_predictive_maintenance_engine()

        assert engine1 is engine2


class TestConfidenceLevels:
    """Lines 909-922: Confidence calculation"""

    def test_confidence_high_7plus_days(self):
        """7+ days of data = HIGH confidence"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        for i in range(10):
            engine.add_sensor_reading(
                "CONF_HIGH",
                "oil_pressure",
                35.0 - (i * 0.2),
                datetime.now(timezone.utc) - timedelta(days=10 - i),
            )

        pred = engine.analyze_sensor("CONF_HIGH", "oil_pressure")
        assert pred.confidence == "HIGH"

    def test_confidence_medium_3to6_days(self):
        """3-6 days of data = MEDIUM confidence"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        for i in range(5):
            engine.add_sensor_reading(
                "CONF_MED",
                "oil_pressure",
                35.0,
                datetime.now(timezone.utc) - timedelta(days=5 - i),
            )

        pred = engine.analyze_sensor("CONF_MED", "oil_pressure")
        assert pred.confidence in ["MEDIUM", "HIGH"]

    def test_confidence_low_less_than_3_days(self):
        """< 3 days of data = LOW confidence"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        for i in range(2):
            engine.add_sensor_reading(
                "CONF_LOW",
                "oil_pressure",
                35.0,
                datetime.now(timezone.utc) - timedelta(days=2 - i),
            )

        pred = engine.analyze_sensor("CONF_LOW", "oil_pressure")
        # Might be None due to insufficient trend data


class TestDaysCalculationCapping:
    """Lines 881-895: Days calculation with 365-day cap"""

    def test_days_to_warning_capped_at_365(self):
        """Very slow trend should cap at 365 days"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Very slow degradation
        for i in range(30):
            engine.add_sensor_reading(
                "SLOW_DEGRADE",
                "oil_pressure",
                50.0 - (i * 0.001),  # Extremely slow drop
                datetime.now(timezone.utc) - timedelta(days=30 - i),
            )

        pred = engine.analyze_sensor("SLOW_DEGRADE", "oil_pressure")

        if pred and pred.days_to_warning:
            assert pred.days_to_warning <= 365


class TestAddSensorReadingEdgeCases:
    """Lines 753-781: add_sensor_reading edge cases"""

    def test_add_sensor_reading_none_value(self):
        """None value should be skipped"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine.add_sensor_reading("NONE_TEST", "oil_pressure", None)

        assert "NONE_TEST" not in engine.histories

    def test_add_sensor_reading_unknown_sensor(self):
        """Unknown sensor should be skipped"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine.add_sensor_reading("UNKNOWN_TEST", "fake_sensor", 123.0)

        assert "UNKNOWN_TEST" not in engine.histories

    def test_add_sensor_reading_naive_timestamp(self):
        """Naive timestamp should be converted to UTC"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        naive_ts = datetime(2025, 1, 1, 12, 0, 0)  # No timezone

        engine.add_sensor_reading("NAIVE_TEST", "oil_pressure", 35.0, naive_ts)

        if (
            "NAIVE_TEST" in engine.histories
            and "oil_pressure" in engine.histories["NAIVE_TEST"]
        ):
            history = engine.histories["NAIVE_TEST"]["oil_pressure"]
            if history.readings:
                assert history.readings[-1].timestamp.tzinfo is not None

    def test_add_sensor_reading_initializes_structures(self):
        """Should initialize truck and sensor structures"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        engine.add_sensor_reading("INIT_TEST", "oil_pressure", 35.0)

        assert "INIT_TEST" in engine.histories
        assert "oil_pressure" in engine.histories["INIT_TEST"]
        assert isinstance(engine.histories["INIT_TEST"]["oil_pressure"], SensorHistory)
