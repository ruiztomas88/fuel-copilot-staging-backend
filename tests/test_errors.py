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
