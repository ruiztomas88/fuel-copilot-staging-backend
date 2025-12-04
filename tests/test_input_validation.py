"""
Tests for Input Validation Module v3.12.21
"""

import pytest
from datetime import datetime, timedelta
from pydantic import ValidationError

from input_validation import (
    # Sanitization
    sanitize_string,
    sanitize_truck_id,
    sanitize_carrier_id,
    sanitize_sql_like,
    # Enums
    AlertType,
    SortOrder,
    TruckStatus,
    UserRole,
    # Models
    PaginationParams,
    DateRangeParams,
    SortParams,
    TruckIdParam,
    TruckListParams,
    TruckMetricsRequest,
    RefuelEventCreate,
    RefuelListParams,
    AlertRequest,
    AlertListParams,
    AlertAcknowledge,
    LoginRequest,
    UserCreate,
    ReportRequest,
    # Validators
    validate_percentage,
    validate_positive_number,
    validate_date_not_future,
    validate_fuel_level,
    # Constants
    MAX_GALLONS,
    MAX_DAYS_RANGE,
)


class TestSanitization:
    """Test sanitization functions."""

    def test_sanitize_string_basic(self):
        """Test basic string sanitization."""
        assert sanitize_string("  hello  ") == "hello"
        assert sanitize_string("hello\x00world") == "helloworld"
        assert sanitize_string("a" * 300) == "a" * 255

    def test_sanitize_string_empty(self):
        """Test empty string handling."""
        assert sanitize_string("") == ""
        assert sanitize_string(None) == ""

    def test_sanitize_truck_id(self):
        """Test truck ID sanitization."""
        assert sanitize_truck_id("abc123") == "ABC123"
        assert sanitize_truck_id("abc-123") == "ABC123"
        assert sanitize_truck_id("  abc  ") == "ABC"
        assert sanitize_truck_id("") == ""

    def test_sanitize_carrier_id(self):
        """Test carrier ID sanitization."""
        assert sanitize_carrier_id("Test_Carrier") == "test_carrier"
        assert sanitize_carrier_id("test-carrier") == "test-carrier"
        assert sanitize_carrier_id("test@carrier!") == "testcarrier"

    def test_sanitize_sql_like(self):
        """Test SQL LIKE pattern escaping."""
        assert sanitize_sql_like("test%search") == "test\\%search"
        assert sanitize_sql_like("test_search") == "test\\_search"
        assert sanitize_sql_like("test\\search") == "test\\\\search"


class TestPaginationParams:
    """Test pagination parameters."""

    def test_default_values(self):
        """Test default pagination values."""
        params = PaginationParams()
        assert params.page == 1
        assert params.page_size == 50
        assert params.offset == 0

    def test_custom_values(self):
        """Test custom pagination values."""
        params = PaginationParams(page=3, page_size=25)
        assert params.page == 3
        assert params.page_size == 25
        assert params.offset == 50

    def test_invalid_page(self):
        """Test invalid page number."""
        with pytest.raises(ValidationError):
            PaginationParams(page=0)
        with pytest.raises(ValidationError):
            PaginationParams(page=-1)

    def test_invalid_page_size(self):
        """Test invalid page size."""
        with pytest.raises(ValidationError):
            PaginationParams(page_size=0)
        with pytest.raises(ValidationError):
            PaginationParams(page_size=1000)  # Too large


class TestDateRangeParams:
    """Test date range parameters."""

    def test_default_days(self):
        """Test default days value."""
        params = DateRangeParams()
        assert params.days == 7

    def test_custom_days(self):
        """Test custom days value."""
        params = DateRangeParams(days=30)
        assert params.days == 30

    def test_max_days(self):
        """Test maximum days limit."""
        with pytest.raises(ValidationError):
            DateRangeParams(days=400)  # Exceeds MAX_DAYS_RANGE

    def test_date_range_validation(self):
        """Test start_date before end_date."""
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)

        # Valid range
        params = DateRangeParams(start_date=yesterday, end_date=now)
        assert params.start_date < params.end_date

        # Invalid range (start after end)
        with pytest.raises(ValidationError):
            DateRangeParams(start_date=now, end_date=yesterday)


class TestTruckIdParam:
    """Test truck ID validation."""

    def test_valid_truck_id(self):
        """Test valid truck IDs."""
        assert TruckIdParam(truck_id="ABC123").truck_id == "ABC123"
        assert TruckIdParam(truck_id="ab12").truck_id == "AB12"

    def test_invalid_truck_id(self):
        """Test invalid truck IDs."""
        with pytest.raises(ValidationError):
            TruckIdParam(truck_id="a")  # Too short

        with pytest.raises(ValidationError):
            TruckIdParam(truck_id="")  # Empty


class TestRefuelEventCreate:
    """Test refuel event creation."""

    def test_valid_refuel(self):
        """Test valid refuel event."""
        event = RefuelEventCreate(
            truck_id="ABC123", gallons=50.5, location="Gas Station A", cost=175.25
        )
        assert event.truck_id == "ABC123"
        assert event.gallons == 50.5

    def test_invalid_gallons(self):
        """Test invalid gallons."""
        with pytest.raises(ValidationError):
            RefuelEventCreate(truck_id="ABC123", gallons=0)

        with pytest.raises(ValidationError):
            RefuelEventCreate(truck_id="ABC123", gallons=600)  # Exceeds MAX_GALLONS

    def test_optional_fields(self):
        """Test optional fields."""
        event = RefuelEventCreate(truck_id="ABC123", gallons=50)
        assert event.location is None
        assert event.cost is None
        assert event.notes is None


class TestAlertRequest:
    """Test alert request validation."""

    def test_valid_alert(self):
        """Test valid alert request."""
        alert = AlertRequest(
            truck_id="ABC123",
            alert_type=AlertType.LOW_FUEL,
            message="Low fuel warning",
            send_sms=True,
        )
        assert alert.truck_id == "ABC123"
        assert alert.alert_type == AlertType.LOW_FUEL

    def test_alert_types(self):
        """Test all alert types."""
        for alert_type in AlertType:
            alert = AlertRequest(truck_id="ABC123", alert_type=alert_type)
            assert alert.alert_type == alert_type


class TestLoginRequest:
    """Test login request validation."""

    def test_valid_login(self):
        """Test valid login."""
        login = LoginRequest(username="admin", password="password123")
        assert login.username == "admin"

    def test_invalid_username(self):
        """Test invalid username."""
        with pytest.raises(ValidationError):
            LoginRequest(username="ab", password="password123")  # Too short

    def test_invalid_password(self):
        """Test invalid password."""
        with pytest.raises(ValidationError):
            LoginRequest(username="admin", password="123")  # Too short


class TestUserCreate:
    """Test user creation validation."""

    def test_valid_user(self):
        """Test valid user creation."""
        user = UserCreate(
            username="newuser",
            password="Password123",
            role=UserRole.VIEWER,
            email="user@example.com",
        )
        assert user.username == "newuser"
        assert user.role == UserRole.VIEWER

    def test_password_requirements(self):
        """Test password requirements."""
        # Missing uppercase
        with pytest.raises(ValidationError):
            UserCreate(username="user", password="password123")

        # Missing lowercase
        with pytest.raises(ValidationError):
            UserCreate(username="user", password="PASSWORD123")

        # Missing digit
        with pytest.raises(ValidationError):
            UserCreate(username="user", password="Passwordabc")

        # Too short
        with pytest.raises(ValidationError):
            UserCreate(username="user", password="Pass1")

    def test_email_validation(self):
        """Test email validation."""
        # Valid email
        user = UserCreate(
            username="user", password="Password123", email="valid@example.com"
        )
        assert user.email == "valid@example.com"

        # Invalid email
        with pytest.raises(ValidationError):
            UserCreate(username="user", password="Password123", email="not-an-email")


class TestValidationHelpers:
    """Test validation helper functions."""

    def test_validate_percentage(self):
        """Test percentage validation."""
        assert validate_percentage(50.0) == 50.0
        assert validate_percentage(0) == 0
        assert validate_percentage(100) == 100

        with pytest.raises(ValueError):
            validate_percentage(-1)
        with pytest.raises(ValueError):
            validate_percentage(101)

    def test_validate_positive_number(self):
        """Test positive number validation."""
        assert validate_positive_number(10) == 10
        assert validate_positive_number(0) == 0

        with pytest.raises(ValueError):
            validate_positive_number(-1)

    def test_validate_date_not_future(self):
        """Test future date validation."""
        yesterday = datetime.utcnow() - timedelta(days=1)
        assert validate_date_not_future(yesterday) == yesterday

        tomorrow = datetime.utcnow() + timedelta(days=1)
        with pytest.raises(ValueError):
            validate_date_not_future(tomorrow)

    def test_validate_fuel_level(self):
        """Test fuel level validation."""
        result = validate_fuel_level(50, 200)
        assert result["level_pct"] == 50
        assert result["capacity_gal"] == 200
        assert result["level_gal"] == 100

        with pytest.raises(ValueError):
            validate_fuel_level(150)  # Over 100%


class TestSortParams:
    """Test sort parameters."""

    def test_valid_sort(self):
        """Test valid sort parameters."""
        params = SortParams(sort_by="created_at", sort_order=SortOrder.ASC)
        assert params.sort_by == "created_at"
        assert params.sort_order == SortOrder.ASC

    def test_invalid_sort_by(self):
        """Test invalid sort field."""
        with pytest.raises(ValidationError):
            SortParams(sort_by="DROP TABLE; --")  # SQL injection attempt


class TestReportRequest:
    """Test report request validation."""

    def test_valid_report(self):
        """Test valid report request."""
        report = ReportRequest(days=30, truck_ids=["ABC123", "XYZ789"], format="csv")
        assert report.days == 30
        assert len(report.truck_ids) == 2
        assert report.format == "csv"

    def test_truck_ids_sanitized(self):
        """Test truck IDs are sanitized."""
        report = ReportRequest(truck_ids=["abc-123", "xyz 789"])
        assert report.truck_ids == ["ABC123", "XYZ789"]

    def test_invalid_format(self):
        """Test invalid format."""
        with pytest.raises(ValidationError):
            ReportRequest(format="xml")  # Not allowed


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
