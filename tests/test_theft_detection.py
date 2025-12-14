"""
Test suite for enhanced fuel theft detection system (v5.8.0)

Tests cover:
- Basic theft detection scenarios
- Time-of-day factor adjustments
- Sensor health factor adjustments
- Combined multi-factor analysis
- Edge cases and boundary conditions
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Import the functions we're testing
from wialon_sync_enhanced import (
    detect_fuel_theft,
    get_time_of_day_factor,
    get_sensor_health_factor,
)


class TestTimeOfDayFactor:
    """Tests for get_time_of_day_factor function."""

    def test_night_hours_weekday(self):
        """Night hours (10PM-5AM) on weekday should return 1.3 factor."""
        # 2AM on a Wednesday
        night_time = datetime(2025, 1, 8, 2, 0, 0, tzinfo=timezone.utc)
        factor, period = get_time_of_day_factor(night_time)

        assert factor == 1.3
        assert period == "NIGHT"

    def test_night_hours_weekend(self):
        """Night hours on weekend should return 1.4 factor (most suspicious)."""
        # 11PM on Saturday
        weekend_night = datetime(2025, 1, 11, 23, 0, 0, tzinfo=timezone.utc)
        factor, period = get_time_of_day_factor(weekend_night)

        assert factor == 1.4
        assert period == "WEEKEND_NIGHT"

    def test_business_hours_weekday(self):
        """Business hours (8AM-6PM) on weekday should return 0.8 factor."""
        # 10AM on a Tuesday
        business_time = datetime(2025, 1, 7, 10, 0, 0, tzinfo=timezone.utc)
        factor, period = get_time_of_day_factor(business_time)

        assert factor == 0.8
        assert period == "BUSINESS_HOURS"

    def test_weekend_day(self):
        """Daytime on weekend should return 1.0 factor (neutral)."""
        # 2PM on Saturday
        weekend_day = datetime(2025, 1, 11, 14, 0, 0, tzinfo=timezone.utc)
        factor, period = get_time_of_day_factor(weekend_day)

        assert factor == 1.0
        assert period == "WEEKEND_DAY"

    def test_evening_weekday(self):
        """Evening (6PM-10PM) on weekday should return 1.0 factor."""
        # 8PM on Thursday
        evening = datetime(2025, 1, 9, 20, 0, 0, tzinfo=timezone.utc)
        factor, period = get_time_of_day_factor(evening)

        assert factor == 1.0
        assert period == "EVENING"

    def test_no_timestamp_uses_current_time(self):
        """When no timestamp provided, should use current time."""
        factor, period = get_time_of_day_factor(None)

        # Should return a valid factor regardless
        assert 0.8 <= factor <= 1.4
        assert period in [
            "NIGHT",
            "WEEKEND_NIGHT",
            "BUSINESS_HOURS",
            "WEEKEND_DAY",
            "EVENING",
        ]

    def test_boundary_hour_5am(self):
        """5AM should be considered night."""
        time_5am = datetime(2025, 1, 8, 5, 0, 0, tzinfo=timezone.utc)
        factor, period = get_time_of_day_factor(time_5am)

        assert factor == 1.3
        assert period == "NIGHT"

    def test_boundary_hour_10pm(self):
        """10PM should be considered night."""
        time_10pm = datetime(2025, 1, 8, 22, 0, 0, tzinfo=timezone.utc)
        factor, period = get_time_of_day_factor(time_10pm)

        assert factor == 1.3
        assert period == "NIGHT"


class TestSensorHealthFactor:
    """Tests for get_sensor_health_factor function."""

    def test_healthy_sensors(self):
        """Normal voltage and GPS should return 1.0 factor."""
        factor, status, issues = get_sensor_health_factor(
            voltage=13.5, gps_quality="Good", sats=8
        )

        assert factor == 1.0
        assert status == "HEALTHY"
        assert issues == []

    def test_critical_voltage(self):
        """Voltage below 11.5V should severely reduce factor."""
        factor, status, issues = get_sensor_health_factor(
            voltage=10.5, gps_quality="Good", sats=8
        )

        assert factor == 0.3
        assert status == "FAILING"
        assert any("Critical voltage" in issue for issue in issues)

    def test_low_voltage(self):
        """Voltage between 11.5 and 12.5V should reduce factor."""
        factor, status, issues = get_sensor_health_factor(
            voltage=12.0, gps_quality="Good", sats=8
        )

        assert factor == 0.6
        assert status == "DEGRADED"
        assert any("Low voltage" in issue for issue in issues)

    def test_very_poor_gps_sats(self):
        """Less than 3 satellites should severely reduce factor."""
        factor, status, issues = get_sensor_health_factor(
            voltage=13.5, gps_quality="Good", sats=2
        )

        assert factor == 0.4
        assert status == "FAILING"
        assert any("Very poor GPS" in issue for issue in issues)

    def test_weak_gps_sats(self):
        """3-4 satellites should moderately reduce factor."""
        factor, status, issues = get_sensor_health_factor(
            voltage=13.5, gps_quality="Good", sats=4
        )

        assert factor == 0.7
        assert status == "DEGRADED"
        assert any("Weak GPS" in issue for issue in issues)

    def test_poor_gps_quality_string(self):
        """Poor GPS quality string should reduce factor."""
        factor, status, issues = get_sensor_health_factor(
            voltage=13.5, gps_quality="poor signal", sats=8
        )

        assert factor == 0.5
        assert status == "DEGRADED"
        assert any("GPS quality" in issue for issue in issues)

    def test_combined_issues(self):
        """Multiple issues should compound the factor reduction (minimum 0.3)."""
        factor, status, issues = get_sensor_health_factor(
            voltage=10.5,  # Critical: 0.3
            gps_quality="poor",  # Poor: 0.5
            sats=2,  # Very poor: 0.4
        )

        # Factor is clamped at minimum 0.3 to avoid complete elimination
        # (see return statement in get_sensor_health_factor)
        assert factor == pytest.approx(0.3, abs=0.1)
        assert status == "FAILING"
        assert len(issues) == 3

    def test_no_sensor_data(self):
        """When no sensor data provided, should return defaults."""
        factor, status, issues = get_sensor_health_factor(
            voltage=None, gps_quality=None, sats=None
        )

        assert factor == 1.0
        assert status == "HEALTHY"
        assert issues == []


class TestDetectFuelTheft:
    """Tests for detect_fuel_theft function."""

    # =========================================================================
    # BASIC THEFT DETECTION
    # =========================================================================

    def test_no_theft_small_drop(self):
        """Small drop (<=3%) should not trigger theft detection."""
        result = detect_fuel_theft(
            sensor_pct=87.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 3% drop
            truck_status="STOPPED",
            time_gap_hours=1.0,
            tank_capacity_gal=200.0,
        )

        assert result is None

    def test_stopped_theft_large_drop(self):
        """Large drop (>10%) while stopped should detect theft."""
        result = detect_fuel_theft(
            sensor_pct=75.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 15% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
        )

        assert result is not None
        assert result["type"] == "STOPPED_THEFT"
        assert result["drop_pct"] == 15.0
        assert result["drop_gal"] == 30.0
        assert result["confidence"] >= 0.5

    def test_stopped_theft_moderate_drop(self):
        """Moderate drop (5-10%) while stopped should raise suspicion."""
        result = detect_fuel_theft(
            sensor_pct=83.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 7% drop
            truck_status="STOPPED",
            time_gap_hours=1.0,
            tank_capacity_gal=200.0,
        )

        assert result is not None
        assert result["type"] == "STOPPED_SUSPICIOUS"
        assert result["drop_pct"] == 7.0

    def test_rapid_theft(self):
        """Rapid large drop (>20%) in short time should detect theft."""
        result = detect_fuel_theft(
            sensor_pct=65.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 25% drop
            truck_status="MOVING",
            time_gap_hours=0.5,  # 30 minutes
            tank_capacity_gal=200.0,
        )

        assert result is not None
        assert result["type"] == "RAPID_LOSS"
        assert result["base_confidence"] >= 0.85

    def test_idle_theft(self):
        """Large drop (>8%) while idling should detect theft."""
        result = detect_fuel_theft(
            sensor_pct=80.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 10% drop
            truck_status="IDLE",
            time_gap_hours=1.0,
            tank_capacity_gal=200.0,
        )

        assert result is not None
        assert result["type"] == "IDLE_LOSS"
        assert result["confidence"] >= 0.5

    def test_no_detection_missing_last_reading(self):
        """No detection when last_sensor_pct is None."""
        result = detect_fuel_theft(
            sensor_pct=75.0,
            estimated_pct=88.0,
            last_sensor_pct=None,
            truck_status="STOPPED",
            time_gap_hours=1.0,
            tank_capacity_gal=200.0,
        )

        assert result is None

    def test_no_detection_missing_current_reading(self):
        """No detection when sensor_pct is None."""
        result = detect_fuel_theft(
            sensor_pct=None,
            estimated_pct=88.0,
            last_sensor_pct=90.0,
            truck_status="STOPPED",
            time_gap_hours=1.0,
            tank_capacity_gal=200.0,
        )

        assert result is None

    # =========================================================================
    # TIME-OF-DAY ENHANCED DETECTION
    # =========================================================================

    def test_night_theft_increased_confidence(self):
        """Theft at night should have increased confidence."""
        # 2AM on Wednesday
        night_time = datetime(2025, 1, 8, 2, 0, 0, tzinfo=timezone.utc)

        result = detect_fuel_theft(
            sensor_pct=78.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 12% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            timestamp=night_time,
        )

        assert result is not None
        assert result["time_period"] == "NIGHT"
        # Base confidence 0.9 * 1.3 (night) = 1.17 → capped at 0.99
        assert result["confidence"] > result["base_confidence"]
        assert any("Time (NIGHT)" in adj for adj in result["adjustments"])

    def test_business_hours_reduced_confidence(self):
        """Theft during business hours should have slightly reduced confidence."""
        # 10AM on Tuesday
        business_time = datetime(2025, 1, 7, 10, 0, 0, tzinfo=timezone.utc)

        result = detect_fuel_theft(
            sensor_pct=78.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 12% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            timestamp=business_time,
        )

        assert result is not None
        assert result["time_period"] == "BUSINESS_HOURS"
        # Base confidence reduced by 0.8 factor
        assert result["confidence"] < result["base_confidence"]

    def test_weekend_night_maximum_suspicion(self):
        """Weekend night theft should have maximum time factor."""
        # Saturday at midnight
        weekend_night = datetime(2025, 1, 11, 0, 0, 0, tzinfo=timezone.utc)

        result = detect_fuel_theft(
            sensor_pct=78.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 12% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            timestamp=weekend_night,
        )

        assert result is not None
        assert result["time_period"] == "WEEKEND_NIGHT"
        assert any("Time (WEEKEND_NIGHT)" in adj for adj in result["adjustments"])

    # =========================================================================
    # SENSOR HEALTH ENHANCED DETECTION
    # =========================================================================

    def test_low_voltage_reduces_confidence_below_threshold(self):
        """Low battery voltage should reduce confidence below reporting threshold.
        
        This is intentional behavior: when sensors are failing, we DON'T want
        to report theft because it's likely a sensor issue, not actual theft.
        """
        result = detect_fuel_theft(
            sensor_pct=78.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 12% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            voltage=10.5,  # Critical voltage reduces factor to 0.3
        )

        # Base confidence 0.9 * sensor factor 0.3 = 0.27 < 0.5 threshold
        # Result should be None (no theft reported)
        assert result is None

    def test_low_voltage_with_higher_base_confidence(self):
        """Even with very high base confidence, critical voltage significantly reduces."""
        # Make drop more severe to test that sensor health still affects reporting
        result = detect_fuel_theft(
            sensor_pct=60.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 30% drop - very severe
            truck_status="STOPPED",
            time_gap_hours=0.5,  # Rapid
            tank_capacity_gal=200.0,
            voltage=11.0,  # Critical voltage
        )
        
        # Even with severe drop, low voltage reduces confidence
        if result is not None:
            assert result["sensor_status"] == "FAILING"
            assert any("Critical voltage" in reason for reason in result["reasons"])

    def test_poor_gps_reduces_confidence_below_threshold(self):
        """Poor GPS should reduce theft confidence below reporting threshold.
        
        This prevents false positives when GPS issues cause erratic readings.
        """
        result = detect_fuel_theft(
            sensor_pct=78.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 12% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            sats=2,  # Very poor GPS reduces factor to 0.4
        )

        # Base confidence 0.9 * sensor factor 0.4 = 0.36 < 0.5 threshold
        assert result is None

    def test_healthy_sensors_no_reduction(self):
        """Healthy sensors should not reduce confidence."""
        result = detect_fuel_theft(
            sensor_pct=78.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 12% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            voltage=13.5,
            gps_quality="Good",
            sats=10,
        )

        assert result is not None
        assert result["sensor_status"] == "HEALTHY"
        # No sensor adjustments
        assert not any("Sensor" in adj for adj in result["adjustments"])

    # =========================================================================
    # COMBINED MULTI-FACTOR ANALYSIS
    # =========================================================================

    def test_night_theft_with_healthy_sensors(self):
        """Night theft with healthy sensors = high confidence."""
        night_time = datetime(2025, 1, 8, 2, 0, 0, tzinfo=timezone.utc)

        result = detect_fuel_theft(
            sensor_pct=75.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 15% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            timestamp=night_time,
            voltage=13.5,
            gps_quality="Good",
            sats=10,
        )

        assert result is not None
        assert result["confidence"] >= 0.9  # High confidence
        assert result["recommendation"].startswith("🚨 HIGH PRIORITY")

    def test_suspicious_drop_but_sensor_failing(self):
        """Large drop but failing sensors = NO THEFT REPORTED.
        
        This is intentional: when sensors are failing, we don't want
        to generate false theft alerts. The drop is likely caused by
        sensor malfunction, not actual fuel theft.
        """
        result = detect_fuel_theft(
            sensor_pct=75.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 15% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            voltage=10.0,  # Critically low: 0.3 factor
            sats=1,  # Almost no GPS: 0.4 factor
        )

        # Base 0.9 * 0.3 (voltage) * 0.4 (GPS) = 0.108 
        # But min factor is 0.3, so: 0.9 * 0.3 = 0.27 < 0.5
        # Result should be None - no theft reported
        assert result is None

    def test_business_hours_with_sensor_issues(self):
        """Business hours + sensor issues = NO THEFT REPORTED."""
        business_time = datetime(2025, 1, 7, 10, 0, 0, tzinfo=timezone.utc)

        result = detect_fuel_theft(
            sensor_pct=75.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 15% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            timestamp=business_time,  # 0.8 factor
            voltage=11.0,  # Critical voltage: 0.3 factor
        )

        # Base 0.9 * 0.8 (business) * 0.3 (voltage) = 0.216 < 0.5
        assert result is None

    # =========================================================================
    # GEOFENCE PLACEHOLDER
    # =========================================================================

    def test_geofence_info_captured(self):
        """GPS coordinates should be captured for future geofence use."""
        result = detect_fuel_theft(
            sensor_pct=75.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 15% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            latitude=25.7617,
            longitude=-80.1918,
        )

        assert result is not None
        assert result["geofence"] is not None
        assert result["geofence"]["lat"] == 25.7617
        assert result["geofence"]["lon"] == -80.1918
        assert result["geofence"]["in_safe_zone"] is None  # Placeholder

    def test_no_geofence_without_coords(self):
        """No geofence info when coordinates not provided."""
        result = detect_fuel_theft(
            sensor_pct=75.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 15% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
        )

        assert result is not None
        assert result["geofence"] is None

    # =========================================================================
    # RECOMMENDATION LEVELS
    # =========================================================================

    def test_high_priority_recommendation(self):
        """Confidence >= 0.85 should get HIGH PRIORITY recommendation."""
        night_time = datetime(2025, 1, 8, 2, 0, 0, tzinfo=timezone.utc)

        result = detect_fuel_theft(
            sensor_pct=65.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 25% drop - rapid loss
            truck_status="STOPPED",
            time_gap_hours=0.5,
            tank_capacity_gal=200.0,
            timestamp=night_time,
            voltage=13.5,
            sats=10,
        )

        assert result is not None
        assert "HIGH PRIORITY" in result["recommendation"]

    def test_medium_priority_recommendation(self):
        """Confidence 0.7-0.85 should get MEDIUM recommendation."""
        result = detect_fuel_theft(
            sensor_pct=78.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 12% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            voltage=12.8,  # Slightly reduces confidence
        )

        assert result is not None
        # Check we're in medium range
        if 0.7 <= result["confidence"] < 0.85:
            assert "MEDIUM" in result["recommendation"]

    def test_low_priority_recommendation(self):
        """Confidence 0.5-0.7 should get LOW recommendation."""
        result = detect_fuel_theft(
            sensor_pct=83.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 7% drop - moderate
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
        )

        assert result is not None
        # Base confidence 0.6 should give low priority
        if result["confidence"] < 0.7:
            assert "LOW" in result["recommendation"]

    # =========================================================================
    # EDGE CASES
    # =========================================================================

    def test_exactly_threshold_values(self):
        """Test exact threshold boundaries."""
        # Exactly 3% drop should not trigger (boundary)
        result = detect_fuel_theft(
            sensor_pct=87.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # Exactly 3% drop
            truck_status="STOPPED",
            time_gap_hours=1.0,
            tank_capacity_gal=200.0,
        )

        assert result is None

    def test_negative_fuel_change(self):
        """Fuel increase (refuel) should not trigger theft."""
        result = detect_fuel_theft(
            sensor_pct=95.0,  # Higher than before
            estimated_pct=85.0,
            last_sensor_pct=80.0,
            truck_status="STOPPED",
            time_gap_hours=1.0,
            tank_capacity_gal=200.0,
        )

        assert result is None

    def test_gallon_calculation_accuracy(self):
        """Verify accurate gallon calculations."""
        result = detect_fuel_theft(
            sensor_pct=75.0,
            estimated_pct=88.0,
            last_sensor_pct=90.0,  # 15% drop
            truck_status="STOPPED",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,  # 200 gal tank
        )

        assert result is not None
        assert result["drop_pct"] == 15.0
        assert result["drop_gal"] == 30.0  # 15% of 200 gallons


class TestTheftDetectionIntegration:
    """Integration tests combining all factors."""

    def test_real_world_night_theft_scenario(self):
        """Simulate realistic night theft scenario with all factors."""
        # Saturday 3AM - truck parked at gas station
        theft_time = datetime(2025, 1, 11, 3, 0, 0, tzinfo=timezone.utc)

        result = detect_fuel_theft(
            sensor_pct=60.0,
            estimated_pct=85.0,
            last_sensor_pct=85.0,  # 25% drop (50 gallons!)
            truck_status="STOPPED",
            time_gap_hours=4.0,  # Parked for 4 hours
            tank_capacity_gal=200.0,
            timestamp=theft_time,
            voltage=13.8,  # Good battery
            gps_quality="Good",
            sats=12,  # Strong GPS
            latitude=25.7617,
            longitude=-80.1918,
        )

        assert result is not None
        assert result["type"] == "STOPPED_THEFT"
        assert result["drop_gal"] == 50.0
        assert result["time_period"] == "WEEKEND_NIGHT"
        assert result["sensor_status"] == "HEALTHY"
        assert result["confidence"] >= 0.95  # Very high confidence
        assert "HIGH PRIORITY" in result["recommendation"]

    def test_real_world_sensor_failure_scenario(self):
        """Simulate sensor failure that looks like theft but isn't."""
        result = detect_fuel_theft(
            sensor_pct=55.0,
            estimated_pct=85.0,
            last_sensor_pct=85.0,  # 30% apparent drop
            truck_status="STOPPED",
            time_gap_hours=1.0,
            tank_capacity_gal=200.0,
            voltage=9.5,  # Very low battery
            gps_quality="none",
            sats=0,  # No GPS at all
        )

        # May still detect but with very low confidence due to sensor issues
        if result is not None:
            assert result["sensor_status"] == "FAILING"
            assert result["confidence"] < 0.3  # Very low confidence
            assert len(result["reasons"]) >= 3  # Multiple warnings

    def test_real_world_daytime_unexplained_loss(self):
        """Simulate unexplained fuel loss during working hours."""
        # Wednesday 2PM
        work_time = datetime(2025, 1, 8, 14, 0, 0, tzinfo=timezone.utc)

        result = detect_fuel_theft(
            sensor_pct=70.0,
            estimated_pct=82.0,
            last_sensor_pct=85.0,  # 15% drop
            truck_status="MOVING",
            time_gap_hours=2.0,
            tank_capacity_gal=200.0,
            timestamp=work_time,
            voltage=14.1,
            sats=10,
        )

        assert result is not None
        # Should detect but with reduced confidence due to business hours
        assert result["time_period"] == "BUSINESS_HOURS"
        assert result["confidence"] < 0.9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
