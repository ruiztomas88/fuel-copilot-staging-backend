"""
Tests for GPS Tracking and Push Notifications Endpoints (v3.12.21)
Covers: #17 GPS tracking, #19 Push notifications
"""

import pytest
from fastapi.testclient import TestClient


class TestGPSTracking:
    """Test GPS tracking endpoints"""

    @pytest.fixture
    def client(self):
        from main import app

        return TestClient(app)

    def test_get_gps_truck_positions(self, client):
        """Should return GPS positions for all trucks"""
        response = client.get("/fuelAnalytics/api/gps/trucks")

        assert response.status_code == 200
        data = response.json()

        assert "trucks" in data
        assert "total" in data
        assert "timestamp" in data
        assert isinstance(data["trucks"], list)

    def test_get_truck_route_history(self, client):
        """Should return route history for a truck"""
        response = client.get("/fuelAnalytics/api/gps/truck/JC1282/history?hours=24")

        assert response.status_code == 200
        data = response.json()

        assert data["truck_id"] == "JC1282"
        assert data["period_hours"] == 24
        assert "route" in data
        assert "stops" in data
        assert "geofence_events" in data

    def test_get_empty_geofences(self, client):
        """Should return empty geofences list initially"""
        response = client.get("/fuelAnalytics/api/gps/geofences")

        assert response.status_code == 200
        data = response.json()

        assert "geofences" in data
        assert "total" in data

    def test_create_geofence(self, client):
        """Should create a new geofence"""
        geofence = {
            "name": "Warehouse A",
            "type": "circle",
            "center": {"lat": 29.7604, "lon": -95.3698},
            "radius_meters": 500,
            "alert_on_entry": True,
            "alert_on_exit": True,
        }

        response = client.post("/fuelAnalytics/api/gps/geofence", json=geofence)

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "created"
        assert "id" in data["geofence"]
        assert data["geofence"]["name"] == "Warehouse A"
        assert data["geofence"]["active"] is True

    def test_delete_geofence(self, client):
        """Should delete a geofence"""
        # First create one
        geofence = {
            "name": "To Delete",
            "type": "circle",
            "center": {"lat": 0, "lon": 0},
            "radius_meters": 100,
        }
        create_response = client.post("/fuelAnalytics/api/gps/geofence", json=geofence)
        geofence_id = create_response.json()["geofence"]["id"]

        # Delete it
        response = client.delete(f"/fuelAnalytics/api/gps/geofence/{geofence_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "deleted"

    def test_delete_nonexistent_geofence(self, client):
        """Should return 404 for non-existent geofence"""
        response = client.delete("/fuelAnalytics/api/gps/geofence/nonexistent")

        assert response.status_code == 404

    def test_get_geofence_events(self, client):
        """Should return events for a geofence"""
        # First create a geofence
        geofence = {
            "name": "Event Test",
            "type": "circle",
            "center": {"lat": 0, "lon": 0},
            "radius_meters": 100,
        }
        create_response = client.post("/fuelAnalytics/api/gps/geofence", json=geofence)
        geofence_id = create_response.json()["geofence"]["id"]

        # Get events
        response = client.get(
            f"/fuelAnalytics/api/gps/geofence/{geofence_id}/events?hours=24"
        )

        assert response.status_code == 200
        data = response.json()

        assert data["geofence_id"] == geofence_id
        assert "events" in data
        assert "summary" in data


class TestPushNotifications:
    """Test push notification endpoints"""

    @pytest.fixture
    def client(self):
        from main import app

        return TestClient(app)

    def test_subscribe_to_push(self, client):
        """Should subscribe a user to push notifications"""
        subscription = {
            "user_id": "test-user-push",
            "device_token": "abcd1234",
            "platform": "ios",
        }

        response = client.post(
            "/fuelAnalytics/api/notifications/subscribe", json=subscription
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "subscribed"
        assert data["user_id"] == "test-user-push"

    def test_subscribe_requires_user_id(self, client):
        """Should require user_id for subscription"""
        subscription = {"device_token": "abcd1234"}

        response = client.post(
            "/fuelAnalytics/api/notifications/subscribe", json=subscription
        )

        assert response.status_code == 400

    def test_unsubscribe_from_push(self, client):
        """Should unsubscribe a user from push notifications"""
        response = client.delete(
            "/fuelAnalytics/api/notifications/unsubscribe/test-user"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "unsubscribed"

    def test_get_user_notifications(self, client):
        """Should return notifications for a user"""
        response = client.get("/fuelAnalytics/api/notifications/test-user?limit=10")

        assert response.status_code == 200
        data = response.json()

        assert "notifications" in data
        assert "total" in data
        assert "unread_count" in data

    def test_send_notification(self, client):
        """Should send a push notification"""
        notification = {
            "user_id": "test-user",
            "title": "Test Alert",
            "body": "This is a test notification",
            "type": "alert",
            "data": {"truck_id": "JC1282"},
        }

        response = client.post(
            "/fuelAnalytics/api/notifications/send", json=notification
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "sent"
        assert "notification_id" in data

    def test_mark_notification_read(self, client):
        """Should mark a notification as read"""
        # First send a notification
        notification = {"user_id": "read-test", "title": "Read Me", "body": "Test"}
        send_response = client.post(
            "/fuelAnalytics/api/notifications/send", json=notification
        )
        notification_id = send_response.json()["notification_id"]

        # Mark as read
        response = client.put(
            f"/fuelAnalytics/api/notifications/{notification_id}/read"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "marked_read"

    def test_mark_nonexistent_notification_read(self, client):
        """Should return 404 for non-existent notification"""
        response = client.put("/fuelAnalytics/api/notifications/nonexistent/read")

        assert response.status_code == 404

    def test_mark_all_notifications_read(self, client):
        """Should mark all notifications as read for a user"""
        user_id = "mark-all-test"

        # Send some notifications
        for i in range(3):
            client.post(
                "/fuelAnalytics/api/notifications/send",
                json={"user_id": user_id, "title": f"Notification {i}", "body": "Test"},
            )

        # Mark all as read
        response = client.post(f"/fuelAnalytics/api/notifications/{user_id}/read-all")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["marked_read"] >= 0
