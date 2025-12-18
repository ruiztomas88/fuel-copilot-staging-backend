"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    🎯 FLEET COMMAND CENTER v1.8.0                              ║
║                                                                                ║
║       The UNIFIED source of truth for fleet health and maintenance            ║
║                                                                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  COMBINES:                                                                     ║
║  ✓ Predictive Maintenance (trend-based days-to-failure)                       ║
║  ✓ ML Anomaly Detection (isolation forest outlier scores)                     ║
║  ✓ Sensor Health (GPS, Voltage, DTC, Idle)                                    ║
║  ✓ Driver Performance (scoring, speeding, idle)                               ║
║  ✓ Component Health (turbo, oil, coolant predictors)                          ║
║  ✓ DTC Analysis (J1939 SPN/FMI with 112 SPNs)                                 ║
║  ✓ DEF Predictor (depletion forecast, derating prevention)                    ║
║  ✓ DTW Pattern Analysis (anomaly detection, fleet clustering)                 ║
║  ✓ Cost Impact Analysis                                                       ║
║  ✓ Real-Time Predictive Engine (TRUE predictive maintenance)                  ║
║  ✓ EWMA/CUSUM Trend Detection (Phase 4)                                       ║
║  ✓ Truck Risk Scoring (Phase 4)                                               ║
║  ✓ Automatic Failure Correlation (Phase 5)                                    ║
║  ✓ MySQL Persistence for ML (Phase 5.6)                                       ║
║  ✓ Wialon Data Loader Service (centralized data loading)                      ║
║                                                                                ║
║  OUTPUT: Single prioritized action list with combined intelligence            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Fuel Copilot Team
Version: 1.8.0 - DEF Predictor & DTW Pattern Analysis
Created: December 2025
Updated: December 2025

CHANGELOG v1.8.0 (DEF PREDICTOR & DTW ANALYSIS):
- 🆕 NEW: DEF Predictor Engine - Predicts DEF depletion to prevent EPA derating
- 🆕 NEW: DTW Pattern Analyzer - Compares truck patterns for anomaly detection
- 🆕 NEW: Wialon Data Loader Service - Centralized data loading with caching
- 📊 51,589+ DEF readings from Wialon integrated
- 🔍 Pattern comparison using Dynamic Time Warping algorithm
- 📦 Fleet clustering by behavior patterns
- 🚨 DEF alerts: good/low/warning/critical/emergency levels
- 📈 Consumption rate calculation (gallons/mile, gallons/hour)
- 🎯 Depletion prediction (miles, hours, days until empty)
- 🔗 New router: /api/v2/def/* and /api/v2/patterns/*

CHANGELOG v1.7.0 (INTEGRATED HEALTH DASHBOARD):
- 🆕 NEW: /truck/{truck_id}/comprehensive endpoint
- 📊 Combines: Predictive + Driver Scoring + Component Health + DTC
- 🎯 Unified Health Score (weighted: 30% predictive, 20% driver, 30% components, 20% DTC)
- 🔧 Integrates driver_scoring_engine.py for driver behavior
- 🌀 Integrates component_health_predictors.py for turbo/oil/coolant
- 📋 Integrates dtc_analyzer.py v4.0 with dtc_database.py v5.8.0 (112 SPNs)
- 🚨 Prioritized recommendations from all sources
- 📈 Status levels: healthy/attention/warning/critical

CHANGELOG v1.6.0 (FASE 5.6 - ML DATA PERSISTENCE):
- 💾 NEW: MySQL persistence for all calculated data (ML training ready)
- 📊 persist_risk_score(): Saves truck risk scores to cc_risk_history
- 🚨 persist_anomaly(): Saves EWMA/CUSUM anomalies to cc_anomaly_history
- 🔧 persist_algorithm_state(): Saves EWMA/CUSUM state to cc_algorithm_state
- 🔗 persist_correlation_event(): Saves failure patterns to cc_correlation_events
- ⛽ persist_def_reading(): Saves DEF consumption to cc_def_history
- 🔄 load_algorithm_state(): Restores algorithm state after restart
- 📦 batch_persist_risk_scores(): Efficient bulk insert for snapshots
- 🗃️ New migration: add_command_center_history_v1_5_0.sql with 6 tables
- ⚡ Auto-persist on: get_top_risk_trucks, detect_trend_with_ewma_cusum,
    detect_failure_correlations, predict_def_depletion
- 🧹 Stored procedure sp_cleanup_command_center_history() for data retention

CHANGELOG v1.5.0 (FASE 4 & 5):
- 🕐 Temporal persistence: 2-3 readings before STOP decision (avoid sensor glitches)
- 📊 Adaptive windows: oil=seconds, def=hours, mpg=days
- 📈 EWMA/CUSUM for subtle change detection in trends
- 🎯 Risk Score per truck (0-100) with top 10 at-risk trucks
- ⚙️ YAML-based configuration for thresholds and weights
- 🏗️ Separation of DETECTION vs DECISION logic
- 🚨 "No recent data" alerts for offline trucks
- 💾 Redis persistence for trend_history
- 🔗 Automatic failure correlation (coolant↑ + oil_temp↑ = systemic)
- 📋 J1939 SPN normalization for standard component mapping
- 💎 DEF predictive: liters/consumption = days remaining
- 📄 External decision table (YAML) for action_steps
- 🎯 Unified scoring v2 with time-horizon as first-class citizen

CHANGELOG v1.3.0:
- 🧮 Exponential decay for urgency scoring (smooth curve vs piecewise)
- 🧮 Weighted priority scoring (45% days + 20% anomaly + 25% criticality + 10% cost)
- 🏥 Distribution-aware fleet health score (penalizes concentrated issues)
- 🔄 Multi-source deduplication with data preservation
- ✅ Sensor validation with SENSOR_VALID_RANGES
- 📊 Component normalization for robust deduplication
- 💡 Enhanced insights (cost impact, escalation warnings)
- ⚡ RT Engine query optimization with window function
- 🔧 _load_engine_safely helper for robust engine loading
- 🐛 Fixed cost_if_ignored calculation in RT Engine
- 🐛 Fixed UrgencySummary.ok calculation (trucks without ANY issue)

CHANGELOG v1.2.0:
- 🆕 Added RealTimePredictiveEngine integration (source #6)
- 🐛 Fixed race condition in _trend_history (thread-safe deque + lock)
- 🐛 Fixed _calculate_trend edge case when recent < 2 elements
- 🐛 Added ActionItem deduplication to prevent duplicate alerts
- Improved pattern detection with component name normalization

CHANGELOG v1.1.0:
- Added weighted priority scoring by component criticality
- Replaced counter-based IDs with UUID for thread safety
- Added comprehensive cost database replacing string parsing
- Improved pattern detection thresholds (% of fleet vs fixed count)
"""

import logging
import uuid
import math
import threading
import functools
import os
import yaml
from collections import deque, Counter
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Callable, TypeVar
from pathlib import Path
import json

# Optional Redis import for trend persistence
try:
    import redis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

logger = logging.getLogger(__name__)

# Type variable for generic caching
T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS
# ═══════════════════════════════════════════════════════════════════════════════


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


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ActionItem:
    """
    A single actionable item for the fleet manager.
    Designed to be understood by anyone from driver to CEO.
    """

    # Identification
    id: str  # Unique ID for tracking
    truck_id: str

    # Priority (combined from multiple sources)
    priority: Priority
    priority_score: float  # 0-100, higher = more urgent

    # What's the issue?
    category: IssueCategory
    component: str  # e.g., "Transmisión", "Bomba de aceite"
    title: str  # Short title for quick understanding
    description: str  # Detailed explanation

    # Impact
    days_to_critical: Optional[float]  # When will it fail?
    cost_if_ignored: Optional[str]  # e.g., "$8,000 - $15,000"

    # Data backing this recommendation
    current_value: Optional[str]  # e.g., "218°F"
    trend: Optional[str]  # e.g., "+2.1°F/día"
    threshold: Optional[str]  # e.g., "Crítico: >225°F"
    confidence: str  # HIGH, MEDIUM, LOW

    # What to do?
    action_type: ActionType
    action_steps: List[str]  # Step-by-step instructions

    # Additional context
    icon: str  # Emoji for visual identification
    sources: List[str]  # What data sources detected this

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
            "days_to_critical": (
                round(self.days_to_critical, 1) if self.days_to_critical else None
            ),
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
    description: str  # Human-readable explanation


# ═══════════════════════════════════════════════════════════════════════════════
# v1.5.0: FASE 4 DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class TruckRiskScore:
    """
    v1.5.0 FASE 4.4: Risk Score per truck (0-100).
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
            "predicted_failure_days": (
                round(self.predicted_failure_days, 1)
                if self.predicted_failure_days
                else None
            ),
        }


@dataclass
class SensorReading:
    """
    v1.5.0 FASE 4.1: Temporal persistence for sensor readings.
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
    v1.5.0 FASE 5.1: Automatic failure correlation.
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
    v1.5.0 FASE 5.3: Real DEF predictive - liters/consumption = days remaining.
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
            "avg_consumption_liters_per_day": round(
                self.avg_consumption_liters_per_day, 2
            ),
            "days_until_empty": round(self.days_until_empty, 1),
            "days_until_derate": round(self.days_until_derate, 1),
            "last_fill_date": (
                self.last_fill_date.isoformat() if self.last_fill_date else None
            ),
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

    immediate_risk: str  # Cost of critical issues
    week_risk: str  # Cost if high priority ignored
    month_risk: str  # Total projected risk


@dataclass
class CommandCenterData:
    """
    Complete Command Center response.
    This is the single source of truth for the frontend.
    """

    # Meta
    generated_at: str
    version: str = "1.0.0"

    # Fleet overview
    fleet_health: FleetHealthScore = None
    total_trucks: int = 0
    trucks_analyzed: int = 0

    # Urgency breakdown
    urgency_summary: UrgencySummary = None

    # Sensor status (GPS, Voltage, etc.)
    sensor_status: SensorStatus = None

    # Cost impact
    cost_projection: CostProjection = None

    # THE MAIN LIST - All actions, prioritized
    action_items: List[ActionItem] = field(default_factory=list)

    # Quick access lists
    critical_actions: List[ActionItem] = field(default_factory=list)
    high_priority_actions: List[ActionItem] = field(default_factory=list)

    # Insights (AI-generated recommendations)
    insights: List[str] = field(default_factory=list)

    # Data quality indicators
    data_quality: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            "generated_at": self.generated_at,
            "version": self.version,
            "fleet_health": (
                {
                    "score": self.fleet_health.score,
                    "status": self.fleet_health.status,
                    "trend": self.fleet_health.trend,
                    "description": self.fleet_health.description,
                }
                if self.fleet_health
                else None
            ),
            "total_trucks": self.total_trucks,
            "trucks_analyzed": self.trucks_analyzed,
            "urgency_summary": (
                {
                    "critical": self.urgency_summary.critical,
                    "high": self.urgency_summary.high,
                    "medium": self.urgency_summary.medium,
                    "low": self.urgency_summary.low,
                    "ok": self.urgency_summary.ok,
                    "total_issues": self.urgency_summary.total_issues,
                }
                if self.urgency_summary
                else None
            ),
            "sensor_status": (
                {
                    "gps_issues": self.sensor_status.gps_issues,
                    "voltage_issues": self.sensor_status.voltage_issues,
                    "dtc_active": self.sensor_status.dtc_active,
                    "idle_deviation": self.sensor_status.idle_deviation,
                    "total_trucks": self.sensor_status.total_trucks,
                }
                if self.sensor_status
                else None
            ),
            "cost_projection": (
                {
                    "immediate_risk": self.cost_projection.immediate_risk,
                    "week_risk": self.cost_projection.week_risk,
                    "month_risk": self.cost_projection.month_risk,
                }
                if self.cost_projection
                else None
            ),
            "action_items": [item.to_dict() for item in self.action_items],
            "critical_actions": [item.to_dict() for item in self.critical_actions],
            "high_priority_actions": [
                item.to_dict() for item in self.high_priority_actions
            ],
            "insights": self.insights,
            "data_quality": self.data_quality,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# COMMAND CENTER ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class FleetCommandCenter:
    """
    Main engine that combines all data sources into unified actionable insights.

    v1.1.0 Improvements:
    - Component criticality weights for more accurate prioritization
    - UUID-based action IDs for thread safety
    - Comprehensive cost database
    - Fleet-size-aware pattern detection

    v1.3.0 Improvements (Phases 1-3):
    - Critical bug fixes (ActionType, cost_if_ignored, imports)
    - Enhanced deduplication with data preservation
    - Robust component normalization
    - Exponential decay priority scoring
    - Fleet health with distribution analysis
    - TTL caching for performance
    - Comprehensive insights generation

    v1.5.0 Improvements (Phases 4-5):
    - Temporal persistence (2-3 readings before STOP)
    - Adaptive sensor windows (oil=seconds, mpg=days)
    - EWMA/CUSUM trend detection
    - Per-truck risk scoring (0-100)
    - YAML-based configuration
    - Detection vs Decision separation
    - Offline truck alerts
    - Redis trend persistence
    - Failure correlation detection
    - J1939 SPN normalization
    - Real DEF prediction
    - External decision tables
    - MySQL persistence for ML training
    - DEF Predictor Engine (v1.8.0)
    - DTW Pattern Analyzer (v1.8.0)
    - Wialon Data Loader Service (v1.8.0)
    """

    VERSION = "1.8.0"

    # Component to category mapping
    COMPONENT_CATEGORIES = {
        "Bomba de aceite / Filtro": IssueCategory.ENGINE,
        "Sistema de enfriamiento": IssueCategory.ENGINE,
        "Sistema de lubricación": IssueCategory.ENGINE,
        "Turbocompresor": IssueCategory.TURBO,
        "Turbo / Intercooler": IssueCategory.TURBO,
        "Intercooler": IssueCategory.TURBO,
        "Transmisión": IssueCategory.TRANSMISSION,
        "Sistema de combustible": IssueCategory.FUEL,
        "Sistema eléctrico": IssueCategory.ELECTRICAL,
        "Sistema DEF": IssueCategory.DEF,
        "Sistema de frenos de aire": IssueCategory.BRAKES,
        "Eficiencia general": IssueCategory.EFFICIENCY,
    }

    # Component icons
    COMPONENT_ICONS = {
        "Bomba de aceite / Filtro": "🛢️",
        "Sistema de enfriamiento": "❄️",
        "Sistema de lubricación": "💧",
        "Turbocompresor": "🌀",
        "Turbo / Intercooler": "🌀",
        "Intercooler": "🌬️",
        "Transmisión": "⚙️",
        "Sistema de combustible": "⛽",
        "Sistema eléctrico": "🔋",
        "Sistema DEF": "💎",
        "Sistema de frenos de aire": "🛑",
        "Eficiencia general": "📊",
        "GPS": "📡",
        "Voltaje": "🔋",
        "DTC": "🔧",
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.1.0: COMPONENT CRITICALITY WEIGHTS
    # Higher weight = higher priority boost for same days_to_critical
    # Based on: safety impact, cost of failure, fleet downtime risk
    # ═══════════════════════════════════════════════════════════════════════════════
    COMPONENT_CRITICALITY = {
        # Safety-critical (3.0x) - Can cause accidents or strand vehicle
        "Transmisión": 3.0,
        "Sistema de frenos de aire": 3.0,
        "Sistema eléctrico": 2.8,  # Battery = stranded
        # High-cost failure (2.5x) - Expensive repair if ignored
        "Turbocompresor": 2.5,
        "Turbo / Intercooler": 2.5,
        "Sistema de enfriamiento": 2.3,  # Engine damage if overheat
        # Compliance/Operational (2.0x) - Fines or operational issues
        "Sistema DEF": 2.0,  # EPA fines, limp mode
        "Sistema de lubricación": 2.0,
        "Sistema de combustible": 1.8,
        # Monitoring/Efficiency (1.0x) - Important but not urgent
        "Bomba de aceite / Filtro": 1.5,
        "Intercooler": 1.5,
        "Eficiencia general": 1.0,
        "GPS": 0.8,
        "Voltaje": 1.0,
        "DTC": 1.2,
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.1.0: COST DATABASE
    # Replaces string parsing with structured cost data
    # Values in USD, based on industry averages for Class 8 trucks
    # ═══════════════════════════════════════════════════════════════════════════════
    COMPONENT_COSTS = {
        "Transmisión": {"min": 8000, "max": 15000, "avg": 11500},
        "Sistema de frenos de aire": {"min": 2000, "max": 5000, "avg": 3500},
        "Sistema eléctrico": {"min": 1500, "max": 4000, "avg": 2750},
        "Turbocompresor": {"min": 3500, "max": 6000, "avg": 4750},
        "Turbo / Intercooler": {"min": 3500, "max": 6000, "avg": 4750},
        "Sistema de enfriamiento": {"min": 2000, "max": 5000, "avg": 3500},
        "Sistema DEF": {"min": 1500, "max": 4000, "avg": 2750},
        "Sistema de lubricación": {"min": 1000, "max": 3000, "avg": 2000},
        "Sistema de combustible": {"min": 800, "max": 2500, "avg": 1650},
        "Bomba de aceite / Filtro": {"min": 500, "max": 1500, "avg": 1000},
        "Intercooler": {"min": 1000, "max": 2500, "avg": 1750},
        "Eficiencia general": {"min": 0, "max": 500, "avg": 250},
        "GPS": {"min": 100, "max": 500, "avg": 300},
        "Voltaje": {"min": 200, "max": 800, "avg": 500},
        "DTC": {"min": 100, "max": 2000, "avg": 1050},
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.1.0: PATTERN DETECTION THRESHOLDS
    # Based on percentage of fleet, not fixed count
    # ═══════════════════════════════════════════════════════════════════════════════
    PATTERN_THRESHOLDS = {
        "fleet_wide_issue_pct": 0.15,  # 15% of fleet with same issue = pattern
        "min_trucks_for_pattern": 2,  # Minimum trucks to declare pattern
        "anomaly_threshold": 0.7,  # Anomaly score threshold for flagging
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.3.0: COMPONENT NORMALIZATION MAPPING
    # Comprehensive mapping for robust deduplication across sources
    # Maps various component names/keywords to canonical system names
    # ═══════════════════════════════════════════════════════════════════════════════
    COMPONENT_NORMALIZATION = {
        # Oil/Lubrication System
        "oil_system": [
            "aceite",
            "oil",
            "lubricación",
            "lubricacion",
            "oil_press",
            "oil_temp",
            "bomba de aceite",
            "filtro de aceite",
            "sistema de lubricación",
        ],
        # Cooling System
        "cooling_system": [
            "coolant",
            "cool_temp",
            "enfriamiento",
            "temperatura",
            "cooling",
            "radiador",
            "termostato",
            "sistema de enfriamiento",
            "refrigerante",
        ],
        # DEF/AdBlue System
        "def_system": [
            "def",
            "adblue",
            "urea",
            "def_level",
            "sistema def",
            "scr",
            "nox",
            "emisiones",
        ],
        # Transmission System
        "transmission": [
            "transmisión",
            "transmision",
            "transmission",
            "trans",
            "trams_t",
            "caja de cambios",
            "clutch",
            "embrague",
        ],
        # Electrical System
        "electrical": [
            "voltaje",
            "voltage",
            "batería",
            "bateria",
            "battery",
            "eléctrico",
            "electrico",
            "alternador",
            "electrical",
            "volt",
        ],
        # Turbo System
        "turbo_system": [
            "turbo",
            "turbocompresor",
            "intercooler",
            "intake",
            "intk",
            "intk_t",
            "boost",
            "presión de aire",
        ],
        # Fuel System
        "fuel_system": [
            "combustible",
            "fuel",
            "diesel",
            "fuel_lvl",
            "fuel_rate",
            "inyector",
            "bomba de combustible",
        ],
        # Brake System
        "brake_system": ["freno", "frenos", "brake", "brakes", "abs", "aire de frenos"],
        # GPS/Location
        "gps": ["gps", "ubicación", "ubicacion", "location", "posición"],
        # DTC/Diagnostics
        "dtc": ["dtc", "código", "codigo", "diagnostic", "error", "fault"],
        # Engine
        "engine": [
            "motor",
            "engine",
            "rpm",
            "engine_load",
            "potencia",
            "engine_hours",
            "carga del motor",
        ],
        # Efficiency
        "efficiency": [
            "eficiencia",
            "efficiency",
            "mpg",
            "consumo",
            "idle",
            "ralentí",
            "ralenti",
        ],
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.3.0: SOURCE HIERARCHY FOR CONFLICT RESOLUTION
    # Higher weight = more trusted source. Used when merging duplicates.
    # ═══════════════════════════════════════════════════════════════════════════════
    SOURCE_HIERARCHY = {
        "Real-Time Predictive": 100,  # Most trusted - live analysis
        "Predictive Maintenance": 90,  # Trend-based prediction
        "ML Anomaly Detection": 80,  # ML-based outliers
        "Sensor Health Monitor": 70,  # Direct sensor readings
        "DTC Events": 60,  # Diagnostic trouble codes
        "DB Alerts": 50,  # Historical database alerts
        "GPS Quality": 40,  # Location accuracy
        "Voltage Monitor": 40,  # Battery/charging
        "Idle Analysis": 30,  # Efficiency metrics
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.3.0: SENSOR VALIDATION RANGES
    # Valid ranges for sensor data to filter NULL, NaN, and out-of-range values
    # ═══════════════════════════════════════════════════════════════════════════════
    SENSOR_VALID_RANGES = {
        "oil_press": {"min": 0, "max": 150, "unit": "PSI"},
        "oil_temp": {"min": 0, "max": 350, "unit": "°F"},
        "cool_temp": {"min": 0, "max": 300, "unit": "°F"},
        "trams_t": {"min": 0, "max": 350, "unit": "°F"},
        "engine_load": {"min": 0, "max": 100, "unit": "%"},
        "rpm": {"min": 0, "max": 3500, "unit": "RPM"},
        "def_level": {"min": 0, "max": 100, "unit": "%"},
        "voltage": {"min": 0, "max": 30, "unit": "V"},
        "intk_t": {"min": -50, "max": 250, "unit": "°F"},
        "fuel_lvl": {"min": 0, "max": 100, "unit": "%"},
        "fuel_rate": {"min": 0, "max": 50, "unit": "gal/h"},
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 4.2: ADAPTIVE SENSOR WINDOWS
    # Different sensors need different time windows for meaningful analysis
    # ═══════════════════════════════════════════════════════════════════════════════
    SENSOR_WINDOWS = {
        # Fast-changing sensors (seconds to minutes)
        "oil_press": {"window_seconds": 30, "min_readings": 3, "type": "fast"},
        "oil_temp": {"window_seconds": 60, "min_readings": 3, "type": "fast"},
        "cool_temp": {"window_seconds": 60, "min_readings": 3, "type": "fast"},
        "rpm": {"window_seconds": 10, "min_readings": 5, "type": "fast"},
        "voltage": {"window_seconds": 30, "min_readings": 3, "type": "fast"},
        # Medium-changing sensors (minutes to hours)
        "def_level": {"window_seconds": 3600, "min_readings": 2, "type": "medium"},
        "fuel_lvl": {"window_seconds": 1800, "min_readings": 2, "type": "medium"},
        "trams_t": {"window_seconds": 300, "min_readings": 3, "type": "medium"},
        "intk_t": {"window_seconds": 300, "min_readings": 3, "type": "medium"},
        # Slow-changing metrics (hours to days)
        "mpg": {"window_seconds": 86400, "min_readings": 5, "type": "slow"},
        "idle_pct": {"window_seconds": 86400, "min_readings": 3, "type": "slow"},
        "engine_hours": {"window_seconds": 86400, "min_readings": 2, "type": "slow"},
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 4.1: TEMPORAL PERSISTENCE THRESHOLDS
    # Require multiple consecutive readings before triggering STOP actions
    # ═══════════════════════════════════════════════════════════════════════════════
    PERSISTENCE_THRESHOLDS = {
        # Critical sensors: need 2 readings to confirm (avoid glitch-triggered STOP)
        "oil_press": {"min_readings_for_critical": 2, "confirmation_window_sec": 60},
        "cool_temp": {"min_readings_for_critical": 2, "confirmation_window_sec": 120},
        "voltage": {"min_readings_for_critical": 2, "confirmation_window_sec": 60},
        # Medium sensors: need 3 readings for pattern confirmation
        "trams_t": {"min_readings_for_critical": 3, "confirmation_window_sec": 300},
        "def_level": {"min_readings_for_critical": 3, "confirmation_window_sec": 3600},
        # Efficiency metrics: longer patterns needed
        "mpg": {"min_readings_for_critical": 5, "confirmation_window_sec": 86400},
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 4.7: OFFLINE DETECTION THRESHOLDS
    # ═══════════════════════════════════════════════════════════════════════════════
    OFFLINE_THRESHOLDS = {
        "hours_no_data_warning": 2,  # 2 hours without data = warning
        "hours_no_data_critical": 12,  # 12 hours = critical/offline
        "gps_stale_hours": 1,  # GPS data older than 1 hour
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.1: FAILURE CORRELATION PATTERNS
    # Based on industry standards (ATRI, TMC, SAE J1939) and fleet experience
    # ═══════════════════════════════════════════════════════════════════════════════
    FAILURE_CORRELATIONS = {
        "overheating_syndrome": {
            "primary": "cool_temp",
            "correlated": ["oil_temp", "trams_t"],
            "min_correlation": 0.7,
            "cause": "Sistema de enfriamiento comprometido o carga excesiva",
            "action": "Verificar radiador, termostato, bomba de agua y fluidos",
        },
        "electrical_failure": {
            "primary": "voltage",
            "correlated": ["engine_load", "rpm"],
            "min_correlation": 0.6,
            "cause": "Falla de alternador o sistema de carga",
            "action": "Probar alternador y verificar conexiones de batería",
        },
        "fuel_system_degradation": {
            "primary": "fuel_rate",
            "correlated": ["mpg", "engine_load"],
            "min_correlation": 0.65,
            "cause": "Inyectores sucios o filtro de combustible obstruido",
            "action": "Revisar filtros de combustible e inyectores",
        },
        "turbo_lag": {
            "primary": "intk_t",
            "correlated": ["engine_load", "cool_temp"],
            "min_correlation": 0.6,
            "cause": "Turbocompresor o intercooler con problemas",
            "action": "Inspeccionar turbo, intercooler y mangueras de aire",
        },
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.2: J1939 SPN NORMALIZATION
    # Standard Parameter Numbers for consistent component identification
    # ═══════════════════════════════════════════════════════════════════════════════
    J1939_SPN_MAP = {
        # Engine
        190: {"component": "engine", "name": "Engine Speed", "unit": "rpm"},
        92: {"component": "engine_load", "name": "Engine Load", "unit": "%"},
        # Temperatures
        110: {
            "component": "cool_temp",
            "name": "Engine Coolant Temperature",
            "unit": "°C",
        },
        175: {"component": "oil_temp", "name": "Engine Oil Temperature", "unit": "°C"},
        177: {
            "component": "trams_t",
            "name": "Transmission Oil Temperature",
            "unit": "°C",
        },
        105: {
            "component": "intk_t",
            "name": "Intake Manifold Temperature",
            "unit": "°C",
        },
        # Pressures
        100: {"component": "oil_press", "name": "Engine Oil Pressure", "unit": "kPa"},
        # DEF/SCR
        5245: {"component": "def_level", "name": "DEF Tank Level", "unit": "%"},
        5246: {"component": "def_temp", "name": "DEF Temperature", "unit": "°C"},
        # Electrical
        168: {"component": "voltage", "name": "Battery Voltage", "unit": "V"},
        # Fuel
        96: {"component": "fuel_lvl", "name": "Fuel Level", "unit": "%"},
        183: {"component": "fuel_rate", "name": "Fuel Rate", "unit": "L/h"},
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.3: DEF CONSUMPTION AVERAGES (Fleet Admin Decision - Simulated)
    # Based on typical Class 8 Freightliner/Peterbilt consumption rates
    # DEF consumption is typically 2-3% of diesel consumption
    # ═══════════════════════════════════════════════════════════════════════════════
    DEF_CONSUMPTION_CONFIG = {
        "tank_capacity_liters": 75,  # Typical DEF tank size
        "avg_consumption_pct_diesel": 2.5,  # 2.5% of diesel = DEF consumption
        "avg_daily_diesel_liters": 150,  # ~40 gallons/day for Class 8
        "derate_threshold_pct": 5,  # Truck derates at 5% DEF
        "warning_threshold_pct": 15,  # Warning at 15% DEF
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.4: EXTERNAL DECISION TABLE (Action Steps by Component)
    # This would normally be loaded from YAML, but defined here as default
    # Fleet admin can override via command_center_config.yaml
    # ═══════════════════════════════════════════════════════════════════════════════
    ACTION_DECISION_TABLE = {
        "oil_system": {
            "CRITICAL": [
                "⚠️ DETENER EL CAMIÓN INMEDIATAMENTE de forma segura",
                "📞 Llamar a servicio de emergencia o grúa",
                "🔧 NO intentar continuar - daño de motor inminente",
            ],
            "HIGH": [
                "📅 Programar servicio para HOY o mañana temprano",
                "✅ Verificar nivel de aceite antes de cada viaje",
                "🔍 Inspeccionar por fugas visibles",
            ],
            "MEDIUM": [
                "📅 Agendar cambio de aceite esta semana",
                "✅ Monitorear presión de aceite diariamente",
            ],
            "LOW": [
                "📋 Incluir en próximo servicio preventivo",
                "✅ Continuar monitoreo normal",
            ],
        },
        "cooling_system": {
            "CRITICAL": [
                "⚠️ DETENER - Riesgo de daño catastrófico al motor",
                "⏳ Dejar enfriar motor 30 minutos antes de abrir radiador",
                "📞 Solicitar asistencia en carretera",
            ],
            "HIGH": [
                "📅 Servicio urgente - no operar en cargas pesadas",
                "✅ Verificar nivel de coolant",
                "🔍 Inspeccionar mangueras y radiador",
            ],
            "MEDIUM": [
                "📅 Agendar inspección de sistema de enfriamiento",
                "✅ Monitorear temperatura continuamente",
            ],
            "LOW": [
                "📋 Revisar en próximo mantenimiento",
            ],
        },
        "def_system": {
            "CRITICAL": [
                "⛽ LLENAR DEF INMEDIATAMENTE - Derate inminente",
                "⚠️ Camión entrará en modo de baja potencia",
                "📍 Ubicar estación de DEF más cercana",
            ],
            "HIGH": [
                "⛽ Llenar DEF hoy - menos de 2 días restantes",
                "📋 Programar revisión del sistema SCR",
            ],
            "MEDIUM": [
                "⛽ Planificar recarga de DEF esta semana",
                "✅ Sistema DEF funcionando normalmente",
            ],
            "LOW": [
                "📋 DEF OK - incluir en rutina de llenado",
            ],
        },
        "transmission": {
            "CRITICAL": [
                "⚠️ DETENER - No forzar transmisión dañada",
                "📞 Llamar grúa especializada",
                "💰 Reparación urgente: $8,000-$15,000",
            ],
            "HIGH": [
                "📅 Servicio de transmisión esta semana",
                "⚠️ Evitar cargas pesadas y pendientes",
                "🔍 Verificar nivel y color de fluido",
            ],
            "MEDIUM": [
                "📅 Inspección de transmisión programada",
                "✅ Cambio de fluido si >60,000 millas",
            ],
            "LOW": [
                "📋 Monitoreo continuo",
            ],
        },
        "electrical": {
            "CRITICAL": [
                "⚠️ Riesgo de quedar varado - batería crítica",
                "📞 Tener cables de arranque o servicio listo",
                "🔧 Probar alternador inmediatamente",
            ],
            "HIGH": [
                "📅 Servicio eléctrico esta semana",
                "✅ Probar batería con multímetro",
                "🔍 Verificar conexiones y terminales",
            ],
            "MEDIUM": [
                "📋 Incluir prueba de batería en servicio",
            ],
            "LOW": [
                "✅ Sistema eléctrico OK",
            ],
        },
        "turbo_system": {
            "CRITICAL": [
                "⚠️ DETENER - Riesgo de falla catastrófica de turbo",
                "🔧 Turbo puede soltar fragmentos al motor",
                "📞 Servicio de emergencia requerido",
            ],
            "HIGH": [
                "📅 Inspección de turbo urgente",
                "⚠️ Reducir carga y velocidad",
                "🔍 Escuchar por ruidos anormales",
            ],
            "MEDIUM": [
                "📅 Agendar inspección de turbo",
                "✅ Verificar mangueras de aire",
            ],
            "LOW": [
                "📋 Monitoreo de turbo normal",
            ],
        },
    }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.5: TIME HORIZON SCORING WEIGHTS
    # Separates immediate, short-term, and medium-term priorities
    # ═══════════════════════════════════════════════════════════════════════════════
    TIME_HORIZON_WEIGHTS = {
        "immediate": {  # 0-24 hours
            "days_weight": 0.50,
            "criticality_weight": 0.30,
            "cost_weight": 0.15,
            "anomaly_weight": 0.05,
        },
        "short_term": {  # 1-7 days
            "days_weight": 0.40,
            "criticality_weight": 0.25,
            "cost_weight": 0.20,
            "anomaly_weight": 0.15,
        },
        "medium_term": {  # 7-30 days
            "days_weight": 0.30,
            "criticality_weight": 0.20,
            "cost_weight": 0.25,
            "anomaly_weight": 0.25,
        },
    }

    # Component normalization cache for performance
    _component_cache: Dict[str, str] = {}

    # v1.5.0 FASE 4.1: Sensor readings buffer for temporal persistence
    _sensor_readings_buffer: Dict[str, deque] = {}
    _sensor_buffer_lock = threading.Lock()

    # v1.5.0 FASE 4.3: EWMA state for trend detection
    _ewma_state: Dict[str, Dict[str, float]] = {}
    _cusum_state: Dict[str, Dict[str, float]] = {}

    # v1.5.0 FASE 4.4: Per-truck risk scores cache
    _truck_risk_cache: Dict[str, TruckRiskScore] = {}
    _risk_cache_timestamp: Optional[datetime] = None
    _RISK_CACHE_TTL_SECONDS = 300  # 5 minutes

    # v1.5.0 FASE 4.8: Redis client for persistence (optional)
    _redis_client: Optional[Any] = None

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize Fleet Command Center.

        v1.5.0: Added optional config_path for YAML configuration loading.

        Args:
            config_path: Optional path to YAML config file for custom thresholds
        """
        # Note: _action_counter kept for backward compatibility but not used for IDs
        self._action_counter = 0
        # Clear component cache on init
        FleetCommandCenter._component_cache = {}

        # v1.5.0 FASE 4.1: Initialize sensor buffers
        FleetCommandCenter._sensor_readings_buffer = {}

        # v1.5.0 FASE 4.3: Initialize EWMA/CUSUM state
        FleetCommandCenter._ewma_state = {}
        FleetCommandCenter._cusum_state = {}

        # v1.5.0 FASE 4.4: Initialize risk cache
        FleetCommandCenter._truck_risk_cache = {}
        FleetCommandCenter._risk_cache_timestamp = None

        # v1.5.0 FASE 4.5: Load external config if provided
        self._load_yaml_config(config_path)

        # v1.5.0 FASE 4.5b: Try to load from DB (overrides YAML)
        self._load_db_config()

        # v1.5.0 FASE 4.8: Initialize Redis connection if available
        self._init_redis()

    def _load_yaml_config(self, config_path: Optional[str] = None) -> None:
        """
        v1.5.0 FASE 4.5: Load configuration from YAML file.

        Allows fleet administrators to customize thresholds without code changes.
        Falls back to defaults if file not found.
        """
        if config_path is None:
            # Try default locations
            possible_paths = [
                Path("command_center_config.yaml"),
                Path("config/command_center_config.yaml"),
                Path(__file__).parent / "command_center_config.yaml",
            ]
            for path in possible_paths:
                if path.exists():
                    config_path = str(path)
                    break

        if config_path and Path(config_path).exists():
            try:
                with open(config_path, "r") as f:
                    config = yaml.safe_load(f) or {}

                # Override class attributes with YAML values
                if "sensor_valid_ranges" in config:
                    self.SENSOR_VALID_RANGES.update(config["sensor_valid_ranges"])
                if "sensor_windows" in config:
                    self.SENSOR_WINDOWS.update(config["sensor_windows"])
                if "persistence_thresholds" in config:
                    self.PERSISTENCE_THRESHOLDS.update(config["persistence_thresholds"])
                if "offline_thresholds" in config:
                    self.OFFLINE_THRESHOLDS.update(config["offline_thresholds"])
                if "failure_correlations" in config:
                    self.FAILURE_CORRELATIONS.update(config["failure_correlations"])
                if "def_consumption_config" in config:
                    self.DEF_CONSUMPTION_CONFIG.update(config["def_consumption_config"])
                if "action_decision_table" in config:
                    self.ACTION_DECISION_TABLE.update(config["action_decision_table"])
                if "time_horizon_weights" in config:
                    self.TIME_HORIZON_WEIGHTS.update(config["time_horizon_weights"])

                logger.info(f"✅ Loaded configuration from {config_path}")
            except Exception as e:
                logger.warning(f"⚠️ Could not load config from {config_path}: {e}")

    def _load_db_config(self) -> None:
        """
        v1.5.0 FASE 4.5b: Load configuration from MySQL database.

        Reads from `command_center_config` table if it exists.
        This overrides YAML config for values stored in DB.
        Falls back gracefully if table doesn't exist or DB is unavailable.
        """
        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()

            # Check if table exists first
            with engine.connect() as conn:
                check_query = text(
                    """
                    SELECT COUNT(*) as cnt 
                    FROM information_schema.tables 
                    WHERE table_schema = DATABASE() 
                    AND table_name = 'command_center_config'
                """
                )
                result = conn.execute(check_query).fetchone()
                if not result or result[0] == 0:
                    logger.debug(
                        "📝 command_center_config table not found - using defaults"
                    )
                    return

                # Load active configuration
                config_query = text(
                    """
                    SELECT config_key, config_value, category 
                    FROM command_center_config 
                    WHERE is_active = TRUE
                """
                )
                rows = conn.execute(config_query).fetchall()

                if not rows:
                    logger.debug("📝 No active config in DB - using defaults")
                    return

                config_loaded = 0
                for row in rows:
                    config_key = row[0]
                    config_value = row[1]
                    category = row[2]

                    # Parse JSON value
                    try:
                        if isinstance(config_value, str):
                            value = json.loads(config_value)
                        else:
                            value = config_value
                    except json.JSONDecodeError:
                        logger.warning(f"⚠️ Invalid JSON in config {config_key}")
                        continue

                    # Apply config based on key pattern
                    if config_key.startswith("sensor_range_"):
                        sensor_name = config_key.replace("sensor_range_", "")
                        self.SENSOR_VALID_RANGES[sensor_name] = value
                        config_loaded += 1
                    elif config_key.startswith("persistence_"):
                        sensor_name = config_key.replace("persistence_", "")
                        self.PERSISTENCE_THRESHOLDS[sensor_name] = value
                        config_loaded += 1
                    elif config_key == "offline_thresholds":
                        self.OFFLINE_THRESHOLDS.update(value)
                        config_loaded += 1
                    elif config_key == "def_consumption":
                        self.DEF_CONSUMPTION_CONFIG.update(value)
                        config_loaded += 1
                    elif config_key.startswith("scoring_"):
                        horizon = config_key.replace("scoring_", "")
                        if horizon in self.TIME_HORIZON_WEIGHTS:
                            self.TIME_HORIZON_WEIGHTS[horizon].update(value)
                            config_loaded += 1
                    elif config_key.startswith("correlation_"):
                        pattern_name = config_key.replace("correlation_", "")
                        self.FAILURE_CORRELATIONS[pattern_name] = value
                        config_loaded += 1

                if config_loaded > 0:
                    logger.info(
                        f"✅ Loaded {config_loaded} config values from database"
                    )

        except ImportError:
            logger.debug("📝 database_mysql not available - skipping DB config")
        except Exception as e:
            logger.warning(f"⚠️ Could not load config from DB: {e}")

    def _init_redis(self) -> None:
        """
        v1.5.0 FASE 4.8: Initialize Redis connection for trend persistence.

        Falls back gracefully to in-memory storage if Redis unavailable.
        """
        if not REDIS_AVAILABLE:
            logger.info("📝 Redis not available - using in-memory trend storage")
            return

        redis_url = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            self._redis_client = redis.from_url(redis_url)
            self._redis_client.ping()
            logger.info(f"✅ Connected to Redis at {redis_url}")
        except Exception as e:
            logger.warning(f"⚠️ Redis connection failed: {e}. Using in-memory storage.")
            self._redis_client = None

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.6: MYSQL PERSISTENCE FOR ML (Risk, Anomalies, Algorithm State)
    # ═══════════════════════════════════════════════════════════════════════════════

    def persist_risk_score(self, risk: "TruckRiskScore") -> bool:
        """
        Persist a truck risk score to MySQL for ML training data.

        v1.5.0 FASE 5.6: Every risk score calculation is saved for future ML.

        Args:
            risk: TruckRiskScore to persist

        Returns:
            True if successful, False otherwise
        """
        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()

            # Map risk level to ENUM
            risk_level_map = {
                "critical": "CRITICAL",
                "high": "HIGH",
                "medium": "MEDIUM",
                "low": "LOW",
                "healthy": "LOW",
            }

            with engine.connect() as conn:
                query = text(
                    """
                    INSERT INTO cc_risk_history (
                        truck_id, risk_score, risk_level,
                        active_issues_count, days_since_maintenance,
                        timestamp
                    ) VALUES (
                        :truck_id, :risk_score, :risk_level,
                        :active_issues, :days_since_maint,
                        NOW()
                    )
                """
                )
                conn.execute(
                    query,
                    {
                        "truck_id": risk.truck_id,
                        "risk_score": risk.risk_score,
                        "risk_level": risk_level_map.get(risk.risk_level, "LOW"),
                        "active_issues": risk.active_issues_count,
                        "days_since_maint": risk.days_since_last_maintenance,
                    },
                )
                conn.commit()
            return True
        except ImportError:
            logger.debug("📝 database_mysql not available - skipping risk persistence")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Could not persist risk score: {e}")
            return False

    def persist_anomaly(
        self,
        truck_id: str,
        sensor_name: str,
        anomaly_type: str,
        severity: str,
        sensor_value: float,
        ewma_value: Optional[float] = None,
        cusum_value: Optional[float] = None,
        threshold: Optional[float] = None,
        z_score: Optional[float] = None,
    ) -> bool:
        """
        Persist an anomaly detection event to MySQL for ML training.

        v1.5.0 FASE 5.6: Records every detected anomaly for pattern learning.

        Args:
            truck_id: Truck identifier
            sensor_name: Name of sensor that triggered anomaly
            anomaly_type: One of 'EWMA', 'CUSUM', 'THRESHOLD', 'CORRELATION'
            severity: One of 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
            sensor_value: Current sensor value
            ewma_value: EWMA value at detection time
            cusum_value: CUSUM value at detection time
            threshold: Threshold that was exceeded
            z_score: Z-score if applicable

        Returns:
            True if successful, False otherwise
        """
        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()

            with engine.connect() as conn:
                query = text(
                    """
                    INSERT INTO cc_anomaly_history (
                        truck_id, sensor_name, anomaly_type, severity,
                        sensor_value, ewma_value, cusum_value, 
                        threshold_used, z_score, detected_at
                    ) VALUES (
                        :truck_id, :sensor_name, :anomaly_type, :severity,
                        :sensor_value, :ewma_value, :cusum_value,
                        :threshold, :z_score, NOW()
                    )
                """
                )
                conn.execute(
                    query,
                    {
                        "truck_id": truck_id,
                        "sensor_name": sensor_name,
                        "anomaly_type": anomaly_type.upper(),
                        "severity": severity.upper(),
                        "sensor_value": sensor_value,
                        "ewma_value": ewma_value,
                        "cusum_value": cusum_value,
                        "threshold": threshold,
                        "z_score": z_score,
                    },
                )
                conn.commit()
            return True
        except ImportError:
            logger.debug(
                "📝 database_mysql not available - skipping anomaly persistence"
            )
            return False
        except Exception as e:
            logger.warning(f"⚠️ Could not persist anomaly: {e}")
            return False

    def persist_algorithm_state(
        self,
        truck_id: str,
        sensor_name: str,
        ewma_value: Optional[float] = None,
        ewma_variance: Optional[float] = None,
        cusum_high: float = 0.0,
        cusum_low: float = 0.0,
        baseline_mean: Optional[float] = None,
        baseline_std: Optional[float] = None,
        samples_count: int = 0,
        trend_direction: str = "STABLE",
        trend_slope: Optional[float] = None,
    ) -> bool:
        """
        Persist EWMA/CUSUM algorithm state for service restart resilience.

        v1.5.0 FASE 5.6: Saves algorithm state so it survives restarts.

        Args:
            truck_id: Truck identifier
            sensor_name: Sensor name
            ewma_value: Current EWMA value
            ewma_variance: Current EWMA variance
            cusum_high: Current CUSUM high value
            cusum_low: Current CUSUM low value
            baseline_mean: Baseline mean for comparison
            baseline_std: Baseline standard deviation
            samples_count: Number of samples processed
            trend_direction: One of 'UP', 'DOWN', 'STABLE'
            trend_slope: Calculated slope of trend

        Returns:
            True if successful, False otherwise
        """
        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()

            with engine.connect() as conn:
                # UPSERT - insert or update on duplicate key
                query = text(
                    """
                    INSERT INTO cc_algorithm_state (
                        truck_id, sensor_name,
                        ewma_value, ewma_variance,
                        cusum_high, cusum_low,
                        baseline_mean, baseline_std, samples_count,
                        trend_direction, trend_slope,
                        updated_at
                    ) VALUES (
                        :truck_id, :sensor_name,
                        :ewma_value, :ewma_variance,
                        :cusum_high, :cusum_low,
                        :baseline_mean, :baseline_std, :samples_count,
                        :trend_direction, :trend_slope,
                        NOW()
                    )
                    ON DUPLICATE KEY UPDATE
                        ewma_value = VALUES(ewma_value),
                        ewma_variance = VALUES(ewma_variance),
                        cusum_high = VALUES(cusum_high),
                        cusum_low = VALUES(cusum_low),
                        baseline_mean = VALUES(baseline_mean),
                        baseline_std = VALUES(baseline_std),
                        samples_count = VALUES(samples_count),
                        trend_direction = VALUES(trend_direction),
                        trend_slope = VALUES(trend_slope),
                        updated_at = NOW()
                """
                )
                conn.execute(
                    query,
                    {
                        "truck_id": truck_id,
                        "sensor_name": sensor_name,
                        "ewma_value": ewma_value,
                        "ewma_variance": ewma_variance,
                        "cusum_high": cusum_high,
                        "cusum_low": cusum_low,
                        "baseline_mean": baseline_mean,
                        "baseline_std": baseline_std,
                        "samples_count": samples_count,
                        "trend_direction": trend_direction.upper(),
                        "trend_slope": trend_slope,
                    },
                )
                conn.commit()
            return True
        except ImportError:
            logger.debug("📝 database_mysql not available - skipping state persistence")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Could not persist algorithm state: {e}")
            return False

    def persist_correlation_event(
        self,
        truck_id: str,
        pattern_name: str,
        pattern_description: str,
        confidence: float,
        sensors_involved: List[str],
        sensor_values: Dict[str, float],
        predicted_component: Optional[str] = None,
        predicted_failure_days: Optional[int] = None,
        recommended_action: Optional[str] = None,
    ) -> bool:
        """
        Persist a multi-sensor correlation event for ML training.

        v1.5.0 FASE 5.6: Saves detected failure patterns.

        Args:
            truck_id: Truck identifier
            pattern_name: Name of detected pattern (e.g., 'engine_overheat')
            pattern_description: Human-readable description
            confidence: Confidence score (0-1)
            sensors_involved: List of sensor names in pattern
            sensor_values: Dict of sensor_name → value at detection time
            predicted_component: Component predicted to fail
            predicted_failure_days: Estimated days until failure
            recommended_action: Recommended maintenance action

        Returns:
            True if successful, False otherwise
        """
        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()

            with engine.connect() as conn:
                query = text(
                    """
                    INSERT INTO cc_correlation_events (
                        truck_id, pattern_name, pattern_description, confidence,
                        sensors_involved, sensor_values,
                        predicted_component, predicted_failure_days, recommended_action,
                        detected_at
                    ) VALUES (
                        :truck_id, :pattern_name, :pattern_desc, :confidence,
                        :sensors_json, :values_json,
                        :pred_component, :pred_days, :rec_action,
                        NOW()
                    )
                """
                )
                conn.execute(
                    query,
                    {
                        "truck_id": truck_id,
                        "pattern_name": pattern_name,
                        "pattern_desc": pattern_description,
                        "confidence": confidence,
                        "sensors_json": json.dumps(sensors_involved),
                        "values_json": json.dumps(sensor_values),
                        "pred_component": predicted_component,
                        "pred_days": predicted_failure_days,
                        "rec_action": recommended_action,
                    },
                )
                conn.commit()
            return True
        except ImportError:
            logger.debug(
                "📝 database_mysql not available - skipping correlation persistence"
            )
            return False
        except Exception as e:
            logger.warning(f"⚠️ Could not persist correlation event: {e}")
            return False

    def persist_def_reading(
        self,
        truck_id: str,
        def_level: float,
        fuel_used: Optional[float] = None,
        estimated_def_used: Optional[float] = None,
        consumption_rate: Optional[float] = None,
        is_refill: bool = False,
    ) -> bool:
        """
        Persist DEF level reading for ML consumption prediction.

        v1.5.0 FASE 5.6: Saves DEF data for consumption model training.

        Args:
            truck_id: Truck identifier
            def_level: Current DEF level (%)
            fuel_used: Fuel used since last refill (gallons)
            estimated_def_used: Estimated DEF consumed (gallons)
            consumption_rate: DEF gallons per 100 gallons diesel
            is_refill: True if this is a refill event

        Returns:
            True if successful, False otherwise
        """
        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()

            with engine.connect() as conn:
                query = text(
                    """
                    INSERT INTO cc_def_history (
                        truck_id, def_level, fuel_used_since_refill,
                        estimated_def_used, consumption_rate,
                        is_refill_event, timestamp
                    ) VALUES (
                        :truck_id, :def_level, :fuel_used,
                        :def_used, :consumption_rate,
                        :is_refill, NOW()
                    )
                """
                )
                conn.execute(
                    query,
                    {
                        "truck_id": truck_id,
                        "def_level": def_level,
                        "fuel_used": fuel_used,
                        "def_used": estimated_def_used,
                        "consumption_rate": consumption_rate,
                        "is_refill": is_refill,
                    },
                )
                conn.commit()
            return True
        except ImportError:
            logger.debug("📝 database_mysql not available - skipping DEF persistence")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Could not persist DEF reading: {e}")
            return False

    def load_algorithm_state(self, truck_id: str, sensor_name: str) -> Optional[Dict]:
        """
        Load persisted algorithm state from MySQL on service startup.

        v1.5.0 FASE 5.6: Restores EWMA/CUSUM state after restart.

        Args:
            truck_id: Truck identifier
            sensor_name: Sensor name

        Returns:
            Dict with algorithm state or None if not found
        """
        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()

            with engine.connect() as conn:
                query = text(
                    """
                    SELECT 
                        ewma_value, ewma_variance,
                        cusum_high, cusum_low,
                        baseline_mean, baseline_std, samples_count,
                        trend_direction, trend_slope, updated_at
                    FROM cc_algorithm_state
                    WHERE truck_id = :truck_id AND sensor_name = :sensor_name
                """
                )
                result = conn.execute(
                    query, {"truck_id": truck_id, "sensor_name": sensor_name}
                ).fetchone()

                if result:
                    return {
                        "ewma_value": result[0],
                        "ewma_variance": result[1],
                        "cusum_high": result[2],
                        "cusum_low": result[3],
                        "baseline_mean": result[4],
                        "baseline_std": result[5],
                        "samples_count": result[6],
                        "trend_direction": result[7],
                        "trend_slope": result[8],
                        "updated_at": result[9],
                    }
                return None
        except ImportError:
            return None
        except Exception as e:
            logger.warning(f"⚠️ Could not load algorithm state: {e}")
            return None

    def batch_persist_risk_scores(self, risks: List["TruckRiskScore"]) -> int:
        """
        Batch persist multiple risk scores for efficiency.

        v1.5.0 FASE 5.6: Efficient bulk insert for periodic snapshots.

        Args:
            risks: List of TruckRiskScore to persist

        Returns:
            Number of successfully persisted records
        """
        if not risks:
            return 0

        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()

            risk_level_map = {
                "critical": "CRITICAL",
                "high": "HIGH",
                "medium": "MEDIUM",
                "low": "LOW",
                "healthy": "LOW",
            }

            values = []
            for risk in risks:
                values.append(
                    {
                        "truck_id": risk.truck_id,
                        "risk_score": risk.risk_score,
                        "risk_level": risk_level_map.get(risk.risk_level, "LOW"),
                        "active_issues": risk.active_issues_count,
                        "days_since_maint": risk.days_since_last_maintenance,
                    }
                )

            with engine.connect() as conn:
                query = text(
                    """
                    INSERT INTO cc_risk_history (
                        truck_id, risk_score, risk_level,
                        active_issues_count, days_since_maintenance,
                        timestamp
                    ) VALUES (
                        :truck_id, :risk_score, :risk_level,
                        :active_issues, :days_since_maint,
                        NOW()
                    )
                """
                )
                for v in values:
                    conn.execute(query, v)
                conn.commit()
            return len(values)
        except ImportError:
            logger.debug("📝 database_mysql not available - skipping batch persistence")
            return 0
        except Exception as e:
            logger.warning(f"⚠️ Could not batch persist risk scores: {e}")
            return 0

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 4.1: TEMPORAL PERSISTENCE (Avoid glitch-triggered STOP)
    # ═══════════════════════════════════════════════════════════════════════════════

    def _record_sensor_reading(
        self, truck_id: str, sensor_name: str, value: float
    ) -> None:
        """
        Record a sensor reading for temporal persistence analysis.

        v1.5.0 FASE 4.1: Stores 2-3 readings before making critical decisions
        to avoid false positives from sensor glitches.
        """
        key = f"{truck_id}:{sensor_name}"
        reading = SensorReading(
            sensor_name=sensor_name,
            truck_id=truck_id,
            value=value,
            timestamp=datetime.now(timezone.utc),
            is_valid=True,
        )

        with self._sensor_buffer_lock:
            if key not in self._sensor_readings_buffer:
                # Keep last 10 readings per sensor per truck
                self._sensor_readings_buffer[key] = deque(maxlen=10)
            self._sensor_readings_buffer[key].append(reading)

    def _has_persistent_critical_reading(
        self, truck_id: str, sensor_name: str, threshold: float, above: bool = True
    ) -> Tuple[bool, int]:
        """
        Check if a critical condition has persisted across multiple readings.

        v1.5.0 FASE 4.1: Returns True only if we have min_readings_for_critical
        consecutive readings above/below threshold.

        Args:
            truck_id: Truck identifier
            sensor_name: Sensor name
            threshold: Critical threshold value
            above: If True, check for values above threshold. If False, below.

        Returns:
            Tuple of (is_persistent, consecutive_count)
        """
        key = f"{truck_id}:{sensor_name}"
        config = self.PERSISTENCE_THRESHOLDS.get(
            sensor_name,
            {"min_readings_for_critical": 2, "confirmation_window_sec": 120},
        )
        min_readings = config["min_readings_for_critical"]
        window_sec = config["confirmation_window_sec"]

        with self._sensor_buffer_lock:
            readings = list(self._sensor_readings_buffer.get(key, []))

        if len(readings) < min_readings:
            return False, len(readings)

        # Filter to readings within confirmation window
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_sec)
        recent = [r for r in readings if r.timestamp > cutoff]

        if len(recent) < min_readings:
            return False, len(recent)

        # Check last N readings
        last_n = recent[-min_readings:]
        if above:
            critical_count = sum(1 for r in last_n if r.value > threshold)
        else:
            critical_count = sum(1 for r in last_n if r.value < threshold)

        is_persistent = critical_count >= min_readings
        return is_persistent, critical_count

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 4.3: EWMA/CUSUM FOR SUBTLE TREND DETECTION
    # ═══════════════════════════════════════════════════════════════════════════════

    def _calculate_ewma(
        self, truck_id: str, sensor_name: str, new_value: float, alpha: float = 0.3
    ) -> float:
        """
        Calculate Exponentially Weighted Moving Average for trend detection.

        v1.5.0 FASE 4.3: EWMA is more responsive to recent changes than simple
        moving average, helping detect subtle degradation patterns.

        Formula: EWMA_t = α * X_t + (1 - α) * EWMA_{t-1}

        Args:
            truck_id: Truck identifier
            sensor_name: Sensor name
            new_value: New reading value
            alpha: Smoothing factor (0-1). Higher = more weight to recent values.

        Returns:
            Current EWMA value
        """
        key = f"{truck_id}:{sensor_name}"

        if key not in self._ewma_state:
            self._ewma_state[key] = {"ewma": new_value, "count": 1}
            return new_value

        state = self._ewma_state[key]
        old_ewma = state["ewma"]
        new_ewma = alpha * new_value + (1 - alpha) * old_ewma

        state["ewma"] = new_ewma
        state["count"] += 1

        return new_ewma

    def _calculate_cusum(
        self,
        truck_id: str,
        sensor_name: str,
        new_value: float,
        target: float,
        threshold: float = 5.0,
    ) -> Tuple[float, float, bool]:
        """
        Calculate CUSUM (Cumulative Sum) for change-point detection.

        v1.5.0 FASE 4.3: CUSUM detects shifts in the mean of a process,
        helping identify when a sensor starts trending abnormally.

        Args:
            truck_id: Truck identifier
            sensor_name: Sensor name
            new_value: New reading value
            target: Expected/normal value (baseline)
            threshold: Alert threshold for CUSUM

        Returns:
            Tuple of (cusum_high, cusum_low, is_alert)
        """
        key = f"{truck_id}:{sensor_name}"

        if key not in self._cusum_state:
            self._cusum_state[key] = {"high": 0.0, "low": 0.0}

        state = self._cusum_state[key]
        deviation = new_value - target

        # Update CUSUM values
        state["high"] = max(0, state["high"] + deviation)
        state["low"] = min(0, state["low"] + deviation)

        # Check for alert condition
        is_alert = state["high"] > threshold or abs(state["low"]) > threshold

        return state["high"], state["low"], is_alert

    def _detect_trend_with_ewma_cusum(
        self,
        truck_id: str,
        sensor_name: str,
        values: List[float],
        baseline: Optional[float] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """
        Analyze a series of values using EWMA and CUSUM combined.

        v1.5.0 FASE 4.3: Combined analysis provides:
        - EWMA: Current smoothed trend
        - CUSUM: Change-point detection

        v1.5.0 FASE 5.6: Now persists anomalies and algorithm state to MySQL.

        Args:
            truck_id: Truck identifier
            sensor_name: Sensor name
            values: List of recent values
            baseline: Optional baseline value. If None, uses first value.
            persist: Whether to persist to MySQL (default True)

        Returns:
            Dict with trend analysis results
        """
        if not values:
            return {
                "trend": "unknown",
                "ewma": None,
                "cusum_alert": False,
                "change_detected": False,
            }

        baseline = baseline if baseline is not None else values[0]

        # Process all values through EWMA and CUSUM
        ewma_value = None
        cusum_alert = False
        cusum_high = 0.0
        cusum_low = 0.0

        for value in values:
            ewma_value = self._calculate_ewma(truck_id, sensor_name, value)
            cusum_high, cusum_low, alert = self._calculate_cusum(
                truck_id, sensor_name, value, baseline
            )
            if alert:
                cusum_alert = True

        # Determine trend direction
        if ewma_value is not None and baseline is not None:
            pct_change = (
                ((ewma_value - baseline) / baseline * 100) if baseline != 0 else 0
            )

            if pct_change > 5:
                trend = "increasing"
            elif pct_change < -5:
                trend = "decreasing"
            else:
                trend = "stable"
        else:
            trend = "stable"
            pct_change = 0

        # v1.5.0 FASE 5.6: Persist to MySQL for ML
        if persist and values:
            # Calculate std for baseline
            if len(values) > 1:
                mean_val = sum(values) / len(values)
                variance = sum((x - mean_val) ** 2 for x in values) / len(values)
                std_val = variance**0.5
            else:
                std_val = None

            # Persist algorithm state
            self.persist_algorithm_state(
                truck_id=truck_id,
                sensor_name=sensor_name,
                ewma_value=ewma_value,
                cusum_high=cusum_high,
                cusum_low=cusum_low,
                baseline_mean=baseline,
                baseline_std=std_val,
                samples_count=len(values),
                trend_direction=(
                    trend.upper() if trend in ("increasing", "decreasing") else "STABLE"
                ),
                trend_slope=pct_change if pct_change else None,
            )

            # Persist anomaly if CUSUM detected change
            if cusum_alert:
                severity = "HIGH" if abs(pct_change) > 15 else "MEDIUM"
                self.persist_anomaly(
                    truck_id=truck_id,
                    sensor_name=sensor_name,
                    anomaly_type="CUSUM",
                    severity=severity,
                    sensor_value=values[-1] if values else 0,
                    ewma_value=ewma_value,
                    cusum_value=max(cusum_high, abs(cusum_low)),
                    threshold=5.0,
                    z_score=pct_change / 100 if pct_change else None,
                )

        return {
            "trend": trend,
            "ewma": round(ewma_value, 2) if ewma_value else None,
            "baseline": round(baseline, 2) if baseline else None,
            "cusum_alert": cusum_alert,
            "change_detected": cusum_alert,
            "pct_change": round(pct_change, 1) if pct_change else 0,
        }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 4.4: TRUCK RISK SCORE (0-100)
    # ═══════════════════════════════════════════════════════════════════════════════

    def calculate_truck_risk_score(
        self,
        truck_id: str,
        action_items: List[ActionItem],
        days_since_maintenance: Optional[int] = None,
        sensor_alerts: Optional[Dict[str, bool]] = None,
    ) -> TruckRiskScore:
        """
        Calculate comprehensive risk score for a single truck.

        v1.5.0 FASE 4.4: Risk score (0-100) allows identifying top 10 at-risk trucks.

        Scoring components:
        - Active issues severity (40%)
        - Days since maintenance (20%)
        - Trend analysis (20%)
        - Sensor alert status (20%)

        Args:
            truck_id: Truck identifier
            action_items: List of ActionItems for this truck
            days_since_maintenance: Days since last PM service
            sensor_alerts: Dict of sensor_name → is_alerting

        Returns:
            TruckRiskScore with risk level and contributing factors
        """
        score = 0.0
        factors = []

        # 1. Active issues severity (40%)
        truck_items = [i for i in action_items if i.truck_id == truck_id]
        issue_score = 0.0

        for item in truck_items:
            if item.priority == Priority.CRITICAL:
                issue_score += 25
                factors.append(f"Critical: {item.component}")
            elif item.priority == Priority.HIGH:
                issue_score += 15
                factors.append(f"High: {item.component}")
            elif item.priority == Priority.MEDIUM:
                issue_score += 5
            elif item.priority == Priority.LOW:
                issue_score += 2

        issue_score = min(40, issue_score)  # Cap at 40
        score += issue_score

        # 2. Days since maintenance (20%)
        if days_since_maintenance is not None:
            if days_since_maintenance > 90:
                score += 20
                factors.append(f"Overdue PM: {days_since_maintenance} days")
            elif days_since_maintenance > 60:
                score += 12
                factors.append(f"PM due soon: {days_since_maintenance} days")
            elif days_since_maintenance > 30:
                score += 5

        # 3. Trend analysis - check for degrading trends (20%)
        # Look for items with negative trends
        degrading_items = [
            i
            for i in truck_items
            if i.trend
            and ("+°F" in i.trend or "↑" in i.trend or "aumentando" in i.trend.lower())
        ]
        if degrading_items:
            trend_score = min(20, len(degrading_items) * 7)
            score += trend_score
            if len(degrading_items) > 0:
                factors.append(f"Degrading trends: {len(degrading_items)}")

        # 4. Sensor alerts (20%)
        if sensor_alerts:
            alert_count = sum(1 for v in sensor_alerts.values() if v)
            alert_score = min(20, alert_count * 5)
            score += alert_score
            if alert_count > 0:
                factors.append(f"Active sensor alerts: {alert_count}")

        # Clamp to 0-100
        score = max(0, min(100, score))

        # Determine risk level
        if score >= 75:
            risk_level = "critical"
        elif score >= 50:
            risk_level = "high"
        elif score >= 30:
            risk_level = "medium"
        elif score >= 10:
            risk_level = "low"
        else:
            risk_level = "healthy"

        # Find minimum days to failure from action items
        days_to_fail = None
        for item in truck_items:
            if item.days_to_critical is not None:
                if days_to_fail is None or item.days_to_critical < days_to_fail:
                    days_to_fail = item.days_to_critical

        return TruckRiskScore(
            truck_id=truck_id,
            risk_score=score,
            risk_level=risk_level,
            contributing_factors=factors[:5],  # Top 5 factors
            days_since_last_maintenance=days_since_maintenance,
            active_issues_count=len(truck_items),
            predicted_failure_days=days_to_fail,
        )

    def get_top_risk_trucks(
        self, action_items: List[ActionItem], top_n: int = 10, persist: bool = True
    ) -> List[TruckRiskScore]:
        """
        Get the top N at-risk trucks based on risk scores.

        v1.5.0 FASE 4.4: Allows fleet manager to focus on most critical trucks.
        v1.5.0 FASE 5.6: Now persists all risk scores to MySQL for ML training.

        Args:
            action_items: All action items for the fleet
            top_n: Number of top risk trucks to return (default 10)
            persist: Whether to persist risk scores to MySQL (default True)

        Returns:
            List of TruckRiskScore sorted by risk score descending
        """
        # Get unique truck IDs
        truck_ids = set(i.truck_id for i in action_items if i.truck_id != "FLEET")

        # Calculate risk for each truck
        risk_scores = []
        for truck_id in truck_ids:
            risk = self.calculate_truck_risk_score(truck_id, action_items)
            risk_scores.append(risk)

        # v1.5.0 FASE 5.6: Persist all risk scores for ML
        if persist and risk_scores:
            persisted = self.batch_persist_risk_scores(risk_scores)
            if persisted > 0:
                logger.debug(f"💾 Persisted {persisted} risk scores to MySQL")

        # Sort by risk score descending
        risk_scores.sort(key=lambda x: x.risk_score, reverse=True)

        return risk_scores[:top_n]

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 4.7: OFFLINE TRUCK DETECTION
    # ═══════════════════════════════════════════════════════════════════════════════

    def detect_offline_trucks(
        self, truck_last_seen: Dict[str, datetime], all_truck_ids: List[str]
    ) -> List[ActionItem]:
        """
        Detect trucks that haven't reported data recently.

        v1.5.0 FASE 4.7: Creates alerts for trucks that appear to be offline.

        Args:
            truck_last_seen: Dict of truck_id → last_seen_timestamp
            all_truck_ids: List of all known truck IDs

        Returns:
            List of ActionItems for offline/stale trucks
        """
        now = datetime.now(timezone.utc)
        warning_hours = self.OFFLINE_THRESHOLDS["hours_no_data_warning"]
        critical_hours = self.OFFLINE_THRESHOLDS["hours_no_data_critical"]

        offline_actions = []

        for truck_id in all_truck_ids:
            last_seen = truck_last_seen.get(truck_id)

            if last_seen is None:
                # Never seen - might be new or truly offline
                hours_offline = critical_hours + 1  # Assume critical
            else:
                # Ensure timezone-aware comparison
                if last_seen.tzinfo is None:
                    last_seen = last_seen.replace(tzinfo=timezone.utc)
                hours_offline = (now - last_seen).total_seconds() / 3600

            if hours_offline >= critical_hours:
                priority = Priority.HIGH
                priority_score = 75.0
                title = f"🚨 Camión sin datos por {hours_offline:.0f}h"
                description = (
                    f"El camión {truck_id} no ha reportado datos en las últimas "
                    f"{hours_offline:.0f} horas. Puede estar apagado, sin conexión, "
                    "o con problemas de telemetría."
                )
            elif hours_offline >= warning_hours:
                priority = Priority.MEDIUM
                priority_score = 50.0
                title = f"⚠️ Datos antiguos ({hours_offline:.0f}h sin actualizar)"
                description = (
                    f"El camión {truck_id} no ha actualizado datos en "
                    f"{hours_offline:.0f} horas. Verificar estado de conexión."
                )
            else:
                continue  # Truck is online

            offline_actions.append(
                ActionItem(
                    id=self._generate_action_id(),
                    truck_id=truck_id,
                    priority=priority,
                    priority_score=priority_score,
                    category=IssueCategory.SENSOR,
                    component="Telemetría",
                    title=title,
                    description=description,
                    days_to_critical=None,
                    cost_if_ignored=None,
                    current_value=f"{hours_offline:.0f} horas sin datos",
                    trend=None,
                    threshold=f"Crítico: >{critical_hours}h",
                    confidence="HIGH",
                    action_type=ActionType.INSPECT,
                    action_steps=[
                        "📡 Verificar conexión del dispositivo telemático",
                        "🔋 Revisar estado de batería del camión",
                        "📞 Contactar al conductor para confirmar ubicación",
                    ],
                    icon="📡",
                    sources=["Offline Detection"],
                )
            )

        return offline_actions

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.1: AUTOMATIC FAILURE CORRELATION
    # ═══════════════════════════════════════════════════════════════════════════════

    def detect_failure_correlations(
        self,
        action_items: List[ActionItem],
        sensor_data: Optional[Dict[str, Dict[str, float]]] = None,
        persist: bool = True,
    ) -> List[FailureCorrelation]:
        """
        Detect correlated failures that indicate systemic issues.

        v1.5.0 FASE 5.1: Uses predefined correlation patterns (e.g., coolant↑ + oil_temp↑)
        to identify underlying causes.

        v1.5.0 FASE 5.6: Now persists detected correlations to MySQL for ML.

        Args:
            action_items: Current action items
            sensor_data: Optional dict of truck_id → {sensor_name: value}
            persist: Whether to persist to MySQL (default True)

        Returns:
            List of FailureCorrelation objects
        """
        correlations = []

        # Group action items by truck
        truck_issues: Dict[str, List[str]] = {}
        for item in action_items:
            if item.truck_id not in truck_issues:
                truck_issues[item.truck_id] = []
            # Normalize component for matching
            norm_comp = self._normalize_component(item.component)
            truck_issues[item.truck_id].append(norm_comp)

        # Check each correlation pattern
        for pattern_id, pattern in self.FAILURE_CORRELATIONS.items():
            primary = pattern["primary"]
            correlated = pattern["correlated"]
            min_correlation = pattern["min_correlation"]

            # Find trucks with primary issue
            affected_trucks = []
            for truck_id, issues in truck_issues.items():
                # Check if truck has primary sensor issue
                primary_match = any(primary in issue for issue in issues)
                if not primary_match:
                    continue

                # Check for correlated issues
                correlated_count = sum(
                    1
                    for sensor in correlated
                    if any(sensor in issue for issue in issues)
                )

                # Calculate correlation strength
                if correlated_count > 0:
                    strength = correlated_count / len(correlated)
                    if strength >= min_correlation:
                        affected_trucks.append(truck_id)

            # If we have affected trucks, create a correlation finding
            if affected_trucks:
                correlation = FailureCorrelation(
                    correlation_id=f"CORR-{pattern_id.upper()}-{uuid.uuid4().hex[:6]}",
                    primary_sensor=primary,
                    correlated_sensors=correlated,
                    correlation_strength=(
                        len(affected_trucks) / len(truck_issues) if truck_issues else 0
                    ),
                    probable_cause=pattern["cause"],
                    recommended_action=pattern["action"],
                    affected_trucks=affected_trucks,
                )
                correlations.append(correlation)

                # v1.5.0 FASE 5.6: Persist to MySQL for ML
                if persist:
                    for truck_id in affected_trucks:
                        # Get sensor values if available
                        sensor_values = {}
                        if sensor_data and truck_id in sensor_data:
                            for sensor in [primary] + correlated:
                                if sensor in sensor_data[truck_id]:
                                    sensor_values[sensor] = sensor_data[truck_id][
                                        sensor
                                    ]

                        self.persist_correlation_event(
                            truck_id=truck_id,
                            pattern_name=pattern_id,
                            pattern_description=pattern.get(
                                "cause", "Unknown correlation"
                            ),
                            confidence=correlation.correlation_strength,
                            sensors_involved=[primary] + correlated,
                            sensor_values=sensor_values,
                            predicted_component=pattern.get("component"),
                            predicted_failure_days=pattern.get("days_to_failure"),
                            recommended_action=pattern.get("action"),
                        )

        return correlations

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.2: J1939 SPN NORMALIZATION
    # ═══════════════════════════════════════════════════════════════════════════════

    def normalize_spn_to_component(self, spn: int) -> Optional[str]:
        """
        Convert J1939 SPN (Standard Parameter Number) to component name.

        v1.5.0 FASE 5.2: Provides standard mapping for DTCs and diagnostic data.

        Args:
            spn: J1939 SPN number

        Returns:
            Component name or None if unknown SPN
        """
        if spn in self.J1939_SPN_MAP:
            return self.J1939_SPN_MAP[spn]["component"]
        return None

    def get_spn_info(self, spn: int) -> Optional[Dict[str, Any]]:
        """
        Get full information for a J1939 SPN.

        Args:
            spn: J1939 SPN number

        Returns:
            Dict with component, name, unit or None
        """
        return self.J1939_SPN_MAP.get(spn)

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.3: DEF PREDICTIVE ANALYSIS
    # ═══════════════════════════════════════════════════════════════════════════════

    def predict_def_depletion(
        self,
        truck_id: str,
        current_level_pct: float,
        daily_miles: Optional[float] = None,
        avg_mpg: Optional[float] = None,
        persist: bool = True,
    ) -> DEFPrediction:
        """
        Predict when DEF will run out based on consumption patterns.

        v1.5.0 FASE 5.3: Real DEF prediction using liters/consumption = days.
        v1.5.0 FASE 5.6: Now persists DEF readings to MySQL for ML.

        DEF consumption is typically 2-3% of diesel consumption for Class 8 trucks.

        Args:
            truck_id: Truck identifier
            current_level_pct: Current DEF level (0-100%)
            daily_miles: Average daily miles (optional)
            avg_mpg: Average MPG (optional)
            persist: Whether to persist to MySQL (default True)

        Returns:
            DEFPrediction with days until empty and derate
        """
        config = self.DEF_CONSUMPTION_CONFIG
        tank_capacity = config["tank_capacity_liters"]
        def_pct_diesel = config["avg_consumption_pct_diesel"] / 100

        # Calculate current DEF liters
        current_liters = (current_level_pct / 100) * tank_capacity

        # Calculate daily DEF consumption
        if daily_miles and avg_mpg and avg_mpg > 0:
            # Calculate based on actual driving data
            daily_diesel_gallons = daily_miles / avg_mpg
            daily_diesel_liters = daily_diesel_gallons * 3.785  # Convert to liters
            daily_def_liters = daily_diesel_liters * def_pct_diesel
        else:
            # Use default consumption rate
            daily_def_liters = config["avg_daily_diesel_liters"] * def_pct_diesel

        # Avoid division by zero
        if daily_def_liters <= 0:
            daily_def_liters = 0.1  # Minimum consumption assumption

        # Calculate days until empty and derate
        days_until_empty = current_liters / daily_def_liters

        # Derate typically happens at 5% DEF
        derate_level_liters = (config["derate_threshold_pct"] / 100) * tank_capacity
        liters_until_derate = current_liters - derate_level_liters
        days_until_derate = max(0, liters_until_derate / daily_def_liters)

        # v1.5.0 FASE 5.6: Persist DEF reading for ML
        if persist:
            # Convert to gallons for consistency
            consumption_rate = def_pct_diesel * 100  # % of diesel consumption
            self.persist_def_reading(
                truck_id=truck_id,
                def_level=current_level_pct,
                fuel_used=daily_miles / avg_mpg if (daily_miles and avg_mpg) else None,
                estimated_def_used=daily_def_liters / 3.785,  # Convert to gallons
                consumption_rate=consumption_rate,
                is_refill=False,
            )

        return DEFPrediction(
            truck_id=truck_id,
            current_level_pct=current_level_pct,
            estimated_liters_remaining=current_liters,
            avg_consumption_liters_per_day=daily_def_liters,
            days_until_empty=days_until_empty,
            days_until_derate=days_until_derate,
        )

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.4: GET ACTION STEPS FROM DECISION TABLE
    # ═══════════════════════════════════════════════════════════════════════════════

    def _get_action_steps_from_table(
        self, component: str, priority: Priority
    ) -> List[str]:
        """
        Get action steps from external decision table.

        v1.5.0 FASE 5.4: Uses ACTION_DECISION_TABLE (loaded from YAML or defaults)
        for consistent, admin-customizable action recommendations.

        Args:
            component: Normalized component name
            priority: Priority level

        Returns:
            List of action step strings
        """
        # Normalize component to decision table key
        norm_component = self._normalize_component(component)

        # Map normalized names to decision table keys
        table_key_map = {
            "oil_system": "oil_system",
            "cooling_system": "cooling_system",
            "def_system": "def_system",
            "transmission": "transmission",
            "electrical": "electrical",
            "turbo_system": "turbo_system",
        }

        table_key = table_key_map.get(norm_component)
        if not table_key or table_key not in self.ACTION_DECISION_TABLE:
            return []  # Fall back to default generation

        priority_key = priority.name if priority != Priority.NONE else "LOW"
        return self.ACTION_DECISION_TABLE[table_key].get(priority_key, [])

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 5.5: TIME-HORIZON AWARE SCORING
    # ═══════════════════════════════════════════════════════════════════════════════

    def _get_time_horizon(self, days_to_critical: Optional[float]) -> str:
        """
        Determine time horizon category for scoring.

        Args:
            days_to_critical: Days until critical failure

        Returns:
            "immediate", "short_term", or "medium_term"
        """
        if days_to_critical is None:
            return "medium_term"
        elif days_to_critical <= 1:
            return "immediate"
        elif days_to_critical <= 7:
            return "short_term"
        else:
            return "medium_term"

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.5.0 FASE 4.6: SEPARATION OF DETECTION AND DECISION
    # Clean architecture: Detect issues first, then decide actions separately
    # ═══════════════════════════════════════════════════════════════════════════════

    def detect_issue(
        self,
        truck_id: str,
        sensor_name: str,
        current_value: float,
        baseline_value: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        DETECTION PHASE: Detect if there's an issue based on sensor data.

        v1.5.0 FASE 4.6: This method only detects and characterizes the issue.
        It does NOT decide what action to take.

        Args:
            truck_id: Truck identifier
            sensor_name: Name of the sensor
            current_value: Current sensor reading
            baseline_value: Optional baseline for comparison

        Returns:
            Detection result dict with:
            - is_issue: bool
            - severity: "none", "low", "medium", "high", "critical"
            - deviation_pct: Percentage deviation from normal
            - trend: Trend direction from EWMA/CUSUM
            - persistence: Whether issue is persistent (not a glitch)
            - raw_data: Original detection data
        """
        result = {
            "is_issue": False,
            "severity": "none",
            "deviation_pct": 0.0,
            "trend": "stable",
            "persistence": False,
            "confidence": "LOW",
            "raw_data": {
                "truck_id": truck_id,
                "sensor_name": sensor_name,
                "current_value": current_value,
                "baseline_value": baseline_value,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        }

        # 1. Validate sensor value
        validated = self._validate_sensor_value(current_value, sensor_name)
        if validated is None:
            result["raw_data"]["validation_failed"] = True
            return result

        # 2. Record reading for temporal persistence
        self._record_sensor_reading(truck_id, sensor_name, validated)

        # 3. Get sensor range for comparison
        sensor_range = self.SENSOR_VALID_RANGES.get(sensor_name, {})
        normal_max = sensor_range.get("max", 100)
        normal_min = sensor_range.get("min", 0)
        normal_mid = (normal_max + normal_min) / 2

        # Use baseline if provided, otherwise use midpoint
        baseline = baseline_value if baseline_value is not None else normal_mid

        # 4. Calculate deviation
        if baseline != 0:
            deviation_pct = ((validated - baseline) / baseline) * 100
        else:
            deviation_pct = 0
        result["deviation_pct"] = round(deviation_pct, 1)

        # 5. Run EWMA/CUSUM analysis
        trend_analysis = self._detect_trend_with_ewma_cusum(
            truck_id, sensor_name, [validated], baseline
        )
        result["trend"] = trend_analysis["trend"]
        result["raw_data"]["ewma"] = trend_analysis.get("ewma")
        result["raw_data"]["cusum_alert"] = trend_analysis.get("cusum_alert")

        # 6. Check persistence (multiple readings confirming the issue)
        # Determine if this is a high or low threshold issue
        is_high_issue = validated > (normal_mid + (normal_max - normal_mid) * 0.7)
        is_low_issue = validated < (normal_mid - (normal_mid - normal_min) * 0.7)

        if is_high_issue:
            threshold = normal_mid + (normal_max - normal_mid) * 0.7
            persistent, count = self._has_persistent_critical_reading(
                truck_id, sensor_name, threshold, above=True
            )
        elif is_low_issue:
            threshold = normal_mid - (normal_mid - normal_min) * 0.7
            persistent, count = self._has_persistent_critical_reading(
                truck_id, sensor_name, threshold, above=False
            )
        else:
            persistent = False
            count = 0

        result["persistence"] = persistent
        result["raw_data"]["persistence_count"] = count

        # 7. Determine severity based on deviation
        abs_deviation = abs(deviation_pct)
        if abs_deviation > 30 or trend_analysis.get("cusum_alert"):
            severity = "critical"
            is_issue = True
        elif abs_deviation > 20:
            severity = "high"
            is_issue = True
        elif abs_deviation > 10:
            severity = "medium"
            is_issue = True
        elif abs_deviation > 5:
            severity = "low"
            is_issue = True
        else:
            severity = "none"
            is_issue = False

        result["is_issue"] = is_issue
        result["severity"] = severity

        # 8. Set confidence based on data quality
        if persistent and count >= 3:
            result["confidence"] = "HIGH"
        elif persistent or count >= 2:
            result["confidence"] = "MEDIUM"
        else:
            result["confidence"] = "LOW"

        return result

    def decide_action(
        self,
        detection_result: Dict[str, Any],
        component: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        DECISION PHASE: Decide what action to take based on detection result.

        v1.5.0 FASE 4.6: This method takes detection output and decides:
        - Priority level
        - Action type
        - Recommended steps

        This separation allows:
        - Testing detection logic independently
        - Customizing decision rules without changing detection
        - Overriding decisions manually if needed

        Args:
            detection_result: Output from detect_issue()
            component: Optional component name for action step lookup

        Returns:
            Decision result dict with:
            - priority: Priority enum
            - priority_score: 0-100
            - action_type: ActionType enum
            - action_steps: List of steps
            - reasoning: Why this decision was made
        """
        if not detection_result.get("is_issue"):
            return {
                "priority": Priority.NONE,
                "priority_score": 0.0,
                "action_type": ActionType.NO_ACTION,
                "action_steps": [],
                "reasoning": "No issue detected",
            }

        severity = detection_result.get("severity", "none")
        persistence = detection_result.get("persistence", False)
        confidence = detection_result.get("confidence", "LOW")
        deviation = detection_result.get("deviation_pct", 0)
        trend = detection_result.get("trend", "stable")

        # Map severity to priority
        severity_to_priority = {
            "critical": Priority.CRITICAL,
            "high": Priority.HIGH,
            "medium": Priority.MEDIUM,
            "low": Priority.LOW,
            "none": Priority.NONE,
        }
        base_priority = severity_to_priority.get(severity, Priority.NONE)

        # Adjust priority based on persistence and trend
        reasoning_parts = [f"Severity: {severity}"]

        # Upgrade priority if issue is persistent
        if persistence and base_priority not in [Priority.CRITICAL, Priority.NONE]:
            priorities_list = [
                Priority.CRITICAL,
                Priority.HIGH,
                Priority.MEDIUM,
                Priority.LOW,
            ]
            current_idx = priorities_list.index(base_priority)
            if current_idx > 0:
                base_priority = priorities_list[current_idx - 1]
                reasoning_parts.append("Upgraded due to persistence")

        # Downgrade if not persistent and confidence is low
        if (
            not persistence
            and confidence == "LOW"
            and base_priority == Priority.CRITICAL
        ):
            base_priority = Priority.HIGH
            reasoning_parts.append("Downgraded: waiting for confirmation")

        # Calculate priority score
        severity_scores = {
            "critical": 90,
            "high": 70,
            "medium": 50,
            "low": 30,
            "none": 0,
        }
        base_score = severity_scores.get(severity, 0)

        # Adjust score based on factors
        score_adjustments = 0
        if persistence:
            score_adjustments += 5
        if trend in ["increasing", "decreasing"] and abs(deviation) > 10:
            score_adjustments += 5
        if confidence == "HIGH":
            score_adjustments += 3

        priority_score = min(100, base_score + score_adjustments)

        # Determine action type
        action_type = self._determine_action_type(base_priority, None)

        # FASE 4.1: Require persistence before STOP_IMMEDIATELY
        if action_type == ActionType.STOP_IMMEDIATELY and not persistence:
            action_type = ActionType.SCHEDULE_THIS_WEEK
            reasoning_parts.append("STOP deferred: awaiting confirmation readings")

        # Get action steps from decision table
        action_steps = []
        if component:
            action_steps = self._get_action_steps_from_table(component, base_priority)

        # Fall back to generated steps if table doesn't have this component
        if not action_steps:
            sensor_name = detection_result.get("raw_data", {}).get("sensor_name", "")
            action_steps = self._generate_action_steps(
                sensor_name, action_type, f"Deviation: {deviation:.1f}%"
            )

        return {
            "priority": base_priority,
            "priority_score": priority_score,
            "action_type": action_type,
            "action_steps": action_steps,
            "reasoning": "; ".join(reasoning_parts),
        }

    def detect_and_decide(
        self,
        truck_id: str,
        sensor_name: str,
        current_value: float,
        baseline_value: Optional[float] = None,
        component: Optional[str] = None,
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Convenience method that runs both detection and decision phases.

        v1.5.0 FASE 4.6: Combines detect_issue() and decide_action() for
        common use cases while keeping the separation for advanced usage.

        Returns:
            Tuple of (detection_result, decision_result)
        """
        detection = self.detect_issue(
            truck_id, sensor_name, current_value, baseline_value
        )
        decision = self.decide_action(detection, component)
        return detection, decision

    def _normalize_component(self, component: str) -> str:
        """
        Normalize component name to canonical form for deduplication.

        v1.3.0: Uses comprehensive mapping instead of simple keyword matching.
        Caches results for performance.

        Args:
            component: Raw component name from any source

        Returns:
            Canonical component name (e.g., "oil_system", "cooling_system")

        Examples:
            "Sistema de Lubricación" → "oil_system"
            "oil_press" → "oil_system"
            "cool_temp" → "cooling_system"
            "Transmisión" → "transmission"
        """
        # Check cache first
        if component in self._component_cache:
            return self._component_cache[component]

        component_lower = component.lower().strip()

        # Remove common prefixes/suffixes for better matching
        component_lower = component_lower.replace("sistema de ", "")
        component_lower = component_lower.replace("sistema ", "")

        # Search through normalization mapping
        for canonical, keywords in self.COMPONENT_NORMALIZATION.items():
            for keyword in keywords:
                if keyword in component_lower:
                    self._component_cache[component] = canonical
                    return canonical

        # If no match, clean and return as-is
        result = component_lower.replace(" ", "_")
        self._component_cache[component] = result
        return result

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.3.0: SENSOR DATA VALIDATION
    # ═══════════════════════════════════════════════════════════════════════════════

    def _validate_sensor_value(self, value: Any, sensor_name: str) -> Optional[float]:
        """
        Validate and sanitize sensor value.

        v1.3.0: Filters NULL, NaN, Inf, and out-of-range values.

        Args:
            value: Raw sensor value (may be None, NaN, or invalid)
            sensor_name: Name of sensor for range lookup

        Returns:
            Validated float value, or None if invalid

        Examples:
            _validate_sensor_value(45.5, "oil_press") → 45.5
            _validate_sensor_value(None, "oil_press") → None
            _validate_sensor_value(999, "oil_press") → None (out of range)
            _validate_sensor_value(float('nan'), "voltage") → None
        """
        if value is None:
            return None

        try:
            val = float(value)

            # Check for NaN and Inf
            if math.isnan(val) or math.isinf(val):
                logger.debug(f"Invalid sensor value for {sensor_name}: {val}")
                return None

            # Check range if defined
            if sensor_name in self.SENSOR_VALID_RANGES:
                range_def = self.SENSOR_VALID_RANGES[sensor_name]
                if val < range_def["min"] or val > range_def["max"]:
                    logger.debug(
                        f"Sensor {sensor_name} value {val} out of range "
                        f"[{range_def['min']}, {range_def['max']}]"
                    )
                    return None

            return val

        except (ValueError, TypeError) as e:
            logger.debug(f"Cannot convert sensor value for {sensor_name}: {e}")
            return None

    def _validate_sensor_dict(
        self, sensors: Dict[str, Any]
    ) -> Dict[str, Optional[float]]:
        """
        Validate all sensor values in a dictionary.

        v1.3.0: Batch validation for efficiency.

        Args:
            sensors: Dictionary of sensor_name → raw_value

        Returns:
            Dictionary with validated values (None for invalid)
        """
        return {
            name: self._validate_sensor_value(value, name)
            for name, value in sensors.items()
        }

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.3.0: SOURCE HIERARCHY UTILITIES
    # ═══════════════════════════════════════════════════════════════════════════════

    def _get_source_weight(self, source: str) -> int:
        """
        Get hierarchy weight for a data source.

        v1.3.0: Used to determine which source to trust in conflicts.

        Args:
            source: Source name (e.g., "Real-Time Predictive (trend)")

        Returns:
            Weight (0-100), higher = more trusted
        """
        for source_key, weight in self.SOURCE_HIERARCHY.items():
            if source_key.lower() in source.lower():
                return weight
        return 25  # Default low weight for unknown sources

    def _get_best_source(self, sources: List[str]) -> str:
        """
        Get the most trusted source from a list.

        v1.3.0: Returns source with highest hierarchy weight.
        """
        if not sources:
            return "Unknown"
        return max(sources, key=self._get_source_weight)

    def _generate_action_id(self) -> str:
        """
        Generate unique action ID using UUID for thread safety.

        v1.1.0: Changed from counter-based to UUID-based to prevent
        race conditions in concurrent environments.
        """
        return f"ACT-{datetime.now(timezone.utc).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"

    def _get_component_cost(self, component: str) -> Dict[str, int]:
        """
        Get cost estimate for a component from the cost database.

        v1.1.0: New method replacing string parsing.
        """
        return self.COMPONENT_COSTS.get(
            component, {"min": 500, "max": 2000, "avg": 1250}
        )

    def _format_cost_string(self, component: str) -> str:
        """
        Format cost as user-friendly string.

        v1.1.0: Uses cost database instead of hardcoded strings.
        """
        cost = self._get_component_cost(component)
        return f"${cost['min']:,} - ${cost['max']:,}"

    def _load_engine_safely(
        self, engine_name: str, factory_func: Callable[[], Any], required: bool = False
    ) -> Optional[Any]:
        """
        Safely load an engine with proper error handling.

        v1.3.0: Centralized engine loading with consistent error handling.
        Reduces code duplication and improves reliability.

        Args:
            engine_name: Human-readable engine name for logging
            factory_func: Callable that creates/returns the engine
            required: If True, raise exception on failure. If False, return None.

        Returns:
            Engine instance or None if failed and not required

        Raises:
            RuntimeError: If required engine fails to load
        """
        try:
            engine = factory_func()
            if engine is not None:
                logger.debug(f"✅ {engine_name} loaded successfully")
            return engine
        except ImportError as e:
            msg = f"❌ {engine_name} import error: {e}"
            logger.warning(msg)
            if required:
                raise RuntimeError(msg) from e
            return None
        except Exception as e:
            msg = f"❌ {engine_name} failed to load: {e}"
            logger.error(msg, exc_info=True)
            if required:
                raise RuntimeError(msg) from e
            return None

    # ═══════════════════════════════════════════════════════════════════════════════
    # v1.3.0: EXPONENTIAL DECAY FOR URGENCY SCORING
    # ═══════════════════════════════════════════════════════════════════════════════

    def _calculate_urgency_from_days(self, days: float) -> float:
        """
        Calculate urgency score using exponential decay.

        v1.3.0: Replaces piecewise linear function with smooth exponential curve.
        This provides more natural prioritization without artificial jumps.

        Formula: 100 * e^(-k * days) where k controls decay rate
        Tuned so that:
        - 0 days = 100 (immediate failure)
        - 1 day = ~93
        - 3 days = ~85
        - 7 days = ~70
        - 14 days = ~55
        - 30 days = ~30
        - 60 days = ~10

        Args:
            days: Days until critical failure

        Returns:
            Urgency score 0-100 (higher = more urgent)
        """
        if days <= 0:
            return 100.0

        # k = 0.04 gives a good decay curve for fleet maintenance
        # Tuned for typical maintenance windows (1 week, 1 month, etc.)
        k = 0.04
        score = 100 * math.exp(-k * days)

        return max(5.0, min(100.0, score))  # Floor at 5 to show it exists

    def _normalize_score_to_100(self, value: float, max_value: float = 100.0) -> float:
        """
        Normalize any score to 0-100 scale.

        v1.3.0: Ensures consistent scoring across all sources.

        Args:
            value: Raw score value
            max_value: Expected maximum of raw scale (e.g., 1.0 for 0-1 scale)

        Returns:
            Score normalized to 0-100
        """
        if max_value <= 0:
            return 50.0  # Default middle score

        normalized = (value / max_value) * 100
        return max(0.0, min(100.0, normalized))

    def _calculate_priority_score(
        self,
        days_to_critical: Optional[float],
        anomaly_score: Optional[float] = None,
        cost_estimate: Optional[str] = None,
        component: Optional[str] = None,
    ) -> Tuple[Priority, float]:
        """
        Calculate combined priority score from multiple signals.

        v1.3.0 Improvements:
        - Uses exponential decay for days_to_critical (smooth curve)
        - Normalizes all inputs to 0-100 scale
        - Weighted combination with configurable weights
        - Better handling of missing signals

        Score Components (v1.3.0):
        - Days urgency (45%): Exponential decay from days_to_critical
        - Anomaly score (20%): Normalized ML anomaly detection score
        - Component criticality (25%): Based on COMPONENT_CRITICALITY weights
        - Cost factor (10%): Based on potential repair cost

        Thresholds:
        - 85+: CRITICAL
        - 65-84: HIGH
        - 40-64: MEDIUM
        - 20-39: LOW
        - <20: NONE

        Returns (Priority enum, numeric score 0-100)
        """
        # Weight configuration (v1.3.0)
        WEIGHT_DAYS = 0.45
        WEIGHT_ANOMALY = 0.20
        WEIGHT_CRITICALITY = 0.25
        WEIGHT_COST = 0.10

        components_used = []
        weighted_score = 0.0
        total_weight = 0.0

        # 1. Days to critical - most important signal
        if days_to_critical is not None:
            days_score = self._calculate_urgency_from_days(days_to_critical)
            weighted_score += days_score * WEIGHT_DAYS
            total_weight += WEIGHT_DAYS
            components_used.append(f"days={days_score:.1f}")

        # 2. Anomaly score - normalize to 0-100 if needed
        if anomaly_score is not None:
            # Handle both 0-1 and 0-100 scales
            if anomaly_score <= 1.0:
                normalized_anomaly = anomaly_score * 100
            else:
                normalized_anomaly = min(100, anomaly_score)
            weighted_score += normalized_anomaly * WEIGHT_ANOMALY
            total_weight += WEIGHT_ANOMALY
            components_used.append(f"anomaly={normalized_anomaly:.1f}")

        # 3. Component criticality
        if component:
            criticality = self.COMPONENT_CRITICALITY.get(component, 1.0)
            # Normalize criticality (1.0-3.0) to 0-100
            # 1.0 = 33, 2.0 = 66, 3.0 = 100
            criticality_score = (criticality / 3.0) * 100
            weighted_score += criticality_score * WEIGHT_CRITICALITY
            total_weight += WEIGHT_CRITICALITY
            components_used.append(f"crit={criticality_score:.1f}")

        # 4. Cost factor
        if component:
            cost_data = self._get_component_cost(component)
            avg_cost = cost_data.get("avg", 0)
            # Normalize cost to 0-100 (assuming max ~$15,000)
            cost_score = min(100, (avg_cost / 15000) * 100)
            weighted_score += cost_score * WEIGHT_COST
            total_weight += WEIGHT_COST
            components_used.append(f"cost={cost_score:.1f}")
        elif cost_estimate:
            # Fallback to string parsing
            if "15,000" in cost_estimate or "10,000" in cost_estimate:
                weighted_score += 80 * WEIGHT_COST
                total_weight += WEIGHT_COST
            elif "5,000" in cost_estimate:
                weighted_score += 50 * WEIGHT_COST
                total_weight += WEIGHT_COST

        # Calculate final score
        if total_weight > 0:
            score = weighted_score / total_weight
        else:
            score = 50.0  # Default middle score

        # Clamp to 0-100
        score = max(0, min(100, score))

        # Log scoring components for debugging
        logger.debug(
            f"Priority score: {score:.1f} (weights: {', '.join(components_used)})"
        )

        # Determine priority level
        if score >= 85:
            priority = Priority.CRITICAL
        elif score >= 65:
            priority = Priority.HIGH
        elif score >= 40:
            priority = Priority.MEDIUM
        elif score >= 20:
            priority = Priority.LOW
        else:
            priority = Priority.NONE

        return priority, round(score, 1)

    def _determine_action_type(
        self, priority: Priority, days_to_critical: Optional[float]
    ) -> ActionType:
        """Determine what action should be taken based on priority"""
        if priority == Priority.CRITICAL:
            if days_to_critical is not None and days_to_critical <= 1:
                return ActionType.STOP_IMMEDIATELY
            return ActionType.SCHEDULE_THIS_WEEK
        elif priority == Priority.HIGH:
            return ActionType.SCHEDULE_THIS_WEEK
        elif priority == Priority.MEDIUM:
            return ActionType.SCHEDULE_THIS_MONTH
        elif priority == Priority.LOW:
            return ActionType.MONITOR
        else:
            return ActionType.NO_ACTION

    def _generate_action_steps(
        self,
        component: str,
        action_type: ActionType,
        recommendation: str,
    ) -> List[str]:
        """Generate step-by-step instructions"""
        steps = []

        if action_type == ActionType.STOP_IMMEDIATELY:
            steps.append("⚠️ Detener el camión de forma segura lo antes posible")
            steps.append("📞 Contactar al taller o servicio de emergencia")
        elif action_type == ActionType.SCHEDULE_THIS_WEEK:
            steps.append("📅 Agendar cita en taller para esta semana")
        elif action_type == ActionType.SCHEDULE_THIS_MONTH:
            steps.append("📅 Incluir en próximo servicio programado")

        # Add component-specific steps
        if recommendation:
            steps.append(f"🔧 {recommendation}")

        if "aceite" in component.lower():
            steps.append("✅ Verificar nivel y calidad de aceite")
            steps.append("✅ Revisar filtro de aceite")
        elif "transmisión" in component.lower():
            steps.append("✅ Verificar nivel de fluido de transmisión")
            steps.append("✅ Inspeccionar cooler de transmisión")
        elif "enfriamiento" in component.lower():
            steps.append("✅ Verificar nivel de coolant")
            steps.append("✅ Inspeccionar radiador y mangueras")
        elif "def" in component.lower():
            steps.append("✅ Llenar tanque DEF")
            steps.append("✅ Verificar calidad del DEF")
        elif "eléctrico" in component.lower() or "batería" in component.lower():
            steps.append("✅ Probar batería con multímetro")
            steps.append("✅ Verificar conexiones y alternador")

        return steps

    def _calculate_fleet_health_score(
        self,
        urgency: UrgencySummary,
        total_trucks: int,
        action_items: Optional[List[ActionItem]] = None,
    ) -> FleetHealthScore:
        """
        Calculate overall fleet health score with distribution analysis.

        v1.3.0 Improvements:
        - Added distribution penalty for systemic issues
        - Considers percentage of fleet affected
        - Multi-truck critical penalty
        - More descriptive status messages with context

        Args:
            urgency: UrgencySummary with issue counts by priority
            total_trucks: Total fleet size
            action_items: Optional list of actions for distribution analysis

        Returns:
            FleetHealthScore with score, status, trend, and description
        """
        if total_trucks == 0:
            return FleetHealthScore(
                score=100,
                status="Sin datos",
                trend="stable",
                description="No hay camiones para analizar",
            )

        # Base score starts at 100
        score = 100.0

        # 1. Calculate weighted severity per truck (normalized by fleet size)
        severity_per_truck = (
            urgency.critical * 15  # Critical issues are severe
            + urgency.high * 8
            + urgency.medium * 3
            + urgency.low * 1
        ) / total_trucks

        # Deduct points based on severity per truck
        score -= severity_per_truck * 3

        # 2. v1.3.0: Distribution penalty - systemic issues are worse
        if action_items:
            # Build truck to issues map
            truck_issues: Dict[str, List[ActionItem]] = {}
            for item in action_items:
                if item.truck_id != "FLEET":
                    if item.truck_id not in truck_issues:
                        truck_issues[item.truck_id] = []
                    truck_issues[item.truck_id].append(item)

            trucks_with_issues = len(truck_issues)
            affected_percentage = (trucks_with_issues / total_trucks) * 100

            # Systemic issue penalty: if >20% of fleet affected
            if affected_percentage > 20:
                systemic_penalty = (
                    affected_percentage - 20
                ) * 0.4  # Up to -32 if 100% affected
                score -= systemic_penalty
                logger.info(
                    f"⚠️ Systemic issue detected: {affected_percentage:.0f}% of fleet affected. "
                    f"Penalty: -{systemic_penalty:.1f} points"
                )

            # 3. v1.3.0: Multiple critical trucks penalty
            critical_trucks = [
                truck_id
                for truck_id, items in truck_issues.items()
                if any(i.priority == Priority.CRITICAL for i in items)
            ]

            if len(critical_trucks) > 1:
                # Multiple trucks in critical state - serious fleet problem
                multi_critical_penalty = min(20, len(critical_trucks) * 4)  # Up to -20
                score -= multi_critical_penalty
                logger.info(
                    f"🚨 {len(critical_trucks)} trucks in critical state. "
                    f"Penalty: -{multi_critical_penalty} points"
                )

        # Clamp to 0-100
        score = max(0, min(100, score))
        score = int(round(score))

        # Determine status with more context
        if score >= 90:
            status = "Excelente"
            description = (
                "La flota está en excelentes condiciones. "
                "Mantener programa de mantenimiento preventivo."
            )
        elif score >= 75:
            status = "Bueno"
            description = (
                "La flota está en buenas condiciones con algunos puntos de atención. "
                f"{urgency.critical + urgency.high} items prioritarios pendientes."
            )
        elif score >= 60:
            status = "Atención"
            description = (
                f"Hay {urgency.total_issues} items que requieren atención. "
                "Revisar lista de acciones prioritarias."
            )
        elif score >= 40:
            status = "Alerta"
            critical_msg = f"{urgency.critical} críticos" if urgency.critical else ""
            high_msg = f"{urgency.high} altos" if urgency.high else ""
            issues_detail = ", ".join(filter(None, [critical_msg, high_msg]))
            description = (
                f"Múltiples problemas detectados ({issues_detail}). "
                "Se recomienda atención inmediata."
            )
        else:
            status = "Crítico"
            description = (
                f"Estado crítico de la flota con {urgency.critical} issues críticos. "
                "Acción inmediata requerida."
            )

        return FleetHealthScore(
            score=score,
            status=status,
            trend="stable",  # TODO: Compare with historical data
            description=description,
        )

    def _generate_insights(
        self,
        action_items: List[ActionItem],
        urgency: UrgencySummary,
    ) -> List[str]:
        """
        Generate AI-style insights for the fleet manager.

        v1.3.0 Improvements:
        - Added cost impact analysis
        - Added trend detection (multiple trucks same issue)
        - Improved pattern detection with percentage thresholds
        - Added severity escalation warnings

        Args:
            action_items: List of all action items
            urgency: UrgencySummary counts

        Returns:
            List of insight strings for display
        """
        insights = []

        # Critical truck alerts
        if urgency.critical > 0:
            trucks = set(
                item.truck_id
                for item in action_items
                if item.priority == Priority.CRITICAL
            )
            if len(trucks) == 1:
                insights.append(
                    f"🚨 {list(trucks)[0]} requiere atención inmediata - revisar antes de operar"
                )
            else:
                insights.append(
                    f"🚨 {len(trucks)} camiones requieren atención inmediata"
                )

        # v1.3.0: Cost impact analysis
        # NOTE: cost_if_ignored is a string like "$8,000 - $15,000", not a number
        # Skip cost analysis for now (needs parsing logic)
        # total_cost_if_ignored = sum(
        #     item.cost_if_ignored or 0
        #     for item in action_items
        #     if item.priority in [Priority.CRITICAL, Priority.HIGH]
        # )
        # if total_cost_if_ignored >= 10000:
        #     insights.append(
        #         f"💰 Costo potencial si no se atiende: ${total_cost_if_ignored:,.0f} USD"
        #     )

        # Component patterns - v1.1.0: Use % of fleet instead of fixed count
        components = [
            item.component
            for item in action_items
            if item.priority in [Priority.CRITICAL, Priority.HIGH]
        ]
        if components:
            common = Counter(components).most_common(2)
            # v1.1.0: Calculate threshold based on fleet size
            fleet_size = len(set(item.truck_id for item in action_items)) or 1
            pattern_threshold = max(
                self.PATTERN_THRESHOLDS["min_trucks_for_pattern"],
                int(fleet_size * self.PATTERN_THRESHOLDS["fleet_wide_issue_pct"]),
            )

            if common[0][1] >= pattern_threshold:
                pct = (common[0][1] / fleet_size) * 100 if fleet_size > 0 else 0
                insights.append(
                    f"📊 Patrón detectado: {common[0][1]} camiones ({pct:.0f}% de flota) con problemas en {common[0][0]}"
                )

        # v1.3.0: Trend detection - issues about to escalate
        near_critical = [
            item
            for item in action_items
            if item.priority == Priority.HIGH
            and item.days_to_critical is not None
            and item.days_to_critical <= 3
        ]
        if near_critical:
            trucks_escalating = set(item.truck_id for item in near_critical)
            insights.append(
                f"⏰ {len(trucks_escalating)} camión(es) con problemas que escalarán a crítico en ≤3 días"
            )

        # Transmission warnings (expensive!)
        trans_issues = [
            i
            for i in action_items
            if "transmisión" in i.component.lower()
            and i.priority in [Priority.CRITICAL, Priority.HIGH]
        ]
        if trans_issues:
            insights.append(
                f"⚠️ {len(trans_issues)} problema(s) de transmisión detectado(s) - reparación costosa si no se atiende"
            )

        # DEF warnings
        def_issues = [
            i
            for i in action_items
            if i.category == IssueCategory.DEF
            and i.priority in [Priority.CRITICAL, Priority.HIGH]
        ]
        if def_issues:
            insights.append(
                f"💎 {len(def_issues)} camión(es) con DEF bajo - derate inminente si no se llena"
            )

        # Positive insight if fleet is healthy
        if urgency.critical == 0 and urgency.high == 0:
            insights.append(
                "✅ No hay problemas críticos o de alta prioridad - la flota está operando bien"
            )

        return insights

    def _deduplicate_action_items(
        self, action_items: List[ActionItem]
    ) -> List[ActionItem]:
        """
        Remove duplicate action items for the same issue with data preservation.

        v1.3.0 Improvements:
        - Uses robust component normalization via COMPONENT_NORMALIZATION mapping
        - Preserves valuable data from all duplicates (descriptions, steps)
        - Uses source hierarchy to determine primary source
        - Merges days_to_critical using most urgent (minimum)
        - Merges action steps without duplicates

        Deduplication key: (truck_id, category, component_normalized)

        Args:
            action_items: List of ActionItems potentially with duplicates

        Returns:
            Deduplicated list with merged data from all sources
        """
        if not action_items:
            return []

        # Group items by deduplication key
        groups: Dict[Tuple[str, str, str], List[ActionItem]] = {}

        for item in action_items:
            # v1.3.0: Use robust normalization
            component_norm = self._normalize_component(item.component)
            key = (item.truck_id, item.category.value, component_norm)

            if key not in groups:
                groups[key] = []
            groups[key].append(item)

        # Process each group
        result = []

        for key, group in groups.items():
            if len(group) == 1:
                # No duplicates, use as-is
                result.append(group[0])
                continue

            # Multiple items for same issue - merge intelligently
            # Sort by priority score (highest first)
            group.sort(key=lambda x: x.priority_score, reverse=True)
            primary = group[0]

            # Collect data from all items
            all_sources: List[str] = []
            all_descriptions: List[str] = [primary.description]
            all_steps: List[str] = list(primary.action_steps)
            all_days: List[float] = []

            # Add primary's data
            for src in primary.sources:
                if src not in all_sources:
                    all_sources.append(src)
            if primary.days_to_critical is not None:
                all_days.append(primary.days_to_critical)

            # Merge data from other items
            for item in group[1:]:
                # Collect sources
                for src in item.sources:
                    if src not in all_sources:
                        all_sources.append(src)

                # Collect unique descriptions
                if item.description and item.description != primary.description:
                    if item.description not in all_descriptions:
                        all_descriptions.append(item.description)

                # Collect unique action steps
                for step in item.action_steps:
                    if step not in all_steps:
                        all_steps.append(step)

                # Collect days_to_critical
                if item.days_to_critical is not None:
                    all_days.append(item.days_to_critical)

            # Determine merged values
            # Use minimum days_to_critical (most urgent)
            merged_days = min(all_days) if all_days else None

            # Build merged description if multiple sources detected same issue
            if len(all_sources) > 1:
                source_str = ", ".join(all_sources[:3])  # Limit to 3 sources
                if len(all_sources) > 3:
                    source_str += f" +{len(all_sources)-3} más"
                merged_description = (
                    f"{all_descriptions[0]}\n\n"
                    f"📊 Detectado por múltiples sistemas: {source_str}"
                )
            else:
                merged_description = all_descriptions[0]

            # Get cost from primary or first non-None
            merged_cost = primary.cost_if_ignored
            if not merged_cost:
                for item in group[1:]:
                    if item.cost_if_ignored:
                        merged_cost = item.cost_if_ignored
                        break

            # Get best current_value, trend, threshold from higher-weight sources
            # v1.3.0: Use source hierarchy
            sorted_by_source = sorted(
                group,
                key=lambda x: max(
                    (self._get_source_weight(s) for s in x.sources), default=0
                ),
                reverse=True,
            )

            best_current = next(
                (i.current_value for i in sorted_by_source if i.current_value), None
            )
            best_trend = next((i.trend for i in sorted_by_source if i.trend), None)
            best_threshold = next(
                (i.threshold for i in sorted_by_source if i.threshold), None
            )

            # Create merged ActionItem
            merged_item = ActionItem(
                id=primary.id,
                truck_id=primary.truck_id,
                priority=primary.priority,
                priority_score=primary.priority_score,
                category=primary.category,
                component=primary.component,
                title=primary.title,
                description=merged_description[:600],  # Cap length
                days_to_critical=merged_days,
                cost_if_ignored=merged_cost,
                current_value=best_current,
                trend=best_trend,
                threshold=best_threshold,
                confidence=primary.confidence,
                action_type=primary.action_type,
                action_steps=all_steps[:10],  # Limit steps
                icon=primary.icon,
                sources=all_sources,
            )

            result.append(merged_item)

        # Log deduplication stats
        original_count = len(action_items)
        final_count = len(result)
        if original_count != final_count:
            logger.info(
                f"🔄 Deduplicated {original_count} → {final_count} action items "
                f"({original_count - final_count} duplicates merged)"
            )

        return result

    def _estimate_costs(self, action_items: List[ActionItem]) -> CostProjection:
        """Estimate potential costs if issues are ignored"""
        immediate_min = 0
        immediate_max = 0
        week_min = 0
        week_max = 0
        month_min = 0
        month_max = 0

        for item in action_items:
            if not item.cost_if_ignored:
                continue

            # Parse cost string like "$8,000 - $15,000"
            try:
                cost_str = item.cost_if_ignored.replace("$", "").replace(",", "")
                if "-" in cost_str:
                    parts = cost_str.split("-")
                    low = int(float(parts[0].strip()))
                    high = int(float(parts[1].strip()))
                else:
                    low = high = int(float(cost_str.strip()))

                if item.priority == Priority.CRITICAL:
                    immediate_min += low
                    immediate_max += high
                elif item.priority == Priority.HIGH:
                    week_min += low
                    week_max += high
                else:
                    month_min += low
                    month_max += high
            except (ValueError, IndexError):
                continue

        def format_range(low: int, high: int) -> str:
            if low == 0 and high == 0:
                return "$0"
            if low == high:
                return f"${low:,}"
            return f"${low:,} - ${high:,}"

        return CostProjection(
            immediate_risk=format_range(immediate_min, immediate_max),
            week_risk=format_range(week_min, week_max),
            month_risk=format_range(
                immediate_min + week_min + month_min,
                immediate_max + week_max + month_max,
            ),
        )

    def generate_command_center_data(self) -> CommandCenterData:
        """
        Main method - generates complete command center data by combining all sources.
        """
        self._action_counter = 0
        action_items: List[ActionItem] = []

        # ═══════════════════════════════════════════════════════════════════
        # GATHER DATA FROM ALL SOURCES
        # ═══════════════════════════════════════════════════════════════════

        # 1. Predictive Maintenance Engine (trend-based)
        try:
            from predictive_maintenance_engine import get_predictive_maintenance_engine

            pm_engine = get_predictive_maintenance_engine()
            pm_data = pm_engine.get_fleet_summary()

            # Convert PM predictions to action items
            for item in pm_data.get("critical_items", []):
                component = item.get("component", "Unknown")
                priority, score = self._calculate_priority_score(
                    days_to_critical=item.get("days_to_critical"),
                    cost_estimate=item.get("cost_if_fail"),
                    component=component,
                )

                category = self.COMPONENT_CATEGORIES.get(
                    component, IssueCategory.ENGINE
                )
                action_type = self._determine_action_type(
                    priority, item.get("days_to_critical")
                )

                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id=item.get("truck_id", "???"),
                        priority=priority,
                        priority_score=score,
                        category=category,
                        component=component,
                        title=f"{component} - Atención Urgente",
                        description=f"Predicción basada en tendencia de sensor {item.get('sensor', 'N/A')}",
                        days_to_critical=item.get("days_to_critical"),
                        cost_if_ignored=item.get("cost_if_fail"),
                        current_value=item.get("current_value"),
                        trend=item.get("trend_per_day"),
                        threshold=None,
                        confidence="HIGH" if item.get("days_to_critical") else "MEDIUM",
                        action_type=action_type,
                        action_steps=self._generate_action_steps(
                            component, action_type, item.get("action", "")
                        ),
                        icon=self.COMPONENT_ICONS.get(component, "🔧"),
                        sources=["Predictive Maintenance Engine"],
                    )
                )

            # Also add high priority items
            for item in pm_data.get("high_priority_items", []):
                component = item.get("component", "Unknown")
                priority, score = self._calculate_priority_score(
                    days_to_critical=item.get("days_to_critical"),
                    component=component,
                )

                if priority == Priority.CRITICAL:
                    continue  # Already added above

                category = self.COMPONENT_CATEGORIES.get(
                    component, IssueCategory.ENGINE
                )
                action_type = self._determine_action_type(
                    priority, item.get("days_to_critical")
                )

                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id=item.get("truck_id", "???"),
                        priority=priority,
                        priority_score=score,
                        category=category,
                        component=component,
                        title=f"{component} - Programar Revisión",
                        description=f"Tendencia indica posible problema en {item.get('sensor', 'N/A')}",
                        days_to_critical=item.get("days_to_critical"),
                        cost_if_ignored=None,
                        current_value=None,
                        trend=None,
                        threshold=None,
                        confidence="MEDIUM",
                        action_type=action_type,
                        action_steps=self._generate_action_steps(
                            component, action_type, ""
                        ),
                        icon=self.COMPONENT_ICONS.get(component, "🔧"),
                        sources=["Predictive Maintenance Engine"],
                    )
                )

        except Exception as e:
            logger.warning(f"Could not get PM data: {e}")

        # 2. ML Anomaly Detection
        try:
            from ml_engines.anomaly_detector import analyze_fleet_anomalies

            anomalies = analyze_fleet_anomalies()

            for truck in anomalies:
                if truck.get("is_anomaly") and truck.get("anomaly_score", 0) >= 60:
                    priority, score = self._calculate_priority_score(
                        days_to_critical=None,
                        anomaly_score=truck.get("anomaly_score"),
                    )

                    # Extract main issue from anomalous features
                    features = truck.get("anomalous_features", [])
                    main_issue = (
                        features[0].get("feature", "Unknown")
                        if features
                        else "Comportamiento anómalo"
                    )

                    action_items.append(
                        ActionItem(
                            id=self._generate_action_id(),
                            truck_id=truck.get("truck_id", "???"),
                            priority=priority,
                            priority_score=score,
                            category=IssueCategory.ENGINE,
                            component="Análisis ML",
                            title=f"Anomalía Detectada - Score {truck.get('anomaly_score', 0):.0f}",
                            description=truck.get(
                                "explanation", "Patrón inusual detectado por ML"
                            ),
                            days_to_critical=None,
                            cost_if_ignored=None,
                            current_value=None,
                            trend=None,
                            threshold=None,
                            confidence="MEDIUM",
                            action_type=ActionType.INSPECT,
                            action_steps=[
                                "🔍 Inspeccionar camión para identificar causa",
                                f"📊 Revisar parámetro: {main_issue}",
                                "📝 Documentar hallazgos",
                            ],
                            icon="🧠",
                            sources=["ML Anomaly Detection"],
                        )
                    )
        except Exception as e:
            logger.debug(f"Could not get ML anomaly data: {e}")

        # 3. Sensor Health (GPS, Voltage, DTC)
        sensor_status = SensorStatus()
        try:
            from database_mysql import (
                get_sensor_health_summary,
                get_trucks_with_sensor_issues,
            )

            sensor_data = get_sensor_health_summary()
            # 🆕 v6.3.1: Get specific truck IDs with issues
            truck_issues = get_trucks_with_sensor_issues()

            sensor_status.total_trucks = sensor_data.get("total_trucks", 0)
            sensor_status.gps_issues = sensor_data.get("trucks_with_gps_issues", 0)
            sensor_status.voltage_issues = sensor_data.get(
                "trucks_with_voltage_issues", 0
            )
            sensor_status.dtc_active = sensor_data.get("trucks_with_dtc_active", 0)
            sensor_status.idle_deviation = sensor_data.get(
                "trucks_with_idle_deviation", 0
            )

            # Add voltage issues as action items if significant
            voltage_trucks = truck_issues.get("voltage_low", [])
            if voltage_trucks:
                truck_list = ", ".join([t["truck_id"] for t in voltage_trucks[:5]])
                if len(voltage_trucks) > 5:
                    truck_list += f" (+{len(voltage_trucks) - 5} más)"
                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id="FLEET",
                        priority=Priority.MEDIUM,
                        priority_score=45,
                        category=IssueCategory.ELECTRICAL,
                        component="Sistema eléctrico",
                        title=f"🔋 {len(voltage_trucks)} Camiones con Voltaje Bajo",
                        description=f"Camiones afectados: {truck_list}",
                        days_to_critical=None,
                        cost_if_ignored="$500 - $1,500 por camión",
                        current_value=(
                            f"Min: {min(t['value'] for t in voltage_trucks):.1f}V"
                            if voltage_trucks
                            else None
                        ),
                        trend=None,
                        threshold="<12.2V o >15.0V",
                        confidence="HIGH",
                        action_type=ActionType.INSPECT,
                        action_steps=[
                            f"🔋 Revisar: {truck_list}",
                            "🔌 Verificar conexiones y terminales",
                            "⚡ Revisar alternador",
                        ],
                        icon="🔋",
                        sources=["Sensor Health Monitor"],
                    )
                )

            # Add DTC alerts with decoded descriptions
            dtc_trucks = truck_issues.get("dtc_active", [])
            if dtc_trucks:
                from dtc_analyzer import get_dtc_analyzer

                analyzer = get_dtc_analyzer()

                # Get detailed DTC info for each truck
                dtc_details = []
                severity_icons = {"critical": "⛔", "warning": "⚠️", "info": "ℹ️"}

                for truck_data in dtc_trucks[:5]:
                    truck_id = truck_data["truck_id"]
                    dtc_code = truck_data.get("dtc_code", "")

                    if dtc_code:
                        # Use get_dtc_analysis_report instead of analyze_dtc
                        result = analyzer.get_dtc_analysis_report(truck_id, dtc_code)

                        if result.get("status") == "error" or not result.get("codes"):
                            dtc_details.append(
                                f"❓ {truck_id}: DTC {dtc_code} (sin decodificar)"
                            )
                        else:
                            codes = result.get("codes", [])
                            if codes:
                                first_code = codes[0]
                                component = first_code.get("component", dtc_code)
                                severity = first_code.get("severity", "warning")
                                icon = severity_icons.get(severity.lower(), "🔧")
                                spn = first_code.get("spn", "")
                                fmi = first_code.get("fmi", "")

                                # Formato: "⛔ CO0681: SPN 5444.1 - Calidad del Fluido DEF"
                                dtc_details.append(
                                    f"{icon} {truck_id}: SPN {spn}.{fmi} - {component}"
                                )

                description = (
                    ", ".join(dtc_details)
                    if dtc_details
                    else f"Ver detalles en dashboard para cada camión"
                )

                truck_list = ", ".join([t["truck_id"] for t in dtc_trucks[:5]])
                if len(dtc_trucks) > 5:
                    truck_list += f" (+{len(dtc_trucks) - 5} más)"

                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id="FLEET",
                        priority=(
                            Priority.HIGH if len(dtc_trucks) >= 3 else Priority.MEDIUM
                        ),
                        priority_score=60 if len(dtc_trucks) >= 3 else 45,
                        category=IssueCategory.SENSOR,
                        component="Códigos DTC",
                        title=f"🔧 {len(dtc_trucks)} Camiones con DTC Activos",
                        description=description,
                        days_to_critical=None,
                        cost_if_ignored=None,
                        current_value=None,
                        trend=None,
                        threshold=None,
                        confidence="HIGH",
                        action_type=ActionType.INSPECT,
                        action_steps=[
                            f"🔍 Revisar DTCs decodificados en dashboard",
                            f"📋 Camiones: {truck_list}",
                            "🔧 Reparar según diagnóstico específico",
                            "✅ Verificar y borrar códigos tras reparación",
                        ],
                        icon="🔧",
                        sources=["DTC Monitor"],
                    )
                )

            # 🆕 v6.3.1: Oil pressure issues - INDIVIDUAL items per truck
            oil_trucks = truck_issues.get("oil_pressure_low", [])
            for oil_truck in oil_trucks:
                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id=oil_truck['truck_id'],
                        priority=Priority.CRITICAL,
                        priority_score=90,
                        category=IssueCategory.ENGINE,
                        component="Sistema de Lubricación",
                        title=f"🛢️ Presión de Aceite Baja",
                        description=f"⚠️ URGENTE - Presión actual: {oil_truck['value']} PSI (límite: <25 PSI)",
                        days_to_critical=0,
                        cost_if_ignored="$15,000 - $50,000 (motor fundido)",
                        current_value=f"{oil_truck['value']:.1f} PSI",
                        trend=None,
                        threshold="<25 PSI",
                        confidence="HIGH",
                        action_type=ActionType.STOP_IMMEDIATELY,
                        action_steps=[
                            f"🛑 DETENER CAMIÓN {oil_truck['truck_id']} INMEDIATAMENTE",
                            "🔍 Verificar nivel de aceite del motor",
                            "🔧 Revisar sensor de presión de aceite",
                            "🔧 Inspeccionar bomba de aceite",
                            "🚫 No conducir hasta resolver el problema",
                        ],
                        icon="🛢️",
                        sources=["Oil Pressure Sensor"],
                    )
                )

            # 🆕 v6.3.1: DEF level warnings - INDIVIDUAL items per truck
            def_trucks = truck_issues.get("def_low", [])
            for def_truck in def_trucks:
                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id=def_truck['truck_id'],
                        priority=Priority.MEDIUM,
                        priority_score=50,
                        category=IssueCategory.DEF,
                        component="Sistema DEF/AdBlue",
                        title=f"🧪 Nivel de DEF Bajo",
                        description=f"Nivel actual: {def_truck['value']:.1f}% (límite: <15%)",
                        days_to_critical=3,
                        cost_if_ignored="$5,000+ (derate del motor)",
                        current_value=f"{def_truck['value']:.1f}%",
                        trend=None,
                        threshold="<15%",
                        confidence="HIGH",
                        action_type=ActionType.SCHEDULE_THIS_WEEK,
                        action_steps=[
                            f"⛽ Recargar DEF en camión {def_truck['truck_id']}",
                            "📍 Localizar estación de DEF cercana",
                            "📝 Verificar consumo normal de DEF",
                            "🔍 Inspeccionar sistema de inyección DEF",
                        ],
                        icon="🧪",
                        sources=["DEF Level Sensor"],
                    )
                )

            # 🆕 v6.3.1: Engine overload alerts - INDIVIDUAL items per truck
            overload_trucks = truck_issues.get("engine_overload", [])
            for overload_truck in overload_trucks:
                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id=overload_truck['truck_id'],
                        priority=Priority.HIGH,
                        priority_score=70,
                        category=IssueCategory.ENGINE,
                        component="Carga del Motor",
                        title=f"🔥 Sobrecarga de Motor",
                        description=f"Carga actual: {overload_truck['value']:.1f}% (límite: >90%)",
                        days_to_critical=7,
                        cost_if_ignored="$5,000 - $15,000 (reparaciones prematuras)",
                        current_value=f"{overload_truck['value']:.1f}%",
                        trend=None,
                        threshold=">90%",
                        confidence="MEDIUM",
                        action_type=ActionType.MONITOR,
                        action_steps=[
                            f"📊 Revisar carga del motor en {overload_truck['truck_id']}",
                            "🔧 Inspeccionar filtros de aire",
                        ],
                        icon="🔥",
                        sources=["Engine Load Sensor"],
                    )
                )

            # 🆕 v6.3.1: Coolant temperature high - INDIVIDUAL items per truck
            coolant_trucks = truck_issues.get("coolant_high", [])
            for coolant_truck in coolant_trucks:
                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id=coolant_truck['truck_id'],
                        priority=Priority.CRITICAL,
                        priority_score=85,
                        category=IssueCategory.ENGINE,
                        component="Sistema de Enfriamiento",
                        title=f"🌡️ Temperatura de Refrigerante Alta",
                        description=f"⚠️ URGENTE - Temperatura: {coolant_truck['value']:.1f}°F (límite: >220°F)",
                        days_to_critical=0,
                        cost_if_ignored="$3,000 - $20,000 (daño por sobrecalentamiento)",
                        current_value=f"{coolant_truck['value']:.1f}°F",
                        trend=None,
                        threshold=">220°F",
                        confidence="HIGH",
                        action_type=ActionType.STOP_IMMEDIATELY,
                        action_steps=[
                            f"🛑 DETENER CAMIÓN {coolant_truck['truck_id']} INMEDIATAMENTE",
                            "💧 Verificar nivel de refrigerante (esperar a que enfríe)",
                            "🔍 Revisar termostato y ventilador",
                            "🔍 Inspeccionar radiador y mangueras",
                            "🚫 NO abrir radiador si está caliente - riesgo de quemaduras",
                        ],
                        icon="🌡️",
                        sources=["Coolant Temperature Sensor"],
                    )
                )

        except Exception as e:
            logger.debug(f"Could not get sensor health data: {e}")

        # 4. Engine Health Alerts (database-stored alerts from real-time monitoring)
        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()
            with engine.connect() as conn:
                # Get active alerts from last 7 days
                result = conn.execute(
                    text(
                        """
                        SELECT 
                            id, truck_id, category, severity, sensor_name,
                            current_value, threshold_value, message, action_required
                        FROM engine_health_alerts
                        WHERE is_active = 1 
                        AND created_at > DATE_SUB(NOW(), INTERVAL 7 DAY)
                        ORDER BY 
                            FIELD(severity, 'critical', 'warning', 'watch', 'info'),
                            created_at DESC
                        LIMIT 50
                    """
                    )
                )
                alerts = result.fetchall()

                for alert in alerts:
                    alert_id, truck_id, category, severity, sensor_name = alert[:5]
                    current_val, threshold_val, message, action_required = alert[5:9]

                    # Map severity to priority
                    priority_map = {
                        "critical": Priority.CRITICAL,
                        "warning": Priority.HIGH,
                        "watch": Priority.MEDIUM,
                        "info": Priority.LOW,
                    }
                    priority = priority_map.get(severity, Priority.MEDIUM)

                    # Calculate priority score
                    score_map = {
                        Priority.CRITICAL: 90,
                        Priority.HIGH: 70,
                        Priority.MEDIUM: 50,
                        Priority.LOW: 30,
                    }
                    score = score_map.get(priority, 50)

                    # Map category to IssueCategory
                    category_map = {
                        "engine": IssueCategory.ENGINE,
                        "transmission": IssueCategory.TRANSMISSION,
                        "electrical": IssueCategory.ELECTRICAL,
                        "fuel": IssueCategory.FUEL,
                        "brake": IssueCategory.BRAKES,
                        "brakes": IssueCategory.BRAKES,
                        "sensor": IssueCategory.SENSOR,
                    }
                    issue_cat = category_map.get(
                        (category or "").lower(), IssueCategory.ENGINE
                    )

                    action_items.append(
                        ActionItem(
                            id=self._generate_action_id(),
                            truck_id=truck_id or "???",
                            priority=priority,
                            priority_score=score,
                            category=issue_cat,
                            component=sensor_name or category or "Unknown",
                            title=f"[{severity.upper()}] {sensor_name or category}",
                            description=message
                            or "Alert from engine health monitoring",
                            days_to_critical=None,
                            cost_if_ignored=None,
                            current_value=str(current_val) if current_val else None,
                            trend=None,
                            threshold=str(threshold_val) if threshold_val else None,
                            confidence="HIGH",
                            action_type=(
                                ActionType.STOP_IMMEDIATELY
                                if priority == Priority.CRITICAL
                                else ActionType.INSPECT
                            ),
                            action_steps=(
                                [action_required]
                                if action_required
                                else ["Investigate and resolve issue"]
                            ),
                            icon=self.COMPONENT_ICONS.get(
                                sensor_name or category or "", "🔧"
                            ),
                            sources=["Engine Health Monitor (DB)"],
                        )
                    )

                logger.info(
                    f"📊 Loaded {len(alerts)} alerts from engine_health_alerts table"
                )

        except Exception as e:
            logger.debug(f"Could not get engine health alerts from DB: {e}")

        # 5. DTC Events (real-time DTC codes from wialon_sync)
        try:
            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            engine = get_sqlalchemy_engine()
            with engine.connect() as conn:
                # Get active DTCs from last 48 hours
                result = conn.execute(
                    text(
                        """
                        SELECT DISTINCT
                            truck_id, dtc_code, severity, system, 
                            description, recommended_action, timestamp_utc
                        FROM dtc_events
                        WHERE status = 'ACTIVE' 
                        AND timestamp_utc > DATE_SUB(NOW(), INTERVAL 48 HOUR)
                        ORDER BY 
                            FIELD(severity, 'CRITICAL', 'WARNING', 'INFO'),
                            timestamp_utc DESC
                        LIMIT 30
                    """
                    )
                )
                dtc_rows = result.fetchall()

                for dtc in dtc_rows:
                    truck_id, dtc_code, severity, system = dtc[:4]
                    description, recommended_action, timestamp = dtc[4:7]

                    # Map severity to priority
                    priority_map = {
                        "CRITICAL": Priority.CRITICAL,
                        "WARNING": Priority.HIGH,
                        "INFO": Priority.MEDIUM,
                    }
                    priority = priority_map.get(severity, Priority.MEDIUM)

                    # Calculate priority score
                    score_map = {
                        Priority.CRITICAL: 95,
                        Priority.HIGH: 75,
                        Priority.MEDIUM: 55,
                    }
                    score = score_map.get(priority, 55)

                    # Map system to category
                    system_category_map = {
                        "ENGINE": IssueCategory.ENGINE,
                        "TRANSMISSION": IssueCategory.TRANSMISSION,
                        "AFTERTREATMENT": IssueCategory.ENGINE,
                        "ELECTRICAL": IssueCategory.ELECTRICAL,
                        "FUEL": IssueCategory.FUEL,
                        "BRAKE": IssueCategory.BRAKES,
                        "BRAKES": IssueCategory.BRAKES,
                    }
                    issue_cat = system_category_map.get(
                        (system or "").upper(), IssueCategory.ENGINE
                    )

                    action_items.append(
                        ActionItem(
                            id=self._generate_action_id(),
                            truck_id=truck_id or "???",
                            priority=priority,
                            priority_score=score,
                            category=issue_cat,
                            component=f"DTC {dtc_code}",
                            title=f"[DTC] {dtc_code} - {system or 'Unknown System'}",
                            description=description or f"DTC code {dtc_code} detected",
                            days_to_critical=None,
                            cost_if_ignored=None,
                            current_value=None,
                            trend=None,
                            threshold=None,
                            confidence="HIGH",
                            action_type=(
                                ActionType.STOP_IMMEDIATELY
                                if priority == Priority.CRITICAL
                                else ActionType.INSPECT
                            ),
                            action_steps=(
                                [recommended_action]
                                if recommended_action
                                else [
                                    f"🔧 Read DTC codes on {truck_id}",
                                    "📋 Diagnose root cause",
                                    "✅ Repair and clear code",
                                ]
                            ),
                            icon="🚨" if priority == Priority.CRITICAL else "⚠️",
                            sources=["DTC Events (Real-time)"],
                        )
                    )

                logger.info(
                    f"📊 Loaded {len(dtc_rows)} active DTCs from dtc_events table"
                )

        except Exception as e:
            logger.debug(f"Could not get DTC events from DB: {e}")

        # ═══════════════════════════════════════════════════════════════════
        # 6. REAL-TIME PREDICTIVE ENGINE (TRUE Predictive Maintenance) 🆕 v1.2.0
        # v1.3.0: Added try/except, optimized query, sensor validation
        # Analyzes live sensor data to predict failures BEFORE they happen
        # ═══════════════════════════════════════════════════════════════════
        try:
            # v1.3.0: Graceful import with fallback
            try:
                from realtime_predictive_engine import get_realtime_predictive_engine
            except ImportError as ie:
                logger.info(f"Real-Time Predictive Engine not available: {ie}")
                raise  # Re-raise to skip this source

            from database_mysql import get_sqlalchemy_engine
            from sqlalchemy import text

            rt_engine = get_realtime_predictive_engine()
            engine = get_sqlalchemy_engine()

            # v1.3.0: Optimized query using window function to get latest per truck
            # This is more efficient than ORDER BY + Python filtering
            with engine.connect() as conn:
                result = conn.execute(
                    text(
                        """
                    SELECT 
                        truck_id,
                        oil_press, oil_temp,
                        cool_temp, trams_t,
                        engine_load, rpm,
                        def_level, voltage,
                        intk_t, fuel_lvl,
                        total_idle_fuel, total_fuel_used,
                        idle_hours, engine_hours
                    FROM (
                        SELECT *,
                            ROW_NUMBER() OVER (
                                PARTITION BY truck_id 
                                ORDER BY timestamp_utc DESC
                            ) as rn
                        FROM real_time_data
                        WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 2 HOUR)
                    ) latest
                    WHERE rn = 1
                """
                    )
                )

                # Build fleet_sensors dict with validated data
                fleet_sensors = {}

                for row in result:
                    truck_id = row[0]

                    # v1.3.0: Validate sensor values before using
                    raw_sensors = {
                        "oil_press": row[1],
                        "oil_temp": row[2],
                        "cool_temp": row[3],
                        "trams_t": row[4],
                        "engine_load": row[5],
                        "rpm": row[6],
                        "def_level": row[7],
                        "voltage": row[8],
                        "intk_t": row[9],
                        "fuel_lvl": row[10],
                    }

                    # Validate sensor values
                    validated = self._validate_sensor_dict(raw_sensors)

                    # Add non-validated fields (totals that don't need range checks)
                    validated["total_idle_fuel"] = row[11]
                    validated["total_fuel_used"] = row[12]
                    validated["idle_hours"] = row[13]
                    validated["engine_hours"] = row[14]

                    fleet_sensors[truck_id] = validated

            # Analyze all trucks
            rt_summary = rt_engine.get_fleet_summary(fleet_sensors)

            for alert_dict in rt_summary.get("all_alerts", []):
                # Map severity to priority
                severity_map = {
                    "CRITICAL": Priority.CRITICAL,
                    "WARNING": Priority.HIGH,
                    "WATCH": Priority.MEDIUM,
                }
                priority = severity_map.get(alert_dict["severity"], Priority.MEDIUM)

                # v1.3.0: Use unified scoring via _calculate_priority_score
                # Get component for scoring
                component = alert_dict["component"]

                # Calculate days to critical from predicted_failure_hours
                hours = alert_dict.get("predicted_failure_hours")
                days_to_critical = hours / 24 if hours is not None else None

                # Use unified priority scoring for consistency
                calculated_priority, score = self._calculate_priority_score(
                    days_to_critical=days_to_critical,
                    anomaly_score=alert_dict.get("confidence"),
                    component=component,
                )

                # Use the higher priority between mapped severity and calculated
                if calculated_priority.value < priority.value:  # CRÍTICO < ALTO < MEDIO
                    priority = calculated_priority

                # Determine category from component
                category_map = {
                    "Sistema de Lubricación": IssueCategory.ENGINE,
                    "Bomba de Aceite": IssueCategory.ENGINE,
                    "Sistema de Enfriamiento": IssueCategory.ENGINE,
                    "Transmisión": IssueCategory.TRANSMISSION,
                    "Sistema DEF": IssueCategory.ENGINE,
                    "Sistema Eléctrico": IssueCategory.ELECTRICAL,
                    "Motor": IssueCategory.ENGINE,
                    "Turbocompresor": IssueCategory.ENGINE,
                    "Eficiencia General": IssueCategory.FUEL,
                }
                category = category_map.get(component, IssueCategory.ENGINE)

                # Determine action type based on alert type and priority
                # 🐛 FIX v1.3.0: Changed SCHEDULE_SERVICE (non-existent) to SCHEDULE_THIS_WEEK
                action_type = ActionType.INSPECT
                if priority == Priority.CRITICAL:
                    action_type = ActionType.STOP_IMMEDIATELY
                elif alert_dict["alert_type"] == "trend":
                    action_type = (
                        ActionType.SCHEDULE_THIS_WEEK
                    )  # Fixed: was SCHEDULE_SERVICE
                elif alert_dict["alert_type"] == "correlation":
                    action_type = ActionType.SCHEDULE_THIS_WEEK

                # Calculate days to critical if available
                hours = alert_dict.get("predicted_failure_hours")
                days_to_critical = hours / 24 if hours is not None else None

                # 🆕 v1.3.0: Get cost estimate for the component
                cost_string = self._format_cost_string(component)

                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id=alert_dict["truck_id"],
                        priority=priority,
                        priority_score=score,
                        category=category,
                        component=component,
                        title=f"🧠 {alert_dict['message'][:60]}{'...' if len(alert_dict['message']) > 60 else ''}",
                        description=alert_dict["recommended_action"],
                        days_to_critical=days_to_critical,
                        cost_if_ignored=cost_string,  # 🐛 FIX v1.3.0: Added cost estimate
                        current_value=None,
                        trend=None,
                        threshold=None,
                        confidence=(
                            "HIGH" if alert_dict["confidence"] >= 85 else "MEDIUM"
                        ),
                        action_type=action_type,
                        action_steps=[
                            alert_dict["recommended_action"],
                            f"📊 Tipo de alerta: {alert_dict['alert_type'].upper()}",
                            f"🎯 Confianza: {alert_dict['confidence']:.0f}%",
                        ],
                        icon="🧠",
                        sources=[f"Real-Time Predictive ({alert_dict['alert_type']})"],
                    )
                )

            logger.info(
                f"🧠 Real-Time Predictive: {rt_summary['critical_count']} críticos, "
                f"{rt_summary['warning_count']} warnings de {rt_summary['total_trucks_analyzed']} trucks"
            )

        except Exception as e:
            logger.debug(f"Could not get real-time predictive data: {e}")

        # ═══════════════════════════════════════════════════════════════════
        # v1.2.0: DEDUPLICATE ACTION ITEMS
        # Same issue can be detected by multiple sources (PM, Sensor Health, DB alerts)
        # Keep the one with highest priority score
        # ═══════════════════════════════════════════════════════════════════
        action_items = self._deduplicate_action_items(action_items)

        # ═══════════════════════════════════════════════════════════════════
        # SORT AND ORGANIZE
        # ═══════════════════════════════════════════════════════════════════

        # Sort by priority score (highest first)
        action_items.sort(key=lambda x: x.priority_score, reverse=True)

        # Get total trucks from various sources (BEFORE urgency summary)
        total_trucks = sensor_status.total_trucks
        if total_trucks == 0:
            try:
                from config import get_allowed_trucks

                total_trucks = len(get_allowed_trucks())
            except:
                total_trucks = 45  # Fallback to known fleet size

        # Update sensor_status.total_trucks if it was 0
        if sensor_status.total_trucks == 0:
            sensor_status = SensorStatus(
                gps_issues=sensor_status.gps_issues,
                voltage_issues=sensor_status.voltage_issues,
                dtc_active=sensor_status.dtc_active,
                idle_deviation=sensor_status.idle_deviation,
                total_trucks=total_trucks,
            )

        # Calculate urgency summary (now with correct total_trucks)
        # v1.3.0: Fixed "OK" calculation - only count trucks without CRITICAL/HIGH issues
        # Previously counted LOW/MEDIUM issues as "OK" which inflated health

        # Get trucks with any issues
        trucks_with_any_issue = set(
            i.truck_id for i in action_items if i.truck_id != "FLEET"
        )

        # v1.3.0: Get trucks with serious issues (CRITICAL or HIGH) - these are NOT ok
        trucks_with_serious_issues = set(
            i.truck_id
            for i in action_items
            if i.truck_id != "FLEET"
            and i.priority in [Priority.CRITICAL, Priority.HIGH]
        )

        # Trucks are "OK" if they have no issues at all
        # (previously, trucks with LOW/MEDIUM issues were counted as partially OK)
        ok_trucks = max(0, total_trucks - len(trucks_with_any_issue))

        urgency = UrgencySummary(
            critical=sum(1 for i in action_items if i.priority == Priority.CRITICAL),
            high=sum(1 for i in action_items if i.priority == Priority.HIGH),
            medium=sum(1 for i in action_items if i.priority == Priority.MEDIUM),
            low=sum(1 for i in action_items if i.priority == Priority.LOW),
            ok=ok_trucks,
        )

        # Log summary for debugging
        logger.debug(
            f"📊 Urgency: {urgency.critical} critical, {urgency.high} high, "
            f"{urgency.medium} medium, {urgency.low} low, {urgency.ok} ok "
            f"(total trucks: {total_trucks}, with issues: {len(trucks_with_any_issue)})"
        )

        # Calculate fleet health score - v1.3.0: now includes distribution analysis
        fleet_health = self._calculate_fleet_health_score(
            urgency, total_trucks, action_items
        )

        # Generate insights
        insights = self._generate_insights(action_items, urgency)

        # Estimate costs
        cost_projection = self._estimate_costs(action_items)

        # Build response
        return CommandCenterData(
            generated_at=datetime.now(timezone.utc).isoformat(),
            fleet_health=fleet_health,
            total_trucks=total_trucks,
            # 🔧 FIX v1.0.1: trucks_analyzed should be total_trucks, not just trucks with issues
            # The Command Center analyzes ALL trucks for potential issues
            trucks_analyzed=total_trucks,
            urgency_summary=urgency,
            sensor_status=sensor_status,
            cost_projection=cost_projection,
            action_items=action_items,
            critical_actions=[
                i for i in action_items if i.priority == Priority.CRITICAL
            ],
            high_priority_actions=[
                i for i in action_items if i.priority == Priority.HIGH
            ],
            insights=insights,
            data_quality={
                "pm_engine": True,  # TODO: Add actual checks
                "ml_anomaly": False,
                "sensor_health": sensor_status.total_trucks > 0,
                "last_sync": datetime.now(timezone.utc).isoformat(),
            },
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_command_center: Optional[FleetCommandCenter] = None


def get_command_center() -> FleetCommandCenter:
    """Get or create the global command center instance"""
    global _command_center
    if _command_center is None:
        _command_center = FleetCommandCenter()
    return _command_center


# ═══════════════════════════════════════════════════════════════════════════════
# API ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter(
    prefix="/fuelAnalytics/api/command-center", tags=["Fleet Command Center"]
)

# v1.1.0: Cache configuration for performance with 45+ trucks
CACHE_TTL_DASHBOARD = 30  # 30 seconds - balances freshness vs performance
CACHE_TTL_ACTIONS = 15  # 15 seconds - more real-time for action items
CACHE_KEY_DASHBOARD = "command_center:dashboard"
CACHE_KEY_ACTIONS = "command_center:actions"


class CommandCenterResponse(BaseModel):
    """API Response model for command center data"""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    cached: bool = False  # v1.1.0: Indicates if response was from cache


@router.get("/dashboard")
async def get_command_center_dashboard(
    bypass_cache: bool = Query(False, description="Bypass cache and get fresh data")
):
    """
    Get the unified Fleet Command Center dashboard data.

    v1.1.0: Now with caching support for better performance.
    Cache TTL: 30 seconds

    Args:
        bypass_cache: Set to true to force fresh data (ignores cache)

    Returns:
        Complete dashboard with:
        - Fleet health score
        - Urgency summary
        - Prioritized action items
        - Sensor status
        - Cost projections
        - Insights
        - cached: Whether response was served from cache
    """
    try:
        # v1.1.0: Try cache first
        from_cache = False
        if not bypass_cache:
            try:
                from cache_service import get_cache

                cache = await get_cache()
                cached_data = await cache.get(CACHE_KEY_DASHBOARD)
                if cached_data:
                    logger.debug("Command Center dashboard served from cache")
                    return {
                        "success": True,
                        "data": cached_data,
                        "cached": True,
                    }
            except Exception as cache_err:
                logger.warning(
                    f"Cache read failed, falling back to fresh data: {cache_err}"
                )

        # Generate fresh data
        cc = get_command_center()
        data = cc.generate_command_center_data()
        data_dict = data.to_dict()

        # v1.1.0: Store in cache
        try:
            from cache_service import get_cache

            cache = await get_cache()
            await cache.set(CACHE_KEY_DASHBOARD, data_dict, ttl=CACHE_TTL_DASHBOARD)
            logger.debug(f"Command Center dashboard cached for {CACHE_TTL_DASHBOARD}s")
        except Exception as cache_err:
            logger.warning(f"Cache write failed: {cache_err}")

        return {
            "success": True,
            "data": data_dict,
            "cached": False,
        }
    except Exception as e:
        import traceback

        logger.error(f"Error getting command center data: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/actions")
async def get_prioritized_actions(
    priority: Optional[str] = None,
    category: Optional[str] = None,
    truck_id: Optional[str] = None,
    limit: int = 50,
):
    """
    Get prioritized action items with optional filtering.

    Args:
        priority: Filter by priority (CRÍTICO, ALTO, MEDIO, BAJO)
        category: Filter by category (Motor, Transmisión, etc.)
        truck_id: Filter by truck ID
        limit: Maximum items to return
    """
    try:
        cc = get_command_center()
        data = cc.generate_command_center_data()

        # Convert to dict and get action items
        data_dict = data.to_dict()
        actions = data_dict.get("action_items", [])

        # Apply filters
        if priority:
            actions = [a for a in actions if a.get("priority") == priority]
        if category:
            actions = [a for a in actions if a.get("category") == category]
        if truck_id:
            actions = [a for a in actions if a.get("truck_id") == truck_id]

        return {
            "success": True,
            "total": len(actions),
            "items": actions[:limit],
        }
    except Exception as e:
        logger.error(f"Error getting actions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/truck/{truck_id}")
async def get_truck_summary(truck_id: str):
    """
    Get command center summary for a specific truck.

    Returns all action items and status for the specified truck.
    """
    try:
        cc = get_command_center()
        data = cc.generate_command_center_data()

        # Convert to dict and filter actions for this truck
        data_dict = data.to_dict()
        all_actions = data_dict.get("action_items", [])
        truck_actions = [a for a in all_actions if a.get("truck_id") == truck_id]

        # Determine truck priority
        if any(a.get("priority") == "CRÍTICO" for a in truck_actions):
            truck_priority = "CRÍTICO"
        elif any(a.get("priority") == "ALTO" for a in truck_actions):
            truck_priority = "ALTO"
        elif any(a.get("priority") == "MEDIO" for a in truck_actions):
            truck_priority = "MEDIO"
        elif any(a.get("priority") == "BAJO" for a in truck_actions):
            truck_priority = "BAJO"
        else:
            truck_priority = "OK"

        return {
            "success": True,
            "truck_id": truck_id,
            "priority": truck_priority,
            "action_count": len(truck_actions),
            "actions": truck_actions,
        }
    except Exception as e:
        logger.error(f"Error getting truck summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/insights")
async def get_fleet_insights():
    """
    Get AI-generated fleet insights.

    Returns actionable insights based on pattern analysis.
    """
    try:
        cc = get_command_center()
        data = cc.generate_command_center_data()
        data_dict = data.to_dict()

        return {
            "success": True,
            "insights": data_dict.get("insights", []),
            "fleet_health": data_dict.get("fleet_health"),
            "data_quality": data_dict.get("data_quality"),
        }
    except Exception as e:
        logger.error(f"Error getting insights: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def command_center_health_check():
    """Health check endpoint for the command center service."""
    try:
        cc = get_command_center()
        # Generate data to verify all systems are working
        data = cc.generate_command_center_data()
        return {
            "status": "healthy",
            "version": cc.VERSION,
            "data_sources": data.data_quality,
            "trucks_analyzed": data.trucks_analyzed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# ═══════════════════════════════════════════════════════════════════════════════
# v1.1.0: HISTORICAL TREND TRACKING
# Track fleet health over time to answer "¿Está mejorando o empeorando?"
# ═══════════════════════════════════════════════════════════════════════════════

# In-memory trend storage (in production, use Redis or DB)
# v1.2.0: Thread-safe deque with lock for concurrent access
_MAX_TREND_HISTORY = 1000  # Keep last 1000 snapshots
_trend_history: deque = deque(maxlen=_MAX_TREND_HISTORY)
_trend_lock = threading.Lock()


def _record_trend_snapshot(data: CommandCenterData) -> None:
    """
    Record a snapshot of fleet health for trend analysis.

    v1.2.0: Thread-safe implementation using lock.
    """
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "fleet_health_score": data.fleet_health.score if data.fleet_health else 0,
        "fleet_health_status": (
            data.fleet_health.status if data.fleet_health else "Unknown"
        ),
        "critical_count": data.urgency_summary.critical if data.urgency_summary else 0,
        "high_count": data.urgency_summary.high if data.urgency_summary else 0,
        "medium_count": data.urgency_summary.medium if data.urgency_summary else 0,
        "low_count": data.urgency_summary.low if data.urgency_summary else 0,
        "total_issues": (
            data.urgency_summary.total_issues if data.urgency_summary else 0
        ),
        "trucks_analyzed": data.trucks_analyzed,
    }

    with _trend_lock:
        _trend_history.append(snapshot)
        # deque with maxlen auto-removes old items, no manual cleanup needed


def _calculate_trend(values: List[float], window: int = 10) -> str:
    """
    Calculate trend direction from recent values.

    Returns: "improving", "stable", "declining"
    """
    if not values or len(values) < 2:
        return "stable"

    recent = values[-min(window, len(values)) :]

    if len(recent) < 2:
        return "stable"

    # Simple linear trend: compare first half avg to second half avg
    # Ensure mid is at least 1 to avoid division by zero and IndexError
    mid = max(1, len(recent) // 2)
    first_half_avg = sum(recent[:mid]) / mid
    second_half_avg = sum(recent[mid:]) / max(1, len(recent) - mid)

    change_pct = (
        ((second_half_avg - first_half_avg) / first_half_avg * 100)
        if first_half_avg > 0
        else 0
    )

    if change_pct > 3:  # 3% improvement threshold
        return "improving"
    elif change_pct < -3:  # 3% decline threshold
        return "declining"
    else:
        return "stable"


@router.get("/trends")
async def get_fleet_trends(
    hours: int = Query(
        24, ge=1, le=168, description="Hours of history to analyze (1-168)"
    ),
):
    """
    Get historical trend data for fleet health.

    v1.1.0: New endpoint to answer "Is the fleet improving or declining?"

    Args:
        hours: Number of hours of history to analyze (default 24, max 168/7 days)

    Returns:
        - trend: "improving", "stable", or "declining"
        - health_scores: Array of historical health scores
        - issue_counts: Array of historical issue counts
        - summary: Human-readable trend summary
    """
    try:
        if not _trend_history:
            # If no history, record current state
            cc = get_command_center()
            data = cc.generate_command_center_data()
            _record_trend_snapshot(data)

        # Filter to requested time window
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        recent_history = [
            h
            for h in _trend_history
            if datetime.fromisoformat(h["timestamp"].replace("Z", "+00:00")) > cutoff
        ]

        if not recent_history:
            recent_history = _trend_history[-10:] if _trend_history else []

        # Extract time series
        health_scores = [h["fleet_health_score"] for h in recent_history]
        issue_counts = [h["total_issues"] for h in recent_history]
        critical_counts = [h["critical_count"] for h in recent_history]

        # Calculate trends
        health_trend = _calculate_trend(health_scores)
        issues_trend = _calculate_trend(issue_counts)
        # For issues, "improving" means decreasing
        if issues_trend == "improving":
            issues_trend = "declining"  # More issues = declining
        elif issues_trend == "declining":
            issues_trend = "improving"  # Fewer issues = improving

        # Generate summary
        current_health = health_scores[-1] if health_scores else 0
        avg_health = sum(health_scores) / len(health_scores) if health_scores else 0

        if health_trend == "improving":
            summary = f"✅ La salud de la flota está mejorando. Score actual: {current_health}%, promedio: {avg_health:.0f}%"
        elif health_trend == "declining":
            summary = f"⚠️ La salud de la flota está empeorando. Score actual: {current_health}%, promedio: {avg_health:.0f}%"
        else:
            summary = f"📊 La salud de la flota está estable. Score actual: {current_health}%, promedio: {avg_health:.0f}%"

        return {
            "success": True,
            "period_hours": hours,
            "data_points": len(recent_history),
            "trend": {
                "health": health_trend,
                "issues": issues_trend,
            },
            "current": {
                "health_score": current_health,
                "critical_issues": critical_counts[-1] if critical_counts else 0,
                "total_issues": issue_counts[-1] if issue_counts else 0,
            },
            "history": {
                "health_scores": health_scores[-50:],  # Last 50 points
                "issue_counts": issue_counts[-50:],
                "timestamps": [h["timestamp"] for h in recent_history[-50:]],
            },
            "summary": summary,
        }
    except Exception as e:
        logger.error(f"Error getting trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trends/record")
async def record_trend_snapshot():
    """
    Manually record a trend snapshot (called periodically by scheduler).

    In production, this should be called every 5-15 minutes by a cron job
    or background task to build historical data.
    """
    try:
        cc = get_command_center()
        data = cc.generate_command_center_data()
        _record_trend_snapshot(data)

        return {
            "success": True,
            "message": "Trend snapshot recorded",
            "total_snapshots": len(_trend_history),
            "current_health": data.fleet_health.score if data.fleet_health else 0,
        }
    except Exception as e:
        logger.error(f"Error recording trend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# v1.5.0 FASE 4 & 5: NEW ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/risk-scores")
async def get_truck_risk_scores(
    top_n: int = Query(
        10, ge=1, le=50, description="Number of top risk trucks to return"
    ),
):
    """
    v1.5.0 FASE 4.4: Get truck risk scores.

    Returns the top N at-risk trucks with their risk scores and contributing factors.
    """
    try:
        cc = get_command_center()
        data = cc.generate_command_center_data()

        risk_scores = cc.get_top_risk_trucks(data.action_items, top_n)

        return {
            "success": True,
            "top_risk_trucks": [r.to_dict() for r in risk_scores],
            "total_trucks_analyzed": data.trucks_analyzed,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error getting risk scores: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/correlations")
async def get_failure_correlations():
    """
    v1.5.0 FASE 5.1: Get detected failure correlations.

    Identifies correlated failures that indicate systemic issues
    (e.g., coolant↑ + oil_temp↑ = cooling system problem).
    """
    try:
        cc = get_command_center()
        data = cc.generate_command_center_data()

        correlations = cc.detect_failure_correlations(data.action_items)

        return {
            "success": True,
            "correlations": [c.to_dict() for c in correlations],
            "patterns_checked": len(cc.FAILURE_CORRELATIONS),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error detecting correlations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/def-prediction/{truck_id}")
async def get_def_prediction(
    truck_id: str,
    current_level: float = Query(
        ..., ge=0, le=100, description="Current DEF level (%)"
    ),
    daily_miles: Optional[float] = Query(None, ge=0, description="Average daily miles"),
    avg_mpg: Optional[float] = Query(None, ge=0, description="Average MPG"),
):
    """
    v1.5.0 FASE 5.3: Get DEF depletion prediction for a truck.

    Predicts days until DEF empty and derate based on consumption patterns.
    """
    try:
        cc = get_command_center()
        prediction = cc.predict_def_depletion(
            truck_id=truck_id,
            current_level_pct=current_level,
            daily_miles=daily_miles,
            avg_mpg=avg_mpg,
        )

        # Generate alert level
        alert_level = "ok"
        if prediction.days_until_derate <= 1:
            alert_level = "critical"
        elif prediction.days_until_derate <= 3:
            alert_level = "high"
        elif prediction.days_until_derate <= 7:
            alert_level = "medium"

        return {
            "success": True,
            "prediction": prediction.to_dict(),
            "alert_level": alert_level,
            "recommendation": (
                f"DEF will reach derate level in {prediction.days_until_derate:.1f} days. "
                + (
                    "⚠️ Fill immediately!"
                    if alert_level in ["critical", "high"]
                    else "Plan refill accordingly."
                )
            ),
        }
    except Exception as e:
        logger.error(f"Error predicting DEF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/detect")
async def detect_sensor_issue(
    truck_id: str = Query(..., description="Truck identifier"),
    sensor_name: str = Query(
        ..., description="Sensor name (e.g., oil_press, cool_temp)"
    ),
    current_value: float = Query(..., description="Current sensor reading"),
    baseline_value: Optional[float] = Query(
        None, description="Optional baseline value"
    ),
    component: Optional[str] = Query(
        None, description="Component name for action lookup"
    ),
):
    """
    v1.5.0 FASE 4.6: Detect and decide on a sensor issue.

    This endpoint demonstrates the separation of DETECTION and DECISION phases:
    - Detection: Analyzes the sensor data to determine if there's an issue
    - Decision: Determines what action to take based on the detection

    Use this for real-time sensor analysis and action recommendation.
    """
    try:
        cc = get_command_center()
        detection, decision = cc.detect_and_decide(
            truck_id=truck_id,
            sensor_name=sensor_name,
            current_value=current_value,
            baseline_value=baseline_value,
            component=component,
        )

        return {
            "success": True,
            "detection": {
                "is_issue": detection["is_issue"],
                "severity": detection["severity"],
                "deviation_pct": detection["deviation_pct"],
                "trend": detection["trend"],
                "persistence": detection["persistence"],
                "confidence": detection["confidence"],
            },
            "decision": {
                "priority": decision["priority"].value,
                "priority_score": decision["priority_score"],
                "action_type": decision["action_type"].value,
                "action_steps": decision["action_steps"],
                "reasoning": decision["reasoning"],
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error in detect/decide: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/spn/{spn}")
async def get_spn_info(spn: int):
    """
    v1.5.0 FASE 5.2: Get J1939 SPN (Standard Parameter Number) information.

    Returns component name and details for a given SPN.
    """
    try:
        cc = get_command_center()
        info = cc.get_spn_info(spn)

        if info is None:
            return {
                "success": False,
                "message": f"SPN {spn} not found in mapping",
                "suggestion": "This SPN may not be in our standard mapping. Contact support to add it.",
            }

        return {
            "success": True,
            "spn": spn,
            "info": info,
        }
    except Exception as e:
        logger.error(f"Error getting SPN info: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config")
async def get_command_center_config():
    """
    v1.5.0 FASE 4.5: Get current configuration.

    Returns the current thresholds, weights, and settings that can be
    customized via YAML configuration file.
    """
    try:
        cc = get_command_center()

        return {
            "success": True,
            "version": cc.VERSION,
            "config": {
                "sensor_windows": cc.SENSOR_WINDOWS,
                "persistence_thresholds": cc.PERSISTENCE_THRESHOLDS,
                "offline_thresholds": cc.OFFLINE_THRESHOLDS,
                "failure_correlations": list(cc.FAILURE_CORRELATIONS.keys()),
                "def_consumption_config": cc.DEF_CONSUMPTION_CONFIG,
                "time_horizon_weights": cc.TIME_HORIZON_WEIGHTS,
            },
            "config_file_note": (
                "These values can be customized by creating a 'command_center_config.yaml' file. "
                "See documentation for format."
            ),
        }
    except Exception as e:
        logger.error(f"Error getting config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# v1.7.0: INTEGRATED TRUCK HEALTH ENDPOINT
# Combines all data sources: Fleet Command Center + Driver Scoring + Component Health + DTC
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/truck/{truck_id}/comprehensive")
async def get_comprehensive_truck_health(
    truck_id: str,
    dtc_string: Optional[str] = Query(
        default=None, description="Current DTC codes (SPN.FMI)"
    ),
):
    """
    v1.7.0: Get comprehensive truck health combining ALL data sources.

    Integrates:
    1. Fleet Command Center predictive maintenance
    2. Driver behavior scoring (speeding, idle)
    3. Component health (turbo, oil, coolant)
    4. DTC analysis (J1939 codes)

    Returns unified health score with prioritized recommendations.
    """
    try:
        cc = get_command_center()

        # Get base Fleet Command Center data
        # Find truck in current data
        truck_actions = [a for a in cc.recent_actions if a.truck_id == truck_id]

        # Calculate base risk score
        try:
            risk_data = cc.calculate_truck_risk_score(truck_id, cc.current_data)
            base_risk = risk_data.get("risk_score", 50)
        except Exception:
            base_risk = 50

        # Get Driver Scoring
        driver_data = {"score": 100, "grade": "A", "tips": []}
        try:
            from driver_scoring_engine import get_scoring_engine

            scoring_engine = get_scoring_engine()
            driver_score = scoring_engine.calculate_score(truck_id, period_days=30)
            tips = scoring_engine.get_improvement_tips(truck_id)
            driver_data = {
                "score": driver_score.score,
                "grade": driver_score.grade,
                "tips": tips[:3],
                "events": len(driver_score.events),
                "speedings": len(driver_score.speeding_events),
            }
        except ImportError:
            logger.debug("Driver scoring engine not available")
        except Exception as e:
            logger.debug(f"Could not get driver score: {e}")

        # Get Component Health
        component_data = {"turbo": {}, "oil": {}, "coolant": {}, "avg_score": 100}
        try:
            from component_health_predictors import (
                get_turbo_predictor,
                get_oil_tracker,
                get_coolant_detector,
            )

            turbo = get_turbo_predictor().predict(truck_id)
            oil = get_oil_tracker().predict(truck_id)
            coolant = get_coolant_detector().predict(truck_id)

            component_data = {
                "turbo": {
                    "score": turbo.score,
                    "status": turbo.status.value,
                    "alerts": turbo.alerts[:2],
                },
                "oil": {
                    "score": oil.score,
                    "status": oil.status.value,
                    "alerts": oil.alerts[:2],
                },
                "coolant": {
                    "score": coolant.score,
                    "status": coolant.status.value,
                    "alerts": coolant.alerts[:2],
                },
                "avg_score": round((turbo.score + oil.score + coolant.score) / 3, 1),
            }
        except ImportError:
            logger.debug("Component health predictors not available")
        except Exception as e:
            logger.debug(f"Could not get component health: {e}")

        # Get DTC Analysis
        dtc_data = {"status": "ok", "codes": [], "systems": []}
        try:
            from dtc_analyzer import get_dtc_analyzer

            analyzer = get_dtc_analyzer()
            dtc_report = analyzer.get_dtc_analysis_report(truck_id, dtc_string)
            dtc_data = {
                "status": dtc_report["status"],
                "codes_count": dtc_report["summary"]["total"],
                "critical_count": dtc_report["summary"]["critical"],
                "systems_affected": dtc_report.get("systems_affected", []),
                "codes": dtc_report["codes"][:3],  # Top 3 codes
            }
        except ImportError:
            logger.debug("DTC analyzer not available")
        except Exception as e:
            logger.debug(f"Could not get DTC analysis: {e}")

        # Calculate Unified Health Score
        # Weighted: Predictive=30%, Driver=20%, Components=30%, DTC=20%
        dtc_score = (
            100
            if dtc_data["status"] == "ok"
            else (50 if dtc_data["status"] == "warning" else 25)
        )
        predictive_score = 100 - base_risk  # Risk is inverse of health

        unified_score = round(
            predictive_score * 0.30
            + driver_data["score"] * 0.20
            + component_data["avg_score"] * 0.30
            + dtc_score * 0.20,
            1,
        )

        # Determine overall status
        if unified_score >= 80:
            status = "healthy"
            status_emoji = "✅"
        elif unified_score >= 60:
            status = "attention"
            status_emoji = "⚠️"
        elif unified_score >= 40:
            status = "warning"
            status_emoji = "🔶"
        else:
            status = "critical"
            status_emoji = "🔴"

        # Collect ALL critical recommendations
        recommendations = []

        # From DTC
        for code in dtc_data.get("codes", []):
            if code.get("severity") == "critical":
                recommendations.append(
                    {
                        "priority": "critical",
                        "source": "DTC",
                        "action": code.get("action", "Revisar código DTC"),
                    }
                )

        # From Component Health
        for comp_name, comp in [
            ("Turbo", component_data.get("turbo", {})),
            ("Aceite", component_data.get("oil", {})),
            ("Refrigerante", component_data.get("coolant", {})),
        ]:
            for alert in comp.get("alerts", []):
                if "⛔" in alert:
                    recommendations.append(
                        {"priority": "critical", "source": comp_name, "action": alert}
                    )
                elif "⚠️" in alert:
                    recommendations.append(
                        {"priority": "warning", "source": comp_name, "action": alert}
                    )

        # From Driver
        for tip in driver_data.get("tips", []):
            if tip.get("priority") == "high":
                recommendations.append(
                    {
                        "priority": "warning",
                        "source": "Conductor",
                        "action": tip.get("tip", ""),
                    }
                )

        # From Fleet Command Center actions
        for action in truck_actions[:3]:
            if action.priority == "CRITICO":
                recommendations.append(
                    {
                        "priority": "critical",
                        "source": "Predictivo",
                        "action": action.accion,
                    }
                )

        # Sort by priority
        priority_order = {"critical": 0, "warning": 1, "info": 2}
        recommendations.sort(key=lambda x: priority_order.get(x["priority"], 99))

        return {
            "success": True,
            "truck_id": truck_id,
            "unified_health_score": unified_score,
            "status": status,
            "status_emoji": status_emoji,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "breakdown": {
                "predictive_maintenance": {
                    "score": predictive_score,
                    "risk_level": base_risk,
                    "active_issues": len(truck_actions),
                },
                "driver_behavior": driver_data,
                "component_health": component_data,
                "dtc_analysis": dtc_data,
            },
            "recommendations": recommendations[:10],  # Top 10
            "version": "1.7.0",
        }

    except Exception as e:
        logger.error(f"Error getting comprehensive health for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
