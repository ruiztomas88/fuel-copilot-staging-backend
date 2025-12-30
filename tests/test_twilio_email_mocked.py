"""
Tests for Twilio and Email service implementations - with mocks
"""

from unittest.mock import MagicMock, Mock, patch

import pytest

from alert_service import (
    EmailAlertService,
    EmailConfig,
    TwilioAlertService,
    TwilioConfig,
)


class TestTwilioAlertServiceMocked:
    """Test TwilioAlertService with mocked Twilio client"""

    def test_send_sms_success(self):
        """Test successful SMS sending"""
        # Setup mock
        with patch("twilio.rest.Client") as mock_client_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_message.sid = "SM123456"
            mock_client.messages.create.return_value = mock_message
            mock_client_class.return_value = mock_client

            # Configure service
            config = TwilioConfig()
            config.account_sid = "ACxxx"
            config.auth_token = "token"
            config.from_number = "+1234567890"

            service = TwilioAlertService(config)

            # Test
            result = service.send_sms("+0987654321", "Test message")

            assert result is True
            assert mock_client.messages.create.called

    def test_send_sms_truncates_long_message(self):
        """Test that long SMS messages are truncated"""
        with patch("twilio.rest.Client") as mock_client_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_message.sid = "SM123"
            mock_client.messages.create.return_value = mock_message
            mock_client_class.return_value = mock_client

            config = TwilioConfig()
            config.account_sid = "ACxxx"
            config.auth_token = "token"
            config.from_number = "+1234567890"

            service = TwilioAlertService(config)

            # Create a message longer than 1600 chars
            long_message = "x" * 1700

            result = service.send_sms("+0987654321", long_message)

            assert result is True

            # Verify message was truncated
            call_args = mock_client.messages.create.call_args
            sent_message = call_args[1]["body"]
            assert len(sent_message) <= 1600
            assert sent_message.endswith("...")

    def test_send_sms_failure(self):
        """Test SMS sending failure"""
        with patch("twilio.rest.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("Network error")
            mock_client_class.return_value = mock_client

            config = TwilioConfig()
            config.account_sid = "ACxxx"
            config.auth_token = "token"
            config.from_number = "+1234567890"

            service = TwilioAlertService(config)

            result = service.send_sms("+0987654321", "Test")

            assert result is False

    def test_send_whatsapp_success(self):
        """Test successful WhatsApp sending"""
        with patch("twilio.rest.Client") as mock_client_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_message.sid = "SM789"
            mock_client.messages.create.return_value = mock_message
            mock_client_class.return_value = mock_client

            config = TwilioConfig()
            config.account_sid = "ACxxx"
            config.auth_token = "token"
            config.from_number = "+1234567890"
            config.whatsapp_from = "+1234567890"

            service = TwilioAlertService(config)

            result = service.send_whatsapp("+0987654321", "Test WhatsApp")

            assert result is True

    def test_send_whatsapp_not_configured(self):
        """Test WhatsApp when whatsapp_from is not configured"""
        with patch("twilio.rest.Client") as mock_client_class:
            mock_client = Mock()
            mock_client_class.return_value = mock_client

            config = TwilioConfig()
            config.account_sid = "ACxxx"
            config.auth_token = "token"
            config.from_number = "+1234567890"
            config.whatsapp_from = ""  # Not configured

            service = TwilioAlertService(config)

            result = service.send_whatsapp("+0987654321", "Test")

            assert result is False

    def test_send_whatsapp_failure(self):
        """Test WhatsApp sending failure"""
        with patch("twilio.rest.Client") as mock_client_class:
            mock_client = Mock()
            mock_client.messages.create.side_effect = Exception("API error")
            mock_client_class.return_value = mock_client

            config = TwilioConfig()
            config.account_sid = "ACxxx"
            config.auth_token = "token"
            config.from_number = "+1234567890"
            config.whatsapp_from = "+1234567890"

            service = TwilioAlertService(config)

            result = service.send_whatsapp("+0987654321", "Test")

            assert result is False

    def test_broadcast_sms_success(self):
        """Test broadcasting SMS to multiple numbers"""
        with patch("twilio.rest.Client") as mock_client_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_message.sid = "SMxxx"
            mock_client.messages.create.return_value = mock_message
            mock_client_class.return_value = mock_client

            config = TwilioConfig()
            config.account_sid = "ACxxx"
            config.auth_token = "token"
            config.from_number = "+1234567890"
            config.to_numbers = ["+1111111111", "+2222222222", "+3333333333"]

            service = TwilioAlertService(config)

            results = service.broadcast_sms("Broadcast test")

            assert len(results) == 3
            assert all(results.values())  # All should be True

    def test_broadcast_sms_no_numbers_configured(self):
        """Test broadcast when no numbers are configured"""
        config = TwilioConfig()
        config.account_sid = "ACxxx"
        config.auth_token = "token"
        config.from_number = "+1234567890"
        config.to_numbers = []  # Empty

        service = TwilioAlertService(config)

        results = service.broadcast_sms("Test")

        assert results == {}

    def test_broadcast_sms_explicit_numbers(self):
        """Test broadcast with explicit number list"""
        with patch("twilio.rest.Client") as mock_client_class:
            mock_client = Mock()
            mock_message = Mock()
            mock_message.sid = "SMyyy"
            mock_client.messages.create.return_value = mock_message
            mock_client_class.return_value = mock_client

            config = TwilioConfig()
            config.account_sid = "ACxxx"
            config.auth_token = "token"
            config.from_number = "+1234567890"

            service = TwilioAlertService(config)

            results = service.broadcast_sms(
                "Test", numbers=["+1111111111", "+2222222222"]
            )

            assert len(results) == 2


class TestEmailAlertServiceMocked:
    """Test EmailAlertService with mocked SMTP"""

    @patch("alert_service.smtplib.SMTP")
    def test_send_email_success(self, mock_smtp_class):
        """Test successful email sending"""
        mock_smtp = Mock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        config = EmailConfig()
        config.smtp_server = "smtp.test.com"
        config.smtp_user = "user@test.com"
        config.smtp_pass = "password"
        config.to_email = "recipient@test.com"

        service = EmailAlertService(config)

        result = service.send_email("Test Subject", "Test Body")

        assert result is True
        assert mock_smtp.starttls.called
        assert mock_smtp.login.called
        assert mock_smtp.send_message.called

    @patch("alert_service.smtplib.SMTP")
    def test_send_email_with_html(self, mock_smtp_class):
        """Test email sending with HTML body"""
        mock_smtp = Mock()
        mock_smtp_class.return_value.__enter__.return_value = mock_smtp

        config = EmailConfig()
        config.smtp_server = "smtp.test.com"
        config.smtp_user = "user@test.com"
        config.smtp_pass = "password"
        config.to_email = "recipient@test.com"

        service = EmailAlertService(config)

        result = service.send_email(
            "Test Subject", "Plain text body", "<html><body>HTML body</body></html>"
        )

        assert result is True

    @patch("alert_service.smtplib.SMTP")
    def test_send_email_failure(self, mock_smtp_class):
        """Test email sending failure"""
        mock_smtp_class.return_value.__enter__.side_effect = Exception(
            "SMTP connection failed"
        )

        config = EmailConfig()
        config.smtp_server = "smtp.test.com"
        config.smtp_user = "user@test.com"
        config.smtp_pass = "password"
        config.to_email = "recipient@test.com"

        service = EmailAlertService(config)

        result = service.send_email("Subject", "Body")

        assert result is False
