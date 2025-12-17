"""
DEF and Pattern Analytics Router
=================================
Version: 1.0.0
Created: December 2025

FastAPI router providing REST endpoints for:
- DEF (Diesel Exhaust Fluid) predictions and alerts
- DTW (Dynamic Time Warping) pattern analysis
- Fleet pattern anomaly detection
- Data loading and cache management

Endpoints:
- GET /def/predictions - Get DEF predictions for all trucks
- GET /def/predictions/{truck_id} - Get DEF prediction for specific truck
- GET /def/fleet-status - Get fleet-wide DEF status summary
- GET /def/alerts - Get trucks needing DEF attention
- GET /patterns/compare - Compare patterns between trucks
- GET /patterns/anomalies - Detect pattern anomalies
- GET /patterns/clusters - Get fleet clustering by patterns
- GET /patterns/similar/{truck_id} - Find similar trucks
- POST /data/refresh - Refresh data from Wialon
- GET /data/inventory - Get data inventory
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, List, Optional, Any
from datetime import datetime
import logging

from def_predictor import DEFPredictor, DEFReading, DEFAlertLevel
from dtw_analyzer import DTWAnalyzer, TimeSeriesData
from wialon_data_loader import get_wialon_loader, WialonDataLoader

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["DEF & Pattern Analytics"])


# ============== Singleton Instances ==============

_def_predictor: Optional[DEFPredictor] = None
_dtw_analyzer: Optional[DTWAnalyzer] = None
_data_loaded: bool = False


def get_def_predictor() -> DEFPredictor:
    """Get or create DEF predictor singleton"""
    global _def_predictor
    if _def_predictor is None:
        loader = get_wialon_loader()
        _def_predictor = DEFPredictor(db_connection=loader.db_connection)
        _def_predictor.load_truck_mapping(loader.tanks_config)
    return _def_predictor


def get_dtw_analyzer() -> DTWAnalyzer:
    """Get or create DTW analyzer singleton"""
    global _dtw_analyzer
    if _dtw_analyzer is None:
        loader = get_wialon_loader()
        _dtw_analyzer = DTWAnalyzer(db_connection=loader.db_connection)
        _dtw_analyzer.load_truck_mapping(loader.tanks_config)
    return _dtw_analyzer


async def ensure_data_loaded(force: bool = False):
    """Ensure analytics data is loaded from Wialon"""
    global _data_loaded

    if _data_loaded and not force:
        return

    loader = get_wialon_loader()

    if not loader.is_connected():
        if not loader.connect():
            raise HTTPException(
                status_code=503, detail="No se pudo conectar a la base de datos Wialon"
            )

    try:
        # Load DEF data for predictor
        def_predictor = get_def_predictor()
        def_predictor.db = loader.db_connection

        def_data = loader.load_def_data(days=30)
        for row in def_data:
            reading = DEFReading(
                timestamp=row["timestamp"],
                unit_id=row["unit_id"],
                truck_id=row["truck_id"],
                level_percent=float(row["def_level"]),
                odometer=float(row["odometer"]) if row.get("odometer") else None,
                engine_hours=(
                    float(row["engine_hours"]) if row.get("engine_hours") else None
                ),
            )
            def_predictor.add_reading(reading)

        # Load time series for DTW analyzer
        dtw_analyzer = get_dtw_analyzer()
        dtw_analyzer.db = loader.db_connection

        # Load fuel level patterns
        fuel_data = loader.load_sensor_data("fuel_lvl", days=30)
        _load_time_series(dtw_analyzer, fuel_data, "fuel_lvl")

        # Load oil pressure patterns
        oil_data = loader.load_sensor_data("oil_press", days=30)
        _load_time_series(dtw_analyzer, oil_data, "oil_press")

        # Load coolant temp patterns
        cool_data = loader.load_sensor_data("cool_temp", days=30)
        _load_time_series(dtw_analyzer, cool_data, "cool_temp")

        _data_loaded = True
        logger.info("Analytics data loaded successfully")

    except Exception as e:
        logger.error(f"Error loading analytics data: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _load_time_series(analyzer: DTWAnalyzer, data: List[Dict], metric: str):
    """Helper to load time series data into DTW analyzer"""
    from collections import defaultdict

    # Group by truck
    by_truck = defaultdict(list)
    for row in data:
        by_truck[row["truck_id"]].append(row)

    # Create time series for each truck
    for truck_id, rows in by_truck.items():
        if len(rows) < 10:  # Minimum data requirement
            continue

        # Sort by timestamp
        rows.sort(key=lambda r: r["timestamp"])

        series = TimeSeriesData(
            truck_id=truck_id,
            unit_id=rows[0]["unit_id"],
            metric_name=metric,
            timestamps=[r["timestamp"] for r in rows],
            values=[float(r[metric]) for r in rows],
        )

        analyzer.add_time_series(series)


# ============== DEF Endpoints ==============


@router.get("/def/predictions")
async def get_def_predictions(
    alert_level: Optional[str] = Query(
        None,
        description="Filter by alert level (good, low, warning, critical, emergency)",
    )
) -> Dict[str, Any]:
    """
    Get DEF predictions for all trucks.

    Returns predictions including:
    - Current DEF level
    - Estimated miles/hours/days until empty
    - Alert level and recommendations
    """
    await ensure_data_loaded()
    predictor = get_def_predictor()

    predictions = predictor.predict_all()

    # Filter by alert level if specified
    if alert_level:
        try:
            level_enum = DEFAlertLevel(alert_level.lower())
            predictions = [p for p in predictions if p.alert_level == level_enum]
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid alert level. Valid values: {[l.value for l in DEFAlertLevel]}",
            )

    return {
        "status": "success",
        "count": len(predictions),
        "predictions": [predictor.to_dict(p) for p in predictions],
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/def/predictions/{truck_id}")
async def get_def_prediction_by_truck(truck_id: str) -> Dict[str, Any]:
    """
    Get DEF prediction for a specific truck.

    Args:
        truck_id: Truck identifier (e.g., VD3579)
    """
    await ensure_data_loaded()
    predictor = get_def_predictor()

    prediction = predictor.predict(truck_id)

    if not prediction:
        raise HTTPException(
            status_code=404, detail=f"No hay datos DEF para el camión {truck_id}"
        )

    return {
        "status": "success",
        "prediction": predictor.to_dict(prediction),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/def/fleet-status")
async def get_def_fleet_status() -> Dict[str, Any]:
    """
    Get fleet-wide DEF status summary.

    Returns:
    - Overall fleet status (good/warning/critical/emergency)
    - Count of trucks by alert level
    - List of trucks needing attention
    """
    await ensure_data_loaded()
    predictor = get_def_predictor()

    return predictor.get_fleet_def_status()


@router.get("/def/alerts")
async def get_def_alerts() -> Dict[str, Any]:
    """
    Get only trucks with DEF alerts (warning or worse).

    Sorted by urgency, most urgent first.
    """
    await ensure_data_loaded()
    predictor = get_def_predictor()

    predictions = predictor.predict_all()

    # Filter to only warning+ levels
    alerts = [
        p
        for p in predictions
        if p.alert_level
        in [DEFAlertLevel.WARNING, DEFAlertLevel.CRITICAL, DEFAlertLevel.EMERGENCY]
    ]

    return {
        "status": "success",
        "alert_count": len(alerts),
        "alerts": [
            {
                "truck_id": p.truck_id,
                "level_percent": round(p.current_level_percent, 1),
                "alert_level": p.alert_level.value,
                "miles_until_empty": round(p.miles_until_empty, 0),
                "days_until_empty": round(p.days_until_empty, 1),
                "urgency_score": p.urgency_score,
                "recommendation": p.recommended_action,
            }
            for p in alerts
        ],
        "timestamp": datetime.now().isoformat(),
    }


# ============== Pattern Analysis Endpoints ==============


@router.get("/patterns/compare")
async def compare_truck_patterns(
    truck_1: str = Query(..., description="First truck ID"),
    truck_2: str = Query(..., description="Second truck ID"),
    metric: str = Query(
        "fuel_lvl", description="Metric to compare (fuel_lvl, oil_press, cool_temp)"
    ),
) -> Dict[str, Any]:
    """
    Compare patterns between two trucks using DTW.

    Returns similarity score and distance metrics.
    """
    await ensure_data_loaded()
    analyzer = get_dtw_analyzer()

    result = analyzer.compare_trucks(truck_1, truck_2, metric)

    if not result:
        raise HTTPException(
            status_code=404,
            detail=f"No hay suficientes datos para comparar {truck_1} y {truck_2} en {metric}",
        )

    return {
        "status": "success",
        "comparison": analyzer.to_dict(result),
        "interpretation": _interpret_similarity(result.similarity_percent),
        "timestamp": datetime.now().isoformat(),
    }


def _interpret_similarity(similarity: float) -> str:
    """Interpret similarity percentage"""
    if similarity > 90:
        return "✅ Patrones muy similares - comportamiento casi idéntico"
    elif similarity > 70:
        return "🟢 Patrones similares - operación comparable"
    elif similarity > 50:
        return "🟡 Patrones moderadamente diferentes - revisar condiciones de operación"
    elif similarity > 30:
        return "🟠 Patrones diferentes - posibles diferencias operativas significativas"
    else:
        return "🔴 Patrones muy diferentes - investigar causas"


@router.get("/patterns/anomalies")
async def detect_pattern_anomalies(
    metric: str = Query("fuel_lvl", description="Metric to analyze"),
    include_normal: bool = Query(
        False, description="Include trucks with normal patterns"
    ),
) -> Dict[str, Any]:
    """
    Detect trucks with anomalous patterns compared to fleet baseline.

    Uses DTW to compare each truck's pattern against all others.
    """
    await ensure_data_loaded()
    analyzer = get_dtw_analyzer()

    anomalies = analyzer.detect_anomalies(metric)

    if not include_normal:
        anomalies = [a for a in anomalies if a.is_anomaly]

    return {
        "status": "success",
        "metric": metric,
        "total_trucks_analyzed": len(anomalies) if include_normal else "N/A",
        "anomaly_count": sum(1 for a in anomalies if a.is_anomaly),
        "results": [
            {
                "truck_id": a.truck_id,
                "is_anomaly": a.is_anomaly,
                "anomaly_score": round(a.anomaly_score, 1),
                "percentile_rank": round(a.percentile_rank, 1),
                "most_similar_truck": a.most_similar_truck,
                "least_similar_truck": a.least_similar_truck,
                "description": a.description,
            }
            for a in anomalies
        ],
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/patterns/clusters")
async def get_fleet_clusters(
    metric: str = Query("fuel_lvl", description="Metric to cluster by"),
    n_clusters: int = Query(3, ge=2, le=5, description="Number of clusters"),
) -> Dict[str, Any]:
    """
    Cluster fleet into groups based on pattern similarity.

    Groups trucks with similar operating patterns together.
    """
    await ensure_data_loaded()
    analyzer = get_dtw_analyzer()

    clusters = analyzer.cluster_fleet(metric, n_clusters=n_clusters)

    return {
        "status": "success",
        "metric": metric,
        "cluster_count": len(clusters),
        "clusters": [
            {
                "cluster_id": c.cluster_id,
                "cluster_name": c.cluster_name,
                "truck_count": len(c.truck_ids),
                "trucks": c.truck_ids,
                "representative_truck": c.centroid_truck,
                "cohesion": round(100 * (1 / (1 + c.avg_intra_cluster_distance)), 1),
                "description": c.pattern_description,
            }
            for c in clusters
        ],
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/patterns/similar/{truck_id}")
async def find_similar_trucks(
    truck_id: str,
    metric: str = Query("fuel_lvl", description="Metric to compare"),
    top_n: int = Query(5, ge=1, le=20, description="Number of results"),
) -> Dict[str, Any]:
    """
    Find trucks with patterns most similar to the given truck.

    Useful for benchmarking and finding comparable vehicles.
    """
    await ensure_data_loaded()
    analyzer = get_dtw_analyzer()

    similar = analyzer.find_most_similar(truck_id, metric, top_n=top_n)

    if not similar:
        raise HTTPException(
            status_code=404,
            detail=f"No hay suficientes datos para encontrar camiones similares a {truck_id}",
        )

    return {
        "status": "success",
        "reference_truck": truck_id,
        "metric": metric,
        "similar_trucks": [
            {
                "truck_id": r.truck_id_2,
                "similarity_percent": round(r.similarity_percent, 1),
                "dtw_distance": round(r.dtw_distance, 4),
                "rank": i + 1,
            }
            for i, r in enumerate(similar)
        ],
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/patterns/summary")
async def get_pattern_summary(
    metric: str = Query("fuel_lvl", description="Metric to analyze")
) -> Dict[str, Any]:
    """
    Get comprehensive pattern analysis summary for the fleet.

    Includes anomalies and clustering in one response.
    """
    await ensure_data_loaded()
    analyzer = get_dtw_analyzer()

    return analyzer.get_fleet_pattern_summary(metric)


# ============== Data Management Endpoints ==============


@router.post("/data/refresh")
async def refresh_analytics_data(
    days: int = Query(30, ge=1, le=90, description="Days of history to load")
) -> Dict[str, Any]:
    """
    Force refresh of all analytics data from Wialon.

    Clears cache and reloads from database.
    """
    global _data_loaded
    _data_loaded = False

    loader = get_wialon_loader()
    loader.clear_cache()

    # Force data reload
    await ensure_data_loaded(force=True)

    return {
        "status": "success",
        "message": f"Datos actualizados ({days} días de historia)",
        "cache_status": loader.get_cache_status(),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/data/inventory")
async def get_data_inventory() -> Dict[str, Any]:
    """
    Get inventory of available data in Wialon database.

    Shows what sensors and events are available.
    """
    loader = get_wialon_loader()

    if not loader.is_connected():
        if not loader.connect():
            raise HTTPException(status_code=503, detail="No se pudo conectar a Wialon")

    inventory = loader.get_data_inventory()
    cache_status = loader.get_cache_status()

    return {
        "status": "success",
        "inventory": inventory,
        "cache": cache_status,
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/data/cache-status")
async def get_cache_status() -> Dict[str, Any]:
    """
    Get current cache status.
    """
    loader = get_wialon_loader()

    return {
        "status": "success",
        "cache": loader.get_cache_status(),
        "timestamp": datetime.now().isoformat(),
    }


# ============== Combined Analytics Endpoint ==============


@router.get("/analytics/dashboard")
async def get_analytics_dashboard() -> Dict[str, Any]:
    """
    Get combined analytics dashboard data.

    Single endpoint for all key metrics:
    - DEF fleet status
    - Pattern anomalies
    - Fleet clusters
    """
    await ensure_data_loaded()

    predictor = get_def_predictor()
    analyzer = get_dtw_analyzer()

    # Get DEF status
    def_status = predictor.get_fleet_def_status()

    # Get anomalies for fuel
    anomalies = analyzer.detect_anomalies("fuel_lvl")
    anomaly_trucks = [a for a in anomalies if a.is_anomaly]

    # Get clusters
    clusters = analyzer.cluster_fleet("fuel_lvl", n_clusters=3)

    return {
        "status": "success",
        "def_status": {
            "fleet_status": def_status.get("fleet_status"),
            "status_icon": def_status.get("status_icon"),
            "message": def_status.get("message"),
            "trucks_needing_attention": len(
                def_status.get("trucks_needing_attention", [])
            ),
            "average_level_percent": def_status.get("average_level_percent"),
        },
        "pattern_analysis": {
            "anomaly_count": len(anomaly_trucks),
            "top_anomalies": [
                {"truck_id": a.truck_id, "score": round(a.anomaly_score, 1)}
                for a in anomaly_trucks[:3]
            ],
            "cluster_count": len(clusters),
            "cluster_sizes": [len(c.truck_ids) for c in clusters],
        },
        "data_freshness": {
            "cache_entries": get_wialon_loader().get_cache_status().get("entries", 0)
        },
        "timestamp": datetime.now().isoformat(),
    }


# Export router
__all__ = ["router"]
