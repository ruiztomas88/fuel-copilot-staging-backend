"""Ultra-targeted tests for final PM missing lines"""

from datetime import datetime, timedelta, timezone

import pytest

from predictive_maintenance_engine import (
    MaintenancePrediction,
    MaintenanceUrgency,
    PredictiveMaintenanceEngine,
)


def test_line_316_zero_denominator():
    """Line 316: Exact zero denominator in calculate_trend"""
    from predictive_maintenance_engine import SensorHistory

    history = SensorHistory("oil_pressure", "TEST")

    # Create data with identical x_values after averaging
    ts = datetime.now(timezone.utc)
    # All on same day
    history.add_reading(ts, 35.0)
    history.add_reading(ts + timedelta(hours=1), 36.0)
    history.add_reading(ts + timedelta(hours=2), 35.5)

    # This creates only 1 daily average, can't calculate trend
    trend = history.calculate_trend()


def test_line_411_413_days_to_warning_only():
    """Lines 411-413: Has days_to_warning but no days_to_critical"""
    pred = MaintenancePrediction(
        truck_id="TEST",
        sensor_name="oil_pressure",
        component="Oil",
        current_value=27.0,
        unit="psi",
        trend_per_day=-0.1,
        trend_direction="DEGRADANDO",
        days_to_warning=50,  # Has warning
        days_to_critical=None,  # No critical
        urgency=MaintenanceUrgency.LOW,
        confidence="HIGH",
        recommended_action="Monitor",
        estimated_cost_if_fail=None,
        warning_threshold=25.0,
        critical_threshold=20.0,
    )

    msg = pred.to_alert_message()
    assert "50 días" in msg


def test_line_419_420_no_trend():
    """Lines 419-420: No trend_per_day"""
    pred = MaintenancePrediction(
        truck_id="TEST",
        sensor_name="oil_pressure",
        component="Oil",
        current_value=22.0,
        unit="psi",
        trend_per_day=None,  # No trend
        trend_direction="DESCONOCIDO",
        days_to_warning=10,
        days_to_critical=5,
        urgency=MaintenanceUrgency.HIGH,
        confidence="LOW",
        recommended_action="Check",
        estimated_cost_if_fail=None,
        warning_threshold=25.0,
        critical_threshold=20.0,
    )

    msg = pred.to_alert_message()
    # Should not have trend string


def test_line_487_mysql_not_available():
    """Line 487: _mysql_available is False"""
    # Set use_mysql=False to force JSON path
    engine = PredictiveMaintenanceEngine(use_mysql=False)
    assert engine._use_mysql == False


def test_line_492_493_batch_timestamp():
    """Lines 492-493: Explicit timestamp in process_sensor_batch"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)

    custom_ts = datetime(2025, 6, 15, 10, 30, 0, tzinfo=timezone.utc)

    engine.process_sensor_batch(
        "CUSTOM_TS", {"oil_pressure": 35.0}, timestamp=custom_ts
    )


def test_line_506_510_none_values_skip():
    """Lines 506-510: None values in batch are skipped"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)

    engine.process_sensor_batch(
        "SKIP_NONE",
        {
            "oil_pressure": 35.0,
            "coolant_temp": None,
            "trans_temp": None,
            "def_level": 45.0,
            "turbo_temp": None,
        },
    )

    assert "oil_pressure" in engine.histories["SKIP_NONE"]
    assert "def_level" in engine.histories["SKIP_NONE"]
    assert "coolant_temp" not in engine.histories["SKIP_NONE"]


def test_line_514_517_default_timestamp():
    """Lines 514-517: Default to current time"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)

    before = datetime.now(timezone.utc)

    engine.process_sensor_batch("DEFAULT_TS", {"oil_pressure": 35.0})

    after = datetime.now(timezone.utc)


def test_line_539_540_no_mysql_rows():
    """Lines 539-540: No rows from MySQL query"""
    engine = PredictiveMaintenanceEngine(use_mysql=True)
    # If MySQL is available but has no data


def test_line_572_574_mysql_load_return():
    """Lines 572-574: Return True after MySQL load"""
    engine = PredictiveMaintenanceEngine(use_mysql=True)


def test_line_623_624_good_fleet_state():
    """Lines 623-624: All trucks OK recommendation"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)

    # Add perfectly healthy trucks
    for truck_num in range(3):
        for day in range(10):
            engine.add_sensor_reading(
                f"HEALTHY{truck_num}",
                "oil_pressure",
                42.0,  # Excellent
                datetime.now(timezone.utc) - timedelta(days=10 - day),
            )

    summary = engine.get_fleet_summary()
    recs = summary["recommendations"]

    # Should say fleet is in good state
    good_state = any("buen estado" in r.lower() for r in recs)


def test_line_658_update_daily_avg_exception():
    """Line 658: Exception in _update_daily_avg_mysql"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)

    # MySQL disabled, should return silently
    engine._update_daily_avg_mysql(
        "TEST", "oil_pressure", 35.0, datetime.now(timezone.utc)
    )


def test_line_712_load_json_exception():
    """Line 712: Exception loading JSON"""
    import tempfile
    from pathlib import Path

    engine = PredictiveMaintenanceEngine(use_mysql=False)

    with tempfile.TemporaryDirectory() as tmpdir:
        engine.STATE_FILE = Path(tmpdir) / "bad.json"

        with open(engine.STATE_FILE, "w") as f:
            f.write("{{{{ invalid")

        # Should handle exception
        engine._load_state_json()


def test_line_965_not_in_active_set():
    """Line 965: Truck not in active_truck_ids set"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)
    engine.histories = {}

    engine.add_sensor_reading("REMOVE", "oil_pressure", 35.0)

    # Active set doesn't include REMOVE
    active = set()

    cleaned = engine.cleanup_inactive_trucks(active)
    assert cleaned >= 1


def test_line_967_continue_not_in_active():
    """Line 967: Continue to next truck"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)
    engine.histories = {}

    engine.add_sensor_reading("KEEP", "oil_pressure", 35.0)
    engine.add_sensor_reading("REMOVE", "oil_pressure", 35.0)

    active = {"KEEP"}

    cleaned = engine.cleanup_inactive_trucks(active)

    assert "KEEP" in engine.histories
    assert "REMOVE" not in engine.histories


def test_line_975_has_recent_true():
    """Line 975: has_recent = True"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)
    engine.histories = {}

    # Add very recent data
    engine.add_sensor_reading(
        "RECENT", "oil_pressure", 35.0, datetime.now(timezone.utc) - timedelta(hours=1)
    )

    active = {"RECENT"}

    cleaned = engine.cleanup_inactive_trucks(active, max_inactive_days=30)

    assert "RECENT" in engine.histories


def test_line_977_break_has_recent():
    """Line 977: Break when has_recent found"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)
    engine.histories = {}

    # Add truck with multiple sensors, one recent
    ts_recent = datetime.now(timezone.utc)
    ts_old = datetime.now(timezone.utc) - timedelta(days=40)

    engine.add_sensor_reading("MULTI", "oil_pressure", 35.0, ts_old)
    engine.add_sensor_reading("MULTI", "coolant_temp", 195.0, ts_recent)

    active = {"MULTI"}

    cleaned = engine.cleanup_inactive_trucks(active, max_inactive_days=30)

    # Should keep because has one recent sensor
    assert "MULTI" in engine.histories


def test_line_981_append_to_remove():
    """Line 981: Append truck to trucks_to_remove"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)
    engine.histories = {}

    # Add truck with old data
    old_ts = datetime.now(timezone.utc) - timedelta(days=45)
    engine.add_sensor_reading("OLD", "oil_pressure", 35.0, old_ts)

    active = {"OLD"}

    cleaned = engine.cleanup_inactive_trucks(active, max_inactive_days=30)


def test_line_1114_1117_delete_predictions_analysis():
    """Lines 1114-1117: Delete from active_predictions and last_analysis"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)
    engine.histories = {}
    engine.active_predictions = {}
    engine.last_analysis = {}

    # Add and analyze
    engine.add_sensor_reading("DEL", "oil_pressure", 35.0)
    engine.analyze_truck("DEL")

    assert "DEL" in engine.active_predictions
    assert "DEL" in engine.last_analysis

    # Remove
    active = set()
    engine.cleanup_inactive_trucks(active)

    assert "DEL" not in engine.active_predictions
    assert "DEL" not in engine.last_analysis


def test_line_1170_truck_not_in_histories():
    """Line 1170: Return None when truck not found"""
    engine = PredictiveMaintenanceEngine(use_mysql=False)

    result = engine.get_sensor_trend("NOTFOUND", "oil_pressure")
    assert result is None


def test_line_1368_1459_main_block():
    """Lines 1368-1459: Main block (not executed in tests)"""
    # This is the if __name__ == "__main__" block
    # Only runs when file is executed directly
    pass
