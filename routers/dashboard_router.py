"""
Dashboard Router - v3.12.21
Dashboard customization and widget management endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Dict, Any
import logging
from datetime import datetime, timezone
from timezone_utils import utc_now

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Dashboard"])

# In-memory storage for user dashboards (replace with DB in production)
_user_dashboards: Dict[str, Dict] = {}
_user_preferences: Dict[str, Dict] = {}


@router.get("/dashboard/widgets/available")
async def get_available_widgets():
    """
    🆕 v3.12.21: Get list of available widget types for dashboard customization.
    """
    from models import WidgetType, WidgetSize

    widgets = [
        {
            "type": WidgetType.FLEET_SUMMARY.value,
            "name": "Fleet Summary",
            "description": "Overview of fleet status, active/offline trucks",
            "default_size": WidgetSize.LARGE.value,
            "available_sizes": [WidgetSize.MEDIUM.value, WidgetSize.LARGE.value],
            "config_options": ["showOffline", "showAlerts"],
        },
        {
            "type": WidgetType.TRUCK_MAP.value,
            "name": "Truck Map",
            "description": "Real-time GPS locations of all trucks",
            "default_size": WidgetSize.LARGE.value,
            "available_sizes": [WidgetSize.LARGE.value, WidgetSize.FULL_WIDTH.value],
            "config_options": ["showLabels", "clusterMarkers"],
        },
        {
            "type": WidgetType.EFFICIENCY_CHART.value,
            "name": "Efficiency Chart",
            "description": "MPG and fuel consumption trends",
            "default_size": WidgetSize.MEDIUM.value,
            "available_sizes": [
                WidgetSize.SMALL.value,
                WidgetSize.MEDIUM.value,
                WidgetSize.LARGE.value,
            ],
            "config_options": ["period", "showTrend"],
        },
        {
            "type": WidgetType.FUEL_LEVELS.value,
            "name": "Fuel Levels",
            "description": "Current fuel levels across fleet",
            "default_size": WidgetSize.MEDIUM.value,
            "available_sizes": [WidgetSize.SMALL.value, WidgetSize.MEDIUM.value],
            "config_options": ["sortBy", "lowFuelThreshold"],
        },
        {
            "type": WidgetType.ALERTS.value,
            "name": "Alerts",
            "description": "Active alerts and notifications",
            "default_size": WidgetSize.SMALL.value,
            "available_sizes": [WidgetSize.SMALL.value, WidgetSize.MEDIUM.value],
            "config_options": ["severityFilter", "limit"],
        },
        {
            "type": WidgetType.MPG_RANKING.value,
            "name": "MPG Ranking",
            "description": "Top/bottom performers by MPG",
            "default_size": WidgetSize.SMALL.value,
            "available_sizes": [WidgetSize.SMALL.value, WidgetSize.MEDIUM.value],
            "config_options": ["topN", "showBottom"],
        },
        {
            "type": WidgetType.IDLE_TRACKING.value,
            "name": "Idle Tracking",
            "description": "Idle time and consumption analysis",
            "default_size": WidgetSize.MEDIUM.value,
            "available_sizes": [WidgetSize.SMALL.value, WidgetSize.MEDIUM.value],
            "config_options": ["period", "threshold"],
        },
        {
            "type": WidgetType.REFUEL_HISTORY.value,
            "name": "Refuel History",
            "description": "Recent refueling events",
            "default_size": WidgetSize.MEDIUM.value,
            "available_sizes": [
                WidgetSize.SMALL.value,
                WidgetSize.MEDIUM.value,
                WidgetSize.LARGE.value,
            ],
            "config_options": ["limit", "showCost"],
        },
        {
            "type": WidgetType.PREDICTIONS.value,
            "name": "Predictions",
            "description": "Fuel consumption and empty tank predictions",
            "default_size": WidgetSize.MEDIUM.value,
            "available_sizes": [WidgetSize.MEDIUM.value, WidgetSize.LARGE.value],
            "config_options": ["predictionHours", "showRange"],
        },
        {
            "type": WidgetType.HEALTH_MONITOR.value,
            "name": "Health Monitor",
            "description": "Truck health scores and anomaly detection",
            "default_size": WidgetSize.LARGE.value,
            "available_sizes": [WidgetSize.MEDIUM.value, WidgetSize.LARGE.value],
            "config_options": ["alertsOnly", "showTrends"],
        },
    ]

    return {"widgets": widgets, "total": len(widgets)}


@router.get("/dashboard/layout/{user_id}")
async def get_dashboard_layout(user_id: str):
    """
    🆕 v3.12.21: Get user's dashboard layout configuration.
    """
    if user_id in _user_dashboards:
        return _user_dashboards[user_id]

    from models import WidgetType, WidgetSize

    default_layout = {
        "user_id": user_id,
        "name": "Default Dashboard",
        "columns": 4,
        "theme": "dark",
        "widgets": [
            {
                "id": "widget-1",
                "widget_type": WidgetType.FLEET_SUMMARY.value,
                "title": "Fleet Overview",
                "size": WidgetSize.LARGE.value,
                "position": {"x": 0, "y": 0},
                "config": {},
                "visible": True,
            },
            {
                "id": "widget-2",
                "widget_type": WidgetType.ALERTS.value,
                "title": "Active Alerts",
                "size": WidgetSize.SMALL.value,
                "position": {"x": 2, "y": 0},
                "config": {"limit": 5},
                "visible": True,
            },
            {
                "id": "widget-3",
                "widget_type": WidgetType.EFFICIENCY_CHART.value,
                "title": "Fleet Efficiency",
                "size": WidgetSize.MEDIUM.value,
                "position": {"x": 0, "y": 2},
                "config": {"period": "24h"},
                "visible": True,
            },
            {
                "id": "widget-4",
                "widget_type": WidgetType.MPG_RANKING.value,
                "title": "Top Performers",
                "size": WidgetSize.SMALL.value,
                "position": {"x": 2, "y": 2},
                "config": {"topN": 5},
                "visible": True,
            },
        ],
        "created_at": utc_now().isoformat(),
        "updated_at": utc_now().isoformat(),
    }

    return default_layout


@router.post("/dashboard/layout/{user_id}")
async def save_dashboard_layout(user_id: str, layout: Dict[str, Any]):
    """
    🆕 v3.12.21: Save user's dashboard layout configuration.
    """
    layout["user_id"] = user_id
    layout["updated_at"] = utc_now().isoformat()

    if user_id not in _user_dashboards:
        layout["created_at"] = utc_now().isoformat()
    else:
        layout["created_at"] = _user_dashboards[user_id].get(
            "created_at", utc_now().isoformat()
        )

    _user_dashboards[user_id] = layout

    logger.info(f"📊 Dashboard layout saved for user {user_id}")
    return {"status": "saved", "layout": layout}


@router.put("/dashboard/widget/{user_id}/{widget_id}")
async def update_widget(user_id: str, widget_id: str, widget_config: Dict[str, Any]):
    """
    🆕 v3.12.21: Update a specific widget's configuration.
    """
    if user_id not in _user_dashboards:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    dashboard = _user_dashboards[user_id]
    widget_found = False

    for widget in dashboard.get("widgets", []):
        if widget["id"] == widget_id:
            widget.update(widget_config)
            widget_found = True
            break

    if not widget_found:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")

    dashboard["updated_at"] = utc_now().isoformat()
    return {"status": "updated", "widget_id": widget_id}


@router.delete("/dashboard/widget/{user_id}/{widget_id}")
async def delete_widget(user_id: str, widget_id: str):
    """
    🆕 v3.12.21: Remove a widget from user's dashboard.
    """
    if user_id not in _user_dashboards:
        raise HTTPException(status_code=404, detail="Dashboard not found")

    dashboard = _user_dashboards[user_id]
    original_count = len(dashboard.get("widgets", []))

    dashboard["widgets"] = [
        w for w in dashboard.get("widgets", []) if w["id"] != widget_id
    ]

    if len(dashboard["widgets"]) == original_count:
        raise HTTPException(status_code=404, detail=f"Widget {widget_id} not found")

    dashboard["updated_at"] = utc_now().isoformat()
    return {"status": "deleted", "widget_id": widget_id}


@router.get("/user/preferences/{user_id}")
async def get_user_preferences(user_id: str):
    """
    🆕 v3.12.21: Get user preferences.
    """
    if user_id in _user_preferences:
        return _user_preferences[user_id]

    return {
        "user_id": user_id,
        "default_dashboard": None,
        "favorite_trucks": [],
        "alert_settings": {
            "email_alerts": False,
            "sms_alerts": False,
            "push_notifications": True,
            "severity_filter": ["critical", "warning"],
        },
        "timezone": "America/Chicago",
        "units": "imperial",
        "notifications_enabled": True,
        "email_reports": False,
        "report_frequency": "daily",
    }


@router.put("/user/preferences/{user_id}")
async def update_user_preferences(user_id: str, preferences: Dict[str, Any]):
    """
    🆕 v3.12.21: Update user preferences.
    """
    preferences["user_id"] = user_id
    _user_preferences[user_id] = preferences

    logger.info(f"⚙️ Preferences updated for user {user_id}")
    return {"status": "updated", "preferences": preferences}
