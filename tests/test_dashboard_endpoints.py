"""
Tests for Dashboard Customization Endpoints (v3.12.21)
Covers: #11 Dashboard widgets, #13 Scheduled reports
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime


class TestDashboardWidgets:
    """Test dashboard widget endpoints"""

    @pytest.fixture
    def client(self):
        from main import app

        return TestClient(app)

    def test_get_available_widgets(self, client):
        """Should return list of available widget types"""
        response = client.get("/fuelAnalytics/api/dashboard/widgets/available")

        assert response.status_code == 200
        data = response.json()

        assert "widgets" in data
        assert "total" in data
        assert data["total"] == len(data["widgets"])
        assert data["total"] >= 10  # We defined 10 widget types

        # Check widget structure
        widget = data["widgets"][0]
        assert "type" in widget
        assert "name" in widget
        assert "description" in widget
        assert "default_size" in widget
        assert "available_sizes" in widget
        assert "config_options" in widget

    def test_get_default_dashboard_layout(self, client):
        """Should return default layout for new user"""
        user_id = "test-user-new"
        response = client.get(f"/fuelAnalytics/api/dashboard/layout/{user_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["user_id"] == user_id
        assert data["name"] == "Default Dashboard"
        assert "widgets" in data
        assert len(data["widgets"]) > 0
        assert data["columns"] == 4
        assert data["theme"] == "dark"

    def test_save_dashboard_layout(self, client):
        """Should save custom dashboard layout"""
        user_id = "test-user-save"
        layout = {
            "name": "My Custom Dashboard",
            "columns": 3,
            "theme": "light",
            "widgets": [
                {
                    "id": "w1",
                    "widget_type": "fleet_summary",
                    "title": "Fleet Overview",
                    "size": "large",
                    "position": {"x": 0, "y": 0},
                    "config": {},
                    "visible": True,
                }
            ],
        }

        response = client.post(
            f"/fuelAnalytics/api/dashboard/layout/{user_id}", json=layout
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "saved"
        assert data["layout"]["user_id"] == user_id
        assert data["layout"]["name"] == "My Custom Dashboard"
        assert data["layout"]["columns"] == 3
        assert "updated_at" in data["layout"]

    def test_update_widget(self, client):
        """Should update a specific widget configuration"""
        user_id = "test-user-widget"

        # First save a layout
        layout = {
            "widgets": [
                {
                    "id": "widget-1",
                    "widget_type": "alerts",
                    "title": "Alerts",
                    "size": "small",
                    "position": {"x": 0, "y": 0},
                    "config": {"limit": 5},
                    "visible": True,
                }
            ]
        }
        client.post(f"/fuelAnalytics/api/dashboard/layout/{user_id}", json=layout)

        # Update the widget
        widget_update = {"title": "Updated Alerts", "config": {"limit": 10}}

        response = client.put(
            f"/fuelAnalytics/api/dashboard/widget/{user_id}/widget-1",
            json=widget_update,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["widget_id"] == "widget-1"

    def test_update_nonexistent_widget(self, client):
        """Should return 404 for non-existent widget"""
        user_id = "test-user-widget-2"

        # Save layout first
        layout = {"widgets": []}
        client.post(f"/fuelAnalytics/api/dashboard/layout/{user_id}", json=layout)

        response = client.put(
            f"/fuelAnalytics/api/dashboard/widget/{user_id}/nonexistent",
            json={"title": "Test"},
        )

        assert response.status_code == 404

    def test_delete_widget(self, client):
        """Should delete a widget from dashboard"""
        user_id = "test-user-delete"

        # Save layout with widget
        layout = {
            "widgets": [
                {
                    "id": "to-delete",
                    "widget_type": "alerts",
                    "title": "Alerts",
                    "size": "small",
                    "position": {"x": 0, "y": 0},
                    "config": {},
                    "visible": True,
                }
            ]
        }
        client.post(f"/fuelAnalytics/api/dashboard/layout/{user_id}", json=layout)

        # Delete widget
        response = client.delete(
            f"/fuelAnalytics/api/dashboard/widget/{user_id}/to-delete"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"


class TestUserPreferences:
    """Test user preferences endpoints"""

    @pytest.fixture
    def client(self):
        from main import app

        return TestClient(app)

    def test_get_default_preferences(self, client):
        """Should return default preferences for new user"""
        user_id = "pref-user-new"
        response = client.get(f"/fuelAnalytics/api/user/preferences/{user_id}")

        assert response.status_code == 200
        data = response.json()

        assert data["user_id"] == user_id
        assert data["timezone"] == "America/Chicago"
        assert data["units"] == "imperial"
        assert data["notifications_enabled"] is True
        assert "alert_settings" in data

    def test_update_preferences(self, client):
        """Should update user preferences"""
        user_id = "pref-user-update"
        preferences = {
            "timezone": "America/New_York",
            "units": "metric",
            "favorite_trucks": ["JC1282", "NQ6975"],
            "notifications_enabled": False,
        }

        response = client.put(
            f"/fuelAnalytics/api/user/preferences/{user_id}", json=preferences
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "updated"
        assert data["preferences"]["timezone"] == "America/New_York"
        assert data["preferences"]["units"] == "metric"
        assert len(data["preferences"]["favorite_trucks"]) == 2


class TestScheduledReports:
    """Test scheduled reports endpoints"""

    @pytest.fixture
    def client(self):
        from main import app

        return TestClient(app)

    def test_get_empty_scheduled_reports(self, client):
        """Should return empty list for user with no reports"""
        response = client.get("/fuelAnalytics/api/reports/scheduled/new-user")

        assert response.status_code == 200
        data = response.json()

        assert data["reports"] == []
        assert data["total"] == 0

    def test_create_scheduled_report(self, client):
        """Should create a new scheduled report"""
        report = {
            "user_id": "report-user",
            "name": "Weekly Efficiency Report",
            "report_type": "efficiency",
            "schedule": "weekly",
            "recipients": ["manager@example.com"],
            "format": "pdf",
        }

        response = client.post("/fuelAnalytics/api/reports/schedule", json=report)

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "created"
        assert "id" in data["report"]
        assert data["report"]["name"] == "Weekly Efficiency Report"
        assert data["report"]["enabled"] is True
        assert data["report"]["next_run"] is not None

    def test_update_scheduled_report(self, client):
        """Should update an existing scheduled report"""
        # First create a report
        report = {
            "user_id": "report-update-user",
            "name": "Daily Report",
            "report_type": "fleet_summary",
            "schedule": "daily",
        }
        create_response = client.post(
            "/fuelAnalytics/api/reports/schedule", json=report
        )
        report_id = create_response.json()["report"]["id"]

        # Update it
        updates = {"name": "Updated Daily Report", "enabled": False}
        response = client.put(
            f"/fuelAnalytics/api/reports/schedule/{report_id}", json=updates
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "updated"
        assert data["report"]["name"] == "Updated Daily Report"
        assert data["report"]["enabled"] is False

    def test_delete_scheduled_report(self, client):
        """Should delete a scheduled report"""
        # First create a report
        report = {
            "user_id": "report-delete-user",
            "name": "To Delete",
            "report_type": "efficiency",
            "schedule": "daily",
        }
        create_response = client.post(
            "/fuelAnalytics/api/reports/schedule", json=report
        )
        report_id = create_response.json()["report"]["id"]

        # Delete it
        response = client.delete(f"/fuelAnalytics/api/reports/schedule/{report_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"

    def test_run_report_now(self, client):
        """Should run a scheduled report immediately"""
        # First create a report
        report = {
            "user_id": "report-run-user",
            "name": "Run Now Test",
            "report_type": "fleet_summary",
            "schedule": "daily",
        }
        create_response = client.post(
            "/fuelAnalytics/api/reports/schedule", json=report
        )
        report_id = create_response.json()["report"]["id"]

        # Run it now
        response = client.post(f"/fuelAnalytics/api/reports/run/{report_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["report_id"] == report_id
        assert "generated_at" in data

    def test_run_nonexistent_report(self, client):
        """Should return 404 for non-existent report"""
        response = client.post("/fuelAnalytics/api/reports/run/nonexistent-id")

        assert response.status_code == 404
