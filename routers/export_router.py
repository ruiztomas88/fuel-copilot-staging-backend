"""
Export Router - v3.12.21
Data export endpoints (CSV, Excel)
"""

from fastapi import APIRouter, Query, HTTPException, Response
from typing import Optional
import logging
from datetime import datetime
import pandas as pd

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Export"])


@router.get("/export/fleet-report")
async def export_fleet_report(
    format: str = Query(default="csv", description="Export format: csv or excel"),
    days: int = Query(default=7, ge=1, le=90, description="Days to include"),
):
    """
    🆕 v3.12.21: Export fleet data to CSV or Excel

    Includes:
    - All trucks with current status
    - MPG, fuel consumption, idle metrics
    - Refuel events
    - Alerts/issues
    """
    try:
        import io
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        query = """
            SELECT 
                truck_id,
                truck_status as status,
                COALESCE(sensor_pct, 0) as fuel_pct,
                COALESCE(estimated_pct, 0) as estimated_fuel_pct,
                COALESCE(drift_pct, 0) as drift_pct,
                COALESCE(mpg_current, 0) as current_mpg,
                COALESCE(avg_mpg_24h, 0) as avg_mpg_24h,
                COALESCE(consumption_gph, 0) as consumption_gph,
                COALESCE(idle_consumption_gph, 0) as idle_gph,
                COALESCE(speed, 0) as speed_mph,
                latitude,
                longitude,
                timestamp_utc as last_update
            FROM truck_data_latest
            WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
            ORDER BY truck_id
        """

        with engine.connect() as conn:
            result = conn.execute(text(query), {"days": days})
            data = [dict(row._mapping) for row in result.fetchall()]

        if not data:
            raise HTTPException(
                status_code=404, detail="No data found for the specified period"
            )

        df = pd.DataFrame(data)

        if "last_update" in df.columns:
            df["last_update"] = pd.to_datetime(df["last_update"]).dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        if format.lower() == "excel":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Fleet Report", index=False)
            output.seek(0)

            filename = f"fleet_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            return Response(
                content=output.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        else:
            output = io.StringIO()
            df.to_csv(output, index=False)

            filename = f"fleet_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/export/refuels")
async def export_refuels_report(
    format: str = Query(default="csv", description="Export format: csv or excel"),
    days: int = Query(default=30, ge=1, le=365, description="Days to include"),
    truck_id: Optional[str] = Query(default=None, description="Filter by truck"),
):
    """
    🆕 v3.12.21: Export refuel events to CSV or Excel
    """
    try:
        import io
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text

        engine = get_sqlalchemy_engine()

        query = """
            SELECT 
                truck_id,
                timestamp_utc as refuel_time,
                fuel_before,
                fuel_after,
                gallons_added,
                refuel_type,
                latitude,
                longitude,
                validated
            FROM refuel_events
            WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
        """

        params = {"days": days}
        if truck_id:
            query += " AND truck_id = :truck_id"
            params["truck_id"] = truck_id

        query += " ORDER BY timestamp_utc DESC"

        with engine.connect() as conn:
            result = conn.execute(text(query), params)
            data = [dict(row._mapping) for row in result.fetchall()]

        if not data:
            raise HTTPException(status_code=404, detail="No refuel events found")

        df = pd.DataFrame(data)

        if "refuel_time" in df.columns:
            df["refuel_time"] = pd.to_datetime(df["refuel_time"]).dt.strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        if format.lower() == "excel":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Refuel Events", index=False)
            output.seek(0)

            filename = f"refuels_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            return Response(
                content=output.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        else:
            output = io.StringIO()
            df.to_csv(output, index=False)

            filename = f"refuels_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Export refuels error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
