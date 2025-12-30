"""
EKF Integration Manager - Fase 2A
Integración del Extended Kalman Filter en el flujo de datos principal

Coordina:
- Instancia de EKF por truck_id
- Persistencia de estado EKF
- Gestión de confianza multi-sensor
- Diagnóstico y observabilidad en tiempo real
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

from ekf_estimator_wrapper import EKFEstimatorWrapper
from sensor_fusion_engine import SensorConfig, SensorFusionEngine, SensorReading

logger = logging.getLogger(__name__)


class EKFManager:
    """Gestor central de instancias EKF por truck_id"""

    def __init__(self, state_dir: str = "data/ekf_states"):
        """
        Inicializa el manager EKF

        Args:
            state_dir: Directorio para persistencia de estados
        """
        self.state_dir = Path(state_dir)
        self.state_dir.mkdir(parents=True, exist_ok=True)

        self.estimators: Dict[str, EKFEstimatorWrapper] = {}
        self.diagnostics: Dict[str, Dict] = {}
        self.health_scores: Dict[str, float] = {}

        logger.info(f"✅ EKFManager inicializado en {state_dir}")

    def get_or_create_estimator(
        self,
        truck_id: str,
        capacity_liters: float = 120.0,
        tank_shape: str = "saddle",
        use_sensor_fusion: bool = True,
    ) -> EKFEstimatorWrapper:
        """Obtiene o crea estimador EKF para un truck"""

        if truck_id not in self.estimators:
            # Cargar estado previo si existe
            state_path = self.state_dir / f"{truck_id}_ekf_state.json"
            previous_state = None

            if state_path.exists():
                try:
                    with open(state_path) as f:
                        previous_state = json.load(f)
                        logger.info(f"📂 Estado previo cargado para {truck_id}")
                except Exception as e:
                    logger.warning(f"⚠️ No se pudo cargar estado anterior: {e}")

            # Crear estimador
            # Nota: previous_state ya no es parámetro del __init__
            # El estado se maneja internamente por EKFEstimatorWrapper
            estimator = EKFEstimatorWrapper(
                truck_id=truck_id,
                capacity_liters=capacity_liters,
                config={"tank_shape": tank_shape},
                use_sensor_fusion=use_sensor_fusion,
            )

            self.estimators[truck_id] = estimator
            self.diagnostics[truck_id] = self._init_diagnostics(truck_id)
            self.health_scores[truck_id] = 1.0

            logger.info(f"🚀 EKF estimador creado para {truck_id}")

        return self.estimators[truck_id]

    def update_with_fusion(
        self,
        truck_id: str,
        fuel_lvl_pct: Optional[float] = None,
        ecu_fuel_used_L: Optional[float] = None,
        ecu_fuel_rate_gph: Optional[float] = None,
        speed_mph: float = 0,
        rpm: int = 0,
        engine_load_pct: float = 0,
        altitude_ft: float = 0,
        altitude_prev_ft: float = 0,
        ambient_temp_c: float = 20,
        capacity_liters: float = 120,
    ) -> Dict:
        """
        Actualiza EKF con datos de múltiples sensores

        Returns:
            Dict con resultados combinados y métricas de confianza
        """

        estimator = self.get_or_create_estimator(truck_id, capacity_liters)

        # Actualizar EKF base
        result = estimator.update(
            fuel_lvl_pct=fuel_lvl_pct,
            speed_mph=speed_mph,
            rpm=rpm,
            engine_load_pct=engine_load_pct,
            altitude_ft=altitude_ft,
            altitude_prev_ft=altitude_prev_ft,
            ambient_temp_c=ambient_temp_c,
            ecu_total_fuel_used_L=ecu_fuel_used_L or 0.0,
            ecu_fuel_rate_gph=ecu_fuel_rate_gph or 0.0,
        )

        # Agregar métricas de fusión
        result["fusion_quality"] = self._calculate_fusion_quality(
            fuel_lvl_pct, ecu_fuel_used_L, ecu_fuel_rate_gph
        )
        result["health_score"] = self.health_scores.get(truck_id, 0.9)

        # Actualizar diagnósticos
        self._update_diagnostics(truck_id, result)

        return result

    def get_health_status(self, truck_id: str) -> Dict:
        """Obtiene estado de salud del EKF"""
        estimator = self.estimators.get(truck_id)
        if not estimator:
            return {"status": "unknown", "reason": "estimator_not_found"}

        diag = self.diagnostics.get(truck_id, {})
        health_score = self.health_scores.get(truck_id, 0.9)

        return {
            "truck_id": truck_id,
            "health_score": health_score,
            "status": (
                "healthy"
                if health_score > 0.8
                else "degraded" if health_score > 0.6 else "unhealthy"
            ),
            "ekf_uncertainty": diag.get("avg_uncertainty_pct", 0),
            "fusion_readings": diag.get("fusion_reading_count", 0),
            "refuel_detections": diag.get("refuel_count", 0),
            "anomalies_detected": diag.get("anomaly_count", 0),
            "last_update": diag.get("last_update"),
        }

    def get_fleet_health(self) -> Dict[str, Dict]:
        """Obtiene estado de salud de toda la flota"""
        return {
            truck_id: self.get_health_status(truck_id)
            for truck_id in self.estimators.keys()
        }

    def persist_state(self, truck_id: str):
        """Persiste el estado actual del estimador"""
        estimator = self.estimators.get(truck_id)
        if not estimator:
            return

        try:
            state_path = self.state_dir / f"{truck_id}_ekf_state.json"
            state_data = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "ekf_state": {
                    "fuel_liters": estimator.ekf.state.fuel_liters,
                    "consumption_rate": estimator.ekf.state.consumption_rate,
                    "fuel_efficiency": estimator.ekf.state.fuel_efficiency,
                },
                "covariance": (
                    estimator.ekf.P.tolist() if hasattr(estimator.ekf, "P") else []
                ),
                "diagnostics": self.diagnostics.get(truck_id, {}),
            }

            with open(state_path, "w") as f:
                json.dump(state_data, f, indent=2)

            logger.debug(f"💾 Estado persistido para {truck_id}")
        except Exception as e:
            logger.error(f"❌ Error persistiendo estado: {e}")

    def persist_all(self):
        """Persiste estado de todos los estimadores"""
        for truck_id in self.estimators.keys():
            self.persist_state(truck_id)

    # ============ MÉTODOS PRIVADOS ============

    def _init_diagnostics(self, truck_id: str) -> Dict:
        """Inicializa estructura de diagnósticos"""
        return {
            "truck_id": truck_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "last_update": None,
            "update_count": 0,
            "avg_uncertainty_pct": 0,
            "fusion_reading_count": 0,
            "refuel_count": 0,
            "anomaly_count": 0,
            "efficiency_trend": [],
            "uncertainty_trend": [],
        }

    def _update_diagnostics(self, truck_id: str, result: Dict):
        """Actualiza diagnósticos con nuevo resultado"""
        diag = self.diagnostics.get(truck_id)
        if not diag:
            return

        diag["last_update"] = datetime.now(timezone.utc).isoformat()
        diag["update_count"] = diag.get("update_count", 0) + 1

        # Actualizar uncertainty trend
        uncertainty = result.get("uncertainty_pct", 0)
        diag["avg_uncertainty_pct"] = (
            diag["avg_uncertainty_pct"] * (diag["update_count"] - 1) + uncertainty
        ) / diag["update_count"]

        # Mantener últimas 100 observaciones
        if len(diag["uncertainty_trend"]) >= 100:
            diag["uncertainty_trend"] = diag["uncertainty_trend"][-99:]
        diag["uncertainty_trend"].append(uncertainty)

        # Detectar refuel (salto en fuel_pct)
        if result.get("refuel_detected"):
            diag["refuel_count"] = diag.get("refuel_count", 0) + 1

        # Calcular health score
        self._update_health_score(truck_id)

    def _update_health_score(self, truck_id: str):
        """Calcula score de salud basado en diagnósticos"""
        diag = self.diagnostics.get(truck_id, {})

        # Base: uncertainty
        uncertainty = diag.get("avg_uncertainty_pct", 0)
        score = max(0, 1.0 - (uncertainty / 100))  # ±100% = 0 health

        # Bonus por fusión consistente
        if diag.get("fusion_reading_count", 0) > 5:
            score = min(1.0, score + 0.1)

        # Penalidad por anomalías
        anomalies = diag.get("anomaly_count", 0)
        if anomalies > 0:
            score -= min(0.2, anomalies * 0.05)

        self.health_scores[truck_id] = max(0, min(1.0, score))

    def _calculate_fusion_quality(
        self,
        fuel_lvl_pct: Optional[float],
        ecu_fuel_used_L: Optional[float],
        ecu_fuel_rate_gph: Optional[float],
    ) -> float:
        """Calcula calidad de fusión de sensores (0-1)"""
        sensors_available = sum(
            [
                fuel_lvl_pct is not None,
                ecu_fuel_used_L is not None,
                ecu_fuel_rate_gph is not None,
            ]
        )

        # 3 sensores = 100%, 2 = 85%, 1 = 60%, 0 = 30%
        quality_map = {3: 1.0, 2: 0.85, 1: 0.60, 0: 0.30}
        return quality_map.get(sensors_available, 0.3)


# Instancia global
_ekf_manager: Optional[EKFManager] = None


def get_ekf_manager() -> EKFManager:
    """Obtiene instancia singleton del EKFManager"""
    global _ekf_manager
    if _ekf_manager is None:
        _ekf_manager = EKFManager()
    return _ekf_manager


def initialize_ekf_manager(state_dir: str = "data/ekf_states"):
    """Inicializa manager con directorio personalizado"""
    global _ekf_manager
    _ekf_manager = EKFManager(state_dir)
