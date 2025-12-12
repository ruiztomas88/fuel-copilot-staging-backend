"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║                     ML INTELLIGENCE ROUTER                                     ║
║            Anomaly Detection & Driver Clustering Endpoints                     ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  Endpoints:                                                                    ║
║  - GET /anomaly/fleet         → Fleet-wide anomaly analysis                   ║
║  - GET /anomaly/truck/{id}    → Single truck anomaly score                    ║
║  - GET /anomaly/summary       → High-level fleet health                       ║
║  - GET /clusters/analysis     → Full driver clustering analysis               ║
║  - GET /clusters/driver/{id}  → Single driver cluster info                    ║
║  - GET /clusters/summary      → Cluster distribution summary                  ║
║  - GET /dashboard             → Combined ML dashboard data                    ║
╚═══════════════════════════════════════════════════════════════════════════════╝

Author: Fuel Copilot ML Team
Version: 1.0.0
Date: December 2025
"""

import logging
from datetime import datetime
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/fuelAnalytics/api/ml",
    tags=["ML Intelligence"],
)


# ═══════════════════════════════════════════════════════════════════════════════
# RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════


class AnomalyFeature(BaseModel):
    feature: str
    value: float
    expected_range: str
    z_score: float
    severity: str


class TruckAnomalyResponse(BaseModel):
    truck_id: str
    anomaly_score: float
    is_anomaly: bool
    status: str
    anomalous_features: List[Dict[str, Any]]
    explanation: str
    timestamp: Optional[str] = None
    data_points_analyzed: Optional[int] = None
    model_trained_on: Optional[int] = None


class FleetAnomalySummary(BaseModel):
    fleet_health_score: float
    total_trucks: int
    status_breakdown: Dict[str, int]
    top_issues: List[Dict[str, Any]]
    timestamp: str


class DriverClusterInfo(BaseModel):
    truck_id: str
    cluster_id: int
    cluster_name: str
    cluster_emoji: str
    cluster_color: str
    description: str
    coaching_tip: str
    metrics: Dict[str, float]
    vs_cluster: Optional[Dict[str, float]] = None


class ClusterSummary(BaseModel):
    clusters: Dict[str, Any]
    total_drivers: int
    clustering_quality: float
    timestamp: str


class InsightItem(BaseModel):
    type: str
    icon: str
    title: str
    message: str


class FullClusterAnalysis(BaseModel):
    summary: ClusterSummary
    drivers: List[DriverClusterInfo]
    insights: List[InsightItem]
    analysis_period_days: int
    timestamp: str


# ═══════════════════════════════════════════════════════════════════════════════
# ANOMALY DETECTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/anomaly/fleet", response_model=List[TruckAnomalyResponse])
async def get_fleet_anomalies():
    """
    Get anomaly scores for all trucks in the fleet.

    Returns trucks sorted by anomaly score (highest/most critical first).

    Status values:
    - NORMAL: Score < 30, all parameters within normal range
    - WATCH: Score 30-50, slight deviations worth monitoring
    - WARNING: Score 50-70, notable issues, schedule inspection
    - CRITICAL: Score > 70, immediate attention required

    Example response:
    ```json
    [
        {
            "truck_id": "VD3579",
            "anomaly_score": 72.5,
            "is_anomaly": true,
            "status": "CRITICAL",
            "anomalous_features": [
                {"feature": "oil_press_normalized", "value": 18.5, "z_score": 3.2}
            ],
            "explanation": "🔴 CRITICAL: Unusual patterns in oil pressure..."
        }
    ]
    ```
    """
    try:
        from ml_engines.anomaly_detector import analyze_fleet_anomalies

        results = analyze_fleet_anomalies()
        return results
    except ImportError as e:
        logger.error(f"ML module import error: {e}")
        raise HTTPException(status_code=500, detail="ML module not available")
    except Exception as e:
        logger.error(f"Fleet anomaly analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomaly/truck/{truck_id}", response_model=TruckAnomalyResponse)
async def get_truck_anomaly(truck_id: str):
    """
    Get anomaly analysis for a specific truck.

    The analysis uses Isolation Forest ML algorithm which:
    1. Learns "normal" patterns from historical data (30 days)
    2. Compares current sensor readings against learned patterns
    3. Scores deviation from normal (0-100)

    Path Parameters:
    - truck_id: Truck identifier (e.g., "VD3579")

    Response includes:
    - anomaly_score: 0-100 (100 = most anomalous)
    - anomalous_features: Which specific sensors are unusual
    - explanation: Human-readable description
    """
    try:
        from ml_engines.anomaly_detector import analyze_truck_anomaly

        result = analyze_truck_anomaly(truck_id)
        return result
    except ImportError as e:
        logger.error(f"ML module import error: {e}")
        raise HTTPException(status_code=500, detail="ML module not available")
    except Exception as e:
        logger.error(f"Truck anomaly analysis failed for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomaly/summary", response_model=FleetAnomalySummary)
async def get_anomaly_summary():
    """
    Get high-level summary of fleet anomaly status.

    Returns:
    - fleet_health_score: 0-100 (100 = completely healthy)
    - status_breakdown: Count of trucks by status (NORMAL, WATCH, WARNING, CRITICAL)
    - top_issues: Top 5 trucks with highest anomaly scores

    Use this for dashboard overview widgets.
    """
    try:
        from ml_engines.anomaly_detector import get_fleet_anomaly_summary

        result = get_fleet_anomaly_summary()
        return result
    except ImportError as e:
        logger.error(f"ML module import error: {e}")
        raise HTTPException(status_code=500, detail="ML module not available")
    except Exception as e:
        logger.error(f"Anomaly summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# DRIVER CLUSTERING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/clusters/analysis")
async def get_cluster_analysis(
    days: int = Query(30, ge=7, le=90, description="Days of history to analyze")
):
    """
    Full driver clustering analysis.

    Uses K-Means clustering to segment drivers into behavioral groups:
    - 🏆 Efficient Pro: Top performers with excellent metrics
    - ✅ Solid Performer: Good, consistent habits
    - 📈 Needs Coaching: Room for improvement
    - ⚠️ At Risk: Significant improvement needed

    Query Parameters:
    - days: Analysis period (7-90 days, default 30)

    Returns:
    - summary: Cluster statistics and distributions
    - drivers: Individual assignments with metrics
    - insights: Actionable recommendations

    Note: First call may take 10-15 seconds to process all driver data.
    """
    try:
        from ml_engines.driver_clustering import analyze_driver_clusters

        result = analyze_driver_clusters(days)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result
    except ImportError as e:
        logger.error(f"ML module import error: {e}")
        raise HTTPException(status_code=500, detail="ML module not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cluster analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clusters/driver/{truck_id}")
async def get_driver_cluster(truck_id: str, days: int = Query(30, ge=7, le=90)):
    """
    Get cluster information for a specific driver.

    Path Parameters:
    - truck_id: Driver/truck identifier

    Query Parameters:
    - days: Analysis period (7-90 days, default 30)

    Returns driver's cluster with:
    - cluster_name: Which group they belong to
    - metrics: Their individual MPG, idle%, speed
    - vs_cluster: How they compare to cluster average
    - coaching_tip: Personalized improvement suggestion
    """
    try:
        from ml_engines.driver_clustering import get_driver_cluster

        result = get_driver_cluster(truck_id, days)

        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])

        return result
    except ImportError as e:
        logger.error(f"ML module import error: {e}")
        raise HTTPException(status_code=500, detail="ML module not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Driver cluster lookup failed for {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/clusters/summary")
async def get_clusters_summary(days: int = Query(30, ge=7, le=90)):
    """
    Get cluster distribution summary (lighter than full analysis).

    Returns just the summary without individual driver details.
    Useful for quick dashboard widgets.

    Query Parameters:
    - days: Analysis period (7-90 days, default 30)
    """
    try:
        from ml_engines.driver_clustering import analyze_driver_clusters

        result = analyze_driver_clusters(days)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return result.get("summary", {})
    except ImportError as e:
        logger.error(f"ML module import error: {e}")
        raise HTTPException(status_code=500, detail="ML module not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cluster summary failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# COMBINED INTELLIGENCE ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════


@router.get("/dashboard")
async def get_ml_dashboard():
    """
    Get combined ML dashboard data.

    Returns both anomaly detection summary and driver clustering
    in a single response for efficient dashboard loading.

    Response includes:
    - anomaly_detection: Fleet health score and status breakdown
    - driver_clustering: Cluster distribution and insights
    - timestamp: When analysis was performed
    """
    try:
        from ml_engines.anomaly_detector import get_fleet_anomaly_summary
        from ml_engines.driver_clustering import analyze_driver_clusters

        # Get anomaly data
        anomaly_summary = get_fleet_anomaly_summary()

        # Get clustering data
        cluster_result = analyze_driver_clusters(30)

        return {
            "anomaly_detection": {
                "fleet_health_score": anomaly_summary.get("fleet_health_score", 100),
                "status_breakdown": anomaly_summary.get("status_breakdown", {}),
                "critical_trucks": anomaly_summary.get("top_issues", [])[:3],
            },
            "driver_clustering": {
                "cluster_distribution": cluster_result.get("summary", {}).get(
                    "clusters", {}
                ),
                "total_drivers": cluster_result.get("summary", {}).get(
                    "total_drivers", 0
                ),
                "insights": cluster_result.get("insights", [])[:3],
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        logger.error(f"ML dashboard failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
