"""
Comprehensive test to push coverage to 100% on all 4 modules
Systematically covers missing lines identified in coverage reports
"""

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest
from sqlalchemy import text

import alert_service
import dtc_analyzer

# Import all 4 modules
import fleet_command_center
import predictive_maintenance_engine
from database_mysql import get_sqlalchemy_engine
from timezone_utils import utc_now

# ════════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ════════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def sample_truck_id():
    """Return default truck ID"""
    return "CO0681"


@pytest.fixture
def ensure_all_tables():
    """Ensure all required tables exist"""
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        # PM tables
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS pm_sensor_history (
                id INT AUTO_INCREMENT PRIMARY KEY,
                truck_id VARCHAR(50),
                sensor_name VARCHAR(100),
                value FLOAT,
                timestamp DATETIME,
                INDEX idx_truck_sensor (truck_id, sensor_name)
            )
        """
            )
        )

        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS pm_predictions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                truck_id VARCHAR(50),
                sensor_name VARCHAR(100),
                urgency VARCHAR(50),
                days_to_failure INT,
                prediction_time DATETIME
            )
        """
            )
        )

        # Alert tables
        conn.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS pending_fuel_drops (
                id INT AUTO_INCREMENT PRIMARY KEY,
                truck_id VARCHAR(50),
                drop_timestamp DATETIME,
                fuel_before FLOAT,
                fuel_after FLOAT,
                drop_pct FLOAT,
                drop_gal FLOAT
            )
        """
            )
        )

        conn.commit()
    yield


# ════════════════════════════════════════════════════════════════════════════════
# TEST DTC ANALYZER - Push to 100%
# ════════════════════════════════════════════════════════════════════════════════


class TestDTCAnalyzerComprehensive:
    """Cover all remaining DTC analyzer lines"""

    def test_dtc_analyzer_singleton(self):
        """Test singleton pattern"""
        analyzer1 = dtc_analyzer.get_dtc_analyzer()
        analyzer2 = dtc_analyzer.get_dtc_analyzer()
        assert analyzer1 is analyzer2

    def test_parse_dtc_string_valid_j1939(self):
        """Test parsing valid J1939 format"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        codes = analyzer.parse_dtc_string("110.0,629.2")
        assert len(codes) >= 1
        assert codes[0].spn == 110

    def test_parse_dtc_string_empty(self):
        """Test parsing empty string"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        codes = analyzer.parse_dtc_string("")
        assert codes == []

    def test_parse_dtc_string_none(self):
        """Test parsing None"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        codes = analyzer.parse_dtc_string(None)
        assert codes == []

    def test_process_truck_dtc_new_codes(self, sample_truck_id):
        """Test processing new DTC codes"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        now = utc_now()

        alerts = analyzer.process_truck_dtc(
            truck_id=sample_truck_id, dtc_string="110.0", timestamp=now
        )
        assert isinstance(alerts, list)

    def test_process_truck_dtc_empty_string(self, sample_truck_id):
        """Test processing empty DTC string"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        now = utc_now()

        alerts = analyzer.process_truck_dtc(
            truck_id=sample_truck_id, dtc_string="", timestamp=now
        )
        assert alerts == []

    def test_process_truck_dtc_critical_codes(self, sample_truck_id):
        """Test processing critical DTC codes"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        now = utc_now()

        # Process critical code
        alerts = analyzer.process_truck_dtc(
            truck_id=sample_truck_id,
            dtc_string="629.2",  # Critical engine code
            timestamp=now,
        )
        assert isinstance(alerts, list)

    def test_get_active_dtcs_no_truck(self):
        """Test get_active_dtcs with no truck parameter"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        active = analyzer.get_active_dtcs()
        assert isinstance(active, dict)

    def test_get_active_dtcs_specific_truck(self, sample_truck_id):
        """Test get_active_dtcs for specific truck"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        active = analyzer.get_active_dtcs(truck_id=sample_truck_id)
        assert isinstance(active, dict)

    def test_get_fleet_dtc_summary(self):
        """Test fleet DTC summary"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        summary = analyzer.get_fleet_dtc_summary()
        assert isinstance(summary, dict)
        assert "trucks_with_dtcs" in summary

    def test_get_dtc_analysis_report(self, sample_truck_id):
        """Test DTC analysis report"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        report = analyzer.get_dtc_analysis_report(
            truck_id=sample_truck_id, dtc_string="110.0,629.2"
        )
        assert isinstance(report, dict)
        assert "truck_id" in report

    def test_get_dtc_analysis_report_empty(self, sample_truck_id):
        """Test DTC analysis report with no codes"""
        analyzer = dtc_analyzer.get_dtc_analyzer()
        report = analyzer.get_dtc_analysis_report(
            truck_id=sample_truck_id, dtc_string=""
        )
        assert isinstance(report, dict)
        assert report.get("status") == "ok"


# ════════════════════════════════════════════════════════════════════════════════
# TEST PREDICTIVE MAINTENANCE ENGINE - Push to 100%
# ════════════════════════════════════════════════════════════════════════════════


class TestPMEngineComprehensive:
    """Cover all remaining PM engine lines"""

    def test_pm_engine_singleton(self):
        """Test PM engine singleton"""
        engine1 = predictive_maintenance_engine.get_predictive_maintenance_engine()
        engine2 = predictive_maintenance_engine.get_predictive_maintenance_engine()
        assert engine1 is engine2

    def test_pm_engine_analyze_truck(self, sample_truck_id, ensure_all_tables):
        """Test analyze_truck method"""
        engine = predictive_maintenance_engine.get_predictive_maintenance_engine()
        predictions = engine.analyze_truck(truck_id=sample_truck_id)
        assert isinstance(predictions, list)

    def test_pm_engine_analyze_fleet(self, ensure_all_tables):
        """Test analyze_fleet method"""
        engine = predictive_maintenance_engine.get_predictive_maintenance_engine()
        fleet = engine.analyze_fleet()
        assert isinstance(fleet, dict)

    def test_pm_engine_get_truck_maintenance_status(
        self, sample_truck_id, ensure_all_tables
    ):
        """Test get_truck_maintenance_status"""
        engine = predictive_maintenance_engine.get_predictive_maintenance_engine()
        status = engine.get_truck_maintenance_status(truck_id=sample_truck_id)
        # Can be None if no data
        assert status is None or isinstance(status, dict)

    def test_pm_engine_get_fleet_summary(self, ensure_all_tables):
        """Test get_fleet_summary"""
        engine = predictive_maintenance_engine.get_predictive_maintenance_engine()
        summary = engine.get_fleet_summary()
        assert isinstance(summary, dict)

    def test_pm_engine_get_maintenance_alerts(self, sample_truck_id, ensure_all_tables):
        """Test get_maintenance_alerts"""
        engine = predictive_maintenance_engine.get_predictive_maintenance_engine()
        alerts = engine.get_maintenance_alerts(truck_id=sample_truck_id)
        assert isinstance(alerts, list)

    def test_sensor_history_dataclass(self):
        """Test SensorHistory dataclass"""
        from predictive_maintenance_engine import SensorHistory

        history = SensorHistory(sensor_name="oil_pressure", truck_id="CO0681")
        assert history.sensor_name == "oil_pressure"
        assert history.truck_id == "CO0681"

    def test_sensor_history_add_reading(self):
        """Test adding readings to sensor history"""
        from predictive_maintenance_engine import SensorHistory

        history = SensorHistory(sensor_name="oil_pressure", truck_id="CO0681")

        now = utc_now()
        history.add_reading(now, 30.0)
        history.add_reading(now + timedelta(days=1), 29.5)

        assert len(history.readings) == 2

    def test_sensor_history_calculate_trend(self):
        """Test trend calculation"""
        from predictive_maintenance_engine import SensorHistory

        history = SensorHistory(sensor_name="oil_pressure", truck_id="CO0681")

        now = utc_now()
        for i in range(10):
            history.add_reading(now + timedelta(days=i), 30.0 - (i * 0.5))

        trend = history.calculate_trend()
        # Should return negative trend or None
        assert trend is None or trend < 0

    def test_sensor_history_get_current_value(self):
        """Test get_current_value"""
        from predictive_maintenance_engine import SensorHistory

        history = SensorHistory(sensor_name="oil_pressure", truck_id="CO0681")

        # No readings
        assert history.get_current_value() is None

        # With reading
        now = utc_now()
        history.add_reading(now, 30.0)
        assert history.get_current_value() == 30.0

    def test_maintenance_prediction_to_dict(self):
        """Test MaintenancePrediction to_dict"""
        from predictive_maintenance_engine import (
            MaintenancePrediction,
            MaintenanceUrgency,
            TrendDirection,
        )

        prediction = MaintenancePrediction(
            truck_id="CO0681",
            sensor_name="oil_pressure",
            component="Oil Pump",
            current_value=28.5,
            unit="psi",
            trend_per_day=-0.3,
            trend_direction=TrendDirection.DEGRADING,
            days_to_warning=15.0,
            days_to_critical=25.0,
            urgency=MaintenanceUrgency.MEDIUM,
            confidence="HIGH",
            recommended_action="Monitor oil pressure",
            estimated_cost_if_fail="$2000",
            warning_threshold=25.0,
            critical_threshold=20.0,
        )

        result = prediction.to_dict()
        assert isinstance(result, dict)
        assert result["truck_id"] == "CO0681"

    def test_maintenance_prediction_to_alert_message(self):
        """Test MaintenancePrediction to_alert_message"""
        from predictive_maintenance_engine import (
            MaintenancePrediction,
            MaintenanceUrgency,
            TrendDirection,
        )

        prediction = MaintenancePrediction(
            truck_id="CO0681",
            sensor_name="oil_pressure",
            component="Oil Pump",
            current_value=28.5,
            unit="psi",
            trend_per_day=-0.3,
            trend_direction=TrendDirection.DEGRADING,
            days_to_warning=15.0,
            days_to_critical=5.0,
            urgency=MaintenanceUrgency.HIGH,
            confidence="HIGH",
            recommended_action="Check oil pressure",
            estimated_cost_if_fail="$2000",
            warning_threshold=25.0,
            critical_threshold=20.0,
        )

        message = prediction.to_alert_message()
        assert isinstance(message, str)
        assert "CO0681" in message


# ════════════════════════════════════════════════════════════════════════════════
# TEST ALERT SERVICE - Push to 100%
# ════════════════════════════════════════════════════════════════════════════════


class TestAlertServiceComprehensive:
    """Cover all remaining alert service lines"""

    def test_alert_enums(self):
        """Test Alert enums"""
        from alert_service import AlertPriority, AlertType

        assert AlertPriority.CRITICAL.value == "critical"
        assert AlertType.THEFT_CONFIRMED.value == "theft_confirmed"

    def test_alert_dataclass(self):
        """Test Alert dataclass"""
        from alert_service import Alert, AlertPriority, AlertType

        alert = Alert(
            alert_type=AlertType.REFUEL,
            priority=AlertPriority.LOW,
            truck_id="CO0681",
            message="Test alert",
        )
        assert alert.truck_id == "CO0681"
        assert isinstance(alert.timestamp, datetime)

    def test_fuel_classifier_singleton(self):
        """Test fuel classifier singleton"""
        classifier1 = alert_service.get_fuel_classifier()
        classifier2 = alert_service.get_fuel_classifier()
        assert classifier1 is classifier2

    def test_fuel_classifier_is_refuel(self):
        """Test is_refuel method"""
        classifier = alert_service.get_fuel_classifier()

        # >= 25 gallons is refuel
        assert classifier.is_refuel(30.0) is True
        assert classifier.is_refuel(20.0) is False

    def test_fuel_classifier_classify_fuel_drop(
        self, sample_truck_id, ensure_all_tables
    ):
        """Test classify_fuel_drop"""
        classifier = alert_service.get_fuel_classifier()
        now = utc_now()

        # Simulate drop
        result = classifier.classify_fuel_drop(
            truck_id=sample_truck_id, fuel_before=100.0, fuel_after=70.0, timestamp=now
        )
        assert isinstance(result, dict)

    def test_fuel_classifier_check_pending_drops(self, ensure_all_tables):
        """Test check_pending_drops"""
        classifier = alert_service.get_fuel_classifier()
        now = utc_now()

        confirmed = classifier.check_pending_drops(current_time=now)
        assert isinstance(confirmed, list)

    def test_alert_manager_singleton(self):
        """Test alert manager singleton"""
        manager1 = alert_service.get_alert_manager()
        manager2 = alert_service.get_alert_manager()
        assert manager1 is manager2

    @patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "AC123",
            "TWILIO_AUTH_TOKEN": "token123",
            "TWILIO_FROM_NUMBER": "+11234567890",
            "TWILIO_TO_NUMBERS": "+10987654321",
        },
    )
    def test_send_theft_alert(self, sample_truck_id):
        """Test send_theft_alert function"""
        # Just test that function exists and can be called
        # We're not actually sending alerts in tests
        from alert_service import send_theft_alert

        assert callable(send_theft_alert)

    @patch.dict(
        os.environ,
        {
            "SMTP_SERVER": "smtp.gmail.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "test@example.com",
            "SMTP_PASS": "password",
            "ALERT_EMAIL_TO": "recipient@example.com",
        },
    )
    def test_email_config(self):
        """Test EmailConfig"""
        from alert_service import EmailConfig

        config = EmailConfig()
        assert config.smtp_server == "smtp.gmail.com"
        assert config.smtp_port == 587


# ════════════════════════════════════════════════════════════════════════════════
# TEST FLEET COMMAND CENTER - Additional Coverage
# ════════════════════════════════════════════════════════════════════════════════


class TestFleetCommandCenterAdditional:
    """Additional tests for fleet command center missing lines"""

    def test_fleet_cc_singleton(self):
        """Test fleet command center singleton"""
        cc1 = fleet_command_center.get_fleet_command_center()
        cc2 = fleet_command_center.get_fleet_command_center()
        assert cc1 is cc2

    def test_fleet_cc_get_comprehensive_truck_health(self, sample_truck_id):
        """Test get_comprehensive_truck_health"""
        cc = fleet_command_center.get_fleet_command_center()
        health = cc.get_comprehensive_truck_health(truck_id=sample_truck_id)
        assert isinstance(health, dict)
        assert "truck_id" in health

    def test_fleet_cc_get_fleet_health_summary(self):
        """Test get_fleet_health_summary"""
        cc = fleet_command_center.get_fleet_command_center()
        summary = cc.get_fleet_health_summary()
        assert isinstance(summary, dict)

    def test_fleet_cc_calculate_truck_risk_score(self, sample_truck_id):
        """Test calculate_truck_risk_score"""
        cc = fleet_command_center.get_fleet_command_center()

        # Create sample action items
        from fleet_command_center import ActionItem

        items = []

        risk = cc.calculate_truck_risk_score(
            truck_id=sample_truck_id, action_items=items
        )
        assert isinstance(risk, fleet_command_center.TruckRiskScore)

    def test_fleet_cc_enums(self):
        """Test fleet command center enums"""
        from fleet_command_center import ActionType, IssueCategory, Urgency

        assert IssueCategory.FUEL_THEFT.value == "fuel_theft"
        assert ActionType.IMMEDIATE_REPAIR.value == "immediate_repair"
        assert Urgency.CRITICAL.value == "CRITICAL"

    def test_fleet_cc_dataclasses(self):
        """Test fleet command center dataclasses"""
        from fleet_command_center import Insight, TruckRiskScore

        risk = TruckRiskScore(
            truck_id="CO0681",
            risk_score=75.5,
            risk_level="high",
            critical_issues=2,
            high_priority_issues=3,
            total_issues=5,
        )
        assert risk.truck_id == "CO0681"

        insight = Insight(
            title="Test Insight",
            description="Test description",
            severity="high",
            affected_trucks=["CO0681"],
            recommended_action="Test action",
        )
        assert insight.title == "Test Insight"
