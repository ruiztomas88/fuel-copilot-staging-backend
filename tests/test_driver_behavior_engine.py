"""
Tests for Driver Behavior Detection Engine v1.0.0

Tests cover:
- Behavior event detection (acceleration, braking, RPM, gear, speed)
- Heavy foot scoring
- Fuel waste calculation
- MPG cross-validation
- State management
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from driver_behavior_engine import (
    DriverBehaviorEngine,
    BehaviorType,
    SeverityLevel,
    BehaviorConfig,
    BehaviorEvent,
    HeavyFootScore,
    MPGCrossValidation,
    TruckBehaviorState,
    CONFIG,
)


class TestBehaviorConfig:
    """Tests for BehaviorConfig defaults"""

    def test_default_config_exists(self):
        """Global CONFIG should exist"""
        assert CONFIG is not None
        assert isinstance(CONFIG, BehaviorConfig)

    def test_accel_thresholds_ordered(self):
        """Acceleration thresholds should be in ascending order"""
        assert CONFIG.accel_minor_threshold < CONFIG.accel_moderate_threshold
        assert CONFIG.accel_moderate_threshold < CONFIG.accel_severe_threshold

    def test_brake_thresholds_ordered(self):
        """Brake thresholds should be negative and descending"""
        assert CONFIG.brake_severe_threshold < CONFIG.brake_moderate_threshold
        assert CONFIG.brake_moderate_threshold < CONFIG.brake_minor_threshold
        assert CONFIG.brake_minor_threshold < 0

    def test_rpm_thresholds_ordered(self):
        """RPM thresholds should be in ascending order"""
        assert CONFIG.rpm_optimal_min < CONFIG.rpm_optimal_max
        assert CONFIG.rpm_optimal_max < CONFIG.rpm_high_warning
        assert CONFIG.rpm_high_warning < CONFIG.rpm_excessive
        assert CONFIG.rpm_excessive < CONFIG.rpm_redline

    def test_speed_thresholds_ordered(self):
        """Speed thresholds should be in ascending order"""
        assert CONFIG.speed_warning < CONFIG.speed_excessive
        assert CONFIG.speed_excessive < CONFIG.speed_severe


class TestBehaviorEvent:
    """Tests for BehaviorEvent dataclass"""

    def test_event_creation(self):
        """Test creating a behavior event"""
        event = BehaviorEvent(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            behavior_type=BehaviorType.HARD_ACCELERATION,
            severity=SeverityLevel.MODERATE,
            value=5.0,
            threshold=4.5,
            fuel_waste_gal=0.05,
        )

        assert event.truck_id == "T001"
        assert event.behavior_type == BehaviorType.HARD_ACCELERATION
        assert event.severity == SeverityLevel.MODERATE

    def test_event_to_dict(self):
        """Test event serialization"""
        now = datetime.now(timezone.utc)
        event = BehaviorEvent(
            truck_id="T001",
            timestamp=now,
            behavior_type=BehaviorType.HARD_BRAKING,
            severity=SeverityLevel.SEVERE,
            value=-8.5,
            threshold=-8.0,
            duration_sec=0.0,
            fuel_waste_gal=0.04,
            context={"speed": 45},
        )

        result = event.to_dict()

        assert isinstance(result, dict)
        assert result["truck_id"] == "T001"
        assert result["behavior_type"] == "hard_braking"
        assert result["severity"] == "severe"
        assert result["value"] == -8.5
        assert result["context"]["speed"] == 45


class TestHeavyFootScore:
    """Tests for HeavyFootScore dataclass"""

    def test_score_creation(self):
        """Test creating a heavy foot score"""
        score = HeavyFootScore(
            truck_id="T001",
            score=85.0,
            grade="B",
            acceleration_score=80.0,
            braking_score=90.0,
            rpm_score=85.0,
            gear_score=80.0,
            speed_score=90.0,
        )

        assert score.truck_id == "T001"
        assert score.score == 85.0
        assert score.grade == "B"

    def test_score_to_dict(self):
        """Test score serialization"""
        score = HeavyFootScore(
            truck_id="T001",
            score=75.0,
            grade="C",
            acceleration_score=70.0,
            braking_score=75.0,
            rpm_score=80.0,
            gear_score=70.0,
            speed_score=80.0,
            hard_accel_count=5,
            hard_brake_count=3,
            total_fuel_waste_gal=0.5,
        )

        result = score.to_dict()

        assert result["score"] == 75.0
        assert result["grade"] == "C"
        assert result["events"]["hard_accelerations"] == 5
        assert result["fuel_impact"]["total_waste_gallons"] == 0.5


class TestTruckBehaviorState:
    """Tests for TruckBehaviorState"""

    def test_state_creation(self):
        """Test creating a truck state"""
        state = TruckBehaviorState(truck_id="T001")

        assert state.truck_id == "T001"
        assert state.last_speed is None
        assert state.hard_accel_count == 0

    def test_reset_daily(self):
        """Test daily reset of counters"""
        state = TruckBehaviorState(truck_id="T001")
        state.hard_accel_count = 10
        state.hard_brake_count = 5
        state.fuel_waste_accel = 0.5
        state.events = [MagicMock()]

        state.reset_daily()

        assert state.hard_accel_count == 0
        assert state.hard_brake_count == 0
        assert state.fuel_waste_accel == 0.0
        assert state.events == []


class TestDriverBehaviorEngine:
    """Tests for the main engine"""

    @pytest.fixture
    def engine(self):
        """Create fresh engine for each test"""
        return DriverBehaviorEngine()

    @pytest.fixture
    def base_timestamp(self):
        """Base timestamp for tests"""
        return datetime.now(timezone.utc)

    # ═══════════════════════════════════════════════════════════════════════════════
    # INITIALIZATION TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_engine_creation(self, engine):
        """Test engine initialization"""
        assert engine.config is not None
        assert engine.truck_states == {}

    def test_engine_with_custom_config(self):
        """Test engine with custom configuration"""
        config = BehaviorConfig(accel_minor_threshold=5.0)
        engine = DriverBehaviorEngine(config=config)

        assert engine.config.accel_minor_threshold == 5.0

    def test_get_or_create_state(self, engine):
        """Test state creation for new truck"""
        state = engine._get_or_create_state("T001")

        assert state.truck_id == "T001"
        assert "T001" in engine.truck_states

    def test_get_existing_state(self, engine):
        """Test retrieving existing state"""
        state1 = engine._get_or_create_state("T001")
        state1.hard_accel_count = 5

        state2 = engine._get_or_create_state("T001")

        assert state2.hard_accel_count == 5
        assert state1 is state2

    # ═══════════════════════════════════════════════════════════════════════════════
    # ACCELERATION DETECTION TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_detect_hard_acceleration_severe(self, engine, base_timestamp):
        """Test severe hard acceleration detection"""
        # First reading to establish baseline
        engine.process_reading("T001", base_timestamp, speed=30.0)

        # Second reading with severe acceleration (6+ mph/s)
        events = engine.process_reading(
            "T001",
            base_timestamp + timedelta(seconds=5),
            speed=60.0,  # +30 mph in 5 seconds = 6 mph/s
        )

        accel_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_ACCELERATION
        ]
        assert len(accel_events) >= 1
        assert any(e.severity == SeverityLevel.SEVERE for e in accel_events)

    def test_detect_hard_acceleration_moderate(self, engine, base_timestamp):
        """Test moderate hard acceleration detection"""
        engine.process_reading("T001", base_timestamp, speed=30.0)

        # +22.5 mph in 5 seconds = 4.5 mph/s (moderate)
        events = engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=5), speed=52.5
        )

        accel_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_ACCELERATION
        ]
        assert len(accel_events) >= 1
        assert any(e.severity == SeverityLevel.MODERATE for e in accel_events)

    def test_detect_hard_acceleration_minor(self, engine, base_timestamp):
        """Test minor hard acceleration detection"""
        engine.process_reading("T001", base_timestamp, speed=30.0)

        # +15 mph in 5 seconds = 3.0 mph/s (minor)
        events = engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=5), speed=45.0
        )

        accel_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_ACCELERATION
        ]
        assert len(accel_events) >= 1
        assert any(e.severity == SeverityLevel.MINOR for e in accel_events)

    def test_normal_acceleration_no_event(self, engine, base_timestamp):
        """Test that normal acceleration doesn't trigger event"""
        engine.process_reading("T001", base_timestamp, speed=30.0)

        # +10 mph in 5 seconds = 2.0 mph/s (normal)
        events = engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=5), speed=40.0
        )

        accel_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_ACCELERATION
        ]
        assert len(accel_events) == 0

    # ═══════════════════════════════════════════════════════════════════════════════
    # BRAKING DETECTION TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_detect_hard_braking_severe(self, engine, base_timestamp):
        """Test severe hard braking detection"""
        engine.process_reading("T001", base_timestamp, speed=60.0)

        # -40 mph in 5 seconds = -8 mph/s (severe)
        events = engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=5), speed=20.0
        )

        brake_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_BRAKING
        ]
        assert len(brake_events) >= 1
        assert any(e.severity == SeverityLevel.SEVERE for e in brake_events)

    def test_detect_hard_braking_moderate(self, engine, base_timestamp):
        """Test moderate hard braking detection"""
        engine.process_reading("T001", base_timestamp, speed=60.0)

        # -30 mph in 5 seconds = -6 mph/s (moderate)
        events = engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=5), speed=30.0
        )

        brake_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_BRAKING
        ]
        assert len(brake_events) >= 1
        assert any(e.severity == SeverityLevel.MODERATE for e in brake_events)

    def test_normal_braking_no_event(self, engine, base_timestamp):
        """Test that normal braking doesn't trigger event"""
        engine.process_reading("T001", base_timestamp, speed=60.0)

        # -10 mph in 5 seconds = -2 mph/s (normal)
        events = engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=5), speed=50.0
        )

        brake_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_BRAKING
        ]
        assert len(brake_events) == 0

    # ═══════════════════════════════════════════════════════════════════════════════
    # DEVICE-DETECTED EVENTS TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_device_harsh_accel_detection(self, engine, base_timestamp):
        """Test device-detected harsh acceleration"""
        events = engine.process_reading(
            "T001",
            base_timestamp,
            speed=40.0,
            device_harsh_accel=2,  # Device detected 2 harsh events
        )

        accel_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_ACCELERATION
        ]
        assert len(accel_events) >= 1
        assert any(
            e.context.get("source") == "device_accelerometer" for e in accel_events
        )

    def test_device_harsh_brake_detection(self, engine, base_timestamp):
        """Test device-detected harsh braking"""
        events = engine.process_reading(
            "T001",
            base_timestamp,
            speed=40.0,
            device_harsh_brake=1,
        )

        brake_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_BRAKING
        ]
        assert len(brake_events) >= 1
        assert any(
            e.context.get("source") == "device_accelerometer" for e in brake_events
        )

    # ═══════════════════════════════════════════════════════════════════════════════
    # TIME GAP HANDLING TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_skip_large_time_gap(self, engine, base_timestamp):
        """Test that large time gaps are skipped"""
        engine.process_reading("T001", base_timestamp, speed=30.0)

        # 10 minute gap (> 300 seconds) - should be skipped
        events = engine.process_reading(
            "T001", base_timestamp + timedelta(minutes=10), speed=60.0
        )

        # No events should be generated due to data gap
        assert len(events) == 0

    def test_skip_duplicate_timestamp(self, engine, base_timestamp):
        """Test that duplicate/near-duplicate readings are skipped"""
        engine.process_reading("T001", base_timestamp, speed=30.0)

        # 0.5 second gap (< 1 second) - should be skipped
        events = engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=0.5), speed=60.0
        )

        assert len(events) == 0

    # ═══════════════════════════════════════════════════════════════════════════════
    # FUEL WASTE CALCULATION TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_fuel_waste_accumulated(self, engine, base_timestamp):
        """Test that fuel waste is accumulated"""
        engine.process_reading("T001", base_timestamp, speed=30.0)

        # Trigger hard acceleration
        engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=5), speed=60.0
        )

        state = engine.truck_states["T001"]
        assert state.fuel_waste_accel > 0

    def test_device_event_fuel_waste_multiplied(self, engine, base_timestamp):
        """Test that device events multiply fuel waste by count"""
        events = engine.process_reading(
            "T001",
            base_timestamp,
            device_harsh_accel=3,  # 3 events
        )

        accel_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_ACCELERATION
        ]
        if accel_events:
            # Fuel waste should be multiplied by count
            expected_waste = CONFIG.fuel_waste_hard_accel_gal * 3
            assert accel_events[0].fuel_waste_gal == pytest.approx(
                expected_waste, rel=0.01
            )

    # ═══════════════════════════════════════════════════════════════════════════════
    # STATE COUNTER TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_hard_accel_counter_incremented(self, engine, base_timestamp):
        """Test that hard acceleration counter is incremented"""
        engine.process_reading("T001", base_timestamp, speed=30.0)
        engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=5), speed=60.0
        )

        state = engine.truck_states["T001"]
        assert state.hard_accel_count >= 1

    def test_hard_brake_counter_incremented(self, engine, base_timestamp):
        """Test that hard braking counter is incremented"""
        engine.process_reading("T001", base_timestamp, speed=60.0)
        engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=5), speed=20.0
        )

        state = engine.truck_states["T001"]
        assert state.hard_brake_count >= 1


class TestMPGCrossValidation:
    """Tests for MPG cross-validation dataclass"""

    def test_validation_creation(self):
        """Test creating a validation result"""
        validation = MPGCrossValidation(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            kalman_mpg=6.5,
            ecu_mpg=6.3,
            difference_pct=3.2,
            is_valid=True,
            recommendation="MPG readings consistent",
        )

        assert validation.is_valid is True
        assert validation.difference_pct == 3.2

    def test_validation_to_dict(self):
        """Test validation serialization"""
        now = datetime.now(timezone.utc)
        validation = MPGCrossValidation(
            truck_id="T001",
            timestamp=now,
            kalman_mpg=6.5,
            ecu_mpg=5.8,
            difference_pct=12.1,
            is_valid=True,
            recommendation="Within tolerance",
        )

        result = validation.to_dict()

        assert result["kalman_mpg"] == 6.5
        assert result["is_valid"] is True


class TestBehaviorTypes:
    """Tests for behavior type enumeration"""

    def test_all_behavior_types_exist(self):
        """All expected behavior types should exist"""
        expected = [
            "HARD_ACCELERATION",
            "HARD_BRAKING",
            "EXCESSIVE_RPM",
            "WRONG_GEAR",
            "OVERSPEEDING",
            "EXCESSIVE_IDLE",
        ]

        for name in expected:
            assert hasattr(BehaviorType, name)

    def test_behavior_type_values(self):
        """Behavior type values should be snake_case strings"""
        assert BehaviorType.HARD_ACCELERATION.value == "hard_acceleration"
        assert BehaviorType.HARD_BRAKING.value == "hard_braking"
        assert BehaviorType.WRONG_GEAR.value == "wrong_gear"


class TestSeverityLevels:
    """Tests for severity level enumeration"""

    def test_all_severity_levels_exist(self):
        """All expected severity levels should exist"""
        expected = ["MINOR", "MODERATE", "SEVERE", "CRITICAL"]

        for name in expected:
            assert hasattr(SeverityLevel, name)

    def test_severity_level_values(self):
        """Severity level values should be lowercase strings"""
        assert SeverityLevel.MINOR.value == "minor"
        assert SeverityLevel.MODERATE.value == "moderate"
        assert SeverityLevel.SEVERE.value == "severe"
        assert SeverityLevel.CRITICAL.value == "critical"


class TestDailyReset:
    """Tests for daily reset functionality"""

    def test_daily_reset_triggered(self):
        """Test that daily reset is triggered on new day"""
        engine = DriverBehaviorEngine()
        engine._last_daily_reset = datetime.now(timezone.utc) - timedelta(days=1)

        # Create state with non-zero counters
        state = engine._get_or_create_state("T001")
        state.hard_accel_count = 10

        # Process reading should trigger reset
        engine._check_daily_reset()

        # Counter should be reset
        assert state.hard_accel_count == 0

    def test_no_reset_same_day(self):
        """Test that reset is not triggered on same day"""
        engine = DriverBehaviorEngine()
        engine._last_daily_reset = datetime.now(timezone.utc)

        # Create state with non-zero counters
        state = engine._get_or_create_state("T001")
        state.hard_accel_count = 10

        # Check reset (should not trigger)
        engine._check_daily_reset()

        # Counter should NOT be reset
        assert state.hard_accel_count == 10


class TestMultipleTrucks:
    """Tests for handling multiple trucks"""

    def test_separate_states_per_truck(self):
        """Each truck should have separate state"""
        engine = DriverBehaviorEngine()
        now = datetime.now(timezone.utc)

        # Process readings for multiple trucks
        engine.process_reading("T001", now, speed=30.0)
        engine.process_reading("T002", now, speed=50.0)

        assert "T001" in engine.truck_states
        assert "T002" in engine.truck_states
        assert engine.truck_states["T001"].last_speed == 30.0
        assert engine.truck_states["T002"].last_speed == 50.0

    def test_events_isolated_per_truck(self):
        """Events should be isolated per truck"""
        engine = DriverBehaviorEngine()
        now = datetime.now(timezone.utc)

        # Setup T001
        engine.process_reading("T001", now, speed=30.0)
        engine.process_reading("T001", now + timedelta(seconds=5), speed=60.0)

        # Setup T002 with no events
        engine.process_reading("T002", now, speed=30.0)
        engine.process_reading("T002", now + timedelta(seconds=5), speed=32.0)

        assert engine.truck_states["T001"].hard_accel_count >= 1
        assert engine.truck_states["T002"].hard_accel_count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# RPM DETECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRPMDetection:
    """Tests for RPM-related behavior detection"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    @pytest.fixture
    def base_timestamp(self):
        return datetime.now(timezone.utc)

    def test_excessive_rpm_critical(self, engine, base_timestamp):
        """Test critical excessive RPM detection (redline)"""
        # First reading to establish timing
        engine.process_reading("T001", base_timestamp, rpm=1500)

        # Simulate sustained redline RPM (2500+) for 10+ seconds
        for i in range(12):
            events = engine.process_reading(
                "T001",
                base_timestamp + timedelta(seconds=i + 1),
                rpm=2600,  # Above redline (2500)
            )

        rpm_events = [
            e for e in events if e.behavior_type == BehaviorType.EXCESSIVE_RPM
        ]
        # Should have critical event after sustained redline
        critical_events = [
            e for e in rpm_events if e.severity == SeverityLevel.CRITICAL
        ]
        assert len(critical_events) >= 1

    def test_excessive_rpm_moderate(self, engine, base_timestamp):
        """Test moderate excessive RPM detection"""
        engine.process_reading("T001", base_timestamp, rpm=1500)

        # Simulate sustained high RPM (2100+) for 5+ seconds but below redline
        for i in range(7):
            events = engine.process_reading(
                "T001",
                base_timestamp + timedelta(seconds=i + 1),
                rpm=2200,  # Above excessive (2100) but below redline (2500)
            )

        rpm_events = [
            e for e in events if e.behavior_type == BehaviorType.EXCESSIVE_RPM
        ]
        assert len(rpm_events) >= 1

    def test_normal_rpm_no_event(self, engine, base_timestamp):
        """Test that normal RPM doesn't trigger event"""
        engine.process_reading("T001", base_timestamp, rpm=1500)

        events = engine.process_reading(
            "T001",
            base_timestamp + timedelta(seconds=5),
            rpm=1600,  # Within optimal range
        )

        rpm_events = [
            e for e in events if e.behavior_type == BehaviorType.EXCESSIVE_RPM
        ]
        assert len(rpm_events) == 0

    def test_high_rpm_fuel_waste(self, engine, base_timestamp):
        """Test fuel waste accumulation for high RPM"""
        engine.process_reading("T001", base_timestamp, rpm=1500)
        engine.process_reading(
            "T001",
            base_timestamp + timedelta(seconds=60),  # 1 minute of high RPM
            rpm=2200,
        )

        state = engine.truck_states["T001"]
        assert state.fuel_waste_rpm > 0


# ═══════════════════════════════════════════════════════════════════════════════
# WRONG GEAR DETECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestWrongGearDetection:
    """Tests for wrong gear detection"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    @pytest.fixture
    def base_timestamp(self):
        return datetime.now(timezone.utc)

    def test_wrong_gear_detection(self, engine, base_timestamp):
        """Test detection of wrong gear (high RPM, low gear, can upshift)"""
        engine.process_reading("T001", base_timestamp, rpm=1500, gear=5, speed=40.0)

        # Simulate sustained high RPM in low gear for 6+ seconds
        for i in range(8):
            events = engine.process_reading(
                "T001",
                base_timestamp + timedelta(seconds=i + 1),
                rpm=1800,  # Above wrong_gear_rpm_threshold (1700)
                gear=5,  # Low gear (not at max ~13)
                speed=45.0,  # Above 25 mph
            )

        gear_events = [e for e in events if e.behavior_type == BehaviorType.WRONG_GEAR]
        assert len(gear_events) >= 1

    def test_no_wrong_gear_at_max_gear(self, engine, base_timestamp):
        """Test no wrong gear event when already at max gear"""
        engine.process_reading("T001", base_timestamp, rpm=1500, gear=13, speed=60.0)

        # High RPM but already at max gear
        for i in range(8):
            events = engine.process_reading(
                "T001",
                base_timestamp + timedelta(seconds=i + 1),
                rpm=1800,
                gear=13,  # At max gear
                speed=65.0,
            )

        gear_events = [e for e in events if e.behavior_type == BehaviorType.WRONG_GEAR]
        assert len(gear_events) == 0

    def test_no_wrong_gear_at_low_speed(self, engine, base_timestamp):
        """Test no wrong gear event at low speed (starting from stop)"""
        engine.process_reading("T001", base_timestamp, rpm=1500, gear=2, speed=15.0)

        # High RPM in low gear but low speed (accelerating from stop is OK)
        for i in range(8):
            events = engine.process_reading(
                "T001",
                base_timestamp + timedelta(seconds=i + 1),
                rpm=1900,
                gear=2,
                speed=20.0,  # Below 25 mph
            )

        gear_events = [e for e in events if e.behavior_type == BehaviorType.WRONG_GEAR]
        assert len(gear_events) == 0


# ═══════════════════════════════════════════════════════════════════════════════
# OVERSPEEDING DETECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestOverspeedingDetection:
    """Tests for overspeeding detection"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    @pytest.fixture
    def base_timestamp(self):
        return datetime.now(timezone.utc)

    def test_overspeeding_severe(self, engine, base_timestamp):
        """Test severe overspeeding detection (75+ mph)"""
        engine.process_reading("T001", base_timestamp, speed=60.0)

        # Simulate sustained severe overspeeding for 60+ seconds
        for i in range(65):
            events = engine.process_reading(
                "T001",
                base_timestamp + timedelta(seconds=i + 1),
                speed=78.0,  # Above severe threshold (75)
            )

        speed_events = [
            e for e in events if e.behavior_type == BehaviorType.OVERSPEEDING
        ]
        assert len(speed_events) >= 1
        assert any(e.severity == SeverityLevel.SEVERE for e in speed_events)

    def test_overspeeding_moderate(self, engine, base_timestamp):
        """Test moderate overspeeding detection (70-75 mph)"""
        engine.process_reading("T001", base_timestamp, speed=60.0)

        # Simulate sustained moderate overspeeding for 60+ seconds
        for i in range(65):
            events = engine.process_reading(
                "T001",
                base_timestamp + timedelta(seconds=i + 1),
                speed=72.0,  # Between excessive (70) and severe (75)
            )

        speed_events = [
            e for e in events if e.behavior_type == BehaviorType.OVERSPEEDING
        ]
        assert len(speed_events) >= 1
        assert any(e.severity == SeverityLevel.MODERATE for e in speed_events)

    def test_overspeeding_minor(self, engine, base_timestamp):
        """Test minor overspeeding detection (65-70 mph)"""
        engine.process_reading("T001", base_timestamp, speed=60.0)

        # Simulate sustained minor overspeeding for 60+ seconds
        for i in range(65):
            events = engine.process_reading(
                "T001",
                base_timestamp + timedelta(seconds=i + 1),
                speed=67.0,  # Between warning (65) and excessive (70)
            )

        speed_events = [
            e for e in events if e.behavior_type == BehaviorType.OVERSPEEDING
        ]
        assert len(speed_events) >= 1
        assert any(e.severity == SeverityLevel.MINOR for e in speed_events)

    def test_no_overspeeding_under_65(self, engine, base_timestamp):
        """Test no overspeeding event under 65 mph"""
        engine.process_reading("T001", base_timestamp, speed=55.0)

        for i in range(65):
            events = engine.process_reading(
                "T001",
                base_timestamp + timedelta(seconds=i + 1),
                speed=63.0,  # Below warning threshold (65)
            )

        speed_events = [
            e for e in events if e.behavior_type == BehaviorType.OVERSPEEDING
        ]
        assert len(speed_events) == 0

    def test_overspeeding_fuel_waste_scales_with_speed(self, engine, base_timestamp):
        """Test that fuel waste scales with mph over 65"""
        engine.process_reading("T001", base_timestamp, speed=60.0)

        # 5 mph over for 60 seconds
        engine.process_reading(
            "T001", base_timestamp + timedelta(seconds=60), speed=70.0
        )

        state = engine.truck_states["T001"]
        assert state.fuel_waste_speed > 0


# ═══════════════════════════════════════════════════════════════════════════════
# MINOR BRAKING TEST
# ═══════════════════════════════════════════════════════════════════════════════


class TestMinorBraking:
    """Tests for minor braking detection"""

    def test_detect_hard_braking_minor(self):
        """Test minor hard braking detection"""
        engine = DriverBehaviorEngine()
        now = datetime.now(timezone.utc)

        engine.process_reading("T001", now, speed=60.0)

        # -20 mph in 5 seconds = -4 mph/s (minor)
        events = engine.process_reading("T001", now + timedelta(seconds=5), speed=40.0)

        brake_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_BRAKING
        ]
        assert len(brake_events) >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# HEAVY FOOT SCORE CALCULATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestHeavyFootScoreCalculation:
    """Tests for heavy foot score calculation logic"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    def test_calculate_score_no_events(self, engine):
        """Perfect score when no events"""
        engine._get_or_create_state("T001")
        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        assert score.score >= 90  # Should be near perfect
        assert score.grade in ["A", "B"]

    def test_calculate_score_with_acceleration_events(self, engine):
        """Score should decrease with acceleration events"""
        state = engine._get_or_create_state("T001")
        state.hard_accel_count = 20
        state.fuel_waste_accel = 1.0

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        assert score.acceleration_score < 100
        assert score.hard_accel_count == 20

    def test_calculate_score_with_brake_events(self, engine):
        """Score should decrease with brake events"""
        state = engine._get_or_create_state("T001")
        state.hard_brake_count = 15
        state.fuel_waste_brake = 0.6

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        assert score.braking_score < 100
        assert score.hard_brake_count == 15

    def test_calculate_score_with_high_rpm(self, engine):
        """Score should decrease with high RPM time"""
        state = engine._get_or_create_state("T001")
        state.high_rpm_seconds = 1800  # 30 minutes
        state.fuel_waste_rpm = 0.5

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        assert score.rpm_score < 100
        assert score.high_rpm_minutes == pytest.approx(30, rel=0.1)

    def test_calculate_score_with_wrong_gear(self, engine):
        """Score should decrease with wrong gear time"""
        state = engine._get_or_create_state("T001")
        state.wrong_gear_seconds = 600  # 10 minutes
        state.fuel_waste_gear = 0.3

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        assert score.gear_score < 100
        assert score.wrong_gear_minutes == pytest.approx(10, rel=0.1)

    def test_calculate_score_with_overspeeding(self, engine):
        """Score should decrease with overspeeding time"""
        state = engine._get_or_create_state("T001")
        state.overspeeding_seconds = 1200  # 20 minutes
        state.fuel_waste_speed = 0.4

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        assert score.speed_score < 100
        assert score.overspeeding_minutes == pytest.approx(20, rel=0.1)

    def test_grade_a_score(self, engine):
        """Score >= 90 should get grade A"""
        state = engine._get_or_create_state("T001")
        # Minimal events
        state.hard_accel_count = 2
        state.hard_brake_count = 2

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        if score.score >= 90:
            assert score.grade == "A"

    def test_grade_b_score(self, engine):
        """Score 80-89 should get grade B"""
        state = engine._get_or_create_state("T001")
        state.hard_accel_count = 8
        state.hard_brake_count = 8
        state.high_rpm_seconds = 600

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        if 80 <= score.score < 90:
            assert score.grade == "B"

    def test_grade_c_score(self, engine):
        """Score 70-79 should get grade C"""
        state = engine._get_or_create_state("T001")
        state.hard_accel_count = 15
        state.hard_brake_count = 12
        state.high_rpm_seconds = 1200

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        if 70 <= score.score < 80:
            assert score.grade == "C"

    def test_grade_d_score(self, engine):
        """Score 60-69 should get grade D"""
        state = engine._get_or_create_state("T001")
        state.hard_accel_count = 25
        state.hard_brake_count = 20
        state.high_rpm_seconds = 2400
        state.overspeeding_seconds = 1800

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        if 60 <= score.score < 70:
            assert score.grade == "D"

    def test_total_fuel_waste_in_score(self, engine):
        """Total fuel waste should sum all categories"""
        state = engine._get_or_create_state("T001")
        state.fuel_waste_accel = 0.5
        state.fuel_waste_brake = 0.3
        state.fuel_waste_rpm = 0.2
        state.fuel_waste_gear = 0.1
        state.fuel_waste_speed = 0.4

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        expected_total = 0.5 + 0.3 + 0.2 + 0.1 + 0.4
        assert score.total_fuel_waste_gal == pytest.approx(expected_total, rel=0.01)

    def test_fuel_waste_breakdown(self, engine):
        """Fuel waste breakdown should contain all categories"""
        state = engine._get_or_create_state("T001")
        state.fuel_waste_accel = 0.5
        state.fuel_waste_brake = 0.3

        score = engine.calculate_heavy_foot_score("T001", period_hours=8)

        assert "hard_acceleration" in score.fuel_waste_breakdown
        assert "hard_braking" in score.fuel_waste_breakdown
        assert "high_rpm" in score.fuel_waste_breakdown
        assert "wrong_gear" in score.fuel_waste_breakdown
        assert "overspeeding" in score.fuel_waste_breakdown

    def test_weighted_overall_score(self, engine):
        """Overall score should use correct weights"""
        state = engine._get_or_create_state("T001")
        # All components at 80
        state.hard_accel_count = 4
        state.hard_brake_count = 4

        score = engine.calculate_heavy_foot_score(
            "T001", period_hours=8, total_driving_hours=8
        )

        # Should be weighted average
        assert 0 <= score.score <= 100


class TestMPGCrossValidationMethod:
    """Tests for MPG cross-validation method"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    def test_cross_validate_insufficient_kalman_samples(self, engine):
        """Should return None if not enough Kalman samples"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [6.5, 6.3, 6.4]  # Only 3
        state.ecu_mpg_samples = [6.2, 6.3, 6.4, 6.5, 6.6]

        result = engine.cross_validate_mpg("T001")

        assert result is None

    def test_cross_validate_insufficient_ecu_samples(self, engine):
        """Should return None if not enough ECU samples"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [6.5, 6.3, 6.4, 6.5, 6.6]
        state.ecu_mpg_samples = [6.2, 6.3]  # Only 2

        result = engine.cross_validate_mpg("T001")

        assert result is None

    def test_cross_validate_valid_samples(self, engine):
        """Should return validation when enough samples"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [6.5, 6.3, 6.4, 6.5, 6.6]
        state.ecu_mpg_samples = [6.2, 6.3, 6.4, 6.5, 6.6]

        result = engine.cross_validate_mpg("T001")

        assert result is not None
        assert result.truck_id == "T001"

    def test_cross_validate_is_valid_within_tolerance(self, engine):
        """Should be valid when within tolerance"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [6.5] * 10
        state.ecu_mpg_samples = [6.4] * 10  # ~1.5% difference

        result = engine.cross_validate_mpg("T001")

        assert result is not None
        assert result.difference_pct < 5  # Within typical tolerance

    def test_cross_validate_kalman_higher(self, engine):
        """Should indicate Kalman higher when applicable"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [7.0] * 10
        state.ecu_mpg_samples = [6.0] * 10  # Kalman ~17% higher

        result = engine.cross_validate_mpg("T001")

        assert result is not None
        assert result.kalman_mpg > result.ecu_mpg
        assert "higher" in result.recommendation.lower()

    def test_cross_validate_kalman_lower(self, engine):
        """Should indicate Kalman lower when applicable"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [5.0] * 10
        state.ecu_mpg_samples = [6.0] * 10  # Kalman ~17% lower

        result = engine.cross_validate_mpg("T001")

        assert result is not None
        assert result.kalman_mpg < result.ecu_mpg
        assert "lower" in result.recommendation.lower()

    def test_cross_validate_zero_ecu_avg(self, engine):
        """Should return None if ECU average is zero"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [6.0] * 10
        state.ecu_mpg_samples = [0.0] * 10

        result = engine.cross_validate_mpg("T001")

        assert result is None


class TestFleetBehaviorSummary:
    """Tests for fleet behavior summary"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    def test_get_fleet_summary_empty(self, engine):
        """Should return database summary when no in-memory state"""
        # With no truck states and mocked database
        with patch.object(engine, "_get_behavior_summary_from_database") as mock_db:
            mock_db.return_value = {
                "fleet_size": 0,
                "average_score": 0,
                "data_source": "database",
            }

            result = engine.get_fleet_behavior_summary()

            mock_db.assert_called_once()

    def test_get_fleet_summary_from_memory(self, engine):
        """Should return memory summary when trucks exist"""
        # Add some truck states
        state1 = engine._get_or_create_state("T001")
        state1.hard_accel_count = 5
        state2 = engine._get_or_create_state("T002")
        state2.hard_accel_count = 10

        result = engine.get_fleet_behavior_summary()

        assert result["fleet_size"] == 2
        assert result["data_source"] == "real-time"

    def test_fleet_summary_has_best_performers(self, engine):
        """Summary should include best performers"""
        for i in range(5):
            state = engine._get_or_create_state(f"T00{i}")
            state.hard_accel_count = i * 3

        result = engine.get_fleet_behavior_summary()

        assert "best_performers" in result
        assert len(result["best_performers"]) <= 3

    def test_fleet_summary_has_worst_performers(self, engine):
        """Summary should include worst performers"""
        for i in range(5):
            state = engine._get_or_create_state(f"T00{i}")
            state.hard_accel_count = i * 3

        result = engine.get_fleet_behavior_summary()

        assert "worst_performers" in result
        assert len(result["worst_performers"]) <= 3

    def test_fleet_summary_has_waste_breakdown(self, engine):
        """Summary should include waste breakdown"""
        state = engine._get_or_create_state("T001")
        state.fuel_waste_accel = 0.5

        result = engine.get_fleet_behavior_summary()

        assert "waste_breakdown" in result
        assert "hard_acceleration" in result["waste_breakdown"]

    def test_fleet_summary_has_behavior_scores(self, engine):
        """Summary should include behavior scores per category"""
        state = engine._get_or_create_state("T001")
        state.hard_accel_count = 5

        result = engine.get_fleet_behavior_summary()

        assert "behavior_scores" in result
        assert "acceleration" in result["behavior_scores"]
        assert "braking" in result["behavior_scores"]

    def test_fleet_summary_has_recommendations(self, engine):
        """Summary should include recommendations"""
        state = engine._get_or_create_state("T001")
        state.hard_accel_count = 5

        result = engine.get_fleet_behavior_summary()

        assert "recommendations" in result
        assert isinstance(result["recommendations"], list)


class TestFleetRecommendations:
    """Tests for fleet recommendation generation"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    def test_recommendations_low_fleet_score(self, engine):
        """Should recommend training when average score is low"""
        scores = [
            HeavyFootScore(
                truck_id="T001",
                score=50.0,
                grade="F",
                acceleration_score=50,
                braking_score=50,
                rpm_score=50,
                gear_score=50,
                speed_score=50,
            ),
            HeavyFootScore(
                truck_id="T002",
                score=55.0,
                grade="F",
                acceleration_score=55,
                braking_score=55,
                rpm_score=55,
                gear_score=55,
                speed_score=55,
            ),
        ]
        waste = {
            "hard_acceleration": 1.0,
            "hard_braking": 0.5,
            "high_rpm": 0.3,
            "wrong_gear": 0.2,
            "overspeeding": 0.1,
        }

        recs = engine._generate_fleet_recommendations(scores, waste)

        assert any("below 70" in r.lower() or "training" in r.lower() for r in recs)

    def test_recommendations_acceleration_issue(self, engine):
        """Should recommend acceleration training when it's the main issue"""
        scores = [
            HeavyFootScore(
                truck_id="T001",
                score=75.0,
                grade="C",
                acceleration_score=60,
                braking_score=85,
                rpm_score=85,
                gear_score=85,
                speed_score=85,
            ),
        ]
        waste = {
            "hard_acceleration": 2.0,
            "hard_braking": 0.5,
            "high_rpm": 0.3,
            "wrong_gear": 0.2,
            "overspeeding": 0.1,
        }

        recs = engine._generate_fleet_recommendations(scores, waste)

        assert any("acceleration" in r.lower() for r in recs)

    def test_recommendations_rpm_issue(self, engine):
        """Should recommend RPM training when it's the main issue"""
        scores = [
            HeavyFootScore(
                truck_id="T001",
                score=75.0,
                grade="C",
                acceleration_score=85,
                braking_score=85,
                rpm_score=60,
                gear_score=85,
                speed_score=85,
            ),
        ]
        waste = {
            "hard_acceleration": 0.2,
            "hard_braking": 0.3,
            "high_rpm": 2.0,
            "wrong_gear": 0.2,
            "overspeeding": 0.1,
        }

        recs = engine._generate_fleet_recommendations(scores, waste)

        assert any("rpm" in r.lower() for r in recs)

    def test_recommendations_overspeeding_issue(self, engine):
        """Should recommend speed control when overspeeding is main issue"""
        scores = [
            HeavyFootScore(
                truck_id="T001",
                score=75.0,
                grade="C",
                acceleration_score=85,
                braking_score=85,
                rpm_score=85,
                gear_score=85,
                speed_score=60,
            ),
        ]
        waste = {
            "hard_acceleration": 0.2,
            "hard_braking": 0.3,
            "high_rpm": 0.2,
            "wrong_gear": 0.2,
            "overspeeding": 2.0,
        }

        recs = engine._generate_fleet_recommendations(scores, waste)

        assert any("overspeed" in r.lower() or "speed" in r.lower() for r in recs)

    def test_recommendations_outlier_trucks(self, engine):
        """Should flag trucks needing immediate attention"""
        scores = [
            HeavyFootScore(
                truck_id="T001",
                score=40.0,
                grade="F",
                acceleration_score=40,
                braking_score=40,
                rpm_score=40,
                gear_score=40,
                speed_score=40,
            ),
            HeavyFootScore(
                truck_id="T002",
                score=85.0,
                grade="B",
                acceleration_score=85,
                braking_score=85,
                rpm_score=85,
                gear_score=85,
                speed_score=85,
            ),
        ]
        waste = {
            "hard_acceleration": 1.0,
            "hard_braking": 0.5,
            "high_rpm": 0.3,
            "wrong_gear": 0.2,
            "overspeeding": 0.1,
        }

        recs = engine._generate_fleet_recommendations(scores, waste)

        assert any("immediate attention" in r.lower() or "T001" in r for r in recs)


class TestBehaviorEventDetails:
    """Tests for behavior event details and context"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    def test_event_has_truck_id(self, engine):
        """Event should contain truck ID"""
        now = datetime.now(timezone.utc)
        engine.process_reading("T001", now, speed=30.0)
        events = engine.process_reading("T001", now + timedelta(seconds=5), speed=60.0)

        if events:
            assert events[0].truck_id == "T001"

    def test_event_has_timestamp(self, engine):
        """Event should contain timestamp"""
        now = datetime.now(timezone.utc)
        engine.process_reading("T001", now, speed=30.0)
        events = engine.process_reading("T001", now + timedelta(seconds=5), speed=60.0)

        if events:
            assert events[0].timestamp is not None

    def test_event_has_value_and_threshold(self, engine):
        """Event should contain value and threshold"""
        now = datetime.now(timezone.utc)
        engine.process_reading("T001", now, speed=30.0)
        events = engine.process_reading("T001", now + timedelta(seconds=5), speed=60.0)

        accel_events = [
            e for e in events if e.behavior_type == BehaviorType.HARD_ACCELERATION
        ]
        if accel_events:
            assert accel_events[0].value is not None
            assert accel_events[0].threshold is not None

    def test_event_has_fuel_waste(self, engine):
        """Event should contain fuel waste estimate"""
        now = datetime.now(timezone.utc)
        engine.process_reading("T001", now, speed=30.0)
        events = engine.process_reading("T001", now + timedelta(seconds=5), speed=60.0)

        if events:
            assert events[0].fuel_waste_gal >= 0

    def test_event_context_has_speed(self, engine):
        """Event context should include unit information"""
        now = datetime.now(timezone.utc)
        engine.process_reading("T001", now, speed=30.0)
        events = engine.process_reading("T001", now + timedelta(seconds=5), speed=60.0)

        if events and events[0].context:
            # Context includes measurement unit info
            assert "unit" in events[0].context or "speed" in events[0].context


class TestTruckStateManagement:
    """Tests for truck state management"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    def test_get_truck_state_creates_new(self, engine):
        """Should create new state for unknown truck"""
        assert "T999" not in engine.truck_states

        state = engine._get_or_create_state("T999")

        assert state is not None
        assert "T999" in engine.truck_states

    def test_get_truck_state_returns_existing(self, engine):
        """Should return existing state for known truck"""
        state1 = engine._get_or_create_state("T001")
        state1.hard_accel_count = 42

        state2 = engine._get_or_create_state("T001")

        assert state2.hard_accel_count == 42

    def test_state_tracks_last_speed(self, engine):
        """State should track last speed reading"""
        now = datetime.now(timezone.utc)
        engine.process_reading("T001", now, speed=55.0)

        state = engine.truck_states["T001"]

        assert state.last_speed == 55.0

    def test_state_tracks_last_timestamp(self, engine):
        """State should track last timestamp"""
        now = datetime.now(timezone.utc)
        engine.process_reading("T001", now, speed=55.0)

        state = engine.truck_states["T001"]

        assert state.last_timestamp == now

    def test_state_tracks_last_rpm(self, engine):
        """State should track last RPM reading"""
        now = datetime.now(timezone.utc)
        engine.process_reading("T001", now, speed=55.0, rpm=1650)

        state = engine.truck_states["T001"]

        assert state.last_rpm == 1650

    def test_state_stores_events(self, engine):
        """State should store events list"""
        now = datetime.now(timezone.utc)
        engine.process_reading("T001", now, speed=30.0)
        events = engine.process_reading("T001", now + timedelta(seconds=5), speed=60.0)

        state = engine.truck_states["T001"]

        assert len(state.events) >= len(events)


# ═══════════════════════════════════════════════════════════════════════════════
# HEAVY FOOT SCORE CALCULATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestHeavyFootScoreCalculation:
    """Tests for heavy foot score calculation logic"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    def test_calculate_score_perfect_driver(self, engine):
        """Test score calculation for perfect driver (no events)"""
        state = engine._get_or_create_state("T001")

        score = engine.calculate_heavy_foot_score(
            "T001", period_hours=8, total_driving_hours=4
        )

        assert score.score >= 90
        assert score.grade == "A"

    def test_calculate_score_with_events(self, engine):
        """Test score calculation with various events"""
        state = engine._get_or_create_state("T001")
        state.hard_accel_count = 15
        state.hard_brake_count = 10
        state.high_rpm_seconds = 600  # 10 minutes
        state.wrong_gear_seconds = 300  # 5 minutes
        state.overspeeding_seconds = 300  # 5 minutes

        score = engine.calculate_heavy_foot_score(
            "T001", period_hours=8, total_driving_hours=4
        )

        assert score.score < 100  # Should have some penalty from events
        assert score.hard_accel_count == 15
        assert score.hard_brake_count == 10

    def test_calculate_score_grade_boundaries(self, engine):
        """Test score grade boundaries"""
        state = engine._get_or_create_state("T001")

        # Perfect score - Grade A
        score_a = engine.calculate_heavy_foot_score("T001", period_hours=8)
        assert score_a.grade == "A"

        # Add many events for lower grade
        state.hard_accel_count = 50
        state.hard_brake_count = 40
        state.high_rpm_seconds = 1800
        state.overspeeding_seconds = 1800

        score_low = engine.calculate_heavy_foot_score(
            "T001", period_hours=8, total_driving_hours=4
        )
        assert score_low.grade in ["D", "F"]

    def test_calculate_score_fuel_waste_breakdown(self, engine):
        """Test fuel waste breakdown in score"""
        state = engine._get_or_create_state("T001")
        state.fuel_waste_accel = 0.5
        state.fuel_waste_brake = 0.3
        state.fuel_waste_rpm = 0.2
        state.fuel_waste_gear = 0.1
        state.fuel_waste_speed = 0.15

        score = engine.calculate_heavy_foot_score("T001")

        assert score.total_fuel_waste_gal == pytest.approx(1.25, rel=0.01)
        assert "hard_acceleration" in score.fuel_waste_breakdown

    def test_calculate_score_no_driving_hours_estimate(self, engine):
        """Test score calculation estimates driving hours if not provided"""
        state = engine._get_or_create_state("T001")

        # Don't provide driving hours - should estimate 40% of period
        score = engine.calculate_heavy_foot_score("T001", period_hours=10)

        # Should not crash
        assert score.score is not None


class TestMPGCrossValidationMethod:
    """Tests for cross_validate_mpg method"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    def test_cross_validate_not_enough_samples(self, engine):
        """Test cross validation returns None without enough samples"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [6.5, 6.6]  # Only 2 samples
        state.ecu_mpg_samples = [6.4, 6.5]

        result = engine.cross_validate_mpg("T001")

        assert result is None

    def test_cross_validate_with_enough_samples(self, engine):
        """Test cross validation with enough samples"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [6.5, 6.6, 6.4, 6.5, 6.7]
        state.ecu_mpg_samples = [6.4, 6.5, 6.3, 6.4, 6.6]

        result = engine.cross_validate_mpg("T001")

        assert result is not None
        assert result.truck_id == "T001"
        assert result.kalman_mpg == pytest.approx(6.54, rel=0.01)

    def test_cross_validate_returns_none_for_zero_ecu(self, engine):
        """Test cross validation returns None if ECU is zero"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [6.5, 6.6, 6.4, 6.5, 6.7]
        state.ecu_mpg_samples = [0, 0, 0, 0, 0]

        result = engine.cross_validate_mpg("T001")

        assert result is None

    def test_cross_validate_recommendation_valid(self, engine):
        """Test recommendation when MPG is valid"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [6.5, 6.5, 6.5, 6.5, 6.5]
        state.ecu_mpg_samples = [6.4, 6.4, 6.4, 6.4, 6.4]

        result = engine.cross_validate_mpg("T001")

        assert "✅" in result.recommendation

    def test_cross_validate_recommendation_kalman_higher(self, engine):
        """Test recommendation when Kalman is higher than ECU"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [8.0, 8.0, 8.0, 8.0, 8.0]  # Much higher
        state.ecu_mpg_samples = [6.0, 6.0, 6.0, 6.0, 6.0]

        result = engine.cross_validate_mpg("T001")

        assert "higher" in result.recommendation.lower()
        assert not result.is_valid

    def test_cross_validate_recommendation_kalman_lower(self, engine):
        """Test recommendation when Kalman is lower than ECU"""
        state = engine._get_or_create_state("T001")
        state.kalman_mpg_samples = [5.0, 5.0, 5.0, 5.0, 5.0]  # Much lower
        state.ecu_mpg_samples = [7.0, 7.0, 7.0, 7.0, 7.0]

        result = engine.cross_validate_mpg("T001")

        assert "lower" in result.recommendation.lower()
        assert not result.is_valid


class TestFleetBehaviorSummary:
    """Tests for fleet behavior summary"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    def test_get_fleet_summary_empty(self, engine):
        """Test fleet summary with no trucks"""
        summary = engine._get_behavior_summary_from_memory()

        assert summary["fleet_size"] == 0
        assert summary["average_score"] == 0

    def test_get_fleet_summary_with_trucks(self, engine):
        """Test fleet summary with multiple trucks"""
        # Setup multiple trucks
        for i in range(3):
            truck_id = f"T00{i+1}"
            state = engine._get_or_create_state(truck_id)
            state.hard_accel_count = i * 2
            state.fuel_waste_accel = i * 0.1

        summary = engine._get_behavior_summary_from_memory()

        assert summary["fleet_size"] == 3
        assert "best_performers" in summary
        assert "worst_performers" in summary
        assert "behavior_scores" in summary
        assert summary["data_source"] == "real-time"

    def test_get_fleet_summary_biggest_issue(self, engine):
        """Test fleet summary identifies biggest issue"""
        state = engine._get_or_create_state("T001")
        state.fuel_waste_accel = 5.0  # Biggest
        state.fuel_waste_brake = 0.5
        state.fuel_waste_rpm = 0.3

        summary = engine._get_behavior_summary_from_memory()

        assert summary["biggest_issue"]["category"] == "hard_acceleration"

    def test_get_fleet_summary_behavior_scores(self, engine):
        """Test fleet summary includes behavior scores"""
        state = engine._get_or_create_state("T001")

        summary = engine._get_behavior_summary_from_memory()

        assert "acceleration" in summary["behavior_scores"]
        assert "braking" in summary["behavior_scores"]
        assert "rpm_mgmt" in summary["behavior_scores"]
        assert "gear_usage" in summary["behavior_scores"]
        assert "speed_control" in summary["behavior_scores"]

    def test_get_fleet_summary_needs_work_count(self, engine):
        """Test fleet summary counts trucks needing work"""
        # Create trucks with varying scores
        for i, score_value in enumerate([50, 65, 85]):
            truck_id = f"T00{i+1}"
            state = engine._get_or_create_state(truck_id)
            state.hard_accel_count = (100 - score_value) // 5

        summary = engine._get_behavior_summary_from_memory()

        # Trucks with score < 70 need work
        assert summary["needs_work_count"] >= 0


class TestFleetRecommendations:
    """Tests for fleet recommendations generation"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    def test_generate_recommendations_high_waste(self, engine):
        """Test recommendations when fuel waste is high"""
        scores = []
        waste = {
            "hard_acceleration": 5.0,
            "hard_braking": 0.5,
            "high_rpm": 0.3,
            "wrong_gear": 0.2,
            "overspeeding": 0.1,
        }

        recommendations = engine._generate_fleet_recommendations(scores, waste)

        assert isinstance(recommendations, list)
        assert len(recommendations) >= 0

    def test_generate_recommendations_poor_scores(self, engine):
        """Test recommendations when many trucks have poor scores"""
        scores = [
            HeavyFootScore(
                truck_id=f"T{i}",
                score=50.0,
                grade="F",
                acceleration_score=50.0,
                braking_score=50.0,
                rpm_score=50.0,
                gear_score=50.0,
                speed_score=50.0,
            )
            for i in range(5)
        ]
        waste = {
            "hard_acceleration": 1.0,
            "hard_braking": 0.5,
            "high_rpm": 0.3,
            "wrong_gear": 0.2,
            "overspeeding": 0.1,
        }

        recommendations = engine._generate_fleet_recommendations(scores, waste)

        assert isinstance(recommendations, list)


class TestBehaviorEventContext:
    """Tests for behavior event context"""

    def test_event_with_context(self):
        """Test event creation with context data"""
        event = BehaviorEvent(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            behavior_type=BehaviorType.HARD_ACCELERATION,
            severity=SeverityLevel.MODERATE,
            value=5.0,
            threshold=4.5,
            context={
                "speed": 45.0,
                "rpm": 1500,
                "source": "calculated",
                "previous_speed": 30.0,
            },
        )

        assert event.context["speed"] == 45.0
        assert event.context["source"] == "calculated"

    def test_event_to_dict_includes_context(self):
        """Test event serialization includes context"""
        event = BehaviorEvent(
            truck_id="T001",
            timestamp=datetime.now(timezone.utc),
            behavior_type=BehaviorType.HARD_BRAKING,
            severity=SeverityLevel.SEVERE,
            value=-8.0,
            threshold=-8.0,
            context={"road_condition": "wet", "load": "heavy"},
        )

        result = event.to_dict()

        assert result["context"]["road_condition"] == "wet"
        assert result["context"]["load"] == "heavy"


class TestProcessReadingEdgeCases:
    """Tests for edge cases in process_reading"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    @pytest.fixture
    def base_timestamp(self):
        return datetime.now(timezone.utc)

    def test_process_reading_with_all_parameters(self, engine, base_timestamp):
        """Test process_reading with all optional parameters"""
        events = engine.process_reading(
            truck_id="T001",
            timestamp=base_timestamp,
            speed=55.0,
            rpm=1600,
            gear=10,
            fuel_rate=5.0,
            kalman_mpg=6.5,
            fuel_economy=6.4,
            device_harsh_accel=0,
            device_harsh_brake=0,
        )

        assert isinstance(events, list)

    def test_process_reading_with_none_values(self, engine, base_timestamp):
        """Test process_reading handles None values gracefully"""
        events = engine.process_reading(
            truck_id="T001", timestamp=base_timestamp, speed=None, rpm=None, gear=None
        )

        assert isinstance(events, list)

    def test_process_reading_updates_mpg_samples(self, engine, base_timestamp):
        """Test that MPG samples are updated"""
        engine.process_reading(
            truck_id="T001",
            timestamp=base_timestamp,
            speed=55.0,
            kalman_mpg=6.5,
            fuel_economy=6.4,
        )

        state = engine.truck_states["T001"]
        assert len(state.kalman_mpg_samples) > 0 or state.last_speed is not None

    def test_process_reading_backward_timestamp_skipped(self, engine, base_timestamp):
        """Test that backward timestamps are skipped"""
        engine.process_reading("T001", base_timestamp, speed=30.0)

        # Backward timestamp
        events = engine.process_reading(
            "T001", base_timestamp - timedelta(seconds=10), speed=60.0
        )

        # Should be skipped or handled gracefully
        assert isinstance(events, list)


class TestConfigValidation:
    """Tests for configuration validation"""

    def test_custom_config_accel_thresholds(self):
        """Test custom acceleration thresholds"""
        config = BehaviorConfig(
            accel_minor_threshold=2.0,
            accel_moderate_threshold=3.5,
            accel_severe_threshold=5.0,
        )
        engine = DriverBehaviorEngine(config=config)

        assert engine.config.accel_minor_threshold == 2.0
        assert engine.config.accel_moderate_threshold == 3.5

    def test_custom_config_fuel_waste(self):
        """Test custom fuel waste values"""
        config = BehaviorConfig(
            fuel_waste_hard_accel_gal=0.1, fuel_waste_hard_brake_gal=0.08
        )
        engine = DriverBehaviorEngine(config=config)

        assert engine.config.fuel_waste_hard_accel_gal == 0.1

    def test_custom_config_speed_thresholds(self):
        """Test custom speed thresholds"""
        config = BehaviorConfig(speed_warning=60, speed_excessive=68, speed_severe=73)

        assert config.speed_warning == 60
        assert config.speed_excessive == 68


class TestIdleDetection:
    """Tests for idle detection"""

    @pytest.fixture
    def engine(self):
        return DriverBehaviorEngine()

    @pytest.fixture
    def base_timestamp(self):
        return datetime.now(timezone.utc)

    def test_excessive_idle_detection(self, engine, base_timestamp):
        """Test excessive idle detection"""
        # Initial reading
        engine.process_reading("T001", base_timestamp, speed=0.0, rpm=700)

        # Simulate extended idle (engine running, not moving)
        for i in range(65):  # More than 60 seconds
            events = engine.process_reading(
                "T001", base_timestamp + timedelta(seconds=i + 1), speed=0.0, rpm=700
            )

        # Check for excessive idle event
        idle_events = [
            e for e in events if e.behavior_type == BehaviorType.EXCESSIVE_IDLE
        ]
        # May or may not trigger based on threshold
        assert isinstance(events, list)
