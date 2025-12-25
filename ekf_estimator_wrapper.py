"""
Wrapper EKF para integración sin-fricción con sistema existente
Feature #5 - Diciembre 2025

Proporciona interface compatible con FuelEstimator existente
pero usa ExtendedKalmanFuelEstimator internamente para mejor precisión
"""

import logging
from datetime import datetime
from typing import Dict, Optional, Tuple

from ekf_fuel_estimator import EKFEstimate, ExtendedKalmanFuelEstimator, TankShape
from sensor_fusion_engine import FusedEstimate, SensorFusionEngine, SensorType

logger = logging.getLogger(__name__)


class EKFEstimatorWrapper:
    """
    Wrapper que proporciona interface compatible con FuelEstimator
    pero usa ExtendedKalmanFuelEstimator (EKF) internamente.

    Propósito: Drop-in replacement con mejor precisión

    Cambios de API mínimos:
    - update() sigue tomando los mismos parámetros
    - Retorna structure.dict() compatible con código existente
    - Agrega optional() sensor fusion
    """

    def __init__(
        self,
        truck_id: str,
        capacity_liters: float,
        config: Dict,
        tanks_config=None,
        use_ekf: bool = True,
        use_sensor_fusion: bool = True,
    ):
        self.truck_id = truck_id
        self.capacity_liters = capacity_liters
        self.capacity = capacity_liters
        self.config = config
        self.tanks_config = tanks_config

        # Determinar forma del tanque
        tank_type = config.get("tank_shape", "saddle")
        if tank_type == "cylinder":
            tank_shape = TankShape.CYLINDER
        elif tank_type == "saddle":
            tank_shape = TankShape.SADDLE
        else:
            tank_shape = TankShape.CUSTOM

        # EKF
        self.ekf = ExtendedKalmanFuelEstimator(
            truck_id=truck_id,
            tank_capacity_L=capacity_liters,
            tank_shape=tank_shape,
            initial_efficiency=1.0,
            enable_logging=True,
        )

        # Sensor fusion (opcional)
        self.use_sensor_fusion = use_sensor_fusion
        if use_sensor_fusion:
            self.fusion = SensorFusionEngine(
                truck_id=truck_id,
                tank_capacity_gal=capacity_liters / 3.78541,
                tank_capacity_L=capacity_liters,
            )
        else:
            self.fusion = None

        # Estado compatible con FuelEstimator original
        self.level_liters = capacity_liters * 0.5
        self.level_pct = 50.0
        self.consumption_lph = 5.0
        self.drift_pct = 0.0
        self.drift_warning = False
        self.initialized = False
        self.last_update_time = None
        self.last_fuel_lvl_pct = None
        self.recent_refuel = False
        self.ecu_consumption_available = False

        # Conversión L/h <-> gph
        self.LITERS_PER_GALLON = 3.78541

    def update(
        self,
        fuel_lvl_pct: Optional[float] = None,
        speed_mph: float = 0,
        rpm: int = 0,
        engine_load_pct: float = 50,
        altitude_ft: float = 0,
        altitude_prev_ft: float = 0,
        timestamp: float = None,
        ecu_total_fuel_used_L: Optional[float] = None,
        ecu_fuel_rate_gph: Optional[float] = None,
        truck_status: str = "MOVING",
        **kwargs
    ) -> Dict:
        """
        Actualizar estimador con lecturas de sensores

        Parámetros compatible con FuelEstimator original
        """
        if timestamp is None:
            from time import time

            timestamp = time()

        # Calcular dt
        dt_hours = 0
        if self.last_update_time:
            dt_hours = (timestamp - self.last_update_time) / 3600
        self.last_update_time = timestamp

        # Calcular grade (pendiente)
        grade_pct = 0
        if dt_hours > 0 and speed_mph > 5:
            # Calcular pendiente desde cambio de altitud
            # distance_ft = speed_mph * 1.467 * seconds = speed * 1.467 * dt_hours * 3600
            distance_ft = speed_mph * 1.467 * dt_hours * 3600
            altitude_change_ft = altitude_ft - altitude_prev_ft
            if distance_ft > 0:
                grade_pct = (altitude_change_ft / distance_ft) * 100

        # Convertir temperatura si está disponible
        ambient_temp_f = kwargs.get("ambient_temp_f", 70)

        # ============ PREDICCIÓN EKF ============
        self.ekf.predict(
            dt_hours=dt_hours,
            speed_mph=speed_mph,
            rpm=rpm,
            engine_load_pct=engine_load_pct,
            grade_pct=grade_pct,
            ambient_temp_f=ambient_temp_f,
        )

        # ============ ACTUALIZAR CON SENSORES ============

        # 1. Sensor de nivel de combustible
        if fuel_lvl_pct is not None and 0 <= fuel_lvl_pct <= 100:
            self.ekf.update_fuel_sensor(fuel_lvl_pct, timestamp)

            if self.fusion:
                self.fusion.add_reading(SensorType.FUEL_LEVEL, fuel_lvl_pct, timestamp)

        # 2. ECU fuel_used (acumulativo, muy preciso)
        if ecu_total_fuel_used_L is not None:
            self.ekf.update_ecu_fuel_used(ecu_total_fuel_used_L, timestamp)

            if self.fusion:
                self.fusion.add_reading(
                    SensorType.ECU_FUEL_USED,
                    ecu_total_fuel_used_L / self.LITERS_PER_GALLON,  # Convertir a gal
                    timestamp,
                )

            self.ecu_consumption_available = True

        # 3. ECU fuel_rate (instantáneo)
        if ecu_fuel_rate_gph is not None:
            self.ekf.update_fuel_rate(ecu_fuel_rate_gph, timestamp)

            if self.fusion:
                self.fusion.add_reading(
                    SensorType.ECU_FUEL_RATE, ecu_fuel_rate_gph, timestamp
                )

        # ============ OBTENER ESTIMACIÓN EKF ============
        ekf_estimate = self.ekf.get_estimate(timestamp)

        # ============ SENSOR FUSION (si habilitado) ============
        if self.fusion:
            fusion_estimate = self.fusion.fuse(timestamp)
            # Usar estimación fusionada si disponible y confiable
            if fusion_estimate.confidence > 0.6:
                self.level_pct = fusion_estimate.fuel_pct
                self.level_liters = fusion_estimate.fuel_liters
                self.consumption_lph = (
                    fusion_estimate.consumption_gph * self.LITERS_PER_GALLON
                )
        else:
            # Usar directamente EKF
            self.level_pct = ekf_estimate.fuel_pct
            self.level_liters = ekf_estimate.fuel_liters
            self.consumption_lph = ekf_estimate.consumption_gph * self.LITERS_PER_GALLON

        # Marcar como inicializado
        if not self.initialized and fuel_lvl_pct is not None:
            self.initialized = True

        # Calcular drift (diferencia vs expectativa)
        # En EKF es la incertidumbre
        self.drift_pct = ekf_estimate.uncertainty_pct
        self.drift_warning = self.drift_pct > 5

        # Retornar resultado compatible con código existente
        return {
            "truck_id": self.truck_id,
            "level_liters": round(self.level_liters, 2),
            "level_pct": round(self.level_pct, 1),
            "consumption_lph": round(self.consumption_lph, 2),
            "consumption_gph": round(self.consumption_lph / self.LITERS_PER_GALLON, 2),
            "drift_pct": round(self.drift_pct, 1),
            "drift_warning": self.drift_warning,
            "initialized": self.initialized,
            "ecu_available": self.ecu_consumption_available,
            "efficiency_factor": round(ekf_estimate.efficiency_factor, 3),
            "uncertainty_pct": round(ekf_estimate.uncertainty_pct, 1),
            "ekf_estimate": ekf_estimate.to_dict(),
        }

    def get_diagnostics(self) -> Dict:
        """Retorna información de diagnóstico"""
        diag = {
            "ekf": self.ekf.get_diagnostics(),
            "estimator": {
                "level_liters": round(self.level_liters, 2),
                "level_pct": round(self.level_pct, 1),
                "consumption_lph": round(self.consumption_lph, 2),
                "drift_pct": round(self.drift_pct, 1),
                "initialized": self.initialized,
            },
        }

        if self.fusion:
            diag["fusion"] = self.fusion.get_diagnostics()

        return diag
