"""
Tests for Days-to-Failure Prediction System (v5.7.9)

Tests cover:
1. calculate_days_to_failure function
2. predict_maintenance_timing function
3. Maintenance prediction alerts
4. Fleet dashboard endpoint
"""

import pytest
import sys
import os
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the functions to test
from mpg_engine import (
    calculate_days_to_failure,
    predict_maintenance_timing,
)


class TestCalculateDaysToFailure:
    """Tests for calculate_days_to_failure function"""

    def test_approaching_upper_threshold(self):
        """Test prediction when approaching upper threshold"""
        # Current: 70, Threshold: 100, Slope: +5/day → 6 days
        result = calculate_days_to_failure(
            current_value=70.0,
            threshold=100.0,
            trend_slope_per_day=5.0,
        )
        assert result == 6.0

    def test_approaching_lower_threshold(self):
        """Test prediction when approaching lower threshold (decreasing)"""
        # Current: 70, Threshold: 50, Slope: -5/day → 4 days
        result = calculate_days_to_failure(
            current_value=70.0,
            threshold=50.0,
            trend_slope_per_day=-5.0,
        )
        assert result == 4.0

    def test_moving_away_from_threshold(self):
        """Test returns None when moving away from threshold"""
        # Current: 70, Threshold: 100, Slope: -5/day → moving away
        result = calculate_days_to_failure(
            current_value=70.0,
            threshold=100.0,
            trend_slope_per_day=-5.0,
        )
        assert result is None

    def test_near_zero_slope(self):
        """Test returns None when slope is near zero"""
        result = calculate_days_to_failure(
            current_value=70.0,
            threshold=100.0,
            trend_slope_per_day=0.0001,
        )
        assert result is None

    def test_already_at_threshold(self):
        """Test returns min_days when already at threshold"""
        result = calculate_days_to_failure(
            current_value=100.0,
            threshold=100.0,
            trend_slope_per_day=5.0,
            min_days=0.5,
        )
        assert result == 0.5

    def test_min_days_clamp(self):
        """Test that result is clamped to min_days"""
        # Very close to threshold → would be < 0.5 days
        result = calculate_days_to_failure(
            current_value=99.9,
            threshold=100.0,
            trend_slope_per_day=10.0,
            min_days=0.5,
        )
        assert result == 0.5

    def test_max_days_clamp(self):
        """Test that result is clamped to max_days"""
        # Very slow trend → would be > 365 days
        result = calculate_days_to_failure(
            current_value=70.0,
            threshold=100.0,
            trend_slope_per_day=0.01,
            max_days=365.0,
        )
        assert result == 365.0

    def test_decreasing_toward_lower_threshold(self):
        """Test voltage dropping toward critical low"""
        # Voltage: 12.5V, Critical: 11.5V, Dropping 0.1V/day → 10 days
        result = calculate_days_to_failure(
            current_value=12.5,
            threshold=11.5,
            trend_slope_per_day=-0.1,
        )
        assert result == 10.0


class TestPredictMaintenanceTiming:
    """Tests for predict_maintenance_timing function"""

    def test_insufficient_data(self):
        """Test with less than 3 data points"""
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=12.5,
            history=[12.5, 12.4],  # Only 2 points
            warning_threshold=12.0,
            critical_threshold=11.5,
            is_higher_worse=False,
        )
        assert result["urgency"] == "UNKNOWN"
        assert "Insufficient data" in result["recommendation"]

    def test_degrading_trend_higher_worse(self):
        """Test degrading trend for temperature (higher is worse)"""
        # Temperature increasing toward threshold
        history = [195.0, 197.0, 199.0, 201.0, 203.0]
        result = predict_maintenance_timing(
            sensor_name="coolant_temp_f",
            current_value=205.0,
            history=history,
            warning_threshold=210.0,
            critical_threshold=230.0,
            is_higher_worse=True,
        )
        assert result["trend_direction"] == "DEGRADING"
        assert result["trend_slope_per_day"] > 0

    def test_degrading_trend_lower_worse(self):
        """Test degrading trend for voltage (lower is worse)"""
        # Voltage decreasing toward threshold
        history = [13.0, 12.8, 12.6, 12.4, 12.2]
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=12.0,
            history=history,
            warning_threshold=12.0,
            critical_threshold=11.5,
            is_higher_worse=False,
        )
        assert result["trend_direction"] == "DEGRADING"
        assert result["trend_slope_per_day"] < 0

    def test_stable_trend(self):
        """Test stable trend detection"""
        # Voltage stable around 13.0V
        history = [13.0, 13.01, 12.99, 13.0, 13.01]
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=13.0,
            history=history,
            warning_threshold=12.0,
            critical_threshold=11.5,
            is_higher_worse=False,
        )
        assert result["trend_direction"] == "STABLE"

    def test_improving_trend(self):
        """Test improving trend detection"""
        # Temperature decreasing (improving)
        history = [210.0, 207.0, 204.0, 201.0, 198.0]
        result = predict_maintenance_timing(
            sensor_name="coolant_temp_f",
            current_value=195.0,
            history=history,
            warning_threshold=210.0,
            critical_threshold=230.0,
            is_higher_worse=True,
        )
        assert result["trend_direction"] == "IMPROVING"
        assert result["urgency"] == "NONE"

    def test_critical_urgency(self):
        """Test CRITICAL urgency when days_to_critical < 7"""
        # Fast degradation toward critical
        history = [12.5, 12.3, 12.1, 11.9, 11.7]  # Dropping 0.2V/day
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=11.6,
            history=history,
            warning_threshold=12.0,
            critical_threshold=11.5,
            is_higher_worse=False,
        )
        # 0.1V to go / 0.2V per day = 0.5 days
        assert result["urgency"] == "CRITICAL"
        assert result["days_to_critical"] is not None
        assert result["days_to_critical"] < 7

    def test_high_urgency(self):
        """Test HIGH urgency when days_to_warning < 7"""
        # Moderate degradation
        history = [12.8, 12.7, 12.6, 12.5, 12.4]  # Dropping 0.1V/day
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=12.3,
            history=history,
            warning_threshold=12.0,
            critical_threshold=11.5,
            is_higher_worse=False,
        )
        # 0.3V to warning / 0.1V per day = 3 days to warning
        assert result["urgency"] in ["HIGH", "CRITICAL"]

    def test_result_contains_all_fields(self):
        """Test that result contains all expected fields"""
        history = [12.5, 12.4, 12.3, 12.2, 12.1]
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=12.0,
            history=history,
            warning_threshold=12.0,
            critical_threshold=11.5,
            is_higher_worse=False,
        )

        expected_fields = [
            "sensor",
            "current_value",
            "warning_threshold",
            "critical_threshold",
            "trend_slope_per_day",
            "trend_direction",
            "days_to_warning",
            "days_to_critical",
            "urgency",
            "recommendation",
        ]
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"


class TestMaintenancePredictionAlert:
    """Tests for maintenance prediction alerts"""

    def test_alert_type_exists(self):
        """Test that MAINTENANCE_PREDICTION alert type exists"""
        from alert_service import AlertType

        assert hasattr(AlertType, "MAINTENANCE_PREDICTION")
        assert AlertType.MAINTENANCE_PREDICTION.value == "maintenance_prediction"

    def test_alert_manager_has_method(self):
        """Test that AlertManager has alert_maintenance_prediction method"""
        from alert_service import AlertManager

        manager = AlertManager()
        assert hasattr(manager, "alert_maintenance_prediction")
        assert callable(getattr(manager, "alert_maintenance_prediction"))

    def test_send_function_exists(self):
        """Test that convenience function exists"""
        from alert_service import send_maintenance_prediction_alert

        assert callable(send_maintenance_prediction_alert)

    @patch("alert_service.AlertManager.send_alert")
    def test_critical_alert_uses_sms(self, mock_send):
        """Test that CRITICAL alerts use SMS channel"""
        from alert_service import AlertManager

        mock_send.return_value = True
        manager = AlertManager()

        manager.alert_maintenance_prediction(
            truck_id="TEST123",
            sensor="battery_voltage",
            current_value=11.6,
            threshold=11.5,
            days_to_failure=2.0,
            urgency="CRITICAL",
            unit="V",
        )

        # Verify SMS is included in channels
        mock_send.assert_called_once()
        call_args = mock_send.call_args
        # Check kwargs first, then positional args
        if call_args.kwargs and "channels" in call_args.kwargs:
            channels = call_args.kwargs["channels"]
        else:
            # channels is passed as second positional arg
            channels = call_args[1].get("channels", []) if call_args[1] else []
        assert "sms" in channels

    @patch("alert_service.AlertManager.send_alert")
    def test_high_alert_uses_email_only(self, mock_send):
        """Test that HIGH alerts use email only"""
        from alert_service import AlertManager

        mock_send.return_value = True
        manager = AlertManager()

        manager.alert_maintenance_prediction(
            truck_id="TEST123",
            sensor="coolant_temp_f",
            current_value=220.0,
            threshold=230.0,
            days_to_failure=5.0,
            urgency="HIGH",
            unit="°F",
        )

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        if call_args.kwargs and "channels" in call_args.kwargs:
            channels = call_args.kwargs["channels"]
        else:
            channels = call_args[1].get("channels", []) if call_args[1] else []
        assert "email" in channels
        assert "sms" not in channels


class TestSensorThresholds:
    """Tests for sensor threshold configuration"""

    def test_all_sensors_have_required_fields(self):
        """Test that all sensor configs have required fields"""
        from routers.sensor_health_router import SENSOR_THRESHOLDS

        required_fields = ["warning", "critical", "is_higher_worse", "unit"]

        for sensor, config in SENSOR_THRESHOLDS.items():
            for field in required_fields:
                assert (
                    field in config
                ), f"Sensor {sensor} missing field: {field}"

    def test_voltage_thresholds_are_logical(self):
        """Test that voltage thresholds make sense"""
        from routers.sensor_health_router import SENSOR_THRESHOLDS

        voltage = SENSOR_THRESHOLDS["battery_voltage"]
        # Lower voltage is worse, so critical < warning
        assert voltage["critical"] < voltage["warning"]
        assert voltage["is_higher_worse"] is False

    def test_temperature_thresholds_are_logical(self):
        """Test that temperature thresholds make sense"""
        from routers.sensor_health_router import SENSOR_THRESHOLDS

        temp = SENSOR_THRESHOLDS["coolant_temp_f"]
        # Higher temp is worse, so critical > warning
        assert temp["critical"] > temp["warning"]
        assert temp["is_higher_worse"] is True

    def test_oil_pressure_thresholds(self):
        """Test that oil pressure thresholds make sense"""
        from routers.sensor_health_router import SENSOR_THRESHOLDS

        oil = SENSOR_THRESHOLDS["oil_pressure_psi"]
        # Lower pressure is worse
        assert oil["critical"] < oil["warning"]
        assert oil["is_higher_worse"] is False

    def test_def_level_thresholds(self):
        """Test that DEF level thresholds make sense"""
        from routers.sensor_health_router import SENSOR_THRESHOLDS

        def_level = SENSOR_THRESHOLDS["def_level_pct"]
        # Lower DEF is worse
        assert def_level["critical"] < def_level["warning"]
        assert def_level["is_higher_worse"] is False

    def test_dpf_soot_thresholds(self):
        """Test that DPF soot thresholds make sense"""
        from routers.sensor_health_router import SENSOR_THRESHOLDS

        dpf = SENSOR_THRESHOLDS["dpf_soot_pct"]
        # Higher soot is worse
        assert dpf["critical"] > dpf["warning"]
        assert dpf["is_higher_worse"] is True


class TestFleetMaintenanceDashboardModels:
    """Tests for Pydantic models"""

    def test_maintenance_prediction_model(self):
        """Test MaintenancePrediction model validation"""
        from routers.sensor_health_router import MaintenancePrediction

        pred = MaintenancePrediction(
            sensor="battery_voltage",
            current_value=12.5,
            warning_threshold=12.0,
            critical_threshold=11.5,
            trend_direction="STABLE",
            days_to_warning=None,
            days_to_critical=None,
            urgency="NONE",
            recommendation="Stable condition",
        )
        assert pred.sensor == "battery_voltage"
        assert pred.urgency == "NONE"
        assert pred.current_value == 12.5

    def test_truck_maintenance_forecast_model(self):
        """Test TruckMaintenanceForecast model validation"""
        from routers.sensor_health_router import (
            TruckMaintenanceForecast,
            MaintenancePrediction,
        )

        forecast = TruckMaintenanceForecast(
            truck_id="TEST123",
            overall_urgency="LOW",
            predictions=[
                MaintenancePrediction(
                    sensor="battery_voltage",
                    current_value=12.5,
                    warning_threshold=12.0,
                    critical_threshold=11.5,
                    trend_direction="STABLE",
                    urgency="NONE",
                    recommendation="OK",
                )
            ],
            needs_attention=False,
            last_updated="2025-12-14T12:00:00Z",
        )
        assert forecast.truck_id == "TEST123"
        assert len(forecast.predictions) == 1
        assert forecast.needs_attention is False

    def test_fleet_maintenance_dashboard_model(self):
        """Test FleetMaintenanceDashboard model validation"""
        from routers.sensor_health_router import FleetMaintenanceDashboard

        dashboard = FleetMaintenanceDashboard(
            total_trucks=10,
            trucks_needing_attention=2,
            critical_count=1,
            high_count=1,
            medium_count=0,
            forecasts=[],
            summary_by_sensor={
                "battery_voltage": {"critical": 1, "high": 0}
            },
            last_updated="2025-12-14T12:00:00Z",
        )
        assert dashboard.total_trucks == 10
        assert dashboard.critical_count == 1


# Integration test with mock database
class TestDaysToFailureEndpoint:
    """Integration tests for days-to-failure endpoints"""

    def test_prediction_with_stable_trend(self):
        """Test prediction returns STABLE for flat data"""
        # Stable voltage around 13.0V - perfectly flat
        history = [13.0, 13.0, 13.0, 13.0, 13.0, 13.0, 13.0]
        
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=13.0,
            history=history,
            warning_threshold=12.0,
            critical_threshold=11.5,
            is_higher_worse=False,
        )
        
        assert result["trend_direction"] == "STABLE"
        assert result["urgency"] == "NONE"
        # Stable trend may still show max days (365) or None
        # The key is that urgency is NONE

    def test_prediction_with_degrading_trend(self):
        """Test prediction returns DEGRADING for declining data"""
        # Voltage steadily dropping
        history = [13.5, 13.3, 13.1, 12.9, 12.7, 12.5, 12.3]
        
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=12.1,
            history=history,
            warning_threshold=12.0,
            critical_threshold=11.5,
            is_higher_worse=False,
        )
        
        assert result["trend_direction"] == "DEGRADING"
        # Should have calculated days to thresholds
        assert result["days_to_warning"] is not None or result["days_to_critical"] is not None

    def test_prediction_urgency_levels(self):
        """Test that urgency is correctly assigned based on days to failure"""
        # Fast drop in voltage: ~ -0.2V/day
        history = [12.5, 12.3, 12.1, 11.9, 11.7]
        
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=11.6,  # Very close to critical (11.5)
            history=history,
            warning_threshold=12.0,
            critical_threshold=11.5,
            is_higher_worse=False,
        )
        
        # Should be CRITICAL since close to threshold
        assert result["urgency"] in ["CRITICAL", "HIGH"]
        assert "maintenance" in result["recommendation"].lower()

    def test_prediction_temperature_higher_worse(self):
        """Test that temperature prediction works (higher is worse)"""
        # Temperature rising
        history = [195, 198, 201, 204, 207]
        
        result = predict_maintenance_timing(
            sensor_name="coolant_temp_f",
            current_value=210,
            history=history,
            warning_threshold=210,
            critical_threshold=230,
            is_higher_worse=True,
        )
        
        assert result["trend_direction"] == "DEGRADING"
        assert result["trend_slope_per_day"] > 0

    def test_integration_alert_and_prediction(self):
        """Test that alert type and prediction work together"""
        from alert_service import AlertType
        
        # Verify alert type exists
        assert AlertType.MAINTENANCE_PREDICTION is not None
        
        # Run a prediction that would trigger alert
        history = [12.2, 12.0, 11.8, 11.6, 11.55]
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=11.55,
            history=history,
            warning_threshold=12.0,
            critical_threshold=11.5,
            is_higher_worse=False,
        )
        
        # This should be critical
        assert result["urgency"] in ["CRITICAL", "HIGH"]
        assert result["days_to_critical"] is not None
        assert result["days_to_critical"] < 7  # Would trigger alert
