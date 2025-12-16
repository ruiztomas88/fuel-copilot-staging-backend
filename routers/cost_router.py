"""
Cost Analysis Router - v4.0
Cost per mile and speed impact analysis endpoints
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional, Any
import logging
import math

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Cost Analysis"])


def sanitize_json(obj: Any) -> Any:
    """
    🔧 v6.2.3: Recursively sanitize data to be JSON-safe.
    Replaces inf, -inf, nan with 0 to prevent JSON serialization errors.
    """
    if isinstance(obj, dict):
        return {k: sanitize_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return 0.0
        return obj
    return obj


@router.get("/cost/per-mile")
async def get_fleet_cost_per_mile(
    days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
):
    """
    🆕 v4.0: Get cost per mile analysis for entire fleet.

    Returns:
        Fleet-wide cost analysis with individual truck breakdowns
    """
    try:
        from cost_per_mile_engine import CostPerMileEngine
        from database_mysql import get_sqlalchemy_engine
        from database import db
        from sqlalchemy import text

        logger.info(f"Starting cost per mile analysis for {days} days")

        engine = get_sqlalchemy_engine()
        cpm_engine = CostPerMileEngine()

        # 🔧 v6.2.6: Use REAL data from refuel_events table for accurate fuel costs
        # This gives us actual gallons purchased, not estimates
        query = """
            SELECT 
                fm.truck_id,
                SUM(CASE WHEN fm.odom_delta_mi > 0 AND fm.odom_delta_mi < 100 THEN fm.odom_delta_mi ELSE 0 END) as odom_miles,
                COUNT(DISTINCT DATE(fm.timestamp_utc)) as active_days,
                AVG(CASE WHEN fm.mpg_current > 3 AND fm.mpg_current < 12 THEN fm.mpg_current END) as avg_mpg,
                COALESCE(ref.total_gallons, 0) as refuel_gallons
            FROM fuel_metrics fm
            LEFT JOIN (
                SELECT truck_id, SUM(gallons_added) as total_gallons
                FROM refuel_events
                WHERE timestamp >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL :days DAY)
                GROUP BY truck_id
            ) ref ON fm.truck_id = ref.truck_id
            WHERE fm.timestamp_utc >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL :days DAY)
            GROUP BY fm.truck_id
            HAVING COUNT(*) > 10
        """

        trucks_data = []
        try:
            with engine.connect() as conn:
                result = conn.execute(text(query), {"days": days})
                rows = result.fetchall()
                logger.info(f"Query returned {len(rows)} trucks")

            # 🔧 v6.2.6: Use refuel data when available, estimate conservatively otherwise
            total_fleet_miles = 0
            total_fleet_gallons = 0
            for row in rows:
                try:
                    odom_miles = float(row[1] or 0)
                    active_days = int(row[2] or 0)
                    avg_mpg = float(row[3] if row[3] is not None else 5.5)
                    refuel_gallons = float(row[4] or 0)

                    if avg_mpg < 3 or avg_mpg > 12:
                        avg_mpg = 5.5

                    # Use odometer miles if available, otherwise estimate conservatively
                    if odom_miles > 10:
                        miles = odom_miles
                    elif refuel_gallons > 0 and avg_mpg > 0:
                        # Estimate from fuel: miles = gallons × MPG
                        miles = refuel_gallons * avg_mpg
                    else:
                        # Very conservative estimate: 100 miles/day for active trucks
                        miles = active_days * 100 if active_days > 0 else 0

                    # Use actual refuel gallons if available, otherwise estimate from miles
                    if refuel_gallons > 0:
                        gallons = refuel_gallons
                    elif miles > 0 and avg_mpg > 0:
                        gallons = miles / avg_mpg
                    else:
                        gallons = 0

                    if miles < 1 and gallons < 1:
                        continue  # Skip trucks with no activity

                    total_fleet_miles += miles
                    total_fleet_gallons += gallons

                    # Conservative engine hours: 1 hour per 50 miles driven
                    engine_hours = miles / 50 if miles > 0 else active_days * 2

                    trucks_data.append(
                        {
                            "truck_id": row[0],
                            "miles": miles,
                            "gallons": gallons,
                            "engine_hours": engine_hours,
                            "avg_mpg": avg_mpg,
                        }
                    )
                except Exception as row_err:
                    logger.warning(f"Error processing row {row[0]}: {row_err}")
                    continue

            logger.info(
                f"Processed {len(trucks_data)} trucks, total_miles={total_fleet_miles:.0f}, "
                f"total_gallons={total_fleet_gallons:.0f}"
            )
        except Exception as db_err:
            logger.warning(f"DB query failed, using fallback: {db_err}")

        if not trucks_data:
            logger.info("No historical data, using current truck data for estimates")
            try:
                all_trucks = db.get_all_trucks()
                for tid in all_trucks[:20]:
                    truck_data = db.get_truck_latest_record(tid)
                    if truck_data:
                        mpg = truck_data.get("mpg_current", 5.5) or 5.5
                        if mpg < 3 or mpg > 12:
                            mpg = 5.5
                        miles = 8000
                        trucks_data.append(
                            {
                                "truck_id": tid,
                                "miles": miles,
                                "gallons": miles / max(mpg, 1),
                                "engine_hours": truck_data.get("engine_hours", 200)
                                or 200,
                                "avg_mpg": mpg,
                            }
                        )
            except Exception as fallback_err:
                logger.error(f"Fallback also failed: {fallback_err}")

        if not trucks_data:
            logger.warning("All data sources failed, returning demo data")
            trucks_data = [
                {
                    "truck_id": "DEMO-001",
                    "miles": 8000,
                    "gallons": 1450,
                    "engine_hours": 200,
                    "avg_mpg": 5.5,
                },
                {
                    "truck_id": "DEMO-002",
                    "miles": 7500,
                    "gallons": 1250,
                    "engine_hours": 190,
                    "avg_mpg": 6.0,
                },
            ]

        report = cpm_engine.generate_cost_report(trucks_data, period_days=days)
        # 🔧 v6.2.3: Sanitize response to remove inf/nan values
        return sanitize_json(report)

    except Exception as e:
        logger.error(f"Cost per mile analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/per-mile/{truck_id}")
async def get_truck_cost_per_mile(
    truck_id: str,
    days: int = Query(30, ge=1, le=365, description="Analysis period in days"),
):
    """
    🆕 v4.0: Get cost per mile analysis for a specific truck.

    Returns:
        Detailed cost breakdown and comparison for the specified truck
    """
    try:
        from cost_per_mile_engine import CostPerMileEngine
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()
        cpm_engine = CostPerMileEngine()

        query = """
            SELECT 
                (MAX(odometer_mi) - MIN(odometer_mi)) as miles,
                (MAX(odometer_mi) - MIN(odometer_mi)) / NULLIF(AVG(CASE WHEN mpg_current > 0 THEN mpg_current END), 0) as gallons,
                MAX(engine_hours) - MIN(engine_hours) as engine_hours,
                AVG(CASE WHEN mpg_current > 0 THEN mpg_current END) as avg_mpg
            FROM fuel_metrics
            WHERE truck_id = :truck_id
                AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
                AND mpg_current > 0
        """

        with engine.connect() as conn:
            result = conn.execute(text(query), {"truck_id": truck_id, "days": days})
            row = result.fetchone()

        if not row or not row[0]:
            raise HTTPException(
                status_code=404, detail=f"No data found for truck {truck_id}"
            )

        truck_data = {
            "miles": float(row[0] or 0),
            "gallons": float(row[1] or 0),
            "engine_hours": float(row[2] or 0),
            "avg_mpg": float(row[3] or 0),
        }

        analysis = cpm_engine.analyze_truck_costs(
            truck_id=truck_id,
            period_days=days,
            truck_data=truck_data,
        )

        return {"status": "success", "data": analysis.to_dict()}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Truck cost analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost/speed-impact")
async def get_speed_cost_impact(
    avg_speed_mph: float = Query(65, ge=40, le=90, description="Average highway speed"),
    monthly_miles: float = Query(8000, ge=1000, le=50000, description="Monthly miles"),
):
    """
    🆕 v4.0: Calculate cost impact of speeding.

    Based on DOE research: "Every 5 mph over 60 reduces fuel efficiency by ~0.7 MPG"

    Returns:
        Cost impact analysis showing potential savings from speed reduction
    """
    try:
        from cost_per_mile_engine import calculate_speed_cost_impact

        impact = calculate_speed_cost_impact(
            avg_speed_mph=avg_speed_mph,
            monthly_miles=monthly_miles,
        )

        return {"status": "success", "data": impact}

    except Exception as e:
        logger.error(f"Speed impact analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
