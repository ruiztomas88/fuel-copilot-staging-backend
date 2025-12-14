"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         ALERTS ROUTER v5.7.0                                   ║
║                    Alert Management & Predictive Alerts                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Endpoints:
- GET /alerts - Active fleet alerts
- GET /alerts/predictive - ML-powered predictive alerts
- GET /alerts/diagnostics - DTC, Voltage, GPS quality alerts (🆕 v5.7.0)
- POST /alerts/test - Send test alert
"""

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from database import db
from observability import logger

# 🆕 v5.7.0: Import diagnostic modules
try:
    from voltage_monitor import analyze_voltage, VoltageStatus
    from gps_quality import analyze_gps_quality, GPSQuality
    from dtc_analyzer import process_dtc_from_sensor_data, DTCSeverity, get_dtc_analyzer

    DIAGNOSTICS_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Diagnostic modules not available: {e}")
    DIAGNOSTICS_AVAILABLE = False

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Alerts"])


class Alert(BaseModel):
    """Alert model"""

    truck_id: str
    alert_type: str
    severity: str
    message: str
    timestamp: datetime
    resolved: bool = False


@router.get("/alerts", response_model=List[Alert])
async def get_alerts(
    severity: Optional[str] = Query(
        None, description="Filter by severity (critical, warning, info)"
    ),
    truck_id: Optional[str] = Query(None, description="Filter by truck ID"),
):
    """
    Get active alerts for fleet.

    Alerts include drift warnings, offline trucks, and anomalies.
    Can be filtered by severity level or specific truck.
    """
    try:
        alerts = db.get_alerts()

        if severity:
            alerts = [a for a in alerts if a.get("severity") == severity]

        if truck_id:
            alerts = [a for a in alerts if a.get("truck_id") == truck_id]

        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching alerts: {str(e)}")


@router.get("/alerts/predictive")
async def get_predictive_alerts(
    days_ahead: int = Query(7, ge=1, le=30, description="Days to predict ahead"),
    include_recommendations: bool = Query(
        True, description="Include action recommendations"
    ),
):
    """
    ML-powered predictive alerts for proactive maintenance.

    Analyzes patterns to predict:
    - Low fuel events (based on consumption rate)
    - Maintenance needs (based on engine health trends)
    - Efficiency degradation (MPG decline patterns)
    - Sensor calibration needs (drift patterns)

    Returns predictions with confidence scores and recommended actions.
    """
    try:
        from cache_service import get_cache

        cache = await get_cache()
        cache_key = f"alerts:predictive:{days_ahead}d"
        cached = await cache.get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        # Get fleet data for analysis
        fleet_data = db.get_fleet_summary()
        trucks = fleet_data.get("truck_details", [])

        predictions = []
        for truck in trucks:
            truck_id = truck.get("truck_id")
            fuel_pct = truck.get("estimated_pct") or 0
            mpg = truck.get("mpg") or 0
            idle = truck.get("idle_gph") or 0
            drift = abs(truck.get("drift_pct") or 0)

            # Predict low fuel (if consuming ~20 gal/day, predict when hitting 20%)
            if fuel_pct < 40 and truck.get("status") != "OFFLINE":
                daily_consumption = 20  # Estimated average
                days_to_low = max(
                    0, (fuel_pct - 20) / (daily_consumption / 3)
                )  # Rough estimate
                if days_to_low < days_ahead:
                    predictions.append(
                        {
                            "truck_id": truck_id,
                            "alert_type": "LOW_FUEL_PREDICTED",
                            "severity": "warning" if days_to_low > 2 else "critical",
                            "confidence": 0.75,
                            "predicted_date": (datetime.now().date().__str__()),
                            "message": f"Fuel expected to reach 20% in ~{int(days_to_low)} days",
                            "recommendation": (
                                "Schedule refueling"
                                if include_recommendations
                                else None
                            ),
                        }
                    )

            # Predict sensor calibration need
            if drift > 8:
                predictions.append(
                    {
                        "truck_id": truck_id,
                        "alert_type": "CALIBRATION_NEEDED",
                        "severity": "warning",
                        "confidence": 0.85,
                        "predicted_date": datetime.now().date().__str__(),
                        "message": f"Sensor drift at {drift}%, calibration recommended",
                        "recommendation": (
                            "Schedule sensor calibration"
                            if include_recommendations
                            else None
                        ),
                    }
                )

            # Predict efficiency degradation
            if mpg > 0 and mpg < 5.5:
                predictions.append(
                    {
                        "truck_id": truck_id,
                        "alert_type": "EFFICIENCY_DEGRADATION",
                        "severity": "info",
                        "confidence": 0.70,
                        "predicted_date": datetime.now().date().__str__(),
                        "message": f"MPG at {mpg}, below optimal range",
                        "recommendation": (
                            "Review driving patterns and maintenance schedule"
                            if include_recommendations
                            else None
                        ),
                    }
                )

        result = {
            "predictions": predictions,
            "total_predictions": len(predictions),
            "analysis_period_days": days_ahead,
            "generated_at": datetime.now().isoformat(),
        }

        await cache.set(cache_key, result, ttl=300)
        return JSONResponse(content=result)
    except Exception as e:
        logger.error(f"Error in predictive alerts: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generating predictions: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# 🆕 v5.7.0: DIAGNOSTIC ALERTS (DTC, Voltage, GPS)
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/alerts/diagnostics")
async def get_diagnostic_alerts():
    """
    🆕 v5.7.0: Get real-time diagnostic alerts.

    Analyzes current telemetry for:
    - DTC (Diagnostic Trouble Codes) - Engine/transmission issues
    - Voltage issues - Battery/alternator problems
    - GPS quality - Poor satellite reception affecting accuracy

    Returns alerts with severity and recommended actions.
    """
    try:
        if not DIAGNOSTICS_AVAILABLE:
            return JSONResponse(
                content={
                    "alerts": [],
                    "summary": {"total": 0, "critical": 0, "warning": 0},
                    "error": "Diagnostic modules not available",
                }
            )

        from cache_service import get_cache

        cache = await get_cache()
        cache_key = "alerts:diagnostics"
        cached = await cache.get(cache_key)
        if cached:
            return JSONResponse(content=cached)

        # 🔧 FIX v5.7.1: Get data from file cache (populated by wialon_sync)
        # instead of direct Wialon query (which requires config)
        import json
        from pathlib import Path

        cache_file = Path("cache/fleet_sensors.json")
        fleet_data = []

        if cache_file.exists():
            try:
                with open(cache_file, "r") as f:
                    cached = json.load(f)
                    fleet_data = cached.get("data", [])
                    logger.debug(f"Got {len(fleet_data)} trucks from sensor cache")
            except Exception as e:
                logger.warning(f"Could not read sensor cache: {e}")

        if not fleet_data:
            # Fallback: try to get from database latest readings
            try:
                fleet_data = db.get_fleet_summary().get("truck_details", [])
                logger.debug(f"Got {len(fleet_data)} trucks from DB fallback")
            except Exception as e:
                logger.warning(f"Could not get fleet data: {e}")
                fleet_data = []

        alerts = []

        for truck in fleet_data:
            truck_id = (
                truck.truck_id
                if hasattr(truck, "truck_id")
                else truck.get("truck_id", "UNKNOWN")
            )

            # DTC Alerts
            dtc_value = getattr(truck, "dtc", None) or truck.get("dtc")
            if dtc_value:
                try:
                    timestamp = (
                        getattr(truck, "timestamp", None)
                        or truck.get("timestamp")
                        or datetime.now()
                    )
                    dtc_alerts = process_dtc_from_sensor_data(
                        truck_id=truck_id,
                        dtc_value=dtc_value,
                        timestamp=timestamp,
                    )
                    for dtc_alert in dtc_alerts:
                        severity = (
                            "critical"
                            if dtc_alert.severity == DTCSeverity.CRITICAL
                            else "warning"
                        )
                        for code in dtc_alert.codes:
                            alerts.append(
                                {
                                    "truck_id": truck_id,
                                    "alert_type": "dtc",
                                    "severity": severity,
                                    "message": f"DTC {code.code}: {code.description}",
                                    "code": code.code,
                                    "system": getattr(
                                        code, "system", "UNKNOWN"
                                    ),  # 🔧 Safe access
                                    "timestamp": datetime.now().isoformat(),
                                    "recommendation": code.recommended_action
                                    or "Schedule diagnostic inspection",
                                }
                            )
                except Exception as e:
                    logger.debug(f"DTC parse error for {truck_id}: {e}")

            # Voltage Alerts
            pwr_int = getattr(truck, "pwr_int", None) or truck.get("pwr_int")
            rpm = getattr(truck, "rpm", None) or truck.get("rpm")
            if pwr_int is not None:
                voltage_alert = analyze_voltage(pwr_int, rpm, truck_id)
                if voltage_alert and voltage_alert.priority not in ["OK", None]:
                    alerts.append(
                        {
                            "truck_id": truck_id,
                            "alert_type": "voltage",
                            "severity": (
                                "critical"
                                if voltage_alert.priority == "CRITICAL"
                                else "warning"
                            ),
                            "message": voltage_alert.message,
                            "voltage": pwr_int,
                            "status": voltage_alert.status.value,
                            "timestamp": datetime.now().isoformat(),
                            "recommendation": voltage_alert.action,
                            "affects_sensors": voltage_alert.may_affect_sensors,
                        }
                    )

            # GPS Quality Alerts
            sats = getattr(truck, "sats", None) or truck.get("sats")
            if sats is not None:
                gps_result = analyze_gps_quality(sats, truck_id)
                if gps_result.quality in [GPSQuality.POOR, GPSQuality.CRITICAL]:
                    severity = (
                        "critical"
                        if gps_result.quality == GPSQuality.CRITICAL
                        else "warning"
                    )
                    alerts.append(
                        {
                            "truck_id": truck_id,
                            "alert_type": "gps_quality",
                            "severity": severity,
                            "message": gps_result.message,
                            "satellites": sats,
                            "quality": gps_result.quality.value,
                            "estimated_accuracy_m": gps_result.estimated_accuracy_m,
                            "timestamp": datetime.now().isoformat(),
                            "recommendation": "Check GPS antenna or move to open area",
                        }
                    )

        # Sort by severity
        severity_order = {"critical": 0, "warning": 1, "info": 2}
        alerts.sort(key=lambda x: severity_order.get(x.get("severity", "info"), 3))

        result = {
            "alerts": alerts,
            "summary": {
                "total": len(alerts),
                "critical": sum(1 for a in alerts if a.get("severity") == "critical"),
                "warning": sum(1 for a in alerts if a.get("severity") == "warning"),
                "by_type": {
                    "dtc": sum(1 for a in alerts if a.get("alert_type") == "dtc"),
                    "voltage": sum(
                        1 for a in alerts if a.get("alert_type") == "voltage"
                    ),
                    "gps_quality": sum(
                        1 for a in alerts if a.get("alert_type") == "gps_quality"
                    ),
                },
            },
            "generated_at": datetime.now().isoformat(),
        }

        # Short cache (30 seconds) since this is real-time
        await cache.set(cache_key, result, ttl=30)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"Error in diagnostic alerts: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error generating diagnostic alerts: {str(e)}"
        )


@router.post("/alerts/test")
async def send_test_alert(
    truck_id: str = Query("TEST-001", description="Truck ID for test alert"),
    alert_type: str = Query("test", description="Alert type"),
    severity: str = Query("info", description="Alert severity"),
):
    """
    Send a test alert for notification system testing.
    """
    try:
        test_alert = {
            "truck_id": truck_id,
            "alert_type": alert_type,
            "severity": severity,
            "message": f"Test alert for {truck_id}",
            "timestamp": datetime.now().isoformat(),
            "is_test": True,
        }

        # Try to send via notification system
        try:
            from alert_service import AlertService

            service = AlertService()
            await service.send_alert(test_alert)
            test_alert["sent"] = True
        except Exception as e:
            logger.warning(f"Could not send test alert via service: {e}")
            test_alert["sent"] = False
            test_alert["send_error"] = str(e)

        return JSONResponse(content=test_alert)
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error sending test alert: {str(e)}"
        )
