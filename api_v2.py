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

from fastapi import APIRouter, Depends, HTTPException, Query, Response, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
import io
import logging

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
    Get comprehensive real-time sensor data for a truck from Wialon.

    Returns all ECU sensor readings including:
    - Oil: Pressure (PSI), Temperature (°F), Level (%)
    - DEF: Tank Level (%)
    - Engine: Load (%), RPM, Coolant Temp (°F)
    - Transmission: Gear Position
    - Braking: Brake Switch status
    - Air Intake: Pressure (Bar), Temperature (°F)
    - Fuel: Temperature (°F)
    - Environmental: Ambient Temp (°F), Barometric Pressure (inHg)
    - Electrical: Battery Voltage (V), Backup Battery (V)
    - Operational: Engine Hours, Idle Hours, PTO Hours
    """
    import mysql.connector
    import yaml
    import os
    from pathlib import Path

    # Wialon DB connection config from environment variables
    WIALON_CONFIG = {
        "host": os.getenv("WIALON_DB_HOST", "20.127.200.135"),
        "port": int(os.getenv("WIALON_DB_PORT", "3306")),
        "database": os.getenv("WIALON_DB_NAME", "wialon_collect"),
        "user": os.getenv("WIALON_DB_USER", "tomas"),
        "password": os.getenv("WIALON_DB_PASS", "Tomas2025"),
        "connect_timeout": 30,
    }

    # Load unit_id mapping from tanks.yaml
    tanks_path = Path(__file__).parent / "tanks.yaml"
    unit_id = None
    tank_capacity = 300  # Default

    try:
        with open(tanks_path, "r") as f:
            tanks_config = yaml.safe_load(f)
            trucks = tanks_config.get("trucks", {})
            if truck_id in trucks:
                unit_id = trucks[truck_id].get("unit_id")
                tank_capacity = trucks[truck_id].get("capacity_gal", 300)
    except Exception as e:
        logger.warning(f"Could not load tanks.yaml: {e}")

    if not unit_id:
        raise HTTPException(
            status_code=404, detail=f"Truck {truck_id} not found in configuration"
        )

    try:
        conn = mysql.connector.connect(**WIALON_CONFIG)
        cursor = conn.cursor(dictionary=True)

        # Query latest data from Wialon
        query = """
            SELECT 
                p.time as timestamp,
                -- Oil System
                MAX(CASE WHEN p.name = 'oil_press' THEN p.value END) as oil_press_raw,
                MAX(CASE WHEN p.name = 'oil_temp' THEN p.value END) as oil_temp_raw,
                MAX(CASE WHEN p.name = 'oil_lvl' THEN p.value END) as oil_level_raw,
                -- DEF
                MAX(CASE WHEN p.name = 'def_level' THEN p.value END) as def_level_raw,
                -- Engine
                MAX(CASE WHEN p.name = 'engine_load' THEN p.value END) as engine_load,
                MAX(CASE WHEN p.name = 'rpm' THEN p.value END) as rpm_raw,
                MAX(CASE WHEN p.name = 'cool_temp' THEN p.value END) as coolant_temp_raw,
                MAX(CASE WHEN p.name = 'cool_lvl' THEN p.value END) as coolant_level,
                -- Transmission & Brakes
                MAX(CASE WHEN p.name = 'gear' THEN p.value END) as gear,
                MAX(CASE WHEN p.name = 'brake_switch' THEN p.value END) as brake_switch,
                -- Air Intake
                MAX(CASE WHEN p.name = 'intake_pressure' THEN p.value END) as intake_pressure,
                MAX(CASE WHEN p.name = 'intk_t' THEN p.value END) as intake_temp_raw,
                MAX(CASE WHEN p.name = 'intrclr_t' THEN p.value END) as intercooler_temp_raw,
                -- Fuel
                MAX(CASE WHEN p.name = 'fuel_t' THEN p.value END) as fuel_temp_raw,
                MAX(CASE WHEN p.name = 'fuel_lvl' THEN p.value END) as fuel_level_raw,
                MAX(CASE WHEN p.name = 'fuel_rate' THEN p.value END) as fuel_rate,
                -- Environmental
                MAX(CASE WHEN p.name = 'ambient_temp' THEN p.value END) as ambient_temp_raw,
                MAX(CASE WHEN p.name = 'barometer' THEN p.value END) as barometer_raw,
                -- Electrical
                MAX(CASE WHEN p.name = 'pwr_ext' THEN p.value END) as voltage,
                MAX(CASE WHEN p.name = 'pwr_int' THEN p.value END) as backup_voltage,
                -- Operational Counters
                MAX(CASE WHEN p.name = 'engine_hours' THEN p.value END) as engine_hours,
                MAX(CASE WHEN p.name = 'idle_hours' THEN p.value END) as idle_hours,
                MAX(CASE WHEN p.name = 'pto_hours' THEN p.value END) as pto_hours,
                MAX(CASE WHEN p.name = 'total_idle_fuel' THEN p.value END) as total_idle_fuel,
                MAX(CASE WHEN p.name = 'total_fuel_used' THEN p.value END) as total_fuel_used,
                -- DTC
                MAX(CASE WHEN p.name = 'dtc' THEN p.value END) as dtc_count,
                MAX(CASE WHEN p.name = 'dtc_code' THEN p.value END) as dtc_code
            FROM tp_params p
            WHERE p.unit_id = %s
              AND p.time > UNIX_TIMESTAMP(NOW() - INTERVAL 5 MINUTE)
            GROUP BY p.time
            ORDER BY p.time DESC
            LIMIT 1
        """

        cursor.execute(query, (unit_id,))
        row = cursor.fetchone()
        cursor.close()
        conn.close()

        if not row:
            # Return empty sensor data with null values
            return {
                "truck_id": truck_id,
                "timestamp": None,
                "data_available": False,
                "message": "No recent sensor data from Wialon (last 5 minutes)",
                # All sensor fields as null
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
            }

        # Helper functions for unit conversions
        def celsius_to_fahrenheit(c):
            if c is None:
                return None
            return round(c * 9 / 5 + 32, 1)

        def raw_to_psi(raw, factor=1.0):
            """Convert raw pressure value to PSI"""
            if raw is None:
                return None
            # PT40 devices: oil_press raw is directly in PSI
            return round(raw * factor, 1)

        def raw_to_percent(raw, max_val=255):
            """Convert raw 0-255 value to percentage"""
            if raw is None:
                return None
            if raw > max_val:
                return raw  # Already in percent
            return round((raw / max_val) * 100, 1)

        def raw_to_inhg(raw):
            """Convert barometer raw (kPa * 10?) to inHg"""
            if raw is None:
                return None
            # Raw value 199 → ~29 inHg (typical sea level)
            # Formula: 1 kPa = 0.2953 inHg
            # If raw is in 0.1 kPa units: raw * 0.1 * 0.2953
            return round(raw * 0.02953 * 5, 1)  # Adjusted factor

        def rpm_from_raw(raw):
            """Convert RPM raw value"""
            if raw is None:
                return None
            # PT40: rpm raw * 32 = actual RPM (or stored directly)
            if raw < 100:  # Likely needs multiplication
                return int(raw * 32)
            return int(raw)

        # Build response with converted values
        from datetime import datetime

        timestamp = (
            datetime.fromtimestamp(row["timestamp"]) if row.get("timestamp") else None
        )

        return {
            "truck_id": truck_id,
            "timestamp": timestamp.isoformat() if timestamp else None,
            "data_available": True,
            # Oil System
            "oil_pressure_psi": raw_to_psi(row.get("oil_press_raw")),
            "oil_temp_f": celsius_to_fahrenheit(row.get("oil_temp_raw")),
            "oil_level_pct": raw_to_percent(row.get("oil_level_raw")),
            # DEF
            "def_level_pct": raw_to_percent(row.get("def_level_raw")),
            # Engine
            "engine_load_pct": row.get("engine_load"),
            "rpm": rpm_from_raw(row.get("rpm_raw")),
            "coolant_temp_f": celsius_to_fahrenheit(row.get("coolant_temp_raw")),
            "coolant_level_pct": raw_to_percent(row.get("coolant_level")),
            # Transmission & Brakes
            "gear": int(row.get("gear")) if row.get("gear") is not None else None,
            "brake_active": (
                row.get("brake_switch") == 255
                if row.get("brake_switch") is not None
                else None
            ),
            # Air Intake
            "intake_pressure_bar": row.get("intake_pressure"),
            "intake_temp_f": celsius_to_fahrenheit(row.get("intake_temp_raw")),
            "intercooler_temp_f": celsius_to_fahrenheit(
                row.get("intercooler_temp_raw")
            ),
            # Fuel
            "fuel_temp_f": celsius_to_fahrenheit(row.get("fuel_temp_raw")),
            "fuel_level_pct": raw_to_percent(row.get("fuel_level_raw")),
            "fuel_rate_gph": row.get("fuel_rate"),
            # Environmental
            "ambient_temp_f": celsius_to_fahrenheit(row.get("ambient_temp_raw")),
            "barometric_pressure_inhg": raw_to_inhg(row.get("barometer_raw")),
            # Electrical
            "voltage": round(row.get("voltage"), 1) if row.get("voltage") else None,
            "backup_voltage": (
                round(row.get("backup_voltage"), 1)
                if row.get("backup_voltage")
                else None
            ),
            # Operational Counters
            "engine_hours": (
                round(row.get("engine_hours"), 1) if row.get("engine_hours") else None
            ),
            "idle_hours": (
                round(row.get("idle_hours"), 1) if row.get("idle_hours") else None
            ),
            "pto_hours": (
                round(row.get("pto_hours"), 1) if row.get("pto_hours") else None
            ),
            "total_idle_fuel_gal": (
                round(row.get("total_idle_fuel"), 1)
                if row.get("total_idle_fuel")
                else None
            ),
            # DTC Info
            "dtc_count": int(row.get("dtc_count") or 0),
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
    from data_export import get_exporter, ExportConfig

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
    from data_export import get_exporter, ExportConfig

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
    from data_export import get_exporter, ExportConfig

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
