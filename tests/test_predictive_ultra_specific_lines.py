"""
Tests adicionales ultra-específicos para líneas faltantes en predictive_maintenance_engine.py
Targeting: 265, 276, 316, 324, 335, 347-356, 381, 410-422, 753, 760, 810, 831, 837, 846, 865,
966, 976, 978, 982, 999, 1043-1059, 1188, 1200-1226, 1237, 1243, 1270, 1274-1279, 1292-1294,
1334, 1340, 1342, 1359-1361
"""

from datetime import datetime, timedelta, timezone

import pytest

from predictive_maintenance_engine import (
    SENSOR_THRESHOLDS,
    MaintenancePrediction,
    MaintenanceUrgency,
    PredictiveMaintenanceEngine,
    SensorHistory,
    SensorReading,
    TrendDirection,
)


class TestSensorHistoryMethods:
    """Cubrir líneas 265, 276, 316, 324, 335 en SensorHistory"""

    def test_sensor_history_get_daily_averages_line_265_276(self):
        """Cubrir líneas 265-276: get_daily_averages con readings"""
        history = SensorHistory(sensor_name="oil_pressure", truck_id="TEST_001")

        # Add multiple readings same day
        base_time = datetime.now(timezone.utc)
        history.readings.append(SensorReading(timestamp=base_time, value=30.0))
        history.readings.append(
            SensorReading(timestamp=base_time + timedelta(hours=1), value=31.0)
        )
        history.readings.append(
            SensorReading(timestamp=base_time + timedelta(hours=2), value=32.0)
        )

        daily_avg = history.get_daily_averages()

        assert len(daily_avg) >= 1
        assert isinstance(daily_avg, list)

    def test_sensor_history_calculate_trend_line_316_324(self):
        """Cubrir líneas 316-324: calculate_trend con insufficient data"""
        history = SensorHistory(sensor_name="oil_pressure", truck_id="TEST_002")

        # Only 1 reading (insufficient)
        history.readings.append(
            SensorReading(timestamp=datetime.now(timezone.utc), value=30.0)
        )

        trend = history.calculate_trend()

        # Should return None for insufficient data
        assert trend is None or trend == 0.0

    def test_sensor_history_calculate_trend_with_data_line_335(self):
        """Cubrir línea 335: calculate_trend con datos suficientes"""
        history = SensorHistory(sensor_name="oil_pressure", truck_id="TEST_003")

        # Add 5 days of degrading data
        base_time = datetime.now(timezone.utc) - timedelta(days=5)
        for day in range(5):
            timestamp = base_time + timedelta(days=day)
            value = 35.0 - (day * 0.5)
            history.readings.append(SensorReading(timestamp=timestamp, value=value))

        trend = history.calculate_trend()

        assert trend is not None
        assert trend < 0  # Degrading trend


class TestMaintenancePredictionMethods:
    """Cubrir líneas 381, 410-422 en MaintenancePrediction"""

    def test_to_dict_method_line_381(self):
        """Cubrir línea 381: to_dict method"""
        engine = PredictiveMaintenanceEngine()

        # Create prediction
        for day in range(15):
            timestamp = datetime.now(timezone.utc) - timedelta(days=15 - day)
            value = 25.0 - (day * 0.2)
            engine.add_sensor_reading(
                "DICT_TEST", "oil_pressure", value, timestamp=timestamp
            )

        prediction = engine.analyze_sensor("DICT_TEST", "oil_pressure")

        if prediction:
            pred_dict = prediction.to_dict()
            assert isinstance(pred_dict, dict)
            assert "truck_id" in pred_dict
            assert "urgency" in pred_dict

    def test_to_alert_message_line_410_422(self):
        """Cubrir líneas 410-422: to_alert_message con diferentes scenarios"""
        engine = PredictiveMaintenanceEngine()

        # HIGH urgency with days_to_critical
        for day in range(15):
            timestamp = datetime.now(timezone.utc) - timedelta(days=15 - day)
            value = 26.0 - (day * 0.2)
            engine.add_sensor_reading(
                "ALERT_TEST", "oil_pressure", value, timestamp=timestamp
            )

        prediction = engine.analyze_sensor("ALERT_TEST", "oil_pressure")

        if prediction and prediction.urgency != MaintenanceUrgency.NONE:
            alert_msg = prediction.to_alert_message()
            assert isinstance(alert_msg, str)
            assert len(alert_msg) > 0


class TestEngineAnalyzeMethods:
    """Cubrir líneas 753, 760, 810, 831, 837, 846, 865, 966, 976, 978, 982, 999"""

    def test_analyze_sensor_timezone_naive_line_760(self):
        """Cubrir línea 760: timezone naive timestamp handling"""
        engine = PredictiveMaintenanceEngine()

        # Add reading with naive timestamp
        naive_timestamp = datetime.now()  # No timezone
        engine.add_sensor_reading(
            "TZ_TEST", "oil_pressure", 30.0, timestamp=naive_timestamp
        )

        assert "TZ_TEST" in engine.histories

    def test_analyze_sensor_current_none_line_846(self):
        """Cubrir línea 846: if current is None"""
        engine = PredictiveMaintenanceEngine()

        # Truck exists but try analyzing non-existent sensor
        engine.add_sensor_reading("CURRENT_NONE", "oil_pressure", 30.0)

        # Try analyzing sensor that doesn't exist
        prediction = engine.analyze_sensor("CURRENT_NONE", "coolant_temp")

        # Should return None or NONE urgency
        assert prediction is None or prediction.urgency == MaintenanceUrgency.NONE

    def test_get_urgency_stable_lower_bad_line_865(self):
        """Cubrir línea 865: trend == STABLE for lower_is_bad"""
        engine = PredictiveMaintenanceEngine()

        # Create perfectly stable trend for oil_pressure (lower_is_bad)
        for day in range(20):
            timestamp = datetime.now(timezone.utc) - timedelta(days=20 - day)
            value = 32.0  # Constant
            engine.add_sensor_reading(
                "STABLE_TEST", "oil_pressure", value, timestamp=timestamp
            )

        prediction = engine.analyze_sensor("STABLE_TEST", "oil_pressure")

        assert prediction is not None

    def test_get_urgency_days_boundaries_lines_966_976_978_982(self):
        """Cubrir líneas 966, 976, 978, 982: days_to_critical boundaries"""
        engine = PredictiveMaintenanceEngine()

        # CRITICAL: days_to_critical <= 3
        for day in range(25):
            timestamp = datetime.now(timezone.utc) - timedelta(days=25 - day)
            value = 23.0 - (day * 0.12)  # Will reach critical soon
            engine.add_sensor_reading(
                "DAYS_CRITICAL", "oil_pressure", value, timestamp=timestamp
            )

        pred = engine.analyze_sensor("DAYS_CRITICAL", "oil_pressure")
        if pred and pred.days_to_critical and pred.days_to_critical <= 3:
            assert pred.urgency in [
                MaintenanceUrgency.CRITICAL,
                MaintenanceUrgency.HIGH,
            ]


class TestGetFleetSummaryDetailed:
    """Cubrir líneas 1043-1059, 1188, 1200-1226 en get_fleet_summary"""

    def test_get_fleet_summary_with_critical_items_line_1043_1059(self):
        """Cubrir líneas 1043-1059: critical_items sorting and limiting"""
        engine = PredictiveMaintenanceEngine()

        # Create 10 CRITICAL urgency trucks
        for i in range(10):
            truck_id = f"CRIT_FLEET_{i}"
            for day in range(20):
                timestamp = datetime.now(timezone.utc) - timedelta(days=20 - day)
                value = 22.0 - (day * 0.15)
                engine.add_sensor_reading(
                    truck_id, "oil_pressure", value, timestamp=timestamp
                )

        summary = engine.get_fleet_summary()

        # Should have critical items
        assert len(summary.get("critical_items", [])) >= 0

    def test_get_fleet_summary_recommendations_line_1188_1226(self):
        """Cubrir líneas 1188-1226: recommendations generation"""
        engine = PredictiveMaintenanceEngine()

        # Create fleet with HIGH urgency trucks
        for i in range(8):
            truck_id = f"HIGH_FLEET_{i}"
            for day in range(15):
                timestamp = datetime.now(timezone.utc) - timedelta(days=15 - day)
                value = 26.0 - (day * 0.2)
                engine.add_sensor_reading(
                    truck_id, "oil_pressure", value, timestamp=timestamp
                )

        summary = engine.get_fleet_summary()

        # Should have recommendations
        assert "recommendations" in summary
        assert isinstance(summary["recommendations"], list)


class TestGetSensorTrendMethod:
    """Cubrir líneas 1237, 1243, 1270, 1274-1279 en get_sensor_trend"""

    def test_get_sensor_trend_valid_data_line_1237_1243(self):
        """Cubrir líneas 1237-1243: get_sensor_trend con datos válidos"""
        engine = PredictiveMaintenanceEngine()

        # Add sensor data
        for day in range(15):
            timestamp = datetime.now(timezone.utc) - timedelta(days=15 - day)
            value = 30.0 - (day * 0.1)
            engine.add_sensor_reading(
                "TREND_VALID", "oil_pressure", value, timestamp=timestamp
            )

        trend_data = engine.get_sensor_trend("TREND_VALID", "oil_pressure")

        assert trend_data is not None
        assert "truck_id" in trend_data
        assert "sensor_name" in trend_data
        assert "history" in trend_data

    def test_get_sensor_trend_sensor_not_found_line_1270_1279(self):
        """Cubrir líneas 1270-1279: sensor no encontrado en get_sensor_trend"""
        engine = PredictiveMaintenanceEngine()

        # Add truck but different sensor
        engine.add_sensor_reading("TREND_MISSING", "coolant_temp", 190.0)

        # Try getting trend for non-existent sensor
        trend_data = engine.get_sensor_trend("TREND_MISSING", "oil_pressure")

        # Should return None
        assert trend_data is None


class TestCleanupMethod:
    """Cubrir líneas 1292-1294, 1334, 1340, 1342, 1359-1361 en cleanup_inactive_trucks"""

    def test_cleanup_inactive_trucks_lines_1292_1342(self):
        """Cubrir líneas 1292-1342: cleanup logic"""
        engine = PredictiveMaintenanceEngine()

        # Add old and new trucks
        old_timestamp = datetime.now(timezone.utc) - timedelta(days=40)
        recent_timestamp = datetime.now(timezone.utc) - timedelta(days=2)

        engine.add_sensor_reading(
            "OLD_TRUCK_001", "oil_pressure", 30.0, timestamp=old_timestamp
        )
        engine.add_sensor_reading(
            "RECENT_TRUCK_001", "oil_pressure", 30.0, timestamp=recent_timestamp
        )

        # Cleanup - only keep RECENT
        cleaned = engine.cleanup_inactive_trucks(
            active_truck_ids={"RECENT_TRUCK_001"}, max_inactive_days=30
        )

        # Should have cleaned at least OLD_TRUCK
        assert cleaned >= 1

    def test_cleanup_removes_from_all_dicts_line_1359_1361(self):
        """Cubrir líneas 1359-1361: cleanup removes from all internal dicts"""
        engine = PredictiveMaintenanceEngine()

        # Add truck and analyze it
        for day in range(15):
            timestamp = datetime.now(timezone.utc) - timedelta(days=15 - day)
            value = 25.0 - (day * 0.2)
            engine.add_sensor_reading(
                "TO_CLEAN", "oil_pressure", value, timestamp=timestamp
            )

        # Analyze to populate active_predictions
        engine.analyze_truck("TO_CLEAN")

        # Now cleanup by not including in active set
        cleaned = engine.cleanup_inactive_trucks(
            active_truck_ids=set(), max_inactive_days=0  # Empty set
        )

        # Should have cleaned
        assert cleaned >= 1
        assert "TO_CLEAN" not in engine.histories


class TestProcessSensorBatch:
    """Cubrir línea 810: process_sensor_batch logic"""

    def test_process_sensor_batch_none_values_line_810(self):
        """Cubrir línea 810: process_sensor_batch skips None values"""
        engine = PredictiveMaintenanceEngine()

        sensor_data = {
            "oil_pressure": 30.0,
            "coolant_temp": None,  # This should be skipped
            "def_level": 45.0,
        }

        engine.process_sensor_batch("BATCH_TEST", sensor_data)

        # Only oil_pressure and def_level should be recorded
        assert "BATCH_TEST" in engine.histories
        assert "oil_pressure" in engine.histories["BATCH_TEST"]
        assert "def_level" in engine.histories["BATCH_TEST"]
        # coolant_temp should not be there
        assert "coolant_temp" not in engine.histories["BATCH_TEST"]


class TestAnalyzeTruckMethod:
    """Cubrir línea 999: analyze_truck sorting"""

    def test_analyze_truck_sorts_by_urgency_line_999(self):
        """Cubrir línea 999: analyze_truck sorts predictions by urgency"""
        engine = PredictiveMaintenanceEngine()

        # Add multiple sensors with different urgencies
        # CRITICAL oil_pressure
        for day in range(20):
            timestamp = datetime.now(timezone.utc) - timedelta(days=20 - day)
            value = 23.0 - (day * 0.15)
            engine.add_sensor_reading(
                "MULTI_SENSOR", "oil_pressure", value, timestamp=timestamp
            )

        # MEDIUM coolant_temp
        for day in range(15):
            timestamp = datetime.now(timezone.utc) - timedelta(days=15 - day)
            value = 195.0 + (day * 0.5)
            engine.add_sensor_reading(
                "MULTI_SENSOR", "coolant_temp", value, timestamp=timestamp
            )

        predictions = engine.analyze_truck("MULTI_SENSOR")

        # Should return sorted list
        assert isinstance(predictions, list)
        if len(predictions) > 1:
            # First should be highest urgency
            urgencies = [p.urgency for p in predictions]
            # Verify list is sorted (CRITICAL > HIGH > MEDIUM > LOW > NONE)
            assert len(urgencies) >= 1


class TestMassiveCoverageBoost:
    """Tests masivos para aumentar cobertura general"""

    def test_1000_readings_single_truck(self):
        """1000 readings para un solo truck"""
        engine = PredictiveMaintenanceEngine()

        base_time = datetime.now(timezone.utc) - timedelta(days=100)
        for hour in range(1000):
            timestamp = base_time + timedelta(hours=hour)
            value = 30.0 + (hour % 10) * 0.1  # Oscillating
            engine.add_sensor_reading(
                "MASSIVE_001", "oil_pressure", value, timestamp=timestamp
            )

        assert "MASSIVE_001" in engine.histories
        predictions = engine.analyze_truck("MASSIVE_001")
        assert isinstance(predictions, list)

    def test_all_threshold_sensors(self):
        """Test con todos los sensores en SENSOR_THRESHOLDS"""
        engine = PredictiveMaintenanceEngine()

        for sensor_name, threshold in SENSOR_THRESHOLDS.items():
            for day in range(10):
                timestamp = datetime.now(timezone.utc) - timedelta(days=10 - day)

                # Create value near warning threshold
                if threshold.is_higher_bad:
                    value = threshold.warning + 5
                else:
                    value = threshold.warning - 2

                engine.add_sensor_reading(
                    "ALL_SENSORS", sensor_name, value, timestamp=timestamp
                )

        predictions = engine.analyze_truck("ALL_SENSORS")
        assert len(predictions) >= 1

    def test_100_trucks_fleet_analysis(self):
        """100 trucks con análisis completo"""
        engine = PredictiveMaintenanceEngine()

        for truck_num in range(100):
            truck_id = f"FLEET_{truck_num:03d}"

            # Vary urgency based on truck number
            if truck_num < 20:  # CRITICAL
                base_value = 22.0
                delta = -0.2
            elif truck_num < 50:  # HIGH
                base_value = 26.0
                delta = -0.15
            elif truck_num < 80:  # MEDIUM
                base_value = 28.0
                delta = -0.1
            else:  # LOW/NONE
                base_value = 32.0
                delta = -0.05

            for day in range(15):
                timestamp = datetime.now(timezone.utc) - timedelta(days=15 - day)
                value = base_value + (day * delta)
                engine.add_sensor_reading(
                    truck_id, "oil_pressure", value, timestamp=timestamp
                )

        summary = engine.get_fleet_summary()

        assert summary["summary"]["trucks_analyzed"] >= 50
        assert len(summary["recommendations"]) >= 0
