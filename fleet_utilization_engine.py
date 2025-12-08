"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    FLEET UTILIZATION ENGINE                                    ║
║                         Fuel Copilot v4.0                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Purpose: Track fleet utilization rate and identify optimization opportunities ║
║  Inspired by Geotab's 95% utilization target                                   ║
║                                                                                ║
║  Metrics:                                                                      ║
║  - Utilization Rate = Productive Hours / Available Hours                       ║
║  - Driving Hours vs Idle Hours vs Engine Off                                   ║
║  - Asset utilization ranking and recommendations                               ║
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

class TruckActivityState(str, Enum):
    """Activity states for utilization tracking"""
    DRIVING = "driving"              # Moving at > 5 mph
    PRODUCTIVE_IDLE = "productive_idle"  # Idle at customer/terminal (loading/unloading)
    NON_PRODUCTIVE_IDLE = "non_productive_idle"  # Idle elsewhere
    ENGINE_OFF = "engine_off"        # Engine off / no data


class UtilizationTier(str, Enum):
    """Utilization tier classification"""
    EXCELLENT = "excellent"  # 90%+ utilization
    GOOD = "good"           # 80-90%
    FAIR = "fair"           # 70-80%
    POOR = "poor"           # 60-70%
    CRITICAL = "critical"   # <60%


# Industry benchmarks (Geotab standard)
UTILIZATION_BENCHMARKS = {
    "target_utilization": 0.95,      # 95% target (Geotab)
    "good_utilization": 0.85,        # 85% = good
    "minimum_acceptable": 0.70,      # 70% = minimum acceptable
    "underutilized_threshold": 0.60, # <60% = severely underutilized
}

# Typical work week configuration
WORK_SCHEDULE = {
    "work_days_per_week": 6,         # Mon-Sat typical for trucking
    "work_hours_per_day": 14,        # HOS max driving + on-duty
    "break_hours_per_day": 2,        # Mandated breaks
    "productive_hours_per_day": 12,  # Realistic productive hours
}

# Opportunity cost for downtime
COST_CONFIG = {
    "revenue_per_mile": 2.50,        # Average trucking revenue
    "avg_mph_when_moving": 50,       # Average speed when driving
    "opportunity_cost_per_hour": 125, # $125/hr lost revenue when not moving
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class TimeBreakdown:
    """Breakdown of time by activity state"""
    driving_hours: float
    productive_idle_hours: float
    non_productive_idle_hours: float
    engine_off_hours: float
    total_hours: float
    
    @property
    def total_idle_hours(self) -> float:
        return self.productive_idle_hours + self.non_productive_idle_hours
    
    @property
    def productive_hours(self) -> float:
        """Driving + productive idle = productive time"""
        return self.driving_hours + self.productive_idle_hours
    
    @property
    def non_productive_hours(self) -> float:
        """Non-productive idle + engine off = wasted time"""
        return self.non_productive_idle_hours + self.engine_off_hours
    
    def to_dict(self) -> Dict:
        return {
            "driving_hours": round(self.driving_hours, 1),
            "productive_idle_hours": round(self.productive_idle_hours, 1),
            "non_productive_idle_hours": round(self.non_productive_idle_hours, 1),
            "engine_off_hours": round(self.engine_off_hours, 1),
            "total_hours": round(self.total_hours, 1),
            "summary": {
                "productive_hours": round(self.productive_hours, 1),
                "non_productive_hours": round(self.non_productive_hours, 1),
                "total_idle_hours": round(self.total_idle_hours, 1),
            },
            "percentages": {
                "driving": round((self.driving_hours / self.total_hours * 100) if self.total_hours > 0 else 0, 1),
                "productive_idle": round((self.productive_idle_hours / self.total_hours * 100) if self.total_hours > 0 else 0, 1),
                "non_productive_idle": round((self.non_productive_idle_hours / self.total_hours * 100) if self.total_hours > 0 else 0, 1),
                "engine_off": round((self.engine_off_hours / self.total_hours * 100) if self.total_hours > 0 else 0, 1),
            }
        }


@dataclass
class UtilizationMetrics:
    """Utilization metrics for analysis"""
    utilization_rate: float          # Primary metric (0-1)
    driving_utilization: float       # Driving hours / available hours
    productive_utilization: float    # (Driving + Prod Idle) / available hours
    
    # Comparisons
    vs_target_percent: float         # % difference from 95% target
    vs_fleet_avg_percent: float      # % difference from fleet average
    
    # Classification
    tier: UtilizationTier
    
    # Opportunity cost
    lost_revenue_per_period: float   # $ lost due to underutilization
    
    def to_dict(self) -> Dict:
        return {
            "utilization_rate": round(self.utilization_rate * 100, 1),
            "driving_utilization": round(self.driving_utilization * 100, 1),
            "productive_utilization": round(self.productive_utilization * 100, 1),
            "vs_target_percent": round(self.vs_target_percent, 1),
            "vs_fleet_avg_percent": round(self.vs_fleet_avg_percent, 1),
            "tier": self.tier.value,
            "lost_revenue_per_period": round(self.lost_revenue_per_period, 2),
        }


@dataclass
class TruckUtilizationAnalysis:
    """Complete utilization analysis for a single truck"""
    truck_id: str
    period_start: datetime
    period_end: datetime
    period_days: int
    
    # Time breakdown
    time_breakdown: TimeBreakdown
    
    # Utilization metrics
    metrics: UtilizationMetrics
    
    # Ranking
    fleet_rank: int = 0
    total_trucks: int = 0
    
    # Recommendations
    recommendations: List[str] = field(default_factory=list)
    
    # Downtime events (significant periods of non-utilization)
    significant_downtimes: List[Dict] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "truck_id": self.truck_id,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
                "days": self.period_days,
            },
            "time_breakdown": self.time_breakdown.to_dict(),
            "metrics": self.metrics.to_dict(),
            "ranking": {
                "position": self.fleet_rank,
                "total_trucks": self.total_trucks,
            },
            "recommendations": self.recommendations,
            "significant_downtimes": self.significant_downtimes,
        }


@dataclass
class FleetUtilizationSummary:
    """Fleet-wide utilization summary"""
    period_start: datetime
    period_end: datetime
    period_days: int
    
    # Fleet totals
    total_trucks: int
    total_driving_hours: float
    total_idle_hours: float
    
    # Fleet averages
    fleet_avg_utilization: float
    fleet_time_breakdown: TimeBreakdown
    
    # Tier distribution
    tier_distribution: Dict[str, int]
    
    # Best/Worst performers
    best_truck: str
    best_utilization: float
    worst_truck: str
    worst_utilization: float
    
    # Underutilized trucks (candidates for action)
    underutilized_trucks: List[str]
    
    # Financial impact
    total_lost_revenue: float
    
    # Individual analyses
    truck_analyses: List[TruckUtilizationAnalysis] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return {
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
                "days": self.period_days,
            },
            "fleet_summary": {
                "total_trucks": self.total_trucks,
                "total_driving_hours": round(self.total_driving_hours, 1),
                "total_idle_hours": round(self.total_idle_hours, 1),
            },
            "utilization": {
                "fleet_average": round(self.fleet_avg_utilization * 100, 1),
                "target": round(UTILIZATION_BENCHMARKS["target_utilization"] * 100, 1),
                "vs_target": round((self.fleet_avg_utilization - UTILIZATION_BENCHMARKS["target_utilization"]) * 100, 1),
                "time_breakdown": self.fleet_time_breakdown.to_dict(),
            },
            "tier_distribution": self.tier_distribution,
            "performance": {
                "best": {
                    "truck_id": self.best_truck,
                    "utilization": round(self.best_utilization * 100, 1),
                },
                "worst": {
                    "truck_id": self.worst_truck,
                    "utilization": round(self.worst_utilization * 100, 1),
                },
            },
            "underutilized_trucks": self.underutilized_trucks,
            "financial_impact": {
                "total_lost_revenue": round(self.total_lost_revenue, 2),
                "potential_savings_message": f"Improving underutilized trucks could recover ${self.total_lost_revenue:,.2f}/month"
            },
            "trucks": [t.to_dict() for t in self.truck_analyses],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class FleetUtilizationEngine:
    """
    Fleet Utilization Tracking Engine
    
    Calculates utilization rate and identifies optimization opportunities:
    - Tracks driving vs idle vs engine off time
    - Classifies idle as productive or non-productive
    - Identifies underutilized assets
    - Provides actionable recommendations
    
    Superior to basic Geotab utilization because:
    1. Classifies idle as productive vs non-productive
    2. Calculates financial impact of underutilization
    3. Provides specific recommendations
    4. Integrates with geofences for context-aware analysis
    """
    
    def __init__(
        self,
        db_connection=None,
        productive_locations: List[Dict] = None,
        work_schedule: Dict = None
    ):
        """
        Initialize Fleet Utilization Engine.
        
        Args:
            db_connection: Database connection for historical queries
            productive_locations: List of geofences considered productive
                                 (customer locations, terminals, etc.)
            work_schedule: Override default work schedule
        """
        self.db = db_connection
        self.productive_locations = productive_locations or []
        self.schedule = {**WORK_SCHEDULE, **(work_schedule or {})}
        logger.info("✅ FleetUtilizationEngine initialized")
    
    def classify_activity_state(
        self,
        speed: float,
        rpm: int,
        location: Tuple[float, float] = None
    ) -> TruckActivityState:
        """
        Classify truck activity state based on telemetry.
        
        Args:
            speed: Current speed in mph
            rpm: Engine RPM
            location: Optional (lat, lon) for geofence matching
        
        Returns:
            TruckActivityState enum
        """
        # Engine off
        if rpm == 0 or rpm is None:
            return TruckActivityState.ENGINE_OFF
        
        # Moving
        if speed > 5:
            return TruckActivityState.DRIVING
        
        # Idle - determine if productive
        if location and self._is_productive_location(location):
            return TruckActivityState.PRODUCTIVE_IDLE
        
        return TruckActivityState.NON_PRODUCTIVE_IDLE
    
    def _is_productive_location(self, location: Tuple[float, float]) -> bool:
        """
        Check if location is within a productive geofence.
        
        Args:
            location: (latitude, longitude)
        
        Returns:
            True if within productive location
        """
        # For now, assume all idle at customer locations is productive
        # In full implementation, would check against geofence database
        # TODO: Integrate with geofence system
        return False  # Conservative default
    
    def calculate_available_hours(self, period_days: int) -> float:
        """
        Calculate available hours for a period based on work schedule.
        
        Args:
            period_days: Number of days in period
        
        Returns:
            Total available hours
        """
        work_days = period_days * (self.schedule["work_days_per_week"] / 7)
        available_hours = work_days * self.schedule["productive_hours_per_day"]
        return available_hours
    
    def classify_utilization_tier(self, utilization_rate: float) -> UtilizationTier:
        """
        Classify utilization into tier.
        
        Args:
            utilization_rate: Utilization rate (0-1)
        
        Returns:
            UtilizationTier enum
        """
        if utilization_rate >= 0.90:
            return UtilizationTier.EXCELLENT
        elif utilization_rate >= 0.80:
            return UtilizationTier.GOOD
        elif utilization_rate >= 0.70:
            return UtilizationTier.FAIR
        elif utilization_rate >= 0.60:
            return UtilizationTier.POOR
        else:
            return UtilizationTier.CRITICAL
    
    def calculate_lost_revenue(
        self,
        available_hours: float,
        productive_hours: float
    ) -> float:
        """
        Calculate revenue lost due to underutilization.
        
        Args:
            available_hours: Total available hours
            productive_hours: Hours actually productive
        
        Returns:
            Lost revenue in dollars
        """
        unused_hours = available_hours - productive_hours
        if unused_hours <= 0:
            return 0.0
        
        return unused_hours * COST_CONFIG["opportunity_cost_per_hour"]
    
    def generate_recommendations(
        self,
        analysis: TruckUtilizationAnalysis
    ) -> List[str]:
        """
        Generate actionable recommendations based on analysis.
        
        Args:
            analysis: Truck utilization analysis
        
        Returns:
            List of recommendation strings
        """
        recommendations = []
        time_breakdown = analysis.time_breakdown
        metrics = analysis.metrics
        
        # Check driving percentage
        driving_pct = time_breakdown.driving_hours / time_breakdown.total_hours if time_breakdown.total_hours > 0 else 0
        if driving_pct < 0.40:
            recommendations.append(
                f"Driving time is only {driving_pct*100:.0f}% - consider route optimization or additional loads"
            )
        
        # Check non-productive idle
        np_idle_pct = time_breakdown.non_productive_idle_hours / time_breakdown.total_hours if time_breakdown.total_hours > 0 else 0
        if np_idle_pct > 0.15:
            recommendations.append(
                f"Non-productive idle is {np_idle_pct*100:.0f}% - investigate causes and reduce unnecessary idling"
            )
        
        # Check utilization tier
        if metrics.tier == UtilizationTier.CRITICAL:
            recommendations.append(
                "CRITICAL: Utilization under 60% - evaluate if truck should be reassigned or fleet reduced"
            )
        elif metrics.tier == UtilizationTier.POOR:
            recommendations.append(
                "Poor utilization - consider adding routes or consolidating with other assets"
            )
        
        # Check vs target
        if metrics.vs_target_percent < -15:
            recommendations.append(
                f"Utilization is {abs(metrics.vs_target_percent):.0f}% below target - review scheduling efficiency"
            )
        
        # If no issues found
        if not recommendations:
            if metrics.tier == UtilizationTier.EXCELLENT:
                recommendations.append("Excellent utilization! Maintain current operational practices.")
            else:
                recommendations.append("Utilization is acceptable. Monitor for optimization opportunities.")
        
        return recommendations
    
    def analyze_truck_utilization(
        self,
        truck_id: str,
        period_days: int = 7,
        truck_data: Dict = None,
        fleet_avg_utilization: float = None
    ) -> TruckUtilizationAnalysis:
        """
        Perform complete utilization analysis for a single truck.
        
        Args:
            truck_id: Truck identifier
            period_days: Number of days to analyze
            truck_data: Pre-fetched truck data with time breakdown
            fleet_avg_utilization: Fleet average for comparison
        
        Returns:
            TruckUtilizationAnalysis with complete analysis
        """
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)
        
        # Get truck data (would normally query database)
        data = truck_data or {
            "driving_hours": 0,
            "productive_idle_hours": 0,
            "non_productive_idle_hours": 0,
            "engine_off_hours": 0,
        }
        
        # Calculate total hours (should match period)
        total_hours = period_days * 24
        
        # Create time breakdown
        time_breakdown = TimeBreakdown(
            driving_hours=data.get("driving_hours", 0),
            productive_idle_hours=data.get("productive_idle_hours", 0),
            non_productive_idle_hours=data.get("non_productive_idle_hours", 0),
            engine_off_hours=data.get("engine_off_hours", total_hours),  # Default to all off
            total_hours=total_hours,
        )
        
        # Calculate available hours based on work schedule
        available_hours = self.calculate_available_hours(period_days)
        
        # Calculate utilization rates
        driving_utilization = time_breakdown.driving_hours / available_hours if available_hours > 0 else 0
        productive_utilization = time_breakdown.productive_hours / available_hours if available_hours > 0 else 0
        
        # Primary utilization rate = productive time / available time
        utilization_rate = min(productive_utilization, 1.0)  # Cap at 100%
        
        # Calculate vs target and fleet avg
        target = UTILIZATION_BENCHMARKS["target_utilization"]
        vs_target = (utilization_rate - target) * 100
        
        vs_fleet = 0.0
        if fleet_avg_utilization and fleet_avg_utilization > 0:
            vs_fleet = (utilization_rate - fleet_avg_utilization) * 100
        
        # Classify tier
        tier = self.classify_utilization_tier(utilization_rate)
        
        # Calculate lost revenue
        lost_revenue = self.calculate_lost_revenue(available_hours, time_breakdown.productive_hours)
        
        # Create metrics
        metrics = UtilizationMetrics(
            utilization_rate=utilization_rate,
            driving_utilization=driving_utilization,
            productive_utilization=productive_utilization,
            vs_target_percent=vs_target,
            vs_fleet_avg_percent=vs_fleet,
            tier=tier,
            lost_revenue_per_period=lost_revenue,
        )
        
        # Create analysis object
        analysis = TruckUtilizationAnalysis(
            truck_id=truck_id,
            period_start=period_start,
            period_end=now,
            period_days=period_days,
            time_breakdown=time_breakdown,
            metrics=metrics,
        )
        
        # Generate recommendations
        analysis.recommendations = self.generate_recommendations(analysis)
        
        return analysis
    
    def analyze_fleet_utilization(
        self,
        trucks_data: List[Dict],
        period_days: int = 7
    ) -> FleetUtilizationSummary:
        """
        Perform complete utilization analysis for entire fleet.
        
        Args:
            trucks_data: List of truck data dictionaries with time breakdowns
            period_days: Number of days to analyze
        
        Returns:
            FleetUtilizationSummary with fleet-wide analysis
        """
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=period_days)
        
        if not trucks_data:
            logger.warning("No trucks data provided for fleet utilization analysis")
            return None
        
        # Calculate fleet totals
        total_driving = sum(t.get("driving_hours", 0) for t in trucks_data)
        total_prod_idle = sum(t.get("productive_idle_hours", 0) for t in trucks_data)
        total_np_idle = sum(t.get("non_productive_idle_hours", 0) for t in trucks_data)
        total_off = sum(t.get("engine_off_hours", 0) for t in trucks_data)
        total_hours = period_days * 24 * len(trucks_data)
        
        fleet_breakdown = TimeBreakdown(
            driving_hours=total_driving,
            productive_idle_hours=total_prod_idle,
            non_productive_idle_hours=total_np_idle,
            engine_off_hours=total_off,
            total_hours=total_hours,
        )
        
        # Calculate fleet average utilization
        available_hours = self.calculate_available_hours(period_days)
        productive_hours = fleet_breakdown.productive_hours
        fleet_avg_utilization = productive_hours / (available_hours * len(trucks_data)) if available_hours > 0 else 0
        
        # Analyze each truck
        truck_analyses = []
        for truck in trucks_data:
            analysis = self.analyze_truck_utilization(
                truck_id=truck.get("truck_id", "Unknown"),
                period_days=period_days,
                truck_data=truck,
                fleet_avg_utilization=fleet_avg_utilization,
            )
            truck_analyses.append(analysis)
        
        # Sort by utilization and assign rankings
        truck_analyses.sort(key=lambda x: x.metrics.utilization_rate, reverse=True)
        for i, analysis in enumerate(truck_analyses):
            analysis.fleet_rank = i + 1
            analysis.total_trucks = len(truck_analyses)
        
        # Calculate tier distribution
        tier_distribution = {tier.value: 0 for tier in UtilizationTier}
        for analysis in truck_analyses:
            tier_distribution[analysis.metrics.tier.value] += 1
        
        # Find best and worst
        best = truck_analyses[0] if truck_analyses else None
        worst = truck_analyses[-1] if truck_analyses else None
        
        # Identify underutilized trucks
        threshold = UTILIZATION_BENCHMARKS["underutilized_threshold"]
        underutilized = [
            a.truck_id for a in truck_analyses 
            if a.metrics.utilization_rate < threshold
        ]
        
        # Calculate total lost revenue
        total_lost = sum(a.metrics.lost_revenue_per_period for a in truck_analyses)
        
        return FleetUtilizationSummary(
            period_start=period_start,
            period_end=now,
            period_days=period_days,
            total_trucks=len(trucks_data),
            total_driving_hours=total_driving,
            total_idle_hours=total_prod_idle + total_np_idle,
            fleet_avg_utilization=fleet_avg_utilization,
            fleet_time_breakdown=fleet_breakdown,
            tier_distribution=tier_distribution,
            best_truck=best.truck_id if best else "",
            best_utilization=best.metrics.utilization_rate if best else 0,
            worst_truck=worst.truck_id if worst else "",
            worst_utilization=worst.metrics.utilization_rate if worst else 0,
            underutilized_trucks=underutilized,
            total_lost_revenue=total_lost,
            truck_analyses=truck_analyses,
        )
    
    def generate_utilization_report(
        self,
        trucks_data: List[Dict],
        period_days: int = 7
    ) -> Dict:
        """
        Generate comprehensive utilization report for dashboard.
        
        This is the main method to call from API endpoints.
        
        Returns:
            Dictionary with all utilization data for frontend display
        """
        summary = self.analyze_fleet_utilization(trucks_data, period_days)
        
        if not summary:
            return {
                "status": "error",
                "message": "No data available for utilization analysis"
            }
        
        return {
            "status": "success",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": summary.to_dict(),
        }
    
    def identify_fleet_optimization_opportunities(
        self,
        summary: FleetUtilizationSummary
    ) -> Dict:
        """
        Identify fleet-level optimization opportunities.
        
        Args:
            summary: Fleet utilization summary
        
        Returns:
            Dictionary with optimization recommendations
        """
        opportunities = {
            "fleet_size_recommendation": None,
            "reassignment_candidates": [],
            "efficiency_improvements": [],
            "estimated_monthly_savings": 0,
        }
        
        # Check if fleet is oversized
        underutilized_count = len(summary.underutilized_trucks)
        if underutilized_count >= 3:
            opportunities["fleet_size_recommendation"] = {
                "action": "Consider reducing fleet size",
                "trucks_to_review": underutilized_count,
                "reasoning": f"{underutilized_count} trucks are below 60% utilization",
            }
        
        # Identify reassignment candidates
        for analysis in summary.truck_analyses:
            if analysis.metrics.tier in [UtilizationTier.CRITICAL, UtilizationTier.POOR]:
                opportunities["reassignment_candidates"].append({
                    "truck_id": analysis.truck_id,
                    "utilization": round(analysis.metrics.utilization_rate * 100, 1),
                    "lost_revenue": round(analysis.metrics.lost_revenue_per_period, 2),
                    "recommendation": analysis.recommendations[0] if analysis.recommendations else "Review assignment",
                })
        
        # Calculate potential savings
        opportunities["estimated_monthly_savings"] = round(summary.total_lost_revenue, 2)
        
        return opportunities


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    # Test the engine
    engine = FleetUtilizationEngine()
    
    # Sample truck data (7-day period)
    # Total available hours for 7 days with 6-day work week = 7 * (6/7) * 12 = 72 hours
    test_trucks = [
        {
            "truck_id": "JC1282",
            "driving_hours": 52,
            "productive_idle_hours": 12,
            "non_productive_idle_hours": 8,
            "engine_off_hours": 96,  # 168 - 72 = 96 off hours
        },
        {
            "truck_id": "RT9127",
            "driving_hours": 48,
            "productive_idle_hours": 10,
            "non_productive_idle_hours": 15,
            "engine_off_hours": 95,
        },
        {
            "truck_id": "FM9838",
            "driving_hours": 35,
            "productive_idle_hours": 8,
            "non_productive_idle_hours": 20,
            "engine_off_hours": 105,
        },
        {
            "truck_id": "SG5760",
            "driving_hours": 60,
            "productive_idle_hours": 15,
            "non_productive_idle_hours": 5,
            "engine_off_hours": 88,
        },
    ]
    
    # Generate fleet report
    report = engine.generate_utilization_report(test_trucks, period_days=7)
    
    import json
    print("=" * 80)
    print("FLEET UTILIZATION ANALYSIS REPORT")
    print("=" * 80)
    print(json.dumps(report, indent=2))
    
    # Get optimization opportunities
    if report["status"] == "success":
        summary = engine.analyze_fleet_utilization(test_trucks, period_days=7)
        opportunities = engine.identify_fleet_optimization_opportunities(summary)
        print("\n" + "=" * 80)
        print("OPTIMIZATION OPPORTUNITIES")
        print("=" * 80)
        print(json.dumps(opportunities, indent=2))
