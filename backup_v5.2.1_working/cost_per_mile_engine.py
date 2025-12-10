"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    COST PER MILE TRACKING ENGINE                               ║
║                         Fuel Copilot v4.0                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Purpose: Track total cost per mile with breakdown and benchmarks              ║
║  Inspired by Geotab but SUPERIOR with Kalman-filtered fuel accuracy           ║
║                                                                                ║
║  Geotab Benchmark: $2.26/mile average for Class 8 trucks                       ║
║  Components: Fuel + Maintenance + Tires + Depreciation                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import statistics

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


class CostTrendDirection(str, Enum):
    """Direction of cost trend"""

    IMPROVING = "improving"  # Costs going down
    STABLE = "stable"  # Within ±5%
    DECLINING = "declining"  # Costs going up (bad)


class CostTier(str, Enum):
    """Cost performance tier based on benchmark comparison"""

    ELITE = "elite"  # Below benchmark (excellent)
    GOOD = "good"  # At benchmark
    AVERAGE = "average"  # Slightly above benchmark
    NEEDS_IMPROVEMENT = "needs_improvement"  # Well above benchmark

    @classmethod
    def from_cost_per_mile(cls, cpm: float) -> "CostTier":
        """Classify cost tier based on industry benchmark"""
        benchmark = INDUSTRY_BENCHMARKS["cost_per_mile_total"]
        if cpm < benchmark * 0.95:
            return cls.ELITE
        elif cpm <= benchmark * 1.05:
            return cls.GOOD
        elif cpm <= benchmark * 1.20:
            return cls.AVERAGE
        else:
            return cls.NEEDS_IMPROVEMENT


# Industry benchmarks (source: ATRI, ATA, Geotab)
INDUSTRY_BENCHMARKS = {
    "cost_per_mile_total": 2.26,  # Geotab average for Class 8 trucks
    "fuel_cost_per_mile": 0.65,  # ~29% of total (at $3.50/gal, 5.4 MPG)
    "maintenance_per_mile": 0.18,  # ~8% of total
    "tire_cost_per_mile": 0.07,  # ~3% of total
    "driver_wages_per_mile": 0.70,  # ~31% (not tracked - FYI)
    "insurance_per_mile": 0.12,  # ~5% (not tracked - FYI)
    "depreciation_per_mile": 0.15,  # ~7% of total
}

# Configurable cost estimates (can be overridden per fleet)
DEFAULT_COST_CONFIG = {
    # Maintenance costs based on engine hours
    "maintenance_cost_per_engine_hour": 0.50,  # $0.50/hr average
    "major_service_interval_hours": 2000,  # Major service every 2000 hrs
    "major_service_cost": 1500,  # Major service cost
    # Tire costs
    "tire_cost_per_mile": 0.07,  # Industry average
    "tire_life_miles": 100000,  # Average tire life
    "tire_set_cost": 7000,  # Full set of tires
    # Depreciation (simplified)
    "depreciation_per_mile": 0.15,  # Industry average
    "truck_value": 150000,  # Average truck value
    "useful_life_miles": 1000000,  # Million mile truck
    # Fuel price (configurable)
    "fuel_price_per_gallon": 3.50,  # Default fuel price
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class CostBreakdown:
    """Detailed cost breakdown per mile"""

    fuel_cost_per_mile: float
    maintenance_cost_per_mile: float
    tire_cost_per_mile: float
    depreciation_per_mile: float
    total_cost_per_mile: float

    # Percentages
    fuel_percent: float = 0.0
    maintenance_percent: float = 0.0
    tire_percent: float = 0.0
    depreciation_percent: float = 0.0

    def __post_init__(self):
        """Calculate percentages"""
        if self.total_cost_per_mile > 0:
            self.fuel_percent = (
                self.fuel_cost_per_mile / self.total_cost_per_mile
            ) * 100
            self.maintenance_percent = (
                self.maintenance_cost_per_mile / self.total_cost_per_mile
            ) * 100
            self.tire_percent = (
                self.tire_cost_per_mile / self.total_cost_per_mile
            ) * 100
            self.depreciation_percent = (
                self.depreciation_per_mile / self.total_cost_per_mile
            ) * 100

    def to_dict(self) -> Dict:
        return {
            "fuel_cost_per_mile": round(self.fuel_cost_per_mile, 4),
            "maintenance_cost_per_mile": round(self.maintenance_cost_per_mile, 4),
            "tire_cost_per_mile": round(self.tire_cost_per_mile, 4),
            "depreciation_per_mile": round(self.depreciation_per_mile, 4),
            "total_cost_per_mile": round(self.total_cost_per_mile, 4),
            "breakdown_percentages": self.breakdown_percentages,
        }

    @property
    def breakdown_percentages(self) -> Dict[str, float]:
        """Return breakdown as percentages dict"""
        if self.total_cost_per_mile <= 0:
            return {"fuel": 0, "maintenance": 0, "tires": 0, "depreciation": 0}
        return {
            "fuel": round(self.fuel_percent, 1),
            "maintenance": round(self.maintenance_percent, 1),
            "tires": round(self.tire_percent, 1),
            "depreciation": round(self.depreciation_percent, 1),
        }


@dataclass
class SpeedImpactAnalysis:
    """Analysis of how speed affects fuel costs"""

    current_speed_mph: float
    optimal_speed_mph: float = 55.0
    estimated_mpg: float = 0.0
    optimal_mpg: float = 6.5
    monthly_miles: float = 0.0
    fuel_price: float = 3.50
    monthly_fuel_cost: float = 0.0
    optimal_fuel_cost: float = 0.0
    potential_monthly_savings: float = 0.0
    mpg_loss_percent: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "current_speed_mph": self.current_speed_mph,
            "optimal_speed_mph": self.optimal_speed_mph,
            "estimated_mpg": round(self.estimated_mpg, 2),
            "optimal_mpg": round(self.optimal_mpg, 2),
            "monthly_miles": self.monthly_miles,
            "fuel_price": self.fuel_price,
            "monthly_fuel_cost": round(self.monthly_fuel_cost, 2),
            "optimal_fuel_cost": round(self.optimal_fuel_cost, 2),
            "potential_monthly_savings": round(self.potential_monthly_savings, 2),
            "mpg_loss_percent": round(self.mpg_loss_percent, 1),
        }


@dataclass
class TruckCostAnalysis:
    """Complete cost analysis for a single truck"""

    truck_id: str
    period_start: datetime
    period_end: datetime
    period_days: int

    # Raw metrics
    total_miles: float
    total_fuel_gallons: float
    total_engine_hours: float
    avg_mpg: float

    # Cost breakdown
    cost_breakdown: CostBreakdown

    # Comparisons
    vs_fleet_avg_percent: float = 0.0  # % vs fleet average
    vs_industry_benchmark_percent: float = 0.0  # % vs $2.26 Geotab

    # Cost tier classification
    cost_tier: Optional[CostTier] = None

    # Trend analysis
    trend_direction: CostTrendDirection = CostTrendDirection.STABLE
    trend_percent_change: float = 0.0  # % change vs previous period

    # Potential savings
    potential_savings_per_month: float = 0.0
    savings_recommendations: List[str] = field(default_factory=list)

    # Ranking
    fleet_rank: int = 0
    total_trucks: int = 0

    def __post_init__(self):
        """Auto-calculate cost tier"""
        if self.cost_tier is None and self.cost_breakdown:
            self.cost_tier = CostTier.from_cost_per_mile(
                self.cost_breakdown.total_cost_per_mile
            )

    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
                "days": self.period_days,
            },
            "metrics": {
                "total_miles": round(self.total_miles, 1),
                "total_fuel_gallons": round(self.total_fuel_gallons, 1),
                "total_engine_hours": round(self.total_engine_hours, 1),
                "avg_mpg": round(self.avg_mpg, 2),
            },
            "costs": self.cost_breakdown.to_dict(),
            "comparisons": {
                "vs_fleet_avg_percent": round(self.vs_fleet_avg_percent, 1),
                "vs_industry_benchmark_percent": round(
                    self.vs_industry_benchmark_percent, 1
                ),
                "industry_benchmark": INDUSTRY_BENCHMARKS["cost_per_mile_total"],
            },
            "trend": {
                "direction": self.trend_direction.value,
                "percent_change": round(self.trend_percent_change, 1),
            },
            "savings": {
                "potential_per_month": round(self.potential_savings_per_month, 2),
                "recommendations": self.savings_recommendations,
            },
            "ranking": {
                "position": self.fleet_rank,
                "total_trucks": self.total_trucks,
            },
        }


@dataclass
class FleetCostSummary:
    """Fleet-wide cost summary"""

    period_start: datetime
    period_end: datetime
    period_days: int

    # Fleet totals
    total_trucks: int
    total_miles: float
    total_fuel_gallons: float
    total_fuel_cost: float

    # Average cost per mile
    fleet_avg_cost_per_mile: float
    cost_breakdown: CostBreakdown

    # Comparison to benchmark
    vs_industry_benchmark_percent: float

    # Best/Worst performers
    best_truck: str
    best_cost_per_mile: float
    worst_truck: str
    worst_cost_per_mile: float

    # Potential fleet savings
    total_potential_savings_per_month: float

    # Individual truck analyses
    truck_analyses: List[TruckCostAnalysis] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
                "days": self.period_days,
            },
            "fleet_summary": {
                "total_trucks": self.total_trucks,
                "total_miles": round(self.total_miles, 1),
                "total_fuel_gallons": round(self.total_fuel_gallons, 1),
                "total_fuel_cost": round(self.total_fuel_cost, 2),
            },
            "cost_per_mile": {
                "fleet_average": round(self.fleet_avg_cost_per_mile, 4),
                "breakdown": self.cost_breakdown.to_dict(),
                "vs_industry_benchmark_percent": round(
                    self.vs_industry_benchmark_percent, 1
                ),
                "industry_benchmark": INDUSTRY_BENCHMARKS["cost_per_mile_total"],
            },
            "performance": {
                "best": {
                    "truck_id": self.best_truck,
                    "cost_per_mile": round(self.best_cost_per_mile, 4),
                },
                "worst": {
                    "truck_id": self.worst_truck,
                    "cost_per_mile": round(self.worst_cost_per_mile, 4),
                },
            },
            "savings": {
                "potential_per_month": round(self.total_potential_savings_per_month, 2),
            },
            "trucks": [t.to_dict() for t in self.truck_analyses],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE CLASS
# ═══════════════════════════════════════════════════════════════════════════════


class CostPerMileEngine:
    """
    Cost Per Mile Tracking Engine

    Calculates total cost per mile with detailed breakdown:
    - Fuel Cost (from Kalman-filtered consumption)
    - Maintenance Cost (estimated from engine hours)
    - Tire Cost (industry average)
    - Depreciation (configurable)

    Superior to Geotab because:
    1. Integrates with Kalman filter for accurate fuel tracking
    2. Provides detailed breakdown and comparisons
    3. Generates actionable savings recommendations
    4. Real-time cost tracking (not just monthly reports)
    """

    def __init__(self, db_connection=None, cost_config: Optional[Dict] = None):
        """
        Initialize Cost Per Mile Engine.

        Args:
            db_connection: Database connection for historical queries
            cost_config: Override default cost configuration
        """
        self.db = db_connection
        self.config = {**DEFAULT_COST_CONFIG, **(cost_config or {})}
        logger.info("✅ CostPerMileEngine initialized")

    def calculate_fuel_cost_per_mile(
        self, miles: float, gallons: float, fuel_price: Optional[float] = None
    ) -> float:
        """
        Calculate fuel cost per mile.

        Formula: (Gallons × Price) / Miles = $/mile

        Args:
            miles: Total miles driven
            gallons: Total gallons consumed
            fuel_price: Price per gallon (uses config default if not provided)

        Returns:
            Fuel cost per mile in dollars
        """
        if miles <= 0:
            return 0.0

        price = fuel_price or self.config["fuel_price_per_gallon"]
        total_fuel_cost = gallons * price
        return total_fuel_cost / miles

    def calculate_maintenance_cost_per_mile(
        self, miles: float, engine_hours: float
    ) -> float:
        """
        Estimate maintenance cost per mile based on engine hours.

        This is an ESTIMATE since we don't have actual maintenance records.
        Uses industry averages and engine hours as a proxy.

        Formula: (Engine Hours × Hourly Rate) / Miles = $/mile

        Args:
            miles: Total miles driven
            engine_hours: Total engine hours

        Returns:
            Estimated maintenance cost per mile
        """
        if miles <= 0:
            return 0.0

        # Calculate maintenance cost based on engine hours
        hourly_rate = self.config["maintenance_cost_per_engine_hour"]
        maintenance_cost = engine_hours * hourly_rate

        # Add prorated major service cost
        major_interval = self.config["major_service_interval_hours"]
        major_cost = self.config["major_service_cost"]
        if engine_hours > 0:
            major_services = engine_hours / major_interval
            maintenance_cost += major_services * major_cost

        return maintenance_cost / miles

    def calculate_cost_breakdown(
        self,
        miles: float,
        gallons: float,
        engine_hours: float,
        fuel_price: Optional[float] = None,
    ) -> CostBreakdown:
        """
        Calculate complete cost breakdown per mile.

        Args:
            miles: Total miles driven
            gallons: Total gallons consumed
            engine_hours: Total engine hours
            fuel_price: Optional override for fuel price

        Returns:
            CostBreakdown dataclass with all components
        """
        fuel_cpm = self.calculate_fuel_cost_per_mile(miles, gallons, fuel_price)
        maintenance_cpm = self.calculate_maintenance_cost_per_mile(miles, engine_hours)
        tire_cpm = self.config["tire_cost_per_mile"]
        depreciation_cpm = self.config["depreciation_per_mile"]

        total_cpm = fuel_cpm + maintenance_cpm + tire_cpm + depreciation_cpm

        return CostBreakdown(
            fuel_cost_per_mile=fuel_cpm,
            maintenance_cost_per_mile=maintenance_cpm,
            tire_cost_per_mile=tire_cpm,
            depreciation_per_mile=depreciation_cpm,
            total_cost_per_mile=total_cpm,
        )

    def analyze_truck_costs(
        self,
        truck_id: str,
        period_days: int = 30,
        truck_data: Optional[Dict] = None,
        fleet_avg_cpm: Optional[float] = None,
        previous_period_cpm: Optional[float] = None,
    ) -> TruckCostAnalysis:
        """
        Perform complete cost analysis for a single truck.

        Args:
            truck_id: Truck identifier
            period_days: Number of days to analyze
            truck_data: Pre-fetched truck data (optional, will query if not provided)
            fleet_avg_cpm: Fleet average cost per mile for comparison
            previous_period_cpm: Previous period CPM for trend analysis

        Returns:
            TruckCostAnalysis with complete analysis
        """
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)

        # Get truck data (would normally query database)
        # For now, use provided data or defaults
        data = truck_data or {
            "miles": 0,
            "gallons": 0,
            "engine_hours": 0,
            "avg_mpg": 0,
        }

        miles = data.get("miles", 0)
        gallons = data.get("gallons", 0)
        engine_hours = data.get("engine_hours", 0)
        avg_mpg = data.get("avg_mpg", 0)

        # Calculate cost breakdown
        breakdown = self.calculate_cost_breakdown(miles, gallons, engine_hours)

        # Calculate comparisons
        vs_fleet = 0.0
        if fleet_avg_cpm and fleet_avg_cpm > 0:
            vs_fleet = (
                (breakdown.total_cost_per_mile - fleet_avg_cpm) / fleet_avg_cpm
            ) * 100

        benchmark = INDUSTRY_BENCHMARKS["cost_per_mile_total"]
        vs_benchmark = ((breakdown.total_cost_per_mile - benchmark) / benchmark) * 100

        # Determine trend
        trend_direction = CostTrendDirection.STABLE
        trend_change = 0.0
        if previous_period_cpm and previous_period_cpm > 0:
            trend_change = (
                (breakdown.total_cost_per_mile - previous_period_cpm)
                / previous_period_cpm
            ) * 100
            if trend_change < -5:
                trend_direction = CostTrendDirection.IMPROVING
            elif trend_change > 5:
                trend_direction = CostTrendDirection.DECLINING

        # Calculate potential savings
        savings = 0.0
        recommendations = []

        # If above fleet average, calculate savings to reach average
        if fleet_avg_cpm and breakdown.total_cost_per_mile > fleet_avg_cpm:
            monthly_miles = (miles / period_days) * 30
            savings = (breakdown.total_cost_per_mile - fleet_avg_cpm) * monthly_miles
            recommendations.append(
                f"Bringing CPM to fleet average would save ${savings:.2f}/month"
            )

        # MPG-based recommendation
        if avg_mpg > 0 and avg_mpg < 6.0:  # Below ideal
            target_mpg = 6.0
            current_fuel_cost = gallons * self.config["fuel_price_per_gallon"]
            target_gallons = miles / target_mpg if target_mpg > 0 else gallons
            target_fuel_cost = target_gallons * self.config["fuel_price_per_gallon"]
            mpg_savings = current_fuel_cost - target_fuel_cost
            if mpg_savings > 0:
                monthly_savings = (mpg_savings / period_days) * 30
                recommendations.append(
                    f"Improving MPG from {avg_mpg:.1f} to {target_mpg:.1f} would save ${monthly_savings:.2f}/month in fuel"
                )
                savings += monthly_savings

        return TruckCostAnalysis(
            truck_id=truck_id,
            period_start=period_start,
            period_end=now,
            period_days=period_days,
            total_miles=miles,
            total_fuel_gallons=gallons,
            total_engine_hours=engine_hours,
            avg_mpg=avg_mpg,
            cost_breakdown=breakdown,
            vs_fleet_avg_percent=vs_fleet,
            vs_industry_benchmark_percent=vs_benchmark,
            trend_direction=trend_direction,
            trend_percent_change=trend_change,
            potential_savings_per_month=savings,
            savings_recommendations=recommendations,
        )

    def analyze_fleet_costs(
        self, trucks_data: List[Dict], period_days: int = 30
    ) -> FleetCostSummary:
        """
        Perform complete cost analysis for entire fleet.

        Args:
            trucks_data: List of truck data dictionaries with:
                - truck_id: str
                - miles: float
                - gallons: float
                - engine_hours: float
                - avg_mpg: float
            period_days: Number of days to analyze

        Returns:
            FleetCostSummary with fleet-wide analysis and individual truck breakdowns
        """
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)

        if not trucks_data:
            logger.warning("No trucks data provided for fleet cost analysis")
            # Return a default empty summary instead of None
            return FleetCostSummary(
                period_start=period_start,
                period_end=now,
                period_days=period_days,
                total_trucks=0,
                total_miles=0,
                total_fuel_gallons=0,
                total_fuel_cost=0,
                fleet_avg_cost_per_mile=0,
                cost_breakdown=CostBreakdown(0, 0, 0, 0, 0),
                vs_industry_benchmark_percent=0,
                best_truck="",
                best_cost_per_mile=0,
                worst_truck="",
                worst_cost_per_mile=0,
                total_potential_savings_per_month=0,
                truck_analyses=[],
            )

        # Calculate fleet totals
        total_miles = sum(t.get("miles", 0) for t in trucks_data)
        total_gallons = sum(t.get("gallons", 0) for t in trucks_data)
        total_engine_hours = sum(t.get("engine_hours", 0) for t in trucks_data)
        total_fuel_cost = total_gallons * self.config["fuel_price_per_gallon"]

        # Calculate fleet average cost per mile
        fleet_breakdown = self.calculate_cost_breakdown(
            total_miles, total_gallons, total_engine_hours
        )

        # Analyze each truck
        truck_analyses = []
        for truck in trucks_data:
            analysis = self.analyze_truck_costs(
                truck_id=truck.get("truck_id", "Unknown"),
                period_days=period_days,
                truck_data=truck,
                fleet_avg_cpm=fleet_breakdown.total_cost_per_mile,
            )
            truck_analyses.append(analysis)

        # Sort by cost per mile and assign rankings
        truck_analyses.sort(key=lambda x: x.cost_breakdown.total_cost_per_mile)
        for i, analysis in enumerate(truck_analyses):
            analysis.fleet_rank = i + 1
            analysis.total_trucks = len(truck_analyses)

        # Find best and worst performers
        best = truck_analyses[0] if truck_analyses else None
        worst = truck_analyses[-1] if truck_analyses else None

        # Calculate benchmark comparison
        benchmark = INDUSTRY_BENCHMARKS["cost_per_mile_total"]
        vs_benchmark = (
            (fleet_breakdown.total_cost_per_mile - benchmark) / benchmark
        ) * 100

        # Calculate total potential savings
        total_savings = sum(t.potential_savings_per_month for t in truck_analyses)

        return FleetCostSummary(
            period_start=period_start,
            period_end=now,
            period_days=period_days,
            total_trucks=len(trucks_data),
            total_miles=total_miles,
            total_fuel_gallons=total_gallons,
            total_fuel_cost=total_fuel_cost,
            fleet_avg_cost_per_mile=fleet_breakdown.total_cost_per_mile,
            cost_breakdown=fleet_breakdown,
            vs_industry_benchmark_percent=vs_benchmark,
            best_truck=best.truck_id if best else "",
            best_cost_per_mile=best.cost_breakdown.total_cost_per_mile if best else 0,
            worst_truck=worst.truck_id if worst else "",
            worst_cost_per_mile=(
                worst.cost_breakdown.total_cost_per_mile if worst else 0
            ),
            total_potential_savings_per_month=total_savings,
            truck_analyses=truck_analyses,
        )

    def get_cost_history(
        self,
        truck_id: Optional[str] = None,
        period_days: int = 90,
        granularity: str = "week",
    ) -> List[Dict]:
        """
        Get historical cost per mile data for trending charts.

        Args:
            truck_id: Specific truck or None for fleet average
            period_days: How far back to look
            granularity: "day", "week", or "month"

        Returns:
            List of data points for charting
        """
        # This would query historical data from database
        # For now, return structure that frontend expects
        return [
            {
                "date": "2025-06-01",
                "cost_per_mile": 2.15,
                "fuel_cpm": 0.62,
                "maintenance_cpm": 0.16,
                "tire_cpm": 0.07,
                "depreciation_cpm": 0.15,
            }
            # ... more data points
        ]

    def generate_cost_report(
        self, trucks_data: List[Dict], period_days: int = 30
    ) -> Dict:
        """
        Generate comprehensive cost report for dashboard.

        This is the main method to call from API endpoints.

        Returns:
            Dictionary with all cost data for frontend display
        """
        summary = self.analyze_fleet_costs(trucks_data, period_days)

        if not summary:
            return {"status": "error", "message": "No data available for cost analysis"}

        return {
            "status": "success",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": summary.to_dict(),
        }

    def calculate_speed_impact(
        self,
        current_speed_mph: float,
        monthly_miles: float,
        fuel_price: Optional[float] = None,
    ) -> SpeedImpactAnalysis:
        """
        Calculate how speed affects fuel costs.

        Based on DOE research: MPG drops ~1% for every 1 MPH above 50.

        Args:
            current_speed_mph: Current average speed
            monthly_miles: Monthly miles driven
            fuel_price: Optional fuel price override

        Returns:
            SpeedImpactAnalysis with savings potential
        """
        fuel_price = fuel_price or self.config["fuel_price_per_gallon"]
        optimal_speed = 55.0
        optimal_mpg = 6.5  # Class 8 optimal at 55 mph

        # Calculate MPG loss due to speed
        # Every 1 MPH above 50 = ~1% fuel economy drop
        speed_penalty = max(0, current_speed_mph - 50) * 0.01
        estimated_mpg = optimal_mpg * (1 - speed_penalty)
        estimated_mpg = max(4.0, estimated_mpg)  # Floor at 4 MPG

        # Calculate costs
        current_gallons = monthly_miles / estimated_mpg
        optimal_gallons = monthly_miles / optimal_mpg

        current_cost = current_gallons * fuel_price
        optimal_cost = optimal_gallons * fuel_price
        savings = current_cost - optimal_cost

        mpg_loss = ((optimal_mpg - estimated_mpg) / optimal_mpg) * 100

        return SpeedImpactAnalysis(
            current_speed_mph=current_speed_mph,
            optimal_speed_mph=optimal_speed,
            estimated_mpg=estimated_mpg,
            optimal_mpg=optimal_mpg,
            monthly_miles=monthly_miles,
            fuel_price=fuel_price,
            monthly_fuel_cost=current_cost,
            optimal_fuel_cost=optimal_cost,
            potential_monthly_savings=max(0, savings),
            mpg_loss_percent=mpg_loss,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def calculate_roi_from_mpg_improvement(
    current_mpg: float,
    target_mpg: float,
    monthly_miles: float,
    fuel_price: float = 3.50,
) -> Dict:
    """
    Calculate ROI from improving MPG.

    Args:
        current_mpg: Current fuel economy
        target_mpg: Target fuel economy
        monthly_miles: Average monthly miles
        fuel_price: Fuel price per gallon

    Returns:
        ROI calculation dictionary
    """
    if current_mpg <= 0 or target_mpg <= 0:
        return {"error": "Invalid MPG values"}

    current_gallons = monthly_miles / current_mpg
    target_gallons = monthly_miles / target_mpg
    gallons_saved = current_gallons - target_gallons

    monthly_savings = gallons_saved * fuel_price
    annual_savings = monthly_savings * 12

    return {
        "current_mpg": round(current_mpg, 2),
        "target_mpg": round(target_mpg, 2),
        "mpg_improvement": round(target_mpg - current_mpg, 2),
        "monthly_miles": round(monthly_miles, 0),
        "gallons_saved_per_month": round(gallons_saved, 1),
        "monthly_savings": round(monthly_savings, 2),
        "annual_savings": round(annual_savings, 2),
        "fuel_price_used": fuel_price,
    }


def calculate_speed_cost_impact(
    avg_speed_mph: float,
    monthly_miles: float,
    base_mpg_at_60: float = 6.5,
    fuel_price: float = 3.50,
) -> Dict:
    """
    Calculate cost impact of speeding based on Geotab research:
    "Every 5 mph over 60 reduces fuel efficiency by ~0.7 MPG"

    Args:
        avg_speed_mph: Average highway speed
        monthly_miles: Monthly miles driven
        base_mpg_at_60: MPG at 60 mph baseline
        fuel_price: Fuel price per gallon

    Returns:
        Cost impact analysis
    """
    # Calculate MPG penalty for speeding
    if avg_speed_mph <= 60:
        mph_over = 0
        mpg_penalty = 0
    else:
        mph_over = avg_speed_mph - 60
        # 0.7 MPG loss per 5 mph over 60
        mpg_penalty = (mph_over / 5) * 0.7

    current_mpg = base_mpg_at_60 - mpg_penalty
    current_mpg = max(current_mpg, 3.0)  # Minimum reasonable MPG

    # Calculate fuel costs
    current_gallons = monthly_miles / current_mpg
    optimal_gallons = monthly_miles / base_mpg_at_60
    wasted_gallons = current_gallons - optimal_gallons

    monthly_cost_impact = wasted_gallons * fuel_price
    annual_cost_impact = monthly_cost_impact * 12

    return {
        "avg_speed_mph": round(avg_speed_mph, 1),
        "optimal_speed_mph": 60,
        "mph_over_optimal": round(mph_over, 1),
        "mpg_penalty": round(mpg_penalty, 2),
        "current_mpg": round(current_mpg, 2),
        "optimal_mpg": round(base_mpg_at_60, 2),
        "wasted_gallons_per_month": round(wasted_gallons, 1),
        "monthly_cost_impact": round(monthly_cost_impact, 2),
        "annual_cost_impact": round(annual_cost_impact, 2),
        "recommendation": (
            f"Reducing speed from {avg_speed_mph:.0f} to 62 mph would save ${monthly_cost_impact:.2f}/month"
            if mph_over > 2
            else "Speed is within optimal range"
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test the engine
    engine = CostPerMileEngine()

    # Sample truck data
    test_trucks = [
        {
            "truck_id": "JC1282",
            "miles": 8500,
            "gallons": 1400,
            "engine_hours": 280,
            "avg_mpg": 6.07,
        },
        {
            "truck_id": "RT9127",
            "miles": 7200,
            "gallons": 1300,
            "engine_hours": 250,
            "avg_mpg": 5.54,
        },
        {
            "truck_id": "FM9838",
            "miles": 6800,
            "gallons": 1150,
            "engine_hours": 230,
            "avg_mpg": 5.91,
        },
        {
            "truck_id": "SG5760",
            "miles": 9100,
            "gallons": 1600,
            "engine_hours": 300,
            "avg_mpg": 5.69,
        },
    ]

    # Generate fleet report
    report = engine.generate_cost_report(test_trucks, period_days=30)

    import json

    print("=" * 80)
    print("COST PER MILE ANALYSIS REPORT")
    print("=" * 80)
    print(json.dumps(report, indent=2))

    # Test speed impact
    print("\n" + "=" * 80)
    print("SPEED COST IMPACT ANALYSIS")
    print("=" * 80)
    speed_impact = calculate_speed_cost_impact(
        avg_speed_mph=68, monthly_miles=8000, base_mpg_at_60=6.5, fuel_price=3.50
    )
    print(json.dumps(speed_impact, indent=2))

    # Test MPG improvement ROI
    print("\n" + "=" * 80)
    print("MPG IMPROVEMENT ROI")
    print("=" * 80)
    roi = calculate_roi_from_mpg_improvement(
        current_mpg=5.5, target_mpg=6.2, monthly_miles=8000, fuel_price=3.50
    )
    print(json.dumps(roi, indent=2))
