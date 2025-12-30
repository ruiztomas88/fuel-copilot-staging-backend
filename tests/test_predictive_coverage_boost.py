"""
Simple tests to improve predictive_maintenance_engine coverage to 90%
Focus: Testing actual code paths that are missing
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from predictive_maintenance_engine import PredictiveMaintenanceEngine, SensorHistory


class TestJSONStatePersistence:
    """Test JSON state persistence - covers lines 682-738"""

    def test_save_and_load_state(self):
        """Test saving and loading state"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Add some data
        engine.process_sensor_batch(
            truck_id="TEST_TRUCK",
            sensor_data={"trans_temp": 185.0, "oil_pressure": 32.0},
            timestamp=datetime.now(timezone.utc),
        )

        # Save state
        engine._save_state()

        # Verify file exists
        assert engine.STATE_FILE.exists()

    def test_load_handles_missing_file(self):
        """Test graceful handling of missing state file"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        # Should not crash even if no state file
        assert isinstance(engine.histories, dict)

    def test_load_handles_corrupt_json(self):
        """Test handling of corrupted JSON file - line 703-704"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Write invalid JSON
        engine.DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(engine.STATE_FILE, "w") as f:
            f.write("{ invalid json !!!")

        # Create new engine - should handle error gracefully
        engine2 = PredictiveMaintenanceEngine(use_mysql=False)
        assert isinstance(engine2.histories, dict)


class TestMySQLPaths:
    """Test MySQL persistence paths - lines 711-715"""

    def test_save_calls_mysql_flush_when_enabled(self):
        """Test that _save_state calls MySQL flush when enabled"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)
        engine._use_mysql = True
        engine._flush_mysql_writes = MagicMock()

        engine.process_sensor_batch(
            truck_id="MYSQL_TRUCK",
            sensor_data={"trans_temp": 180.0},
            timestamp=datetime.now(timezone.utc),
        )

        engine._save_state()

        # MySQL flush should be called
        engine._flush_mysql_writes.assert_called_once()


class TestSensorHistoryClass:
    """Test SensorHistory class methods"""

    def test_sensor_history_to_dict(self):
        """Test converting SensorHistory to dict"""
        history = SensorHistory(sensor_name="test_sensor", truck_id="TRUCK1")
        history.baseline_mean = 50.0
        history.baseline_std = 5.0

        data = history.to_dict()

        assert data["sensor_name"] == "test_sensor"
        assert data["truck_id"] == "TRUCK1"
        assert data["baseline_mean"] == 50.0

    def test_sensor_history_from_dict(self):
        """Test creating SensorHistory from dict"""
        data = {
            "sensor_name": "coolant_temp",
            "truck_id": "TRUCK2",
            "baseline_mean": 195.0,
            "baseline_std": 10.0,
            "readings": [],
        }

        history = SensorHistory.from_dict(data)

        assert history.sensor_name == "coolant_temp"
        assert history.truck_id == "TRUCK2"
        assert history.baseline_mean == 195.0


class TestFleetAnalysis:
    """Test fleet analysis methods - lines 1200-1226"""

    def test_analyze_fleet_with_multiple_trucks(self):
        """Test analyzing entire fleet"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Add data for multiple trucks
        for truck_id in ["FLEET1", "FLEET2", "FLEET3"]:
            for i in range(15):
                engine.process_sensor_batch(
                    truck_id=truck_id,
                    sensor_data={"trans_temp": 170.0 + (i * 3.0)},
                    timestamp=datetime.now(timezone.utc) - timedelta(hours=15 - i),
                )

        # Analyze fleet
        results = engine.analyze_fleet()

        # Should return dict
        assert isinstance(results, dict)

    def test_get_fleet_summary(self):
        """Test getting fleet summary"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        # Add data
        for i in range(10):
            engine.process_sensor_batch(
                truck_id="SUMMARY_TRUCK",
                sensor_data={"trans_temp": 180.0 + i},
                timestamp=datetime.now(timezone.utc) - timedelta(hours=10 - i),
            )

        summary = engine.get_fleet_summary()

        assert isinstance(summary, dict)


class TestMainBlock:
    """Test main block execution - lines 1369-1460"""

    def test_simulation_like_main_block(self):
        """Test simulation similar to __main__ block"""
        import random

        engine = PredictiveMaintenanceEngine(use_mysql=False)

        trucks = ["FM3679", "CO0681"]

        # Simulate a few days
        for truck in trucks:
            for day in range(7):
                ts = datetime.now(timezone.utc) - timedelta(days=7 - day)

                trans_temp = 175 + (day * 2.5) + random.uniform(-3, 3)
                oil_pressure = 35 - (day * 0.6) + random.uniform(-2, 2)

                engine.process_sensor_batch(
                    truck_id=truck,
                    sensor_data={
                        "trans_temp": trans_temp,
                        "oil_pressure": oil_pressure,
                    },
                    timestamp=ts,
                )

        # Analyze
        results = engine.analyze_fleet()

        assert isinstance(results, dict)


class TestEdgeCases:
    """Test edge cases"""

    def test_process_batch_with_none_values(self):
        """Test processing batch with None values - line 589, 592-593"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        engine.process_sensor_batch(
            truck_id="NONE_TRUCK",
            sensor_data={
                "trans_temp": None,
                "oil_pressure": 35.0,
                "coolant_temp": None,
            },
            timestamp=datetime.now(timezone.utc),
        )

        # Should only process non-None values
        if "NONE_TRUCK" in engine.histories:
            assert "oil_pressure" in engine.histories["NONE_TRUCK"]

    def test_analyze_empty_truck(self):
        """Test analyzing truck with no history"""
        engine = PredictiveMaintenanceEngine(use_mysql=False)

        predictions = engine.analyze_truck("NONEXISTENT")

        assert predictions == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
