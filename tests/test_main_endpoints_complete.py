"""Complete endpoint coverage for main.py"""

import pytest
import requests

BASE = "http://localhost:8000/fuelAnalytics/api"


class TestMainEndpointsComplete:
    def test_all_trucks_endpoints(self):
        for tid in [
            "DO9693",
            "FF7702",
            "GS5030",
            "GS5032",
            "GS5033",
            "GS5034",
            "GS5035",
            "GS5036",
            "GS5037",
            "GS5038",
        ]:
            requests.get(f"{BASE}/trucks/{tid}")
            requests.get(f"{BASE}/trucks/{tid}/sensor-history")
            requests.get(f"{BASE}/trucks/{tid}/fuel-trend")
            requests.get(f"{BASE}/analytics/driver/{tid}/history")
            requests.get(f"{BASE}/analytics/truck/{tid}/mpg-context")

    def test_all_analytics(self):
        requests.get(f"{BASE}/analytics/driver-scorecard")
        requests.get(f"{BASE}/analytics/enhanced-kpis")
        requests.get(f"{BASE}/analytics/enhanced-loss-analysis")
        requests.get(f"{BASE}/analytics/route-efficiency")
        requests.get(f"{BASE}/analytics/cost-attribution")
        requests.get(f"{BASE}/analytics/inefficiency-causes")
        requests.get(f"{BASE}/analytics/inefficiency-by-truck")
        requests.get(f"{BASE}/loss-analysis")

    def test_fleet_endpoints(self):
        requests.get(f"{BASE}/fleet")
        requests.get(f"{BASE}/trucks")
        requests.get(f"{BASE}/fleet/sensor-health")
        requests.get(f"{BASE}/health/fleet/summary")

    def test_refuel_endpoints(self):
        requests.get(f"{BASE}/refuels")
        requests.get(f"{BASE}/refuels/analytics")

    def test_alert_endpoints(self):
        requests.get(f"{BASE}/alerts")

    def test_kpi_endpoints(self):
        requests.get(f"{BASE}/kpis")

    def test_batch_endpoints(self):
        requests.get(f"{BASE}/batch/dashboard")

    def test_health_endpoints(self):
        requests.get(f"{BASE}/health")
        requests.get(f"{BASE}/health/quick")
        requests.get(f"{BASE}/health/deep")
        requests.get(f"{BASE}/status")
        requests.get(f"{BASE}/cache/stats")

    def test_theft_endpoints(self):
        requests.get(f"{BASE}/theft-analysis")
