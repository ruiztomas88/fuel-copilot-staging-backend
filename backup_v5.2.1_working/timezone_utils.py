"""
Fuel Copilot - Timezone Utilities

Provides consistent timezone handling across the application.

IMPORTANT: All internal timestamps should be UTC.
Only convert to local timezone for display purposes.

This module replaces deprecated datetime.utcnow() with
timezone-aware datetime.now(timezone.utc) calls.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from zoneinfo import ZoneInfo


# Default timezone for business operations
BUSINESS_TZ = ZoneInfo("America/New_York")  # EST/EDT


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime

    This replaces deprecated datetime.utcnow() which returns naive datetime.

    Returns:
        Timezone-aware datetime in UTC
    """
    return datetime.now(timezone.utc)


def local_now(tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Get current local time as timezone-aware datetime

    Args:
        tz: Timezone to use. Defaults to BUSINESS_TZ (EST/EDT)

    Returns:
        Timezone-aware datetime in specified timezone
    """
    target_tz = tz or BUSINESS_TZ
    return datetime.now(target_tz)


def epoch_to_utc(epoch: int) -> datetime:
    """
    Convert Unix epoch timestamp to timezone-aware UTC datetime

    Args:
        epoch: Unix timestamp (seconds since 1970-01-01 UTC)

    Returns:
        Timezone-aware datetime in UTC
    """
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def utc_to_local(dt: datetime, tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Convert UTC datetime to local timezone

    Args:
        dt: UTC datetime (can be naive or aware)
        tz: Target timezone. Defaults to BUSINESS_TZ

    Returns:
        Timezone-aware datetime in target timezone
    """
    target_tz = tz or BUSINESS_TZ

    # If naive, assume UTC
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(target_tz)


def local_to_utc(dt: datetime, source_tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Convert local datetime to UTC

    Args:
        dt: Local datetime (can be naive or aware)
        source_tz: Source timezone if dt is naive. Defaults to BUSINESS_TZ

    Returns:
        Timezone-aware datetime in UTC
    """
    if dt.tzinfo is None:
        # Naive datetime - assume it's in source_tz
        source = source_tz or BUSINESS_TZ
        dt = dt.replace(tzinfo=source)

    return dt.astimezone(timezone.utc)


def ensure_utc(dt: Optional[datetime]) -> Optional[datetime]:
    """
    Ensure datetime is timezone-aware UTC

    Args:
        dt: Input datetime (can be naive, UTC, or local)

    Returns:
        Timezone-aware UTC datetime, or None if input is None
    """
    if dt is None:
        return None

    if dt.tzinfo is None:
        # Naive - assume UTC (safest assumption for server-side data)
        return dt.replace(tzinfo=timezone.utc)

    # Already aware - convert to UTC
    return dt.astimezone(timezone.utc)


def format_utc(dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    """
    Format datetime as UTC string

    Args:
        dt: Datetime to format (will be converted to UTC)
        fmt: Format string

    Returns:
        Formatted string with 'UTC' suffix
    """
    utc_dt = ensure_utc(dt)
    if utc_dt is None:
        return ""
    return f"{utc_dt.strftime(fmt)} UTC"


def format_local(
    dt: datetime, fmt: str = "%Y-%m-%d %H:%M:%S", tz: Optional[ZoneInfo] = None
) -> str:
    """
    Format datetime as local timezone string

    Args:
        dt: Datetime to format
        fmt: Format string
        tz: Target timezone. Defaults to BUSINESS_TZ

    Returns:
        Formatted string in local timezone
    """
    local_dt = utc_to_local(dt, tz)
    return local_dt.strftime(fmt)


def get_today_utc() -> datetime:
    """
    Get start of today in UTC

    Returns:
        Midnight UTC for current day
    """
    now = utc_now()
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def get_today_local(tz: Optional[ZoneInfo] = None) -> datetime:
    """
    Get start of today in local timezone

    Args:
        tz: Timezone. Defaults to BUSINESS_TZ

    Returns:
        Midnight in local timezone for current day
    """
    now = local_now(tz)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def hours_ago(hours: float) -> datetime:
    """
    Get datetime N hours ago in UTC

    Args:
        hours: Number of hours back

    Returns:
        UTC datetime N hours ago
    """
    return utc_now() - timedelta(hours=hours)


def minutes_ago(minutes: float) -> datetime:
    """
    Get datetime N minutes ago in UTC

    Args:
        minutes: Number of minutes back

    Returns:
        UTC datetime N minutes ago
    """
    return utc_now() - timedelta(minutes=minutes)


def calculate_age_minutes(timestamp: datetime) -> float:
    """
    Calculate age of timestamp in minutes

    Args:
        timestamp: Datetime to check (will be converted to UTC)

    Returns:
        Age in minutes (positive if timestamp is in past)
    """
    utc_ts = ensure_utc(timestamp)
    if utc_ts is None:
        return float("inf")

    delta = utc_now() - utc_ts
    return delta.total_seconds() / 60.0


def is_stale(timestamp: datetime, max_age_minutes: float = 30.0) -> bool:
    """
    Check if timestamp is older than threshold

    Args:
        timestamp: Datetime to check
        max_age_minutes: Maximum acceptable age in minutes

    Returns:
        True if timestamp is older than max_age_minutes
    """
    return calculate_age_minutes(timestamp) > max_age_minutes


# Common timezone objects for convenience
UTC = timezone.utc
EST = ZoneInfo("America/New_York")
CST = ZoneInfo("America/Chicago")
PST = ZoneInfo("America/Los_Angeles")
