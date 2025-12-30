"""
AI Driver Coaching System
=========================

Analyzes driver behavior and provides personalized coaching.

Benefits:
- 10-15% fuel savings
- Reduced wear and tear
- Safer driving
- Data-driven feedback

Author: Fuel Copilot Team
Date: December 26, 2025
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


class DrivingBehavior(Enum):
    """Driving behavior categories"""

    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    NEEDS_IMPROVEMENT = "needs_improvement"
    POOR = "poor"


@dataclass
class CoachingTip:
    """Single coaching recommendation"""

    category: str  # "fuel_efficiency", "safety", "maintenance"
    severity: str  # "info", "warning", "critical"
    title: str
    description: str
    potential_savings: float  # $ per month
    metric_name: str
    current_value: float
    target_value: float
    improvement_pct: float


class DriverCoachingEngine:
    """
    AI-powered driver coaching system

    Analyzes driving patterns and provides actionable recommendations
    """

    def __init__(self):
        # Benchmark values (fleet average or industry standard)
        self.benchmarks = {
            "avg_mpg": 6.5,
            "max_speed": 65,
            "idle_time_pct": 15.0,
            "harsh_braking_count": 2,  # per 100 miles
            "harsh_acceleration_count": 3,  # per 100 miles
            "speeding_minutes": 10,  # per day
            "night_driving_pct": 10.0,
            "cost_per_mile": 0.50,
        }

    def analyze_driver(
        self, truck_id: str, driver_name: str, period_days: int = 30
    ) -> Dict:
        """
        Comprehensive driver analysis

        Returns:
            - Overall score (0-100)
            - Behavior category
            - Coaching tips
            - Comparison to fleet average
        """
        # This would fetch real data from database
        # For now, using example data
        driver_stats = self._get_driver_stats(truck_id, period_days)

        # Calculate scores
        scores = self._calculate_scores(driver_stats)

        # Generate coaching tips
        tips = self._generate_coaching_tips(driver_stats, scores)

        # Overall assessment
        overall_score = np.mean(list(scores.values()))
        behavior = self._categorize_behavior(overall_score)

        # Calculate potential savings
        savings = self._calculate_potential_savings(driver_stats, tips)

        return {
            "truck_id": truck_id,
            "driver_name": driver_name,
            "period_days": period_days,
            "overall_score": round(overall_score, 1),
            "behavior_category": behavior.value,
            "scores": {k: round(v, 1) for k, v in scores.items()},
            "coaching_tips": [
                {
                    "category": tip.category,
                    "severity": tip.severity,
                    "title": tip.title,
                    "description": tip.description,
                    "potential_savings_monthly": round(tip.potential_savings, 2),
                    "current_value": round(tip.current_value, 2),
                    "target_value": round(tip.target_value, 2),
                    "improvement_pct": round(tip.improvement_pct, 1),
                }
                for tip in tips
            ],
            "potential_monthly_savings": round(savings, 2),
            "fleet_comparison": self._compare_to_fleet(driver_stats),
            "strengths": self._identify_strengths(scores),
            "weaknesses": self._identify_weaknesses(scores),
        }

    def _get_driver_stats(self, truck_id: str, days: int) -> Dict:
        """
        Get driver statistics from database

        This would be replaced with actual database queries
        """
        # Example stats
        return {
            "total_miles": 3250,
            "total_fuel": 520,
            "avg_mpg": 6.25,
            "idle_time_hours": 28,
            "idle_time_pct": 18.5,
            "speeding_events": 15,
            "speeding_minutes": 125,
            "harsh_braking_count": 8,
            "harsh_acceleration_count": 12,
            "night_driving_hours": 35,
            "night_driving_pct": 12.0,
            "avg_speed": 58,
            "max_speed": 72,
            "stops_count": 45,
            "fuel_cost": 1872,  # $3.60/gallon
            "cost_per_mile": 0.576,
        }

    def _calculate_scores(self, stats: Dict) -> Dict[str, float]:
        """
        Calculate individual scores (0-100)

        Categories:
        - Fuel efficiency
        - Speed management
        - Idle time
        - Driving smoothness
        - Safety
        """
        scores = {}

        # 1. Fuel Efficiency Score
        mpg_ratio = stats["avg_mpg"] / self.benchmarks["avg_mpg"]
        scores["fuel_efficiency"] = min(100, mpg_ratio * 100)

        # 2. Idle Time Score (lower is better)
        idle_ratio = self.benchmarks["idle_time_pct"] / max(stats["idle_time_pct"], 1)
        scores["idle_management"] = min(100, idle_ratio * 100)

        # 3. Speed Management Score
        speed_violations = stats["speeding_minutes"] / 60  # hours
        if speed_violations == 0:
            scores["speed_management"] = 100
        else:
            scores["speed_management"] = max(0, 100 - (speed_violations * 10))

        # 4. Driving Smoothness Score
        total_events = stats["harsh_braking_count"] + stats["harsh_acceleration_count"]
        events_per_100_miles = (total_events / stats["total_miles"]) * 100
        benchmark_events = (
            self.benchmarks["harsh_braking_count"]
            + self.benchmarks["harsh_acceleration_count"]
        )
        smoothness_ratio = benchmark_events / max(events_per_100_miles, 1)
        scores["driving_smoothness"] = min(100, smoothness_ratio * 100)

        # 5. Safety Score
        safety_violations = (stats["max_speed"] > 70) * 20 + (  # Speeding penalty
            stats["night_driving_pct"] > 15
        ) * 10  # Night driving penalty
        scores["safety"] = max(0, 100 - safety_violations)

        return scores

    def _generate_coaching_tips(self, stats: Dict, scores: Dict) -> List[CoachingTip]:
        """Generate personalized coaching tips"""
        tips = []

        # Tip 1: Fuel Efficiency
        if scores["fuel_efficiency"] < 90:
            mpg_improvement = self.benchmarks["avg_mpg"] - stats["avg_mpg"]
            monthly_miles = stats["total_miles"]
            fuel_savings = (mpg_improvement / stats["avg_mpg"]) * (
                monthly_miles / stats["avg_mpg"]
            )
            cost_savings = fuel_savings * 3.60  # $3.60/gallon

            tips.append(
                CoachingTip(
                    category="fuel_efficiency",
                    severity="warning" if scores["fuel_efficiency"] < 70 else "info",
                    title="Improve Fuel Economy",
                    description=f"Your MPG ({stats['avg_mpg']:.2f}) is below fleet average ({self.benchmarks['avg_mpg']:.2f}). "
                    f"Focus on steady acceleration, maintaining consistent speeds, and anticipating stops.",
                    potential_savings=cost_savings,
                    metric_name="MPG",
                    current_value=stats["avg_mpg"],
                    target_value=self.benchmarks["avg_mpg"],
                    improvement_pct=(
                        (self.benchmarks["avg_mpg"] - stats["avg_mpg"])
                        / stats["avg_mpg"]
                    )
                    * 100,
                )
            )

        # Tip 2: Idle Time
        if scores["idle_management"] < 80:
            idle_reduction = stats["idle_time_pct"] - self.benchmarks["idle_time_pct"]
            # Idling costs ~0.8 gallons/hour
            gallons_wasted = (
                (idle_reduction / 100) * stats["total_miles"] * 0.8 / stats["avg_mpg"]
            )
            cost_savings = gallons_wasted * 3.60

            tips.append(
                CoachingTip(
                    category="fuel_efficiency",
                    severity="warning",
                    title="Reduce Idle Time",
                    description=f"Your idle time ({stats['idle_time_pct']:.1f}%) is {idle_reduction:.1f}% higher than target. "
                    f"Turn off the engine during long waits (>5 minutes). Use APU for climate control when parked.",
                    potential_savings=cost_savings,
                    metric_name="Idle Time %",
                    current_value=stats["idle_time_pct"],
                    target_value=self.benchmarks["idle_time_pct"],
                    improvement_pct=idle_reduction,
                )
            )

        # Tip 3: Speeding
        if scores["speed_management"] < 85:
            speeding_hours = stats["speeding_minutes"] / 60
            # Speeding reduces MPG by ~15-20%
            fuel_waste_pct = 0.17
            fuel_wasted = fuel_waste_pct * stats["total_fuel"]
            cost_savings = fuel_wasted * 3.60

            tips.append(
                CoachingTip(
                    category="safety",
                    severity=(
                        "critical" if stats["speeding_minutes"] > 180 else "warning"
                    ),
                    title="Reduce Speeding",
                    description=f"Detected {stats['speeding_events']} speeding events totaling {stats['speeding_minutes']} minutes. "
                    f"Every 5 mph over 65 reduces fuel economy by ~7%. Use cruise control on highways.",
                    potential_savings=cost_savings,
                    metric_name="Speeding Minutes",
                    current_value=stats["speeding_minutes"],
                    target_value=self.benchmarks["speeding_minutes"],
                    improvement_pct=(
                        (
                            stats["speeding_minutes"]
                            - self.benchmarks["speeding_minutes"]
                        )
                        / stats["speeding_minutes"]
                    )
                    * 100,
                )
            )

        # Tip 4: Harsh Driving
        if scores["driving_smoothness"] < 80:
            total_events = (
                stats["harsh_braking_count"] + stats["harsh_acceleration_count"]
            )
            # Each harsh event costs ~$0.50 in fuel + wear
            cost_per_event = 0.50
            monthly_events = total_events
            cost_savings = monthly_events * cost_per_event

            tips.append(
                CoachingTip(
                    category="maintenance",
                    severity="warning",
                    title="Smoother Driving",
                    description=f"Detected {stats['harsh_braking_count']} harsh braking and "
                    f"{stats['harsh_acceleration_count']} harsh acceleration events. "
                    f"Anticipate traffic flow, maintain safe following distance, and accelerate gradually.",
                    potential_savings=cost_savings,
                    metric_name="Harsh Events",
                    current_value=total_events,
                    target_value=self.benchmarks["harsh_braking_count"]
                    + self.benchmarks["harsh_acceleration_count"],
                    improvement_pct=((total_events - 5) / total_events) * 100,
                )
            )

        # Tip 5: Night Driving
        if stats["night_driving_pct"] > 15:
            tips.append(
                CoachingTip(
                    category="safety",
                    severity="info",
                    title="Night Driving Safety",
                    description=f"You drive {stats['night_driving_pct']:.1f}% at night. "
                    f"Ensure adequate rest, use high beams when safe, and watch for wildlife.",
                    potential_savings=0,  # Safety tip, not cost
                    metric_name="Night Driving %",
                    current_value=stats["night_driving_pct"],
                    target_value=10.0,
                    improvement_pct=0,
                )
            )

        # Sort by potential savings (highest first)
        tips.sort(key=lambda x: x.potential_savings, reverse=True)

        return tips

    def _calculate_potential_savings(
        self, stats: Dict, tips: List[CoachingTip]
    ) -> float:
        """Calculate total potential monthly savings"""
        return sum(tip.potential_savings for tip in tips)

    def _categorize_behavior(self, score: float) -> DrivingBehavior:
        """Categorize driver based on overall score"""
        if score >= 90:
            return DrivingBehavior.EXCELLENT
        elif score >= 80:
            return DrivingBehavior.GOOD
        elif score >= 70:
            return DrivingBehavior.AVERAGE
        elif score >= 60:
            return DrivingBehavior.NEEDS_IMPROVEMENT
        else:
            return DrivingBehavior.POOR

    def _compare_to_fleet(self, stats: Dict) -> Dict:
        """Compare driver to fleet average"""
        return {
            "mpg": {
                "driver": stats["avg_mpg"],
                "fleet_avg": self.benchmarks["avg_mpg"],
                "percentile": self._calculate_percentile(
                    stats["avg_mpg"], self.benchmarks["avg_mpg"]
                ),
            },
            "idle_time": {
                "driver": stats["idle_time_pct"],
                "fleet_avg": self.benchmarks["idle_time_pct"],
                "percentile": self._calculate_percentile(
                    self.benchmarks["idle_time_pct"],  # Inverted (lower is better)
                    stats["idle_time_pct"],
                ),
            },
            "cost_per_mile": {
                "driver": stats["cost_per_mile"],
                "fleet_avg": self.benchmarks["cost_per_mile"],
                "percentile": self._calculate_percentile(
                    self.benchmarks["cost_per_mile"], stats["cost_per_mile"]  # Inverted
                ),
            },
        }

    def _calculate_percentile(self, value: float, benchmark: float) -> int:
        """Calculate percentile (0-100)"""
        ratio = value / benchmark
        percentile = int(ratio * 50)  # Simplified
        return min(100, max(0, percentile))

    def _identify_strengths(self, scores: Dict) -> List[str]:
        """Identify driver's strengths"""
        strengths = []
        for category, score in scores.items():
            if score >= 85:
                strengths.append(category.replace("_", " ").title())
        return strengths

    def _identify_weaknesses(self, scores: Dict) -> List[str]:
        """Identify areas for improvement"""
        weaknesses = []
        for category, score in scores.items():
            if score < 70:
                weaknesses.append(category.replace("_", " ").title())
        return weaknesses


# =====================================================
# INTEGRATION WITH API
# =====================================================

# Global coaching engine
coaching_engine = DriverCoachingEngine()


async def get_driver_coaching(truck_id: str, period_days: int = 30) -> Dict:
    """
    Get driver coaching analysis

    Args:
        truck_id: Truck to analyze
        period_days: Analysis period (default 30 days)

    Returns:
        Comprehensive coaching report
    """
    # Get driver name from database
    driver_name = "John Doe"  # Replace with DB query

    # Analyze driver
    analysis = coaching_engine.analyze_driver(
        truck_id=truck_id, driver_name=driver_name, period_days=period_days
    )

    return analysis


# =====================================================
# FASTAPI ENDPOINTS
# =====================================================

"""
# Add to main.py:

@app.get("/api/v2/trucks/{truck_id}/coaching")
async def get_coaching_report(truck_id: str, days: int = 30):
    '''Get AI driver coaching report'''
    
    report = await get_driver_coaching(truck_id, period_days=days)
    
    return report


@app.get("/api/v2/fleet/coaching/leaderboard")
async def get_coaching_leaderboard():
    '''Get driver leaderboard by performance'''
    
    # Analyze all drivers
    drivers = []
    for truck_id in get_all_truck_ids():
        analysis = await get_driver_coaching(truck_id)
        drivers.append({
            'truck_id': truck_id,
            'driver_name': analysis['driver_name'],
            'overall_score': analysis['overall_score'],
            'potential_savings': analysis['potential_monthly_savings']
        })
    
    # Sort by score
    drivers.sort(key=lambda x: x['overall_score'], reverse=True)
    
    return {
        'leaderboard': drivers,
        'top_performer': drivers[0] if drivers else None,
        'most_improvement_needed': drivers[-1] if drivers else None
    }
"""


if __name__ == "__main__":
    # Example usage
    engine = DriverCoachingEngine()
    report = engine.analyze_driver("FL0208", "John Doe", 30)

    print(f"\n{'='*60}")
    print(f"DRIVER COACHING REPORT - {report['driver_name']}")
    print(f"{'='*60}\n")
    print(f"Overall Score: {report['overall_score']}/100")
    print(f"Category: {report['behavior_category'].upper()}")
    print(f"Potential Monthly Savings: ${report['potential_monthly_savings']:.2f}\n")

    print("COACHING TIPS:")
    for i, tip in enumerate(report["coaching_tips"], 1):
        print(f"\n{i}. {tip['title']} ({tip['severity'].upper()})")
        print(f"   {tip['description']}")
        print(f"   💰 Potential Savings: ${tip['potential_savings_monthly']:.2f}/month")
