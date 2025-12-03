"""
Tests for Observability Module (Metrics & Health Checks)

Run with: pytest tests/test_observability.py -v
"""

import pytest
import time
import threading
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from observability import (
    MetricsRegistry,
    MetricType,
    HealthChecker,
    HealthCheckResult,
    HealthStatus,
    ObservabilityServer,
    get_metrics,
    get_health_checker,
)


class TestMetricsRegistry:
    """Tests for MetricsRegistry"""

    def test_counter_increments(self):
        """Counter metric increments correctly"""
        metrics = MetricsRegistry(prefix="test")
        metrics.counter("requests_total", "Total requests")

        metrics.inc("requests_total")
        metrics.inc("requests_total")
        metrics.inc("requests_total", 5)

        output = metrics.get_prometheus_format()
        assert "test_requests_total 7" in output

    def test_gauge_sets_value(self):
        """Gauge metric sets and updates value"""
        metrics = MetricsRegistry(prefix="test")
        metrics.gauge("active_connections", "Active connections")

        metrics.set("active_connections", 10)
        output = metrics.get_prometheus_format()
        assert "test_active_connections 10" in output

        metrics.set("active_connections", 5)
        output = metrics.get_prometheus_format()
        assert "test_active_connections 5" in output

    def test_gauge_dec(self):
        """Gauge can decrement"""
        metrics = MetricsRegistry(prefix="test")
        metrics.gauge("items", "Items count")

        metrics.set("items", 10)
        metrics.dec("items", 3)

        output = metrics.get_prometheus_format()
        assert "test_items 7" in output

    def test_histogram_observes_values(self):
        """Histogram records observations in buckets"""
        metrics = MetricsRegistry(prefix="test")
        metrics.histogram("latency", "Request latency", buckets=[0.1, 0.5, 1.0])

        metrics.observe("latency", 0.05)  # In 0.1 bucket
        metrics.observe("latency", 0.3)  # In 0.5 bucket
        metrics.observe("latency", 0.8)  # In 1.0 bucket
        metrics.observe("latency", 2.0)  # Only in +Inf

        output = metrics.get_prometheus_format()

        assert 'test_latency_bucket{le="0.1"} 1' in output
        assert 'test_latency_bucket{le="0.5"} 2' in output
        assert 'test_latency_bucket{le="1.0"} 3' in output
        assert 'test_latency_bucket{le="+Inf"} 4' in output
        assert "test_latency_count 4" in output

    def test_histogram_sum(self):
        """Histogram tracks sum of observations"""
        metrics = MetricsRegistry(prefix="test")
        metrics.histogram("processing_time", "Processing time")

        metrics.observe("processing_time", 1.0)
        metrics.observe("processing_time", 2.0)
        metrics.observe("processing_time", 3.0)

        output = metrics.get_prometheus_format()
        assert "test_processing_time_sum 6.0" in output

    def test_prometheus_format_includes_help(self):
        """Prometheus format includes HELP comments"""
        metrics = MetricsRegistry(prefix="test")
        metrics.counter("my_counter", "A helpful description")

        output = metrics.get_prometheus_format()
        assert "# HELP test_my_counter A helpful description" in output
        assert "# TYPE test_my_counter counter" in output

    def test_json_format(self):
        """Can export as JSON"""
        metrics = MetricsRegistry(prefix="test")
        metrics.counter("requests", "Requests")
        metrics.gauge("connections", "Connections")

        metrics.inc("requests", 10)
        metrics.set("connections", 5)

        json_output = metrics.get_json_format()

        assert json_output["test_requests"]["value"] == 10
        assert json_output["test_connections"]["value"] == 5

    def test_thread_safety(self):
        """Metrics are thread-safe"""
        metrics = MetricsRegistry(prefix="test")
        metrics.counter("concurrent", "Concurrent increments")

        def increment_many():
            for _ in range(1000):
                metrics.inc("concurrent")

        threads = [threading.Thread(target=increment_many) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        output = metrics.get_prometheus_format()
        assert "test_concurrent 10000" in output


class TestHealthChecker:
    """Tests for HealthChecker"""

    def test_register_and_check(self):
        """Can register and run health checks"""
        health = HealthChecker()

        health.register(
            "test_check",
            lambda: HealthCheckResult(
                name="test_check",
                status=HealthStatus.HEALTHY,
                message="All good",
            ),
        )

        result = health.check("test_check")

        assert result.status == HealthStatus.HEALTHY
        assert result.message == "All good"

    def test_unknown_check_returns_unhealthy(self):
        """Unknown check returns unhealthy status"""
        health = HealthChecker()

        result = health.check("nonexistent")

        assert result.status == HealthStatus.UNHEALTHY
        assert "Unknown check" in result.message

    def test_check_exception_returns_unhealthy(self):
        """Exception in check returns unhealthy"""
        health = HealthChecker()

        def failing_check():
            raise RuntimeError("Check failed!")

        health.register("failing", failing_check)
        result = health.check("failing")

        assert result.status == HealthStatus.UNHEALTHY
        assert "Check failed!" in result.message

    def test_check_all(self):
        """check_all runs all registered checks"""
        health = HealthChecker()

        health.register(
            "check1",
            lambda: HealthCheckResult(
                name="check1", status=HealthStatus.HEALTHY, message="OK"
            ),
        )
        health.register(
            "check2",
            lambda: HealthCheckResult(
                name="check2", status=HealthStatus.DEGRADED, message="Slow"
            ),
        )

        results = health.check_all()

        assert len(results) == 2
        assert "check1" in results
        assert "check2" in results

    def test_overall_status_healthy(self):
        """Overall status is HEALTHY when all checks pass"""
        health = HealthChecker()

        health.register(
            "check1",
            lambda: HealthCheckResult(
                name="check1", status=HealthStatus.HEALTHY, message="OK"
            ),
        )
        health.register(
            "check2",
            lambda: HealthCheckResult(
                name="check2", status=HealthStatus.HEALTHY, message="OK"
            ),
        )

        assert health.get_overall_status() == HealthStatus.HEALTHY

    def test_overall_status_degraded(self):
        """Overall status is DEGRADED when one check is degraded"""
        health = HealthChecker()

        health.register(
            "healthy",
            lambda: HealthCheckResult(
                name="healthy", status=HealthStatus.HEALTHY, message="OK"
            ),
        )
        health.register(
            "degraded",
            lambda: HealthCheckResult(
                name="degraded", status=HealthStatus.DEGRADED, message="Slow"
            ),
        )

        assert health.get_overall_status() == HealthStatus.DEGRADED

    def test_overall_status_unhealthy(self):
        """Overall status is UNHEALTHY when one check fails"""
        health = HealthChecker()

        health.register(
            "healthy",
            lambda: HealthCheckResult(
                name="healthy", status=HealthStatus.HEALTHY, message="OK"
            ),
        )
        health.register(
            "unhealthy",
            lambda: HealthCheckResult(
                name="unhealthy", status=HealthStatus.UNHEALTHY, message="Down"
            ),
        )

        assert health.get_overall_status() == HealthStatus.UNHEALTHY

    def test_json_report(self):
        """JSON report includes all check details"""
        health = HealthChecker()

        health.register(
            "database",
            lambda: HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Connected",
                details={"connections": 5},
            ),
        )

        report = health.get_json_report()

        assert report["status"] == "healthy"
        assert "timestamp" in report
        assert "database" in report["checks"]
        assert report["checks"]["database"]["status"] == "healthy"
        assert report["checks"]["database"]["message"] == "Connected"

    def test_latency_tracked(self):
        """Health check latency is tracked"""
        health = HealthChecker()

        def slow_check():
            time.sleep(0.1)
            return HealthCheckResult(
                name="slow", status=HealthStatus.HEALTHY, message="OK"
            )

        health.register("slow", slow_check)
        result = health.check("slow")

        assert result.latency_ms >= 100


class TestObservabilityServer:
    """Tests for ObservabilityServer HTTP endpoints"""

    @pytest.fixture
    def server(self):
        """Create and start test server"""
        metrics = MetricsRegistry(prefix="test")
        health = HealthChecker()

        metrics.counter("test_counter", "Test counter")
        metrics.inc("test_counter", 42)

        health.register(
            "test_check",
            lambda: HealthCheckResult(
                name="test_check",
                status=HealthStatus.HEALTHY,
                message="Test OK",
            ),
        )

        server = ObservabilityServer(metrics, health, port=9099)
        server.start()
        time.sleep(0.1)  # Wait for server to start

        yield server

        server.stop()

    def test_metrics_endpoint(self, server):
        """GET /metrics returns Prometheus format"""
        import urllib.request

        response = urllib.request.urlopen("http://localhost:9099/metrics")
        content = response.read().decode()

        assert response.status == 200
        assert "test_test_counter 42" in content

    def test_health_endpoint(self, server):
        """GET /health returns JSON health report"""
        import urllib.request

        response = urllib.request.urlopen("http://localhost:9099/health")
        content = json.loads(response.read().decode())

        assert response.status == 200
        assert content["status"] == "healthy"
        assert "test_check" in content["checks"]

    def test_liveness_endpoint(self, server):
        """GET /health/live returns liveness status"""
        import urllib.request

        response = urllib.request.urlopen("http://localhost:9099/health/live")
        content = json.loads(response.read().decode())

        assert response.status == 200
        assert content["alive"] is True

    def test_readiness_endpoint(self, server):
        """GET /health/ready returns readiness status"""
        import urllib.request

        response = urllib.request.urlopen("http://localhost:9099/health/ready")
        content = json.loads(response.read().decode())

        assert response.status == 200
        assert content["ready"] is True


class TestGlobalInstances:
    """Tests for global metrics and health instances"""

    def test_get_metrics_returns_same_instance(self):
        """get_metrics returns singleton"""
        metrics1 = get_metrics()
        metrics2 = get_metrics()

        assert metrics1 is metrics2

    def test_get_health_checker_returns_same_instance(self):
        """get_health_checker returns singleton"""
        health1 = get_health_checker()
        health2 = get_health_checker()

        assert health1 is health2

    def test_global_metrics_have_defaults(self):
        """Global metrics registry has default metrics"""
        metrics = get_metrics()
        output = metrics.get_prometheus_format()

        # Check for pre-registered metrics
        assert "fuel_copilot_trucks_processed_total" in output
        assert "fuel_copilot_errors_total" in output
        assert "fuel_copilot_active_trucks" in output


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
