"""
🆕 DEC 24 2025: Truck MPG History Router
Per-truck MPG history endpoint for frontend visualization
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import pymysql
from fastapi import APIRouter, HTTPException, Query
from logger_config import get_logger
from pydantic import BaseModel

from database_mysql import get_db_connection

logger = get_logger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api/v2/trucks", tags=["Trucks MPG History"])


class MPGHistoryPoint(BaseModel):
    """Single MPG data point"""

    timestamp: datetime
    mpg: float
    truck_status: str
    speed_mph: Optional[float] = None
    consumption_gph: Optional[float] = None


class TruckMPGHistory(BaseModel):
    """Complete MPG history for a truck"""

    truck_id: str
    period_hours: int
    data_points: List[MPGHistoryPoint]
    avg_mpg: float
    min_mpg: float
    max_mpg: float
    baseline_mpg: Optional[float] = None
    deviation_pct: Optional[float] = None


@router.get("/{truck_id}/mpg-history", response_model=TruckMPGHistory)
async def get_truck_mpg_history(
    truck_id: str,
    hours: int = Query(24, ge=1, le=168, description="Hours of history (1-168)"),
):
    """
    Get MPG history for a specific truck

    Returns time-series MPG data with baseline comparison

    Args:
        truck_id: Truck identifier
        hours: Number of hours to retrieve (default 24, max 168 = 1 week)

    Returns:
        MPG history with statistics and baseline comparison
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor(pymysql.cursors.DictCursor)

        # Calculate time range
        end_time = datetime.now(timezone.utc)
        start_time = end_time - timedelta(hours=hours)

        # Get MPG history - only valid readings
        cursor.execute(
            """
            SELECT 
                timestamp_utc,
                mpg_current as mpg,
                truck_status,
                speed_mph,
                consumption_gph
            FROM fuel_metrics
            WHERE truck_id = %s
                AND timestamp_utc >= %s
                AND timestamp_utc <= %s
                AND mpg_current > 3.5 AND mpg_current < 12  -- Valid MPG range
                AND truck_status = 'MOVING'  -- Only moving MPG
            ORDER BY timestamp_utc ASC
        """,
            (truck_id, start_time, end_time),
        )

        records = cursor.fetchall()

        if not records:
            cursor.close()
            conn.close()
            raise HTTPException(
                status_code=404,
                detail=f"No MPG history found for {truck_id} in last {hours} hours",
            )

        # Get baseline MPG from truck_specs
        cursor.execute(
            """
            SELECT baseline_mpg_loaded
            FROM truck_specs
            WHERE truck_id = %s
        """,
            (truck_id,),
        )

        baseline_row = cursor.fetchone()
        baseline_mpg = baseline_row["baseline_mpg_loaded"] if baseline_row else None

        cursor.close()
        conn.close()

        # Convert to data points
        data_points = [
            MPGHistoryPoint(
                timestamp=rec["timestamp_utc"],
                mpg=round(rec["mpg"], 2),
                truck_status=rec["truck_status"],
                speed_mph=rec["speed_mph"],
                consumption_gph=rec["consumption_gph"],
            )
            for rec in records
        ]

        # Calculate statistics
        mpg_values = [p.mpg for p in data_points]
        avg_mpg = sum(mpg_values) / len(mpg_values)
        min_mpg = min(mpg_values)
        max_mpg = max(mpg_values)

        # Calculate deviation from baseline
        deviation_pct = None
        if baseline_mpg and baseline_mpg > 0:
            deviation_pct = ((avg_mpg - baseline_mpg) / baseline_mpg) * 100

        return TruckMPGHistory(
            truck_id=truck_id,
            period_hours=hours,
            data_points=data_points,
            avg_mpg=round(avg_mpg, 2),
            min_mpg=round(min_mpg, 2),
            max_mpg=round(max_mpg, 2),
            baseline_mpg=baseline_mpg,
            deviation_pct=(
                round(deviation_pct, 1) if deviation_pct is not None else None
            ),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching MPG history for {truck_id}: {e}")
        raise HTTPException(
            status_code=500, detail=f"Error fetching MPG history: {str(e)}"
        )
