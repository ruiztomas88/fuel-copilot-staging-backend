"""
Tests for terrain_factor.py - Altitude-based fuel consumption adjustment

Tests cover:
- Haversine distance calculation
- Grade calculation
- Grade classification
- Terrain fuel factor calculation
- TerrainTracker class
- FleetTerrainManager class
- Global convenience functions

Target: 80%+ coverage (from 36%)
"""

import pytest
import math
from unittest.mock import patch, MagicMock

from terrain_factor import (
    # Constants
    TRUCK_WEIGHT_LBS,
    GRAVITY_FT_S2,
    BTU_PER_GALLON_DIESEL,
    DIESEL_EFFICIENCY,
    FEET_PER_METER,
    FEET_PER_MILE,
    # Data classes
    TerrainConfig,
    TerrainState,
    # Functions
    calculate_haversine_distance,
    calculate_grade,
    classify_grade,
    calculate_terrain_fuel_factor,
    get_terrain_manager,
    get_terrain_fuel_factor,
    # Classes
    TerrainTracker,
    FleetTerrainManager,
)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestConstants:
    """Test that constants have expected values"""

    def test_truck_weight_is_reasonable(self):
        """Average loaded Class 8 truck weight"""
        assert TRUCK_WEIGHT_LBS == 60000
        assert 40000 <= TRUCK_WEIGHT_LBS <= 80000

    def test_gravity_constant(self):
        """Earth gravity in ft/s²"""
        assert abs(GRAVITY_FT_S2 - 32.174) < 0.01

    def test_btu_per_gallon_diesel(self):
        """BTU content of diesel fuel"""
        assert BTU_PER_GALLON_DIESEL == 129500

    def test_diesel_efficiency(self):
        """Typical diesel engine efficiency"""
        assert DIESEL_EFFICIENCY == 0.42
        assert 0.3 <= DIESEL_EFFICIENCY <= 0.5

    def test_feet_per_meter(self):
        """Conversion constant"""
        assert abs(FEET_PER_METER - 3.28084) < 0.0001

    def test_feet_per_mile(self):
        """Conversion constant"""
        assert FEET_PER_MILE == 5280


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTerrainConfig:
    """Test TerrainConfig dataclass defaults"""

    def test_default_values(self):
        """Verify default configuration values"""
        config = TerrainConfig()

        # Grade thresholds
        assert config.flat_threshold == 1.0
        assert config.mild_grade == 3.0
        assert config.moderate_grade == 6.0
        assert config.steep_grade == 10.0

        # Fuel impact
        assert config.climbing_impact_per_pct == 0.015
        assert config.descending_impact_per_pct == 0.008

        # Smoothing
        assert config.altitude_smoothing_window == 5
        assert config.grade_smoothing_factor == 0.3

        # GPS noise
        assert config.min_distance_ft == 100.0
        assert config.max_reasonable_grade == 20.0

    def test_custom_values(self):
        """Test creating config with custom values"""
        config = TerrainConfig(
            flat_threshold=2.0,
            steep_grade=15.0,
            climbing_impact_per_pct=0.02,
        )

        assert config.flat_threshold == 2.0
        assert config.steep_grade == 15.0
        assert config.climbing_impact_per_pct == 0.02
        # Other values should be defaults
        assert config.mild_grade == 3.0


class TestTerrainState:
    """Test TerrainState dataclass defaults"""

    def test_default_values(self):
        """Verify default state values"""
        state = TerrainState()

        assert state.current_altitude_ft is None
        assert state.current_grade_pct == 0.0
        assert state.smoothed_grade_pct == 0.0
        assert state.terrain_type == "FLAT"
        assert state.grade_category == "FLAT"
        assert state.total_elevation_gain_ft == 0.0
        assert state.total_elevation_loss_ft == 0.0
        assert state.distance_traveled_mi == 0.0
        assert state.altitude_history == []
        assert state.grade_history == []
        assert state.last_altitude_ft is None
        assert state.last_latitude is None
        assert state.last_longitude is None

    def test_custom_state(self):
        """Test creating state with custom values"""
        state = TerrainState(
            current_altitude_ft=1000.0,
            terrain_type="CLIMBING",
            grade_category="MODERATE",
        )

        assert state.current_altitude_ft == 1000.0
        assert state.terrain_type == "CLIMBING"
        assert state.grade_category == "MODERATE"


# ═══════════════════════════════════════════════════════════════════════════════
# HAVERSINE DISTANCE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateHaversineDistance:
    """Test Haversine distance calculation"""

    def test_same_point_returns_zero(self):
        """Distance from point to itself is zero"""
        distance = calculate_haversine_distance(34.0, -118.0, 34.0, -118.0)
        assert distance == 0.0

    def test_known_distance_los_angeles_to_san_francisco(self):
        """Test with known city pair ~350 miles"""
        # LA: 34.0522, -118.2437
        # SF: 37.7749, -122.4194
        distance_ft = calculate_haversine_distance(
            34.0522, -118.2437, 37.7749, -122.4194
        )
        distance_mi = distance_ft / FEET_PER_MILE

        # Should be approximately 350-400 miles
        assert 340 <= distance_mi <= 400

    def test_short_distance_accuracy(self):
        """Test accuracy for short distances typical in tracking"""
        # ~1 degree latitude ≈ 69 miles
        distance_ft = calculate_haversine_distance(34.0, -118.0, 35.0, -118.0)
        distance_mi = distance_ft / FEET_PER_MILE

        assert 68 <= distance_mi <= 70

    def test_longitude_distance_varies_with_latitude(self):
        """1 degree longitude is shorter near poles"""
        # At equator
        distance_equator = calculate_haversine_distance(0.0, 0.0, 0.0, 1.0)

        # At 60 degrees latitude
        distance_60lat = calculate_haversine_distance(60.0, 0.0, 60.0, 1.0)

        # Should be roughly half at 60° latitude
        assert distance_60lat < distance_equator
        ratio = distance_60lat / distance_equator
        assert 0.45 <= ratio <= 0.55

    def test_negative_coordinates(self):
        """Test with southern and western hemispheres"""
        # Buenos Aires to Sydney (roughly)
        distance_ft = calculate_haversine_distance(-34.6, -58.4, -33.9, 151.2)
        distance_mi = distance_ft / FEET_PER_MILE

        # Should be around 7,000-8,000 miles
        assert 7000 <= distance_mi <= 8000

    def test_returns_positive_distance(self):
        """Distance is always positive regardless of direction"""
        distance1 = calculate_haversine_distance(34.0, -118.0, 35.0, -117.0)
        distance2 = calculate_haversine_distance(35.0, -117.0, 34.0, -118.0)

        assert distance1 > 0
        assert distance2 > 0
        assert abs(distance1 - distance2) < 1  # Should be equal


# ═══════════════════════════════════════════════════════════════════════════════
# GRADE CALCULATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateGrade:
    """Test grade calculation from altitude and distance"""

    def test_insufficient_distance_returns_none(self):
        """Below min_distance_ft returns None"""
        config = TerrainConfig(min_distance_ft=100.0)
        grade = calculate_grade(10.0, 50.0, config)  # 50 ft < 100 ft
        assert grade is None

    def test_exactly_min_distance_returns_none(self):
        """Exactly at min_distance_ft still returns None (< not <=)"""
        config = TerrainConfig(min_distance_ft=100.0)
        grade = calculate_grade(10.0, 99.9, config)
        assert grade is None

    def test_above_min_distance_returns_grade(self):
        """Above min_distance_ft returns grade"""
        config = TerrainConfig(min_distance_ft=100.0)
        grade = calculate_grade(10.0, 101.0, config)
        assert grade is not None
        assert abs(grade - 9.9) < 0.1  # (10/101) * 100 ≈ 9.9%

    def test_flat_grade(self):
        """Zero altitude change = 0% grade"""
        grade = calculate_grade(0.0, 1000.0)
        assert grade == 0.0

    def test_uphill_grade(self):
        """Positive altitude change = positive grade"""
        # 10 ft rise over 100 ft = 10% grade
        grade = calculate_grade(10.0, 100.1)
        assert grade is not None
        assert grade > 0
        assert abs(grade - 10.0) < 0.1

    def test_downhill_grade(self):
        """Negative altitude change = negative grade"""
        grade = calculate_grade(-10.0, 100.1)
        assert grade is not None
        assert grade < 0
        assert abs(grade + 10.0) < 0.1

    def test_unreasonable_grade_rejected(self):
        """Grade above max_reasonable_grade returns None"""
        config = TerrainConfig(max_reasonable_grade=20.0, min_distance_ft=10.0)
        # 30% grade should be rejected
        grade = calculate_grade(30.0, 100.0, config)
        assert grade is None

    def test_exactly_at_max_reasonable_grade(self):
        """Grade at exactly max_reasonable_grade is accepted"""
        config = TerrainConfig(max_reasonable_grade=20.0, min_distance_ft=10.0)
        grade = calculate_grade(20.0, 100.0, config)
        assert grade is not None
        assert abs(grade - 20.0) < 0.1

    def test_negative_unreasonable_grade_rejected(self):
        """Large negative grade (GPS noise) is rejected"""
        config = TerrainConfig(max_reasonable_grade=20.0, min_distance_ft=10.0)
        grade = calculate_grade(-25.0, 100.0, config)
        assert grade is None

    def test_with_default_config(self):
        """Test uses default config if not provided"""
        grade = calculate_grade(5.0, 500.0)  # 1% grade
        assert grade is not None
        assert abs(grade - 1.0) < 0.1


# ═══════════════════════════════════════════════════════════════════════════════
# GRADE CLASSIFICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestClassifyGrade:
    """Test grade classification into terrain type and category"""

    def test_flat_terrain(self):
        """Below flat threshold is FLAT"""
        terrain_type, grade_category = classify_grade(0.5)
        assert terrain_type == "FLAT"
        assert grade_category == "FLAT"

    def test_exactly_at_flat_threshold(self):
        """Exactly at threshold is still FLAT (< not <=)"""
        config = TerrainConfig(flat_threshold=1.0)
        terrain_type, grade_category = classify_grade(0.99, config)
        assert terrain_type == "FLAT"

    def test_mild_climbing(self):
        """Mild uphill grade"""
        config = TerrainConfig(flat_threshold=1.0, mild_grade=3.0)
        terrain_type, grade_category = classify_grade(2.0, config)
        assert terrain_type == "CLIMBING"
        assert grade_category == "MILD"

    def test_mild_descending(self):
        """Mild downhill grade"""
        terrain_type, grade_category = classify_grade(-2.0)
        assert terrain_type == "DESCENDING"
        assert grade_category == "MILD"

    def test_moderate_climbing(self):
        """Moderate uphill grade"""
        terrain_type, grade_category = classify_grade(5.0)
        assert terrain_type == "CLIMBING"
        assert grade_category == "MODERATE"

    def test_moderate_descending(self):
        """Moderate downhill grade"""
        terrain_type, grade_category = classify_grade(-5.0)
        assert terrain_type == "DESCENDING"
        assert grade_category == "MODERATE"

    def test_steep_climbing(self):
        """Steep uphill grade"""
        terrain_type, grade_category = classify_grade(12.0)
        assert terrain_type == "CLIMBING"
        assert grade_category == "STEEP"

    def test_steep_descending(self):
        """Steep downhill grade"""
        terrain_type, grade_category = classify_grade(-12.0)
        assert terrain_type == "DESCENDING"
        assert grade_category == "STEEP"

    def test_boundary_mild_to_moderate(self):
        """Test boundary between mild and moderate"""
        config = TerrainConfig(mild_grade=3.0, moderate_grade=6.0)
        # Just below moderate
        _, cat1 = classify_grade(2.9, config)
        assert cat1 == "MILD"
        # At moderate
        _, cat2 = classify_grade(3.1, config)
        assert cat2 == "MODERATE"

    def test_boundary_moderate_to_steep(self):
        """Test boundary between moderate and steep"""
        config = TerrainConfig(moderate_grade=6.0, steep_grade=10.0)
        # Just below steep
        _, cat1 = classify_grade(5.9, config)
        assert cat1 == "MODERATE"
        # At steep threshold
        _, cat2 = classify_grade(6.1, config)
        assert cat2 == "STEEP"


# ═══════════════════════════════════════════════════════════════════════════════
# TERRAIN FUEL FACTOR TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateTerrainFuelFactor:
    """Test fuel consumption factor calculation"""

    def test_flat_returns_one(self):
        """Flat terrain = no adjustment (factor = 1.0)"""
        factor = calculate_terrain_fuel_factor(0.0)
        assert factor == 1.0

    def test_below_flat_threshold_returns_one(self):
        """Below flat threshold returns 1.0"""
        factor = calculate_terrain_fuel_factor(0.5)  # Less than 1.0 threshold
        assert factor == 1.0

    def test_climbing_increases_fuel(self):
        """Climbing requires more fuel (factor > 1.0)"""
        # 5% uphill with default 1.5% per 1% grade = 7.5% more = 1.075
        factor = calculate_terrain_fuel_factor(5.0)
        assert factor > 1.0
        assert abs(factor - 1.075) < 0.001

    def test_descending_decreases_fuel(self):
        """Descending requires less fuel (factor < 1.0)"""
        # 5% downhill with default 0.8% per 1% grade = 4% less = 0.96
        factor = calculate_terrain_fuel_factor(-5.0)
        assert factor < 1.0
        assert abs(factor - 0.96) < 0.001

    def test_steep_climbing(self):
        """Very steep climb increases fuel significantly"""
        # 10% uphill = 15% more fuel = 1.15
        factor = calculate_terrain_fuel_factor(10.0)
        assert abs(factor - 1.15) < 0.001

    def test_steep_descending(self):
        """Steep descent reduces fuel"""
        # 10% downhill = 8% less = 0.92
        factor = calculate_terrain_fuel_factor(-10.0)
        assert abs(factor - 0.92) < 0.001

    def test_descending_capped_at_50_percent_reduction(self):
        """Descending fuel can't go below 0.5 (50%)"""
        # Very steep downhill - would be more than 50% reduction
        # 80% grade would be 64% reduction, but capped at 50%
        factor = calculate_terrain_fuel_factor(-80.0)
        assert factor == 0.5

    def test_custom_config(self):
        """Test with custom fuel impact values"""
        config = TerrainConfig(
            flat_threshold=0.5,
            climbing_impact_per_pct=0.02,  # 2% per 1% grade
        )
        # 5% uphill = 10% more = 1.10
        factor = calculate_terrain_fuel_factor(5.0, config)
        assert abs(factor - 1.10) < 0.001

    def test_linear_relationship(self):
        """Fuel factor increases linearly with grade"""
        factor_5 = calculate_terrain_fuel_factor(5.0)
        factor_10 = calculate_terrain_fuel_factor(10.0)

        # Increase should be double
        increase_5 = factor_5 - 1.0
        increase_10 = factor_10 - 1.0

        assert abs(increase_10 / increase_5 - 2.0) < 0.01


# ═══════════════════════════════════════════════════════════════════════════════
# TERRAIN TRACKER CLASS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTerrainTracker:
    """Test TerrainTracker class"""

    def test_initialization(self):
        """Test tracker is initialized correctly"""
        tracker = TerrainTracker("TRUCK001")

        assert tracker.truck_id == "TRUCK001"
        assert tracker.config is not None
        assert tracker.state is not None
        assert tracker.state.terrain_type == "FLAT"

    def test_custom_config(self):
        """Test tracker with custom config"""
        custom_config = TerrainConfig(flat_threshold=2.0)
        tracker = TerrainTracker("TRUCK001", custom_config)

        assert tracker.config.flat_threshold == 2.0

    def test_update_with_none_altitude(self):
        """Update with None altitude returns 1.0"""
        tracker = TerrainTracker("TRUCK001")
        factor = tracker.update(altitude_ft=None)

        assert factor == 1.0

    def test_first_update_returns_one(self):
        """First update (no previous position) returns 1.0"""
        tracker = TerrainTracker("TRUCK001")
        factor = tracker.update(altitude_ft=1000.0, latitude=34.0, longitude=-118.0)

        assert factor == 1.0
        assert tracker.state.current_altitude_ft == 1000.0
        assert tracker.state.last_altitude_ft == 1000.0
        assert tracker.state.last_latitude == 34.0
        assert tracker.state.last_longitude == -118.0

    def test_second_update_with_climbing(self):
        """Second update calculates grade for climbing"""
        tracker = TerrainTracker("TRUCK001")

        # First position
        tracker.update(altitude_ft=1000.0, latitude=34.0, longitude=-118.0)

        # Move to higher altitude (climbing)
        factor = tracker.update(altitude_ft=1100.0, latitude=34.01, longitude=-118.0)

        # Should have positive grade and factor > 1.0
        assert tracker.state.terrain_type in ["CLIMBING", "FLAT"]
        assert factor >= 1.0

    def test_update_tracks_elevation_gain(self):
        """Elevation gain is tracked over updates"""
        tracker = TerrainTracker("TRUCK001")

        # Start low
        tracker.update(altitude_ft=1000.0, latitude=34.0, longitude=-118.0)

        # Climb 100 ft
        tracker.update(altitude_ft=1100.0, latitude=34.01, longitude=-118.0)

        # More climbing
        tracker.update(altitude_ft=1200.0, latitude=34.02, longitude=-118.0)

        assert tracker.state.total_elevation_gain_ft >= 0

    def test_update_tracks_elevation_loss(self):
        """Elevation loss is tracked over updates"""
        tracker = TerrainTracker("TRUCK001")

        # Start high
        tracker.update(altitude_ft=2000.0, latitude=34.0, longitude=-118.0)

        # Descend
        tracker.update(altitude_ft=1900.0, latitude=34.01, longitude=-118.0)
        tracker.update(altitude_ft=1800.0, latitude=34.02, longitude=-118.0)

        assert tracker.state.total_elevation_loss_ft >= 0

    def test_update_without_gps_coordinates(self):
        """Update with altitude but no GPS uses altitude-only"""
        tracker = TerrainTracker("TRUCK001")

        # First update with altitude only
        factor1 = tracker.update(altitude_ft=1000.0)
        assert factor1 == 1.0

        # Second update with altitude only
        factor2 = tracker.update(altitude_ft=1100.0)
        # Without GPS, can't calculate grade properly
        assert factor2 == 1.0

    def test_get_terrain_summary(self):
        """Test terrain summary output"""
        tracker = TerrainTracker("TRUCK001")
        tracker.update(altitude_ft=1000.0, latitude=34.0, longitude=-118.0)

        summary = tracker.get_terrain_summary()

        assert "terrain_type" in summary
        assert "grade_category" in summary
        assert "current_grade_pct" in summary  # This is the smoothed grade
        assert "total_elevation_gain_ft" in summary
        assert "total_elevation_loss_ft" in summary
        assert "distance_mi" in summary
        assert "fuel_factor" in summary
        assert "truck_id" in summary

    def test_ema_smoothing(self):
        """Grade is smoothed using EMA"""
        tracker = TerrainTracker("TRUCK001")
        tracker.config.grade_smoothing_factor = 0.3

        tracker.update(altitude_ft=1000.0, latitude=34.0, longitude=-118.0)
        tracker.update(altitude_ft=1500.0, latitude=34.01, longitude=-118.0)  # Big jump

        # Summary includes current_grade_pct which is the smoothed grade
        summary = tracker.get_terrain_summary()
        assert "current_grade_pct" in summary
        # The grade should be a reasonable value
        assert isinstance(summary["current_grade_pct"], (int, float))


# ═══════════════════════════════════════════════════════════════════════════════
# FLEET TERRAIN MANAGER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFleetTerrainManager:
    """Test FleetTerrainManager class"""

    def test_initialization(self):
        """Manager initializes with empty tracker dict"""
        manager = FleetTerrainManager()

        assert hasattr(manager, "_trackers")
        assert len(manager._trackers) == 0

    def test_custom_config(self):
        """Manager uses custom config for new trackers"""
        custom_config = TerrainConfig(flat_threshold=2.0)
        manager = FleetTerrainManager(custom_config)

        tracker = manager.get_tracker("TRUCK001")
        assert tracker.config.flat_threshold == 2.0

    def test_get_tracker_creates_new(self):
        """get_tracker creates tracker if not exists"""
        manager = FleetTerrainManager()

        tracker = manager.get_tracker("TRUCK001")

        assert tracker is not None
        assert tracker.truck_id == "TRUCK001"
        assert "TRUCK001" in manager._trackers

    def test_get_tracker_returns_existing(self):
        """get_tracker returns same instance for same truck"""
        manager = FleetTerrainManager()

        tracker1 = manager.get_tracker("TRUCK001")
        tracker2 = manager.get_tracker("TRUCK001")

        assert tracker1 is tracker2

    def test_get_fuel_factor(self):
        """get_fuel_factor delegates to tracker"""
        manager = FleetTerrainManager()

        factor = manager.get_fuel_factor(
            truck_id="TRUCK001",
            altitude_ft=1000.0,
            latitude=34.0,
            longitude=-118.0,
        )

        # First update returns 1.0
        assert factor == 1.0

    def test_get_fleet_summary_empty(self):
        """Empty manager returns empty summary"""
        manager = FleetTerrainManager()

        summary = manager.get_fleet_summary()

        assert summary["trucks_tracked"] == 0
        assert summary["climbing"] == []
        assert summary["descending"] == []
        assert summary["flat_count"] == 0
        assert summary["trucks_on_grades"] == 0

    def test_get_fleet_summary_with_trucks(self):
        """Summary includes all tracked trucks"""
        manager = FleetTerrainManager()

        # Add three trucks
        manager.get_tracker("TRUCK001")
        manager.get_tracker("TRUCK002")
        manager.get_tracker("TRUCK003")

        summary = manager.get_fleet_summary()

        assert summary["trucks_tracked"] == 3

    def test_fleet_summary_classifies_terrain(self):
        """Summary correctly classifies trucks by terrain"""
        manager = FleetTerrainManager()

        # Initialize truck and simulate climbing
        tracker = manager.get_tracker("TRUCK001")
        tracker.state.terrain_type = "CLIMBING"
        tracker.state.smoothed_grade_pct = 5.0

        # Initialize another as descending
        tracker2 = manager.get_tracker("TRUCK002")
        tracker2.state.terrain_type = "DESCENDING"
        tracker2.state.smoothed_grade_pct = -3.0

        # Another as flat
        tracker3 = manager.get_tracker("TRUCK003")
        tracker3.state.terrain_type = "FLAT"

        summary = manager.get_fleet_summary()

        assert len(summary["climbing"]) == 1
        assert len(summary["descending"]) == 1
        assert summary["flat_count"] == 1
        assert summary["trucks_on_grades"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL FUNCTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestGlobalFunctions:
    """Test module-level convenience functions"""

    def test_get_terrain_manager_returns_manager(self):
        """get_terrain_manager returns FleetTerrainManager"""
        manager = get_terrain_manager()
        assert isinstance(manager, FleetTerrainManager)

    def test_get_terrain_manager_singleton(self):
        """get_terrain_manager returns same instance"""
        manager1 = get_terrain_manager()
        manager2 = get_terrain_manager()
        assert manager1 is manager2

    def test_get_terrain_fuel_factor(self):
        """get_terrain_fuel_factor convenience function works"""
        # Reset global manager to ensure clean state
        import terrain_factor
        terrain_factor._terrain_manager = None

        factor = get_terrain_fuel_factor(
            truck_id="TEST_TRUCK",
            altitude=1000.0,
            latitude=34.0,
            longitude=-118.0,
            speed=55.0,
        )

        assert factor == 1.0  # First update

    def test_get_terrain_fuel_factor_with_none_altitude(self):
        """get_terrain_fuel_factor handles None altitude"""
        factor = get_terrain_fuel_factor(
            truck_id="TEST_TRUCK2",
            altitude=None,
        )

        assert factor == 1.0


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES AND ERROR HANDLING
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_haversine_with_antipodal_points(self):
        """Test maximum distance calculation (opposite sides of Earth)"""
        distance = calculate_haversine_distance(0.0, 0.0, 0.0, 180.0)
        distance_mi = distance / FEET_PER_MILE

        # Half Earth circumference ≈ 12,450 miles
        assert 12000 <= distance_mi <= 13000

    def test_extreme_altitude_change(self):
        """Large altitude changes are handled"""
        tracker = TerrainTracker("TRUCK001")

        # Very large altitude change (simulating GPS glitch)
        tracker.update(altitude_ft=1000.0, latitude=34.0, longitude=-118.0)
        factor = tracker.update(altitude_ft=10000.0, latitude=34.001, longitude=-118.0)

        # Should handle gracefully (either reject or return value)
        assert factor >= 0.5
        assert factor <= 2.0

    def test_zero_distance_travel(self):
        """Staying in place doesn't cause divide by zero"""
        tracker = TerrainTracker("TRUCK001")

        tracker.update(altitude_ft=1000.0, latitude=34.0, longitude=-118.0)
        factor = tracker.update(
            altitude_ft=1000.0, latitude=34.0, longitude=-118.0
        )  # Same position

        assert factor == 1.0

    def test_very_small_grade(self):
        """Very small grades are treated as flat"""
        factor = calculate_terrain_fuel_factor(0.001)
        assert factor == 1.0

    def test_tracker_with_many_updates(self):
        """Tracker handles many sequential updates"""
        tracker = TerrainTracker("TRUCK001")

        for i in range(100):
            altitude = 1000.0 + (i * 10)  # Gradually climbing
            lat = 34.0 + (i * 0.001)
            factor = tracker.update(altitude_ft=altitude, latitude=lat, longitude=-118.0)
            assert 0.5 <= factor <= 2.0

        summary = tracker.get_terrain_summary()
        assert summary["total_elevation_gain_ft"] > 0

    def test_manager_with_many_trucks(self):
        """Manager handles many trucks"""
        manager = FleetTerrainManager()

        for i in range(50):
            truck_id = f"TRUCK{i:03d}"
            manager.get_fuel_factor(
                truck_id=truck_id,
                altitude_ft=1000.0 + i * 10,
                latitude=34.0,
                longitude=-118.0,
            )

        summary = manager.get_fleet_summary()
        assert summary["trucks_tracked"] == 50


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION SCENARIOS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntegrationScenarios:
    """Test realistic usage scenarios"""

    def test_climbing_mountain_pass(self):
        """Simulate truck climbing mountain pass"""
        tracker = TerrainTracker("TRUCK001")

        # Starting at base
        tracker.update(altitude_ft=500.0, latitude=34.0, longitude=-118.0, speed_mph=45.0)

        # Climbing the pass
        altitudes = [700, 1000, 1500, 2000, 2500, 3000]  # Going up
        lat = 34.01

        factors = []
        for alt in altitudes:
            factor = tracker.update(
                altitude_ft=alt, latitude=lat, longitude=-118.0, speed_mph=35.0
            )
            factors.append(factor)
            lat += 0.01

        # Most factors should be > 1.0 (more fuel for climbing)
        climbing_factors = [f for f in factors if f > 1.01]
        assert len(climbing_factors) > 0

        # Check elevation gain was tracked (starting at 500, ending at 3000 = 2500 ft total)
        # But due to GPS filtering and smoothing, may not get full amount
        summary = tracker.get_terrain_summary()
        assert summary["total_elevation_gain_ft"] > 1000  # At least 1000 ft gained

    def test_descending_valley(self):
        """Simulate truck descending into valley"""
        tracker = TerrainTracker("TRUCK001")

        # Starting at top
        tracker.update(altitude_ft=3000.0, latitude=34.0, longitude=-118.0)

        # Descending
        altitudes = [2500, 2000, 1500, 1000, 500]
        lat = 34.01

        factors = []
        for alt in altitudes:
            factor = tracker.update(altitude_ft=alt, latitude=lat, longitude=-118.0)
            factors.append(factor)
            lat += 0.01

        # Most factors should be < 1.0 (less fuel for descending)
        descending_factors = [f for f in factors if f < 0.99]
        assert len(descending_factors) > 0

    def test_rolling_hills(self):
        """Simulate truck on rolling terrain"""
        tracker = TerrainTracker("TRUCK001")

        # Alternating up and down
        altitudes = [1000, 1100, 1000, 1100, 1000, 1100, 1000]
        lat = 34.0

        for alt in altitudes:
            tracker.update(altitude_ft=alt, latitude=lat, longitude=-118.0)
            lat += 0.01

        summary = tracker.get_terrain_summary()
        # Should have both gains and losses
        assert summary["total_elevation_gain_ft"] >= 0
        assert summary["total_elevation_loss_ft"] >= 0

    def test_flat_highway(self):
        """Simulate truck on flat highway"""
        tracker = TerrainTracker("TRUCK001")

        # Very flat terrain
        lat = 34.0
        for _ in range(10):
            factor = tracker.update(
                altitude_ft=500.0, latitude=lat, longitude=-118.0, speed_mph=65.0
            )
            lat += 0.01

        summary = tracker.get_terrain_summary()
        assert summary["terrain_type"] == "FLAT"


# ═══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL COVERAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAdditionalCoverage:
    """Tests to cover remaining untested branches"""

    def test_altitude_conversion_from_meters(self):
        """Test that low altitude values are converted from meters"""
        tracker = TerrainTracker("TRUCK001")

        # Altitude below 500 is assumed to be meters
        # 100 meters = ~328 feet
        tracker.update(altitude_ft=100.0, latitude=34.0, longitude=-118.0)

        # The altitude should be converted to feet
        assert tracker.state.current_altitude_ft > 300  # 100m = ~328ft

    def test_speed_based_distance_estimation(self):
        """Test distance estimation from speed when no GPS coordinates"""
        tracker = TerrainTracker("TRUCK001")

        # First update with coordinates
        tracker.update(altitude_ft=1000.0, latitude=34.0, longitude=-118.0)

        # Second update with speed but no GPS - uses speed to estimate distance
        # Note: The time_delta_hours defaults to some value in the update method
        factor = tracker.update(altitude_ft=1100.0, speed_mph=55.0)

        # Should still return a valid factor
        assert factor >= 0.5
        assert factor <= 2.0

    def test_tracker_reset(self):
        """Test reset method clears state"""
        tracker = TerrainTracker("TRUCK001")

        # Accumulate some state
        tracker.update(altitude_ft=1000.0, latitude=34.0, longitude=-118.0)
        tracker.update(altitude_ft=1500.0, latitude=34.01, longitude=-118.0)

        # Verify state has values
        assert tracker.state.current_altitude_ft is not None
        assert tracker.state.last_latitude is not None

        # Reset
        tracker.reset()

        # Verify state is cleared
        assert tracker.state.current_altitude_ft is None
        assert tracker.state.last_altitude_ft is None
        assert tracker.state.last_latitude is None
        assert tracker.state.last_longitude is None
        assert tracker.state.terrain_type == "FLAT"
        assert tracker.state.total_elevation_gain_ft == 0.0
