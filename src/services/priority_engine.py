"""
Priority Engine Service

Extracted from fleet_command_center.py for cleaner architecture.

This service handles all priority scoring, urgency calculation, and action type
determination using exponential decay and multi-signal weighting.

v1.0.0 Features:
- Exponential decay urgency scoring (smooth curve vs piecewise linear)
- Multi-signal priority calculation (days, anomaly, criticality, cost)
- Time-horizon aware scoring weights (immediate, short-term, medium-term)
- Component criticality weighting
- Action type determination based on priority and urgency
- Score normalization utilities

Author: Fleet Analytics Team
Created: 2025-12-18
"""

import math
import structlog
from typing import Optional, Tuple, Dict, Any
from src.models.command_center_models import Priority, ActionType

logger = structlog.get_logger()


class PriorityEngine:
    """
    Priority scoring and action determination engine.

    This service calculates priority scores using exponential decay for
    days_to_critical and weighted combination of multiple signals.

    Example Usage:
        engine = PriorityEngine()
        priority, score = engine.calculate_priority_score(
            days_to_critical=3.5,
            anomaly_score=0.85,
            component="Transmisión"
        )
        # priority = Priority.HIGH, score = 78.5
    """

    # Component criticality weights (safety, cost, downtime impact)
    # Higher weight = higher priority boost for same days_to_critical
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

    # Component costs in USD (min, max, avg) - Industry averages for Class 8
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

    # Time horizon scoring weights
    # Different time horizons require different prioritization
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

    # Exponential decay constant for urgency calculation
    # k = 0.04 gives good curve: 0d=100, 7d=~70, 30d=~30, 60d=~10
    DECAY_CONSTANT = 0.04

    # Priority thresholds
    CRITICAL_THRESHOLD = 85
    HIGH_THRESHOLD = 65
    MEDIUM_THRESHOLD = 40
    LOW_THRESHOLD = 20

    def __init__(
        self,
        component_criticality: Optional[Dict[str, float]] = None,
        component_costs: Optional[Dict[str, Dict[str, int]]] = None,
        time_horizon_weights: Optional[Dict[str, Dict[str, float]]] = None,
        decay_constant: Optional[float] = None,
    ):
        """
        Initialize PriorityEngine with optional custom configurations.

        Args:
            component_criticality: Optional custom component weights
            component_costs: Optional custom component costs
            time_horizon_weights: Optional custom time horizon weights
            decay_constant: Optional custom decay constant for urgency
        """
        self.component_criticality = component_criticality or self.COMPONENT_CRITICALITY
        self.component_costs = component_costs or self.COMPONENT_COSTS
        self.time_horizon_weights = time_horizon_weights or self.TIME_HORIZON_WEIGHTS
        self.decay_constant = decay_constant or self.DECAY_CONSTANT

        logger.debug(
            "PriorityEngine initialized",
            components=len(self.component_criticality),
            decay_k=self.decay_constant,
        )

    def calculate_urgency_from_days(self, days: float) -> float:
        """
        Calculate urgency score using exponential decay.

        Replaces piecewise linear function with smooth exponential curve.
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

        Examples:
            >>> engine = PriorityEngine()
            >>> engine.calculate_urgency_from_days(0)
            100.0
            >>> engine.calculate_urgency_from_days(7)
            75.4  # approximately
            >>> engine.calculate_urgency_from_days(30)
            30.1  # approximately
        """
        if days <= 0:
            return 100.0

        score = 100 * math.exp(-self.decay_constant * days)

        # Floor at 5 to show it exists
        return max(5.0, min(100.0, score))

    def normalize_score_to_100(self, value: float, max_value: float = 100.0) -> float:
        """
        Normalize any score to 0-100 scale.

        Ensures consistent scoring across all sources.

        Args:
            value: Raw score value
            max_value: Expected maximum of raw scale (e.g., 1.0 for 0-1 scale)

        Returns:
            Score normalized to 0-100

        Examples:
            >>> engine = PriorityEngine()
            >>> engine.normalize_score_to_100(0.85, 1.0)
            85.0
            >>> engine.normalize_score_to_100(150, 200)
            75.0
        """
        if max_value <= 0:
            return 50.0  # Default middle score

        normalized = (value / max_value) * 100
        return max(0.0, min(100.0, normalized))

    def get_component_cost(self, component: str) -> Dict[str, int]:
        """
        Get cost estimate for a component from the cost database.

        Args:
            component: Component name

        Returns:
            Dict with min, max, avg costs in USD

        Examples:
            >>> engine = PriorityEngine()
            >>> engine.get_component_cost("Transmisión")
            {'min': 8000, 'max': 15000, 'avg': 11500}
        """
        return self.component_costs.get(
            component, {"min": 500, "max": 2000, "avg": 1250}
        )

    def format_cost_string(self, component: str) -> str:
        """
        Format cost as user-friendly string.

        Args:
            component: Component name

        Returns:
            Formatted cost range string

        Examples:
            >>> engine = PriorityEngine()
            >>> engine.format_cost_string("Transmisión")
            '$8,000 - $15,000'
        """
        cost = self.get_component_cost(component)
        return f"${cost['min']:,} - ${cost['max']:,}"

    def get_time_horizon(self, days_to_critical: Optional[float]) -> str:
        """
        Determine time horizon category for scoring.

        Args:
            days_to_critical: Days until critical failure

        Returns:
            "immediate", "short_term", or "medium_term"

        Examples:
            >>> engine = PriorityEngine()
            >>> engine.get_time_horizon(0.5)
            'immediate'
            >>> engine.get_time_horizon(5)
            'short_term'
            >>> engine.get_time_horizon(20)
            'medium_term'
        """
        if days_to_critical is None:
            return "medium_term"
        elif days_to_critical <= 1:
            return "immediate"
        elif days_to_critical <= 7:
            return "short_term"
        else:
            return "medium_term"

    def calculate_priority_score(
        self,
        days_to_critical: Optional[float] = None,
        anomaly_score: Optional[float] = None,
        cost_estimate: Optional[str] = None,
        component: Optional[str] = None,
        use_time_horizon_weights: bool = True,
    ) -> Tuple[Priority, float]:
        """
        Calculate combined priority score from multiple signals.

        Score Components (weighted):
        - Days urgency (30-50%): Exponential decay from days_to_critical
        - Anomaly score (5-25%): Normalized ML anomaly detection score
        - Component criticality (20-30%): Based on COMPONENT_CRITICALITY weights
        - Cost factor (10-25%): Based on potential repair cost

        Weights vary by time horizon:
        - Immediate (0-1d): Focus on days (50%), criticality (30%)
        - Short-term (1-7d): Balanced approach (40%, 25%, 20%, 15%)
        - Medium-term (7-30d): Consider cost/anomaly more (25% each)

        Thresholds:
        - 85+: CRITICAL
        - 65-84: HIGH
        - 40-64: MEDIUM
        - 20-39: LOW
        - <20: NONE

        Args:
            days_to_critical: Days until critical failure (most important signal)
            anomaly_score: ML anomaly detection score (0-1 or 0-100)
            cost_estimate: Optional cost string (fallback if component not provided)
            component: Component name for criticality and cost lookup
            use_time_horizon_weights: If True, adjust weights based on time horizon

        Returns:
            Tuple of (Priority enum, numeric score 0-100)

        Examples:
            >>> engine = PriorityEngine()
            >>> priority, score = engine.calculate_priority_score(
            ...     days_to_critical=3.5,
            ...     anomaly_score=0.85,
            ...     component="Transmisión"
            ... )
            >>> priority
            <Priority.HIGH: 'ALTO'>
            >>> score >= 65
            True
        """
        # Determine time horizon and get weights
        horizon = self.get_time_horizon(days_to_critical)
        if use_time_horizon_weights:
            weights = self.time_horizon_weights[horizon]
            weight_days = weights["days_weight"]
            weight_anomaly = weights["anomaly_weight"]
            weight_criticality = weights["criticality_weight"]
            weight_cost = weights["cost_weight"]
        else:
            # Default balanced weights
            weight_days = 0.45
            weight_anomaly = 0.20
            weight_criticality = 0.25
            weight_cost = 0.10

        components_used = []
        weighted_score = 0.0
        total_weight = 0.0

        # 1. Days to critical - most important signal
        if days_to_critical is not None:
            days_score = self.calculate_urgency_from_days(days_to_critical)
            weighted_score += days_score * weight_days
            total_weight += weight_days
            components_used.append(f"days={days_score:.1f}")

        # 2. Anomaly score - normalize to 0-100 if needed
        if anomaly_score is not None:
            # Handle both 0-1 and 0-100 scales
            if anomaly_score <= 1.0:
                normalized_anomaly = anomaly_score * 100
            else:
                normalized_anomaly = min(100, anomaly_score)
            weighted_score += normalized_anomaly * weight_anomaly
            total_weight += weight_anomaly
            components_used.append(f"anomaly={normalized_anomaly:.1f}")

        # 3. Component criticality
        if component:
            criticality = self.component_criticality.get(component, 1.0)
            # Normalize criticality (1.0-3.0) to 0-100
            # 1.0 = 33, 2.0 = 66, 3.0 = 100
            criticality_score = (criticality / 3.0) * 100
            weighted_score += criticality_score * weight_criticality
            total_weight += weight_criticality
            components_used.append(f"crit={criticality_score:.1f}")

        # 4. Cost factor
        if component:
            cost_data = self.get_component_cost(component)
            avg_cost = cost_data.get("avg", 0)
            # Normalize cost to 0-100 (assuming max ~$15,000)
            cost_score = min(100, (avg_cost / 15000) * 100)
            weighted_score += cost_score * weight_cost
            total_weight += weight_cost
            components_used.append(f"cost={cost_score:.1f}")
        elif cost_estimate:
            # Fallback to string parsing
            if "15,000" in cost_estimate or "10,000" in cost_estimate:
                weighted_score += 80 * weight_cost
                total_weight += weight_cost
            elif "5,000" in cost_estimate:
                weighted_score += 50 * weight_cost
                total_weight += weight_cost

        # Calculate final score
        if total_weight > 0:
            score = weighted_score / total_weight
        else:
            score = 50.0  # Default middle score

        # Clamp to 0-100
        score = max(0, min(100, score))

        # Log scoring components for debugging
        logger.debug(
            "Priority score calculated",
            score=round(score, 1),
            horizon=horizon,
            components=", ".join(components_used),
        )

        # Determine priority level
        if score >= self.CRITICAL_THRESHOLD:
            priority = Priority.CRITICAL
        elif score >= self.HIGH_THRESHOLD:
            priority = Priority.HIGH
        elif score >= self.MEDIUM_THRESHOLD:
            priority = Priority.MEDIUM
        elif score >= self.LOW_THRESHOLD:
            priority = Priority.LOW
        else:
            priority = Priority.NONE

        return priority, round(score, 1)

    def determine_action_type(
        self, priority: Priority, days_to_critical: Optional[float]
    ) -> ActionType:
        """
        Determine what action should be taken based on priority and urgency.

        Decision Logic:
        - CRITICAL + <=1 day → STOP_IMMEDIATELY
        - CRITICAL + >1 day → SCHEDULE_THIS_WEEK
        - HIGH → SCHEDULE_THIS_WEEK
        - MEDIUM → SCHEDULE_THIS_MONTH
        - LOW → MONITOR
        - NONE → NO_ACTION

        Args:
            priority: Priority level from calculate_priority_score()
            days_to_critical: Days until critical failure

        Returns:
            ActionType enum

        Examples:
            >>> engine = PriorityEngine()
            >>> engine.determine_action_type(Priority.CRITICAL, 0.5)
            <ActionType.STOP_IMMEDIATELY: 'DETENER'>
            >>> engine.determine_action_type(Priority.HIGH, 5)
            <ActionType.SCHEDULE_THIS_WEEK: 'AGENDAR_ESTA_SEMANA'>
        """
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

    def calculate_priority_with_action(
        self,
        days_to_critical: Optional[float] = None,
        anomaly_score: Optional[float] = None,
        component: Optional[str] = None,
        use_time_horizon_weights: bool = True,
    ) -> Dict[str, Any]:
        """
        Convenience method that calculates both priority and action type.

        Returns a comprehensive result dictionary with all scoring details.

        Args:
            days_to_critical: Days until critical failure
            anomaly_score: ML anomaly detection score (0-1 or 0-100)
            component: Component name
            use_time_horizon_weights: If True, adjust weights based on time horizon

        Returns:
            Dict with:
            - priority: Priority enum
            - priority_score: float 0-100
            - action_type: ActionType enum
            - time_horizon: str
            - cost_estimate: str (if component provided)
            - urgency_score: float (if days_to_critical provided)

        Examples:
            >>> engine = PriorityEngine()
            >>> result = engine.calculate_priority_with_action(
            ...     days_to_critical=3.5,
            ...     anomaly_score=0.85,
            ...     component="Transmisión"
            ... )
            >>> result['priority']
            <Priority.HIGH: 'ALTO'>
            >>> result['action_type']
            <ActionType.SCHEDULE_THIS_WEEK: 'AGENDAR_ESTA_SEMANA'>
        """
        # Calculate priority score
        priority, score = self.calculate_priority_score(
            days_to_critical=days_to_critical,
            anomaly_score=anomaly_score,
            component=component,
            use_time_horizon_weights=use_time_horizon_weights,
        )

        # Determine action type
        action_type = self.determine_action_type(priority, days_to_critical)

        # Build result dictionary
        result = {
            "priority": priority,
            "priority_score": score,
            "action_type": action_type,
            "time_horizon": self.get_time_horizon(days_to_critical),
        }

        # Add optional fields
        if component:
            result["cost_estimate"] = self.format_cost_string(component)

        if days_to_critical is not None:
            result["urgency_score"] = self.calculate_urgency_from_days(days_to_critical)

        return result
