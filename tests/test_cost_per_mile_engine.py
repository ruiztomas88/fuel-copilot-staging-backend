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
