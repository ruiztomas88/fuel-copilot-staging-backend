"""
Lifecycle Manager for FastAPI Application
==========================================

Refactors large lifespan() function into manageable components.

Author: Fuel Copilot Team
Date: December 26, 2025
Version: 1.0.1 - Enhanced error logging and crash detection
"""

import asyncio
import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Optional

from database_async_wrapper import async_db

logger: logging.Logger = logging.getLogger(__name__)

# Setup crash log file
crash_log_file = "logs/backend_crashes.log"


def log_crash(exception: Exception, context: str = "Unknown"):
    """Log crashes to dedicated file for debugging"""
    try:
        import os

        os.makedirs("logs", exist_ok=True)

        with open(crash_log_file, "a") as f:
            f.write(f"\n{'='*80}\n")
            f.write(f"🔥 BACKEND CRASH DETECTED\n")
            f.write(f"Time: {datetime.now().isoformat()}\n")
            f.write(f"Context: {context}\n")
            f.write(f"Exception: {type(exception).__name__}: {str(exception)}\n")
            f.write(f"\nStack Trace:\n")
            f.write(traceback.format_exc())
            f.write(f"\n{'='*80}\n")

        logger.critical(
            f"🔥 CRASH logged to {crash_log_file}: {type(exception).__name__}"
        )
    except Exception as log_err:
        logger.error(f"Failed to log crash: {log_err}")


class LifecycleManager:
    """Manages application startup and shutdown lifecycle"""

    def __init__(self) -> None:
        """Initialize lifecycle manager"""
        self.cache: Optional[Any] = None
        self.db_pool: Optional[Any] = None

    async def initialize_cache(self) -> None:
        """Initialize multi-layer cache connection"""
        try:
            logger.info("🔄 Initializing multi-layer cache...")
            from multi_layer_cache import cache

            await cache.connect()
            self.cache = cache
            logger.info("✅ Multi-layer cache connected successfully")
        except Exception as e:
            logger.warning(f"⚠️ Cache initialization failed: {e}")
            log_crash(e, "Cache Initialization")

    async def initialize_database_pool(self) -> None:
        """Initialize async database connection pool"""
        try:
            logger.info("🔄 Initializing async database pool...")
            from database_async import get_async_pool

            self.db_pool = await get_async_pool()
            logger.info("✅ Async DB pool initialized successfully")
        except Exception as e:
            logger.error(f"❌ Failed to initialize async pool: {e}")
            log_crash(e, "Database Pool Initialization")
            # Don't crash - some endpoints still work without async

    async def count_trucks(self) -> Optional[int]:
        """
        Count available trucks on startup.

        Returns:
            Number of trucks or None if count failed
        """
        try:
            trucks = await async_db.get_all_trucks()
            truck_count = len(trucks)
            logger.info(f"Available trucks: {truck_count}")
            return truck_count
        except Exception as e:
            logger.warning(f"Could not count trucks on startup (non-critical): {e}")
            logger.info("API starting without truck count - will work normally")
            return None

    async def startup(self) -> None:
        """Execute all startup tasks"""
        logger.info("=" * 80)
        logger.info("🚀 Fuel Copilot API v3.12.0 STARTING...")
        logger.info(f"📅 Startup Time: {datetime.now().isoformat()}")
        logger.info("=" * 80)

        try:
            # Initialize components in sequence
            await self.initialize_cache()
            await self.initialize_database_pool()
            await self.count_trucks()

            logger.info("MySQL enhanced features: enabled")
            logger.info("=" * 80)
            logger.info("✅ API ready for connections")
            logger.info("=" * 80)
        except Exception as e:
            logger.critical(f"🔥 FATAL ERROR during startup: {e}")
            log_crash(e, "Startup Sequence")
            raise  # Re-raise to prevent partial startup

    async def shutdown_cache(self) -> None:
        """Disconnect cache gracefully"""
        if self.cache:
            try:
                logger.info("🔄 Disconnecting cache...")
                await self.cache.disconnect()
                logger.info("✅ Cache disconnected")
            except Exception as e:
                logger.warning(f"⚠️ Error disconnecting cache: {e}")
                log_crash(e, "Cache Shutdown")

    async def shutdown_database_pool(self) -> None:
        """Close database pool gracefully"""
        try:
            logger.info("🔄 Closing async database pool...")
            from database_async import close_async_pool

            await close_async_pool()
            logger.info("✅ Async DB pool closed")
        except Exception as e:
            logger.error(f"❌ Error closing pool: {e}")
            log_crash(e, "Database Pool Shutdown")

    async def shutdown(self) -> None:
        """Execute all shutdown tasks"""
        logger.info("=" * 80)
        logger.info("🛑 Shutting down Fuel Copilot API")
        logger.info(f"📅 Shutdown Time: {datetime.now().isoformat()}")
        logger.info("=" * 80)

        try:
            # Shutdown components in reverse order
            await self.shutdown_cache()
            await self.shutdown_database_pool()

            logger.info("=" * 80)
            logger.info("✅ Clean shutdown completed")
            logger.info("=" * 80)
        except Exception as e:
            logger.error(f"🔥 Error during shutdown: {e}")
            log_crash(e, "Shutdown Sequence")


# Global lifecycle manager instance
lifecycle_manager: LifecycleManager = LifecycleManager()
