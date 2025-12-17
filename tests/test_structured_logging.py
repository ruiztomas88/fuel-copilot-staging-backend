"""
Tests for Structured Logging Module
"""

import pytest
import json
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from structured_logging import (
    JSONFormatter,
    ConsoleFormatter,
    setup_logging,
    get_logger,
    set_correlation_id,
    get_correlation_id,
    generate_correlation_id,
    correlation_id_var,
    log_execution,
)


class TestJSONFormatter:
    """Tests for JSON log formatting"""

    def test_formats_as_json(self):
        """Output should be valid JSON"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["message"] == "Test message"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test"

    def test_includes_timestamp(self):
        """Output should include ISO timestamp"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "timestamp" in parsed
        assert "T" in parsed["timestamp"]  # ISO format

    def test_includes_source_location(self):
        """Output should include file/line/function"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "source" in parsed
        assert parsed["source"]["line"] == 42
        assert parsed["source"]["function"] == "test_function"

    def test_includes_correlation_id(self):
        """Output should include correlation ID when set"""
        formatter = JSONFormatter()

        # Set correlation ID
        set_correlation_id("test-123")

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed.get("correlation_id") == "test-123"

        # Cleanup
        correlation_id_var.set(None)

    def test_masks_sensitive_fields(self):
        """Sensitive fields should be masked"""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.password = "secret123"
        record.api_key = "key123"
        record.normal_field = "visible"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed.get("password") == "***MASKED***"
        assert parsed.get("api_key") == "***MASKED***"
        assert parsed.get("normal_field") == "visible"

    def test_includes_exception_info(self):
        """Exception info should be included"""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"
        assert "Test error" in parsed["exception"]["message"]


class TestCorrelationId:
    """Tests for correlation ID functionality"""

    def test_generate_creates_uuid(self):
        """Generated ID should be UUID-like"""
        id1 = generate_correlation_id()
        id2 = generate_correlation_id()

        assert len(id1) == 36  # UUID format
        assert id1 != id2

    def test_set_and_get(self):
        """Can set and retrieve correlation ID"""
        set_correlation_id("my-id-123")
        assert get_correlation_id() == "my-id-123"

        # Cleanup
        correlation_id_var.set(None)

    def test_set_generates_if_none(self):
        """Set without argument generates new ID"""
        correlation_id_var.set(None)

        new_id = set_correlation_id()

        assert new_id is not None
        assert len(new_id) == 36
        assert get_correlation_id() == new_id

        # Cleanup
        correlation_id_var.set(None)


class TestSetupLogging:
    """Tests for logging setup"""

    def test_sets_log_level(self):
        """Should set correct log level"""
        setup_logging(level="DEBUG", format_type="console")

        logger = logging.getLogger()
        assert logger.level == logging.DEBUG

    def test_uses_json_format(self):
        """Should use JSON formatter when specified"""
        setup_logging(format_type="json")

        logger = logging.getLogger()
        handler = logger.handlers[0]

        assert isinstance(handler.formatter, JSONFormatter)

    def test_uses_console_format(self):
        """Should use console formatter when specified"""
        setup_logging(format_type="console")

        logger = logging.getLogger()
        handler = logger.handlers[0]

        assert isinstance(handler.formatter, ConsoleFormatter)


class TestLogExecutionDecorator:
    """Tests for log_execution decorator"""

    def test_logs_function_execution(self, capsys):
        """Should log start and end of function"""
        setup_logging(level="INFO", format_type="console")

        @log_execution()
        def sample_function():
            return 42

        result = sample_function()

        captured = capsys.readouterr()
        assert result == 42
        assert "Starting sample_function" in captured.out
        assert "Completed sample_function" in captured.out

    def test_logs_duration(self, capsys):
        """Should log execution duration"""
        import time

        setup_logging(level="INFO", format_type="console")

        @log_execution()
        def slow_function():
            time.sleep(0.1)
            return "done"

        slow_function()

        captured = capsys.readouterr()
        assert "duration_ms" in captured.out or "Completed" in captured.out

    def test_logs_exceptions(self, capsys):
        """Should log exceptions"""
        setup_logging(level="ERROR", format_type="console")

        @log_execution()
        def failing_function():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            failing_function()

        captured = capsys.readouterr()
        assert "Failed failing_function" in captured.out


class TestGetLogger:
    """Tests for get_logger function"""

    def test_returns_logger(self):
        """Should return logger instance"""
        logger = get_logger("test.module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_same_name_same_logger(self):
        """Same name should return same logger"""
        logger1 = get_logger("test.same")
        logger2 = get_logger("test.same")

        assert logger1 is logger2


# ═══════════════════════════════════════════════════════════════════════════════
# EXTENDED TESTS FOR STRUCTURED LOGGING
# ═══════════════════════════════════════════════════════════════════════════════


class TestJSONFormatterExtended:
    """Extended tests for JSONFormatter"""

    @pytest.fixture
    def formatter(self):
        return JSONFormatter()

    def test_format_masks_password(self, formatter):
        """Password fields should be masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Login",
            args=(),
            exc_info=None,
        )
        record.password = "secret123"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["password"] == "***MASKED***"

    def test_format_masks_token(self, formatter):
        """Token fields should be masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Auth",
            args=(),
            exc_info=None,
        )
        record.token = "jwt_token_here"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["token"] == "***MASKED***"

    def test_format_masks_secret(self, formatter):
        """Secret fields should be masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Config",
            args=(),
            exc_info=None,
        )
        record.secret = "my_secret"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["secret"] == "***MASKED***"

    def test_format_masks_api_key(self, formatter):
        """API key fields should be masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="API call",
            args=(),
            exc_info=None,
        )
        record.api_key = "key123"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["api_key"] == "***MASKED***"

    def test_format_masks_authorization(self, formatter):
        """Authorization fields should be masked"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Request",
            args=(),
            exc_info=None,
        )
        record.authorization = "Bearer token"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["authorization"] == "***MASKED***"

    def test_format_includes_source(self, formatter):
        """Should include source location"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "source" in parsed
        assert parsed["source"]["line"] == 42

    def test_serialize_datetime(self, formatter):
        """Should serialize datetime values"""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc)
        result = formatter._serialize_value(now)

        assert isinstance(result, str)
        assert "T" in result  # ISO format

    def test_serialize_list(self, formatter):
        """Should serialize list values"""
        result = formatter._serialize_value([1, 2, 3])

        assert result == [1, 2, 3]

    def test_serialize_nested_dict(self, formatter):
        """Should serialize nested dicts"""
        data = {"outer": {"inner": "value"}}
        result = formatter._serialize_value(data)

        assert result["outer"]["inner"] == "value"

    def test_serialize_custom_object(self, formatter):
        """Should convert custom objects to string"""

        class Custom:
            def __str__(self):
                return "custom_str"

        result = formatter._serialize_value(Custom())

        assert result == "custom_str"

    def test_format_with_exception(self, formatter):
        """Should include exception info"""
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error",
            args=(),
            exc_info=None,
        )

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            record.exc_info = sys.exc_info()

        output = formatter.format(record)
        parsed = json.loads(output)

        assert "exception" in parsed
        assert parsed["exception"]["type"] == "ValueError"

    def test_format_with_correlation_id(self, formatter):
        """Should include correlation ID when set"""
        correlation_id_var.set("test-correlation-123")

        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            parsed = json.loads(output)

            assert parsed["correlation_id"] == "test-correlation-123"
        finally:
            correlation_id_var.set(None)


class TestConsoleFormatterExtended:
    """Extended tests for ConsoleFormatter"""

    @pytest.fixture
    def formatter(self):
        return ConsoleFormatter()

    def test_includes_timestamp(self, formatter):
        """Should include timestamp in output"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert ":" in output  # Time format HH:MM:SS

    def test_includes_level(self, formatter):
        """Should include log level"""
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "WARNING" in output

    def test_includes_message(self, formatter):
        """Should include message"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="My custom message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        assert "My custom message" in output

    def test_with_correlation_prefix(self, formatter):
        """Should show correlation ID prefix"""
        correlation_id_var.set("abc12345-6789")

        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="Test",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)

            assert "abc12345" in output
        finally:
            correlation_id_var.set(None)

    def test_color_codes_defined(self, formatter):
        """Should have color codes for all levels"""
        assert "DEBUG" in formatter.COLORS
        assert "INFO" in formatter.COLORS
        assert "WARNING" in formatter.COLORS
        assert "ERROR" in formatter.COLORS
        assert "CRITICAL" in formatter.COLORS

    def test_extras_in_output(self, formatter):
        """Extra fields should appear in output"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.truck_id = "T001"

        output = formatter.format(record)

        assert "truck_id" in output


class TestCorrelationIdExtended:
    """Extended tests for correlation ID"""

    def test_generate_correlation_id(self):
        """Should generate valid UUID"""
        corr_id = generate_correlation_id()

        assert corr_id is not None
        assert len(corr_id) > 0

    def test_set_and_get_correlation_id(self):
        """Should set and retrieve correlation ID"""
        set_correlation_id("my-test-id")

        try:
            result = get_correlation_id()
            assert result == "my-test-id"
        finally:
            correlation_id_var.set(None)

    def test_correlation_id_default_none(self):
        """Default should be None"""
        correlation_id_var.set(None)

        result = get_correlation_id()

        assert result is None

    def test_correlation_id_isolation(self):
        """Each set should be isolated"""
        set_correlation_id("first")
        first = get_correlation_id()

        set_correlation_id("second")
        second = get_correlation_id()

        assert first == "first"
        assert second == "second"

        correlation_id_var.set(None)


class TestLogLevelsExtended:
    """Extended tests for log levels"""

    @pytest.fixture
    def formatter(self):
        return JSONFormatter()

    def test_debug_level(self, formatter):
        """DEBUG level format"""
        record = logging.LogRecord(
            name="test",
            level=logging.DEBUG,
            pathname="test.py",
            lineno=1,
            msg="Debug",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "DEBUG"

    def test_info_level(self, formatter):
        """INFO level format"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Info",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "INFO"

    def test_warning_level(self, formatter):
        """WARNING level format"""
        record = logging.LogRecord(
            name="test",
            level=logging.WARNING,
            pathname="test.py",
            lineno=1,
            msg="Warning",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "WARNING"

    def test_error_level(self, formatter):
        """ERROR level format"""
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "ERROR"

    def test_critical_level(self, formatter):
        """CRITICAL level format"""
        record = logging.LogRecord(
            name="test",
            level=logging.CRITICAL,
            pathname="test.py",
            lineno=1,
            msg="Critical",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["level"] == "CRITICAL"


class TestLogExtraFields:
    """Tests for extra fields in logs"""

    @pytest.fixture
    def formatter(self):
        return JSONFormatter()

    def test_string_extra(self, formatter):
        """Should include string extras"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.user_id = "user123"

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["user_id"] == "user123"

    def test_numeric_extra(self, formatter):
        """Should include numeric extras"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.count = 42
        record.price = 19.99

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["count"] == 42
        assert parsed["price"] == 19.99

    def test_boolean_extra(self, formatter):
        """Should include boolean extras"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.is_active = True
        record.is_deleted = False

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["is_active"] is True
        assert parsed["is_deleted"] is False

    def test_list_extra(self, formatter):
        """Should include list extras"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.tags = ["urgent", "production"]

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["tags"] == ["urgent", "production"]

    def test_dict_extra(self, formatter):
        """Should include dict extras"""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )
        record.metadata = {"key": "value"}

        output = formatter.format(record)
        parsed = json.loads(output)

        assert parsed["metadata"]["key"] == "value"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
