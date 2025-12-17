"""
Tests for Slow Siphoning Detector
═══════════════════════════════════════════════════════════════════════════════
"""

import pytest
from datetime import datetime, timedelta, timezone
from siphon_detector import (
    SlowSiphonDetector,
    SiphonAlert,
    DailyFuelChange,
)


class TestSlowSiphonDetector:
    """Test suite for slow siphoning detection"""

    def test_no_siphoning_normal_consumption(self):
        """Normal consumption should not trigger siphoning alert"""
        detector = SlowSiphonDetector()

        # Simulate 5 days of normal consumption (only driving)
        readings = []
        base_date = datetime.now(timezone.utc) - timedelta(days=5)
        fuel_level = 80.0
        odometer = 50000

        for day in range(6):
            readings.append(
                {
                    "timestamp": base_date + timedelta(days=day),
                    "fuel_pct": fuel_level,
                    "odometer": odometer,
                    "idle_hours": 2.0,
                }
            )

            # Normal consumption: 50 miles @ 6 MPG + 2h idle
            miles = 50
            consumption_gal = (miles / 6.0) + (2.0 * 1.5)
            fuel_level -= (consumption_gal / 200) * 100
            odometer += miles

        alert = detector.analyze("TEST_001", readings, tank_capacity_gal=200.0)
        assert alert is None, "Normal consumption should not trigger alert"

    def test_siphoning_detected_3_consecutive_days(self):
        """3+ days of unexplained loss should trigger alert"""
        detector = SlowSiphonDetector()

        readings = []
        base_date = datetime.now(timezone.utc) - timedelta(days=5)
        fuel_level = 80.0
        odometer = 50000

        for day in range(6):
            readings.append(
                {
                    "timestamp": base_date + timedelta(days=day),
                    "fuel_pct": fuel_level,
                    "odometer": odometer,
                    "idle_hours": 2.0,
                }
            )

            # Normal consumption + siphoning
            miles = 50
            normal_consumption_gal = (miles / 6.0) + (2.0 * 1.5)
            siphon_gal = 5.0  # 5 gallons stolen per day

            total_loss_pct = ((normal_consumption_gal + siphon_gal) / 200) * 100
            fuel_level -= total_loss_pct
            odometer += miles

        alert = detector.analyze("TEST_002", readings, tank_capacity_gal=200.0)

        assert alert is not None, "Siphoning pattern should be detected"
        assert alert.period_days >= 3, "Should detect multi-day pattern"
        assert alert.total_gallons_lost >= 10.0, "Total loss should be significant"
        assert alert.confidence >= 50, "Should have reasonable confidence"

    def test_siphoning_high_confidence_consistent_pattern(self):
        """Consistent daily siphoning should have high confidence"""
        detector = SlowSiphonDetector()

        readings = []
        base_date = datetime.now(timezone.utc) - timedelta(days=7)
        fuel_level = 85.0
        odometer = 60000

        # 7 days of very consistent siphoning (exactly 6 gal/day)
        for day in range(8):
            readings.append(
                {
                    "timestamp": base_date + timedelta(days=day),
                    "fuel_pct": fuel_level,
                    "odometer": odometer,
                    "idle_hours": 2.0,
                }
            )

            miles = 60
            normal_gal = (miles / 6.0) + (2.0 * 1.5)
            siphon_gal = 6.0  # Consistent 6 gal/day

            total_pct = ((normal_gal + siphon_gal) / 200) * 100
            fuel_level -= total_pct
            odometer += miles

        alert = detector.analyze("TEST_003", readings, tank_capacity_gal=200.0)

        assert alert is not None
        assert alert.confidence >= 70, "Consistent pattern should have high confidence"
        assert alert.period_days >= 5, "Should detect long pattern"
        assert "HIGH" in alert.recommendation or "MEDIUM" in alert.recommendation

    def test_no_detection_insufficient_days(self):
        """Less than 3 days should not trigger alert even with loss"""
        detector = SlowSiphonDetector()

        readings = []
        base_date = datetime.now(timezone.utc) - timedelta(days=2)
        fuel_level = 80.0

        # Only 2 days of data
        for day in range(2):
            readings.append(
                {
                    "timestamp": base_date + timedelta(days=day),
                    "fuel_pct": fuel_level,
                    "odometer": 50000 + (day * 50),
                    "idle_hours": 2.0,
                }
            )
            fuel_level -= 8.0  # Large daily loss

        alert = detector.analyze("TEST_004", readings, tank_capacity_gal=200.0)
        assert alert is None, "Should require minimum 3 days"

    def test_no_detection_small_total_loss(self):
        """Small total loss should not trigger even with multiple days"""
        detector = SlowSiphonDetector()

        readings = []
        base_date = datetime.now(timezone.utc) - timedelta(days=5)
        fuel_level = 80.0
        odometer = 50000

        # 5 days of tiny unexplained losses (1 gal/day)
        for day in range(6):
            readings.append(
                {
                    "timestamp": base_date + timedelta(days=day),
                    "fuel_pct": fuel_level,
                    "odometer": odometer,
                    "idle_hours": 2.0,
                }
            )

            miles = 50
            normal_gal = (miles / 6.0) + (2.0 * 1.5)
            siphon_gal = 1.0  # Only 1 gal/day (below threshold)

            total_pct = ((normal_gal + siphon_gal) / 200) * 100
            fuel_level -= total_pct
            odometer += miles

        alert = detector.analyze("TEST_005", readings, tank_capacity_gal=200.0)
        assert alert is None, "Small losses should not trigger"

    def test_pattern_resets_after_normal_day(self):
        """Pattern should reset if interrupted by normal day"""
        detector = SlowSiphonDetector()

        readings = []
        base_date = datetime.now(timezone.utc) - timedelta(days=7)
        fuel_level = 85.0
        odometer = 50000

        for day in range(8):
            readings.append(
                {
                    "timestamp": base_date + timedelta(days=day),
                    "fuel_pct": fuel_level,
                    "odometer": odometer,
                    "idle_hours": 2.0,
                }
            )

            miles = 50
            normal_gal = (miles / 6.0) + (2.0 * 1.5)

            # Day 3: normal consumption (no siphoning)
            # Other days: siphoning
            if day == 3:
                siphon_gal = 0.0
            else:
                siphon_gal = 6.0

            total_pct = ((normal_gal + siphon_gal) / 200) * 100
            fuel_level -= total_pct
            odometer += miles

        alert = detector.analyze("TEST_006", readings, tank_capacity_gal=200.0)

        # Should detect either 2 days before or 4 days after interruption
        # Depending on which segment meets threshold first
        if alert:
            assert alert.period_days <= 4, "Pattern broken by normal day"

    def test_daily_summary(self):
        """Test daily summary generation"""
        detector = SlowSiphonDetector()
        from datetime import datetime, timedelta, timezone

        today = datetime.now(timezone.utc).date()
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).date()

        # Add some test data
        detector.daily_history["TEST_TRUCK"] = [
            DailyFuelChange(
                date=yesterday.isoformat(),
                fuel_start_pct=80.0,
                fuel_end_pct=75.0,
                change_pct=5.0,
                change_gal=10.0,
                expected_consumption_gal=6.0,
                unexplained_loss_gal=4.0,  # Suspicious
                miles_driven=50.0,
                hours_idle=2.0,
            ),
            DailyFuelChange(
                date=today.isoformat(),
                fuel_start_pct=75.0,
                fuel_end_pct=70.0,
                change_pct=5.0,
                change_gal=10.0,
                expected_consumption_gal=9.0,
                unexplained_loss_gal=1.0,  # Normal
                miles_driven=60.0,
                hours_idle=2.0,
            ),
        ]

        summary = detector.get_daily_summary("TEST_TRUCK", days=7)

        assert summary["truck_id"] == "TEST_TRUCK"
        assert summary["days_analyzed"] == 2
        assert summary["total_unexplained_loss_gal"] == 5.0
        assert summary["suspicious_days"] == 1

    def test_zero_readings(self):
        """Empty readings list should return None"""
        detector = SlowSiphonDetector()
        alert = detector.analyze("TEST_007", [], tank_capacity_gal=200.0)
        assert alert is None

    def test_single_reading(self):
        """Single reading should return None"""
        detector = SlowSiphonDetector()
        readings = [
            {
                "timestamp": datetime.now(timezone.utc),
                "fuel_pct": 80.0,
                "odometer": 50000,
                "idle_hours": 0,
            }
        ]
        alert = detector.analyze("TEST_008", readings, tank_capacity_gal=200.0)
        assert alert is None

    def test_large_siphoning_very_high_confidence(self):
        """Large consistent siphoning should have very high confidence"""
        detector = SlowSiphonDetector()

        readings = []
        base_date = datetime.now(timezone.utc) - timedelta(days=6)
        fuel_level = 90.0
        odometer = 50000

        # 6 days of large siphoning (10 gal/day)
        for day in range(7):
            readings.append(
                {
                    "timestamp": base_date + timedelta(days=day),
                    "fuel_pct": fuel_level,
                    "odometer": odometer,
                    "idle_hours": 2.0,
                }
            )

            miles = 50
            normal_gal = (miles / 6.0) + (2.0 * 1.5)
            siphon_gal = 10.0  # Large theft

            total_pct = ((normal_gal + siphon_gal) / 200) * 100
            fuel_level -= total_pct
            odometer += miles

        alert = detector.analyze("TEST_009", readings, tank_capacity_gal=200.0)

        assert alert is not None
        assert alert.total_gallons_lost >= 40.0, "Should detect large total loss"
        assert alert.confidence >= 85, "Large consistent loss = high confidence"
        assert "HIGH" in alert.recommendation or "CRITICAL" in alert.recommendation


@pytest.fixture
def sample_detector():
    """Fixture providing a detector instance"""
    return SlowSiphonDetector()


@pytest.fixture
def normal_consumption_readings():
    """Fixture providing normal consumption readings"""
    readings = []
    base_date = datetime.now(timezone.utc) - timedelta(days=5)
    fuel_level = 80.0
    odometer = 50000

    for day in range(6):
        readings.append(
            {
                "timestamp": base_date + timedelta(days=day),
                "fuel_pct": fuel_level,
                "odometer": odometer,
                "idle_hours": 2.0,
            }
        )

        miles = 50
        consumption_gal = (miles / 6.0) + (2.0 * 1.5)
        fuel_level -= (consumption_gal / 200) * 100
        odometer += miles

    return readings


def test_detector_with_fixtures(sample_detector, normal_consumption_readings):
    """Test using fixtures"""
    alert = sample_detector.analyze("FIXTURE_TEST", normal_consumption_readings, 200.0)
    assert alert is None
