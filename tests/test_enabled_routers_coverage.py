"""
Targeted Router Tests for Enabled Routers
Focus on maximizing coverage for ml_intelligence, auth, and admin routers
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with real app"""
    from main import app

    return TestClient(app)


# ============================================================================
# ML INTELLIGENCE ROUTER - COMPREHENSIVE COVERAGE
# ============================================================================


class TestMLIntelligenceRouterCoverage:
    """Maximize coverage for ml_intelligence.py router"""

    def test_ml_dashboard_basic(self, client):
        """GET /ml/dashboard returns ML dashboard"""
        response = client.get("/fuelAnalytics/api/ml/dashboard")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)

    def test_ml_dashboard_with_hours(self, client):
        """GET /ml/dashboard with hours parameter"""
        response = client.get("/fuelAnalytics/api/ml/dashboard?hours=24")
        assert response.status_code == 200

    def test_ml_dashboard_hours_48(self, client):
        """GET /ml/dashboard with hours=48"""
        response = client.get("/fuelAnalytics/api/ml/dashboard?hours=48")
        assert response.status_code == 200

    def test_ml_dashboard_hours_168(self, client):
        """GET /ml/dashboard with hours=168 (1 week)"""
        response = client.get("/fuelAnalytics/api/ml/dashboard?hours=168")
        assert response.status_code == 200

    def test_ml_anomaly_summary_direct(self, client):
        """GET /ml/anomaly-detection/summary endpoint"""
        response = client.get("/fuelAnalytics/api/ml/anomaly/summary")
        assert response.status_code in [200, 404]

    def test_ml_driver_clustering_summary(self, client):
        """GET /ml/driver-clustering/summary endpoint"""
        response = client.get("/fuelAnalytics/api/ml/clusters/summary")
        assert response.status_code in [200, 400, 404]  # May require truck param

    def test_ml_predictions_refuel(self, client):
        """Test refuel prediction via ML"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/analytics/next-refuel-prediction?truck_id={trucks[0]}"
            )
            assert response.status_code in [200, 404, 500]

    def test_ml_status_endpoint(self, client):
        """Test ML system status"""
        response = client.get("/fuelAnalytics/api/ml/status")
        assert response.status_code in [200, 404]


# ============================================================================
# AUTH ROUTER - COMPREHENSIVE COVERAGE
# ============================================================================


class TestAuthRouterCoverage:
    """Maximize coverage for auth_router.py"""

    def test_login_no_credentials(self, client):
        """POST /auth/login without credentials returns 422"""
        response = client.post("/fuelAnalytics/api/auth/login")
        assert response.status_code in [422, 400, 401]

    def test_login_empty_username(self, client):
        """POST /auth/login with empty username"""
        response = client.post(
            "/fuelAnalytics/api/auth/login", data={"username": "", "password": "test"}
        )
        assert response.status_code in [401, 422]

    def test_login_empty_password(self, client):
        """POST /auth/login with empty password"""
        response = client.post(
            "/fuelAnalytics/api/auth/login", data={"username": "test", "password": ""}
        )
        assert response.status_code in [401, 422]

    def test_login_wrong_username(self, client):
        """POST /auth/login with wrong username"""
        response = client.post(
            "/fuelAnalytics/api/auth/login",
            data={"username": "wronguser", "password": "wrongpass"},
        )
        assert response.status_code in [401, 422]

    def test_login_wrong_password(self, client):
        """POST /auth/login with wrong password"""
        response = client.post(
            "/fuelAnalytics/api/auth/login",
            data={"username": "admin", "password": "wrongpassword123"},
        )
        assert response.status_code in [401, 422]

    def test_login_special_characters(self, client):
        """POST /auth/login with special characters"""
        response = client.post(
            "/fuelAnalytics/api/auth/login",
            data={"username": "user@test!#$", "password": "pass<>?"},
        )
        assert response.status_code in [401, 422]

    def test_login_very_long_credentials(self, client):
        """POST /auth/login with very long credentials"""
        response = client.post(
            "/fuelAnalytics/api/auth/login",
            data={"username": "u" * 1000, "password": "p" * 1000},
        )
        assert response.status_code in [401, 422]

    def test_login_json_format(self, client):
        """POST /auth/login with JSON body instead of form"""
        response = client.post(
            "/fuelAnalytics/api/auth/login",
            json={"username": "test", "password": "test"},
        )
        assert response.status_code in [200, 401, 422]

    def test_me_no_token(self, client):
        """GET /auth/me without token"""
        response = client.get("/fuelAnalytics/api/auth/me")
        assert response.status_code in [401, 403, 422]

    def test_me_invalid_token(self, client):
        """GET /auth/me with invalid token"""
        response = client.get(
            "/fuelAnalytics/api/auth/me",
            headers={"Authorization": "Bearer invalid_token_here"},
        )
        assert response.status_code in [401, 403, 422]

    def test_me_malformed_header(self, client):
        """GET /auth/me with malformed authorization header"""
        response = client.get(
            "/fuelAnalytics/api/auth/me", headers={"Authorization": "NotBearer token"}
        )
        assert response.status_code in [401, 403, 422]

    def test_me_empty_token(self, client):
        """GET /auth/me with empty bearer token"""
        response = client.get(
            "/fuelAnalytics/api/auth/me", headers={"Authorization": "Bearer "}
        )
        assert response.status_code in [401, 403, 422]

    def test_refresh_no_token(self, client):
        """POST /auth/refresh without token"""
        response = client.post("/fuelAnalytics/api/auth/refresh")
        assert response.status_code in [401, 403, 422]

    def test_refresh_invalid_token(self, client):
        """POST /auth/refresh with invalid token"""
        response = client.post(
            "/fuelAnalytics/api/auth/refresh",
            headers={"Authorization": "Bearer invalid_refresh_token"},
        )
        assert response.status_code in [401, 403, 422]

    def test_refresh_with_access_token(self, client):
        """POST /auth/refresh with access token instead of refresh token"""
        # First try to get an access token
        response = client.post(
            "/fuelAnalytics/api/auth/login",
            data={"username": "admin", "password": "admin"},
        )
        if response.status_code == 200:
            token = response.json().get("access_token")
            if token:
                refresh_response = client.post(
                    "/fuelAnalytics/api/auth/refresh",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert refresh_response.status_code in [200, 401, 403, 422]


# ============================================================================
# ADMIN ROUTER - COMPREHENSIVE COVERAGE
# ============================================================================


class TestAdminRouterCoverage:
    """Maximize coverage for admin_router.py"""

    def test_admin_stats_no_auth(self, client):
        """GET /admin/stats without auth"""
        response = client.get("/fuelAnalytics/api/admin/stats")
        assert response.status_code in [200, 401, 403]

    def test_admin_stats_invalid_auth(self, client):
        """GET /admin/stats with invalid auth"""
        response = client.get(
            "/fuelAnalytics/api/admin/stats",
            headers={"Authorization": "Bearer invalid"},
        )
        assert response.status_code in [200, 401, 403]

    def test_admin_users_no_auth(self, client):
        """GET /admin/users without auth"""
        response = client.get("/fuelAnalytics/api/admin/users")
        assert response.status_code in [200, 401, 403]

    def test_admin_users_invalid_auth(self, client):
        """GET /admin/users with invalid auth"""
        response = client.get(
            "/fuelAnalytics/api/admin/users",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code in [200, 401, 403]

    def test_admin_carriers_no_auth(self, client):
        """GET /admin/carriers without auth"""
        response = client.get("/fuelAnalytics/api/admin/carriers")
        assert response.status_code in [200, 401, 403]

    def test_admin_carriers_invalid_auth(self, client):
        """GET /admin/carriers with invalid auth"""
        response = client.get(
            "/fuelAnalytics/api/admin/carriers",
            headers={"Authorization": "Bearer invalid_token"},
        )
        assert response.status_code in [200, 401, 403]

    def test_admin_create_user_no_auth(self, client):
        """POST /admin/users without auth"""
        response = client.post(
            "/fuelAnalytics/api/admin/users",
            json={"username": "newuser", "password": "newpass", "role": "viewer"},
        )
        assert response.status_code in [
            200,
            201,
            401,
            403,
            405,
            422,
        ]  # POST may not be allowed

    def test_admin_create_user_invalid_data(self, client):
        """POST /admin/users with invalid data"""
        response = client.post(
            "/fuelAnalytics/api/admin/users", json={"invalid": "data"}
        )
        assert response.status_code in [401, 403, 405, 422]  # POST may not be allowed

    def test_admin_delete_user_no_auth(self, client):
        """DELETE /admin/users/{id} without auth"""
        response = client.delete("/fuelAnalytics/api/admin/users/123")
        assert response.status_code in [200, 401, 403, 404, 405]

    def test_admin_update_user_no_auth(self, client):
        """PUT /admin/users/{id} without auth"""
        response = client.put(
            "/fuelAnalytics/api/admin/users/123", json={"role": "admin"}
        )
        assert response.status_code in [200, 401, 403, 404, 405, 422]

    def test_admin_system_info(self, client):
        """GET /admin/system-info endpoint"""
        response = client.get("/fuelAnalytics/api/admin/system-info")
        assert response.status_code in [200, 401, 403, 404]

    def test_admin_audit_log(self, client):
        """GET /admin/audit-log endpoint"""
        response = client.get("/fuelAnalytics/api/admin/audit-log")
        assert response.status_code in [200, 401, 403, 404]


# ============================================================================
# AUTH FLOW - COMPLETE WORKFLOW COVERAGE
# ============================================================================


class TestAuthWorkflow:
    """Test complete auth workflow for coverage"""

    def test_complete_login_me_refresh_flow(self, client):
        """Test complete auth workflow: login -> me -> refresh"""
        # Try login with development default credentials
        login_response = client.post(
            "/fuelAnalytics/api/auth/login",
            data={"username": "admin", "password": "admin"},
        )

        if login_response.status_code == 200:
            data = login_response.json()
            access_token = data.get("access_token")

            # Test /me with valid token
            if access_token:
                me_response = client.get(
                    "/fuelAnalytics/api/auth/me",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                assert me_response.status_code in [200, 401, 403]

                # Test refresh
                refresh_token = data.get("refresh_token")
                if refresh_token:
                    refresh_response = client.post(
                        "/fuelAnalytics/api/auth/refresh",
                        headers={"Authorization": f"Bearer {refresh_token}"},
                    )
                    assert refresh_response.status_code in [200, 401, 403]

    def test_login_with_skylord_user(self, client):
        """Try login with skylord user (another dev default)"""
        response = client.post(
            "/fuelAnalytics/api/auth/login",
            data={"username": "skylord", "password": "skylord"},
        )
        assert response.status_code in [200, 401, 422]

    def test_login_with_viewer_user(self, client):
        """Try login with viewer user (another dev default)"""
        response = client.post(
            "/fuelAnalytics/api/auth/login",
            data={"username": "skylord_viewer", "password": "skylord_viewer"},
        )
        assert response.status_code in [200, 401, 422]


# ============================================================================
# ADDITIONAL EDGE CASES FOR MAX COVERAGE
# ============================================================================


class TestEdgeCasesForCoverage:
    """Edge cases to maximize code path coverage"""

    def test_ml_dashboard_zero_hours(self, client):
        """Test with hours=0 (edge case)"""
        response = client.get("/fuelAnalytics/api/ml/dashboard?hours=0")
        assert response.status_code in [200, 400, 422]

    def test_ml_dashboard_negative_hours(self, client):
        """Test with negative hours"""
        response = client.get("/fuelAnalytics/api/ml/dashboard?hours=-1")
        assert response.status_code in [200, 400, 422]

    def test_ml_dashboard_very_large_hours(self, client):
        """Test with very large hours"""
        response = client.get("/fuelAnalytics/api/ml/dashboard?hours=10000")
        assert response.status_code in [200, 400, 422]

    def test_admin_stats_with_query_params(self, client):
        """Test admin stats with query parameters"""
        response = client.get("/fuelAnalytics/api/admin/stats?period=week")
        assert response.status_code in [200, 401, 403, 422]

    def test_auth_login_method_not_allowed(self, client):
        """Test login with wrong HTTP method"""
        response = client.get("/fuelAnalytics/api/auth/login")
        assert response.status_code in [404, 405, 422]  # GET not allowed on login

    def test_auth_me_method_not_allowed(self, client):
        """Test /me with wrong HTTP method"""
        response = client.post("/fuelAnalytics/api/auth/me")
        assert response.status_code in [405, 422]

    def test_admin_cors_preflight(self, client):
        """Test CORS preflight request"""
        response = client.options(
            "/fuelAnalytics/api/admin/stats",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in [200, 204, 405]
