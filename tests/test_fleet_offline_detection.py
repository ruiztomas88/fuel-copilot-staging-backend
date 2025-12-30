"""
Test lines 2241-2306: Offline truck detection
Force execution by providing truck_last_seen data
"""

from datetime import datetime, timedelta, timezone

import pytest

from fleet_command_center import FleetCommandCenter


class TestOfflineTruckDetection:
    """Test lines 2241-2306: detect_offline_trucks execution"""

    def test_detect_offline_trucks_critical(self):
        """Test critical offline detection (>24h)"""
        fcc = FleetCommandCenter()

        # Create truck_last_seen with critical offline trucks
        now = datetime.now(timezone.utc)
        truck_last_seen = {
            "CRITICAL_OFFLINE_001": now - timedelta(hours=30),  # 30h offline - critical
            "CRITICAL_OFFLINE_002": now - timedelta(hours=48),  # 48h offline - critical
        }

        all_trucks = ["CRITICAL_OFFLINE_001", "CRITICAL_OFFLINE_002", "ONLINE_TRUCK"]

        # Call detect_offline_trucks to hit lines 2241-2306
        offline_actions = fcc.detect_offline_trucks(truck_last_seen, all_trucks)

        assert isinstance(offline_actions, list)
        # Should create action items for offline trucks
        assert len(offline_actions) >= 2  # At least 2 critical

    def test_detect_offline_trucks_warning(self):
        """Test warning offline detection (>4h but <24h)"""
        fcc = FleetCommandCenter()

        now = datetime.now(timezone.utc)
        truck_last_seen = {
            "WARNING_OFFLINE_001": now - timedelta(hours=6),  # 6h - warning
            "WARNING_OFFLINE_002": now - timedelta(hours=10),  # 10h - warning
        }

        all_trucks = ["WARNING_OFFLINE_001", "WARNING_OFFLINE_002"]

        offline_actions = fcc.detect_offline_trucks(truck_last_seen, all_trucks)

        assert isinstance(offline_actions, list)
        # Should create warning level action items
        assert len(offline_actions) >= 1

    def test_detect_offline_trucks_never_seen(self):
        """Test trucks with no last_seen data (line 2249-2251)"""
        fcc = FleetCommandCenter()

        truck_last_seen = {}  # No data for any truck

        all_trucks = ["NEVER_SEEN_001", "NEVER_SEEN_002"]

        offline_actions = fcc.detect_offline_trucks(truck_last_seen, all_trucks)

        assert isinstance(offline_actions, list)
        # Should treat as critical offline
        assert len(offline_actions) >= 1

    def test_detect_offline_trucks_naive_datetime(self):
        """Test timezone handling for naive datetimes (lines 2255-2256)"""
        fcc = FleetCommandCenter()

        # Create naive datetime (no timezone)
        naive_time = datetime.now() - timedelta(hours=30)
        truck_last_seen = {
            "NAIVE_TIME_TRUCK": naive_time  # Naive datetime without tzinfo
        }

        all_trucks = ["NAIVE_TIME_TRUCK"]

        offline_actions = fcc.detect_offline_trucks(truck_last_seen, all_trucks)

        assert isinstance(offline_actions, list)

    def test_detect_offline_trucks_online(self):
        """Test trucks that are online (< warning threshold)"""
        fcc = FleetCommandCenter()

        now = datetime.now(timezone.utc)
        truck_last_seen = {
            "ONLINE_TRUCK_001": now - timedelta(minutes=30),  # 30 min - online
            "ONLINE_TRUCK_002": now - timedelta(hours=1),  # 1h - online
        }

        all_trucks = ["ONLINE_TRUCK_001", "ONLINE_TRUCK_002"]

        offline_actions = fcc.detect_offline_trucks(truck_last_seen, all_trucks)

        # Should return empty or very short list
        assert isinstance(offline_actions, list)
        # Trucks are online, should not create alerts
        assert len(offline_actions) == 0

    def test_detect_offline_trucks_mixed_scenarios(self):
        """Test mix of critical, warning, and online trucks"""
        fcc = FleetCommandCenter()

        now = datetime.now(timezone.utc)
        truck_last_seen = {
            "CRITICAL_001": now - timedelta(hours=50),  # Critical
            "WARNING_001": now - timedelta(hours=8),  # Warning
            "ONLINE_001": now - timedelta(minutes=15),  # Online
        }

        all_trucks = ["CRITICAL_001", "WARNING_001", "ONLINE_001", "NEVER_SEEN_001"]

        offline_actions = fcc.detect_offline_trucks(truck_last_seen, all_trucks)

        assert isinstance(offline_actions, list)
        # Should have critical, warning, and never_seen items
        assert len(offline_actions) >= 2
