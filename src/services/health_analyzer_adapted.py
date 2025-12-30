"""
Health Analyzer Service - ADAPTED for fuel_copilot_local

Analyzes truck and fleet health using our repositories.
Simplified version that works with our actual data structure.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class HealthAnalyzer:
    """Analyzes truck and fleet health based on sensor data and metrics."""

    def __init__(self):
        """Initialize HealthAnalyzer."""
        logger.info("HealthAnalyzer initialized (adapted version)")

    def calculate_truck_risk_score(
        self,
        truck_id: str,
        sensor_data: Dict[str, Any],
        dtc_count: int = 0,
        fuel_level: Optional[float] = None,
        days_offline: int = 0,
    ) -> Dict[str, Any]:
        """
        Calculate risk score for a truck (0-100).

        Higher score = higher risk

        Components:
        - Sensor alerts (40%)
        - DTCs active (30%)
        - Fuel level critical (15%)
        - Days offline (15%)
        """
        score = 0.0
        factors = []

        # 1. Sensor alerts (40%)
        sensor_score = 0
        if (
            sensor_data.get("coolant_temp_f") is not None
            and sensor_data["coolant_temp_f"] > 230
        ):
            sensor_score += 20
            factors.append("CRITICAL: Coolant temp high")
        elif (
            sensor_data.get("coolant_temp_f") is not None
            and sensor_data["coolant_temp_f"] > 220
        ):
            sensor_score += 10
            factors.append("WARNING: Coolant temp elevated")

        if (
            sensor_data.get("oil_pressure_psi") is not None
            and sensor_data["oil_pressure_psi"] < 15
        ):
            sensor_score += 20
            factors.append("CRITICAL: Oil pressure low")
        elif (
            sensor_data.get("oil_pressure_psi") is not None
            and sensor_data["oil_pressure_psi"] < 25
        ):
            sensor_score += 10
            factors.append("WARNING: Oil pressure below normal")

        if (
            sensor_data.get("battery_voltage") is not None
            and sensor_data["battery_voltage"] < 11.5
        ):
            sensor_score += 10
            factors.append("WARNING: Battery voltage low")

        if (
            sensor_data.get("def_level_pct") is not None
            and sensor_data["def_level_pct"] < 10
        ):
            sensor_score += 10
            factors.append("WARNING: DEF level critical")

        sensor_score = min(40, sensor_score)
        score += sensor_score

        # 2. DTCs (30%)
        dtc_score = min(30, dtc_count * 10)
        if dtc_count > 0:
            factors.append(f"Active DTCs: {dtc_count}")
        score += dtc_score

        # 3. Fuel level (15%)
        fuel_score = 0
        if fuel_level is not None:
            if fuel_level < 10:
                fuel_score = 15
                factors.append("CRITICAL: Fuel very low")
            elif fuel_level < 20:
                fuel_score = 10
                factors.append("WARNING: Fuel low")
            elif fuel_level < 30:
                fuel_score = 5
        score += fuel_score

        # 4. Days offline (15%)
        offline_score = 0
        if days_offline > 7:
            offline_score = 15
            factors.append(f"CRITICAL: Offline {days_offline} days")
        elif days_offline > 3:
            offline_score = 10
            factors.append(f"WARNING: Offline {days_offline} days")
        elif days_offline > 1:
            offline_score = 5
        score += offline_score

        # Determine risk level
        if score >= 75:
            risk_level = "CRITICAL"
        elif score >= 50:
            risk_level = "HIGH"
        elif score >= 25:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return {
            "truck_id": truck_id,
            "risk_score": round(score, 1),
            "risk_level": risk_level,
            "contributing_factors": factors,
            "sensor_score": sensor_score,
            "dtc_score": dtc_score,
            "fuel_score": fuel_score,
            "offline_score": offline_score,
        }

    def calculate_fleet_health_score(
        self,
        total_trucks: int,
        active_trucks: int,
        trucks_with_issues: int,
        trucks_with_dtcs: int,
        trucks_low_fuel: int,
    ) -> Dict[str, Any]:
        """
        Calculate overall fleet health score (0-100).

        Higher score = healthier fleet
        """
        if total_trucks == 0:
            return {"health_score": 0, "health_level": "UNKNOWN", "total_trucks": 0}

        # Start with 100 and deduct points
        score = 100.0

        # Deduct for offline trucks (max 30 points)
        offline_trucks = total_trucks - active_trucks
        offline_pct = (offline_trucks / total_trucks) * 100
        offline_penalty = min(30, offline_pct * 0.5)
        score -= offline_penalty

        # Deduct for trucks with issues (max 40 points)
        issues_pct = (trucks_with_issues / total_trucks) * 100
        issues_penalty = min(40, issues_pct * 0.8)
        score -= issues_penalty

        # Deduct for DTCs (max 20 points)
        dtc_pct = (trucks_with_dtcs / total_trucks) * 100
        dtc_penalty = min(20, dtc_pct * 0.4)
        score -= dtc_penalty

        # Deduct for low fuel (max 10 points)
        fuel_pct = (trucks_low_fuel / total_trucks) * 100
        fuel_penalty = min(10, fuel_pct * 0.2)
        score -= fuel_penalty

        score = max(0, score)

        # Determine health level
        if score >= 85:
            health_level = "EXCELLENT"
        elif score >= 70:
            health_level = "GOOD"
        elif score >= 50:
            health_level = "FAIR"
        elif score >= 30:
            health_level = "POOR"
        else:
            health_level = "CRITICAL"

        return {
            "health_score": round(score, 1),
            "health_level": health_level,
            "total_trucks": total_trucks,
            "active_trucks": active_trucks,
            "offline_trucks": offline_trucks,
            "trucks_with_issues": trucks_with_issues,
            "trucks_with_dtcs": trucks_with_dtcs,
            "trucks_low_fuel": trucks_low_fuel,
            "breakdown": {
                "offline_penalty": round(offline_penalty, 1),
                "issues_penalty": round(issues_penalty, 1),
                "dtc_penalty": round(dtc_penalty, 1),
                "fuel_penalty": round(fuel_penalty, 1),
            },
        }

    def get_fleet_insights(self, fleet_health: Dict[str, Any]) -> List[str]:
        """Generate actionable insights from fleet health data."""
        insights = []

        score = fleet_health["health_score"]

        if score < 50:
            insights.append(
                "⚠️ URGENT: Fleet health is below 50% - immediate attention required"
            )

        if (
            fleet_health.get("offline_trucks", 0)
            > fleet_health.get("total_trucks", 1) * 0.3
        ):
            insights.append(
                f"📡 {fleet_health['offline_trucks']} trucks offline - check connectivity"
            )

        if fleet_health.get("trucks_with_dtcs", 0) > 5:
            insights.append(
                f"�� {fleet_health['trucks_with_dtcs']} trucks with DTCs - schedule diagnostics"
            )

        if fleet_health.get("trucks_with_issues", 0) > 0:
            insights.append(
                f"⚠️ {fleet_health['trucks_with_issues']} trucks with sensor alerts"
            )

        if score >= 85:
            insights.append("✅ Fleet operating at optimal health")

        return insights
