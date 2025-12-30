"""
Service Container for Dependency Injection
===========================================

Eliminates global variables and provides centralized dependency management.

Author: Fuel Copilot Team
Date: December 26, 2025
"""

from typing import Optional


class ServiceContainer:
    """
    Centralized service container for dependency injection.

    Replaces global variables with managed instances:
    - Future: Settings, Cache, Database, etc.
    """

    _instance: Optional["ServiceContainer"] = None

    def __init__(self) -> None:
        """Initialize services lazily"""
        pass

    @classmethod
    def get_instance(cls) -> "ServiceContainer":
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_settings(self):
        """
        Get settings from config module.

        Returns:
            Settings object with fuel configuration
        """
        from config import FUEL, REFUEL

        # Create a simple namespace object to hold settings
        class FuelSettings:
            def __init__(self):
                self.price_per_gallon = FUEL.PRICE_PER_GALLON
                self.min_refuel_gallons = REFUEL.MIN_REFUEL_GALLONS
                self.min_refuel_jump_pct = REFUEL.MIN_JUMP_PCT

        class Settings:
            def __init__(self):
                self.fuel = FuelSettings()

        return Settings()

    @property
    def settings(self):
        """Get settings instance (lazy loaded)"""
        return self.get_settings()

    def reset(self) -> None:
        """Reset all services (useful for testing)"""
        pass


# Global container instance (singleton pattern)
container = ServiceContainer.get_instance()


def get_container() -> ServiceContainer:
    """Get service container instance"""
    return ServiceContainer.get_instance()
