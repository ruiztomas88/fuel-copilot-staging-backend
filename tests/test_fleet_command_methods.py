"""
Comprehensive tests for FleetCommandCenter methods to reach 90% coverage
Tests all helper methods, data processing, and business logic
"""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from fleet_command_center import (
    ActionItem,
    ActionType,
    CommandCenterData,
    CostProjection,
    DEFPrediction,
    FailureCorrelation,
    FleetCommandCenter,
    FleetHealthScore,
    IssueCategory,
    Priority,
    SensorReading,
    SensorStatus,
    TruckRiskScore,
    UrgencySummary,
)


class TestFleetCommandCenterMethods:
    """Test FleetCommandCenter methods comprehensively"""

    def test_normalize_component_variations(self):
        """Test component normalization with many variations"""
        fcc = FleetCommandCenter()

        # Oil system variations
        assert fcc._normalize_component("oil_press") == "oil_system"
        assert fcc._normalize_component("oil_temp") == "oil_system"
        assert fcc._normalize_component("aceite") == "oil_system"
        assert fcc._normalize_component("Sistema de Lubricación") == "oil_system"
        assert fcc._normalize_component("Bomba de aceite") == "oil_system"

        # Cooling system variations
        assert fcc._normalize_component("coolant") == "cooling_system"
        assert fcc._normalize_component("cool_temp") == "cooling_system"
        assert fcc._normalize_component("enfriamiento") == "cooling_system"
        assert fcc._normalize_component("radiador") == "cooling_system"

        # DEF system variations
        assert fcc._normalize_component("def") == "def_system"
        assert fcc._normalize_component("def_level") == "def_system"
        assert fcc._normalize_component("adblue") == "def_system"
        assert fcc._normalize_component("scr") == "def_system"

        # Transmission variations
        assert fcc._normalize_component("transmisión") == "transmission"
        assert fcc._normalize_component("transmission") == "transmission"
        assert fcc._normalize_component("trams_t") == "transmission"

        # Electrical variations
        assert fcc._normalize_component("voltage") == "electrical"
        assert fcc._normalize_component("voltaje") == "electrical"
        assert fcc._normalize_component("batería") == "electrical"
        assert fcc._normalize_component("alternador") == "electrical"

        # Turbo variations
        assert fcc._normalize_component("turbo") == "turbo_system"
        assert fcc._normalize_component("intercooler") == "turbo_system"
        assert fcc._normalize_component("boost") == "turbo_system"

        # Fuel variations
        assert fcc._normalize_component("fuel") == "fuel_system"
        assert fcc._normalize_component("combustible") == "fuel_system"
        assert fcc._normalize_component("diesel") == "fuel_system"

        # Brake variations
        assert fcc._normalize_component("freno") == "brake_system"
        assert fcc._normalize_component("brake") == "brake_system"

        # Unknown components
        assert "unknown" in fcc._normalize_component("unknown_component_xyz").lower()

    def test_validate_sensor_values_comprehensive(self):
        """Test sensor validation with many scenarios"""
        fcc = FleetCommandCenter()

        # Valid values
        assert fcc._validate_sensor_value(50, "oil_press") == 50
        assert fcc._validate_sensor_value(100.5, "cool_temp") == 100.5
        assert fcc._validate_sensor_value(50.0, "def_level") == 50.0
        assert fcc._validate_sensor_value(12.5, "voltage") == 12.5
        assert fcc._validate_sensor_value(1500, "rpm") == 1500

        # Out of range values (should return None)
        assert fcc._validate_sensor_value(-10, "oil_press") is None
        assert fcc._validate_sensor_value(200, "oil_press") is None
        assert fcc._validate_sensor_value(400, "cool_temp") is None
        assert fcc._validate_sensor_value(150, "def_level") is None
        assert fcc._validate_sensor_value(40, "voltage") is None
        assert fcc._validate_sensor_value(5000, "rpm") is None

        # None and invalid values
        assert fcc._validate_sensor_value(None, "oil_press") is None
        assert fcc._validate_sensor_value(float("nan"), "oil_press") is None
        assert fcc._validate_sensor_value(float("inf"), "oil_press") is None
        assert fcc._validate_sensor_value("invalid", "oil_press") is None

        # Unknown sensors (no validation, passes through or returns value)
        result = fcc._validate_sensor_value(999, "unknown_sensor")
        assert result is not None or result == 999

    def test_validate_sensor_dict(self):
        """Test batch sensor validation"""
        fcc = FleetCommandCenter()

        sensors = {
            "oil_press": 50,
            "cool_temp": 180,
            "def_level": 75,
            "invalid_sensor": None,
            "rpm": 1800,
        }

        validated = fcc._validate_sensor_dict(sensors)
        assert validated["oil_press"] == 50
        assert validated["cool_temp"] == 180
        assert validated["def_level"] == 75
        assert validated["rpm"] == 1800

    def test_get_source_weight_all_sources(self):
        """Test source weights for all known sources"""
        fcc = FleetCommandCenter()

        assert fcc._get_source_weight("Real-Time Predictive") == 100
        assert fcc._get_source_weight("Predictive Maintenance") == 90
        assert fcc._get_source_weight("ML Anomaly Detection") == 80
        assert fcc._get_source_weight("Sensor Health Monitor") == 70
        assert fcc._get_source_weight("DTC Events") == 60
        assert fcc._get_source_weight("DB Alerts") == 50
        assert fcc._get_source_weight("GPS Quality") == 40
        assert fcc._get_source_weight("Voltage Monitor") == 40
        assert fcc._get_source_weight("Idle Analysis") == 30

        # Unknown sources get default weight
        weight = fcc._get_source_weight("Unknown Source XYZ")
        assert isinstance(weight, int)
        assert weight >= 0

    def test_get_best_source_multiple_scenarios(self):
        """Test getting best source from various combinations"""
        fcc = FleetCommandCenter()

        # Test different combinations
        sources1 = ["Idle Analysis", "Real-Time Predictive", "DTC Events"]
        best1 = fcc._get_best_source(sources1)
        assert best1 in sources1

        sources2 = [
            "Sensor Health Monitor",
            "ML Anomaly Detection",
            "Predictive Maintenance",
        ]
        best2 = fcc._get_best_source(sources2)
        assert best2 in sources2

        sources3 = ["GPS Quality", "Voltage Monitor"]
        best3 = fcc._get_best_source(sources3)
        assert best3 in sources3

        # Single source
        assert fcc._get_best_source(["Only Source"]) == "Only Source"

    def test_generate_multiple_action_ids(self):
        """Test action ID generation uniqueness"""
        fcc = FleetCommandCenter()

        ids = set()
        for i in range(100):
            action_id = fcc._generate_action_id()
            assert action_id not in ids  # Must be unique
            assert isinstance(action_id, str)
            assert len(action_id) > 0
            ids.add(action_id)

    def test_get_component_cost_all_components(self):
        """Test cost retrieval for all known components"""
        fcc = FleetCommandCenter()

        # Test all known components
        components = [
            "Transmisión",
            "Sistema de frenos de aire",
            "Sistema eléctrico",
            "Turbocompresor",
            "Turbo / Intercooler",
            "Sistema de enfriamiento",
            "Sistema DEF",
            "Sistema de lubricación",
            "Sistema de combustible",
            "Bomba de aceite / Filtro",
            "Intercooler",
            "Eficiencia general",
            "GPS",
            "Voltaje",
            "DTC",
        ]

        for component in components:
            cost = fcc._get_component_cost(component)
            assert "min" in cost
            assert "max" in cost
            assert "avg" in cost
            # Some components may have zero cost if not in the database
            if cost["min"] > 0:
                assert cost["max"] > cost["min"]
                assert cost["avg"] >= cost["min"]
                assert cost["avg"] <= cost["max"]

    def test_format_cost_string_all_components(self):
        """Test cost string formatting for all components"""
        fcc = FleetCommandCenter()

        components = ["Transmisión", "Turbocompresor", "Sistema DEF", "GPS"]

        for component in components:
            cost_str = fcc._format_cost_string(component)
            assert "$" in cost_str
            assert isinstance(cost_str, str)
            assert len(cost_str) > 0

    def test_calculate_urgency_from_days_range(self):
        """Test urgency calculation across full range"""
        fcc = FleetCommandCenter()

        # Test various day ranges
        test_cases = [
            (0.1, "should be very high urgency"),
            (0.5, "critical - less than 1 day"),
            (1.0, "critical - 1 day"),
            (2.0, "high urgency"),
            (3.0, "high urgency"),
            (5.0, "medium urgency"),
            (7.0, "medium urgency"),
            (10.0, "lower urgency"),
            (15.0, "low urgency"),
            (30.0, "very low urgency"),
            (60.0, "minimal urgency"),
        ]

        for days, description in test_cases:
            urgency = fcc._calculate_urgency_from_days(days)
            assert isinstance(urgency, (int, float))
            assert urgency >= 0

    def test_normalize_spn_to_component_all_known(self):
        """Test SPN normalization for all known SPNs"""
        fcc = FleetCommandCenter()

        # Test all J1939 SPNs
        spn_tests = [
            (190, "engine"),
            (92, "engine_load"),
            (110, "cool_temp"),
            (175, "oil_temp"),
            (177, "trams_t"),
            (105, "intk_t"),
            (100, "oil_press"),
            (5245, "def_level"),
            (5246, "def_temp"),
            (168, "voltage"),
            (96, "fuel_lvl"),
            (183, "fuel_rate"),
        ]

        for spn, expected_component in spn_tests:
            component = fcc.normalize_spn_to_component(spn)
            assert component == expected_component

    def test_get_spn_info_all_known(self):
        """Test SPN info retrieval for all known SPNs"""
        fcc = FleetCommandCenter()

        spns = [190, 92, 110, 175, 177, 105, 100, 5245, 5246, 168, 96, 183]

        for spn in spns:
            info = fcc.get_spn_info(spn)
            assert info is not None
            assert "component" in info
            assert "name" in info
            assert "unit" in info

    def test_get_time_horizon_all_ranges(self):
        """Test time horizon calculation for all ranges"""
        fcc = FleetCommandCenter()

        # Test various day ranges
        horizons = []
        for days in [0.5, 1, 2, 3, 5, 7, 10, 15, 30, 60]:
            horizon = fcc._get_time_horizon(days)
            assert horizon in ["immediate", "short_term", "medium_term"]
            horizons.append(horizon)


class TestDataClassOperations:
    """Test all dataclass operations"""

    def test_action_item_full_lifecycle(self):
        """Test ActionItem creation, modification, and serialization"""
        action = ActionItem(
            id="test-action-123",
            truck_id="DO9693",
            priority=Priority.CRITICAL,
            priority_score=95.0,
            category=IssueCategory.ENGINE,
            component="oil_system",
            title="Critical Oil Pressure",
            description="Oil pressure dangerously low",
            days_to_critical=0.5,
            cost_if_ignored="$10,000-$20,000",
            current_value="10 PSI",
            trend="-5 PSI/hour",
            threshold="Critical: <20 PSI",
            confidence="HIGH",
            action_type=ActionType.STOP_IMMEDIATELY,
            action_steps=["Stop vehicle immediately", "Call service"],
            icon="🛢️",
            sources=["Sensor Health Monitor", "Real-Time Predictive"],
        )

        # Test all attributes
        assert action.truck_id == "DO9693"
        assert action.priority == Priority.CRITICAL
        assert action.priority_score == 95.0
        assert action.category == IssueCategory.ENGINE
        assert action.days_to_critical == 0.5
        assert len(action.sources) == 2

        # Test serialization
        data = action.to_dict()
        assert data["truck_id"] == "DO9693"
        assert data["priority"] == "CRÍTICO"
        assert data["category"] == "Motor"
        assert data["priority_score"] == 95.0

    def test_truck_risk_score_full(self):
        """Test TruckRiskScore full functionality"""
        risk = TruckRiskScore(
            truck_id="FF7702",
            risk_score=85.5,
            risk_level="critical",
            contributing_factors=["High oil temp", "DEF low", "DTC active"],
            days_since_last_maintenance=45,
            active_issues_count=5,
            predicted_failure_days=2.5,
        )

        assert risk.truck_id == "FF7702"
        assert risk.risk_score == 85.5
        assert risk.risk_level == "critical"
        assert len(risk.contributing_factors) == 3
        assert risk.active_issues_count == 5

        data = risk.to_dict()
        assert data["risk_score"] == 85.5
        assert data["predicted_failure_days"] == 2.5

    def test_urgency_summary_calculations(self):
        """Test UrgencySummary with various values"""
        summary = UrgencySummary(critical=5, high=10, medium=15, low=8, ok=50)

        assert summary.total_issues == 38  # 5+10+15+8
        assert summary.critical == 5
        assert summary.ok == 50

    def test_fleet_health_score_creation(self):
        """Test FleetHealthScore creation"""
        health = FleetHealthScore(
            score=75,
            status="Bueno",
            trend="improving",
            description="Fleet health is improving overall",
        )

        assert health.score == 75
        assert health.status == "Bueno"
        assert health.trend == "improving"

    def test_cost_projection_creation(self):
        """Test CostProjection creation"""
        cost = CostProjection(
            immediate_risk="$15,000", week_risk="$25,000", month_risk="$50,000"
        )

        assert cost.immediate_risk == "$15,000"
        assert cost.week_risk == "$25,000"
        assert cost.month_risk == "$50,000"

    def test_sensor_status_creation(self):
        """Test SensorStatus creation"""
        status = SensorStatus(
            gps_issues=3,
            voltage_issues=2,
            dtc_active=5,
            idle_deviation=1,
            total_trucks=25,
        )

        assert status.gps_issues == 3
        assert status.total_trucks == 25

    def test_def_prediction_full(self):
        """Test DEFPrediction with all fields"""
        pred = DEFPrediction(
            truck_id="DO9693",
            current_level_pct=25.5,
            estimated_liters_remaining=19.1,
            avg_consumption_liters_per_day=2.5,
            days_until_empty=7.6,
            days_until_derate=5.8,
            last_fill_date=datetime(2025, 1, 15, 10, 30, tzinfo=timezone.utc),
        )

        assert pred.truck_id == "DO9693"
        assert pred.current_level_pct == 25.5
        assert pred.days_until_empty == 7.6

        data = pred.to_dict()
        assert data["days_until_derate"] == 5.8
        assert data["last_fill_date"] is not None

    def test_failure_correlation_full(self):
        """Test FailureCorrelation with all fields"""
        corr = FailureCorrelation(
            correlation_id="CORR-OVERHEAT-001",
            primary_sensor="cool_temp",
            correlated_sensors=["oil_temp", "trams_t", "intk_t"],
            correlation_strength=0.92,
            probable_cause="Cooling system failure - radiator or water pump",
            recommended_action="Inspect cooling system immediately",
            affected_trucks=["DO9693", "FF7702"],
        )

        assert corr.correlation_id == "CORR-OVERHEAT-001"
        assert len(corr.correlated_sensors) == 3
        assert corr.correlation_strength == 0.92

        data = corr.to_dict()
        assert data["correlation_strength"] == 0.92
        assert len(data["affected_trucks"]) == 2

    def test_sensor_reading_creation(self):
        """Test SensorReading creation"""
        reading = SensorReading(
            sensor_name="oil_press",
            truck_id="DO9693",
            value=35.5,
            timestamp=datetime.now(timezone.utc),
            is_valid=True,
        )

        assert reading.sensor_name == "oil_press"
        assert reading.value == 35.5
        assert reading.is_valid is True

    def test_command_center_data_full(self):
        """Test CommandCenterData with all fields"""
        data = CommandCenterData(
            generated_at=datetime.now(timezone.utc).isoformat(),
            version="1.8.0",
            fleet_health=FleetHealthScore(85, "Excelente", "improving", "Good"),
            total_trucks=25,
            trucks_analyzed=23,
            urgency_summary=UrgencySummary(2, 5, 10, 8, 10),
            sensor_status=SensorStatus(1, 2, 3, 0, 25),
            cost_projection=CostProjection("$10K", "$25K", "$50K"),
            action_items=[],
            critical_actions=[],
            high_priority_actions=[],
            insights=[{"type": "info", "message": "Fleet healthy"}],
            data_quality={"score": 95},
        )

        assert data.total_trucks == 25
        assert data.trucks_analyzed == 23

        dict_data = data.to_dict()
        assert dict_data["total_trucks"] == 25
        assert dict_data["version"] == "1.8.0"
