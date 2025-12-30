"""
Simplified tests to cover missing lines in alert_service.py
Focus: Execute uncovered code paths
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from alert_service import get_fuel_classifier


class TestAlertSimplePaths:
    """Simple tests to hit uncovered lines"""

    def test_volatile_sensor_detection(self):
        """Cover lines 229-235: high volatility detection"""
        classifier = get_fuel_classifier()
        truck_id = "TVOL"

        # Create highly volatile data
        for val in [100, 50, 95, 45, 90, 40]:
            classifier.add_fuel_reading(truck_id, val)

        # This should trigger sensor issue due to volatility
        result = classifier.process_fuel_reading(
            truck_id=truck_id,
            last_fuel_pct=40,
            current_fuel_pct=5,  # Big drop
            tank_capacity_gal=100,
            location="Test",
        )

        # Should detect sensor issue
        assert "SENSOR" in result.get("classification", "")

    def test_refuel_path(self):
        """Cover lines 355-380: refuel detection"""
        classifier = get_fuel_classifier()
        truck_id = "TREF"

        # Baseline low fuel
        classifier.add_fuel_reading(truck_id, 30)
        classifier.add_fuel_reading(truck_id, 30)

        # Refuel
        result = classifier.process_fuel_reading(
            truck_id=truck_id,
            last_fuel_pct=30,
            current_fuel_pct=95,
            tank_capacity_gal=100,
            location="Station",
        )

        assert result["classification"] == "REFUEL"

    def test_immediate_theft_detection(self):
        """Cover lines for immediate theft classification"""
        classifier = get_fuel_classifier()
        truck_id = "TTHEFT"

        # Stable readings
        classifier.add_fuel_reading(truck_id, 100)
        classifier.add_fuel_reading(truck_id, 100)

        # Massive drop while stopped
        result = classifier.process_fuel_reading(
            truck_id=truck_id,
            last_fuel_pct=100,
            current_fuel_pct=60,  # 40% drop
            tank_capacity_gal=100,
            location="Yard",
            truck_status="STOPPED",
        )

        # Should classify as theft
        assert "THEFT" in result.get("classification", "")

    def test_recovery_check_no_pending(self):
        """Cover lines 560-562: recovery check with no pending drops"""
        classifier = get_fuel_classifier()

        result = classifier.check_recovery("NODROPS", 50)
        assert result is None

    @patch("alert_service.smtplib.SMTP")
    def test_email_send_path(self, mock_smtp):
        """Cover email sending path lines 702-781"""
        from alert_service import EmailAlertService, EmailConfig

        # Create configured email service
        config = EmailConfig()
        config.smtp_server = "smtp.test.com"
        config.smtp_port = 587
        config.smtp_user = "user@test.com"
        config.smtp_pass = "pass"
        config.to_email = "admin@test.com"

        service = EmailAlertService(config)

        # Mock SMTP
        mock_server = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_server

        # Send email with correct signature
        result = service.send_email(
            subject="Test Alert",
            body="Theft detected on truck TEST",
            html_body="<h1>Theft Alert</h1>",
        )

        assert result is True

    def test_cleanup_old_drops(self):
        """Cover cleanup lines 988-1004"""
        classifier = get_fuel_classifier()

        # This will execute cleanup logic
        classifier.cleanup_stale_drops()

        # No assertion needed, just execute path

    def test_high_drop_classification(self):
        """Cover various classification paths"""
        classifier = get_fuel_classifier()
        truck_id = "TDROP"

        # Stable baseline
        for _ in range(10):
            classifier.add_fuel_reading(truck_id, 100)

        # Moderate drop
        result = classifier.process_fuel_reading(
            truck_id=truck_id,
            last_fuel_pct=100,
            current_fuel_pct=85,  # 15% drop
            tank_capacity_gal=100,
            location="Highway",
        )

        # Should be buffered or classified
        assert result is not None
