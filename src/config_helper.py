"""
Configuration helper for Service Layer Architecture

Bridges legacy config.py with new repository/service pattern.

Usage:
    from src.config_helper import get_db_config, create_repositories

    db_config = get_db_config()
    repos = create_repositories(db_config)
"""

import sys
from pathlib import Path
from typing import Any, Dict

# Add parent directory to path to import root-level config
root_dir = Path(__file__).parent.parent
sys.path.insert(0, str(root_dir))

from config import DATABASE


def get_db_config() -> Dict[str, Any]:
    """
    Get MySQL connection config in format expected by repositories.

    Returns:
        Dict with keys: host, port, user, password, database, charset
    """
    # Password is optional for local development (e.g., root with no password)
    # Production should always have a password set

    return {
        "host": DATABASE.HOST,
        "port": DATABASE.PORT,
        "user": DATABASE.USER,
        "password": DATABASE.PASSWORD,  # Can be empty string for local dev
        "database": DATABASE.DATABASE,
        "charset": DATABASE.CHARSET,
    }


def create_repositories(db_config: Dict[str, Any] = None):
    """
    Create all repository instances with proper configuration.

    Args:
        db_config: Optional DB config. If None, uses get_db_config()

    Returns:
        Dict with repository instances:
        {
            'truck': TruckRepository,
            'sensor': SensorRepository,
            'def': DEFRepository,
            'dtc': DTCRepository,
        }
    """
    from src.repositories import (
        DEFRepository,
        DTCRepository,
        SensorRepository,
        TruckRepository,
    )

    if db_config is None:
        db_config = get_db_config()

    return {
        "truck": TruckRepository(db_config, pool_size=DATABASE.POOL_SIZE),
        "sensor": SensorRepository(db_config, pool_size=DATABASE.POOL_SIZE),
        "def": DEFRepository(db_config, pool_size=DATABASE.POOL_SIZE),
        "dtc": DTCRepository(db_config, pool_size=DATABASE.POOL_SIZE),
    }


def create_services(repositories: Dict[str, Any]):
    """
    Create all service instances with injected repositories.

    Args:
        repositories: Dict from create_repositories()

    Returns:
        Dict with service instances:
        {
            'analytics': AnalyticsService,
            'priority': PriorityEngine,
            'health': HealthAnalyzer,
            'def_predictor': DEFPredictor,
            'pattern': PatternAnalyzer,
        }
    """
    from src.services import (
        AnalyticsService,
        DEFPredictor,
        HealthAnalyzer,
        PatternAnalyzer,
        PriorityEngine,
    )

    return {
        "analytics": AnalyticsService(
            truck_repo=repositories["truck"],
            sensor_repo=repositories["sensor"],
            def_repo=repositories["def"],
            dtc_repo=repositories["dtc"],
        ),
        "priority": PriorityEngine(),
        "health": HealthAnalyzer(
            truck_repo=repositories["truck"],
            sensor_repo=repositories["sensor"],
        ),
        "def_predictor": DEFPredictor(
            def_repo=repositories["def"],
        ),
        "pattern": PatternAnalyzer(
            dtc_repo=repositories["dtc"],
        ),
    }


def create_orchestrator(services: Dict[str, Any], repositories: Dict[str, Any]):
    """
    Create FleetOrchestrator with all dependencies.

    Args:
        services: Dict from create_services()
        repositories: Dict from create_repositories()

    Returns:
        FleetOrchestrator instance
    """
    from src.orchestrators import FleetOrchestrator, OrchestratorConfig

    config = OrchestratorConfig(
        enable_caching=True,
        cache_ttl_seconds=300,
        enable_persistence=True,
        enable_pattern_detection=True,
        enable_failure_correlation=True,
        offline_hours_warning=2,
        offline_hours_critical=12,
    )

    return FleetOrchestrator(
        priority_engine=services["priority"],
        health_analyzer=services["health"],
        def_predictor=services["def_predictor"],
        pattern_analyzer=services["pattern"],
        truck_repo=repositories["truck"],
        sensor_repo=repositories["sensor"],
        def_repo=repositories["def"],
        dtc_repo=repositories["dtc"],
        config=config,
    )


# Quick setup function for convenience
def setup_architecture():
    """
    One-liner to set up entire architecture.

    Returns:
        Tuple of (repositories, services, orchestrator)

    Example:
        repos, services, orchestrator = setup_architecture()
        data = orchestrator.get_command_center_data()
    """
    db_config = get_db_config()
    repositories = create_repositories(db_config)
    services = create_services(repositories)
    orchestrator = create_orchestrator(services, repositories)

    return repositories, services, orchestrator
