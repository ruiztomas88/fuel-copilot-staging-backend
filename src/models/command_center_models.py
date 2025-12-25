"""
Command Center Data Models
===========================

All dataclasses and enums used by the Fleet Command Center.
Extracted from fleet_command_center.py for better modularity.

Author: Fuel Copilot Team
Version: 2.0.0 - Refactored Module
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


# ══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ══════════════════════════════════════════════════════════════════════════════


class Priority(str, Enum):
    """Unified priority levels"""
    CRITICAL = "CRÍTICO"
    HIGH = "ALTO"
    MEDIUM = "MEDIO"
    LOW = "BAJO"
    NONE = "OK"


class IssueCategory(str, Enum):
    """Categories of issues"""
    ENGINE = "Motor"
    TRANSMISSION = "Transmisión"
    ELECTRICAL = "Eléctrico"
    FUEL = "Combustible"
    DEF = "DEF"
    BRAKES = "Frenos"
    TURBO = "Turbo"
    SENSOR = "Sensores"
    GPS = "GPS"
    EFFICIENCY = "Eficiencia"
    DRIVER = "Conductor"


class ActionType(str, Enum):
    """Types of recommended actions"""
    STOP_IMMEDIATELY = "Detener Inmediatamente"
    SCHEDULE_THIS_WEEK = "Programar Esta Semana"
    SCHEDULE_THIS_MONTH = "Programar Este Mes"
    MONITOR = "Monitorear"
    INSPECT = "Inspeccionar"
    NO_ACTION = "Sin Acción"


# ══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ══════════════════════════════════════════════════════════════════════════════


@dataclass
class ActionItem:
    """
    A single actionable item for the fleet manager.
    Designed to be understood by anyone from driver to CEO.
    """
    # Identification
    id: str
    truck_id: str

    # Priority (combined from multiple sources)
    priority: Priority
    priority_score: float  # 0-100, higher = more urgent

    # What's the issue?
    category: IssueCategory
    component: str
    title: str
    description: str

    # Impact
    days_to_critical: Optional[float] = None
    cost_if_ignored: Optional[str] = None

    # Data backing this recommendation
    current_value: Optional[str] = None
    trend: Optional[str] = None
    threshold: Optional[str] = None
    confidence: str = "MEDIUM"

    # What to do?
    action_type: ActionType = ActionType.MONITOR
    action_steps: List[str] = field(default_factory=list)

    # Additional context
    icon: str = "⚠️"
    sources: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "truck_id": self.truck_id,
            "priority": self.priority.value,
            "priority_score": round(self.priority_score, 1),
            "category": self.category.value,
            "component": self.component,
            "title": self.title,
            "description": self.description,
            "days_to_critical": round(self.days_to_critical, 1) if self.days_to_critical else None,
            "cost_if_ignored": self.cost_if_ignored,
            "current_value": self.current_value,
            "trend": self.trend,
            "threshold": self.threshold,
            "confidence": self.confidence,
            "action_type": self.action_type.value,
            "action_steps": self.action_steps,
            "icon": self.icon,
            "sources": self.sources,
        }


@dataclass
class FleetHealthScore:
    """Overall fleet health metrics"""
    score: int  # 0-100
    status: str  # "Excelente", "Bueno", "Atención", "Crítico"
    trend: str  # "improving", "stable", "declining"
    description: str


@dataclass
class TruckRiskScore:
    """
    Risk Score per truck (0-100).
    Allows identifying the top 10 at-risk trucks.
    """
    truck_id: str
    risk_score: float  # 0-100, higher = more at risk
    risk_level: str  # "critical", "high", "medium", "low", "healthy"
    contributing_factors: List[str] = field(default_factory=list)
    days_since_last_maintenance: Optional[int] = None
    active_issues_count: int = 0
    predicted_failure_days: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truck_id": self.truck_id,
            "risk_score": round(self.risk_score, 1),
            "risk_level": self.risk_level,
            "contributing_factors": self.contributing_factors,
            "days_since_last_maintenance": self.days_since_last_maintenance,
            "active_issues_count": self.active_issues_count,
            "predicted_failure_days": round(self.predicted_failure_days, 1) if self.predicted_failure_days else None,
        }


@dataclass
class SensorReading:
    """
    Temporal persistence for sensor readings.
    Store 2-3 readings before making STOP decisions to avoid glitches.
    """
    sensor_name: str
    truck_id: str
    value: float
    timestamp: datetime
    is_valid: bool = True


@dataclass
class FailureCorrelation:
    """
    Automatic failure correlation.
    Detects when multiple sensors indicate the same underlying problem.
    """
    correlation_id: str
    primary_sensor: str
    correlated_sensors: List[str]
    correlation_strength: float  # 0.0-1.0
    probable_cause: str
    recommended_action: str
    affected_trucks: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "primary_sensor": self.primary_sensor,
            "correlated_sensors": self.correlated_sensors,
            "correlation_strength": round(self.correlation_strength, 2),
            "probable_cause": self.probable_cause,
            "recommended_action": self.recommended_action,
            "affected_trucks": self.affected_trucks,
        }


@dataclass
class DEFPrediction:
    """
    Real DEF predictive - liters/consumption = days remaining.
    """
    truck_id: str
    current_level_pct: float
    estimated_liters_remaining: float
    avg_consumption_liters_per_day: float
    days_until_empty: float
    days_until_derate: float  # Usually triggers at ~5%
    last_fill_date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truck_id": self.truck_id,
            "current_level_pct": round(self.current_level_pct, 1),
            "estimated_liters_remaining": round(self.estimated_liters_remaining, 1),
            "avg_consumption_liters_per_day": round(self.avg_consumption_liters_per_day, 2),
            "days_until_empty": round(self.days_until_empty, 1),
            "days_until_derate": round(self.days_until_derate, 1),
            "last_fill_date": self.last_fill_date.isoformat() if self.last_fill_date else None,
        }


@dataclass
class UrgencySummary:
    """Count of issues by urgency"""
    critical: int = 0
    high: int = 0
    medium: int = 0
    low: int = 0
    ok: int = 0

    @property
    def total_issues(self) -> int:
        return self.critical + self.high + self.medium + self.low


@dataclass
class SensorStatus:
    """Status of non-engine sensors"""
    gps_issues: int = 0
    voltage_issues: int = 0
    dtc_active: int = 0
    idle_deviation: int = 0
    total_trucks: int = 0


@dataclass
class CostProjection:
    """Projected costs if issues are ignored"""
    immediate_risk: str
    week_risk: str
    month_risk: str


@dataclass
class CommandCenterData:
    """
    Complete Command Center response.
    This is the single source of truth for the frontend.
    """
    # Meta
    generated_at: str
    version: str = "2.0.0"

    # Fleet overview
    fleet_health: Optional[FleetHealthScore] = None
    total_trucks: int = 0
    trucks_analyzed: int = 0

    # Urgency breakdown
    urgency_summary: Optional[UrgencySummary] = None

    # Sensor status (GPS, Voltage, etc.)
    sensor_status: Optional[SensorStatus] = None

    # Cost impact
    cost_projection: Optional[CostProjection] = None

    # THE MAIN LIST - All actions, prioritized
    action_items: List[ActionItem] = field(default_factory=list)

    # Quick access lists
    critical_actions: List[ActionItem] = field(default_factory=list)
    high_priority_actions: List[ActionItem] = field(default_factory=list)

    # Insights (AI-generated recommendations)
    insights: List[Dict[str, str]] = field(default_factory=list)

    # Data quality indicators
    data_quality: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            "generated_at": self.generated_at,
            "version": self.version,
            "fleet_health": {
                "score": self.fleet_health.score,
                "status": self.fleet_health.status,
                "trend": self.fleet_health.trend,
                "description": self.fleet_health.description,
            } if self.fleet_health else None,
            "total_trucks": self.total_trucks,
            "trucks_analyzed": self.trucks_analyzed,
            "urgency_summary": {
                "critical": self.urgency_summary.critical,
                "high": self.urgency_summary.high,
                "medium": self.urgency_summary.medium,
                "low": self.urgency_summary.low,
                "ok": self.urgency_summary.ok,
                "total_issues": self.urgency_summary.total_issues,
            } if self.urgency_summary else None,
            "sensor_status": {
                "gps_issues": self.sensor_status.gps_issues,
                "voltage_issues": self.sensor_status.voltage_issues,
                "dtc_active": self.sensor_status.dtc_active,
                "idle_deviation": self.sensor_status.idle_deviation,
                "total_trucks": self.sensor_status.total_trucks,
            } if self.sensor_status else None,
            "cost_projection": {
                "immediate_risk": self.cost_projection.immediate_risk,
                "week_risk": self.cost_projection.week_risk,
                "month_risk": self.cost_projection.month_risk,
            } if self.cost_projection else None,
            "action_items": [item.to_dict() for item in self.action_items],
            "critical_actions": [item.to_dict() for item in self.critical_actions],
            "high_priority_actions": [item.to_dict() for item in self.high_priority_actions],
            "insights": self.insights,
            "data_quality": self.data_quality,
        }
