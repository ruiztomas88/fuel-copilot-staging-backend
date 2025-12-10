"""
Centralized Error Handling for Fuel Copilot API
🆕 v3.12.21: Provides consistent error responses and logging

Features:
- Standardized error response format
- Automatic error logging with context
- Exception mapping to HTTP status codes
- Retry logic for transient errors
"""

import logging
import traceback
from typing import Optional, Dict, Any, Type
from functools import wraps
from datetime import datetime, timezone
from enum import Enum

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


# Helper for timezone-aware UTC datetime
def utc_now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


# =============================================================================
# Error Categories
# =============================================================================


class ErrorCategory(str, Enum):
    """Categories for error classification"""

    DATABASE = "database"
    VALIDATION = "validation"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    EXTERNAL_SERVICE = "external_service"
    INTERNAL = "internal"
    RATE_LIMIT = "rate_limit"
    NOT_FOUND = "not_found"


# =============================================================================
# Custom Exceptions
# =============================================================================


class FuelCopilotError(Exception):
    """Base exception for Fuel Copilot"""

    def __init__(
        self,
        message: str,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.category = category
        self.status_code = status_code
        self.details = details or {}
        self.timestamp = utc_now().isoformat()


class DatabaseError(FuelCopilotError):
    """Database-related errors"""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            category=ErrorCategory.DATABASE,
            status_code=503,
            details=details,
        )


class ValidationError(FuelCopilotError):
    """Input validation errors"""

    def __init__(self, message: str, field: str = None, details: Optional[Dict] = None):
        details = details or {}
        if field:
            details["field"] = field
        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            status_code=400,
            details=details,
        )


class NotFoundError(FuelCopilotError):
    """Resource not found errors"""

    def __init__(self, resource: str, resource_id: str = None):
        details = {"resource": resource}
        if resource_id:
            details["resource_id"] = resource_id
        super().__init__(
            message=f"{resource} not found",
            category=ErrorCategory.NOT_FOUND,
            status_code=404,
            details=details,
        )


class AuthenticationError(FuelCopilotError):
    """Authentication errors"""

    def __init__(self, message: str = "Authentication required"):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHENTICATION,
            status_code=401,
        )


class AuthorizationError(FuelCopilotError):
    """Authorization errors"""

    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            category=ErrorCategory.AUTHORIZATION,
            status_code=403,
        )


class ExternalServiceError(FuelCopilotError):
    """External service errors (Wialon, Twilio, etc.)"""

    def __init__(self, service: str, message: str, details: Optional[Dict] = None):
        details = details or {}
        details["service"] = service
        super().__init__(
            message=f"{service} error: {message}",
            category=ErrorCategory.EXTERNAL_SERVICE,
            status_code=502,
            details=details,
        )


class RateLimitError(FuelCopilotError):
    """Rate limit exceeded errors"""

    def __init__(self, limit: int, window_seconds: int, retry_after: int = None):
        details = {
            "limit": limit,
            "window_seconds": window_seconds,
        }
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(
            message=f"Rate limit exceeded: {limit} requests per {window_seconds}s",
            category=ErrorCategory.RATE_LIMIT,
            status_code=429,
            details=details,
        )


# =============================================================================
# Error Response Builder
# =============================================================================


def build_error_response(
    error: Exception,
    request_id: Optional[str] = None,
    include_trace: bool = False,
) -> Dict[str, Any]:
    """
    Build a standardized error response.

    Args:
        error: The exception to format
        request_id: Optional request ID for tracking
        include_trace: Whether to include stack trace (dev only)

    Returns:
        Dict with error details
    """
    if isinstance(error, FuelCopilotError):
        response = {
            "error": True,
            "category": error.category.value,
            "message": error.message,
            "status_code": error.status_code,
            "timestamp": error.timestamp,
            "details": error.details,
        }
    elif isinstance(error, HTTPException):
        response = {
            "error": True,
            "category": "http",
            "message": error.detail,
            "status_code": error.status_code,
            "timestamp": utc_now().isoformat(),
            "details": {},
        }
    else:
        response = {
            "error": True,
            "category": ErrorCategory.INTERNAL.value,
            "message": str(error) or "An unexpected error occurred",
            "status_code": 500,
            "timestamp": utc_now().isoformat(),
            "details": {},
        }

    if request_id:
        response["request_id"] = request_id

    if include_trace:
        response["trace"] = traceback.format_exc()

    return response


# =============================================================================
# Error Handler Decorator
# =============================================================================


def handle_errors(
    logger_name: str = None,
    default_message: str = "An error occurred",
    reraise: bool = True,
):
    """
    Decorator for consistent error handling in endpoint functions.

    Args:
        logger_name: Logger name for error logging
        default_message: Default message if error has none
        reraise: Whether to reraise as HTTPException

    Usage:
        @handle_errors(logger_name="api.trucks")
        async def get_truck(truck_id: str):
            ...
    """

    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            log = logging.getLogger(logger_name) if logger_name else logger
            try:
                return await func(*args, **kwargs)
            except FuelCopilotError as e:
                log.error(
                    f"{e.category.value}: {e.message}", extra={"details": e.details}
                )
                if reraise:
                    raise HTTPException(status_code=e.status_code, detail=e.message)
                raise
            except HTTPException:
                raise
            except Exception as e:
                log.exception(f"Unexpected error in {func.__name__}: {e}")
                if reraise:
                    raise HTTPException(status_code=500, detail=default_message)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            log = logging.getLogger(logger_name) if logger_name else logger
            try:
                return func(*args, **kwargs)
            except FuelCopilotError as e:
                log.error(
                    f"{e.category.value}: {e.message}", extra={"details": e.details}
                )
                if reraise:
                    raise HTTPException(status_code=e.status_code, detail=e.message)
                raise
            except HTTPException:
                raise
            except Exception as e:
                log.exception(f"Unexpected error in {func.__name__}: {e}")
                if reraise:
                    raise HTTPException(status_code=500, detail=default_message)
                raise

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


# =============================================================================
# Exception Handlers for FastAPI
# =============================================================================


async def fuel_copilot_exception_handler(
    request: Request, exc: FuelCopilotError
) -> JSONResponse:
    """Handle FuelCopilotError exceptions"""
    logger.error(
        f"[{exc.category.value}] {exc.message}",
        extra={
            "status_code": exc.status_code,
            "details": exc.details,
            "path": request.url.path,
        },
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=build_error_response(exc),
    )


async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions"""
    logger.exception(f"Unexpected error: {exc}", extra={"path": request.url.path})
    return JSONResponse(
        status_code=500,
        content=build_error_response(exc),
    )


def register_exception_handlers(app):
    """
    Register all exception handlers with a FastAPI app.

    Usage:
        from errors import register_exception_handlers
        register_exception_handlers(app)
    """
    app.add_exception_handler(FuelCopilotError, fuel_copilot_exception_handler)
    # Uncomment to handle all exceptions (be careful in production)
    # app.add_exception_handler(Exception, generic_exception_handler)
    logger.info("✅ Exception handlers registered")


# =============================================================================
# Exports
# =============================================================================

__all__ = [
    # Categories
    "ErrorCategory",
    # Exceptions
    "FuelCopilotError",
    "DatabaseError",
    "ValidationError",
    "NotFoundError",
    "AuthenticationError",
    "AuthorizationError",
    "ExternalServiceError",
    "RateLimitError",
    # Utilities
    "build_error_response",
    "handle_errors",
    "register_exception_handlers",
]
