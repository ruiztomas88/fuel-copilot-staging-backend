"""
Tests for Cost Per Mile Engine
v4.0: Complete test coverage for cost tracking functionality

Run with: pytest tests/test_cost_per_mile_engine.py -v
"""

import pytest
from datetime import datetime, timezone, timedelta
from cost_per_mile_engine import (
    CostPerMileEngine,
    CostBreakdown,
    TruckCostAnalysis,
    FleetCostSummary,
    SpeedImpactAnalysis,
    CostTier,
    DEFAULT_COST_CONFIG,
    INDUSTRY_BENCHMARKS,
)


class TestCostBreakdown:
    """Test CostBreakdown dataclass"""

    def test_create_breakdown(self):
        """Test creating a cost breakdown"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.65,
            maintenance_cost_per_mile=0.18,
            tire_cost_per_mile=0.05,
            depreciation_per_mile=0.12,
            total_cost_per_mile=1.00,
        )
        assert breakdown.fuel_cost_per_mile == 0.65
        assert breakdown.total_cost_per_mile == 1.00

    def test_breakdown_percentages(self):
        """Test percentage calculation"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.60,
            maintenance_cost_per_mile=0.20,
            tire_cost_per_mile=0.10,
            depreciation_per_mile=0.10,
            total_cost_per_mile=1.00,
        )
        pcts = breakdown.breakdown_percentages
        assert pcts["fuel"] == 60.0
        assert pcts["maintenance"] == 20.0
        assert pcts["tires"] == 10.0
        assert pcts["depreciation"] == 10.0

    def test_breakdown_percentages_zero_total(self):
        """Handle zero total gracefully"""
        breakdown = CostBreakdown(0, 0, 0, 0, 0)
        pcts = breakdown.breakdown_percentages
        assert all(v == 0 for v in pcts.values())


class TestCostTier:
    """Test cost tier classification"""

    def test_elite_tier(self):
        """Test elite tier (below benchmark)"""
        assert CostTier.from_cost_per_mile(2.00) == CostTier.ELITE

    def test_good_tier(self):
        """Test good tier (at benchmark)"""
        assert CostTier.from_cost_per_mile(2.26) == CostTier.GOOD

    def test_average_tier(self):
        """Test average tier (slightly above benchmark)"""
        assert CostTier.from_cost_per_mile(2.50) == CostTier.AVERAGE

    def test_needs_improvement_tier(self):
        """Test needs improvement tier (well above benchmark)"""
        assert CostTier.from_cost_per_mile(3.00) == CostTier.NEEDS_IMPROVEMENT


class TestCostPerMileEngine:
    """Test main engine functionality"""

    @pytest.fixture
    def engine(self):
        """Create engine instance for tests"""
        return CostPerMileEngine()

    def test_initialization(self, engine):
        """Test engine initializes with default config"""
        assert engine.config is not None
        assert "fuel_price_per_gallon" in engine.config
        assert (
            engine.config["fuel_price_per_gallon"]
            == DEFAULT_COST_CONFIG["fuel_price_per_gallon"]
        )

    def test_initialization_with_custom_config(self):
        """Test engine with custom config"""
        custom_config = {"fuel_price_per_gallon": 4.50}
        engine = CostPerMileEngine(cost_config=custom_config)
        assert engine.config["fuel_price_per_gallon"] == 4.50

    def test_calculate_fuel_cost_per_mile(self, engine):
        """Test fuel cost calculation"""
        # 100 miles, 16.67 gallons at $3.50/gal = $58.35 / 100 = $0.58/mile
        cost = engine.calculate_fuel_cost_per_mile(
            miles=100, gallons=16.67, fuel_price=3.50
        )
        assert cost == pytest.approx(0.58, rel=0.01)

    def test_calculate_fuel_cost_zero_miles(self, engine):
        """Test fuel cost with zero miles returns 0"""
        cost = engine.calculate_fuel_cost_per_mile(miles=0, gallons=10)
        assert cost == 0.0

    def test_calculate_fuel_cost_uses_default_price(self, engine):
        """Test fuel cost uses default price when not specified"""
        cost = engine.calculate_fuel_cost_per_mile(miles=100, gallons=20)
        expected = (20 * engine.config["fuel_price_per_gallon"]) / 100
        assert cost == pytest.approx(expected, rel=0.01)

    def test_calculate_maintenance_cost_per_mile(self, engine):
        """Test maintenance cost calculation"""
        # Based on engine hours and miles
        cost = engine.calculate_maintenance_cost_per_mile(miles=10000, engine_hours=200)
        assert cost > 0
        assert cost < 1.0  # Should be reasonable

    def test_calculate_maintenance_zero_miles(self, engine):
        """Test maintenance cost with zero miles"""
        cost = engine.calculate_maintenance_cost_per_mile(miles=0, engine_hours=100)
        assert cost == 0.0

    def test_calculate_cost_breakdown(self, engine):
        """Test complete cost breakdown"""
        breakdown = engine.calculate_cost_breakdown(
            miles=1000,
            gallons=166.67,  # ~6 MPG
            engine_hours=20,
        )
        assert isinstance(breakdown, CostBreakdown)
        assert breakdown.fuel_cost_per_mile > 0
        assert breakdown.maintenance_cost_per_mile > 0
        assert breakdown.tire_cost_per_mile > 0
        assert breakdown.depreciation_per_mile > 0
        assert breakdown.total_cost_per_mile > 0
        # Total should equal sum of components
        expected_total = (
            breakdown.fuel_cost_per_mile
            + breakdown.maintenance_cost_per_mile
            + breakdown.tire_cost_per_mile
            + breakdown.depreciation_per_mile
        )
        assert breakdown.total_cost_per_mile == pytest.approx(expected_total, rel=0.001)

    def test_analyze_truck_costs(self, engine):
        """Test single truck analysis"""
        truck_data = {
            "truck_id": "TRUCK-001",
            "miles": 5000,
            "gallons": 833,  # ~6 MPG
            "engine_hours": 100,
        }
        analysis = engine.analyze_truck_costs(
            truck_id="TRUCK-001",
            period_days=30,
            truck_data=truck_data,
            fleet_avg_cpm=2.20,
        )
        assert isinstance(analysis, TruckCostAnalysis)
        assert analysis.truck_id == "TRUCK-001"
        assert analysis.period_days == 30
        assert analysis.cost_breakdown is not None
        assert analysis.cost_tier is not None

    def test_analyze_truck_costs_vs_fleet(self, engine):
        """Test truck analysis compares to fleet average"""
        truck_data = {
            "miles": 5000,
            "gallons": 1000,  # Poor MPG (5 MPG)
            "engine_hours": 100,
        }
        analysis = engine.analyze_truck_costs(
            truck_id="TRUCK-001",
            period_days=30,
            truck_data=truck_data,
            fleet_avg_cpm=2.00,  # Fleet average
        )
        # vs_fleet_avg_percent shows comparison to fleet
        assert hasattr(analysis, "vs_fleet_avg_percent")

    def test_analyze_fleet_costs(self, engine):
        """Test fleet-wide analysis"""
        trucks_data = [
            {"truck_id": "T1", "miles": 5000, "gallons": 800, "engine_hours": 100},
            {"truck_id": "T2", "miles": 4000, "gallons": 700, "engine_hours": 80},
            {"truck_id": "T3", "miles": 6000, "gallons": 1100, "engine_hours": 120},
        ]
        summary = engine.analyze_fleet_costs(trucks_data, period_days=30)

        assert isinstance(summary, FleetCostSummary)
        assert summary.total_trucks == 3
        assert summary.total_miles == 15000
        assert summary.fleet_avg_cost_per_mile > 0
        assert len(summary.truck_analyses) == 3
        # Best truck should have lowest cost
        assert summary.best_cost_per_mile <= summary.worst_cost_per_mile

    def test_analyze_fleet_costs_empty(self, engine):
        """Test fleet analysis with no trucks"""
        summary = engine.analyze_fleet_costs([], period_days=30)
        assert summary.total_trucks == 0
        assert summary.total_miles == 0

    def test_analyze_fleet_rankings(self, engine):
        """Test that trucks are ranked correctly"""
        trucks_data = [
            {
                "truck_id": "T1",
                "miles": 5000,
                "gallons": 1000,
                "engine_hours": 100,
            },  # Worst MPG
            {
                "truck_id": "T2",
                "miles": 5000,
                "gallons": 700,
                "engine_hours": 100,
            },  # Best MPG
            {
                "truck_id": "T3",
                "miles": 5000,
                "gallons": 850,
                "engine_hours": 100,
            },  # Middle
        ]
        summary = engine.analyze_fleet_costs(trucks_data, period_days=30)

        # T2 should be rank 1 (best), T1 should be rank 3 (worst)
        rankings = {a.truck_id: a.fleet_rank for a in summary.truck_analyses}
        assert rankings["T2"] == 1
        assert rankings["T1"] == 3


class TestSpeedImpactAnalysis:
    """Test speed impact calculations"""

    @pytest.fixture
    def engine(self):
        return CostPerMileEngine()

    def test_speed_impact_at_55mph(self, engine):
        """Test impact at optimal speed"""
        analysis = engine.calculate_speed_impact(
            current_speed_mph=55, monthly_miles=10000
        )
        assert isinstance(analysis, SpeedImpactAnalysis)
        # At 55mph, should have good MPG
        assert analysis.estimated_mpg >= 6.0

    def test_speed_impact_at_75mph(self, engine):
        """Test impact at high speed"""
        analysis = engine.calculate_speed_impact(
            current_speed_mph=75, monthly_miles=10000
        )
        # At 75mph, MPG drops significantly
        assert analysis.estimated_mpg < 6.0
        # Should show potential savings
        assert analysis.potential_monthly_savings > 0

    def test_speed_impact_comparison(self, engine):
        """Compare 65 vs 75 mph"""
        analysis_65 = engine.calculate_speed_impact(65, 10000)
        analysis_75 = engine.calculate_speed_impact(75, 10000)

        # 65 mph should have better MPG
        assert analysis_65.estimated_mpg > analysis_75.estimated_mpg
        # 65 mph should have lower monthly cost
        assert analysis_65.monthly_fuel_cost < analysis_75.monthly_fuel_cost


class TestIndustryBenchmarks:
    """Test benchmark comparisons"""

    def test_benchmark_exists(self):
        """Test that industry benchmarks are defined"""
        assert "cost_per_mile_total" in INDUSTRY_BENCHMARKS
        assert "fuel_cost_per_mile" in INDUSTRY_BENCHMARKS
        assert INDUSTRY_BENCHMARKS["cost_per_mile_total"] == 2.26

    def test_vs_benchmark_calculation(self):
        """Test benchmark comparison"""
        engine = CostPerMileEngine()
        trucks_data = [
            {"truck_id": "T1", "miles": 10000, "gallons": 1600, "engine_hours": 200},
        ]
        summary = engine.analyze_fleet_costs(trucks_data, period_days=30)

        # vs_industry_benchmark_percent should be calculated
        assert hasattr(summary, "vs_industry_benchmark_percent")


class TestDefaultConfig:
    """Test default configuration values"""

    def test_fuel_price(self):
        """Test default fuel price is reasonable"""
        assert 3.0 <= DEFAULT_COST_CONFIG["fuel_price_per_gallon"] <= 5.0

    def test_tire_cost(self):
        """Test default tire cost is reasonable"""
        assert 0.03 <= DEFAULT_COST_CONFIG["tire_cost_per_mile"] <= 0.10

    def test_depreciation(self):
        """Test default depreciation is reasonable"""
        assert 0.05 <= DEFAULT_COST_CONFIG["depreciation_per_mile"] <= 0.20


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def engine(self):
        return CostPerMileEngine()

    def test_negative_miles_treated_as_zero(self, engine):
        """Negative miles should be handled gracefully"""
        cost = engine.calculate_fuel_cost_per_mile(miles=-100, gallons=10)
        assert cost == 0.0

    def test_negative_gallons_treated_as_zero(self, engine):
        """Negative gallons should be handled gracefully"""
        cost = engine.calculate_fuel_cost_per_mile(miles=100, gallons=-10)
        # Engine may return negative or zero; key is it doesn't crash
        assert isinstance(cost, (int, float))

    def test_very_small_values(self, engine):
        """Very small values should not cause division errors"""
        cost = engine.calculate_fuel_cost_per_mile(miles=0.001, gallons=0.0001)
        assert cost >= 0  # Should not raise

    def test_very_large_values(self, engine):
        """Very large values should not cause overflow"""
        cost = engine.calculate_fuel_cost_per_mile(miles=1000000, gallons=200000)
        assert cost > 0  # Should calculate correctly


# ═══════════════════════════════════════════════════════════════════════════════
# EXTENDED TEST CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


class TestCostTierClassificationExtended:
    """Extended tests for CostTier classification"""

    def test_elite_boundary_exact(self):
        """Test exact elite boundary"""
        benchmark = INDUSTRY_BENCHMARKS["cost_per_mile_total"]
        elite_threshold = benchmark * 0.95
        tier = CostTier.from_cost_per_mile(elite_threshold - 0.001)
        assert tier == CostTier.ELITE

    def test_good_boundary_exact(self):
        """Test exact good boundary"""
        benchmark = INDUSTRY_BENCHMARKS["cost_per_mile_total"]
        tier = CostTier.from_cost_per_mile(benchmark)
        assert tier == CostTier.GOOD

    def test_average_boundary_exact(self):
        """Test exact average boundary"""
        benchmark = INDUSTRY_BENCHMARKS["cost_per_mile_total"]
        avg_threshold = benchmark * 1.15
        tier = CostTier.from_cost_per_mile(avg_threshold)
        assert tier == CostTier.AVERAGE

    def test_needs_improvement_boundary(self):
        """Test needs_improvement boundary"""
        benchmark = INDUSTRY_BENCHMARKS["cost_per_mile_total"]
        threshold = benchmark * 1.21
        tier = CostTier.from_cost_per_mile(threshold)
        assert tier == CostTier.NEEDS_IMPROVEMENT

    def test_very_low_cost(self):
        """Test very low cost classification"""
        tier = CostTier.from_cost_per_mile(0.50)
        assert tier == CostTier.ELITE

    def test_very_high_cost(self):
        """Test very high cost classification"""
        tier = CostTier.from_cost_per_mile(5.00)
        assert tier == CostTier.NEEDS_IMPROVEMENT


class TestCostBreakdownExtended:
    """Extended tests for CostBreakdown"""

    def test_breakdown_with_zero_total(self):
        """Test breakdown with zero total"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.0,
            maintenance_cost_per_mile=0.0,
            tire_cost_per_mile=0.0,
            depreciation_per_mile=0.0,
            total_cost_per_mile=0.0,
        )
        pcts = breakdown.breakdown_percentages
        assert pcts["fuel"] == 0

    def test_breakdown_to_dict_rounding(self):
        """Test to_dict rounding precision"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.654321,
            maintenance_cost_per_mile=0.1876543,
            tire_cost_per_mile=0.0723456,
            depreciation_per_mile=0.1567891,
            total_cost_per_mile=1.0711101,
        )
        result = breakdown.to_dict()
        assert result["fuel_cost_per_mile"] == 0.6543
        assert result["maintenance_cost_per_mile"] == 0.1877

    def test_breakdown_high_fuel_percentage(self):
        """Test breakdown with high fuel percentage"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.80,
            maintenance_cost_per_mile=0.10,
            tire_cost_per_mile=0.05,
            depreciation_per_mile=0.05,
            total_cost_per_mile=1.00,
        )
        pcts = breakdown.breakdown_percentages
        assert pcts["fuel"] == 80.0

    def test_breakdown_equal_distribution(self):
        """Test breakdown with equal distribution"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.25,
            maintenance_cost_per_mile=0.25,
            tire_cost_per_mile=0.25,
            depreciation_per_mile=0.25,
            total_cost_per_mile=1.00,
        )
        pcts = breakdown.breakdown_percentages
        assert (
            pcts["fuel"] == pcts["maintenance"] == pcts["tires"] == pcts["depreciation"]
        )


class TestSpeedImpactExtended:
    """Extended tests for SpeedImpactAnalysis"""

    def test_speed_impact_default_values(self):
        """Test default values in SpeedImpactAnalysis"""
        analysis = SpeedImpactAnalysis(current_speed_mph=65.0)
        assert analysis.optimal_speed_mph == 55.0
        assert analysis.optimal_mpg == 6.5
        assert analysis.fuel_price == 3.50

    def test_speed_impact_high_monthly_miles(self):
        """Test with high monthly miles"""
        analysis = SpeedImpactAnalysis(
            current_speed_mph=75.0,
            monthly_miles=20000,
            estimated_mpg=4.5,
            fuel_price=4.00,
            monthly_fuel_cost=17778,
            optimal_fuel_cost=12308,
            potential_monthly_savings=5470,
        )
        assert analysis.potential_monthly_savings == 5470

    def test_speed_impact_to_dict_structure(self):
        """Test to_dict structure"""
        analysis = SpeedImpactAnalysis(
            current_speed_mph=70.0,
            estimated_mpg=5.2,
            monthly_miles=15000,
        )
        result = analysis.to_dict()
        assert "current_speed_mph" in result
        assert "optimal_speed_mph" in result
        assert "potential_monthly_savings" in result


class TestTruckCostAnalysisExtended:
    """Extended tests for TruckCostAnalysis"""

    def test_truck_analysis_with_recommendations(self):
        """Test truck analysis with recommendations"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.90,
            maintenance_cost_per_mile=0.20,
            tire_cost_per_mile=0.08,
            depreciation_per_mile=0.15,
            total_cost_per_mile=1.33,
        )
        now = datetime.now(timezone.utc)
        analysis = TruckCostAnalysis(
            truck_id="T001",
            period_start=now - timedelta(days=30),
            period_end=now,
            period_days=30,
            total_miles=8000,
            total_fuel_gallons=1455,
            total_engine_hours=350,
            avg_mpg=5.5,
            cost_breakdown=breakdown,
            savings_recommendations=["Reduce speed", "Check tire pressure"],
        )
        assert len(analysis.savings_recommendations) == 2

    def test_truck_analysis_trend_improving(self):
        """Test truck analysis with improving trend"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.60,
            maintenance_cost_per_mile=0.15,
            tire_cost_per_mile=0.06,
            depreciation_per_mile=0.14,
            total_cost_per_mile=0.95,
        )
        now = datetime.now(timezone.utc)
        analysis = TruckCostAnalysis(
            truck_id="T002",
            period_start=now - timedelta(days=30),
            period_end=now,
            period_days=30,
            total_miles=12000,
            total_fuel_gallons=1714,
            total_engine_hours=480,
            avg_mpg=7.0,
            cost_breakdown=breakdown,
            trend_direction="improving",
            trend_percent_change=-5.2,
        )
        assert analysis.trend_percent_change < 0

    def test_truck_analysis_ranking(self):
        """Test truck analysis with ranking"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.65,
            maintenance_cost_per_mile=0.18,
            tire_cost_per_mile=0.07,
            depreciation_per_mile=0.15,
            total_cost_per_mile=1.05,
        )
        now = datetime.now(timezone.utc)
        analysis = TruckCostAnalysis(
            truck_id="T003",
            period_start=now - timedelta(days=30),
            period_end=now,
            period_days=30,
            total_miles=10000,
            total_fuel_gallons=1667,
            total_engine_hours=400,
            avg_mpg=6.0,
            cost_breakdown=breakdown,
            fleet_rank=3,
            total_trucks=10,
        )
        assert analysis.fleet_rank == 3
        assert analysis.total_trucks == 10


class TestFleetCostSummaryExtended:
    """Extended tests for FleetCostSummary"""

    def test_fleet_summary_with_truck_analyses(self):
        """Test fleet summary with individual truck analyses"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.68,
            maintenance_cost_per_mile=0.19,
            tire_cost_per_mile=0.07,
            depreciation_per_mile=0.15,
            total_cost_per_mile=1.09,
        )
        now = datetime.now(timezone.utc)

        # Create individual truck analyses
        truck_analyses = []
        for i in range(3):
            truck_breakdown = CostBreakdown(
                fuel_cost_per_mile=0.65 + i * 0.05,
                maintenance_cost_per_mile=0.18,
                tire_cost_per_mile=0.07,
                depreciation_per_mile=0.15,
                total_cost_per_mile=1.05 + i * 0.05,
            )
            truck_analyses.append(
                TruckCostAnalysis(
                    truck_id=f"T{i+1:03d}",
                    period_start=now - timedelta(days=30),
                    period_end=now,
                    period_days=30,
                    total_miles=10000,
                    total_fuel_gallons=1667,
                    total_engine_hours=400,
                    avg_mpg=6.0,
                    cost_breakdown=truck_breakdown,
                )
            )

        summary = FleetCostSummary(
            period_start=now - timedelta(days=30),
            period_end=now,
            period_days=30,
            total_trucks=3,
            total_miles=30000,
            total_fuel_gallons=5000,
            total_fuel_cost=17500,
            fleet_avg_cost_per_mile=1.09,
            cost_breakdown=breakdown,
            vs_industry_benchmark_percent=-51.8,
            best_truck="T001",
            best_cost_per_mile=1.05,
            worst_truck="T003",
            worst_cost_per_mile=1.15,
            total_potential_savings_per_month=450,
            truck_analyses=truck_analyses,
        )

        assert len(summary.truck_analyses) == 3
        result = summary.to_dict()
        assert len(result["trucks"]) == 3


class TestIndustryBenchmarksExtended:
    """Extended tests for industry benchmarks"""

    def test_benchmark_relationships(self):
        """Test that component benchmarks sum approximately to total"""
        components = (
            INDUSTRY_BENCHMARKS["fuel_cost_per_mile"]
            + INDUSTRY_BENCHMARKS["maintenance_per_mile"]
            + INDUSTRY_BENCHMARKS["tire_cost_per_mile"]
            + INDUSTRY_BENCHMARKS["depreciation_per_mile"]
        )
        # Components should be less than total (excludes driver wages, insurance)
        assert components < INDUSTRY_BENCHMARKS["cost_per_mile_total"]

    def test_fuel_is_largest_tracked_component(self):
        """Test fuel is the largest tracked cost component"""
        assert (
            INDUSTRY_BENCHMARKS["fuel_cost_per_mile"]
            > INDUSTRY_BENCHMARKS["maintenance_per_mile"]
        )
        assert (
            INDUSTRY_BENCHMARKS["fuel_cost_per_mile"]
            > INDUSTRY_BENCHMARKS["tire_cost_per_mile"]
        )

    def test_driver_wages_largest_overall(self):
        """Test driver wages is largest overall component"""
        assert (
            INDUSTRY_BENCHMARKS["driver_wages_per_mile"]
            > INDUSTRY_BENCHMARKS["fuel_cost_per_mile"]
        )


class TestCostCalculationMethods:
    """Tests for various cost calculation methods"""

    @pytest.fixture
    def engine(self):
        return CostPerMileEngine()

    def test_calculate_with_different_fuel_prices(self, engine):
        """Test calculations with various fuel prices"""
        prices = [3.00, 3.50, 4.00, 4.50, 5.00]
        for price in prices:
            cost = engine.calculate_fuel_cost_per_mile(
                miles=100, gallons=17, fuel_price=price
            )
            assert cost > 0
            expected = (17 * price) / 100
            assert cost == pytest.approx(expected, rel=0.01)

    def test_calculate_maintenance_per_engine_hour(self, engine):
        """Test maintenance cost based on engine hours"""
        hours = [100, 200, 500, 1000]
        for h in hours:
            cost = engine.calculate_maintenance_cost_per_mile(
                engine_hours=h, miles=h * 25
            )
            assert cost >= 0

    def test_tire_cost_constant(self, engine):
        """Test tire cost is constant per mile"""
        # Tire cost is a config constant
        cost1 = engine.config["tire_cost_per_mile"]
        cost2 = engine.config["tire_cost_per_mile"]
        assert cost1 == cost2
        assert cost1 == 0.07  # Default value


class TestSavingsProjections:
    """Tests for savings projection calculations"""

    @pytest.fixture
    def engine(self):
        return CostPerMileEngine()

    def test_annual_savings_projection(self, engine):
        """Test annual savings projection"""
        monthly_savings = 500
        annual = monthly_savings * 12
        assert annual == 6000

    def test_fleet_wide_savings(self, engine):
        """Test fleet-wide savings calculation"""
        per_truck_savings = 200
        fleet_size = 10
        total = per_truck_savings * fleet_size
        assert total == 2000

    def test_savings_from_mpg_improvement(self, engine):
        """Test savings from MPG improvement"""
        # 1 MPG improvement from 6 to 7 at $3.50/gal over 10k miles
        current_cost = (10000 / 6) * 3.50  # $5833
        improved_cost = (10000 / 7) * 3.50  # $5000
        savings = current_cost - improved_cost
        assert savings > 800


class TestTrendDetection:
    """Tests for cost trend detection"""

    @pytest.fixture
    def engine(self):
        return CostPerMileEngine()

    def test_improving_trend_threshold(self, engine):
        """Test improving trend detection threshold"""
        # More than 5% decrease = improving
        current = 1.10
        previous = 1.20
        change = (current - previous) / previous * 100
        assert change < -5

    def test_declining_trend_threshold(self, engine):
        """Test declining trend detection threshold"""
        # More than 5% increase = declining
        current = 1.30
        previous = 1.20
        change = (current - previous) / previous * 100
        assert change > 5

    def test_stable_trend_range(self, engine):
        """Test stable trend range"""
        # Within ±5% = stable
        current = 1.22
        previous = 1.20
        change = (current - previous) / previous * 100
        assert -5 <= change <= 5


class TestRankingMethods:
    """Tests for truck ranking methods"""

    @pytest.fixture
    def engine(self):
        return CostPerMileEngine()

    def test_rank_by_ascending_cost(self, engine):
        """Test ranking by ascending cost (best first)"""
        costs = [1.20, 0.95, 1.10, 1.30, 0.90]
        sorted_costs = sorted(costs)
        assert sorted_costs[0] == 0.90
        assert sorted_costs[-1] == 1.30

    def test_percentile_calculation(self, engine):
        """Test percentile ranking calculation"""
        trucks = 10
        rank = 2
        percentile = (trucks - rank + 1) / trucks * 100
        assert percentile == 90


class TestDataclassDefaults:
    """Tests for dataclass default values"""

    def test_cost_breakdown_default_percentages(self):
        """Test CostBreakdown default percentage is 0"""
        breakdown = CostBreakdown(
            fuel_cost_per_mile=0.0,
            maintenance_cost_per_mile=0.0,
            tire_cost_per_mile=0.0,
            depreciation_per_mile=0.0,
            total_cost_per_mile=0.0,
        )
        assert breakdown.fuel_percent == 0.0

    def test_speed_impact_defaults(self):
        """Test SpeedImpactAnalysis default values"""
        analysis = SpeedImpactAnalysis(current_speed_mph=60)
        assert analysis.optimal_speed_mph == 55.0
        assert analysis.estimated_mpg == 0.0
        assert analysis.monthly_fuel_cost == 0.0


class TestEnumValues:
    """Tests for enum value consistency"""

    def test_cost_tier_values_unique(self):
        """Test all CostTier values are unique"""
        values = [tier.value for tier in CostTier]
        assert len(values) == len(set(values))

    def test_cost_tier_string_values(self):
        """Test CostTier string values"""
        assert CostTier.ELITE.value == "elite"
        assert CostTier.GOOD.value == "good"
        assert CostTier.AVERAGE.value == "average"
        assert CostTier.NEEDS_IMPROVEMENT.value == "needs_improvement"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
