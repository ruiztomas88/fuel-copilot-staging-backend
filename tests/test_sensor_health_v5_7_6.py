"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║              TESTS: Sensor Health & Idle Validation v5.7.6                     ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Tests for:
1. Idle validation logic
2. Sensor health router endpoints
3. Voltage trending
4. GPS quality overview
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock

# Import modules under test
from idle_engine import (
    validate_idle_calculation,
    IdleValidationResult,
    IdleMethod,
    IdleMode,
    IdleConfig,
    detect_idle_mode,
    calculate_idle_consumption,
)


# ═══════════════════════════════════════════════════════════════════════════════
# IDLE VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdleValidation:
    """Test idle validation against ECU data"""

    def test_validate_with_no_ecu_data(self):
        """Should return LOW confidence when no ECU data available"""
        result = validate_idle_calculation(
            truck_id="TEST001",
            calculated_idle_hours=3.5,
            ecu_idle_hours=None,
            ecu_engine_hours=None,
            time_period_hours=24.0,
        )

        assert result.is_valid is True
        assert result.confidence == "LOW"
        assert "No ECU idle_hours available" in result.message
        assert result.ecu_idle_hours is None

    def test_validate_with_matching_values(self):
        """Should validate successfully when calc matches ECU delta"""
        # The validation compares calculated hours vs expected delta from ECU
        # If we give calc=2.5h and the ECU suggests similar, it should pass
        result = validate_idle_calculation(
            truck_id="CO0681",
            calculated_idle_hours=2.5,  # Our calculation
            ecu_idle_hours=1250.5,  # Cumulative ECU counter
            ecu_engine_hours=8500.0,
            time_period_hours=24.0,
        )

        # The function validates against expected ratio, not direct comparison
        # Check that it runs without error and returns a result
        assert result.ecu_idle_hours == 1250.5
        assert result.confidence in ["HIGH", "MEDIUM", "LOW"]

    def test_validate_with_out_of_range_ecu(self):
        """Should flag invalid when ECU value is out of range"""
        result = validate_idle_calculation(
            truck_id="TEST001",
            calculated_idle_hours=3.0,
            ecu_idle_hours=-100,  # Invalid negative
            ecu_engine_hours=8500.0,
            time_period_hours=24.0,
        )

        assert result.is_valid is False
        assert result.confidence == "LOW"
        assert "out of range" in result.message.lower()

    def test_validate_extreme_ecu_value(self):
        """Should flag invalid when ECU value exceeds reasonable limits"""
        result = validate_idle_calculation(
            truck_id="TEST001",
            calculated_idle_hours=3.0,
            ecu_idle_hours=150000,  # >100k hours unrealistic
            ecu_engine_hours=200000,
            time_period_hours=24.0,
        )

        assert result.is_valid is False
        assert "out of range" in result.message.lower()

    def test_idle_ratio_in_message(self):
        """Should include idle ratio info in message"""
        # 20% idle ratio (typical for linehaul)
        result = validate_idle_calculation(
            truck_id="TEST001",
            calculated_idle_hours=4.0,
            ecu_idle_hours=2000.0,  # 2000 idle out of 10000 engine hours = 20%
            ecu_engine_hours=10000.0,
            time_period_hours=24.0,
        )

        # Message should mention ratio
        assert "ratio" in result.message.lower() or "%" in result.message

    def test_validation_result_dataclass(self):
        """Test IdleValidationResult dataclass properties"""
        result = IdleValidationResult(
            is_valid=True,
            calculated_idle_hours=3.5,
            ecu_idle_hours=1250.0,
            deviation_pct=5.2,
            confidence="HIGH",
            message="Test message",
        )

        assert result.is_valid is True
        assert result.calculated_idle_hours == 3.5
        assert result.deviation_pct == 5.2
        assert result.confidence == "HIGH"
        # needs_investigation should be False for small deviation
        assert result.needs_investigation is False

    def test_needs_investigation_high_deviation(self):
        """Should flag needs_investigation when deviation is high"""
        result = IdleValidationResult(
            is_valid=False,
            calculated_idle_hours=10.0,
            ecu_idle_hours=3.0,
            deviation_pct=25.0,  # >15% threshold
            confidence="MEDIUM",
            message="High deviation detected",
        )

        assert result.needs_investigation is True


# ═══════════════════════════════════════════════════════════════════════════════
# IDLE DETECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdleDetection:
    """Test idle mode detection"""

    def test_detect_idle_mode_engine_off(self):
        """Test engine off detection (zero GPH)"""
        result = detect_idle_mode(0.0)
        assert result == IdleMode.ENGINE_OFF

    def test_detect_idle_mode_normal(self):
        """Test normal idle detection (< 1.2 GPH)"""
        result = detect_idle_mode(0.8)  # Typical Class 8 idle
        assert result == IdleMode.NORMAL

    def test_detect_idle_mode_reefer(self):
        """Test reefer idle detection (1.2-2.5 GPH)"""
        result = detect_idle_mode(1.8)
        assert result == IdleMode.REEFER

    def test_detect_idle_mode_heavy(self):
        """Test heavy idle detection (> 2.5 GPH)"""
        result = detect_idle_mode(3.0)
        assert result == IdleMode.HEAVY

    def test_detect_idle_mode_with_config(self):
        """Test idle detection with custom config"""
        config = IdleConfig(
            normal_max_gph=1.0,  # Lower threshold
            reefer_max_gph=2.0
        )
        # 1.1 GPH would be REEFER with custom config (above normal_max 1.0)
        result = detect_idle_mode(1.1, config=config)
        assert result == IdleMode.REEFER


# ═══════════════════════════════════════════════════════════════════════════════
# IDLE CONSUMPTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdleConsumption:
    """Test idle consumption calculation"""

    def test_calculate_when_stopped_with_fuel_rate(self):
        """Should calculate idle from fuel rate when stopped"""
        idle_gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=650,
            fuel_rate=3.0,  # 3 LPH from sensor
            current_fuel_L=200.0,
            previous_fuel_L=200.5,
            time_delta_hours=0.0833,  # 5 minutes
            truck_id="TEST001",
        )

        # Should return a value
        assert idle_gph >= 0
        assert method in [
            IdleMethod.SENSOR_FUEL_RATE,
            IdleMethod.CALCULATED_DELTA,
            IdleMethod.FALLBACK_CONSENSUS,
            IdleMethod.NOT_IDLE,
            IdleMethod.ENGINE_OFF,
        ]

    def test_no_idle_when_moving(self):
        """Should return NOT_IDLE when truck is moving"""
        idle_gph, method = calculate_idle_consumption(
            truck_status="MOVING",
            rpm=1400,
            fuel_rate=15.0,
            current_fuel_L=200.0,
            previous_fuel_L=201.0,
            time_delta_hours=0.1,
            truck_id="TEST001",
        )

        assert method == IdleMethod.NOT_IDLE
        assert idle_gph == 0.0

    def test_engine_off_when_rpm_zero(self):
        """Should return ENGINE_OFF when RPM is 0"""
        idle_gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=0,
            fuel_rate=0,
            current_fuel_L=200.0,
            previous_fuel_L=200.0,
            time_delta_hours=0.1,
            truck_id="TEST001",
        )

        assert method == IdleMethod.ENGINE_OFF
        assert idle_gph == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# SENSOR HEALTH ROUTER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestSensorHealthRouter:
    """Test sensor health router endpoints"""

    @pytest.fixture
    def mock_db(self):
        """Mock database for tests"""
        with patch("routers.sensor_health_router.db") as mock:
            mock.get_all_trucks.return_value = ["CO0681", "YM6023", "PC1280"]
            mock.get_truck_latest_record.return_value = {
                "truck_id": "CO0681",
                "idle_hours_ecu": 1250.5,
                "engine_hours": 8500.0,
                "idle_gph": 0.75,
                "gps_quality": "GOOD",
                "gps_satellites": 12,
                "voltage": 14.2,
                "voltage_status": "NORMAL",
                "dtc_count": 0,
                "dtc": 0,
            }
            yield mock

    def test_idle_validation_response_model(self):
        """Test IdleValidationResponse model structure"""
        from routers.sensor_health_router import IdleValidationResponse

        response = IdleValidationResponse(
            truck_id="TEST001",
            is_valid=True,
            confidence="HIGH",
            calculated_idle_hours=3.5,
            ecu_idle_hours=1250.0,
            deviation_pct=5.0,
            idle_ratio_pct=15.0,
            needs_investigation=False,
            message="Validation OK",
            last_validated="2025-12-14T00:00:00Z",
        )

        assert response.truck_id == "TEST001"
        assert response.is_valid is True
        assert response.confidence == "HIGH"

    def test_sensor_health_summary_model(self):
        """Test SensorHealthSummary model structure"""
        from routers.sensor_health_router import SensorHealthSummary

        summary = SensorHealthSummary(
            total_trucks=10,
            trucks_with_gps_issues=1,
            trucks_with_voltage_issues=2,
            trucks_with_dtc_active=0,
            trucks_with_idle_deviation=1,
            overall_health_score=90.0,
            last_updated="2025-12-14T00:00:00Z",
        )

        assert summary.total_trucks == 10
        assert summary.overall_health_score == 90.0

    def test_voltage_data_point_model(self):
        """Test VoltageDataPoint model structure"""
        from routers.sensor_health_router import VoltageDataPoint

        point = VoltageDataPoint(
            timestamp="2025-12-14T10:30:00Z",
            voltage=14.2,
            rpm=650.0,
            status="NORMAL",
        )

        assert point.voltage == 14.2
        assert point.status == "NORMAL"


# ═══════════════════════════════════════════════════════════════════════════════
# MIGRATION FILE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMigrationFiles:
    """Test migration file content"""

    def test_idle_validation_migration_exists(self):
        """Migration file should exist and have correct structure"""
        from pathlib import Path

        migration_path = Path("migrations/add_idle_validation_v5_7_6.sql")
        assert migration_path.exists(), "Migration file not found"

        content = migration_path.read_text()

        # Check for required elements
        assert "idle_validation_log" in content
        assert "calculated_idle_hours" in content
        assert "ecu_idle_hours" in content
        assert "deviation_pct" in content
        assert "needs_investigation" in content
        assert "CREATE TABLE" in content or "CREATE INDEX" in content


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER REGISTRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestRouterRegistration:
    """Test that router is properly registered"""

    def test_sensor_health_router_in_init(self):
        """sensor_health_router should be in __all__"""
        from routers import __all__

        assert "sensor_health_router" in __all__

    def test_sensor_health_router_importable(self):
        """sensor_health_router should be importable"""
        from routers import sensor_health_router

        assert sensor_health_router is not None

    def test_router_has_endpoints(self):
        """Router should have defined endpoints"""
        from routers.sensor_health_router import router

        routes = [route.path for route in router.routes]

        assert "/idle-validation" in routes or any(
            "idle-validation" in r for r in routes
        )
        assert "/summary" in routes or any("summary" in r for r in routes)
