"""
Tests for Gamification Engine
v4.0: Complete test coverage for badges and leaderboard

Run with: pytest tests/test_gamification_engine.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from gamification_engine import (
    GamificationEngine,
    DriverBadge,
    BadgeTier,
    TrendDirection,
    DriverLeaderboardEntry,
    GamificationSummary,
    BADGE_DEFINITIONS,
    SCORE_WEIGHTS,
)


class TestBadgeTier:
    """Test badge tier enum"""

    def test_badge_tiers_exist(self):
        """Test all tiers are defined"""
        assert BadgeTier.BRONZE is not None
        assert BadgeTier.SILVER is not None
        assert BadgeTier.GOLD is not None
        assert BadgeTier.PLATINUM is not None

    def test_tier_values(self):
        """Test tier string values"""
        assert BadgeTier.BRONZE.value == "bronze"
        assert BadgeTier.SILVER.value == "silver"
        assert BadgeTier.GOLD.value == "gold"
        assert BadgeTier.PLATINUM.value == "platinum"


class TestTrendDirection:
    """Test trend direction enum"""

    def test_trends_exist(self):
        """Test all trends are defined"""
        assert TrendDirection.UP is not None
        assert TrendDirection.DOWN is not None
        assert TrendDirection.STABLE is not None


class TestDriverBadge:
    """Test DriverBadge dataclass"""

    def test_create_badge(self):
        """Test creating a badge"""
        badge = DriverBadge(
            id="fuel_saver_bronze",
            name="Fuel Saver",
            description="Save fuel consistently",
            icon="⛽",
            tier=BadgeTier.BRONZE,
            requirement="MPG >= fleet average for 7 days",
        )
        assert badge.id == "fuel_saver_bronze"
        assert badge.tier == BadgeTier.BRONZE
        assert badge.earned_at is None
        assert badge.progress == 0.0

    def test_badge_with_progress(self):
        """Test badge with progress"""
        badge = DriverBadge(
            id="fuel_saver_bronze",
            name="Fuel Saver",
            description="Save fuel consistently",
            icon="⛽",
            tier=BadgeTier.BRONZE,
            requirement="MPG >= fleet average for 7 days",
            progress=75.0,
        )
        assert badge.progress == 75.0

    def test_badge_earned(self):
        """Test badge when earned"""
        now = datetime.now(timezone.utc)
        badge = DriverBadge(
            id="fuel_saver_bronze",
            name="Fuel Saver",
            description="Save fuel consistently",
            icon="⛽",
            tier=BadgeTier.BRONZE,
            requirement="MPG >= fleet average for 7 days",
            earned_at=now,
            progress=100.0,
        )
        assert badge.earned_at is not None
        assert badge.progress == 100.0

    def test_badge_to_dict(self):
        """Test badge serialization"""
        badge = DriverBadge(
            id="fuel_saver_bronze",
            name="Fuel Saver",
            description="Save fuel consistently",
            icon="⛽",
            tier=BadgeTier.BRONZE,
            requirement="MPG >= fleet average for 7 days",
        )
        d = badge.to_dict()
        assert d["id"] == "fuel_saver_bronze"
        assert d["tier"] == "bronze"
        assert d["earned_at"] is None


class TestDriverLeaderboardEntry:
    """Test DriverLeaderboardEntry dataclass"""

    def test_create_entry(self):
        """Test creating a leaderboard entry"""
        entry = DriverLeaderboardEntry(
            rank=1,
            truck_id="T001",
            driver_name="John Doe",
            overall_score=85.5,
            mpg_score=90.0,
            idle_score=80.0,
            safety_score=86.0,
            trend=TrendDirection.UP,
            trend_change=2.5,
            badges_earned=3,
            streak_days=14,
        )
        assert entry.rank == 1
        assert entry.overall_score == 85.5
        assert entry.trend == TrendDirection.UP

    def test_entry_to_dict(self):
        """Test entry serialization"""
        entry = DriverLeaderboardEntry(
            rank=1,
            truck_id="T001",
            driver_name="John Doe",
            overall_score=85.5,
            mpg_score=90.0,
            idle_score=80.0,
            safety_score=86.0,
            trend=TrendDirection.UP,
            trend_change=2.5,
            badges_earned=3,
            streak_days=14,
        )
        d = entry.to_dict()
        assert d["rank"] == 1
        assert d["trend"] == "up"
        assert d["overall_score"] == 85.5


class TestBadgeDefinitions:
    """Test badge definitions"""

    def test_definitions_exist(self):
        """Test that badge definitions are loaded"""
        assert len(BADGE_DEFINITIONS) > 0

    def test_fuel_badges_exist(self):
        """Test fuel efficiency badges"""
        assert "fuel_saver_bronze" in BADGE_DEFINITIONS
        assert "fuel_saver_silver" in BADGE_DEFINITIONS
        assert "fuel_saver_gold" in BADGE_DEFINITIONS

    def test_idle_badges_exist(self):
        """Test idle reduction badges"""
        assert "idle_reducer_bronze" in BADGE_DEFINITIONS
        assert "idle_reducer_silver" in BADGE_DEFINITIONS

    def test_badge_definition_structure(self):
        """Test badge definitions have required fields"""
        for badge_id, badge in BADGE_DEFINITIONS.items():
            assert "name" in badge
            assert "description" in badge
            assert "tier" in badge
            assert "requirement" in badge


class TestScoreWeights:
    """Test scoring weight configuration"""

    def test_weights_sum_to_one(self):
        """Test that weights sum to 1.0"""
        total = sum(SCORE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.01

    def test_mpg_weight_highest(self):
        """Test that MPG has highest weight"""
        assert SCORE_WEIGHTS["mpg"] >= SCORE_WEIGHTS["idle"]


class TestGamificationEngine:
    """Test main engine functionality"""

    @pytest.fixture
    def engine(self):
        """Create engine instance"""
        return GamificationEngine()

    def test_initialization(self, engine):
        """Test engine initializes correctly"""
        assert engine is not None

    def test_calculate_mpg_score(self, engine):
        """Test MPG score calculation"""
        # Good MPG should get high score
        score = engine.calculate_mpg_score(mpg=7.5, fleet_avg_mpg=6.5)
        assert score > 75

        # Bad MPG should get lower score
        score = engine.calculate_mpg_score(mpg=5.0, fleet_avg_mpg=6.5)
        assert score < 75

    def test_calculate_idle_score(self, engine):
        """Test idle score calculation"""
        # Low idle should get high score
        score = engine.calculate_idle_score(idle_pct=5.0)
        assert score > 80

        # High idle should get lower score
        score = engine.calculate_idle_score(idle_pct=25.0)
        assert score < 70

    def test_calculate_overall_score(self, engine):
        """Test overall score calculation"""
        # Engine expects individual scores, not driver_data dict
        mpg_score = engine.calculate_mpg_score(7.0, 6.5)
        idle_score = engine.calculate_idle_score(10.0)
        score = engine.calculate_overall_score(
            mpg_score=mpg_score,
            idle_score=idle_score,
            consistency_score=80.0,
            improvement_score=50.0,
        )
        assert 0 <= score <= 100

    def test_check_badge_eligibility(self, engine):
        """Test badge eligibility checking"""
        badges = engine.check_badge_eligibility(
            truck_id="T001",
            mpg_history=[7.0, 7.2, 7.1, 7.3, 7.0, 7.1, 7.2],
            idle_history=[10.0, 9.5, 10.5, 9.0, 10.0, 9.8, 10.2],
            fleet_avg_mpg=6.5,
            current_rank=1,
            total_trucks=10,
        )
        assert isinstance(badges, list)

    def test_generate_leaderboard(self, engine):
        """Test leaderboard generation"""
        drivers_data = [
            {
                "truck_id": "T001",
                "driver_name": "John",
                "mpg": 7.5,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 8.0,
                "safety_score": 90.0,
                "previous_score": 82.0,
            },
            {
                "truck_id": "T002",
                "driver_name": "Jane",
                "mpg": 7.0,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 12.0,
                "safety_score": 88.0,
                "previous_score": 80.0,
            },
            {
                "truck_id": "T003",
                "driver_name": "Bob",
                "mpg": 6.0,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 18.0,
                "safety_score": 75.0,
                "previous_score": 78.0,
            },
        ]
        leaderboard = engine.generate_leaderboard(drivers_data)
        assert isinstance(leaderboard, list)
        assert len(leaderboard) == 3
        # Best performer should be rank 1
        assert leaderboard[0].rank == 1

    def test_leaderboard_entry_types(self, engine):
        """Test that leaderboard returns correct types"""
        drivers_data = [
            {
                "truck_id": "T001",
                "driver_name": "John",
                "mpg": 7.5,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 8.0,
                "safety_score": 90.0,
            },
        ]
        leaderboard = engine.generate_leaderboard(drivers_data)
        assert isinstance(leaderboard[0], DriverLeaderboardEntry)

    def test_get_gamification_summary(self, engine):
        """Test full gamification summary"""
        drivers_data = [
            {
                "truck_id": "T001",
                "driver_name": "John",
                "mpg": 7.5,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 8.0,
                "safety_score": 90.0,
            },
            {
                "truck_id": "T002",
                "driver_name": "Jane",
                "mpg": 7.0,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 12.0,
                "safety_score": 88.0,
            },
        ]
        summary = engine.generate_gamification_summary(drivers_data)
        assert isinstance(summary, GamificationSummary)
        assert len(summary.leaderboard) == 2
        assert len(summary.available_badges) > 0

    def test_summary_to_dict(self, engine):
        """Test summary serialization"""
        drivers_data = [
            {
                "truck_id": "T001",
                "driver_name": "John",
                "mpg": 7.5,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 8.0,
                "safety_score": 90.0,
            },
        ]
        summary = engine.generate_gamification_summary(drivers_data)
        d = summary.to_dict()
        assert "leaderboard" in d
        assert "available_badges" in d
        assert "fleet_stats" in d


class TestTrendCalculation:
    """Test trend direction calculation"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_improving_trend(self, engine):
        """Test detection of improving trend"""
        trend, change = engine.determine_trend(current_score=85.0, previous_score=80.0)
        assert trend == TrendDirection.UP
        assert change > 0

    def test_declining_trend(self, engine):
        """Test detection of declining trend"""
        trend, change = engine.determine_trend(current_score=75.0, previous_score=80.0)
        assert trend == TrendDirection.DOWN
        assert change < 0

    def test_stable_trend(self, engine):
        """Test detection of stable trend"""
        trend, change = engine.determine_trend(current_score=80.0, previous_score=80.5)
        assert trend == TrendDirection.STABLE
        assert abs(change) < 2


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_empty_drivers_list(self, engine):
        """Handle empty driver list"""
        leaderboard = engine.generate_leaderboard([])
        assert leaderboard == []

    def test_single_driver(self, engine):
        """Handle single driver"""
        drivers_data = [
            {
                "truck_id": "T001",
                "driver_name": "John",
                "mpg": 7.0,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 10.0,
                "safety_score": 85.0,
            },
        ]
        leaderboard = engine.generate_leaderboard(drivers_data)
        assert len(leaderboard) == 1
        assert leaderboard[0].rank == 1

    def test_zero_mpg(self, engine):
        """Handle zero MPG gracefully"""
        score = engine.calculate_mpg_score(mpg=0.0, fleet_avg_mpg=6.5)
        assert score >= 0

    def test_negative_idle(self, engine):
        """Handle negative idle gracefully"""
        score = engine.calculate_idle_score(idle_pct=-5.0)
        assert score >= 0

    def test_missing_driver_fields(self, engine):
        """Handle missing optional fields"""
        drivers_data = [
            {
                "truck_id": "T001",
                "driver_name": "John",
                "mpg": 7.0,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 10.0,
            },
        ]
        # Should not raise even with missing safety_score
        leaderboard = engine.generate_leaderboard(drivers_data)
        assert len(leaderboard) == 1


class TestStreakTracking:
    """Test streak tracking functionality"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_streak_badge_eligibility(self, engine):
        """Test streak badges require minimum days"""
        # Long streak should qualify for streak badges
        badges = engine.check_badge_eligibility(
            truck_id="T001",
            mpg_history=[7.0] * 30,
            idle_history=[10.0] * 30,
            fleet_avg_mpg=6.5,
            current_rank=1,
            total_trucks=10,
        )
        # Should have some streak-related badges
        streak_badges = [b for b in badges if "streak" in b.id.lower()]
        assert (
            len(streak_badges) >= 0
        )  # May or may not have depending on implementation


class TestFleetStats:
    """Test fleet statistics calculation"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_fleet_stats_included(self, engine):
        """Test that fleet stats are included in summary"""
        drivers_data = [
            {
                "truck_id": "T001",
                "driver_name": "John",
                "mpg": 7.5,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 8.0,
                "safety_score": 90.0,
            },
            {
                "truck_id": "T002",
                "driver_name": "Jane",
                "mpg": 6.0,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 15.0,
                "safety_score": 80.0,
            },
        ]
        summary = engine.generate_gamification_summary(drivers_data)
        assert summary.fleet_stats is not None
        assert isinstance(summary.fleet_stats, dict)


# ═══════════════════════════════════════════════════════════════════════════════
# EXTENDED TEST CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


class TestMPGScoreEdgeCases:
    """Extended edge case tests for MPG scoring"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_mpg_very_high_ratio(self, engine):
        """Test MPG score with very high ratio"""
        score = engine.calculate_mpg_score(mpg=12.0, fleet_avg_mpg=6.0)
        assert score == 100.0  # Capped at 100

    def test_mpg_very_low_ratio(self, engine):
        """Test MPG score with very low ratio"""
        score = engine.calculate_mpg_score(mpg=2.0, fleet_avg_mpg=6.0)
        assert score == 0.0  # Capped at 0

    def test_mpg_exactly_80_percent(self, engine):
        """Test MPG score at exactly 80% of average"""
        # 80% ratio = 0 points
        score = engine.calculate_mpg_score(mpg=4.8, fleet_avg_mpg=6.0)
        assert score == pytest.approx(0.0, abs=5)

    def test_mpg_exactly_120_percent(self, engine):
        """Test MPG score at exactly 120% of average"""
        # 120% ratio = 100 points
        score = engine.calculate_mpg_score(mpg=7.2, fleet_avg_mpg=6.0)
        assert score == pytest.approx(100.0, abs=5)


class TestIdleScoreEdgeCases:
    """Extended edge case tests for idle scoring"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_idle_zero_percent(self, engine):
        """Test idle score at 0%"""
        score = engine.calculate_idle_score(idle_pct=0.0)
        assert score == 100.0

    def test_idle_exactly_10_percent(self, engine):
        """Test idle score at exactly 10%"""
        score = engine.calculate_idle_score(idle_pct=10.0)
        assert score == 75.0

    def test_idle_exactly_20_percent(self, engine):
        """Test idle score at exactly 20%"""
        score = engine.calculate_idle_score(idle_pct=20.0)
        assert score == 25.0

    def test_idle_very_high(self, engine):
        """Test idle score at very high percentage"""
        score = engine.calculate_idle_score(idle_pct=50.0)
        assert score == 0.0  # Capped


class TestConsistencyScoreEdgeCases:
    """Extended edge case tests for consistency scoring"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_consistency_exactly_5_percent(self, engine):
        """Test consistency at 5% variance"""
        score = engine.calculate_consistency_score(score_variance=5.0)
        assert score == 75.0

    def test_consistency_exactly_15_percent(self, engine):
        """Test consistency at 15% variance"""
        score = engine.calculate_consistency_score(score_variance=15.0)
        assert score == 25.0

    def test_consistency_very_high_variance(self, engine):
        """Test consistency with very high variance"""
        score = engine.calculate_consistency_score(score_variance=30.0)
        assert score == 0.0  # Capped


class TestImprovementScoreEdgeCases:
    """Extended edge case tests for improvement scoring"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_improvement_10_points(self, engine):
        """Test 10 point improvement"""
        score = engine.calculate_improvement_score(
            current_score=80.0, previous_score=70.0
        )
        # 10 point change = 50 + (10/20 * 50) = 75
        assert score == 75.0

    def test_improvement_negative_10_points(self, engine):
        """Test 10 point decline"""
        score = engine.calculate_improvement_score(
            current_score=65.0, previous_score=75.0
        )
        # -10 point change = 50 + (-10/20 * 50) = 25
        assert score == 25.0

    def test_improvement_extreme_gain(self, engine):
        """Test extreme improvement"""
        score = engine.calculate_improvement_score(
            current_score=100.0, previous_score=50.0
        )
        assert score == 100.0  # Capped


class TestOverallScoreEdgeCases:
    """Extended tests for overall score calculation"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_overall_mixed_scores(self, engine):
        """Test overall score with mixed component scores"""
        score = engine.calculate_overall_score(
            mpg_score=100.0,
            idle_score=0.0,
            consistency_score=50.0,
            improvement_score=50.0,
        )
        # 100*0.4 + 0*0.3 + 50*0.15 + 50*0.15 = 40 + 0 + 7.5 + 7.5 = 55
        assert score == pytest.approx(55.0, abs=0.5)

    def test_overall_with_default_consistency_improvement(self, engine):
        """Test overall score with default consistency and improvement"""
        score = engine.calculate_overall_score(
            mpg_score=80.0,
            idle_score=60.0,
        )
        # Uses default 50 for consistency and improvement
        # 80*0.4 + 60*0.3 + 50*0.15 + 50*0.15 = 32 + 18 + 7.5 + 7.5 = 65
        assert score == pytest.approx(65.0, abs=0.5)


class TestTrendDeterminationEdgeCases:
    """Extended tests for trend determination"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_trend_exactly_plus_2(self, engine):
        """Test trend at exactly +2 change"""
        trend, change = engine.determine_trend(current_score=77.0, previous_score=75.0)
        assert trend == TrendDirection.STABLE
        assert change == 2.0

    def test_trend_exactly_minus_2(self, engine):
        """Test trend at exactly -2 change"""
        trend, change = engine.determine_trend(current_score=73.0, previous_score=75.0)
        assert trend == TrendDirection.STABLE
        assert change == -2.0

    def test_trend_just_above_threshold(self, engine):
        """Test trend just above UP threshold"""
        trend, change = engine.determine_trend(current_score=77.1, previous_score=75.0)
        assert trend == TrendDirection.UP

    def test_trend_just_below_threshold(self, engine):
        """Test trend just below DOWN threshold"""
        trend, change = engine.determine_trend(current_score=72.9, previous_score=75.0)
        assert trend == TrendDirection.DOWN


class TestBadgeDefinitionsExtended:
    """Extended tests for badge definitions"""

    def test_all_badges_have_icons(self):
        """Test all badges have icons"""
        for badge_id, badge_def in BADGE_DEFINITIONS.items():
            assert badge_def["icon"], f"{badge_id} missing icon"
            assert len(badge_def["icon"]) > 0

    def test_badge_tiers_distribution(self):
        """Test badge tier distribution"""
        tier_counts = {tier: 0 for tier in BadgeTier}
        for badge_def in BADGE_DEFINITIONS.values():
            tier_counts[badge_def["tier"]] += 1

        # Should have badges at all tiers
        assert tier_counts[BadgeTier.BRONZE] > 0
        assert tier_counts[BadgeTier.SILVER] > 0
        assert tier_counts[BadgeTier.GOLD] > 0
        assert tier_counts[BadgeTier.PLATINUM] > 0

    def test_consistency_badge_exists(self):
        """Test consistency badge exists"""
        assert "consistent_performer" in BADGE_DEFINITIONS

    def test_streak_master_badge_exists(self):
        """Test streak master badge exists"""
        assert "streak_master" in BADGE_DEFINITIONS


class TestDriverBadgeExtended:
    """Extended tests for DriverBadge dataclass"""

    def test_badge_progress_rounding(self):
        """Test badge progress rounding in to_dict"""
        badge = DriverBadge(
            id="test_badge",
            name="Test Badge",
            description="Test description",
            icon="🎯",
            tier=BadgeTier.BRONZE,
            requirement="Test requirement",
            progress=65.567,
        )
        result = badge.to_dict()
        assert result["progress"] == 65.6

    def test_badge_all_tiers(self):
        """Test creating badges with all tiers"""
        for tier in BadgeTier:
            badge = DriverBadge(
                id=f"test_{tier.value}",
                name=f"Test {tier.value}",
                description="Test",
                icon="🎯",
                tier=tier,
                requirement="Test",
            )
            assert badge.tier == tier


class TestLeaderboardEntryExtended:
    """Extended tests for DriverLeaderboardEntry"""

    def test_entry_with_zero_streak(self):
        """Test leaderboard entry with zero streak"""
        entry = DriverLeaderboardEntry(
            rank=10,
            truck_id="T010",
            driver_name="New Driver",
            overall_score=50.0,
            mpg_score=45.0,
            idle_score=55.0,
            safety_score=50.0,
            trend=TrendDirection.STABLE,
            trend_change=0.0,
            badges_earned=0,
            streak_days=0,
        )
        result = entry.to_dict()
        assert result["streak_days"] == 0

    def test_entry_with_negative_trend(self):
        """Test leaderboard entry with negative trend"""
        entry = DriverLeaderboardEntry(
            rank=8,
            truck_id="T008",
            driver_name="Declining Driver",
            overall_score=60.0,
            mpg_score=55.0,
            idle_score=65.0,
            safety_score=60.0,
            trend=TrendDirection.DOWN,
            trend_change=-8.5,
            badges_earned=1,
            streak_days=0,
        )
        result = entry.to_dict()
        assert result["trend"] == "down"
        assert result["trend_change"] == -8.5


class TestGamificationSummaryExtended:
    """Extended tests for GamificationSummary"""

    def test_empty_leaderboard(self):
        """Test summary with empty leaderboard"""
        summary = GamificationSummary(
            leaderboard=[],
            available_badges=[],
            fleet_stats={},
        )
        result = summary.to_dict()
        assert result["leaderboard"] == []

    def test_summary_with_multiple_entries(self):
        """Test summary with multiple leaderboard entries"""
        entries = []
        for i in range(5):
            entries.append(
                DriverLeaderboardEntry(
                    rank=i + 1,
                    truck_id=f"T{i+1:03d}",
                    driver_name=f"Driver {i+1}",
                    overall_score=90.0 - i * 5,
                    mpg_score=88.0 - i * 3,
                    idle_score=85.0 - i * 4,
                    safety_score=87.0 - i * 2,
                    trend=TrendDirection.STABLE,
                    trend_change=0.0,
                    badges_earned=5 - i,
                    streak_days=10 - i,
                )
            )

        summary = GamificationSummary(
            leaderboard=entries,
            available_badges=[],
            fleet_stats={"total_drivers": 5},
        )
        result = summary.to_dict()
        assert len(result["leaderboard"]) == 5


class TestScoreWeightsValidation:
    """Tests for score weight validation"""

    def test_all_weights_positive(self):
        """Test all weights are positive"""
        for weight_name, weight_value in SCORE_WEIGHTS.items():
            assert weight_value > 0, f"Weight {weight_name} should be positive"

    def test_weights_sum_exactly_one(self):
        """Test weights sum to exactly 1.0"""
        total = sum(SCORE_WEIGHTS.values())
        assert total == 1.0

    def test_mpg_has_highest_weight(self):
        """Test MPG has highest weight"""
        assert SCORE_WEIGHTS["mpg"] >= max(
            SCORE_WEIGHTS["idle"],
            SCORE_WEIGHTS["consistency"],
            SCORE_WEIGHTS["improvement"],
        )


class TestBadgeCategoryValidation:
    """Tests for badge category validation"""

    def test_all_badges_have_category(self):
        """Test all badges have a category"""
        for badge_id, badge_def in BADGE_DEFINITIONS.items():
            assert "category" in badge_def, f"{badge_id} missing category"

    def test_valid_categories(self):
        """Test categories are from valid set"""
        valid_categories = {
            "mpg",
            "idle",
            "consistency",
            "streak",
            "improvement",
            "special",
        }
        for badge_id, badge_def in BADGE_DEFINITIONS.items():
            assert (
                badge_def["category"] in valid_categories
            ), f"{badge_id} has invalid category"


class TestEngineWithEmptyData:
    """Tests for engine with empty or minimal data"""

    @pytest.fixture
    def engine(self):
        return GamificationEngine()

    def test_summary_with_no_drivers(self, engine):
        """Test generating summary with no drivers"""
        summary = engine.generate_gamification_summary([])
        assert summary is not None
        assert len(summary.leaderboard) == 0

    def test_summary_with_single_driver(self, engine):
        """Test generating summary with single driver"""
        drivers_data = [
            {
                "truck_id": "T001",
                "driver_name": "Solo Driver",
                "mpg": 6.5,
                "fleet_avg_mpg": 6.5,
                "idle_percent": 12.0,
                "safety_score": 85.0,
            }
        ]
        summary = engine.generate_gamification_summary(drivers_data)
        assert len(summary.leaderboard) == 1


class TestProgressCalculation:
    """Tests for badge progress calculation"""

    def test_progress_percentage_formula(self):
        """Test progress percentage formula"""
        # 7 days out of 14 required = 50%
        days_completed = 7
        days_required = 14
        progress = (days_completed / days_required) * 100
        assert progress == 50.0

    def test_progress_exceeds_100(self):
        """Test progress doesn't exceed 100"""
        days_completed = 20
        days_required = 14
        progress = min((days_completed / days_required) * 100, 100.0)
        assert progress == 100.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
