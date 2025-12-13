"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                         ANALYTICS ROUTER v5.6.0                                ║
║                    Advanced Analytics & Intelligence                           ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Endpoints:
- GET /analytics/driver-scorecard - Driver performance scores
- GET /analytics/enhanced-kpis - Enhanced KPIs with health index
- GET /analytics/enhanced-loss-analysis - Detailed loss breakdown
- GET /analytics/route-efficiency - Route efficiency metrics
- GET /analytics/cost-attribution - Cost breakdown by category
- GET /analytics/inefficiency-causes - Inefficiency root causes
- GET /analytics/inefficiency-by-truck - Per-truck inefficiency
- GET /analytics/next-refuel-prediction - Refuel predictions
- GET /analytics/historical-comparison - Period comparisons
- GET /analytics/trends - Fleet trends analysis
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from database import db
from observability import logger

# Try importing cache
try:
    from cache_service import get_cache
except ImportError:
    get_cache = None

router = APIRouter(prefix="/fuelAnalytics/api/analytics", tags=["Analytics"])


@router.get("/driver-scorecard")
async def get_driver_scorecard(
    days: int = Query(7, ge=1, le=30, description="Days to analyze"),
):
    """
    Comprehensive Driver Scorecard System.

    Returns multi-dimensional driver scores based on:
    - Speed Optimization (55-65 mph optimal)
    - RPM Discipline (1200-1600 optimal)
    - Idle Management (vs fleet average)
    - Fuel Consistency (consumption variability)
    - MPG Performance (vs 5.7 baseline)
    """
    try:
        from database_mysql import get_driver_scorecard

        result = get_driver_scorecard(days_back=days)
        return result
    except Exception as e:
        logger.error(f"Error in driver scorecard: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error in driver scorecard: {str(e)}"
        )


@router.get("/enhanced-kpis")
async def get_enhanced_kpis(
    days: int = Query(1, ge=1, le=30, description="Days to analyze"),
):
    """
    Enhanced KPI Dashboard with Fleet Health Index.

    Provides comprehensive financial intelligence:
    - Fleet Health Index (composite score 0-100)
    - Fuel cost breakdown (moving vs idle vs inefficiency)
    - ROI and cost-per-mile analysis
    - Savings opportunity matrix
    - Monthly/annual projections
    """
    try:
        from database_mysql import get_enhanced_kpis

        result = get_enhanced_kpis(days_back=days)
        return result
    except Exception as e:
        logger.error(f"Error in enhanced KPIs: {e}")
        raise HTTPException(status_code=500, detail=f"Error in enhanced KPIs: {str(e)}")


@router.get("/enhanced-loss-analysis")
async def get_enhanced_loss_analysis(
    days: int = Query(1, ge=1, le=30, description="Days to analyze"),
):
    """
    Enhanced Loss Analysis with Root Cause Intelligence.

    Detailed breakdown of fuel losses:
    - EXCESSIVE IDLE: Patterns and impact
    - HIGH ALTITUDE: Route-based analysis
    - RPM ABUSE: High RPM driving patterns
    - OVERSPEEDING: Speed profile analysis
    - THERMAL: Coolant temperature issues
    """
    try:
        from database_mysql import get_enhanced_loss_analysis

        result = get_enhanced_loss_analysis(days_back=days)
        return result
    except Exception as e:
        logger.error(f"Error in enhanced loss analysis: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error in enhanced loss analysis: {str(e)}"
        )


@router.get("/route-efficiency")
async def get_route_efficiency(
    days: int = Query(7, ge=1, le=30, description="Days to analyze"),
):
    """
    Route efficiency analysis with MPG by route segments.
    """
    try:
        # Get fleet data for analysis
        fleet_data = db.get_fleet_summary()
        trucks = fleet_data.get("truck_details", [])

        route_data = []
        for truck in trucks:
            if truck.get("mpg") and truck.get("mpg") > 0:
                route_data.append(
                    {
                        "truck_id": truck["truck_id"],
                        "avg_mpg": truck["mpg"],
                        "efficiency_rating": (
                            "good"
                            if truck["mpg"] > 6
                            else "average" if truck["mpg"] > 5 else "poor"
                        ),
                    }
                )

        return {
            "analysis_period_days": days,
            "routes_analyzed": len(route_data),
            "data": route_data,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in route efficiency: {str(e)}"
        )


@router.get("/cost-attribution")
async def get_cost_attribution(
    days: int = Query(7, ge=1, le=30, description="Days to analyze"),
    fuel_price: float = Query(3.50, description="Fuel price per gallon"),
):
    """
    Cost breakdown by category (idle, moving, inefficiency).
    """
    try:
        from database_mysql import get_kpi_summary

        kpis = get_kpi_summary(days_back=days)

        total_gallons = kpis.get("total_gallons", 0)
        idle_gallons = kpis.get("idle_gallons", 0)
        moving_gallons = total_gallons - idle_gallons

        return {
            "analysis_period_days": days,
            "fuel_price_per_gallon": fuel_price,
            "total_fuel_cost": round(total_gallons * fuel_price, 2),
            "cost_breakdown": {
                "moving_cost": round(moving_gallons * fuel_price, 2),
                "idle_cost": round(idle_gallons * fuel_price, 2),
                "idle_percentage": (
                    round(idle_gallons / total_gallons * 100, 1)
                    if total_gallons > 0
                    else 0
                ),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in cost attribution: {str(e)}"
        )


@router.get("/inefficiency-causes")
async def get_inefficiency_causes(
    days: int = Query(7, ge=1, le=30, description="Days to analyze"),
):
    """
    Analyze root causes of inefficiency across fleet.
    """
    try:
        from database_mysql import get_loss_analysis

        loss_data = get_loss_analysis(days_back=days)
        return loss_data
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in inefficiency causes: {str(e)}"
        )


@router.get("/inefficiency-by-truck")
async def get_inefficiency_by_truck(
    days: int = Query(7, ge=1, le=30, description="Days to analyze"),
):
    """
    Per-truck inefficiency breakdown.
    """
    try:
        fleet_data = db.get_fleet_summary()
        trucks = fleet_data.get("truck_details", [])

        inefficiency_data = []
        for truck in trucks:
            mpg = truck.get("mpg") or 0
            idle = truck.get("idle_gph") or 0

            # Calculate inefficiency score (higher = worse)
            inefficiency_score = 0
            if mpg > 0 and mpg < 5.7:  # Below baseline
                inefficiency_score += (5.7 - mpg) * 10
            if idle > 1.0:  # Above normal idle
                inefficiency_score += (idle - 1.0) * 20

            inefficiency_data.append(
                {
                    "truck_id": truck["truck_id"],
                    "mpg": mpg,
                    "idle_gph": idle,
                    "inefficiency_score": round(inefficiency_score, 1),
                    "status": truck.get("status"),
                }
            )

        # Sort by inefficiency score descending
        inefficiency_data.sort(key=lambda x: x["inefficiency_score"], reverse=True)

        return {
            "analysis_period_days": days,
            "trucks": inefficiency_data,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in inefficiency by truck: {str(e)}"
        )


@router.get("/next-refuel-prediction")
async def get_next_refuel_prediction(
    truck_id: Optional[str] = Query(None, description="Specific truck ID"),
):
    """
    Predict next refuel time and location based on consumption patterns.
    """
    try:
        fleet_data = db.get_fleet_summary()
        trucks = fleet_data.get("truck_details", [])

        if truck_id:
            trucks = [t for t in trucks if t["truck_id"] == truck_id]

        predictions = []
        for truck in trucks:
            fuel_pct = truck.get("estimated_pct") or 0
            if fuel_pct > 0:
                # Estimate consumption rate (~20 gal/day average)
                daily_consumption_pct = 8  # ~8% per day average
                days_to_20pct = max(0, (fuel_pct - 20) / daily_consumption_pct)

                predictions.append(
                    {
                        "truck_id": truck["truck_id"],
                        "current_fuel_pct": fuel_pct,
                        "estimated_days_to_refuel": round(days_to_20pct, 1),
                        "urgency": (
                            "immediate"
                            if days_to_20pct < 1
                            else "soon" if days_to_20pct < 3 else "normal"
                        ),
                    }
                )

        return {
            "predictions": predictions,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in refuel prediction: {str(e)}"
        )


@router.get("/historical-comparison")
async def get_historical_comparison(
    period1_days: int = Query(7, description="First period (recent)"),
    period2_days: int = Query(7, description="Second period (comparison)"),
):
    """
    Compare metrics between two time periods.
    """
    try:
        from database_mysql import get_kpi_summary

        current = get_kpi_summary(days_back=period1_days)
        previous = get_kpi_summary(days_back=period1_days + period2_days)

        # Calculate deltas
        def calc_delta(curr, prev, key):
            c = curr.get(key, 0) or 0
            p = prev.get(key, 0) or 0
            if p == 0:
                return 0
            return round((c - p) / p * 100, 1)

        return {
            "current_period": {
                "days": period1_days,
                "metrics": current,
            },
            "comparison_period": {
                "days": period2_days,
                "metrics": previous,
            },
            "deltas": {
                "mpg_change_pct": calc_delta(current, previous, "avg_mpg"),
                "fuel_change_pct": calc_delta(current, previous, "total_gallons"),
                "idle_change_pct": calc_delta(current, previous, "idle_gallons"),
            },
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Error in historical comparison: {str(e)}"
        )


@router.get("/trends")
async def get_fleet_trends(
    days: int = Query(30, ge=7, le=90, description="Days to analyze"),
    metric: str = Query("mpg", description="Metric to trend (mpg, fuel, idle)"),
):
    """
    Fleet-wide trend analysis for specified metric.
    """
    try:
        # Simplified trend - would need historical DB queries for real trends
        fleet_data = db.get_fleet_summary()

        return {
            "metric": metric,
            "analysis_period_days": days,
            "current_value": fleet_data.get(f"avg_{metric}", 0),
            "trend_direction": "stable",  # Would compute from historical data
            "data_points": [],  # Would be historical data
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error in trends: {str(e)}")
