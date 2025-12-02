"""
Pydantic Models for Fuel Copilot API v3.7.0

Strict type validation for all API endpoints.
Generates automatic OpenAPI documentation.

Usage:
    from models_v2 import TruckResponse, FleetResponse, APIError
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime
from enum import Enum


# ===========================================
# ENUMS
# ===========================================


class TruckStatus(str, Enum):
    """Truck operational status"""

    MOVING = "MOVING"
    STOPPED = "STOPPED"
    OFFLINE = "OFFLINE"


class ConfidenceLevel(str, Enum):
    """Kalman filter confidence indicator"""

    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class AlertType(str, Enum):
    """Types of alerts"""

    THEFT = "THEFT"
    REFUEL = "REFUEL"
    DRIFT = "DRIFT"
    OFFLINE = "OFFLINE"
    LOW_FUEL = "LOW_FUEL"
    SENSOR_ERROR = "SENSOR_ERROR"


# ===========================================
# BASE MODELS
# ===========================================


class APIResponse(BaseModel):
    """Base API response model"""

    success: bool = True
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {"success": True, "timestamp": "2025-11-26T12:00:00Z"}
        }
    )


class APIError(BaseModel):
    """API error response"""

    success: bool = False
    error: str
    message: str
    code: Optional[str] = None
    details: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": False,
                "error": "Not Found",
                "message": "Truck ID 'INVALID' not found",
                "code": "TRUCK_NOT_FOUND",
                "timestamp": "2025-11-26T12:00:00Z",
            }
        }
    )


# ===========================================
# TRUCK MODELS
# ===========================================


class FuelMetrics(BaseModel):
    """Fuel level metrics"""

    sensor_pct: Optional[float] = Field(
        None, ge=0, le=100, description="Sensor reading in %"
    )
    estimated_pct: Optional[float] = Field(
        None, ge=0, le=100, description="Kalman estimate in %"
    )
    sensor_liters: Optional[float] = Field(
        None, ge=0, description="Sensor reading in liters"
    )
    estimated_liters: Optional[float] = Field(
        None, ge=0, description="Kalman estimate in liters"
    )
    sensor_gallons: Optional[float] = Field(
        None, ge=0, description="Sensor reading in gallons"
    )
    estimated_gallons: Optional[float] = Field(
        None, ge=0, description="Kalman estimate in gallons"
    )

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "sensor_pct": 75.5,
                "estimated_pct": 74.8,
                "sensor_liters": 151.0,
                "estimated_liters": 149.6,
                "sensor_gallons": 39.9,
                "estimated_gallons": 39.5,
            }
        }
    )


class DriftMetrics(BaseModel):
    """Sensor drift metrics"""

    drift_pct: Optional[float] = Field(
        None, description="Drift between sensor and estimate"
    )
    drift_warning: bool = Field(False, description="True if drift exceeds threshold")
    confidence: ConfidenceLevel = Field(
        ConfidenceLevel.HIGH, description="Kalman confidence level"
    )

    @field_validator("drift_pct")
    @classmethod
    def validate_drift(cls, v):
        if v is not None and abs(v) > 100:
            raise ValueError("Drift percentage must be between -100 and 100")
        return v


class EfficiencyMetrics(BaseModel):
    """Fuel efficiency metrics"""

    mpg_current: Optional[float] = Field(None, ge=0, le=20, description="Current MPG")
    mpg_average: Optional[float] = Field(None, ge=0, le=20, description="Average MPG")
    consumption_gph: Optional[float] = Field(None, ge=0, description="Gallons per hour")
    consumption_lph: Optional[float] = Field(None, ge=0, description="Liters per hour")


class LocationData(BaseModel):
    """Truck location data"""

    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    speed_kmh: Optional[float] = Field(None, ge=0, description="Speed in km/h")
    speed_mph: Optional[float] = Field(None, ge=0, description="Speed in mph")
    heading: Optional[float] = Field(
        None, ge=0, le=360, description="Heading in degrees"
    )
    odometer_km: Optional[float] = Field(None, ge=0)
    odometer_miles: Optional[float] = Field(None, ge=0)


class TruckResponse(BaseModel):
    """Full truck data response"""

    truck_id: str = Field(
        ..., min_length=1, max_length=10, description="Unique truck identifier"
    )
    timestamp_utc: datetime = Field(..., description="Last data timestamp (UTC)")
    status: TruckStatus = Field(..., description="Current truck status")

    # Nested metrics
    fuel: FuelMetrics
    drift: DriftMetrics
    efficiency: EfficiencyMetrics
    location: LocationData

    # Metadata
    data_age_minutes: Optional[float] = Field(
        None, ge=0, description="Age of data in minutes"
    )
    tank_capacity_liters: Optional[float] = Field(None, ge=0)
    last_refuel: Optional[datetime] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "truck_id": "NQ6975",
                "timestamp_utc": "2025-11-26T12:00:00Z",
                "status": "MOVING",
                "fuel": {
                    "sensor_pct": 75.5,
                    "estimated_pct": 74.8,
                    "sensor_liters": 151.0,
                    "estimated_liters": 149.6,
                },
                "drift": {
                    "drift_pct": 0.7,
                    "drift_warning": False,
                    "confidence": "HIGH",
                },
                "efficiency": {"mpg_current": 7.5, "consumption_gph": 3.2},
                "location": {"speed_kmh": 65.0, "odometer_km": 125000.0},
                "data_age_minutes": 2.5,
            }
        }
    )


class TruckSummary(BaseModel):
    """Simplified truck data for fleet list"""

    truck_id: str
    status: TruckStatus
    fuel_pct: Optional[float] = Field(None, ge=0, le=100)
    mpg: Optional[float] = None
    drift_warning: bool = False
    last_update: datetime


# ===========================================
# FLEET MODELS
# ===========================================


class FleetStats(BaseModel):
    """Fleet-wide statistics"""

    total_trucks: int = Field(..., ge=0)
    moving: int = Field(..., ge=0)
    stopped: int = Field(..., ge=0)
    offline: int = Field(..., ge=0)
    avg_fuel_pct: Optional[float] = Field(None, ge=0, le=100)
    avg_mpg: Optional[float] = None
    trucks_with_drift_warning: int = Field(0, ge=0)


class FleetResponse(APIResponse):
    """Fleet data response"""

    stats: FleetStats
    trucks: List[TruckSummary]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "timestamp": "2025-11-26T12:00:00Z",
                "stats": {
                    "total_trucks": 39,
                    "moving": 25,
                    "stopped": 10,
                    "offline": 4,
                    "avg_fuel_pct": 65.5,
                    "avg_mpg": 7.2,
                },
                "trucks": [
                    {
                        "truck_id": "NQ6975",
                        "status": "MOVING",
                        "fuel_pct": 75.5,
                        "mpg": 7.5,
                        "drift_warning": False,
                        "last_update": "2025-11-26T12:00:00Z",
                    }
                ],
            }
        }
    )


# ===========================================
# ALERT MODELS
# ===========================================


class Alert(BaseModel):
    """Alert notification"""

    id: str = Field(..., description="Unique alert ID")
    truck_id: str
    type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime
    acknowledged: bool = False
    details: Optional[Dict[str, Any]] = None


class AlertsResponse(APIResponse):
    """Alerts list response"""

    total: int = Field(..., ge=0)
    unacknowledged: int = Field(..., ge=0)
    alerts: List[Alert]


# ===========================================
# HISTORY MODELS
# ===========================================


class HistoryPoint(BaseModel):
    """Single point in history"""

    timestamp: datetime
    fuel_pct: Optional[float] = None
    estimated_pct: Optional[float] = None
    speed_kmh: Optional[float] = None
    status: Optional[TruckStatus] = None


class HistoryResponse(APIResponse):
    """Historical data response"""

    truck_id: str
    period_hours: int
    data_points: int = Field(..., ge=0)
    history: List[HistoryPoint]


# ===========================================
# REFUEL MODELS
# ===========================================


class RefuelEvent(BaseModel):
    """Detected refuel event"""

    truck_id: str
    timestamp: datetime
    fuel_before_pct: float = Field(..., ge=0, le=100)
    fuel_after_pct: float = Field(..., ge=0, le=100)
    liters_added: Optional[float] = Field(None, ge=0)
    gallons_added: Optional[float] = Field(None, ge=0)
    location: Optional[LocationData] = None
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH


class RefuelsResponse(APIResponse):
    """Refuel events response"""

    truck_id: Optional[str] = None
    total: int = Field(..., ge=0)
    refuels: List[RefuelEvent]


# ===========================================
# KPI MODELS
# ===========================================


class KPIMetrics(BaseModel):
    """Key Performance Indicators"""

    period: str = Field(..., description="Time period (daily, weekly, monthly)")

    # Fleet metrics
    total_distance_km: float = Field(..., ge=0)
    total_fuel_consumed_liters: float = Field(..., ge=0)
    fleet_avg_mpg: float = Field(..., ge=0)

    # Efficiency
    best_performer_truck: Optional[str] = None
    best_performer_mpg: Optional[float] = None
    worst_performer_truck: Optional[str] = None
    worst_performer_mpg: Optional[float] = None

    # Operational
    avg_uptime_pct: float = Field(..., ge=0, le=100)
    total_idle_hours: float = Field(..., ge=0)
    refuel_count: int = Field(..., ge=0)
    drift_alerts_count: int = Field(..., ge=0)


class KPIResponse(APIResponse):
    """KPI response"""

    kpis: KPIMetrics


# ===========================================
# HEALTH CHECK MODELS
# ===========================================


class HealthComponent(BaseModel):
    """Health of a single component"""

    name: str
    status: Literal["healthy", "degraded", "unhealthy"]
    latency_ms: Optional[float] = None
    message: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response"""

    status: Literal["healthy", "degraded", "unhealthy"]
    version: str
    uptime_seconds: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    components: List[HealthComponent]

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "3.7.0",
                "uptime_seconds": 3600.0,
                "timestamp": "2025-11-26T12:00:00Z",
                "components": [
                    {"name": "database", "status": "healthy", "latency_ms": 5.2},
                    {"name": "wialon", "status": "healthy", "latency_ms": 45.0},
                ],
            }
        }
    )


# ===========================================
# REQUEST MODELS
# ===========================================


class TruckFilterRequest(BaseModel):
    """Truck filter parameters"""

    status: Optional[TruckStatus] = None
    min_fuel_pct: Optional[float] = Field(None, ge=0, le=100)
    max_fuel_pct: Optional[float] = Field(None, ge=0, le=100)
    drift_warning_only: bool = False
    limit: int = Field(100, ge=1, le=500)
    offset: int = Field(0, ge=0)


class DateRangeRequest(BaseModel):
    """Date range for historical queries"""

    start_date: datetime
    end_date: datetime

    @field_validator("end_date")
    @classmethod
    def validate_date_range(cls, v, info):
        start = info.data.get("start_date")
        if start and v < start:
            raise ValueError("end_date must be after start_date")
        return v
