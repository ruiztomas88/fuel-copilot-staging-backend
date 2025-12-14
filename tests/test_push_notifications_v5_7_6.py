"""
Tests for Push Notification Service v5.7.6
═══════════════════════════════════════════════════════════════════════════════

Test coverage for Web Push notification service.
"""

import pytest
from datetime import datetime, timedelta
import uuid

from push_notification_service import (
    PushSubscription,
    Notification,
    NotificationResult,
    NotificationType,
    NotificationPriority,
    PushNotificationService,
    send_voltage_alert,
    send_dtc_alert,
    send_fuel_alert,
)


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestPushSubscription:
    """Test PushSubscription dataclass"""

    def test_basic_creation(self):
        """Should create subscription with required fields"""
        sub = PushSubscription(
            user_id="user123",
            endpoint="https://push.example.com/abc123",
            keys={"p256dh": "key1", "auth": "key2"},
        )
        assert sub.user_id == "user123"
        assert sub.platform == "web"

    def test_to_dict(self):
        """Should serialize to dict"""
        sub = PushSubscription(
            user_id="user123",
            endpoint="https://push.example.com/abc123",
            keys={"p256dh": "key1", "auth": "key2"},
            platform="web",
            device_name="Chrome Browser",
        )
        d = sub.to_dict()
        assert d["user_id"] == "user123"
        assert d["platform"] == "web"
        assert "keys" in d

    def test_from_browser(self):
        """Should create from browser subscription object"""
        browser_sub = {
            "endpoint": "https://fcm.googleapis.com/fcm/send/abc123",
            "keys": {
                "p256dh": "BNcRdreAL...",
                "auth": "tBH...",
            },
        }
        sub = PushSubscription.from_browser("user456", browser_sub)
        assert sub.user_id == "user456"
        assert sub.endpoint == browser_sub["endpoint"]
        assert sub.keys["p256dh"] == "BNcRdreAL..."


class TestNotification:
    """Test Notification dataclass"""

    def test_basic_creation(self):
        """Should create notification with defaults"""
        notif = Notification(
            id="notif123", user_id="user456", title="Test Title", body="Test Body"
        )
        assert notif.title == "Test Title"
        assert notif.notification_type == NotificationType.INFO
        assert notif.priority == NotificationPriority.NORMAL

    def test_to_push_payload(self):
        """Should convert to Web Push payload"""
        notif = Notification(
            id="notif123",
            user_id="user456",
            title="Alert",
            body="Critical issue detected",
            notification_type=NotificationType.ALERT,
            data={"truck_id": "CO0681"},
        )
        payload = notif.to_push_payload()

        assert payload["title"] == "Alert"
        assert payload["body"] == "Critical issue detected"
        assert "data" in payload
        assert payload["data"]["type"] == "alert"
        assert payload["data"]["truck_id"] == "CO0681"

    def test_to_dict(self):
        """Should serialize to dict"""
        notif = Notification(
            id="notif123", user_id="user456", title="Test", body="Body"
        )
        d = notif.to_dict()
        assert d["id"] == "notif123"
        assert d["type"] == "info"
        assert "created_at" in d

    def test_with_actions(self):
        """Should include actions in payload"""
        notif = Notification(
            id="notif123",
            user_id="user456",
            title="Alert",
            body="Issue detected",
            actions=[
                {"action": "view", "title": "Ver Detalles"},
                {"action": "dismiss", "title": "Ignorar"},
            ],
        )
        payload = notif.to_push_payload()
        assert "actions" in payload
        assert len(payload["actions"]) == 2


class TestNotificationResult:
    """Test NotificationResult dataclass"""

    def test_success_result(self):
        """Should represent successful send"""
        result = NotificationResult(
            notification_id="notif123", user_id="user456", success=True
        )
        assert result.success == True
        assert result.error is None

    def test_failed_result(self):
        """Should represent failed send"""
        result = NotificationResult(
            notification_id="notif123",
            user_id="user456",
            success=False,
            error="Endpoint not found",
        )
        assert result.success == False
        assert "Endpoint" in result.error

    def test_to_dict(self):
        """Should serialize to dict"""
        result = NotificationResult(
            notification_id="notif123", user_id="user456", success=True
        )
        d = result.to_dict()
        assert d["success"] == True


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestPushNotificationService:
    """Test PushNotificationService class"""

    def test_service_init(self):
        """Should initialize without database"""
        service = PushNotificationService()
        assert service.db_pool is None
        assert service._subscriptions == {}

    @pytest.mark.asyncio
    async def test_subscribe(self):
        """Should subscribe a user"""
        service = PushNotificationService()

        subscription_info = {
            "endpoint": "https://push.example.com/user123",
            "keys": {"p256dh": "key1", "auth": "key2"},
        }

        sub = await service.subscribe("user123", subscription_info)

        assert sub.user_id == "user123"
        assert "user123" in service._subscriptions
        assert len(service._subscriptions["user123"]) == 1

    @pytest.mark.asyncio
    async def test_subscribe_multiple_devices(self):
        """Should handle multiple devices per user"""
        service = PushNotificationService()

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device2",
                "keys": {"p256dh": "key3", "auth": "key4"},
            },
        )

        subs = await service.get_subscriptions("user123")
        assert len(subs) == 2

    @pytest.mark.asyncio
    async def test_subscribe_deduplicate(self):
        """Should deduplicate same endpoint"""
        service = PushNotificationService()

        subscription_info = {
            "endpoint": "https://push.example.com/same",
            "keys": {"p256dh": "key1", "auth": "key2"},
        }

        await service.subscribe("user123", subscription_info)
        await service.subscribe("user123", subscription_info)

        subs = await service.get_subscriptions("user123")
        assert len(subs) == 1

    @pytest.mark.asyncio
    async def test_unsubscribe(self):
        """Should unsubscribe a user"""
        service = PushNotificationService()

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )

        await service.unsubscribe("user123")

        subs = await service.get_subscriptions("user123")
        assert len(subs) == 0

    @pytest.mark.asyncio
    async def test_unsubscribe_specific_endpoint(self):
        """Should unsubscribe specific endpoint"""
        service = PushNotificationService()

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )
        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device2",
                "keys": {"p256dh": "key3", "auth": "key4"},
            },
        )

        await service.unsubscribe("user123", "https://push.example.com/device1")

        subs = await service.get_subscriptions("user123")
        assert len(subs) == 1
        assert subs[0].endpoint == "https://push.example.com/device2"

    @pytest.mark.asyncio
    async def test_send_no_subscriptions(self):
        """Should handle send with no subscriptions"""
        service = PushNotificationService()

        results = await service.send(
            user_id="unknown_user", title="Test", body="Test body"
        )

        assert len(results) == 1
        assert results[0].success == False
        assert "No subscriptions" in results[0].error

    @pytest.mark.asyncio
    async def test_send_notification(self):
        """Should send notification (simulated)"""
        service = PushNotificationService()

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )

        results = await service.send(
            user_id="user123",
            title="Test Alert",
            body="This is a test",
            notification_type=NotificationType.ALERT,
        )

        assert len(results) == 1
        # Simulated mode should succeed
        assert results[0].success == True

    @pytest.mark.asyncio
    async def test_get_user_notifications(self):
        """Should return notification history"""
        service = PushNotificationService()

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )

        await service.send("user123", "Title 1", "Body 1")
        await service.send("user123", "Title 2", "Body 2")

        history = await service.get_user_notifications("user123")

        assert history["total"] == 2
        assert len(history["notifications"]) == 2

    @pytest.mark.asyncio
    async def test_mark_as_read(self):
        """Should mark notification as read"""
        service = PushNotificationService()

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )

        await service.send("user123", "Title", "Body")

        history = await service.get_user_notifications("user123")
        notif_id = history["notifications"][0]["id"]

        result = await service.mark_as_read("user123", notif_id)
        assert result == True

        history = await service.get_user_notifications("user123")
        assert history["unread_count"] == 0

    def test_get_vapid_key(self):
        """Should return VAPID public key"""
        service = PushNotificationService()
        key = service.get_vapid_public_key()
        # Key will be empty in test environment
        assert isinstance(key, str)


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT HELPER TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestAlertHelpers:
    """Test alert-specific notification helpers"""

    @pytest.mark.asyncio
    async def test_send_voltage_alert_critical(self):
        """Should send critical voltage alert"""
        service = PushNotificationService()

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )

        results = await send_voltage_alert(
            service,
            user_id="user123",
            truck_id="CO0681",
            voltage=11.0,
            status="CRITICAL_LOW",
        )

        assert len(results) == 1
        assert results[0].success == True

    @pytest.mark.asyncio
    async def test_send_voltage_alert_low(self):
        """Should send low voltage alert"""
        service = PushNotificationService()

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )

        results = await send_voltage_alert(
            service, user_id="user123", truck_id="CO0681", voltage=12.0, status="LOW"
        )

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_send_dtc_alert(self):
        """Should send DTC alert"""
        service = PushNotificationService()

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )

        results = await send_dtc_alert(
            service,
            user_id="user123",
            truck_id="JC1282",
            dtc_code="SPN100.FMI4",
            description="Engine Oil Pressure - Voltage Low",
            severity="critical",
        )

        assert len(results) == 1
        assert results[0].success == True

    @pytest.mark.asyncio
    async def test_send_fuel_alert_theft(self):
        """Should send fuel theft alert"""
        service = PushNotificationService()

        await service.subscribe(
            "user123",
            {
                "endpoint": "https://push.example.com/device1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )

        results = await send_fuel_alert(
            service,
            user_id="user123",
            truck_id="YM6023",
            fuel_level=45.0,
            alert_type="theft",
        )

        assert len(results) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# FLEET ALERT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFleetAlerts:
    """Test fleet-wide alert functionality"""

    @pytest.mark.asyncio
    async def test_send_fleet_alert(self):
        """Should send alert to all fleet users"""
        service = PushNotificationService()

        # Subscribe multiple users
        await service.subscribe(
            "user1",
            {
                "endpoint": "https://push.example.com/user1",
                "keys": {"p256dh": "key1", "auth": "key2"},
            },
        )
        await service.subscribe(
            "user2",
            {
                "endpoint": "https://push.example.com/user2",
                "keys": {"p256dh": "key3", "auth": "key4"},
            },
        )

        results = await service.send_fleet_alert(
            carrier_id="FB01", title="Fleet Alert", body="Important fleet notification"
        )

        assert results["total_users"] == 2
        assert results["successful"] == 2


# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION TYPES AND PRIORITY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestNotificationEnums:
    """Test notification type and priority enums"""

    def test_notification_types(self):
        """Should have all notification types"""
        assert NotificationType.ALERT.value == "alert"
        assert NotificationType.WARNING.value == "warning"
        assert NotificationType.INFO.value == "info"
        assert NotificationType.SYSTEM.value == "system"

    def test_notification_priorities(self):
        """Should have all priority levels"""
        assert NotificationPriority.CRITICAL.value == "critical"
        assert NotificationPriority.HIGH.value == "high"
        assert NotificationPriority.NORMAL.value == "normal"
        assert NotificationPriority.LOW.value == "low"
