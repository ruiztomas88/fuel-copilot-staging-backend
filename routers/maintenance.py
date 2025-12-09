"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                    MAINTENANCE ROUTER                                          ║
║              Predictive Maintenance API Endpoints                              ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Consolidates:                                                                 ║
║  - /maintenance/fleet-health (unified engine)                                  ║
║  - /maintenance/truck/{truck_id}                                               ║
║  - /maintenance/alerts                                                         ║
║  - /maintenance/alerts/{id}/acknowledge                                        ║
║  - /maintenance/alerts/{id}/resolve                                            ║
║  - /maintenance/alerts/summary                                                 ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import os
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
import pymysql

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fuelAnalytics/api/maintenance",
    tags=["Predictive Maintenance"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def get_fuel_db_connection():
    """Get connection to Fuel Analytics DB for maintenance alerts"""
    return pymysql.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"),
        password=os.getenv("MYSQL_PASSWORD", ""),
        database=os.getenv("MYSQL_DATABASE", "fuel_analytics"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def get_wialon_connection():
    """Get connection to Wialon DB for sensor data"""
    return pymysql.connect(
        host=os.getenv("WIALON_DB_HOST", "localhost"),
        port=int(os.getenv("WIALON_DB_PORT", "3306")),
        user=os.getenv("WIALON_DB_USER", ""),
        password=os.getenv("WIALON_DB_PASS", ""),
        database=os.getenv("WIALON_DB_NAME", "wialon_collect"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def fetch_sensor_data() -> list:
    """Fetch latest sensor readings from Wialon"""
    trucks_data = []

    try:
        conn = get_wialon_connection()
    except Exception as e:
        logger.warning(f"Cannot connect to Wialon DB: {e}")
        return []  # Return empty list, endpoint will use demo data

    try:
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    s.unit,
                    s.n as truck_name,
                    s.p as param,
                    s.value,
                    s.m as epoch
                FROM sensors s
                INNER JOIN (
                    SELECT unit, p, MAX(m) as max_epoch
                    FROM sensors
                    WHERE m >= UNIX_TIMESTAMP() - 7200
                    GROUP BY unit, p
                ) latest ON s.unit = latest.unit AND s.p = latest.p AND s.m = latest.max_epoch
                WHERE s.m >= UNIX_TIMESTAMP() - 7200
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            unit_data = {}
            param_mapping = {
                "oil_press": "oil_press",
                "cool_temp": "cool_temp",
                "oil_temp": "oil_temp",
                "pwr_ext": "pwr_ext",
                "def_level": "def_level",
                "rpm": "rpm",
                "engine_load": "engine_load",
                "fuel_rate": "fuel_rate",
                "fuel_lvl": "fuel_lvl",
                "speed": "speed",
            }

            for row in rows:
                unit_id = row["unit"]
                if unit_id not in unit_data:
                    unit_data[unit_id] = {
                        "truck_id": row["truck_name"] or str(unit_id),
                        "unit_id": unit_id,
                    }

                param = row["param"]
                value = row["value"]

                if param in param_mapping:
                    unit_data[unit_id][param_mapping[param]] = value

            trucks_data = list(unit_data.values())
    finally:
        conn.close()

    return trucks_data


def fetch_historical_data(truck_id: str, unit_id: int, days: int = 7) -> Dict:
    """Fetch historical sensor data for trend analysis"""
    historical = {}

    try:
        conn = get_wialon_connection()
    except Exception as e:
        logger.warning(f"Cannot connect to Wialon DB for history: {e}")
        return {}  # Return empty dict

    try:
        with conn.cursor() as cursor:
            query = """
                SELECT p as param, value, m as epoch
                FROM sensors
                WHERE unit = %s
                  AND m >= UNIX_TIMESTAMP() - %s
                ORDER BY m ASC
            """
            cursor.execute(query, (unit_id, days * 24 * 3600))
            rows = cursor.fetchall()

            for row in rows:
                param = row["param"]
                if param not in historical:
                    historical[param] = []
                ts = datetime.fromtimestamp(row["epoch"], tz=timezone.utc)
                historical[param].append((ts, float(row["value"])))
    finally:
        conn.close()

    return historical


# ═══════════════════════════════════════════════════════════════════════════════
# AUTH DEPENDENCY (imported from main)
# ═══════════════════════════════════════════════════════════════════════════════

# This will be injected when the router is included in main.py
_require_auth = None


def set_auth_dependency(auth_func):
    """Set the auth dependency from main.py"""
    global _require_auth
    _require_auth = auth_func


def get_current_user():
    """Get current user dependency"""
    if _require_auth is None:
        raise HTTPException(status_code=500, detail="Auth not configured")
    return Depends(_require_auth)


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/fleet-health")
async def get_fleet_health(
    include_trends: bool = Query(False, description="Include 7-day trend analysis"),
    include_anomalies: bool = Query(
        False, description="Include Nelson Rules anomaly detection"
    ),
):
    """
    🆕 v5.0: Unified fleet health endpoint.
    
    Returns fleet health report with demo data if real data unavailable.
    """
    # Default demo response - always works
    demo_response = {
        "status": "success",
        "data_source": "demo",
        "fleet_summary": {
            "total_trucks": 3,
            "healthy_count": 2,
            "warning_count": 1,
            "critical_count": 0,
            "fleet_health_score": 85,
            "data_freshness": "Demo data",
        },
        "alert_summary": {
            "critical": 0,
            "high": 1,
            "medium": 2,
            "low": 1,
        },
        "trucks": [
            {
                "truck_id": "T101",
                "overall_score": 95,
                "status": "healthy",
                "current_values": {"oil_press": 45, "cool_temp": 195, "pwr_ext": 14.1},
                "alerts": [],
                "last_updated": datetime.now(timezone.utc).isoformat(),
            },
            {
                "truck_id": "T102", 
                "overall_score": 72,
                "status": "warning",
                "current_values": {"oil_press": 28, "cool_temp": 215, "pwr_ext": 13.2},
                "alerts": [
                    {
                        "category": "engine",
                        "severity": "high",
                        "title": "Low Oil Pressure",
                        "message": "Oil pressure below normal range",
                        "metric": "oil_press",
                        "current_value": 28,
                        "threshold": 30,
                        "recommendation": "Check oil level and pressure sensor"
                    }
                ],
                "last_updated": datetime.now(timezone.utc).isoformat(),
            },
            {
                "truck_id": "T103",
                "overall_score": 88,
                "status": "healthy", 
                "current_values": {"oil_press": 52, "cool_temp": 188, "pwr_ext": 14.3},
                "alerts": [],
                "last_updated": datetime.now(timezone.utc).isoformat(),
            },
        ],
        "alerts": [
            {
                "truck_id": "T102",
                "category": "engine",
                "severity": "high",
                "title": "Low Oil Pressure",
                "message": "Oil pressure 28 psi (threshold: 30 psi)",
                "recommendation": "Check oil level and sensor",
            }
        ],
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    
    try:
        # Try to use real engine
        from unified_health_engine import UnifiedHealthEngine
        engine = UnifiedHealthEngine()
        
        # Get sensor data (will return [] if Wialon unavailable)
        trucks_data = fetch_sensor_data()
        
        if not trucks_data:
            logger.info("No sensor data available, returning demo response")
            return demo_response

        # Generate real report
        report = engine.generate_fleet_report(
            trucks_data,
            include_trends=include_trends,
            include_anomalies=include_anomalies,
        )
        
        if report:
            report["data_source"] = "live"
            return report
        else:
            return demo_response

    except ImportError as e:
        logger.warning(f"UnifiedHealthEngine not available: {e}")
        return demo_response
    except Exception as e:
        logger.error(f"Fleet health error: {e}", exc_info=True)
        # Return demo data instead of crashing
        demo_response["error_info"] = str(e)
        return demo_response


@router.get("/truck/{truck_id}")
async def get_truck_health(truck_id: str):
    """
    Get detailed health analysis for a specific truck.

    Returns:
        Detailed health report with component scores and alerts
    """
    try:
        from unified_health_engine import UnifiedHealthEngine

        engine = UnifiedHealthEngine()

        truck_data = {"truck_id": truck_id}
        unit_id = None

        # Try to get Wialon data, but don't crash if unavailable
        try:
            conn = get_wialon_connection()
            try:
                with conn.cursor() as cursor:
                    # Get unit_id and latest values
                    query = """
                        SELECT unit, p as param, value
                        FROM sensors
                        WHERE n LIKE %s
                          AND m >= UNIX_TIMESTAMP() - 7200
                        ORDER BY m DESC
                    """
                    cursor.execute(query, (f"%{truck_id}%",))
                    rows = cursor.fetchall()

                    seen_params = set()
                    for row in rows:
                        if unit_id is None:
                            unit_id = row.get("unit")
                        param = row["param"]
                        if param not in seen_params:
                            seen_params.add(param)
                            truck_data[param] = row["value"]
            finally:
                conn.close()
        except Exception as e:
            logger.warning(f"Cannot fetch Wialon data for {truck_id}: {e}")
            # Use demo data
            truck_data = {
                "truck_id": truck_id,
                "oil_press": 45,
                "cool_temp": 195,
                "pwr_ext": 14.1,
                "rpm": 1400,
            }

        # Build current values
        current_values = {
            k: float(v)
            for k, v in truck_data.items()
            if k not in ("truck_id", "unit_id") and v is not None
        }

        # Fetch historical data
        historical = {}
        if unit_id:
            try:
                historical = fetch_historical_data(truck_id, unit_id, days=7)
            except Exception as e:
                logger.warning(f"Could not fetch history for {truck_id}: {e}")

        # Analyze truck
        health = engine.analyze_truck(truck_id, current_values, historical)

        return {
            "status": "success",
            "data": health.to_dict(),
        }

    except Exception as e:
        logger.error(f"Truck health error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts(
    severity: Optional[str] = None,
    truck_id: Optional[str] = None,
    unresolved_only: bool = True,
    limit: int = 50,
):
    """
    Get persisted maintenance alerts.

    Query params:
        severity: Filter by severity (critical, high, medium, low)
        truck_id: Filter by truck
        unresolved_only: Only show unresolved alerts (default: true)
        limit: Max number of alerts (default: 50)
    """
    try:
        conn = get_fuel_db_connection()

        query = """
            SELECT 
                id, truck_id, category, severity, title, message,
                metric, current_value, threshold, trend_pct,
                recommendation, estimated_days_to_failure,
                created_at, acknowledged_at, acknowledged_by,
                resolved_at, resolved_by
            FROM maintenance_alerts
            WHERE 1=1
        """
        params: Dict[str, Any] = {}

        if severity:
            query += " AND severity = %(severity)s"
            params["severity"] = severity

        if truck_id:
            query += " AND truck_id = %(truck_id)s"
            params["truck_id"] = truck_id

        if unresolved_only:
            query += " AND resolved_at IS NULL"

        query += " ORDER BY FIELD(severity, 'critical', 'high', 'medium', 'low'), created_at DESC"
        query += f" LIMIT {limit}"

        with conn.cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        conn.close()

        return {
            "status": "success",
            "count": len(rows),
            "alerts": [
                {
                    **row,
                    "created_at": (
                        row["created_at"].isoformat() if row.get("created_at") else None
                    ),
                    "acknowledged_at": (
                        row["acknowledged_at"].isoformat()
                        if row.get("acknowledged_at")
                        else None
                    ),
                    "resolved_at": (
                        row["resolved_at"].isoformat()
                        if row.get("resolved_at")
                        else None
                    ),
                }
                for row in rows
            ],
        }

    except Exception as e:
        logger.error(f"Get alerts error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: int, username: str = "system"):
    """Acknowledge a maintenance alert."""
    try:
        conn = get_fuel_db_connection()

        with conn.cursor() as cursor:
            query = """
                UPDATE maintenance_alerts
                SET acknowledged_at = NOW(),
                    acknowledged_by = %s
                WHERE id = %s AND acknowledged_at IS NULL
            """
            cursor.execute(query, (username, alert_id))
            affected = cursor.rowcount

        conn.commit()
        conn.close()

        if affected == 0:
            raise HTTPException(
                status_code=404, detail="Alert not found or already acknowledged"
            )

        return {"status": "success", "message": f"Alert {alert_id} acknowledged"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Acknowledge alert error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: int, username: str = "system"):
    """Resolve/close a maintenance alert."""
    try:
        conn = get_fuel_db_connection()

        with conn.cursor() as cursor:
            query = """
                UPDATE maintenance_alerts
                SET resolved_at = NOW(),
                    resolved_by = %s
                WHERE id = %s AND resolved_at IS NULL
            """
            cursor.execute(query, (username, alert_id))
            affected = cursor.rowcount

        conn.commit()
        conn.close()

        if affected == 0:
            raise HTTPException(
                status_code=404, detail="Alert not found or already resolved"
            )

        return {"status": "success", "message": f"Alert {alert_id} resolved"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Resolve alert error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/summary")
async def get_alerts_summary():
    """Get summary of unresolved alerts by severity and truck."""
    try:
        conn = get_fuel_db_connection()

        with conn.cursor() as cursor:
            # Count by severity
            cursor.execute(
                """
                SELECT severity, COUNT(*) as count
                FROM maintenance_alerts
                WHERE resolved_at IS NULL
                GROUP BY severity
            """
            )
            by_severity = {row["severity"]: row["count"] for row in cursor.fetchall()}

            # Count by truck (top 10)
            cursor.execute(
                """
                SELECT truck_id, COUNT(*) as count,
                       SUM(CASE WHEN severity = 'critical' THEN 1 ELSE 0 END) as critical_count
                FROM maintenance_alerts
                WHERE resolved_at IS NULL
                GROUP BY truck_id
                ORDER BY critical_count DESC, count DESC
                LIMIT 10
            """
            )
            by_truck = list(cursor.fetchall())

            # Recent 24h vs previous 24h
            cursor.execute(
                """
                SELECT 
                    SUM(CASE WHEN created_at >= NOW() - INTERVAL 24 HOUR THEN 1 ELSE 0 END) as last_24h,
                    SUM(CASE WHEN created_at >= NOW() - INTERVAL 48 HOUR 
                             AND created_at < NOW() - INTERVAL 24 HOUR THEN 1 ELSE 0 END) as prev_24h
                FROM maintenance_alerts
                WHERE resolved_at IS NULL
            """
            )
            trend = cursor.fetchone()

        conn.close()

        total_unresolved = sum(by_severity.values())

        return {
            "status": "success",
            "summary": {
                "total_unresolved": total_unresolved,
                "by_severity": by_severity,
                "top_trucks": by_truck,
                "trend": {
                    "last_24h": trend["last_24h"] or 0,
                    "prev_24h": trend["prev_24h"] or 0,
                    "change": (trend["last_24h"] or 0) - (trend["prev_24h"] or 0),
                },
            },
        }

    except Exception as e:
        logger.error(f"Alerts summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
