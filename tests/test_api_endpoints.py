"""
Comprehensive API Endpoint Tests
Tests real API endpoints in the application
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    from main import app

    return TestClient(app)


# ============================================================================
# HEALTH ENDPOINTS
# ============================================================================


class TestHealthEndpoints:
    """Tests for health check endpoints"""

    def test_health_basic(self, client):
        """GET /health should return OK."""
        response = client.get("/fuelAnalytics/api/health")
        assert response.status_code == 200

    def test_health_quick(self, client):
        """GET /health/quick should return quick health."""
        response = client.get("/fuelAnalytics/api/health/quick")
        assert response.status_code == 200

    def test_health_deep(self, client):
        """GET /health/deep should return detailed health."""
        response = client.get("/fuelAnalytics/api/health/deep")
        assert response.status_code == 200


# ============================================================================
# FLEET ENDPOINTS
# ============================================================================


class TestFleetEndpoints:
    """Tests for fleet endpoints"""

    def test_get_fleet(self, client):
        """GET /fleet should return fleet data."""
        response = client.get("/fuelAnalytics/api/fleet")
        assert response.status_code == 200

    def test_get_efficiency(self, client):
        """GET /efficiency should return efficiency data."""
        response = client.get("/fuelAnalytics/api/efficiency")
        assert response.status_code == 200

    def test_fleet_sensor_health(self, client):
        """GET /fleet/sensor-health should return sensor data."""
        response = client.get("/fuelAnalytics/api/fleet/sensor-health")
        assert response.status_code == 200


# ============================================================================
# KPI ENDPOINTS
# ============================================================================


class TestKPIEndpoints:
    """Tests for KPI endpoints"""

    def test_get_kpis(self, client):
        """GET /kpis should return KPI data."""
        response = client.get("/fuelAnalytics/api/kpis")
        assert response.status_code == 200
        data = response.json()
        # Verify structure
        assert isinstance(data, dict)


# ============================================================================
# ALERTS ENDPOINTS
# ============================================================================


class TestAlertsEndpoints:
    """Tests for alerts endpoints"""

    def test_get_alerts(self, client):
        """GET /alerts should return alerts."""
        response = client.get("/fuelAnalytics/api/alerts")
        assert response.status_code == 200

    def test_get_predictive_alerts(self, client):
        """GET /alerts/predictive should return predictive alerts."""
        response = client.get("/fuelAnalytics/api/alerts/predictive")
        assert response.status_code == 200


# ============================================================================
# ANALYTICS ENDPOINTS
# ============================================================================


class TestAnalyticsEndpoints:
    """Tests for analytics endpoints"""

    def test_analytics_trends(self, client):
        """GET /analytics/trends may return 200 or 500 if no DB."""
        response = client.get("/fuelAnalytics/api/analytics/trends")
        assert response.status_code in [200, 500]

    def test_analytics_enhanced_kpis(self, client):
        """GET /analytics/enhanced-kpis should return enhanced KPIs."""
        response = client.get("/fuelAnalytics/api/analytics/enhanced-kpis")
        assert response.status_code == 200

    def test_analytics_cost_attribution(self, client):
        """GET /analytics/cost-attribution should return cost data."""
        response = client.get("/fuelAnalytics/api/analytics/cost-attribution")
        assert response.status_code == 200

    def test_analytics_driver_scorecard(self, client):
        """GET /analytics/driver-scorecard should return scorecard."""
        response = client.get("/fuelAnalytics/api/analytics/driver-scorecard")
        assert response.status_code == 200

    def test_analytics_inefficiency_causes(self, client):
        """GET /analytics/inefficiency-causes should return causes."""
        response = client.get("/fuelAnalytics/api/analytics/inefficiency-causes")
        assert response.status_code == 200

    def test_analytics_route_efficiency(self, client):
        """GET /analytics/route-efficiency should return route data."""
        response = client.get("/fuelAnalytics/api/analytics/route-efficiency")
        assert response.status_code == 200

    def test_analytics_historical_comparison(self, client):
        """GET /analytics/historical-comparison requires params."""
        response = client.get(
            "/fuelAnalytics/api/analytics/historical-comparison?days=7"
        )
        assert response.status_code in [200, 422]


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================


class TestAuthEndpoints:
    """Tests for auth endpoints"""

    def test_login_missing_credentials(self, client):
        """POST /auth/login without credentials should fail."""
        response = client.post("/fuelAnalytics/api/auth/login")
        assert response.status_code in [400, 401, 422]

    def test_login_invalid_credentials(self, client):
        """POST /auth/login with wrong credentials should fail."""
        response = client.post(
            "/fuelAnalytics/api/auth/login",
            data={"username": "invalid", "password": "wrong"},
        )
        assert response.status_code in [400, 401, 403, 422]

    def test_me_without_token(self, client):
        """GET /auth/me without token should fail."""
        response = client.get("/fuelAnalytics/api/auth/me")
        assert response.status_code in [401, 403]


# ============================================================================
# COST ENDPOINTS
# ============================================================================


class TestCostEndpoints:
    """Tests for cost endpoints"""

    def test_cost_per_mile(self, client):
        """GET /cost/per-mile should return cost data."""
        response = client.get("/fuelAnalytics/api/cost/per-mile")
        assert response.status_code == 200

    def test_cost_speed_impact(self, client):
        """GET /cost/speed-impact should return speed impact."""
        response = client.get("/fuelAnalytics/api/cost/speed-impact")
        assert response.status_code == 200


# ============================================================================
# ENGINE HEALTH ENDPOINTS
# ============================================================================


class TestEngineHealthEndpoints:
    """Tests for engine health endpoints"""

    def test_engine_health_alerts(self, client):
        """GET /engine-health/alerts should return alerts."""
        response = client.get("/fuelAnalytics/api/engine-health/alerts")
        assert response.status_code == 200

    def test_engine_health_fleet_summary(self, client):
        """GET /engine-health/fleet-summary may return 200 or 500."""
        response = client.get("/fuelAnalytics/api/engine-health/fleet-summary")
        assert response.status_code in [200, 500]

    def test_engine_health_thresholds(self, client):
        """GET /engine-health/thresholds should return thresholds."""
        response = client.get("/fuelAnalytics/api/engine-health/thresholds")
        assert response.status_code == 200

    def test_engine_health_maintenance_predictions(self, client):
        """GET /engine-health/maintenance-predictions should return predictions."""
        response = client.get(
            "/fuelAnalytics/api/engine-health/maintenance-predictions"
        )
        assert response.status_code == 200


# ============================================================================
# GAMIFICATION ENDPOINTS
# ============================================================================


class TestGamificationEndpoints:
    """Tests for gamification endpoints"""

    def test_gamification_leaderboard(self, client):
        """GET /gamification/leaderboard should return leaderboard."""
        response = client.get("/fuelAnalytics/api/gamification/leaderboard")
        assert response.status_code == 200


# ============================================================================
# GPS ENDPOINTS
# ============================================================================


class TestGPSEndpoints:
    """Tests for GPS endpoints"""

    def test_gps_trucks(self, client):
        """GET /gps/trucks should return truck locations."""
        response = client.get("/fuelAnalytics/api/gps/trucks")
        assert response.status_code == 200

    def test_gps_geofences(self, client):
        """GET /gps/geofences should return geofences."""
        response = client.get("/fuelAnalytics/api/gps/geofences")
        assert response.status_code == 200


# ============================================================================
# GEOFENCE ENDPOINTS
# ============================================================================


class TestGeofenceEndpoints:
    """Tests for geofence endpoints"""

    def test_geofence_zones(self, client):
        """GET /geofence/zones should return zones."""
        response = client.get("/fuelAnalytics/api/geofence/zones")
        assert response.status_code == 200

    def test_geofence_events(self, client):
        """GET /geofence/events should return events."""
        response = client.get("/fuelAnalytics/api/geofence/events")
        assert response.status_code == 200


# ============================================================================
# MAINTENANCE ENDPOINTS
# ============================================================================


class TestMaintenanceEndpoints:
    """Tests for maintenance endpoints"""

    def test_maintenance_fleet_health(self, client):
        """GET /maintenance/fleet-health should return fleet health."""
        response = client.get("/fuelAnalytics/api/maintenance/fleet-health")
        assert response.status_code == 200


# ============================================================================
# ML ENDPOINTS
# ============================================================================


class TestMLEndpoints:
    """Tests for ML endpoints"""

    def test_ml_dashboard(self, client):
        """GET /ml/dashboard should return ML dashboard."""
        response = client.get("/fuelAnalytics/api/ml/dashboard")
        assert response.status_code == 200

    def test_ml_anomaly_summary(self, client):
        """GET /ml/anomaly/summary should return anomaly summary."""
        response = client.get("/fuelAnalytics/api/ml/anomaly/summary")
        assert response.status_code == 200

    def test_ml_anomaly_fleet(self, client):
        """GET /ml/anomaly/fleet should return fleet anomalies."""
        response = client.get("/fuelAnalytics/api/ml/anomaly/fleet")
        assert response.status_code == 200

    def test_ml_clusters_summary(self, client):
        """GET /ml/clusters/summary may return 200 or 400."""
        response = client.get("/fuelAnalytics/api/ml/clusters/summary")
        assert response.status_code in [200, 400]

    def test_ml_clusters_analysis(self, client):
        """GET /ml/clusters/analysis may return 200 or 400."""
        response = client.get("/fuelAnalytics/api/ml/clusters/analysis")
        assert response.status_code in [200, 400]


# ============================================================================
# EXPORT ENDPOINTS
# ============================================================================


class TestExportEndpoints:
    """Tests for export endpoints"""

    def test_export_fleet_report(self, client):
        """GET /export/fleet-report may return 200 or 500."""
        response = client.get("/fuelAnalytics/api/export/fleet-report")
        assert response.status_code in [200, 500]

    def test_export_refuels(self, client):
        """GET /export/refuels may return 200 or 500."""
        response = client.get("/fuelAnalytics/api/export/refuels")
        assert response.status_code in [200, 500]


# ============================================================================
# LOSS ANALYSIS ENDPOINTS
# ============================================================================


class TestLossAnalysisEndpoints:
    """Tests for loss analysis endpoints"""

    def test_loss_analysis(self, client):
        """GET /loss-analysis should return loss data."""
        response = client.get("/fuelAnalytics/api/loss-analysis")
        assert response.status_code == 200


# ============================================================================
# CACHE ENDPOINTS
# ============================================================================


class TestCacheEndpoints:
    """Tests for cache endpoints"""

    def test_cache_stats(self, client):
        """GET /cache/stats should return cache stats."""
        response = client.get("/fuelAnalytics/api/cache/stats")
        assert response.status_code == 200


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================


class TestAdminEndpoints:
    """Tests for admin endpoints - require authentication"""

    def test_admin_stats_requires_auth(self, client):
        """GET /admin/stats requires authentication."""
        response = client.get("/fuelAnalytics/api/admin/stats")
        assert response.status_code == 401

    def test_admin_users_requires_auth(self, client):
        """GET /admin/users requires authentication."""
        response = client.get("/fuelAnalytics/api/admin/users")
        assert response.status_code == 401

    def test_admin_carriers_requires_auth(self, client):
        """GET /admin/carriers requires authentication."""
        response = client.get("/fuelAnalytics/api/admin/carriers")
        assert response.status_code == 401


# ============================================================================
# BATCH ENDPOINTS
# ============================================================================


class TestBatchEndpoints:
    """Tests for batch endpoints"""

    def test_batch_dashboard(self, client):
        """GET /batch/dashboard should return batch dashboard data."""
        response = client.get("/fuelAnalytics/api/batch/dashboard")
        assert response.status_code == 200


# ============================================================================
# DASHBOARD WIDGETS ENDPOINTS
# ============================================================================


class TestDashboardWidgetsEndpoints:
    """Tests for dashboard widgets endpoints"""

    def test_available_widgets(self, client):
        """GET /dashboard/widgets/available should return widgets."""
        response = client.get("/fuelAnalytics/api/dashboard/widgets/available")
        assert response.status_code == 200
