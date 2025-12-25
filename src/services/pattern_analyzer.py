"""
Pattern Analyzer Service - Failure Correlation Detection

Detects correlated failures across trucks to identify systemic issues.

This service analyzes action items to find patterns where multiple sensors
fail together, indicating underlying root causes (e.g., coolant↑ + oil_temp↑
= cooling system failure).

Extracted from fleet_command_center.py v1.5.0 FASE 5.1

Usage:
    analyzer = PatternAnalyzer()
    correlations = analyzer.detect_failure_correlations(action_items)

    # Custom patterns
    custom = PatternAnalyzer(custom_patterns={
        "custom_pattern": {
            "primary": "sensor_name",
            "correlated": ["sensor2", "sensor3"],
            "min_correlation": 0.7,
            "cause": "Root cause description",
            "action": "Recommended action"
        }
    })
"""

import uuid
from typing import List, Dict, Optional
from dataclasses import dataclass
import structlog

from src.models.command_center_models import ActionItem, FailureCorrelation


logger = structlog.get_logger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DEFAULT CORRELATION PATTERNS
# ═══════════════════════════════════════════════════════════════════════════════

DEFAULT_FAILURE_PATTERNS = {
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
# PATTERN ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════


class PatternAnalyzer:
    """
    Analyzes action items to detect correlated failures indicating systemic issues.

    Attributes:
        failure_patterns: Dict of pattern_id → pattern config

    Example:
        >>> analyzer = PatternAnalyzer()
        >>> items = [
        ...     ActionItem(truck_id="TR1", component="cool_temp", priority=Priority.CRITICAL),
        ...     ActionItem(truck_id="TR1", component="oil_temp", priority=Priority.HIGH),
        ...     ActionItem(truck_id="TR1", component="trams_t", priority=Priority.MEDIUM),
        ... ]
        >>> correlations = analyzer.detect_failure_correlations(items)
        >>> # Returns [FailureCorrelation for overheating_syndrome]
    """

    def __init__(self, custom_patterns: Optional[Dict] = None):
        """
        Initialize PatternAnalyzer with correlation patterns.

        Args:
            custom_patterns: Optional dict to override or extend default patterns.
                            Keys: pattern_id (str)
                            Values: dict with primary, correlated, min_correlation, cause, action
        """
        self.failure_patterns = DEFAULT_FAILURE_PATTERNS.copy()
        if custom_patterns:
            self.failure_patterns.update(custom_patterns)

    def detect_failure_correlations(
        self,
        action_items: List[ActionItem],
        sensor_data: Optional[Dict[str, Dict[str, float]]] = None,
    ) -> List[FailureCorrelation]:
        """
        Detect correlated failures across trucks.

        Analyzes action items to find patterns where primary sensor issues
        are accompanied by correlated sensor issues, indicating root causes.

        Args:
            action_items: List of ActionItem to analyze
            sensor_data: Optional dict of truck_id → {sensor_name: value}
                        Used for additional context (not required for detection)

        Returns:
            List of FailureCorrelation objects, one per detected pattern

        Example:
            >>> items = [
            ...     ActionItem(truck_id="FF7702", component="voltage", ...),
            ...     ActionItem(truck_id="FF7702", component="engine_load", ...),
            ...     ActionItem(truck_id="GS5030", component="voltage", ...),
            ... ]
            >>> correlations = analyzer.detect_failure_correlations(items)
            >>> len(correlations)  # May detect electrical_failure pattern
            1
        """
        correlations = []

        # Group action items by truck
        truck_issues = self._group_issues_by_truck(action_items)

        if not truck_issues:
            logger.debug("No action items to analyze")
            return correlations

        # Check each correlation pattern
        for pattern_id, pattern in self.failure_patterns.items():
            correlation = self._check_pattern(
                pattern_id, pattern, truck_issues, sensor_data
            )
            if correlation:
                correlations.append(correlation)
                logger.info(
                    "Detected failure correlation",
                    pattern=pattern_id,
                    affected_trucks=len(correlation.affected_trucks),
                    strength=correlation.correlation_strength,
                )

        return correlations

    def _group_issues_by_truck(
        self, action_items: List[ActionItem]
    ) -> Dict[str, List[str]]:
        """
        Group action items by truck_id.

        Returns dict: truck_id → list of normalized component names
        """
        truck_issues: Dict[str, List[str]] = {}
        for item in action_items:
            if item.truck_id not in truck_issues:
                truck_issues[item.truck_id] = []
            # Normalize component for matching
            norm_comp = self._normalize_component(item.component)
            truck_issues[item.truck_id].append(norm_comp)
        return truck_issues

    def _check_pattern(
        self,
        pattern_id: str,
        pattern: Dict,
        truck_issues: Dict[str, List[str]],
        sensor_data: Optional[Dict[str, Dict[str, float]]],
    ) -> Optional[FailureCorrelation]:
        """
        Check if a specific pattern exists in the truck issues.

        Returns FailureCorrelation if pattern detected, None otherwise.
        """
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
                1 for sensor in correlated if any(sensor in issue for issue in issues)
            )

            # Calculate correlation strength (% of correlated sensors present)
            if correlated_count > 0:
                strength = correlated_count / len(correlated)
                if strength >= min_correlation:
                    affected_trucks.append(truck_id)

        # If we have affected trucks, create a correlation finding
        if affected_trucks:
            # Calculate fleet-wide correlation strength
            fleet_strength = (
                len(affected_trucks) / len(truck_issues) if truck_issues else 0.0
            )

            return FailureCorrelation(
                correlation_id=f"CORR-{pattern_id.upper()}-{uuid.uuid4().hex[:6]}",
                primary_sensor=primary,
                correlated_sensors=correlated,
                correlation_strength=fleet_strength,
                probable_cause=pattern["cause"],
                recommended_action=pattern["action"],
                affected_trucks=affected_trucks,
            )

        return None

    def _normalize_component(self, component: str) -> str:
        """
        Normalize component name for pattern matching.

        Converts to lowercase and handles common variations.

        Args:
            component: Component name from ActionItem

        Returns:
            Normalized component name

        Example:
            >>> analyzer._normalize_component("COOL_TEMP")
            'cool_temp'
            >>> analyzer._normalize_component("Engine Coolant Temperature")
            'cool_temp'
        """
        # Convert to lowercase
        norm = component.lower()

        # Handle common variations
        mappings = {
            "coolant": "cool_temp",
            "coolant_temp": "cool_temp",
            "engine_coolant": "cool_temp",
            "oil": "oil_temp",
            "transmission": "trams_t",
            "transmission_temp": "trams_t",
            "intake": "intk_t",
            "intake_temp": "intk_t",
            "battery": "voltage",
            "battery_voltage": "voltage",
            "fuel": "fuel_rate",
            "mpg": "mpg",
            "engine": "engine_load",
            "rpm": "rpm",
        }

        # Check for exact match first
        for key, value in mappings.items():
            if key in norm:
                return value

        # Return normalized original if no mapping found
        return norm

    def add_pattern(
        self,
        pattern_id: str,
        primary: str,
        correlated: List[str],
        min_correlation: float,
        cause: str,
        action: str,
    ) -> None:
        """
        Add or update a correlation pattern.

        Args:
            pattern_id: Unique pattern identifier
            primary: Primary sensor that triggers the pattern
            correlated: List of correlated sensors
            min_correlation: Minimum correlation strength (0.0-1.0)
            cause: Probable cause description
            action: Recommended action

        Example:
            >>> analyzer.add_pattern(
            ...     "custom_pattern",
            ...     "sensor1",
            ...     ["sensor2", "sensor3"],
            ...     0.75,
            ...     "Custom root cause",
            ...     "Custom action"
            ... )
        """
        self.failure_patterns[pattern_id] = {
            "primary": primary,
            "correlated": correlated,
            "min_correlation": min_correlation,
            "cause": cause,
            "action": action,
        }
        logger.info("Added correlation pattern", pattern_id=pattern_id)

    def remove_pattern(self, pattern_id: str) -> bool:
        """
        Remove a correlation pattern.

        Args:
            pattern_id: Pattern identifier to remove

        Returns:
            True if pattern was removed, False if not found
        """
        if pattern_id in self.failure_patterns:
            del self.failure_patterns[pattern_id]
            logger.info("Removed correlation pattern", pattern_id=pattern_id)
            return True
        return False

    def get_pattern(self, pattern_id: str) -> Optional[Dict]:
        """
        Get a specific correlation pattern.

        Args:
            pattern_id: Pattern identifier

        Returns:
            Pattern dict or None if not found
        """
        return self.failure_patterns.get(pattern_id)

    def list_patterns(self) -> List[str]:
        """
        List all available correlation pattern IDs.

        Returns:
            List of pattern IDs
        """
        return list(self.failure_patterns.keys())

    def get_pattern_count(self) -> int:
        """
        Get total number of correlation patterns.

        Returns:
            Pattern count
        """
        return len(self.failure_patterns)
