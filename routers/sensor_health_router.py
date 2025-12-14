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

router = APIRouter(prefix="/fuelAnalytics/api/sensor-health", tags=["Sensor Health"])


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class IdleValidationResponse(BaseModel):
    """Idle validation result for a truck"""

    truck_id: str
    is_valid: bool
    confidence: str
    calculated_idle_hours: float
    ecu_idle_hours: Optional[float]
    deviation_pct: Optional[float]
    idle_ratio_pct: Optional[float]
    needs_investigation: bool
    message: str
    last_validated: str


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

    Returns:
        List of validation results per truck
    """
    if not IDLE_VALIDATION_AVAILABLE:
        raise HTTPException(
            status_code=503, detail="Idle validation module not available"
        )

    try:
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

                # Get idle data
                ecu_idle = record.get("idle_hours_ecu")
                ecu_engine = record.get("engine_hours")
                calc_idle = record.get("idle_gph", 0) * 24  # Rough estimate from GPH

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
                        is_valid=validation.is_valid,
                        confidence=validation.confidence,
                        calculated_idle_hours=validation.calculated_idle_hours,
                        ecu_idle_hours=validation.ecu_idle_hours,
                        deviation_pct=validation.deviation_pct,
                        idle_ratio_pct=round(idle_ratio, 1) if idle_ratio else None,
                        needs_investigation=validation.needs_investigation,
                        message=validation.message,
                        last_validated=datetime.now(timezone.utc).isoformat(),
                    )
                )

            except Exception as e:
                logger.debug(f"Error validating idle for {tid}: {e}")
                continue

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
                quality = record.get("gps_quality", "UNKNOWN")

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
                        "latitude": record.get("latitude"),
                        "longitude": record.get("longitude"),
                    }
                )

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
