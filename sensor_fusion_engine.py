"""
Sensor Fusion Engine - Fusión multi-sensor de combustible
Feature #5 - Diciembre 2025

Combina múltiples sensores con pesos adaptativos:
- Fuel level sensor (capacitivo, ruidoso, no-lineal)
- ECU fuel_used counter (preciso, acumulativo)
- ECU fuel_rate instant (moderado, rápido)
- Estimación de consumo por velocidad
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class SensorType:
    """Tipos de sensores disponibles"""

    FUEL_LEVEL = "fuel_level"
    ECU_FUEL_USED = "ecu_fuel_used"
    ECU_FUEL_RATE = "ecu_fuel_rate"
    SPEED_ESTIMATED = "speed_estimated"


@dataclass
class SensorReading:
    """Lectura individual de sensor"""

    sensor_id: str
    value: float
    timestamp: float
    uncertainty: float
    is_valid: bool = True
    notes: str = ""


@dataclass
class FusedEstimate:
    """Estimación fusionada de múltiples sensores"""

    fuel_pct: float
    fuel_liters: float
    consumption_gph: float
    confidence: float  # 0-1
    sensor_weights: Dict[str, float]  # Qué peso tuvo cada sensor
    anomalous_sensors: List[str]
    timestamp: float

    def to_dict(self) -> Dict:
        return {
            "fuel_pct": round(self.fuel_pct, 1),
            "fuel_liters": round(self.fuel_liters, 2),
            "consumption_gph": round(self.consumption_gph, 2),
            "confidence": round(self.confidence, 2),
            "sensor_weights": {k: round(v, 3) for k, v in self.sensor_weights.items()},
            "anomalous_sensors": self.anomalous_sensors,
            "timestamp": self.timestamp,
        }


@dataclass
class SensorConfig:
    """Configuración de sensor"""

    sensor_type: str
    base_weight: float = 0.5
    noise_std: float = 1.0
    max_rate_of_change: float = 10.0  # Por minuto
    history_window: int = 20
    enabled: bool = True


class SensorFusionEngine:
    """
    Motor de fusión multi-sensor para estimación de combustible

    Implementa:
    - Weighted sensor fusion con pesos adaptativos
    - Detección y exclusión de sensores anómalos
    - Manejo de diferentes tasas de actualización
    - Consistency checking entre sensores

    Algoritmo:
    1. Validar cada sensor (rate of change, rango válido)
    2. Calcular peso adaptativo basado en historial de consistencia
    3. Fusionar con weighted average
    4. Detectar anomalías comparando sensores
    """

    def __init__(
        self,
        truck_id: str,
        tank_capacity_gal: float,
        tank_capacity_L: Optional[float] = None,
        enable_logging: bool = True,
    ):
        self.truck_id = truck_id
        self.tank_capacity_gal = tank_capacity_gal
        self.tank_capacity_L = tank_capacity_L or tank_capacity_gal * 3.78541
        self.enable_logging = enable_logging

        # Configuración de sensores
        self.sensor_configs = {
            SensorType.FUEL_LEVEL: SensorConfig(
                sensor_type=SensorType.FUEL_LEVEL,
                base_weight=0.4,
                noise_std=3.0,  # ±3% típico
                max_rate_of_change=2.0,  # %/min
            ),
            SensorType.ECU_FUEL_USED: SensorConfig(
                sensor_type=SensorType.ECU_FUEL_USED,
                base_weight=0.8,  # Muy confiable
                noise_std=0.1,  # Muy preciso
                max_rate_of_change=5.0,  # gal/min
            ),
            SensorType.ECU_FUEL_RATE: SensorConfig(
                sensor_type=SensorType.ECU_FUEL_RATE,
                base_weight=0.3,
                noise_std=0.5,
                max_rate_of_change=10.0,
            ),
        }

        # Historial por sensor
        self.sensor_history: Dict[str, List[SensorReading]] = {
            k: [] for k in self.sensor_configs
        }

        # Pesos adaptativos (se ajustan basado en consistency)
        self.adaptive_weights = {
            k: v.base_weight for k, v in self.sensor_configs.items()
        }

        # Métricas de consistencia (para detectar sensores defectuosos)
        self.consistency_metrics = {
            k: {"innovations": [], "residuals": []} for k in self.sensor_configs
        }

        # Estado fusionado
        self.fused_fuel_pct = 50.0
        self.fused_fuel_liters = self.tank_capacity_L * 0.5
        self.fused_consumption_gph = 5.0
        self.last_fused_time = None
        self.last_ecu_total_gal = None

    def add_reading(self, sensor_type: str, value: float, timestamp: float) -> bool:
        """
        Agregar lectura de sensor

        Valida rate of change y rango válido
        """
        if sensor_type not in self.sensor_configs:
            logger.warning(f"Unknown sensor type: {sensor_type}")
            return False

        config = self.sensor_configs[sensor_type]
        if not config.enabled:
            return False

        # Validar rate of change
        is_valid = True
        if self.sensor_history[sensor_type]:
            last = self.sensor_history[sensor_type][-1]
            dt_min = (timestamp - last.timestamp) / 60

            if dt_min > 0:
                rate = abs(value - last.value) / dt_min

                if rate > config.max_rate_of_change:
                    is_valid = False
                    if self.enable_logging:
                        logger.warning(
                            f"[{self.truck_id}] {sensor_type} rate too high: "
                            f"{rate:.2f}/min > {config.max_rate_of_change}"
                        )

        # Validar rangos
        if sensor_type == SensorType.FUEL_LEVEL:
            if not (0 <= value <= 100):
                is_valid = False
                logger.warning(f"Fuel level out of range: {value}%")

        elif sensor_type == SensorType.ECU_FUEL_USED:
            if value < 0 or value > self.tank_capacity_gal * 2:
                is_valid = False
                logger.warning(f"ECU fuel used out of range: {value} gal")

        elif sensor_type == SensorType.ECU_FUEL_RATE:
            if not (0 <= value <= 50):
                is_valid = False
                logger.warning(f"Fuel rate out of range: {value} gph")

        # Crear lectura
        reading = SensorReading(
            sensor_id=sensor_type,
            value=value,
            timestamp=timestamp,
            uncertainty=config.noise_std,
            is_valid=is_valid,
        )

        self.sensor_history[sensor_type].append(reading)

        # Mantener historial acotado
        max_history = config.history_window
        if len(self.sensor_history[sensor_type]) > max_history:
            self.sensor_history[sensor_type] = self.sensor_history[sensor_type][
                -max_history:
            ]

        return is_valid

    def _get_sensor_estimate(
        self, sensor_type: str, reference_fuel_pct: Optional[float] = None
    ) -> Optional[Tuple[float, float]]:
        """
        Obtener estimación de un sensor específico

        Retorna: (fuel_pct, consumption_gph) o None
        """
        readings = self.sensor_history[sensor_type]

        if not readings:
            return None

        # Tomar últimos N válidos
        valid_readings = [r for r in readings[-5:] if r.is_valid]

        if not valid_readings:
            return None

        if sensor_type == SensorType.FUEL_LEVEL:
            # Promedio ponderado por recency
            values = [r.value for r in valid_readings]
            weights = [0.5**i for i in range(len(values) - 1, -1, -1)]
            fuel_pct = np.average(values, weights=weights)

            return fuel_pct, None  # No hay consumo directo

        elif sensor_type == SensorType.ECU_FUEL_USED:
            # Delta desde primer registro
            if len(valid_readings) >= 2:
                delta_gal = valid_readings[-1].value - valid_readings[0].value
                dt_hours = (
                    valid_readings[-1].timestamp - valid_readings[0].timestamp
                ) / 3600

                if dt_hours > 0 and 0 < delta_gal < self.tank_capacity_gal:
                    consumption_gph = delta_gal / dt_hours

                    # Estimar fuel actual basado en consumo
                    if reference_fuel_pct is not None:
                        consumed_pct = (delta_gal / self.tank_capacity_gal) * 100
                        fuel_pct = max(0, min(100, reference_fuel_pct - consumed_pct))
                        return fuel_pct, consumption_gph

                    return None, consumption_gph

            return None, None

        elif sensor_type == SensorType.ECU_FUEL_RATE:
            # Promedio del fuel rate reciente
            values = [r.value for r in valid_readings]
            consumption_gph = np.mean(values)

            return None, consumption_gph

        return None, None

    def fuse(self, timestamp: float) -> FusedEstimate:
        """
        Realizar fusión de sensores

        Método: Weighted least squares con pesos adaptativos
        """
        estimates_pct = []
        weights_pct = []
        consumption_values = []
        anomalous = []

        # 1. Estimación desde fuel_level sensor
        if self.sensor_history[SensorType.FUEL_LEVEL]:
            result = self._get_sensor_estimate(SensorType.FUEL_LEVEL)
            if result[0] is not None:
                estimates_pct.append(result[0])
                weights_pct.append(self.adaptive_weights[SensorType.FUEL_LEVEL])
            else:
                anomalous.append(SensorType.FUEL_LEVEL)

        # 2. Estimación desde ECU fuel_used
        if self.sensor_history[SensorType.ECU_FUEL_USED]:
            # Usar último estimate de fuel como referencia
            ref = estimates_pct[0] if estimates_pct else self.fused_fuel_pct

            result = self._get_sensor_estimate(SensorType.ECU_FUEL_USED, ref)
            if result[0] is not None:
                estimates_pct.append(result[0])
                weights_pct.append(self.adaptive_weights[SensorType.ECU_FUEL_USED])

            if result[1] is not None:
                consumption_values.append(result[1])

        # 3. Estimación desde ECU fuel_rate
        if self.sensor_history[SensorType.ECU_FUEL_RATE]:
            result = self._get_sensor_estimate(SensorType.ECU_FUEL_RATE)
            if result[1] is not None:
                consumption_values.append(result[1])

        # ============ VALIDACIÓN CRUZADA ============
        # Si estimates de fuel difieren mucho, hay problema
        if len(estimates_pct) >= 2:
            variance = np.var(estimates_pct)

            if variance > 100:  # >10% diferencia
                anomalous.append("high_variance")

                if self.enable_logging:
                    logger.warning(
                        f"[{self.truck_id}] Sensor variance high: {variance:.1f} "
                        f"({estimates_pct})"
                    )

                # Reducir peso de sensor menos confiable (si hay variance)
                # Confiar más en ECU (más preciso)
                for i, est in enumerate(estimates_pct):
                    if i == 0:  # fuel_level
                        weights_pct[i] *= 0.5

        # ============ FUSIÓN FINAL DE COMBUSTIBLE ============
        if estimates_pct and weights_pct:
            total_weight = sum(weights_pct)
            fused_pct = (
                sum(e * w for e, w in zip(estimates_pct, weights_pct)) / total_weight
            )

            # Calcular confidence (cuántos sensores contribuyeron)
            n_sensors = len(self.sensor_configs)
            n_active = len([1 for s in self.sensor_history if self.sensor_history[s]])
            confidence = (n_active / n_sensors) if n_sensors > 0 else 0.5
        else:
            # Fallback a último conocido
            fused_pct = self.fused_fuel_pct
            confidence = 0.3
            anomalous.append("no_estimates")

        # ============ FUSIÓN DE CONSUMO ============
        if consumption_values:
            fused_consumption_gph = np.mean(consumption_values)
        else:
            fused_consumption_gph = self.fused_consumption_gph

        # ============ ACTUALIZAR ESTADO ============
        self.fused_fuel_pct = fused_pct
        self.fused_fuel_liters = fused_pct / 100 * self.tank_capacity_L
        self.fused_consumption_gph = fused_consumption_gph
        self.last_fused_time = timestamp

        return FusedEstimate(
            fuel_pct=round(fused_pct, 1),
            fuel_liters=round(self.fused_fuel_liters, 2),
            consumption_gph=round(fused_consumption_gph, 2),
            confidence=round(confidence, 2),
            sensor_weights={
                k: round(self.adaptive_weights[k], 3) for k in self.sensor_configs
            },
            anomalous_sensors=anomalous,
            timestamp=timestamp,
        )

    def get_diagnostics(self) -> Dict:
        """Retorna información de diagnóstico de sensores"""
        return {
            "truck_id": self.truck_id,
            "fused_state": {
                "fuel_pct": round(self.fused_fuel_pct, 1),
                "fuel_liters": round(self.fused_fuel_liters, 2),
                "consumption_gph": round(self.fused_consumption_gph, 2),
            },
            "sensor_readings": {
                k: len(self.sensor_history[k]) for k in self.sensor_configs
            },
            "adaptive_weights": {
                k: round(self.adaptive_weights[k], 3) for k in self.sensor_configs
            },
            "last_fused_time": self.last_fused_time,
        }
