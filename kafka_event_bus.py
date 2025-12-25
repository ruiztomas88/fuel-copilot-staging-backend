"""
Kafka Event Bus - Fase 2C
Arquitectura event-driven para microservicios desacoplados

Topics:
- fuel_events: Cambios en estado de combustible
- driver_events: Eventos de conducción
- anomaly_events: Detección de anomalías
- maintenance_events: Alertas de mantenimiento
- system_events: Eventos del sistema

Features:
- Productor de eventos desde sync
- Consumidores asíncronos para procesamiento
- Persistencia de eventos
- Replay de eventos para debugging
"""

import json
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Tipos de eventos en el sistema"""

    # Combustible
    FUEL_LEVEL_CHANGE = "fuel_level_change"
    REFUEL_DETECTED = "refuel_detected"
    FUEL_ANOMALY = "fuel_anomaly"
    SIPHONING_DETECTED = "siphoning_detected"
    FUEL_PREDICTION = "fuel_prediction"

    # Conductor
    DRIVER_SESSION_START = "driver_session_start"
    DRIVER_SESSION_END = "driver_session_end"
    AGGRESSIVE_DRIVING = "aggressive_driving"
    EFFICIENT_DRIVING = "efficient_driving"
    UNSAFE_PATTERN = "unsafe_pattern"

    # Mantenimiento
    MAINTENANCE_ALERT = "maintenance_alert"
    OIL_CHANGE_DUE = "oil_change_due"
    FILTER_REPLACEMENT = "filter_replacement"
    DTC_ALERT = "dtc_alert"

    # Sensores
    SENSOR_MALFUNCTION = "sensor_malfunction"
    SENSOR_CALIBRATION = "sensor_calibration"
    SENSOR_HEALTH_CHECK = "sensor_health_check"

    # Sistema
    SYNC_COMPLETE = "sync_complete"
    SYSTEM_ERROR = "system_error"
    CONFIGURATION_CHANGE = "configuration_change"


class FuelEvent:
    """Evento de combustible"""

    def __init__(
        self,
        event_type: EventType,
        truck_id: str,
        fuel_level_pct: float,
        consumption_gph: float,
        metadata: Optional[Dict] = None,
    ):
        self.event_type = event_type
        self.truck_id = truck_id
        self.fuel_level_pct = fuel_level_pct
        self.consumption_gph = consumption_gph
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.event_id = f"{truck_id}_{event_type.value}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

    def to_dict(self) -> Dict:
        """Serializa evento a dict"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "truck_id": self.truck_id,
            "fuel_level_pct": self.fuel_level_pct,
            "consumption_gph": self.consumption_gph,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        """Serializa evento a JSON"""
        return json.dumps(self.to_dict())


class DriverEvent:
    """Evento de conducción"""

    def __init__(
        self,
        event_type: EventType,
        driver_id: str,
        truck_id: str,
        score: float,
        metadata: Optional[Dict] = None,
    ):
        self.event_type = event_type
        self.driver_id = driver_id
        self.truck_id = truck_id
        self.score = score
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.event_id = f"{driver_id}_{truck_id}_{event_type.value}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

    def to_dict(self) -> Dict:
        """Serializa evento a dict"""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "driver_id": self.driver_id,
            "truck_id": self.truck_id,
            "score": self.score,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class AnomalyEvent:
    """Evento de anomalía"""

    def __init__(
        self,
        anomaly_type: str,
        truck_id: str,
        severity: str,  # "info", "warning", "critical"
        message: str,
        confidence: float = 0.9,
        metadata: Optional[Dict] = None,
    ):
        self.anomaly_type = anomaly_type
        self.truck_id = truck_id
        self.severity = severity
        self.message = message
        self.confidence = confidence
        self.metadata = metadata or {}
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.event_id = (
            f"{truck_id}_anomaly_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
        )

    def to_dict(self) -> Dict:
        """Serializa evento a dict"""
        return {
            "event_id": self.event_id,
            "event_type": EventType.FUEL_ANOMALY.value,
            "anomaly_type": self.anomaly_type,
            "truck_id": self.truck_id,
            "severity": self.severity,
            "message": self.message,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
        }


class EventBus:
    """Bus de eventos local (mockup de Kafka para staging)"""

    def __init__(self):
        """Inicializa event bus"""
        self.event_log: List[Dict] = []
        self.subscribers: Dict[str, List[Callable]] = {}
        self.topic_counts: Dict[str, int] = {}

        # Inicializar topics
        for event_type in EventType:
            topic = event_type.value
            self.subscribers[topic] = []
            self.topic_counts[topic] = 0

        logger.info("✅ Event Bus inicializado")

    def subscribe(self, topic: str, handler: Callable):
        """Suscribe handler a un topic"""
        if topic not in self.subscribers:
            self.subscribers[topic] = []

        self.subscribers[topic].append(handler)
        logger.debug(f"📡 Handler suscrito a {topic}")

    def publish(self, topic: str, event: Dict):
        """Publica evento a un topic"""
        # Agregar timestamp de publicación si no existe
        if "timestamp" not in event:
            event["timestamp"] = datetime.now(timezone.utc).isoformat()

        # Guardar en log
        self.event_log.append(
            {
                "topic": topic,
                "event": event,
                "published_at": datetime.now(timezone.utc).isoformat(),
            }
        )

        self.topic_counts[topic] = self.topic_counts.get(topic, 0) + 1

        # Ejecutar handlers (síncrono para staging)
        handlers = self.subscribers.get(topic, [])
        for handler in handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(f"❌ Error en handler de {topic}: {e}")

        # Limitar tamaño del log
        if len(self.event_log) > 10000:
            self.event_log = self.event_log[-5000:]

    def publish_fuel_event(
        self,
        truck_id: str,
        event_type: EventType,
        fuel_level_pct: float,
        consumption_gph: float,
        metadata: Optional[Dict] = None,
    ):
        """Publica evento de combustible"""
        event = FuelEvent(
            event_type=event_type,
            truck_id=truck_id,
            fuel_level_pct=fuel_level_pct,
            consumption_gph=consumption_gph,
            metadata=metadata,
        )
        self.publish(event_type.value, event.to_dict())

    def publish_driver_event(
        self,
        driver_id: str,
        truck_id: str,
        event_type: EventType,
        score: float,
        metadata: Optional[Dict] = None,
    ):
        """Publica evento de conducción"""
        event = DriverEvent(
            event_type=event_type,
            driver_id=driver_id,
            truck_id=truck_id,
            score=score,
            metadata=metadata,
        )
        self.publish(event_type.value, event.to_dict())

    def publish_anomaly_event(
        self,
        truck_id: str,
        anomaly_type: str,
        severity: str,
        message: str,
        confidence: float = 0.9,
        metadata: Optional[Dict] = None,
    ):
        """Publica evento de anomalía"""
        event = AnomalyEvent(
            anomaly_type=anomaly_type,
            truck_id=truck_id,
            severity=severity,
            message=message,
            confidence=confidence,
            metadata=metadata,
        )
        self.publish(EventType.FUEL_ANOMALY.value, event.to_dict())

    def get_events_for_topic(self, topic: str, limit: int = 100) -> List[Dict]:
        """Obtiene eventos de un topic"""
        events = [e["event"] for e in self.event_log if e["topic"] == topic]
        return events[-limit:]

    def get_events_for_truck(self, truck_id: str, limit: int = 100) -> List[Dict]:
        """Obtiene eventos de un truck"""
        events = [
            e["event"] for e in self.event_log if e["event"].get("truck_id") == truck_id
        ]
        return events[-limit:]

    def get_statistics(self) -> Dict:
        """Obtiene estadísticas del event bus"""
        return {
            "total_events": len(self.event_log),
            "events_by_topic": self.topic_counts,
            "active_subscribers": {
                topic: len(handlers)
                for topic, handlers in self.subscribers.items()
                if len(handlers) > 0
            },
        }

    def replay_events(
        self,
        truck_id: Optional[str] = None,
        event_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict]:
        """Replay de eventos para debugging"""
        events = self.event_log

        if truck_id:
            events = [e for e in events if e["event"].get("truck_id") == truck_id]

        if event_type:
            events = [e for e in events if e["event"].get("event_type") == event_type]

        return events[-limit:]


# Instancia global
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Obtiene instancia singleton del event bus"""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def initialize_event_bus():
    """Inicializa event bus y subscriptores"""
    bus = get_event_bus()

    # Subscriptor para alertas de anomalía
    def anomaly_alert_handler(event: Dict):
        truck_id = event.get("truck_id")
        anomaly_type = event.get("anomaly_type")
        severity = event.get("severity")
        logger.warning(
            f"🚨 {severity.upper()} Anomalía {anomaly_type} en {truck_id}: {event.get('message')}"
        )

    bus.subscribe(EventType.FUEL_ANOMALY.value, anomaly_alert_handler)

    # Subscriptor para alertas de conducción agresiva
    def aggressive_driving_handler(event: Dict):
        driver_id = event.get("driver_id")
        truck_id = event.get("truck_id")
        logger.warning(f"⚠️ Conducción agresiva: {driver_id} en {truck_id}")

    bus.subscribe(EventType.AGGRESSIVE_DRIVING.value, aggressive_driving_handler)

    # Subscriptor para refueles
    def refuel_handler(event: Dict):
        truck_id = event.get("truck_id")
        fuel_pct = event.get("fuel_level_pct")
        logger.info(f"⛽ Refuel detectado: {truck_id} → {fuel_pct}%")

    bus.subscribe(EventType.REFUEL_DETECTED.value, refuel_handler)

    logger.info("✅ Event Bus suscriptores inicializados")
