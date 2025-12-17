"""
Engine Health Router - v3.13.0
Engine health monitoring, alerts, and maintenance predictions
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Engine Health"])


@router.get("/engine-health/fleet-summary")
async def get_engine_health_fleet_summary():
    """
    🆕 v3.13.0: Get fleet-wide engine health summary.

    Returns:
    - Count of healthy/warning/critical/offline trucks
    - Top critical and warning alerts
    - Sensor coverage statistics
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text
        from engine_health_engine import EngineHealthAnalyzer

        engine = get_sqlalchemy_engine()
        analyzer = EngineHealthAnalyzer()

        query = """
            SELECT 
                fm.truck_id,
                fm.timestamp_utc,
                fm.oil_pressure_psi,
                fm.coolant_temp_f,
                fm.oil_temp_f,
                fm.battery_voltage,
                fm.def_level_pct,
                fm.engine_load_pct,
                fm.rpm,
                fm.speed_mph,
                fm.truck_status
            FROM fuel_metrics fm
            INNER JOIN (
                SELECT truck_id, MAX(timestamp_utc) as max_ts
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
                GROUP BY truck_id
            ) latest ON fm.truck_id = latest.truck_id 
                     AND fm.timestamp_utc = latest.max_ts
            ORDER BY fm.truck_id
        """

        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            columns = result.keys()

        fleet_data = [dict(zip(columns, row)) for row in rows]
        summary = analyzer.analyze_fleet_health(fleet_data)

        return summary.to_dict()

    except ImportError as e:
        logger.warning(f"Engine health module not available: {e}")
        return {
            "error": "Engine health module not available",
            "summary": {
                "total_trucks": 0,
                "healthy": 0,
                "warning": 0,
                "critical": 0,
                "offline": 0,
            },
        }
    except Exception as e:
        logger.error(f"Error getting fleet health summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/engine-health/trucks/{truck_id}")
async def get_truck_health_detail(
    truck_id: str,
    include_history: bool = Query(True, description="Include 7-day history for trends"),
):
    """
    🆕 v3.13.0: Get detailed engine health status for a specific truck.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text
        from engine_health_engine import EngineHealthAnalyzer, BaselineCalculator

        engine = get_sqlalchemy_engine()
        analyzer = EngineHealthAnalyzer()

        current_query = """
            SELECT 
                truck_id,
                timestamp_utc,
                oil_pressure_psi,
                coolant_temp_f,
                oil_temp_f,
                battery_voltage,
                def_level_pct,
                engine_load_pct,
                rpm,
                speed_mph,
                truck_status,
                latitude,
                longitude
            FROM fuel_metrics
            WHERE truck_id = :truck_id
            ORDER BY timestamp_utc DESC
            LIMIT 1
        """

        with engine.connect() as conn:
            result = conn.execute(text(current_query), {"truck_id": truck_id})
            row = result.fetchone()

            if not row:
                raise HTTPException(
                    status_code=404, detail=f"Truck {truck_id} not found"
                )

            columns = result.keys()
            current_data = dict(zip(columns, row))

        historical_data = []
        baselines = {}

        if include_history:
            history_query = """
                SELECT 
                    timestamp_utc,
                    oil_pressure_psi,
                    coolant_temp_f,
                    oil_temp_f,
                    battery_voltage,
                    def_level_pct,
                    engine_load_pct,
                    rpm
                FROM fuel_metrics
                WHERE truck_id = :truck_id
                  AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                  AND rpm > 400
                ORDER BY timestamp_utc DESC
                LIMIT 5000
            """

            with engine.connect() as conn:
                result = conn.execute(text(history_query), {"truck_id": truck_id})
                rows = result.fetchall()
                columns = result.keys()
                historical_data = [dict(zip(columns, row)) for row in rows]

            # 🔧 v6.2.2: BUG-001 FIX - Calculate and persist baselines
            for sensor in ["oil_pressure_psi", "coolant_temp_f", "battery_voltage"]:
                baseline = BaselineCalculator.calculate_baseline(
                    truck_id, sensor, historical_data
                )
                baselines[sensor] = baseline
            
            # Save baselines to database for persistence (BUG-001 fix)
            if baselines:
                analyzer._save_baselines(truck_id, baselines)

        status = analyzer.analyze_truck_health(
            truck_id, current_data, historical_data, baselines
        )
        response = status.to_dict()

        if include_history and historical_data:
            sample_rate = max(1, len(historical_data) // 100)
            sampled = historical_data[::sample_rate][:100]

            response["history"] = {
                "timestamps": [str(d.get("timestamp_utc", "")) for d in sampled],
                "oil_pressure": [d.get("oil_pressure_psi") for d in sampled],
                "coolant_temp": [d.get("coolant_temp_f") for d in sampled],
                "oil_temp": [d.get("oil_temp_f") for d in sampled],
                "battery": [d.get("battery_voltage") for d in sampled],
            }

            response["baselines"] = {
                sensor: {
                    "mean_30d": b.mean_30d,
                    "mean_7d": b.mean_7d,
                    "std_30d": b.std_30d,
                    "min_30d": b.min_30d,
                    "max_30d": b.max_30d,
                }
                for sensor, b in baselines.items()
                if b.sample_count > 0
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting truck health for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/engine-health/alerts")
async def get_health_alerts(
    severity: Optional[str] = Query(
        None, description="Filter by severity: critical, warning, watch"
    ),
    truck_id: Optional[str] = Query(None, description="Filter by truck"),
    active_only: bool = Query(True, description="Only active alerts"),
    limit: int = Query(50, ge=1, le=200),
):
    """
    🆕 v3.13.0: Get engine health alerts.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        conditions = []
        params = {"limit": limit}

        if active_only:
            conditions.append("is_active = TRUE")

        if severity:
            conditions.append("severity = :severity")
            params["severity"] = severity

        if truck_id:
            conditions.append("truck_id = :truck_id")
            params["truck_id"] = truck_id

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT 
                id, truck_id, category, severity, sensor_name,
                current_value, threshold_value, baseline_value,
                message, action_required, trend_direction,
                is_active, created_at, acknowledged_at
            FROM engine_health_alerts
            WHERE {where_clause}
            ORDER BY 
                FIELD(severity, 'critical', 'warning', 'watch', 'info'),
                created_at DESC
            LIMIT :limit
        """

        try:
            with engine.connect() as conn:
                result = conn.execute(text(query), params)
                rows = result.fetchall()
                columns = result.keys()

            alerts = [dict(zip(columns, row)) for row in rows]

            for alert in alerts:
                for key in ["created_at", "acknowledged_at"]:
                    if alert.get(key):
                        alert[key] = str(alert[key])

            return {
                "alerts": alerts,
                "count": len(alerts),
                "filters": {
                    "severity": severity,
                    "truck_id": truck_id,
                    "active_only": active_only,
                },
            }
        except Exception as db_error:
            logger.warning(f"Engine health alerts table may not exist: {db_error}")
            return {
                "alerts": [],
                "count": 0,
                "message": "No alerts table - run migration first",
            }

    except Exception as e:
        logger.error(f"Error getting health alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/engine-health/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(
    alert_id: int,
    acknowledged_by: str = Query(..., description="User who acknowledged"),
):
    """
    🆕 v3.13.0: Acknowledge an engine health alert.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        query = """
            UPDATE engine_health_alerts
            SET acknowledged_at = NOW(),
                acknowledged_by = :acknowledged_by
            WHERE id = :alert_id
        """

        with engine.connect() as conn:
            result = conn.execute(
                text(query), {"alert_id": alert_id, "acknowledged_by": acknowledged_by}
            )
            conn.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {"status": "acknowledged", "alert_id": alert_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error acknowledging alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/engine-health/alerts/{alert_id}/resolve")
async def resolve_alert(
    alert_id: int,
    resolution_notes: str = Query(None, description="Notes about the resolution"),
):
    """
    🆕 v3.13.0: Resolve/close an engine health alert.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        query = """
            UPDATE engine_health_alerts
            SET is_active = FALSE,
                resolved_at = NOW(),
                resolution_notes = :notes
            WHERE id = :alert_id
        """

        with engine.connect() as conn:
            result = conn.execute(
                text(query), {"alert_id": alert_id, "notes": resolution_notes}
            )
            conn.commit()

        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Alert not found")

        return {"status": "resolved", "alert_id": alert_id}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resolving alert {alert_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/engine-health/thresholds")
async def get_health_thresholds():
    """
    🆕 v3.13.0: Get current engine health thresholds.
    """
    from engine_health_engine import ENGINE_HEALTH_THRESHOLDS

    return {
        "thresholds": ENGINE_HEALTH_THRESHOLDS,
        "description": "Threshold values for engine health monitoring",
    }


@router.get("/engine-health/maintenance-predictions")
async def get_maintenance_predictions(
    truck_id: Optional[str] = Query(None, description="Filter by truck"),
    urgency: Optional[str] = Query(
        None, description="Filter by urgency: low, medium, high, critical"
    ),
    status: str = Query(
        "active", description="Status: active, scheduled, completed, all"
    ),
):
    """
    🆕 v3.13.0: Get maintenance predictions based on engine health analysis.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        conditions = []
        params = {}

        if status != "all":
            conditions.append("status = :status")
            params["status"] = status

        if truck_id:
            conditions.append("truck_id = :truck_id")
            params["truck_id"] = truck_id

        if urgency:
            conditions.append("urgency = :urgency")
            params["urgency"] = urgency

        where_clause = " AND ".join(conditions) if conditions else "1=1"

        query = f"""
            SELECT 
                id, truck_id, component, urgency, prediction,
                recommended_action, estimated_repair_cost, if_ignored_cost,
                predicted_failure_date, confidence_pct, status,
                scheduled_date, created_at
            FROM maintenance_predictions
            WHERE {where_clause}
            ORDER BY 
                FIELD(urgency, 'critical', 'high', 'medium', 'low'),
                predicted_failure_date ASC
            LIMIT 100
        """

        try:
            with engine.connect() as conn:
                result = conn.execute(text(query), params)
                rows = result.fetchall()
                columns = result.keys()

            predictions = [dict(zip(columns, row)) for row in rows]

            for pred in predictions:
                for key in ["predicted_failure_date", "scheduled_date", "created_at"]:
                    if pred.get(key):
                        pred[key] = str(pred[key])

            return {"predictions": predictions, "count": len(predictions)}
        except Exception:
            return {
                "predictions": [],
                "count": 0,
                "message": "Run migration to create maintenance_predictions table",
            }

    except Exception as e:
        logger.error(f"Error getting maintenance predictions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/engine-health/sensor-history/{truck_id}/{sensor}")
async def get_sensor_history(
    truck_id: str,
    sensor: str,
    days: int = Query(7, ge=1, le=30),
):
    """
    🆕 v3.13.0: Get historical data for a specific sensor.
    """
    valid_sensors = [
        "oil_pressure_psi",
        "coolant_temp_f",
        "oil_temp_f",
        "battery_voltage",
        "def_level_pct",
        "engine_load_pct",
    ]

    if sensor not in valid_sensors:
        raise HTTPException(
            status_code=400, detail=f"Invalid sensor. Valid options: {valid_sensors}"
        )

    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        query = f"""
            SELECT 
                DATE_FORMAT(timestamp_utc, '%Y-%m-%d %H:00:00') as hour,
                AVG({sensor}) as avg_value,
                MIN({sensor}) as min_value,
                MAX({sensor}) as max_value,
                COUNT(*) as sample_count
            FROM fuel_metrics
            WHERE truck_id = :truck_id
              AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
              AND {sensor} IS NOT NULL
              AND rpm > 400
            GROUP BY DATE_FORMAT(timestamp_utc, '%Y-%m-%d %H:00:00')
            ORDER BY hour DESC
            LIMIT 720
        """

        with engine.connect() as conn:
            result = conn.execute(text(query), {"truck_id": truck_id, "days": days})
            rows = result.fetchall()
            columns = result.keys()

        data = [dict(zip(columns, row)) for row in rows]

        values = [d["avg_value"] for d in data if d["avg_value"] is not None]

        stats = {}
        if values:
            import statistics

            stats = {
                "mean": round(statistics.mean(values), 2),
                "min": round(min(values), 2),
                "max": round(max(values), 2),
                "std": round(statistics.stdev(values), 2) if len(values) > 1 else 0,
            }

        return {
            "truck_id": truck_id,
            "sensor": sensor,
            "days": days,
            "data": data,
            "statistics": stats,
            "data_points": len(data),
        }

    except Exception as e:
        logger.error(f"Error getting sensor history: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/engine-health/analyze-now")
async def trigger_health_analysis():
    """
    🆕 v3.13.0: Trigger immediate health analysis for all trucks.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text
        from engine_health_engine import EngineHealthAnalyzer

        engine = get_sqlalchemy_engine()
        analyzer = EngineHealthAnalyzer()

        query = """
            SELECT 
                fm.truck_id,
                fm.timestamp_utc,
                fm.oil_pressure_psi,
                fm.coolant_temp_f,
                fm.oil_temp_f,
                fm.battery_voltage,
                fm.def_level_pct,
                fm.engine_load_pct,
                fm.rpm
            FROM fuel_metrics fm
            INNER JOIN (
                SELECT truck_id, MAX(timestamp_utc) as max_ts
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 15 MINUTE)
                GROUP BY truck_id
            ) latest ON fm.truck_id = latest.truck_id 
                     AND fm.timestamp_utc = latest.max_ts
        """

        with engine.connect() as conn:
            result = conn.execute(text(query))
            rows = result.fetchall()
            columns = result.keys()

        fleet_data = [dict(zip(columns, row)) for row in rows]
        summary = analyzer.analyze_fleet_health(fleet_data)

        alerts_saved = 0
        try:
            for alert in summary.critical_alerts + summary.warning_alerts:
                insert_query = """
                    INSERT INTO engine_health_alerts 
                    (truck_id, category, severity, sensor_name, current_value, 
                     threshold_value, baseline_value, message, action_required, 
                     trend_direction, is_active)
                    VALUES 
                    (:truck_id, :category, :severity, :sensor_name, :current_value,
                     :threshold_value, :baseline_value, :message, :action_required,
                     :trend_direction, TRUE)
                """

                with engine.connect() as conn:
                    conn.execute(
                        text(insert_query),
                        {
                            "truck_id": alert.truck_id,
                            "category": alert.category.value,
                            "severity": alert.severity.value,
                            "sensor_name": alert.sensor_name,
                            "current_value": alert.current_value,
                            "threshold_value": alert.threshold_value,
                            "baseline_value": alert.baseline_value,
                            "message": alert.message,
                            "action_required": alert.action_required,
                            "trend_direction": alert.trend_direction,
                        },
                    )
                    conn.commit()
                    alerts_saved += 1
        except Exception as save_error:
            logger.warning(f"Could not save alerts (table may not exist): {save_error}")

        return {
            "status": "completed",
            "trucks_analyzed": len(fleet_data),
            "critical_alerts": summary.trucks_critical,
            "warning_alerts": summary.trucks_warning,
            "alerts_saved": alerts_saved,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Error running health analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))
