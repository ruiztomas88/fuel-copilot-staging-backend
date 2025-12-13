"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                        ANALYTICS ROUTER                                        ║
║                  Fuel Analytics & KPI Endpoints                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Endpoints:                                                                    ║
║  - /efficiency/fleet (fleet-wide efficiency metrics)                           ║
║  - /efficiency/truck/{truck_id} (single truck efficiency)                      ║
║  - /kpis (key performance indicators)                                          ║
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
    prefix="/fuelAnalytics/api/analytics",
    tags=["Analytics"],
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


def get_fuel_db_connection():
    """Get connection to Fuel Analytics DB"""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "fuel_analytics"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/efficiency/fleet")
async def get_fleet_efficiency(
    days: int = Query(7, description="Number of days to analyze"),
):
    """
    Get fleet-wide fuel efficiency metrics.

    Returns:
        Fleet efficiency statistics including avg MPG, total fuel, trends
    """
    try:
        conn = get_fuel_db_connection()

        with conn.cursor() as cursor:
            # Get efficiency data from refuels/trips if available
            cursor.execute(
                """
                SELECT 
                    truck_id,
                    AVG(mpg) as avg_mpg,
                    SUM(fuel_gallons) as total_fuel,
                    SUM(miles) as total_miles,
                    COUNT(*) as trip_count
                FROM (
                    SELECT truck_id, mpg, fuel_gallons, miles
                    FROM trips
                    WHERE created_at >= NOW() - INTERVAL %s DAY
                    UNION ALL
                    SELECT truck_id, mpg, gallons as fuel_gallons, miles
                    FROM refuels
                    WHERE refuel_date >= NOW() - INTERVAL %s DAY
                      AND mpg IS NOT NULL
                ) combined
                GROUP BY truck_id
            """,
                (days, days),
            )

            by_truck = list(cursor.fetchall())

        conn.close()

        # Calculate fleet totals
        total_fuel = sum(t.get("total_fuel") or 0 for t in by_truck)
        total_miles = sum(t.get("total_miles") or 0 for t in by_truck)

        fleet_mpg = total_miles / total_fuel if total_fuel > 0 else None

        return {
            "status": "success",
            "period_days": days,
            "fleet": {
                "avg_mpg": round(fleet_mpg, 2) if fleet_mpg else None,
                "total_fuel_gallons": round(total_fuel, 1),
                "total_miles": round(total_miles, 1),
                "truck_count": len(by_truck),
            },
            "by_truck": [
                {
                    "truck_id": t["truck_id"],
                    "avg_mpg": round(t["avg_mpg"], 2) if t.get("avg_mpg") else None,
                    "total_fuel": (
                        round(t["total_fuel"], 1) if t.get("total_fuel") else 0
                    ),
                    "total_miles": (
                        round(t["total_miles"], 1) if t.get("total_miles") else 0
                    ),
                }
                for t in by_truck
            ],
        }

    except Exception as e:
        logger.error(f"Fleet efficiency error: {e}")
        # Return empty data on error (table might not exist)
        return {
            "status": "success",
            "period_days": days,
            "fleet": {
                "avg_mpg": None,
                "total_fuel_gallons": 0,
                "total_miles": 0,
                "truck_count": 0,
            },
            "by_truck": [],
            "note": "No efficiency data available",
        }


@router.get("/efficiency/truck/{truck_id}")
async def get_truck_efficiency(
    truck_id: str,
    days: int = Query(30, description="Number of days to analyze"),
):
    """
    Get fuel efficiency metrics for a specific truck.

    Returns:
        Detailed efficiency history with trend analysis
    """
    try:
        conn = get_fuel_db_connection()

        with conn.cursor() as cursor:
            # Get trip/refuel history
            cursor.execute(
                """
                SELECT 
                    DATE(created_at) as date,
                    AVG(mpg) as daily_mpg,
                    SUM(fuel_gallons) as daily_fuel,
                    SUM(miles) as daily_miles
                FROM (
                    SELECT truck_id, created_at, mpg, fuel_gallons, miles
                    FROM trips
                    WHERE truck_id = %s 
                      AND created_at >= NOW() - INTERVAL %s DAY
                    UNION ALL
                    SELECT truck_id, refuel_date as created_at, mpg, gallons as fuel_gallons, miles
                    FROM refuels
                    WHERE truck_id = %s
                      AND refuel_date >= NOW() - INTERVAL %s DAY
                      AND mpg IS NOT NULL
                ) combined
                GROUP BY DATE(created_at)
                ORDER BY date
            """,
                (truck_id, days, truck_id, days),
            )

            daily_data = list(cursor.fetchall())

        conn.close()

        # Calculate trend
        if len(daily_data) >= 7:
            recent_avg = sum(
                d["daily_mpg"] for d in daily_data[-7:] if d.get("daily_mpg")
            ) / min(7, len([d for d in daily_data[-7:] if d.get("daily_mpg")]) or 1)

            older_avg = sum(
                d["daily_mpg"] for d in daily_data[:-7] if d.get("daily_mpg")
            ) / max(1, len([d for d in daily_data[:-7] if d.get("daily_mpg")]))

            if older_avg > 0:
                trend_pct = ((recent_avg - older_avg) / older_avg) * 100
            else:
                trend_pct = 0
        else:
            trend_pct = None

        total_fuel = sum(d.get("daily_fuel") or 0 for d in daily_data)
        total_miles = sum(d.get("daily_miles") or 0 for d in daily_data)

        return {
            "status": "success",
            "truck_id": truck_id,
            "period_days": days,
            "summary": {
                "avg_mpg": (
                    round(total_miles / total_fuel, 2) if total_fuel > 0 else None
                ),
                "total_fuel": round(total_fuel, 1),
                "total_miles": round(total_miles, 1),
                "trend_pct": round(trend_pct, 1) if trend_pct is not None else None,
            },
            "daily": [
                {
                    "date": d["date"].isoformat() if d.get("date") else None,
                    "mpg": round(d["daily_mpg"], 2) if d.get("daily_mpg") else None,
                    "fuel": round(d["daily_fuel"], 1) if d.get("daily_fuel") else 0,
                    "miles": round(d["daily_miles"], 1) if d.get("daily_miles") else 0,
                }
                for d in daily_data
            ],
        }

    except Exception as e:
        logger.error(f"Truck efficiency error: {e}")
        return {
            "status": "success",
            "truck_id": truck_id,
            "period_days": days,
            "summary": {
                "avg_mpg": None,
                "total_fuel": 0,
                "total_miles": 0,
                "trend_pct": None,
            },
            "daily": [],
            "note": "No efficiency data available for this truck",
        }


@router.get("/kpis")
async def get_kpis():
    """
    Get key performance indicators for the fleet.

    Returns:
        KPIs including efficiency, utilization, and health metrics
    """
    try:
        fuel_conn = get_fuel_db_connection()
        wialon_conn = get_wialon_connection()

        kpis = {}

        # Fleet size and activity
        with wialon_conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT 
                    COUNT(DISTINCT unit) as total_trucks,
                    COUNT(DISTINCT CASE WHEN m >= UNIX_TIMESTAMP() - 7200 THEN unit END) as online_trucks
                FROM sensors
            """
            )
            fleet = cursor.fetchone()
            kpis["fleet_size"] = fleet["total_trucks"]
            kpis["trucks_online"] = fleet["online_trucks"]
            kpis["online_pct"] = (
                round((fleet["online_trucks"] / fleet["total_trucks"]) * 100, 1)
                if fleet["total_trucks"] > 0
                else 0
            )

        wialon_conn.close()

        # Maintenance alerts
        try:
            with fuel_conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT 
                        COUNT(*) as total_unresolved,
                        SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical,
                        SUM(CASE WHEN severity = 'high' THEN 1 ELSE 0 END) as high
                    FROM maintenance_alerts
                    WHERE resolved_at IS NULL
                """
                )
                alerts = cursor.fetchone()
                kpis["unresolved_alerts"] = alerts["total_unresolved"] or 0
                kpis["critical_alerts"] = alerts["critical"] or 0
                kpis["high_alerts"] = alerts["high"] or 0
        except Exception as alerts_err:
            logger.warning(f"Failed to fetch maintenance alerts KPIs: {alerts_err}")
            kpis["unresolved_alerts"] = 0
            kpis["critical_alerts"] = 0
            kpis["high_alerts"] = 0

        # Fuel efficiency (last 7 days)
        try:
            with fuel_conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT AVG(mpg) as avg_mpg
                    FROM refuels
                    WHERE refuel_date >= NOW() - INTERVAL 7 DAY
                      AND mpg IS NOT NULL
                      AND mpg > 0
                      AND mpg < 20
                """
                )
                eff = cursor.fetchone()
                kpis["fleet_avg_mpg_7d"] = (
                    round(eff["avg_mpg"], 2) if eff.get("avg_mpg") else None
                )
        except Exception as mpg_err:
            logger.warning(f"Failed to fetch fleet MPG KPIs: {mpg_err}")
            kpis["fleet_avg_mpg_7d"] = None

        fuel_conn.close()

        return {
            "status": "success",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "kpis": kpis,
        }

    except Exception as e:
        logger.error(f"KPIs error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
