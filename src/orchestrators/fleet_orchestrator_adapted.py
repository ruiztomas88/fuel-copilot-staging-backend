"""
Fleet Orchestrator - ADAPTED for our fuel_copilot_local database

Combines repositories and services to provide high-level fleet operations.
This is a simplified version that reuses our existing database_mysql functions.
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from src.repositories.def_repository import DEFRepository
from src.repositories.dtc_repository import DTCRepository
from src.repositories.sensor_repository import SensorRepository
from src.repositories.truck_repository import TruckRepository
from src.services.analytics_service_adapted import AnalyticsService
from src.services.def_predictor_adapted import DEFPredictor
from src.services.health_analyzer_adapted import HealthAnalyzer
from src.services.pattern_analyzer_adapted import PatternAnalyzer
from src.services.priority_engine import PriorityEngine

logger = logging.getLogger(__name__)


def convert_to_json_serializable(obj):
    """Convert Decimal and datetime objects to JSON serializable types."""
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {k: convert_to_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_to_json_serializable(item) for item in obj]
    return obj


class FleetOrchestrator:
    """
    High-level fleet operations orchestrator.

    Coordinates between repositories and services to provide
    complete fleet management functionality.
    """

    def __init__(
        self,
        truck_repo: TruckRepository,
        sensor_repo: SensorRepository,
        def_repo: DEFRepository,
        dtc_repo: DTCRepository,
    ):
        """Initialize orchestrator with repositories."""
        self.truck_repo = truck_repo
        self.sensor_repo = sensor_repo
        self.def_repo = def_repo
        self.dtc_repo = dtc_repo

        # Initialize services
        self.analytics = AnalyticsService()
        self.priority_engine = PriorityEngine()
        self.health_analyzer = HealthAnalyzer()
        self.def_predictor = DEFPredictor()
        self.pattern_analyzer = PatternAnalyzer()

        logger.info("FleetOrchestrator initialized with all services")

    def get_command_center_data(self) -> Dict[str, Any]:
        """
        Get comprehensive fleet data for command center dashboard.

        Returns:
            Dictionary with fleet summary, truck details, alerts, etc.
        """
        try:
            # Get fleet summary
            fleet_summary = self.analytics.get_fleet_summary()

            # Get all trucks with their latest data
            trucks = self.truck_repo.get_all_trucks()

            # Get active alerts
            sensor_alerts = []
            for truck in trucks[:5]:  # Limit for performance
                alerts = self.sensor_repo.get_sensor_alerts(truck["truck_id"])
                sensor_alerts.extend(alerts)

            # Get trucks with low DEF
            low_def_trucks = self.def_repo.get_low_def_trucks(threshold=15)

            # Get active DTCs
            fleet_dtcs = self.dtc_repo.get_fleet_dtcs()

            # Combine into response and convert all Decimals/datetimes
            data = {
                "timestamp": datetime.utcnow().isoformat(),
                "fleet_summary": fleet_summary,
                "total_trucks": len(trucks),
                "trucks": [
                    {
                        "truck_id": t["truck_id"],
                        "status": t.get("status"),
                        "fuel_level": (
                            float(t["fuel_level"]) if t.get("fuel_level") else None
                        ),
                        "speed": float(t["speed"]) if t.get("speed") else None,
                        "mpg": float(t["mpg"]) if t.get("mpg") else None,
                        "last_update": (
                            t.get("last_update").isoformat()
                            if t.get("last_update")
                            else None
                        ),
                    }
                    for t in trucks[:20]  # Limit for response size
                ],
                "alerts": {
                    "sensor_alerts": sensor_alerts[:10],
                    "low_def": len(low_def_trucks),
                    "active_dtcs": len(fleet_dtcs),
                },
                "metrics": {
                    "active_trucks": fleet_summary.get("active_trucks", 0),
                    "offline_trucks": fleet_summary.get("offline_trucks", 0),
                    "moving_trucks": fleet_summary.get("moving_trucks", 0),
                    "idling_trucks": fleet_summary.get("idling_trucks", 0),
                },
            }

            # Convert any remaining Decimals/datetimes
            return convert_to_json_serializable(data)

        except Exception as e:
            logger.error(f"Error getting command center data: {e}", exc_info=True)
            return {"error": str(e), "timestamp": datetime.utcnow().isoformat()}

    def get_truck_detail(self, truck_id: str) -> Dict[str, Any]:
        """Get detailed information for a specific truck."""
        try:
            truck = self.truck_repo.get_truck_by_id(truck_id)
            if not truck:
                return {"error": f"Truck {truck_id} not found"}

            sensors = self.sensor_repo.get_truck_sensors(truck_id)
            sensor_alerts = self.sensor_repo.get_sensor_alerts(truck_id)
            def_level = self.def_repo.get_def_level(truck_id)
            dtcs = self.dtc_repo.get_active_dtcs(truck_id)

            data = {
                "truck_id": truck_id,
                "basic_info": truck,
                "sensors": sensors,
                "alerts": sensor_alerts,
                "def_level": float(def_level) if def_level else None,
                "dtcs": dtcs,
            }

            return convert_to_json_serializable(data)

        except Exception as e:
            logger.error(f"Error getting truck detail for {truck_id}: {e}")
            return {"error": str(e)}

    def get_fleet_health_overview(self) -> Dict[str, Any]:
        """Get fleet-wide health overview."""
        try:
            all_sensors = self.sensor_repo.get_all_sensors_for_fleet()
            low_def = self.def_repo.get_low_def_trucks(threshold=20)
            dtc_counts = self.dtc_repo.get_dtc_count_by_truck(days=7)

            # Calculate health scores
            trucks_with_issues = len(
                [
                    s
                    for s in all_sensors
                    if s.get("coolant_temp_f") and s["coolant_temp_f"] > 220
                ]
            )
            trucks_with_low_def = len(low_def)
            trucks_with_dtcs = len(dtc_counts)

            return {
                "total_trucks": len(all_sensors),
                "trucks_with_issues": trucks_with_issues,
                "trucks_with_low_def": trucks_with_low_def,
                "trucks_with_dtcs": trucks_with_dtcs,
                "health_score": max(
                    0,
                    100
                    - (trucks_with_issues * 5)
                    - (trucks_with_low_def * 2)
                    - (trucks_with_dtcs * 3),
                ),
            }

        except Exception as e:
            logger.error(f"Error getting fleet health: {e}")
            return {"error": str(e)}

    def get_advanced_fleet_health(self) -> Dict[str, Any]:
        """Get advanced fleet health with HealthAnalyzer."""
        try:
            # Get basic data
            trucks = self.truck_repo.get_all_trucks()
            all_sensors = self.sensor_repo.get_all_sensors_for_fleet()
            dtc_counts = self.dtc_repo.get_dtc_count_by_truck(days=7)

            # Count issues
            active_trucks = len(
                [t for t in trucks if t.get("status") not in ["OFFLINE", None]]
            )
            trucks_with_dtcs = len(dtc_counts)

            # Detect issues from sensors
            trucks_with_issues = 0
            trucks_low_fuel = 0
            for sensor in all_sensors:
                has_issue = False
                if sensor.get("coolant_temp_f") and sensor["coolant_temp_f"] > 220:
                    has_issue = True
                if sensor.get("oil_pressure_psi") and sensor["oil_pressure_psi"] < 25:
                    has_issue = True
                if sensor.get("battery_voltage") and sensor["battery_voltage"] < 12.0:
                    has_issue = True
                if has_issue:
                    trucks_with_issues += 1

            for truck in trucks:
                if truck.get("fuel_level") and truck["fuel_level"] < 20:
                    trucks_low_fuel += 1

            # Use HealthAnalyzer
            health_data = self.health_analyzer.calculate_fleet_health_score(
                total_trucks=len(trucks),
                active_trucks=active_trucks,
                trucks_with_issues=trucks_with_issues,
                trucks_with_dtcs=trucks_with_dtcs,
                trucks_low_fuel=trucks_low_fuel,
            )

            # Get insights
            insights = self.health_analyzer.get_fleet_insights(health_data)
            health_data["insights"] = insights

            return convert_to_json_serializable(health_data)

        except Exception as e:
            logger.error(f"Error getting advanced fleet health: {e}", exc_info=True)
            return {"error": str(e)}

    def get_truck_risk_analysis(self, truck_id: str) -> Dict[str, Any]:
        """Get comprehensive risk analysis for a truck."""
        try:
            # Get truck data
            truck = self.truck_repo.get_truck_by_id(truck_id)
            if not truck:
                return {"error": f"Truck {truck_id} not found"}

            sensors = self.sensor_repo.get_truck_sensors(truck_id)
            dtcs = self.dtc_repo.get_active_dtcs(truck_id)
            fuel_level = truck.get("fuel_level_pct")

            # Calculate days offline
            last_update = truck.get("last_update")
            days_offline = 0
            if last_update:
                time_diff = datetime.utcnow() - last_update
                days_offline = int(time_diff.total_seconds() / 86400)

            # Use HealthAnalyzer
            risk_score = self.health_analyzer.calculate_truck_risk_score(
                truck_id=truck_id,
                sensor_data=sensors or {},
                dtc_count=len(dtcs),
                fuel_level=fuel_level,
                days_offline=days_offline,
            )

            # Use PatternAnalyzer for correlations
            dtc_codes = [d.get("dtc_code") for d in dtcs if d.get("dtc_code")]
            correlations = self.pattern_analyzer.detect_correlations(
                truck_id=truck_id, sensor_data=sensors or {}, dtc_codes=dtc_codes
            )

            return convert_to_json_serializable(
                {
                    "truck_id": truck_id,
                    "risk_analysis": risk_score,
                    "correlations": correlations,
                    "dtcs": dtcs,
                    "sensors": sensors,
                }
            )

        except Exception as e:
            logger.error(f"Error getting truck risk for {truck_id}: {e}", exc_info=True)
            return {"error": str(e)}

    def get_def_predictions(
        self, truck_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Get DEF predictions for trucks."""
        try:
            predictions = []

            if truck_ids:
                # Specific trucks
                for truck_id in truck_ids:
                    def_level = self.def_repo.get_def_level(truck_id)
                    truck = self.truck_repo.get_truck_by_id(truck_id)

                    prediction = self.def_predictor.predict_def_depletion(
                        truck_id=truck_id,
                        current_level_pct=def_level,
                        avg_mpg=truck.get("mpg") if truck else None,
                    )
                    predictions.append(prediction)
            else:
                # All trucks with low DEF
                low_def_trucks = self.def_repo.get_low_def_trucks(threshold=30)
                for truck_data in low_def_trucks:
                    truck_id = truck_data["truck_id"]
                    def_level = truck_data["def_level_pct"]

                    prediction = self.def_predictor.predict_def_depletion(
                        truck_id=truck_id, current_level_pct=def_level
                    )
                    predictions.append(prediction)

            # Sort by urgency (days until derate)
            predictions.sort(key=lambda x: x.get("days_until_derate") or 999)

            return convert_to_json_serializable(
                {
                    "predictions": predictions,
                    "total": len(predictions),
                    "critical": len(
                        [p for p in predictions if p["status"] == "CRITICAL"]
                    ),
                    "warnings": len(
                        [p for p in predictions if p["status"] == "WARNING"]
                    ),
                }
            )

        except Exception as e:
            logger.error(f"Error getting DEF predictions: {e}", exc_info=True)
            return {"error": str(e)}

    def get_fleet_patterns(self) -> Dict[str, Any]:
        """Detect patterns across the fleet."""
        try:
            # Get fleet data
            all_sensors = self.sensor_repo.get_all_sensors_for_fleet()
            fleet_dtcs = self.dtc_repo.get_fleet_dtcs()

            # Use PatternAnalyzer
            patterns = self.pattern_analyzer.detect_fleet_patterns(
                trucks_sensor_data=all_sensors, dtc_data=fleet_dtcs
            )

            # Get systemic issues
            systemic_issues = self.pattern_analyzer.get_systemic_issues(patterns)

            return convert_to_json_serializable(
                {
                    "patterns": patterns,
                    "total_patterns": len(patterns),
                    "systemic_issues": systemic_issues,
                    "high_severity": len(
                        [p for p in patterns if p["severity"] == "HIGH"]
                    ),
                }
            )

        except Exception as e:
            logger.error(f"Error detecting fleet patterns: {e}", exc_info=True)
            return {"error": str(e)}
