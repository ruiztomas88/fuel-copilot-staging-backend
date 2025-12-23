"""
╔═══════════════════════════════════════════════════════════════════════════════╗
║           🧠 REAL-TIME PREDICTIVE MAINTENANCE ENGINE v1.0.0                    ║
║                                                                                ║
║    TRUE Predictive Maintenance - Predicts failures BEFORE they happen         ║
║                                                                                ║
╠═══════════════════════════════════════════════════════════════════════════════╣
║  FEATURES:                                                                     ║
║  ✓ Threshold-based alerts (oil pressure, coolant temp, etc.)                  ║
║  ✓ Trend analysis (gradual degradation detection)                             ║
║  ✓ Cross-sensor correlation (multi-sensor failure patterns)                   ║
║  ✓ Historical baseline comparison                                             ║
║  ✓ Efficiency analysis (idle waste, fuel consumption)                         ║
║                                                                                ║
║  SENSORS USED:                                                                 ║
║  - oil_press, oil_temp (Lubrication system)                                   ║
║  - cool_temp (Cooling system)                                                 ║
║  - trams_t (Transmission)                                                     ║
║  - engine_load, rpm (Engine health)                                           ║
║  - def_level (DEF/AdBlue compliance)                                          ║
║  - intk_t, intake_pressure (Turbo health)                                     ║
║  - fuel_rate, fuel_lvl (Fuel system)                                          ║
║  - voltage (Electrical system)                                                ║
║                                                                                ║
║  Author: Fuel Copilot Team                                                     ║
║  Created: December 2025                                                        ║
╚═══════════════════════════════════════════════════════════════════════════════╝
"""

import logging
import math
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class PredictiveAlert:
    """Alert generated from real-time sensor analysis."""

    truck_id: str
    component: str
    severity: str  # CRITICAL, WARNING, WATCH
    message: str
    predicted_failure_hours: Optional[float]
    confidence: float  # 0-100
    sensor_evidence: List[Dict[str, Any]]  # Which sensors triggered this
    recommended_action: str
    alert_type: str = "threshold"  # threshold, trend, correlation, efficiency

    def to_dict(self) -> Dict[str, Any]:
        return {
            "truck_id": self.truck_id,
            "component": self.component,
            "severity": self.severity,
            "message": self.message,
            "predicted_failure_hours": self.predicted_failure_hours,
            "confidence": self.confidence,
            "sensor_evidence": self.sensor_evidence,
            "recommended_action": self.recommended_action,
            "alert_type": self.alert_type,
        }


@dataclass
class TruckSensorState:
    """Tracks sensor history for trend analysis."""

    truck_id: str
    history: Dict[str, deque] = field(default_factory=dict)
    last_update: Optional[datetime] = None

    def add_reading(
        self, sensor: str, value: float, timestamp: datetime, max_readings: int = 288
    ):
        """Add a sensor reading to history."""
        if sensor not in self.history:
            self.history[sensor] = deque(maxlen=max_readings)
        self.history[sensor].append((timestamp, value))
        self.last_update = timestamp


# ═══════════════════════════════════════════════════════════════════════════════
# REAL-TIME PREDICTIVE ENGINE
# ═══════════════════════════════════════════════════════════════════════════════


class RealTimePredictiveEngine:
    """
    Analyzes live sensor data to predict failures BEFORE they happen.

    This is TRUE predictive maintenance, not reactive alerting.

    Uses:
    1. Threshold-based alerts (immediate danger detection)
    2. Trend analysis (gradual degradation over 24h windows)
    3. Cross-sensor correlation (combined failure patterns)
    4. Efficiency analysis (idle waste, fuel consumption)
    """

    VERSION = "1.0.0"

    # ═══════════════════════════════════════════════════════════════════════════════
    # THRESHOLDS - Based on industry standards for Class 8 trucks
    # ═══════════════════════════════════════════════════════════════════════════════

    THRESHOLDS = {
        # Oil System (PSI for pressure, °F for temp)
        "oil_press_critical_low": 25,  # PSI - STOP IMMEDIATELY
        "oil_press_warning_low": 35,  # PSI - Schedule service
        "oil_press_normal_min": 40,  # PSI - Normal minimum
        "oil_press_critical_high": 90,  # PSI - Sensor issue or blockage
        "oil_temp_warning": 250,  # °F - High temp
        "oil_temp_critical": 270,  # °F - DANGER
        "oil_temp_normal_max": 230,  # °F - Normal maximum
        # Coolant System
        "cool_temp_warning": 220,  # °F - Getting hot
        "cool_temp_critical": 235,  # °F - OVERHEATING
        "cool_temp_normal_max": 210,  # °F - Normal operating range
        "cool_temp_cold": 160,  # °F - Engine not warmed up
        # Transmission
        "trans_temp_warning": 220,  # °F - High temp
        "trans_temp_critical": 250,  # °F - Damage imminent
        "trans_temp_normal_max": 200,  # °F - Normal max
        # Engine Load
        "engine_load_high": 85,  # % - Sustained high load
        "engine_load_critical": 95,  # % - Overload
        # DEF System
        "def_level_critical": 10,  # % - Derate imminent
        "def_level_warning": 20,  # % - Plan refill
        "def_level_low": 25,  # % - Getting low
        # RPM
        "rpm_idle_max": 800,  # RPM - Normal idle
        "rpm_redline": 2100,  # RPM - Max safe RPM
        # Turbo/Intake
        "intake_temp_warning": 140,  # °F - Hot intake air
        "intake_pressure_low": 1.5,  # bar - Turbo underperforming
        # Voltage
        "voltage_critical_low": 11.5,  # V - Battery failing
        "voltage_warning_low": 12.2,  # V - Battery weak
        "voltage_warning_high": 15.0,  # V - Overcharging
        "voltage_critical_high": 15.5,  # V - Regulator failure
    }

    # Trend thresholds (change per reading that indicates degradation)
    TREND_THRESHOLDS = {
        "oil_press_decline_per_reading": -0.3,  # PSI
        "cool_temp_rise_per_reading": 0.5,  # °F
        "trans_temp_rise_per_reading": 0.3,  # °F
        "oil_temp_rise_per_reading": 0.4,  # °F
        "voltage_decline_per_reading": -0.02,  # V
    }

    def __init__(self):
        """Initialize the predictive engine."""
        # Store sensor history per truck (thread-safe)
        self._truck_states: Dict[str, TruckSensorState] = {}
        self._lock = threading.Lock()

        # Configuration
        self.history_window = timedelta(hours=24)
        self.max_readings_per_sensor = 288  # 24h at 5min intervals

    def _get_truck_state(self, truck_id: str) -> TruckSensorState:
        """Get or create truck state (thread-safe)."""
        with self._lock:
            if truck_id not in self._truck_states:
                self._truck_states[truck_id] = TruckSensorState(truck_id=truck_id)
            return self._truck_states[truck_id]

    def _update_sensor_history(
        self,
        truck_id: str,
        sensors: Dict[str, float],
        timestamp: datetime,
    ) -> None:
        """Store sensor readings for trend analysis."""
        state = self._get_truck_state(truck_id)

        for sensor_name, value in sensors.items():
            if value is not None:
                state.add_reading(
                    sensor_name, value, timestamp, self.max_readings_per_sensor
                )

    def _convert_to_fahrenheit(self, value: float) -> float:
        """
        Convert temperature to Fahrenheit if needed.

        Heuristic: if value < 150, it's likely Celsius.
        """
        if value < 150:
            return (value * 9 / 5) + 32
        return value

    def analyze_truck(
        self,
        truck_id: str,
        current_sensors: Dict[str, float],
        timestamp: Optional[datetime] = None,
    ) -> List[PredictiveAlert]:
        """
        Analyze current sensor readings and predict issues.

        Args:
            truck_id: Truck identifier
            current_sensors: Dict of sensor_name -> value
            timestamp: Reading timestamp (default: now)

        Returns:
            List of PredictiveAlert objects
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        alerts = []

        # Update history for trend analysis
        self._update_sensor_history(truck_id, current_sensors, timestamp)

        # 1. CRITICAL THRESHOLD CHECKS (Immediate danger)
        alerts.extend(self._check_critical_thresholds(truck_id, current_sensors))

        # 2. WARNING THRESHOLD CHECKS (Schedule service)
        alerts.extend(self._check_warning_thresholds(truck_id, current_sensors))

        # 3. TREND ANALYSIS (Gradual degradation - TRUE PREDICTIVE)
        alerts.extend(self._analyze_trends(truck_id, current_sensors))

        # 4. CROSS-SENSOR CORRELATION (Combined failures)
        alerts.extend(self._check_correlations(truck_id, current_sensors))

        # 5. EFFICIENCY ANALYSIS
        alerts.extend(self._analyze_efficiency(truck_id, current_sensors))

        return alerts

    def _check_critical_thresholds(
        self,
        truck_id: str,
        sensors: Dict[str, float],
    ) -> List[PredictiveAlert]:
        """Check for immediate danger conditions."""
        alerts = []

        # Oil Pressure - CRITICAL LOW
        oil_press = sensors.get("oil_press")
        if (
            oil_press is not None
            and oil_press < self.THRESHOLDS["oil_press_critical_low"]
        ):
            alerts.append(
                PredictiveAlert(
                    truck_id=truck_id,
                    component="Sistema de Lubricación",
                    severity="CRITICAL",
                    message=f"🚨 PRESIÓN DE ACEITE CRÍTICA: {oil_press:.0f} PSI (mín: {self.THRESHOLDS['oil_press_critical_low']})",
                    predicted_failure_hours=0,  # Imminent
                    confidence=0.95,  # Normalized to 0-1 range
                    sensor_evidence=[
                        {
                            "sensor": "oil_press",
                            "value": oil_press,
                            "threshold": self.THRESHOLDS["oil_press_critical_low"],
                            "unit": "PSI",
                        }
                    ],
                    recommended_action="DETENER INMEDIATAMENTE. Motor puede fundirse en minutos. Verificar nivel de aceite y fugas.",
                    alert_type="threshold",
                )
            )

        # Coolant Temperature - CRITICAL
        cool_temp = sensors.get("cool_temp")
        if cool_temp is not None:
            cool_temp_f = self._convert_to_fahrenheit(cool_temp)

            if cool_temp_f >= self.THRESHOLDS["cool_temp_critical"]:
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Sistema de Enfriamiento",
                        severity="CRITICAL",
                        message=f"🔥 MOTOR SOBRECALENTADO: {cool_temp_f:.0f}°F (máx: {self.THRESHOLDS['cool_temp_critical']})",
                        predicted_failure_hours=0,
                        confidence=0.98,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {
                                "sensor": "cool_temp",
                                "value": cool_temp_f,
                                "threshold": self.THRESHOLDS["cool_temp_critical"],
                                "unit": "°F",
                            }
                        ],
                        recommended_action="DETENER Y DEJAR ENFRIAR. No abrir radiador si está caliente. Verificar nivel de coolant y radiador.",
                        alert_type="threshold",
                    )
                )

        # Transmission Temperature - CRITICAL
        trans_temp = sensors.get("trams_t")
        if trans_temp is not None:
            trans_temp_f = self._convert_to_fahrenheit(trans_temp)

            if trans_temp_f >= self.THRESHOLDS["trans_temp_critical"]:
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Transmisión",
                        severity="CRITICAL",
                        message=f"🔥 TRANSMISIÓN CRÍTICA: {trans_temp_f:.0f}°F (máx: {self.THRESHOLDS['trans_temp_critical']})",
                        predicted_failure_hours=0.5,  # Minutes to failure
                        confidence=0.92,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {
                                "sensor": "trams_t",
                                "value": trans_temp_f,
                                "threshold": self.THRESHOLDS["trans_temp_critical"],
                                "unit": "°F",
                            }
                        ],
                        recommended_action="DETENER. Dejar enfriar. Riesgo de daño permanente ($8k-$15k). Verificar cooler de transmisión.",
                        alert_type="threshold",
                    )
                )

        # DEF Level - CRITICAL
        def_level = sensors.get("def_level")
        if def_level is not None and def_level < self.THRESHOLDS["def_level_critical"]:
            alerts.append(
                PredictiveAlert(
                    truck_id=truck_id,
                    component="Sistema DEF",
                    severity="CRITICAL",
                    message=f"💧 DEF CRÍTICO: {def_level:.0f}% (mín: {self.THRESHOLDS['def_level_critical']})",
                    predicted_failure_hours=2,  # Derate in ~2 hours
                    confidence=1.0,  # Normalized to 0-1 range
                    sensor_evidence=[
                        {
                            "sensor": "def_level",
                            "value": def_level,
                            "threshold": self.THRESHOLDS["def_level_critical"],
                            "unit": "%",
                        }
                    ],
                    recommended_action="LLENAR DEF INMEDIATAMENTE. Motor entrará en derate (<5 MPH) en <50 millas.",
                    alert_type="threshold",
                )
            )

        # Voltage - CRITICAL LOW
        voltage = sensors.get("voltage")
        if voltage is not None and voltage < self.THRESHOLDS["voltage_critical_low"]:
            alerts.append(
                PredictiveAlert(
                    truck_id=truck_id,
                    component="Sistema Eléctrico",
                    severity="CRITICAL",
                    message=f"🔋 VOLTAJE CRÍTICO: {voltage:.1f}V (mín: {self.THRESHOLDS['voltage_critical_low']})",
                    predicted_failure_hours=1,
                    confidence=0.90,  # Normalized to 0-1 range
                    sensor_evidence=[
                        {
                            "sensor": "voltage",
                            "value": voltage,
                            "threshold": self.THRESHOLDS["voltage_critical_low"],
                            "unit": "V",
                        }
                    ],
                    recommended_action="BATERÍA FALLANDO. Riesgo de quedarse tirado. Verificar alternador y batería.",
                    alert_type="threshold",
                )
            )

        return alerts

    def _check_warning_thresholds(
        self,
        truck_id: str,
        sensors: Dict[str, float],
    ) -> List[PredictiveAlert]:
        """Check for conditions that need attention soon."""
        alerts = []

        # Oil Pressure - WARNING (only if not already critical)
        oil_press = sensors.get("oil_press")
        if oil_press is not None:
            if (
                self.THRESHOLDS["oil_press_warning_low"]
                <= oil_press
                < self.THRESHOLDS["oil_press_normal_min"]
            ):
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Sistema de Lubricación",
                        severity="WARNING",
                        message=f"⚠️ Presión de aceite baja: {oil_press:.0f} PSI",
                        predicted_failure_hours=24,
                        confidence=0.75,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {"sensor": "oil_press", "value": oil_press, "unit": "PSI"}
                        ],
                        recommended_action="Programar inspección. Verificar nivel de aceite y filtro.",
                        alert_type="threshold",
                    )
                )

        # Oil Temperature - WARNING
        oil_temp = sensors.get("oil_temp")
        if oil_temp is not None:
            oil_temp_f = self._convert_to_fahrenheit(oil_temp)

            if (
                self.THRESHOLDS["oil_temp_normal_max"]
                < oil_temp_f
                < self.THRESHOLDS["oil_temp_critical"]
            ):
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Sistema de Lubricación",
                        severity="WARNING",
                        message=f"🌡️ Temperatura de aceite alta: {oil_temp_f:.0f}°F",
                        predicted_failure_hours=48,
                        confidence=0.70,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {"sensor": "oil_temp", "value": oil_temp_f, "unit": "°F"}
                        ],
                        recommended_action="Reducir carga. Verificar cooler de aceite. Programar cambio de aceite.",
                        alert_type="threshold",
                    )
                )

        # Coolant Temperature - WARNING
        cool_temp = sensors.get("cool_temp")
        if cool_temp is not None:
            cool_temp_f = self._convert_to_fahrenheit(cool_temp)

            if (
                self.THRESHOLDS["cool_temp_normal_max"]
                < cool_temp_f
                < self.THRESHOLDS["cool_temp_critical"]
            ):
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Sistema de Enfriamiento",
                        severity="WARNING",
                        message=f"🌡️ Temperatura de coolant elevada: {cool_temp_f:.0f}°F",
                        predicted_failure_hours=12,
                        confidence=0.75,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {"sensor": "cool_temp", "value": cool_temp_f, "unit": "°F"}
                        ],
                        recommended_action="Monitorear de cerca. Verificar nivel de coolant, termostato y ventilador.",
                        alert_type="threshold",
                    )
                )

        # Transmission Temperature - WARNING
        trans_temp = sensors.get("trams_t")
        if trans_temp is not None:
            trans_temp_f = self._convert_to_fahrenheit(trans_temp)

            if (
                self.THRESHOLDS["trans_temp_normal_max"]
                < trans_temp_f
                < self.THRESHOLDS["trans_temp_critical"]
            ):
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Transmisión",
                        severity="WARNING",
                        message=f"🌡️ Temperatura de transmisión alta: {trans_temp_f:.0f}°F",
                        predicted_failure_hours=72,
                        confidence=0.68,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {"sensor": "trams_t", "value": trans_temp_f, "unit": "°F"}
                        ],
                        recommended_action="Reducir carga. Programar inspección de cooler de transmisión.",
                        alert_type="threshold",
                    )
                )

        # Engine Load - WARNING
        engine_load = sensors.get("engine_load")
        if (
            engine_load is not None
            and engine_load >= self.THRESHOLDS["engine_load_high"]
        ):
            severity = (
                "WARNING"
                if engine_load < self.THRESHOLDS["engine_load_critical"]
                else "CRITICAL"
            )
            alerts.append(
                PredictiveAlert(
                    truck_id=truck_id,
                    component="Motor",
                    severity=severity,
                    message=f"📊 Carga de motor sostenida alta: {engine_load:.0f}%",
                    predicted_failure_hours=(
                        168 if severity == "WARNING" else 24
                    ),  # 1 week or 1 day
                    confidence=0.60,  # Normalized to 0-1 range
                    sensor_evidence=[
                        {"sensor": "engine_load", "value": engine_load, "unit": "%"}
                    ],
                    recommended_action="Verificar carga transportada. Revisar filtros de aire. Considerar rutas alternativas.",
                    alert_type="threshold",
                )
            )

        # DEF Level - WARNING
        def_level = sensors.get("def_level")
        if def_level is not None:
            if (
                self.THRESHOLDS["def_level_critical"]
                < def_level
                <= self.THRESHOLDS["def_level_warning"]
            ):
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Sistema DEF",
                        severity="WARNING",
                        message=f"💧 DEF bajo: {def_level:.0f}%",
                        predicted_failure_hours=48,
                        confidence=0.95,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {"sensor": "def_level", "value": def_level, "unit": "%"}
                        ],
                        recommended_action="Planificar recarga de DEF en próxima parada.",
                        alert_type="threshold",
                    )
                )

        # Voltage - WARNING
        voltage = sensors.get("voltage")
        if voltage is not None:
            if (
                self.THRESHOLDS["voltage_critical_low"]
                < voltage
                <= self.THRESHOLDS["voltage_warning_low"]
            ):
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Sistema Eléctrico",
                        severity="WARNING",
                        message=f"🔋 Voltaje bajo: {voltage:.1f}V",
                        predicted_failure_hours=24,
                        confidence=0.80,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {"sensor": "voltage", "value": voltage, "unit": "V"}
                        ],
                        recommended_action="Verificar batería y alternador. Posible batería débil.",
                        alert_type="threshold",
                    )
                )
            elif voltage >= self.THRESHOLDS["voltage_warning_high"]:
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Sistema Eléctrico",
                        severity="WARNING",
                        message=f"🔋 Voltaje alto: {voltage:.1f}V (sobrecarga)",
                        predicted_failure_hours=72,
                        confidence=0.75,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {"sensor": "voltage", "value": voltage, "unit": "V"}
                        ],
                        recommended_action="Verificar regulador de voltaje y alternador.",
                        alert_type="threshold",
                    )
                )

        return alerts

    def _analyze_trends(
        self,
        truck_id: str,
        current_sensors: Dict[str, float],
    ) -> List[PredictiveAlert]:
        """
        Analyze sensor trends to predict failures BEFORE they happen.

        THIS IS TRUE PREDICTIVE MAINTENANCE.

        Example: Oil pressure declining 0.5 PSI per reading
        → Predict failure in X hours before threshold is reached
        """
        alerts = []
        state = self._get_truck_state(truck_id)

        # Minimum readings needed for reliable trend
        MIN_READINGS = 10

        # Oil Pressure Trend
        oil_history = state.history.get("oil_press")
        if oil_history and len(oil_history) >= MIN_READINGS:
            values = [v for _, v in oil_history]
            slope = self._calculate_slope(values[-20:])  # Last 20 readings

            # If declining significantly
            if slope < self.TREND_THRESHOLDS["oil_press_decline_per_reading"]:
                current = values[-1]
                # Predict when it will hit critical threshold
                if slope != 0:
                    readings_to_critical = (
                        current - self.THRESHOLDS["oil_press_critical_low"]
                    ) / abs(slope)
                    hours_to_critical = (
                        readings_to_critical * 0.083
                    )  # Assuming 5min intervals

                    if 0 < hours_to_critical < 168:  # Less than 1 week
                        alerts.append(
                            PredictiveAlert(
                                truck_id=truck_id,
                                component="Sistema de Lubricación",
                                severity=(
                                    "WARNING" if hours_to_critical > 24 else "CRITICAL"
                                ),
                                message=f"📉 PREDICTIVO: Presión de aceite en declive ({current:.0f} PSI, tendencia: {slope:.2f} PSI/lectura)",
                                predicted_failure_hours=hours_to_critical,
                                confidence=0.85,  # Normalized to 0-1 range
                                sensor_evidence=[
                                    {
                                        "sensor": "oil_press",
                                        "current": current,
                                        "trend_per_reading": slope,
                                        "predicted_failure_hours": hours_to_critical,
                                    }
                                ],
                                recommended_action=f"MANTENIMIENTO PREDICTIVO: Bomba de aceite degradándose. Falla estimada en ~{hours_to_critical:.0f} horas. Programar reemplazo preventivo.",
                                alert_type="trend",
                            )
                        )

        # Coolant Temperature Trend (rising)
        cool_history = state.history.get("cool_temp")
        if cool_history and len(cool_history) >= MIN_READINGS:
            values = [self._convert_to_fahrenheit(v) for _, v in cool_history]
            slope = self._calculate_slope(values[-20:])

            # If temperature rising consistently
            if slope > self.TREND_THRESHOLDS["cool_temp_rise_per_reading"]:
                current_f = values[-1]

                if slope > 0:
                    readings_to_critical = (
                        self.THRESHOLDS["cool_temp_critical"] - current_f
                    ) / slope
                    hours_to_critical = readings_to_critical * 0.083

                    if 0 < hours_to_critical < 72:
                        alerts.append(
                            PredictiveAlert(
                                truck_id=truck_id,
                                component="Sistema de Enfriamiento",
                                severity="WARNING",
                                message=f"📈 PREDICTIVO: Temperatura de coolant subiendo ({current_f:.0f}°F, +{slope:.2f}°F/lectura)",
                                predicted_failure_hours=hours_to_critical,
                                confidence=0.78,  # Normalized to 0-1 range
                                sensor_evidence=[
                                    {
                                        "sensor": "cool_temp",
                                        "current": current_f,
                                        "trend_per_reading": slope,
                                    }
                                ],
                                recommended_action=f"MANTENIMIENTO PREDICTIVO: Sistema de enfriamiento degradándose. Sobrecalentamiento en ~{hours_to_critical:.0f}h. Verificar termostato, radiador, bomba de agua.",
                                alert_type="trend",
                            )
                        )

        # Transmission Temperature Trend
        trans_history = state.history.get("trams_t")
        if trans_history and len(trans_history) >= MIN_READINGS:
            values = [self._convert_to_fahrenheit(v) for _, v in trans_history]
            slope = self._calculate_slope(values[-20:])

            if slope > self.TREND_THRESHOLDS["trans_temp_rise_per_reading"]:
                current_f = values[-1]

                if slope > 0:
                    readings_to_critical = (
                        self.THRESHOLDS["trans_temp_critical"] - current_f
                    ) / slope
                    hours_to_critical = readings_to_critical * 0.083

                    if 0 < hours_to_critical < 168:
                        alerts.append(
                            PredictiveAlert(
                                truck_id=truck_id,
                                component="Transmisión",
                                severity="WARNING",
                                message=f"📈 PREDICTIVO: Temperatura de transmisión subiendo ({current_f:.0f}°F, +{slope:.2f}°F/lectura)",
                                predicted_failure_hours=hours_to_critical,
                                confidence=0.72,  # Normalized to 0-1 range
                                sensor_evidence=[
                                    {
                                        "sensor": "trams_t",
                                        "current": current_f,
                                        "trend_per_reading": slope,
                                    }
                                ],
                                recommended_action=f"MANTENIMIENTO PREDICTIVO: Transmisión recalentándose. Daño potencial en ~{hours_to_critical:.0f}h. Verificar cooler y fluido.",
                                alert_type="trend",
                            )
                        )

        # Voltage Trend (declining)
        voltage_history = state.history.get("voltage")
        if voltage_history and len(voltage_history) >= MIN_READINGS:
            values = [v for _, v in voltage_history]
            slope = self._calculate_slope(values[-20:])

            if slope < self.TREND_THRESHOLDS["voltage_decline_per_reading"]:
                current = values[-1]

                if slope != 0:
                    readings_to_critical = (
                        current - self.THRESHOLDS["voltage_critical_low"]
                    ) / abs(slope)
                    hours_to_critical = readings_to_critical * 0.083

                    if 0 < hours_to_critical < 72:
                        alerts.append(
                            PredictiveAlert(
                                truck_id=truck_id,
                                component="Sistema Eléctrico",
                                severity="WARNING",
                                message=f"📉 PREDICTIVO: Voltaje en declive ({current:.1f}V, {slope:.3f}V/lectura)",
                                predicted_failure_hours=hours_to_critical,
                                confidence=0.80,  # Normalized to 0-1 range
                                sensor_evidence=[
                                    {
                                        "sensor": "voltage",
                                        "current": current,
                                        "trend_per_reading": slope,
                                    }
                                ],
                                recommended_action=f"MANTENIMIENTO PREDICTIVO: Batería degradándose. Falla estimada en ~{hours_to_critical:.0f}h. Reemplazar batería preventivamente.",
                                alert_type="trend",
                            )
                        )

        return alerts

    def _check_correlations(
        self,
        truck_id: str,
        sensors: Dict[str, float],
    ) -> List[PredictiveAlert]:
        """
        Check for correlated sensor readings that indicate specific failures.

        Examples:
        - High oil temp + Low oil pressure = Oil pump failing
        - High coolant temp + High oil temp = Cooling system failure
        - Low intake pressure + High intake temp = Turbo failure
        """
        alerts = []

        oil_press = sensors.get("oil_press")
        oil_temp = sensors.get("oil_temp")
        cool_temp = sensors.get("cool_temp")
        intk_t = sensors.get("intk_t")
        intake_pressure = sensors.get("intake_pressure")

        # Correlation 1: High oil temp + Low oil pressure = Oil pump failing
        if oil_temp is not None and oil_press is not None:
            oil_temp_f = self._convert_to_fahrenheit(oil_temp)

            if oil_temp_f > 240 and oil_press < 45:
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Bomba de Aceite",
                        severity="CRITICAL",
                        message=f"🚨 CORRELACIÓN CRÍTICA: Aceite caliente ({oil_temp_f:.0f}°F) + Presión baja ({oil_press:.0f} PSI)",
                        predicted_failure_hours=12,
                        confidence=0.92,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {"sensor": "oil_temp", "value": oil_temp_f, "unit": "°F"},
                            {"sensor": "oil_press", "value": oil_press, "unit": "PSI"},
                        ],
                        recommended_action="BOMBA DE ACEITE FALLANDO. Reemplazar inmediatamente. Riesgo de daño catastrófico al motor.",
                        alert_type="correlation",
                    )
                )

        # Correlation 2: High coolant temp + High oil temp = Cooling system failure
        if cool_temp is not None and oil_temp is not None:
            cool_temp_f = self._convert_to_fahrenheit(cool_temp)
            oil_temp_f = self._convert_to_fahrenheit(oil_temp)

            if cool_temp_f > 215 and oil_temp_f > 245:
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Sistema de Enfriamiento",
                        severity="CRITICAL",
                        message=f"🔥 CORRELACIÓN: Coolant ({cool_temp_f:.0f}°F) y aceite ({oil_temp_f:.0f}°F) ambos calientes",
                        predicted_failure_hours=6,
                        confidence=0.88,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {"sensor": "cool_temp", "value": cool_temp_f, "unit": "°F"},
                            {"sensor": "oil_temp", "value": oil_temp_f, "unit": "°F"},
                        ],
                        recommended_action="FALLA DE ENFRIAMIENTO GENERAL. Verificar radiador, termostato, bomba de agua, y ventilador.",
                        alert_type="correlation",
                    )
                )

        # Correlation 3: Low intake pressure + High intake temp = Turbo failing
        if intake_pressure is not None and intk_t is not None:
            intk_t_f = self._convert_to_fahrenheit(intk_t)

            if intake_pressure < 1.8 and intk_t_f > 120:
                alerts.append(
                    PredictiveAlert(
                        truck_id=truck_id,
                        component="Turbocompresor",
                        severity="WARNING",
                        message=f"🌀 CORRELACIÓN: Baja presión de intake ({intake_pressure:.1f} bar) + Alta temp ({intk_t_f:.0f}°F)",
                        predicted_failure_hours=168,  # 1 week
                        confidence=0.75,  # Normalized to 0-1 range
                        sensor_evidence=[
                            {
                                "sensor": "intake_pressure",
                                "value": intake_pressure,
                                "unit": "bar",
                            },
                            {"sensor": "intk_t", "value": intk_t_f, "unit": "°F"},
                        ],
                        recommended_action="TURBO DEGRADÁNDOSE. Reducción de potencia detectada. Programar inspección de turbo e intercooler.",
                        alert_type="correlation",
                    )
                )

        return alerts

    def _analyze_efficiency(
        self,
        truck_id: str,
        sensors: Dict[str, float],
    ) -> List[PredictiveAlert]:
        """
        Analyze efficiency metrics and generate coaching insights.

        🔧 v1.2.1: Removed dependency on idle_hours_ecu (corrupted sensor)
        Now calculates idle from truck_status = 'STOPPED' records
        """
        alerts = []

        # Note: We no longer use idle_hours_ecu sensor because it's corrupted
        # (shows values like 2.6M hours = 303 years!)
        # Instead, idle is calculated in get_loss_analysis() from truck_status='STOPPED'
        # where STOPPED = engine_running AND speed < 2 mph

        # Efficiency alerts are now handled by Loss Analysis
        # This function is kept for future non-idle efficiency metrics

        return alerts

    def _calculate_slope(self, values: List[float]) -> float:
        """
        Calculate linear regression slope for trend analysis.

        Returns slope (change per reading).
        """
        if len(values) < 2:
            return 0.0

        n = len(values)
        x = list(range(n))

        # Linear regression: y = mx + b
        sum_x = sum(x)
        sum_y = sum(values)
        sum_xy = sum(x[i] * values[i] for i in range(n))
        sum_x2 = sum(xi**2 for xi in x)

        # Slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x^2)
        denominator = n * sum_x2 - sum_x**2
        if denominator == 0:
            return 0.0

        slope = (n * sum_xy - sum_x * sum_y) / denominator

        return slope

    def analyze_fleet(
        self,
        fleet_sensors: Dict[str, Dict[str, float]],
        timestamp: Optional[datetime] = None,
    ) -> Dict[str, List[PredictiveAlert]]:
        """
        Analyze all trucks in the fleet.

        Args:
            fleet_sensors: Dict mapping truck_id -> sensor readings
            timestamp: Optional timestamp (default: now)

        Returns:
            Dict mapping truck_id -> list of alerts
        """
        results = {}

        for truck_id, sensors in fleet_sensors.items():
            alerts = self.analyze_truck(truck_id, sensors, timestamp)
            if alerts:
                results[truck_id] = alerts

        return results

    def get_fleet_summary(
        self,
        fleet_sensors: Dict[str, Dict[str, float]],
    ) -> Dict[str, Any]:
        """
        Get a summary of fleet health from real-time analysis.

        Returns summary with:
        - total_trucks_analyzed
        - trucks_with_alerts
        - critical_count, warning_count, watch_count
        - all_alerts (flat list)
        """
        results = self.analyze_fleet(fleet_sensors)

        all_alerts = []
        critical_count = 0
        warning_count = 0
        watch_count = 0

        for truck_id, alerts in results.items():
            for alert in alerts:
                all_alerts.append(alert)
                if alert.severity == "CRITICAL":
                    critical_count += 1
                elif alert.severity == "WARNING":
                    warning_count += 1
                else:
                    watch_count += 1

        # Sort by severity then confidence
        severity_order = {"CRITICAL": 0, "WARNING": 1, "WATCH": 2}
        all_alerts.sort(
            key=lambda a: (severity_order.get(a.severity, 3), -a.confidence)
        )

        return {
            "total_trucks_analyzed": len(fleet_sensors),
            "trucks_with_alerts": len(results),
            "critical_count": critical_count,
            "warning_count": warning_count,
            "watch_count": watch_count,
            "all_alerts": [a.to_dict() for a in all_alerts],
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SINGLETON
# ═══════════════════════════════════════════════════════════════════════════════

_predictive_engine: Optional[RealTimePredictiveEngine] = None


def get_realtime_predictive_engine() -> RealTimePredictiveEngine:
    """Get or create the global predictive engine instance."""
    global _predictive_engine
    if _predictive_engine is None:
        _predictive_engine = RealTimePredictiveEngine()
    return _predictive_engine
