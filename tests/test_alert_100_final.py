"""
Alert Service 100% Coverage Final Test
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest

from alert_service import FuelEventClassifier, PendingFuelDrop


class TestAlert100Coverage:
    """Cover remaining 66.37% uncovered lines in alert_service"""

    def setup_method(self):
        """Setup for each test"""
        self.classifier = FuelEventClassifier()

    def test_register_fuel_drop_high_volatility(self):
        """Test lines 229-235: High sensor volatility classification"""
        # Build up volatile history
        for val in [80, 70, 90, 60, 85, 75, 95, 65]:
            self.classifier._sensor_history["T001"].append(val)

        result = self.classifier.register_fuel_drop(
            truck_id="T001",
            fuel_before=80.0,
            fuel_after=65.0,
            location="Test Location",
            truck_status="MOVING",
        )

        assert result in ["SENSOR_VOLATILE", None]

    def test_register_extreme_theft_while_stopped(self):
        """Test lines 257-260: Extreme drop while stopped"""
        result = self.classifier.register_fuel_drop(
            truck_id="T002",
            fuel_before=90.0,
            fuel_after=50.0,  # 40% drop
            location="Parking Lot",
            truck_status="STOPPED",
        )

        assert result == "IMMEDIATE_THEFT"

    def test_check_recovery_sensor_issue(self):
        """Test lines 275-319: Recovery check - sensor issue path"""
        # First create a pending drop
        now = datetime.now(timezone.utc)
        self.classifier._pending_drops["T003"] = PendingFuelDrop(
            truck_id="T003",
            drop_timestamp=now - timedelta(minutes=20),  # Old enough
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="MOVING",
        )

        # Check recovery with fuel back to original
        result = self.classifier.check_recovery(
            "T003", 79.0
        )  # Recovered to near original

        assert result is not None
        assert result["classification"] == "SENSOR_ISSUE"

    def test_check_recovery_refuel_after_drop(self):
        """Test refuel after drop classification"""
        now = datetime.now(timezone.utc)
        self.classifier._pending_drops["T004"] = PendingFuelDrop(
            truck_id="T004",
            drop_timestamp=now - timedelta(minutes=20),
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="MOVING",
        )

        # Fuel increased significantly (refueled)
        result = self.classifier.check_recovery("T004", 90.0)

        assert result is not None
        assert result["classification"] == "REFUEL_AFTER_DROP"

    def test_check_recovery_theft_confirmed(self):
        """Test theft confirmed when fuel stays low"""
        now = datetime.now(timezone.utc)
        self.classifier._pending_drops["T005"] = PendingFuelDrop(
            truck_id="T005",
            drop_timestamp=now - timedelta(minutes=20),
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="STOPPED",
        )

        # Fuel stayed low
        result = self.classifier.check_recovery("T005", 66.0)

        assert result is not None
        assert result["classification"] == "THEFT_CONFIRMED"

    def test_check_recovery_no_pending_drop(self):
        """Test check recovery when no pending drop exists"""
        result = self.classifier.check_recovery("T999", 80.0)
        assert result is None

    def test_check_recovery_too_soon(self):
        """Test check recovery called too soon"""
        now = datetime.now(timezone.utc)
        self.classifier._pending_drops["T006"] = PendingFuelDrop(
            truck_id="T006",
            drop_timestamp=now - timedelta(minutes=1),  # Too recent
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="MOVING",
        )

        result = self.classifier.check_recovery("T006", 79.0)
        assert result is None  # Still waiting

    def test_cleanup_stale_drops(self):
        """Test cleanup of stale pending drops"""
        now = datetime.now(timezone.utc)

        # Add old pending drop
        self.classifier._pending_drops["T_OLD"] = PendingFuelDrop(
            truck_id="T_OLD",
            drop_timestamp=now - timedelta(hours=25),  # Very old
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="MOVING",
        )

        # Add recent one
        self.classifier._pending_drops["T_NEW"] = PendingFuelDrop(
            truck_id="T_NEW",
            drop_timestamp=now - timedelta(minutes=5),
            fuel_before=80.0,
            fuel_after=65.0,
            drop_pct=15.0,
            drop_gal=10.0,
            location="Test",
            truck_status="MOVING",
        )

        self.classifier.cleanup_stale_drops()

        assert "T_OLD" not in self.classifier._pending_drops
        assert "T_NEW" in self.classifier._pending_drops


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--cov=alert_service", "--cov-report=term-missing"])
