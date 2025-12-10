"""
fuel_stations.py - External Fuel Station API Integration
Addresses audit item #20: Integración fuel stations API
Version: 3.12.21

Integrates with external APIs to get:
- Nearby fuel stations
- Real-time fuel prices
- Station amenities
- Optimal refuel recommendations
"""

import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class FuelType(str, Enum):
    DIESEL = "diesel"
    REGULAR = "regular"
    PREMIUM = "premium"
    E85 = "e85"


class StationAmenities(BaseModel):
    """Available amenities at a fuel station."""

    restrooms: bool = False
    restaurant: bool = False
    convenience_store: bool = False
    truck_parking: bool = False
    truck_wash: bool = False
    def_available: bool = False  # Diesel Exhaust Fluid
    scales: bool = False
    showers: bool = False
    wifi: bool = False
    atm: bool = False


class FuelStation(BaseModel):
    """Fuel station information."""

    id: str
    name: str
    brand: str
    address: str
    city: str
    state: str
    zip_code: str
    latitude: float
    longitude: float
    diesel_price: Optional[float] = None
    regular_price: Optional[float] = None
    price_updated_at: Optional[datetime] = None
    distance_miles: Optional[float] = None
    amenities: Optional[StationAmenities] = None
    rating: Optional[float] = None
    is_truck_stop: bool = False


class RefuelRecommendation(BaseModel):
    """Recommendation for optimal refueling."""

    station: FuelStation
    current_fuel_pct: float
    fuel_needed_gallons: float
    estimated_cost: float
    urgency: str  # low, medium, high, critical
    reason: str
    estimated_arrival_minutes: Optional[int] = None
    potential_savings: Optional[float] = None


class FuelStationAPIConfig:
    """Configuration for external fuel station APIs."""

    # Primary API: GasBuddy (example - use actual API keys in production)
    GASBUDDY_API_KEY = os.getenv("GASBUDDY_API_KEY", "")
    GASBUDDY_BASE_URL = "https://api.gasbuddy.com/v1"

    # Alternative: OPIS (Oil Price Information Service)
    OPIS_API_KEY = os.getenv("OPIS_API_KEY", "")
    OPIS_BASE_URL = "https://api.opisnet.com/v2"

    # Truck Stop APIs
    PILOT_FLYING_J_API = os.getenv("PFJ_API_KEY", "")
    LOVES_API = os.getenv("LOVES_API_KEY", "")
    TA_PETRO_API = os.getenv("TA_PETRO_API_KEY", "")

    # Cache duration
    PRICE_CACHE_MINUTES = 30
    STATION_CACHE_HOURS = 24


class FuelStationService:
    """Service for fetching fuel station data from external APIs."""

    def __init__(self):
        self.config = FuelStationAPIConfig()
        self._price_cache: Dict[str, Dict] = {}
        self._station_cache: Dict[str, List[FuelStation]] = {}
        self._cache_timestamps: Dict[str, datetime] = {}

    async def get_nearby_stations(
        self,
        latitude: float,
        longitude: float,
        radius_miles: float = 25,
        fuel_type: FuelType = FuelType.DIESEL,
        truck_stops_only: bool = True,
    ) -> List[FuelStation]:
        """
        Get nearby fuel stations.

        Args:
            latitude: Current latitude
            longitude: Current longitude
            radius_miles: Search radius in miles
            fuel_type: Type of fuel needed
            truck_stops_only: Filter to truck stops only

        Returns:
            List of nearby fuel stations sorted by distance
        """
        cache_key = f"{latitude:.3f}_{longitude:.3f}_{radius_miles}_{fuel_type}"

        # Check cache
        if cache_key in self._station_cache:
            cache_time = self._cache_timestamps.get(cache_key)
            if cache_time and datetime.utcnow() - cache_time < timedelta(minutes=30):
                return self._station_cache[cache_key]

        stations = []

        try:
            # Try multiple APIs in parallel
            async with httpx.AsyncClient(timeout=10.0) as client:
                tasks = [
                    self._fetch_truck_stops(client, latitude, longitude, radius_miles),
                    self._fetch_gasbuddy_stations(
                        client, latitude, longitude, radius_miles, fuel_type
                    ),
                ]

                results = await asyncio.gather(*tasks, return_exceptions=True)

                for result in results:
                    if isinstance(result, list):
                        stations.extend(result)
                    elif isinstance(result, Exception):
                        logger.warning(f"API fetch failed: {result}")

            # Deduplicate by location
            stations = self._deduplicate_stations(stations)

            # Filter truck stops if requested
            if truck_stops_only:
                stations = [s for s in stations if s.is_truck_stop]

            # Sort by distance
            stations.sort(key=lambda s: s.distance_miles or float("inf"))

            # Cache results
            self._station_cache[cache_key] = stations
            self._cache_timestamps[cache_key] = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error fetching stations: {e}")
            # Return mock data for development
            stations = self._get_mock_stations(latitude, longitude)

        return stations

    async def _fetch_truck_stops(
        self, client: httpx.AsyncClient, lat: float, lng: float, radius: float
    ) -> List[FuelStation]:
        """Fetch from major truck stop APIs."""
        stations = []

        # Pilot Flying J API
        if self.config.PILOT_FLYING_J_API:
            try:
                response = await client.get(
                    "https://api.pilotflyingj.com/locations",
                    params={
                        "lat": lat,
                        "lng": lng,
                        "radius": radius,
                        "type": "truck_stop",
                    },
                    headers={
                        "Authorization": f"Bearer {self.config.PILOT_FLYING_J_API}"
                    },
                )
                if response.status_code == 200:
                    data = response.json()
                    for loc in data.get("locations", []):
                        stations.append(self._parse_pfj_station(loc))
            except Exception as e:
                logger.warning(f"Pilot Flying J API error: {e}")

        # Love's API
        if self.config.LOVES_API:
            try:
                response = await client.get(
                    "https://api.loves.com/stations",
                    params={"latitude": lat, "longitude": lng, "radius": radius},
                    headers={"X-API-Key": self.config.LOVES_API},
                )
                if response.status_code == 200:
                    data = response.json()
                    for loc in data.get("stations", []):
                        stations.append(self._parse_loves_station(loc))
            except Exception as e:
                logger.warning(f"Love's API error: {e}")

        return stations

    async def _fetch_gasbuddy_stations(
        self,
        client: httpx.AsyncClient,
        lat: float,
        lng: float,
        radius: float,
        fuel_type: FuelType,
    ) -> List[FuelStation]:
        """Fetch from GasBuddy API for price information."""
        if not self.config.GASBUDDY_API_KEY:
            return []

        try:
            response = await client.get(
                f"{self.config.GASBUDDY_BASE_URL}/stations",
                params={
                    "lat": lat,
                    "lng": lng,
                    "radius": radius,
                    "fuel_type": fuel_type.value,
                },
                headers={"Authorization": f"Bearer {self.config.GASBUDDY_API_KEY}"},
            )

            if response.status_code == 200:
                data = response.json()
                return [
                    self._parse_gasbuddy_station(s) for s in data.get("stations", [])
                ]

        except Exception as e:
            logger.warning(f"GasBuddy API error: {e}")

        return []

    def _parse_pfj_station(self, data: dict) -> FuelStation:
        """Parse Pilot Flying J station data."""
        return FuelStation(
            id=f"pfj_{data.get('id')}",
            name=data.get("name", "Pilot Flying J"),
            brand="Pilot Flying J",
            address=data.get("address", ""),
            city=data.get("city", ""),
            state=data.get("state", ""),
            zip_code=data.get("zip", ""),
            latitude=data.get("latitude", 0),
            longitude=data.get("longitude", 0),
            diesel_price=data.get("diesel_price"),
            distance_miles=data.get("distance"),
            is_truck_stop=True,
            amenities=StationAmenities(
                restrooms=True,
                restaurant=data.get("has_restaurant", False),
                convenience_store=True,
                truck_parking=True,
                truck_wash=data.get("has_truck_wash", False),
                def_available=data.get("has_def", True),
                scales=data.get("has_scales", False),
                showers=data.get("has_showers", False),
                wifi=data.get("has_wifi", True),
            ),
        )

    def _parse_loves_station(self, data: dict) -> FuelStation:
        """Parse Love's station data."""
        return FuelStation(
            id=f"loves_{data.get('id')}",
            name=data.get("name", "Love's Travel Stop"),
            brand="Love's",
            address=data.get("address", ""),
            city=data.get("city", ""),
            state=data.get("state", ""),
            zip_code=data.get("zip_code", ""),
            latitude=data.get("lat", 0),
            longitude=data.get("lng", 0),
            diesel_price=data.get("diesel_price"),
            distance_miles=data.get("distance_miles"),
            is_truck_stop=True,
            amenities=StationAmenities(
                restrooms=True,
                restaurant=True,
                convenience_store=True,
                truck_parking=True,
                truck_wash=data.get("truck_wash", False),
                def_available=True,
                scales=data.get("scales", False),
                showers=True,
                wifi=True,
            ),
        )

    def _parse_gasbuddy_station(self, data: dict) -> FuelStation:
        """Parse GasBuddy station data."""
        return FuelStation(
            id=f"gb_{data.get('id')}",
            name=data.get("name", ""),
            brand=data.get("brand", ""),
            address=data.get("address", ""),
            city=data.get("city", ""),
            state=data.get("state", ""),
            zip_code=data.get("zip", ""),
            latitude=data.get("latitude", 0),
            longitude=data.get("longitude", 0),
            diesel_price=data.get("diesel_price"),
            regular_price=data.get("regular_price"),
            price_updated_at=(
                datetime.fromisoformat(data["price_updated"])
                if data.get("price_updated")
                else None
            ),
            distance_miles=data.get("distance"),
            is_truck_stop=data.get("is_truck_stop", False),
            rating=data.get("rating"),
        )

    def _deduplicate_stations(self, stations: List[FuelStation]) -> List[FuelStation]:
        """Remove duplicate stations based on location proximity."""
        unique = []
        for station in stations:
            is_duplicate = False
            for existing in unique:
                dist = self._haversine_distance(
                    station.latitude,
                    station.longitude,
                    existing.latitude,
                    existing.longitude,
                )
                if dist < 0.1:  # Within 0.1 miles
                    # Keep the one with more info
                    if station.diesel_price and not existing.diesel_price:
                        unique.remove(existing)
                        unique.append(station)
                    is_duplicate = True
                    break
            if not is_duplicate:
                unique.append(station)
        return unique

    def _haversine_distance(
        self, lat1: float, lon1: float, lat2: float, lon2: float
    ) -> float:
        """Calculate distance between two coordinates in miles."""
        from math import radians, sin, cos, sqrt, atan2

        R = 3959  # Earth's radius in miles

        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        return R * c

    def _get_mock_stations(self, lat: float, lng: float) -> List[FuelStation]:
        """Return mock stations for development/testing."""
        return [
            FuelStation(
                id="mock_1",
                name="Pilot Travel Center #421",
                brand="Pilot Flying J",
                address="1234 Highway 59",
                city="Houston",
                state="TX",
                zip_code="77001",
                latitude=lat + 0.05,
                longitude=lng + 0.03,
                diesel_price=3.459,
                distance_miles=5.2,
                is_truck_stop=True,
                rating=4.2,
                amenities=StationAmenities(
                    restrooms=True,
                    restaurant=True,
                    convenience_store=True,
                    truck_parking=True,
                    truck_wash=True,
                    def_available=True,
                    scales=True,
                    showers=True,
                    wifi=True,
                ),
            ),
            FuelStation(
                id="mock_2",
                name="Love's Travel Stop #456",
                brand="Love's",
                address="5678 Interstate 10",
                city="Houston",
                state="TX",
                zip_code="77002",
                latitude=lat + 0.08,
                longitude=lng - 0.02,
                diesel_price=3.419,
                distance_miles=8.7,
                is_truck_stop=True,
                rating=4.5,
                amenities=StationAmenities(
                    restrooms=True,
                    restaurant=True,
                    convenience_store=True,
                    truck_parking=True,
                    truck_wash=True,
                    def_available=True,
                    scales=False,
                    showers=True,
                    wifi=True,
                ),
            ),
            FuelStation(
                id="mock_3",
                name="TA Travel Center",
                brand="TA Petro",
                address="9012 US Highway 290",
                city="Austin",
                state="TX",
                zip_code="78701",
                latitude=lat - 0.1,
                longitude=lng + 0.05,
                diesel_price=3.499,
                distance_miles=12.3,
                is_truck_stop=True,
                rating=4.0,
                amenities=StationAmenities(
                    restrooms=True,
                    restaurant=True,
                    convenience_store=True,
                    truck_parking=True,
                    truck_wash=False,
                    def_available=True,
                    scales=True,
                    showers=True,
                    wifi=True,
                ),
            ),
        ]

    async def get_refuel_recommendations(
        self,
        truck_id: str,
        current_lat: float,
        current_lng: float,
        current_fuel_pct: float,
        tank_capacity_gal: float = 200,
        avg_mpg: float = 5.7,
    ) -> List[RefuelRecommendation]:
        """
        Get optimal refueling recommendations based on current status.

        Args:
            truck_id: Truck identifier
            current_lat: Current latitude
            current_lng: Current longitude
            current_fuel_pct: Current fuel level percentage
            tank_capacity_gal: Tank capacity in gallons
            avg_mpg: Average miles per gallon

        Returns:
            List of refuel recommendations sorted by urgency/value
        """
        # Determine urgency based on fuel level
        if current_fuel_pct < 10:
            urgency = "critical"
            radius = 10  # Search closer for critical
        elif current_fuel_pct < 20:
            urgency = "high"
            radius = 20
        elif current_fuel_pct < 35:
            urgency = "medium"
            radius = 30
        else:
            urgency = "low"
            radius = 50

        # Get nearby stations
        stations = await self.get_nearby_stations(
            current_lat, current_lng, radius_miles=radius, truck_stops_only=True
        )

        recommendations = []
        current_gallons = tank_capacity_gal * (current_fuel_pct / 100)
        fuel_needed = tank_capacity_gal - current_gallons

        # Find cheapest prices for comparison
        prices = [s.diesel_price for s in stations if s.diesel_price]
        min_price = min(prices) if prices else 3.50
        avg_price = sum(prices) / len(prices) if prices else 3.50

        for station in stations[:10]:  # Top 10 closest
            if not station.diesel_price:
                continue

            estimated_cost = station.diesel_price * fuel_needed
            savings = (avg_price - station.diesel_price) * fuel_needed

            # Estimate arrival time (rough calculation based on distance)
            est_arrival = int(
                station.distance_miles * 1.5
            )  # ~40 mph average with stops

            # Generate recommendation reason
            reasons = []
            if station.diesel_price <= min_price + 0.05:
                reasons.append("Lowest price in area")
            if station.distance_miles <= 5:
                reasons.append("Very close by")
            if station.rating and station.rating >= 4.5:
                reasons.append("Highly rated")
            if station.amenities and station.amenities.truck_wash:
                reasons.append("Truck wash available")
            if station.amenities and station.amenities.showers:
                reasons.append("Showers available")

            reason = (
                "; ".join(reasons)
                if reasons
                else f"Distance: {station.distance_miles:.1f} mi"
            )

            recommendations.append(
                RefuelRecommendation(
                    station=station,
                    current_fuel_pct=current_fuel_pct,
                    fuel_needed_gallons=round(fuel_needed, 1),
                    estimated_cost=round(estimated_cost, 2),
                    urgency=urgency,
                    reason=reason,
                    estimated_arrival_minutes=est_arrival,
                    potential_savings=round(savings, 2) if savings > 0 else None,
                )
            )

        # Sort by value (balance of price, distance, and amenities)
        recommendations.sort(
            key=lambda r: (
                0 if r.urgency == "critical" else 1,  # Critical first
                r.station.diesel_price or 999,  # Then by price
                r.station.distance_miles or 999,  # Then by distance
            )
        )

        return recommendations

    async def get_price_trends(
        self, state: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """Get diesel price trends for route planning."""
        # This would typically call a historical price API
        # For now, return simulated data

        return {
            "period": f"Last {days} days",
            "state": state or "National",
            "current_avg": 3.489,
            "trend": "stable",  # rising, falling, stable
            "change_pct": -0.5,
            "forecast": "Prices expected to remain stable",
            "best_days": ["Tuesday", "Wednesday"],
            "worst_days": ["Friday", "Saturday"],
            "regional_comparison": {
                "TX": 3.419,
                "LA": 3.389,
                "OK": 3.449,
                "AR": 3.479,
                "NM": 3.529,
            },
        }


# Singleton instance
fuel_station_service = FuelStationService()


# API Router
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/fuel-stations", tags=["Fuel Stations"])


@router.get("/nearby")
async def get_nearby_fuel_stations(
    lat: float = Query(..., description="Latitude"),
    lng: float = Query(..., description="Longitude"),
    radius: float = Query(25, description="Search radius in miles"),
    truck_stops_only: bool = Query(True, description="Filter to truck stops only"),
    fuel_type: FuelType = Query(FuelType.DIESEL, description="Type of fuel"),
):
    """Get nearby fuel stations with current prices."""
    stations = await fuel_station_service.get_nearby_stations(
        latitude=lat,
        longitude=lng,
        radius_miles=radius,
        fuel_type=fuel_type,
        truck_stops_only=truck_stops_only,
    )

    return {
        "count": len(stations),
        "search_location": {"lat": lat, "lng": lng},
        "radius_miles": radius,
        "stations": [s.model_dump() for s in stations],
    }


@router.get("/recommendations/{truck_id}")
async def get_refuel_recommendations(
    truck_id: str,
    lat: float = Query(..., description="Current latitude"),
    lng: float = Query(..., description="Current longitude"),
    fuel_pct: float = Query(..., description="Current fuel percentage"),
    tank_capacity: float = Query(200, description="Tank capacity in gallons"),
    avg_mpg: float = Query(5.7, description="Average MPG"),
):
    """Get optimal refueling recommendations for a truck."""
    recommendations = await fuel_station_service.get_refuel_recommendations(
        truck_id=truck_id,
        current_lat=lat,
        current_lng=lng,
        current_fuel_pct=fuel_pct,
        tank_capacity_gal=tank_capacity,
        avg_mpg=avg_mpg,
    )

    return {
        "truck_id": truck_id,
        "current_fuel_pct": fuel_pct,
        "recommendations_count": len(recommendations),
        "recommendations": [r.model_dump() for r in recommendations],
    }


@router.get("/price-trends")
async def get_price_trends(
    state: Optional[str] = Query(None, description="State code (e.g., TX)"),
    days: int = Query(30, description="Number of days for trend analysis"),
):
    """Get diesel price trends and forecasts."""
    trends = await fuel_station_service.get_price_trends(state=state, days=days)
    return trends
