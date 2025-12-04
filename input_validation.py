"""
Input Validation Module v3.12.21
Robust validation for all API inputs

Features:
- Pydantic V2 models for request validation
- Custom validators for domain-specific rules
- Sanitization functions
- Rate limit aware validation
"""

import re
from datetime import datetime, timedelta
from typing import Optional, List, Any, Union
from pydantic import BaseModel, Field, field_validator, model_validator
from enum import Enum


# ============================================
# Constants
# ============================================

# Truck ID patterns (adjust for your fleet naming convention)
TRUCK_ID_PATTERN = re.compile(r"^[A-Z0-9]{2,10}$")

# Carrier ID patterns
CARRIER_ID_PATTERN = re.compile(r"^[a-z0-9_-]{1,50}$")

# Username patterns
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_@.-]{3,50}$")

# Maximum values for safety
MAX_GALLONS = 500  # Max gallons per refuel
MAX_MPG = 20  # Max realistic MPG for heavy trucks
MAX_SPEED_MPH = 100  # Max realistic speed
MAX_DAYS_RANGE = 365  # Max days for queries
MAX_RESULTS = 10000  # Max results per query


# ============================================
# Enums
# ============================================


class AlertType(str, Enum):
    LOW_FUEL = "low_fuel"
    THEFT = "theft"
    REFUEL = "refuel"
    DRIFT = "drift"
    EFFICIENCY = "efficiency"


class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"


class TruckStatus(str, Enum):
    MOVING = "moving"
    STOPPED = "stopped"
    PARKED = "parked"
    OFFLINE = "offline"


class UserRole(str, Enum):
    SUPER_ADMIN = "super_admin"
    CARRIER_ADMIN = "carrier_admin"
    VIEWER = "viewer"


# ============================================
# Sanitization Functions
# ============================================


def sanitize_string(value: str, max_length: int = 255) -> str:
    """
    Sanitize a string input.
    - Strip whitespace
    - Remove control characters
    - Truncate to max length
    """
    if not value:
        return ""

    # Remove control characters except newlines and tabs
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", value)

    # Strip and truncate
    return sanitized.strip()[:max_length]


def sanitize_truck_id(truck_id: str) -> str:
    """
    Sanitize and normalize truck ID.
    - Uppercase
    - Remove special characters
    """
    if not truck_id:
        return ""
    return re.sub(r"[^A-Z0-9]", "", truck_id.upper())[:10]


def sanitize_carrier_id(carrier_id: str) -> str:
    """
    Sanitize and normalize carrier ID.
    - Lowercase
    - Allow only alphanumeric, underscore, hyphen
    """
    if not carrier_id:
        return ""
    return re.sub(r"[^a-z0-9_-]", "", carrier_id.lower())[:50]


def sanitize_sql_like(value: str) -> str:
    """
    Escape SQL LIKE wildcards for safe pattern matching.
    """
    if not value:
        return ""
    # Escape % and _ which are SQL wildcards
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


# ============================================
# Base Request Models
# ============================================


class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints."""

    page: int = Field(default=1, ge=1, le=10000, description="Page number")
    page_size: int = Field(default=50, ge=1, le=500, description="Items per page")

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class DateRangeParams(BaseModel):
    """Date range parameters for queries."""

    days: int = Field(default=7, ge=1, le=MAX_DAYS_RANGE, description="Number of days")
    start_date: Optional[datetime] = Field(default=None, description="Start date (UTC)")
    end_date: Optional[datetime] = Field(default=None, description="End date (UTC)")

    @model_validator(mode="after")
    def validate_date_range(self):
        if self.start_date and self.end_date:
            if self.start_date > self.end_date:
                raise ValueError("start_date must be before end_date")
            if (self.end_date - self.start_date).days > MAX_DAYS_RANGE:
                raise ValueError(f"Date range cannot exceed {MAX_DAYS_RANGE} days")
        return self


class SortParams(BaseModel):
    """Sorting parameters for list endpoints."""

    sort_by: str = Field(default="created_at", max_length=50)
    sort_order: SortOrder = Field(default=SortOrder.DESC)

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, v: str) -> str:
        # Only allow alphanumeric and underscore
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", v):
            raise ValueError("Invalid sort field")
        return v


# ============================================
# Truck Request Models
# ============================================


class TruckIdParam(BaseModel):
    """Single truck ID parameter."""

    truck_id: str = Field(..., min_length=2, max_length=10)

    @field_validator("truck_id")
    @classmethod
    def validate_truck_id(cls, v: str) -> str:
        sanitized = sanitize_truck_id(v)
        if not TRUCK_ID_PATTERN.match(sanitized):
            raise ValueError("Invalid truck ID format")
        return sanitized


class TruckListParams(PaginationParams, SortParams):
    """Parameters for listing trucks."""

    carrier_id: Optional[str] = Field(default=None, max_length=50)
    status: Optional[TruckStatus] = None
    search: Optional[str] = Field(default=None, max_length=100)

    @field_validator("carrier_id")
    @classmethod
    def validate_carrier_id(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_carrier_id(v)
        return v

    @field_validator("search")
    @classmethod
    def validate_search(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_string(v, 100)
        return v


class TruckMetricsRequest(DateRangeParams):
    """Request for truck metrics."""

    truck_id: str = Field(..., min_length=2, max_length=10)
    include_fuel_events: bool = Field(default=True)
    include_efficiency: bool = Field(default=True)
    include_alerts: bool = Field(default=True)

    @field_validator("truck_id")
    @classmethod
    def validate_truck_id(cls, v: str) -> str:
        return sanitize_truck_id(v)


# ============================================
# Refuel Request Models
# ============================================


class RefuelEventCreate(BaseModel):
    """Create a new refuel event."""

    truck_id: str = Field(..., min_length=2, max_length=10)
    gallons: float = Field(..., gt=0, le=MAX_GALLONS)
    timestamp: Optional[datetime] = None
    location: Optional[str] = Field(default=None, max_length=200)
    cost: Optional[float] = Field(default=None, ge=0, le=10000)
    odometer: Optional[float] = Field(default=None, ge=0)
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("truck_id")
    @classmethod
    def validate_truck_id(cls, v: str) -> str:
        return sanitize_truck_id(v)

    @field_validator("location", "notes")
    @classmethod
    def validate_string_fields(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_string(v)
        return v


class RefuelListParams(DateRangeParams, PaginationParams):
    """Parameters for listing refuel events."""

    truck_id: Optional[str] = Field(default=None, max_length=10)
    min_gallons: float = Field(default=0, ge=0, le=MAX_GALLONS)
    anomalies_only: bool = Field(default=False)

    @field_validator("truck_id")
    @classmethod
    def validate_truck_id(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_truck_id(v)
        return v


# ============================================
# Alert Request Models
# ============================================


class AlertRequest(BaseModel):
    """Request to send an alert."""

    truck_id: str = Field(..., min_length=2, max_length=10)
    alert_type: AlertType
    message: Optional[str] = Field(default=None, max_length=500)
    send_sms: bool = Field(default=False)
    send_email: bool = Field(default=True)

    @field_validator("truck_id")
    @classmethod
    def validate_truck_id(cls, v: str) -> str:
        return sanitize_truck_id(v)

    @field_validator("message")
    @classmethod
    def validate_message(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_string(v, 500)
        return v


class AlertListParams(DateRangeParams, PaginationParams):
    """Parameters for listing alerts."""

    truck_id: Optional[str] = None
    alert_type: Optional[AlertType] = None
    acknowledged: Optional[bool] = None

    @field_validator("truck_id")
    @classmethod
    def validate_truck_id(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_truck_id(v)
        return v


class AlertAcknowledge(BaseModel):
    """Acknowledge an alert."""

    alert_id: int = Field(..., gt=0)
    notes: Optional[str] = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_string(v, 500)
        return v


# ============================================
# User/Auth Request Models
# ============================================


class LoginRequest(BaseModel):
    """Login request."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=4, max_length=128)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        sanitized = sanitize_string(v, 50)
        if not USERNAME_PATTERN.match(sanitized):
            raise ValueError("Invalid username format")
        return sanitized


class UserCreate(BaseModel):
    """Create a new user."""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8, max_length=128)
    role: UserRole = Field(default=UserRole.VIEWER)
    carrier_id: Optional[str] = Field(default=None, max_length=50)
    email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("username")
    @classmethod
    def validate_username(cls, v: str) -> str:
        sanitized = sanitize_string(v, 50)
        if not USERNAME_PATTERN.match(sanitized):
            raise ValueError("Invalid username format")
        return sanitized

    @field_validator("password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain a digit")
        return v

    @field_validator("carrier_id")
    @classmethod
    def validate_carrier_id(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_carrier_id(v)
        return v

    @field_validator("email")
    @classmethod
    def validate_email(cls, v: Optional[str]) -> Optional[str]:
        if v:
            # Basic email validation
            if not re.match(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$", v):
                raise ValueError("Invalid email format")
        return v


# ============================================
# Report Request Models
# ============================================


class ReportRequest(DateRangeParams):
    """Request for generating reports."""

    truck_ids: Optional[List[str]] = Field(default=None, max_length=100)
    carrier_id: Optional[str] = Field(default=None, max_length=50)
    include_charts: bool = Field(default=True)
    format: str = Field(default="json", pattern=r"^(json|csv|pdf)$")

    @field_validator("truck_ids")
    @classmethod
    def validate_truck_ids(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v:
            return [sanitize_truck_id(tid) for tid in v]
        return v

    @field_validator("carrier_id")
    @classmethod
    def validate_carrier_id(cls, v: Optional[str]) -> Optional[str]:
        if v:
            return sanitize_carrier_id(v)
        return v


# ============================================
# Validation Helpers
# ============================================


def validate_percentage(value: float) -> float:
    """Validate a percentage value (0-100)."""
    if value < 0 or value > 100:
        raise ValueError("Percentage must be between 0 and 100")
    return value


def validate_positive_number(value: float) -> float:
    """Validate a positive number."""
    if value < 0:
        raise ValueError("Value must be positive")
    return value


def validate_date_not_future(value: datetime) -> datetime:
    """Validate that a date is not in the future."""
    if value > datetime.utcnow():
        raise ValueError("Date cannot be in the future")
    return value


def validate_fuel_level(level_pct: float, capacity_gal: float = None) -> dict:
    """Validate fuel level values."""
    result = {"level_pct": validate_percentage(level_pct)}

    if capacity_gal is not None:
        if capacity_gal < 10 or capacity_gal > 500:
            raise ValueError("Tank capacity must be between 10 and 500 gallons")
        result["capacity_gal"] = capacity_gal
        result["level_gal"] = (level_pct / 100) * capacity_gal

    return result


# ============================================
# Dependency Injection Helpers
# ============================================


def get_validated_truck_id(truck_id: str) -> str:
    """FastAPI dependency for validating truck IDs."""
    validated = TruckIdParam(truck_id=truck_id)
    return validated.truck_id


def get_validated_pagination(page: int = 1, page_size: int = 50) -> PaginationParams:
    """FastAPI dependency for pagination."""
    return PaginationParams(page=page, page_size=page_size)


def get_validated_date_range(days: int = 7) -> DateRangeParams:
    """FastAPI dependency for date range."""
    return DateRangeParams(days=days)


# Export all models and functions
__all__ = [
    # Enums
    "AlertType",
    "SortOrder",
    "TruckStatus",
    "UserRole",
    # Sanitization
    "sanitize_string",
    "sanitize_truck_id",
    "sanitize_carrier_id",
    "sanitize_sql_like",
    # Base models
    "PaginationParams",
    "DateRangeParams",
    "SortParams",
    # Truck models
    "TruckIdParam",
    "TruckListParams",
    "TruckMetricsRequest",
    # Refuel models
    "RefuelEventCreate",
    "RefuelListParams",
    # Alert models
    "AlertRequest",
    "AlertListParams",
    "AlertAcknowledge",
    # User models
    "LoginRequest",
    "UserCreate",
    # Report models
    "ReportRequest",
    # Validation helpers
    "validate_percentage",
    "validate_positive_number",
    "validate_date_not_future",
    "validate_fuel_level",
    # Dependencies
    "get_validated_truck_id",
    "get_validated_pagination",
    "get_validated_date_range",
]
