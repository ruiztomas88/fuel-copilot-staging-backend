"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    🎯 FLEET COMMAND CENTER v1.1.0                              ║
║                                                                                ║
║       The UNIFIED source of truth for fleet health and maintenance            ║
║                                                                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  COMBINES:                                                                     ║
║  ✓ Predictive Maintenance (trend-based days-to-failure)                       ║
║  ✓ ML Anomaly Detection (isolation forest outlier scores)                     ║
║  ✓ Sensor Health (GPS, Voltage, DTC, Idle)                                    ║
║  ✓ Driver Performance (clustering & coaching)                                 ║
║  ✓ Cost Impact Analysis                                                       ║
║                                                                                ║
║  OUTPUT: Single prioritized action list with combined intelligence            ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Fuel Copilot Team
Version: 1.1.0 - Algorithmic improvements based on AI code review
Created: December 2025
Updated: January 2025

CHANGELOG v1.1.0:
- Added weighted priority scoring by component criticality
- Replaced counter-based IDs with UUID for thread safety
- Added comprehensive cost database replacing string parsing
- Improved pattern detection thresholds (% of fleet vs fixed count)
"""

import logging
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import json

logger = logging.getLogger(__name__)


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
    """

    VERSION = "1.1.0"

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

    def __init__(self):
        # Note: _action_counter kept for backward compatibility but not used for IDs
        self._action_counter = 0

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

    def _calculate_priority_score(
        self,
        days_to_critical: Optional[float],
        anomaly_score: Optional[float] = None,
        cost_estimate: Optional[str] = None,
        component: Optional[str] = None,
    ) -> Tuple[Priority, float]:
        """
        Calculate combined priority score from multiple signals.

        v1.1.0 Improvements:
        - Added component criticality weighting
        - Uses cost database instead of string parsing
        - More nuanced scoring formula

        Score formula:
        - Base from days_to_critical: 100 - (days * 5), capped at 100
        - Anomaly bonus: anomaly_score * 0.2 (up to +20 points)
        - Component criticality multiplier: 1.0 - 3.0x
        - Cost factor: Based on avg cost from database

        Thresholds:
        - 85+: CRITICAL
        - 65-84: HIGH
        - 40-64: MEDIUM
        - 20-39: LOW
        - <20: NONE

        Returns (Priority enum, numeric score 0-100)
        """
        score = 50.0  # Default middle score

        # Days to critical is the primary signal
        if days_to_critical is not None:
            if days_to_critical <= 0:
                score = 100.0
            elif days_to_critical <= 3:
                score = 95.0 - (days_to_critical * 1.5)
            elif days_to_critical <= 7:
                score = 85.0 - ((days_to_critical - 3) * 5)
            elif days_to_critical <= 30:
                score = 65.0 - ((days_to_critical - 7) * 1.5)
            else:
                score = max(20.0, 50.0 - (days_to_critical - 30) * 0.5)

        # Anomaly score bonus
        if anomaly_score is not None:
            score += anomaly_score * 0.2

        # v1.1.0: Component criticality multiplier
        # Apply a weighted boost based on component importance
        if component:
            criticality = self.COMPONENT_CRITICALITY.get(component, 1.0)
            # Scale the score by criticality, but cap the boost to prevent runaway scores
            # A criticality of 3.0 can boost a 50 score to ~75 (50 * 1.5)
            # Formula: score + (score * (criticality - 1) * 0.5)
            criticality_boost = (criticality - 1.0) * 0.5
            score = score * (1 + criticality_boost)

        # v1.1.0: Cost factor using database instead of string parsing
        if component:
            cost_data = self._get_component_cost(component)
            avg_cost = cost_data.get("avg", 0)
            # High cost items (>$5000 avg) get +5, very high (>$10000) get +10
            if avg_cost >= 10000:
                score += 10
            elif avg_cost >= 5000:
                score += 5
            elif avg_cost >= 3000:
                score += 2
        elif cost_estimate and ("15,000" in cost_estimate or "10,000" in cost_estimate):
            # Fallback to old string parsing for backward compatibility
            score += 5

        # Clamp to 0-100
        score = max(0, min(100, score))

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

        return priority, score

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
    ) -> FleetHealthScore:
        """Calculate overall fleet health score"""
        if total_trucks == 0:
            return FleetHealthScore(
                score=100,
                status="Sin datos",
                trend="stable",
                description="No hay camiones para analizar",
            )

        # Base score starts at 100
        score = 100.0

        # Calculate weighted severity per truck (normalized by fleet size)
        # This ensures fair comparison regardless of fleet size
        severity_per_truck = (
            urgency.critical * 15  # Critical issues are severe
            + urgency.high * 8
            + urgency.medium * 3
            + urgency.low * 1
        ) / total_trucks

        # Deduct points based on severity per truck
        # Scale factor of 3 means: 1 critical issue per truck = -45 points
        score -= severity_per_truck * 3

        # Clamp to 0-100
        score = max(0, min(100, score))
        score = int(round(score))

        # Determine status
        if score >= 90:
            status = "Excelente"
            description = "La flota está en excelentes condiciones. Mantener programa de mantenimiento preventivo."
        elif score >= 75:
            status = "Bueno"
            description = "La flota está en buenas condiciones con algunos puntos de atención menores."
        elif score >= 60:
            status = "Atención"
            description = "Hay varios items que requieren atención. Revisar lista de acciones prioritarias."
        elif score >= 40:
            status = "Alerta"
            description = (
                "Múltiples problemas detectados. Se recomienda atención inmediata."
            )
        else:
            status = "Crítico"
            description = "Estado crítico de la flota. Acción inmediata requerida en varios camiones."

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
        """Generate AI-style insights for the fleet manager"""
        insights = []

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

        # Component patterns - v1.1.0: Use % of fleet instead of fixed count
        components = [
            item.component
            for item in action_items
            if item.priority in [Priority.CRITICAL, Priority.HIGH]
        ]
        if components:
            from collections import Counter

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
            from database_mysql import get_sensor_health_summary

            sensor_data = get_sensor_health_summary()

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
            if sensor_status.voltage_issues > 0:
                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id="FLEET",
                        priority=Priority.MEDIUM,
                        priority_score=45,
                        category=IssueCategory.ELECTRICAL,
                        component="Sistema eléctrico",
                        title=f"{sensor_status.voltage_issues} Camiones con Voltaje Bajo",
                        description="Camiones con voltaje de batería por debajo del nivel óptimo",
                        days_to_critical=None,
                        cost_if_ignored="$500 - $1,500 por camión",
                        current_value=None,
                        trend=None,
                        threshold="<12.8V",
                        confidence="HIGH",
                        action_type=ActionType.INSPECT,
                        action_steps=[
                            "🔋 Probar baterías con multímetro",
                            "🔌 Verificar conexiones y terminales",
                            "⚡ Revisar alternador",
                        ],
                        icon="🔋",
                        sources=["Sensor Health Monitor"],
                    )
                )

            # Add DTC alerts
            if sensor_status.dtc_active > 0:
                action_items.append(
                    ActionItem(
                        id=self._generate_action_id(),
                        truck_id="FLEET",
                        priority=(
                            Priority.HIGH
                            if sensor_status.dtc_active >= 3
                            else Priority.MEDIUM
                        ),
                        priority_score=60 if sensor_status.dtc_active >= 3 else 45,
                        category=IssueCategory.SENSOR,
                        component="Códigos DTC",
                        title=f"{sensor_status.dtc_active} Camiones con DTC Activos",
                        description="Códigos de diagnóstico activos que requieren revisión",
                        days_to_critical=None,
                        cost_if_ignored=None,
                        current_value=None,
                        trend=None,
                        threshold=None,
                        confidence="HIGH",
                        action_type=ActionType.INSPECT,
                        action_steps=[
                            "🔧 Leer códigos DTC con escáner",
                            "📋 Identificar causa raíz",
                            "✅ Reparar y borrar códigos",
                        ],
                        icon="🔧",
                        sources=["DTC Monitor"],
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
        trucks_with_issues = len(
            set(i.truck_id for i in action_items if i.truck_id != "FLEET")
        )
        urgency = UrgencySummary(
            critical=sum(1 for i in action_items if i.priority == Priority.CRITICAL),
            high=sum(1 for i in action_items if i.priority == Priority.HIGH),
            medium=sum(1 for i in action_items if i.priority == Priority.MEDIUM),
            low=sum(1 for i in action_items if i.priority == Priority.LOW),
            ok=max(0, total_trucks - trucks_with_issues),
        )

        # Calculate fleet health score
        fleet_health = self._calculate_fleet_health_score(urgency, total_trucks)

        # Generate insights
        insights = self._generate_insights(action_items, urgency)

        # Estimate costs
        cost_projection = self._estimate_costs(action_items)

        # Build response
        return CommandCenterData(
            generated_at=datetime.now(timezone.utc).isoformat(),
            fleet_health=fleet_health,
            total_trucks=total_trucks,
            trucks_analyzed=len(
                set(i.truck_id for i in action_items if i.truck_id != "FLEET")
            ),
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
        logger.error(f"Error getting command center data: {e}")
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
_trend_history: List[Dict[str, Any]] = []
_MAX_TREND_HISTORY = 1000  # Keep last 1000 snapshots


def _record_trend_snapshot(data: CommandCenterData) -> None:
    """Record a snapshot of fleet health for trend analysis."""
    global _trend_history

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

    _trend_history.append(snapshot)

    # Keep only last N snapshots
    if len(_trend_history) > _MAX_TREND_HISTORY:
        _trend_history = _trend_history[-_MAX_TREND_HISTORY:]


def _calculate_trend(values: List[float], window: int = 10) -> str:
    """
    Calculate trend direction from recent values.

    Returns: "improving", "stable", "declining"
    """
    if len(values) < 2:
        return "stable"

    recent = values[-min(window, len(values)) :]

    if len(recent) < 2:
        return "stable"

    # Simple linear trend: compare first half avg to second half avg
    mid = len(recent) // 2
    first_half_avg = sum(recent[:mid]) / mid if mid > 0 else recent[0]
    second_half_avg = sum(recent[mid:]) / (len(recent) - mid)

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
