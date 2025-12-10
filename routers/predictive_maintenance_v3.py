"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║               PREDICTIVE MAINTENANCE V3 - ROUTER                               ║
║                    FastAPI Endpoints for V3 Health System                      ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Endpoints:                                                                    ║
║  - GET /v3/fleet-health (full fleet analysis)                                  ║
║  - GET /v3/truck-health/{truck_id} (single truck analysis)                     ║
║  - GET /v3/kalman-recommendation/{truck_id} (Kalman Q_r recommendation)        ║
║                                                                                ║
║  Features:                                                                     ║
║  - Operational Context (smart threshold adjustment)                            ║
║  - Nelson Rules (statistical anomaly detection)                                ║
║  - Maintenance Schedule                                                        ║
║  - Trend Analysis (7-day regression)                                           ║
║  - Kalman Filter Recommendations                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

# Import V3 engine (completely isolated from other health engines)
from predictive_maintenance_v3 import (
    analyze_fleet_health,
    analyze_single_truck,
    get_recommended_Q_r,
    get_kalman_confidence,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fuelAnalytics/api/v3",
    tags=["Predictive Maintenance V3"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# FLEET HEALTH ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/fleet-health")
async def get_fleet_health(
    include_trends: bool = Query(True, description="Include 7-day trend analysis"),
    include_maintenance: bool = Query(True, description="Include maintenance schedule"),
):
    """
    Get comprehensive fleet health analysis with V3 features:

    - **Operational Context**: Smart threshold adjustment based on driving conditions
    - **Nelson Rules**: Statistical anomaly detection before thresholds are crossed
    - **Maintenance Schedule**: Upcoming maintenance items based on odometer/hours
    - **Trend Analysis**: 7-day regression to predict future issues

    Returns:
    - total_trucks: Number of trucks analyzed
    - healthy_count / warning_count / critical_count: Status breakdown
    - average_score: Fleet-wide health score (0-100)
    - total_potential_savings: Estimated savings from preventive action
    - trucks: Detailed health data for each truck
    - all_alerts: All active alerts sorted by severity
    - all_anomalies: Nelson rule violations (early warning signs)
    - suppressed_alerts_count: Alerts that were NOT fired due to operational context
    """
    try:
        report = analyze_fleet_health(
            include_trends=include_trends,
            include_maintenance=include_maintenance,
        )

        return JSONResponse(
            content=report.to_dict(),
            headers={
                "Cache-Control": "max-age=60",  # Cache for 1 minute
                "X-Predictive-V3": "true",
            },
        )

    except Exception as e:
        logger.error(f"[V3] Fleet health error: {e}")
        # Return demo data instead of crashing
        from predictive_maintenance_v3 import generate_demo_report

        return JSONResponse(
            content=generate_demo_report().to_dict(),
            headers={
                "X-Predictive-V3": "true",
                "X-Data-Source": "demo",
            },
        )


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLE TRUCK HEALTH ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/truck-health/{truck_id}")
async def get_truck_health(
    truck_id: str,
    include_trends: bool = Query(True, description="Include 7-day trend analysis"),
    include_maintenance: bool = Query(True, description="Include maintenance schedule"),
):
    """
    Get detailed health analysis for a single truck.

    Returns:
    - truck_id: Truck identifier
    - health_score: 0-100 health score
    - status: healthy/warning/critical
    - sensors: Current sensor readings
    - alerts: Active alerts for this truck
    - operational_context: Current driving conditions and threshold adjustments
    - anomalies: Nelson rule violations (statistical anomalies)
    - maintenance: Upcoming maintenance items
    - suppressed_alerts_count: Alerts prevented by operational context
    """
    try:
        result = analyze_single_truck(
            truck_id=truck_id,
            include_trends=include_trends,
            include_maintenance=include_maintenance,
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Truck {truck_id} not found or no recent data available",
            )

        return JSONResponse(
            content=result,
            headers={
                "Cache-Control": "max-age=30",
                "X-Predictive-V3": "true",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[V3] Truck health error for {truck_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error analyzing truck {truck_id}: {str(e)}"
        )


# ═══════════════════════════════════════════════════════════════════════════════
# KALMAN RECOMMENDATION ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/kalman-recommendation/{truck_id}")
async def get_kalman_recommendation(truck_id: str):
    """
    Get recommended Kalman filter parameters for a specific truck.

    This endpoint provides adaptive Q_r (process noise) recommendations
    based on the truck's current operational state:

    - **PARKED**: Very low Q_r (0.01) - fuel shouldn't change
    - **STOPPED**: Low Q_r (0.05) - engine running but stationary
    - **IDLE**: Slightly higher Q_r - small consumption expected
    - **MOVING**: Higher Q_r proportional to consumption rate

    Use this to dynamically adjust Kalman filter sensitivity based on
    what the truck is actually doing.

    Returns:
    - Q_r: Recommended process noise value
    - status: Truck status (PARKED, STOPPED, IDLE, MOVING)
    - reason: Explanation for the recommendation
    - speed, rpm, fuel_rate: Current values used for calculation
    """
    try:
        result = get_recommended_Q_r(truck_id)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"[V3] Kalman recommendation error for {truck_id}: {e}")
        # Return safe default
        return JSONResponse(
            content={
                "Q_r": 0.1,
                "status": "UNKNOWN",
                "reason": f"Could not determine truck status: {str(e)}",
                "speed": None,
                "rpm": None,
                "fuel_rate": None,
            }
        )


# ═══════════════════════════════════════════════════════════════════════════════
# KALMAN CONFIDENCE ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/kalman-confidence")
async def get_kalman_confidence_levels(
    P: float = Query(..., description="Kalman covariance (P) value"),
):
    """
    Convert Kalman filter covariance (P) to human-readable confidence level.

    Lower P = higher confidence in the fuel level estimate.

    Parameters:
    - P: Current Kalman covariance value

    Returns:
    - level: HIGH, MEDIUM, LOW, or VERY_LOW
    - score: 0-100 confidence score
    - color: green, yellow, orange, or red
    - description: Human-readable explanation
    """
    result = get_kalman_confidence(P)
    return JSONResponse(content=result)


# ═══════════════════════════════════════════════════════════════════════════════
# OPERATIONAL CONTEXT INFO ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/context-info")
async def get_context_info():
    """
    Get information about the Operational Context feature.

    This endpoint explains how your system differs from Geotab/Samsara:
    - Traditional systems: Static thresholds (Coolant > 220°F = ALERT always)
    - Your system: Context-aware thresholds that adjust based on conditions

    Returns documentation about supported contexts and threshold adjustments.
    """
    return JSONResponse(
        content={
            "feature": "Operational Context",
            "description": "Smart threshold adjustment based on driving conditions",
            "competitive_advantage": "Unlike Geotab/Samsara, alerts are contextual not just threshold-based",
            "supported_contexts": {
                "grade_climbing": {
                    "detection": "High load + low speed + altitude increasing",
                    "adjustments": {
                        "coolant_temp": "+15°F threshold",
                        "oil_temp": "+10°F threshold",
                        "oil_press": "-5 PSI threshold",
                    },
                    "explanation": "Elevated temps expected when climbing with load",
                },
                "heavy_haul": {
                    "detection": "Very high engine load + moderate speed",
                    "adjustments": {
                        "coolant_temp": "+10°F threshold",
                        "oil_temp": "+8°F threshold",
                        "oil_press": "-3 PSI threshold",
                    },
                    "explanation": "Heavy load causes slightly elevated temps",
                },
                "idle": {
                    "detection": "Speed < 3 mph + RPM < 900",
                    "adjustments": {
                        "coolant_temp": "-5°F threshold (stricter)",
                    },
                    "explanation": "Cooling system should easily maintain temps at idle",
                },
                "cold_start": {
                    "detection": "Coolant or oil temp below 160°F",
                    "adjustments": {
                        "oil_press": "+10 PSI threshold",
                    },
                    "explanation": "Cold oil is thicker, higher pressure is normal",
                },
                "hot_ambient": {
                    "detection": "Ambient temp > 95°F",
                    "adjustments": {
                        "coolant_temp": "+8°F threshold",
                        "oil_temp": "+5°F threshold",
                    },
                    "explanation": "Hot weather reduces cooling efficiency",
                },
                "normal": {
                    "detection": "Default when no special conditions detected",
                    "adjustments": "No threshold modifications",
                    "explanation": "Standard operating conditions",
                },
            },
            "benefits": [
                "Fewer false positive alerts",
                "More actionable warnings (alerts that fire ARE significant)",
                "Reduced alert fatigue for operators",
                "Better than Geotab/Samsara which use static thresholds",
            ],
        }
    )
