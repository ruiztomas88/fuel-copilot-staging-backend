"""
Tests for Idle Engine

Run with: pytest tests/test_idle_engine.py -v
"""

import pytest
from idle_engine import (
    IdleMethod,
    IdleMode,
    IdleConfig,
    calculate_idle_consumption,
    detect_idle_mode,
    calculate_idle_cost,
)


class TestCalculateIdleConsumption:
    """Test idle consumption calculation"""

    def test_not_idle_when_moving(self):
        """Should return 0 when truck is moving"""
        gph, method = calculate_idle_consumption(
            truck_status="MOVING",
            rpm=800,
            fuel_rate=3.0,
            current_fuel_L=400,
            previous_fuel_L=400,
            time_delta_hours=0.5,
        )
        assert gph == 0.0
        assert method == IdleMethod.NOT_IDLE

    def test_engine_off(self):
        """Should return 0 when engine is off"""
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=0,
            fuel_rate=None,
            current_fuel_L=400,
            previous_fuel_L=400,
            time_delta_hours=0.5,
        )
        assert gph == 0.0
        assert method == IdleMethod.ENGINE_OFF

    def test_sensor_fuel_rate_method(self):
        """Should use sensor when available and valid"""
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=700,
            fuel_rate=4.0,  # LPH
            current_fuel_L=400,
            previous_fuel_L=400,
            time_delta_hours=0.5,
        )
        assert method == IdleMethod.SENSOR_FUEL_RATE
        # 4 LPH / 3.78541 = ~1.06 GPH
        assert 1.0 <= gph <= 1.1

    def test_calculated_delta_method(self):
        """Should use delta when sensor unavailable"""
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=700,
            fuel_rate=None,
            current_fuel_L=398.0,
            previous_fuel_L=400.0,  # 2L consumed
            time_delta_hours=1.0,  # In 1 hour
        )
        assert method == IdleMethod.CALCULATED_DELTA
        # 2 LPH / 3.78541 = ~0.528 GPH
        assert gph == pytest.approx(0.528, rel=1e-2)

    def test_fallback_method(self):
        """Should use fallback/RPM-based estimate when both sensor methods fail"""
        config = IdleConfig(fallback_gph=0.8)
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=700,
            fuel_rate=None,
            current_fuel_L=400.0,
            previous_fuel_L=400.0,  # No delta
            time_delta_hours=0.05,  # Too short window
            config=config,
        )
        assert method == IdleMethod.FALLBACK_CONSENSUS
        # 🔧 FIX v3.9.4: Now uses RPM-based estimate (0.3 + 0.7*0.2 = 0.44 GPH for 700 RPM)
        assert 0.4 <= gph <= 0.5  # RPM-based estimate range

    def test_pure_fallback_without_rpm(self):
        """Should use pure fallback when RPM is not available"""
        config = IdleConfig(fallback_gph=0.8)
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=None,  # No RPM data
            fuel_rate=None,
            current_fuel_L=400.0,
            previous_fuel_L=400.0,
            time_delta_hours=0.05,
            config=config,
        )
        assert method == IdleMethod.FALLBACK_CONSENSUS
        assert gph == 0.8  # Pure fallback


class TestDetectIdleMode:
    """Test idle mode detection"""

    def test_engine_off_mode(self):
        """0 GPH should be ENGINE_OFF"""
        mode = detect_idle_mode(0.0)
        assert mode == IdleMode.ENGINE_OFF

    def test_normal_mode(self):
        """0.8 GPH should be NORMAL"""
        mode = detect_idle_mode(0.8)
        assert mode == IdleMode.NORMAL

    def test_reefer_mode(self):
        """1.8 GPH should be REEFER"""
        mode = detect_idle_mode(1.8)
        assert mode == IdleMode.REEFER

    def test_heavy_mode(self):
        """3.0 GPH should be HEAVY"""
        mode = detect_idle_mode(3.0)
        assert mode == IdleMode.HEAVY


class TestCalculateIdleCost:
    """Test idle cost calculation"""

    def test_8_hours_at_1_gph(self):
        """8 hours at 1 gph, $3.50/gal"""
        cost = calculate_idle_cost(1.0, 8.0, 3.50)
        assert cost == pytest.approx(28.0, rel=1e-3)

    def test_zero_idle(self):
        """Zero idle should cost nothing"""
        cost = calculate_idle_cost(0.0, 8.0, 3.50)
        assert cost == 0.0


class TestTemperatureFactor:
    """Test temperature adjustment factor for idle consumption"""

    def test_no_temperature_data(self):
        """Should return 1.0 when no temperature data"""
        from idle_engine import get_temperature_factor

        factor, reason = get_temperature_factor(None)
        assert factor == 1.0
        assert reason == "NO_TEMP_DATA"

    def test_extreme_cold(self):
        """Should return 1.5 for extreme cold (<32F)"""
        from idle_engine import get_temperature_factor

        factor, reason = get_temperature_factor(20.0)
        assert factor == 1.5
        assert reason == "EXTREME_COLD"

    def test_cold(self):
        """Should return 1.25 for cold (32-60F)"""
        from idle_engine import get_temperature_factor

        factor, reason = get_temperature_factor(50.0)
        assert factor == 1.25
        assert reason == "COLD"

    def test_comfort_zone(self):
        """Should return 1.0 for comfort zone (60-75F)"""
        from idle_engine import get_temperature_factor

        factor, reason = get_temperature_factor(70.0)
        assert factor == 1.0
        assert reason == "COMFORT_ZONE"

    def test_hot(self):
        """Should return 1.3 for hot (75-95F)"""
        from idle_engine import get_temperature_factor

        factor, reason = get_temperature_factor(85.0)
        assert factor == 1.3
        assert reason == "HOT"

    def test_extreme_hot(self):
        """Should return 1.5 for extreme hot (>95F)"""
        from idle_engine import get_temperature_factor

        factor, reason = get_temperature_factor(100.0)
        assert factor == 1.5
        assert reason == "EXTREME_HOT"


class TestIdleStatus:
    """Test idle status generation"""

    def test_not_idle_status(self):
        """Should return NOT_IDLE status"""
        from idle_engine import get_idle_status

        status = get_idle_status(0.0, IdleMethod.NOT_IDLE, IdleMode.ENGINE_OFF)
        assert status["status"] == "NOT_IDLE"
        assert status["message"] == "Truck is moving"

    def test_engine_off_status(self):
        """Should return ENGINE_OFF status"""
        from idle_engine import get_idle_status

        status = get_idle_status(0.0, IdleMethod.ENGINE_OFF, IdleMode.ENGINE_OFF)
        assert status["status"] == "ENGINE_OFF"
        assert status["message"] == "Engine is off"

    def test_normal_idle_status(self):
        """Should return NORMAL idle status"""
        from idle_engine import get_idle_status

        status = get_idle_status(0.8, IdleMethod.SENSOR_FUEL_RATE, IdleMode.NORMAL)
        assert status["status"] == "NORMAL"
        assert "0.80 gph" in status["message"]

    def test_reefer_idle_status(self):
        """Should return REEFER idle status"""
        from idle_engine import get_idle_status

        status = get_idle_status(1.8, IdleMethod.SENSOR_FUEL_RATE, IdleMode.REEFER)
        assert status["status"] == "REEFER"
        assert "1.80 gph" in status["message"]

    def test_heavy_idle_status(self):
        """Should return HEAVY idle status"""
        from idle_engine import get_idle_status

        status = get_idle_status(3.0, IdleMethod.CALCULATED_DELTA, IdleMode.HEAVY)
        assert status["status"] == "HEAVY"
        assert "investigate" in status["message"].lower()

    def test_status_with_temperature(self):
        """Should include temperature info when provided"""
        from idle_engine import get_idle_status

        status = get_idle_status(
            0.8, IdleMethod.FALLBACK_CONSENSUS, IdleMode.NORMAL, temperature_f=20.0
        )
        assert "temperature_f" in status
        assert status["temperature_f"] == 20.0
        assert status["temperature_factor"] == 1.5
        assert status["temperature_reason"] == "EXTREME_COLD"


class TestHvacImpact:
    """Test HVAC impact estimation"""

    def test_hvac_impact_no_temp(self):
        """Should return zero impact with no temperature"""
        from idle_engine import estimate_hvac_impact

        result = estimate_hvac_impact(None, 8.0)
        assert result["hvac_impact_gallons"] == 0.0
        assert result["climate_zone"] == "UNKNOWN"

    def test_hvac_impact_extreme_cold(self):
        """Should calculate 50% increase in extreme cold"""
        from idle_engine import estimate_hvac_impact

        result = estimate_hvac_impact(20.0, 8.0, base_gph=0.8)
        assert result["base_gallons"] == 6.4
        assert result["adjusted_gallons"] == 9.6
        assert result["hvac_impact_gallons"] == 3.2
        assert result["hvac_impact_pct"] == 50.0
        assert result["climate_zone"] == "EXTREME_COLD"

    def test_hvac_impact_comfort_zone(self):
        """Should calculate zero impact in comfort zone"""
        from idle_engine import estimate_hvac_impact

        result = estimate_hvac_impact(70.0, 8.0, base_gph=0.8)
        assert result["hvac_impact_gallons"] == 0.0
        assert result["hvac_impact_pct"] == 0.0
        assert result["climate_zone"] == "COMFORT_ZONE"


class TestIdleValidation:
    """Test idle calculation validation"""

    def test_validation_no_ecu_data(self):
        """Should return LOW confidence without ECU data"""
        from idle_engine import validate_idle_calculation

        result = validate_idle_calculation("T101", 8.0, None, None)
        assert result.confidence == "LOW"
        assert result.ecu_idle_hours is None

    def test_validation_high_confidence(self):
        """Should return HIGH confidence when calculation matches expected"""
        from idle_engine import validate_idle_calculation

        # Using idle_ratio of 20% (normal range)
        # ecu_idle=200, ecu_engine=1000 -> ratio=20%
        # expected_daily_idle = 24 * 0.4 * 20/100 = 1.92h
        result = validate_idle_calculation(
            "T101", 1.92, 200, 1000, time_period_hours=24.0
        )
        assert result.confidence == "HIGH"
        assert result.deviation_pct is not None

    def test_validation_needs_investigation(self):
        """Should flag for investigation when deviation > 15%"""
        from idle_engine import validate_idle_calculation

        result = validate_idle_calculation("T101", 8.0, 12.0, 100.0)
        assert result.needs_investigation
        assert abs(result.deviation_pct) > 15.0


class TestEcuIdleCounter:
    """Test ECU idle counter method"""

    def test_ecu_idle_counter_valid(self):
        """Should use ECU idle counter when available"""
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=700,
            fuel_rate=None,
            current_fuel_L=400,
            previous_fuel_L=400,
            time_delta_hours=0.5,
            total_idle_fuel=10.5,  # Current ECU counter
            previous_total_idle_fuel=10.0,  # Previous ECU counter
        )
        assert method == IdleMethod.ECU_IDLE_COUNTER
        # (10.5 - 10.0) / 0.5 = 1.0 GPH
        assert gph == pytest.approx(1.0, rel=0.01)

    def test_ecu_idle_counter_negative_delta(self):
        """Should skip ECU counter if it went backwards"""
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=None,
            fuel_rate=None,
            current_fuel_L=400,
            previous_fuel_L=400,
            time_delta_hours=0.5,
            total_idle_fuel=10.0,
            previous_total_idle_fuel=10.5,  # Counter went backwards
        )
        # Should fall through to fallback
        assert method == IdleMethod.FALLBACK_CONSENSUS

    def test_ecu_idle_counter_too_large(self):
        """Should skip ECU counter if delta is too large"""
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=None,
            fuel_rate=None,
            current_fuel_L=400,
            previous_fuel_L=400,
            time_delta_hours=0.5,
            total_idle_fuel=20.0,
            previous_total_idle_fuel=10.0,  # 10 gallon delta - too large
        )
        # Should fall through to fallback
        assert method == IdleMethod.FALLBACK_CONSENSUS


class TestRpmBasedEstimate:
    """Test RPM-based idle estimation"""

    def test_rpm_600(self):
        """600 RPM should estimate ~0.42 GPH"""
        config = IdleConfig(fallback_gph=0.8)
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=600,
            fuel_rate=None,
            current_fuel_L=400.0,
            previous_fuel_L=400.0,
            time_delta_hours=0.05,  # Too short for delta
            config=config,
        )
        assert method == IdleMethod.FALLBACK_CONSENSUS
        # 0.3 + 0.6 * 0.2 = 0.42 GPH
        assert 0.4 <= gph <= 0.45

    def test_rpm_1000(self):
        """1000 RPM should estimate ~0.50 GPH"""
        config = IdleConfig(fallback_gph=0.8)
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=1000,
            fuel_rate=None,
            current_fuel_L=400.0,
            previous_fuel_L=400.0,
            time_delta_hours=0.05,
            config=config,
        )
        assert method == IdleMethod.FALLBACK_CONSENSUS
        # 0.3 + 1.0 * 0.2 = 0.50 GPH
        assert 0.48 <= gph <= 0.52

    def test_rpm_with_temperature(self):
        """RPM estimate should be adjusted for temperature"""
        config = IdleConfig(fallback_gph=0.8)
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=600,
            fuel_rate=None,
            current_fuel_L=400.0,
            previous_fuel_L=400.0,
            time_delta_hours=0.05,
            config=config,
            temperature_f=20.0,  # Extreme cold = 1.5x
        )
        # 0.42 * 1.5 = 0.63 GPH
        assert 0.6 <= gph <= 0.66


class TestSensorFuelRateEma:
    """Test EMA smoothing on sensor fuel rate"""

    def test_ema_smoothing(self):
        """Should apply EMA smoothing when previous value exists"""
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=700,
            fuel_rate=4.0,  # LPH (raw ~1.06 GPH)
            current_fuel_L=400,
            previous_fuel_L=400,
            time_delta_hours=0.5,
            previous_idle_gph=0.8,  # Previous value
        )
        assert method == IdleMethod.SENSOR_FUEL_RATE
        # EMA: 0.3 * 1.06 + 0.7 * 0.8 = 0.318 + 0.56 = 0.878
        assert 0.85 <= gph <= 0.92

    def test_sensor_out_of_range_low(self):
        """Should skip sensor if value too low"""
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=700,
            fuel_rate=0.1,  # Too low
            current_fuel_L=400,
            previous_fuel_L=400,
            time_delta_hours=0.5,
        )
        # Should fall through to RPM-based estimate
        assert method == IdleMethod.FALLBACK_CONSENSUS

    def test_sensor_out_of_range_high(self):
        """Should skip sensor if value too high"""
        gph, method = calculate_idle_consumption(
            truck_status="STOPPED",
            rpm=700,
            fuel_rate=50.0,  # Way too high - out of range
            current_fuel_L=400,
            previous_fuel_L=400,
            time_delta_hours=0.5,
        )
        # Should fall through to RPM-based estimate
        assert method == IdleMethod.FALLBACK_CONSENSUS
