"""
Reports Router - v3.12.21
Scheduled reports and report generation endpoints
"""

from fastapi import APIRouter, Query, HTTPException, Response
from typing import Dict, Any, Optional
import logging
from datetime import datetime, timedelta
from timezone_utils import utc_now
import pandas as pd

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api", tags=["Reports"])

# In-memory storage for scheduled reports (replace with DB in production)
_scheduled_reports: Dict[str, Dict] = {}


@router.get("/reports/schedules")
async def get_report_schedules():
    """
    🆕 v3.12.21: Get all scheduled reports.
    """
    return {
        "schedules": list(_scheduled_reports.values()),
        "count": len(_scheduled_reports),
    }


@router.post("/reports/schedules")
async def create_report_schedule(
    name: str = Query(..., description="Report name"),
    report_type: str = Query(
        ..., description="Type: daily_summary, weekly_kpis, monthly_analysis"
    ),
    frequency: str = Query(..., description="Frequency: daily, weekly, monthly"),
    email_to: str = Query(..., description="Email recipient(s), comma-separated"),
    include_trucks: Optional[str] = Query(
        None, description="Truck IDs to include, comma-separated"
    ),
):
    """
    🆕 v3.12.21: Create a scheduled report.
    """
    import uuid

    schedule_id = str(uuid.uuid4())[:8]

    schedule = {
        "id": schedule_id,
        "name": name,
        "report_type": report_type,
        "frequency": frequency,
        "email_to": [e.strip() for e in email_to.split(",")],
        "include_trucks": (
            [t.strip() for t in include_trucks.split(",")] if include_trucks else None
        ),
        "created_at": datetime.now().isoformat(),
        "last_run": None,
        "next_run": None,
        "status": "active",
    }

    _scheduled_reports[schedule_id] = schedule

    return {
        "success": True,
        "schedule": schedule,
        "message": f"Report schedule '{name}' created successfully",
    }


@router.delete("/reports/schedules/{schedule_id}")
async def delete_report_schedule(schedule_id: str):
    """
    🆕 v3.12.21: Delete a scheduled report.
    """
    if schedule_id not in _scheduled_reports:
        raise HTTPException(status_code=404, detail="Schedule not found")

    del _scheduled_reports[schedule_id]
    return {"success": True, "message": f"Schedule {schedule_id} deleted"}


@router.post("/reports/generate")
async def generate_report_now(
    report_type: str = Query(
        ..., description="Type: daily_summary, weekly_kpis, theft_analysis"
    ),
    days: int = Query(7, ge=1, le=90, description="Days to include"),
    format: str = Query("json", description="Format: json, csv, excel"),
):
    """
    🆕 v3.12.21: Generate a report immediately.
    """
    try:
        from database_mysql import get_sqlalchemy_engine
        from sqlalchemy import text
        import io

        engine = get_sqlalchemy_engine()

        if report_type == "daily_summary":
            query = """
                SELECT 
                    truck_id,
                    DATE(timestamp_utc) as date,
                    AVG(mpg) as avg_mpg,
                    AVG(consumption_gph) as avg_consumption,
                    AVG(sensor_fuel_pct) as avg_fuel_level,
                    MAX(daily_miles) as miles_driven,
                    SUM(CASE WHEN event_type = 'REFUEL' THEN 1 ELSE 0 END) as refuel_count
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
                GROUP BY truck_id, DATE(timestamp_utc)
                ORDER BY date DESC, truck_id
            """
        elif report_type == "weekly_kpis":
            query = """
                SELECT 
                    YEARWEEK(timestamp_utc) as week,
                    COUNT(DISTINCT truck_id) as active_trucks,
                    AVG(mpg) as fleet_avg_mpg,
                    AVG(idle_pct) as fleet_avg_idle,
                    SUM(fuel_consumed_gal) as total_fuel_gal,
                    SUM(daily_miles) / COUNT(DISTINCT DATE(timestamp_utc)) as avg_daily_miles
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
                GROUP BY YEARWEEK(timestamp_utc)
                ORDER BY week DESC
            """
        elif report_type == "theft_analysis":
            query = """
                SELECT 
                    truck_id,
                    timestamp_utc,
                    sensor_fuel_pct,
                    estimated_fuel_pct,
                    status,
                    CASE 
                        WHEN ABS(sensor_fuel_pct - estimated_fuel_pct) > 10 
                        AND status = 'STOPPED' THEN 'SUSPICIOUS'
                        ELSE 'NORMAL'
                    END as alert_status
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL :days DAY)
                  AND ABS(sensor_fuel_pct - estimated_fuel_pct) > 5
                ORDER BY timestamp_utc DESC
                LIMIT 500
            """
        else:
            raise HTTPException(
                status_code=400, detail=f"Unknown report type: {report_type}"
            )

        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={"days": days})

        if format == "json":
            return {
                "report_type": report_type,
                "days": days,
                "generated_at": datetime.now().isoformat(),
                "row_count": len(df),
                "data": df.to_dict(orient="records"),
            }
        elif format == "excel":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name=report_type, index=False)
            output.seek(0)

            filename = f"{report_type}_{datetime.now().strftime('%Y%m%d')}.xlsx"
            return Response(
                content=output.getvalue(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )
        else:
            output = io.StringIO()
            df.to_csv(output, index=False)

            filename = f"{report_type}_{datetime.now().strftime('%Y%m%d')}.csv"
            return Response(
                content=output.getvalue(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename={filename}"},
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/scheduled/{user_id}")
async def get_scheduled_reports(user_id: str):
    """
    🆕 v3.12.21: Get user's scheduled reports.
    """
    user_reports = [
        r for r in _scheduled_reports.values() if r.get("user_id") == user_id
    ]
    return {"reports": user_reports, "total": len(user_reports)}


@router.post("/reports/schedule")
async def create_scheduled_report(report: Dict[str, Any]):
    """
    🆕 v3.12.21: Create a new scheduled report.
    """
    import uuid

    report_id = f"report-{uuid.uuid4().hex[:8]}"
    report["id"] = report_id
    report["created_at"] = utc_now().isoformat()
    report["enabled"] = True
    report["last_run"] = None

    schedule = report.get("schedule", "daily")
    if schedule == "daily":
        report["next_run"] = (
            (utc_now() + timedelta(days=1))
            .replace(hour=6, minute=0, second=0)
            .isoformat()
        )
    elif schedule == "weekly":
        report["next_run"] = (
            (utc_now() + timedelta(days=7))
            .replace(hour=6, minute=0, second=0)
            .isoformat()
        )
    elif schedule == "monthly":
        report["next_run"] = (
            (utc_now() + timedelta(days=30))
            .replace(hour=6, minute=0, second=0)
            .isoformat()
        )

    _scheduled_reports[report_id] = report

    logger.info(f"📅 Scheduled report created: {report_id}")
    return {"status": "created", "report": report}


@router.put("/reports/schedule/{report_id}")
async def update_scheduled_report(report_id: str, updates: Dict[str, Any]):
    """
    🆕 v3.12.21: Update a scheduled report.
    """
    if report_id not in _scheduled_reports:
        raise HTTPException(status_code=404, detail="Report not found")

    report = _scheduled_reports[report_id]
    report.update(updates)
    report["updated_at"] = utc_now().isoformat()

    return {"status": "updated", "report": report}


@router.delete("/reports/schedule/{report_id}")
async def delete_scheduled_report_v2(report_id: str):
    """
    🆕 v3.12.21: Delete a scheduled report.
    """
    if report_id not in _scheduled_reports:
        raise HTTPException(status_code=404, detail="Report not found")

    del _scheduled_reports[report_id]

    logger.info(f"🗑️ Scheduled report deleted: {report_id}")
    return {"status": "deleted", "report_id": report_id}


@router.post("/reports/run/{report_id}")
async def run_report_now(report_id: str):
    """
    🆕 v3.12.21: Run a scheduled report immediately.
    """
    if report_id not in _scheduled_reports:
        raise HTTPException(status_code=404, detail="Report not found")

    report = _scheduled_reports[report_id]
    report_type = report.get("report_type", "fleet_summary")

    try:
        data = {"message": f"Report type '{report_type}' generated"}
        report["last_run"] = utc_now().isoformat()

        return {
            "status": "success",
            "report_id": report_id,
            "generated_at": report["last_run"],
            "data_preview": str(data)[:500] if data else None,
        }
    except Exception as e:
        logger.error(f"Report generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
