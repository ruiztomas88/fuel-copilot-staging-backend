"""
sse_endpoints.py - Server-Sent Events for Real-Time Updates
Addresses audit item #13: WebSocket → SSE
Version: 3.12.21
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import AsyncGenerator, Optional, Dict, Any
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sse", tags=["SSE"])


class SSEManager:
    """Manages Server-Sent Events connections and broadcasting."""

    def __init__(self):
        self.active_connections: Dict[str, set] = {
            "fleet": set(),
            "alerts": set(),
            "metrics": set(),
        }
        self.last_data: Dict[str, Any] = {}

    async def connect(self, channel: str, client_id: str):
        """Register a client connection."""
        if channel not in self.active_connections:
            self.active_connections[channel] = set()
        self.active_connections[channel].add(client_id)
        logger.info(
            f"SSE client {client_id} connected to {channel}. Total: {len(self.active_connections[channel])}"
        )

    async def disconnect(self, channel: str, client_id: str):
        """Remove a client connection."""
        if channel in self.active_connections:
            self.active_connections[channel].discard(client_id)
            logger.info(f"SSE client {client_id} disconnected from {channel}")

    def format_sse(
        self, data: Any, event: Optional[str] = None, id: Optional[str] = None
    ) -> str:
        """Format data as SSE message."""
        lines = []
        if id:
            lines.append(f"id: {id}")
        if event:
            lines.append(f"event: {event}")

        if isinstance(data, dict):
            data_str = json.dumps(data)
        else:
            data_str = str(data)

        lines.append(f"data: {data_str}")
        lines.append("")  # Empty line to end message
        return "\n".join(lines) + "\n"

    def format_heartbeat(self) -> str:
        """Format heartbeat message to keep connection alive."""
        return f": heartbeat {datetime.utcnow().isoformat()}\n\n"


sse_manager = SSEManager()


async def get_fleet_updates() -> AsyncGenerator[Dict[str, Any], None]:
    """Generate fleet status updates from database."""
    from database_pool import get_db_connection

    while True:
        try:
            async with get_db_connection() as conn:
                # Get latest metrics per truck
                result = await conn.execute(
                    """
                    SELECT 
                        m.truck_id,
                        m.sensor_pct,
                        m.estimated_pct,
                        m.mpg_current,
                        m.speed_mph,
                        m.truck_status,
                        m.latitude,
                        m.longitude,
                        m.timestamp_utc
                    FROM fuel_metrics m
                    INNER JOIN (
                        SELECT truck_id, MAX(timestamp_utc) as max_ts
                        FROM fuel_metrics
                        WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
                        GROUP BY truck_id
                    ) latest ON m.truck_id = latest.truck_id 
                        AND m.timestamp_utc = latest.max_ts
                """
                )

                trucks = []
                for row in result:
                    trucks.append(
                        {
                            "truck_id": row.truck_id,
                            "fuel_pct": round(
                                row.estimated_pct or row.sensor_pct or 0, 1
                            ),
                            "mpg": round(row.mpg_current or 0, 2),
                            "speed": round(row.speed_mph or 0, 1),
                            "status": row.truck_status or "unknown",
                            "location": (
                                {"lat": row.latitude, "lng": row.longitude}
                                if row.latitude and row.longitude
                                else None
                            ),
                            "last_update": (
                                row.timestamp_utc.isoformat()
                                if row.timestamp_utc
                                else None
                            ),
                        }
                    )

                yield {
                    "type": "fleet_update",
                    "timestamp": datetime.utcnow().isoformat(),
                    "truck_count": len(trucks),
                    "trucks": trucks,
                }

        except Exception as e:
            logger.error(f"Error fetching fleet updates: {e}")
            yield {
                "type": "error",
                "message": "Failed to fetch fleet data",
                "timestamp": datetime.utcnow().isoformat(),
            }

        await asyncio.sleep(5)  # Update every 5 seconds


async def get_alert_updates() -> AsyncGenerator[Dict[str, Any], None]:
    """Generate alert updates from database."""
    from database_pool import get_db_connection

    last_check = datetime.utcnow() - timedelta(minutes=5)

    while True:
        try:
            async with get_db_connection() as conn:
                # Get new alerts since last check
                result = await conn.execute(
                    """
                    SELECT 
                        id,
                        truck_id,
                        alert_type,
                        severity,
                        message,
                        created_at,
                        resolved,
                        resolved_at
                    FROM alerts
                    WHERE created_at > :last_check
                    ORDER BY created_at DESC
                    LIMIT 50
                """,
                    {"last_check": last_check},
                )

                alerts = []
                for row in result:
                    alerts.append(
                        {
                            "id": row.id,
                            "truck_id": row.truck_id,
                            "alert_type": row.alert_type,
                            "severity": row.severity,
                            "message": row.message,
                            "created_at": (
                                row.created_at.isoformat() if row.created_at else None
                            ),
                            "resolved": row.resolved,
                            "resolved_at": (
                                row.resolved_at.isoformat() if row.resolved_at else None
                            ),
                        }
                    )

                if alerts:
                    yield {
                        "type": "new_alerts",
                        "timestamp": datetime.utcnow().isoformat(),
                        "count": len(alerts),
                        "alerts": alerts,
                    }
                else:
                    yield {
                        "type": "heartbeat",
                        "timestamp": datetime.utcnow().isoformat(),
                    }

                last_check = datetime.utcnow()

        except Exception as e:
            logger.error(f"Error fetching alert updates: {e}")
            yield {
                "type": "error",
                "message": "Failed to fetch alerts",
                "timestamp": datetime.utcnow().isoformat(),
            }

        await asyncio.sleep(3)  # Check for alerts every 3 seconds


async def get_truck_metrics_stream(
    truck_id: str,
) -> AsyncGenerator[Dict[str, Any], None]:
    """Generate real-time metrics for a specific truck."""
    from database_pool import get_db_connection

    while True:
        try:
            async with get_db_connection() as conn:
                result = await conn.execute(
                    """
                    SELECT 
                        sensor_pct,
                        estimated_pct,
                        fuel_gallons,
                        mpg_current,
                        mpg_ema,
                        speed_mph,
                        mileage_delta,
                        truck_status,
                        idle_duration_minutes,
                        latitude,
                        longitude,
                        anomaly_score,
                        timestamp_utc
                    FROM fuel_metrics
                    WHERE truck_id = :truck_id
                    ORDER BY timestamp_utc DESC
                    LIMIT 1
                """,
                    {"truck_id": truck_id},
                )

                row = result.fetchone()

                if row:
                    yield {
                        "type": "truck_metrics",
                        "truck_id": truck_id,
                        "timestamp": datetime.utcnow().isoformat(),
                        "metrics": {
                            "fuel": {
                                "sensor_pct": round(row.sensor_pct or 0, 1),
                                "estimated_pct": round(row.estimated_pct or 0, 1),
                                "gallons": round(row.fuel_gallons or 0, 1),
                            },
                            "performance": {
                                "mpg_current": round(row.mpg_current or 0, 2),
                                "mpg_ema": round(row.mpg_ema or 0, 2),
                                "speed_mph": round(row.speed_mph or 0, 1),
                            },
                            "status": row.truck_status or "unknown",
                            "idle_minutes": row.idle_duration_minutes or 0,
                            "location": (
                                {"lat": row.latitude, "lng": row.longitude}
                                if row.latitude and row.longitude
                                else None
                            ),
                            "anomaly_score": round(row.anomaly_score or 0, 3),
                        },
                    }
                else:
                    yield {
                        "type": "no_data",
                        "truck_id": truck_id,
                        "timestamp": datetime.utcnow().isoformat(),
                    }

        except Exception as e:
            logger.error(f"Error fetching truck metrics: {e}")
            yield {
                "type": "error",
                "message": f"Failed to fetch metrics for {truck_id}",
                "timestamp": datetime.utcnow().isoformat(),
            }

        await asyncio.sleep(2)  # Update every 2 seconds for individual truck


@router.get("/fleet")
async def sse_fleet_stream(
    request: Request, current_user: dict = Depends(get_current_user)
):
    """
    Server-Sent Events stream for fleet-wide updates.

    Provides real-time updates on all trucks including:
    - Fuel levels
    - Current speed
    - MPG
    - Location
    - Status changes

    Updates every 5 seconds.
    """
    client_id = f"{current_user.get('sub', 'anon')}_{datetime.utcnow().timestamp()}"

    async def event_generator():
        await sse_manager.connect("fleet", client_id)
        try:
            async for update in get_fleet_updates():
                # Check if client disconnected
                if await request.is_disconnected():
                    break

                yield sse_manager.format_sse(
                    data=update,
                    event="fleet_update",
                    id=str(datetime.utcnow().timestamp()),
                )
        finally:
            await sse_manager.disconnect("fleet", client_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/alerts")
async def sse_alerts_stream(
    request: Request, current_user: dict = Depends(get_current_user)
):
    """
    Server-Sent Events stream for real-time alerts.

    Provides instant notification when:
    - New alerts are created
    - Alert severity changes
    - Alerts are resolved

    Checks for new alerts every 3 seconds.
    """
    client_id = f"{current_user.get('sub', 'anon')}_{datetime.utcnow().timestamp()}"

    async def event_generator():
        await sse_manager.connect("alerts", client_id)
        try:
            async for update in get_alert_updates():
                if await request.is_disconnected():
                    break

                event_type = (
                    "heartbeat" if update.get("type") == "heartbeat" else "alert"
                )
                yield sse_manager.format_sse(
                    data=update, event=event_type, id=str(datetime.utcnow().timestamp())
                )
        finally:
            await sse_manager.disconnect("alerts", client_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/truck/{truck_id}")
async def sse_truck_stream(
    request: Request, truck_id: str, current_user: dict = Depends(get_current_user)
):
    """
    Server-Sent Events stream for individual truck metrics.

    Provides high-frequency updates (every 2 seconds) for:
    - Fuel sensor readings
    - Estimated fuel levels
    - Current MPG
    - Speed
    - Location
    - Anomaly scores
    """
    client_id = (
        f"{current_user.get('sub', 'anon')}_{truck_id}_{datetime.utcnow().timestamp()}"
    )

    async def event_generator():
        await sse_manager.connect("metrics", client_id)
        try:
            async for update in get_truck_metrics_stream(truck_id):
                if await request.is_disconnected():
                    break

                yield sse_manager.format_sse(
                    data=update,
                    event="truck_metrics",
                    id=str(datetime.utcnow().timestamp()),
                )
        finally:
            await sse_manager.disconnect("metrics", client_id)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/connections")
async def get_sse_connections(current_user: dict = Depends(get_current_user)):
    """Get current SSE connection statistics (admin only)."""
    if current_user.get("role") != "super_admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    return {
        "connections": {
            channel: len(clients)
            for channel, clients in sse_manager.active_connections.items()
        },
        "total": sum(len(c) for c in sse_manager.active_connections.values()),
    }
