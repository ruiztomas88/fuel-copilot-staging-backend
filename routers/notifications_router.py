"""
Notifications Router - v3.12.21
Push notifications management endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any, List
import logging
from timezone_utils import utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Notifications"])

# In-memory storage for notifications
_push_subscriptions: Dict[str, Dict] = {}
_notification_queue: List[Dict] = []


@router.post("/notifications/subscribe")
async def subscribe_to_push(subscription: Dict[str, Any]):
    """
    🆕 v3.12.21: Subscribe a device to push notifications.
    """
    user_id = subscription.get("user_id")
    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required")

    subscription["subscribed_at"] = utc_now().isoformat()
    subscription["active"] = True

    _push_subscriptions[user_id] = subscription

    logger.info(f"🔔 Push subscription added for user {user_id}")
    return {"status": "subscribed", "user_id": user_id}


@router.delete("/notifications/unsubscribe/{user_id}")
async def unsubscribe_from_push(user_id: str):
    """
    🆕 v3.12.21: Unsubscribe a device from push notifications.
    """
    if user_id in _push_subscriptions:
        del _push_subscriptions[user_id]

    return {"status": "unsubscribed", "user_id": user_id}


@router.get("/notifications/{user_id}")
async def get_user_notifications(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
):
    """
    🆕 v3.12.21: Get notifications for a user.
    """
    user_notifications = [
        n
        for n in _notification_queue
        if n.get("user_id") == user_id or n.get("broadcast", False)
    ]

    if unread_only:
        user_notifications = [n for n in user_notifications if not n.get("read", False)]

    return {
        "notifications": user_notifications[-limit:],
        "total": len(user_notifications),
        "unread_count": len(
            [n for n in user_notifications if not n.get("read", False)]
        ),
    }


@router.post("/notifications/send")
async def send_notification(notification: Dict[str, Any]):
    """
    🆕 v3.12.21: Send a push notification.

    For internal/admin use to send alerts to users.
    """
    import uuid

    notification["id"] = f"notif-{uuid.uuid4().hex[:8]}"
    notification["created_at"] = utc_now().isoformat()
    notification["read"] = False

    _notification_queue.append(notification)

    if len(_notification_queue) > 1000:
        _notification_queue.pop(0)

    target = notification.get("user_id", "broadcast")
    logger.info(
        f"📨 Notification sent to {target}: {notification.get('title', 'No title')}"
    )

    return {"status": "sent", "notification_id": notification["id"]}


@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str):
    """
    🆕 v3.12.21: Mark a notification as read.
    """
    for notification in _notification_queue:
        if notification.get("id") == notification_id:
            notification["read"] = True
            notification["read_at"] = utc_now().isoformat()
            return {"status": "marked_read", "notification_id": notification_id}

    raise HTTPException(status_code=404, detail="Notification not found")


@router.post("/notifications/{user_id}/read-all")
async def mark_all_notifications_read(user_id: str):
    """
    🆕 v3.12.21: Mark all notifications as read for a user.
    """
    count = 0
    for notification in _notification_queue:
        if notification.get("user_id") == user_id or notification.get(
            "broadcast", False
        ):
            if not notification.get("read", False):
                notification["read"] = True
                notification["read_at"] = utc_now().isoformat()
                count += 1

    return {"status": "success", "marked_read": count}
