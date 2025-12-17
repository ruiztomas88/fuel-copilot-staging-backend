"""
Driver Alerts Router v1.0.0
═══════════════════════════════════════════════════════════════════════════════

API endpoints for driver behavior scoring and alerts.

Endpoints:
- GET /driver-alerts/{truck_id} - Get driver alerts and score for a truck
- GET /driver-alerts/fleet/rankings - Get fleet driver rankings
- GET /driver-alerts/{truck_id}/dtc-report - Get DTC analysis for a truck
- GET /driver-alerts/{truck_id}/component-health - Get component health predictions

Based on VERIFIED data from Wialon:
- OverSpeed events (event_id 54)
- Long Idle events (event_id 20)
- Speedings table
- DTC codes (j1939_spn, j1939_fmi)
- Component sensors (oil_level, cool_lvl, intrclr_t, etc.)

Author: Fuel Analytics Team
Version: 1.0.0
Created: December 2025
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta
import logging

# Import scoring engine
from driver_scoring_engine import (
    DriverScoringEngine,
    get_scoring_engine,
    EventType,
)

# Import DTC analyzer
from dtc_analyzer import (
    DTCAnalyzer,
    get_dtc_analyzer,
    DTCSeverity,
)

# Import component predictors
from component_health_predictors import (
    TurboHealthPredictor,
    OilConsumptionTracker,
    CoolantLeakDetector,
    get_turbo_predictor,
    get_oil_tracker,
    get_coolant_detector,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api/driver-alerts", tags=["Driver Alerts"])


# ═══════════════════════════════════════════════════════════════════════════════
# DRIVER SCORE & ALERTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{truck_id}")
async def get_driver_alerts(
    truck_id: str,
    days: int = Query(default=30, ge=1, le=90, description="Period in days"),
) -> Dict[str, Any]:
    """
    Get driver alerts and safety score for a specific truck.

    Returns:
    - Current safety score (0-100)
    - Grade (A/B/C/D/F)
    - Event breakdown (speeding, idle, etc.)
    - Improvement tips
    - Recent alerts

    Example:
        GET /driver-alerts/CO0681?days=30
    """
    try:
        engine = get_scoring_engine()

        # Calculate score for period
        score = engine.calculate_score(truck_id, period_days=days)

        # Get improvement tips
        tips = engine.get_improvement_tips(truck_id)

        return {
            "success": True,
            "truck_id": truck_id,
            "period_days": days,
            "score": {
                "value": score.score,
                "grade": score.grade,
                "grade_info": score.summary["grade_info"],
            },
            "breakdown": score.summary["breakdown"],
            "event_counts": score.summary["event_counts"],
            "idle_hours": score.summary.get("idle_hours", 0),
            "tips": tips,
            "recent_events": [
                {
                    "type": e.event_type.name,
                    "timestamp": e.timestamp.isoformat(),
                    "impact": e.score_impact,
                }
                for e in score.events[-10:]  # Last 10 events
            ],
            "recent_speedings": [
                {
                    "timestamp": s.timestamp.isoformat(),
                    "max_speed": s.max_speed_kmh,
                    "limit": s.speed_limit_kmh,
                    "over": s.over_limit_kmh,
                    "impact": s.score_impact,
                }
                for s in score.speeding_events[-5:]  # Last 5 speedings
            ],
        }

    except Exception as e:
        logger.error(f"Error getting driver alerts for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fleet/rankings")
async def get_fleet_rankings(
    days: int = Query(default=30, ge=1, le=90, description="Period in days"),
    limit: int = Query(default=50, ge=1, le=100, description="Max results"),
) -> Dict[str, Any]:
    """
    Get fleet driver safety rankings.

    Returns trucks ranked by driver safety score (highest to lowest).

    Example:
        GET /driver-alerts/fleet/rankings?days=30&limit=20
    """
    try:
        engine = get_scoring_engine()
        rankings = engine.get_fleet_rankings(period_days=days)

        # Limit results
        rankings = rankings[:limit]

        # Calculate fleet averages
        if rankings:
            avg_score = sum(r["score"] for r in rankings) / len(rankings)
            grade_counts = {}
            for r in rankings:
                grade_counts[r["grade"]] = grade_counts.get(r["grade"], 0) + 1
        else:
            avg_score = 100
            grade_counts = {}

        return {
            "success": True,
            "period_days": days,
            "fleet_summary": {
                "total_trucks": len(rankings),
                "average_score": round(avg_score, 1),
                "grade_distribution": grade_counts,
            },
            "rankings": rankings,
        }

    except Exception as e:
        logger.error(f"Error getting fleet rankings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DTC ANALYSIS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{truck_id}/dtc-report")
async def get_dtc_report(
    truck_id: str,
    dtc_string: Optional[str] = Query(
        default=None, description="DTC string from Wialon, e.g. '597.4,1089.2'"
    ),
) -> Dict[str, Any]:
    """
    Get comprehensive DTC (Diagnostic Trouble Code) analysis for a truck.

    Uses dtc_database.py v5.8.0 with 112 SPNs and 23 FMIs for detailed
    Spanish descriptions and recommended actions.

    Parameters:
    - truck_id: Truck identifier
    - dtc_string: Optional DTC string from Wialon sensors (format: SPN.FMI)

    Example:
        GET /driver-alerts/CO0681/dtc-report?dtc_string=597.4,1089.2
    """
    try:
        analyzer = get_dtc_analyzer()

        # Get comprehensive report
        report = analyzer.get_dtc_analysis_report(truck_id, dtc_string)

        return {"success": True, **report}

    except Exception as e:
        logger.error(f"Error getting DTC report for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# COMPONENT HEALTH
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{truck_id}/component-health")
async def get_component_health(
    truck_id: str,
    component: Optional[str] = Query(
        default=None, description="Specific component: turbo, oil, coolant, or all"
    ),
) -> Dict[str, Any]:
    """
    Get predictive health analysis for truck components.

    Components analyzed:
    - turbo: Turbocharger health (intrclr_t, intake_pres)
    - oil: Oil system health (oil_level, oil_press, oil_temp)
    - coolant: Cooling system health (cool_lvl, cool_temp)

    Example:
        GET /driver-alerts/CO0681/component-health
        GET /driver-alerts/CO0681/component-health?component=turbo
    """
    try:
        results = {}

        if component is None or component == "all":
            # Get all components
            turbo = get_turbo_predictor()
            oil = get_oil_tracker()
            coolant = get_coolant_detector()

            results = {
                "turbo": turbo.predict(truck_id).to_dict(),
                "oil": oil.predict(truck_id).to_dict(),
                "coolant": coolant.predict(truck_id).to_dict(),
            }

            # Calculate overall score
            scores = [
                results["turbo"]["score"],
                results["oil"]["score"],
                results["coolant"]["score"],
            ]
            avg_score = sum(scores) / len(scores)

            # Collect all critical alerts
            all_alerts = []
            for comp in results.values():
                all_alerts.extend([a for a in comp["alerts"] if "⛔" in a or "⚠️" in a])

        elif component == "turbo":
            turbo = get_turbo_predictor()
            results = {"turbo": turbo.predict(truck_id).to_dict()}
            avg_score = results["turbo"]["score"]
            all_alerts = results["turbo"]["alerts"]

        elif component == "oil":
            oil = get_oil_tracker()
            results = {"oil": oil.predict(truck_id).to_dict()}
            avg_score = results["oil"]["score"]
            all_alerts = results["oil"]["alerts"]

        elif component == "coolant":
            coolant = get_coolant_detector()
            results = {"coolant": coolant.predict(truck_id).to_dict()}
            avg_score = results["coolant"]["score"]
            all_alerts = results["coolant"]["alerts"]

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown component: {component}. Use: turbo, oil, coolant, or all",
            )

        return {
            "success": True,
            "truck_id": truck_id,
            "overall_score": round(avg_score, 1),
            "critical_alerts": all_alerts[:5],
            "components": results,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting component health for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED ALERTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{truck_id}/combined")
async def get_combined_alerts(
    truck_id: str,
    dtc_string: Optional[str] = Query(default=None, description="Current DTC codes"),
    days: int = Query(default=30, ge=1, le=90, description="Period for scoring"),
) -> Dict[str, Any]:
    """
    Get all alerts combined: driver score + DTC + component health.

    This is the unified view of all truck alerts and issues.

    Example:
        GET /driver-alerts/CO0681/combined?dtc_string=597.4&days=30
    """
    try:
        # Get driver score
        scoring_engine = get_scoring_engine()
        driver_score = scoring_engine.calculate_score(truck_id, period_days=days)
        tips = scoring_engine.get_improvement_tips(truck_id)

        # Get DTC report
        dtc_analyzer = get_dtc_analyzer()
        dtc_report = dtc_analyzer.get_dtc_analysis_report(truck_id, dtc_string)

        # Get component health
        turbo = get_turbo_predictor()
        oil = get_oil_tracker()
        coolant = get_coolant_detector()

        turbo_pred = turbo.predict(truck_id)
        oil_pred = oil.predict(truck_id)
        coolant_pred = coolant.predict(truck_id)

        component_avg = (turbo_pred.score + oil_pred.score + coolant_pred.score) / 3

        # Collect ALL critical alerts
        all_alerts = []

        # From DTCs
        if dtc_report["status"] in ["critical", "warning"]:
            all_alerts.append(
                {
                    "source": "DTC",
                    "severity": dtc_report["status"],
                    "message": dtc_report["message"],
                }
            )

        # From components
        for pred, name in [
            (turbo_pred, "Turbo"),
            (oil_pred, "Oil"),
            (coolant_pred, "Coolant"),
        ]:
            for alert in pred.alerts:
                if "⛔" in alert or "⚠️" in alert:
                    all_alerts.append(
                        {
                            "source": name,
                            "severity": "critical" if "⛔" in alert else "warning",
                            "message": alert,
                        }
                    )

        # From driver behavior
        if driver_score.score < 60:
            all_alerts.append(
                {
                    "source": "Driver",
                    "severity": "warning",
                    "message": f"Puntuación de conductor baja: {driver_score.score}/100 ({driver_score.grade})",
                }
            )

        # Calculate overall truck health (weighted average)
        # Driver: 25%, DTC: 25%, Components: 50%
        dtc_score = (
            100
            if dtc_report["status"] == "ok"
            else (50 if dtc_report["status"] == "warning" else 25)
        )
        overall_score = (
            driver_score.score * 0.25 + dtc_score * 0.25 + component_avg * 0.50
        )

        return {
            "success": True,
            "truck_id": truck_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "overall_health_score": round(overall_score, 1),
            "all_alerts": all_alerts,
            "driver": {
                "score": driver_score.score,
                "grade": driver_score.grade,
                "tips": tips[:3],
            },
            "dtc": {
                "status": dtc_report["status"],
                "codes_count": dtc_report["summary"]["total"],
                "systems_affected": dtc_report.get("systems_affected", []),
            },
            "components": {
                "average_score": round(component_avg, 1),
                "turbo": {"score": turbo_pred.score, "status": turbo_pred.status.value},
                "oil": {"score": oil_pred.score, "status": oil_pred.status.value},
                "coolant": {
                    "score": coolant_pred.score,
                    "status": coolant_pred.status.value,
                },
            },
        }

    except Exception as e:
        logger.error(f"Error getting combined alerts for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# SIMULATE DATA (for testing without Wialon)
# ═══════════════════════════════════════════════════════════════════════════════


@router.post("/{truck_id}/simulate")
async def simulate_truck_data(
    truck_id: str,
    scenario: str = Query(
        default="healthy", description="Scenario: healthy, speeder, problematic"
    ),
) -> Dict[str, Any]:
    """
    Simulate driver events and sensor data for testing.

    Scenarios:
    - healthy: Good driver with normal sensors
    - speeder: Driver with multiple speeding events
    - problematic: Driver with issues + bad sensor readings

    Note: This is for testing/demo purposes.
    """
    try:
        now = datetime.now(timezone.utc)

        # Get all engines
        scoring = get_scoring_engine()
        turbo = get_turbo_predictor()
        oil = get_oil_tracker()
        coolant = get_coolant_detector()

        if scenario == "healthy":
            # Good driver, healthy truck
            scoring.process_event(truck_id, 54, now - timedelta(days=15))  # 1 overspeed

            for i in range(20):
                turbo.add_reading(truck_id, intrclr_t=55, intake_pres=28)
                oil.add_reading(truck_id, oil_level=80, oil_press=45, oil_temp=95)
                coolant.add_reading(truck_id, cool_lvl=85, cool_temp=90)

            message = f"Simulated healthy scenario for {truck_id}"

        elif scenario == "speeder":
            # Bad driver habits
            for i in range(10):
                scoring.process_event(truck_id, 54, now - timedelta(days=i))
                scoring.process_speeding(
                    truck_id, now - timedelta(days=i), 130, 105, 60
                )
            scoring.add_idle_hours(truck_id, 5.0)

            # Normal sensors
            for i in range(20):
                turbo.add_reading(truck_id, intrclr_t=58, intake_pres=27)
                oil.add_reading(truck_id, oil_level=70, oil_press=42, oil_temp=98)
                coolant.add_reading(truck_id, cool_lvl=75, cool_temp=92)

            message = f"Simulated speeder scenario for {truck_id}"

        elif scenario == "problematic":
            # Bad everything
            for i in range(5):
                scoring.process_event(truck_id, 54, now - timedelta(days=i))
                scoring.process_speeding(
                    truck_id, now - timedelta(days=i), 150, 105, 120
                )
            scoring.add_idle_hours(truck_id, 8.0)

            # Problem sensors
            for i in range(20):
                turbo.add_reading(
                    truck_id, intrclr_t=75 + i, intake_pres=15 - (i * 0.3)
                )
                oil.add_reading(truck_id, oil_level=30 - i, oil_press=18, oil_temp=120)
                coolant.add_reading(truck_id, cool_lvl=25, cool_temp=110)

            message = f"Simulated problematic scenario for {truck_id}"

        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown scenario: {scenario}. Use: healthy, speeder, problematic",
            )

        return {
            "success": True,
            "message": message,
            "truck_id": truck_id,
            "scenario": scenario,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error simulating data for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
