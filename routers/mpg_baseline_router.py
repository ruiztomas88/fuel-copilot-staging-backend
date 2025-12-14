"""
MPG Baseline Router v5.7.6
═══════════════════════════════════════════════════════════════════════════════

API endpoints for historical MPG baseline analysis.

Endpoints:
- GET /mpg-baseline/{truck_id} - Get baseline for a truck
- GET /mpg-baseline/fleet - Get baselines for all trucks
- GET /mpg-baseline/{truck_id}/deviation - Analyze current MPG vs baseline
- POST /mpg-baseline/calculate - Trigger baseline recalculation
"""

import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/mpg-baseline", tags=["MPG Baseline"])


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class MPGBaselineResponse(BaseModel):
    """Response model for MPG baseline"""

    truck_id: str
    baseline_mpg: float = Field(..., description="Calculated baseline MPG")
    std_dev: float = Field(..., description="Standard deviation")
    min_mpg: float = Field(..., description="Minimum observed MPG")
    max_mpg: float = Field(..., description="Maximum observed MPG")
    sample_count: int = Field(..., description="Number of samples used")
    days_analyzed: int = Field(..., description="Days of data analyzed")
    confidence: str = Field(
        ..., description="Confidence level: LOW, MEDIUM, HIGH, VERY_HIGH"
    )
    confidence_score: float = Field(..., description="Numeric confidence 0-1")
    percentile_25: float = Field(..., description="25th percentile")
    percentile_75: float = Field(..., description="75th percentile")
    last_calculated: Optional[str] = Field(
        None, description="ISO timestamp of calculation"
    )


class DeviationResponse(BaseModel):
    """Response model for deviation analysis"""

    truck_id: str
    current_mpg: float
    baseline_mpg: float
    deviation_pct: float = Field(..., description="Percentage deviation from baseline")
    z_score: float = Field(..., description="Standard deviations from mean")
    status: str = Field(
        ..., description="NORMAL, LOW, HIGH, CRITICAL_LOW, CRITICAL_HIGH"
    )
    message: str = Field(..., description="Human-readable status message")
    confidence: str = Field(..., description="Baseline confidence level")


class FleetBaselineResponse(BaseModel):
    """Response model for fleet-wide baselines"""

    total_trucks: int
    avg_baseline_mpg: float
    trucks_high_confidence: int
    trucks_low_confidence: int
    baselines: list[dict]


class FleetComparisonResponse(BaseModel):
    """Response for comparing truck to fleet"""

    truck_id: str
    truck_baseline: float
    fleet_average: float
    difference_mpg: float
    difference_pct: float
    status: str = Field(..., description="ABOVE_AVERAGE, AVERAGE, BELOW_AVERAGE")
    message: str


class CalculationRequest(BaseModel):
    """Request to calculate baseline"""

    truck_ids: Optional[list[str]] = Field(
        None, description="Specific trucks (or all if null)"
    )
    days: int = Field(30, ge=7, le=365, description="Days of history to analyze")
    min_speed_mph: float = Field(10.0, ge=0, description="Minimum speed to filter idle")


# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/{truck_id}", response_model=MPGBaselineResponse)
async def get_truck_baseline(
    truck_id: str,
    days: int = Query(30, ge=7, le=365, description="Days of history to analyze"),
):
    """
    Get historical MPG baseline for a specific truck.

    Calculates baseline from fuel_metrics data using:
    - IQR filtering to remove outliers
    - Statistical analysis (mean, std dev, percentiles)
    - Confidence scoring based on data quality
    """
    try:
        from mpg_baseline_service import MPGBaselineService
        from database_pool import get_pool

        pool = await get_pool()
        service = MPGBaselineService(db_pool=pool)

        baseline = await service.calculate_baseline(truck_id, days=days)
        return MPGBaselineResponse(**baseline.to_dict())

    except ImportError:
        # Fallback for testing without database
        logger.warning(
            f"Database not available, returning mock baseline for {truck_id}"
        )
        return MPGBaselineResponse(
            truck_id=truck_id,
            baseline_mpg=5.7,
            std_dev=0.8,
            min_mpg=4.5,
            max_mpg=7.0,
            sample_count=0,
            days_analyzed=days,
            confidence="MOCK",
            confidence_score=0.0,
            percentile_25=5.2,
            percentile_75=6.2,
            last_calculated=None,
        )
    except Exception as e:
        logger.error(f"Error getting baseline for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{truck_id}/deviation", response_model=DeviationResponse)
async def analyze_deviation(
    truck_id: str,
    current_mpg: float = Query(..., description="Current MPG reading to analyze"),
):
    """
    Analyze how current MPG deviates from truck's historical baseline.

    Returns status indicators:
    - NORMAL: Within expected range
    - LOW: MPG below baseline (potential issue)
    - HIGH: MPG above baseline (possible sensor error)
    - CRITICAL_LOW: Severe deviation, needs immediate attention
    - CRITICAL_HIGH: Extremely high, likely sensor error
    """
    try:
        from mpg_baseline_service import MPGBaselineService
        from database_pool import get_pool

        pool = await get_pool()
        service = MPGBaselineService(db_pool=pool)

        # First get baseline
        baseline = await service.calculate_baseline(truck_id, days=30)

        # Then analyze deviation
        analysis = service.analyze_deviation(truck_id, current_mpg, baseline=baseline)
        return DeviationResponse(**analysis.to_dict())

    except ImportError:
        from mpg_baseline_service import MPGBaselineService, MPGBaseline

        service = MPGBaselineService()
        baseline = MPGBaseline(truck_id=truck_id)
        analysis = service.analyze_deviation(truck_id, current_mpg, baseline=baseline)
        return DeviationResponse(**analysis.to_dict())

    except Exception as e:
        logger.error(f"Error analyzing deviation for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/fleet", response_model=FleetBaselineResponse)
@router.get("/fleet/summary", response_model=FleetBaselineResponse)
async def get_fleet_baselines(
    days: int = Query(30, ge=7, le=365, description="Days of history to analyze")
):
    """
    Get MPG baselines for all trucks in the fleet.

    Returns summary statistics and individual baselines for each truck
    with sufficient data.
    """
    try:
        from mpg_baseline_service import MPGBaselineService
        from database_pool import get_pool

        pool = await get_pool()
        service = MPGBaselineService(db_pool=pool)

        baselines = await service.calculate_fleet_baselines(days=days)

        # Build response
        high_conf = sum(
            1 for b in baselines.values() if b.confidence in ("HIGH", "VERY_HIGH")
        )
        low_conf = sum(
            1 for b in baselines.values() if b.confidence in ("LOW", "INSUFFICIENT")
        )

        avg_mpg = (
            sum(b.baseline_mpg for b in baselines.values()) / len(baselines)
            if baselines
            else 5.7
        )

        return FleetBaselineResponse(
            total_trucks=len(baselines),
            avg_baseline_mpg=round(avg_mpg, 2),
            trucks_high_confidence=high_conf,
            trucks_low_confidence=low_conf,
            baselines=[b.to_dict() for b in baselines.values()],
        )

    except ImportError:
        logger.warning("Database not available, returning empty fleet summary")
        return FleetBaselineResponse(
            total_trucks=0,
            avg_baseline_mpg=5.7,
            trucks_high_confidence=0,
            trucks_low_confidence=0,
            baselines=[],
        )
    except Exception as e:
        logger.error(f"Error getting fleet baselines: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{truck_id}/fleet-comparison", response_model=FleetComparisonResponse)
async def compare_to_fleet(truck_id: str, days: int = Query(30, ge=7, le=365)):
    """
    Compare a truck's baseline to the fleet average.

    Shows whether the truck performs above, at, or below fleet average.
    """
    try:
        from mpg_baseline_service import MPGBaselineService, compare_to_fleet_average
        from database_pool import get_pool

        pool = await get_pool()
        service = MPGBaselineService(db_pool=pool)

        # Get truck baseline
        baseline = await service.calculate_baseline(truck_id, days=days)

        # Get fleet average
        fleet_baselines = await service.calculate_fleet_baselines(days=days)
        if fleet_baselines:
            fleet_avg = sum(b.baseline_mpg for b in fleet_baselines.values()) / len(
                fleet_baselines
            )
        else:
            fleet_avg = 5.7

        # Compare
        result = compare_to_fleet_average(baseline, fleet_avg)
        return FleetComparisonResponse(**result)

    except ImportError:
        return FleetComparisonResponse(
            truck_id=truck_id,
            truck_baseline=5.7,
            fleet_average=5.7,
            difference_mpg=0.0,
            difference_pct=0.0,
            status="AVERAGE",
            message="Database not available for comparison",
        )
    except Exception as e:
        logger.error(f"Error comparing {truck_id} to fleet: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calculate")
async def trigger_calculation(request: CalculationRequest):
    """
    Trigger baseline recalculation for specified trucks or entire fleet.

    Use this to force recalculation after significant data changes.
    """
    try:
        from mpg_baseline_service import MPGBaselineService
        from database_pool import get_pool

        pool = await get_pool()
        service = MPGBaselineService(db_pool=pool)

        if request.truck_ids:
            # Calculate for specific trucks
            results = {}
            for truck_id in request.truck_ids:
                baseline = await service.calculate_baseline(
                    truck_id, days=request.days, min_speed_mph=request.min_speed_mph
                )
                results[truck_id] = baseline.to_dict()

            return {
                "status": "completed",
                "trucks_processed": len(results),
                "baselines": results,
            }
        else:
            # Calculate for entire fleet
            baselines = await service.calculate_fleet_baselines(
                days=request.days, min_speed_mph=request.min_speed_mph
            )

            return {
                "status": "completed",
                "trucks_processed": len(baselines),
                "summary": service.get_fleet_summary(),
            }

    except ImportError:
        return {"status": "skipped", "message": "Database not available"}
    except Exception as e:
        logger.error(f"Error calculating baselines: {e}")
        raise HTTPException(status_code=500, detail=str(e))
