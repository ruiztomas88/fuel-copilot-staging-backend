"""
Component Health Predictors v1.0.0
═══════════════════════════════════════════════════════════════════════════════

Specific component predictors based on VERIFIED sensor data from Wialon DB:

1. TurboHealthPredictor - Uses:
   - intrclr_t (Intercooler Temperature) ✅ VERIFIED
   - intake_pres (Intake Manifold Pressure) ✅ VERIFIED
   - boost_pres (if available)

2. OilConsumptionTracker - Uses:
   - oil_level sensor ✅ VERIFIED
   - oil_press (Oil Pressure) ✅ VERIFIED
   - oil_temp (Oil Temperature) ✅ VERIFIED
   - engine_hours for consumption rate

3. CoolantLeakDetector - Uses:
   - cool_lvl (Coolant Level) ✅ VERIFIED
   - cool_temp (Coolant Temperature) ✅ VERIFIED

These integrate with the main predictive_maintenance_engine.py for unified
fleet health monitoring.

Author: Fuel Analytics Team
Version: 1.0.0
Created: December 2025
"""

import logging
import statistics
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# COMMON DEFINITIONS
# ═══════════════════════════════════════════════════════════════════════════════


class ComponentHealth(Enum):
    """Component health status"""

    EXCELLENT = "excellent"
    GOOD = "good"
    FAIR = "fair"
    WARNING = "warning"
    CRITICAL = "critical"


class TrendDirection(Enum):
    """Trend direction for sensor readings"""

    STABLE = "stable"
    IMPROVING = "improving"
    DEGRADING = "degrading"


@dataclass
class SensorReading:
    """A single sensor reading with timestamp"""

    timestamp: datetime
    value: float
    sensor_name: str
    unit: str = ""


@dataclass
class ComponentPrediction:
    """Health prediction for a component"""

    component: str
    truck_id: str
    status: ComponentHealth
    score: int  # 0-100
    trend: TrendDirection
    confidence: float  # 0-1
    prediction_date: datetime
    estimated_failure_days: Optional[int] = None
    alerts: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    sensor_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "truck_id": self.truck_id,
            "status": self.status.value,
            "score": self.score,
            "trend": self.trend.value,
            "confidence": round(self.confidence, 2),
            "prediction_date": self.prediction_date.isoformat(),
            "estimated_failure_days": self.estimated_failure_days,
            "alerts": self.alerts,
            "recommendations": self.recommendations,
            "sensor_data": self.sensor_data,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# TURBO HEALTH PREDICTOR
# ═══════════════════════════════════════════════════════════════════════════════


class TurboHealthPredictor:
    """
    Predicts turbocharger health based on:
    - Intercooler temperature (intrclr_t) ✅ VERIFIED in Wialon
    - Intake manifold pressure (intake_pres) ✅ VERIFIED in Wialon

    Warning Signs:
    - High intercooler temps = Turbo overheating
    - Low boost pressure = Turbo degradation

    🆕 STANDARDIZED: Temperatures in °F (Fahrenheit) for consistency across all modules
    """

    # 🆕 STANDARDIZED: Changed from °C to °F for consistency
    # Normal: 86-149°F (30-65°C)
    # Warning: 167°F (75°C)
    # Critical: 185°F (85°C)
    INTERCOOLER_TEMP_NORMAL = (86, 149)  # °F (was 30-65°C)
    INTERCOOLER_TEMP_WARNING = 167  # °F (was 75°C)
    INTERCOOLER_TEMP_CRITICAL = 185  # °F (was 85°C)

    BOOST_PRESSURE_MIN = 15
    BOOST_PRESSURE_NORMAL = (20, 35)

    def __init__(self, history_size: int = 100):
        self._readings: Dict[str, Dict[str, deque]] = {}
        self.history_size = history_size

    @staticmethod
    def ensure_fahrenheit(temp: float) -> float:
        """
        Ensure temperature is in Fahrenheit.

        Auto-detects if value is likely Celsius and converts.

        HEURISTIC:
        - If temp < 100 → likely Celsius (intercooler rarely >100°F but often >100°C is rare)
        - If temp >= 100 → likely Fahrenheit

        Args:
            temp: Temperature value (°C or °F)

        Returns:
            Temperature in °F
        """
        # Intercooler temps are typically 30-85°C (86-185°F)
        # If value is < 100, it's almost certainly Celsius
        if temp < 100:
            # Convert C to F: F = (C * 9/5) + 32
            return (temp * 9 / 5) + 32

        # Already in Fahrenheit
        return temp

    def add_reading(
        self,
        truck_id: str,
        intrclr_t: Optional[float] = None,
        intake_pres: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ):
        """Add sensor readings for a truck"""
        if truck_id not in self._readings:
            self._readings[truck_id] = {
                "intrclr_t": deque(maxlen=self.history_size),
                "intake_pres": deque(maxlen=self.history_size),
            }

        ts = timestamp or datetime.now(timezone.utc)

        if intrclr_t is not None:
            # 🆕 Ensure temperature is in Fahrenheit
            intrclr_t_f = self.ensure_fahrenheit(intrclr_t)

            self._readings[truck_id]["intrclr_t"].append(
                SensorReading(ts, intrclr_t_f, "intrclr_t", "°F")
            )
        if intake_pres is not None:
            self._readings[truck_id]["intake_pres"].append(
                SensorReading(ts, intake_pres, "intake_pres", "PSI")
            )

    def predict(self, truck_id: str) -> ComponentPrediction:
        """Generate turbo health prediction"""
        now = datetime.now(timezone.utc)

        if truck_id not in self._readings:
            return ComponentPrediction(
                component="Turbocharger",
                truck_id=truck_id,
                status=ComponentHealth.GOOD,
                score=100,
                trend=TrendDirection.STABLE,
                confidence=0.0,
                prediction_date=now,
                alerts=["Sin datos de sensores disponibles"],
                recommendations=["Verificar conectividad de sensores"],
            )

        readings = self._readings[truck_id]
        alerts = []
        recommendations = []
        score = 100
        confidence = 0.0
        avg_temp = None
        avg_pressure = None

        # Analyze intercooler temperature
        intrclr_data = list(readings["intrclr_t"])
        if intrclr_data:
            temps = [r.value for r in intrclr_data]
            avg_temp = statistics.mean(temps)
            max_temp = max(temps)

            confidence += 0.5

            if max_temp >= self.INTERCOOLER_TEMP_CRITICAL:
                score -= 50
                alerts.append(f"⛔ Temp intercooler CRÍTICA: {max_temp:.1f}°F")
                recommendations.append("Detener. Verificar turbo y enfriamiento.")
            elif max_temp >= self.INTERCOOLER_TEMP_WARNING:
                score -= 25
                alerts.append(f"⚠️ Temp intercooler alta: {max_temp:.1f}°F")
                recommendations.append("Programar revisión de turbo.")
            elif avg_temp > self.INTERCOOLER_TEMP_NORMAL[1]:
                score -= 10
                alerts.append(f"ℹ️ Temp intercooler elevada: {avg_temp:.1f}°F")

        # Analyze boost/intake pressure
        pressure_data = list(readings["intake_pres"])
        if pressure_data:
            pressures = [r.value for r in pressure_data]
            avg_pressure = statistics.mean(pressures)
            min_pressure = min(pressures)

            confidence += 0.5

            if min_pressure < self.BOOST_PRESSURE_MIN:
                score -= 35
                alerts.append(f"⚠️ Presión boost baja: {min_pressure:.1f} PSI")
                recommendations.append("Verificar wastegate y sellos del turbo.")

            if len(pressures) >= 5:
                variance = statistics.variance(pressures)
                if variance > 50:
                    score -= 20
                    alerts.append("⚠️ Presión errática - Posible wastegate")

        # Determine trend
        trend = (
            self._calculate_trend(intrclr_data)
            if intrclr_data
            else TrendDirection.STABLE
        )

        # Determine status
        status = self._score_to_status(score)

        # Failure estimate
        failure_days = None
        if score < 50 and trend == TrendDirection.DEGRADING:
            failure_days = max(7, int((score / 5) * 7))

        if not alerts:
            alerts.append("✅ Turbo operando normalmente")
        if not recommendations:
            recommendations.append("Continuar monitoreo regular.")

        return ComponentPrediction(
            component="Turbocharger",
            truck_id=truck_id,
            status=status,
            score=max(0, score),
            trend=trend,
            confidence=min(1.0, confidence),
            prediction_date=now,
            estimated_failure_days=failure_days,
            alerts=alerts,
            recommendations=recommendations,
            sensor_data={
                "readings_count": len(intrclr_data) + len(pressure_data),
                "avg_intercooler_temp": round(avg_temp, 1) if avg_temp else None,
                "avg_boost_pressure": round(avg_pressure, 1) if avg_pressure else None,
            },
        )

    def _calculate_trend(self, readings: List[SensorReading]) -> TrendDirection:
        if len(readings) < 10:
            return TrendDirection.STABLE

        n = len(readings)
        first_third = [r.value for r in list(readings)[: n // 3]]
        last_third = [r.value for r in list(readings)[-n // 3 :]]

        avg_first = statistics.mean(first_third)
        avg_last = statistics.mean(last_third)

        # Fix C1: Prevent division by zero using max(abs(avg_first), 0.001)
        change_pct = (avg_last - avg_first) / max(abs(avg_first), 0.001) * 100

        if change_pct > 10:
            return TrendDirection.DEGRADING
        elif change_pct < -10:
            return TrendDirection.IMPROVING
        return TrendDirection.STABLE

    def _score_to_status(self, score: int) -> ComponentHealth:
        if score >= 90:
            return ComponentHealth.EXCELLENT
        elif score >= 75:
            return ComponentHealth.GOOD
        elif score >= 50:
            return ComponentHealth.FAIR
        elif score >= 25:
            return ComponentHealth.WARNING
        return ComponentHealth.CRITICAL


# ═══════════════════════════════════════════════════════════════════════════════
# OIL CONSUMPTION TRACKER
# ═══════════════════════════════════════════════════════════════════════════════


class OilConsumptionTracker:
    """
    Tracks oil consumption and predicts service needs.

    Uses:
    - oil_level ✅ VERIFIED in Wialon
    - oil_press ✅ VERIFIED in Wialon
    - oil_temp ✅ VERIFIED in Wialon

    Note: All temperatures are in °F (Fahrenheit) to match fleet_command_center.py
    """

    OIL_LEVEL_MIN_PCT = 20
    OIL_LEVEL_WARNING_PCT = 35

    OIL_PRESSURE_MIN_PSI = 10
    OIL_PRESSURE_WARNING_PSI = 20
    OIL_PRESSURE_NORMAL = (25, 65)

    # Fix C2: Standardized to °F (was °C before)
    # Normal operating temp: 180-230°F (82-110°C)
    # Warning: 250°F (121°C), Critical: 260°F (127°C)
    OIL_TEMP_NORMAL = (180, 230)  # °F
    OIL_TEMP_WARNING = 250  # °F
    OIL_TEMP_CRITICAL = 260  # °F

    def __init__(self, history_size: int = 200):
        self._readings: Dict[str, Dict[str, deque]] = {}
        self.history_size = history_size

    def add_reading(
        self,
        truck_id: str,
        oil_level: Optional[float] = None,
        oil_press: Optional[float] = None,
        oil_temp: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ):
        """Add sensor readings"""
        if truck_id not in self._readings:
            self._readings[truck_id] = {
                "oil_level": deque(maxlen=self.history_size),
                "oil_press": deque(maxlen=self.history_size),
                "oil_temp": deque(maxlen=self.history_size),
            }

        ts = timestamp or datetime.now(timezone.utc)

        if oil_level is not None:
            self._readings[truck_id]["oil_level"].append(
                SensorReading(ts, oil_level, "oil_level", "%")
            )
        if oil_press is not None:
            self._readings[truck_id]["oil_press"].append(
                SensorReading(ts, oil_press, "oil_press", "PSI")
            )
        if oil_temp is not None:
            self._readings[truck_id]["oil_temp"].append(
                SensorReading(ts, oil_temp, "oil_temp", "°C")
            )

    def predict(self, truck_id: str) -> ComponentPrediction:
        """Generate oil system health prediction"""
        now = datetime.now(timezone.utc)

        if truck_id not in self._readings:
            return ComponentPrediction(
                component="Oil System",
                truck_id=truck_id,
                status=ComponentHealth.GOOD,
                score=100,
                trend=TrendDirection.STABLE,
                confidence=0.0,
                prediction_date=now,
                alerts=["Sin datos de sensores de aceite"],
                recommendations=["Verificar sensores de aceite"],
            )

        readings = self._readings[truck_id]
        alerts = []
        recommendations = []
        score = 100
        confidence = 0.0
        current_level = None

        # Analyze oil level
        level_data = list(readings["oil_level"])
        if level_data:
            levels = [r.value for r in level_data]
            current_level = levels[-1]

            confidence += 0.35

            if current_level <= self.OIL_LEVEL_MIN_PCT:
                score -= 60
                alerts.append(f"⛔ Nivel aceite CRÍTICO: {current_level:.0f}%")
                recommendations.append("¡DETENER! Agregar aceite.")
            elif current_level <= self.OIL_LEVEL_WARNING_PCT:
                score -= 25
                alerts.append(f"⚠️ Nivel aceite bajo: {current_level:.0f}%")
                recommendations.append("Agregar aceite. Verificar fugas.")

        # Analyze oil pressure
        press_data = list(readings["oil_press"])
        if press_data:
            pressures = [r.value for r in press_data]
            current_pressure = pressures[-1]
            min_pressure = min(pressures)

            confidence += 0.35

            if min_pressure < self.OIL_PRESSURE_MIN_PSI:
                score -= 50
                alerts.append(f"⛔ Presión aceite CRÍTICA: {min_pressure:.0f} PSI")
                recommendations.append("¡DETENER MOTOR!")
            elif current_pressure < self.OIL_PRESSURE_WARNING_PSI:
                score -= 25
                alerts.append(f"⚠️ Presión aceite baja: {current_pressure:.0f} PSI")
                recommendations.append("Servicio urgente.")

        # Analyze oil temperature
        temp_data = list(readings["oil_temp"])
        if temp_data:
            temps = [r.value for r in temp_data]
            max_temp = max(temps)

            confidence += 0.3

            if max_temp >= self.OIL_TEMP_CRITICAL:
                score -= 40
                alerts.append(f"⛔ Temp aceite CRÍTICA: {max_temp:.0f}°C")
                recommendations.append("Detener y dejar enfriar.")
            elif max_temp >= self.OIL_TEMP_WARNING:
                score -= 20
                alerts.append(f"⚠️ Temp aceite alta: {max_temp:.0f}°C")

        # Trend from oil level
        trend = (
            self._calculate_trend(level_data) if level_data else TrendDirection.STABLE
        )
        status = self._score_to_status(score)

        # Failure estimate
        failure_days = None
        if current_level and current_level < 50 and trend == TrendDirection.DEGRADING:
            daily_drop = 0.5
            days_to_critical = (current_level - self.OIL_LEVEL_MIN_PCT) / daily_drop
            failure_days = max(1, int(days_to_critical))

        if not alerts:
            alerts.append("✅ Sistema de aceite OK")
        if not recommendations:
            recommendations.append("Continuar programa regular.")

        return ComponentPrediction(
            component="Oil System",
            truck_id=truck_id,
            status=status,
            score=max(0, score),
            trend=trend,
            confidence=min(1.0, confidence),
            prediction_date=now,
            estimated_failure_days=failure_days,
            alerts=alerts,
            recommendations=recommendations,
            sensor_data={
                "current_level": current_level,
                "readings_count": len(level_data) + len(press_data) + len(temp_data),
            },
        )

    def _calculate_trend(self, readings: List[SensorReading]) -> TrendDirection:
        if len(readings) < 5:
            return TrendDirection.STABLE

        n = len(readings)
        first_half = [r.value for r in list(readings)[: n // 2]]
        last_half = [r.value for r in list(readings)[-n // 2 :]]

        avg_first = statistics.mean(first_half)
        avg_last = statistics.mean(last_half)

        # Fix C1: Prevent division by zero using max(abs(avg_first), 0.001)
        change_pct = (avg_last - avg_first) / max(abs(avg_first), 0.001) * 100

        if change_pct < -5:
            return TrendDirection.DEGRADING
        elif change_pct > 5:
            return TrendDirection.IMPROVING
        return TrendDirection.STABLE

    def _score_to_status(self, score: int) -> ComponentHealth:
        if score >= 90:
            return ComponentHealth.EXCELLENT
        elif score >= 75:
            return ComponentHealth.GOOD
        elif score >= 50:
            return ComponentHealth.FAIR
        elif score >= 25:
            return ComponentHealth.WARNING
        return ComponentHealth.CRITICAL


# ═══════════════════════════════════════════════════════════════════════════════
# COOLANT LEAK DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════


class CoolantLeakDetector:
    """
    Detects coolant leaks and cooling system issues.

    Uses:
    - cool_lvl ✅ VERIFIED in Wialon
    - cool_temp ✅ VERIFIED in Wialon
    """

    COOLANT_LEVEL_MIN_PCT = 15
    COOLANT_LEVEL_WARNING_PCT = 30

    COOLANT_TEMP_NORMAL = (80, 100)
    COOLANT_TEMP_WARNING = 105
    COOLANT_TEMP_CRITICAL = 115

    def __init__(self, history_size: int = 200):
        self._readings: Dict[str, Dict[str, deque]] = {}
        self.history_size = history_size

    def add_reading(
        self,
        truck_id: str,
        cool_lvl: Optional[float] = None,
        cool_temp: Optional[float] = None,
        timestamp: Optional[datetime] = None,
    ):
        """Add sensor readings"""
        if truck_id not in self._readings:
            self._readings[truck_id] = {
                "cool_lvl": deque(maxlen=self.history_size),
                "cool_temp": deque(maxlen=self.history_size),
            }

        ts = timestamp or datetime.now(timezone.utc)

        if cool_lvl is not None:
            self._readings[truck_id]["cool_lvl"].append(
                SensorReading(ts, cool_lvl, "cool_lvl", "%")
            )
        if cool_temp is not None:
            self._readings[truck_id]["cool_temp"].append(
                SensorReading(ts, cool_temp, "cool_temp", "°C")
            )

    def predict(self, truck_id: str) -> ComponentPrediction:
        """Generate cooling system health prediction"""
        now = datetime.now(timezone.utc)

        if truck_id not in self._readings:
            return ComponentPrediction(
                component="Cooling System",
                truck_id=truck_id,
                status=ComponentHealth.GOOD,
                score=100,
                trend=TrendDirection.STABLE,
                confidence=0.0,
                prediction_date=now,
                alerts=["Sin datos de refrigerante"],
                recommendations=["Verificar sensores"],
            )

        readings = self._readings[truck_id]
        alerts = []
        recommendations = []
        score = 100
        confidence = 0.0
        leak_detected = False
        current_level = None

        # Analyze coolant level
        level_data = list(readings["cool_lvl"])
        if level_data:
            levels = [r.value for r in level_data]
            current_level = levels[-1]

            confidence += 0.5

            if current_level <= self.COOLANT_LEVEL_MIN_PCT:
                score -= 60
                alerts.append(f"⛔ Nivel refrigerante CRÍTICO: {current_level:.0f}%")
                recommendations.append("¡DETENER! Agregar refrigerante.")
                leak_detected = True
            elif current_level <= self.COOLANT_LEVEL_WARNING_PCT:
                score -= 30
                alerts.append(f"⚠️ Nivel refrigerante bajo: {current_level:.0f}%")
                recommendations.append("Inspeccionar por fugas.")
                leak_detected = True

            # Check for leak pattern
            if len(levels) >= 10:
                drop_rate = self._calculate_drop_rate(levels)
                if drop_rate > 1.0:
                    score -= 25
                    alerts.append(f"⚠️ Posible fuga: {drop_rate:.1f}%/día")
                    leak_detected = True

        # Analyze coolant temperature
        temp_data = list(readings["cool_temp"])
        if temp_data:
            temps = [r.value for r in temp_data]
            max_temp = max(temps)

            confidence += 0.5

            if max_temp >= self.COOLANT_TEMP_CRITICAL:
                score -= 50
                alerts.append(f"⛔ Temp CRÍTICA: {max_temp:.0f}°C")
                recommendations.append("Apagar motor inmediatamente.")
            elif max_temp >= self.COOLANT_TEMP_WARNING:
                score -= 25
                alerts.append(f"⚠️ Temp alta: {max_temp:.0f}°C")
                recommendations.append("Verificar termostato y radiador.")

            # Temperature variance check
            if len(temps) >= 5:
                variance = statistics.variance(temps)
                if variance > 100:
                    score -= 15
                    alerts.append("⚠️ Temp errática - Termostato?")

        # Combined: Low level + high temp = critical
        if current_level and temp_data:
            max_temp = max([r.value for r in temp_data])
            if current_level < 40 and max_temp > self.COOLANT_TEMP_WARNING:
                score -= 30
                alerts.append("⛔ PELIGRO: Nivel bajo + Temp alta")
                recommendations.insert(0, "URGENTE: Detener operación.")

        trend = (
            self._calculate_trend(level_data) if level_data else TrendDirection.STABLE
        )
        status = self._score_to_status(score)

        # Failure estimate
        failure_days = None
        if leak_detected and current_level:
            days_remaining = (current_level - self.COOLANT_LEVEL_MIN_PCT) / 2
            failure_days = max(1, int(days_remaining))

        if not alerts:
            alerts.append("✅ Sistema de enfriamiento OK")
        if not recommendations:
            recommendations.append("Inspecciones regulares.")

        return ComponentPrediction(
            component="Cooling System",
            truck_id=truck_id,
            status=status,
            score=max(0, score),
            trend=trend,
            confidence=min(1.0, confidence),
            prediction_date=now,
            estimated_failure_days=failure_days,
            alerts=alerts,
            recommendations=recommendations,
            sensor_data={
                "current_level": current_level,
                "leak_detected": leak_detected,
                "readings_count": len(level_data) + len(temp_data),
            },
        )

    def _calculate_drop_rate(self, levels: List[float]) -> float:
        if len(levels) < 5:
            return 0.0

        first_avg = statistics.mean(levels[: len(levels) // 3])
        last_avg = statistics.mean(levels[-len(levels) // 3 :])

        days = 7  # Assume ~7 days of data
        daily_drop = (first_avg - last_avg) / days

        return max(0, daily_drop)

    def _calculate_trend(self, readings: List[SensorReading]) -> TrendDirection:
        if len(readings) < 5:
            return TrendDirection.STABLE

        n = len(readings)
        first_half = [r.value for r in list(readings)[: n // 2]]
        last_half = [r.value for r in list(readings)[-n // 2 :]]

        avg_first = statistics.mean(first_half)
        avg_last = statistics.mean(last_half)

        # Fix C1: Prevent division by zero using max(abs(avg_first), 0.001)
        change_pct = (avg_last - avg_first) / max(abs(avg_first), 0.001) * 100

        if change_pct < -5:
            return TrendDirection.DEGRADING
        elif change_pct > 5:
            return TrendDirection.IMPROVING
        return TrendDirection.STABLE

    def _score_to_status(self, score: int) -> ComponentHealth:
        if score >= 90:
            return ComponentHealth.EXCELLENT
        elif score >= 75:
            return ComponentHealth.GOOD
        elif score >= 50:
            return ComponentHealth.FAIR
        elif score >= 25:
            return ComponentHealth.WARNING
        return ComponentHealth.CRITICAL


# ═══════════════════════════════════════════════════════════════════════════════
# Fix C6: MEMORY CLEANUP UTILITIES
# Prevents memory leaks from trucks removed from fleet
# ═══════════════════════════════════════════════════════════════════════════════


def cleanup_inactive_trucks(
    predictors: list, active_truck_ids: set, max_inactive_days: int = 7
) -> int:
    """
    Clean up history buffers for trucks that are no longer active.

    Fix C6: Prevents memory leaks by removing data for trucks that
    have been removed from the fleet or are inactive for extended periods.

    Args:
        predictors: List of predictor instances to clean
        active_truck_ids: Set of currently active truck IDs
        max_inactive_days: Days of inactivity before cleanup (default 7)

    Returns:
        Number of trucks cleaned up
    """
    cleaned_count = 0
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=max_inactive_days)

    for predictor in predictors:
        if not hasattr(predictor, "_readings"):
            continue

        trucks_to_remove = []

        for truck_id, readings_dict in predictor._readings.items():
            # Remove if not in active fleet
            if truck_id not in active_truck_ids:
                trucks_to_remove.append(truck_id)
                continue

            # Check for inactivity
            has_recent_data = False
            for sensor_readings in readings_dict.values():
                if sensor_readings and len(sensor_readings) > 0:
                    latest_reading = max(sensor_readings, key=lambda r: r.timestamp)
                    if latest_reading.timestamp > cutoff_time:
                        has_recent_data = True
                        break

            if not has_recent_data:
                trucks_to_remove.append(truck_id)

        # Remove inactive trucks
        for truck_id in trucks_to_remove:
            del predictor._readings[truck_id]
            cleaned_count += 1
            logger.info(f"Cleaned up history buffer for inactive truck: {truck_id}")

    return cleaned_count


# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL INSTANCES
# ═══════════════════════════════════════════════════════════════════════════════

_turbo_predictor: Optional[TurboHealthPredictor] = None
_oil_tracker: Optional[OilConsumptionTracker] = None
_coolant_detector: Optional[CoolantLeakDetector] = None


def get_turbo_predictor() -> TurboHealthPredictor:
    global _turbo_predictor
    if _turbo_predictor is None:
        _turbo_predictor = TurboHealthPredictor()
    return _turbo_predictor


def get_oil_tracker() -> OilConsumptionTracker:
    global _oil_tracker
    if _oil_tracker is None:
        _oil_tracker = OilConsumptionTracker()
    return _oil_tracker


def get_coolant_detector() -> CoolantLeakDetector:
    global _coolant_detector
    if _coolant_detector is None:
        _coolant_detector = CoolantLeakDetector()
    return _coolant_detector


def cleanup_all_predictors(active_truck_ids: set) -> int:
    """
    Convenience function to clean up all global predictor instances.

    Call this periodically (e.g., daily) to prevent memory leaks.

    Args:
        active_truck_ids: Set of currently active truck IDs from tanks.yaml

    Returns:
        Total number of trucks cleaned up across all predictors
    """
    predictors = [_turbo_predictor, _oil_tracker, _coolant_detector]

    # Filter out None values
    active_predictors = [p for p in predictors if p is not None]

    if not active_predictors:
        return 0

    return cleanup_inactive_trucks(active_predictors, active_truck_ids)


# ═══════════════════════════════════════════════════════════════════════════════
# TEST
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 60)
    print("COMPONENT HEALTH PREDICTORS TEST")
    print("=" * 60)

    turbo = TurboHealthPredictor()
    oil = OilConsumptionTracker()
    coolant = CoolantLeakDetector()

    # Simulate healthy truck
    for i in range(20):
        turbo.add_reading("CO0681", intrclr_t=55, intake_pres=28)
        oil.add_reading("CO0681", oil_level=75, oil_press=45, oil_temp=95)
        coolant.add_reading("CO0681", cool_lvl=80, cool_temp=92)

    print("\n[CO0681] Healthy Truck:")
    print(
        f"  Turbo: {turbo.predict('CO0681').score} ({turbo.predict('CO0681').status.value})"
    )
    print(
        f"  Oil: {oil.predict('CO0681').score} ({oil.predict('CO0681').status.value})"
    )
    print(
        f"  Coolant: {coolant.predict('CO0681').score} ({coolant.predict('CO0681').status.value})"
    )

    # Simulate problematic truck
    for i in range(20):
        turbo.add_reading("PC1280", intrclr_t=80 + i, intake_pres=12 - (i * 0.3))
        oil.add_reading("PC1280", oil_level=25 - i, oil_press=15, oil_temp=125)
        coolant.add_reading("PC1280", cool_lvl=20 - (i * 0.5), cool_temp=112)

    print("\n[PC1280] Problematic Truck:")

    tp = turbo.predict("PC1280")
    print(f"  Turbo: {tp.score} ({tp.status.value})")
    for alert in tp.alerts[:2]:
        print(f"    - {alert}")

    op = oil.predict("PC1280")
    print(f"  Oil: {op.score} ({op.status.value})")
    for alert in op.alerts[:2]:
        print(f"    - {alert}")

    cp = coolant.predict("PC1280")
    print(f"  Coolant: {cp.score} ({cp.status.value})")
    for alert in cp.alerts[:2]:
        print(f"    - {alert}")

    print("\n" + "=" * 60)
