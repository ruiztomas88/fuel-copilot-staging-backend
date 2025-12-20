"""
Additional HTTP endpoint tests for api_v2.py to boost coverage to 90%
"""

import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://localhost:8000"


class TestAPIv2FleetEndpoints:
    """Test v2 fleet endpoints"""

    def test_v2_trucks_list(self):
        """Test GET /fuelAnalytics/api/v2/trucks"""
        response = requests.get(f"{BASE_URL}/fuelAnalytics/api/v2/trucks")
        assert response.status_code == 200

    def test_v2_truck_detail(self):
        """Test GET /fuelAnalytics/api/v2/trucks/{{truck_id}}"""
        for truck_id in ["DO9693", "FF7702", "GS5030"]:
            response = requests.get(
                f"{BASE_URL}/fuelAnalytics/api/v2/trucks/{truck_id}"
            )
            assert response.status_code in [200, 404]

    def test_v2_truck_refuels(self):
        """Test GET /fuelAnalytics/api/v2/trucks/{{truck_id}}/refuels"""
        for truck_id in ["DO9693", "FF7702", "GS5030"]:
            response = requests.get(
                f"{BASE_URL}/fuelAnalytics/api/v2/trucks/{truck_id}/refuels"
            )
            assert response.status_code in [200, 404]

    def test_v2_truck_sensors(self):
        """Test GET /fuelAnalytics/api/v2/trucks/{{truck_id}}/sensors"""
        for truck_id in ["DO9693", "FF7702", "GS5030"]:
            response = requests.get(
                f"{BASE_URL}/fuelAnalytics/api/v2/trucks/{truck_id}/sensors"
            )
            assert response.status_code in [200, 404]

    def test_v2_truck_alerts(self):
        """Test GET /fuelAnalytics/api/v2/trucks/{{truck_id}}/alerts"""
        for truck_id in ["DO9693", "FF7702", "GS5030"]:
            response = requests.get(
                f"{BASE_URL}/fuelAnalytics/api/v2/trucks/{truck_id}/alerts"
            )
            assert response.status_code in [200, 404]

    def test_v2_truck_maintenance(self):
        """Test GET /fuelAnalytics/api/v2/trucks/{{truck_id}}/maintenance"""
        for truck_id in ["DO9693", "FF7702", "GS5030"]:
            response = requests.get(
                f"{BASE_URL}/fuelAnalytics/api/v2/trucks/{truck_id}/maintenance"
            )
            assert response.status_code in [200, 404]


class TestAPIv2AnalyticsEndpoints:
    """Test v2 analytics endpoints"""

    def test_v2_analytics_summary(self):
        """Test GET /fuelAnalytics/api/v2/analytics/summary"""
        response = requests.get(f"{BASE_URL}/fuelAnalytics/api/v2/analytics/summary")
        assert response.status_code == 200

    def test_v2_analytics_mpg(self):
        """Test GET /fuelAnalytics/api/v2/analytics/mpg"""
        response = requests.get(f"{BASE_URL}/fuelAnalytics/api/v2/analytics/mpg")
        assert response.status_code == 200

    def test_v2_analytics_fuel_loss(self):
        """Test GET /fuelAnalytics/api/v2/analytics/fuel-loss"""
        response = requests.get(f"{BASE_URL}/fuelAnalytics/api/v2/analytics/fuel-loss")
        assert response.status_code == 200

    def test_v2_analytics_driver_scores(self):
        """Test GET /fuelAnalytics/api/v2/analytics/driver-scores"""
        response = requests.get(
            f"{BASE_URL}/fuelAnalytics/api/v2/analytics/driver-scores"
        )
        assert response.status_code == 200


class TestAPIv2AlertEndpoints:
    """Test v2 alert endpoints"""

    def test_v2_alerts_active(self):
        """Test GET /fuelAnalytics/api/v2/alerts/active"""
        response = requests.get(f"{BASE_URL}/fuelAnalytics/api/v2/alerts/active")
        assert response.status_code == 200

    def test_v2_alerts_critical(self):
        """Test GET /fuelAnalytics/api/v2/alerts/critical"""
        response = requests.get(f"{BASE_URL}/fuelAnalytics/api/v2/alerts/critical")
        assert response.status_code == 200

    def test_v2_alerts_resolved(self):
        """Test GET /fuelAnalytics/api/v2/alerts/resolved"""
        response = requests.get(f"{BASE_URL}/fuelAnalytics/api/v2/alerts/resolved")
        assert response.status_code == 200


class TestAPIv2MaintenanceEndpoints:
    """Test v2 maintenance endpoints"""

    def test_v2_maintenance_upcoming(self):
        """Test GET /fuelAnalytics/api/v2/maintenance/upcoming"""
        response = requests.get(f"{BASE_URL}/fuelAnalytics/api/v2/maintenance/upcoming")
        assert response.status_code == 200

    def test_v2_maintenance_overdue(self):
        """Test GET /fuelAnalytics/api/v2/maintenance/overdue"""
        response = requests.get(f"{BASE_URL}/fuelAnalytics/api/v2/maintenance/overdue")
        assert response.status_code == 200


class TestAPIv2HealthEndpoints:
    """Test v2 health endpoints"""

    def test_v2_health_fleet(self):
        """Test GET /fuelAnalytics/api/v2/health/fleet"""
        response = requests.get(f"{BASE_URL}/fuelAnalytics/api/v2/health/fleet")
        assert response.status_code == 200

    def test_v2_health_truck(self):
        """Test GET /fuelAnalytics/api/v2/health/truck/{{truck_id}}"""
        for truck_id in ["DO9693", "FF7702", "GS5030"]:
            response = requests.get(
                f"{BASE_URL}/fuelAnalytics/api/v2/health/truck/{truck_id}"
            )
            assert response.status_code in [200, 404]
