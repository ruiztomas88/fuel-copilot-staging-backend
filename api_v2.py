"""
API Endpoints v3.12.21
Additional endpoints for new features

This file contains endpoints for:
- #32: Audit log API
- #33: API key management
- #17: Refuel predictions
- #19: Fuel cost tracking
- #21: Sensor anomalies
- #22: Data export
"""

import io
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Create router
# Note: The prefix /fuelAnalytics/api/v2 is added by routers.py registration
# So we only define the base routes here (e.g., /maintenance/fleet)
router = APIRouter(tags=["v2"])


# =============================================================================
# PYDANTIC MODELS
# =============================================================================
class APIKeyCreate(BaseModel):
    """Request model for creating API key."""

    name: str = Field(..., min_length=3, max_length=100)
    description: Optional[str] = None
    carrier_id: Optional[str] = None
    role: str = Field(default="viewer", pattern="^(viewer|carrier_admin|admin)$")
    scopes: Optional[List[str]] = None
    rate_limit_per_minute: int = Field(default=60, ge=1, le=1000)
    rate_limit_per_day: int = Field(default=10000, ge=100, le=100000)
    expires_in_days: Optional[int] = Field(default=None, ge=1, le=365)


class AuditLogQuery(BaseModel):
    """Query parameters for audit log."""

    action: Optional[str] = None
    user_id: Optional[str] = None
    carrier_id: Optional[str] = None
    resource_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    success_only: Optional[bool] = None
    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class ExportRequest(BaseModel):
    """Request model for data export."""

    carrier_id: Optional[str] = None
    truck_ids: Optional[List[str]] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    include_metrics: bool = True
    include_refuels: bool = True
    include_alerts: bool = True
    include_summary: bool = True
    format: str = Field(default="excel", pattern="^(excel|pdf|csv)$")


# =============================================================================
# API KEY ENDPOINTS (#33)
# =============================================================================
@router.post("/api-keys", summary="Create API Key", tags=["API Keys"])
async def create_api_key(
    request: APIKeyCreate,
    # current_user = Depends(require_admin),  # Uncomment when auth is ready
):
    """
    Create a new API key.

    Returns the full API key (only shown once - save it securely!).
    """
    from api_key_auth import get_api_key_manager

    manager = get_api_key_manager()
    result = manager.create_key(
        name=request.name,
        description=request.description,
        carrier_id=request.carrier_id,
        role=request.role,
        scopes=request.scopes,
        rate_limit_per_minute=request.rate_limit_per_minute,
        rate_limit_per_day=request.rate_limit_per_day,
        expires_in_days=request.expires_in_days,
        created_by=None,  # current_user.username when auth ready
    )

    if not result:
        raise HTTPException(status_code=500, detail="Failed to create API key")

    full_key, key_info = result

    return {
        "api_key": full_key,  # Only returned once!
        "key_info": key_info,
        "warning": "Save this API key securely - it will not be shown again!",
    }


@router.get("/api-keys", summary="List API Keys", tags=["API Keys"])
async def list_api_keys(
    carrier_id: Optional[str] = None,
    include_inactive: bool = False,
):
    """List API keys (without revealing the actual keys)."""
    from api_key_auth import get_api_key_manager

    manager = get_api_key_manager()
    keys = manager.list_keys(carrier_id=carrier_id, include_inactive=include_inactive)

    return {
        "keys": keys,
        "total": len(keys),
    }


@router.delete("/api-keys/{key_id}", summary="Revoke API Key", tags=["API Keys"])
async def revoke_api_key(key_id: int):
    """Revoke (deactivate) an API key."""
    from api_key_auth import get_api_key_manager

    manager = get_api_key_manager()
    success = manager.revoke_key(key_id)

    if not success:
        raise HTTPException(status_code=404, detail="API key not found")

    return {"message": "API key revoked", "key_id": key_id}


# =============================================================================
# AUDIT LOG ENDPOINTS (#32)
# =============================================================================
@router.get("/audit-log", summary="Query Audit Log", tags=["Audit"])
async def query_audit_log(
    action: Optional[str] = None,
    user_id: Optional[str] = None,
    carrier_id: Optional[str] = None,
    resource_type: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    success_only: Optional[bool] = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    """
    Query audit log entries with filtering.

    Supports filtering by action, user, carrier, resource, date range, and success status.
    """
    from audit_log import get_audit_logger

    audit = get_audit_logger()
    entries = audit.query(
        action=action,
        user_id=user_id,
        carrier_id=carrier_id,
        resource_type=resource_type,
        start_date=start_date,
        end_date=end_date,
        success_only=success_only,
        limit=limit,
        offset=offset,
    )

    return {
        "entries": entries,
        "count": len(entries),
        "limit": limit,
        "offset": offset,
    }


@router.get("/audit-log/summary", summary="Audit Log Summary", tags=["Audit"])
async def get_audit_summary(
    carrier_id: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=90),
):
    """Get audit log summary statistics."""
    from audit_log import get_audit_logger

    audit = get_audit_logger()
    summary = audit.get_summary(carrier_id=carrier_id, days=days)

    return summary


# =============================================================================
# REFUEL PREDICTION ENDPOINTS (#17)
# =============================================================================
@router.get(
    "/predictions/refuel/{truck_id}",
    summary="Predict Next Refuel",
    tags=["Predictions"],
)
async def predict_refuel(
    truck_id: str,
    tank_capacity: float = Query(default=200.0, ge=50, le=500),
):
    """
    Predict when a truck will need refueling.

    Uses historical consumption patterns and ML regression.
    """
    from refuel_prediction import get_prediction_engine

    engine = get_prediction_engine()

    # Get current fuel level from database
    from database_mysql import MySQLDatabase

    db = MySQLDatabase()
    truck_data = db.get_truck_detail(truck_id)

    if not truck_data:
        raise HTTPException(status_code=404, detail=f"Truck {truck_id} not found")

    current_fuel_pct = truck_data.get("fuel_pct", 50)

    prediction = engine.predict_refuel(
        truck_id=truck_id,
        current_fuel_pct=current_fuel_pct,
        tank_capacity_gal=tank_capacity,
    )

    if not prediction:
        raise HTTPException(
            status_code=400,
            detail="Insufficient historical data for prediction (need 7+ days)",
        )

    return prediction.to_dict()


@router.get(
    "/predictions/fleet", summary="Fleet Refuel Predictions", tags=["Predictions"]
)
async def predict_fleet_refuels(
    carrier_id: Optional[str] = None,
):
    """
    Get refuel predictions for entire fleet.

    Returns trucks sorted by urgency (hours until refuel needed).
    """
    from refuel_prediction import get_prediction_engine

    engine = get_prediction_engine()
    predictions = engine.predict_fleet(carrier_id=carrier_id)

    return {
        "predictions": predictions,
        "total": len(predictions),
        "urgent": [
            p for p in predictions if p["prediction"]["hours_until_refuel_needed"] < 8
        ],
    }


@router.get(
    "/predictions/consumption/{truck_id}",
    summary="Consumption Trend",
    tags=["Predictions"],
)
async def get_consumption_trend(
    truck_id: str,
    days: int = Query(default=30, ge=7, le=90),
):
    """Get consumption trend analysis for a truck."""
    from refuel_prediction import get_prediction_engine

    engine = get_prediction_engine()
    trend = engine.get_consumption_trend(truck_id=truck_id, days=days)

    return trend


# =============================================================================
# FUEL COST ENDPOINTS (#19)
# =============================================================================
@router.get("/costs/truck/{truck_id}", summary="Truck Cost Summary", tags=["Costs"])
async def get_truck_costs(
    truck_id: str,
    days: int = Query(default=30, ge=1, le=90),
):
    """Get fuel cost summary for a specific truck."""
    from fuel_cost_tracker import get_cost_tracker

    tracker = get_cost_tracker()
    summary = tracker.get_truck_cost_summary(truck_id=truck_id, days=days)

    return summary


@router.get("/costs/fleet", summary="Fleet Cost Summary", tags=["Costs"])
async def get_fleet_costs(
    carrier_id: Optional[str] = None,
    days: int = Query(default=7, ge=1, le=30),
):
    """Get fuel cost summary for entire fleet."""
    from fuel_cost_tracker import get_cost_tracker

    tracker = get_cost_tracker()
    summary = tracker.get_fleet_cost_summary(carrier_id=carrier_id, days=days)

    return summary


@router.get("/costs/drivers/{truck_id}", summary="Compare Drivers", tags=["Costs"])
async def compare_drivers(
    truck_id: str,
    days: int = Query(default=30, ge=7, le=90),
):
    """Compare fuel costs between drivers on the same truck."""
    from fuel_cost_tracker import get_cost_tracker

    tracker = get_cost_tracker()
    comparison = tracker.compare_drivers(truck_id=truck_id, days=days)

    return comparison


@router.get("/cost/per-mile", summary="Fleet Cost Per Mile Analysis", tags=["Costs"])
async def get_cost_per_mile(
    days: int = Query(default=30, ge=1, le=90),
):
    """
    Get detailed cost per mile analysis for the fleet.

    Returns comprehensive breakdown including:
    - Fleet average cost per mile
    - Per-truck cost per mile with rankings
    - Industry benchmark comparisons
    - Cost breakdown (fuel, maintenance, tires, depreciation)
    - Potential savings opportunities
    """
    from cost_per_mile_engine import CostPerMileEngine
    from database_mysql import MySQLDatabase

    try:
        db = MySQLDatabase()
        engine = CostPerMileEngine(db)

        # Get truck metrics from database for the specified period
        query = f"""
        SELECT 
            truck_id,
            SUM(miles_traveled) as miles,
            SUM(fuel_consumed_gallons) as gallons,
            SUM(engine_hours_delta) as engine_hours,
            AVG(mpg) as avg_mpg
        FROM daily_truck_metrics
        WHERE date >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)
        AND miles_traveled > 0
        GROUP BY truck_id
        HAVING miles > 0 AND gallons > 0
        """

        trucks_data = []
        with db.get_connection() as conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute(query)
            trucks_data = cursor.fetchall()

        logger.info(
            f"Fetched {len(trucks_data)} trucks for cost per mile analysis ({days} days)"
        )

        # Get fleet analysis
        fleet_summary = engine.analyze_fleet_costs(
            trucks_data=trucks_data, period_days=days
        )

        # Format response to match frontend expectations
        return {
            "status": "success",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "data": {
                "period": {
                    "start": fleet_summary.period_start.isoformat(),
                    "end": fleet_summary.period_end.isoformat(),
                    "days": fleet_summary.period_days,
                },
                "fleet_summary": {
                    "total_trucks": fleet_summary.total_trucks,
                    "total_miles": fleet_summary.total_miles,
                    "total_fuel_gallons": fleet_summary.total_fuel_gallons,
                    "total_fuel_cost": fleet_summary.total_fuel_cost,
                },
                "cost_per_mile": {
                    "fleet_average": fleet_summary.fleet_avg_cost_per_mile,
                    "breakdown": fleet_summary.cost_breakdown.to_dict(),
                    "vs_industry_benchmark_percent": fleet_summary.vs_industry_benchmark_percent,
                    "industry_benchmark": 2.26,
                },
                "performance": {
                    "best": {
                        "truck_id": fleet_summary.best_truck,
                        "cost_per_mile": fleet_summary.best_cost_per_mile,
                    },
                    "worst": {
                        "truck_id": fleet_summary.worst_truck,
                        "cost_per_mile": fleet_summary.worst_cost_per_mile,
                    },
                },
                "savings": {
                    "potential_per_month": fleet_summary.total_potential_savings_per_month
                },
                "trucks": [
                    {
                        "truck_id": t.truck_id,
                        "cost_per_mile": t.cost_breakdown.total_cost_per_mile,
                        "miles": t.total_miles,
                        "gallons": t.total_fuel_gallons,
                        "engine_hours": t.total_engine_hours,
                        "avg_mpg": t.avg_mpg,
                    }
                    for t in fleet_summary.truck_analyses
                ],
            },
        }
    except Exception as e:
        logger.error(f"Error generating cost per mile analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# SENSOR ANOMALY ENDPOINTS (#21)
# =============================================================================
@router.get(
    "/sensors/anomalies/{truck_id}", summary="Detect Sensor Anomalies", tags=["Sensors"]
)
async def detect_sensor_anomalies(
    truck_id: str,
    sensor: str = Query(
        default="fuel_level", pattern="^(fuel_level|fuel_kalman|speed|mpg)$"
    ),
    hours: int = Query(default=24, ge=1, le=168),
):
    """Detect anomalies in sensor readings."""
    from sensor_anomaly import get_anomaly_detector

    detector = get_anomaly_detector()
    anomalies = detector.detect_anomalies(
        truck_id=truck_id,
        sensor_name=sensor,
        hours=hours,
    )

    return {
        "truck_id": truck_id,
        "sensor": sensor,
        "period_hours": hours,
        "anomalies": [a.to_dict() for a in anomalies],
        "total": len(anomalies),
    }


@router.get("/sensors/health/{truck_id}", summary="Sensor Health", tags=["Sensors"])
async def get_sensor_health(
    truck_id: str,
    sensor: str = Query(default="fuel_level"),
):
    """Get health status for a sensor."""
    from sensor_anomaly import get_anomaly_detector

    detector = get_anomaly_detector()
    health = detector.get_sensor_health(truck_id=truck_id, sensor_name=sensor)

    return health.to_dict()


@router.get("/sensors/fleet-status", summary="Fleet Sensor Status", tags=["Sensors"])
async def get_fleet_sensor_status(
    carrier_id: Optional[str] = None,
    sensor: str = Query(default="fuel_level"),
):
    """Get sensor health status for all trucks in fleet."""
    from sensor_anomaly import get_anomaly_detector

    detector = get_anomaly_detector()
    status = detector.get_fleet_sensor_status(
        carrier_id=carrier_id,
        sensor_name=sensor,
    )

    return status


@router.get(
    "/sensors/timeline/{truck_id}", summary="Anomaly Timeline", tags=["Sensors"]
)
async def get_anomaly_timeline(
    truck_id: str,
    sensor: str = Query(default="fuel_level"),
    hours: int = Query(default=24, ge=1, le=168),
):
    """Get timeline of anomalies for visualization."""
    from sensor_anomaly import get_anomaly_detector

    detector = get_anomaly_detector()
    timeline = detector.get_anomaly_timeline(
        truck_id=truck_id,
        sensor_name=sensor,
        hours=hours,
    )

    return timeline


# =============================================================================
# 🆕 v6.3.0: TRUCK SENSOR DATA ENDPOINT
# =============================================================================
@router.get(
    "/trucks/{truck_id}/sensors", summary="Real-time Sensor Data", tags=["Sensors"]
)
async def get_truck_sensors(truck_id: str):
    """
    Get comprehensive real-time sensor data for a truck.

    ⚡ OPTIMIZED v2.0: Reads from local cache table (truck_sensors_cache)
    Updated every 30 seconds by sensor_cache_updater.py service.
    Much faster than querying Wialon directly (1 simple SELECT vs 2000 rows).

    Returns all ECU sensor readings including:
    - Oil: Pressure (PSI), Temperature (°F), Level (%)
    - DEF: Tank Level (%)
    - Engine: Load (%), RPM, Coolant Temp (°F)
    - Transmission: Gear Position
    - Braking: Brake Switch status
    - Air Intake: Pressure (Bar), Temperature (°F)
    - Fuel: Temperature (°F), Level (%)
    - Environmental: Ambient Temp (°F), Barometric Pressure (inHg)
    - Electrical: Battery Voltage (V), Backup Battery (V)
    - Operational: Engine Hours, Idle Hours, PTO Hours
    """
    import os

    import mysql.connector

    # Connect to local fuel_copilot database
    FUEL_COPILOT_CONFIG = {
        "host": "localhost",
        "port": 3306,
        "user": os.getenv("MYSQL_USER", "fuel_admin"),
        "password": os.getenv("MYSQL_PASSWORD"),
        "database": "fuel_copilot",
    }

    try:
        conn = mysql.connector.connect(**FUEL_COPILOT_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Simple SELECT from cache table - super fast!
        query = """
            SELECT 
                truck_id, timestamp, data_age_seconds,
                oil_pressure_psi, oil_temp_f, oil_level_pct,
                def_level_pct,
                engine_load_pct, rpm, coolant_temp_f, coolant_level_pct,
                gear, brake_active,
                intake_pressure_bar, intake_temp_f, intercooler_temp_f,
                fuel_temp_f, fuel_level_pct, fuel_rate_gph,
                ambient_temp_f, barometric_pressure_inhg,
                voltage, backup_voltage,
                engine_hours, idle_hours, pto_hours,
                total_idle_fuel_gal, total_fuel_used_gal,
                dtc_count, dtc_code,
                latitude, longitude, speed_mph, altitude_ft, odometer_mi
            FROM truck_sensors_cache
            WHERE truck_id = %s
        """

        cursor.execute(query, (truck_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            # No data in cache - truck not found or no recent data
            return {
                "truck_id": truck_id,
                "timestamp": None,
                "data_available": False,
                "message": "No recent sensor data available. Cache may be updating.",
                "oil_pressure_psi": None,
                "oil_temp_f": None,
                "oil_level_pct": None,
                "def_level_pct": None,
                "engine_load_pct": None,
                "rpm": None,
                "coolant_temp_f": None,
                "coolant_level_pct": None,
                "gear": None,
                "brake_active": None,
                "intake_pressure_bar": None,
                "intake_temp_f": None,
                "intercooler_temp_f": None,
                "fuel_temp_f": None,
                "fuel_level_pct": None,
                "fuel_rate_gph": None,
                "ambient_temp_f": None,
                "barometric_pressure_inhg": None,
                "voltage": None,
                "backup_voltage": None,
                "engine_hours": None,
                "idle_hours": None,
                "pto_hours": None,
                "total_idle_fuel_gal": None,
                "total_fuel_used_gal": None,
                "dtc_count": None,
                "dtc_code": None,
                "latitude": None,
                "longitude": None,
                "speed_mph": None,
                "altitude_ft": None,
                "odometer_mi": None,
            }

        # Return cached data - already formatted and ready to use!
        return {
            "truck_id": row["truck_id"],
            "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
            "data_available": True,
            "data_age_seconds": row.get("data_age_seconds"),
            # Oil System
            "oil_pressure_psi": (
                float(row["oil_pressure_psi"])
                if row["oil_pressure_psi"] is not None
                else None
            ),
            "oil_temp_f": (
                float(row["oil_temp_f"]) if row["oil_temp_f"] is not None else None
            ),
            "oil_level_pct": (
                float(row["oil_level_pct"])
                if row["oil_level_pct"] is not None
                else None
            ),
            # DEF
            "def_level_pct": (
                float(row["def_level_pct"])
                if row["def_level_pct"] is not None
                else None
            ),
            # Engine
            "engine_load_pct": (
                float(row["engine_load_pct"])
                if row["engine_load_pct"] is not None
                else None
            ),
            "rpm": int(row["rpm"]) if row["rpm"] is not None else None,
            "coolant_temp_f": (
                float(row["coolant_temp_f"])
                if row["coolant_temp_f"] is not None
                else None
            ),
            "coolant_level_pct": (
                float(row["coolant_level_pct"])
                if row["coolant_level_pct"] is not None
                else None
            ),
            # Transmission & Brakes
            "gear": int(row["gear"]) if row["gear"] is not None else None,
            "brake_active": (
                bool(row["brake_active"]) if row["brake_active"] is not None else None
            ),
            # Air Intake
            "intake_pressure_bar": (
                float(row["intake_pressure_bar"])
                if row["intake_pressure_bar"] is not None
                else None
            ),
            "intake_temp_f": (
                float(row["intake_temp_f"])
                if row["intake_temp_f"] is not None
                else None
            ),
            "intercooler_temp_f": (
                float(row["intercooler_temp_f"])
                if row["intercooler_temp_f"] is not None
                else None
            ),
            # Fuel
            "fuel_temp_f": (
                float(row["fuel_temp_f"]) if row["fuel_temp_f"] is not None else None
            ),
            "fuel_level_pct": (
                float(row["fuel_level_pct"])
                if row["fuel_level_pct"] is not None
                else None
            ),
            "fuel_rate_gph": (
                float(row["fuel_rate_gph"])
                if row["fuel_rate_gph"] is not None
                else None
            ),
            # Environmental
            "ambient_temp_f": (
                float(row["ambient_temp_f"])
                if row["ambient_temp_f"] is not None
                else None
            ),
            "barometric_pressure_inhg": (
                float(row["barometric_pressure_inhg"])
                if row["barometric_pressure_inhg"] is not None
                else None
            ),
            # Electrical
            "voltage": float(row["voltage"]) if row["voltage"] is not None else None,
            "backup_voltage": (
                float(row["backup_voltage"])
                if row["backup_voltage"] is not None
                else None
            ),
            # Operational Counters
            "engine_hours": (
                float(row["engine_hours"]) if row["engine_hours"] is not None else None
            ),
            "idle_hours": (
                float(row["idle_hours"]) if row["idle_hours"] is not None else None
            ),
            "pto_hours": (
                float(row["pto_hours"]) if row["pto_hours"] is not None else None
            ),
            "total_idle_fuel_gal": (
                float(row["total_idle_fuel_gal"])
                if row["total_idle_fuel_gal"] is not None
                else None
            ),
            "total_fuel_used_gal": (
                float(row["total_fuel_used_gal"])
                if row["total_fuel_used_gal"] is not None
                else None
            ),
            # DTC
            "dtc_count": (
                int(row["dtc_count"]) if row["dtc_count"] is not None else None
            ),
            "dtc_code": row["dtc_code"],
            # GPS & Odometer
            "latitude": (
                float(row["latitude"]) if row["latitude"] is not None else None
            ),
            "longitude": (
                float(row["longitude"]) if row["longitude"] is not None else None
            ),
            "speed_mph": (
                float(row["speed_mph"]) if row["speed_mph"] is not None else None
            ),
            "altitude_ft": (
                float(row["altitude_ft"]) if row["altitude_ft"] is not None else None
            ),
            "odometer_mi": (
                float(row["odometer_mi"]) if row["odometer_mi"] is not None else None
            ),
        }

    except mysql.connector.Error as e:
        logger.error(f"MySQL error fetching sensors for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
    except Exception as e:
        logger.error(f"Error fetching sensors for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# DATA EXPORT ENDPOINTS (#22)
# =============================================================================
@router.post("/export/excel", summary="Export to Excel", tags=["Export"])
async def export_to_excel(
    request: ExportRequest,
    background_tasks: BackgroundTasks,
):
    """
    Export fleet data to Excel format.

    Returns Excel file as download.
    """
    from data_export import ExportConfig, get_exporter

    config = ExportConfig(
        carrier_id=request.carrier_id,
        truck_ids=request.truck_ids,
        start_date=request.start_date,
        end_date=request.end_date,
        include_metrics=request.include_metrics,
        include_refuels=request.include_refuels,
        include_alerts=request.include_alerts,
        include_summary=request.include_summary,
    )

    exporter = get_exporter()

    try:
        excel_data = exporter.export_to_excel(config)
        filename = exporter.generate_filename(config, "xlsx")

        return StreamingResponse(
            io.BytesIO(excel_data),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/export/pdf", summary="Export to PDF", tags=["Export"])
async def export_to_pdf(request: ExportRequest):
    """
    Export fleet data to PDF report.

    Returns PDF file as download.
    """
    from data_export import ExportConfig, get_exporter

    config = ExportConfig(
        carrier_id=request.carrier_id,
        truck_ids=request.truck_ids,
        start_date=request.start_date,
        end_date=request.end_date,
        include_metrics=request.include_metrics,
        include_refuels=request.include_refuels,
        include_alerts=request.include_alerts,
        include_summary=request.include_summary,
    )

    exporter = get_exporter()

    try:
        pdf_data = exporter.export_to_pdf(config)
        filename = exporter.generate_filename(config, "pdf")

        return StreamingResponse(
            io.BytesIO(pdf_data),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/csv/{data_type}", summary="Export to CSV", tags=["Export"])
async def export_to_csv(
    data_type: str,
    carrier_id: Optional[str] = None,
    truck_ids: Optional[str] = None,  # Comma-separated
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
):
    """
    Export specific data type to CSV.

    Data types: metrics, refuels, alerts, summary
    """
    from data_export import ExportConfig, get_exporter

    if data_type not in ("metrics", "refuels", "alerts", "summary"):
        raise HTTPException(status_code=400, detail="Invalid data type")

    config = ExportConfig(
        carrier_id=carrier_id,
        truck_ids=truck_ids.split(",") if truck_ids else None,
        start_date=start_date,
        end_date=end_date,
    )

    exporter = get_exporter()

    try:
        csv_data = exporter.export_to_csv(config, data_type=data_type)
        filename = f"{data_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

        return StreamingResponse(
            io.BytesIO(csv_data),
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# USER MANAGEMENT ENDPOINTS (#5-8)
# =============================================================================
@router.get("/users", summary="List Users", tags=["Users"])
async def list_users(
    carrier_id: Optional[str] = None,
):
    """List all users, optionally filtered by carrier."""
    from user_management import get_user_manager

    manager = get_user_manager()
    users = manager.list_users(carrier_id=carrier_id)

    return {
        "users": users,
        "total": len(users),
    }


@router.get("/carriers", summary="List Carriers", tags=["Users"])
async def list_carriers(
    active_only: bool = True,
):
    """List all carriers."""
    from user_management import get_user_manager

    manager = get_user_manager()
    carriers = manager.list_carriers(active_only=active_only)

    return {
        "carriers": carriers,
        "total": len(carriers),
    }


# =============================================================================
# DRIVER BEHAVIOR ENDPOINTS (#NEW v5.10.0)
# =============================================================================
@router.get(
    "/behavior/score/{truck_id}",
    summary="Heavy Foot Score",
    tags=["Driver Behavior"],
)
async def get_heavy_foot_score(
    truck_id: str,
    period_hours: float = Query(24.0, ge=1, le=168, description="Hours to analyze"),
):
    """
    Get "Heavy Foot" score for a specific truck.

    Score breakdown:
    - 100 = Perfect driver
    - 80+ = Good driver (grade A/B)
    - 60-79 = Average driver (grade C/D)
    - <60 = Aggressive driver (grade F)

    Components analyzed:
    - Hard acceleration events
    - Hard braking events
    - High RPM operation
    - Wrong gear usage (if gear sensor available)
    - Overspeeding
    """
    from driver_behavior_engine import get_behavior_engine

    engine = get_behavior_engine()
    score = engine.calculate_heavy_foot_score(truck_id, period_hours=period_hours)

    return score.to_dict()


@router.get(
    "/behavior/fleet",
    summary="Fleet Behavior Summary",
    tags=["Driver Behavior"],
)
async def get_fleet_behavior_summary():
    """
    Get fleet-wide driver behavior summary.

    Returns:
    - Best/worst performers
    - Total fuel waste by behavior category
    - Common issues across fleet
    - Actionable recommendations
    """
    from driver_behavior_engine import get_behavior_engine

    engine = get_behavior_engine()
    summary = engine.get_fleet_behavior_summary()

    # 🔧 v6.2.8: Always return valid response, no more 404
    return summary


@router.get(
    "/behavior/mpg-validation/{truck_id}",
    summary="MPG Cross-Validation",
    tags=["Driver Behavior"],
)
async def get_mpg_cross_validation(truck_id: str):
    """
    Compare Kalman-filtered MPG vs ECU fuel_economy sensor.

    Returns validation status showing if our MPG calculation
    matches the truck's ECU reading.

    Requires fuel_economy sensor to be available.
    """
    from driver_behavior_engine import get_behavior_engine

    engine = get_behavior_engine()
    result = engine.cross_validate_mpg(truck_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Not enough data for cross-validation. Need fuel_economy sensor and recent readings.",
        )

    return result.to_dict()


@router.get(
    "/behavior/events/{truck_id}",
    summary="Recent Behavior Events",
    tags=["Driver Behavior"],
)
async def get_behavior_events(
    truck_id: str,
    severity: Optional[str] = Query(
        None, description="Filter by severity: minor, moderate, severe, critical"
    ),
    limit: int = Query(50, ge=1, le=200),
):
    """
    Get recent behavior events for a truck.

    Events include:
    - Hard acceleration
    - Hard braking
    - Excessive RPM
    - Wrong gear usage
    - Overspeeding
    """
    from driver_behavior_engine import get_behavior_engine

    engine = get_behavior_engine()
    state = engine.truck_states.get(truck_id)

    if state is None:
        raise HTTPException(
            status_code=404, detail=f"No behavior data for truck {truck_id}"
        )

    events = state.events

    # Filter by severity if specified
    if severity:
        events = [e for e in events if e.severity.value == severity]

    # Return most recent events
    events = sorted(events, key=lambda e: e.timestamp, reverse=True)[:limit]

    return {
        "truck_id": truck_id,
        "total_events": len(state.events),
        "events": [e.to_dict() for e in events],
    }


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.11.0: PREDICTIVE MAINTENANCE ENDPOINTS
# Uses trend analysis to predict failures BEFORE they happen
# ═══════════════════════════════════════════════════════════════════════════════


@router.get(
    "/maintenance/status/{truck_id}",
    summary="Truck Maintenance Status",
    tags=["Predictive Maintenance"],
)
async def get_truck_maintenance_status(truck_id: str):
    """
    Get predictive maintenance status for a truck.

    Uses sensor trend analysis to predict when components will need service.

    Example: "Trans temp subiendo +2.1°F/día → llegará a zona crítica en ~5 días"

    Sensors analyzed:
    - Oil pressure (bomba de aceite)
    - Coolant temp (sistema enfriamiento)
    - Trans temp (transmisión)
    - Turbo temp (turbocompresor)
    - Boost pressure (turbo/intercooler)
    - DEF level (sistema DEF)
    - Battery voltage (sistema eléctrico)
    """
    from predictive_maintenance_engine import get_predictive_maintenance_engine

    engine = get_predictive_maintenance_engine()
    status = engine.get_truck_maintenance_status(truck_id)

    if status is None:
        raise HTTPException(
            status_code=404, detail=f"No maintenance data for truck {truck_id}"
        )

    return status


@router.get(
    "/maintenance/alerts/{truck_id}",
    summary="Maintenance Alerts",
    tags=["Predictive Maintenance"],
)
async def get_maintenance_alerts(truck_id: str):
    """
    Get active maintenance alerts for a truck.

    Only returns CRITICAL and HIGH priority items that need attention.

    Alerts include:
    - Days until component reaches critical threshold
    - Current value and trend
    - Recommended action
    - Estimated cost if failure occurs
    """
    from predictive_maintenance_engine import get_predictive_maintenance_engine

    engine = get_predictive_maintenance_engine()
    alerts = engine.get_maintenance_alerts(truck_id)

    return {
        "truck_id": truck_id,
        "alerts": alerts,
        "total_alerts": len(alerts),
    }


@router.get(
    "/maintenance/fleet",
    summary="Fleet Maintenance Overview",
    tags=["Predictive Maintenance"],
)
async def get_fleet_maintenance():
    """
    Get fleet-wide predictive maintenance summary.

    Returns:
    - Count of trucks by urgency level (critical/high/medium/low)
    - Top critical items requiring immediate attention
    - High priority items for this week
    - Fleet-wide recommendations

    Example insight:
    "3 camiones con problemas en Transmisión - considerar revisión de flota"
    """
    from predictive_maintenance_engine import get_predictive_maintenance_engine

    engine = get_predictive_maintenance_engine()
    summary = engine.get_fleet_summary()

    return summary


@router.get(
    "/maintenance/trend/{truck_id}/{sensor_name}",
    summary="Sensor Trend Analysis",
    tags=["Predictive Maintenance"],
)
async def get_sensor_trend(truck_id: str, sensor_name: str):
    """
    Get detailed trend analysis for a specific sensor.

    Valid sensor names:
    - oil_pressure, coolant_temp, oil_temp
    - turbo_temp, boost_pressure, intercooler_temp
    - trans_temp, fuel_temp
    - battery_voltage, def_level
    - brake_air_pressure, mpg

    Returns:
    - Current value
    - Trend per day (e.g., +2.1°F/día)
    - Historical daily averages
    - Warning and critical thresholds
    """
    from predictive_maintenance_engine import get_predictive_maintenance_engine

    engine = get_predictive_maintenance_engine()
    trend = engine.get_sensor_trend(truck_id, sensor_name)

    if trend is None:
        raise HTTPException(
            status_code=404,
            detail=f"No trend data for {sensor_name} on truck {truck_id}",
        )

    return trend


# =============================================================================
# DEF (DIESEL EXHAUST FLUID) ENDPOINTS
# =============================================================================


@router.get("/def/fleet-status", summary="DEF Fleet Status", tags=["DEF Analytics"])
async def get_def_fleet_status():
    """
    Get DEF status summary for entire fleet.

    Returns:
    - Fleet status (good/attention/warning/critical/emergency)
    - Average DEF level across fleet
    - Level distribution by status
    - Trucks needing attention with recommendations
    """
    from def_predictor import get_def_predictor

    predictor = get_def_predictor()
    status = predictor.get_fleet_def_status()

    return status


@router.get("/def/predictions", summary="DEF Predictions", tags=["DEF Analytics"])
async def get_def_predictions(
    alert_level: Optional[str] = Query(
        None,
        description="Filter by alert level: good, low, warning, critical, emergency",
    )
):
    """
    Get DEF predictions for all trucks.

    Optionally filter by alert level.

    Returns predictions sorted by urgency (most urgent first).
    """
    from def_predictor import get_def_predictor

    predictor = get_def_predictor()
    predictions = predictor.predict_all()

    # Filter by alert level if specified
    if alert_level:
        predictions = [p for p in predictions if p.alert_level.value == alert_level]

    return {
        "predictions": [predictor.to_dict(p) for p in predictions],
        "count": len(predictions),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/def/predictions/{truck_id}",
    summary="DEF Prediction for Truck",
    tags=["DEF Analytics"],
)
async def get_def_prediction(truck_id: str):
    """
    Get DEF prediction for a specific truck.

    Returns:
    - Current DEF level (percent and gallons)
    - Alert level
    - Predictions (miles/hours/days until empty)
    - Consumption rates
    - Recommendation
    """
    from def_predictor import get_def_predictor

    predictor = get_def_predictor()
    prediction = predictor.predict(truck_id)

    if prediction is None:
        raise HTTPException(
            status_code=404,
            detail=f"No DEF data available for truck {truck_id}",
        )

    return {"prediction": predictor.to_dict(prediction)}


@router.get("/def/alerts", summary="DEF Alerts", tags=["DEF Analytics"])
async def get_def_alerts():
    """
    Get list of trucks with DEF alerts (needing attention).

    Returns only trucks with alert_level warning, critical, or emergency.
    Sorted by urgency score (most urgent first).
    """
    from def_predictor import DEFAlertLevel, get_def_predictor

    predictor = get_def_predictor()
    predictions = predictor.predict_all()

    # Filter for trucks needing attention
    alert_levels = {
        DEFAlertLevel.WARNING,
        DEFAlertLevel.CRITICAL,
        DEFAlertLevel.EMERGENCY,
    }
    alerts = [
        {
            "truck_id": p.truck_id,
            "level_percent": p.current_level_percent,
            "alert_level": p.alert_level.value,
            "miles_until_empty": p.miles_until_empty,
            "days_until_empty": p.days_until_empty,
            "urgency_score": p.urgency_score,
            "recommendation": p.recommended_action,
        }
        for p in predictions
        if p.alert_level in alert_levels
    ]

    return {
        "alerts": alerts,
        "count": len(alerts),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# TRIP AND DRIVER BEHAVIOR ENDPOINTS
# =============================================================================
@router.get("/trucks/{truck_id}/trips", summary="Get Truck Trips", tags=["Trips"])
async def get_truck_trips(
    truck_id: str,
    days: int = Query(
        default=7, ge=1, le=30, description="Number of days to look back"
    ),
    limit: int = Query(default=50, ge=1, le=500, description="Max trips to return"),
):
    """
    Get recent trips for a specific truck.

    Returns trip history including:
    - Duration and distance
    - Average/max speed
    - Driver behavior metrics (harsh events, speeding)
    """
    from database_mysql import get_connection

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    truck_id,
                    start_time,
                    end_time,
                    duration_hours,
                    distance_miles,
                    avg_speed,
                    max_speed,
                    odometer,
                    driver_name,
                    harsh_accel_count,
                    harsh_brake_count,
                    speeding_count,
                    created_at
                FROM truck_trips
                WHERE truck_id = %s
                  AND start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
                ORDER BY start_time DESC
                LIMIT %s
            """
            cursor.execute(query, (truck_id, days, limit))
            trips = cursor.fetchall()

            # Calculate summary stats
            total_distance = sum(t["distance_miles"] or 0 for t in trips)
            total_hours = sum(t["duration_hours"] or 0 for t in trips)
            total_speeding = sum(t["speeding_count"] or 0 for t in trips)
            total_harsh_accel = sum(t["harsh_accel_count"] or 0 for t in trips)
            total_harsh_brake = sum(t["harsh_brake_count"] or 0 for t in trips)

            avg_speed = (total_distance / total_hours) if total_hours > 0 else 0

            return {
                "truck_id": truck_id,
                "trips": [
                    {
                        "start_time": (
                            t["start_time"].isoformat() if t["start_time"] else None
                        ),
                        "end_time": (
                            t["end_time"].isoformat() if t["end_time"] else None
                        ),
                        "duration_hours": (
                            round(t["duration_hours"], 2) if t["duration_hours"] else 0
                        ),
                        "distance_miles": (
                            round(t["distance_miles"], 2) if t["distance_miles"] else 0
                        ),
                        "avg_speed": round(t["avg_speed"], 1) if t["avg_speed"] else 0,
                        "max_speed": round(t["max_speed"], 1) if t["max_speed"] else 0,
                        "odometer": round(t["odometer"], 1) if t["odometer"] else 0,
                        "driver": t["driver_name"],
                        "harsh_accel": t["harsh_accel_count"] or 0,
                        "harsh_brake": t["harsh_brake_count"] or 0,
                        "speeding": t["speeding_count"] or 0,
                    }
                    for t in trips
                ],
                "summary": {
                    "total_trips": len(trips),
                    "total_distance_miles": round(total_distance, 1),
                    "total_hours": round(total_hours, 1),
                    "avg_speed_mph": round(avg_speed, 1),
                    "total_speeding_events": total_speeding,
                    "total_harsh_accel": total_harsh_accel,
                    "total_harsh_brake": total_harsh_brake,
                },
                "period_days": days,
            }
    except Exception as e:
        logger.error(f"Failed to fetch trips for truck {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch trips: {str(e)}")
    finally:
        if conn:
            conn.close()


@router.get(
    "/trucks/{truck_id}/speeding-events",
    summary="Get Speeding Events",
    tags=["Driver Behavior"],
)
async def get_speeding_events(
    truck_id: str,
    days: int = Query(
        default=7, ge=1, le=30, description="Number of days to look back"
    ),
    severity: Optional[str] = Query(
        default=None,
        pattern="^(minor|moderate|severe)$",
        description="Filter by severity",
    ),
):
    """
    Get speeding violation events for a specific truck.

    Returns:
    - Timestamp and duration
    - Speed vs limit
    - Severity classification
    - Driver information
    """
    from database_mysql import get_connection

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            query = """
                SELECT 
                    truck_id,
                    start_time,
                    end_time,
                    duration_minutes,
                    max_speed,
                    speed_limit,
                    speed_over_limit,
                    distance_miles,
                    driver_name,
                    severity,
                    latitude,
                    longitude,
                    created_at
                FROM truck_speeding_events
                WHERE truck_id = %s
                  AND start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
            """

            params = [truck_id, days]
            if severity:
                query += " AND severity = %s"
                params.append(severity)

            query += " ORDER BY start_time DESC"

            cursor.execute(query, params)
            events = cursor.fetchall()

            # Calculate stats by severity
            severity_counts = {"minor": 0, "moderate": 0, "severe": 0}
            for event in events:
                severity_counts[event["severity"]] += 1

            return {
                "truck_id": truck_id,
                "events": [
                    {
                        "start_time": (
                            e["start_time"].isoformat() if e["start_time"] else None
                        ),
                        "end_time": (
                            e["end_time"].isoformat() if e["end_time"] else None
                        ),
                        "duration_minutes": (
                            round(e["duration_minutes"], 1)
                            if e["duration_minutes"]
                            else 0
                        ),
                        "max_speed": round(e["max_speed"], 1) if e["max_speed"] else 0,
                        "speed_limit": (
                            round(e["speed_limit"], 1) if e["speed_limit"] else 0
                        ),
                        "speed_over_limit": (
                            round(e["speed_over_limit"], 1)
                            if e["speed_over_limit"]
                            else 0
                        ),
                        "distance_miles": (
                            round(e["distance_miles"], 2) if e["distance_miles"] else 0
                        ),
                        "driver": e["driver_name"],
                        "severity": e["severity"],
                        "location": (
                            {"lat": e["latitude"], "lon": e["longitude"]}
                            if e["latitude"] and e["longitude"]
                            else None
                        ),
                    }
                    for e in events
                ],
                "summary": {
                    "total_events": len(events),
                    "by_severity": severity_counts,
                },
                "period_days": days,
            }
    except Exception as e:
        logger.error(f"Failed to fetch speeding events for truck {truck_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch speeding events: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


@router.get(
    "/fleet/driver-behavior",
    summary="Fleet Driver Behavior Metrics",
    tags=["Driver Behavior"],
)
async def get_fleet_driver_behavior(
    days: int = Query(default=7, ge=1, le=30, description="Number of days to analyze")
):
    """
    Get fleet-wide driver behavior metrics and scoring.

    Analyzes:
    - Speeding violations
    - Harsh acceleration/braking
    - Driver safety scores
    """
    from database_mysql import get_connection

    try:
        conn = get_connection()
        with conn.cursor() as cursor:
            # Get trip-based metrics
            trips_query = """
                SELECT 
                    truck_id,
                    COUNT(*) as trip_count,
                    SUM(distance_miles) as total_miles,
                    SUM(speeding_count) as total_speeding,
                    SUM(harsh_accel_count) as total_harsh_accel,
                    SUM(harsh_brake_count) as total_harsh_brake,
                    AVG(avg_speed) as avg_speed
                FROM truck_trips
                WHERE start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY truck_id
            """
            cursor.execute(trips_query, (days,))
            trip_metrics = cursor.fetchall()

            # Get speeding event details
            speeding_query = """
                SELECT 
                    truck_id,
                    severity,
                    COUNT(*) as event_count
                FROM truck_speeding_events
                WHERE start_time >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY truck_id, severity
            """
            cursor.execute(speeding_query, (days,))
            speeding_by_severity = cursor.fetchall()

            # Build truck profiles
            truck_profiles = {}
            for tm in trip_metrics:
                truck_id = tm["truck_id"]
                total_miles = tm["total_miles"] or 0

                # Calculate safety score (0-100, higher is better)
                # Deduct points for violations per 100 miles
                base_score = 100
                if total_miles > 0:
                    speeding_penalty = min(
                        30, (tm["total_speeding"] / total_miles * 100) * 10
                    )
                    accel_penalty = min(
                        20, (tm["total_harsh_accel"] / total_miles * 100) * 10
                    )
                    brake_penalty = min(
                        20, (tm["total_harsh_brake"] / total_miles * 100) * 10
                    )
                    safety_score = max(
                        0, base_score - speeding_penalty - accel_penalty - brake_penalty
                    )
                else:
                    safety_score = base_score

                truck_profiles[truck_id] = {
                    "truck_id": truck_id,
                    "trips": tm["trip_count"],
                    "total_miles": round(total_miles, 1),
                    "speeding_events": tm["total_speeding"] or 0,
                    "harsh_accel": tm["total_harsh_accel"] or 0,
                    "harsh_brake": tm["total_harsh_brake"] or 0,
                    "avg_speed": round(tm["avg_speed"], 1) if tm["avg_speed"] else 0,
                    "safety_score": round(safety_score, 1),
                    "speeding_by_severity": {"minor": 0, "moderate": 0, "severe": 0},
                }

            # Add speeding severity breakdown
            for se in speeding_by_severity:
                truck_id = se["truck_id"]
                if truck_id in truck_profiles:
                    truck_profiles[truck_id]["speeding_by_severity"][se["severity"]] = (
                        se["event_count"]
                    )

            # Fleet-wide aggregates
            fleet_total_miles = sum(p["total_miles"] for p in truck_profiles.values())
            fleet_total_speeding = sum(
                p["speeding_events"] for p in truck_profiles.values()
            )
            fleet_total_harsh_accel = sum(
                p["harsh_accel"] for p in truck_profiles.values()
            )
            fleet_total_harsh_brake = sum(
                p["harsh_brake"] for p in truck_profiles.values()
            )
            fleet_avg_safety_score = (
                sum(p["safety_score"] for p in truck_profiles.values())
                / len(truck_profiles)
                if truck_profiles
                else 0
            )

            return {
                "trucks": list(truck_profiles.values()),
                "fleet_summary": {
                    "total_trucks": len(truck_profiles),
                    "total_miles": round(fleet_total_miles, 1),
                    "total_speeding_events": fleet_total_speeding,
                    "total_harsh_accel": fleet_total_harsh_accel,
                    "total_harsh_brake": fleet_total_harsh_brake,
                    "avg_safety_score": round(fleet_avg_safety_score, 1),
                    "violations_per_100_miles": round(
                        (
                            (fleet_total_speeding / fleet_total_miles * 100)
                            if fleet_total_miles > 0
                            else 0
                        ),
                        2,
                    ),
                },
                "period_days": days,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
    except Exception as e:
        logger.error(f"Failed to calculate fleet driver behavior: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to calculate driver behavior: {str(e)}"
        )
    finally:
        if conn:
            conn.close()


# =============================================================================
# RUL PREDICTOR ENDPOINTS
# =============================================================================
@router.get(
    "/rul-predictions/{truck_id}",
    summary="Get RUL Predictions",
    tags=["Predictive Maintenance"],
)
async def get_rul_predictions(
    truck_id: str,
    component: Optional[str] = Query(
        None, description="Specific component to predict (turbo, oil, coolant, etc.)"
    ),
):
    """
    Get Remaining Useful Life (RUL) predictions for truck components.

    Predicts days and miles until component failure using:
    - Linear degradation model (constant rate)
    - Exponential degradation model (accelerating failure)

    Returns predictions with confidence scores and recommended service dates.
    """
    try:
        import os

        import mysql.connector

        from rul_predictor import RULPredictor

        predictor = RULPredictor()

        # Connect to local fuel_copilot database
        DB_CONFIG = {
            "host": "localhost",
            "port": 3306,
            "user": os.getenv("MYSQL_USER", "fuel_admin"),
            "password": os.getenv("MYSQL_PASSWORD"),
            "database": "fuel_copilot",
        }

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Get component health history from database
        # Query last 60 days of health scores
        query = """
        SELECT 
            timestamp,
            turbo_health,
            oil_consumption_health,
            coolant_leak_health,
            def_system_health,
            battery_health,
            alternator_health
        FROM component_health
        WHERE truck_id = %s
        AND timestamp >= DATE_SUB(NOW(), INTERVAL 60 DAY)
        ORDER BY timestamp ASC
        """

        cursor.execute(query, (truck_id,))
        rows = cursor.fetchall()

        if not rows:
            return {
                "truck_id": truck_id,
                "predictions": [],
                "message": "No health history found for this truck",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Build history dict for each component
        component_histories = {
            "turbo_health": [],
            "oil_consumption_health": [],
            "coolant_leak_health": [],
            "def_system_health": [],
            "battery_health": [],
            "alternator_health": [],
        }

        for row in rows:
            timestamp = row["timestamp"]
            for comp in component_histories.keys():
                if row[comp] is not None:
                    component_histories[comp].append((timestamp, row[comp]))

        # Generate predictions
        predictions = []

        components_to_check = [component] if component else component_histories.keys()

        for comp_name in components_to_check:
            history = component_histories.get(comp_name, [])
            if not history:
                continue

            prediction = predictor.predict_rul(comp_name, history)

            if prediction:
                pred_dict = {
                    "component": prediction.component,
                    "current_score": prediction.current_score,
                    "model_used": prediction.model_used,
                    "rul_days": prediction.rul_days,
                    "rul_miles": prediction.rul_miles,
                    "degradation_rate_per_day": prediction.degradation_rate_per_day,
                    "confidence": prediction.confidence,
                    "recommended_service_date": (
                        prediction.recommended_service_date.isoformat()
                        if prediction.recommended_service_date
                        else None
                    ),
                    "estimated_repair_cost": prediction.estimated_repair_cost,
                    "status": prediction.status,
                    "message": prediction.message,
                }
                predictions.append(pred_dict)

        return {
            "truck_id": truck_id,
            "predictions": predictions,
            "count": len(predictions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get RUL predictions for {truck_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get RUL predictions: {str(e)}"
        )
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


# =============================================================================
# SIPHONING DETECTION ENDPOINTS
# =============================================================================
@router.get(
    "/siphoning-alerts",
    summary="Get Siphoning Alerts",
    tags=["Theft Detection"],
)
async def get_siphoning_alerts(
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
    truck_id: Optional[str] = Query(None, description="Filter by specific truck"),
    min_confidence: float = Query(
        0.5, ge=0.0, le=1.0, description="Minimum confidence threshold"
    ),
):
    """
    Get slow siphoning detection alerts for the fleet.

    Detects gradual fuel theft (2%/day over multiple days) that evades instant detection.
    Returns alerts with confidence scores and recommendations.
    """
    try:
        import os

        import mysql.connector

        from siphon_detector import SlowSiphonDetector

        detector = SlowSiphonDetector()

        # Connect to local fuel_copilot database
        DB_CONFIG = {
            "host": "localhost",
            "port": 3306,
            "user": os.getenv("MYSQL_USER", "fuel_admin"),
            "password": os.getenv("MYSQL_PASSWORD"),
            "database": "fuel_copilot",
        }

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Get fuel readings for analysis
        truck_filter = "AND truck_id = %s" if truck_id else ""
        params = [days]
        if truck_id:
            params.append(truck_id)

        query = f"""
        SELECT 
            truck_id,
            timestamp,
            fuel_level_pct,
            fuel_level_liters,
            odometer_km
        FROM fuel_readings
        WHERE timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
        {truck_filter}
        ORDER BY truck_id, timestamp ASC
        """

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()

        if not rows:
            return {
                "alerts": [],
                "period_days": days,
                "message": "No fuel data found for analysis",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Group by truck
        truck_readings = {}
        for row in rows:
            tid = row["truck_id"]
            if tid not in truck_readings:
                truck_readings[tid] = []
            truck_readings[tid].append(row)

        # Analyze each truck
        alerts = []
        for tid, readings in truck_readings.items():
            # Assume 200 gallon tank (standard semi truck)
            tank_capacity_gal = 200.0

            alert = detector.analyze(tid, readings, tank_capacity_gal)

            if alert and alert.confidence >= min_confidence:
                alert_dict = {
                    "truck_id": tid,
                    "start_date": alert.start_date,
                    "end_date": alert.end_date,
                    "period_days": alert.period_days,
                    "total_gallons_lost": alert.total_gallons_lost,
                    "avg_daily_loss_gal": alert.avg_daily_loss_gal,
                    "confidence": alert.confidence,
                    "pattern_description": alert.pattern_description,
                    "recommendation": alert.recommendation,
                }
                alerts.append(alert_dict)

        # Sort by confidence (highest first)
        alerts.sort(key=lambda x: x["confidence"], reverse=True)

        return {
            "alerts": alerts,
            "count": len(alerts),
            "period_days": days,
            "total_loss_gallons": sum(a["total_gallons_lost"] for a in alerts),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get siphoning alerts: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get siphoning alerts: {str(e)}"
        )
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


# =============================================================================
# MPG CONTEXT ENDPOINTS
# =============================================================================
@router.get(
    "/mpg-context/{truck_id}",
    summary="Get MPG Context",
    tags=["Fuel Efficiency"],
)
async def get_mpg_context(
    truck_id: str,
    days: int = Query(7, ge=1, le=30, description="Number of days to analyze"),
):
    """
    Get MPG context explanation for driver scoring.

    Returns route-specific baselines and adjustment factors:
    - Route type (Highway, City, Mountain, etc.)
    - Load factors (Empty, Normal, Heavy, Overloaded)
    - Weather factors (Clear, Rain, Snow, etc.)
    - Terrain factors (Flat, Rolling, Hilly, Mountainous)

    Helps explain why expected MPG differs from baseline.
    """
    try:
        import os

        import mysql.connector

        from mpg_context import (
            MPGContextEngine,
            RouteContext,
            RouteType,
            WeatherCondition,
        )

        engine = MPGContextEngine()

        # Connect to local fuel_copilot database
        DB_CONFIG = {
            "host": "localhost",
            "port": 3306,
            "user": os.getenv("MYSQL_USER", "fuel_admin"),
            "password": os.getenv("MYSQL_PASSWORD"),
            "database": "fuel_copilot",
        }

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Get recent trip data
        query = """
        SELECT 
            timestamp,
            avg_speed_mph,
            stop_count,
            distance_miles,
            elevation_change_ft,
            is_loaded,
            load_weight_lbs,
            weather_condition,
            ambient_temp_f,
            actual_mpg
        FROM trip_data
        WHERE truck_id = %s
        AND timestamp >= DATE_SUB(NOW(), INTERVAL %s DAY)
        ORDER BY timestamp DESC
        LIMIT 50
        """

        cursor.execute(query, (truck_id, days))
        rows = cursor.fetchall()

        if not rows:
            return {
                "truck_id": truck_id,
                "contexts": [],
                "message": "No trip data found for this truck",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        # Analyze contexts
        contexts = []

        for row in rows:
            # Classify route
            route_type = engine.classify_route(
                avg_speed_mph=row["avg_speed_mph"] or 45.0,
                stop_count=row["stop_count"] or 10,
                distance_miles=row["distance_miles"] or 100.0,
                elevation_change_ft=row["elevation_change_ft"] or 0.0,
            )

            # Map weather string to enum
            weather_map = {
                "clear": WeatherCondition.CLEAR,
                "rain": WeatherCondition.RAIN,
                "snow": WeatherCondition.SNOW,
                "wind": WeatherCondition.WIND,
                "extreme_cold": WeatherCondition.EXTREME_COLD,
                "extreme_heat": WeatherCondition.EXTREME_HEAT,
            }
            weather = weather_map.get(
                row.get("weather_condition", "clear"), WeatherCondition.CLEAR
            )

            # Create context
            context = RouteContext(
                route_type=route_type,
                avg_speed_mph=row["avg_speed_mph"] or 45.0,
                stop_count=row["stop_count"] or 10,
                elevation_change_ft=row["elevation_change_ft"] or 0.0,
                distance_miles=row["distance_miles"] or 100.0,
                is_loaded=row.get("is_loaded", True),
                load_weight_lbs=row.get("load_weight_lbs"),
                weather=weather,
                ambient_temp_f=row.get("ambient_temp_f"),
            )

            # Calculate expected MPG
            result = engine.calculate_expected_mpg(context)

            context_dict = {
                "timestamp": row["timestamp"].isoformat(),
                "route_type": route_type.value,
                "baseline_mpg": result.baseline_mpg,
                "expected_mpg": result.expected_mpg,
                "actual_mpg": row.get("actual_mpg"),
                "route_factor": result.route_factor,
                "load_factor": result.load_factor,
                "weather_factor": result.weather_factor,
                "terrain_factor": result.terrain_factor,
                "combined_factor": result.combined_factor,
                "confidence": result.confidence,
                "explanation": result.explanation,
            }
            contexts.append(context_dict)

        # Calculate averages
        avg_expected_mpg = (
            sum(c["expected_mpg"] for c in contexts) / len(contexts) if contexts else 0
        )
        avg_actual_mpg = (
            sum(c.get("actual_mpg", 0) for c in contexts if c.get("actual_mpg"))
            / len([c for c in contexts if c.get("actual_mpg")])
            if any(c.get("actual_mpg") for c in contexts)
            else 0
        )

        return {
            "truck_id": truck_id,
            "contexts": contexts,
            "summary": {
                "period_days": days,
                "trip_count": len(contexts),
                "avg_expected_mpg": round(avg_expected_mpg, 2),
                "avg_actual_mpg": (
                    round(avg_actual_mpg, 2) if avg_actual_mpg > 0 else None
                ),
                "performance_vs_expected": (
                    round(
                        ((avg_actual_mpg - avg_expected_mpg) / avg_expected_mpg * 100),
                        1,
                    )
                    if avg_expected_mpg > 0 and avg_actual_mpg > 0
                    else None
                ),
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        error_msg = str(e)
        # 🔧 FIX Dec 20 2025: Manejar tabla trip_data no existente
        if "trip_data" in error_msg and "doesn't exist" in error_msg:
            logger.warning(
                f"Table trip_data not found - MPG context not available for {truck_id}"
            )
            return {
                "truck_id": truck_id,
                "contexts": [],
                "summary": {
                    "period_days": days,
                    "trip_count": 0,
                    "avg_expected_mpg": None,
                    "avg_actual_mpg": None,
                    "performance_vs_expected": None,
                },
                "message": "MPG context analysis requires trip_data table (feature not yet available)",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        logger.error(f"Failed to get MPG context for {truck_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get MPG context: {str(e)}"
        )
    finally:
        if "cursor" in locals():
            cursor.close()
        if "conn" in locals():
            conn.close()


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v7.1: PREDICTIVE MAINTENANCE v4 - RUL PREDICTOR
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/trucks/{truck_id}/predictive-maintenance")
async def get_predictive_maintenance(truck_id: str):
    """
    🔧 Predictive Maintenance v4 - RUL (Remaining Useful Life) Predictor

    Analyzes component health and predicts failures before they occur.

    **ROI:**
    - $15,000-$30,000/truck/year in avoided breakdowns
    - 40% reduction in unplanned downtime

    **Components Monitored:**
    - ECM/ECU (Engine Control Module)
    - Turbocharger
    - DPF (Diesel Particulate Filter)
    - DEF System
    - Cooling System

    Returns:
    - Component health scores (0-100)
    - RUL predictions in days
    - Maintenance alerts prioritized by urgency
    - Cost estimates for repairs
    """
    try:
        from predictive_maintenance_v4 import get_rul_predictor

        predictor = get_rul_predictor()

        # Connect to local fuel_copilot database
        DB_CONFIG = {
            "host": "localhost",
            "port": 3306,
            "user": os.getenv("MYSQL_USER", "fuel_admin"),
            "password": os.getenv("MYSQL_PASSWORD"),
            "database": "fuel_copilot",
        }

        import mysql.connector

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Get latest sensor readings from truck_sensors_cache
        query = """
        SELECT 
            rpm, oil_temp_f as oil_temp, coolant_temp_f as cool_temp, 
            oil_pressure_psi as oil_press, def_level_pct as def_level,
            engine_load_pct as engine_load, turbo_pressure_psi as boost_press, 
            egr_temp_f as egt, fuel_level_pct,
            odometer_mi as odometer_km, engine_hours as engine_hours_total
        FROM truck_sensors_cache
        WHERE truck_id = %s
        LIMIT 1
        """

        cursor.execute(query, (truck_id,))
        sensor_row = cursor.fetchone()

        if not sensor_row:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=404, detail=f"No sensor data found for truck {truck_id}"
            )

        # Convert to sensor_readings dict (handle None values)
        sensor_readings = {
            k: float(v) if v is not None else 0.0
            for k, v in sensor_row.items()
            if k not in ["odometer_km", "engine_hours_total"]
        }

        engine_hours = float(sensor_row.get("engine_hours_total") or 0)

        # Analyze truck components
        component_healths, maintenance_alerts = predictor.analyze_truck(
            truck_id=truck_id,
            sensor_readings=sensor_readings,
            engine_hours=engine_hours,
        )

        # Prioritize alerts
        prioritized_alerts = predictor.prioritize_maintenance(maintenance_alerts)

        # Calculate aggregate metrics
        avg_health = (
            sum(c.health_score for c in component_healths) / len(component_healths)
            if component_healths
            else 100
        )
        critical_count = sum(1 for c in component_healths if c.risk_level == "CRITICAL")
        high_count = sum(1 for c in component_healths if c.risk_level == "HIGH")
        total_risk_cost = sum(a.estimated_cost for a in prioritized_alerts)

        # Find nearest predicted failure
        nearest_failure_days = None
        for health in component_healths:
            if health.rul_days and health.rul_days < 9999:
                if (
                    nearest_failure_days is None
                    or health.rul_days < nearest_failure_days
                ):
                    nearest_failure_days = health.rul_days

        cursor.close()
        conn.close()

        return {
            "truck_id": truck_id,
            "overall_health": round(avg_health, 1),
            "risk_summary": {
                "critical_components": critical_count,
                "high_risk_components": high_count,
                "total_risk_cost_usd": round(total_risk_cost, 2),
                "nearest_predicted_failure_days": nearest_failure_days,
            },
            "component_health": [
                {
                    "component": c.component,
                    "health_score": c.health_score,
                    "rul_days": c.rul_days,
                    "risk_level": c.risk_level,
                    "failure_probability_30d": c.failure_probability_30d,
                    "contributing_sensors": c.contributing_sensors,
                    "recommendation": c.maintenance_recommendation,
                    "estimated_repair_cost": c.estimated_cost,
                }
                for c in component_healths
            ],
            "maintenance_alerts": [
                {
                    "component": a.component,
                    "severity": a.severity,
                    "health_score": a.health_score,
                    "rul_days": a.rul_days,
                    "message": a.message,
                    "estimated_cost": a.estimated_cost,
                    "recommended_action": a.recommended_action,
                    "created_at": a.created_at.isoformat(),
                }
                for a in prioritized_alerts
            ],
            "sensor_readings": sensor_readings,
            "engine_hours": engine_hours,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except ImportError as e:
        logger.error(f"Failed to import predictive_maintenance_v4: {e}")
        raise HTTPException(
            status_code=501, detail="Predictive Maintenance v4 module not available"
        )
    except Exception as e:
        logger.error(f"Failed to get predictive maintenance for {truck_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Predictive maintenance analysis failed: {str(e)}"
        )


@router.get("/fleet/predictive-maintenance-summary")
async def get_fleet_predictive_maintenance_summary():
    """
    Fleet-wide predictive maintenance summary.

    Shows aggregate health metrics and prioritized maintenance schedule for entire fleet.
    """
    try:
        from predictive_maintenance_v4 import get_rul_predictor

        predictor = get_rul_predictor()

        # Connect to database
        DB_CONFIG = {
            "host": "localhost",
            "port": 3306,
            "user": os.getenv("MYSQL_USER", "fuel_admin"),
            "password": os.getenv("MYSQL_PASSWORD"),
            "database": "fuel_copilot",
        }

        import mysql.connector

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Get all active trucks with latest sensors
        query = """
        SELECT DISTINCT truck_id
        FROM truck_sensors_cache
        WHERE last_updated >= DATE_SUB(NOW(), INTERVAL 7 DAY)
        """

        cursor.execute(query)
        trucks = cursor.fetchall()

        fleet_alerts = []
        fleet_health_scores = []

        for truck_row in trucks:
            truck_id = truck_row["truck_id"]

            # Get sensor data
            sensor_query = """
            SELECT 
                rpm, oil_temp_f as oil_temp, coolant_temp_f as cool_temp, 
                oil_pressure_psi as oil_press, def_level_pct as def_level,
                engine_load_pct as engine_load, turbo_pressure_psi as boost_press, 
                egr_temp_f as egt, engine_hours as engine_hours_total
            FROM truck_sensors_cache
            WHERE truck_id = %s
            LIMIT 1
            """

            cursor.execute(sensor_query, (truck_id,))
            sensor_row = cursor.fetchone()

            if not sensor_row:
                continue

            sensor_readings = {
                k: float(v) if v is not None else 0.0
                for k, v in sensor_row.items()
                if k != "engine_hours_total"
            }

            engine_hours = float(sensor_row.get("engine_hours_total") or 0)

            # Analyze truck
            component_healths, alerts = predictor.analyze_truck(
                truck_id, sensor_readings, engine_hours
            )

            if component_healths:
                avg_health = sum(c.health_score for c in component_healths) / len(
                    component_healths
                )
                fleet_health_scores.append(avg_health)

            fleet_alerts.extend(alerts)

        # Prioritize all fleet alerts
        prioritized_fleet_alerts = predictor.prioritize_maintenance(fleet_alerts)

        # Calculate fleet metrics
        fleet_avg_health = (
            sum(fleet_health_scores) / len(fleet_health_scores)
            if fleet_health_scores
            else 100
        )
        urgent_alerts = [a for a in fleet_alerts if a.severity == "URGENT"]
        warning_alerts = [a for a in fleet_alerts if a.severity == "WARNING"]
        total_risk_cost = sum(a.estimated_cost for a in fleet_alerts)

        cursor.close()
        conn.close()

        return {
            "fleet_size": len(trucks),
            "fleet_avg_health": round(fleet_avg_health, 1),
            "total_alerts": len(fleet_alerts),
            "urgent_alerts": len(urgent_alerts),
            "warning_alerts": len(warning_alerts),
            "total_risk_cost_usd": round(total_risk_cost, 2),
            "top_priority_alerts": [
                {
                    "truck_id": a.truck_id,
                    "component": a.component,
                    "severity": a.severity,
                    "health_score": a.health_score,
                    "rul_days": a.rul_days,
                    "message": a.message,
                    "estimated_cost": a.estimated_cost,
                    "recommended_action": a.recommended_action,
                }
                for a in prioritized_fleet_alerts[:20]  # Top 20 most urgent
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get fleet predictive maintenance summary: {e}")
        raise HTTPException(
            status_code=500, detail=f"Fleet maintenance analysis failed: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v7.1: FLEET METRICS ENDPOINTS - For Metrics Dashboard
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/fleet/summary")
async def get_fleet_summary():
    """
    Fleet-wide summary metrics for dashboard.

    Returns cost/mile, utilization, MPG, active trucks, etc.
    """
    try:
        import pymysql

        from db_connection import get_pymysql_connection

        with get_pymysql_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Calculate metrics from fuel_metrics (last 7 days)
                # ✅ FIX DEC22: Calculate real miles traveled per truck (MAX - MIN odometer)
                # NOT sum of odometers (that's accumulative values)
                cursor.execute(
                    """
                    WITH truck_miles AS (
                        SELECT 
                            truck_id,
                            MAX(odometer_mi) - MIN(odometer_mi) as miles_traveled,
                            SUM(estimated_gallons) as total_fuel_gal
                        FROM fuel_metrics
                        WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                            AND odometer_mi IS NOT NULL AND odometer_mi > 0
                        GROUP BY truck_id
                        HAVING miles_traveled > 0 AND total_fuel_gal > 0
                    )
                    SELECT 
                        AVG((total_fuel_gal * 3.50) / miles_traveled) as avg_cost_per_mile,
                        (SELECT COUNT(DISTINCT truck_id) FROM fuel_metrics 
                         WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)) as active_trucks,
                        (SELECT AVG(mpg_current) FROM fuel_metrics 
                         WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                         AND mpg_current IS NOT NULL) as avg_mpg,
                        SUM(miles_traveled) as total_miles,
                        SUM(total_fuel_gal * 3.50) as total_fuel_cost
                    FROM truck_miles
                """
                )

                metrics = cursor.fetchone()

                # Get utilization from fuel_metrics (engine_hours vs idle_hours_ecu)
                cursor.execute(
                    """
                    SELECT 
                        SUM(engine_hours) as total_engine,
                        SUM(idle_hours_ecu) as total_idle
                    FROM fuel_metrics
                    WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)
                """
                )

                util = cursor.fetchone()

                total_engine = util.get("total_engine") or 0
                total_idle = util.get("total_idle") or 0
                active = total_engine - total_idle
                utilization_pct = (
                    (active / total_engine * 100) if total_engine > 0 else 0
                )

        return {
            "cost_per_mile": round(float(metrics["avg_cost_per_mile"] or 0), 2),
            "active_trucks": metrics["active_trucks"] or 0,
            "avg_mpg": round(float(metrics["avg_mpg"] or 0), 2),
            "utilization_pct": round(utilization_pct, 1),
            "total_miles": round(float(metrics["total_miles"] or 0), 1),
            "total_fuel_cost": round(float(metrics["total_fuel_cost"] or 0), 2),
            "period_days": 7,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get fleet summary: {e}")
        raise HTTPException(status_code=500, detail=f"Fleet summary failed: {str(e)}")


@router.get("/fleet/cost-analysis")
async def get_fleet_cost_analysis():
    """
    Fleet cost analysis with breakdown by category and truck.

    Returns:
    - Cost distribution (fuel, maintenance, labor)
    - Per-truck cost analysis
    - Monthly trends
    """
    try:
        import mysql.connector

        DB_CONFIG = {
            "host": "localhost",
            "port": 3306,
            "user": os.getenv("MYSQL_USER", "fuel_admin"),
            "password": os.getenv("MYSQL_PASSWORD"),
            "database": "fuel_copilot",
        }

        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Get fuel costs from fuel_metrics (estimated at $3.50/gal)
        cursor.execute(
            """
            SELECT 
                SUM(estimated_gallons * 3.50) as total_fuel_cost
            FROM fuel_metrics
            WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY)
        """
        )

        fuel_data = cursor.fetchone()
        total_fuel = float(fuel_data["total_fuel_cost"] or 0.0)

        # Estimate maintenance and labor (industry standard percentages)
        total_maintenance = total_fuel * 0.30  # 30% of fuel cost
        total_labor = total_fuel * 0.40  # 40% of fuel cost

        # Get per-truck cost breakdown
        # ✅ FIX DEC22: Calculate real miles traveled (MAX - MIN odometer per truck)
        cursor.execute(
            """
            SELECT 
                truck_id,
                CASE 
                    WHEN (MAX(odometer_mi) - MIN(odometer_mi)) > 0 
                    THEN (SUM(estimated_gallons) * 3.50) / (MAX(odometer_mi) - MIN(odometer_mi))
                    ELSE NULL
                END as cost_per_mile,
                SUM(estimated_gallons * 3.50) as total_cost,
                MAX(odometer_mi) - MIN(odometer_mi) as total_miles
            FROM fuel_metrics
            WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                AND odometer_mi IS NOT NULL AND odometer_mi > 0
            GROUP BY truck_id
            HAVING total_miles > 0
            ORDER BY cost_per_mile DESC
        """
        )

        truck_costs = cursor.fetchall()

        cursor.close()
        conn.close()

        return {
            "cost_distribution": {
                "fuel": round(total_fuel, 2),
                "maintenance": round(total_maintenance, 2),
                "labor": round(total_labor, 2),
            },
            "cost_by_truck": [
                {
                    "truck_id": row["truck_id"],
                    "cost_per_mile": round(float(row["cost_per_mile"] or 0), 2),
                    "total_cost": round(float(row["total_cost"] or 0), 2),
                    "total_miles": round(float(row["total_miles"] or 0), 1),
                }
                for row in truck_costs
            ],
        }

    except Exception as e:
        logger.error(f"Failed to get cost analysis: {e}")
        raise HTTPException(status_code=500, detail=f"Cost analysis failed: {str(e)}")


@router.get("/fleet/utilization")
async def get_fleet_utilization(
    period: str = Query(default="week", pattern="^(week|month|quarter)$")
):
    """
    Fleet utilization metrics.

    Returns active/idle/parked time distribution by truck.
    """
    try:
        import pymysql

        from db_connection import get_pymysql_connection

        with get_pymysql_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Determine date range
                if period == "week":
                    days = 7
                elif period == "month":
                    days = 30
                else:  # quarter
                    days = 90

                # Get utilization from fuel_metrics (using idle_hours_ecu)
                query = """
                SELECT 
                    truck_id,
                    SUM(engine_hours) as total_engine_hours,
                    SUM(idle_hours_ecu) as total_idle_hours,
                    AVG(CASE WHEN engine_hours > 0 
                        THEN ((engine_hours - idle_hours_ecu) / engine_hours) * 100 
                        ELSE 0 END) as avg_utilization_pct
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s DAY)
                GROUP BY truck_id
                HAVING total_engine_hours > 0
                """

                cursor.execute(query, (days,))
                trucks = cursor.fetchall()

                truck_utilization = []
                total_active = 0
                total_idle = 0

                for truck in trucks:
                    engine_hours = truck.get("total_engine_hours") or 0
                    idle_hours = truck.get("total_idle_hours") or 0
                    active_hours = max(0, engine_hours - idle_hours)
                    utilization_pct = truck.get("avg_utilization_pct") or 0

                    truck_utilization.append(
                        {
                            "truck_id": truck.get("truck_id"),
                            "active_hours": round(active_hours, 1),
                            "idle_hours": round(idle_hours, 1),
                            "engine_hours": round(engine_hours, 1),
                            "utilization_pct": round(utilization_pct, 1),
                        }
                    )

                    total_active += active_hours
                    total_idle += idle_hours

                total_hours = total_active + total_idle
                fleet_utilization_pct = (
                    (total_active / total_hours * 100) if total_hours > 0 else 0
                )

        return {
            "period": period,
            "days": days,
            "fleet_summary": {
                "active_hours": round(total_active, 1),
                "idle_hours": round(total_idle, 1),
                "total_hours": round(total_hours, 1),
                "utilization_pct": round(fleet_utilization_pct, 1),
            },
            "by_truck": truck_utilization,
            "target_utilization_pct": 60.0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get utilization: {e}")
        raise HTTPException(
            status_code=500, detail=f"Utilization analysis failed: {str(e)}"
        )
