"""
Tests for Centralized Error Handling (v3.12.21)
Covers: #9 Centralized error handling
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


class TestCustomExceptions:
    """Test custom exception classes"""

    def test_fuel_copilot_error_creation(self):
        """Should create base error with message"""
        from errors import FuelCopilotError, ErrorCategory

        error = FuelCopilotError("Something went wrong")

        assert error.message == "Something went wrong"
        assert error.status_code == 500
        assert error.category == ErrorCategory.INTERNAL

    def test_fuel_copilot_error_with_custom_values(self):
        """Should create error with custom status and category"""
        from errors import FuelCopilotError, ErrorCategory

        error = FuelCopilotError(
            "Custom error", status_code=400, category=ErrorCategory.VALIDATION
        )

        assert error.status_code == 400
        assert error.category == ErrorCategory.VALIDATION

    def test_database_error(self):
        """Should create database error"""
        from errors import DatabaseError, ErrorCategory

        error = DatabaseError("Connection failed")

        assert error.message == "Connection failed"
        assert error.status_code == 503
        assert error.category == ErrorCategory.DATABASE

    def test_authentication_error(self):
        """Should create authentication error"""
        from errors import AuthenticationError, ErrorCategory

        error = AuthenticationError("Invalid token")

        assert error.status_code == 401
        assert error.category == ErrorCategory.AUTHENTICATION

    def test_validation_error(self):
        """Should create validation error"""
        from errors import ValidationError, ErrorCategory

        error = ValidationError("Invalid input", field="truck_id")

        assert error.status_code == 400
        assert error.category == ErrorCategory.VALIDATION
        assert error.details["field"] == "truck_id"

    def test_rate_limit_error(self):
        """Should create rate limit error with limit and window"""
        from errors import RateLimitError, ErrorCategory

        error = RateLimitError(limit=100, window_seconds=60, retry_after=30)

        assert error.status_code == 429
        assert error.category == ErrorCategory.RATE_LIMIT
        assert error.details["retry_after"] == 30

    def test_external_service_error(self):
        """Should create external service error"""
        from errors import ExternalServiceError, ErrorCategory

        error = ExternalServiceError(service="Wialon", message="API failed")

        assert error.status_code == 502
        assert error.category == ErrorCategory.EXTERNAL_SERVICE
        assert error.details["service"] == "Wialon"

    def test_not_found_error(self):
        """Should create not found error"""
        from errors import NotFoundError, ErrorCategory

        error = NotFoundError(resource="truck", resource_id="JC1282")

        assert error.status_code == 404
        assert error.category == ErrorCategory.NOT_FOUND
        assert error.details["resource"] == "truck"
        assert error.details["resource_id"] == "JC1282"


class TestErrorResponseBuilder:
    """Test error response builder function"""

    def test_build_response_from_fuel_copilot_error(self):
        """Should build response from FuelCopilotError"""
        from errors import FuelCopilotError, build_error_response

        error = FuelCopilotError("Test error")
        response = build_error_response(error)

        assert response["error"] is True
        assert response["message"] == "Test error"
        assert response["status_code"] == 500
        assert "timestamp" in response

    def test_build_response_from_database_error(self):
        """Should build response from DatabaseError"""
        from errors import DatabaseError, build_error_response

        error = DatabaseError("Connection lost")
        response = build_error_response(error)

        assert response["category"] == "database"
        assert response["status_code"] == 503

    def test_build_response_with_details(self):
        """Should include error details"""
        from errors import ValidationError, build_error_response

        error = ValidationError("Invalid value", field="mpg")
        response = build_error_response(error)

        assert response["details"]["field"] == "mpg"


class TestErrorHandlers:
    """Test exception handler registration"""

    @pytest.fixture
    def app_with_handlers(self):
        """Create FastAPI app with error handlers"""
        from errors import register_exception_handlers, FuelCopilotError, DatabaseError

        app = FastAPI()
        register_exception_handlers(app)

        @app.get("/test-internal-error")
        async def trigger_internal_error():
            raise FuelCopilotError("Internal error test")

        @app.get("/test-db-error")
        async def trigger_db_error():
            raise DatabaseError("Database connection failed")

        return app

    def test_internal_error_handler(self, app_with_handlers):
        """Should handle FuelCopilotError correctly"""
        client = TestClient(app_with_handlers)

        response = client.get("/test-internal-error")

        assert response.status_code == 500
        data = response.json()
        assert data["error"] is True
        assert data["message"] == "Internal error test"

    def test_database_error_handler(self, app_with_handlers):
        """Should handle DatabaseError correctly"""
        client = TestClient(app_with_handlers)

        response = client.get("/test-db-error")

        assert response.status_code == 503
        data = response.json()
        assert data["error"] is True
        assert "Database connection failed" in data["message"]


class TestErrorCategories:
    """Test error categories"""

    def test_all_categories_defined(self):
        """Should have all expected error categories"""
        from errors import ErrorCategory

        expected = [
            "database",
            "validation",
            "authentication",
            "authorization",
            "external_service",
            "internal",
            "rate_limit",
            "not_found",
        ]

        for cat in expected:
            assert hasattr(ErrorCategory, cat.upper())


class TestBuildErrorResponseHTTPException:
    """Test build_error_response with HTTPException"""

    def test_build_response_from_http_exception(self):
        """Should build response from HTTPException"""
        from fastapi import HTTPException
        from errors import build_error_response

        error = HTTPException(status_code=404, detail="Not found")
        response = build_error_response(error)

        assert response["error"] is True
        assert response["category"] == "http"
        assert response["message"] == "Not found"
        assert response["status_code"] == 404
        assert "timestamp" in response

    def test_build_response_from_generic_exception(self):
        """Should build response from generic Exception"""
        from errors import build_error_response

        error = ValueError("Something bad happened")
        response = build_error_response(error)

        assert response["error"] is True
        assert response["category"] == "internal"
        assert response["message"] == "Something bad happened"
        assert response["status_code"] == 500

    def test_build_response_with_empty_message(self):
        """Should handle exception with empty message"""
        from errors import build_error_response

        error = Exception("")
        response = build_error_response(error)

        assert response["error"] is True
        assert response["message"] == "An unexpected error occurred"

    def test_build_response_with_request_id(self):
        """Should include request_id when provided"""
        from errors import FuelCopilotError, build_error_response

        error = FuelCopilotError("Test")
        response = build_error_response(error, request_id="req-123")

        assert response["request_id"] == "req-123"

    def test_build_response_with_trace(self):
        """Should include trace when requested"""
        from errors import FuelCopilotError, build_error_response

        error = FuelCopilotError("Test")
        response = build_error_response(error, include_trace=True)

        assert "trace" in response


class TestHandleErrorsDecorator:
    """Test handle_errors decorator"""

    def test_handle_errors_async_fuel_copilot_error(self):
        """Should handle FuelCopilotError in async function"""
        import asyncio
        from errors import handle_errors, ValidationError
        from fastapi import HTTPException

        @handle_errors(logger_name="test")
        async def test_func():
            raise ValidationError("Invalid input", field="test")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(test_func())

        assert exc_info.value.status_code == 400

    def test_handle_errors_async_generic_exception(self):
        """Should handle generic exception in async function"""
        import asyncio
        from errors import handle_errors
        from fastapi import HTTPException

        @handle_errors(logger_name="test", default_message="Something failed")
        async def test_func():
            raise RuntimeError("Unexpected error")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(test_func())

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Something failed"

    def test_handle_errors_async_http_exception_passthrough(self):
        """Should pass through HTTPException unchanged"""
        import asyncio
        from errors import handle_errors
        from fastapi import HTTPException

        @handle_errors(logger_name="test")
        async def test_func():
            raise HTTPException(status_code=403, detail="Forbidden")

        with pytest.raises(HTTPException) as exc_info:
            asyncio.get_event_loop().run_until_complete(test_func())

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == "Forbidden"

    def test_handle_errors_sync_fuel_copilot_error(self):
        """Should handle FuelCopilotError in sync function"""
        from errors import handle_errors, DatabaseError
        from fastapi import HTTPException

        @handle_errors(logger_name="test")
        def test_func():
            raise DatabaseError("Connection failed")

        with pytest.raises(HTTPException) as exc_info:
            test_func()

        assert exc_info.value.status_code == 503

    def test_handle_errors_sync_generic_exception(self):
        """Should handle generic exception in sync function"""
        from errors import handle_errors
        from fastapi import HTTPException

        @handle_errors(logger_name="test", default_message="Error occurred")
        def test_func():
            raise ValueError("Bad value")

        with pytest.raises(HTTPException) as exc_info:
            test_func()

        assert exc_info.value.status_code == 500
        assert exc_info.value.detail == "Error occurred"

    def test_handle_errors_sync_http_exception_passthrough(self):
        """Should pass through HTTPException in sync function"""
        from errors import handle_errors
        from fastapi import HTTPException

        @handle_errors(logger_name="test")
        def test_func():
            raise HTTPException(status_code=401, detail="Unauthorized")

        with pytest.raises(HTTPException) as exc_info:
            test_func()

        assert exc_info.value.status_code == 401

    def test_handle_errors_without_reraise(self):
        """Should not convert to HTTPException when reraise=False"""
        from errors import handle_errors, ValidationError

        @handle_errors(logger_name="test", reraise=False)
        def test_func():
            raise ValidationError("Test error")

        with pytest.raises(ValidationError):
            test_func()

    def test_handle_errors_async_without_reraise(self):
        """Should not convert to HTTPException when reraise=False (async)"""
        import asyncio
        from errors import handle_errors, DatabaseError

        @handle_errors(logger_name="test", reraise=False)
        async def test_func():
            raise DatabaseError("DB error")

        with pytest.raises(DatabaseError):
            asyncio.get_event_loop().run_until_complete(test_func())

    def test_handle_errors_success(self):
        """Should return result on success"""
        import asyncio
        from errors import handle_errors

        @handle_errors()
        async def test_func():
            return {"status": "ok"}

        result = asyncio.get_event_loop().run_until_complete(test_func())
        assert result["status"] == "ok"

    def test_handle_errors_sync_success(self):
        """Should return result on success (sync)"""
        from errors import handle_errors

        @handle_errors()
        def test_func():
            return {"status": "ok"}

        result = test_func()
        assert result["status"] == "ok"


class TestAuthorizationError:
    """Test AuthorizationError"""

    def test_authorization_error_default_message(self):
        """Should use default message"""
        from errors import AuthorizationError, ErrorCategory

        error = AuthorizationError()

        assert error.message == "Insufficient permissions"
        assert error.status_code == 403
        assert error.category == ErrorCategory.AUTHORIZATION

    def test_authorization_error_custom_message(self):
        """Should accept custom message"""
        from errors import AuthorizationError

        error = AuthorizationError("Admin access required")

        assert error.message == "Admin access required"


class TestRateLimitErrorWithoutRetryAfter:
    """Test RateLimitError without retry_after"""

    def test_rate_limit_error_without_retry_after(self):
        """Should work without retry_after"""
        from errors import RateLimitError

        error = RateLimitError(limit=50, window_seconds=30)

        assert error.details["limit"] == 50
        assert error.details["window_seconds"] == 30
        assert "retry_after" not in error.details


class TestNotFoundErrorWithoutId:
    """Test NotFoundError without resource_id"""

    def test_not_found_error_without_id(self):
        """Should work without resource_id"""
        from errors import NotFoundError

        error = NotFoundError(resource="sensor")

        assert error.details["resource"] == "sensor"
        assert "resource_id" not in error.details


class TestValidationErrorWithoutField:
    """Test ValidationError without field"""

    def test_validation_error_without_field(self):
        """Should work without field"""
        from errors import ValidationError

        error = ValidationError("General validation error")

        assert error.message == "General validation error"
        assert "field" not in error.details


class TestExternalServiceErrorWithDetails:
    """Test ExternalServiceError with extra details"""

    def test_external_service_error_with_details(self):
        """Should include extra details"""
        from errors import ExternalServiceError

        error = ExternalServiceError(
            service="Twilio",
            message="SMS failed",
            details={"phone": "+1234567890", "error_code": "E001"},
        )

        assert error.details["service"] == "Twilio"
        assert error.details["phone"] == "+1234567890"
        assert error.details["error_code"] == "E001"


class TestUtcNow:
    """Test utc_now helper function"""

    def test_utc_now_returns_timezone_aware(self):
        """Should return timezone-aware datetime"""
        from errors import utc_now
        from datetime import timezone

        now = utc_now()

        assert now.tzinfo is not None
        assert now.tzinfo == timezone.utc
