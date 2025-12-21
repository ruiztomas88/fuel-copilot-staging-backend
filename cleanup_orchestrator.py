#!/usr/bin/env python3
"""
🧹 Memory Cleanup Orchestrator
Version: v6.5.0
Date: December 21, 2025

Runs weekly to cleanup inactive trucks from all singleton engines.

Schedule: Every Sunday at 3:00 AM UTC
Command: 0 3 * * 0 cd /path/to/backend && python cleanup_orchestrator.py
"""

import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_active_truck_ids() -> set:
    """
    Get set of currently active truck IDs from database.

    A truck is considered active if:
    - It appears in tanks.yaml
    - It has sensor data in the last 7 days
    """
    try:
        import yaml

        # Load from tanks.yaml
        tanks_path = Path(__file__).parent / "tanks.yaml"
        with open(tanks_path, "r", encoding="utf-8") as f:
            tanks_config = yaml.safe_load(f)

        active_trucks = set(tanks_config.get("trucks", {}).keys())
        logger.info(f"✅ Loaded {len(active_trucks)} active trucks from tanks.yaml")

        return active_trucks

    except Exception as e:
        logger.error(f"❌ Failed to load active trucks: {e}")
        return set()


def cleanup_all_engines(active_truck_ids: set, max_inactive_days: int = 30) -> dict:
    """
    Run cleanup on all singleton engines.

    Returns:
        dict: Summary of cleanup results per engine
    """
    results = {}

    # 1. Driver Behavior Engine
    try:
        from driver_behavior_engine import get_behavior_engine

        engine = get_behavior_engine()
        if hasattr(engine, "cleanup_inactive_trucks"):
            count = engine.cleanup_inactive_trucks(active_truck_ids, max_inactive_days)
            results["driver_behavior"] = count
        else:
            results["driver_behavior"] = "⚠️ No cleanup method"
    except Exception as e:
        results["driver_behavior"] = f"❌ Error: {e}"

    # 2. Theft Detection Pattern Analyzer
    try:
        from theft_detection_engine import PATTERN_ANALYZER

        if hasattr(PATTERN_ANALYZER, "cleanup_inactive_trucks"):
            count = PATTERN_ANALYZER.cleanup_inactive_trucks(
                active_truck_ids, max_inactive_days
            )
            results["theft_detection"] = count
        else:
            results["theft_detection"] = "⚠️ No cleanup method"
    except Exception as e:
        results["theft_detection"] = f"❌ Error: {e}"

    # 3. MPG Baseline Manager
    try:
        from mpg_engine import get_baseline_manager

        manager = get_baseline_manager()
        if hasattr(manager, "cleanup_inactive_trucks"):
            count = manager.cleanup_inactive_trucks(active_truck_ids, max_inactive_days)
            results["mpg_baseline"] = count
        else:
            results["mpg_baseline"] = "⚠️ No cleanup method"
    except Exception as e:
        results["mpg_baseline"] = f"❌ Error: {e}"

    # 4. Alert Manager
    try:
        from alert_service import get_alert_manager

        manager = get_alert_manager()
        if hasattr(manager, "cleanup_inactive_trucks"):
            count = manager.cleanup_inactive_trucks(active_truck_ids, max_inactive_days)
            results["alert_manager"] = count
        else:
            results["alert_manager"] = "⚠️ No cleanup method"
    except Exception as e:
        results["alert_manager"] = f"❌ Error: {e}"

    # 5. Predictive Maintenance Engine
    try:
        from predictive_maintenance_engine import get_predictive_maintenance_engine

        engine = get_predictive_maintenance_engine()
        if hasattr(engine, "cleanup_inactive_trucks"):
            count = engine.cleanup_inactive_trucks(active_truck_ids, max_inactive_days)
            results["predictive_maintenance"] = count
        else:
            results["predictive_maintenance"] = "⚠️ No cleanup method"
    except Exception as e:
        results["predictive_maintenance"] = f"❌ Error: {e}"

    # 6. Driver Scoring Engine
    try:
        from driver_scoring_engine import get_scoring_engine

        engine = get_scoring_engine()
        if hasattr(engine, "cleanup_inactive_trucks"):
            count = engine.cleanup_inactive_trucks(active_truck_ids, max_inactive_days)
            results["driver_scoring"] = count
        else:
            results["driver_scoring"] = "⚠️ No cleanup method"
    except Exception as e:
        results["driver_scoring"] = f"❌ Error: {e}"

    # 7. Component Health Predictors
    try:
        from component_health_predictors import (
            cleanup_inactive_trucks,
            get_coolant_detector,
            get_oil_tracker,
            get_turbo_predictor,
        )

        predictors = [
            get_turbo_predictor(),
            get_oil_tracker(),
            get_coolant_detector(),
        ]
        count = cleanup_inactive_trucks(predictors, active_truck_ids, max_inactive_days)
        results["component_health"] = count
    except Exception as e:
        results["component_health"] = f"❌ Error: {e}"

    return results


def main():
    """Main cleanup orchestrator"""
    print("\n" + "=" * 70)
    print("🧹 MEMORY CLEANUP ORCHESTRATOR")
    print(f"   Started at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    # Get active trucks
    active_trucks = get_active_truck_ids()

    if not active_trucks:
        logger.error("❌ No active trucks found, aborting cleanup")
        return 1

    print(f"\n✅ Active trucks: {len(active_trucks)}")
    print(f"   Max inactive days: 30")

    # Run cleanup
    print("\n🔄 Running cleanup across all engines...")
    results = cleanup_all_engines(active_trucks, max_inactive_days=30)

    # Print results
    print("\n" + "=" * 70)
    print("📊 CLEANUP RESULTS")
    print("=" * 70)

    total_cleaned = 0
    for engine_name, result in results.items():
        if isinstance(result, int):
            total_cleaned += result
            status = f"✅ Cleaned {result} trucks"
        else:
            status = str(result)

        print(f"   {engine_name:30s}: {status}")

    print("\n" + "=" * 70)
    print(f"   TOTAL: {total_cleaned} inactive trucks removed")
    print(f"   Completed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 70)

    logger.info(f"✅ Cleanup complete: {total_cleaned} trucks removed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
