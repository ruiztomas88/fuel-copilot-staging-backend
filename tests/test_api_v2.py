"""
Comprehensive tests for api_v2.py endpoints
Target: 90% coverage of v2 API endpoints
"""

import pytest
from fastapi.testclient import TestClient


class TestAPIv2Endpoints:
    """Test API v2 endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from main import app

        return TestClient(app)

    def test_v2_fleet_health(self, client):
        """Test /api/v2/fleet/health endpoint"""
        response = client.get("/api/v2/fleet/health")

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_v2_fleet_health_advanced(self, client):
        """Test /api/v2/fleet/health-advanced endpoint"""
        response = client.get("/api/v2/fleet/health-advanced")

        assert response.status_code == 200

    def test_v2_truck_risk(self, client):
        """Test /api/v2/truck/risk endpoint"""
        response = client.get("/api/v2/truck/CO0681/risk")

        assert response.status_code == 200

    def test_v2_def_predictions(self, client):
        """Test /api/v2/def/predictions endpoint"""
        response = client.get("/api/v2/def/predictions")

        assert response.status_code == 200

    def test_v2_cost_per_mile(self, client):
        """Test /api/v2/cost/per-mile endpoint"""
        response = client.get("/api/v2/cost/per-mile")

        assert response.status_code == 200

    def test_v2_fleet_patterns(self, client):
        """Test /api/v2/fleet/patterns endpoint"""
        response = client.get("/api/v2/fleet/patterns")

        assert response.status_code == 200

    def test_v2_truck_specs(self, client):
        """Test /api/v2/truck-specs endpoint"""
        response = client.get("/api/v2/truck-specs")

        assert response.status_code == 200


class TestAPIv2ErrorHandling:
    """Test API v2 error handling"""

    @pytest.fixture
    def client(self):
        from main import app

        return TestClient(app)

    def test_invalid_truck_id(self, client):
        """Test invalid truck ID handling"""
        response = client.get("/api/v2/truck/INVALID_999/risk")

        # Should return 200 with empty/error response or 404
        assert response.status_code in [200, 404]


class TestAPIv2QueryParams:
    """Test API v2 query parameters"""

    @pytest.fixture
    def client(self):
        from main import app

        return TestClient(app)

    def test_timeframe_parameters(self, client):
        """Test endpoints with timeframe parameters"""
        response = client.get("/api/v2/fleet/health?days=7")

        assert response.status_code == 200


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
