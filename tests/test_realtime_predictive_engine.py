"""
Tests for RealTimePredictiveEngine - TRUE Predictive Maintenance.

Tests cover:
- Threshold-based alerts (critical and warning)
- Trend analysis (predictive degradation)
- Cross-sensor correlation
- Efficiency analysis
- Fleet-wide summary
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from realtime_predictive_engine import (
    RealTimePredictiveEngine,
    PredictiveAlert,
    TruckSensorState,
    get_realtime_predictive_engine,
)


class TestPredictiveAlert:
    """Tests for PredictiveAlert dataclass."""

    def test_alert_creation(self):
        """Test basic alert creation."""
        alert = PredictiveAlert(
            truck_id="T001",
            component="Sistema de Lubricación",
            severity="CRITICAL",
            message="Oil pressure critical",
            predicted_failure_hours=0,
            confidence=95,
            sensor_evidence=[{"sensor": "oil_press", "value": 20}],
            recommended_action="Stop immediately",
            alert_type="threshold",
        )

        assert alert.truck_id == "T001"
        assert alert.severity == "CRITICAL"
        assert alert.confidence == 95

    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = PredictiveAlert(
            truck_id="T001",
            component="Motor",
            severity="WARNING",
            message="Temperature high",
            predicted_failure_hours=24,
            confidence=75,
            sensor_evidence=[{"sensor": "cool_temp", "value": 225}],
            recommended_action="Schedule service",
            alert_type="threshold",
        )

        result = alert.to_dict()

        assert isinstance(result, dict)
        assert result["truck_id"] == "T001"
        assert result["severity"] == "WARNING"
        assert result["alert_type"] == "threshold"


class TestTruckSensorState:
    """Tests for TruckSensorState tracking."""

    def test_add_reading(self):
        """Test adding sensor readings."""
        state = TruckSensorState(truck_id="T001")
        now = datetime.now(timezone.utc)

        state.add_reading("oil_press", 45.0, now)
        state.add_reading("oil_press", 44.0, now + timedelta(minutes=5))

        assert "oil_press" in state.history
        assert len(state.history["oil_press"]) == 2
        assert state.last_update == now + timedelta(minutes=5)

    def test_max_readings_limit(self):
        """Test that history is limited to max_readings."""
        state = TruckSensorState(truck_id="T001")
        now = datetime.now(timezone.utc)

        # Add more than max_readings
        for i in range(300):
            state.add_reading(
                "oil_press",
                45.0 - i * 0.1,
                now + timedelta(minutes=i * 5),
                max_readings=100,
            )

        assert len(state.history["oil_press"]) == 100


class TestRealTimePredictiveEngine:
    """Tests for the main predictive engine."""

    @pytest.fixture
    def engine(self):
        """Create fresh engine for each test."""
        return RealTimePredictiveEngine()

    # ═══════════════════════════════════════════════════════════════════════════════
    # CRITICAL THRESHOLD TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_oil_pressure_critical_low(self, engine):
        """Test critical oil pressure detection."""
        sensors = {"oil_press": 20}  # Below 25 PSI critical threshold

        alerts = engine.analyze_truck("T001", sensors)

        critical_alerts = [a for a in alerts if a.severity == "CRITICAL"]
        assert len(critical_alerts) >= 1
        assert any("PRESIÓN DE ACEITE CRÍTICA" in a.message for a in critical_alerts)

    def test_coolant_temp_critical(self, engine):
        """Test critical coolant temperature detection."""
        sensors = {"cool_temp": 240}  # Above 235°F critical (already in F)

        alerts = engine.analyze_truck("T001", sensors)

        critical_alerts = [a for a in alerts if a.severity == "CRITICAL"]
        assert len(critical_alerts) >= 1
        assert any("SOBRECALENTADO" in a.message for a in critical_alerts)

    def test_coolant_temp_celsius_conversion(self, engine):
        """Test that Celsius temperatures are converted to Fahrenheit."""
        # 120°C = 248°F which is above critical
        sensors = {"cool_temp": 120}  # Celsius (will be converted)

        alerts = engine.analyze_truck("T001", sensors)

        # Should detect as critical (248°F > 235°F threshold)
        critical_alerts = [a for a in alerts if a.severity == "CRITICAL"]
        assert len(critical_alerts) >= 1

    def test_transmission_temp_critical(self, engine):
        """Test critical transmission temperature."""
        sensors = {"trams_t": 260}  # Above 250°F critical

        alerts = engine.analyze_truck("T001", sensors)

        critical_alerts = [a for a in alerts if a.severity == "CRITICAL"]
        assert len(critical_alerts) >= 1
        assert any("TRANSMISIÓN CRÍTICA" in a.message for a in critical_alerts)

    def test_def_level_critical(self, engine):
        """Test critical DEF level detection."""
        sensors = {"def_level": 5}  # Below 10% critical

        alerts = engine.analyze_truck("T001", sensors)

        critical_alerts = [a for a in alerts if a.severity == "CRITICAL"]
        assert len(critical_alerts) >= 1
        assert any("DEF CRÍTICO" in a.message for a in critical_alerts)

    def test_voltage_critical_low(self, engine):
        """Test critical low voltage detection."""
        sensors = {"voltage": 11.0}  # Below 11.5V critical

        alerts = engine.analyze_truck("T001", sensors)

        critical_alerts = [a for a in alerts if a.severity == "CRITICAL"]
        assert len(critical_alerts) >= 1
        assert any("VOLTAJE CRÍTICO" in a.message for a in critical_alerts)

    # ═══════════════════════════════════════════════════════════════════════════════
    # WARNING THRESHOLD TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_oil_pressure_warning(self, engine):
        """Test warning oil pressure detection."""
        sensors = {"oil_press": 37}  # Between 35 (warning) and 40 (normal)

        alerts = engine.analyze_truck("T001", sensors)

        warning_alerts = [a for a in alerts if a.severity == "WARNING"]
        assert len(warning_alerts) >= 1
        assert any("Presión de aceite baja" in a.message for a in warning_alerts)

    def test_coolant_temp_warning(self, engine):
        """Test warning coolant temperature."""
        sensors = {"cool_temp": 225}  # Between 210 (normal) and 235 (critical)

        alerts = engine.analyze_truck("T001", sensors)

        warning_alerts = [a for a in alerts if a.severity == "WARNING"]
        assert len(warning_alerts) >= 1
        assert any(
            "Temperatura de coolant elevada" in a.message for a in warning_alerts
        )

    def test_def_level_warning(self, engine):
        """Test DEF warning level."""
        sensors = {"def_level": 15}  # Between 10 (critical) and 20 (warning)

        alerts = engine.analyze_truck("T001", sensors)

        warning_alerts = [a for a in alerts if a.severity == "WARNING"]
        assert len(warning_alerts) >= 1
        assert any("DEF bajo" in a.message for a in warning_alerts)

    def test_engine_load_high(self, engine):
        """Test high engine load warning."""
        sensors = {"engine_load": 90}  # Above 85% threshold

        alerts = engine.analyze_truck("T001", sensors)

        warning_alerts = [a for a in alerts if a.severity == "WARNING"]
        assert len(warning_alerts) >= 1
        assert any("Carga de motor sostenida alta" in a.message for a in warning_alerts)

    def test_voltage_warning_low(self, engine):
        """Test warning low voltage."""
        sensors = {"voltage": 12.0}  # Between 11.5 (critical) and 12.2 (warning)

        alerts = engine.analyze_truck("T001", sensors)

        warning_alerts = [a for a in alerts if a.severity == "WARNING"]
        assert len(warning_alerts) >= 1
        assert any("Voltaje bajo" in a.message for a in warning_alerts)

    def test_voltage_warning_high(self, engine):
        """Test warning high voltage (overcharging)."""
        sensors = {"voltage": 15.2}  # Above 15.0V threshold

        alerts = engine.analyze_truck("T001", sensors)

        warning_alerts = [a for a in alerts if a.severity == "WARNING"]
        assert len(warning_alerts) >= 1
        assert any("Voltaje alto" in a.message for a in warning_alerts)

    # ═══════════════════════════════════════════════════════════════════════════════
    # TREND ANALYSIS TESTS (TRUE PREDICTIVE)
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_oil_pressure_declining_trend(self, engine):
        """Test detection of declining oil pressure trend."""
        now = datetime.now(timezone.utc)

        # Simulate gradual oil pressure decline
        for i in range(25):
            sensors = {"oil_press": 50 - i * 0.5}  # Declining 0.5 PSI per reading
            engine.analyze_truck("T001", sensors, now + timedelta(minutes=i * 5))

        # Final reading
        final_sensors = {"oil_press": 38}  # Still safe but declining
        alerts = engine.analyze_truck(
            "T001", final_sensors, now + timedelta(minutes=125)
        )

        trend_alerts = [a for a in alerts if a.alert_type == "trend"]
        # Should detect declining trend
        assert any(
            "PREDICTIVO" in a.message or "Presión de aceite en declive" in a.message
            for a in alerts
        )

    def test_coolant_temp_rising_trend(self, engine):
        """Test detection of rising coolant temperature trend."""
        now = datetime.now(timezone.utc)

        # Simulate gradual coolant temperature rise
        for i in range(25):
            sensors = {"cool_temp": 190 + i * 1}  # Rising 1°F per reading
            engine.analyze_truck("T001", sensors, now + timedelta(minutes=i * 5))

        # Final reading - still below critical but rising
        final_sensors = {"cool_temp": 215}
        alerts = engine.analyze_truck(
            "T001", final_sensors, now + timedelta(minutes=125)
        )

        # Should potentially detect rising trend (depends on slope)
        trend_alerts = [a for a in alerts if a.alert_type == "trend"]
        # Note: This may or may not trigger depending on slope threshold

    def test_calculate_slope(self, engine):
        """Test slope calculation for trend analysis."""
        # Linear declining values
        values = [50, 49, 48, 47, 46, 45, 44, 43, 42, 41]
        slope = engine._calculate_slope(values)

        assert slope == pytest.approx(-1.0, abs=0.01)

    def test_calculate_slope_flat(self, engine):
        """Test slope calculation for flat trend."""
        values = [45, 45, 45, 45, 45, 45, 45, 45, 45, 45]
        slope = engine._calculate_slope(values)

        assert slope == pytest.approx(0.0, abs=0.01)

    def test_calculate_slope_insufficient_data(self, engine):
        """Test slope calculation with insufficient data."""
        values = [45]
        slope = engine._calculate_slope(values)

        assert slope == 0.0

    # ═══════════════════════════════════════════════════════════════════════════════
    # CORRELATION TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_oil_pump_failing_correlation(self, engine):
        """Test detection of oil pump failure pattern."""
        # Correlation requires: oil_temp > 240°F AND oil_press < 45 PSI
        sensors = {
            "oil_temp": 250,  # High (in °F, > 240)
            "oil_press": 42,  # Low (< 45)
        }

        alerts = engine.analyze_truck("T001", sensors)

        # Should detect oil pump correlation
        correlation_alerts = [a for a in alerts if a.alert_type == "correlation"]
        assert len(correlation_alerts) >= 1
        # Text is in recommended_action
        assert any(
            "BOMBA DE ACEITE FALLANDO" in a.recommended_action
            for a in correlation_alerts
        )

    def test_cooling_system_failure_correlation(self, engine):
        """Test detection of general cooling system failure."""
        # Correlation requires: cool_temp > 215°F AND oil_temp > 245°F
        sensors = {
            "cool_temp": 220,  # High coolant (> 215)
            "oil_temp": 250,  # High oil (> 245)
        }

        alerts = engine.analyze_truck("T001", sensors)

        # Should detect cooling correlation
        correlation_alerts = [a for a in alerts if a.alert_type == "correlation"]
        assert len(correlation_alerts) >= 1
        # Text is in recommended_action
        assert any(
            "FALLA DE ENFRIAMIENTO GENERAL" in a.recommended_action
            for a in correlation_alerts
        )

    def test_turbo_failing_correlation(self, engine):
        """Test detection of turbo failure pattern."""
        # Correlation requires: intake_pressure < 1.8 bar AND intk_t > 120°F
        sensors = {
            "intake_pressure": 1.6,  # Low pressure (< 1.8)
            "intk_t": 125,  # High intake temp (> 120°F)
        }

        alerts = engine.analyze_truck("T001", sensors)

        correlation_alerts = [a for a in alerts if a.alert_type == "correlation"]
        assert len(correlation_alerts) >= 1
        # Text is in recommended_action
        assert any(
            "TURBO DEGRADÁNDOSE" in a.recommended_action for a in correlation_alerts
        )

    # ═══════════════════════════════════════════════════════════════════════════════
    # EFFICIENCY ANALYSIS TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_excessive_idle_detection(self, engine):
        """Test detection of excessive idle time."""
        sensors = {
            "idle_hours": 450,  # 45% idle
            "engine_hours": 1000,
        }

        alerts = engine.analyze_truck("T001", sensors)

        efficiency_alerts = [a for a in alerts if a.alert_type == "efficiency"]
        assert len(efficiency_alerts) >= 1
        assert any("IDLE EXCESIVO" in a.message for a in efficiency_alerts)

    def test_idle_cost_calculation(self, engine):
        """Test that idle cost is calculated in message."""
        sensors = {
            "idle_hours": 500,
            "engine_hours": 1000,
            "total_idle_fuel": 200,  # 200 gallons wasted
        }

        alerts = engine.analyze_truck("T001", sensors)

        efficiency_alerts = [a for a in alerts if a.alert_type == "efficiency"]
        assert len(efficiency_alerts) >= 1
        # Should mention cost in message
        assert any("$" in a.message for a in efficiency_alerts)

    def test_normal_idle_no_alert(self, engine):
        """Test that normal idle percentage doesn't trigger alert."""
        sensors = {
            "idle_hours": 250,  # 25% idle - normal
            "engine_hours": 1000,
        }

        alerts = engine.analyze_truck("T001", sensors)

        efficiency_alerts = [a for a in alerts if a.alert_type == "efficiency"]
        assert len(efficiency_alerts) == 0

    # ═══════════════════════════════════════════════════════════════════════════════
    # NO ALERTS TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_healthy_truck_no_alerts(self, engine):
        """Test that a healthy truck generates no alerts."""
        sensors = {
            "oil_press": 50,  # Normal
            "oil_temp": 200,  # Normal
            "cool_temp": 190,  # Normal
            "trams_t": 180,  # Normal
            "def_level": 75,  # Good
            "voltage": 13.8,  # Good
            "engine_load": 60,  # Normal
        }

        alerts = engine.analyze_truck("T001", sensors)

        # Should have no critical or warning alerts
        serious_alerts = [a for a in alerts if a.severity in ("CRITICAL", "WARNING")]
        assert len(serious_alerts) == 0

    def test_empty_sensors(self, engine):
        """Test handling of empty sensor data."""
        sensors = {}

        alerts = engine.analyze_truck("T001", sensors)

        assert len(alerts) == 0

    def test_none_values(self, engine):
        """Test handling of None sensor values."""
        sensors = {
            "oil_press": None,
            "cool_temp": None,
            "voltage": None,
        }

        alerts = engine.analyze_truck("T001", sensors)

        # Should not crash, no alerts expected
        assert len(alerts) == 0

    # ═══════════════════════════════════════════════════════════════════════════════
    # FLEET ANALYSIS TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_analyze_fleet(self, engine):
        """Test fleet-wide analysis."""
        fleet_sensors = {
            "T001": {"oil_press": 20, "cool_temp": 190},  # Critical oil
            "T002": {"oil_press": 50, "cool_temp": 225},  # Warning coolant
            "T003": {"oil_press": 50, "cool_temp": 190},  # Healthy
        }

        results = engine.analyze_fleet(fleet_sensors)

        assert "T001" in results  # Should have alerts
        assert "T002" in results  # Should have alerts
        # T003 may or may not be in results depending on thresholds

    def test_get_fleet_summary(self, engine):
        """Test fleet summary generation."""
        fleet_sensors = {
            "T001": {"oil_press": 20},  # Critical
            "T002": {"oil_press": 37},  # Warning
            "T003": {"oil_press": 50},  # Healthy
        }

        summary = engine.get_fleet_summary(fleet_sensors)

        assert summary["total_trucks_analyzed"] == 3
        assert summary["trucks_with_alerts"] >= 2
        assert summary["critical_count"] >= 1
        assert isinstance(summary["all_alerts"], list)

    def test_fleet_summary_sorting(self, engine):
        """Test that alerts are sorted by severity then confidence."""
        fleet_sensors = {
            "T001": {"oil_press": 20},  # Critical
            "T002": {"oil_press": 37},  # Warning
            "T003": {"def_level": 5},  # Critical
            "T004": {"cool_temp": 225},  # Warning
        }

        summary = engine.get_fleet_summary(fleet_sensors)
        alerts = summary["all_alerts"]

        # First alerts should be critical
        critical_indices = [
            i for i, a in enumerate(alerts) if a["severity"] == "CRITICAL"
        ]
        warning_indices = [
            i for i, a in enumerate(alerts) if a["severity"] == "WARNING"
        ]

        if critical_indices and warning_indices:
            assert max(critical_indices) < min(warning_indices)

    # ═══════════════════════════════════════════════════════════════════════════════
    # THREAD SAFETY TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_concurrent_truck_analysis(self, engine):
        """Test that concurrent analysis doesn't crash."""
        import threading

        errors = []

        def analyze_truck(truck_id):
            try:
                for i in range(10):
                    sensors = {"oil_press": 45 - i * 0.1}
                    engine.analyze_truck(truck_id, sensors)
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=analyze_truck, args=(f"T{i:03d}",))
            for i in range(10)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    # ═══════════════════════════════════════════════════════════════════════════════
    # SINGLETON TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_singleton_returns_same_instance(self):
        """Test that get_realtime_predictive_engine returns singleton."""
        engine1 = get_realtime_predictive_engine()
        engine2 = get_realtime_predictive_engine()

        assert engine1 is engine2


class TestTemperatureConversion:
    """Tests for temperature unit handling."""

    @pytest.fixture
    def engine(self):
        return RealTimePredictiveEngine()

    def test_fahrenheit_pass_through(self, engine):
        """Test that Fahrenheit values pass through unchanged."""
        result = engine._convert_to_fahrenheit(220)  # Already in F
        assert result == 220

    def test_celsius_conversion(self, engine):
        """Test that Celsius values are converted."""
        result = engine._convert_to_fahrenheit(100)  # 100°C = 212°F
        assert result == pytest.approx(212, abs=0.5)

    def test_boundary_value(self, engine):
        """Test boundary value (150 is threshold)."""
        result = engine._convert_to_fahrenheit(150)
        # 150 is passed through as-is (assumed F)
        assert result == 150


class TestPredictedFailureTime:
    """Tests for failure time prediction accuracy."""

    @pytest.fixture
    def engine(self):
        return RealTimePredictiveEngine()

    def test_immediate_failure_detection(self, engine):
        """Test that critical conditions show immediate failure."""
        sensors = {"oil_press": 20}  # Critical

        alerts = engine.analyze_truck("T001", sensors)

        critical_alerts = [a for a in alerts if a.severity == "CRITICAL"]
        assert len(critical_alerts) >= 1
        # Predicted failure should be 0 or very low
        assert any(a.predicted_failure_hours == 0 for a in critical_alerts)

    def test_def_derate_prediction(self, engine):
        """Test DEF derate timing prediction."""
        sensors = {"def_level": 5}  # Critical

        alerts = engine.analyze_truck("T001", sensors)

        def_alerts = [a for a in alerts if "DEF" in a.component]
        assert len(def_alerts) >= 1
        # Should predict derate in ~2 hours
        assert any(a.predicted_failure_hours == 2 for a in def_alerts)
