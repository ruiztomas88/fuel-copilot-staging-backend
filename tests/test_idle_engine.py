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
