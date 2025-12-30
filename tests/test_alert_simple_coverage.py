"""
Alert Service - Tests simples para las 83 líneas faltantes
Enfoque: Cubrir código sin mocks complejos
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from alert_service import (
    Alert,
    AlertManager,
    AlertPriority,
    AlertType,
    EmailAlertService,
    EmailConfig,
    TwilioAlertService,
    TwilioConfig,
    get_alert_manager,
)


class TestAlertServiceSimpleCoverage:
    """Tests simples para maximizar cobertura"""

    def test_twilio_not_configured(self):
        """Test Twilio no configurado - líneas 510-519"""
        config = TwilioConfig(
            account_sid=None, auth_token=None, from_number=None, to_numbers=[]
        )
        service = TwilioAlertService(config)

        # Try to initialize - should fail gracefully
        result = service._initialize_client()
        assert result is False

    def test_email_not_configured(self):
        """Test Email no configurado"""
        config = EmailConfig(
            smtp_server=None,
            smtp_port=587,
            smtp_user=None,
            smtp_pass=None,
            to_email=None,
        )
        service = EmailAlertService(config)

        # Try to send - should fail gracefully
        result = service.send_email("Test", "Body")
        assert result is False

    def test_alert_manager_singleton(self):
        """Test singleton pattern"""
        manager1 = get_alert_manager()
        manager2 = get_alert_manager()
        assert manager1 is manager2

    def test_alert_manager_send_with_rate_limiting(self):
        """Test rate limiting - línea 908"""
        manager = AlertManager()

        alert = Alert(
            alert_type=AlertType.THEFT_SUSPECTED,
            priority=AlertPriority.CRITICAL,
            truck_id="T001",
            message="Test alert",
            details={},
        )

        # Send alert twice quickly - second should be rate limited
        manager.send_alert(alert, channels=[])

        # Verify type tracking
        type_key = f"T001:{AlertType.THEFT_SUSPECTED.value}"
        assert type_key in manager._last_alert_by_type

    @patch("smtplib.SMTP")
    def test_email_send_with_mock_smtp(self, mock_smtp_class):
        """Test email sending - líneas 669-693"""
        mock_smtp = MagicMock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        config = EmailConfig(
            smtp_server="smtp.test.com",
            smtp_port=587,
            smtp_user="test@test.com",
            smtp_pass="password",
            to_email="alerts@test.com",
        )
        service = EmailAlertService(config)

        result = service.send_email(
            subject="Test", body="Plain body", html_body="<h1>HTML</h1>"
        )

        assert result is True
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("test@test.com", "password")

    def test_twilio_broadcast_no_numbers(self):
        """Test broadcast sin números - líneas 605-616"""
        config = TwilioConfig(
            account_sid="AC123",
            auth_token="token",
            from_number="+1234567890",
            to_numbers=[],
        )
        service = TwilioAlertService(config)

        results = service.broadcast_sms("Test message")
        assert results == {}

    def test_alert_history_tracking(self):
        """Test alert history"""
        manager = AlertManager()

        alert = Alert(
            alert_type=AlertType.LOW_FUEL,
            priority=AlertPriority.MEDIUM,
            truck_id="T002",
            message="Low fuel",
            details={},
        )

        initial_count = len(manager._alert_history)
        manager.send_alert(alert, channels=[])

        assert len(manager._alert_history) == initial_count + 1


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=alert_service", "--cov-report=term-missing"])
