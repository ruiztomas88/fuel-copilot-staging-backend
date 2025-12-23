"""
Adaptive Refuel Thresholds - Quick Win Implementation
Aprende thresholds óptimos por camión basado en historial de refuels

Author: Fuel Copilot Team
Version: 1.0.0
Date: December 23, 2025
"""

from collections import defaultdict
from typing import Dict, Optional, Tuple
import numpy as np
import json
from pathlib import Path
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)

# Data persistence path
DATA_DIR = Path(__file__).parent / "data"
THRESHOLDS_FILE = DATA_DIR / "adaptive_refuel_thresholds.json"


@dataclass
class TruckThreshold:
    """Thresholds for a specific truck"""
    
    truck_id: str
    min_pct: float  # Minimum percentage increase to consider refuel
    min_gal: float  # Minimum gallons to consider refuel
    sensor_variance: float  # Noise level of this truck's sensor
    confirmed_refuels: int  # Number of confirmed refuels used for learning
    last_updated: str  # ISO timestamp


class AdaptiveRefuelThresholds:
    """
    Aprende thresholds óptimos de refuel por camión basado en:
    - Historial de refuels confirmados
    - Varianza del sensor de ese camión específico
    - Capacidad del tanque
    
    Uso:
        thresholds = AdaptiveRefuelThresholds()
        # Registrar refuels confirmados
        thresholds.record_confirmed_refuel('VD3579', increase_pct=12.5, increase_gal=25.0)
        
        # Obtener thresholds ajustados
        min_pct, min_gal = thresholds.get_thresholds('VD3579')
        
        # Usar en detect_refuel
        if increase_pct >= min_pct and increase_gal >= min_gal:
            # Refuel detected!
    """
    
    def __init__(
        self, 
        default_min_pct: float = 8.0, 
        default_min_gal: float = 3.0,
        learning_rate: float = 0.2  # Qué tan rápido ajusta (0-1)
    ):
        self.default_min_pct = default_min_pct
        self.default_min_gal = default_min_gal
        self.learning_rate = learning_rate
        
        # Historial de refuels por truck
        self._refuel_history: Dict[str, list] = defaultdict(list)
        
        # Varianza de sensor por truck (ruido típico)
        self._sensor_variance: Dict[str, float] = {}
        
        # Thresholds aprendidos
        self._learned_thresholds: Dict[str, TruckThreshold] = {}
        
        # Load from disk if exists
        self._load_from_disk()
    
    def record_confirmed_refuel(
        self,
        truck_id: str,
        increase_pct: float,
        increase_gal: float,
        confidence: float = 1.0
    ):
        """
        Registra un refuel confirmado (ej: por recibo de gasolina o validación manual)
        
        Args:
            truck_id: ID del camión
            increase_pct: Porcentaje de incremento detectado
            increase_gal: Galones agregados
            confidence: Confianza en la detección (0-1)
        """
        if confidence < 0.5:
            return  # Ignorar detecciones de baja confianza
        
        self._refuel_history[truck_id].append({
            'increase_pct': increase_pct,
            'increase_gal': increase_gal,
            'confidence': confidence
        })
        
        # Mantener solo últimos 50 refuels (evita memoria infinita)
        if len(self._refuel_history[truck_id]) > 50:
            self._refuel_history[truck_id].pop(0)
        
        # Re-calcular thresholds
        self._update_thresholds(truck_id)
        self._save_to_disk()
    
    def update_sensor_variance(self, truck_id: str, variance: float):
        """
        Actualiza la varianza conocida del sensor de un camión
        
        Args:
            truck_id: ID del camión
            variance: Desviación estándar del sensor (% o gallons)
        """
        self._sensor_variance[truck_id] = variance
        self._update_thresholds(truck_id)
    
    def _update_thresholds(self, truck_id: str):
        """Recalcula thresholds basado en historial"""
        history = self._refuel_history.get(truck_id, [])
        
        if len(history) < 3:
            # Muy pocos datos, usar defaults
            return
        
        # Extraer valores
        pcts = [r['increase_pct'] for r in history]
        gals = [r['increase_gal'] for r in history]
        
        # Calcular percentil 10 (los refuels más pequeños)
        # Usamos percentil 10 en lugar de mínimo para ser robusto a outliers
        min_pct_observed = np.percentile(pcts, 10)
        min_gal_observed = np.percentile(gals, 10)
        
        # Aplicar learning rate (mezcla entre default y observado)
        learned_min_pct = (
            self.learning_rate * min_pct_observed +
            (1 - self.learning_rate) * self.default_min_pct
        )
        learned_min_gal = (
            self.learning_rate * min_gal_observed +
            (1 - self.learning_rate) * self.default_min_gal
        )
        
        # Ajustar por varianza del sensor (sensores ruidosos necesitan thresholds más altos)
        variance = self._sensor_variance.get(truck_id, 1.0)
        variance_factor = 1.0 + (variance - 1.0) * 0.5  # 50% de ajuste por varianza
        
        learned_min_pct *= variance_factor
        learned_min_gal *= variance_factor
        
        # Guardar thresholds aprendidos
        from datetime import datetime
        
        self._learned_thresholds[truck_id] = TruckThreshold(
            truck_id=truck_id,
            min_pct=round(learned_min_pct, 2),
            min_gal=round(learned_min_gal, 2),
            sensor_variance=round(variance, 3),
            confirmed_refuels=len(history),
            last_updated=datetime.utcnow().isoformat()
        )
        
        logger.info(
            f"📊 [{truck_id}] Adaptive thresholds updated: "
            f"{learned_min_pct:.1f}% / {learned_min_gal:.1f} gal "
            f"(from {len(history)} refuels, variance={variance:.2f})"
        )
    
    def get_thresholds(self, truck_id: str) -> Tuple[float, float]:
        """
        Obtiene thresholds óptimos para un camión
        
        Args:
            truck_id: ID del camión
        
        Returns:
            (min_pct, min_gal) tupla con thresholds ajustados
        """
        if truck_id in self._learned_thresholds:
            threshold = self._learned_thresholds[truck_id]
            return threshold.min_pct, threshold.min_gal
        
        # No hay thresholds aprendidos, usar defaults
        return self.default_min_pct, self.default_min_gal
    
    def get_all_thresholds(self) -> Dict[str, TruckThreshold]:
        """Retorna todos los thresholds aprendidos"""
        return self._learned_thresholds.copy()
    
    def _save_to_disk(self):
        """Persiste thresholds a disco"""
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            
            data = {
                'thresholds': {
                    tid: asdict(threshold) 
                    for tid, threshold in self._learned_thresholds.items()
                },
                'sensor_variance': self._sensor_variance,
                'refuel_history': {
                    tid: history[-20:]  # Solo últimos 20 por truck
                    for tid, history in self._refuel_history.items()
                }
            }
            
            with open(THRESHOLDS_FILE, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.debug(f"💾 Adaptive thresholds saved to {THRESHOLDS_FILE}")
            
        except Exception as e:
            logger.error(f"Failed to save adaptive thresholds: {e}")
    
    def _load_from_disk(self):
        """Carga thresholds desde disco"""
        try:
            if not THRESHOLDS_FILE.exists():
                return
            
            with open(THRESHOLDS_FILE, 'r') as f:
                data = json.load(f)
            
            # Restaurar thresholds
            for tid, threshold_dict in data.get('thresholds', {}).items():
                self._learned_thresholds[tid] = TruckThreshold(**threshold_dict)
            
            # Restaurar varianzas
            self._sensor_variance = data.get('sensor_variance', {})
            
            # Restaurar historial
            for tid, history in data.get('refuel_history', {}).items():
                self._refuel_history[tid] = history
            
            logger.info(
                f"✅ Loaded adaptive thresholds for {len(self._learned_thresholds)} trucks"
            )
            
        except Exception as e:
            logger.warning(f"Failed to load adaptive thresholds: {e}")


# Singleton para uso global
_adaptive_thresholds = None


def get_adaptive_thresholds() -> AdaptiveRefuelThresholds:
    """Obtiene la instancia singleton de adaptive thresholds"""
    global _adaptive_thresholds
    if _adaptive_thresholds is None:
        _adaptive_thresholds = AdaptiveRefuelThresholds()
    return _adaptive_thresholds


# Integración con detect_refuel:
# 
# En wialon_sync_enhanced.py, reemplazar:
#
#   min_increase_pct = _settings.fuel.min_refuel_jump_pct
#   min_increase_gal = _settings.fuel.min_refuel_gallons
#
# Con:
#
#   from adaptive_refuel_thresholds import get_adaptive_thresholds
#   adaptive = get_adaptive_thresholds()
#   min_increase_pct, min_increase_gal = adaptive.get_thresholds(truck_id)
#
# Y cuando se confirma un refuel (después de guardarlo en DB):
#
#   adaptive.record_confirmed_refuel(
#       truck_id=truck_id,
#       increase_pct=fuel_increase_pct,
#       increase_gal=increase_gal,
#       confidence=0.9  # Alta confianza si pasa todas las validaciones
#   )
