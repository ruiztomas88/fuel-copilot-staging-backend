"""
EKF Diagnostic Endpoints - Fase 2A v1
API endpoints para monitoreo y diagnóstico de EKF en tiempo real

Endpoints:
- GET /fuelAnalytics/api/ekf/health/fleet
- GET /fuelAnalytics/api/ekf/health/{truck_id}
- GET /fuelAnalytics/api/ekf/diagnostics/{truck_id}
- GET /fuelAnalytics/api/ekf/trends/{truck_id}
- POST /fuelAnalytics/api/ekf/reset/{truck_id}
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from ekf_integration import get_ekf_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api/ekf", tags=["ekf"])


@router.get("/health/fleet")
async def get_fleet_ekf_health() -> Dict:
    """
    Obtiene estado de salud EKF de toda la flota

    Returns:
        {
            "fleet_health_score": 0.92,
            "total_trucks": 45,
            "healthy_trucks": 43,
            "degraded_trucks": 2,
            "trucks": [
                {
                    "truck_id": "JC1282",
                    "health_score": 0.98,
                    "status": "healthy",
                    "uncertainty": 1.2,
                    "fusion_sensors": 3,
                    "last_update": "2025-12-23T14:35:20Z"
                },
                ...
            ]
        }
    """
    try:
        manager = get_ekf_manager()
        fleet_health = manager.get_fleet_health()

        if not fleet_health:
            return {
                "fleet_health_score": 0.0,
                "total_trucks": 0,
                "healthy_trucks": 0,
                "degraded_trucks": 0,
                "trucks": [],
            }

        # Calcular agregados
        scores = [h["health_score"] for h in fleet_health.values()]
        fleet_avg = sum(scores) / len(scores) if scores else 0

        healthy = sum(1 for h in fleet_health.values() if h["health_score"] > 0.8)
        degraded = sum(
            1 for h in fleet_health.values() if 0.6 < h["health_score"] <= 0.8
        )

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fleet_health_score": round(fleet_avg, 3),
            "total_trucks": len(fleet_health),
            "healthy_trucks": healthy,
            "degraded_trucks": degraded,
            "unhealthy_trucks": len(fleet_health) - healthy - degraded,
            "trucks": list(fleet_health.values()),
        }
    except Exception as e:
        logger.error(f"❌ Error obteniendo health de flota: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health/{truck_id}")
async def get_truck_ekf_health(truck_id: str) -> Dict:
    """
    Obtiene estado de salud EKF de un truck específico

    Returns:
        {
            "truck_id": "JC1282",
            "health_score": 0.98,
            "status": "healthy",
            "ekf_uncertainty": 1.2,
            "fusion_readings": 45,
            "refuel_detections": 2,
            "anomalies_detected": 0,
            "last_update": "2025-12-23T14:35:20Z",
            "recommendations": []
        }
    """
    try:
        manager = get_ekf_manager()
        health = manager.get_health_status(truck_id)

        if health["status"] == "unknown":
            raise HTTPException(status_code=404, detail=f"No data for {truck_id}")

        # Generar recomendaciones
        recommendations = _generate_recommendations(health)
        health["recommendations"] = recommendations
        health["timestamp"] = datetime.now(timezone.utc).isoformat()

        return health
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error obteniendo health de {truck_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/diagnostics/{truck_id}")
async def get_truck_ekf_diagnostics(
    truck_id: str,
    detailed: bool = Query(False),
) -> Dict:
    """
    Obtiene diagnósticos detallados del EKF para un truck

    Args:
        detailed: Si True, incluye histórico completo

    Returns:
        {
            "truck_id": "JC1282",
            "diagnostics": {
                "update_count": 156,
                "avg_uncertainty_pct": 1.8,
                "fusion_quality": 0.95,
                "sensor_coverage": {
                    "fuel_level": true,
                    "ecu_fuel_used": true,
                    "ecu_fuel_rate": true
                },
                "recent_events": [
                    {
                        "type": "refuel",
                        "fuel_jump_pct": 45.2,
                        "volume_liters": 54.0,
                        "timestamp": "2025-12-23T12:30:00Z"
                    }
                ]
            }
        }
    """
    try:
        manager = get_ekf_manager()
        estimator = manager.estimators.get(truck_id)

        if not estimator:
            raise HTTPException(status_code=404, detail=f"No EKF data for {truck_id}")

        diag = manager.diagnostics.get(truck_id, {})

        result = {
            "truck_id": truck_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "diagnostics": {
                "update_count": diag.get("update_count", 0),
                "avg_uncertainty_pct": round(diag.get("avg_uncertainty_pct", 0), 2),
                "fusion_reading_count": diag.get("fusion_reading_count", 0),
                "refuel_detections": diag.get("refuel_count", 0),
                "anomalies_detected": diag.get("anomaly_count", 0),
                "health_score": manager.health_scores.get(truck_id, 0.9),
            },
        }

        if detailed:
            result["diagnostics"]["uncertainty_trend"] = diag.get(
                "uncertainty_trend", []
            )[-50:]
            result["diagnostics"]["efficiency_trend"] = diag.get(
                "efficiency_trend", []
            )[-50:]

        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error obteniendo diagnostics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends/{truck_id}")
async def get_ekf_trends(
    truck_id: str,
    hours: int = Query(24, ge=1, le=720),
) -> Dict:
    """
    Obtiene tendencias de EKF (uncertainty, efficiency, fuel consumption)

    Args:
        hours: Rango en horas (1-720)

    Returns:
        {
            "truck_id": "JC1282",
            "period_hours": 24,
            "trends": {
                "uncertainty": [
                    {"timestamp": "2025-12-22T14:35:00Z", "value": 2.1},
                    ...
                ],
                "efficiency": [
                    {"timestamp": "2025-12-22T14:35:00Z", "value": 0.98},
                    ...
                ],
                "consumption_gph": [
                    {"timestamp": "2025-12-22T14:35:00Z", "value": 3.2},
                    ...
                ]
            }
        }
    """
    try:
        manager = get_ekf_manager()
        diag = manager.diagnostics.get(truck_id)

        if not diag:
            raise HTTPException(status_code=404, detail=f"No trends for {truck_id}")

        # Retornar últimas N observaciones (aproximado a hours)
        uncertainty_trend = diag.get("uncertainty_trend", [])
        efficiency_trend = diag.get("efficiency_trend", [])

        # Estimar punto de datos por hora (típicamente 1 por minuto en producción)
        # Para demo, usar últimas 24 valores
        points = min(24, len(uncertainty_trend))

        return {
            "truck_id": truck_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "period_hours": hours,
            "trends": {
                "uncertainty_last_n": uncertainty_trend[-points:],
                "efficiency_last_n": efficiency_trend[-points:],
                "update_count": len(uncertainty_trend),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error obteniendo trends: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset/{truck_id}")
async def reset_ekf_state(truck_id: str, force: bool = Query(False)) -> Dict:
    """
    Reinicia el estado EKF de un truck

    Args:
        force: Si True, reinicia sin confirmación

    Returns:
        {"status": "reset", "truck_id": "JC1282", "timestamp": "..."}
    """
    try:
        if not force:
            # En producción, requerir confirmación adicional
            return {
                "status": "reset_pending",
                "truck_id": truck_id,
                "message": "Call again with force=true to confirm",
            }

        manager = get_ekf_manager()

        if truck_id in manager.estimators:
            del manager.estimators[truck_id]
            if truck_id in manager.diagnostics:
                del manager.diagnostics[truck_id]
            if truck_id in manager.health_scores:
                del manager.health_scores[truck_id]

            logger.warning(f"⚠️ EKF reset para {truck_id}")

            return {
                "status": "reset",
                "truck_id": truck_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            raise HTTPException(status_code=404, detail=f"No EKF for {truck_id}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Error resetando EKF: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============ HELPER FUNCTIONS ============


def _generate_recommendations(health: Dict) -> List[str]:
    """Genera recomendaciones basadas en estado de salud"""
    recommendations = []

    score = health.get("health_score", 0.9)
    uncertainty = health.get("ekf_uncertainty", 0)

    if score < 0.6:
        recommendations.append("⚠️ Revisar sensores de combustible - salud baja")
    elif score < 0.8:
        recommendations.append("📊 Considerar calibración de sensores")

    if uncertainty > 5:
        recommendations.append("📈 Incertidumbre alta - verificar ECU")
    elif uncertainty > 2:
        recommendations.append("🔧 Incertidumbre moderada - monitorear")

    if health.get("anomalies_detected", 0) > 5:
        recommendations.append("🚨 Anomalías recurrentes detectadas")

    return recommendations
