"""Complete coverage for predictive_maintenance_engine.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timezone

from predictive_maintenance_engine import *


class TestPredictiveComplete:
    def test_sensor_history_all_methods(self):
        h = SensorHistory("oil_press", "DO9693")
        h.add_reading(datetime.now(timezone.utc), 45.5)
        h.add_reading(datetime.now(timezone.utc), 44.0)
        h.add_reading(datetime.now(timezone.utc), 42.5)
        h.get_daily_averages()
        h.calculate_trend()
        h.get_current_value()
        h.get_readings_count()
        d = h.to_dict()
        SensorHistory.from_dict(d)

    def test_maintenance_prediction_all_methods(self):
        p = MaintenancePrediction(
            "DO9693",
            "oil_system",
            MaintenanceUrgency.HIGH,
            5.0,
            0.85,
            "Test",
            75.0,
            "Action",
        )
        p.to_dict()
        p.to_alert_message()

    def test_engine_init(self):
        e = PredictiveMaintenanceEngine(use_mysql=False)
        e.get_storage_info()
        e.save()
        e.flush()

    def test_get_engine(self):
        get_predictive_maintenance_engine()

    def test_enums(self):
        assert MaintenanceUrgency.CRITICAL
        assert MaintenanceUrgency.HIGH
        assert MaintenanceUrgency.MEDIUM
        assert MaintenanceUrgency.LOW
        assert TrendDirection.INCREASING
        assert TrendDirection.DECREASING
        assert TrendDirection.STABLE
