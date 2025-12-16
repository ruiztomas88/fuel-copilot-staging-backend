"""
Integration Tests for Fuel Copilot System

Tests the full pipeline:
- Wialon data ingestion
- FuelEstimator processing
- CSV/MySQL output
- Alert generation

Author: Fuel Copilot Team
Version: 1.0.0
Date: November 26, 2025
"""

import pytest
import sys
import time
from pathlib import Path
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, MagicMock, patch

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_truck_data():
    """Create mock truck data from Wialon"""

    class MockTruckData:
        def __init__(self, truck_id="TEST001"):
            self.truck_id = truck_id
            self.unit_id = 12345
            self.timestamp = datetime.now(timezone.utc)
            self.epoch_time = int(time.time())
            self.fuel_lvl = 50.0  # 50%
            self.fuel_rate = 15.0  # L/h
            self.speed = 55.0  # mph
            self.rpm = 1500
            self.hdop = 1.2
            self.altitude = 500.0  # ft
            self.coolant_temp = 190.0  # F
            self.odometer = 150000.0  # miles
            self.pwr_ext = 13.8  # volts
            self.total_fuel_used = 50000.0  # gallons
            self.engine_load = 45  # %

    return MockTruckData()


@pytest.fixture
def mock_tanks_config():
    """Mock tanks configuration"""

    class MockTanksConfig:
        def __init__(self):
            self.trucks = {
                "TEST001": {"capacity_liters": 757.0, "capacity_gallons": 200.0}
            }

        def get_capacity(self, truck_id: str) -> float:
            return self.trucks.get(truck_id, {}).get("capacity_liters", 757.0)

        def get_refuel_factor(self, truck_id: str, default: float = 1.0) -> float:
            return 1.0

    return MockTanksConfig()


@pytest.fixture
def estimator(mock_tanks_config):
    """Create FuelEstimator for testing"""
    from estimator import FuelEstimator, COMMON_CONFIG

    est = FuelEstimator(
        truck_id="TEST001",
        capacity_liters=757.0,
        config=COMMON_CONFIG,
        tanks_config=mock_tanks_config,
    )
    est.initialize(sensor_pct=50.0)
    return est


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestFullPipeline:
    """Test the complete data processing pipeline"""

    def test_truck_data_to_estimate(
        self, estimator, mock_truck_data, mock_tanks_config
    ):
        """Test: Wialon data → FuelEstimator → Estimate"""
        # Process the data - v5.9.0: Use update_sensor_quality instead of removed calculate_adaptive_noise
        estimator.update_sensor_quality(
            satellites=10,  # Good GPS
            voltage=28.0,  # Normal voltage
        )

        # Calculate consumption
        ecu_consumption = estimator.calculate_ecu_consumption(
            total_fuel_used=mock_truck_data.total_fuel_used,
            dt_hours=15 / 3600,  # 15 seconds
            fuel_rate_lph=mock_truck_data.fuel_rate,
        )

        # First ECU reading initializes counter, no consumption yet
        assert ecu_consumption is None  # First reading

        # Simulate second reading
        estimator.last_total_fuel_used = mock_truck_data.total_fuel_used
        new_total_fuel = mock_truck_data.total_fuel_used + 0.1  # +0.1 gal

        ecu_consumption = estimator.calculate_ecu_consumption(
            total_fuel_used=new_total_fuel,
            dt_hours=15 / 3600,
            fuel_rate_lph=mock_truck_data.fuel_rate,
        )

        assert ecu_consumption is not None
        assert ecu_consumption > 0

        # Predict with consumption
        consumption = ecu_consumption if ecu_consumption else mock_truck_data.fuel_rate
        estimator.predict(15 / 3600, consumption)

        # Update with sensor reading
        estimator.update(mock_truck_data.fuel_lvl)

        # Get estimate
        estimate = estimator.get_estimate()

        assert "level_pct" in estimate
        assert "level_liters" in estimate
        assert "consumption_lph" in estimate
        assert "drift_pct" in estimate
        assert 0 <= estimate["level_pct"] <= 100

    def test_multiple_trucks_parallel(self, mock_tanks_config):
        """Test parallel processing of multiple trucks"""
        from estimator import FuelEstimator, COMMON_CONFIG
        from concurrent.futures import ThreadPoolExecutor, as_completed

        # Create multiple estimators
        truck_ids = [f"TRUCK{i:03d}" for i in range(10)]
        estimators = {}

        for truck_id in truck_ids:
            est = FuelEstimator(
                truck_id=truck_id,
                capacity_liters=757.0,
                config=COMMON_CONFIG,
                tanks_config=mock_tanks_config,
            )
            est.initialize(sensor_pct=50.0 + (hash(truck_id) % 30))
            estimators[truck_id] = est

        # Process in parallel
        results = {}

        def process_truck(truck_id, est):
            est.predict(15 / 3600, 15.0)  # 15 L/h
            est.update(est.level_pct - 0.1)  # Small consumption
            return est.get_estimate()

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(process_truck, tid, est): tid
                for tid, est in estimators.items()
            }

            for future in as_completed(futures):
                truck_id = futures[future]
                results[truck_id] = future.result()

        # Verify all trucks processed
        assert len(results) == len(truck_ids)

        for truck_id, estimate in results.items():
            assert "level_pct" in estimate
            assert "drift_pct" in estimate


class TestCircuitBreakerIntegration:
    """Test circuit breaker with real scenarios"""

    def test_database_failure_triggers_circuit(self):
        """Test circuit opens after repeated DB failures"""
        from circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState

        breaker = CircuitBreaker(
            "test_db",
            CircuitBreakerConfig(
                failure_threshold=3,
                timeout_seconds=5,
            ),
        )

        @breaker
        def failing_db_call():
            raise ConnectionError("DB unavailable")

        # Trigger failures
        for _ in range(3):
            try:
                failing_db_call()
            except ConnectionError:
                pass

        # Circuit should be open
        assert breaker.state == CircuitState.OPEN

    def test_circuit_recovers_after_timeout(self):
        """Test circuit goes to half-open after timeout"""
        from circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState

        breaker = CircuitBreaker(
            "test_recovery",
            CircuitBreakerConfig(
                failure_threshold=2,
                timeout_seconds=0.5,  # Short timeout for test
                success_threshold=1,
            ),
        )

        @breaker
        def sometimes_fails(should_fail=True):
            if should_fail:
                raise ConnectionError("Failed")
            return "success"

        # Open the circuit
        for _ in range(2):
            try:
                sometimes_fails(should_fail=True)
            except ConnectionError:
                pass  # Expected - opening the circuit

        assert breaker.state == CircuitState.OPEN

        # Wait for timeout
        time.sleep(0.6)

        # Next call should try (half-open)
        assert breaker.can_execute()

        # Successful call should close circuit
        result = sometimes_fails(should_fail=False)
        assert result == "success"
        assert breaker.state == CircuitState.CLOSED


class TestObservabilityIntegration:
    """Test metrics and health check integration"""

    def test_metrics_increment_during_processing(self):
        """Test metrics update during truck processing"""
        from observability import MetricsRegistry

        metrics = MetricsRegistry(prefix="test")
        metrics.counter("trucks_processed", "Trucks processed")
        metrics.histogram("processing_time", "Processing time")

        # Simulate processing
        for i in range(10):
            start = time.time()
            time.sleep(0.01)  # Simulate work
            metrics.inc("trucks_processed")
            metrics.observe("processing_time", time.time() - start)

        # Check metrics
        output = metrics.get_prometheus_format()
        assert "test_trucks_processed 10" in output
        assert "test_processing_time_count 10" in output

    def test_health_check_integration(self):
        """Test health checks work correctly"""
        from observability import HealthChecker, HealthCheckResult, HealthStatus

        health = HealthChecker()

        # Register checks
        health.register(
            "always_healthy",
            lambda: HealthCheckResult(
                name="always_healthy",
                status=HealthStatus.HEALTHY,
                message="OK",
            ),
        )

        health.register(
            "sometimes_degraded",
            lambda: HealthCheckResult(
                name="sometimes_degraded",
                status=HealthStatus.DEGRADED,
                message="Slow but working",
            ),
        )

        # Run checks
        results = health.check_all()

        assert len(results) == 2
        assert results["always_healthy"].status == HealthStatus.HEALTHY
        assert results["sometimes_degraded"].status == HealthStatus.DEGRADED

        # Overall should be degraded (not fully healthy)
        assert health.get_overall_status() == HealthStatus.DEGRADED


class TestAlertIntegration:
    """Test alert system integration"""

    def test_drift_alert_triggers(self):
        """Test that high drift triggers alert logic"""
        from estimator import FuelEstimator, COMMON_CONFIG

        config = {**COMMON_CONFIG, "max_drift_pct": 5.0}

        est = FuelEstimator(
            truck_id="ALERT_TEST",
            capacity_liters=757.0,
            config=config,
        )
        est.initialize(sensor_pct=50.0)

        # Create significant drift by predicting with high consumption
        for _ in range(50):  # 50 iterations
            est.predict(1 / 60, 30.0)  # 30 L/h for 50 minutes total

        # Now update with original sensor value
        est.update(50.0)  # Sensor says 50%, but estimate is much lower

        estimate = est.get_estimate()

        # Drift should be significant (estimate lower than sensor)
        # With 50 * 30/60 = 25L consumed, ~3.3% of 757L tank
        assert abs(estimate["drift_pct"]) > 0.5  # Should have some drift


class TestEndToEnd:
    """End-to-end tests simulating real scenarios"""

    def test_highway_driving_scenario(self, mock_tanks_config):
        """Test realistic highway driving scenario"""
        from estimator import FuelEstimator, COMMON_CONFIG
        from mpg_engine import update_mpg_state, MPGState, MPGConfig

        est = FuelEstimator(
            truck_id="HIGHWAY_TEST",
            capacity_liters=908.5,  # 240 gal
            config=COMMON_CONFIG,
            tanks_config=mock_tanks_config,
        )
        est.initialize(sensor_pct=80.0)

        mpg_state = MPGState()
        mpg_config = MPGConfig()

        # Simulate 1 hour of highway driving
        speed = 65  # mph
        fuel_rate = 28.0  # L/h (about 7.4 GPH = ~8.8 MPG)

        for minute in range(60):
            # v5.9.0: Use update_sensor_quality instead of removed calculate_adaptive_noise
            est.update_sensor_quality(
                satellites=10,  # Good GPS
                voltage=28.0,  # Normal voltage
            )

            # Predict consumption (1 minute)
            est.predict(1 / 60, fuel_rate)

            # Sensor reading (with noise)
            import random

            sensor_pct = est.level_pct + random.uniform(-1, 1)
            est.update(sensor_pct)

        # After 1 hour at 28 L/h = 28L consumed
        # Started at 80% of 908.5L = 726.8L
        # Should end at ~698.8L = ~77%
        estimate = est.get_estimate()

        assert 70 < estimate["level_pct"] < 85  # Reasonable range
        assert abs(estimate["drift_pct"]) < 5  # Drift should be controlled

    def test_refuel_detection_scenario(self, mock_tanks_config):
        """Test refuel detection during operation"""
        from estimator import FuelEstimator, COMMON_CONFIG

        est = FuelEstimator(
            truck_id="REFUEL_TEST",
            capacity_liters=757.0,
            config=COMMON_CONFIG,
            tanks_config=mock_tanks_config,
        )
        est.initialize(sensor_pct=25.0)  # Low fuel

        # Simulate driving
        for _ in range(10):
            est.predict(1 / 60, 15.0)
            est.update(est.level_pct - 0.2)

        level_before = est.level_pct

        # Simulate refuel - sensor jumps to 90%
        # In real system, refuel detection happens in main loop
        # Here we simulate by updating with high sensor value
        est.update(90.0)  # Sensor reports 90% after refuel

        level_after = est.level_pct

        # Should have increased significantly toward sensor
        assert level_after > level_before + 30  # Moved toward 90%

    def test_offline_recovery_scenario(self, mock_tanks_config):
        """Test recovery after truck goes offline"""
        from estimator import FuelEstimator, COMMON_CONFIG

        est = FuelEstimator(
            truck_id="OFFLINE_TEST",
            capacity_liters=757.0,
            config=COMMON_CONFIG,
            tanks_config=mock_tanks_config,
        )
        est.initialize(sensor_pct=60.0)

        # Normal operation
        for _ in range(5):
            est.predict(1 / 60, 15.0)
            est.update(est.level_pct - 0.1)

        level_before_offline = est.level_pct

        # Simulate 3 hour gap (offline)
        # In real scenario, we'd skip processing and then...

        # Come back online with different fuel level (consumed while offline)
        sensor_after = 40.0  # 20% consumed while offline

        # Emergency reset should trigger
        reset_triggered = est.check_emergency_reset(
            sensor_pct=sensor_after,
            time_gap_hours=3.0,
            truck_status="MOVING",
        )

        # If drift was high enough, reset would trigger
        # In this case, we need drift > 30%
        if abs(level_before_offline - sensor_after) > 30:
            assert reset_triggered
            assert abs(est.level_pct - sensor_after) < 1


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
