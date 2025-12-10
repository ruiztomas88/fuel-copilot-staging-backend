"""
Observability Module - Prometheus Metrics & Health Checks

Provides production-grade monitoring:
- Prometheus metrics export
- Health check endpoint
- System diagnostics
- Alert integration

Author: Fuel Copilot Team
Version: 1.0.0
Date: November 26, 2025
"""

import time
import logging
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, field
from enum import Enum
from http.server import HTTPServer, BaseHTTPRequestHandler
import json

logger = logging.getLogger(__name__)


# ============================================================================
# METRICS
# ============================================================================


class MetricType(Enum):
    """Types of metrics"""

    COUNTER = "counter"  # Only increases (e.g., requests_total)
    GAUGE = "gauge"  # Can increase/decrease (e.g., active_connections)
    HISTOGRAM = "histogram"  # Distribution (e.g., request_latency)
    SUMMARY = "summary"  # Similar to histogram, different aggregation


@dataclass
class Metric:
    """Single metric with labels"""

    name: str
    type: MetricType
    help: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    # For histograms
    buckets: List[float] = field(default_factory=list)
    bucket_counts: Dict[float, int] = field(default_factory=dict)
    sum: float = 0.0
    count: int = 0


class MetricsRegistry:
    """
    Prometheus-compatible metrics registry

    Usage:
        metrics = MetricsRegistry()

        # Counter
        metrics.counter("trucks_processed_total", "Total trucks processed")
        metrics.inc("trucks_processed_total", labels={"status": "success"})

        # Gauge
        metrics.gauge("active_trucks", "Currently active trucks")
        metrics.set("active_trucks", 39)

        # Histogram
        metrics.histogram("processing_seconds", "Processing time",
                         buckets=[0.1, 0.5, 1.0, 5.0])
        metrics.observe("processing_seconds", 0.234)
    """

    def __init__(self, prefix: str = "fuel_copilot"):
        self.prefix = prefix
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.Lock()

    def _full_name(self, name: str) -> str:
        """Get full metric name with prefix"""
        return f"{self.prefix}_{name}"

    def counter(self, name: str, help: str):
        """Register a counter metric"""
        full_name = self._full_name(name)
        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Metric(
                    name=full_name,
                    type=MetricType.COUNTER,
                    help=help,
                )

    def gauge(self, name: str, help: str):
        """Register a gauge metric"""
        full_name = self._full_name(name)
        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Metric(
                    name=full_name,
                    type=MetricType.GAUGE,
                    help=help,
                )

    def histogram(self, name: str, help: str, buckets: List[float] = None):
        """Register a histogram metric"""
        full_name = self._full_name(name)
        if buckets is None:
            buckets = [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

        with self._lock:
            if full_name not in self._metrics:
                self._metrics[full_name] = Metric(
                    name=full_name,
                    type=MetricType.HISTOGRAM,
                    help=help,
                    buckets=sorted(buckets),
                    bucket_counts={b: 0 for b in buckets},
                )

    def inc(self, name: str, value: float = 1.0, labels: Dict[str, str] = None):
        """Increment a counter"""
        full_name = self._full_name(name)
        with self._lock:
            if full_name in self._metrics:
                self._metrics[full_name].value += value

    def dec(self, name: str, value: float = 1.0):
        """Decrement a gauge"""
        full_name = self._full_name(name)
        with self._lock:
            if full_name in self._metrics:
                self._metrics[full_name].value -= value

    def set(self, name: str, value: float):
        """Set a gauge value"""
        full_name = self._full_name(name)
        with self._lock:
            if full_name in self._metrics:
                self._metrics[full_name].value = value

    def observe(self, name: str, value: float):
        """Observe a value for histogram"""
        full_name = self._full_name(name)
        with self._lock:
            if full_name in self._metrics:
                metric = self._metrics[full_name]
                metric.sum += value
                metric.count += 1

                for bucket in metric.buckets:
                    if value <= bucket:
                        metric.bucket_counts[bucket] += 1

    def get_prometheus_format(self) -> str:
        """Export metrics in Prometheus format"""
        lines = []

        with self._lock:
            for metric in self._metrics.values():
                # Help and type
                lines.append(f"# HELP {metric.name} {metric.help}")
                lines.append(f"# TYPE {metric.name} {metric.type.value}")

                if metric.type == MetricType.HISTOGRAM:
                    # Histogram buckets
                    for bucket in metric.buckets:
                        count = metric.bucket_counts.get(bucket, 0)
                        lines.append(f'{metric.name}_bucket{{le="{bucket}"}} {count}')
                    lines.append(f'{metric.name}_bucket{{le="+Inf"}} {metric.count}')
                    lines.append(f"{metric.name}_sum {metric.sum}")
                    lines.append(f"{metric.name}_count {metric.count}")
                else:
                    # Counter or Gauge
                    lines.append(f"{metric.name} {metric.value}")

                lines.append("")

        return "\n".join(lines)

    def get_json_format(self) -> Dict:
        """Export metrics as JSON"""
        result = {}

        with self._lock:
            for name, metric in self._metrics.items():
                if metric.type == MetricType.HISTOGRAM:
                    result[name] = {
                        "type": "histogram",
                        "sum": metric.sum,
                        "count": metric.count,
                        "buckets": metric.bucket_counts,
                    }
                else:
                    result[name] = {
                        "type": metric.type.value,
                        "value": metric.value,
                    }

        return result


# ============================================================================
# HEALTH CHECKS
# ============================================================================


class HealthStatus(Enum):
    """Health check status"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class HealthCheckResult:
    """Result of a health check"""

    name: str
    status: HealthStatus
    message: str = ""
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Dict = field(default_factory=dict)


class HealthChecker:
    """
    Health check system for monitoring dependencies

    Usage:
        health = HealthChecker()

        # Register checks
        health.register("database", check_database_connection)
        health.register("wialon", check_wialon_connection)

        # Run all checks
        results = health.check_all()

        # Get overall status
        status = health.get_overall_status()
    """

    def __init__(self):
        self._checks: Dict[str, Callable[[], HealthCheckResult]] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}

    def register(self, name: str, check_fn: Callable[[], HealthCheckResult]):
        """Register a health check"""
        self._checks[name] = check_fn
        logger.info(f"📋 Registered health check: {name}")

    def check(self, name: str) -> HealthCheckResult:
        """Run a single health check"""
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Unknown check: {name}",
            )

        start = time.time()
        try:
            result = self._checks[name]()
            result.latency_ms = (time.time() - start) * 1000
        except Exception as e:
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                latency_ms=(time.time() - start) * 1000,
            )

        self._last_results[name] = result
        return result

    def check_all(self) -> Dict[str, HealthCheckResult]:
        """Run all health checks"""
        results = {}
        for name in self._checks:
            results[name] = self.check(name)
        return results

    def get_overall_status(self) -> HealthStatus:
        """Get overall system health status"""
        results = self.check_all()

        if not results:
            return HealthStatus.HEALTHY

        statuses = [r.status for r in results.values()]

        if all(s == HealthStatus.HEALTHY for s in statuses):
            return HealthStatus.HEALTHY
        elif any(s == HealthStatus.UNHEALTHY for s in statuses):
            return HealthStatus.UNHEALTHY
        else:
            return HealthStatus.DEGRADED

    def get_json_report(self) -> Dict:
        """Get full health report as JSON"""
        results = self.check_all()
        overall = self.get_overall_status()

        return {
            "status": overall.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "latency_ms": result.latency_ms,
                    "details": result.details,
                }
                for name, result in results.items()
            },
        }


# ============================================================================
# HTTP SERVER FOR METRICS & HEALTH
# ============================================================================


class ObservabilityHandler(BaseHTTPRequestHandler):
    """HTTP handler for /metrics and /health endpoints"""

    metrics_registry: MetricsRegistry = None
    health_checker: HealthChecker = None

    def do_GET(self):
        if self.path == "/metrics":
            self._handle_metrics()
        elif self.path == "/health":
            self._handle_health()
        elif self.path == "/health/live":
            self._handle_liveness()
        elif self.path == "/health/ready":
            self._handle_readiness()
        else:
            self.send_error(404, "Not Found")

    def _handle_metrics(self):
        """Handle /metrics endpoint (Prometheus format)"""
        if self.metrics_registry:
            content = self.metrics_registry.get_prometheus_format()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(content.encode())
        else:
            self.send_error(503, "Metrics not available")

    def _handle_health(self):
        """Handle /health endpoint (full report)"""
        if self.health_checker:
            report = self.health_checker.get_json_report()
            status_code = 200 if report["status"] == "healthy" else 503

            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(report, indent=2).encode())
        else:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "healthy"}).encode())

    def _handle_liveness(self):
        """Handle /health/live endpoint (is process alive)"""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"alive": True}).encode())

    def _handle_readiness(self):
        """Handle /health/ready endpoint (is ready to serve)"""
        if self.health_checker:
            status = self.health_checker.get_overall_status()
            is_ready = status in (HealthStatus.HEALTHY, HealthStatus.DEGRADED)
            status_code = 200 if is_ready else 503
        else:
            status_code = 200
            is_ready = True

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"ready": is_ready}).encode())

    def log_message(self, format, *args):
        """Suppress default logging"""
        pass


class ObservabilityServer:
    """
    HTTP server for observability endpoints

    Provides:
    - GET /metrics - Prometheus metrics
    - GET /health - Full health report
    - GET /health/live - Liveness probe
    - GET /health/ready - Readiness probe

    Usage:
        metrics = MetricsRegistry()
        health = HealthChecker()

        server = ObservabilityServer(metrics, health, port=9090)
        server.start()  # Starts in background thread

        # Later:
        server.stop()
    """

    def __init__(
        self,
        metrics: MetricsRegistry = None,
        health: HealthChecker = None,
        host: str = "0.0.0.0",
        port: int = 9090,
    ):
        self.metrics = metrics
        self.health = health
        self.host = host
        self.port = port
        self._server: Optional[HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self):
        """Start server in background thread"""
        handler = ObservabilityHandler
        handler.metrics_registry = self.metrics
        handler.health_checker = self.health

        self._server = HTTPServer((self.host, self.port), handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

        logger.info(
            f"🔭 Observability server started on http://{self.host}:{self.port}"
        )
        logger.info(f"   📊 Metrics: http://{self.host}:{self.port}/metrics")
        logger.info(f"   💚 Health:  http://{self.host}:{self.port}/health")

    def stop(self):
        """Stop server"""
        if self._server:
            self._server.shutdown()
            logger.info("🔭 Observability server stopped")


# ============================================================================
# PRE-BUILT HEALTH CHECKS
# ============================================================================


def create_database_check(db_config: Dict) -> Callable[[], HealthCheckResult]:
    """Create a database health check"""

    def check_database() -> HealthCheckResult:
        try:
            import pymysql

            conn = pymysql.connect(
                host=db_config.get("host", "localhost"),
                port=db_config.get("port", 3306),
                user=db_config.get("user", ""),
                password=db_config.get("password", ""),
                database=db_config.get("database", ""),
                connect_timeout=5,
            )
            conn.ping()
            conn.close()

            return HealthCheckResult(
                name="database",
                status=HealthStatus.HEALTHY,
                message="Connected successfully",
            )
        except Exception as e:
            return HealthCheckResult(
                name="database",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )

    return check_database


def create_wialon_check(wialon_config) -> Callable[[], HealthCheckResult]:
    """Create a Wialon connection health check"""

    def check_wialon() -> HealthCheckResult:
        try:
            from wialon_reader import WialonReader

            reader = WialonReader(wialon_config, {})
            if reader.connect():
                reader.disconnect()
                return HealthCheckResult(
                    name="wialon",
                    status=HealthStatus.HEALTHY,
                    message="Connected successfully",
                )
            else:
                return HealthCheckResult(
                    name="wialon",
                    status=HealthStatus.UNHEALTHY,
                    message="Connection failed",
                )
        except Exception as e:
            return HealthCheckResult(
                name="wialon",
                status=HealthStatus.UNHEALTHY,
                message=str(e),
            )

    return check_wialon


# ============================================================================
# GLOBAL INSTANCES
# ============================================================================

# Global metrics registry
_metrics = MetricsRegistry()

# Global health checker
_health = HealthChecker()

# Pre-register common metrics
_metrics.counter("trucks_processed_total", "Total trucks processed")
_metrics.counter("errors_total", "Total errors")
_metrics.gauge("active_trucks", "Currently active trucks")
_metrics.gauge("cycle_duration_seconds", "Last cycle duration")
_metrics.histogram("truck_processing_seconds", "Truck processing time")
_metrics.histogram("db_query_seconds", "Database query time")

# 🆕 v3.9.7: Refuel metrics for monitoring
_metrics.counter("refuels_detected_total", "Total refuel events detected")
_metrics.gauge("refuels_last_gallons", "Gallons in last refuel")
_metrics.counter("mysql_retries_total", "Total MySQL retry attempts")
_metrics.counter("mysql_failures_total", "Total MySQL failures")


def get_metrics() -> MetricsRegistry:
    """Get global metrics registry"""
    return _metrics


def get_health_checker() -> HealthChecker:
    """Get global health checker"""
    return _health


# ============================================================================
# EXAMPLE USAGE
# ============================================================================

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Get global instances
    metrics = get_metrics()
    health = get_health_checker()

    # Register health checks
    health.register(
        "self",
        lambda: HealthCheckResult(
            name="self",
            status=HealthStatus.HEALTHY,
            message="Process is running",
        ),
    )

    # Start server
    server = ObservabilityServer(metrics, health, port=9090)
    server.start()

    # Simulate some work
    import random

    for i in range(100):
        metrics.inc("trucks_processed_total")
        metrics.observe("truck_processing_seconds", random.uniform(0.01, 0.5))
        time.sleep(0.1)

    metrics.set("active_trucks", 39)
    metrics.set("cycle_duration_seconds", 5.2)

    print("\n📊 Metrics (Prometheus format):")
    print(metrics.get_prometheus_format())

    print("\n💚 Health Report:")
    print(json.dumps(health.get_json_report(), indent=2))

    # Keep running
    print("\n🔭 Server running. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        server.stop()
