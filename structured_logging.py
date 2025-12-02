"""
Structured Logging Module for Fuel Copilot v3.7.0

Provides JSON-formatted logging for production environments.
Compatible with ELK Stack, CloudWatch, Datadog, etc.

Features:
- JSON format for log aggregation
- Correlation IDs for request tracing
- Performance metrics in logs
- Sensitive data masking
- Log level configuration via environment

Usage:
    from structured_logging import setup_logging, get_logger, correlation_id_var

    setup_logging()
    logger = get_logger(__name__)

    logger.info("Processing truck", extra={"truck_id": "NQ6975", "fuel_pct": 75.5})
"""

import logging
import json
import sys
import os
import uuid
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from contextvars import ContextVar
from functools import wraps
import traceback

# Context variable for correlation ID (thread-safe)
correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)


class JSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.

    Output format:
    {
        "timestamp": "2025-11-26T12:00:00.000Z",
        "level": "INFO",
        "logger": "fuel_copilot",
        "message": "Processing truck",
        "correlation_id": "abc-123",
        "truck_id": "NQ6975",
        "duration_ms": 45.2
    }
    """

    # Fields to mask in logs (security)
    SENSITIVE_FIELDS = {"password", "token", "secret", "api_key", "authorization"}

    def format(self, record: logging.LogRecord) -> str:
        # Base log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add correlation ID if available
        correlation_id = correlation_id_var.get()
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        # Add source location
        log_entry["source"] = {
            "file": record.filename,
            "line": record.lineno,
            "function": record.funcName,
        }

        # Add extra fields from record
        if hasattr(record, "__dict__"):
            for key, value in record.__dict__.items():
                if key not in {
                    "name",
                    "msg",
                    "args",
                    "created",
                    "filename",
                    "funcName",
                    "levelname",
                    "levelno",
                    "lineno",
                    "module",
                    "msecs",
                    "pathname",
                    "process",
                    "processName",
                    "relativeCreated",
                    "stack_info",
                    "exc_info",
                    "exc_text",
                    "thread",
                    "threadName",
                    "message",
                    "asctime",
                }:
                    # Mask sensitive fields
                    if key.lower() in self.SENSITIVE_FIELDS:
                        log_entry[key] = "***MASKED***"
                    else:
                        log_entry[key] = self._serialize_value(value)

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": (
                    traceback.format_exception(*record.exc_info)
                    if record.exc_info[0]
                    else None
                ),
            }

        return json.dumps(log_entry, default=str, ensure_ascii=False)

    def _serialize_value(self, value: Any) -> Any:
        """Serialize value for JSON"""
        if isinstance(value, (str, int, float, bool, type(None))):
            return value
        elif isinstance(value, (list, tuple)):
            return [self._serialize_value(v) for v in value]
        elif isinstance(value, dict):
            return {k: self._serialize_value(v) for k, v in value.items()}
        elif isinstance(value, datetime):
            return value.isoformat()
        else:
            return str(value)


class ConsoleFormatter(logging.Formatter):
    """
    Human-readable formatter for development.
    Uses colors if terminal supports it.
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        # Add correlation ID prefix
        correlation_id = correlation_id_var.get()
        prefix = f"[{correlation_id[:8]}] " if correlation_id else ""

        # Color based on level
        color = self.COLORS.get(record.levelname, "")
        reset = self.RESET if color else ""

        # Format timestamp
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Build message
        message = f"{timestamp} {color}{record.levelname:8}{reset} {prefix}{record.getMessage()}"

        # Add extra fields
        extras = []
        for key, value in record.__dict__.items():
            if key not in {
                "name",
                "msg",
                "args",
                "created",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "exc_info",
                "exc_text",
                "thread",
                "threadName",
                "message",
                "asctime",
            }:
                extras.append(f"{key}={value}")

        if extras:
            message += f" | {' '.join(extras)}"

        # Add exception if present
        if record.exc_info:
            message += "\n" + "".join(traceback.format_exception(*record.exc_info))

        return message


def setup_logging(
    level: str = None,
    format_type: str = None,
    log_file: str = None,
) -> None:
    """
    Configure logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_type: "json" for structured or "console" for human-readable
        log_file: Optional file path for logging

    Environment variables:
        LOG_LEVEL: Set log level
        LOG_FORMAT: Set format (json or console)
    """
    # Get config from env or args
    level = level or os.getenv("LOG_LEVEL", "INFO").upper()
    format_type = format_type or os.getenv("LOG_FORMAT", "console").lower()

    # Create root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level, logging.INFO))

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create formatter
    if format_type == "json":
        formatter = JSONFormatter()
    else:
        formatter = ConsoleFormatter()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler (optional)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(JSONFormatter())  # Always JSON for files
        root_logger.addHandler(file_handler)

    # Reduce noise from third-party libraries
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name"""
    return logging.getLogger(name)


def generate_correlation_id() -> str:
    """Generate a new correlation ID"""
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: str = None) -> str:
    """Set correlation ID for current context"""
    if correlation_id is None:
        correlation_id = generate_correlation_id()
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID"""
    return correlation_id_var.get()


# ===========================================
# DECORATORS
# ===========================================


def log_execution(logger: logging.Logger = None, level: int = logging.INFO):
    """
    Decorator to log function execution with timing.

    Usage:
        @log_execution()
        def process_truck(truck_id):
            ...
    """

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            start_time = time.time()
            func_name = func.__name__

            logger.log(
                level,
                f"Starting {func_name}",
                extra={
                    "function": func_name,
                    "args_count": len(args),
                    "kwargs_keys": list(kwargs.keys()),
                },
            )

            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                logger.log(
                    level,
                    f"Completed {func_name}",
                    extra={
                        "function": func_name,
                        "duration_ms": round(duration_ms, 2),
                        "success": True,
                    },
                )

                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                logger.error(
                    f"Failed {func_name}",
                    extra={
                        "function": func_name,
                        "duration_ms": round(duration_ms, 2),
                        "success": False,
                        "error": str(e),
                    },
                    exc_info=True,
                )

                raise

        return wrapper

    return decorator


def log_execution_async(logger: logging.Logger = None, level: int = logging.INFO):
    """Async version of log_execution decorator"""

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            start_time = time.time()
            func_name = func.__name__

            logger.log(
                level,
                f"Starting {func_name}",
                extra={
                    "function": func_name,
                },
            )

            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                logger.log(
                    level,
                    f"Completed {func_name}",
                    extra={
                        "function": func_name,
                        "duration_ms": round(duration_ms, 2),
                        "success": True,
                    },
                )

                return result
            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000

                logger.error(
                    f"Failed {func_name}",
                    extra={
                        "function": func_name,
                        "duration_ms": round(duration_ms, 2),
                        "error": str(e),
                    },
                    exc_info=True,
                )

                raise

        return wrapper

    return decorator


# ===========================================
# FASTAPI MIDDLEWARE
# ===========================================


class LoggingMiddleware:
    """
    FastAPI middleware for request/response logging with correlation IDs.

    Usage:
        from structured_logging import LoggingMiddleware
        app.add_middleware(LoggingMiddleware)
    """

    def __init__(self, app):
        self.app = app
        self.logger = get_logger("api.request")

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        # Generate or extract correlation ID
        headers = dict(scope.get("headers", []))
        correlation_id = (
            headers.get(b"x-correlation-id", b"").decode() or generate_correlation_id()
        )
        set_correlation_id(correlation_id)

        # Extract request info
        method = scope.get("method", "")
        path = scope.get("path", "")
        query_string = scope.get("query_string", b"").decode()
        client = scope.get("client", ("", 0))

        start_time = time.time()
        status_code = 500

        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                # Add correlation ID to response headers
                headers = list(message.get("headers", []))
                headers.append((b"x-correlation-id", correlation_id.encode()))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            duration_ms = (time.time() - start_time) * 1000

            # Log request
            log_level = logging.WARNING if status_code >= 400 else logging.INFO
            self.logger.log(
                log_level,
                f"{method} {path}",
                extra={
                    "method": method,
                    "path": path,
                    "query_string": query_string,
                    "status_code": status_code,
                    "duration_ms": round(duration_ms, 2),
                    "client_ip": client[0],
                    "correlation_id": correlation_id,
                },
            )


# ===========================================
# EXAMPLE USAGE
# ===========================================

if __name__ == "__main__":
    # Setup logging
    setup_logging(level="DEBUG", format_type="console")

    logger = get_logger(__name__)

    # Set correlation ID
    set_correlation_id("test-123")

    # Log examples
    logger.debug("Debug message")
    logger.info("Processing truck", extra={"truck_id": "NQ6975", "fuel_pct": 75.5})
    logger.warning(
        "High drift detected", extra={"truck_id": "RT9127", "drift_pct": 8.5}
    )
    logger.error(
        "Database connection failed", extra={"host": "localhost", "port": 3306}
    )

    # Test decorator
    @log_execution()
    def example_function(x, y):
        return x + y

    result = example_function(1, 2)

    # Test JSON format
    print("\n--- JSON Format ---")
    setup_logging(format_type="json")
    logger.info("JSON formatted log", extra={"value": 42})
