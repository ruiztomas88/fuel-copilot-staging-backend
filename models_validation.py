"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    PYDANTIC VALIDATION MODELS                                  ║
║                    Input Validation & Type Safety                              ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Comprehensive Pydantic models for API request/response validation.
Prevents SQL injection, data corruption, and provides type safety.

Created: Dec 26, 2025
Author: Auditoría Implementation
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, constr, validator

# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════


class TruckStatus(str, Enum):
    """Valid truck status values"""

    MOVING = "MOVING"
    STOPPED = "STOPPED"
    PARKED = "PARKED"
    OFFLINE = "OFFLINE"
    IDLE = "IDLE"


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


class TheftAlgorithm(str, Enum):
    """Theft detection algorithms"""

    RULE_BASED = "rule"
    ML_BASED = "ml"
    HYBRID = "hybrid"


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class TruckIDRequest(BaseModel):
    """Validate truck ID format"""

    truck_id: constr(min_length=2, max_length=20, pattern=r"^[A-Z0-9-]+$")

    class Config:
        json_schema_extra = {"example": {"truck_id": "FL-0208"}}


class DateRangeRequest(BaseModel):
    """Validate date range queries"""

    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    days: Optional[int] = Field(default=7, ge=1, le=365)

    @validator("end_date")
    def end_date_must_be_after_start(cls, v, values):
        if v and "start_date" in values and values["start_date"]:
            if v < values["start_date"]:
                raise ValueError("end_date must be after start_date")
        return v

    class Config:
        json_schema_extra = {"example": {"days": 30}}


class TheftAnalysisRequest(BaseModel):
    """Request model for theft analysis endpoint"""

    days: int = Field(default=7, ge=1, le=90, description="Number of days to analyze")
    algorithm: TheftAlgorithm = Field(default=TheftAlgorithm.RULE_BASED)
    min_confidence: float = Field(default=0.7, ge=0.0, le=1.0)

    class Config:
        json_schema_extra = {
            "example": {"days": 30, "algorithm": "ml", "min_confidence": 0.8}
        }


class PredictiveMaintenanceRequest(BaseModel):
    """Request model for predictive maintenance endpoint"""

    truck_id: Optional[constr(pattern=r"^[A-Z0-9-]+$")] = None
    component: Optional[str] = None
    days_ahead: int = Field(default=30, ge=1, le=180)
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)

    class Config:
        json_schema_extra = {
            "example": {"truck_id": "FL-0208", "component": "engine", "days_ahead": 60}
        }


class BatchTruckRequest(BaseModel):
    """Request model for batch truck operations"""

    truck_ids: List[constr(pattern=r"^[A-Z0-9-]+$")] = Field(..., max_items=100)
    include_sensors: bool = Field(default=True)
    include_dtcs: bool = Field(default=False)

    @validator("truck_ids")
    def truck_ids_not_empty(cls, v):
        if not v:
            raise ValueError("truck_ids cannot be empty")
        # Remove duplicates
        return list(set(v))

    class Config:
        json_schema_extra = {
            "example": {
                "truck_ids": ["FL-0208", "FL-0209", "FL-0210"],
                "include_sensors": True,
                "include_dtcs": True,
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class SensorDataResponse(BaseModel):
    """Standardized sensor data response"""

    truck_id: str
    timestamp: Optional[datetime]
    sensors: Dict[str, Any]
    data_available: bool = True
    error: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "truck_id": "FL-0208",
                "timestamp": "2025-12-26T18:00:00Z",
                "sensors": {"fuel_level_pct": 75.5, "rpm": 1450, "speed_mph": 65.0},
                "data_available": True,
            }
        }


class DTCResponse(BaseModel):
    """DTC event response model"""

    dtc_code: str
    spn: Optional[int]
    fmi: Optional[int]
    severity: AlertSeverity
    description: str
    timestamp_utc: datetime
    status: str

    class Config:
        json_schema_extra = {
            "example": {
                "dtc_code": "P0128",
                "spn": 110,
                "fmi": 2,
                "severity": "HIGH",
                "description": "Coolant Thermostat Temperature Below Regulated Temperature",
                "timestamp_utc": "2025-12-26T18:00:00Z",
                "status": "ACTIVE",
            }
        }


class TheftEventResponse(BaseModel):
    """Theft event response model"""

    truck_id: str
    timestamp: datetime
    fuel_drop_pct: float
    latitude: Optional[float]
    longitude: Optional[float]
    confidence: float
    algorithm_used: str
    status: str

    class Config:
        json_schema_extra = {
            "example": {
                "truck_id": "FL-0208",
                "timestamp": "2025-12-26T18:00:00Z",
                "fuel_drop_pct": 15.5,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "confidence": 0.92,
                "algorithm_used": "ml",
                "status": "CONFIRMED",
            }
        }


class HealthCheckResponse(BaseModel):
    """Health check response"""

    status: str = Field(default="healthy")
    timestamp: datetime
    database: bool
    cache: bool
    version: str

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2025-12-26T18:00:00Z",
                "database": True,
                "cache": True,
                "version": "v6.3.0",
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# ERROR MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class ErrorResponse(BaseModel):
    """Standardized error response"""

    error: str
    detail: Optional[str] = None
    code: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.utcnow())

    class Config:
        json_schema_extra = {
            "example": {
                "error": "Resource not found",
                "detail": "Truck FL-9999 does not exist",
                "code": "TRUCK_NOT_FOUND",
                "timestamp": "2025-12-26T18:00:00Z",
            }
        }


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def sanitize_truck_id(truck_id: str) -> str:
    """
    Sanitize and validate truck ID.
    Prevents SQL injection and ensures valid format.
    """
    # Remove whitespace
    truck_id = truck_id.strip().upper()

    # Validate format
    if not truck_id or len(truck_id) < 2 or len(truck_id) > 20:
        raise ValueError("Invalid truck ID length")

    # Only allow alphanumeric and dash
    if not all(c.isalnum() or c == "-" for c in truck_id):
        raise ValueError("Invalid truck ID format")

    return truck_id


def validate_date_range(days: int) -> int:
    """Validate days parameter is within acceptable range"""
    if days < 1:
        return 1
    if days > 365:
        return 365
    return days
