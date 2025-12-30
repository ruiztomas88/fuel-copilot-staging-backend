"""
Async Wrapper for database.py
==============================

Wraps synchronous database.py methods with async equivalents
to eliminate blocking I/O in FastAPI endpoints.

Author: Fuel Copilot Team
Date: December 26, 2025
Version: 1.0.0 with complete type hints
"""

import asyncio
from functools import wraps
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypeVar, cast

from database import DatabaseManager, db

# Type variable for generic function wrapping
T = TypeVar("T")


def async_wrapper(sync_func: Callable[..., T]) -> Callable[..., Awaitable[T]]:
    """
    Decorator to wrap synchronous database functions as async.

    Runs sync function in thread pool to avoid blocking event loop.

    Args:
        sync_func: Synchronous function to wrap

    Returns:
        Async function that runs sync_func in thread pool
    """

    @wraps(sync_func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: sync_func(*args, **kwargs))

    return wrapper


class AsyncDatabaseWrapper:
    """
    Async wrapper for DatabaseManager.

    Provides async methods for all database operations to prevent
    blocking the FastAPI event loop.
    """

    def __init__(self, db_instance: DatabaseManager = db) -> None:
        """
        Initialize wrapper with database instance.

        Args:
            db_instance: DatabaseManager instance to wrap (default: global db)
        """
        self._db = db_instance

    async def get_all_trucks(self) -> List[str]:
        """
        Get list of all truck IDs (async).

        Returns:
            List of truck ID strings
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._db.get_all_trucks)

    async def get_truck_latest_record(self, truck_id: str) -> Optional[Dict[str, Any]]:
        """
        Get latest record for truck (async).

        Args:
            truck_id: Truck identifier

        Returns:
            Latest truck record dict or None if not found
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._db.get_truck_latest_record, truck_id
        )

    async def get_trucks_batch(self, truck_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Batch fetch truck data (async).

        Args:
            truck_ids: List of truck IDs to fetch

        Returns:
            Dictionary mapping truck_id to truck record
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._db.get_trucks_batch, truck_ids)

    async def get_fleet_summary(self) -> Dict[str, Any]:
        """
        Get fleet summary statistics (async).

        Returns:
            Dictionary with fleet metrics (active_trucks, avg_mpg, etc.)
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._db.get_fleet_summary)

    async def get_truck_history(
        self, truck_id: str, hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        Get truck history (async).

        Args:
            truck_id: Truck identifier
            hours: Number of hours of history (default: 24)

        Returns:
            List of historical data point dicts
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._db.get_truck_history, truck_id, hours
        )

    async def get_refuel_history(
        self, truck_id: str, days: int = 30
    ) -> List[Dict[str, Any]]:
        """
        Get refuel history for truck (async).

        Args:
            truck_id: Truck identifier
            days: Number of days of history (default: 30)

        Returns:
            List of refuel event dicts
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None, self._db.get_refuel_history, truck_id, days
        )

    async def get_all_refuels(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get all refuels for entire fleet (async).

        Args:
            days: Number of days of history (default: 7)

        Returns:
            List of refuel event dicts for all trucks
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._db.get_all_refuels, days)

    async def get_efficiency_rankings(self) -> List[Dict[str, Any]]:
        """
        Get efficiency rankings for all trucks (async).

        Returns:
            List of truck efficiency dicts sorted by MPG
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._db.get_efficiency_rankings)

    async def get_active_alerts(self) -> List[Dict[str, Any]]:
        """
        Get active alerts (async).

        Returns:
            List of active alert dicts
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._db.get_active_alerts)

    async def get_alerts(self) -> List[Dict[str, Any]]:
        """
        Get active alerts (async) - alias for get_active_alerts.

        Returns:
            List of active alert dicts
        """
        return await self.get_active_alerts()

    async def get_fleet_kpis(self) -> Dict[str, Any]:
        """
        Get fleet KPIs (async).

        Returns:
            Dictionary with KPI metrics
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._db.get_fleet_kpis)


# Global async wrapper instance
async_db: AsyncDatabaseWrapper = AsyncDatabaseWrapper()
