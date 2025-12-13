"""
Predictive Maintenance Router - v5.0/v5.3.0
Fleet health monitoring with operational context and Nelson Rules
"""

from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from typing import Optional
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Predictive Maintenance"])


@router.get("/maintenance/fleet-health")
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
        "alert_summary": {"critical": 0, "high": 1, "medium": 2, "low": 1},
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
                        "recommendation": "Check oil level and pressure sensor",
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

    logger.info("Predictive Maintenance: Using demo data (Wialon integration disabled)")
    return demo_response


@router.get("/maintenance/truck/{truck_id}")
async def get_truck_health(
    truck_id: str,
    days: int = Query(7, ge=1, le=30, description="History days"),
):
    """
    🆕 v5.0: Get detailed health analysis for a specific truck.
    """
    return {
        "status": "success",
        "data_source": "demo",
        "truck_id": truck_id,
        "overall_score": 85,
        "status": "healthy",
        "current_values": {"oil_press": 45, "cool_temp": 195, "pwr_ext": 14.1},
        "alerts": [],
        "trends": {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


@router.get("/v5/predictive-maintenance")
async def get_predictive_maintenance_v5():
    """
    🆕 v5.3.7: Wrapper for V3 fleet health that filters by tanks.yaml.
    """
    try:
        from predictive_maintenance_v3 import analyze_fleet_health

        report = analyze_fleet_health(include_trends=True, include_maintenance=True)
        report_dict = report.to_dict()

        trucks_list = report_dict.get("trucks", [])

        status_breakdown = {"NORMAL": 0, "WARNING": 0, "WATCH": 0, "CRITICAL": 0}
        for truck in trucks_list:
            status = truck.get("status", "NORMAL").upper()
            if status in status_breakdown:
                status_breakdown[status] += 1
            elif status == "HEALTHY":
                status_breakdown["NORMAL"] += 1

        return {
            "success": True,
            "source": "predictive_maintenance_v3",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fleet_health": {
                "total_trucks": len(trucks_list),
                "average_health_score": report_dict.get("fleet_summary", {}).get(
                    "average_score", 80
                ),
                "status_breakdown": status_breakdown,
            },
            "trucks": [
                {
                    "truck_id": t.get("truck_id"),
                    "health_score": t.get("overall_score", 80),
                    "status": t.get("status", "NORMAL"),
                    "sensors": t.get("current_values", {}),
                    "issues": [a.get("title", "") for a in t.get("alerts", [])],
                    "last_updated": t.get(
                        "last_updated", datetime.now(timezone.utc).isoformat()
                    ),
                }
                for t in trucks_list
            ],
        }

    except Exception as e:
        logger.error(f"[V5] Predictive maintenance error: {e}")
        return {
            "success": True,
            "source": "fallback",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fleet_health": {
                "total_trucks": 0,
                "average_health_score": 0,
                "status_breakdown": {
                    "NORMAL": 0,
                    "WARNING": 0,
                    "WATCH": 0,
                    "CRITICAL": 0,
                },
            },
            "trucks": [],
        }


# V3 Endpoints
router_v3 = APIRouter(prefix="/fuelAnalytics/api", tags=["Predictive Maintenance V3"])


@router_v3.get("/v3/fleet-health")
async def get_fleet_health_v3(
    include_trends: bool = Query(True, description="Include 7-day trend analysis"),
    include_maintenance: bool = Query(True, description="Include maintenance schedule"),
):
    """
    🆕 v5.3.0: PREDICTIVE MAINTENANCE V3 - Complete fleet health analysis.
    """
    try:
        from predictive_maintenance_v3 import analyze_fleet_health, generate_demo_report

        report = analyze_fleet_health(
            include_trends=include_trends,
            include_maintenance=include_maintenance,
        )

        return JSONResponse(
            content=report.to_dict(),
            headers={"Cache-Control": "max-age=60", "X-Predictive-V3": "true"},
        )

    except Exception as e:
        logger.error(f"[V3] Fleet health error: {e}")
        from predictive_maintenance_v3 import generate_demo_report

        return JSONResponse(
            content=generate_demo_report().to_dict(),
            headers={"X-Predictive-V3": "true", "X-Data-Source": "demo"},
        )


@router_v3.get("/v3/truck-health/{truck_id}")
async def get_truck_health_v3(
    truck_id: str,
    include_trends: bool = Query(True, description="Include 7-day trend analysis"),
    include_maintenance: bool = Query(True, description="Include maintenance schedule"),
):
    """
    🆕 v5.3.0: Get detailed V3 health analysis for a single truck.
    """
    try:
        from predictive_maintenance_v3 import analyze_single_truck

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
            headers={"Cache-Control": "max-age=30", "X-Predictive-V3": "true"},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[V3] Truck health error for {truck_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error analyzing truck {truck_id}: {str(e)}"
        )


@router_v3.get("/v3/kalman-recommendation/{truck_id}")
async def get_kalman_recommendation_v3(truck_id: str):
    """
    🆕 v5.3.0: Get recommended Kalman filter Q_r (process noise) for a truck.
    """
    try:
        from predictive_maintenance_v3 import get_recommended_Q_r

        result = get_recommended_Q_r(truck_id)
        return JSONResponse(content=result)

    except Exception as e:
        logger.error(f"[V3] Kalman recommendation error for {truck_id}: {e}")
        return JSONResponse(
            content={
                "Q_r": 0.1,
                "status": "UNKNOWN",
                "reason": f"Could not determine truck status: {str(e)}",
            }
        )


@router_v3.get("/v3/kalman-confidence")
async def get_kalman_confidence_v3(
    P: float = Query(..., description="Kalman covariance (P) value"),
):
    """
    🆕 v5.3.0: Convert Kalman covariance (P) to confidence level.
    """
    from predictive_maintenance_v3 import get_kalman_confidence

    result = get_kalman_confidence(P)
    return JSONResponse(content=result)


@router_v3.get("/v3/context-info")
async def get_context_info_v3():
    """
    🆕 v5.3.0: Documentation for Operational Context feature.
    """
    return JSONResponse(
        content={
            "feature": "Operational Context",
            "version": "V3",
            "description": "Smart threshold adjustment based on driving conditions",
            "competitive_advantage": "Unlike Geotab/Samsara, alerts are contextual not just threshold-based",
            "supported_contexts": {
                "grade_climbing": {
                    "detection": "High load + low speed + altitude increasing",
                    "adjustments": {
                        "coolant_temp": "+15°F",
                        "oil_temp": "+10°F",
                        "oil_press": "-5 PSI",
                    },
                },
                "heavy_haul": {
                    "detection": "Very high engine load + moderate speed",
                    "adjustments": {
                        "coolant_temp": "+10°F",
                        "oil_temp": "+8°F",
                        "oil_press": "-3 PSI",
                    },
                },
                "idle": {
                    "detection": "Speed < 3 mph + RPM < 900",
                    "adjustments": {"coolant_temp": "-5°F (stricter)"},
                },
                "cold_start": {
                    "detection": "Coolant or oil temp below 160°F",
                    "adjustments": {"oil_press": "+10 PSI"},
                },
                "hot_ambient": {
                    "detection": "Ambient temp > 95°F",
                    "adjustments": {"coolant_temp": "+8°F", "oil_temp": "+5°F"},
                },
                "normal": {
                    "detection": "Default when no special conditions",
                    "adjustments": "None",
                },
            },
            "benefits": [
                "Fewer false positive alerts",
                "More actionable warnings",
                "Reduced alert fatigue",
                "Better than Geotab/Samsara static thresholds",
            ],
        }
    )
