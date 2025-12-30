"""
Wialon Sync - Fases 2A, 2B, 2C Integration Module
Integración de EKF, ML Pipeline y Event-Driven Architecture

Este módulo extiende wialon_sync_enhanced.py con:
- EKFManager para reemplazo/complemento del FuelEstimator
- LSTM Predictor para predicciones de consumo
- Anomaly Detector para detección de fraude/fallas
- DriverBehaviorScorer para evaluación de conductores
- Event Bus para arquitectura event-driven
- Microservices Orchestrator para procesamiento desacoplado

Author: Fuel Copilot Team
Version: 1.0.0
Date: December 2025
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class Wialon2ABCIntegration:
    """Integración de Fases 2A, 2B, 2C en el flujo Wialon"""

    def __init__(self):
        """Inicializa los managers de las fases 2A, 2B, 2C"""
        self.ekf_manager = None
        self.lstm_predictor = None
        self.anomaly_detector = None
        self.behavior_scorer = None
        self.event_bus = None
        self.orchestrator = None
        self.route_optimizer = None

        self._initialize_managers()

    def _initialize_managers(self):
        """Inicializa todos los managers de forma segura"""
        try:
            from ekf_integration import get_ekf_manager

            self.ekf_manager = get_ekf_manager()
            logger.info("✅ EKF Manager inicializado")
        except Exception as e:
            logger.warning(f"⚠️ EKF Manager no disponible: {e}")

        try:
            from lstm_fuel_predictor import get_lstm_predictor

            self.lstm_predictor = get_lstm_predictor()
            logger.info("✅ LSTM Predictor inicializado")
        except Exception as e:
            logger.warning(f"⚠️ LSTM Predictor no disponible: {e}")

        try:
            from anomaly_detection_v2 import get_anomaly_detector

            self.anomaly_detector = get_anomaly_detector()
            logger.info("✅ Anomaly Detector inicializado")
        except Exception as e:
            logger.warning(f"⚠️ Anomaly Detector no disponible: {e}")

        try:
            from driver_behavior_scoring_v2 import get_behavior_scorer

            self.behavior_scorer = get_behavior_scorer()
            logger.info("✅ Driver Behavior Scorer inicializado")
        except Exception as e:
            logger.warning(f"⚠️ Driver Behavior Scorer no disponible: {e}")

        try:
            from kafka_event_bus import get_event_bus

            self.event_bus = get_event_bus()
            logger.info("✅ Event Bus inicializado")
        except Exception as e:
            logger.warning(f"⚠️ Event Bus no disponible: {e}")

        try:
            from microservices_orchestrator import get_orchestrator

            self.orchestrator = get_orchestrator()
            logger.info("✅ Microservices Orchestrator inicializado")
        except Exception as e:
            logger.warning(f"⚠️ Microservices Orchestrator no disponible: {e}")

        try:
            from route_optimization_engine import get_route_optimizer

            self.route_optimizer = get_route_optimizer()
            logger.info("✅ Route Optimizer inicializado")
        except Exception as e:
            logger.warning(f"⚠️ Route Optimizer no disponible: {e}")

    def update_ekf_with_sensor_data(
        self, truck_id: str, sensor_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Actualiza EKF con datos de sensores (FASE 2A)

        Args:
            truck_id: ID del truck
            sensor_data: Datos de sensores

        Returns:
            Resultado EKF incluyendo fuel_level_liters, health_score, etc.
        """
        if not self.ekf_manager:
            return {}

        try:
            # Extraer datos relevantes
            fuel_level_pct = sensor_data.get("fuel_lvl")
            fuel_rate_lph = sensor_data.get("fuel_rate")
            speed_mph = sensor_data.get("speed")
            rpm = sensor_data.get("rpm")
            timestamp = sensor_data.get("timestamp", datetime.now(timezone.utc))

            # Convertir fuel_rate de L/h a gph para EKF
            fuel_rate_gph = (fuel_rate_lph / 3.78541) if fuel_rate_lph else 0

            # Validar y convertir valores numéricos (evitar NoneType comparisons)
            speed_mph = float(speed_mph) if speed_mph is not None else 0.0
            rpm = int(rpm) if rpm is not None else 0

            # Actualizar EKF con parámetros correctos
            result = self.ekf_manager.update_with_fusion(
                truck_id=truck_id,
                fuel_lvl_pct=fuel_level_pct,
                ecu_fuel_rate_gph=fuel_rate_gph,
                speed_mph=speed_mph,
                rpm=rpm,
            )

            # Publicar evento de actualización de combustible
            if self.event_bus:
                from kafka_event_bus import EventType

                # Firma correcta: publish_fuel_event(truck_id, event_type, fuel_level_pct, consumption_gph, metadata)
                self.event_bus.publish_fuel_event(
                    truck_id=truck_id,
                    event_type=EventType.FUEL_LEVEL_CHANGE,
                    fuel_level_pct=result.get("fuel_level_pct", fuel_level_pct),
                    consumption_gph=fuel_rate_gph,
                    metadata={
                        "source": "ekf",
                        "timestamp": (
                            timestamp.isoformat()
                            if hasattr(timestamp, "isoformat")
                            else str(timestamp)
                        ),
                    },
                )

            return result
        except Exception as e:
            logger.error(f"Error updating EKF for {truck_id}: {e}")
            return {}

    def detect_anomalies(
        self, truck_id: str, sensor_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Detecta anomalías con Isolation Forest (FASE 2B)

        Args:
            truck_id: ID del truck
            sensor_data: Datos de sensores

        Returns:
            Resultado de detección incluyendo anomaly_type, severity, confidence
        """
        if not self.anomaly_detector:
            return {}

        try:
            # Preparar features para anomalía
            fuel_level_pct = sensor_data.get("fuel_lvl")
            speed = sensor_data.get("speed")
            rpm = sensor_data.get("rpm")
            fuel_rate_lph = sensor_data.get("fuel_rate")
            timestamp = sensor_data.get("timestamp", datetime.now(timezone.utc))

            # Validar y convertir valores numéricos
            speed = float(speed) if speed is not None else 0.0
            fuel_rate_lph = float(fuel_rate_lph) if fuel_rate_lph is not None else 0.0

            # Detectar anomalías
            # Firma correcta v2: detect_anomalies(truck_id, consumption_gph, speed_mph, idle_pct, ambient_temp_c)
            consumption_gph = (fuel_rate_lph / 3.78541) if fuel_rate_lph > 0 else 0.0
            result = self.anomaly_detector.detect_anomalies(
                truck_id=truck_id,
                consumption_gph=consumption_gph,
                speed_mph=speed,
                idle_pct=0,  # TODO: calcular idle % real
                ambient_temp_c=20,  # TODO: obtener temperatura real
            )

            # Publicar evento de anomalía si se detecta
            if result.get("anomaly_detected") and self.event_bus:
                self.event_bus.publish_anomaly_event(
                    truck_id=truck_id,
                    anomaly_type=result.get("anomaly_type"),
                    severity=result.get("severity"),
                    message=result.get("message"),
                    confidence=result.get("confidence"),
                    timestamp=timestamp,
                )

            return result
        except Exception as e:
            logger.error(f"Error detecting anomalies for {truck_id}: {e}")
            return {}

    def score_driver_behavior(
        self, truck_id: str, driver_id: str, session_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Califica comportamiento del conductor (FASE 2B)

        Args:
            truck_id: ID del truck
            driver_id: ID del conductor
            session_data: Datos de la sesión

        Returns:
            Resultado incluyendo efficiency_score, aggressiveness_score, safety_score
        """
        if not self.behavior_scorer:
            return {}

        try:
            # Calificar sesión
            result = self.behavior_scorer.score_driving_session(
                truck_id=truck_id,
                driver_id=driver_id,
                session_data=session_data,
            )

            # Publicar evento de sesión de conductor
            if self.event_bus:
                self.event_bus.publish_driver_event(
                    driver_id=driver_id,
                    truck_id=truck_id,
                    score=result.get("overall_score", 0),
                    efficiency=result.get("efficiency_score", 0),
                    safety=result.get("safety_score", 0),
                    timestamp=datetime.now(timezone.utc),
                )

            return result
        except Exception as e:
            logger.error(f"Error scoring driver {driver_id}: {e}")
            return {}

    def predict_fuel_consumption(
        self, truck_id: str, lookback_hours: int = 24
    ) -> Dict[str, Any]:
        """
        Predice consumo de combustible con LSTM (FASE 2B)

        Args:
            truck_id: ID del truck
            lookback_hours: Horas para mirar atrás en historial

        Returns:
            Predicciones para 1/4/12/24 horas
        """
        if not self.lstm_predictor:
            return {}

        try:
            # Firma correcta: predict(truck_id, recent_consumption, hours_ahead)
            # Por ahora usamos lista vacía ya que no tenemos historial reciente
            predictions = self.lstm_predictor.predict(
                truck_id=truck_id,
                recent_consumption=[],  # TODO: obtener consumo reciente de DB
                hours_ahead=4,
            )
            return predictions
        except Exception as e:
            logger.error(f"Error predicting fuel for {truck_id}: {e}")
            return {}

    def publish_event(self, topic: str, event_data: Dict[str, Any]) -> Optional[str]:
        """
        Publica evento al bus (FASE 2C)

        Args:
            topic: Nombre del topic
            event_data: Datos del evento

        Returns:
            ID del evento si se publica exitosamente
        """
        if not self.event_bus:
            return None

        try:
            self.event_bus.publish(topic, event_data)
            return event_data.get("event_id", "unknown")
        except Exception as e:
            logger.error(f"Error publishing event to {topic}: {e}")
            return None

    def get_service_status(self) -> Dict[str, Any]:
        """Obtiene estado de todos los servicios"""
        status = {
            "ekf_manager": self.ekf_manager is not None,
            "lstm_predictor": self.lstm_predictor is not None,
            "anomaly_detector": self.anomaly_detector is not None,
            "behavior_scorer": self.behavior_scorer is not None,
            "event_bus": self.event_bus is not None,
            "orchestrator": self.orchestrator is not None,
            "route_optimizer": self.route_optimizer is not None,
        }

        # Si orchestrator está disponible, obtener su estado
        if self.orchestrator:
            try:
                status["orchestrator_details"] = self.orchestrator.get_service_status()
            except Exception as e:
                logger.warning(f"Error getting orchestrator status: {e}")

        return status


# Singleton instance
_integration_instance: Optional[Wialon2ABCIntegration] = None


def get_wialon_integration() -> Wialon2ABCIntegration:
    """Obtiene o crea instancia singleton de integración"""
    global _integration_instance
    if _integration_instance is None:
        _integration_instance = Wialon2ABCIntegration()
    return _integration_instance


def initialize_wialon_integration() -> Wialon2ABCIntegration:
    """Inicializa integración (llamar en startup)"""
    integration = get_wialon_integration()
    logger.info(
        f"✅ Wialon 2ABC Integration inicializada. Status: {integration.get_service_status()}"
    )
    return integration
