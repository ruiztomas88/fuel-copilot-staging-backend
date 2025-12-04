"""
Fuel Cost Tracker v3.12.21
Trip-based fuel cost attribution

Addresses audit item #19: Fuel cost tracker por viaje

Features:
- Track fuel costs by trip/route
- Associate refuels with specific trips
- Calculate cost per mile per trip
- Driver cost comparison
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from contextlib import contextmanager
import os
import statistics

import pymysql
from pymysql.cursors import DictCursor

logger = logging.getLogger(__name__)


# =============================================================================
# DATABASE CONNECTION
# =============================================================================
def _get_db_config() -> Dict:
    """Get database configuration from environment."""
    return {
        "host": os.getenv("MYSQL_HOST", "localhost"),
        "port": int(os.getenv("MYSQL_PORT", "3306")),
        "user": os.getenv("MYSQL_USER", "fuel_admin"),
        "password": os.getenv("MYSQL_PASSWORD", ""),
        "database": os.getenv("MYSQL_DATABASE", "fuel_copilot"),
        "charset": "utf8mb4",
        "cursorclass": DictCursor,
        "autocommit": True,
    }


@contextmanager
def get_db_connection():
    """Get database connection with automatic cleanup."""
    conn = None
    try:
        conn = pymysql.connect(**_get_db_config())
        yield conn
    finally:
        if conn:
            conn.close()


# =============================================================================
# DATA CLASSES
# =============================================================================
@dataclass
class TripCost:
    """Cost analysis for a single trip."""

    trip_id: str
    truck_id: str
    driver_id: Optional[str]
    carrier_id: str

    # Trip details
    start_time: datetime
    end_time: datetime
    origin: Optional[str]
    destination: Optional[str]

    # Metrics
    total_miles: float
    total_gallons: float
    avg_mpg: float
    idle_gallons: float
    idle_percent: float

    # Costs
    fuel_cost: float
    cost_per_mile: float
    idle_cost: float

    # Refuels during trip
    refuel_count: int
    refuel_gallons: float
    refuel_cost: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "trip_id": self.trip_id,
            "truck_id": self.truck_id,
            "driver_id": self.driver_id,
            "carrier_id": self.carrier_id,
            "trip": {
                "start_time": self.start_time.isoformat() if self.start_time else None,
                "end_time": self.end_time.isoformat() if self.end_time else None,
                "origin": self.origin,
                "destination": self.destination,
                "duration_hours": (
                    (self.end_time - self.start_time).total_seconds() / 3600
                    if self.end_time and self.start_time
                    else 0
                ),
            },
            "metrics": {
                "total_miles": round(self.total_miles, 1),
                "total_gallons": round(self.total_gallons, 1),
                "avg_mpg": round(self.avg_mpg, 2),
                "idle_gallons": round(self.idle_gallons, 1),
                "idle_percent": round(self.idle_percent, 1),
            },
            "costs": {
                "fuel_cost": round(self.fuel_cost, 2),
                "cost_per_mile": round(self.cost_per_mile, 3),
                "idle_cost": round(self.idle_cost, 2),
                "total_cost": round(self.fuel_cost + self.idle_cost, 2),
            },
            "refuels": {
                "count": self.refuel_count,
                "gallons": round(self.refuel_gallons, 1),
                "cost": round(self.refuel_cost, 2),
            },
        }


@dataclass
class CostSummary:
    """Fleet-wide cost summary."""

    period_start: datetime
    period_end: datetime
    carrier_id: Optional[str]

    # Totals
    total_trips: int
    total_miles: float
    total_gallons: float
    total_cost: float

    # Averages
    avg_mpg: float
    avg_cost_per_mile: float
    avg_cost_per_trip: float

    # Breakdown
    cost_by_truck: Dict[str, float]
    cost_by_driver: Dict[str, float]

    # Trends
    trend_vs_previous: float  # % change vs previous period


# =============================================================================
# FUEL COST TRACKER
# =============================================================================
class FuelCostTracker:
    """
    Track fuel costs by trip and calculate cost per mile.

    A "trip" is defined as a period of continuous driving (with stops < 8 hours).
    """

    # Fuel price per gallon
    FUEL_PRICE = float(os.getenv("FUEL_PRICE_PER_GALLON", "3.50"))

    # Max stop duration before new trip (hours)
    MAX_STOP_HOURS = 8

    def __init__(self):
        self._ensure_table_exists()

    def _ensure_table_exists(self) -> None:
        """Create trips table if it doesn't exist."""
        create_sql = """
        CREATE TABLE IF NOT EXISTS trips (
            id BIGINT AUTO_INCREMENT PRIMARY KEY,
            trip_id VARCHAR(50) NOT NULL UNIQUE,
            truck_id VARCHAR(20) NOT NULL,
            driver_id VARCHAR(100),
            carrier_id VARCHAR(50) DEFAULT 'skylord',
            
            -- Trip details
            start_time DATETIME NOT NULL,
            end_time DATETIME,
            origin_name VARCHAR(200),
            origin_lat DOUBLE,
            origin_lng DOUBLE,
            destination_name VARCHAR(200),
            destination_lat DOUBLE,
            destination_lng DOUBLE,
            
            -- Metrics
            total_miles DOUBLE DEFAULT 0,
            total_gallons DOUBLE DEFAULT 0,
            avg_mpg DOUBLE,
            idle_minutes INT DEFAULT 0,
            idle_gallons DOUBLE DEFAULT 0,
            
            -- Costs
            fuel_cost DOUBLE DEFAULT 0,
            cost_per_mile DOUBLE,
            
            -- Status
            status VARCHAR(20) DEFAULT 'in_progress',  -- in_progress, completed, cancelled
            
            -- Metadata
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            
            INDEX idx_trip_truck (truck_id, start_time DESC),
            INDEX idx_trip_carrier (carrier_id, start_time DESC),
            INDEX idx_trip_driver (driver_id, start_time DESC),
            INDEX idx_trip_status (status, start_time DESC)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """

        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(create_sql)
                    logger.info("✅ Trips table ready")
        except Exception as e:
            logger.warning(f"⚠️ Could not create trips table: {e}")

    # =========================================================================
    # TRIP DETECTION
    # =========================================================================
    def detect_trips(
        self,
        truck_id: str,
        start_date: datetime,
        end_date: datetime,
    ) -> List[Dict]:
        """
        Detect trips from fuel_metrics data.

        A trip starts when truck starts moving and ends when
        it stops for more than MAX_STOP_HOURS.
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT 
                            timestamp_utc,
                            truck_status,
                            mileage_delta,
                            consumption_gph,
                            idle_duration_minutes,
                            latitude,
                            longitude
                        FROM fuel_metrics
                        WHERE truck_id = %s
                          AND timestamp_utc BETWEEN %s AND %s
                        ORDER BY timestamp_utc
                        """,
                        (truck_id, start_date, end_date),
                    )
                    rows = cursor.fetchall()

                    if not rows:
                        return []

                    # Detect trips
                    trips = []
                    current_trip = None
                    last_moving_time = None

                    for row in rows:
                        is_moving = row["truck_status"] == "MOVING"
                        timestamp = row["timestamp_utc"]

                        if is_moving:
                            if current_trip is None:
                                # Start new trip
                                current_trip = {
                                    "truck_id": truck_id,
                                    "start_time": timestamp,
                                    "end_time": None,
                                    "total_miles": 0,
                                    "total_gallons": 0,
                                    "idle_minutes": 0,
                                    "data_points": [],
                                }

                            # Add data point
                            current_trip["data_points"].append(row)
                            current_trip["total_miles"] += row["mileage_delta"] or 0
                            current_trip["total_gallons"] += (
                                row["consumption_gph"] or 0
                            ) * 0.5  # 30-min intervals
                            last_moving_time = timestamp

                        else:
                            # Stopped
                            if current_trip is not None:
                                current_trip["idle_minutes"] += (
                                    row["idle_duration_minutes"] or 0
                                )

                                # Check if stop is long enough to end trip
                                if last_moving_time:
                                    stop_duration = (
                                        timestamp - last_moving_time
                                    ).total_seconds() / 3600

                                    if stop_duration > self.MAX_STOP_HOURS:
                                        # End trip
                                        current_trip["end_time"] = last_moving_time
                                        trips.append(current_trip)
                                        current_trip = None
                                        last_moving_time = None

                    # Handle last trip
                    if current_trip is not None:
                        current_trip["end_time"] = (
                            last_moving_time or current_trip["start_time"]
                        )
                        trips.append(current_trip)

                    # Calculate costs for each trip
                    for i, trip in enumerate(trips):
                        trip["trip_id"] = (
                            f"{truck_id}_{trip['start_time'].strftime('%Y%m%d%H%M')}"
                        )
                        trip["avg_mpg"] = (
                            trip["total_miles"] / trip["total_gallons"]
                            if trip["total_gallons"] > 0
                            else 0
                        )
                        trip["fuel_cost"] = trip["total_gallons"] * self.FUEL_PRICE
                        trip["cost_per_mile"] = (
                            trip["fuel_cost"] / trip["total_miles"]
                            if trip["total_miles"] > 0
                            else 0
                        )
                        trip["idle_gallons"] = (
                            trip["idle_minutes"] * 0.8 / 60
                        )  # ~0.8 GPH idle
                        trip["idle_cost"] = trip["idle_gallons"] * self.FUEL_PRICE

                        # Remove raw data points
                        del trip["data_points"]

                    return trips

        except Exception as e:
            logger.error(f"Error detecting trips for {truck_id}: {e}")
            return []

    # =========================================================================
    # COST CALCULATIONS
    # =========================================================================
    def get_truck_cost_summary(
        self,
        truck_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """Get cost summary for a specific truck."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        trips = self.detect_trips(truck_id, start_date, end_date)

        if not trips:
            return {
                "truck_id": truck_id,
                "period_days": days,
                "trips": [],
                "summary": {
                    "total_trips": 0,
                    "total_miles": 0,
                    "total_gallons": 0,
                    "total_cost": 0,
                    "avg_mpg": 0,
                    "avg_cost_per_mile": 0,
                },
            }

        total_miles = sum(t["total_miles"] for t in trips)
        total_gallons = sum(t["total_gallons"] for t in trips)
        total_cost = sum(t["fuel_cost"] for t in trips)

        return {
            "truck_id": truck_id,
            "period_days": days,
            "trips": trips,
            "summary": {
                "total_trips": len(trips),
                "total_miles": round(total_miles, 1),
                "total_gallons": round(total_gallons, 1),
                "total_cost": round(total_cost, 2),
                "avg_mpg": (
                    round(total_miles / total_gallons, 2) if total_gallons > 0 else 0
                ),
                "avg_cost_per_mile": (
                    round(total_cost / total_miles, 3) if total_miles > 0 else 0
                ),
                "avg_cost_per_trip": round(total_cost / len(trips), 2),
                "idle_cost": round(sum(t["idle_cost"] for t in trips), 2),
            },
        }

    def get_fleet_cost_summary(
        self,
        carrier_id: Optional[str] = None,
        days: int = 7,
    ) -> Dict[str, Any]:
        """Get cost summary for entire fleet."""
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)

        # Get all trucks
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    where = ""
                    params = [start_date, end_date]

                    if carrier_id and carrier_id != "*":
                        where = "AND carrier_id = %s"
                        params.append(carrier_id)

                    cursor.execute(
                        f"""
                        SELECT DISTINCT truck_id
                        FROM fuel_metrics
                        WHERE timestamp_utc BETWEEN %s AND %s
                        {where}
                        """,
                        params,
                    )
                    trucks = [r["truck_id"] for r in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Error getting trucks: {e}")
            trucks = []

        # Aggregate costs
        truck_costs = {}
        total_miles = 0
        total_gallons = 0
        total_cost = 0
        total_trips = 0

        for truck_id in trucks:
            summary = self.get_truck_cost_summary(truck_id, days)
            if summary["summary"]["total_trips"] > 0:
                truck_costs[truck_id] = {
                    "cost": summary["summary"]["total_cost"],
                    "miles": summary["summary"]["total_miles"],
                    "gallons": summary["summary"]["total_gallons"],
                    "trips": summary["summary"]["total_trips"],
                    "mpg": summary["summary"]["avg_mpg"],
                    "cost_per_mile": summary["summary"]["avg_cost_per_mile"],
                }
                total_miles += summary["summary"]["total_miles"]
                total_gallons += summary["summary"]["total_gallons"]
                total_cost += summary["summary"]["total_cost"]
                total_trips += summary["summary"]["total_trips"]

        # Sort trucks by cost
        sorted_trucks = sorted(
            truck_costs.items(), key=lambda x: x[1]["cost"], reverse=True
        )

        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat(),
                "days": days,
            },
            "carrier_id": carrier_id,
            "summary": {
                "total_trucks": len(truck_costs),
                "total_trips": total_trips,
                "total_miles": round(total_miles, 1),
                "total_gallons": round(total_gallons, 1),
                "total_cost": round(total_cost, 2),
                "avg_mpg": (
                    round(total_miles / total_gallons, 2) if total_gallons > 0 else 0
                ),
                "avg_cost_per_mile": (
                    round(total_cost / total_miles, 3) if total_miles > 0 else 0
                ),
            },
            "by_truck": dict(sorted_trucks[:10]),  # Top 10 by cost
            "top_cost": sorted_trucks[0] if sorted_trucks else None,
            "best_mpg": (
                max(truck_costs.items(), key=lambda x: x[1]["mpg"], default=(None, {}))[
                    0
                ]
                if truck_costs
                else None
            ),
            "worst_mpg": (
                min(truck_costs.items(), key=lambda x: x[1]["mpg"], default=(None, {}))[
                    0
                ]
                if truck_costs
                else None
            ),
        }

    # =========================================================================
    # COST COMPARISON
    # =========================================================================
    def compare_drivers(
        self,
        truck_id: str,
        days: int = 30,
    ) -> Dict[str, Any]:
        """
        Compare costs between drivers on the same truck.

        Note: Requires driver_id in fuel_metrics (from ELD integration).
        """
        try:
            with get_db_connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT 
                            driver_id,
                            SUM(mileage_delta) as total_miles,
                            SUM(consumption_gph * 0.5) as total_gallons,
                            AVG(mpg_current) as avg_mpg,
                            SUM(idle_duration_minutes) as idle_minutes,
                            COUNT(*) as data_points
                        FROM fuel_metrics
                        WHERE truck_id = %s
                          AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s DAY)
                          AND driver_id IS NOT NULL
                        GROUP BY driver_id
                        """,
                        (truck_id, days),
                    )
                    rows = cursor.fetchall()

                    if not rows:
                        return {
                            "truck_id": truck_id,
                            "period_days": days,
                            "drivers": [],
                            "message": "No driver data available (requires ELD integration)",
                        }

                    drivers = []
                    for row in rows:
                        total_gallons = row["total_gallons"] or 0
                        total_miles = row["total_miles"] or 0
                        fuel_cost = total_gallons * self.FUEL_PRICE

                        drivers.append(
                            {
                                "driver_id": row["driver_id"],
                                "total_miles": round(total_miles, 1),
                                "total_gallons": round(total_gallons, 1),
                                "avg_mpg": round(row["avg_mpg"] or 0, 2),
                                "fuel_cost": round(fuel_cost, 2),
                                "cost_per_mile": (
                                    round(fuel_cost / total_miles, 3)
                                    if total_miles > 0
                                    else 0
                                ),
                                "idle_hours": round((row["idle_minutes"] or 0) / 60, 1),
                                "data_points": row["data_points"],
                            }
                        )

                    # Sort by efficiency (cost per mile)
                    drivers.sort(key=lambda d: d["cost_per_mile"])

                    # Calculate rankings
                    for i, driver in enumerate(drivers):
                        driver["rank"] = i + 1
                        driver["efficiency_rating"] = (
                            "A"
                            if driver["cost_per_mile"] < 0.50
                            else (
                                "B"
                                if driver["cost_per_mile"] < 0.60
                                else "C" if driver["cost_per_mile"] < 0.70 else "D"
                            )
                        )

                    return {
                        "truck_id": truck_id,
                        "period_days": days,
                        "drivers": drivers,
                        "best_driver": drivers[0]["driver_id"] if drivers else None,
                        "cost_difference": (
                            round(
                                (
                                    drivers[-1]["cost_per_mile"]
                                    - drivers[0]["cost_per_mile"]
                                )
                                * 100,
                                1,
                            )
                            if len(drivers) > 1
                            else 0
                        ),
                    }

        except Exception as e:
            logger.error(f"Error comparing drivers: {e}")
            return {"error": str(e)}


# =============================================================================
# GLOBAL INSTANCE
# =============================================================================
_cost_tracker: Optional[FuelCostTracker] = None


def get_cost_tracker() -> FuelCostTracker:
    """Get or create FuelCostTracker singleton."""
    global _cost_tracker
    if _cost_tracker is None:
        _cost_tracker = FuelCostTracker()
    return _cost_tracker
