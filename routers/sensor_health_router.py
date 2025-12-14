"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     SENSOR HEALTH ROUTER v5.7.6                                ║
║              Idle Validation, Sensor Quality & Health Monitoring               ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Endpoints:
- GET /sensor-health/idle-validation - Idle validation status per truck
- GET /sensor-health/summary - Fleet sensor health overview
- GET /sensor-health/voltage-history/{truck_id} - Voltage trending
- GET /sensor-health/gps-quality - GPS quality fleet overview
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import db
from observability import logger

# Import idle validation
try:
    from idle_engine import validate_idle_calculation, IdleValidationResult

    IDLE_VALIDATION_AVAILABLE = True
except ImportError:
    IDLE_VALIDATION_AVAILABLE = False
    logger.warning("Idle validation module not available")

# Import GPS quality
try:
    from gps_quality import analyze_gps_quality, GPSQuality

    GPS_QUALITY_AVAILABLE = True
except ImportError:
    GPS_QUALITY_AVAILABLE = False

# Import voltage monitor
try:
    from voltage_monitor import analyze_voltage, VoltageStatus

    VOLTAGE_AVAILABLE = True
except ImportError:
    VOLTAGE_AVAILABLE = False

# 🆕 v5.7.6: Import alert service for automatic alerts
try:
    from alert_service import send_idle_deviation_alert, send_gps_quality_alert

    ALERTS_AVAILABLE = True
except ImportError:
    ALERTS_AVAILABLE = False
    logger.warning("Alert service not available for sensor health alerts")

router = APIRouter(prefix="/fuelAnalytics/api/sensor-health", tags=["Sensor Health"])


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class ExpectedRange(BaseModel):
    """Expected idle GPH range"""

    min_gph: float = 0.4
    max_gph: float = 1.2


class IdleValidationResponse(BaseModel):
    """Idle validation result for a truck - matches frontend IdleValidation type"""

    truck_id: str
    timestamp: str
    idle_mode: str  # ENGINE_OFF, NORMAL, REEFER, HEAVY
    idle_gph: float
    is_valid: bool
    validation_status: str  # VALID, ANOMALY, SENSOR_ERROR, UNKNOWN
    expected_range: ExpectedRange
    confidence: float  # 0.0 - 1.0
    message: str
    # Legacy fields for backwards compatibility
    calculated_idle_hours: Optional[float] = None
    ecu_idle_hours: Optional[float] = None
    deviation_pct: Optional[float] = None
    idle_ratio_pct: Optional[float] = None
    needs_investigation: bool = False


class SensorHealthSummary(BaseModel):
    """Fleet sensor health summary"""

    total_trucks: int
    trucks_with_gps_issues: int
    trucks_with_voltage_issues: int
    trucks_with_dtc_active: int
    trucks_with_idle_deviation: int
    overall_health_score: float
    last_updated: str


class VoltageDataPoint(BaseModel):
    """Single voltage reading"""

    timestamp: str
    voltage: float
    rpm: Optional[float]
    status: str


# ═══════════════════════════════════════════════════════════════════════════════
# CACHING FOR EXPENSIVE OPERATIONS
# ═══════════════════════════════════════════════════════════════════════════════

# 🆕 v5.7.6: In-memory cache for expensive operations
# 🔧 v5.7.8: Fixed BUG #13 - timestamp per cache key instead of global
# 🚀 v5.7.11: Extended caching to days-to-failure endpoint
_idle_validation_cache: Dict[str, Dict[str, Any]] = {}
_days_to_failure_cache: Dict[str, Dict[str, Any]] = {}
_sensor_health_cache: Dict[str, Dict[str, Any]] = {}
_gps_quality_cache: Dict[str, Dict[str, Any]] = {}
_voltage_summary_cache: Dict[str, Dict[str, Any]] = {}

IDLE_CACHE_TTL_SECONDS = 60  # Cache for 60 seconds
DAYS_TO_FAILURE_CACHE_TTL = 120  # 2 minutes - this is the slowest endpoint
SENSOR_HEALTH_CACHE_TTL = 60  # 1 minute
GPS_QUALITY_CACHE_TTL = 60  # 1 minute
VOLTAGE_SUMMARY_CACHE_TTL = 60  # 1 minute


# ═══════════════════════════════════════════════════════════════════════════════
# IDLE VALIDATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


def _get_expected_range(idle_mode: str) -> ExpectedRange:
    """Get expected idle GPH range based on idle mode"""
    ranges = {
        "ENGINE_OFF": ExpectedRange(min_gph=0.0, max_gph=0.1),
        "NORMAL": ExpectedRange(min_gph=0.4, max_gph=1.2),
        "REEFER": ExpectedRange(min_gph=1.0, max_gph=2.0),
        "HEAVY": ExpectedRange(min_gph=1.5, max_gph=2.5),
    }
    return ranges.get(idle_mode, ExpectedRange(min_gph=0.4, max_gph=1.2))


def _map_to_validation_status(validation) -> str:
    """Map validation result to frontend status"""
    if validation.is_valid:
        return "VALID"
    if validation.needs_investigation:
        return "ANOMALY"
    if validation.confidence == "LOW":
        return "SENSOR_ERROR"
    return "UNKNOWN"


def _confidence_to_float(confidence_str: str) -> float:
    """Convert confidence string to float"""
    mapping = {"HIGH": 0.9, "MEDIUM": 0.7, "LOW": 0.4}
    return mapping.get(confidence_str, 0.5)


@router.get("/idle-validation", response_model=List[IdleValidationResponse])
async def get_idle_validation_status(
    truck_id: Optional[str] = Query(None, description="Filter by truck ID"),
    only_issues: bool = Query(
        False, description="Only show trucks with validation issues"
    ),
):
    """
    🆕 v5.7.6: Get idle validation status for all trucks.

    Compares our calculated idle hours against ECU idle_hours sensor
    to validate accuracy of our idle tracking.

    🔧 v5.7.6: Added caching (60s TTL) for performance.

    Returns:
        List of validation results per truck
    """
    global _idle_validation_cache

    if not IDLE_VALIDATION_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Idle validation module not available"
        )

    try:
        # Check cache (only for full fleet requests without truck_id filter)
        cache_key = f"idle_validation:{truck_id or 'all'}:{only_issues}"
        now = datetime.now(timezone.utc)

        # 🔧 v5.7.8: Fixed BUG #13 - check timestamp per cache key
        if cache_key in _idle_validation_cache:
            cache_entry = _idle_validation_cache[cache_key]
            cache_age = (now - cache_entry["timestamp"]).total_seconds()
            if cache_age < IDLE_CACHE_TTL_SECONDS:
                logger.debug(f"Cache hit for {cache_key} (age: {cache_age:.1f}s)")
                return cache_entry["data"]

        # Get latest truck data with idle info
        trucks = db.get_all_trucks()
        results = []

        for tid in trucks:
            if truck_id and tid != truck_id:
                continue

            try:
                record = db.get_truck_latest_record(tid)
                if not record:
                    continue

                # Get idle data from record
                idle_gph = record.get("idle_gph") or record.get("consumption_gph", 0)
                idle_mode_raw = record.get("idle_mode") or record.get(
                    "idle_method", "NOT_IDLE"
                )

                # Map idle mode to standard values
                idle_mode = "ENGINE_OFF"
                if (
                    idle_mode_raw == "NOT_IDLE"
                    or record.get("truck_status") == "MOVING"
                ):
                    idle_mode = "ENGINE_OFF"
                elif "REEFER" in str(idle_mode_raw).upper():
                    idle_mode = "REEFER"
                elif "HEAVY" in str(idle_mode_raw).upper() or idle_gph > 1.5:
                    idle_mode = "HEAVY"
                elif record.get("truck_status") == "STOPPED" or idle_gph > 0:
                    idle_mode = "NORMAL"

                ecu_idle = record.get("idle_hours_ecu")
                ecu_engine = record.get("engine_hours")
                calc_idle = idle_gph * 24  # Rough estimate from GPH

                # Validate
                validation = validate_idle_calculation(
                    truck_id=tid,
                    calculated_idle_hours=calc_idle,
                    ecu_idle_hours=ecu_idle,
                    ecu_engine_hours=ecu_engine,
                    time_period_hours=24.0,
                )

                # Calculate idle ratio
                idle_ratio = None
                if ecu_idle and ecu_engine and ecu_engine > 0:
                    idle_ratio = (ecu_idle / ecu_engine) * 100

                if only_issues and not validation.needs_investigation:
                    continue

                results.append(
                    IdleValidationResponse(
                        truck_id=tid,
                        timestamp=record.get("timestamp", now.isoformat()),
                        idle_mode=idle_mode,
                        idle_gph=round(idle_gph, 2) if idle_gph else 0.0,
                        is_valid=validation.is_valid,
                        validation_status=_map_to_validation_status(validation),
                        expected_range=_get_expected_range(idle_mode),
                        confidence=_confidence_to_float(validation.confidence),
                        message=validation.message,
                        calculated_idle_hours=validation.calculated_idle_hours,
                        ecu_idle_hours=validation.ecu_idle_hours,
                        deviation_pct=validation.deviation_pct,
                        idle_ratio_pct=round(idle_ratio, 1) if idle_ratio else None,
                        needs_investigation=validation.needs_investigation,
                    )
                )

                # 🆕 v5.7.6: Trigger automatic alert for significant deviations
                if (
                    ALERTS_AVAILABLE
                    and validation.needs_investigation
                    and validation.deviation_pct is not None
                    and abs(validation.deviation_pct) > 15
                    and ecu_idle is not None
                ):
                    try:
                        send_idle_deviation_alert(
                            truck_id=tid,
                            calculated_hours=calc_idle,
                            ecu_hours=ecu_idle,
                            deviation_pct=validation.deviation_pct,
                        )
                        logger.info(
                            f"⏱️ Idle deviation alert sent for {tid}: {validation.deviation_pct:+.1f}%"
                        )
                    except Exception as alert_err:
                        logger.debug(
                            f"Failed to send idle deviation alert: {alert_err}"
                        )

            except Exception as e:
                logger.debug(f"Error validating idle for {tid}: {e}")
                continue

        # 🔧 v5.7.8: Fixed BUG #13 - store timestamp per cache key
        _idle_validation_cache[cache_key] = {"data": results, "timestamp": now}
        logger.debug(f"Cached {len(results)} idle validation results")

        return results

    except Exception as e:
        logger.error(f"Error in idle validation endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# SENSOR HEALTH SUMMARY
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/summary", response_model=SensorHealthSummary)
async def get_sensor_health_summary():
    """
    🆕 v5.7.6: Get fleet-wide sensor health summary.
    🚀 v5.7.11: Added caching for faster response times.

    Returns counts of trucks with various sensor issues:
    - GPS quality problems
    - Voltage issues
    - Active DTCs
    - Idle calculation deviations
    """
    global _sensor_health_cache

    try:
        # Check cache first
        cache_key = "summary"
        now = datetime.now(timezone.utc)

        if cache_key in _sensor_health_cache:
            cache_entry = _sensor_health_cache[cache_key]
            cache_age = (now - cache_entry["timestamp"]).total_seconds()
            if cache_age < SENSOR_HEALTH_CACHE_TTL:
                logger.debug(
                    f"Cache hit for sensor health summary (age: {cache_age:.1f}s)"
                )
                return cache_entry["data"]

        trucks = db.get_all_trucks()
        total = len(trucks)

        gps_issues = 0
        voltage_issues = 0
        dtc_active = 0
        idle_deviation = 0

        for tid in trucks:
            try:
                record = db.get_truck_latest_record(tid)
                if not record:
                    continue

                # Check GPS
                gps_quality = record.get("gps_quality")
                if gps_quality in ["POOR", "CRITICAL"]:
                    gps_issues += 1

                # Check voltage
                voltage_status = record.get("voltage_status")
                if voltage_status in ["LOW", "HIGH", "CRITICAL_LOW", "CRITICAL_HIGH"]:
                    voltage_issues += 1

                # Check DTCs
                dtc_count = record.get("dtc_count", 0) or 0
                dtc = record.get("dtc", 0) or 0
                if dtc_count > 0 or dtc > 0:
                    dtc_active += 1

                # Check idle deviation
                idle_dev = record.get("idle_deviation_pct")
                if idle_dev and abs(idle_dev) > 15:
                    idle_deviation += 1

            except Exception as e:
                logger.debug(f"Error checking {tid}: {e}")
                continue

        # Calculate overall health score (100 = perfect, 0 = all issues)
        if total > 0:
            issues = gps_issues + voltage_issues + dtc_active + idle_deviation
            max_issues = total * 4  # 4 categories
            health_score = max(0, 100 - (issues / max_issues * 100))
        else:
            health_score = 100.0

        result = SensorHealthSummary(
            total_trucks=total,
            trucks_with_gps_issues=gps_issues,
            trucks_with_voltage_issues=voltage_issues,
            trucks_with_dtc_active=dtc_active,
            trucks_with_idle_deviation=idle_deviation,
            overall_health_score=round(health_score, 1),
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

        # Store in cache
        _sensor_health_cache[cache_key] = {"data": result, "timestamp": now}
        logger.debug("Cached sensor health summary")

        return result

    except Exception as e:
        logger.error(f"Error getting sensor health summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# VOLTAGE TRENDING
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/voltage-history/{truck_id}", response_model=List[VoltageDataPoint])
async def get_voltage_history(
    truck_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history (1-168)"),
):
    """
    🆕 v5.7.6: Get voltage history for a truck.

    Returns historical voltage readings for trending analysis.
    Useful for detecting:
    - Battery degradation over time
    - Alternator issues
    - Parasitic drains when parked
    """
    if not VOLTAGE_AVAILABLE:
        raise HTTPException(status_code=503, detail="Voltage monitor not available")

    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        with engine.connect() as conn:
            query = text(
                """
                SELECT 
                    timestamp_utc,
                    battery_voltage as voltage,
                    rpm
                FROM fuel_metrics
                WHERE truck_id = :truck_id
                AND timestamp_utc > DATE_SUB(NOW(), INTERVAL :hours HOUR)
                AND battery_voltage IS NOT NULL
                ORDER BY timestamp_utc ASC
            """
            )

            result = conn.execute(query, {"truck_id": truck_id, "hours": hours})
            rows = result.fetchall()

            data_points = []
            for row in rows:
                voltage = float(row.voltage) if row.voltage else None
                if voltage is None:
                    continue

                rpm = float(row.rpm) if row.rpm else None
                is_running = rpm and rpm > 100

                # Determine status
                if is_running:
                    if voltage < 12.0:
                        status = "CRITICAL_LOW"
                    elif voltage < 13.2:
                        status = "LOW"
                    elif voltage > 15.5:
                        status = "CRITICAL_HIGH"
                    elif voltage > 14.8:
                        status = "HIGH"
                    else:
                        status = "NORMAL"
                else:
                    if voltage < 11.5:
                        status = "CRITICAL_LOW"
                    elif voltage < 12.2:
                        status = "LOW"
                    elif voltage > 13.2:
                        status = "HIGH"
                    else:
                        status = "NORMAL"

                data_points.append(
                    VoltageDataPoint(
                        timestamp=(
                            row.timestamp_utc.isoformat() if row.timestamp_utc else ""
                        ),
                        voltage=voltage,
                        rpm=rpm,
                        status=status,
                    )
                )

            return data_points

    except Exception as e:
        logger.error(f"Error getting voltage history for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# GPS QUALITY OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/gps-quality")
async def get_gps_quality_overview():
    """
    🆕 v5.7.6: Get GPS quality overview for all trucks.
    🚀 v5.7.11: Added caching for faster response times.

    Returns satellite counts and quality levels.
    Useful for identifying trucks with GPS antenna issues.
    """
    global _gps_quality_cache

    try:
        # Check cache first
        cache_key = "gps_quality"
        now = datetime.now(timezone.utc)

        if cache_key in _gps_quality_cache:
            cache_entry = _gps_quality_cache[cache_key]
            cache_age = (now - cache_entry["timestamp"]).total_seconds()
            if cache_age < GPS_QUALITY_CACHE_TTL:
                logger.debug(f"Cache hit for GPS quality (age: {cache_age:.1f}s)")
                return cache_entry["data"]

        trucks = db.get_all_trucks()
        results = []

        quality_counts = {
            "EXCELLENT": 0,
            "GOOD": 0,
            "MODERATE": 0,
            "POOR": 0,
            "CRITICAL": 0,
            "UNKNOWN": 0,
        }

        for tid in trucks:
            try:
                record = db.get_truck_latest_record(tid)
                if not record:
                    continue

                sats = record.get("gps_satellites") or record.get("sats")
                quality_raw = record.get("gps_quality", "UNKNOWN")

                # Parse quality string (format: "QUALITY|sats=X|acc=Ym")
                quality = "UNKNOWN"
                accuracy = None
                if quality_raw and "|" in str(quality_raw):
                    parts = str(quality_raw).split("|")
                    quality = parts[0] if parts else "UNKNOWN"
                    for part in parts[1:]:
                        if part.startswith("acc="):
                            try:
                                accuracy = float(
                                    part.replace("acc=", "").replace("m", "")
                                )
                            except:
                                pass
                elif quality_raw:
                    quality = str(quality_raw)

                # Count by quality
                if quality in quality_counts:
                    quality_counts[quality] += 1
                else:
                    quality_counts["UNKNOWN"] += 1

                results.append(
                    {
                        "truck_id": tid,
                        "satellites": sats,
                        "quality": quality,
                        "accuracy_m": accuracy,
                        "latitude": record.get("latitude"),
                        "longitude": record.get("longitude"),
                    }
                )

                # 🆕 v5.7.6: Trigger alert for poor GPS quality
                if (
                    ALERTS_AVAILABLE
                    and quality in ["POOR", "CRITICAL"]
                    and sats is not None
                ):
                    try:
                        send_gps_quality_alert(
                            truck_id=tid,
                            satellites=sats,
                            quality_level=quality,
                            estimated_accuracy_m=accuracy
                            or 0.0,  # Default to 0.0 if None
                        )
                        logger.info(f"📡 GPS quality alert sent for {tid}: {quality}")
                    except Exception as alert_err:
                        logger.debug(f"Failed to send GPS quality alert: {alert_err}")

            except Exception as e:
                logger.debug(f"Error checking GPS for {tid}: {e}")
                continue

        result = {
            "trucks": results,
            "summary": {
                "total": len(trucks),
                "by_quality": quality_counts,
                "issues_count": quality_counts["POOR"] + quality_counts["CRITICAL"],
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        # Store in cache
        _gps_quality_cache[cache_key] = {"data": result, "timestamp": now}
        logger.debug("Cached GPS quality overview")

        return result

    except Exception as e:
        logger.error(f"Error getting GPS quality overview: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# VOLTAGE SUMMARY (Fleet Overview)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/voltage-summary")
async def get_voltage_summary():
    """
    🆕 v5.7.6: Get voltage summary for all trucks in the fleet.
    🚀 v5.7.11: Added caching for faster response times.

    Returns current voltage status and trends for each truck.
    Useful for identifying battery/alternator issues fleet-wide.
    """
    global _voltage_summary_cache

    try:
        # Check cache first
        cache_key = "voltage_summary"
        now = datetime.now(timezone.utc)

        if cache_key in _voltage_summary_cache:
            cache_entry = _voltage_summary_cache[cache_key]
            cache_age = (now - cache_entry["timestamp"]).total_seconds()
            if cache_age < VOLTAGE_SUMMARY_CACHE_TTL:
                logger.debug(f"Cache hit for voltage summary (age: {cache_age:.1f}s)")
                return cache_entry["data"]

        trucks = db.get_all_trucks()
        results = []

        status_counts = {
            "CRITICAL_LOW": 0,
            "LOW": 0,
            "NORMAL": 0,
            "HIGH": 0,
            "CRITICAL_HIGH": 0,
            "UNKNOWN": 0,
        }

        for tid in trucks:
            try:
                record = db.get_truck_latest_record(tid)
                if not record:
                    continue

                voltage = record.get("voltage") or record.get("pwr_int")
                if voltage is None:
                    status_counts["UNKNOWN"] += 1
                    continue

                # Determine status
                if voltage < 11.5:
                    status = "CRITICAL_LOW"
                elif voltage < 12.2:
                    status = "LOW"
                elif voltage <= 14.4:
                    status = "NORMAL"
                elif voltage <= 15.0:
                    status = "HIGH"
                else:
                    status = "CRITICAL_HIGH"

                status_counts[status] += 1

                results.append(
                    {
                        "truck_id": tid,
                        "voltage": round(voltage, 2),
                        "status": status,
                        "timestamp": (
                            record.get("timestamp_utc", "").isoformat()
                            if hasattr(record.get("timestamp_utc", ""), "isoformat")
                            else str(record.get("timestamp_utc", ""))
                        ),
                    }
                )

            except Exception as e:
                logger.debug(f"Error checking voltage for {tid}: {e}")
                continue

        # Calculate summary stats
        voltages = [r["voltage"] for r in results if r.get("voltage")]
        avg_voltage = sum(voltages) / len(voltages) if voltages else 0

        result = {
            "trucks": results,
            "summary": {
                "total": len(trucks),
                "avg_voltage": round(avg_voltage, 2),
                "by_status": status_counts,
                "issues_count": status_counts["CRITICAL_LOW"]
                + status_counts["LOW"]
                + status_counts["HIGH"]
                + status_counts["CRITICAL_HIGH"],
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

        # Store in cache
        _voltage_summary_cache[cache_key] = {"data": result, "timestamp": now}
        logger.debug("Cached voltage summary")

        return result

    except Exception as e:
        logger.error(f"Error getting voltage summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.7.6: VOLTAGE TRENDING (Prediction)
# ═══════════════════════════════════════════════════════════════════════════════

# Import voltage history manager
try:
    from voltage_history import get_voltage_trending, get_voltage_history_manager

    VOLTAGE_HISTORY_AVAILABLE = True
except ImportError:
    VOLTAGE_HISTORY_AVAILABLE = False
    logger.warning("Voltage history module not available")


@router.get("/voltage-trending/{truck_id}")
async def get_voltage_trending_for_truck(
    truck_id: str,
    days_back: int = Query(30, ge=1, le=90, description="Days of history to analyze"),
):
    """
    🆕 v5.7.6: Get voltage trending and prediction for a specific truck.

    Analyzes voltage history to predict:
    - Battery degradation
    - Alternator issues
    - Days until potential failure

    Args:
        truck_id: Truck ID to analyze
        days_back: Days of history to analyze (1-90, default 30)

    Returns:
        Trending summary with prediction data
    """
    if not VOLTAGE_HISTORY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Voltage history module not available"
        )

    try:
        trending = get_voltage_trending(truck_id, days_back)
        return trending

    except Exception as e:
        logger.error(f"Error getting voltage trending for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/voltage-fleet-trending")
async def get_fleet_voltage_trending():
    """
    🆕 v5.7.6: Get voltage trending summary for the entire fleet.

    Returns aggregated voltage health data for all trucks.
    """
    if not VOLTAGE_HISTORY_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Voltage history module not available"
        )

    try:
        manager = get_voltage_history_manager()
        return manager.get_fleet_summary()

    except Exception as e:
        logger.error(f"Error getting fleet voltage trending: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.7.9: DAYS-TO-FAILURE DASHBOARD
# Provides predictive maintenance insights for the entire fleet
# ═══════════════════════════════════════════════════════════════════════════════

# Import maintenance prediction
try:
    from mpg_engine import predict_maintenance_timing, calculate_days_to_failure

    PREDICTION_AVAILABLE = True
except ImportError:
    PREDICTION_AVAILABLE = False
    logger.warning("Maintenance prediction module not available")


class MaintenancePrediction(BaseModel):
    """Maintenance prediction for a single sensor/metric"""

    sensor: str
    current_value: float
    warning_threshold: float
    critical_threshold: float
    trend_direction: str  # DEGRADING, STABLE, IMPROVING, UNKNOWN
    days_to_warning: Optional[float] = None
    days_to_critical: Optional[float] = None
    urgency: str  # CRITICAL, HIGH, MEDIUM, LOW, NONE
    recommendation: str


class TruckMaintenanceForecast(BaseModel):
    """Complete maintenance forecast for a truck"""

    truck_id: str
    overall_urgency: str  # Highest urgency across all sensors
    predictions: List[MaintenancePrediction]
    needs_attention: bool
    last_updated: str


class FleetMaintenanceDashboard(BaseModel):
    """Fleet-wide maintenance dashboard"""

    total_trucks: int
    trucks_needing_attention: int
    critical_count: int
    high_count: int
    medium_count: int
    forecasts: List[TruckMaintenanceForecast]
    summary_by_sensor: Dict[str, Dict[str, int]]
    last_updated: str


# Sensor thresholds for predictive maintenance
SENSOR_THRESHOLDS = {
    "battery_voltage": {
        "warning": 12.0,
        "critical": 11.5,
        "is_higher_worse": False,  # Lower voltage is worse
        "unit": "V",
    },
    "coolant_temp_f": {
        "warning": 210.0,
        "critical": 230.0,
        "is_higher_worse": True,  # Higher temp is worse
        "unit": "°F",
    },
    "oil_pressure_psi": {
        "warning": 25.0,
        "critical": 15.0,
        "is_higher_worse": False,  # Lower pressure is worse
        "unit": "PSI",
    },
    "def_level_pct": {
        "warning": 15.0,
        "critical": 5.0,
        "is_higher_worse": False,  # Lower DEF is worse
        "unit": "%",
    },
    "dpf_soot_pct": {
        "warning": 80.0,
        "critical": 95.0,
        "is_higher_worse": True,  # Higher soot is worse
        "unit": "%",
    },
}


async def _get_sensor_history(
    truck_id: str, sensor_field: str, days: int = 30
) -> List[float]:
    """Get daily aggregated sensor history for a truck"""
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        with engine.connect() as conn:
            query = text(
                f"""
                SELECT 
                    DATE(timestamp_utc) as day,
                    AVG({sensor_field}) as avg_value
                FROM fuel_metrics
                WHERE truck_id = :truck_id
                AND timestamp_utc > DATE_SUB(NOW(), INTERVAL :days DAY)
                AND {sensor_field} IS NOT NULL
                GROUP BY DATE(timestamp_utc)
                ORDER BY day ASC
            """
            )

            result = conn.execute(query, {"truck_id": truck_id, "days": days})
            rows = result.fetchall()

            return [float(row.avg_value) for row in rows if row.avg_value is not None]

    except Exception as e:
        logger.debug(f"Error getting sensor history for {truck_id}/{sensor_field}: {e}")
        return []


# 🚀 v5.7.11: Batch query for all sensor histories at once - MAJOR PERFORMANCE IMPROVEMENT
async def _get_all_sensor_histories_batch(
    truck_ids: List[str], days: int = 30
) -> Dict[str, Dict[str, List[float]]]:
    """
    Get daily aggregated sensor history for ALL trucks in a single query.
    Returns: {truck_id: {sensor_field: [values]}}
    """
    # Define sensor fields to fetch
    sensor_fields = [
        "battery_voltage",
        "coolant_temp_f",
        "oil_pressure_psi",
        "def_level_pct",
        "dpf_soot_pct",
    ]

    result_dict: Dict[str, Dict[str, List[float]]] = {}

    # Initialize empty structure
    for tid in truck_ids:
        result_dict[tid] = {field: [] for field in sensor_fields}

    if not truck_ids:
        return result_dict

    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        with engine.connect() as conn:
            # Build a single query that gets daily averages for all sensors for all trucks
            placeholders = ", ".join([f":truck_{i}" for i in range(len(truck_ids))])
            params: Dict[str, Any] = {
                f"truck_{i}": tid for i, tid in enumerate(truck_ids)
            }
            params["days"] = days

            query = text(
                f"""
                SELECT 
                    truck_id,
                    DATE(timestamp_utc) as day,
                    AVG(battery_voltage) as avg_battery_voltage,
                    AVG(coolant_temp_f) as avg_coolant_temp_f,
                    AVG(oil_pressure_psi) as avg_oil_pressure_psi,
                    AVG(def_level_pct) as avg_def_level_pct,
                    AVG(dpf_soot_pct) as avg_dpf_soot_pct
                FROM fuel_metrics
                WHERE truck_id IN ({placeholders})
                AND timestamp_utc > DATE_SUB(NOW(), INTERVAL :days DAY)
                GROUP BY truck_id, DATE(timestamp_utc)
                ORDER BY truck_id, day ASC
            """
            )

            result = conn.execute(query, params)

            # Get column names BEFORE fetchall
            columns = (
                list(result.keys())
                if hasattr(result, "keys")
                else [
                    "truck_id",
                    "day",
                    "avg_battery_voltage",
                    "avg_coolant_temp_f",
                    "avg_oil_pressure_psi",
                    "avg_def_level_pct",
                    "avg_dpf_soot_pct",
                ]
            )

            rows = result.fetchall()

            # Process results - use index-based access for compatibility
            for row in rows:
                # Convert row to dict for easier access
                try:
                    # Try _mapping first (SQLAlchemy 2.0+)
                    if hasattr(row, "_mapping"):
                        row_dict = dict(row._mapping)
                    else:
                        row_dict = dict(zip(columns, row))
                except Exception:
                    row_dict = dict(zip(columns, row))

                tid = row_dict.get("truck_id")
                if tid not in result_dict:
                    continue

                for field in sensor_fields:
                    value = row_dict.get(f"avg_{field}")
                    if value is not None:
                        result_dict[tid][field].append(float(value))

        logger.debug(
            f"Batch fetched sensor histories for {len(truck_ids)} trucks in single query"
        )
        return result_dict

    except Exception as e:
        logger.error(f"Error in batch sensor history query: {e}")
        return result_dict  # Return empty structure instead of empty dict


@router.get("/days-to-failure/{truck_id}")
async def get_truck_maintenance_forecast(
    truck_id: str,
    days_back: int = Query(30, ge=7, le=90, description="Days of history to analyze"),
):
    """
    🆕 v5.7.9: Get maintenance forecast for a specific truck.

    Analyzes sensor trends and predicts when maintenance will be needed.

    Args:
        truck_id: Truck ID to analyze
        days_back: Days of history to analyze (7-90, default 30)

    Returns:
        TruckMaintenanceForecast with predictions for all monitored sensors
    """
    if not PREDICTION_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Maintenance prediction module not available"
        )

    try:
        predictions = []
        highest_urgency = "NONE"
        urgency_order = {
            "CRITICAL": 5,
            "HIGH": 4,
            "MEDIUM": 3,
            "LOW": 2,
            "NONE": 1,
            "UNKNOWN": 0,
        }

        # Get current values
        record = db.get_truck_latest_record(truck_id)
        if not record:
            raise HTTPException(status_code=404, detail=f"Truck {truck_id} not found")

        # Map of record fields to sensor names
        field_mapping = {
            "battery_voltage": ["battery_voltage", "voltage", "pwr_int"],
            "coolant_temp_f": ["coolant_temp_f", "coolant_temp"],
            "oil_pressure_psi": ["oil_pressure_psi", "oil_press"],
            "def_level_pct": ["def_level_pct", "def_level"],
            "dpf_soot_pct": ["dpf_soot_pct", "dpf_soot"],
        }

        for sensor_name, config in SENSOR_THRESHOLDS.items():
            # Get current value from record
            current_value = None
            db_field = sensor_name

            for field in field_mapping.get(sensor_name, [sensor_name]):
                current_value = record.get(field)
                if current_value is not None:
                    db_field = field
                    break

            if current_value is None:
                continue

            # Get history
            history = await _get_sensor_history(truck_id, db_field, days_back)

            if len(history) < 3:
                # Not enough data for prediction
                predictions.append(
                    MaintenancePrediction(
                        sensor=sensor_name,
                        current_value=round(float(current_value), 2),
                        warning_threshold=config["warning"],
                        critical_threshold=config["critical"],
                        trend_direction="UNKNOWN",
                        days_to_warning=None,
                        days_to_critical=None,
                        urgency="UNKNOWN",
                        recommendation=f"Insufficient data ({len(history)}/3 days minimum)",
                    )
                )
                continue

            # Run prediction
            prediction = predict_maintenance_timing(
                sensor_name=sensor_name,
                current_value=float(current_value),
                history=history,
                warning_threshold=config["warning"],
                critical_threshold=config["critical"],
                is_higher_worse=config["is_higher_worse"],
            )

            pred_model = MaintenancePrediction(
                sensor=sensor_name,
                current_value=prediction["current_value"],
                warning_threshold=config["warning"],
                critical_threshold=config["critical"],
                trend_direction=prediction["trend_direction"],
                days_to_warning=prediction["days_to_warning"],
                days_to_critical=prediction["days_to_critical"],
                urgency=prediction["urgency"],
                recommendation=prediction["recommendation"],
            )
            predictions.append(pred_model)

            # 🆕 v5.7.9: Send alert if days-to-critical < 7
            if (
                ALERTS_AVAILABLE
                and prediction["days_to_critical"] is not None
                and prediction["days_to_critical"] < 7
                and prediction["urgency"] in ["CRITICAL", "HIGH"]
            ):
                try:
                    from alert_service import send_maintenance_prediction_alert

                    send_maintenance_prediction_alert(
                        truck_id=truck_id,
                        sensor=sensor_name,
                        current_value=prediction["current_value"],
                        threshold=config["critical"],
                        days_to_failure=prediction["days_to_critical"],
                        urgency=prediction["urgency"],
                        unit=config.get("unit", ""),
                    )
                    logger.info(
                        f"⚠️ Maintenance alert sent for {truck_id}/{sensor_name}: "
                        f"{prediction['days_to_critical']:.0f} days to critical"
                    )
                except Exception as alert_err:
                    logger.debug(f"Failed to send maintenance alert: {alert_err}")

            # Track highest urgency
            if urgency_order.get(prediction["urgency"], 0) > urgency_order.get(
                highest_urgency, 0
            ):
                highest_urgency = prediction["urgency"]

        needs_attention = highest_urgency in ["CRITICAL", "HIGH", "MEDIUM"]

        return TruckMaintenanceForecast(
            truck_id=truck_id,
            overall_urgency=highest_urgency,
            predictions=predictions,
            needs_attention=needs_attention,
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting maintenance forecast for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/days-to-failure", response_model=FleetMaintenanceDashboard)
async def get_fleet_maintenance_dashboard(
    days_back: int = Query(30, ge=7, le=90, description="Days of history to analyze"),
    only_attention: bool = Query(
        False, description="Only show trucks needing attention"
    ),
):
    """
    🆕 v5.7.9: Get fleet-wide maintenance dashboard with days-to-failure predictions.
    🚀 v5.7.11: MAJOR OPTIMIZATION - batch queries + caching for 10x faster response.

    Provides an overview of all trucks with predicted maintenance needs.

    Args:
        days_back: Days of history to analyze (7-90, default 30)
        only_attention: If True, only return trucks needing attention

    Returns:
        FleetMaintenanceDashboard with all truck forecasts and summary statistics
    """
    global _days_to_failure_cache

    if not PREDICTION_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Maintenance prediction module not available"
        )

    try:
        # 🚀 v5.7.11: Check cache first
        cache_key = f"dtf:{days_back}:{only_attention}"
        now = datetime.now(timezone.utc)

        if cache_key in _days_to_failure_cache:
            cache_entry = _days_to_failure_cache[cache_key]
            cache_age = (now - cache_entry["timestamp"]).total_seconds()
            if cache_age < DAYS_TO_FAILURE_CACHE_TTL:
                logger.debug(f"Cache hit for days-to-failure (age: {cache_age:.1f}s)")
                return cache_entry["data"]

        from config import get_allowed_trucks

        allowed_trucks = get_allowed_trucks()
        if not allowed_trucks:
            return FleetMaintenanceDashboard(
                total_trucks=0,
                trucks_needing_attention=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                forecasts=[],
                summary_by_sensor={},
                last_updated=datetime.now(timezone.utc).isoformat(),
            )

        # 🚀 v5.7.11: Limit trucks and use batch query
        # Convert set to list if needed
        trucks_list = (
            list(allowed_trucks) if isinstance(allowed_trucks, set) else allowed_trucks
        )
        trucks_to_process = trucks_list[:50]

        # Get ALL sensor histories in ONE batch query (was 50*5=250 queries before!)
        all_histories = await _get_all_sensor_histories_batch(
            trucks_to_process, days_back
        )

        forecasts = []
        critical_count = 0
        high_count = 0
        medium_count = 0

        # Track sensor-level summary
        sensor_summary: Dict[str, Dict[str, int]] = {}
        for sensor in SENSOR_THRESHOLDS.keys():
            sensor_summary[sensor] = {
                "critical": 0,
                "high": 0,
                "medium": 0,
                "low": 0,
                "none": 0,
                "unknown": 0,
            }

        urgency_order = {
            "CRITICAL": 5,
            "HIGH": 4,
            "MEDIUM": 3,
            "LOW": 2,
            "NONE": 1,
            "UNKNOWN": 0,
        }

        # Map of record fields to sensor names
        field_mapping = {
            "battery_voltage": ["battery_voltage", "voltage", "pwr_int"],
            "coolant_temp_f": ["coolant_temp_f", "coolant_temp"],
            "oil_pressure_psi": ["oil_pressure_psi", "oil_press"],
            "def_level_pct": ["def_level_pct", "def_level"],
            "dpf_soot_pct": ["dpf_soot_pct", "dpf_soot"],
        }

        for truck_id in trucks_to_process:
            try:
                # Get current values
                record = db.get_truck_latest_record(truck_id)
                if not record:
                    continue

                predictions = []
                highest_urgency = "NONE"

                # Get pre-fetched histories for this truck
                truck_histories = all_histories.get(truck_id, {})

                for sensor_name, config in SENSOR_THRESHOLDS.items():
                    # Get current value from record
                    current_value = None

                    for field in field_mapping.get(sensor_name, [sensor_name]):
                        current_value = record.get(field)
                        if current_value is not None:
                            break

                    if current_value is None:
                        continue

                    # Get history from batch results
                    history = truck_histories.get(sensor_name, [])

                    if len(history) < 3:
                        predictions.append(
                            MaintenancePrediction(
                                sensor=sensor_name,
                                current_value=round(float(current_value), 2),
                                warning_threshold=config["warning"],
                                critical_threshold=config["critical"],
                                trend_direction="UNKNOWN",
                                days_to_warning=None,
                                days_to_critical=None,
                                urgency="UNKNOWN",
                                recommendation=f"Insufficient data ({len(history)}/3 days minimum)",
                            )
                        )
                        continue

                    # Run prediction
                    prediction = predict_maintenance_timing(
                        sensor_name=sensor_name,
                        current_value=float(current_value),
                        history=history,
                        warning_threshold=config["warning"],
                        critical_threshold=config["critical"],
                        is_higher_worse=config["is_higher_worse"],
                    )

                    pred_model = MaintenancePrediction(
                        sensor=sensor_name,
                        current_value=prediction["current_value"],
                        warning_threshold=config["warning"],
                        critical_threshold=config["critical"],
                        trend_direction=prediction["trend_direction"],
                        days_to_warning=prediction["days_to_warning"],
                        days_to_critical=prediction["days_to_critical"],
                        urgency=prediction["urgency"],
                        recommendation=prediction["recommendation"],
                    )
                    predictions.append(pred_model)

                    # Track highest urgency
                    if urgency_order.get(prediction["urgency"], 0) > urgency_order.get(
                        highest_urgency, 0
                    ):
                        highest_urgency = prediction["urgency"]

                needs_attention = highest_urgency in ["CRITICAL", "HIGH", "MEDIUM"]

                if only_attention and not needs_attention:
                    continue

                forecast = TruckMaintenanceForecast(
                    truck_id=truck_id,
                    overall_urgency=highest_urgency,
                    predictions=predictions,
                    needs_attention=needs_attention,
                    last_updated=now.isoformat(),
                )
                forecasts.append(forecast)

                # Count urgencies
                if highest_urgency == "CRITICAL":
                    critical_count += 1
                elif highest_urgency == "HIGH":
                    high_count += 1
                elif highest_urgency == "MEDIUM":
                    medium_count += 1

                # Update sensor summary
                for pred in predictions:
                    if pred.sensor in sensor_summary:
                        urgency_key = pred.urgency.lower()
                        if urgency_key in sensor_summary[pred.sensor]:
                            sensor_summary[pred.sensor][urgency_key] += 1

            except Exception as e:
                logger.debug(f"Error forecasting {truck_id}: {e}")
                continue

        # Sort by urgency (critical first)
        urgency_sort_order = {
            "CRITICAL": 0,
            "HIGH": 1,
            "MEDIUM": 2,
            "LOW": 3,
            "NONE": 4,
            "UNKNOWN": 5,
        }
        forecasts.sort(key=lambda f: urgency_sort_order.get(f.overall_urgency, 99))

        result = FleetMaintenanceDashboard(
            total_trucks=len(allowed_trucks),
            trucks_needing_attention=critical_count + high_count + medium_count,
            critical_count=critical_count,
            high_count=high_count,
            medium_count=medium_count,
            forecasts=forecasts,
            summary_by_sensor=sensor_summary,
            last_updated=now.isoformat(),
        )

        # 🚀 v5.7.11: Store in cache
        _days_to_failure_cache[cache_key] = {"data": result, "timestamp": now}
        logger.info(f"🚀 Days-to-failure dashboard cached ({len(forecasts)} trucks)")

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting fleet maintenance dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))
