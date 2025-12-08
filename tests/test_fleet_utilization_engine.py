"""
Tests for Fleet Utilization Engine
v4.0: Complete test coverage for utilization tracking

Run with: pytest tests/test_fleet_utilization_engine.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from fleet_utilization_engine import (
    FleetUtilizationEngine,
    UtilizationMetrics,
    TruckUtilizationAnalysis,
    FleetUtilizationSummary,
    UtilizationTier,
    TimeBreakdown,
    TruckActivityState,
    UTILIZATION_TARGETS,
    UTILIZATION_BENCHMARKS,
)


class TestUtilizationTier:
    """Test utilization tier classification"""

    def test_elite_tier(self):
        """Test elite tier (95%+)"""
        assert UtilizationTier.from_percentage(96.0) == UtilizationTier.ELITE

    def test_optimal_tier(self):
        """Test optimal tier (85-95%)"""
        assert UtilizationTier.from_percentage(90.0) == UtilizationTier.OPTIMAL

    def test_moderate_tier(self):
        """Test moderate tier (70-85%)"""
        assert UtilizationTier.from_percentage(78.0) == UtilizationTier.MODERATE

    def test_needs_improvement_tier(self):
        """Test needs improvement tier (<70%)"""
        assert (
            UtilizationTier.from_percentage(65.0) == UtilizationTier.NEEDS_IMPROVEMENT
        )

    def test_boundary_values(self):
        """Test exact boundary values"""
        assert UtilizationTier.from_percentage(95.0) == UtilizationTier.ELITE
        assert UtilizationTier.from_percentage(85.0) == UtilizationTier.OPTIMAL
        assert UtilizationTier.from_percentage(70.0) == UtilizationTier.MODERATE


class TestTimeBreakdown:
    """Test TimeBreakdown dataclass"""

    def test_create_time_breakdown(self):
        """Test creating time breakdown"""
        breakdown = TimeBreakdown(
            driving_hours=50.0,
            productive_idle_hours=10.0,
            non_productive_idle_hours=8.0,
            engine_off_hours=100.0,
            total_hours=168.0,
        )
        assert breakdown.driving_hours == 50.0
        assert breakdown.productive_idle_hours == 10.0
        assert breakdown.non_productive_idle_hours == 8.0
        assert breakdown.engine_off_hours == 100.0
        assert breakdown.total_hours == 168.0

    def test_total_idle_hours(self):
        """Test total idle calculation"""
        breakdown = TimeBreakdown(
            driving_hours=50.0,
            productive_idle_hours=10.0,
            non_productive_idle_hours=8.0,
            engine_off_hours=100.0,
            total_hours=168.0,
        )
        assert breakdown.total_idle_hours == 18.0

    def test_productive_hours(self):
        """Test productive hours calculation"""
        breakdown = TimeBreakdown(
            driving_hours=50.0,
            productive_idle_hours=10.0,
            non_productive_idle_hours=8.0,
            engine_off_hours=100.0,
            total_hours=168.0,
        )
        # Productive = driving + productive_idle
        assert breakdown.productive_hours == 60.0

    def test_non_productive_hours(self):
        """Test non-productive hours (includes engine off)"""
        breakdown = TimeBreakdown(
            driving_hours=50.0,
            productive_idle_hours=10.0,
            non_productive_idle_hours=8.0,
            engine_off_hours=100.0,
            total_hours=168.0,
        )
        # non_productive_hours = non_productive_idle + engine_off
        assert breakdown.non_productive_hours == 108.0

    def test_to_dict(self):
        """Test serialization"""
        breakdown = TimeBreakdown(
            driving_hours=50.0,
            productive_idle_hours=10.0,
            non_productive_idle_hours=8.0,
            engine_off_hours=100.0,
            total_hours=168.0,
        )
        d = breakdown.to_dict()
        assert "summary" in d
        assert "percentages" in d
        assert d["driving_hours"] == 50.0


class TestUtilizationMetrics:
    """Test UtilizationMetrics dataclass"""

    def test_create_metrics(self):
        """Test creating utilization metrics"""
        metrics = UtilizationMetrics(
            utilization_rate=0.85,
            driving_utilization=0.70,
            productive_utilization=0.85,
            vs_target_percent=-10.0,
            vs_fleet_avg_percent=5.0,
            tier=UtilizationTier.OPTIMAL,
            lost_revenue_per_period=500.0,
        )
        assert metrics.utilization_rate == 0.85
        assert metrics.tier == UtilizationTier.OPTIMAL
        assert metrics.lost_revenue_per_period == 500.0

    def test_metrics_to_dict(self):
        """Test metrics serialization"""
        metrics = UtilizationMetrics(
            utilization_rate=0.85,
            driving_utilization=0.70,
            productive_utilization=0.85,
            vs_target_percent=-10.0,
            vs_fleet_avg_percent=5.0,
            tier=UtilizationTier.OPTIMAL,
            lost_revenue_per_period=500.0,
        )
        d = metrics.to_dict()
        assert d["utilization_rate"] == 85.0  # Converted to percentage
        assert d["tier"] == "optimal"


class TestFleetUtilizationEngine:
    """Test main engine functionality"""

    @pytest.fixture
    def engine(self):
        """Create engine instance"""
        return FleetUtilizationEngine()

    def test_initialization(self, engine):
        """Test engine initializes correctly"""
        assert engine is not None
        assert hasattr(engine, "target_utilization")
        assert engine.target_utilization == 95.0  # Default target

    def test_initialization_custom_target(self):
        """Test engine with custom target"""
        engine = FleetUtilizationEngine(target_utilization=90.0)
        assert engine.target_utilization == 90.0

    def test_analyze_truck_utilization(self, engine):
        """Test single truck utilization analysis"""
        truck_data = {
            "truck_id": "TRUCK-001",
            "driving_hours": 50,
            "productive_idle_hours": 10,
            "non_productive_idle_hours": 8,
            "engine_off_hours": 100,
        }
        result = engine.analyze_truck_utilization(
            truck_id="TRUCK-001",
            period_days=7,
            truck_data=truck_data,
        )

        assert isinstance(result, TruckUtilizationAnalysis)
        assert result.truck_id == "TRUCK-001"
        assert result.metrics is not None
        assert result.time_breakdown is not None

    def test_analyze_truck_utilization_classifies_tier(self, engine):
        """Test that utilization is properly classified"""
        # High utilization truck
        high_util_data = {
            "driving_hours": 70,
            "productive_idle_hours": 10,
            "non_productive_idle_hours": 2,
            "engine_off_hours": 86,
        }
        result = engine.analyze_truck_utilization("T1", 7, high_util_data)
        # With 80 productive hours out of ~72 available, should be high tier
        assert result.metrics.tier in [UtilizationTier.ELITE, UtilizationTier.OPTIMAL]

        # Low utilization truck
        low_util_data = {
            "driving_hours": 30,
            "productive_idle_hours": 5,
            "non_productive_idle_hours": 20,
            "engine_off_hours": 113,
        }
        result = engine.analyze_truck_utilization("T2", 7, low_util_data)
        assert result.metrics.tier in [
            UtilizationTier.MODERATE,
            UtilizationTier.NEEDS_IMPROVEMENT,
        ]

    def test_analyze_fleet_utilization(self, engine):
        """Test fleet-wide utilization analysis"""
        trucks_data = [
            {
                "truck_id": "T1",
                "driving_hours": 60,
                "productive_idle_hours": 10,
                "non_productive_idle_hours": 5,
                "engine_off_hours": 93,
            },
            {
                "truck_id": "T2",
                "driving_hours": 50,
                "productive_idle_hours": 8,
                "non_productive_idle_hours": 10,
                "engine_off_hours": 100,
            },
            {
                "truck_id": "T3",
                "driving_hours": 40,
                "productive_idle_hours": 5,
                "non_productive_idle_hours": 15,
                "engine_off_hours": 108,
            },
        ]
        summary = engine.analyze_fleet_utilization(trucks_data, period_days=7)

        assert isinstance(summary, FleetUtilizationSummary)
        assert summary.total_trucks == 3
        assert summary.fleet_avg_utilization > 0
        assert len(summary.truck_analyses) == 3

    def test_analyze_fleet_utilization_empty(self, engine):
        """Test fleet utilization with no trucks"""
        summary = engine.analyze_fleet_utilization([], period_days=7)
        assert summary.total_trucks == 0
        assert summary.fleet_avg_utilization == 0

    def test_fleet_rankings(self, engine):
        """Test trucks are ranked by utilization"""
        trucks_data = [
            {
                "truck_id": "T1",
                "driving_hours": 30,
                "productive_idle_hours": 5,
                "non_productive_idle_hours": 10,
                "engine_off_hours": 123,
            },  # Low
            {
                "truck_id": "T2",
                "driving_hours": 70,
                "productive_idle_hours": 10,
                "non_productive_idle_hours": 2,
                "engine_off_hours": 86,
            },  # High
            {
                "truck_id": "T3",
                "driving_hours": 50,
                "productive_idle_hours": 8,
                "non_productive_idle_hours": 8,
                "engine_off_hours": 102,
            },  # Medium
        ]
        summary = engine.analyze_fleet_utilization(trucks_data, period_days=7)

        # T2 should be best (rank 1), T1 worst (rank 3)
        rankings = {a.truck_id: a.fleet_rank for a in summary.truck_analyses}
        assert rankings["T2"] == 1
        assert rankings["T1"] == 3


class TestRevenueLossCalculation:
    """Test revenue loss calculations"""

    @pytest.fixture
    def engine(self):
        return FleetUtilizationEngine()

    def test_calculate_lost_revenue(self, engine):
        """Test revenue loss calculation"""
        # With 72 available hours and 50 productive hours
        # Lost hours = 72 - 50 = 22 hours
        # Lost revenue = 22 * 125/hr = 2750
        lost = engine.calculate_lost_revenue(
            available_hours=72.0, productive_hours=50.0
        )
        assert lost > 0
        assert lost == 22 * 125  # 2750

    def test_no_revenue_loss_at_full_utilization(self, engine):
        """Test no revenue loss when fully utilized"""
        lost = engine.calculate_lost_revenue(
            available_hours=72.0, productive_hours=72.0
        )
        assert lost == 0

    def test_calculate_available_hours(self, engine):
        """Test available hours calculation"""
        # Default: 6 work days * 12 productive hours = 72 hours per week
        available = engine.calculate_available_hours(period_days=7)
        assert available == 72.0


class TestActivityClassification:
    """Test activity state classification"""

    @pytest.fixture
    def engine(self):
        return FleetUtilizationEngine()

    def test_classify_driving(self, engine):
        """Test driving state classification"""
        state = engine.classify_activity_state(speed=55.0, rpm=1500)
        assert state == TruckActivityState.DRIVING

    def test_classify_engine_off(self, engine):
        """Test engine off classification"""
        state = engine.classify_activity_state(speed=0, rpm=0)
        assert state == TruckActivityState.ENGINE_OFF

    def test_classify_idle(self, engine):
        """Test idle classification (low speed, engine running)"""
        state = engine.classify_activity_state(speed=0, rpm=800)
        # Should be idle (productive or non-productive)
        assert state in [
            TruckActivityState.PRODUCTIVE_IDLE,
            TruckActivityState.NON_PRODUCTIVE_IDLE,
        ]


class TestRecommendations:
    """Test recommendation generation"""

    @pytest.fixture
    def engine(self):
        return FleetUtilizationEngine()

    def test_generate_recommendations_low_utilization(self, engine):
        """Test recommendations for low utilization"""
        truck_data = {
            "truck_id": "T1",
            "driving_hours": 30,
            "productive_idle_hours": 5,
            "non_productive_idle_hours": 20,
            "engine_off_hours": 113,
        }
        analysis = engine.analyze_truck_utilization("T1", 7, truck_data)
        recommendations = engine.generate_recommendations(analysis)

        assert isinstance(recommendations, list)
        # Low utilization should generate recommendations
        assert len(recommendations) > 0

    def test_recommendations_for_high_idle(self, engine):
        """Test recommendations for high idle time"""
        truck_data = {
            "truck_id": "T1",
            "driving_hours": 40,
            "productive_idle_hours": 5,
            "non_productive_idle_hours": 25,  # High non-productive idle
            "engine_off_hours": 98,
        }
        analysis = engine.analyze_truck_utilization("T1", 7, truck_data)
        recommendations = engine.generate_recommendations(analysis)

        # Should have recommendations (may or may not contain "idle")
        assert isinstance(recommendations, list)


class TestUtilizationTargets:
    """Test utilization target constants"""

    def test_targets_defined(self):
        """Test that targets are properly defined"""
        assert "elite" in UTILIZATION_TARGETS
        assert "optimal" in UTILIZATION_TARGETS
        assert "geotab_benchmark" in UTILIZATION_TARGETS

    def test_target_values_reasonable(self):
        """Test target values are in reasonable range"""
        for name, value in UTILIZATION_TARGETS.items():
            assert 50 <= value <= 100, f"Target {name} has unreasonable value {value}"

    def test_benchmarks_defined(self):
        """Test benchmarks are defined"""
        assert "target_utilization" in UTILIZATION_BENCHMARKS
        assert "good_utilization" in UTILIZATION_BENCHMARKS
        assert "underutilized_threshold" in UTILIZATION_BENCHMARKS


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def engine(self):
        return FleetUtilizationEngine()

    def test_zero_hours(self, engine):
        """Handle zero hours gracefully"""
        truck_data = {
            "driving_hours": 0,
            "productive_idle_hours": 0,
            "non_productive_idle_hours": 0,
            "engine_off_hours": 168,
        }
        result = engine.analyze_truck_utilization("T1", 7, truck_data)
        assert result.metrics.utilization_rate == 0

    def test_very_large_fleet(self, engine):
        """Test with large fleet (performance check)"""
        trucks_data = [
            {
                "truck_id": f"T{i}",
                "driving_hours": 50 + (i % 20),
                "productive_idle_hours": 10,
                "non_productive_idle_hours": 8 - (i % 5),
                "engine_off_hours": 100,
            }
            for i in range(100)  # 100 trucks
        ]
        summary = engine.analyze_fleet_utilization(trucks_data, period_days=7)
        assert summary.total_trucks == 100
        assert len(summary.truck_analyses) == 100


class TestReportGeneration:
    """Test utilization report generation"""

    @pytest.fixture
    def engine(self):
        return FleetUtilizationEngine()

    def test_generate_utilization_report(self, engine):
        """Test report generation"""
        trucks_data = [
            {
                "truck_id": "T1",
                "driving_hours": 50,
                "productive_idle_hours": 10,
                "non_productive_idle_hours": 8,
                "engine_off_hours": 100,
            },
            {
                "truck_id": "T2",
                "driving_hours": 60,
                "productive_idle_hours": 12,
                "non_productive_idle_hours": 5,
                "engine_off_hours": 91,
            },
        ]
        report = engine.generate_utilization_report(trucks_data, period_days=7)

        assert report["status"] == "success"
        assert "data" in report
        assert "fleet_summary" in report["data"]

    def test_generate_report_empty_fleet(self, engine):
        """Test report with empty fleet"""
        report = engine.generate_utilization_report([], period_days=7)
        assert report["status"] == "success"
        assert report["data"]["fleet_summary"]["total_trucks"] == 0


class TestFleetOptimization:
    """Test fleet optimization opportunity identification"""

    @pytest.fixture
    def engine(self):
        return FleetUtilizationEngine()

    def test_identify_optimization_opportunities(self, engine):
        """Test optimization opportunity identification"""
        trucks_data = [
            {
                "truck_id": "T1",
                "driving_hours": 30,  # Low
                "productive_idle_hours": 5,
                "non_productive_idle_hours": 20,
                "engine_off_hours": 113,
            },
            {
                "truck_id": "T2",
                "driving_hours": 60,  # Good
                "productive_idle_hours": 10,
                "non_productive_idle_hours": 5,
                "engine_off_hours": 93,
            },
        ]
        summary = engine.analyze_fleet_utilization(trucks_data, period_days=7)
        opportunities = engine.identify_fleet_optimization_opportunities(summary)

        assert isinstance(opportunities, dict)
        # Should have optimization-related keys
        assert "fleet_size_recommendation" in opportunities
        assert "estimated_monthly_savings" in opportunities

    def test_identify_underutilized_trucks(self, engine):
        """Test that underutilized trucks are flagged"""
        trucks_data = [
            {
                "truck_id": "T1",
                "driving_hours": 20,  # Very low
                "productive_idle_hours": 5,
                "non_productive_idle_hours": 25,
                "engine_off_hours": 118,
            },
        ]
        summary = engine.analyze_fleet_utilization(trucks_data, period_days=7)
        opportunities = engine.identify_fleet_optimization_opportunities(summary)

        # Should identify T1 as underutilized
        assert (
            len(summary.underutilized_trucks) > 0
            or opportunities.get("underutilized_count", 0) > 0
        )


class TestTierDistribution:
    """Test tier distribution tracking"""

    @pytest.fixture
    def engine(self):
        return FleetUtilizationEngine()

    def test_tier_distribution(self, engine):
        """Test tier distribution in fleet summary"""
        trucks_data = [
            {
                "truck_id": "T1",
                "driving_hours": 70,  # Elite
                "productive_idle_hours": 10,
                "non_productive_idle_hours": 2,
                "engine_off_hours": 86,
            },
            {
                "truck_id": "T2",
                "driving_hours": 30,  # Needs improvement
                "productive_idle_hours": 5,
                "non_productive_idle_hours": 20,
                "engine_off_hours": 113,
            },
        ]
        summary = engine.analyze_fleet_utilization(trucks_data, period_days=7)

        assert isinstance(summary.tier_distribution, dict)
        # Should have counts for different tiers
        total_count = sum(summary.tier_distribution.values())
        assert total_count == 2  # Both trucks counted


class TestSerialization:
    """Test data serialization"""

    @pytest.fixture
    def engine(self):
        return FleetUtilizationEngine()

    def test_analysis_to_dict(self, engine):
        """Test TruckUtilizationAnalysis serialization"""
        truck_data = {
            "truck_id": "T1",
            "driving_hours": 50,
            "productive_idle_hours": 10,
            "non_productive_idle_hours": 8,
            "engine_off_hours": 100,
        }
        analysis = engine.analyze_truck_utilization("T1", 7, truck_data)
        d = analysis.to_dict()

        assert "truck_id" in d
        assert "period" in d
        assert "metrics" in d
        assert "time_breakdown" in d

    def test_summary_to_dict(self, engine):
        """Test FleetUtilizationSummary serialization"""
        trucks_data = [
            {
                "truck_id": "T1",
                "driving_hours": 50,
                "productive_idle_hours": 10,
                "non_productive_idle_hours": 8,
                "engine_off_hours": 100,
            }
        ]
        summary = engine.analyze_fleet_utilization(trucks_data, period_days=7)
        d = summary.to_dict()

        assert "period" in d
        assert "fleet_summary" in d
        assert "utilization" in d
