"""
Pydantic models for FastAPI request/response validation
🔧 FIX v3.9.4: Updated to use ConfigDict instead of deprecated class Config
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Dict, Any
from datetime import datetime
from enum import Enum


class TruckStatus(str, Enum):
    """Truck operational status"""

    MOVING = "MOVING"
    IDLE = "IDLE"
    ENGINE_OFF = "ENGINE_OFF"
    OFFLINE = "OFFLINE"
    REFUELING = "REFUELING"


class AlertSeverity(str, Enum):
    """Alert severity levels"""

    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertType(str, Enum):
    """Types of alerts"""

    OFFLINE = "offline"
    HIGH_IDLE = "high_idle"
    LOW_MPG = "low_mpg"
    LOW_FUEL = "low_fuel"
    REFUEL_DETECTED = "refuel_detected"


class TruckSummary(BaseModel):
    """Summary information for a single truck"""

    truck_id: str
    mpg: float = Field(ge=0, le=15)
    idle_gph: float = Field(ge=0, le=5)
    fuel_L: float = Field(ge=0)
    fuel_percent: float = Field(ge=0, le=100)
    status: TruckStatus
    last_update: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "truck_id": "JC1282",
                "mpg": 6.8,
                "idle_gph": 0.9,
                "fuel_L": 450.5,
                "fuel_percent": 75.2,
                "status": "MOVING",
                "last_update": "2025-11-20T04:30:00",
            }
        }
    )


class FleetSummary(BaseModel):
    """Fleet-wide summary statistics"""

    total_trucks: int
    active_trucks: int
    offline_trucks: int
    critical_count: int
    warning_count: int
    healthy_count: int
    avg_mpg: float
    avg_idle_gph: float
    truck_details: List[Dict[str, Any]]
    timestamp: datetime
    data_source: Optional[str] = "MySQL"  # NEW: Indica si la data viene de MySQL o CSV

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_trucks": 40,
                "active_trucks": 36,
                "offline_trucks": 4,
                "critical_count": 0,
                "warning_count": 2,
                "healthy_count": 34,
                "avg_mpg": 6.5,
                "avg_idle_gph": 0.85,
                "truck_details": [],
                "timestamp": "2025-11-20T04:30:00",
                "data_source": "MySQL",
            }
        }
    )


class TruckDetail(BaseModel):
    """Detailed information for a single truck"""

    truck_id: str
    timestamp: datetime

    # Location & Motion
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    speed_mph: Optional[float] = Field(None, ge=0, le=120)
    odometer_mi: Optional[float] = Field(None, ge=0)

    # Fuel System
    fuel_L: float = Field(ge=0)
    fuel_gal: float = Field(ge=0)
    fuel_percent: float = Field(ge=0, le=100)
    capacity_gal: float = Field(ge=0)

    # MPG Calculation
    mpg_current: Optional[float] = Field(None, ge=0, le=15)
    mpg_distance_accum: Optional[float] = Field(None, ge=0)
    mpg_fuel_accum_gal: Optional[float] = Field(None, ge=0)

    # Idle Tracking
    idle_consumption_gph: Optional[float] = Field(None, ge=0, le=5)
    idle_method: Optional[str] = None
    idle_mode: Optional[str] = None

    # Engine Data
    rpm: Optional[int] = Field(None, ge=0, le=3000)
    fuel_rate_lph: Optional[float] = Field(None, ge=0)
    engine_hours: Optional[float] = Field(None, ge=0)

    # Status
    status: TruckStatus
    refuel_detected: bool = False

    # Anchors
    anchor_type: Optional[str] = None
    anchor_gal: Optional[float] = Field(None, ge=0)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "truck_id": "JC1282",
                "timestamp": "2025-11-20T04:30:00",
                "speed_mph": 65.5,
                "fuel_L": 450.5,
                "fuel_gal": 119.0,
                "fuel_percent": 75.2,
                "capacity_gal": 200,
                "mpg_current": 6.8,
                "idle_consumption_gph": 0.9,
                "idle_method": "SENSOR_FUEL_RATE",
                "idle_mode": "NORMAL",
                "rpm": 1450,
                "status": "MOVING",
                "refuel_detected": False,
            }
        }
    )


class HistoricalRecord(BaseModel):
    """Historical data point"""

    timestamp: datetime
    mpg: Optional[float] = None
    idle_gph: Optional[float] = None
    fuel_percent: Optional[float] = None
    speed_mph: Optional[float] = None
    status: Optional[str] = None


class EfficiencyRanking(BaseModel):
    """Efficiency ranking for a truck"""

    truck_id: str
    mpg: Optional[float] = None
    idle_gph: Optional[float] = None
    overall_score: Optional[float] = Field(None, ge=0, le=200)
    mpg_score: Optional[float] = Field(None, ge=0, le=200)
    idle_score: Optional[float] = Field(None, ge=0, le=200)
    rank: Optional[int] = None


# RefuelEvent model moved below (line ~250) to avoid duplication


class Alert(BaseModel):
    """Alert model"""

    truck_id: str
    type: AlertType
    severity: AlertSeverity
    message: str
    timestamp: datetime

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "truck_id": "JC1282",
                "type": "high_idle",
                "severity": "warning",
                "message": "High idle consumption: 1.8 GPH",
                "timestamp": "2025-11-20T04:30:00",
            }
        }
    )


class KPIData(BaseModel):
    """Financial KPI data"""

    total_fuel_consumed_gal: float
    total_fuel_cost_usd: float
    total_idle_waste_gal: float
    total_idle_cost_usd: float
    avg_fuel_price_per_gal: float
    total_distance_mi: float
    fleet_avg_mpg: float

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_fuel_consumed_gal": 12500.5,
                "total_fuel_cost_usd": 43751.75,
                "total_idle_waste_gal": 850.2,
                "total_idle_cost_usd": 2975.70,
                "avg_fuel_price_per_gal": 3.50,
                "total_distance_mi": 82503.0,
                "fleet_avg_mpg": 6.6,
            }
        }
    )


class RefuelEvent(BaseModel):
    """Refuel event data"""

    truck_id: str
    timestamp: datetime
    date: str
    time: str
    gallons: float
    liters: float
    fuel_level_before: Optional[float] = None
    fuel_level_after: Optional[float] = None

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "truck_id": "JC1282",
                "timestamp": "2025-11-20T14:30:00",
                "date": "2025-11-20",
                "time": "14:30:00",
                "gallons": 125.5,
                "liters": 475.2,
                "fuel_level_after": 95.2,
            }
        }
    )


class WebSocketMessage(BaseModel):
    """WebSocket message format"""

    type: str  # "fleet_update", "truck_update", "alert"
    data: Dict[str, Any]
    timestamp: datetime


class HealthCheck(BaseModel):
    """API health check response"""

    status: str
    version: str
    timestamp: datetime
    trucks_available: int

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "version": "3.1.0",
                "timestamp": "2025-11-20T04:30:00",
                "trucks_available": 40,
            }
        }
    )
