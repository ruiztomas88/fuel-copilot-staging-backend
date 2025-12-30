#!/usr/bin/env python3
"""
🧹 Clear MPG States - Reset all truck MPG values to start fresh

This script clears the accumulated MPG states for all trucks,
forcing them to recalculate MPG from scratch using the new
v3.15.0 configuration (stricter thresholds, no dynamic alpha).

Usage:
    python3 clear_mpg_states.py [--backup]

Options:
    --backup    Create backup before clearing (recommended)

Author: Fuel Copilot Team
Date: December 29, 2025
"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

# Paths
DATA_DIR = Path("data")
MPG_STATES_FILE = DATA_DIR / "mpg_states.json"
BASELINES_FILE = DATA_DIR / "mpg_baselines.json"


def backup_file(filepath: Path) -> Path:
    """Create timestamped backup of a file"""
    if not filepath.exists():
        print(f"⚠️  {filepath} does not exist, skipping backup")
        return None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = (
        filepath.parent / f"{filepath.stem}_backup_{timestamp}{filepath.suffix}"
    )
    shutil.copy2(filepath, backup_path)
    print(f"✅ Backup created: {backup_path}")
    return backup_path


def clear_mpg_states(create_backup: bool = True) -> dict:
    """
    Clear all MPG states, keeping only the structure.

    This resets:
    - distance_accum -> 0.0
    - fuel_accum_gal -> 0.0
    - mpg_current -> null (will be recalculated)
    - window_count -> 0
    - mpg_history -> []

    Returns:
        Dict with statistics
    """
    if not MPG_STATES_FILE.exists():
        print(f"❌ {MPG_STATES_FILE} not found")
        return {"error": "File not found"}

    # Backup if requested
    if create_backup:
        backup_file(MPG_STATES_FILE)

    # Load current states
    with open(MPG_STATES_FILE, "r") as f:
        states = json.load(f)

    trucks_cleared = 0
    old_mpg_values = {}

    # Clear each truck's state
    for truck_id, state in states.items():
        old_mpg = state.get("mpg_current")
        old_mpg_values[truck_id] = old_mpg

        # Reset accumulators and MPG
        state["distance_accum"] = 0.0
        state["fuel_accum_gal"] = 0.0
        state["mpg_current"] = None
        state["window_count"] = 0
        state["last_raw_mpg"] = None
        state["mpg_history"] = []

        # Keep sensor tracking (for delta calculation)
        # state["last_fuel_lvl_pct"] - keep
        # state["last_odometer_mi"] - keep
        # state["last_timestamp"] - keep

        trucks_cleared += 1

    # Save cleared states
    with open(MPG_STATES_FILE, "w") as f:
        json.dump(states, f, indent=2)

    print(f"\n✅ Cleared MPG states for {trucks_cleared} trucks")
    print(f"📝 File: {MPG_STATES_FILE}")

    # Show old values for reference
    print(f"\n📊 Previous MPG values (now reset):")
    for truck_id, mpg in sorted(old_mpg_values.items()):
        if mpg is not None:
            print(f"  {truck_id}: {mpg:.2f} MPG")

    return {"trucks_cleared": trucks_cleared, "old_values": old_mpg_values}


def clear_baselines(create_backup: bool = True) -> dict:
    """
    Clear MPG baselines (optional - usually you want to keep these).

    Returns:
        Dict with statistics
    """
    if not BASELINES_FILE.exists():
        print(f"ℹ️  {BASELINES_FILE} not found (baselines not in use yet)")
        return {"trucks_cleared": 0}

    # Backup if requested
    if create_backup:
        backup_file(BASELINES_FILE)

    # Load and count
    with open(BASELINES_FILE, "r") as f:
        baselines = json.load(f)

    count = len(baselines)

    # Clear by replacing with empty dict
    with open(BASELINES_FILE, "w") as f:
        json.dump({}, f, indent=2)

    print(f"\n✅ Cleared {count} truck baselines")
    print(f"📝 File: {BASELINES_FILE}")

    return {"trucks_cleared": count}


def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Clear MPG states to start fresh with new configuration"
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup creation (not recommended)",
    )
    parser.add_argument(
        "--clear-baselines",
        action="store_true",
        help="Also clear learned baselines (usually not needed)",
    )

    args = parser.parse_args()
    create_backup = not args.no_backup

    print("🧹 MPG State Cleaner v1.0")
    print("=" * 60)
    print(f"Target: {MPG_STATES_FILE}")
    print(f"Backup: {'Yes' if create_backup else 'No'}")
    print("=" * 60)

    # Clear states
    result = clear_mpg_states(create_backup=create_backup)

    # Optionally clear baselines
    if args.clear_baselines:
        print("\n⚠️  Clearing baselines (learned truck-specific MPG patterns)...")
        clear_baselines(create_backup=create_backup)

    print("\n" + "=" * 60)
    print("✅ Done! Trucks will recalculate MPG from scratch.")
    print("💡 New configuration active:")
    print("   - min_miles: 20.0 (was 5.0)")
    print("   - min_fuel_gal: 2.5 (was 0.75)")
    print("   - max_mpg: 8.5 (was 9.0)")
    print("   - ema_alpha: 0.20 (was 0.4)")
    print("   - dynamic_alpha: DISABLED")
    print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
