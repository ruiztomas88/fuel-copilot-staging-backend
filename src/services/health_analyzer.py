"""
Health Analyzer Service

Extracted from fleet_command_center.py for cleaner architecture.

This service handles:
- Truck risk score calculation (0-100 individual truck health)
- Fleet health score calculation (overall fleet status)
- Top at-risk trucks identification
- Urgency summary aggregation
- Fleet insights generation

v1.0.0 Features:
- Per-truck risk scoring with contributing factors
- Fleet health with systemic issue detection
- Pattern detection for common problems
- Cost impact analysis
- Trend-based escalation warnings
- Structured insights for frontend

Author: Fleet Analytics Team
Created: 2025-12-18
"""

import structlog
from typing import List, Dict, Optional, Any, Tuple, Set
from collections import Counter
from src.models.command_center_models import (
    ActionItem,
    TruckRiskScore,
    FleetHealthScore,
    UrgencySummary,
    Priority,
    IssueCategory,
)

logger = structlog.get_logger()


class HealthAnalyzer:
    """
    Analyzes truck and fleet health based on action items.

    Provides comprehensive health metrics:
    - Individual truck risk scores (0-100)
    - Fleet-wide health scores with distribution analysis
    - Pattern detection for systemic issues
    - Actionable insights for fleet managers

    Example Usage:
        analyzer = HealthAnalyzer()

        # Get truck risk score
        risk = analyzer.calculate_truck_risk_score(
            truck_id="FF7702",
            action_items=all_actions,
            days_since_maintenance=45
        )

        # Get top 10 at-risk trucks
        top_risks = analyzer.get_top_risk_trucks(all_actions, top_n=10)

        # Calculate fleet health
        urgency = analyzer.calculate_urgency_summary(all_actions)
        health = analyzer.calculate_fleet_health_score(urgency, total_trucks=50)
    """

    # Pattern detection thresholds
    PATTERN_THRESHOLDS = {
        "fleet_wide_issue_pct": 0.15,  # 15% of fleet with same issue = pattern
        "min_trucks_for_pattern": 2,  # Minimum trucks to declare pattern
        "anomaly_threshold": 0.7,  # Anomaly score threshold for flagging
    }

    def __init__(
        self,
        pattern_thresholds: Optional[Dict[str, float]] = None,
    ):
        """
        Initialize HealthAnalyzer with optional custom configuration.

        Args:
            pattern_thresholds: Optional custom pattern detection thresholds
        """
        self.pattern_thresholds = pattern_thresholds or self.PATTERN_THRESHOLDS
        logger.debug("HealthAnalyzer initialized")

    def calculate_truck_risk_score(
        self,
        truck_id: str,
        action_items: List[ActionItem],
        days_since_maintenance: Optional[int] = None,
        sensor_alerts: Optional[Dict[str, bool]] = None,
    ) -> TruckRiskScore:
        """
        Calculate comprehensive risk score for a single truck.

        Risk score (0-100) allows identifying top 10 at-risk trucks.

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

        Examples:
            >>> analyzer = HealthAnalyzer()
            >>> risk = analyzer.calculate_truck_risk_score(
            ...     truck_id="FF7702",
            ...     action_items=[critical_item, high_item],
            ...     days_since_maintenance=90
            ... )
            >>> risk.risk_level
            'critical'
            >>> risk.risk_score >= 75
            True
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
        self, action_items: List[ActionItem], top_n: int = 10
    ) -> List[TruckRiskScore]:
        """
        Get the top N at-risk trucks based on risk scores.

        Allows fleet manager to focus on most critical trucks.

        Args:
            action_items: All action items for the fleet
            top_n: Number of top risk trucks to return (default 10)

        Returns:
            List of TruckRiskScore sorted by risk score descending

        Examples:
            >>> analyzer = HealthAnalyzer()
            >>> top_risks = analyzer.get_top_risk_trucks(all_actions, top_n=5)
            >>> len(top_risks) <= 5
            True
            >>> top_risks[0].risk_score >= top_risks[-1].risk_score
            True
        """
        # Get unique truck IDs
        truck_ids = set(i.truck_id for i in action_items if i.truck_id != "FLEET")

        # Calculate risk for each truck
        risk_scores = []
        for truck_id in truck_ids:
            risk = self.calculate_truck_risk_score(truck_id, action_items)
            risk_scores.append(risk)

        # Sort by risk score descending
        risk_scores.sort(key=lambda x: x.risk_score, reverse=True)

        return risk_scores[:top_n]

    def calculate_urgency_summary(
        self, action_items: List[ActionItem]
    ) -> UrgencySummary:
        """
        Calculate urgency summary from action items.

        Aggregates action items by priority level.

        Args:
            action_items: List of all action items

        Returns:
            UrgencySummary with counts by priority

        Examples:
            >>> analyzer = HealthAnalyzer()
            >>> urgency = analyzer.calculate_urgency_summary([
            ...     critical_item, high_item, medium_item
            ... ])
            >>> urgency.critical
            1
            >>> urgency.total_issues
            3
        """
        critical = sum(1 for i in action_items if i.priority == Priority.CRITICAL)
        high = sum(1 for i in action_items if i.priority == Priority.HIGH)
        medium = sum(1 for i in action_items if i.priority == Priority.MEDIUM)
        low = sum(1 for i in action_items if i.priority == Priority.LOW)

        return UrgencySummary(
            critical=critical,
            high=high,
            medium=medium,
            low=low,
        )

    def calculate_fleet_health_score(
        self,
        urgency: UrgencySummary,
        total_trucks: int,
        action_items: Optional[List[ActionItem]] = None,
    ) -> FleetHealthScore:
        """
        Calculate overall fleet health score with distribution analysis.

        Improvements:
        - Distribution penalty for systemic issues
        - Considers percentage of fleet affected
        - Multi-truck critical penalty
        - Descriptive status messages with context

        Args:
            urgency: UrgencySummary with issue counts by priority
            total_trucks: Total fleet size
            action_items: Optional list of actions for distribution analysis

        Returns:
            FleetHealthScore with score, status, trend, and description

        Examples:
            >>> analyzer = HealthAnalyzer()
            >>> urgency = UrgencySummary(critical=0, high=1, medium=2, low=3)
            >>> health = analyzer.calculate_fleet_health_score(urgency, 50)
            >>> 0 <= health.score <= 100
            True
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

        # 1. Calculate weighted severity per truck
        severity_per_truck = (
            urgency.critical * 15  # Critical issues are severe
            + urgency.high * 8
            + urgency.medium * 3
            + urgency.low * 1
        ) / max(
            1, total_trucks
        )  # Prevent division by zero

        # Deduct points based on severity per truck
        score -= severity_per_truck * 3

        # 2. Distribution penalty - systemic issues are worse
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
                systemic_penalty = (affected_percentage - 20) * 0.4
                score -= systemic_penalty
                logger.info(
                    "Systemic issue detected",
                    affected_pct=round(affected_percentage, 1),
                    penalty=round(systemic_penalty, 1),
                )

            # 3. Multiple critical trucks penalty
            critical_trucks = [
                truck_id
                for truck_id, items in truck_issues.items()
                if any(i.priority == Priority.CRITICAL for i in items)
            ]

            if len(critical_trucks) > 1:
                multi_critical_penalty = min(20, len(critical_trucks) * 4)
                score -= multi_critical_penalty
                logger.info(
                    "Multiple critical trucks",
                    count=len(critical_trucks),
                    penalty=multi_critical_penalty,
                )

        # Clamp to 0-100
        score = max(0, min(100, score))
        score = int(round(score))

        # Determine status with context
        if score >= 90:
            status = "Excelente"
            description = (
                "La flota está en excelentes condiciones. "
                "Mantener programa de mantenimiento preventivo."
            )
        elif score >= 75:
            status = "Bueno"
            priority_count = urgency.critical + urgency.high
            description = (
                f"La flota está en buenas condiciones con algunos puntos de atención. "
                f"{priority_count} items prioritarios pendientes."
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

    def generate_insights(
        self,
        action_items: List[ActionItem],
        urgency: UrgencySummary,
        fleet_size: Optional[int] = None,
    ) -> List[Dict[str, str]]:
        """
        Generate AI-style insights for the fleet manager.

        Improvements:
        - Pattern detection with percentage thresholds
        - Trend detection (multiple trucks same issue)
        - Severity escalation warnings
        - Cost impact analysis potential
        - Component-specific warnings

        Returns structured dict format for frontend compatibility:
        {type, title, message, icon}

        Args:
            action_items: List of all action items
            urgency: UrgencySummary counts
            fleet_size: Optional fleet size for pattern detection

        Returns:
            List of structured insight objects

        Examples:
            >>> analyzer = HealthAnalyzer()
            >>> insights = analyzer.generate_insights(actions, urgency)
            >>> all('type' in i and 'title' in i for i in insights)
            True
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
                    {
                        "type": "warning",
                        "title": "Atención Inmediata Requerida",
                        "message": f"{list(trucks)[0]} requiere atención inmediata - revisar antes de operar",
                        "icon": "🚨",
                    }
                )
            else:
                insights.append(
                    {
                        "type": "warning",
                        "title": "Múltiples Camiones Críticos",
                        "message": f"{len(trucks)} camiones requieren atención inmediata",
                        "icon": "🚨",
                    }
                )

        # Component patterns - use % of fleet instead of fixed count
        components = [
            item.component
            for item in action_items
            if item.priority in [Priority.CRITICAL, Priority.HIGH]
        ]
        if components:
            common = Counter(components).most_common(2)

            # Calculate threshold based on fleet size
            if fleet_size is None:
                fleet_size = len(set(item.truck_id for item in action_items)) or 1

            pattern_threshold = max(
                self.pattern_thresholds["min_trucks_for_pattern"],
                int(fleet_size * self.pattern_thresholds["fleet_wide_issue_pct"]),
            )

            if common[0][1] >= pattern_threshold:
                pct = (common[0][1] / fleet_size) * 100 if fleet_size > 0 else 0
                insights.append(
                    {
                        "type": "trend",
                        "title": "Patrón Detectado en la Flota",
                        "message": f"{common[0][1]} camiones ({pct:.0f}% de flota) tienen problemas con {common[0][0]}",
                        "icon": "📊",
                    }
                )

        # Trend detection - issues about to escalate
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
                {
                    "type": "warning",
                    "title": "Problemas Escalando",
                    "message": f"{len(trucks_escalating)} camión(es) con problemas que escalarán a crítico en ≤3 días",
                    "icon": "⏰",
                }
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
                {
                    "type": "warning",
                    "title": "Problemas de Transmisión",
                    "message": f"{len(trans_issues)} problema(s) de transmisión detectado(s) - reparación costosa si no se atiende",
                    "icon": "⚠️",
                }
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
                {
                    "type": "warning",
                    "title": "DEF Bajo",
                    "message": f"{len(def_issues)} camión(es) con DEF bajo - derate inminente si no se llena",
                    "icon": "💎",
                }
            )

        # Positive insight if fleet is healthy
        if urgency.critical == 0 and urgency.high == 0:
            insights.append(
                {
                    "type": "success",
                    "title": "Flota Saludable",
                    "message": "No hay problemas críticos o de alta prioridad - la flota está operando bien",
                    "icon": "✅",
                }
            )

        return insights

    def analyze_fleet_distribution(
        self, action_items: List[ActionItem]
    ) -> Dict[str, Any]:
        """
        Analyze how issues are distributed across the fleet.

        Provides insights on:
        - How many trucks have issues
        - What percentage of fleet is affected
        - Most common issues across fleet
        - Trucks with multiple issues

        Args:
            action_items: All action items

        Returns:
            Dict with distribution statistics

        Examples:
            >>> analyzer = HealthAnalyzer()
            >>> dist = analyzer.analyze_fleet_distribution(actions)
            >>> 'trucks_with_issues' in dist
            True
            >>> 'common_components' in dist
            True
        """
        # Build truck to issues map
        truck_issues: Dict[str, List[ActionItem]] = {}
        for item in action_items:
            if item.truck_id != "FLEET":
                if item.truck_id not in truck_issues:
                    truck_issues[item.truck_id] = []
                truck_issues[item.truck_id].append(item)

        # Find trucks with multiple issues
        trucks_multi_issues = [
            truck_id for truck_id, items in truck_issues.items() if len(items) > 2
        ]

        # Count components
        components = [
            item.component for item in action_items if item.truck_id != "FLEET"
        ]
        common_components = Counter(components).most_common(5)

        # Priority distribution
        priority_dist = {
            "critical": sum(1 for i in action_items if i.priority == Priority.CRITICAL),
            "high": sum(1 for i in action_items if i.priority == Priority.HIGH),
            "medium": sum(1 for i in action_items if i.priority == Priority.MEDIUM),
            "low": sum(1 for i in action_items if i.priority == Priority.LOW),
        }

        return {
            "trucks_with_issues": len(truck_issues),
            "trucks_multiple_issues": len(trucks_multi_issues),
            "common_components": common_components,
            "priority_distribution": priority_dist,
            "total_issues": len(action_items),
        }
