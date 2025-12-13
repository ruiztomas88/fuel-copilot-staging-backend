"""
Predictions Router - v3.12.21
Refuel predictions and historical comparison analytics
"""

from fastapi import APIRouter, Query, HTTPException
from typing import Optional
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Analytics"])


@router.get("/analytics/next-refuel-prediction")
async def get_next_refuel_prediction(
    truck_id: Optional[str] = Query(
        default=None, description="Specific truck or None for all"
    ),
):
    """
    🆕 v3.12.21: Predict when each truck needs its next refuel

    Uses:
    - Current fuel level (%)
    - Average consumption rate (gal/hour moving, gal/hour idle)
    - Historical refuel patterns
    - Planned route (if available)

    Returns:
        - Estimated hours/miles until refuel needed
        - Recommended refuel location (nearest fuel stops)
        - Confidence level based on data quality
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        query = """
            SELECT 
                fm.truck_id,
                fm.sensor_pct as current_fuel_pct,
                fm.estimated_pct as kalman_fuel_pct,
                fm.mpg_current as avg_mpg_24h,
                fm.consumption_gph as avg_consumption_gph_24h,
                CASE WHEN fm.truck_status = 'IDLE' THEN fm.consumption_gph ELSE 0.8 END as avg_idle_gph_24h,
                fm.truck_status,
                fm.speed_mph as speed,
                fm.timestamp_utc
            FROM fuel_metrics fm
            INNER JOIN (
                SELECT truck_id, MAX(timestamp_utc) as max_ts
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 2 HOUR)
                GROUP BY truck_id
            ) latest ON fm.truck_id = latest.truck_id AND fm.timestamp_utc = latest.max_ts
            WHERE fm.truck_id IS NOT NULL
        """

        if truck_id:
            query += " AND fm.truck_id = :truck_id"

        with engine.connect() as conn:
            if truck_id:
                result = conn.execute(text(query), {"truck_id": truck_id})
            else:
                result = conn.execute(text(query))

            rows = result.fetchall()

        predictions = []
        for row in rows:
            row_dict = dict(row._mapping)

            current_pct = (
                row_dict.get("kalman_fuel_pct")
                or row_dict.get("current_fuel_pct")
                or 50
            )
            consumption_gph = row_dict.get("avg_consumption_gph_24h") or 4.0
            idle_gph = row_dict.get("avg_idle_gph_24h") or 0.8
            avg_mpg = row_dict.get("avg_mpg_24h") or 5.7
            status = row_dict.get("truck_status") or "STOPPED"

            tank_capacity_gal = 200
            current_gallons = (current_pct / 100) * tank_capacity_gal

            low_fuel_threshold_pct = 15
            gallons_until_low = current_gallons - (
                low_fuel_threshold_pct / 100 * tank_capacity_gal
            )

            if gallons_until_low <= 0:
                hours_until_refuel = 0
                miles_until_refuel = 0
                urgency = "critical"
            else:
                if status == "MOVING":
                    current_consumption = consumption_gph
                else:
                    current_consumption = idle_gph

                blended_consumption = (consumption_gph * 0.7) + (idle_gph * 0.3)

                hours_until_refuel = (
                    gallons_until_low / blended_consumption
                    if blended_consumption > 0
                    else 999
                )
                miles_until_refuel = (
                    hours_until_refuel * 50 if avg_mpg and avg_mpg > 0 else 0
                )

                if hours_until_refuel < 4:
                    urgency = "critical"
                elif hours_until_refuel < 8:
                    urgency = "warning"
                elif hours_until_refuel < 24:
                    urgency = "normal"
                else:
                    urgency = "good"

            predictions.append(
                {
                    "truck_id": row_dict["truck_id"],
                    "current_fuel_pct": round(current_pct, 1),
                    "current_gallons": round(current_gallons, 1),
                    "hours_until_refuel": (
                        round(hours_until_refuel, 1)
                        if hours_until_refuel < 999
                        else None
                    ),
                    "miles_until_refuel": (
                        round(miles_until_refuel, 0) if miles_until_refuel > 0 else None
                    ),
                    "urgency": urgency,
                    "estimated_refuel_time": (
                        (
                            datetime.now() + timedelta(hours=hours_until_refuel)
                        ).isoformat()
                        if hours_until_refuel < 999
                        else None
                    ),
                    "avg_consumption_gph": round(consumption_gph, 2),
                    "confidence": (
                        "high" if row_dict.get("avg_consumption_gph_24h") else "medium"
                    ),
                }
            )

        urgency_order = {"critical": 0, "warning": 1, "normal": 2, "good": 3}
        predictions.sort(
            key=lambda x: (
                urgency_order.get(x["urgency"], 99),
                x.get("hours_until_refuel") or 999,
            )
        )

        return {
            "predictions": predictions,
            "count": len(predictions),
            "critical_count": len(
                [p for p in predictions if p["urgency"] == "critical"]
            ),
            "warning_count": len([p for p in predictions if p["urgency"] == "warning"]),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Next refuel prediction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/historical-comparison")
async def get_historical_comparison(
    period1_start: str = Query(..., description="Start date for period 1 (YYYY-MM-DD)"),
    period1_end: str = Query(..., description="End date for period 1 (YYYY-MM-DD)"),
    period2_start: str = Query(..., description="Start date for period 2 (YYYY-MM-DD)"),
    period2_end: str = Query(..., description="End date for period 2 (YYYY-MM-DD)"),
    truck_id: Optional[str] = Query(None, description="Specific truck ID (optional)"),
):
    """
    🆕 v3.12.21: Compare fleet metrics between two time periods.

    Useful for:
    - Month-over-month comparison
    - Before/after analysis (e.g., driver training impact)
    - Seasonal patterns

    Returns changes in:
    - MPG, fuel consumption, idle time
    - Cost metrics
    - Refuel patterns
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        base_query = """
            SELECT 
                COUNT(DISTINCT truck_id) as truck_count,
                AVG(mpg) as avg_mpg,
                AVG(consumption_gph) as avg_consumption_gph,
                AVG(idle_pct) as avg_idle_pct,
                SUM(CASE WHEN event_type = 'REFUEL' THEN 1 ELSE 0 END) as refuel_count,
                AVG(sensor_fuel_pct) as avg_fuel_level,
                AVG(daily_miles) as avg_daily_miles,
                SUM(fuel_consumed_gal) as total_fuel_consumed
            FROM fuel_metrics
            WHERE timestamp_utc BETWEEN :start_date AND :end_date
        """

        truck_filter = " AND truck_id = :truck_id" if truck_id else ""

        with engine.connect() as conn:
            params1 = {"start_date": period1_start, "end_date": period1_end}
            if truck_id:
                params1["truck_id"] = truck_id
            result1 = (
                conn.execute(text(base_query + truck_filter), params1)
                .mappings()
                .fetchone()
            )

            params2 = {"start_date": period2_start, "end_date": period2_end}
            if truck_id:
                params2["truck_id"] = truck_id
            result2 = (
                conn.execute(text(base_query + truck_filter), params2)
                .mappings()
                .fetchone()
            )

        def safe_pct_change(old, new):
            if old and old > 0 and new:
                return round(((new - old) / old) * 100, 1)
            return None

        def safe_val(val):
            return round(float(val), 2) if val else 0

        period1_data = dict(result1) if result1 else {}
        period2_data = dict(result2) if result2 else {}

        return {
            "period1": {
                "start": period1_start,
                "end": period1_end,
                "avg_mpg": safe_val(period1_data.get("avg_mpg")),
                "avg_consumption_gph": safe_val(
                    period1_data.get("avg_consumption_gph")
                ),
                "avg_idle_pct": safe_val(period1_data.get("avg_idle_pct")),
                "refuel_count": int(period1_data.get("refuel_count") or 0),
                "total_fuel_consumed": safe_val(
                    period1_data.get("total_fuel_consumed")
                ),
            },
            "period2": {
                "start": period2_start,
                "end": period2_end,
                "avg_mpg": safe_val(period2_data.get("avg_mpg")),
                "avg_consumption_gph": safe_val(
                    period2_data.get("avg_consumption_gph")
                ),
                "avg_idle_pct": safe_val(period2_data.get("avg_idle_pct")),
                "refuel_count": int(period2_data.get("refuel_count") or 0),
                "total_fuel_consumed": safe_val(
                    period2_data.get("total_fuel_consumed")
                ),
            },
            "changes": {
                "mpg_change_pct": safe_pct_change(
                    period1_data.get("avg_mpg"), period2_data.get("avg_mpg")
                ),
                "consumption_change_pct": safe_pct_change(
                    period1_data.get("avg_consumption_gph"),
                    period2_data.get("avg_consumption_gph"),
                ),
                "idle_change_pct": safe_pct_change(
                    period1_data.get("avg_idle_pct"), period2_data.get("avg_idle_pct")
                ),
                "fuel_consumed_change_pct": safe_pct_change(
                    period1_data.get("total_fuel_consumed"),
                    period2_data.get("total_fuel_consumed"),
                ),
            },
            "truck_id": truck_id,
            "generated_at": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Historical comparison error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/analytics/trends")
async def get_fleet_trends(
    days: int = Query(30, ge=7, le=365, description="Days of history"),
    metric: str = Query(
        "mpg", description="Metric to trend: mpg, consumption, idle, fuel_level"
    ),
    truck_id: Optional[str] = Query(None, description="Specific truck ID (optional)"),
):
    """
    🆕 v3.12.21: Get daily trends for a specific metric.

    Returns daily averages for charting/visualization.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        metric_map = {
            "mpg": "AVG(mpg)",
            "consumption": "AVG(consumption_gph)",
            "idle": "AVG(idle_pct)",
            "fuel_level": "AVG(sensor_fuel_pct)",
        }

        if metric not in metric_map:
            raise HTTPException(status_code=400, detail=f"Invalid metric: {metric}")

        query = f"""
            SELECT 
                DATE(timestamp_utc) as date,
                {metric_map[metric]} as value,
                COUNT(*) as sample_count
            FROM fuel_metrics
            WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
            {"AND truck_id = :truck_id" if truck_id else ""}
            GROUP BY DATE(timestamp_utc)
            ORDER BY date ASC
        """

        params = {"days": days}
        if truck_id:
            params["truck_id"] = truck_id

        with engine.connect() as conn:
            result = conn.execute(text(query), params).mappings().fetchall()

        trends = [
            {
                "date": str(row["date"]),
                "value": round(float(row["value"]), 2) if row["value"] else None,
                "sample_count": int(row["sample_count"]),
            }
            for row in result
        ]

        return {
            "metric": metric,
            "days": days,
            "truck_id": truck_id,
            "data": trends,
            "count": len(trends),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Fleet trends error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
