"""
Confidence Scoring for Fuel Estimations - Quick Win Implementation
Calcula qué tan confiable es cada estimación basado en calidad de datos

Author: Fuel Copilot Team
Version: 1.0.0
Date: December 23, 2025
"""

from dataclasses import dataclass
from typing import Optional, List
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Niveles de confianza"""
    HIGH = "high"       # >80% - Datos excelentes, estimación muy confiable
    MEDIUM = "medium"   # 50-80% - Datos aceptables, estimación moderada
    LOW = "low"         # 20-50% - Datos cuestionables, usar con precaución
    VERY_LOW = "very_low"  # <20% - Básicamente adivinando


@dataclass
class EstimationConfidence:
    """Resultado del análisis de confianza"""
    score: float  # 0-100
    level: ConfidenceLevel
    factors: dict  # Qué factores contribuyeron
    warnings: list  # Advertencias para el usuario


def calculate_estimation_confidence(
    sensor_pct: Optional[float],
    time_gap_hours: float,
    gps_satellites: Optional[int],
    battery_voltage: Optional[float],
    kalman_variance: float,
    sensor_age_seconds: int,
    ecu_available: bool,
    drift_pct: Optional[float] = None,
    speed: Optional[float] = None,
    rpm: Optional[int] = None
) -> EstimationConfidence:
    """
    Calcula qué tan confiable es la estimación actual
    
    Factores considerados:
    - Disponibilidad de sensor de fuel
    - Freshness de datos (qué tan recientes)
    - Calidad de GPS (número de satélites)
    - Voltaje de batería (indica salud eléctrica)
    - Varianza del Kalman filter (incertidumbre del modelo)
    - Disponibilidad de ECU (datos más precisos)
    - Drift entre Kalman y sensor
    - Disponibilidad de speed/rpm
    
    Args:
        sensor_pct: Nivel de combustible del sensor (%)
        time_gap_hours: Horas desde última actualización
        gps_satellites: Número de satélites GPS
        battery_voltage: Voltaje de batería (V)
        kalman_variance: Varianza del Kalman filter
        sensor_age_seconds: Edad del dato del sensor (segundos)
        ecu_available: Si hay datos de ECU disponibles
        drift_pct: Drift entre Kalman y sensor (%)
        speed: Velocidad actual (mph)
        rpm: RPM actual
    
    Returns:
        EstimationConfidence con score, level, factors, warnings
    """
    score = 100.0
    factors = {}
    warnings = []
    
    # ========================================================================
    # Factor 1: Disponibilidad de sensor de fuel (-30 si no hay)
    # ========================================================================
    if sensor_pct is None:
        score -= 30
        factors['fuel_sensor'] = 'missing'
        warnings.append("Sin lectura de sensor de combustible - usando solo Kalman")
    else:
        factors['fuel_sensor'] = 'present'
    
    # ========================================================================
    # Factor 2: Freshness de datos (-5 por cada hora de gap)
    # ========================================================================
    gap_penalty = min(25, time_gap_hours * 5)
    score -= gap_penalty
    factors['data_freshness'] = f"{time_gap_hours:.1f}h gap ({-gap_penalty:.0f} pts)"
    
    if time_gap_hours > 2:
        warnings.append(f"Datos tienen {time_gap_hours:.1f} horas de antigüedad")
    
    # ========================================================================
    # Factor 3: Calidad de GPS (-15 si pocos satélites)
    # ========================================================================
    if gps_satellites is not None:
        if gps_satellites < 4:
            score -= 15
            factors['gps_quality'] = f'{gps_satellites} sats (poor)'
            warnings.append(f"GPS débil ({gps_satellites} satélites < 4)")
        elif gps_satellites < 6:
            score -= 5
            factors['gps_quality'] = f'{gps_satellites} sats (fair)'
        else:
            score += 5  # Bonus por GPS excelente
            factors['gps_quality'] = f'{gps_satellites} sats (excellent)'
    else:
        score -= 10
        factors['gps_quality'] = 'unknown'
    
    # ========================================================================
    # Factor 4: Voltaje de batería (-10 si bajo, +5 si óptimo)
    # ========================================================================
    if battery_voltage is not None:
        if battery_voltage < 11.5:
            score -= 15
            factors['battery'] = f'{battery_voltage:.1f}V (critical)'
            warnings.append(f"Batería baja ({battery_voltage:.1f}V < 11.5V) - sensores pueden fallar")
        elif battery_voltage < 12.0:
            score -= 5
            factors['battery'] = f'{battery_voltage:.1f}V (low)'
        elif battery_voltage > 14.5:
            score -= 5
            factors['battery'] = f'{battery_voltage:.1f}V (high - charging)'
        else:
            score += 5  # Bonus por voltaje óptimo
            factors['battery'] = f'{battery_voltage:.1f}V (optimal)'
    else:
        factors['battery'] = 'unknown'
    
    # ========================================================================
    # Factor 5: Varianza de Kalman (-15 si muy alta)
    # ========================================================================
    if kalman_variance > 50:
        score -= 15
        factors['kalman_variance'] = f'{kalman_variance:.1f} (high)'
        warnings.append("Alta incertidumbre en estimación Kalman")
    elif kalman_variance > 20:
        score -= 5
        factors['kalman_variance'] = f'{kalman_variance:.1f} (moderate)'
    else:
        factors['kalman_variance'] = f'{kalman_variance:.1f} (low)'
    
    # ========================================================================
    # Factor 6: ECU disponible (+10 bonus)
    # ========================================================================
    if ecu_available:
        score += 10
        factors['ecu'] = 'available'
    else:
        factors['ecu'] = 'unavailable'
    
    # ========================================================================
    # Factor 7: Sensor age (-5 por cada 5 min sobre 15 min)
    # ========================================================================
    if sensor_age_seconds > 900:  # >15 min
        age_penalty = min(15, (sensor_age_seconds - 900) / 300 * 5)
        score -= age_penalty
        factors['sensor_age'] = f"{sensor_age_seconds/60:.0f}min ({-age_penalty:.0f} pts)"
    else:
        factors['sensor_age'] = 'fresh'
    
    # ========================================================================
    # Factor 8: Drift entre Kalman y sensor (-10 si >10%)
    # ========================================================================
    if drift_pct is not None:
        abs_drift = abs(drift_pct)
        if abs_drift > 10:
            score -= 15
            factors['drift'] = f'{abs_drift:.1f}% (high)'
            warnings.append(f"Alto drift entre Kalman y sensor ({abs_drift:.1f}%)")
        elif abs_drift > 5:
            score -= 5
            factors['drift'] = f'{abs_drift:.1f}% (moderate)'
        else:
            factors['drift'] = f'{abs_drift:.1f}% (low)'
    
    # ========================================================================
    # Factor 9: Disponibilidad de speed/rpm (+5 si ambos)
    # ========================================================================
    if speed is not None and rpm is not None:
        score += 5
        factors['motion_sensors'] = 'both available'
    elif speed is not None or rpm is not None:
        factors['motion_sensors'] = 'partial'
    else:
        score -= 5
        factors['motion_sensors'] = 'missing'
        warnings.append("Sin datos de velocidad o RPM")
    
    # ========================================================================
    # Normalizar score
    # ========================================================================
    score = max(0, min(100, score))
    
    # Determinar nivel
    if score >= 80:
        level = ConfidenceLevel.HIGH
    elif score >= 50:
        level = ConfidenceLevel.MEDIUM
    elif score >= 20:
        level = ConfidenceLevel.LOW
    else:
        level = ConfidenceLevel.VERY_LOW
    
    return EstimationConfidence(
        score=round(score, 1),
        level=level,
        factors=factors,
        warnings=warnings
    )


def get_confidence_badge_color(level: ConfidenceLevel) -> str:
    """Retorna color para badge en dashboard"""
    colors = {
        ConfidenceLevel.HIGH: "green",
        ConfidenceLevel.MEDIUM: "yellow",
        ConfidenceLevel.LOW: "orange",
        ConfidenceLevel.VERY_LOW: "red"
    }
    return colors.get(level, "gray")


def get_confidence_description(level: ConfidenceLevel, lang: str = "en") -> str:
    """Retorna descripción human-readable"""
    descriptions = {
        "en": {
            ConfidenceLevel.HIGH: "Highly reliable estimate - trust this data",
            ConfidenceLevel.MEDIUM: "Moderately reliable - generally accurate",
            ConfidenceLevel.LOW: "Low confidence - use with caution",
            ConfidenceLevel.VERY_LOW: "Very uncertain - data quality issues"
        },
        "es": {
            ConfidenceLevel.HIGH: "Estimación muy confiable - confía en estos datos",
            ConfidenceLevel.MEDIUM: "Moderadamente confiable - generalmente precisa",
            ConfidenceLevel.LOW: "Baja confianza - usar con precaución",
            ConfidenceLevel.VERY_LOW: "Muy incierto - problemas de calidad de datos"
        }
    }
    return descriptions.get(lang, descriptions["en"]).get(level, "Unknown")


# Integración en wialon_sync_enhanced.py:
#
# En process_truck(), después de calcular metrics (línea ~2027):
#
#   from confidence_scoring import calculate_estimation_confidence
#
#   confidence = calculate_estimation_confidence(
#       sensor_pct=sensor_pct,
#       time_gap_hours=time_gap_hours,
#       gps_satellites=sats,
#       battery_voltage=pwr_ext,
#       kalman_variance=estimator.P,
#       sensor_age_seconds=int(data_age_min * 60),
#       ecu_available=total_fuel_used is not None,
#       drift_pct=drift_pct,
#       speed=speed,
#       rpm=rpm
#   )
#
#   # Agregar al metrics dict:
#   "confidence_score": confidence.score,
#   "confidence_level": confidence.level.value,
#   "confidence_warnings": "|".join(confidence.warnings),
#
# En el INSERT INTO fuel_metrics, agregar columnas:
#   confidence_score DECIMAL(5,2),
#   confidence_level VARCHAR(20),
#   confidence_warnings TEXT
#
# En el dashboard, mostrar badge con color según nivel:
#   <Badge color={getConfidenceColor(truck.confidence_level)}>
#     {truck.confidence_score}% confidence
#   </Badge>
