"""
Real Integration Tests for main.py v2 Endpoints
Tests against actual database with real data

No mocking - testing actual behavior as user demanded
"""

import pytest
from fastapi.testclient import TestClient


class TestV2Endpoints:
    """Integration tests for all v2 endpoints"""

    def test_fleet_health_endpoint(self, test_client):
        """Test GET /fuelAnalytics/api/v2/fleet/health"""
        response = test_client.get("/fuelAnalytics/api/v2/fleet/health")

        assert response.status_code == 200
        data = response.json()

        # Verify structure (actual response)
        assert "total_trucks" in data
        assert "trucks_with_issues" in data
        assert "trucks_with_low_def" in data
        assert "trucks_with_dtcs" in data
        assert "health_score" in data

        # Verify values are non-negative
        assert data["total_trucks"] >= 0
        assert data["trucks_with_issues"] >= 0
        assert data["trucks_with_low_def"] >= 0
        assert data["trucks_with_dtcs"] >= 0
        assert 0 <= data["health_score"] <= 100

    def test_fleet_health_advanced_endpoint(self, test_client):
        """Test GET /fuelAnalytics/api/v2/fleet/health/advanced"""
        response = test_client.get("/fuelAnalytics/api/v2/fleet/health/advanced")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "health_score" in data
        assert "health_level" in data
        assert "total_trucks" in data
        assert "active_trucks" in data
        assert "offline_trucks" in data
        assert "breakdown" in data
        assert "insights" in data

        # Verify health score range
        assert 0 <= data["health_score"] <= 100

        # Verify health level is valid
        assert data["health_level"] in ["EXCELLENT", "GOOD", "FAIR", "POOR", "CRITICAL"]

        # Verify breakdown structure
        breakdown = data["breakdown"]
        assert "offline_penalty" in breakdown
        assert "issues_penalty" in breakdown
        assert "dtc_penalty" in breakdown
        assert "fuel_penalty" in breakdown

        # Verify insights is a list
        assert isinstance(data["insights"], list)

    def test_truck_risk_endpoint_valid_truck(self, test_client):
        """Test GET /fuelAnalytics/api/v2/truck/{truck_id}/risk with valid truck"""
        # Use a truck ID that exists (from specs-summary we know JB6858 exists)
        truck_id = "JB6858"
        response = test_client.get(f"/fuelAnalytics/api/v2/truck/{truck_id}/risk")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "truck_id" in data
        assert data["truck_id"] == truck_id
        assert "risk_analysis" in data

        risk = data["risk_analysis"]
        assert "risk_score" in risk
        assert "risk_level" in risk
        assert "contributing_factors" in risk

        # Verify risk score range
        assert 0 <= risk["risk_score"] <= 100

        # Verify risk level is valid
        assert risk["risk_level"] in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def test_truck_risk_endpoint_invalid_truck(self, test_client):
        """Test GET /fuelAnalytics/api/v2/truck/{truck_id}/risk with invalid truck"""
        response = test_client.get("/fuelAnalytics/api/v2/truck/INVALID999/risk")

        # Should return 200 with error message (based on actual behavior)
        assert response.status_code == 200
        data = response.json()
        assert "error" in data

    def test_def_predictions_endpoint(self, test_client):
        """Test GET /fuelAnalytics/api/v2/fleet/def-predictions"""
        response = test_client.get("/fuelAnalytics/api/v2/fleet/def-predictions")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "predictions" in data
        assert "total" in data
        assert "critical" in data
        assert "warnings" in data

        # Verify counts are non-negative
        assert data["total"] >= 0
        assert data["critical"] >= 0
        assert data["warnings"] >= 0

        # Verify predictions is a list
        assert isinstance(data["predictions"], list)

        # If predictions exist, verify structure
        if data["predictions"]:
            prediction = data["predictions"][0]
            assert "truck_id" in prediction
            assert "status" in prediction
            assert "current_level_pct" in prediction
            assert "days_until_empty" in prediction

    def test_def_predictions_with_truck_filter(self, test_client):
        """Test GET /fuelAnalytics/api/v2/fleet/def-predictions?truck_ids=..."""
        response = test_client.get(
            "/fuelAnalytics/api/v2/fleet/def-predictions?truck_ids=JB6858"
        )

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "predictions" in data
        assert isinstance(data["predictions"], list)

    def test_fleet_patterns_endpoint(self, test_client):
        """Test GET /fuelAnalytics/api/v2/fleet/patterns"""
        response = test_client.get("/fuelAnalytics/api/v2/fleet/patterns")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "patterns" in data
        assert "total_patterns" in data
        assert "systemic_issues" in data
        assert "high_severity" in data

        # Verify counts are non-negative
        assert data["total_patterns"] >= 0
        assert data["high_severity"] >= 0

        # Verify patterns is a list
        assert isinstance(data["patterns"], list)
        assert isinstance(data["systemic_issues"], list)

    def test_fleet_specs_summary_endpoint(self, test_client):
        """Test GET /fuelAnalytics/api/v2/fleet/specs-summary"""
        response = test_client.get("/fuelAnalytics/api/v2/fleet/specs-summary")

        assert response.status_code == 200
        data = response.json()

        # Verify structure
        assert "fleet_summary" in data
        assert "total_groups" in data

        # Verify counts
        assert data["total_groups"] >= 0
        assert isinstance(data["fleet_summary"], list)
        assert len(data["fleet_summary"]) == data["total_groups"]

        # If summary exists, verify structure
        if data["fleet_summary"]:
            group = data["fleet_summary"][0]
            assert "make" in group
            assert "model" in group
            assert "truck_count" in group
            assert "oldest_year" in group
            assert "newest_year" in group
            assert "year_range" in group

    def test_command_center_endpoint(self, test_client):
        """Test GET /fuelAnalytics/api/v2/command-center"""
        response = test_client.get("/fuelAnalytics/api/v2/command-center")

        assert response.status_code == 200
        data = response.json()

        # Verify structure (actual response)
        assert "timestamp" in data
        assert "fleet_summary" in data
        assert "total_trucks" in data
        assert "trucks" in data
        assert "alerts" in data
        assert "metrics" in data

        # Verify fleet summary
        fleet = data["fleet_summary"]
        assert "total_trucks" in fleet
        assert "active_trucks" in fleet
        assert "offline_trucks" in fleet
        assert "moving_trucks" in fleet
        assert "stopped_trucks" in fleet
        assert "idling_trucks" in fleet

        # Verify trucks is a list
        assert isinstance(data["trucks"], list)

        # Verify alerts structure
        alerts = data["alerts"]
        assert (
            "sensor_alerts" in alerts or "low_def" in alerts or "active_dtcs" in alerts
        )


class TestV2EndpointsEdgeCases:
    """Edge case tests for v2 endpoints"""

    def test_health_endpoint_performance(self, test_client):
        """Verify health endpoint responds quickly"""
        import time

        start = time.time()
        response = test_client.get("/fuelAnalytics/api/v2/fleet/health")
        duration = time.time() - start

        assert response.status_code == 200
        assert duration < 3.0  # Should respond in under 3 seconds

    def test_concurrent_requests(self, test_client):
        """Test multiple concurrent requests work"""
        import concurrent.futures

        def make_request():
            return test_client.get("/fuelAnalytics/api/v2/fleet/health")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [f.result() for f in futures]

        # All requests should succeed
        assert all(r.status_code == 200 for r in results)
