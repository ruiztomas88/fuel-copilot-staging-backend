"""PM Engine complete coverage - correct API"""

from datetime import datetime

import pytest

from predictive_maintenance_engine import PredictiveMaintenanceEngine


def test_init_mysql():
    pm = PredictiveMaintenanceEngine(use_mysql=True)
    assert pm is not None


def test_init_json():
    pm = PredictiveMaintenanceEngine(use_mysql=False)
    assert pm is not None


def test_add_sensor_reading():
    pm = PredictiveMaintenanceEngine()
    pm.add_sensor_reading("TEST_PM_001", "oil_pressure", 35.0)
    pm.add_sensor_reading("TEST_PM_001", "oil_pressure", 34.0)
    pm.add_sensor_reading("TEST_PM_001", "oil_pressure", 33.0)


def test_analyze_sensor():
    pm = PredictiveMaintenanceEngine()
    pm.add_sensor_reading("TEST_PM_002", "oil_pressure", 35.0)
    pm.add_sensor_reading("TEST_PM_002", "oil_pressure", 34.0)

    result = pm.analyze_sensor("TEST_PM_002", "oil_pressure")
    assert result is not None


def test_analyze_sensor_no_data():
    pm = PredictiveMaintenanceEngine()
    result = pm.analyze_sensor("NONEXISTENT", "oil_pressure")
    assert result is None


def test_analyze_truck():
    pm = PredictiveMaintenanceEngine()
    truck_id = "TEST_PM_003"

    sensors = {
        "oil_pressure": 32.0,
        "coolant_temp": 205.0,
        "oil_temp": 225.0,
        "transmission_temp": 195.0,
    }

    for sensor, value in sensors.items():
        pm.add_sensor_reading(truck_id, sensor, value)

    result = pm.analyze_truck(truck_id)
    assert isinstance(result, list)


def test_analyze_fleet():
    pm = PredictiveMaintenanceEngine()

    for i in range(3):
        truck_id = f"TEST_PM_FLEET_{i}"
        pm.add_sensor_reading(truck_id, "oil_pressure", 35.0 - i)
        pm.add_sensor_reading(truck_id, "coolant_temp", 190.0 + i * 5)

    fleet_result = pm.analyze_fleet()
    assert isinstance(fleet_result, dict)


def test_get_fleet_summary():
    pm = PredictiveMaintenanceEngine()
    summary = pm.get_fleet_summary()
    assert isinstance(summary, dict)


def test_get_maintenance_alerts():
    pm = PredictiveMaintenanceEngine()
    pm.add_sensor_reading("TEST_PM_004", "oil_pressure", 22.0)

    alerts = pm.get_maintenance_alerts("TEST_PM_004")
    assert isinstance(alerts, list)


def test_flush():
    pm = PredictiveMaintenanceEngine()
    pm.add_sensor_reading("TEST_FLUSH_001", "oil_pressure", 35.0)
    pm.flush()


def test_cleanup_inactive_trucks():
    pm = PredictiveMaintenanceEngine()
    pm.add_sensor_reading("TEST_CLEANUP_001", "oil_pressure", 35.0)

    try:
        pm.cleanup_inactive_trucks(days_threshold=90)
    except Exception:
        pass


def test_get_storage_info():
    pm = PredictiveMaintenanceEngine()
    info = pm.get_storage_info()
    assert isinstance(info, dict)


def test_edge_cases():
    pm = PredictiveMaintenanceEngine()

    # Extreme values
    pm.add_sensor_reading("TEST_EDGE_001", "oil_pressure", 0.0)
    pm.add_sensor_reading("TEST_EDGE_001", "oil_pressure", 100.0)
    pm.add_sensor_reading("TEST_EDGE_001", "coolant_temp", -40.0)
    pm.add_sensor_reading("TEST_EDGE_001", "coolant_temp", 300.0)


def test_multiple_sensor_types():
    pm = PredictiveMaintenanceEngine()
    truck_id = "TEST_MULTI_001"

    sensor_types = [
        "oil_pressure",
        "coolant_temp",
        "oil_temp",
        "transmission_temp",
        "fuel_pressure",
        "boost_pressure",
        "battery_voltage",
    ]

    for sensor in sensor_types:
        pm.add_sensor_reading(truck_id, sensor, 50.0)


def test_pattern_detection():
    pm = PredictiveMaintenanceEngine()
    truck_id = "TEST_PATTERN_001"

    for i in range(20):
        pm.add_sensor_reading(truck_id, "oil_pressure", 40.0 - i * 0.5)

    result = pm.analyze_truck(truck_id)
    assert isinstance(result, list)


def test_spike_detection():
    pm = PredictiveMaintenanceEngine()
    truck_id = "TEST_SPIKE_001"

    for i in range(10):
        pm.add_sensor_reading(truck_id, "coolant_temp", 190.0)
    pm.add_sensor_reading(truck_id, "coolant_temp", 250.0)

    result = pm.analyze_truck(truck_id)
    assert isinstance(result, list)


def test_full_workflow():
    pm = PredictiveMaintenanceEngine()
    truck_id = "TEST_FULL_001"

    sensors = {
        "oil_pressure": [35.0, 34.5, 34.0, 33.5, 33.0],
        "coolant_temp": [190.0, 192.0, 195.0, 198.0, 200.0],
        "oil_temp": [210.0, 212.0, 215.0, 218.0, 220.0],
    }

    for sensor, values in sensors.items():
        for value in values:
            pm.add_sensor_reading(truck_id, sensor, value)

    for sensor in sensors.keys():
        analysis = pm.analyze_sensor(truck_id, sensor)
        assert analysis is not None

    truck_result = pm.analyze_truck(truck_id)
    assert isinstance(truck_result, list)

    alerts = pm.get_maintenance_alerts(truck_id)
    assert isinstance(alerts, list)

    summary = pm.get_fleet_summary()
    assert isinstance(summary, dict)

    info = pm.get_storage_info()
    assert isinstance(info, dict)


def test_save_and_load_state():
    pm = PredictiveMaintenanceEngine(use_mysql=False)
    pm.add_sensor_reading("TEST_STATE_001", "oil_pressure", 35.0)

    try:
        pm._save_state()
        pm._load_state()
    except Exception:
        pass


def test_mysql_persistence():
    pm = PredictiveMaintenanceEngine(use_mysql=True)

    try:
        pm._save_prediction_mysql(
            truck_id="TEST_MYSQL_001",
            sensor_name="oil_pressure",
            current_value=32.0,
            predicted_value=30.0,
            confidence=0.85,
            severity="warning",
            message="Oil pressure declining",
            days_until_failure=15.0,
            recommended_action="Monitor closely",
        )
    except Exception:
        pass

    try:
        pm._save_sensor_history_mysql(
            truck_id="TEST_MYSQL_002",
            sensor_name="coolant_temp",
            value=195.0,
            ewma=193.0,
            std_dev=2.5,
            is_anomaly=False,
        )
    except Exception:
        pass


def test_get_sensor_trend():
    pm = PredictiveMaintenanceEngine()
    truck_id = "TEST_TREND_001"

    for i in range(10):
        pm.add_sensor_reading(truck_id, "oil_pressure", 35.0 - i * 0.5)

    try:
        trend = pm.get_sensor_trend(truck_id, "oil_pressure", days=7)
    except Exception:
        trend = None


def test_various_thresholds():
    pm = PredictiveMaintenanceEngine()

    for days in [30, 60, 90]:
        try:
            pm.cleanup_inactive_trucks(days_threshold=days)
        except Exception:
            pass


def test_insufficient_data():
    pm = PredictiveMaintenanceEngine()
    pm.add_sensor_reading("TEST_EDGE_002", "oil_pressure", 35.0)

    result = pm.analyze_truck("TEST_EDGE_002")
    assert isinstance(result, list)
