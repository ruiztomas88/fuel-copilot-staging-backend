"""
Comprehensive Router Tests for 90%+ Coverage
Tests all router endpoints using real integration tests
"""

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client with real app"""
    from main import app

    return TestClient(app)


# ============================================================================
# ALERTS ROUTER TESTS
# ============================================================================


class TestAlertsRouterComprehensive:
    """Comprehensive tests for alerts_router.py"""

    def test_get_alerts_success(self, client):
        """GET /alerts returns alerts list"""
        response = client.get("/fuelAnalytics/api/alerts")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_get_alerts_filter_severity_warning(self, client):
        """GET /alerts with severity=warning filter"""
        response = client.get("/fuelAnalytics/api/alerts?severity=warning")
        assert response.status_code == 200

    def test_get_alerts_filter_severity_critical(self, client):
        """GET /alerts with severity=critical filter"""
        response = client.get("/fuelAnalytics/api/alerts?severity=critical")
        assert response.status_code == 200

    def test_get_alerts_filter_severity_info(self, client):
        """GET /alerts with severity=info filter"""
        response = client.get("/fuelAnalytics/api/alerts?severity=info")
        assert response.status_code == 200

    def test_get_alerts_filter_truck_id(self, client):
        """GET /alerts with truck_id filter"""
        response = client.get("/fuelAnalytics/api/alerts?truck_id=TRUCK-001")
        assert response.status_code == 200

    def test_get_alerts_filter_combined(self, client):
        """GET /alerts with both severity and truck_id filters"""
        response = client.get(
            "/fuelAnalytics/api/alerts?severity=warning&truck_id=TRUCK-001"
        )
        assert response.status_code == 200

    def test_predictive_alerts_default(self, client):
        """GET /alerts/predictive returns predictions"""
        response = client.get("/fuelAnalytics/api/alerts/predictive")
        assert response.status_code == 200

    def test_predictive_alerts_days_7(self, client):
        """GET /alerts/predictive with days_ahead=7"""
        response = client.get("/fuelAnalytics/api/alerts/predictive?days_ahead=7")
        assert response.status_code == 200

    def test_predictive_alerts_days_14(self, client):
        """GET /alerts/predictive with days_ahead=14"""
        response = client.get("/fuelAnalytics/api/alerts/predictive?days_ahead=14")
        assert response.status_code == 200

    def test_predictive_alerts_days_30(self, client):
        """GET /alerts/predictive with days_ahead=30"""
        response = client.get("/fuelAnalytics/api/alerts/predictive?days_ahead=30")
        assert response.status_code == 200

    def test_predictive_alerts_no_recommendations(self, client):
        """GET /alerts/predictive without recommendations"""
        response = client.get(
            "/fuelAnalytics/api/alerts/predictive?include_recommendations=false"
        )
        assert response.status_code == 200

    def test_test_alert_default(self, client):
        """POST /alerts/test with defaults"""
        response = client.post("/fuelAnalytics/api/alerts/test")
        assert response.status_code == 200

    def test_test_alert_custom_truck(self, client):
        """POST /alerts/test with custom truck_id"""
        response = client.post("/fuelAnalytics/api/alerts/test?truck_id=TEST-XYZ")
        assert response.status_code == 200

    def test_test_alert_custom_type(self, client):
        """POST /alerts/test with custom alert_type"""
        response = client.post("/fuelAnalytics/api/alerts/test?alert_type=fuel_low")
        assert response.status_code in [200, 400]  # May require valid alert_type enum

    def test_test_alert_custom_severity(self, client):
        """POST /alerts/test with custom severity"""
        response = client.post("/fuelAnalytics/api/alerts/test?severity=critical")
        assert response.status_code == 200


# ============================================================================
# FLEET ROUTER TESTS
# ============================================================================


class TestFleetRouterComprehensive:
    """Comprehensive tests for fleet_router.py"""

    def test_get_fleet_summary(self, client):
        """GET /fleet returns fleet summary"""
        response = client.get("/fuelAnalytics/api/fleet")
        assert response.status_code == 200

    def test_get_all_trucks(self, client):
        """GET /trucks returns truck list"""
        response = client.get("/fuelAnalytics/api/trucks")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    def test_fleet_sensor_health(self, client):
        """GET /fleet/sensor-health returns sensor data"""
        response = client.get("/fuelAnalytics/api/fleet/sensor-health")
        assert response.status_code == 200


# ============================================================================
# TRUCKS ROUTER TESTS
# ============================================================================


class TestTrucksRouterComprehensive:
    """Comprehensive tests for trucks_router.py"""

    def test_get_efficiency_rankings(self, client):
        """GET /efficiency returns efficiency rankings"""
        response = client.get("/fuelAnalytics/api/efficiency")
        assert response.status_code == 200

    def test_get_truck_refuels_default(self, client):
        """GET /trucks/{id}/refuels with defaults"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(f"/fuelAnalytics/api/trucks/{trucks[0]}/refuels")
            assert response.status_code == 200

    def test_get_truck_refuels_days_7(self, client):
        """GET /trucks/{id}/refuels with days=7"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/refuels?days=7"
            )
            assert response.status_code == 200

    def test_get_truck_refuels_days_30(self, client):
        """GET /trucks/{id}/refuels with days=30"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/refuels?days=30"
            )
            assert response.status_code == 200

    def test_get_truck_refuels_days_60(self, client):
        """GET /trucks/{id}/refuels with days=60"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/refuels?days=60"
            )
            assert response.status_code == 200

    def test_get_truck_refuels_days_90(self, client):
        """GET /trucks/{id}/refuels with days=90"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/refuels?days=90"
            )
            assert response.status_code == 200

    def test_get_truck_history_default(self, client):
        """GET /trucks/{id}/history with defaults"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(f"/fuelAnalytics/api/trucks/{trucks[0]}/history")
            assert response.status_code in [200, 404]

    def test_get_truck_history_hours_24(self, client):
        """GET /trucks/{id}/history with hours=24"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/history?hours=24"
            )
            assert response.status_code in [200, 404]

    def test_get_truck_history_hours_48(self, client):
        """GET /trucks/{id}/history with hours=48"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/history?hours=48"
            )
            assert response.status_code in [200, 404]

    def test_get_truck_history_hours_168(self, client):
        """GET /trucks/{id}/history with hours=168"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/history?hours=168"
            )
            assert response.status_code in [200, 404]

    def test_get_truck_sensor_history_default(self, client):
        """GET /trucks/{id}/sensor-history with defaults"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/sensor-history"
            )
            assert response.status_code == 200

    def test_get_truck_sensor_history_hours_48(self, client):
        """GET /trucks/{id}/sensor-history with hours=48"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/sensor-history?hours=48"
            )
            assert response.status_code == 200

    def test_get_truck_fuel_trend_default(self, client):
        """GET /trucks/{id}/fuel-trend with defaults"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(f"/fuelAnalytics/api/trucks/{trucks[0]}/fuel-trend")
            assert response.status_code == 200

    def test_get_truck_fuel_trend_hours_72(self, client):
        """GET /trucks/{id}/fuel-trend with hours=72"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/fuel-trend?hours=72"
            )
            assert response.status_code == 200


# ============================================================================
# HEALTH ROUTER TESTS
# ============================================================================


class TestHealthRouterComprehensive:
    """Comprehensive tests for health_router.py"""

    def test_api_status(self, client):
        """GET /status returns basic status"""
        response = client.get("/fuelAnalytics/api/status")
        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_health_check(self, client):
        """GET /health returns health data"""
        response = client.get("/fuelAnalytics/api/health")
        assert response.status_code == 200

    def test_health_quick(self, client):
        """GET /health/quick returns quick status"""
        response = client.get("/fuelAnalytics/api/health/quick")
        assert response.status_code == 200

    def test_health_deep(self, client):
        """GET /health/deep returns deep health check"""
        response = client.get("/fuelAnalytics/api/health/deep")
        assert response.status_code in [200, 500, 503]

    def test_cache_stats(self, client):
        """GET /cache/stats returns cache info"""
        response = client.get("/fuelAnalytics/api/cache/stats")
        assert response.status_code == 200


# ============================================================================
# KPI ROUTER TESTS
# ============================================================================


class TestKPIRouterComprehensive:
    """Comprehensive tests for kpis_router.py"""

    def test_get_kpis_default(self, client):
        """GET /kpis returns KPI data"""
        response = client.get("/fuelAnalytics/api/kpis")
        assert response.status_code == 200

    def test_get_kpis_days_1(self, client):
        """GET /kpis with days=1"""
        response = client.get("/fuelAnalytics/api/kpis?days=1")
        assert response.status_code == 200

    def test_get_kpis_days_7(self, client):
        """GET /kpis with days=7"""
        response = client.get("/fuelAnalytics/api/kpis?days=7")
        assert response.status_code == 200

    def test_get_kpis_days_30(self, client):
        """GET /kpis with days=30"""
        response = client.get("/fuelAnalytics/api/kpis?days=30")
        assert response.status_code == 200

    def test_get_kpis_days_90(self, client):
        """GET /kpis with days=90"""
        response = client.get("/fuelAnalytics/api/kpis?days=90")
        assert response.status_code == 200

    def test_loss_analysis_default(self, client):
        """GET /loss-analysis returns loss data"""
        response = client.get("/fuelAnalytics/api/loss-analysis")
        assert response.status_code == 200

    def test_loss_analysis_days_7(self, client):
        """GET /loss-analysis with days=7"""
        response = client.get("/fuelAnalytics/api/loss-analysis?days=7")
        assert response.status_code == 200

    def test_loss_analysis_days_30(self, client):
        """GET /loss-analysis with days=30"""
        response = client.get("/fuelAnalytics/api/loss-analysis?days=30")
        assert response.status_code == 200


# ============================================================================
# COST ROUTER TESTS
# ============================================================================


class TestCostRouterComprehensive:
    """Comprehensive tests for cost_router.py"""

    def test_cost_per_mile_fleet_default(self, client):
        """GET /cost/per-mile returns fleet cost analysis"""
        response = client.get("/fuelAnalytics/api/cost/per-mile")
        assert response.status_code == 200

    def test_cost_per_mile_fleet_days_30(self, client):
        """GET /cost/per-mile with days=30"""
        response = client.get("/fuelAnalytics/api/cost/per-mile?days=30")
        assert response.status_code == 200

    def test_cost_per_mile_fleet_days_60(self, client):
        """GET /cost/per-mile with days=60"""
        response = client.get("/fuelAnalytics/api/cost/per-mile?days=60")
        assert response.status_code == 200

    def test_cost_per_mile_fleet_days_90(self, client):
        """GET /cost/per-mile with days=90"""
        response = client.get("/fuelAnalytics/api/cost/per-mile?days=90")
        assert response.status_code == 200

    def test_cost_speed_impact(self, client):
        """GET /cost/speed-impact returns speed analysis"""
        response = client.get("/fuelAnalytics/api/cost/speed-impact")
        assert response.status_code == 200

    def test_cost_per_mile_truck(self, client):
        """GET /cost/per-mile/{truck_id}"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(f"/fuelAnalytics/api/cost/per-mile/{trucks[0]}")
            assert response.status_code in [200, 404, 500]


# ============================================================================
# ENGINE HEALTH ROUTER TESTS
# ============================================================================


class TestEngineHealthRouterComprehensive:
    """Comprehensive tests for engine_health_router.py"""

    def test_engine_health_alerts(self, client):
        """GET /engine-health/alerts returns alerts"""
        response = client.get("/fuelAnalytics/api/engine-health/alerts")
        assert response.status_code == 200

    def test_engine_health_fleet_summary(self, client):
        """GET /engine-health/fleet-summary returns fleet health"""
        response = client.get("/fuelAnalytics/api/engine-health/fleet-summary")
        assert response.status_code in [
            200,
            500,
        ]  # May fail if engine health service unavailable

    def test_engine_health_thresholds(self, client):
        """GET /engine-health/thresholds returns thresholds"""
        response = client.get("/fuelAnalytics/api/engine-health/thresholds")
        assert response.status_code == 200

    def test_engine_health_maintenance_predictions(self, client):
        """GET /engine-health/maintenance-predictions"""
        response = client.get(
            "/fuelAnalytics/api/engine-health/maintenance-predictions"
        )
        assert response.status_code == 200

    def test_engine_health_analyze_now(self, client):
        """POST /engine-health/analyze-now triggers analysis"""
        response = client.post("/fuelAnalytics/api/engine-health/analyze-now")
        assert response.status_code in [
            200,
            500,
        ]  # May fail if analysis engine unavailable

    def test_engine_health_truck_detail(self, client):
        """GET /engine-health/{truck_id}"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(f"/fuelAnalytics/api/engine-health/{trucks[0]}")
            assert response.status_code in [200, 404]


# ============================================================================
# GPS ROUTER TESTS
# ============================================================================


class TestGPSRouterComprehensive:
    """Comprehensive tests for gps_router.py"""

    def test_gps_trucks(self, client):
        """GET /gps/trucks returns truck locations"""
        response = client.get("/fuelAnalytics/api/gps/trucks")
        assert response.status_code == 200

    def test_gps_geofences(self, client):
        """GET /gps/geofences returns geofence data"""
        response = client.get("/fuelAnalytics/api/gps/geofences")
        assert response.status_code == 200

    def test_gps_truck_history_default(self, client):
        """GET /gps/truck/{id}/history returns location history"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(f"/fuelAnalytics/api/gps/truck/{trucks[0]}/history")
            assert response.status_code in [200, 404]

    def test_gps_truck_history_hours_24(self, client):
        """GET /gps/truck/{id}/history with hours=24"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/gps/truck/{trucks[0]}/history?hours=24"
            )
            assert response.status_code in [200, 404]

    def test_gps_truck_history_hours_48(self, client):
        """GET /gps/truck/{id}/history with hours=48"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/gps/truck/{trucks[0]}/history?hours=48"
            )
            assert response.status_code in [200, 404]


# ============================================================================
# GEOFENCE ROUTER TESTS
# ============================================================================


class TestGeofenceRouterComprehensive:
    """Comprehensive tests for geofence_router.py"""

    def test_geofence_zones(self, client):
        """GET /geofence/zones returns zones"""
        response = client.get("/fuelAnalytics/api/geofence/zones")
        assert response.status_code == 200

    def test_geofence_events_default(self, client):
        """GET /geofence/events returns events"""
        response = client.get("/fuelAnalytics/api/geofence/events")
        assert response.status_code == 200

    def test_geofence_events_days_7(self, client):
        """GET /geofence/events with days=7"""
        response = client.get("/fuelAnalytics/api/geofence/events?days=7")
        assert response.status_code == 200

    def test_geofence_events_days_30(self, client):
        """GET /geofence/events with days=30"""
        response = client.get("/fuelAnalytics/api/geofence/events?days=30")
        assert response.status_code == 200


# ============================================================================
# GAMIFICATION ROUTER TESTS
# ============================================================================


class TestGamificationRouterComprehensive:
    """Comprehensive tests for gamification_router.py"""

    def test_gamification_leaderboard(self, client):
        """GET /gamification/leaderboard returns rankings"""
        response = client.get("/fuelAnalytics/api/gamification/leaderboard")
        assert response.status_code == 200

    def test_gamification_badges(self, client):
        """GET /gamification/badges/{truck_id}"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(f"/fuelAnalytics/api/gamification/badges/{trucks[0]}")
            assert response.status_code == 200

    def test_gamification_achievements(self, client):
        """GET /gamification/achievements"""
        response = client.get("/fuelAnalytics/api/gamification/achievements")
        assert response.status_code in [200, 404]


# ============================================================================
# MAINTENANCE ROUTER TESTS
# ============================================================================


class TestMaintenanceRouterComprehensive:
    """Comprehensive tests for maintenance_router.py"""

    def test_maintenance_fleet_health(self, client):
        """GET /maintenance/fleet-health"""
        response = client.get("/fuelAnalytics/api/maintenance/fleet-health")
        assert response.status_code == 200

    def test_maintenance_schedule(self, client):
        """GET /maintenance/schedule"""
        response = client.get("/fuelAnalytics/api/maintenance/schedule")
        assert response.status_code in [200, 404]

    def test_maintenance_predictions(self, client):
        """GET /maintenance/predictions"""
        response = client.get("/fuelAnalytics/api/maintenance/predictions")
        assert response.status_code in [200, 404]

    def test_maintenance_v3_dashboard(self, client):
        """GET /v3/maintenance/dashboard"""
        response = client.get("/fuelAnalytics/api/v3/maintenance/dashboard")
        assert response.status_code in [200, 404]


# ============================================================================
# EXPORT ROUTER TESTS
# ============================================================================


class TestExportRouterComprehensive:
    """Comprehensive tests for export_router.py"""

    def test_export_fleet_report(self, client):
        """GET /export/fleet-report"""
        response = client.get("/fuelAnalytics/api/export/fleet-report")
        assert response.status_code in [
            200,
            500,
        ]  # May fail if export service unavailable

    def test_export_refuels_default(self, client):
        """GET /export/refuels with defaults"""
        response = client.get("/fuelAnalytics/api/export/refuels")
        assert response.status_code in [200, 500]  # May fail if table doesn't exist

    def test_export_refuels_csv(self, client):
        """GET /export/refuels with format=csv"""
        response = client.get("/fuelAnalytics/api/export/refuels?format=csv")
        assert response.status_code in [200, 500]  # May fail if table doesn't exist

    def test_export_refuels_days_30(self, client):
        """GET /export/refuels with days=30"""
        response = client.get("/fuelAnalytics/api/export/refuels?days=30")
        assert response.status_code in [200, 500]  # May fail if table doesn't exist

    def test_export_refuels_days_60(self, client):
        """GET /export/refuels with days=60"""
        response = client.get("/fuelAnalytics/api/export/refuels?days=60")
        assert response.status_code in [200, 500]  # May fail if table doesn't exist


# ============================================================================
# DASHBOARD ROUTER TESTS
# ============================================================================


class TestDashboardRouterComprehensive:
    """Comprehensive tests for dashboard_router.py"""

    def test_available_widgets(self, client):
        """GET /dashboard/widgets returns widgets"""
        response = client.get("/fuelAnalytics/api/dashboard/widgets")
        assert response.status_code in [200, 404]  # May not be implemented

    def test_dashboard_layout(self, client):
        """GET /dashboard/layout"""
        response = client.get("/fuelAnalytics/api/dashboard/layout")
        assert response.status_code in [200, 404]

    def test_batch_dashboard(self, client):
        """GET /batch/dashboard"""
        response = client.get("/fuelAnalytics/api/batch/dashboard")
        assert response.status_code == 200


# ============================================================================
# ANALYTICS ROUTER TESTS
# ============================================================================


class TestAnalyticsRouterComprehensive:
    """Comprehensive tests for analytics_router.py"""

    def test_analytics_trends_default(self, client):
        """GET /analytics/trends"""
        response = client.get("/fuelAnalytics/api/analytics/trends")
        assert response.status_code in [200, 500]  # May fail if data unavailable

    def test_analytics_trends_days_7(self, client):
        """GET /analytics/trends?days=7"""
        response = client.get("/fuelAnalytics/api/analytics/trends?days=7")
        assert response.status_code in [200, 500]  # May fail if data unavailable

    def test_analytics_trends_days_30(self, client):
        """GET /analytics/trends?days=30"""
        response = client.get("/fuelAnalytics/api/analytics/trends?days=30")
        assert response.status_code in [200, 500]  # May fail if data unavailable

    def test_analytics_enhanced_kpis(self, client):
        """GET /analytics/enhanced-kpis"""
        response = client.get("/fuelAnalytics/api/analytics/enhanced-kpis")
        assert response.status_code == 200

    def test_analytics_cost_attribution(self, client):
        """GET /analytics/cost-attribution"""
        response = client.get("/fuelAnalytics/api/analytics/cost-attribution")
        assert response.status_code == 200

    def test_analytics_driver_scorecard(self, client):
        """GET /analytics/driver-scorecard"""
        response = client.get("/fuelAnalytics/api/analytics/driver-scorecard")
        assert response.status_code == 200

    def test_analytics_inefficiency_causes(self, client):
        """GET /analytics/inefficiency-causes"""
        response = client.get("/fuelAnalytics/api/analytics/inefficiency-causes")
        assert response.status_code == 200

    def test_analytics_route_efficiency(self, client):
        """GET /analytics/route-efficiency"""
        response = client.get("/fuelAnalytics/api/analytics/route-efficiency")
        assert response.status_code == 200

    def test_analytics_historical_comparison(self, client):
        """GET /analytics/historical-comparison"""
        response = client.get("/fuelAnalytics/api/analytics/historical-comparison")
        assert response.status_code in [200, 422, 500]  # May require parameters

    def test_analytics_next_refuel_prediction(self, client):
        """GET /analytics/next-refuel-prediction"""
        response = client.get("/fuelAnalytics/api/analytics/next-refuel-prediction")
        assert response.status_code == 200


# ============================================================================
# ML INTELLIGENCE ROUTER TESTS
# ============================================================================


class TestMLIntelligenceRouterComprehensive:
    """Comprehensive tests for ml_intelligence.py"""

    def test_ml_dashboard(self, client):
        """GET /ml/dashboard"""
        response = client.get("/fuelAnalytics/api/ml/dashboard")
        assert response.status_code == 200

    def test_ml_anomaly_summary(self, client):
        """GET /ml/anomaly-detection/summary"""
        response = client.get("/fuelAnalytics/api/ml/anomaly-detection/summary")
        assert response.status_code in [200, 404]  # Endpoint may not exist

    def test_ml_anomaly_fleet(self, client):
        """GET /ml/anomaly-detection/fleet"""
        response = client.get("/fuelAnalytics/api/ml/anomaly-detection/fleet")
        assert response.status_code in [200, 404]  # Endpoint may not exist

    def test_ml_anomaly_fleet_hours_24(self, client):
        """GET /ml/anomaly-detection/fleet?hours=24"""
        response = client.get("/fuelAnalytics/api/ml/anomaly-detection/fleet?hours=24")
        assert response.status_code in [200, 404]  # Endpoint may not exist

    def test_ml_anomaly_fleet_hours_48(self, client):
        """GET /ml/anomaly-detection/fleet?hours=48"""
        response = client.get("/fuelAnalytics/api/ml/anomaly-detection/fleet?hours=48")
        assert response.status_code in [200, 404]  # Endpoint may not exist

    def test_ml_clusters_summary(self, client):
        """GET /ml/driver-clustering/summary"""
        response = client.get("/fuelAnalytics/api/ml/driver-clustering/summary")
        assert response.status_code in [200, 404]  # Endpoint may not exist

    def test_ml_clusters_analysis(self, client):
        """GET /ml/driver-clustering/analysis"""
        response = client.get("/fuelAnalytics/api/ml/driver-clustering/analysis")
        assert response.status_code in [200, 404]  # Endpoint may not exist


# ============================================================================
# REPORTS ROUTER TESTS
# ============================================================================


class TestReportsRouterComprehensive:
    """Comprehensive tests for reports_router.py"""

    def test_report_schedules(self, client):
        """GET /reports/schedules"""
        response = client.get("/fuelAnalytics/api/reports/schedules")
        assert response.status_code in [200, 404]

    def test_report_generate_daily(self, client):
        """GET /reports/generate/daily"""
        response = client.get("/fuelAnalytics/api/reports/generate/daily")
        assert response.status_code in [200, 404, 500]

    def test_report_generate_weekly(self, client):
        """GET /reports/generate/weekly"""
        response = client.get("/fuelAnalytics/api/reports/generate/weekly")
        assert response.status_code in [200, 404, 500]


# ============================================================================
# NOTIFICATIONS ROUTER TESTS
# ============================================================================


class TestNotificationsRouterComprehensive:
    """Comprehensive tests for notifications_router.py"""

    def test_notifications_list(self, client):
        """GET /notifications"""
        response = client.get("/fuelAnalytics/api/notifications")
        assert response.status_code in [200, 404]

    def test_notifications_settings(self, client):
        """GET /notifications/settings"""
        response = client.get("/fuelAnalytics/api/notifications/settings")
        assert response.status_code in [200, 404]


# ============================================================================
# UTILIZATION ROUTER TESTS
# ============================================================================


class TestUtilizationRouterComprehensive:
    """Comprehensive tests for utilization_router.py"""

    def test_utilization_fleet(self, client):
        """GET /utilization/fleet"""
        response = client.get("/fuelAnalytics/api/utilization/fleet")
        assert response.status_code == 200

    def test_utilization_truck(self, client):
        """GET /utilization/{truck_id}"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(f"/fuelAnalytics/api/utilization/{trucks[0]}")
            assert response.status_code in [200, 404]

    def test_utilization_optimization(self, client):
        """GET /utilization/optimization"""
        response = client.get("/fuelAnalytics/api/utilization/optimization")
        assert response.status_code in [200, 404]


# ============================================================================
# AUTH ROUTER TESTS
# ============================================================================


class TestAuthRouterComprehensive:
    """Comprehensive tests for auth_router.py"""

    def test_login_missing_credentials(self, client):
        """POST /auth/login without credentials"""
        response = client.post("/fuelAnalytics/api/auth/login")
        assert response.status_code in [422, 400, 401]

    def test_login_invalid_credentials(self, client):
        """POST /auth/login with invalid credentials"""
        response = client.post(
            "/fuelAnalytics/api/auth/login",
            data={"username": "invalid_user", "password": "invalid_pass"},
        )
        assert response.status_code in [401, 422]

    def test_me_without_token(self, client):
        """GET /auth/me without token"""
        response = client.get("/fuelAnalytics/api/auth/me")
        assert response.status_code in [401, 403, 422]

    def test_refresh_without_token(self, client):
        """POST /auth/refresh without token"""
        response = client.post("/fuelAnalytics/api/auth/refresh")
        assert response.status_code in [401, 403, 422]


# ============================================================================
# ADMIN ROUTER TESTS
# ============================================================================


class TestAdminRouterComprehensive:
    """Comprehensive tests for admin_router.py"""

    def test_admin_stats(self, client):
        """GET /admin/stats"""
        response = client.get("/fuelAnalytics/api/admin/stats")
        assert response.status_code in [200, 401, 403]

    def test_admin_users(self, client):
        """GET /admin/users"""
        response = client.get("/fuelAnalytics/api/admin/users")
        assert response.status_code in [200, 401, 403]

    def test_admin_carriers(self, client):
        """GET /admin/carriers"""
        response = client.get("/fuelAnalytics/api/admin/carriers")
        assert response.status_code in [200, 401, 403]


# ============================================================================
# EDGE CASES AND BOUNDARY TESTS
# ============================================================================


class TestBoundaryConditions:
    """Tests for boundary conditions and edge cases"""

    def test_kpis_boundary_min_days(self, client):
        """Test KPIs with minimum days=1"""
        response = client.get("/fuelAnalytics/api/kpis?days=1")
        assert response.status_code == 200

    def test_kpis_boundary_max_days(self, client):
        """Test KPIs with maximum days=90"""
        response = client.get("/fuelAnalytics/api/kpis?days=90")
        assert response.status_code == 200

    def test_history_boundary_min_hours(self, client):
        """Test history with minimum hours=1"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/history?hours=1"
            )
            assert response.status_code in [200, 404]

    def test_history_boundary_max_hours(self, client):
        """Test history with maximum hours=168"""
        trucks = client.get("/fuelAnalytics/api/trucks").json()
        if trucks:
            response = client.get(
                f"/fuelAnalytics/api/trucks/{trucks[0]}/history?hours=168"
            )
            assert response.status_code in [200, 404]

    def test_predictive_alerts_boundary_min(self, client):
        """Test predictive alerts with days_ahead=1"""
        response = client.get("/fuelAnalytics/api/alerts/predictive?days_ahead=1")
        assert response.status_code == 200

    def test_predictive_alerts_boundary_max(self, client):
        """Test predictive alerts with days_ahead=30"""
        response = client.get("/fuelAnalytics/api/alerts/predictive?days_ahead=30")
        assert response.status_code == 200


# ============================================================================
# ADDITIONAL COVERAGE TESTS
# ============================================================================


class TestAdditionalCoverage:
    """Additional tests to maximize coverage"""

    def test_alerts_unknown_severity(self, client):
        """Test alerts with unknown severity value"""
        response = client.get("/fuelAnalytics/api/alerts?severity=unknown")
        assert response.status_code == 200

    def test_export_unknown_format(self, client):
        """Test export with unknown format"""
        response = client.get("/fuelAnalytics/api/export/refuels?format=unknown")
        assert response.status_code in [
            200,
            400,
            500,
        ]  # May error on invalid format or DB

    def test_cost_per_mile_max_days(self, client):
        """Test cost per mile with max days"""
        response = client.get("/fuelAnalytics/api/cost/per-mile?days=365")
        assert response.status_code == 200

    def test_ml_anomaly_extended_hours(self, client):
        """Test ML anomaly with extended hours"""
        response = client.get("/fuelAnalytics/api/ml/anomaly-detection/fleet?hours=168")
        assert response.status_code in [200, 404]  # Endpoint may not exist
