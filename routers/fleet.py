"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                          FLEET ROUTER                                          ║
║                    Fleet Management API Endpoints                              ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Endpoints:                                                                    ║
║  - /trucks (get all trucks)                                                    ║
║  - /fleet-summary (fleet overview)                                             ║
║  - /truck/{truck_id}/details (single truck details)                            ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Query, HTTPException
import pymysql

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fuelAnalytics/api",
    tags=["Fleet Management"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_wialon_connection():
    """Get connection to Wialon DB"""
    return pymysql.connect(
        host=os.getenv("WIALON_DB_HOST", "localhost"),
        port=int(os.getenv("WIALON_DB_PORT", "3306")),
        user=os.getenv("WIALON_DB_USER", ""),
        password=os.getenv("WIALON_DB_PASS", ""),
        database=os.getenv("WIALON_DB_NAME", "wialon_collect"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/trucks")
async def get_trucks(
    active_only: bool = Query(True, description="Only show trucks with recent data"),
    hours: int = Query(24, description="Hours to look back for activity"),
):
    """
    Get list of all trucks in the fleet.

    Returns:
        List of trucks with their current status
    """
    try:
        conn = get_wialon_connection()

        with conn.cursor() as cursor:
            query = """
                SELECT DISTINCT 
                    unit,
                    n as truck_name,
                    MAX(m) as last_seen
                FROM sensors
                WHERE 1=1
            """
            params = []

            if active_only:
                query += " AND m >= UNIX_TIMESTAMP() - %s"
                params.append(hours * 3600)

            query += " GROUP BY unit, n ORDER BY n"

            cursor.execute(query, params)
            rows = cursor.fetchall()

        conn.close()

        trucks = []
        for row in rows:
            last_seen = None
            if row.get("last_seen"):
                last_seen = datetime.fromtimestamp(
                    row["last_seen"], tz=timezone.utc
                ).isoformat()

            trucks.append(
                {
                    "unit_id": row["unit"],
                    "truck_id": row["truck_name"] or str(row["unit"]),
                    "last_seen": last_seen,
                    "active": True,
                }
            )

        return {
            "status": "success",
            "count": len(trucks),
            "trucks": trucks,
        }

    except Exception as e:
        logger.error(f"Get trucks error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fleet-summary")
async def get_fleet_summary():
    """
    Get fleet overview with key metrics.

    Returns:
        Summary statistics for the entire fleet
    """
    try:
        conn = get_wialon_connection()

        now = datetime.now(timezone.utc)

        with conn.cursor() as cursor:
            # Active trucks in last 24h
            cursor.execute(
                """
                SELECT COUNT(DISTINCT unit) as active_count
                FROM sensors
                WHERE m >= UNIX_TIMESTAMP() - 86400
            """
            )
            active_24h = cursor.fetchone()["active_count"]

            # Active trucks in last 2h (online now)
            cursor.execute(
                """
                SELECT COUNT(DISTINCT unit) as online_count
                FROM sensors
                WHERE m >= UNIX_TIMESTAMP() - 7200
            """
            )
            online_now = cursor.fetchone()["online_count"]

            # Total unique trucks
            cursor.execute("SELECT COUNT(DISTINCT unit) as total FROM sensors")
            total_trucks = cursor.fetchone()["total"]

            # Average fuel level (if available)
            cursor.execute(
                """
                SELECT AVG(value) as avg_fuel
                FROM sensors s
                INNER JOIN (
                    SELECT unit, MAX(m) as max_m
                    FROM sensors
                    WHERE p = 'fuel_lvl' AND m >= UNIX_TIMESTAMP() - 7200
                    GROUP BY unit
                ) latest ON s.unit = latest.unit AND s.m = latest.max_m
                WHERE s.p = 'fuel_lvl'
            """
            )
            result = cursor.fetchone()
            avg_fuel = result["avg_fuel"] if result else None

        conn.close()

        return {
            "status": "success",
            "summary": {
                "total_trucks": total_trucks,
                "online_now": online_now,
                "active_24h": active_24h,
                "offline": total_trucks - online_now,
                "avg_fuel_level_pct": round(avg_fuel, 1) if avg_fuel else None,
                "timestamp": now.isoformat(),
            },
        }

    except Exception as e:
        logger.error(f"Fleet summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/truck/{truck_id}/details")
async def get_truck_details(truck_id: str):
    """
    Get detailed information for a specific truck.

    Returns:
        Truck details including latest sensor readings
    """
    try:
        conn = get_wialon_connection()

        with conn.cursor() as cursor:
            # Find truck by name pattern
            cursor.execute(
                """
                SELECT unit, n as truck_name
                FROM sensors
                WHERE n LIKE %s
                GROUP BY unit, n
                LIMIT 1
            """,
                (f"%{truck_id}%",),
            )

            truck = cursor.fetchone()
            if not truck:
                raise HTTPException(
                    status_code=404, detail=f"Truck {truck_id} not found"
                )

            unit_id = truck["unit"]

            # Get latest sensor values
            cursor.execute(
                """
                SELECT 
                    s.p as param,
                    s.value,
                    s.m as epoch
                FROM sensors s
                INNER JOIN (
                    SELECT p, MAX(m) as max_m
                    FROM sensors
                    WHERE unit = %s AND m >= UNIX_TIMESTAMP() - 7200
                    GROUP BY p
                ) latest ON s.p = latest.p AND s.m = latest.max_m
                WHERE s.unit = %s
            """,
                (unit_id, unit_id),
            )

            sensors = {}
            last_update = None
            for row in cursor.fetchall():
                sensors[row["param"]] = row["value"]
                if row["epoch"]:
                    ts = row["epoch"]
                    if last_update is None or ts > last_update:
                        last_update = ts

        conn.close()

        return {
            "status": "success",
            "truck": {
                "truck_id": truck["truck_name"] or str(unit_id),
                "unit_id": unit_id,
                "last_update": (
                    datetime.fromtimestamp(last_update, tz=timezone.utc).isoformat()
                    if last_update
                    else None
                ),
                "sensors": sensors,
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Truck details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
