"""
Terrain Factor Module - Altitude-based fuel consumption adjustment

Calculates terrain impact on fuel consumption using GPS altitude data.
Integrates with both:
- Kalman filter (estimator.py) for consumption prediction
- MPG engine for baseline adjustment

Physics:
- Climbing: Extra fuel to overcome gravity (potential energy)
- Descending: Reduced fuel (gravity assists, engine braking)
- Formula: E = m * g * h (potential energy)
- For Class 8 trucks: ~1.5% fuel increase per 1% grade

🆕 v3.12.28: New module for terrain-aware fuel estimation

Author: Fuel Copilot Team
Version: v3.12.28
Date: December 2024
"""

import logging
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from collections import deque
import math

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════════════

# Physics constants for Class 8 trucks
TRUCK_WEIGHT_LBS = 60000  # Average loaded weight
GRAVITY_FT_S2 = 32.174  # ft/s²
BTU_PER_GALLON_DIESEL = 129500  # BTU per gallon of diesel
DIESEL_EFFICIENCY = 0.42  # Typical diesel engine efficiency
FEET_PER_METER = 3.28084
FEET_PER_MILE = 5280


@dataclass
class TerrainConfig:
    """Configuration for terrain factor calculation"""

    # Grade thresholds (%)
    flat_threshold: float = 1.0  # Below this is considered flat
    mild_grade: float = 3.0  # Mild grade threshold
    moderate_grade: float = 6.0  # Moderate grade
    steep_grade: float = 10.0  # Steep grade

    # Fuel impact multipliers (per 1% grade)
    climbing_impact_per_pct: float = 0.015  # 1.5% more fuel per 1% uphill grade
    descending_impact_per_pct: float = 0.008  # 0.8% less fuel per 1% downhill

    # Smoothing settings
    altitude_smoothing_window: int = 5  # Samples for moving average
    grade_smoothing_factor: float = 0.3  # EMA alpha for grade

    # GPS noise rejection
    min_distance_ft: float = 100.0  # Minimum distance for grade calc
    max_reasonable_grade: float = 20.0  # Reject grades above this as GPS noise


@dataclass
class TerrainState:
    """State for terrain tracking"""

    # Current values
    current_altitude_ft: Optional[float] = None
    current_grade_pct: float = 0.0
    smoothed_grade_pct: float = 0.0

    # Terrain classification
    terrain_type: str = "FLAT"  # FLAT, CLIMBING, DESCENDING
    grade_category: str = "FLAT"  # FLAT, MILD, MODERATE, STEEP

    # Running statistics
    total_elevation_gain_ft: float = 0.0
    total_elevation_loss_ft: float = 0.0
    distance_traveled_mi: float = 0.0

    # History for smoothing
    altitude_history: List[float] = field(default_factory=list)
    grade_history: List[float] = field(default_factory=list)

    # Last position for delta calculation
    last_altitude_ft: Optional[float] = None
    last_latitude: Optional[float] = None
    last_longitude: Optional[float] = None


def calculate_haversine_distance(
    lat1: float, lon1: float, lat2: float, lon2: float
) -> float:
    """
    Calculate distance between two GPS coordinates in feet.

    Uses Haversine formula for accuracy.
    """
    R = 3959 * FEET_PER_MILE  # Earth radius in feet

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.asin(math.sqrt(a))

    return R * c


def calculate_grade(
    altitude_delta_ft: float,
    horizontal_distance_ft: float,
    config: TerrainConfig = TerrainConfig(),
) -> Optional[float]:
    """
    Calculate road grade as percentage.

    Grade = (rise / run) * 100

    Args:
        altitude_delta_ft: Elevation change in feet
        horizontal_distance_ft: Horizontal distance traveled in feet
        config: Terrain configuration

    Returns:
        Grade percentage (positive = uphill, negative = downhill)
        None if insufficient data
    """
    if horizontal_distance_ft < config.min_distance_ft:
        return None

    grade_pct = (altitude_delta_ft / horizontal_distance_ft) * 100

    # Reject unreasonable grades (GPS noise)
    if abs(grade_pct) > config.max_reasonable_grade:
        logger.debug(f"Rejecting unreasonable grade: {grade_pct:.1f}%")
        return None

    return grade_pct


def classify_grade(
    grade_pct: float, config: TerrainConfig = TerrainConfig()
) -> Tuple[str, str]:
    """
    Classify grade into terrain type and category.

    Returns:
        Tuple of (terrain_type, grade_category)
        - terrain_type: FLAT, CLIMBING, DESCENDING
        - grade_category: FLAT, MILD, MODERATE, STEEP
    """
    abs_grade = abs(grade_pct)

    # Determine direction
    if abs_grade < config.flat_threshold:
        terrain_type = "FLAT"
    elif grade_pct > 0:
        terrain_type = "CLIMBING"
    else:
        terrain_type = "DESCENDING"

    # Determine severity
    if abs_grade < config.flat_threshold:
        grade_category = "FLAT"
    elif abs_grade < config.mild_grade:
        grade_category = "MILD"
    elif abs_grade < config.moderate_grade:
        grade_category = "MODERATE"
    else:
        grade_category = "STEEP"

    return terrain_type, grade_category


def calculate_terrain_fuel_factor(
    grade_pct: float, config: TerrainConfig = TerrainConfig()
) -> float:
    """
    Calculate fuel consumption multiplier based on grade.

    Returns:
        Factor to multiply base fuel consumption
        - >1.0 for climbing (more fuel)
        - <1.0 for descending (less fuel)
        - =1.0 for flat

    Example:
        >>> calculate_terrain_fuel_factor(5.0)  # 5% uphill
        1.075  # 7.5% more fuel

        >>> calculate_terrain_fuel_factor(-5.0)  # 5% downhill
        0.96   # 4% less fuel
    """
    if abs(grade_pct) < config.flat_threshold:
        return 1.0

    if grade_pct > 0:
        # Climbing: more fuel needed
        impact = config.climbing_impact_per_pct * grade_pct
        return 1.0 + impact
    else:
        # Descending: less fuel needed (but can't go negative)
        impact = config.descending_impact_per_pct * abs(grade_pct)
        return max(0.5, 1.0 - impact)  # Cap at 50% reduction


class TerrainTracker:
    """
    Tracks terrain conditions for a truck.

    Usage:
        tracker = TerrainTracker(truck_id="CO0681")

        # Update with GPS data
        factor = tracker.update(
            altitude_ft=1500.0,
            latitude=34.0522,
            longitude=-118.2437,
            speed_mph=55.0
        )

        # Get fuel consumption adjustment
        adjusted_consumption = base_consumption * factor
    """

    def __init__(self, truck_id: str, config: TerrainConfig = TerrainConfig()):
        self.truck_id = truck_id
        self.config = config
        self.state = TerrainState()

    def update(
        self,
        altitude_ft: Optional[float],
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        speed_mph: Optional[float] = None,
        time_delta_hours: float = 15 / 3600,  # Default 15 seconds
    ) -> float:
        """
        Update terrain tracking with new GPS data.

        Args:
            altitude_ft: Current altitude in feet (or meters, will convert)
            latitude: GPS latitude
            longitude: GPS longitude
            speed_mph: Current speed in MPH
            time_delta_hours: Time since last update

        Returns:
            Fuel consumption factor (multiply by base consumption)
        """
        if altitude_ft is None:
            return 1.0  # No altitude data, assume flat

        # Convert meters to feet if altitude seems to be in meters
        # (Wialon typically reports in meters)
        if altitude_ft < 500:  # Likely meters
            altitude_ft = altitude_ft * FEET_PER_METER

        # Smooth altitude with moving average
        self.state.altitude_history.append(altitude_ft)
        if len(self.state.altitude_history) > self.config.altitude_smoothing_window:
            self.state.altitude_history.pop(0)

        smoothed_altitude = sum(self.state.altitude_history) / len(
            self.state.altitude_history
        )

        # Calculate grade if we have previous position
        if self.state.last_altitude_ft is not None:
            # Calculate horizontal distance
            if (
                latitude
                and longitude
                and self.state.last_latitude
                and self.state.last_longitude
            ):
                horizontal_dist_ft = calculate_haversine_distance(
                    self.state.last_latitude,
                    self.state.last_longitude,
                    latitude,
                    longitude,
                )
            elif speed_mph and speed_mph > 1:
                # Estimate from speed
                horizontal_dist_ft = speed_mph * FEET_PER_MILE * time_delta_hours
            else:
                horizontal_dist_ft = 0

            if horizontal_dist_ft > self.config.min_distance_ft:
                altitude_delta = smoothed_altitude - self.state.last_altitude_ft

                grade = calculate_grade(altitude_delta, horizontal_dist_ft, self.config)

                if grade is not None:
                    # EMA smoothing for grade
                    alpha = self.config.grade_smoothing_factor
                    self.state.smoothed_grade_pct = (
                        alpha * grade + (1 - alpha) * self.state.smoothed_grade_pct
                    )
                    self.state.current_grade_pct = grade

                    # Update terrain classification
                    terrain_type, grade_category = classify_grade(
                        self.state.smoothed_grade_pct, self.config
                    )
                    self.state.terrain_type = terrain_type
                    self.state.grade_category = grade_category

                    # Track cumulative elevation changes
                    if altitude_delta > 0:
                        self.state.total_elevation_gain_ft += altitude_delta
                    else:
                        self.state.total_elevation_loss_ft += abs(altitude_delta)

                    self.state.distance_traveled_mi += (
                        horizontal_dist_ft / FEET_PER_MILE
                    )

        # Update last position
        self.state.last_altitude_ft = smoothed_altitude
        self.state.current_altitude_ft = altitude_ft
        if latitude:
            self.state.last_latitude = latitude
        if longitude:
            self.state.last_longitude = longitude

        # Return fuel factor
        return calculate_terrain_fuel_factor(self.state.smoothed_grade_pct, self.config)

    def get_terrain_summary(self) -> dict:
        """Get summary of terrain conditions"""
        return {
            "truck_id": self.truck_id,
            "current_altitude_ft": self.state.current_altitude_ft,
            "current_grade_pct": round(self.state.smoothed_grade_pct, 1),
            "terrain_type": self.state.terrain_type,
            "grade_category": self.state.grade_category,
            "fuel_factor": round(
                calculate_terrain_fuel_factor(
                    self.state.smoothed_grade_pct, self.config
                ),
                3,
            ),
            "total_elevation_gain_ft": round(self.state.total_elevation_gain_ft, 0),
            "total_elevation_loss_ft": round(self.state.total_elevation_loss_ft, 0),
            "distance_mi": round(self.state.distance_traveled_mi, 1),
        }

    def reset(self):
        """Reset terrain tracking state"""
        self.state = TerrainState()


# ═══════════════════════════════════════════════════════════════════════════════
# FLEET TERRAIN MANAGER
# ═══════════════════════════════════════════════════════════════════════════════


class FleetTerrainManager:
    """
    Manages terrain tracking for entire fleet.

    Usage:
        manager = FleetTerrainManager()

        # Get fuel factor for a truck
        factor = manager.get_fuel_factor(
            truck_id="CO0681",
            altitude_ft=1500,
            latitude=34.05,
            longitude=-118.24,
            speed_mph=55
        )

        # Get fleet terrain summary
        summary = manager.get_fleet_summary()
    """

    def __init__(self, config: TerrainConfig = TerrainConfig()):
        self.config = config
        self._trackers: dict[str, TerrainTracker] = {}

    def get_tracker(self, truck_id: str) -> TerrainTracker:
        """Get or create terrain tracker for truck"""
        if truck_id not in self._trackers:
            self._trackers[truck_id] = TerrainTracker(truck_id, self.config)
        return self._trackers[truck_id]

    def get_fuel_factor(
        self,
        truck_id: str,
        altitude_ft: Optional[float],
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        speed_mph: Optional[float] = None,
    ) -> float:
        """Get terrain-based fuel consumption factor for truck"""
        tracker = self.get_tracker(truck_id)
        return tracker.update(
            altitude_ft=altitude_ft,
            latitude=latitude,
            longitude=longitude,
            speed_mph=speed_mph,
        )

    def get_fleet_summary(self) -> dict:
        """Get terrain summary for all tracked trucks"""
        climbing = []
        descending = []
        flat = []

        for truck_id, tracker in self._trackers.items():
            terrain = tracker.state.terrain_type
            if terrain == "CLIMBING":
                climbing.append(
                    {"truck_id": truck_id, "grade": tracker.state.smoothed_grade_pct}
                )
            elif terrain == "DESCENDING":
                descending.append(
                    {"truck_id": truck_id, "grade": tracker.state.smoothed_grade_pct}
                )
            else:
                flat.append(truck_id)

        return {
            "trucks_tracked": len(self._trackers),
            "climbing": climbing,
            "descending": descending,
            "flat_count": len(flat),
            "trucks_on_grades": len(climbing) + len(descending),
        }


# Global instance for use in sync loop
_terrain_manager: Optional[FleetTerrainManager] = None


def get_terrain_manager() -> FleetTerrainManager:
    """Get or create global terrain manager"""
    global _terrain_manager
    if _terrain_manager is None:
        _terrain_manager = FleetTerrainManager()
    return _terrain_manager


def get_terrain_fuel_factor(
    truck_id: str,
    altitude: Optional[float],
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    speed: Optional[float] = None,
) -> float:
    """
    Convenience function to get terrain fuel factor.

    Usage in wialon_sync_enhanced.py:
        from terrain_factor import get_terrain_fuel_factor

        terrain_factor = get_terrain_fuel_factor(
            truck_id=truck_data.truck_id,
            altitude=truck_data.altitude,
            latitude=truck_data.latitude,
            longitude=truck_data.longitude,
            speed=truck_data.speed
        )

        # Adjust fuel consumption
        adjusted_consumption = base_consumption * terrain_factor
    """
    manager = get_terrain_manager()
    return manager.get_fuel_factor(
        truck_id=truck_id,
        altitude_ft=altitude,
        latitude=latitude,
        longitude=longitude,
        speed_mph=speed,
    )


def calculate_contextualized_mpg(
    raw_mpg: float,
    terrain_factor: float = 1.0,
    weather_factor: float = 1.0,
    load_factor: float = 1.0,
    baseline_mpg: float = 5.7,
) -> dict:
    """
    Calculate contextualized MPG accounting for external factors.
    
    This helps answer: "Is this truck performing well given the conditions?"
    
    Args:
        raw_mpg: Actual measured MPG
        terrain_factor: From terrain tracker (>1 = uphill, <1 = downhill)
        weather_factor: Weather impact (1.0 = normal, 1.1 = headwind/cold, etc.)
        load_factor: Cargo impact (1.0 = empty, 1.15 = full load)
        baseline_mpg: Expected baseline for this truck
        
    Returns:
        Dict with raw_mpg, adjusted_mpg, expected_mpg, and performance rating
        
    Example:
        >>> calculate_contextualized_mpg(
        ...     raw_mpg=5.0,
        ...     terrain_factor=1.10,  # 10% uphill penalty
        ...     load_factor=1.05,     # 5% load penalty
        ...     baseline_mpg=6.0
        ... )
        {
            "raw_mpg": 5.0,
            "adjusted_mpg": 5.78,  # What they would get in ideal conditions
            "expected_mpg": 5.19,  # What we expect given conditions
            "performance_vs_expected": -3.7,  # -3.7% below expected
            "rating": "GOOD"  # Despite low raw MPG, performing well for conditions
        }
    """
    # Combined environmental factor
    combined_factor = terrain_factor * weather_factor * load_factor
    
    # What the MPG would be in ideal conditions (adjusted up if conditions are hard)
    adjusted_mpg = raw_mpg * combined_factor
    
    # What we expect given the conditions (baseline adjusted down for conditions)
    expected_mpg = baseline_mpg / combined_factor
    
    # Performance vs expectation
    if expected_mpg > 0:
        performance_pct = ((raw_mpg - expected_mpg) / expected_mpg) * 100
    else:
        performance_pct = 0.0
    
    # Rating based on performance vs expected
    if performance_pct >= 5:
        rating = "EXCELLENT"
        message = "Beating expectations by {:.1f}%".format(performance_pct)
    elif performance_pct >= -5:
        rating = "GOOD"
        message = "Performing as expected"
    elif performance_pct >= -15:
        rating = "NEEDS_ATTENTION"
        message = "Below expected by {:.1f}%".format(abs(performance_pct))
    else:
        rating = "CRITICAL"
        message = "Significantly below expected - investigate"
    
    return {
        "raw_mpg": round(raw_mpg, 2),
        "adjusted_mpg": round(adjusted_mpg, 2),
        "expected_mpg": round(expected_mpg, 2),
        "performance_vs_expected_pct": round(performance_pct, 1),
        "rating": rating,
        "message": message,
        "factors": {
            "terrain": round(terrain_factor, 3),
            "weather": round(weather_factor, 3),
            "load": round(load_factor, 3),
            "combined": round(combined_factor, 3),
        },
        "baseline_mpg": baseline_mpg,
    }


def get_truck_contextualized_mpg(
    truck_id: str,
    raw_mpg: float,
    altitude: Optional[float] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    speed: Optional[float] = None,
    baseline_mpg: float = 5.7,
) -> dict:
    """
    Get contextualized MPG for a specific truck using its current terrain.
    
    Args:
        truck_id: Truck identifier
        raw_mpg: Current raw MPG reading
        altitude: Current altitude (ft or m)
        latitude: GPS latitude
        longitude: GPS longitude  
        speed: Current speed (mph)
        baseline_mpg: Truck's baseline MPG
        
    Returns:
        Contextualized MPG analysis dict
    """
    # Get terrain factor
    if altitude is not None:
        terrain_factor = get_terrain_fuel_factor(
            truck_id=truck_id,
            altitude=altitude,
            latitude=latitude,
            longitude=longitude,
            speed=speed,
        )
    else:
        terrain_factor = 1.0
    
    # TODO: Weather factor from external API (OpenWeather, etc.)
    weather_factor = 1.0
    
    # TODO: Load factor from weight sensors if available
    load_factor = 1.0
    
    return calculate_contextualized_mpg(
        raw_mpg=raw_mpg,
        terrain_factor=terrain_factor,
        weather_factor=weather_factor,
        load_factor=load_factor,
        baseline_mpg=baseline_mpg,
    )


if __name__ == "__main__":
    # Test the terrain tracker
    logging.basicConfig(level=logging.DEBUG)

    tracker = TerrainTracker("TEST001")

    # Simulate climbing a hill
    test_data = [
        (100, 34.0, -118.0, 55),  # Start
        (150, 34.01, -118.0, 55),  # Climbing
        (200, 34.02, -118.0, 55),  # Climbing
        (250, 34.03, -118.0, 55),  # Climbing
        (250, 34.04, -118.0, 55),  # Flat
        (200, 34.05, -118.0, 55),  # Descending
        (150, 34.06, -118.0, 55),  # Descending
        (100, 34.07, -118.0, 55),  # Descending
    ]

    print("\n" + "=" * 60)
    print("TERRAIN FACTOR TEST")
    print("=" * 60)

    for alt, lat, lon, speed in test_data:
        factor = tracker.update(alt * FEET_PER_METER, lat, lon, speed)
        summary = tracker.get_terrain_summary()
        print(
            f"\nAltitude: {alt}m → {summary['terrain_type']:10} "
            f"Grade: {summary['current_grade_pct']:+5.1f}% "
            f"Factor: {factor:.3f}"
        )

    print("\n" + "=" * 60)
    print("Final Summary:", tracker.get_terrain_summary())
    print("=" * 60)
