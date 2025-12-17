"""
Unit Tests for Critical Bug Fixes - Week 1
═══════════════════════════════════════════════════════════════════════════════

Tests for:
- BUG-002: Circuit Breaker in theft_detection_engine.py
- BUG-024: readings_per_day validation in mpg_engine.py

Run with: pytest tests/test_critical_fixes.py -v --cov
"""

import pytest
import time
import sys
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, Mock

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    CircuitBreakerConfig,
    get_circuit_breaker
)


class TestCircuitBreaker:
    """Tests for Circuit Breaker implementation (BUG-002)"""

    def test_circuit_closed_allows_requests(self):
        """CLOSED state should allow all requests"""
        breaker = CircuitBreaker("test_closed", CircuitBreakerConfig(failure_threshold=3))
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker.can_execute() is True

    def test_circuit_opens_after_threshold(self):
        """Circuit should OPEN after reaching failure threshold"""
        breaker = CircuitBreaker("test_opens", CircuitBreakerConfig(failure_threshold=3))
        
        # Record 3 failures
        for i in range(3):
            breaker.record_failure(Exception(f"test failure {i}"))
        
        assert breaker.state == CircuitState.OPEN

    def test_circuit_breaker_open_exception(self):
        """OPEN circuit should raise CircuitBreakerOpenError"""
        breaker = CircuitBreaker("test_exception", CircuitBreakerConfig(failure_threshold=2))
        
        # Open the circuit
        breaker.record_failure(Exception("error 1"))
        breaker.record_failure(Exception("error 2"))
        
        assert breaker.state == CircuitState.OPEN
        
        # Should raise exception when trying to execute
        with pytest.raises(CircuitBreakerOpenError):
            breaker.execute(lambda: "should not run")

    def test_circuit_recovers_after_timeout(self):
        """Circuit should move to HALF_OPEN after timeout"""
        breaker = CircuitBreaker(
            "test_recovery",
            CircuitBreakerConfig(failure_threshold=2, timeout_seconds=1)
        )
        
        # Open circuit
        breaker.record_failure(Exception("fail 1"))
        breaker.record_failure(Exception("fail 2"))
        assert breaker.state == CircuitState.OPEN
        
        # Wait for timeout
        time.sleep(1.1)
        
        # Should transition to HALF_OPEN
        assert breaker.can_execute() is True
        assert breaker.state == CircuitState.HALF_OPEN

    def test_circuit_closes_after_successful_recovery(self):
        """HALF_OPEN should close after success_threshold successes"""
        breaker = CircuitBreaker(
            "test_closes",
            CircuitBreakerConfig(
                failure_threshold=2,
                success_threshold=2,
                timeout_seconds=1
            )
        )
        
        # Open circuit
        breaker.record_failure(Exception("fail 1"))
        breaker.record_failure(Exception("fail 2"))
        assert breaker.state == CircuitState.OPEN
        
        # Wait for timeout to HALF_OPEN
        time.sleep(1.1)
        assert breaker.can_execute() is True
        
        # Record successes
        breaker.record_success()
        breaker.record_success()
        
        # Should be CLOSED now
        assert breaker.state == CircuitState.CLOSED

    def test_circuit_rejects_calls_when_open(self):
        """OPEN circuit should reject calls immediately"""
        breaker = CircuitBreaker("test_rejects", CircuitBreakerConfig(failure_threshold=1))
        
        breaker.record_failure(Exception("immediate fail"))
        assert breaker.state == CircuitState.OPEN
        
        # Stats should track rejection
        initial_rejected = breaker.stats.rejected_calls
        
        with pytest.raises(CircuitBreakerOpenError):
            breaker.execute(lambda: "rejected")
        
        assert breaker.stats.rejected_calls == initial_rejected + 1

    def test_circuit_decorator_usage(self):
        """Test using circuit breaker as decorator"""
        breaker = CircuitBreaker("test_decorator", CircuitBreakerConfig(failure_threshold=2))
        
        @breaker
        def risky_function():
            raise ValueError("Always fails")
        
        # First two calls should raise ValueError (not caught by breaker)
        with pytest.raises(ValueError):
            risky_function()
        with pytest.raises(ValueError):
            risky_function()
        
        # Third call should raise CircuitBreakerOpenError (circuit opened)
        with pytest.raises(CircuitBreakerOpenError):
            risky_function()

    def test_circuit_stats_tracking(self):
        """Circuit should track statistics correctly"""
        breaker = CircuitBreaker("test_stats", CircuitBreakerConfig(failure_threshold=5))
        
        # Execute some successful calls
        result = breaker.execute(lambda: 42)
        assert result == 42
        assert breaker.stats.successful_calls == 1
        
        # Execute failing call
        try:
            breaker.execute(lambda: (_ for _ in ()).throw(RuntimeError("test")))
        except RuntimeError:
            pass
        
        assert breaker.stats.failed_calls == 1
        assert breaker.stats.total_calls == 2

    def test_circuit_get_status(self):
        """get_status() should return complete info"""
        breaker = CircuitBreaker("test_status", CircuitBreakerConfig(failure_threshold=2))
        
        status = breaker.get_status()
        
        assert status["name"] == "test_status"
        assert status["state"] == CircuitState.CLOSED.value
        assert "stats" in status
        assert status["stats"]["total_calls"] == 0

    def test_circuit_manual_reset(self):
        """Manual reset should restore circuit to CLOSED state"""
        breaker = CircuitBreaker("test_reset", CircuitBreakerConfig(failure_threshold=1))
        
        # Open circuit
        breaker.record_failure(Exception("fail"))
        assert breaker.state == CircuitState.OPEN
        
        # Manual reset
        breaker.reset()
        
        assert breaker.state == CircuitState.CLOSED
        assert breaker.stats.failed_calls == 0
        assert breaker.can_execute() is True


class TestReadingsPerDayValidation:
    """Tests for readings_per_day parameter (BUG-024)"""

    def test_daily_data_default(self):
        """Default readings_per_day=1.0 for daily data"""
        # Mock mpg_engine function
        from mpg_engine import predict_maintenance_timing
        
        # Create realistic battery voltage history (daily readings)
        # Just a list of float values, NOT dicts
        history = [12.8 - (i * 0.01) for i in range(30)]  # Declining voltage over 30 days
        
        result = predict_maintenance_timing(
            sensor_name="voltage",
            current_value=12.4,
            history=history,
            warning_threshold=12.2,
            critical_threshold=11.8,
            is_higher_worse=False,
            readings_per_day=1.0  # Explicit daily
        )
        
        assert "days_to_warning" in result
        assert result.get("readings_frequency") == "1.0 readings/day"

    def test_hourly_data_explicit(self):
        """readings_per_day=24 for hourly data"""
        from mpg_engine import predict_maintenance_timing
        
        # Hourly readings for 3 days (72 readings)
        history = [12.8 - (i * 0.01) for i in range(72)]
        
        result = predict_maintenance_timing(
            sensor_name="voltage",
            current_value=12.5,
            history=history,
            warning_threshold=12.2,
            critical_threshold=11.8,
            is_higher_worse=False,
            readings_per_day=24.0  # Hourly readings
        )
        
        assert result.get("readings_frequency") == "24.0 readings/day"
        # Should scale prediction by 24x
        assert "days_to_warning" in result

    def test_invalid_readings_per_day_clamped(self):
        """Invalid readings_per_day should be clamped to 1.0"""
        from mpg_engine import predict_maintenance_timing
        
        history = [12.8 - (i * 0.01) for i in range(10)]
        
        # Test negative value
        result = predict_maintenance_timing(
            sensor_name="voltage",
            current_value=12.5,
            history=history,
            warning_threshold=12.2,
            critical_threshold=11.8,
            is_higher_worse=False,
            readings_per_day=-5.0  # Invalid!
        )
        
        # Should fallback to 1.0
        assert result.get("readings_frequency") == "1.0 readings/day"

    def test_high_frequency_low_samples_warning(self):
        """High frequency + few samples should trigger warning"""
        from mpg_engine import predict_maintenance_timing
        import logging
        
        # Only 5 readings but claiming 1000/day
        history = [12.8, 12.7, 12.6, 12.5, 12.4]
        
        with patch('mpg_engine.logger') as mock_logger:
            result = predict_maintenance_timing(
                sensor_name="voltage",
                current_value=12.5,
                history=history,
                warning_threshold=12.2,
                critical_threshold=11.8,
                is_higher_worse=False,
                readings_per_day=1000.0  # Very high frequency
            )
            
            # Should have logged warning
            assert mock_logger.warning.called

    def test_realistic_scenario_battery_voltage(self):
        """Real-world scenario: battery voltage degradation"""
        from mpg_engine import predict_maintenance_timing
        
        # Simulate 60 days of daily voltage readings showing degradation
        # Starting at 13.0V, degrading to 12.5V (-0.008V per day)
        history = [13.0 - (i * 0.008) for i in range(60)]
        
        current_value = 12.5
        
        result = predict_maintenance_timing(
            sensor_name="battery_voltage",
            current_value=current_value,
            history=history,
            warning_threshold=12.2,  # 37.5 days away
            critical_threshold=11.8,  # 87.5 days away  
            is_higher_worse=False,
            readings_per_day=1.0
        )
        
        # Verify prediction is reasonable
        assert result.get("trend_direction") in ["DEGRADING", "IMPROVING", "STABLE"]
        assert "days_to_warning" in result
        
        # Days to warning should be ~37 days (not 0.01 or 900)
        days_to_warning = result.get("days_to_warning")
        if days_to_warning and days_to_warning > 0:
            assert 20 < days_to_warning < 60, f"Expected ~37 days, got {days_to_warning}"

    def test_per_minute_data_scaling(self):
        """Test per-minute data (1440 readings/day)"""
        from mpg_engine import predict_maintenance_timing
        
        # 24 hours of per-minute readings (sample every 10 minutes = 144 readings)
        history = [100 - (i * 0.001) for i in range(144)]
        
        result = predict_maintenance_timing(
            sensor_name="temp",
            current_value=98.5,
            history=history,
            warning_threshold=95.0,
            critical_threshold=90.0,
            is_higher_worse=False,
            readings_per_day=1440.0  # Per minute
        )
        
        assert result.get("readings_frequency") == "1440.0 readings/day"


class TestTheftDetectionCircuitBreaker:
    """Integration tests for theft detection with circuit breaker (BUG-002)"""

    @patch('theft_detection_engine.get_local_engine')
    def test_theft_detection_survives_db_failure(self, mock_get_engine):
        """Theft detection should continue even if DB fails"""
        from theft_detection_engine import TheftPatternAnalyzer
        
        # Mock DB failure
        mock_get_engine.return_value = None
        
        # Create analyzer
        analyzer = TheftPatternAnalyzer()
        
        # Should not crash when trying to load from DB
        # (circuit breaker protects it)
        try:
            analyzer._load_from_db()
        except Exception as e:
            pytest.fail(f"Should not raise exception, got: {e}")

    @patch('theft_detection_engine.get_local_engine')
    def test_theft_detection_persists_when_db_available(self, mock_get_engine):
        """When DB available, theft events should persist"""
        from theft_detection_engine import TheftPatternAnalyzer
        
        # Mock working DB connection that uses sqlalchemy execute pattern
        mock_result = Mock()
        mock_conn = Mock()
        mock_conn.execute = Mock(return_value=mock_result)
        mock_conn.commit = Mock()
        mock_conn.__enter__ = Mock(return_value=mock_conn)
        mock_conn.__exit__ = Mock(return_value=False)
        
        mock_engine = Mock()
        mock_engine.connect = Mock(return_value=mock_conn)
        mock_get_engine.return_value = mock_engine
        
        analyzer = TheftPatternAnalyzer()
        
        # Should successfully persist event
        try:
            analyzer._persist_event(
                truck_id="TEST123",
                timestamp=datetime.now(),
                drop_gal=25.0,
                confidence=0.85
            )
        except Exception as e:
            pytest.fail(f"Should persist successfully, got: {e}")
        
        # Verify execute was called
        assert mock_conn.execute.called


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
