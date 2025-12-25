"""
Microservices Architecture - Fase 2C
Descomposición de servicios para escalabilidad

Servicios:
- FuelMetricsService: Cálculo de métricas de combustible
- AnomalyService: Detección de anomalías
- DriverBehaviorService: Análisis de conducción
- PredictionService: Predicciones (LSTM)
- AlertService: Gestión de alertas
- MaintenanceService: Predicción de mantenimiento

Comunicación: Event Bus (Kafka mockup para staging)
"""

import logging
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from kafka_event_bus import EventType, get_event_bus

logger = logging.getLogger(__name__)


class MicroService(ABC):
    """Base para todos los microservicios"""

    def __init__(self, service_name: str):
        """Inicializa microservicio"""
        self.service_name = service_name
        self.event_bus = get_event_bus()
        self.status = "initialized"
        self.error_count = 0
        self.success_count = 0

        logger.info(f"✅ {service_name} inicializado")

    @abstractmethod
    def process(self, event: Dict) -> Optional[Dict]:
        """Procesa un evento"""
        pass

    def get_status(self) -> Dict:
        """Obtiene estado del servicio"""
        return {
            "service_name": self.service_name,
            "status": self.status,
            "success_count": self.success_count,
            "error_count": self.error_count,
            "uptime_seconds": 0,  # Implementar con timestamps
        }


class FuelMetricsService(MicroService):
    """Servicio para cálculo de métricas de combustible"""

    def __init__(self):
        """Inicializa servicio de métricas"""
        super().__init__("FuelMetricsService")
        self.truck_metrics: Dict[str, Dict] = {}

        # Suscribir a eventos de cambio de combustible
        self.event_bus.subscribe(EventType.FUEL_LEVEL_CHANGE.value, self.process)

    def process(self, event: Dict) -> Optional[Dict]:
        """Procesa cambios de nivel de combustible"""
        try:
            truck_id = event.get("truck_id")
            fuel_level_pct = event.get("fuel_level_pct")
            consumption_gph = event.get("consumption_gph")

            # Actualizar métricas
            if truck_id not in self.truck_metrics:
                self.truck_metrics[truck_id] = {
                    "fuel_level_pct": fuel_level_pct,
                    "consumption_gph": consumption_gph,
                    "updates": 0,
                }

            self.truck_metrics[truck_id].update(
                {
                    "fuel_level_pct": fuel_level_pct,
                    "consumption_gph": consumption_gph,
                    "updates": self.truck_metrics[truck_id]["updates"] + 1,
                    "last_update": datetime.now(timezone.utc).isoformat(),
                }
            )

            self.success_count += 1

            # Publicar métrica calculada
            result = {
                "truck_id": truck_id,
                "fuel_level_pct": fuel_level_pct,
                "consumption_gph": consumption_gph,
                "service": "FuelMetricsService",
            }

            return result
        except Exception as e:
            logger.error(f"❌ Error en FuelMetricsService: {e}")
            self.error_count += 1
            return None

    def get_truck_metrics(self, truck_id: str) -> Optional[Dict]:
        """Obtiene métricas de un truck"""
        return self.truck_metrics.get(truck_id)

    def get_all_metrics(self) -> Dict:
        """Obtiene métricas de todos los trucks"""
        return self.truck_metrics


class AnomalyService(MicroService):
    """Servicio para detección de anomalías"""

    def __init__(self):
        """Inicializa servicio de anomalías"""
        super().__init__("AnomalyService")
        self.anomalies: Dict[str, List[Dict]] = {}

        # Suscribir a eventos de combustible
        self.event_bus.subscribe(EventType.FUEL_LEVEL_CHANGE.value, self.process)

    def process(self, event: Dict) -> Optional[Dict]:
        """Procesa eventos para detectar anomalías"""
        try:
            truck_id = event.get("truck_id")
            consumption_gph = event.get("consumption_gph")

            # Lógica simplificada de detección
            is_anomaly = consumption_gph > 10  # Consumo > 10 gph es anómalo

            if is_anomaly:
                anomaly = {
                    "truck_id": truck_id,
                    "type": "high_consumption",
                    "consumption_gph": consumption_gph,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                if truck_id not in self.anomalies:
                    self.anomalies[truck_id] = []

                self.anomalies[truck_id].append(anomaly)

                # Publicar evento de anomalía
                self.event_bus.publish_anomaly_event(
                    truck_id=truck_id,
                    anomaly_type="high_consumption",
                    severity="warning",
                    message=f"Consumo anómalamente alto: {consumption_gph} gph",
                    confidence=0.85,
                )

                self.success_count += 1
                return anomaly
        except Exception as e:
            logger.error(f"❌ Error en AnomalyService: {e}")
            self.error_count += 1

        return None

    def get_anomalies(self, truck_id: str) -> List[Dict]:
        """Obtiene anomalías de un truck"""
        return self.anomalies.get(truck_id, [])


class DriverBehaviorService(MicroService):
    """Servicio para análisis de conducción"""

    def __init__(self):
        """Inicializa servicio de conducción"""
        super().__init__("DriverBehaviorService")
        self.driver_sessions: Dict[str, Dict] = {}

    def process(self, event: Dict) -> Optional[Dict]:
        """Procesa eventos de conducción"""
        try:
            event_type = event.get("event_type")

            if event_type == EventType.DRIVER_SESSION_END.value:
                driver_id = event.get("driver_id")
                truck_id = event.get("truck_id")
                score = event.get("score", 0)

                # Registrar sesión
                session_key = f"{driver_id}_{truck_id}"
                self.driver_sessions[session_key] = {
                    "driver_id": driver_id,
                    "truck_id": truck_id,
                    "score": score,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                # Publicar evento
                if score > 80:
                    event_type = EventType.EFFICIENT_DRIVING.value
                elif score < 40:
                    event_type = EventType.UNSAFE_PATTERN.value

                self.success_count += 1

            return event
        except Exception as e:
            logger.error(f"❌ Error en DriverBehaviorService: {e}")
            self.error_count += 1

        return None

    def get_driver_sessions(self, driver_id: str) -> List[Dict]:
        """Obtiene sesiones de un driver"""
        return [
            s for s in self.driver_sessions.values() if s.get("driver_id") == driver_id
        ]


class PredictionService(MicroService):
    """Servicio para predicciones (LSTM, etc)"""

    def __init__(self):
        """Inicializa servicio de predicciones"""
        super().__init__("PredictionService")
        self.predictions: Dict[str, List[Dict]] = {}

    def process(self, event: Dict) -> Optional[Dict]:
        """Procesa eventos para generar predicciones"""
        try:
            truck_id = event.get("truck_id")
            consumption_gph = event.get("consumption_gph")

            # Simulación de predicción LSTM
            prediction = {
                "truck_id": truck_id,
                "prediction_hours": 4,
                "predicted_consumption_gph": consumption_gph * 1.1,  # Predicción simple
                "confidence": 0.85,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            if truck_id not in self.predictions:
                self.predictions[truck_id] = []

            self.predictions[truck_id].append(prediction)

            # Limitar histórico
            if len(self.predictions[truck_id]) > 100:
                self.predictions[truck_id] = self.predictions[truck_id][-100:]

            # Publicar evento de predicción
            self.event_bus.publish(
                EventType.FUEL_PREDICTION.value,
                prediction,
            )

            self.success_count += 1
            return prediction
        except Exception as e:
            logger.error(f"❌ Error en PredictionService: {e}")
            self.error_count += 1

        return None

    def get_predictions(self, truck_id: str) -> List[Dict]:
        """Obtiene predicciones de un truck"""
        return self.predictions.get(truck_id, [])[-10:]


class AlertService(MicroService):
    """Servicio de gestión de alertas"""

    def __init__(self):
        """Inicializa servicio de alertas"""
        super().__init__("AlertService")
        self.active_alerts: Dict[str, List[Dict]] = {}

    def process(self, event: Dict) -> Optional[Dict]:
        """Procesa eventos que generan alertas"""
        try:
            event_type = event.get("event_type")
            truck_id = event.get("truck_id")

            # Convertir eventos a alertas
            alert_mapping = {
                EventType.FUEL_ANOMALY.value: "Anomalía detectada",
                EventType.AGGRESSIVE_DRIVING.value: "Conducción agresiva",
                EventType.SIPHONING_DETECTED.value: "Posible robo",
                EventType.SENSOR_MALFUNCTION.value: "Sensor defectuoso",
            }

            if event_type in alert_mapping:
                alert = {
                    "truck_id": truck_id,
                    "alert_type": event_type,
                    "message": alert_mapping[event_type],
                    "severity": event.get("severity", "warning"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                if truck_id not in self.active_alerts:
                    self.active_alerts[truck_id] = []

                self.active_alerts[truck_id].append(alert)

                logger.warning(f"🚨 Alert: {alert}")
                self.success_count += 1

                return alert
        except Exception as e:
            logger.error(f"❌ Error en AlertService: {e}")
            self.error_count += 1

        return None

    def get_alerts(self, truck_id: str) -> List[Dict]:
        """Obtiene alertas de un truck"""
        return self.active_alerts.get(truck_id, [])


class MaintenanceService(MicroService):
    """Servicio de predicción de mantenimiento"""

    def __init__(self):
        """Inicializa servicio de mantenimiento"""
        super().__init__("MaintenanceService")
        self.maintenance_predictions: Dict[str, Dict] = {}

    def process(self, event: Dict) -> Optional[Dict]:
        """Procesa eventos para predecir mantenimiento"""
        try:
            truck_id = event.get("truck_id")
            consumption_gph = event.get("consumption_gph")

            # Simulación: alto consumo indica posible problema mecánico
            if consumption_gph > 5:
                maintenance = {
                    "truck_id": truck_id,
                    "recommendation": "Oil change recommended",
                    "priority": "medium",
                    "confidence": 0.70,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

                self.maintenance_predictions[truck_id] = maintenance

                # Publicar evento
                self.event_bus.publish(
                    EventType.MAINTENANCE_ALERT.value,
                    maintenance,
                )

                self.success_count += 1
                return maintenance
        except Exception as e:
            logger.error(f"❌ Error en MaintenanceService: {e}")
            self.error_count += 1

        return None

    def get_maintenance_plan(self, truck_id: str) -> Optional[Dict]:
        """Obtiene plan de mantenimiento de un truck"""
        return self.maintenance_predictions.get(truck_id)


class MicroserviceOrchestrator:
    """Orquestador de microservicios"""

    def __init__(self):
        """Inicializa orquestador"""
        self.services: Dict[str, MicroService] = {}

        # Instanciar todos los servicios
        self.services["fuel"] = FuelMetricsService()
        self.services["anomaly"] = AnomalyService()
        self.services["driver"] = DriverBehaviorService()
        self.services["prediction"] = PredictionService()
        self.services["alert"] = AlertService()
        self.services["maintenance"] = MaintenanceService()

        logger.info(f"✅ Orquestador inicializado con {len(self.services)} servicios")

    def get_service_status(self) -> Dict:
        """Obtiene estado de todos los servicios"""
        return {
            service_name: service.get_status()
            for service_name, service in self.services.items()
        }

    def get_service(self, service_name: str) -> Optional[MicroService]:
        """Obtiene un servicio específico"""
        return self.services.get(service_name)


# Instancia global
_orchestrator: Optional[MicroserviceOrchestrator] = None


def get_orchestrator() -> MicroserviceOrchestrator:
    """Obtiene instancia singleton del orquestrador"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MicroserviceOrchestrator()
    return _orchestrator
