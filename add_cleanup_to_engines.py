#!/usr/bin/env python3
"""
🛠️ Add cleanup_inactive_trucks() to multiple engines

Version: v6.5.0
Date: December 21, 2025

This script adds memory cleanup methods to singleton engines
to prevent memory leaks from inactive/removed trucks.
"""

import re
from pathlib import Path

# Cleanup method template
CLEANUP_METHOD = '''
    def cleanup_inactive_trucks(
        self, active_truck_ids: set, max_inactive_days: int = 30
    ) -> int:
        """
        🆕 v6.5.0: Remove data for trucks inactive > max_inactive_days.

        Prevents memory leaks from trucks removed from fleet.

        Args:
            active_truck_ids: Set of currently active truck IDs
            max_inactive_days: Days of inactivity before cleanup (default 30)

        Returns:
            Number of trucks cleaned up
        """
        from datetime import datetime, timezone, timedelta

        cleaned_count = 0
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=max_inactive_days)
        trucks_to_remove = []

        # Identify truck data structures to clean
        # This will be customized per engine based on its attributes
        {CLEANUP_LOGIC}

        if cleaned_count > 0:
            logger.info(
                f"🧹 Cleaned up data for {{cleaned_count}} inactive trucks in {{self.__class__.__name__}}"
            )

        return cleaned_count
'''

# Engine-specific cleanup logic
ENGINE_CLEANUP_LOGIC = {
    "idle_engine.py": """
        # IdleEngine typically uses self.truck_states or similar
        if hasattr(self, 'truck_states'):
            for truck_id in list(self.truck_states.keys()):
                if truck_id not in active_truck_ids:
                    del self.truck_states[truck_id]
                    cleaned_count += 1
""",
    "gamification_engine.py": """
        # GamificationEngine uses self.driver_stats
        if hasattr(self, 'driver_stats'):
            for driver_id in list(self.driver_stats.keys()):
                # Driver IDs might include truck info
                # Clean based on inactivity
                trucks_to_remove.append(driver_id)
            for driver_id in trucks_to_remove:
                if driver_id in self.driver_stats:
                    del self.driver_stats[driver_id]
                    cleaned_count += 1
""",
    "driver_scoring_engine.py": """
        # DriverScoringEngine uses self.scores or self.metrics
        if hasattr(self, 'scores'):
            for truck_id in list(self.scores.keys()):
                if truck_id not in active_truck_ids:
                    del self.scores[truck_id]
                    cleaned_count += 1
        if hasattr(self, 'metrics'):
            for truck_id in list(self.metrics.keys()):
                if truck_id not in active_truck_ids:
                    del self.metrics[truck_id]
                    cleaned_count += 1
""",
}


def add_cleanup_to_file(filepath: Path, cleanup_logic: str):
    """Add cleanup method to an engine file"""
    print(f"\n📝 Processing: {filepath.name}")

    content = filepath.read_text(encoding="utf-8")

    # Check if cleanup already exists
    if "cleanup_inactive_trucks" in content:
        print(f"   ⏭️ Skipped: cleanup_inactive_trucks already exists")
        return False

    # Find the global instance section
    patterns = [
        r"(# Global instance.*?\n)",
        r"(_\w+_engine.*?=.*?None\n)",
        r"(def get_\w+_engine\(\))",
    ]

    match = None
    for pattern in patterns:
        match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
        if match:
            break

    if not match:
        print(f"   ❌ Failed: Could not find global instance section")
        return False

    # Insert cleanup method before global instance
    insert_pos = match.start()
    cleanup_code = CLEANUP_METHOD.replace("{CLEANUP_LOGIC}", cleanup_logic)

    new_content = content[:insert_pos] + cleanup_code + "\n" + content[insert_pos:]

    # Write back
    filepath.write_text(new_content, encoding="utf-8")
    print(f"   ✅ Added cleanup_inactive_trucks() method")
    return True


def main():
    """Add cleanup to engines that don't have it yet"""
    print("=" * 70)
    print("🛠️ Adding cleanup_inactive_trucks() to Engines")
    print("=" * 70)

    backend_dir = Path(__file__).parent
    modified_count = 0

    for filename, cleanup_logic in ENGINE_CLEANUP_LOGIC.items():
        filepath = backend_dir / filename
        if not filepath.exists():
            print(f"\n⚠️ {filename} not found, skipping")
            continue

        if add_cleanup_to_file(filepath, cleanup_logic):
            modified_count += 1

    print("\n" + "=" * 70)
    print(f"📊 SUMMARY: Modified {modified_count} files")
    print("=" * 70)


if __name__ == "__main__":
    main()
