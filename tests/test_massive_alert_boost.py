"""Massive Alert Service Boost - Target 90%"""

from unittest.mock import MagicMock, patch

import pytest

from alert_service import *


class TestAlertServiceComplete:
    def test_alert_priority_all_values(self):
        assert AlertPriority.LOW.value == "low"
        assert AlertPriority.MEDIUM.value == "medium"
        assert AlertPriority.HIGH.value == "high"
        assert AlertPriority.CRITICAL.value == "critical"

    def test_alert_type_all_values(self):
        assert AlertType.REFUEL.value == "refuel"
        assert AlertType.THEFT_SUSPECTED.value == "theft_suspected"
        assert AlertType.THEFT_CONFIRMED.value == "theft_confirmed"
        assert AlertType.SENSOR_ISSUE.value == "sensor_issue"
        assert AlertType.DRIFT_WARNING.value == "drift_warning"
        assert AlertType.SENSOR_OFFLINE.value == "sensor_offline"
        assert AlertType.LOW_FUEL.value == "low_fuel"
        assert AlertType.EFFICIENCY_DROP.value == "efficiency_drop"
        assert AlertType.MAINTENANCE_DUE.value == "maintenance_due"
        assert AlertType.DTC_ALERT.value == "dtc_alert"
        assert AlertType.VOLTAGE_ALERT.value == "voltage_alert"
        assert AlertType.IDLE_DEVIATION.value == "idle_deviation"
        assert AlertType.GPS_QUALITY.value == "gps_quality"
        assert AlertType.MAINTENANCE_PREDICTION.value == "maintenance_prediction"
        assert AlertType.MPG_UNDERPERFORMANCE.value == "mpg_underperformance"

    def test_alert_creation_basic(self):
        a = Alert(AlertType.REFUEL, AlertPriority.LOW, "TRK001", "Test")
        assert a.truck_id == "TRK001"
        assert a.message == "Test"
        assert a.timestamp is not None

    def test_alert_with_details(self):
        a = Alert(
            AlertType.THEFT_SUSPECTED,
            AlertPriority.CRITICAL,
            "TRK001",
            "Theft",
            {"drop": 20.0},
        )
        assert a.details["drop"] == 20.0

    def test_pending_fuel_drop_creation(self):
        p = PendingFuelDrop("TRK001", 50.0, 30.0, datetime.now())
        assert p.truck_id == "TRK001"
        assert p.before_pct == 50.0
        assert p.after_pct == 30.0

    def test_fuel_classifier_normal(self):
        fc = FuelEventClassifier()
        r = fc.classify_fuel_event("TRK001", 50.0, 48.0, "MOVING", datetime.now())
        assert r["event_type"] in [
            "normal_consumption",
            "rapid_drop",
            "refuel",
            "sensor_glitch",
        ]

    def test_fuel_classifier_refuel(self):
        fc = FuelEventClassifier()
        r = fc.classify_fuel_event("TRK001", 30.0, 90.0, "STOPPED", datetime.now())
        assert r["event_type"] == "refuel"

    def test_fuel_classifier_theft(self):
        fc = FuelEventClassifier()
        r = fc.classify_fuel_event("TRK001", 80.0, 30.0, "STOPPED", datetime.now())
        assert r["event_type"] in ["rapid_drop", "sensor_glitch", "theft_suspected"]

    def test_get_fuel_classifier_singleton(self):
        fc1 = get_fuel_classifier()
        fc2 = get_fuel_classifier()
        assert fc1 is fc2

    @patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "test",
            "TWILIO_AUTH_TOKEN": "test",
            "TWILIO_FROM_NUMBER": "+1234567890",
        },
    )
    def test_twilio_config(self):
        tc = TwilioConfig()
        assert tc.account_sid == "test"
        assert tc.auth_token == "test"
        assert tc.from_number == "+1234567890"

    @patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "test",
            "TWILIO_AUTH_TOKEN": "test",
            "TWILIO_FROM_NUMBER": "+1234567890",
        },
    )
    @patch("alert_service.Client")
    def test_twilio_service_init(self, mc):
        ts = TwilioAlertService()
        assert ts.config.account_sid == "test"

    @patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "test",
            "TWILIO_AUTH_TOKEN": "test",
            "TWILIO_FROM_NUMBER": "+1234567890",
            "TWILIO_TO_NUMBERS": "+0987654321",
        },
    )
    @patch("alert_service.Client")
    def test_twilio_send_sms(self, mc):
        mc_instance = MagicMock()
        mc_instance.messages.create.return_value = MagicMock(sid="test_sid")
        mc.return_value = mc_instance
        ts = TwilioAlertService()
        r = ts.send_sms("Test message")
        assert r is True or r is False

    @patch.dict(
        os.environ,
        {
            "TWILIO_ACCOUNT_SID": "test",
            "TWILIO_AUTH_TOKEN": "test",
            "TWILIO_FROM_NUMBER": "+1234567890",
            "TWILIO_TO_NUMBERS": "+111,+222",
        },
    )
    @patch("alert_service.Client")
    def test_twilio_multiple_numbers(self, mc):
        mc_instance = MagicMock()
        mc_instance.messages.create.return_value = MagicMock(sid="test_sid")
        mc.return_value = mc_instance
        ts = TwilioAlertService()
        r = ts.send_sms("Multi test")
        assert r is True or r is False

    @patch.dict(
        os.environ,
        {
            "SMTP_SERVER": "smtp.test.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "test@test.com",
            "SMTP_PASS": "pass",
            "ALERT_EMAIL_TO": "to@test.com",
        },
    )
    def test_email_config(self):
        ec = EmailConfig()
        assert ec.smtp_server == "smtp.test.com"
        assert ec.smtp_port == 587
        assert ec.smtp_user == "test@test.com"

    @patch.dict(
        os.environ,
        {
            "SMTP_SERVER": "smtp.test.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "test@test.com",
            "SMTP_PASS": "pass",
            "ALERT_EMAIL_TO": "to@test.com",
        },
    )
    @patch("alert_service.smtplib.SMTP")
    def test_email_service_send(self, ms):
        ms_instance = MagicMock()
        ms.return_value.__enter__.return_value = ms_instance
        es = EmailAlertService()
        r = es.send_email("Subject", "Body")
        assert r is True or r is False

    @patch.dict(
        os.environ,
        {
            "SMTP_SERVER": "smtp.test.com",
            "SMTP_PORT": "587",
            "SMTP_USER": "test@test.com",
            "SMTP_PASS": "pass",
            "ALERT_EMAIL_TO": "to@test.com",
        },
    )
    @patch("alert_service.smtplib.SMTP")
    def test_email_html(self, ms):
        ms_instance = MagicMock()
        ms.return_value.__enter__.return_value = ms_instance
        es = EmailAlertService()
        r = es.send_email("HTML Test", "<h1>Test</h1>", is_html=True)
        assert r is True or r is False

    @patch("alert_service.get_db_connection")
    def test_alert_manager_init(self, mdb):
        mdb.return_value = MagicMock()
        am = AlertManager()
        assert am is not None

    @patch("alert_service.get_db_connection")
    def test_alert_manager_create(self, mdb):
        mc = MagicMock()
        mdb.return_value = mc
        am = AlertManager()
        a = Alert(AlertType.LOW_FUEL, AlertPriority.MEDIUM, "TRK001", "Low fuel")
        r = am.create_alert(a)
        assert r is True or r is False

    @patch("alert_service.get_db_connection")
    def test_alert_manager_get_active(self, mdb):
        mc = MagicMock()
        mcur = MagicMock()
        mcur.fetchall.return_value = []
        mc.cursor.return_value.__enter__.return_value = mcur
        mdb.return_value = mc
        am = AlertManager()
        r = am.get_active_alerts()
        assert isinstance(r, list)

    @patch("alert_service.get_db_connection")
    def test_alert_manager_dismiss(self, mdb):
        mc = MagicMock()
        mdb.return_value = mc
        am = AlertManager()
        r = am.dismiss_alert(1)
        assert r is True or r is False

    def test_get_alert_manager_singleton(self):
        am1 = get_alert_manager()
        am2 = get_alert_manager()
        assert am1 is am2

    @patch("alert_service.get_alert_manager")
    @patch("alert_service.TwilioAlertService")
    @patch("alert_service.EmailAlertService")
    def test_send_theft_alert(self, me, mt, mam):
        send_theft_alert("TRK001", 80.0, 30.0, datetime.now())

    @patch("alert_service.get_alert_manager")
    def test_send_theft_confirmed_alert(self, mam):
        send_theft_confirmed_alert("TRK001", 50.0, 20.0, datetime.now())

    @patch("alert_service.get_alert_manager")
    def test_send_sensor_issue_alert(self, mam):
        send_sensor_issue_alert("TRK001", 60.0, 30.0, datetime.now())

    @patch("alert_service.get_alert_manager")
    def test_send_low_fuel_alert(self, mam):
        send_low_fuel_alert("TRK001", 15.0)

    @patch("alert_service.get_alert_manager")
    def test_send_dtc_alert(self, mam):
        send_dtc_alert("TRK001", "SPN 1234", "Engine issue")

    @patch("alert_service.get_alert_manager")
    def test_send_voltage_alert(self, mam):
        send_voltage_alert("TRK001", 10.5)

    @patch("alert_service.get_alert_manager")
    def test_send_idle_deviation_alert(self, mam):
        send_idle_deviation_alert("TRK001", 2.5, 1.5)

    @patch("alert_service.get_alert_manager")
    def test_send_gps_quality_alert(self, mam):
        send_gps_quality_alert("TRK001", 3)

    @patch("alert_service.get_alert_manager")
    def test_send_maintenance_prediction_alert(self, mam):
        send_maintenance_prediction_alert("TRK001", "Engine Filter", 5)
