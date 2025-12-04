"""
field_normalizer.py - Field Name Normalization Layer
Addresses audit item #14: Field mismatch FE/BE
Version: 3.12.21

This module provides a middleware layer to normalize field names
between frontend expectations and backend responses.

Common mismatches:
- fuelLevel vs fuel_level
- truckId vs truck_id
- mpgCurrent vs mpg_current
- timestampUtc vs timestamp_utc
- sensorPct vs sensor_pct
"""

import re
from typing import Any, Dict, List, Union, Optional
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import json


class FieldNameConverter:
    """
    Converts field names between camelCase and snake_case.
    Maintains a mapping for consistent transformations.
    """

    # Explicit mappings for non-standard conversions
    EXPLICIT_MAPPINGS = {
        # Backend -> Frontend
        "truck_id": "truckId",
        "carrier_id": "carrierId",
        "timestamp_utc": "timestamp",  # Frontend uses 'timestamp'
        "sensor_pct": "sensorLevel",  # Frontend expects 'sensorLevel'
        "estimated_pct": "estimatedLevel",
        "fuel_gallons": "fuelGallons",
        "tank_capacity_gal": "tankCapacity",
        "mpg_current": "mpgCurrent",
        "mpg_ema": "mpgEma",
        "consumption_gph": "consumptionRate",
        "speed_mph": "speed",  # Simplified
        "mileage_delta": "mileageDelta",
        "truck_status": "status",  # Simplified
        "idle_duration_minutes": "idleMinutes",
        "refuel_detected": "isRefueling",
        "anomaly_score": "anomalyScore",
        "created_at": "createdAt",
        "updated_at": "updatedAt",
        "resolved_at": "resolvedAt",
        "price_updated_at": "priceUpdatedAt",
        "last_update": "lastUpdate",
        "fuel_pct": "fuelPercent",
        "avg_mpg": "avgMpg",
        "total_gallons": "totalGallons",
        "total_cost": "totalCost",
        "distance_miles": "distance",
        "is_truck_stop": "isTruckStop",
        "diesel_price": "dieselPrice",
        "regular_price": "regularPrice",
        "zip_code": "zipCode",
    }

    # Reverse mappings (Frontend -> Backend)
    REVERSE_MAPPINGS = {v: k for k, v in EXPLICIT_MAPPINGS.items()}

    @classmethod
    def to_camel_case(cls, snake_str: str) -> str:
        """Convert snake_case to camelCase."""
        # Check explicit mapping first
        if snake_str in cls.EXPLICIT_MAPPINGS:
            return cls.EXPLICIT_MAPPINGS[snake_str]

        # General conversion
        components = snake_str.split("_")
        return components[0] + "".join(x.title() for x in components[1:])

    @classmethod
    def to_snake_case(cls, camel_str: str) -> str:
        """Convert camelCase to snake_case."""
        # Check explicit reverse mapping first
        if camel_str in cls.REVERSE_MAPPINGS:
            return cls.REVERSE_MAPPINGS[camel_str]

        # General conversion
        s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", camel_str)
        return re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1).lower()

    @classmethod
    def convert_keys(
        cls, obj: Any, converter: callable, depth: int = 0, max_depth: int = 10
    ) -> Any:
        """
        Recursively convert all keys in a dict/list structure.

        Args:
            obj: Object to convert (dict, list, or primitive)
            converter: Function to apply to each key
            depth: Current recursion depth
            max_depth: Maximum recursion depth (prevent infinite loops)
        """
        if depth > max_depth:
            return obj

        if isinstance(obj, dict):
            return {
                converter(k): cls.convert_keys(v, converter, depth + 1, max_depth)
                for k, v in obj.items()
            }
        elif isinstance(obj, list):
            return [
                cls.convert_keys(item, converter, depth + 1, max_depth) for item in obj
            ]
        else:
            return obj

    @classmethod
    def to_frontend(cls, obj: Any) -> Any:
        """Convert all keys to camelCase for frontend consumption."""
        return cls.convert_keys(obj, cls.to_camel_case)

    @classmethod
    def to_backend(cls, obj: Any) -> Any:
        """Convert all keys to snake_case for backend processing."""
        return cls.convert_keys(obj, cls.to_snake_case)


class FieldNormalizationMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware that automatically normalizes field names.

    - Incoming requests: camelCase -> snake_case
    - Outgoing responses: snake_case -> camelCase

    Can be disabled per-request with X-Skip-Field-Normalization header.
    """

    def __init__(self, app, exclude_paths: Optional[List[str]] = None):
        super().__init__(app)
        self.exclude_paths = exclude_paths or [
            "/docs",
            "/redoc",
            "/openapi.json",
            "/health",
            "/metrics",
        ]

    async def dispatch(self, request: Request, call_next):
        # Check if normalization should be skipped
        skip_normalization = (
            request.headers.get("X-Skip-Field-Normalization", "").lower() == "true"
        )

        # Check excluded paths
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            skip_normalization = True

        if skip_normalization:
            return await call_next(request)

        # Normalize incoming request body (camelCase -> snake_case)
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                body = await request.body()
                if body:
                    data = json.loads(body)
                    normalized_data = FieldNameConverter.to_backend(data)

                    # Create new request with normalized body
                    # Note: This requires a custom request wrapper
                    request.state.normalized_body = normalized_data
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # Not JSON, skip normalization

        # Process the request
        response = await call_next(request)

        # Normalize outgoing response (snake_case -> camelCase)
        if response.headers.get("content-type", "").startswith("application/json"):
            try:
                # Read response body
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk

                if body:
                    data = json.loads(body)
                    normalized_data = FieldNameConverter.to_frontend(data)
                    normalized_body = json.dumps(normalized_data).encode()

                    # Create new response with normalized body
                    return Response(
                        content=normalized_body,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                        media_type="application/json",
                    )
            except (json.JSONDecodeError, UnicodeDecodeError):
                pass  # Not valid JSON, return as-is

        return response


# Response model wrappers for automatic conversion

from pydantic import BaseModel, ConfigDict
from typing import TypeVar, Generic

T = TypeVar("T")


class CamelCaseModel(BaseModel):
    """Base model that automatically converts to camelCase in JSON."""

    model_config = ConfigDict(
        populate_by_name=True, alias_generator=FieldNameConverter.to_camel_case
    )

    def model_dump(self, **kwargs) -> Dict[str, Any]:
        """Override to use camelCase by default."""
        kwargs.setdefault("by_alias", True)
        return super().model_dump(**kwargs)


class APIResponse(CamelCaseModel, Generic[T]):
    """Standard API response wrapper with camelCase."""

    success: bool = True
    data: Optional[T] = None
    message: Optional[str] = None
    errors: Optional[List[str]] = None

    @classmethod
    def ok(cls, data: T, message: str = None) -> "APIResponse[T]":
        return cls(success=True, data=data, message=message)

    @classmethod
    def error(cls, message: str, errors: List[str] = None) -> "APIResponse":
        return cls(success=False, message=message, errors=errors)


# Field mapping utilities for specific conversions


class FleetDataNormalizer:
    """Specialized normalizer for fleet/truck data."""

    @staticmethod
    def normalize_truck_response(truck_data: Dict) -> Dict:
        """Normalize a single truck data response for frontend."""
        return {
            "truckId": truck_data.get("truck_id"),
            "carrierId": truck_data.get("carrier_id"),
            "timestamp": truck_data.get("timestamp_utc"),
            "fuel": {
                "sensorLevel": truck_data.get("sensor_pct"),
                "estimatedLevel": truck_data.get("estimated_pct"),
                "gallons": truck_data.get("fuel_gallons"),
                "tankCapacity": truck_data.get("tank_capacity_gal", 200),
            },
            "performance": {
                "mpgCurrent": truck_data.get("mpg_current"),
                "mpgEma": truck_data.get("mpg_ema"),
                "consumptionRate": truck_data.get("consumption_gph"),
                "speed": truck_data.get("speed_mph"),
            },
            "status": truck_data.get("truck_status"),
            "idleMinutes": truck_data.get("idle_duration_minutes", 0),
            "location": (
                {"lat": truck_data.get("latitude"), "lng": truck_data.get("longitude")}
                if truck_data.get("latitude")
                else None
            ),
            "isRefueling": truck_data.get("refuel_detected", False),
            "anomalyScore": truck_data.get("anomaly_score"),
        }

    @staticmethod
    def normalize_fleet_response(fleet_data: List[Dict]) -> List[Dict]:
        """Normalize a list of truck data for frontend."""
        return [
            FleetDataNormalizer.normalize_truck_response(truck) for truck in fleet_data
        ]

    @staticmethod
    def normalize_alert_response(alert_data: Dict) -> Dict:
        """Normalize alert data for frontend."""
        return {
            "id": alert_data.get("id"),
            "truckId": alert_data.get("truck_id"),
            "alertType": alert_data.get("alert_type"),
            "severity": alert_data.get("severity"),
            "message": alert_data.get("message"),
            "createdAt": alert_data.get("created_at"),
            "resolved": alert_data.get("resolved", False),
            "resolvedAt": alert_data.get("resolved_at"),
            "metadata": FieldNameConverter.to_frontend(alert_data.get("metadata", {})),
        }

    @staticmethod
    def normalize_refuel_event(event_data: Dict) -> Dict:
        """Normalize refuel event data for frontend."""
        return {
            "id": event_data.get("id"),
            "truckId": event_data.get("truck_id"),
            "timestamp": event_data.get("timestamp_utc"),
            "location": {
                "lat": event_data.get("latitude"),
                "lng": event_data.get("longitude"),
                "address": event_data.get("location_address"),
            },
            "fuelAdded": {
                "gallons": event_data.get("gallons_added"),
                "startLevel": event_data.get("fuel_level_before"),
                "endLevel": event_data.get("fuel_level_after"),
            },
            "cost": {
                "total": event_data.get("cost"),
                "pricePerGallon": event_data.get("price_per_gallon"),
            },
            "driver": event_data.get("driver_id"),
            "verified": event_data.get("verified", False),
        }


# Utility functions for endpoint decorators


def normalize_response(func):
    """Decorator to normalize response data to camelCase."""
    import functools
    from fastapi.responses import JSONResponse

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        result = await func(*args, **kwargs)

        if isinstance(result, dict):
            normalized = FieldNameConverter.to_frontend(result)
            return JSONResponse(content=normalized)
        elif isinstance(result, list):
            normalized = [
                FieldNameConverter.to_frontend(item) if isinstance(item, dict) else item
                for item in result
            ]
            return JSONResponse(content=normalized)

        return result

    return wrapper


def normalize_request(func):
    """Decorator to normalize incoming request data to snake_case."""
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        # Find request body in kwargs
        for key, value in kwargs.items():
            if isinstance(value, dict):
                kwargs[key] = FieldNameConverter.to_backend(value)

        return await func(*args, **kwargs)

    return wrapper


# Example usage with FastAPI dependency injection

from fastapi import Depends


def get_normalized_body(request: Request) -> Optional[Dict]:
    """
    Dependency that returns normalized request body (snake_case).
    Use after FieldNormalizationMiddleware is applied.
    """
    return getattr(request.state, "normalized_body", None)
