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


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
