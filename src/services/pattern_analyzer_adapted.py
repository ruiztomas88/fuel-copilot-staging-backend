"""
Pattern Analyzer Service - ADAPTED for fuel_copilot_local

Detects patterns and correlations in truck issues.
Simplified version that works with our actual sensor and DTC data.
"""

import logging
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PatternAnalyzer:
    """Analyzes patterns across fleet for systemic issues."""

    # Known failure patterns
    FAILURE_PATTERNS = {
        "overheating": {
            "sensors": ["coolant_temp_f", "oil_temp_f", "trans_temp_f"],
            "threshold_pct": 0.2,  # 20% of fleet
            "description": "Overheating syndrome - cooling system issues",
        },
        "electrical": {
            "sensors": ["battery_voltage"],
            "threshold_pct": 0.15,
            "description": "Electrical system issues",
        },
        "def_system": {
            "sensors": ["def_level_pct"],
            "threshold_pct": 0.25,
            "description": "DEF system issues across fleet",
        },
    }

    def __init__(self):
        """Initialize Pattern Analyzer."""
        logger.info("PatternAnalyzer initialized (adapted version)")

    def detect_fleet_patterns(
        self, trucks_sensor_data: List[Dict[str, Any]], dtc_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect patterns across the fleet.

        Args:
            trucks_sensor_data: List of sensor dicts (from sensor_repo)
            dtc_data: List of DTC dicts (from dtc_repo)

        Returns:
            List of detected patterns
        """
        patterns = []
        total_trucks = len(trucks_sensor_data)

        if total_trucks == 0:
            return patterns

        # 1. Analyze sensor patterns
        sensor_issues = defaultdict(list)

        for truck_data in trucks_sensor_data:
            truck_id = truck_data.get("truck_id")

            # Check coolant temp
            if truck_data.get("coolant_temp_f") and truck_data["coolant_temp_f"] > 220:
                sensor_issues["coolant_high"].append(truck_id)

            # Check oil pressure
            if (
                truck_data.get("oil_pressure_psi")
                and truck_data["oil_pressure_psi"] < 25
            ):
                sensor_issues["oil_pressure_low"].append(truck_id)

            # Check battery
            if (
                truck_data.get("battery_voltage")
                and truck_data["battery_voltage"] < 12.0
            ):
                sensor_issues["battery_low"].append(truck_id)

            # Check DEF
            if truck_data.get("def_level_pct") and truck_data["def_level_pct"] < 15:
                sensor_issues["def_low"].append(truck_id)

        # Detect patterns (>20% of fleet)
        threshold = total_trucks * 0.2

        for issue_type, affected_trucks in sensor_issues.items():
            if len(affected_trucks) >= threshold:
                patterns.append(
                    {
                        "pattern_type": "sensor_pattern",
                        "issue": issue_type,
                        "affected_trucks": affected_trucks,
                        "count": len(affected_trucks),
                        "affected_count": len(affected_trucks),  # Add for compatibility
                        "percentage": round(
                            (len(affected_trucks) / total_trucks) * 100, 1
                        ),
                        "severity": (
                            "HIGH"
                            if len(affected_trucks) >= total_trucks * 0.3
                            else "MEDIUM"
                        ),
                        "recommendation": self._get_recommendation(issue_type),
                    }
                )

        # 2. Analyze DTC patterns
        if dtc_data:
            dtc_codes = Counter()
            for dtc in dtc_data:
                if dtc.get("dtc_code"):
                    dtc_codes[dtc["dtc_code"]] += 1

            # Common DTCs (>3 trucks)
            for dtc_code, count in dtc_codes.items():
                if count >= 3:
                    patterns.append(
                        {
                            "pattern_type": "dtc_pattern",
                            "dtc_code": dtc_code,
                            "count": count,
                            "affected_count": count,  # Add for compatibility
                            "percentage": round((count / total_trucks) * 100, 1),
                            "severity": "HIGH" if count >= 5 else "MEDIUM",
                            "recommendation": f"Investigate DTC {dtc_code} - affecting {count} trucks",
                        }
                    )

        # Sort by severity and count
        patterns.sort(key=lambda x: (x["severity"] == "HIGH", x["count"]), reverse=True)

        return patterns

    def detect_correlations(
        self, truck_id: str, sensor_data: Dict[str, Any], dtc_codes: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Detect correlated issues for a single truck.

        Args:
            truck_id: Truck ID
            sensor_data: Sensor readings dict
            dtc_codes: List of active DTC codes

        Returns:
            List of detected correlations
        """
        correlations = []

        # Pattern 1: High temp + Low pressure = Cooling system failure
        coolant_temp = sensor_data.get("coolant_temp_f")
        oil_pressure = sensor_data.get("oil_pressure_psi")
        coolant_high = coolant_temp is not None and coolant_temp > 220
        oil_pressure_low = oil_pressure is not None and oil_pressure < 25

        if coolant_high and oil_pressure_low:
            correlations.append(
                {
                    "pattern": "cooling_failure",
                    "description": "High coolant temp + Low oil pressure",
                    "severity": "CRITICAL",
                    "root_cause": "Cooling system or lubrication failure",
                    "action": "IMMEDIATE: Stop truck, check coolant and oil",
                }
            )

        # Pattern 2: Multiple temp sensors high = Overheating
        temps_high = 0
        coolant_temp = sensor_data.get("coolant_temp_f")
        oil_temp = sensor_data.get("oil_temp_f")
        trans_temp = sensor_data.get("trans_temp_f")

        if coolant_temp is not None and coolant_temp > 220:
            temps_high += 1
        if oil_temp is not None and oil_temp > 250:
            temps_high += 1
        if trans_temp is not None and trans_temp > 230:
            temps_high += 1

        if temps_high >= 2:
            correlations.append(
                {
                    "pattern": "widespread_overheating",
                    "description": f"{temps_high} temperature sensors elevated",
                    "severity": "CRITICAL",
                    "root_cause": "Systemic overheating - cooling system failure",
                    "action": "IMMEDIATE: Check radiator, coolant, and fan",
                }
            )

        # Pattern 3: Low battery + Multiple DTCs = Electrical issue
        battery_voltage = sensor_data.get("battery_voltage")
        battery_low = battery_voltage is not None and battery_voltage < 12.0
        multiple_dtcs = len(dtc_codes) >= 3

        if battery_low and multiple_dtcs:
            correlations.append(
                {
                    "pattern": "electrical_failure",
                    "description": "Low battery with multiple DTCs",
                    "severity": "HIGH",
                    "root_cause": "Alternator or electrical system failure",
                    "action": "Test alternator and battery connections",
                }
            )

        return correlations

    def _get_recommendation(self, issue_type: str) -> str:
        """Get recommendation for issue type."""
        recommendations = {
            "coolant_high": "Check cooling systems fleet-wide - possible coolant quality issue",
            "oil_pressure_low": "Inspect oil systems - possible filter or pump issues",
            "battery_low": "Check alternators and batteries - possible charging system pattern",
            "def_low": "Schedule DEF refills - multiple trucks need service",
        }
        return recommendations.get(
            issue_type, "Investigate issue across affected trucks"
        )

    def get_systemic_issues(
        self, patterns: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Extract systemic issues from patterns."""
        issues = []

        for pattern in patterns:
            if pattern["severity"] == "HIGH":
                if pattern["pattern_type"] == "sensor_pattern":
                    issues.append(
                        {
                            "type": "sensor",
                            "description": f"{pattern['issue']}: {pattern['count']} trucks ({pattern['percentage']}%)",
                            "recommendation": pattern["recommendation"],
                            "severity": "HIGH",
                            "count": pattern["count"],
                        }
                    )
                elif pattern["pattern_type"] == "dtc_pattern":
                    issues.append(
                        {
                            "type": "dtc",
                            "description": f"DTC {pattern['dtc_code']}: {pattern['count']} trucks ({pattern['percentage']}%)",
                            "severity": "HIGH",
                            "count": pattern["count"],
                        }
                    )

        return issues
