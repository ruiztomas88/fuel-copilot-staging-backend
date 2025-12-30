"""
Rate Limiting Utilities
=======================

Refactors large check_rate_limit() function into smaller, testable components.

Author: Fuel Copilot Team
Date: December 26, 2025
"""

import os
from collections import defaultdict
from time import time
from typing import Dict, List, Tuple

# In-memory rate limit storage
_rate_limit_store: Dict[str, List[float]] = defaultdict(list)


def current_time() -> float:
    """Get current timestamp"""
    return time()


def get_rate_limit_for_role(role: str) -> int:
    """
    Get rate limit based on user role.

    Args:
        role: User role (super_admin, admin, viewer, anonymous)

    Returns:
        Requests per minute limit

    🔧 v4.1.1: DRASTICALLY INCREASED to prevent frontend blocking
    """
    limits = {
        "super_admin": 1000,  # Increased from 300
        "admin": 800,  # Increased from 120
        "viewer": 600,  # Increased from 60
        "anonymous": 500,  # Increased from 30 (16.7x increase!)
    }
    return limits.get(role, 500)  # Default to 500 instead of 30


def is_rate_limiting_enabled() -> bool:
    """Check if rate limiting is enabled (can be disabled for testing)"""
    return os.getenv("SKIP_RATE_LIMIT", "").lower() not in ("1", "true", "yes")


def clean_old_entries(client_id: str, window_seconds: int = 60) -> None:
    """
    Remove rate limit entries older than the time window.

    Args:
        client_id: Client identifier
        window_seconds: Time window in seconds (default: 60)
    """
    now = current_time()
    _rate_limit_store[client_id] = [
        ts for ts in _rate_limit_store[client_id] if now - ts < window_seconds
    ]


def get_current_request_count(client_id: str) -> int:
    """
    Get current request count for client within the time window.

    Args:
        client_id: Client identifier

    Returns:
        Number of requests in current window
    """
    return len(_rate_limit_store[client_id])


def record_request(client_id: str) -> None:
    """
    Record a new request for rate limiting.

    Args:
        client_id: Client identifier
    """
    _rate_limit_store[client_id].append(current_time())


def check_rate_limit(client_id: str, role: str = "anonymous") -> Tuple[bool, int]:
    """
    Check if client has exceeded rate limit.

    Args:
        client_id: Client identifier
        role: User role (determines rate limit)

    Returns:
        Tuple of (allowed: bool, remaining: int)

    Examples:
        >>> check_rate_limit("192.168.1.1", "admin")
        (True, 119)  # Allowed, 119 requests remaining

        >>> check_rate_limit("192.168.1.2", "anonymous")
        (False, 0)  # Blocked, 0 requests remaining
    """
    # Skip rate limiting in test mode
    if not is_rate_limiting_enabled():
        return True, 999

    # Clean expired entries
    clean_old_entries(client_id)

    # Get limit and current count
    limit = get_rate_limit_for_role(role)
    current_count = get_current_request_count(client_id)

    # Check if limit exceeded
    if current_count >= limit:
        return False, 0

    # Record this request
    record_request(client_id)

    # Calculate remaining
    remaining = limit - current_count - 1
    return True, remaining


def get_allowed_origins() -> List[str]:
    """
    Get list of allowed CORS origins.

    Returns:
        List of allowed origin URLs
    """
    return [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://localhost:5173",
        "https://fuelanalytics.fleetbooster.net",
        "https://fleetbooster.net",
    ]


def is_origin_allowed(origin: str) -> bool:
    """
    Check if origin is in allowed list.

    Args:
        origin: Origin URL from request

    Returns:
        True if origin is allowed
    """
    return origin in get_allowed_origins()


def build_cors_headers(origin: str) -> Dict[str, str]:
    """
    Build CORS headers for 429 rate limit response.

    Args:
        origin: Origin URL from request

    Returns:
        Dictionary of CORS headers
    """
    headers = {}

    if is_origin_allowed(origin):
        headers["Access-Control-Allow-Origin"] = origin
        headers["Access-Control-Allow-Credentials"] = "true"
        headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
        headers["Access-Control-Allow-Headers"] = "*"

    return headers


def build_rate_limit_headers(role: str, remaining: int) -> Dict[str, str]:
    """
    Build rate limit headers for response.

    Args:
        role: User role
        remaining: Remaining requests

    Returns:
        Dictionary of rate limit headers
    """
    return {
        "Retry-After": "60",
        "X-RateLimit-Limit": str(get_rate_limit_for_role(role)),
        "X-RateLimit-Remaining": str(remaining),
    }
