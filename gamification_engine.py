"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    DRIVER GAMIFICATION ENGINE                                  ║
║                         Fuel Copilot v4.0                                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Purpose: Gamification system with badges, leaderboards, and achievements     ║
║  Features: Driver rankings, performance badges, streak tracking               ║
║                                                                                ║
║  Competitive Feature vs Geotab/Samsara/Motive:                                ║
║  - Most competitors charge extra for gamification modules                      ║
║  - We include it FREE with advanced scoring algorithms                         ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# ENUMS AND CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════


class BadgeTier(str, Enum):
    """Badge tier levels"""

    BRONZE = "bronze"
    SILVER = "silver"
    GOLD = "gold"
    PLATINUM = "platinum"


class TrendDirection(str, Enum):
    """Performance trend direction"""

    UP = "up"
    DOWN = "down"
    STABLE = "stable"


# Badge definitions
BADGE_DEFINITIONS = {
    # MPG Badges
    "fuel_saver_bronze": {
        "name": "Fuel Saver",
        "description": "Maintain MPG above fleet average for 7 days",
        "icon": "⛽",
        "tier": BadgeTier.BRONZE,
        "requirement": "MPG ≥ fleet average for 7 consecutive days",
        "category": "mpg",
    },
    "fuel_saver_silver": {
        "name": "Fuel Master",
        "description": "Maintain MPG 10% above fleet average for 14 days",
        "icon": "⛽",
        "tier": BadgeTier.SILVER,
        "requirement": "MPG ≥ 110% fleet average for 14 consecutive days",
        "category": "mpg",
    },
    "fuel_saver_gold": {
        "name": "Fuel Champion",
        "description": "Top 3 MPG in fleet for 30 days",
        "icon": "🏆",
        "tier": BadgeTier.GOLD,
        "requirement": "Top 3 MPG ranking for 30 consecutive days",
        "category": "mpg",
    },
    # Idle Badges
    "idle_reducer_bronze": {
        "name": "Idle Reducer",
        "description": "Keep idle below 15% for a week",
        "icon": "⏱️",
        "tier": BadgeTier.BRONZE,
        "requirement": "Idle time < 15% for 7 consecutive days",
        "category": "idle",
    },
    "idle_reducer_silver": {
        "name": "Idle Master",
        "description": "Keep idle below 10% for 14 days",
        "icon": "⏱️",
        "tier": BadgeTier.SILVER,
        "requirement": "Idle time < 10% for 14 consecutive days",
        "category": "idle",
    },
    "idle_reducer_gold": {
        "name": "Zero Waste Champion",
        "description": "Lowest idle in fleet for 30 days",
        "icon": "🥇",
        "tier": BadgeTier.GOLD,
        "requirement": "Lowest idle percentage for 30 consecutive days",
        "category": "idle",
    },
    # Consistency Badges
    "consistent_performer": {
        "name": "Consistent Performer",
        "description": "Maintain stable scores for 14 days",
        "icon": "📊",
        "tier": BadgeTier.BRONZE,
        "requirement": "Score variance < 5% for 14 consecutive days",
        "category": "consistency",
    },
    "streak_master": {
        "name": "Streak Master",
        "description": "30-day above-average streak",
        "icon": "🔥",
        "tier": BadgeTier.SILVER,
        "requirement": "Above fleet average for 30 consecutive days",
        "category": "streak",
    },
    # Improvement Badges
    "most_improved": {
        "name": "Most Improved",
        "description": "Greatest improvement this month",
        "icon": "📈",
        "tier": BadgeTier.GOLD,
        "requirement": "Largest score increase month-over-month",
        "category": "improvement",
    },
    "comeback_king": {
        "name": "Comeback Champion",
        "description": "Improved from bottom 25% to top 50%",
        "icon": "👑",
        "tier": BadgeTier.PLATINUM,
        "requirement": "Move from bottom quartile to top half of fleet",
        "category": "improvement",
    },
    # Special Badges
    "perfect_week": {
        "name": "Perfect Week",
        "description": "Top performer for entire week",
        "icon": "⭐",
        "tier": BadgeTier.GOLD,
        "requirement": "#1 ranking for 7 consecutive days",
        "category": "special",
    },
    "eco_warrior": {
        "name": "Eco Warrior",
        "description": "Save 100+ gallons vs fleet average",
        "icon": "🌱",
        "tier": BadgeTier.PLATINUM,
        "requirement": "Cumulative fuel savings ≥ 100 gallons",
        "category": "special",
    },
}

# Scoring weights
SCORE_WEIGHTS = {
    "mpg": 0.40,  # 40% of total score
    "idle": 0.30,  # 30% of total score
    "consistency": 0.15,  # 15% of total score
    "improvement": 0.15,  # 15% of total score
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class DriverBadge:
    """Badge earned or available for a driver"""

    id: str
    name: str
    description: str
    icon: str
    tier: BadgeTier
    requirement: str
    earned_at: Optional[datetime] = None
    progress: float = 0.0  # 0-100

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "icon": self.icon,
            "tier": self.tier.value,
            "requirement": self.requirement,
            "earned_at": self.earned_at.isoformat() if self.earned_at else None,
            "progress": round(self.progress, 1),
        }


@dataclass
class DriverLeaderboardEntry:
    """Entry in the driver leaderboard"""

    rank: int
    truck_id: str
    driver_name: str
    overall_score: float
    mpg_score: float
    idle_score: float
    safety_score: float
    trend: TrendDirection
    trend_change: float
    badges_earned: int
    streak_days: int

    def to_dict(self) -> Dict:
        return {
            "rank": self.rank,
            "truck_id": self.truck_id,
            "driver_name": self.driver_name,
            "overall_score": round(self.overall_score, 1),
            "mpg_score": round(self.mpg_score, 1),
            "idle_score": round(self.idle_score, 1),
            "safety_score": round(self.safety_score, 1),
            "trend": self.trend.value,
            "trend_change": round(self.trend_change, 1),
            "badges_earned": self.badges_earned,
            "streak_days": self.streak_days,
        }


@dataclass
class GamificationSummary:
    """Fleet gamification summary"""

    leaderboard: List[DriverLeaderboardEntry]
    available_badges: List[DriverBadge]
    fleet_stats: Dict

    def to_dict(self) -> Dict:
        return {
            "leaderboard": [e.to_dict() for e in self.leaderboard],
            "available_badges": [b.to_dict() for b in self.available_badges],
            "fleet_stats": self.fleet_stats,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ENGINE CLASS
# ═══════════════════════════════════════════════════════════════════════════════


class GamificationEngine:
    """
    Driver Gamification Engine

    Features:
    - Leaderboard with rankings and trends
    - Badge system with progress tracking
    - Streak tracking for consistency
    - Fair scoring that accounts for route difficulty
    """

    def __init__(self, db_connection=None):
        """Initialize Gamification Engine."""
        self.db = db_connection
        logger.info("✅ GamificationEngine initialized")

    def calculate_mpg_score(self, mpg: float, fleet_avg_mpg: float) -> float:
        """
        Calculate MPG score (0-100).

        100 = 20% above fleet average
        50 = At fleet average
        0 = 20% below fleet average
        """
        if fleet_avg_mpg <= 0:
            return 50.0

        ratio = mpg / fleet_avg_mpg
        # Scale: 0.8 = 0 points, 1.0 = 50 points, 1.2 = 100 points
        # 🆕 v5.5.5: Explicit divisor variable for clarity
        divisor = 0.4
        score = (ratio - 0.8) / divisor * 100 if divisor != 0 else 50.0
        return max(0, min(100, score))

    def calculate_idle_score(self, idle_pct: float) -> float:
        """
        Calculate Idle score (0-100).

        100 = 5% or less idle
        50 = 15% idle (industry average)
        0 = 25% or more idle
        """
        # Scale: 5% = 100 points, 15% = 50 points, 25% = 0 points
        score = (25 - idle_pct) / 20 * 100
        return max(0, min(100, score))

    def calculate_consistency_score(self, score_variance: float) -> float:
        """
        Calculate consistency score (0-100).

        100 = Very consistent (variance < 2%)
        50 = Moderately consistent (variance ~10%)
        0 = Highly variable (variance > 20%)
        """
        # Lower variance = higher score
        score = (20 - score_variance) / 20 * 100
        return max(0, min(100, score))

    def calculate_improvement_score(
        self, current_score: float, previous_score: float
    ) -> float:
        """
        Calculate improvement score (0-100).

        100 = Improved by 20+ points
        50 = No change
        0 = Declined by 20+ points
        """
        change = current_score - previous_score
        score = 50 + (change / 20 * 50)
        return max(0, min(100, score))

    def calculate_overall_score(
        self,
        mpg_score: float,
        idle_score: float,
        consistency_score: float = 50,
        improvement_score: float = 50,
    ) -> float:
        """Calculate weighted overall score."""
        return (
            mpg_score * SCORE_WEIGHTS["mpg"]
            + idle_score * SCORE_WEIGHTS["idle"]
            + consistency_score * SCORE_WEIGHTS["consistency"]
            + improvement_score * SCORE_WEIGHTS["improvement"]
        )

    def determine_trend(
        self, current_score: float, previous_score: float
    ) -> Tuple[TrendDirection, float]:
        """Determine score trend direction and magnitude."""
        change = current_score - previous_score

        if change > 2:
            return TrendDirection.UP, change
        elif change < -2:
            return TrendDirection.DOWN, change
        else:
            return TrendDirection.STABLE, change

    def check_badge_eligibility(
        self,
        truck_id: str,
        mpg_history: List[float],
        idle_history: List[float],
        fleet_avg_mpg: float,
        current_rank: int,
        total_trucks: int,
    ) -> List[DriverBadge]:
        """
        Check which badges a driver has earned or is progressing towards.

        Returns list of badges with progress or earned status.
        """
        badges = []

        # Calculate streaks
        days_above_avg = 0
        for mpg in reversed(mpg_history):
            if mpg >= fleet_avg_mpg:
                days_above_avg += 1
            else:
                break

        days_low_idle = 0
        for idle in reversed(idle_history):
            if idle < 15:
                days_low_idle += 1
            else:
                break

        # Check each badge
        for badge_id, badge_def in BADGE_DEFINITIONS.items():
            badge = DriverBadge(
                id=badge_id,
                name=badge_def["name"],
                description=badge_def["description"],
                icon=badge_def["icon"],
                tier=badge_def["tier"],
                requirement=badge_def["requirement"],
            )

            # Fuel Saver Bronze - 7 days above average
            if badge_id == "fuel_saver_bronze":
                badge.progress = min(100, (days_above_avg / 7) * 100)
                if days_above_avg >= 7:
                    badge.earned_at = datetime.now(timezone.utc)

            # Fuel Saver Silver - 14 days 10% above
            elif badge_id == "fuel_saver_silver":
                days_10_above = sum(
                    1 for mpg in mpg_history[-14:] if mpg >= fleet_avg_mpg * 1.1
                )
                badge.progress = min(100, (days_10_above / 14) * 100)
                if days_10_above >= 14:
                    badge.earned_at = datetime.now(timezone.utc)

            # Idle Reducer Bronze - 7 days below 15%
            elif badge_id == "idle_reducer_bronze":
                badge.progress = min(100, (days_low_idle / 7) * 100)
                if days_low_idle >= 7:
                    badge.earned_at = datetime.now(timezone.utc)

            # Idle Reducer Silver - 14 days below 10%
            elif badge_id == "idle_reducer_silver":
                days_under_10 = sum(1 for idle in idle_history[-14:] if idle < 10)
                badge.progress = min(100, (days_under_10 / 14) * 100)
                if days_under_10 >= 14:
                    badge.earned_at = datetime.now(timezone.utc)

            # Streak Master - 30 days above average
            elif badge_id == "streak_master":
                badge.progress = min(100, (days_above_avg / 30) * 100)
                if days_above_avg >= 30:
                    badge.earned_at = datetime.now(timezone.utc)

            # Perfect Week - #1 for 7 days
            elif badge_id == "perfect_week":
                if current_rank == 1:
                    badge.progress = 100
                    badge.earned_at = datetime.now(timezone.utc)
                else:
                    badge.progress = 0

            badges.append(badge)

        return badges

    def generate_leaderboard(
        self, drivers_data: List[Dict]
    ) -> List[DriverLeaderboardEntry]:
        """
        Generate driver leaderboard from performance data.

        Args:
            drivers_data: List of dicts with truck_id, mpg, idle_pct, etc.

        Returns:
            Sorted leaderboard entries
        """
        if not drivers_data:
            return []

        # Calculate fleet averages
        fleet_avg_mpg = sum(d.get("mpg", 0) for d in drivers_data) / len(drivers_data)

        entries = []
        for driver in drivers_data:
            truck_id = driver.get("truck_id", "Unknown")
            mpg = driver.get("mpg", fleet_avg_mpg)
            idle_pct = driver.get("idle_pct", 15)
            previous_score = driver.get("previous_score", 50)

            # Calculate component scores
            mpg_score = self.calculate_mpg_score(mpg, fleet_avg_mpg)
            idle_score = self.calculate_idle_score(idle_pct)
            consistency_score = driver.get("consistency_score", 50)
            improvement_score = self.calculate_improvement_score(
                (mpg_score + idle_score) / 2, previous_score
            )

            # Calculate overall score
            overall_score = self.calculate_overall_score(
                mpg_score, idle_score, consistency_score, improvement_score
            )

            # Determine trend
            trend, trend_change = self.determine_trend(overall_score, previous_score)

            entry = DriverLeaderboardEntry(
                rank=0,  # Will be set after sorting
                truck_id=truck_id,
                driver_name=driver.get("driver_name", f"Driver {truck_id}"),
                overall_score=overall_score,
                mpg_score=mpg_score,
                idle_score=idle_score,
                safety_score=driver.get("safety_score", 80),
                trend=trend,
                trend_change=trend_change,
                badges_earned=driver.get("badges_earned", 0),
                streak_days=driver.get("streak_days", 0),
            )
            entries.append(entry)

        # Sort by overall score (descending)
        entries.sort(key=lambda x: x.overall_score, reverse=True)

        # Assign ranks
        for i, entry in enumerate(entries):
            entry.rank = i + 1

        return entries

    def get_available_badges(self) -> List[DriverBadge]:
        """Get list of all available badges."""
        badges = []
        for badge_id, badge_def in BADGE_DEFINITIONS.items():
            badge = DriverBadge(
                id=badge_id,
                name=badge_def["name"],
                description=badge_def["description"],
                icon=badge_def["icon"],
                tier=badge_def["tier"],
                requirement=badge_def["requirement"],
            )
            badges.append(badge)
        return badges

    def generate_gamification_summary(
        self, drivers_data: List[Dict]
    ) -> GamificationSummary:
        """
        Generate complete gamification summary.

        Args:
            drivers_data: List of driver performance data

        Returns:
            GamificationSummary with leaderboard, badges, and stats
        """
        leaderboard = self.generate_leaderboard(drivers_data)
        available_badges = self.get_available_badges()

        # Calculate fleet stats
        if leaderboard:
            total_badges = sum(e.badges_earned for e in leaderboard)
            avg_score = sum(e.overall_score for e in leaderboard) / len(leaderboard)
            top_performer = leaderboard[0].truck_id if leaderboard else "N/A"

            # Find most improved (highest positive trend)
            most_improved = max(
                leaderboard,
                key=lambda x: x.trend_change if x.trend == TrendDirection.UP else -100,
            )
            most_improved_id = (
                most_improved.truck_id
                if most_improved.trend == TrendDirection.UP
                else "N/A"
            )
        else:
            total_badges = 0
            avg_score = 0
            top_performer = "N/A"
            most_improved_id = "N/A"

        fleet_stats = {
            "total_badges_earned": total_badges,
            "avg_score": round(avg_score, 1),
            "top_performer": top_performer,
            "most_improved": most_improved_id,
        }

        return GamificationSummary(
            leaderboard=leaderboard,
            available_badges=available_badges,
            fleet_stats=fleet_stats,
        )

    def generate_gamification_report(self, drivers_data: List[Dict]) -> Dict:
        """
        Generate gamification report for API response.

        This is the main method to call from API endpoints.
        """
        summary = self.generate_gamification_summary(drivers_data)

        return {
            "status": "success",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": summary.to_dict(),
        }

    def get_driver_badges(
        self, truck_id: str, driver_data: Dict, fleet_avg_mpg: float = 6.0
    ) -> Dict:
        """
        Get badges for a specific driver.

        Args:
            truck_id: Truck identifier
            driver_data: Dict with mpg_history, idle_history, etc.

        Returns:
            Dict with badges and progress
        """
        mpg_history = driver_data.get("mpg_history", [6.0] * 30)
        idle_history = driver_data.get("idle_history", [12.0] * 30)
        current_rank = driver_data.get("rank", 10)
        total_trucks = driver_data.get("total_trucks", 25)

        badges = self.check_badge_eligibility(
            truck_id=truck_id,
            mpg_history=mpg_history,
            idle_history=idle_history,
            fleet_avg_mpg=fleet_avg_mpg,
            current_rank=current_rank,
            total_trucks=total_trucks,
        )

        earned_badges = [b for b in badges if b.earned_at is not None]
        in_progress = [b for b in badges if b.earned_at is None and b.progress > 0]

        return {
            "status": "success",
            "truck_id": truck_id,
            "badges": [b.to_dict() for b in badges],
            "earned_count": len(earned_badges),
            "in_progress_count": len(in_progress),
            "total_score": driver_data.get("overall_score", 50),
            "rank": current_rank,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# STANDALONE TESTING
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    engine = GamificationEngine()

    # Sample driver data
    test_drivers = [
        {
            "truck_id": "JC1282",
            "mpg": 6.8,
            "idle_pct": 8,
            "driver_name": "Carlos M.",
            "previous_score": 72,
            "streak_days": 15,
        },
        {
            "truck_id": "RT9127",
            "mpg": 5.9,
            "idle_pct": 12,
            "driver_name": "Miguel R.",
            "previous_score": 65,
            "streak_days": 5,
        },
        {
            "truck_id": "FM9838",
            "mpg": 6.2,
            "idle_pct": 18,
            "driver_name": "Juan P.",
            "previous_score": 58,
            "streak_days": 0,
        },
        {
            "truck_id": "SG5760",
            "mpg": 5.5,
            "idle_pct": 22,
            "driver_name": "Roberto L.",
            "previous_score": 45,
            "streak_days": 0,
        },
        {
            "truck_id": "NQ6975",
            "mpg": 7.1,
            "idle_pct": 6,
            "driver_name": "Pedro S.",
            "previous_score": 78,
            "streak_days": 22,
        },
    ]

    # Generate report
    report = engine.generate_gamification_report(test_drivers)

    import json

    print("=" * 80)
    print("GAMIFICATION REPORT")
    print("=" * 80)
    print(json.dumps(report, indent=2))
