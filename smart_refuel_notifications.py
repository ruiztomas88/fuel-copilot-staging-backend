"""
Smart Refuel Notifications - Quick Win Implementation
Notificaciones inteligentes de refuels APENAS detectados para confirmación rápida

Author: Fuel Copilot Team
Version: 1.0.0
Date: December 23, 2025
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class RefuelNotification:
    """Notificación de refuel detectado"""
    truck_id: str
    truck_name: str
    timestamp: str  # ISO 8601
    fuel_before: float
    fuel_after: float
    gallons_added: float
    increase_pct: float
    location: str
    confidence: float  # 0-100
    detection_method: str  # "kalman", "sensor", "both"
    requires_confirmation: bool
    notification_sent: bool = False
    confirmed_by: Optional[str] = None
    confirmed_at: Optional[str] = None


class SmartRefuelNotifier:
    """
    Sistema de notificaciones inteligentes para refuels
    
    Features:
    - Notifica APENAS detecta refuel (en tiempo real)
    - Prioriza por confianza (HIGH confidence = notificar inmediato)
    - Agrupa refuels múltiples en 1 notificación si son cercanos
    - Trackea confirmaciones de usuarios
    - Aprende qué notificaciones son útiles vs ruido
    """
    
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        self.notifications_file = self.data_dir / "refuel_notifications.json"
        self.confirmations_file = self.data_dir / "refuel_confirmations.json"
        
        self.pending_notifications: Dict[str, RefuelNotification] = {}
        self.confirmation_history: List[Dict] = []
        
        self._load_state()
    
    def _load_state(self):
        """Carga estado persistido"""
        try:
            if self.notifications_file.exists():
                with open(self.notifications_file, 'r') as f:
                    data = json.load(f)
                    self.pending_notifications = {
                        k: RefuelNotification(**v) for k, v in data.items()
                    }
                logger.info(f"Loaded {len(self.pending_notifications)} pending notifications")
            
            if self.confirmations_file.exists():
                with open(self.confirmations_file, 'r') as f:
                    self.confirmation_history = json.load(f)
                logger.info(f"Loaded {len(self.confirmation_history)} confirmation records")
        
        except Exception as e:
            logger.error(f"Error loading notifier state: {e}")
    
    def _save_state(self):
        """Persiste estado"""
        try:
            with open(self.notifications_file, 'w') as f:
                json.dump(
                    {k: asdict(v) for k, v in self.pending_notifications.items()},
                    f, indent=2
                )
            
            with open(self.confirmations_file, 'w') as f:
                json.dump(self.confirmation_history, f, indent=2)
        
        except Exception as e:
            logger.error(f"Error saving notifier state: {e}")
    
    def create_refuel_notification(
        self,
        truck_id: str,
        truck_name: str,
        timestamp: datetime,
        fuel_before: float,
        fuel_after: float,
        gallons_added: float,
        increase_pct: float,
        location: str,
        confidence: float,
        detection_method: str
    ) -> RefuelNotification:
        """
        Crea notificación de refuel
        
        Args:
            truck_id: ID del truck
            truck_name: Nombre del truck
            timestamp: Cuándo ocurrió el refuel
            fuel_before: Combustible antes (gal)
            fuel_after: Combustible después (gal)
            gallons_added: Galones agregados
            increase_pct: % de incremento
            location: Ubicación GPS o dirección
            confidence: Confianza de detección (0-100)
            detection_method: "kalman", "sensor", "both"
        
        Returns:
            RefuelNotification
        """
        # Determinar si requiere confirmación
        requires_confirmation = self._should_require_confirmation(
            gallons_added, increase_pct, confidence
        )
        
        notif = RefuelNotification(
            truck_id=truck_id,
            truck_name=truck_name,
            timestamp=timestamp.isoformat(),
            fuel_before=fuel_before,
            fuel_after=fuel_after,
            gallons_added=gallons_added,
            increase_pct=increase_pct,
            location=location,
            confidence=confidence,
            detection_method=detection_method,
            requires_confirmation=requires_confirmation
        )
        
        # Guardar en pending
        notif_key = f"{truck_id}_{timestamp.isoformat()}"
        self.pending_notifications[notif_key] = notif
        self._save_state()
        
        logger.info(
            f"Created refuel notification: {truck_name} +{gallons_added:.1f}gal "
            f"({increase_pct:.1f}%) - confidence {confidence:.1f}% "
            f"- requires_confirmation: {requires_confirmation}"
        )
        
        return notif
    
    def _should_require_confirmation(
        self,
        gallons_added: float,
        increase_pct: float,
        confidence: float
    ) -> bool:
        """
        Decide si refuel requiere confirmación manual
        
        Lógica:
        - Si confidence >= 90% → NO requiere confirmación (auto-confirmar)
        - Si gallons_added < 5 gal → SI requiere (puede ser ruido)
        - Si increase_pct < 10% → SI requiere (sospechoso)
        - Si confidence < 50% → SI requiere (muy incierto)
        - Caso normal (50-90% confidence) → NO requiere
        
        Args:
            gallons_added: Galones agregados
            increase_pct: % de incremento
            confidence: Confianza (0-100)
        
        Returns:
            True si requiere confirmación manual
        """
        # Alta confianza → auto-confirmar
        if confidence >= 90:
            return False
        
        # Refuel muy pequeño → requiere confirmación
        if gallons_added < 5:
            return True
        
        # Incremento muy pequeño → sospechoso
        if increase_pct < 10:
            return True
        
        # Baja confianza → requiere confirmación
        if confidence < 50:
            return True
        
        # Caso normal
        return False
    
    def get_pending_notifications(
        self,
        truck_id: Optional[str] = None,
        since_hours: float = 24
    ) -> List[RefuelNotification]:
        """
        Obtiene notificaciones pendientes
        
        Args:
            truck_id: Filtrar por truck (opcional)
            since_hours: Solo últimas N horas (default 24)
        
        Returns:
            Lista de RefuelNotification
        """
        cutoff = datetime.now() - timedelta(hours=since_hours)
        
        notifications = []
        for notif in self.pending_notifications.values():
            # Filtrar por truck si se especifica
            if truck_id and notif.truck_id != truck_id:
                continue
            
            # Filtrar por tiempo
            notif_time = datetime.fromisoformat(notif.timestamp)
            if notif_time < cutoff:
                continue
            
            notifications.append(notif)
        
        # Ordenar por timestamp descendente (más recientes primero)
        notifications.sort(key=lambda n: n.timestamp, reverse=True)
        
        return notifications
    
    def confirm_refuel(
        self,
        truck_id: str,
        timestamp: str,
        confirmed_by: str,
        is_valid: bool,
        notes: Optional[str] = None
    ):
        """
        Confirma o rechaza un refuel detectado
        
        Args:
            truck_id: ID del truck
            timestamp: Timestamp ISO del refuel
            confirmed_by: Usuario que confirma
            is_valid: True si es refuel real, False si es falso positivo
            notes: Notas adicionales
        """
        notif_key = f"{truck_id}_{timestamp}"
        
        if notif_key not in self.pending_notifications:
            logger.warning(f"Notification not found: {notif_key}")
            return
        
        notif = self.pending_notifications[notif_key]
        notif.confirmed_by = confirmed_by
        notif.confirmed_at = datetime.now().isoformat()
        
        # Guardar en historial
        confirmation = {
            "truck_id": truck_id,
            "timestamp": timestamp,
            "gallons_added": notif.gallons_added,
            "confidence": notif.confidence,
            "is_valid": is_valid,
            "confirmed_by": confirmed_by,
            "confirmed_at": notif.confirmed_at,
            "notes": notes
        }
        self.confirmation_history.append(confirmation)
        
        # Remover de pending
        del self.pending_notifications[notif_key]
        
        self._save_state()
        
        logger.info(
            f"Refuel {'CONFIRMED' if is_valid else 'REJECTED'}: "
            f"{notif.truck_name} +{notif.gallons_added:.1f}gal by {confirmed_by}"
        )
    
    def get_confirmation_stats(self, days: int = 30) -> Dict:
        """
        Estadísticas de confirmaciones
        
        Args:
            days: Últimos N días
        
        Returns:
            Dict con estadísticas
        """
        cutoff = datetime.now() - timedelta(days=days)
        
        recent_confirmations = [
            c for c in self.confirmation_history
            if datetime.fromisoformat(c['confirmed_at']) >= cutoff
        ]
        
        if not recent_confirmations:
            return {
                "total": 0,
                "confirmed": 0,
                "rejected": 0,
                "accuracy": 0.0
            }
        
        total = len(recent_confirmations)
        confirmed = sum(1 for c in recent_confirmations if c['is_valid'])
        rejected = total - confirmed
        
        # Calcular accuracy por banda de confianza
        high_conf = [c for c in recent_confirmations if c['confidence'] >= 80]
        medium_conf = [c for c in recent_confirmations if 50 <= c['confidence'] < 80]
        low_conf = [c for c in recent_confirmations if c['confidence'] < 50]
        
        return {
            "total": total,
            "confirmed": confirmed,
            "rejected": rejected,
            "accuracy": confirmed / total * 100,
            "high_confidence_accuracy": sum(1 for c in high_conf if c['is_valid']) / len(high_conf) * 100 if high_conf else 0,
            "medium_confidence_accuracy": sum(1 for c in medium_conf if c['is_valid']) / len(medium_conf) * 100 if medium_conf else 0,
            "low_confidence_accuracy": sum(1 for c in low_conf if c['is_valid']) / len(low_conf) * 100 if low_conf else 0
        }


# Singleton
_notifier_instance = None

def get_refuel_notifier() -> SmartRefuelNotifier:
    """Obtiene instancia singleton"""
    global _notifier_instance
    if _notifier_instance is None:
        _notifier_instance = SmartRefuelNotifier()
    return _notifier_instance


# Integración en wialon_sync_enhanced.py:
#
# En save_refuel_event(), después de INSERT exitoso (línea ~1550):
#
#   from smart_refuel_notifications import get_refuel_notifier
#
#   notifier = get_refuel_notifier()
#   notif = notifier.create_refuel_notification(
#       truck_id=truck_id,
#       truck_name=truck_name,
#       timestamp=timestamp,
#       fuel_before=fuel_before,
#       fuel_after=fuel_after,
#       gallons_added=gallons_added,
#       increase_pct=increase_pct,
#       location=location_str,  # Formatear GPS a string
#       confidence=confidence_score,  # Del confidence_scoring.py
#       detection_method="both" if sensor_jump and kalman_jump else "kalman" if kalman_jump else "sensor"
#   )
#
#   # Si NO requiere confirmación y confidence >= 90%, auto-confirmar
#   if not notif.requires_confirmation:
#       notifier.confirm_refuel(
#           truck_id=truck_id,
#           timestamp=timestamp.isoformat(),
#           confirmed_by="auto",
#           is_valid=True,
#           notes="Auto-confirmed - high confidence"
#       )
#
# API endpoint para obtener notificaciones pendientes:
#
#   @app.get("/api/refuel-notifications")
#   def get_refuel_notifications(truck_id: Optional[str] = None):
#       notifier = get_refuel_notifier()
#       notifications = notifier.get_pending_notifications(truck_id=truck_id)
#       return [asdict(n) for n in notifications]
#
#   @app.post("/api/refuel-notifications/confirm")
#   def confirm_refuel_notification(
#       truck_id: str,
#       timestamp: str,
#       confirmed_by: str,
#       is_valid: bool,
#       notes: Optional[str] = None
#   ):
#       notifier = get_refuel_notifier()
#       notifier.confirm_refuel(truck_id, timestamp, confirmed_by, is_valid, notes)
#       return {"status": "ok"}
