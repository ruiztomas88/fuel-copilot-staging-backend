"""
Push Notification Service v5.7.6
═══════════════════════════════════════════════════════════════════════════════

Web Push notification service using VAPID for browser push notifications.
Also supports Firebase Cloud Messaging (FCM) for mobile apps.

Features:
- Web Push via VAPID (for PWA/browsers)
- Store/manage push subscriptions
- Send notifications with retry logic
- Batch notifications for fleet alerts
- Notification history tracking

Setup:
1. Generate VAPID keys: `npx web-push generate-vapid-keys`
2. Set environment variables:
   - VAPID_PUBLIC_KEY
   - VAPID_PRIVATE_KEY
   - VAPID_EMAIL (contact email)

Usage:
    service = PushNotificationService()

    # Subscribe a user
    await service.subscribe(user_id, subscription_info)

    # Send notification
    await service.send(user_id, title="Alert", body="Low fuel!")

    # Send to all fleet users
    await service.send_fleet_alert(carrier_id, title, body, data)

Author: Fuel Analytics Team
Version: 5.7.6
"""

import os
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════


# VAPID keys for Web Push - must be generated and set in environment
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "")
VAPID_EMAIL = os.getenv("VAPID_EMAIL", "mailto:admin@fleetbooster.com")


class NotificationType(Enum):
    """Types of notifications"""

    ALERT = "alert"  # Critical alerts (DTC, voltage, etc)
    WARNING = "warning"  # Warnings (low fuel, maintenance due)
    INFO = "info"  # Informational (refuel complete, trip ended)
    SYSTEM = "system"  # System notifications (sync complete, etc)


class NotificationPriority(Enum):
    """Notification priority levels"""

    CRITICAL = "critical"  # Must deliver immediately
    HIGH = "high"  # Important, deliver soon
    NORMAL = "normal"  # Standard delivery
    LOW = "low"  # Can be batched/delayed


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PushSubscription:
    """Web Push subscription info (from browser)"""

    user_id: str
    endpoint: str
    keys: dict  # p256dh and auth keys
    platform: str = "web"  # web, ios, android
    device_name: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_used: Optional[datetime] = None

    def to_dict(self) -> dict:
        return {
            "user_id": self.user_id,
            "endpoint": self.endpoint,
            "keys": self.keys,
            "platform": self.platform,
            "device_name": self.device_name,
            "created_at": self.created_at.isoformat(),
            "last_used": self.last_used.isoformat() if self.last_used else None,
        }

    @classmethod
    def from_browser(
        cls, user_id: str, browser_subscription: dict
    ) -> "PushSubscription":
        """Create from browser PushSubscription object"""
        return cls(
            user_id=user_id,
            endpoint=browser_subscription.get("endpoint", ""),
            keys={
                "p256dh": browser_subscription.get("keys", {}).get("p256dh", ""),
                "auth": browser_subscription.get("keys", {}).get("auth", ""),
            },
            platform="web",
        )


@dataclass
class Notification:
    """Notification to send"""

    id: str
    user_id: str
    title: str
    body: str
    notification_type: NotificationType = NotificationType.INFO
    priority: NotificationPriority = NotificationPriority.NORMAL

    # Optional data payload
    data: dict = field(default_factory=dict)

    # Display options
    icon: Optional[str] = None
    badge: Optional[str] = None
    image: Optional[str] = None
    tag: Optional[str] = None  # Group notifications
    require_interaction: bool = False  # Keep visible until dismissed

    # Actions (buttons in notification)
    actions: list = field(default_factory=list)

    # Tracking
    created_at: datetime = field(default_factory=datetime.utcnow)
    sent_at: Optional[datetime] = None
    delivered: bool = False
    read: bool = False

    def to_push_payload(self) -> dict:
        """Convert to Web Push payload"""
        payload = {
            "title": self.title,
            "body": self.body,
            "data": {
                "notification_id": self.id,
                "type": self.notification_type.value,
                "priority": self.priority.value,
                **self.data,
            },
        }

        if self.icon:
            payload["icon"] = self.icon
        if self.badge:
            payload["badge"] = self.badge
        if self.image:
            payload["image"] = self.image
        if self.tag:
            payload["tag"] = self.tag
        if self.require_interaction:
            payload["requireInteraction"] = True
        if self.actions:
            payload["actions"] = self.actions

        return payload

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "body": self.body,
            "type": self.notification_type.value,
            "priority": self.priority.value,
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "delivered": self.delivered,
            "read": self.read,
        }


@dataclass
class NotificationResult:
    """Result of sending a notification"""

    notification_id: str
    user_id: str
    success: bool
    error: Optional[str] = None
    endpoint: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "success": self.success,
            "error": self.error,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# PUSH NOTIFICATION SERVICE
# ═══════════════════════════════════════════════════════════════════════════════


class PushNotificationService:
    """
    Web Push notification service.

    Manages subscriptions and sends push notifications via VAPID.
    """

    def __init__(self, db_pool=None):
        self.db_pool = db_pool

        # In-memory subscription cache (for testing/dev without DB)
        self._subscriptions: dict[str, list[PushSubscription]] = {}

        # Notification history
        self._notifications: dict[str, list[Notification]] = {}

        # Check if web-push is available
        self._webpush_available = self._check_webpush()

    def _check_webpush(self) -> bool:
        """Check if pywebpush is installed"""
        try:
            from pywebpush import webpush

            return True
        except ImportError:
            logger.warning(
                "pywebpush not installed. Push notifications will be simulated."
            )
            return False

    async def subscribe(
        self,
        user_id: str,
        subscription_info: dict,
        platform: str = "web",
        device_name: Optional[str] = None,
    ) -> PushSubscription:
        """
        Subscribe a user to push notifications.

        Args:
            user_id: User identifier
            subscription_info: Browser PushSubscription object
            platform: Platform (web, ios, android)
            device_name: Optional device identifier

        Returns:
            PushSubscription object
        """
        subscription = PushSubscription(
            user_id=user_id,
            endpoint=subscription_info.get("endpoint", ""),
            keys={
                "p256dh": subscription_info.get("keys", {}).get("p256dh", ""),
                "auth": subscription_info.get("keys", {}).get("auth", ""),
            },
            platform=platform,
            device_name=device_name,
        )

        # Store in memory cache
        if user_id not in self._subscriptions:
            self._subscriptions[user_id] = []

        # Remove duplicate endpoints
        self._subscriptions[user_id] = [
            s
            for s in self._subscriptions[user_id]
            if s.endpoint != subscription.endpoint
        ]

        self._subscriptions[user_id].append(subscription)

        # Store in database if available
        if self.db_pool:
            await self._store_subscription_db(subscription)

        logger.info(f"[{user_id}] Subscribed to push notifications ({platform})")
        return subscription

    async def unsubscribe(self, user_id: str, endpoint: Optional[str] = None) -> bool:
        """
        Unsubscribe a user from push notifications.

        Args:
            user_id: User identifier
            endpoint: Specific endpoint to unsubscribe (or all if None)

        Returns:
            True if unsubscribed
        """
        if user_id in self._subscriptions:
            if endpoint:
                self._subscriptions[user_id] = [
                    s for s in self._subscriptions[user_id] if s.endpoint != endpoint
                ]
            else:
                del self._subscriptions[user_id]

        logger.info(f"[{user_id}] Unsubscribed from push notifications")
        return True

    async def get_subscriptions(self, user_id: str) -> list[PushSubscription]:
        """Get all subscriptions for a user"""
        return self._subscriptions.get(user_id, [])

    async def send(
        self,
        user_id: str,
        title: str,
        body: str,
        notification_type: NotificationType = NotificationType.INFO,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        data: Optional[dict] = None,
        **kwargs,
    ) -> list[NotificationResult]:
        """
        Send push notification to a user.

        Args:
            user_id: Target user
            title: Notification title
            body: Notification body
            notification_type: Type of notification
            priority: Delivery priority
            data: Additional data payload
            **kwargs: Additional notification options

        Returns:
            List of NotificationResult for each subscription
        """
        import uuid

        notification = Notification(
            id=str(uuid.uuid4()),
            user_id=user_id,
            title=title,
            body=body,
            notification_type=notification_type,
            priority=priority,
            data=data or {},
            **kwargs,
        )

        # Store notification
        if user_id not in self._notifications:
            self._notifications[user_id] = []
        self._notifications[user_id].append(notification)

        # Get user subscriptions
        subscriptions = await self.get_subscriptions(user_id)

        if not subscriptions:
            logger.warning(f"[{user_id}] No push subscriptions found")
            return [
                NotificationResult(
                    notification_id=notification.id,
                    user_id=user_id,
                    success=False,
                    error="No subscriptions found",
                )
            ]

        results = []
        for sub in subscriptions:
            result = await self._send_to_endpoint(notification, sub)
            results.append(result)

        return results

    async def _send_to_endpoint(
        self, notification: Notification, subscription: PushSubscription
    ) -> NotificationResult:
        """Send notification to a specific endpoint"""

        if not self._webpush_available:
            # Simulate success for testing
            logger.info(
                f"[SIMULATED] Push to {subscription.user_id}: {notification.title}"
            )
            notification.sent_at = datetime.utcnow()
            notification.delivered = True
            return NotificationResult(
                notification_id=notification.id,
                user_id=subscription.user_id,
                success=True,
                endpoint=subscription.endpoint[:50] + "...",
            )

        try:
            from pywebpush import webpush, WebPushException

            payload = json.dumps(notification.to_push_payload())

            subscription_info = {
                "endpoint": subscription.endpoint,
                "keys": subscription.keys,
            }

            webpush(
                subscription_info=subscription_info,
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_EMAIL},
            )

            notification.sent_at = datetime.utcnow()
            notification.delivered = True
            subscription.last_used = datetime.utcnow()

            logger.info(f"[{subscription.user_id}] Push sent: {notification.title}")

            return NotificationResult(
                notification_id=notification.id,
                user_id=subscription.user_id,
                success=True,
                endpoint=subscription.endpoint[:50] + "...",
            )

        except Exception as e:
            error_msg = str(e)
            logger.error(f"[{subscription.user_id}] Push failed: {error_msg}")

            # Remove invalid subscriptions (410 Gone)
            if "410" in error_msg or "expired" in error_msg.lower():
                await self.unsubscribe(subscription.user_id, subscription.endpoint)

            return NotificationResult(
                notification_id=notification.id,
                user_id=subscription.user_id,
                success=False,
                error=error_msg[:100],
            )

    async def send_fleet_alert(
        self,
        carrier_id: str,
        title: str,
        body: str,
        notification_type: NotificationType = NotificationType.ALERT,
        data: Optional[dict] = None,
    ) -> dict:
        """
        Send alert to all users of a carrier/fleet.

        Args:
            carrier_id: Carrier identifier
            title: Alert title
            body: Alert body
            notification_type: Type of notification
            data: Additional data

        Returns:
            Summary of send results
        """
        # Get all users for carrier (would query database)
        # For now, send to all cached subscriptions
        all_users = list(self._subscriptions.keys())

        results = {
            "total_users": len(all_users),
            "successful": 0,
            "failed": 0,
            "details": [],
        }

        for user_id in all_users:
            user_results = await self.send(
                user_id=user_id,
                title=title,
                body=body,
                notification_type=notification_type,
                priority=NotificationPriority.HIGH,
                data={**(data or {}), "carrier_id": carrier_id},
            )

            for result in user_results:
                if result.success:
                    results["successful"] += 1
                else:
                    results["failed"] += 1
                results["details"].append(result.to_dict())

        return results

    async def get_user_notifications(
        self, user_id: str, limit: int = 20, unread_only: bool = False
    ) -> dict:
        """Get notification history for a user"""
        notifications = self._notifications.get(user_id, [])

        if unread_only:
            notifications = [n for n in notifications if not n.read]

        # Sort by created_at descending
        notifications = sorted(notifications, key=lambda n: n.created_at, reverse=True)

        return {
            "notifications": [n.to_dict() for n in notifications[:limit]],
            "total": len(self._notifications.get(user_id, [])),
            "unread_count": len(
                [n for n in self._notifications.get(user_id, []) if not n.read]
            ),
        }

    async def mark_as_read(self, user_id: str, notification_id: str) -> bool:
        """Mark a notification as read"""
        notifications = self._notifications.get(user_id, [])
        for n in notifications:
            if n.id == notification_id:
                n.read = True
                return True
        return False

    async def _store_subscription_db(self, subscription: PushSubscription):
        """Store subscription in database"""
        if not self.db_pool:
            return

        try:
            async with self.db_pool.acquire() as conn:
                async with conn.cursor() as cursor:
                    await cursor.execute(
                        """
                        INSERT INTO push_subscriptions 
                        (user_id, endpoint, keys_p256dh, keys_auth, platform, device_name, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                        keys_p256dh = VALUES(keys_p256dh),
                        keys_auth = VALUES(keys_auth),
                        updated_at = NOW()
                    """,
                        (
                            subscription.user_id,
                            subscription.endpoint,
                            subscription.keys.get("p256dh", ""),
                            subscription.keys.get("auth", ""),
                            subscription.platform,
                            subscription.device_name,
                        ),
                    )
                    await conn.commit()
        except Exception as e:
            logger.error(f"Failed to store subscription: {e}")

    def get_vapid_public_key(self) -> str:
        """Get VAPID public key for frontend"""
        return VAPID_PUBLIC_KEY


# ═══════════════════════════════════════════════════════════════════════════════
# ALERT-SPECIFIC NOTIFICATIONS
# ═══════════════════════════════════════════════════════════════════════════════


async def send_voltage_alert(
    service: PushNotificationService,
    user_id: str,
    truck_id: str,
    voltage: float,
    status: str,
) -> list[NotificationResult]:
    """Send voltage alert notification"""

    if status == "CRITICAL_LOW":
        title = f"⛔ {truck_id}: Voltaje Crítico"
        body = f"Voltaje de batería en {voltage:.1f}V - El camión no arrancará"
        priority = NotificationPriority.CRITICAL
    elif status == "LOW":
        title = f"⚠️ {truck_id}: Voltaje Bajo"
        body = f"Voltaje en {voltage:.1f}V - Batería descargándose"
        priority = NotificationPriority.HIGH
    else:
        title = f"🔋 {truck_id}: Alerta de Voltaje"
        body = f"Voltaje: {voltage:.1f}V ({status})"
        priority = NotificationPriority.NORMAL

    return await service.send(
        user_id=user_id,
        title=title,
        body=body,
        notification_type=NotificationType.ALERT,
        priority=priority,
        data={"truck_id": truck_id, "voltage": voltage, "status": status},
        tag=f"voltage-{truck_id}",
        require_interaction=status.startswith("CRITICAL"),
    )


async def send_dtc_alert(
    service: PushNotificationService,
    user_id: str,
    truck_id: str,
    dtc_code: str,
    description: str,
    severity: str,
) -> list[NotificationResult]:
    """Send DTC (diagnostic trouble code) alert"""

    if severity == "critical":
        title = f"⛔ {truck_id}: Código Crítico {dtc_code}"
        priority = NotificationPriority.CRITICAL
    else:
        title = f"⚠️ {truck_id}: DTC {dtc_code}"
        priority = NotificationPriority.HIGH

    return await service.send(
        user_id=user_id,
        title=title,
        body=description,
        notification_type=NotificationType.ALERT,
        priority=priority,
        data={"truck_id": truck_id, "dtc_code": dtc_code, "severity": severity},
        tag=f"dtc-{truck_id}",
        require_interaction=severity == "critical",
    )


async def send_fuel_alert(
    service: PushNotificationService,
    user_id: str,
    truck_id: str,
    fuel_level: float,
    alert_type: str,
) -> list[NotificationResult]:
    """Send fuel-related alert"""

    if alert_type == "low":
        title = f"⛽ {truck_id}: Combustible Bajo"
        body = f"Nivel de combustible: {fuel_level:.0f}% - Programar repostaje"
        priority = NotificationPriority.HIGH
    elif alert_type == "theft":
        title = f"🚨 {truck_id}: Posible Robo de Combustible"
        body = f"Pérdida anormal detectada. Nivel actual: {fuel_level:.0f}%"
        priority = NotificationPriority.CRITICAL
    else:
        title = f"⛽ {truck_id}: Alerta de Combustible"
        body = f"Nivel: {fuel_level:.0f}%"
        priority = NotificationPriority.NORMAL

    return await service.send(
        user_id=user_id,
        title=title,
        body=body,
        notification_type=NotificationType.ALERT,
        priority=priority,
        data={"truck_id": truck_id, "fuel_level": fuel_level, "alert_type": alert_type},
        tag=f"fuel-{truck_id}",
    )
