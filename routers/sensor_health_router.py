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
# IDLE VALIDATION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


# 🆕 v5.7.6: In-memory cache for expensive operations
_idle_validation_cache: Dict[str, Any] = {}
_idle_cache_timestamp: Optional[datetime] = None
IDLE_CACHE_TTL_SECONDS = 60  # Cache for 60 seconds


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
    global _idle_validation_cache, _idle_cache_timestamp

    if not IDLE_VALIDATION_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Idle validation module not available"
        )

    try:
        # Check cache (only for full fleet requests without truck_id filter)
        cache_key = f"idle_validation:{truck_id or 'all'}:{only_issues}"
        now = datetime.now(timezone.utc)

        if (
            cache_key in _idle_validation_cache
            and _idle_cache_timestamp
            and (now - _idle_cache_timestamp).total_seconds() < IDLE_CACHE_TTL_SECONDS
        ):
            logger.debug(f"Cache hit for {cache_key}")
            return _idle_validation_cache[cache_key]

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

        # Update cache
        _idle_validation_cache[cache_key] = results
        _idle_cache_timestamp = now
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

    Returns counts of trucks with various sensor issues:
    - GPS quality problems
    - Voltage issues
    - Active DTCs
    - Idle calculation deviations
    """
    try:
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

        return SensorHealthSummary(
            total_trucks=total,
            trucks_with_gps_issues=gps_issues,
            trucks_with_voltage_issues=voltage_issues,
            trucks_with_dtc_active=dtc_active,
            trucks_with_idle_deviation=idle_deviation,
            overall_health_score=round(health_score, 1),
            last_updated=datetime.now(timezone.utc).isoformat(),
        )

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

    Returns satellite counts and quality levels.
    Useful for identifying trucks with GPS antenna issues.
    """
    try:
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
                            estimated_accuracy_m=accuracy,
                        )
                        logger.info(f"📡 GPS quality alert sent for {tid}: {quality}")
                    except Exception as alert_err:
                        logger.debug(f"Failed to send GPS quality alert: {alert_err}")

            except Exception as e:
                logger.debug(f"Error checking GPS for {tid}: {e}")
                continue

        return {
            "trucks": results,
            "summary": {
                "total": len(trucks),
                "by_quality": quality_counts,
                "issues_count": quality_counts["POOR"] + quality_counts["CRITICAL"],
            },
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }

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

    Returns current voltage status and trends for each truck.
    Useful for identifying battery/alternator issues fleet-wide.
    """
    try:
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

        return {
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
