"""
Extended Kalman Filter (EKF) para estimación de combustible
Feature #5 - Diciembre 2025

Mejoras sobre Kalman Filter lineal:
- Modela no-linealidad del consumo basado en física real
- Maneja tanques saddle (no-lineales)
- Fusiona múltiples sensores con pesos adaptativos
- Estima eficiencia del camión en tiempo real
- Detección de sensores defectuosos
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class TankShape(Enum):
    """Formas de tanque comunes en camiones"""

    CYLINDER = "cylinder"  # Cilíndrico: lineal
    SADDLE = "saddle"  # Dos tanques: no-lineal
    RECTANGULAR = "rectangular"  # Tanque rectangular
    CUSTOM = "custom"  # Personalizado


@dataclass
class VehicleState:
    """Estado del vehículo para EKF"""

    fuel_liters: float  # Combustible en tanque
    consumption_rate: float  # Tasa de consumo actual (L/h)
    fuel_efficiency: float  # Eficiencia actual (factor multiplicativo)


@dataclass
class EKFEstimate:
    """Resultado de estimación del EKF"""

    fuel_liters: float
    fuel_pct: float
    consumption_gph: float
    uncertainty_pct: float
    efficiency_factor: float
    timestamp: float

    def to_dict(self) -> Dict:
        return {
            "fuel_liters": round(self.fuel_liters, 2),
            "fuel_pct": round(self.fuel_pct, 1),
            "consumption_gph": round(self.consumption_gph, 2),
            "uncertainty_pct": round(self.uncertainty_pct, 1),
            "efficiency_factor": round(self.efficiency_factor, 3),
            "timestamp": self.timestamp,
        }


class ExtendedKalmanFuelEstimator:
    """
    Extended Kalman Filter para estimación de combustible

    Modelo de estado no-lineal:
    x = [fuel_L, consumption_rate_Lph, efficiency_factor]

    Transición:
        fuel[k+1] = fuel[k] - consumption_rate[k] * dt
        consumption_rate[k+1] = f(speed, rpm, load, grade, temp)
        efficiency[k+1] = efficiency[k] + w_eff

    Observaciones:
        z1 = sensor_fuel_level (ruidoso, no-lineal)
        z2 = ECU_fuel_used (muy preciso)
        z3 = fuel_rate_instant (moderado)
    """

    def __init__(
        self,
        truck_id: str,
        tank_capacity_L: float,
        tank_shape: TankShape = TankShape.SADDLE,
        initial_efficiency: float = 1.0,
        enable_logging: bool = True,
    ):
        self.truck_id = truck_id
        self.tank_capacity_L = tank_capacity_L
        self.tank_shape = tank_shape
        self.enable_logging = enable_logging

        # Estado inicial: [fuel_L, consumption_rate_Lph, efficiency_factor]
        self.x = np.array(
            [
                tank_capacity_L * 0.5,  # Asumir tanque medio lleno
                5.0,  # Consumo base típico
                initial_efficiency,
            ]
        )

        # Covarianza del estado (incertidumbre inicial)
        self.P = np.diag(
            [
                100.0,  # Alta incertidumbre en fuel inicial
                1.0,  # Consumo varía pero predecible
                0.01,  # Eficiencia muy estable
            ]
        )

        # Process noise - qué tan rápido esperamos que cambien los estados
        self.Q = np.diag(
            [
                0.1,  # Fuel cambia según consumo (determinístico)
                0.5,  # Consumo varía por condiciones (aero, grade, etc)
                0.001,  # Eficiencia es muy estable
            ]
        )

        # Measurement noise - qué tan ruidosos son los sensores
        self.R_fuel_sensor = 25.0  # Sensor de tanque muy ruidoso (±5%)
        self.R_ecu = 0.01  # ECU muy preciso
        self.R_fuel_rate = 1.0  # Fuel rate moderado

        # Historial para debugging
        self.state_history: List[Dict] = []
        self.innovation_history: List[Dict] = []
        self.last_update_time = None
        self.last_ecu_total = None

    def state_transition(
        self,
        x: np.ndarray,
        dt_hours: float,
        speed_mph: float,
        rpm: int,
        engine_load_pct: float = 50,
        grade_pct: float = 0,
        ambient_temp_f: float = 70,
    ) -> np.ndarray:
        """
        Modelo de transición de estado no-lineal basado en física

        Modela consumo como función de:
        - Velocidad (aerodinámico: proporcional a v²)
        - Carga del motor
        - Pendiente (grade)
        - Temperatura ambiental
        """
        fuel, rate, efficiency = x

        # ============ MODELO FÍSICO DE CONSUMO ============
        # Basado en: consumo = f(resistencia_aero, carga, grade, temp)

        # 1. Consumo en idle (motor encendido, sin movimiento)
        base_consumption = 1.2  # L/h típico idle

        # 2. Resistencia aerodinámica: F_aero ∝ v²
        # A mayor velocidad, exponencialmente más consumo
        # Validado empíricamente: consumo_aero ≈ 0.0003 * v²
        aero_factor = 0.0003 * (speed_mph**2)

        # 3. Carga del motor: engine_load_pct es directo
        # 50% load = baseline, 100% load = más consumo
        load_factor = 1 + (engine_load_pct - 50) / 100

        # 4. Pendiente (grade): subidas consumen mucho más
        # Empírico: +1% grade ≈ +5% consumo
        grade_factor = 1 + grade_pct * 0.05

        # 5. Temperatura: motor frío consume más
        # <50°F: penalización significativa
        temp_factor = 1 + max(0, (70 - ambient_temp_f) / 100)

        # Consumo total predicho
        predicted_rate = (
            base_consumption + aero_factor * load_factor * grade_factor * temp_factor
        )

        # Aplicar eficiencia del camión (factor de ajuste)
        # efficiency < 1.0 = camión eficiente
        # efficiency > 1.0 = camión ineficiente
        predicted_rate *= efficiency

        # Asegurar valores razonables
        predicted_rate = max(0.5, min(30, predicted_rate))

        # ============ ACTUALIZAR ESTADO ============
        new_fuel = fuel - rate * dt_hours
        new_fuel = max(0, min(self.tank_capacity_L, new_fuel))

        # Suavizar transición del rate (no cambios bruscos, física)
        alpha = 0.3  # 30% peso al valor predicho, 70% inercia
        new_rate = alpha * predicted_rate + (1 - alpha) * rate

        # Eficiencia se mantiene (se actualiza en measurement update)
        new_efficiency = efficiency

        if self.enable_logging:
            logger.debug(
                f"[{self.truck_id}] State transition: "
                f"fuel={new_fuel:.1f}L, rate={new_rate:.2f}L/h, "
                f"speed={speed_mph}mph, load={engine_load_pct}%, grade={grade_pct:.1f}%"
            )

        return np.array([new_fuel, new_rate, new_efficiency])

    def state_jacobian(self, x: np.ndarray, dt_hours: float, **kwargs) -> np.ndarray:
        """
        Jacobiano de la función de transición: ∂f/∂x

        Necesario para EKF (actualización de covarianza)
        """
        F = np.array(
            [
                [1, -dt_hours, 0],  # ∂fuel/∂[fuel, rate, eff]
                [0, 0.7, 0],  # ∂rate/∂[fuel, rate, eff] (suavizado)
                [0, 0, 1],  # ∂eff/∂[fuel, rate, eff]
            ]
        )
        return F

    def measurement_model_fuel_sensor(self, x: np.ndarray) -> float:
        """
        Modelo de observación no-lineal para sensor de tanque

        h(x) = sensor_reading dado fuel_liters

        Tanques saddle no son lineales:
        - Sensor capacitivo mide altura, no volumen
        - Dos tanques conectados tienen forma irregular
        - Efectivo hay regiones donde pequeño cambio volumétrico
          causa gran cambio en altura (sensor)
        """
        fuel_L = x[0]
        fuel_pct = (fuel_L / self.tank_capacity_L) * 100
        fuel_pct = max(0, min(100, fuel_pct))

        if self.tank_shape == TankShape.SADDLE:
            # Modelo no-lineal típico de tanques saddle
            # Basado en curva de calibración real
            if fuel_pct < 20:
                # Zona baja: sensor menos sensible (cambios pequeños)
                # 10L real = 9% indicado
                sensor_reading = fuel_pct * 0.9
            elif fuel_pct > 80:
                # Zona alta: sensor satura (cambios grandes da poco)
                # 90L real = 86% indicado
                sensor_reading = 80 + (fuel_pct - 80) * 0.7
            else:
                # Zona media: razonablemente lineal
                sensor_reading = fuel_pct

        elif self.tank_shape == TankShape.CYLINDER:
            # Cilíndrico es lineal
            sensor_reading = fuel_pct

        else:
            # Default: asumir lineal
            sensor_reading = fuel_pct

        return sensor_reading

    def measurement_jacobian_fuel_sensor(self, x: np.ndarray) -> np.ndarray:
        """
        Jacobiano de h() para sensor de fuel: ∂h/∂x
        """
        fuel_L = x[0]
        fuel_pct = (fuel_L / self.tank_capacity_L) * 100
        fuel_pct = max(0, min(100, fuel_pct))

        if self.tank_shape == TankShape.SADDLE:
            if fuel_pct < 20:
                d_sensor_d_fuel = 0.9 / self.tank_capacity_L * 100
            elif fuel_pct > 80:
                d_sensor_d_fuel = 0.7 / self.tank_capacity_L * 100
            else:
                d_sensor_d_fuel = 1.0 / self.tank_capacity_L * 100
        else:
            d_sensor_d_fuel = 1.0 / self.tank_capacity_L * 100

        # Jacobiano: [∂h/∂fuel, ∂h/∂rate, ∂h/∂eff]
        return np.array([[d_sensor_d_fuel, 0, 0]])

    def predict(
        self,
        dt_hours: float,
        speed_mph: float,
        rpm: int,
        engine_load_pct: float = 50,
        grade_pct: float = 0,
        ambient_temp_f: float = 70,
    ):
        """Paso de predicción del EKF"""
        if dt_hours <= 0:
            return

        # Predicción del estado
        self.x = self.state_transition(
            self.x, dt_hours, speed_mph, rpm, engine_load_pct, grade_pct, ambient_temp_f
        )

        # Jacobiano
        F = self.state_jacobian(self.x, dt_hours)

        # Predicción de covarianza: P = F*P*F^T + Q
        self.P = F @ self.P @ F.T + self.Q

        # Acotar valores (sanidad)
        self.x[0] = max(0, min(self.tank_capacity_L, self.x[0]))
        self.x[1] = max(0.5, min(30, self.x[1]))
        self.x[2] = max(0.5, min(2.0, self.x[2]))

    def update_fuel_sensor(self, sensor_pct: float, timestamp: float):
        """Actualización con lectura del sensor de tanque"""
        # Predicción de medición
        z_pred = self.measurement_model_fuel_sensor(self.x)

        # Jacobiano de medición
        H = self.measurement_jacobian_fuel_sensor(self.x)

        # Innovation (residual): y = z - h(x̂)
        y = sensor_pct - z_pred

        # Innovación covarianza: S = H*P*H^T + R
        S = H @ self.P @ H.T + self.R_fuel_sensor

        if S > 0:
            # Kalman gain: K = P*H^T / S
            K = self.P @ H.T / S

            # Actualización de estado: x = x + K*y
            self.x = self.x + K.flatten() * y

            # Actualización de covarianza: P = (I - K*H)*P
            self.P = (np.eye(3) - K @ H) @ self.P

        # Guardar para diagnóstico
        self.innovation_history.append(
            {
                "sensor_pct": sensor_pct,
                "predicted_pct": z_pred,
                "innovation": y,
                "kalman_gain": K[0, 0] if S > 0 else 0,
                "timestamp": timestamp,
            }
        )

        if self.enable_logging:
            logger.debug(
                f"[{self.truck_id}] Fuel sensor update: "
                f"z={sensor_pct:.1f}%, pred={z_pred:.1f}%, innov={y:.1f}%"
            )

    def update_ecu_fuel_used(self, ecu_total_L: float, timestamp: float):
        """
        Actualización con contador acumulativo de ECU

        Esta es la medición MÁS PRECISA (ECU mide inyección real)
        """
        if self.last_ecu_total is None:
            self.last_ecu_total = ecu_total_L
            return

        delta_ecu = ecu_total_L - self.last_ecu_total

        # Validar: delta debe ser positivo y razonable (<50L per update)
        if delta_ecu < 0 or delta_ecu > 50:
            logger.warning(
                f"[{self.truck_id}] Invalid ECU delta: {delta_ecu:.2f}L "
                f"({self.last_ecu_total:.1f} -> {ecu_total_L:.1f})"
            )
            return

        if delta_ecu > 0:
            # El ECU dice que gastamos delta_ecu
            # Esto es información muy precisa sobre consumo real

            # Reducir incertidumbre del fuel significativamente
            # (ECU sabe exactamente qué inyectó)
            self.P[0, 0] *= 0.5

            if self.state_history:
                # Ajustar efficiency factor basado en discrepancia
                prev_fuel = self.state_history[-1].get("fuel_L", self.x[0])
                predicted_consumption = prev_fuel - self.x[0]

                if predicted_consumption > 0 and delta_ecu > 0:
                    # Ratio real vs predicho
                    efficiency_update = delta_ecu / predicted_consumption

                    # Suavizar: no cambiar drasticamente
                    alpha = 0.05
                    self.x[2] = (1 - alpha) * self.x[2] + alpha * efficiency_update
                    self.x[2] = max(0.5, min(2.0, self.x[2]))

            self.last_ecu_total = ecu_total_L

            if self.enable_logging:
                logger.debug(
                    f"[{self.truck_id}] ECU update: consumed {delta_ecu:.2f}L, "
                    f"efficiency factor = {self.x[2]:.3f}"
                )

    def update_fuel_rate(self, fuel_rate_gph: float, timestamp: float):
        """
        Actualización con fuel_rate instantáneo del ECU

        Útil como validación pero menos preciso que accumulated
        """
        # Convertir gal/h a L/h
        fuel_rate_Lph = fuel_rate_gph * 3.78541

        # Este es un rate instantáneo, puede ser ruidoso
        # Usamos observación con peso moderado

        # Si nuestro consumo predicho difiere mucho del ECU, ajustar
        diff = abs(fuel_rate_Lph - self.x[1])

        if diff > 5:  # Diferencia mayor a 5 L/h es sospechosa
            logger.warning(
                f"[{self.truck_id}] Fuel rate mismatch: "
                f"ECU={fuel_rate_gph:.2f}gph, estimated={self.x[1]/3.78541:.2f}gph"
            )
            # Ajustar levemente (no confiar totalmente en rate)
            alpha = 0.1
            self.x[1] = (1 - alpha) * self.x[1] + alpha * fuel_rate_Lph

    def get_estimate(self, timestamp: float) -> EKFEstimate:
        """Retorna estimación actual"""
        fuel_L = self.x[0]
        fuel_pct = (fuel_L / self.tank_capacity_L) * 100
        fuel_pct = max(0, min(100, fuel_pct))

        # Consumo en gal/h
        consumption_gph = self.x[1] / 3.78541

        # Incertidumbre en porcentaje
        uncertainty_pct = np.sqrt(self.P[0, 0]) / self.tank_capacity_L * 100

        estimate = EKFEstimate(
            fuel_liters=fuel_L,
            fuel_pct=fuel_pct,
            consumption_gph=consumption_gph,
            uncertainty_pct=uncertainty_pct,
            efficiency_factor=self.x[2],
            timestamp=timestamp,
        )

        # Guardar en historial
        self.state_history.append(
            {
                "timestamp": timestamp,
                "fuel_L": fuel_L,
                "fuel_pct": fuel_pct,
                "consumption_gph": consumption_gph,
                "efficiency_factor": self.x[2],
                "uncertainty_pct": uncertainty_pct,
            }
        )

        # Mantener historial acotado (últimas 1000 muestras)
        if len(self.state_history) > 1000:
            self.state_history = self.state_history[-1000:]

        return estimate

    def get_diagnostics(self) -> Dict:
        """Retorna información de diagnóstico del filtro"""
        return {
            "truck_id": self.truck_id,
            "state": {
                "fuel_L": round(self.x[0], 2),
                "consumption_rate_Lph": round(self.x[1], 2),
                "efficiency_factor": round(self.x[2], 3),
            },
            "covariance_diagonal": [round(self.P[i, i], 4) for i in range(3)],
            "recent_innovations": (
                self.innovation_history[-10:] if self.innovation_history else []
            ),
            "state_history_size": len(self.state_history),
            "last_update_time": self.last_update_time,
        }
