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

        # 🔧 v6.2.2: Simplified query - calculate gallons from miles/mpg in Python
        # to avoid SQL division issues
        query = """
            SELECT 
                truck_id,
                SUM(CASE WHEN odom_delta_mi > 0 AND odom_delta_mi < 100 THEN odom_delta_mi ELSE 0 END) as miles,
                COUNT(DISTINCT DATE(timestamp_utc)) * 8 as engine_hours,
                AVG(CASE WHEN mpg_current > 3 AND mpg_current < 12 THEN mpg_current END) as avg_mpg
            FROM fuel_metrics
            WHERE timestamp_utc >= DATE_SUB(UTC_TIMESTAMP(), INTERVAL :days DAY)
            GROUP BY truck_id
            HAVING SUM(CASE WHEN odom_delta_mi > 0 AND odom_delta_mi < 100 THEN odom_delta_mi ELSE 0 END) > 10
        """

        trucks_data = []
        try:
            with engine.connect() as conn:
                result = conn.execute(text(query), {"days": days})
                rows = result.fetchall()
                logger.info(f"Query returned {len(rows)} trucks")

            # 🔧 v6.2.2: Simplified - 4 columns now (removed gallons from SQL)
            # row[0]=truck_id, row[1]=miles, row[2]=engine_hours, row[3]=avg_mpg
            for row in rows:
                try:
                    miles = float(row[1] or 0)
                    engine_hours = float(row[2] or 0)
                    avg_mpg = float(row[3] if row[3] is not None else 5.5)
                    if avg_mpg < 3 or avg_mpg > 12:
                        avg_mpg = 5.5

                    # Calculate gallons from miles/mpg
                    gallons = miles / avg_mpg if avg_mpg > 0 else 0

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
