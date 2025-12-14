"""
Unit Tests for Voltage Monitor v1.0.0

Tests validate:
- Voltage status classification
- Alert generation with correct priority
- Sensor correlation analysis
- Fleet batch processing
- Voltage quality factor calculation
- Alert cooldown management
"""

import pytest
import sys
from pathlib import Path
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from voltage_monitor import (
    VoltageStatus,
    VoltageAlert,
    VoltageThresholds,
    analyze_voltage,
    analyze_fleet_voltage,
    check_voltage_sensor_correlation,
    get_voltage_quality_factor,
    VoltageAlertManager,
)


# ============================================================================
# 1. VOLTAGE STATUS CLASSIFICATION
# ============================================================================


class TestVoltageClassification:
    """Test voltage status detection"""

    def test_battery_dead_engine_off(self):
        """Critical low voltage with engine off = dead battery"""
        alert = analyze_voltage(11.2, rpm=None, truck_id="TEST001")
        
        assert alert.status == VoltageStatus.CRITICAL_LOW
        assert alert.priority == "CRITICAL"
        assert "BATERÍA MUERTA" in alert.message
        assert alert.may_affect_sensors is True

    def test_battery_low_engine_off(self):
        """Low voltage with engine off = battery discharging"""
        alert = analyze_voltage(12.0, rpm=None, truck_id="TEST001")
        
        assert alert.status == VoltageStatus.LOW
        assert alert.priority == "HIGH"
        assert alert.is_engine_running is False

    def test_battery_normal_engine_off(self):
        """Normal voltage with engine off"""
        alert = analyze_voltage(12.6, rpm=None, truck_id="TEST001")
        
        assert alert.status == VoltageStatus.NORMAL
        assert alert.priority == "OK"
        assert alert.may_affect_sensors is False

    def test_alternator_fail_engine_running(self):
        """Critical low voltage with engine running = alternator failure"""
        alert = analyze_voltage(12.3, rpm=700, truck_id="TEST001")
        
        assert alert.status == VoltageStatus.CRITICAL_LOW
        assert alert.priority == "CRITICAL"
        assert "ALTERNADOR FALLANDO" in alert.message

    def test_charging_weak_engine_running(self):
        """Low charging voltage = weak alternator"""
        alert = analyze_voltage(13.0, rpm=650, truck_id="TEST001")
        
        assert alert.status == VoltageStatus.LOW
        assert alert.priority == "HIGH"
        assert "Carga débil" in alert.message

    def test_charging_normal_engine_running(self):
        """Normal charging voltage"""
        alert = analyze_voltage(14.2, rpm=700, truck_id="TEST001")
        
        assert alert.status == VoltageStatus.NORMAL
        assert alert.priority == "OK"
        assert alert.is_engine_running is True

    def test_overcharging_engine_running(self):
        """High voltage = overcharging"""
        alert = analyze_voltage(15.0, rpm=700, truck_id="TEST001")
        
        assert alert.status == VoltageStatus.HIGH
        assert alert.priority == "MEDIUM"

    def test_overvoltage_critical(self):
        """Critical high voltage = dangerous"""
        alert = analyze_voltage(15.8, rpm=750, truck_id="TEST001")
        
        assert alert.status == VoltageStatus.CRITICAL_HIGH
        assert alert.priority == "CRITICAL"
        assert "SOBREVOLTAJE" in alert.message
        assert alert.may_affect_sensors is True

    def test_null_voltage_returns_none(self):
        """No voltage data returns None"""
        alert = analyze_voltage(None, rpm=700, truck_id="TEST001")
        assert alert is None


# ============================================================================
# 2. SENSOR CORRELATION
# ============================================================================


class TestSensorCorrelation:
    """Test voltage-sensor correlation analysis"""

    def test_correlation_found(self):
        """Low voltage + bad sensor = correlation"""
        result = check_voltage_sensor_correlation(
            voltage=11.5,
            fuel_sensor_variance=3.0,
            fuel_drift_pct=8.0,
        )
        
        assert result["is_voltage_issue"] is True
        assert result["correlation_found"] is True
        assert "correlaciona" in result["explanation"]

    def test_voltage_issue_no_correlation(self):
        """Low voltage but sensors OK = no correlation"""
        result = check_voltage_sensor_correlation(
            voltage=11.5,
            fuel_sensor_variance=1.0,
            fuel_drift_pct=2.0,
        )
        
        assert result["is_voltage_issue"] is True
        assert result["correlation_found"] is False

    def test_sensor_issue_voltage_ok(self):
        """Sensors bad but voltage OK = no correlation"""
        result = check_voltage_sensor_correlation(
            voltage=14.0,
            fuel_sensor_variance=3.0,
            fuel_drift_pct=8.0,
        )
        
        assert result["is_voltage_issue"] is False
        assert result["correlation_found"] is False

    def test_all_normal(self):
        """Everything normal = no issues"""
        result = check_voltage_sensor_correlation(
            voltage=14.0,
            fuel_sensor_variance=1.0,
            fuel_drift_pct=2.0,
        )
        
        assert result["is_voltage_issue"] is False
        assert "normalmente" in result["explanation"]


# ============================================================================
# 3. QUALITY FACTOR
# ============================================================================


class TestVoltageQualityFactor:
    """Test voltage quality factor calculation"""

    def test_perfect_charging(self):
        """Perfect charging voltage = 1.0"""
        factor = get_voltage_quality_factor(14.2, is_engine_running=True)
        assert factor == 1.0

    def test_marginal_charging(self):
        """Marginal charging = reduced factor"""
        factor = get_voltage_quality_factor(12.8, is_engine_running=True)
        assert factor == 0.85

    def test_critical_charging(self):
        """Critical voltage = minimum factor"""
        factor = get_voltage_quality_factor(11.5, is_engine_running=True)
        assert factor == 0.5

    def test_battery_full(self):
        """Full battery = 1.0"""
        factor = get_voltage_quality_factor(12.6, is_engine_running=False)
        assert factor == 1.0

    def test_battery_low(self):
        """Low battery = reduced factor"""
        factor = get_voltage_quality_factor(11.8, is_engine_running=False)
        assert factor == 0.7

    def test_no_data(self):
        """No data = assume OK"""
        factor = get_voltage_quality_factor(None, is_engine_running=True)
        assert factor == 1.0


# ============================================================================
# 4. FLEET ANALYSIS
# ============================================================================


class TestFleetAnalysis:
    """Test fleet-wide voltage analysis"""

    def test_fleet_summary(self):
        """Fleet analysis produces correct summary"""
        fleet = [
            {"truck_id": "T001", "pwr_int": 14.2, "rpm": 700},
            {"truck_id": "T002", "pwr_int": 12.8, "rpm": 650},
            {"truck_id": "T003", "pwr_int": 11.2, "rpm": None},
            {"truck_id": "T004", "pwr_int": None, "rpm": None},
        ]
        
        result = analyze_fleet_voltage(fleet)
        
        assert result["summary"]["total_trucks"] == 4
        assert result["summary"]["critical"] == 1  # T003
        assert result["summary"]["warnings"] == 1  # T002
        assert result["summary"]["ok"] == 1  # T001
        assert result["summary"]["no_data"] == 1  # T004
        assert result["needs_attention"] is True

    def test_fleet_alerts_sorted_by_priority(self):
        """Alerts are sorted critical first"""
        fleet = [
            {"truck_id": "T001", "pwr_int": 14.2, "rpm": 700},  # OK
            {"truck_id": "T002", "pwr_int": 13.0, "rpm": 650},  # HIGH
            {"truck_id": "T003", "pwr_int": 11.2, "rpm": None},  # CRITICAL
        ]
        
        result = analyze_fleet_voltage(fleet)
        
        # Critical should be first
        assert result["alerts"][0]["priority"] == "CRITICAL"
        assert result["alerts"][1]["priority"] == "HIGH"


# ============================================================================
# 5. ALERT MANAGER
# ============================================================================


class TestAlertManager:
    """Test alert cooldown management"""

    def test_critical_always_passes(self):
        """Critical alerts always pass through"""
        mgr = VoltageAlertManager(cooldown_minutes=60)
        
        alert1 = VoltageAlert(
            truck_id="T001",
            voltage=11.0,
            status=VoltageStatus.CRITICAL_LOW,
            is_engine_running=False,
            priority="CRITICAL",
        )
        
        # First alert passes
        assert mgr.should_alert("T001", "CRITICAL") is True
        # Critical always passes even immediately after
        assert mgr.should_alert("T001", "CRITICAL") is True

    def test_non_critical_respects_cooldown(self):
        """Non-critical alerts respect cooldown"""
        mgr = VoltageAlertManager(cooldown_minutes=60)
        
        # First passes
        assert mgr.should_alert("T001", "HIGH") is True
        # Second blocked by cooldown
        assert mgr.should_alert("T001", "HIGH") is False

    def test_process_alert_filters_ok(self):
        """OK priority alerts are filtered out"""
        mgr = VoltageAlertManager()
        
        ok_alert = VoltageAlert(
            truck_id="T001",
            voltage=14.2,
            status=VoltageStatus.NORMAL,
            is_engine_running=True,
            priority="OK",
        )
        
        result = mgr.process_alert(ok_alert)
        assert result is None

    def test_process_alert_returns_valid(self):
        """Valid alerts pass through"""
        mgr = VoltageAlertManager()
        
        alert = VoltageAlert(
            truck_id="T001",
            voltage=11.0,
            status=VoltageStatus.CRITICAL_LOW,
            is_engine_running=False,
            priority="CRITICAL",
        )
        
        result = mgr.process_alert(alert)
        assert result is not None
        assert result.priority == "CRITICAL"


# ============================================================================
# 6. ALERT SERIALIZATION
# ============================================================================


class TestAlertSerialization:
    """Test VoltageAlert serialization"""

    def test_to_dict(self):
        """Alert converts to dictionary correctly"""
        alert = VoltageAlert(
            truck_id="TEST001",
            voltage=14.2,
            status=VoltageStatus.NORMAL,
            is_engine_running=True,
            priority="OK",
            message="Test message",
            timestamp=datetime(2025, 12, 13, 12, 0, 0),
        )
        
        d = alert.to_dict()
        
        assert d["truck_id"] == "TEST001"
        assert d["voltage"] == 14.2
        assert d["status"] == "NORMAL"
        assert d["is_engine_running"] is True
        assert d["priority"] == "OK"
        assert d["message"] == "Test message"
        assert "2025-12-13" in d["timestamp"]


# ============================================================================
# 7. EDGE CASES
# ============================================================================


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_exactly_at_threshold(self):
        """Test values exactly at thresholds"""
        thresholds = VoltageThresholds()
        
        # Exactly at battery_critical_low
        alert = analyze_voltage(thresholds.battery_critical_low, rpm=None, truck_id="T001")
        assert alert.status == VoltageStatus.LOW  # >= threshold, so not critical
        
    def test_rpm_zero_vs_none(self):
        """RPM=0 vs RPM=None should both mean engine off"""
        alert_none = analyze_voltage(12.6, rpm=None, truck_id="T001")
        alert_zero = analyze_voltage(12.6, rpm=0, truck_id="T001")
        
        assert alert_none.is_engine_running is False
        assert alert_zero.is_engine_running is False

    def test_rpm_low_idle(self):
        """RPM < 100 should be considered off"""
        alert = analyze_voltage(12.6, rpm=50, truck_id="T001")
        assert alert.is_engine_running is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
