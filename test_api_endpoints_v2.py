"""
Comprehensive API endpoint testing with pytest
Tests all v2 advanced endpoints
"""

import pytest
import requests

BASE_URL = "http://localhost:8000"


class TestV2Endpoints:
    """Test suite for v2 API endpoints"""

    def test_fleet_health_advanced(self):
        """Test /api/v2/fleet/health/advanced endpoint"""
        url = f"{BASE_URL}/fuelAnalytics/api/v2/fleet/health/advanced"

        try:
            response = requests.get(url, timeout=10)
            assert (
                response.status_code == 200
            ), f"Expected 200, got {response.status_code}"

            data = response.json()

            # Verify expected fields
            expected_fields = [
                "health_score",
                "total_trucks",
                "active_trucks",
                "breakdown",
                "insights",
            ]
            for field in expected_fields:
                assert field in data, f"Missing field: {field}"

            # Verify data types
            assert isinstance(data["health_score"], (int, float))
            assert isinstance(data["total_trucks"], int)
            assert isinstance(data["active_trucks"], int)
            assert isinstance(data["breakdown"], dict)
            assert isinstance(data["insights"], list)

            print(f"✅ Fleet Health Advanced: {data['health_score']:.1f}")

        except requests.exceptions.ConnectionError:
            pytest.skip("Backend server not running")

    def test_truck_risk(self):
        """Test /api/v2/truck/{id}/risk endpoint"""
        truck_id = "RA1234"  # Use a known truck ID
        url = f"{BASE_URL}/fuelAnalytics/api/v2/truck/{truck_id}/risk"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 404:
                pytest.skip(f"Truck {truck_id} not found in database")

            assert response.status_code == 200
            data = response.json()

            # Verify expected fields
            expected_fields = ["truck_id", "risk_analysis", "correlations"]
            for field in expected_fields:
                assert field in data, f"Missing field: {field}"

            assert data["truck_id"] == truck_id
            assert "risk_score" in data["risk_analysis"]

            print(f"✅ Truck Risk: {data['risk_analysis']['risk_score']:.1f}")

        except requests.exceptions.ConnectionError:
            pytest.skip("Backend server not running")

    def test_def_predictions(self):
        """Test /api/v2/fleet/def-predictions endpoint"""
        url = f"{BASE_URL}/fuelAnalytics/api/v2/fleet/def-predictions"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            data = response.json()

            # Verify expected fields
            expected_fields = ["predictions", "total", "critical", "warnings"]
            for field in expected_fields:
                assert field in data, f"Missing field: {field}"

            assert isinstance(data["predictions"], list)
            assert isinstance(data["total"], int)

            print(f"✅ DEF Predictions: {data['total']} trucks analyzed")

        except requests.exceptions.ConnectionError:
            pytest.skip("Backend server not running")

    def test_fleet_patterns(self):
        """Test /api/v2/fleet/patterns endpoint"""
        url = f"{BASE_URL}/fuelAnalytics/api/v2/fleet/patterns"

        try:
            response = requests.get(url, timeout=10)
            assert response.status_code == 200

            data = response.json()

            # Verify expected fields
            expected_fields = ["patterns", "total_patterns", "systemic_issues"]
            for field in expected_fields:
                assert field in data, f"Missing field: {field}"

            assert isinstance(data["patterns"], list)
            assert isinstance(data["total_patterns"], int)

            print(f"✅ Fleet Patterns: {data['total_patterns']} patterns detected")

        except requests.exceptions.ConnectionError:
            pytest.skip("Backend server not running")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
