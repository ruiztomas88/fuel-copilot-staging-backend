"""
Anomaly Detection Engine - Fase 2B
Detección de anomalías en consumo de combustible usando Isolation Forest

Features:
- Detección de siphoning (drenaje anormal)
- Detección de sensor malfunction
- Detección de fugas lentas
- Análisis temporal y contextual
- Alertas automáticas
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler

    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    logging.warning("⚠️ scikit-learn no disponible - anomaly detection deshabilitado")

logger = logging.getLogger(__name__)


class AnomalyType:
    """Tipos de anomalías detectables"""

    SIPHONING = "siphoning"  # Drenaje rápido
    SENSOR_MALFUNCTION = "sensor_malfunction"  # Sensor defectuoso
    SLOW_LEAK = "slow_leak"  # Fuga lenta
    CONSUMPTION_SPIKE = "consumption_spike"  # Pico de consumo anormal
    INCONSISTENT_REFUEL = "inconsistent_refuel"  # Patrón de refuel extraño
    IDLE_EXCESSIVE = "idle_excessive"  # Consumo en idle muy alto


class AnomalyDetector:
    """Detector de anomalías con Isolation Forest"""

    def __init__(self):
        """Inicializa detector de anomalías"""
        self.models: Dict[str, IsolationForest] = {}
        self.scalers: Dict[str, StandardScaler] = {}
        self.anomaly_history: Dict[str, List[Dict]] = {}
        self.thresholds: Dict[str, Dict] = {}

        if SKLEARN_AVAILABLE:
            logger.info("✅ Anomaly Detector inicializado")
        else:
            logger.warning("⚠️ Anomaly detection deshabilitado")

    def train_detector(
        self,
        truck_id: str,
        consumption_data: List[float],
        speed_data: List[float],
        idle_pct_data: List[float],
        refuel_count: int = 0,
        contamination: float = 0.05,  # Asume 5% de anomalías
    ) -> Dict:
        """
        Entrena Isolation Forest para un truck

        Args:
            truck_id: Identificador
            consumption_data: Histórico de consumo (gph)
            speed_data: Histórico de velocidad (mph)
            idle_pct_data: Porcentaje de tiempo en idle
            refuel_count: Número de refueles (para normalización)
            contamination: Proporción esperada de anomalías

        Returns:
            {"status": "trained", "anomalies_detected": 5, ...}
        """
        if not SKLEARN_AVAILABLE:
            return {"status": "unavailable"}

        if len(consumption_data) < 10:
            return {
                "status": "insufficient_data",
                "required": 10,
                "available": len(consumption_data),
            }

        try:
            # Crear feature matrix
            features = self._create_feature_matrix(
                consumption_data, speed_data, idle_pct_data
            )

            # Normalizar
            scaler = StandardScaler()
            features_scaled = scaler.fit_transform(features)
            self.scalers[truck_id] = scaler

            # Entrenar Isolation Forest
            model = IsolationForest(
                contamination=contamination,
                random_state=42,
                n_estimators=100,
            )
            predictions = model.fit_predict(features_scaled)
            self.models[truck_id] = model

            # Contar anomalías
            anomalies = sum(1 for p in predictions if p == -1)

            # Calcular umbrales adaptativos
            self._compute_thresholds(truck_id, consumption_data, speed_data)

            logger.info(f"✅ Detector entrenado para {truck_id}: {anomalies} anomalías")
            return {
                "status": "trained",
                "truck_id": truck_id,
                "total_samples": len(consumption_data),
                "anomalies_detected": anomalies,
                "anomaly_rate_pct": round(anomalies / len(consumption_data) * 100, 2),
            }
        except Exception as e:
            logger.error(f"❌ Error entrenando detector: {e}")
            return {"status": "training_failed", "error": str(e)}

    def detect_anomalies(
        self,
        truck_id: str,
        consumption_gph: float,
        speed_mph: float,
        idle_pct: float,
        ambient_temp_c: float = 20,
        recent_history: Optional[List[float]] = None,
    ) -> Dict:
        """
        Detecta anomalías en observación actual

        Args:
            truck_id: Identificador
            consumption_gph: Consumo actual
            speed_mph: Velocidad actual
            idle_pct: Porcentaje en idle
            ambient_temp_c: Temperatura ambiente
            recent_history: Últimas N observaciones para análisis temporal

        Returns:
            {
                "is_anomaly": False,
                "anomaly_type": None,
                "anomaly_score": 0.15,
                "confidence": 0.92,
                "details": {...}
            }
        """
        if not SKLEARN_AVAILABLE:
            return {"is_anomaly": False, "status": "unavailable"}

        if truck_id not in self.models:
            return {
                "is_anomaly": False,
                "status": "model_not_found",
                "truck_id": truck_id,
            }

        try:
            # Crear features para observación actual
            features = np.array([[consumption_gph, speed_mph, idle_pct]])

            # Normalizar
            scaler = self.scalers.get(truck_id)
            if scaler:
                features = scaler.transform(features)

            # Predicción Isolation Forest
            model = self.models[truck_id]
            prediction = model.predict(features)[0]
            anomaly_score = -model.score_samples(features)[
                0
            ]  # Score positivo para anomalías

            # Determinar si es anomalía
            is_anomaly = prediction == -1

            # Clasificar tipo de anomalía
            anomaly_type = None
            confidence = 0.0
            details = {}

            if is_anomaly:
                anomaly_type, confidence, details = self._classify_anomaly(
                    truck_id,
                    consumption_gph,
                    speed_mph,
                    idle_pct,
                    ambient_temp_c,
                    recent_history,
                )

            # Registrar en histórico
            if truck_id not in self.anomaly_history:
                self.anomaly_history[truck_id] = []

            if is_anomaly:
                self.anomaly_history[truck_id].append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "type": anomaly_type,
                        "score": float(anomaly_score),
                        "consumption_gph": consumption_gph,
                        "speed_mph": speed_mph,
                    }
                )
                # Mantener últimas 100
                if len(self.anomaly_history[truck_id]) > 100:
                    self.anomaly_history[truck_id] = self.anomaly_history[truck_id][
                        -100:
                    ]

            return {
                "is_anomaly": is_anomaly,
                "truck_id": truck_id,
                "anomaly_type": anomaly_type,
                "anomaly_score": float(anomaly_score),
                "confidence": float(confidence),
                "details": details,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"❌ Error detectando anomalías: {e}")
            return {"is_anomaly": False, "error": str(e)}

    def get_anomaly_summary(self, truck_id: str, days: int = 7) -> Dict:
        """Obtiene resumen de anomalías"""
        history = self.anomaly_history.get(truck_id, [])

        if not history:
            return {
                "truck_id": truck_id,
                "total_anomalies": 0,
                "anomaly_types": {},
                "recent_anomalies": [],
            }

        # Contar por tipo
        type_counts = {}
        for item in history:
            atype = item.get("type", "unknown")
            type_counts[atype] = type_counts.get(atype, 0) + 1

        return {
            "truck_id": truck_id,
            "total_anomalies": len(history),
            "anomaly_types": type_counts,
            "recent_anomalies": history[-10:],  # Últimas 10
        }

    # ============ MÉTODOS PRIVADOS ============

    def _create_feature_matrix(
        self,
        consumption: List[float],
        speed: List[float],
        idle_pct: List[float],
    ) -> np.ndarray:
        """Crea matriz de features para Isolation Forest"""
        features = []

        for i in range(len(consumption)):
            f = [
                consumption[i],
                speed[i] if i < len(speed) else 0,
                idle_pct[i] if i < len(idle_pct) else 0,
            ]
            features.append(f)

        return np.array(features, dtype=np.float32)

    def _classify_anomaly(
        self,
        truck_id: str,
        consumption_gph: float,
        speed_mph: float,
        idle_pct: float,
        ambient_temp_c: float,
        recent_history: Optional[List[float]],
    ) -> Tuple[str, float, Dict]:
        """Clasifica el tipo específico de anomalía"""

        thresholds = self.thresholds.get(truck_id, {})
        details = {}
        anomaly_type = AnomalyType.CONSUMPTION_SPIKE
        confidence = 0.7

        # Análisis de siphoning (consumo muy alto en parado)
        if speed_mph < 2 and idle_pct > 90:
            if consumption_gph > thresholds.get("idle_max_gph", 0.5) * 2:
                anomaly_type = AnomalyType.SIPHONING
                confidence = 0.95
                details["consumption_vs_idle_max"] = consumption_gph / thresholds.get(
                    "idle_max_gph", 0.1
                )

        # Análisis de fuga lenta (degradación gradual)
        if recent_history and len(recent_history) > 5:
            trend = np.polyfit(range(len(recent_history)), recent_history, 1)[0]
            if trend > 0.1:  # Consumo aumentando
                anomaly_type = AnomalyType.SLOW_LEAK
                confidence = 0.85
                details["consumption_trend_gph_per_hour"] = float(trend)

        # Análisis de pico de consumo
        max_normal = thresholds.get("consumption_max_gph", 5.0)
        if consumption_gph > max_normal * 1.5:
            anomaly_type = AnomalyType.CONSUMPTION_SPIKE
            confidence = 0.80
            details["consumption_ratio"] = consumption_gph / max_normal

        return anomaly_type, confidence, details

    def _compute_thresholds(
        self,
        truck_id: str,
        consumption: List[float],
        speed: List[float],
    ):
        """Computa umbrales adaptativos por truck"""
        consumption = np.array(consumption)
        speed = np.array(speed)

        # Filtrar observaciones en idle (speed < 5 mph)
        idle_mask = speed < 5
        idle_consumption = consumption[idle_mask] if any(idle_mask) else consumption

        # Filtrar observaciones en highway (speed > 50 mph)
        highway_mask = speed > 50
        highway_consumption = (
            consumption[highway_mask] if any(highway_mask) else consumption
        )

        self.thresholds[truck_id] = {
            "consumption_mean_gph": float(np.mean(consumption)),
            "consumption_max_gph": float(np.percentile(consumption, 95)),
            "consumption_std_gph": float(np.std(consumption)),
            "idle_max_gph": (
                float(np.percentile(idle_consumption, 90))
                if len(idle_consumption) > 0
                else 0.5
            ),
            "highway_max_gph": (
                float(np.percentile(highway_consumption, 95))
                if len(highway_consumption) > 0
                else 4.0
            ),
        }


# Instancia global
_anomaly_detector: Optional[AnomalyDetector] = None


def get_anomaly_detector() -> AnomalyDetector:
    """Obtiene instancia singleton del detector de anomalías"""
    global _anomaly_detector
    if _anomaly_detector is None:
        _anomaly_detector = AnomalyDetector()
    return _anomaly_detector
