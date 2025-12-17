"""
Tests for MPG Context Engine
═══════════════════════════════════════════════════════════════════════════════
"""

import pytest
from mpg_context import (
    MPGContextEngine,
    RouteContext,
    MPGExpectation,
    RouteType,
    WeatherCondition,
)


class TestMPGContextEngine:
    """Test suite for MPG context calculations"""

    def test_highway_empty_clear_optimal(self):
        """Highway + Empty + Clear = Best MPG"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.HIGHWAY,
            avg_speed_mph=65.0,
            stop_count=2,
            elevation_change_ft=100,
            distance_miles=200,
            is_loaded=False,
            weather=WeatherCondition.CLEAR,
        )
        
        result = engine.calculate_expected_mpg(context)
        
        # Highway baseline = 6.5, empty = +15%
        assert result.expected_mpg > 7.0
        assert result.baseline_mpg == 6.5
        assert result.load_factor == 1.15  # empty
        assert result.confidence > 0.7

    def test_city_loaded_rain_poor(self):
        """City + Loaded + Rain = Poor MPG"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.CITY,
            avg_speed_mph=25.0,
            stop_count=50,
            elevation_change_ft=50,
            distance_miles=40,
            is_loaded=True,
            load_weight_lbs=35000,  # Heavy load
            weather=WeatherCondition.RAIN,
        )
        
        result = engine.calculate_expected_mpg(context)
        
        # City baseline = 4.8, loaded, rain penalty
        assert result.expected_mpg < 5.0
        assert result.baseline_mpg == 4.8
        assert result.weather_factor < 1.0  # rain penalty

    def test_mountain_overloaded_snow_extreme(self):
        """Mountain + Overloaded + Snow = Extreme penalty"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.MOUNTAIN,
            avg_speed_mph=40.0,
            stop_count=20,
            elevation_change_ft=5000,
            distance_miles=100,
            is_loaded=True,
            load_weight_lbs=45000,  # Overloaded
            weather=WeatherCondition.SNOW,
        )
        
        result = engine.calculate_expected_mpg(context)
        
        # Mountain baseline = 4.2, overloaded, snow, terrain
        assert result.expected_mpg < 4.0
        assert result.baseline_mpg == 4.2
        assert result.load_factor == 0.90  # overloaded

    def test_route_classification_highway(self):
        """High speed, few stops = Highway"""
        engine = MPGContextEngine()
        
        route = engine.classify_route(
            avg_speed_mph=65.0,
            stop_count=5,
            distance_miles=200,
            elevation_change_ft=100,
        )
        
        assert route == RouteType.HIGHWAY

    def test_route_classification_city(self):
        """Low speed, many stops = City"""
        engine = MPGContextEngine()
        
        route = engine.classify_route(
            avg_speed_mph=25.0,
            stop_count=60,
            distance_miles=30,
            elevation_change_ft=50,
        )
        
        assert route == RouteType.CITY

    def test_route_classification_mountain(self):
        """High elevation change = Mountain"""
        engine = MPGContextEngine()
        
        route = engine.classify_route(
            avg_speed_mph=45.0,
            stop_count=15,
            distance_miles=100,
            elevation_change_ft=12000,  # 120 ft/mile
        )
        
        assert route == RouteType.MOUNTAIN

    def test_route_classification_suburban(self):
        """Medium speed, medium stops = Suburban"""
        engine = MPGContextEngine()
        
        route = engine.classify_route(
            avg_speed_mph=40.0,
            stop_count=24,
            distance_miles=60,
            elevation_change_ft=200,
        )
        
        assert route == RouteType.SUBURBAN

    def test_load_factor_empty(self):
        """Empty load should boost MPG"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.HIGHWAY,
            avg_speed_mph=60.0,
            stop_count=5,
            elevation_change_ft=100,
            distance_miles=100,
            is_loaded=False,
        )
        
        result = engine.calculate_expected_mpg(context)
        assert result.load_factor == 1.15

    def test_load_factor_normal(self):
        """Normal load should be neutral"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.HIGHWAY,
            avg_speed_mph=60.0,
            stop_count=5,
            elevation_change_ft=100,
            distance_miles=100,
            is_loaded=True,
            load_weight_lbs=25000,  # Normal load (62.5% of 40k capacity)
        )
        
        result = engine.calculate_expected_mpg(context)
        assert result.load_factor == 1.0

    def test_load_factor_heavy(self):
        """Heavy load should penalize MPG"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.HIGHWAY,
            avg_speed_mph=60.0,
            stop_count=5,
            elevation_change_ft=100,
            distance_miles=100,
            is_loaded=True,
            load_weight_lbs=35000,  # Heavy (87.5% of capacity)
        )
        
        result = engine.calculate_expected_mpg(context)
        assert result.load_factor == 0.95

    def test_load_factor_overloaded(self):
        """Overloaded should heavily penalize MPG"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.HIGHWAY,
            avg_speed_mph=60.0,
            stop_count=5,
            elevation_change_ft=100,
            distance_miles=100,
            is_loaded=True,
            load_weight_lbs=45000,  # Overloaded (112.5% of capacity)
        )
        
        result = engine.calculate_expected_mpg(context)
        assert result.load_factor == 0.90

    def test_weather_factor_clear(self):
        """Clear weather should be neutral"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.HIGHWAY,
            avg_speed_mph=60.0,
            stop_count=5,
            elevation_change_ft=100,
            distance_miles=100,
            is_loaded=False,
            weather=WeatherCondition.CLEAR,
        )
        
        result = engine.calculate_expected_mpg(context)
        assert result.weather_factor == 1.0

    def test_weather_factor_rain(self):
        """Rain should reduce MPG"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.HIGHWAY,
            avg_speed_mph=60.0,
            stop_count=5,
            elevation_change_ft=100,
            distance_miles=100,
            is_loaded=False,
            weather=WeatherCondition.RAIN,
        )
        
        result = engine.calculate_expected_mpg(context)
        assert result.weather_factor < 1.0

    def test_weather_factor_snow(self):
        """Snow should reduce MPG significantly"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.HIGHWAY,
            avg_speed_mph=60.0,
            stop_count=5,
            elevation_change_ft=100,
            distance_miles=100,
            is_loaded=False,
            weather=WeatherCondition.SNOW,
        )
        
        result = engine.calculate_expected_mpg(context)
        assert result.weather_factor < 0.95

    def test_weather_factor_extreme_cold(self):
        """Extreme cold should heavily reduce MPG"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.HIGHWAY,
            avg_speed_mph=60.0,
            stop_count=5,
            elevation_change_ft=100,
            distance_miles=100,
            is_loaded=False,
            weather=WeatherCondition.EXTREME_COLD,
            ambient_temp_f=-10,
        )
        
        result = engine.calculate_expected_mpg(context)
        assert result.weather_factor < 0.90

    def test_driver_score_meets_expectation(self):
        """Driver achieving expected MPG gets no penalty"""
        engine = MPGContextEngine()
        
        adjusted = engine.adjust_driver_score(
            raw_mpg=5.0,
            expected_mpg=5.0,
            raw_score=85.0,
        )
        
        # No adjustment needed
        assert 84.0 <= adjusted <= 86.0

    def test_driver_score_exceeds_expectation(self):
        """Driver beating expectation gets bonus"""
        engine = MPGContextEngine()
        
        adjusted = engine.adjust_driver_score(
            raw_mpg=6.5,
            expected_mpg=5.0,
            raw_score=80.0,
        )
        
        # 30% better should get bonus
        assert adjusted > 80.0

    def test_driver_score_below_expectation(self):
        """Driver below expectation gets penalty"""
        engine = MPGContextEngine()
        
        adjusted = engine.adjust_driver_score(
            raw_mpg=4.0,
            expected_mpg=5.0,
            raw_score=80.0,
        )
        
        # 20% worse = penalty
        assert adjusted < 80.0

    def test_polynomial_combination(self):
        """All factors should multiply correctly"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.SUBURBAN,
            avg_speed_mph=45.0,
            stop_count=30,
            elevation_change_ft=1500,
            distance_miles=100,
            is_loaded=True,
            load_weight_lbs=35000,  # Heavy
            weather=WeatherCondition.RAIN,
        )
        
        result = engine.calculate_expected_mpg(context)
        
        # Suburban baseline = 5.5
        assert result.baseline_mpg == 5.5
        # All factors should combine multiplicatively
        expected = result.baseline_mpg * result.route_factor * result.load_factor * result.weather_factor * result.terrain_factor
        assert abs(result.expected_mpg - expected) < 0.01

    def test_mixed_route_type(self):
        """Mixed route should work"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.MIXED,
            avg_speed_mph=50.0,
            stop_count=20,
            elevation_change_ft=500,
            distance_miles=150,
            is_loaded=False,
        )
        
        result = engine.calculate_expected_mpg(context)
        
        # Mixed should have valid MPG
        assert result.expected_mpg > 0
        assert result.expected_mpg < 10

    def test_zero_distance_edge_case(self):
        """Zero distance should handle gracefully"""
        engine = MPGContextEngine()
        
        # Should not crash with zero distance
        route = engine.classify_route(
            avg_speed_mph=30.0,
            stop_count=0,
            distance_miles=0.01,  # Near zero
            elevation_change_ft=0,
        )
        
        assert route in [RouteType.HIGHWAY, RouteType.CITY, RouteType.SUBURBAN, RouteType.MOUNTAIN, RouteType.MIXED]

    def test_all_factors_present_in_result(self):
        """Result should contain all factor breakdowns"""
        engine = MPGContextEngine()
        
        context = RouteContext(
            route_type=RouteType.HIGHWAY,
            avg_speed_mph=65.0,
            stop_count=5,
            elevation_change_ft=100,
            distance_miles=200,
            is_loaded=False,
            weather=WeatherCondition.CLEAR,
        )
        
        result = engine.calculate_expected_mpg(context)
        
        assert result.baseline_mpg is not None
        assert result.expected_mpg is not None
        assert result.route_factor is not None
        assert result.load_factor is not None
        assert result.weather_factor is not None
        assert result.terrain_factor is not None


@pytest.fixture
def sample_engine():
    """Fixture providing engine instance"""
    return MPGContextEngine()


@pytest.fixture
def highway_context():
    """Fixture providing highway context"""
    return RouteContext(
        route_type=RouteType.HIGHWAY,
        avg_speed_mph=65.0,
        stop_count=5,
        elevation_change_ft=100,
        distance_miles=200,
        is_loaded=False,
        weather=WeatherCondition.CLEAR,
    )


@pytest.fixture
def city_context():
    """Fixture providing city context"""
    return RouteContext(
        route_type=RouteType.CITY,
        avg_speed_mph=25.0,
        stop_count=40,
        elevation_change_ft=50,
        distance_miles=40,
        is_loaded=True,
        load_weight_lbs=35000,
        weather=WeatherCondition.RAIN,
    )


def test_with_fixtures(sample_engine, highway_context, city_context):
    """Test using fixtures"""
    highway_result = sample_engine.calculate_expected_mpg(highway_context)
    city_result = sample_engine.calculate_expected_mpg(city_context)
    
    # Highway should have better MPG than city
    assert highway_result.expected_mpg > city_result.expected_mpg
    
    # Highway should have better baseline
    assert highway_result.baseline_mpg > city_result.baseline_mpg
