"""
Analytics Service - Fleet Analytics and KPI Calculations

Extracted from database_mysql.py for cleaner architecture.

This service combines data from multiple repositories to generate
analytics, KPIs, and insights.

FASE 11: Database Orchestrator Refactoring
Author: Fuel Copilot Team
Created: December 2025
"""

import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import logging

from src.repositories.truck_repository import TruckRepository
from src.repositories.sensor_repository import SensorRepository
from src.repositories.def_repository import DEFRepository
from src.repositories.dtc_repository import DTCRepository

logger = logging.getLogger(__name__)


class AnalyticsService:
    """
    Fleet analytics service combining multiple data sources.

    Replaces monolithic database_mysql.py functions with service-oriented approach.
    """

    def __init__(
        self,
        truck_repo: TruckRepository,
        sensor_repo: SensorRepository,
        def_repo: DEFRepository,
        dtc_repo: DTCRepository,
    ):
        """
        Initialize AnalyticsService with required repositories.

        Args:
            truck_repo: TruckRepository instance
            sensor_repo: SensorRepository instance
            def_repo: DEFRepository instance
            dtc_repo: DTCRepository instance
        """
        self.truck_repo = truck_repo
        self.sensor_repo = sensor_repo
        self.def_repo = def_repo
        self.dtc_repo = dtc_repo
        logger.info("AnalyticsService initialized")

    async def get_fleet_summary(self) -> Dict[str, Any]:
        """
        Get fleet-wide summary statistics.

        Returns:
            Dictionary with fleet summary:
            - total_trucks: int
            - active_trucks: int
            - avg_mpg: float
            - total_fuel_consumed: float
            - total_miles: float
            - health_score: float
        """
        try:
            # Get all trucks
            trucks = await self.truck_repo.get_all_trucks()

            if not trucks:
                return self._empty_fleet_summary()

            total_trucks = len(trucks)
            active_trucks = sum(1 for t in trucks if getattr(t, "is_active", True))

            # Calculate aggregates
            total_fuel = sum(getattr(t, "fuel_consumed", 0) for t in trucks)
            total_miles = sum(getattr(t, "miles_driven", 0) for t in trucks)
            avg_mpg = (total_miles / total_fuel) if total_fuel > 0 else 0

            # Simple health score based on active DTCs
            total_dtcs = 0
            for truck in trucks:
                truck_dtcs = await self.dtc_repo.get_active_dtcs([truck.truck_id])
                total_dtcs += len(truck_dtcs)

            health_score = max(0, 100 - (total_dtcs * 5))  # -5 points per DTC

            return {
                "total_trucks": total_trucks,
                "active_trucks": active_trucks,
                "avg_mpg": round(avg_mpg, 2),
                "total_fuel_consumed": round(total_fuel, 2),
                "total_miles": round(total_miles, 2),
                "health_score": round(health_score, 1),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting fleet summary: {e}", exc_info=True)
            return self._empty_fleet_summary()

    async def get_truck_efficiency_stats(
        self, truck_id: str, days_back: int = 30
    ) -> Dict[str, Any]:
        """
        Get efficiency statistics for a specific truck.

        Args:
            truck_id: Truck ID
            days_back: Number of days to analyze

        Returns:
            Dictionary with efficiency stats:
            - truck_id: str
            - avg_mpg: float
            - mpg_vs_baseline: float
            - fuel_consumed: float
            - miles_driven: float
            - efficiency_rating: str (HIGH/MEDIUM/LOW)
        """
        try:
            # Get truck data
            truck = await self.truck_repo.get_truck_by_id(truck_id)
            if not truck:
                return {"error": f"Truck {truck_id} not found"}

            # Get sensor readings for fuel and distance
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days_back)

            sensors = await self.sensor_repo.get_readings_range(
                truck_id=truck_id, start_time=start_date, end_time=end_date
            )

            # Calculate stats
            fuel_consumed = sum(
                getattr(s, "fuel_level_delta", 0)
                for s in sensors
                if getattr(s, "fuel_level_delta", 0) > 0
            )
            miles_driven = sum(
                getattr(s, "odometer_delta", 0)
                for s in sensors
                if hasattr(s, "odometer_delta")
            )

            avg_mpg = (miles_driven / fuel_consumed) if fuel_consumed > 0 else 0
            baseline_mpg = 5.7  # Industry baseline for Class 8
            mpg_vs_baseline = (
                ((avg_mpg - baseline_mpg) / baseline_mpg * 100)
                if baseline_mpg > 0
                else 0
            )

            # Rating
            if mpg_vs_baseline > 5:
                rating = "HIGH"
            elif mpg_vs_baseline < -5:
                rating = "LOW"
            else:
                rating = "MEDIUM"

            return {
                "truck_id": truck_id,
                "avg_mpg": round(avg_mpg, 2),
                "mpg_vs_baseline": round(mpg_vs_baseline, 1),
                "fuel_consumed": round(fuel_consumed, 2),
                "miles_driven": round(miles_driven, 2),
                "efficiency_rating": rating,
                "days_analyzed": days_back,
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting truck efficiency stats: {e}", exc_info=True)
            return {"error": str(e)}

    async def get_sensor_health_summary(self) -> Dict[str, Any]:
        """
        Get summary of sensor health across fleet.

        Returns:
            Dictionary with sensor health summary:
            - gps_issues: int
            - voltage_issues: int
            - fuel_sensor_issues: int
            - total_sensors: int
            - health_percentage: float
        """
        try:
            # Get all trucks
            trucks = await self.truck_repo.get_all_trucks()

            gps_issues = 0
            voltage_issues = 0
            fuel_issues = 0

            for truck in trucks:
                # Get recent sensors
                sensors = await self.sensor_repo.get_recent_readings(
                    truck_id=truck.truck_id, limit=100
                )

                # Check for issues
                for sensor in sensors:
                    if hasattr(sensor, "gps_valid") and not sensor.gps_valid:
                        gps_issues += 1
                    if hasattr(sensor, "voltage") and (
                        sensor.voltage < 11 or sensor.voltage > 15
                    ):
                        voltage_issues += 1
                    if hasattr(sensor, "fuel_level") and (
                        sensor.fuel_level < 0 or sensor.fuel_level > 100
                    ):
                        fuel_issues += 1

            total_sensors = len(trucks) * 3  # GPS, Voltage, Fuel per truck
            total_issues = gps_issues + voltage_issues + fuel_issues
            health_pct = (
                ((total_sensors - total_issues) / total_sensors * 100)
                if total_sensors > 0
                else 100
            )

            return {
                "gps_issues": gps_issues,
                "voltage_issues": voltage_issues,
                "fuel_sensor_issues": fuel_issues,
                "total_sensors": total_sensors,
                "health_percentage": round(health_pct, 1),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting sensor health summary: {e}", exc_info=True)
            return {
                "gps_issues": 0,
                "voltage_issues": 0,
                "fuel_sensor_issues": 0,
                "total_sensors": 0,
                "health_percentage": 0.0,
                "error": str(e),
            }

    def _empty_fleet_summary(self) -> Dict[str, Any]:
        """Return empty fleet summary."""
        return {
            "total_trucks": 0,
            "active_trucks": 0,
            "avg_mpg": 0.0,
            "total_fuel_consumed": 0.0,
            "total_miles": 0.0,
            "health_score": 0.0,
            "timestamp": datetime.now().isoformat(),
        }
