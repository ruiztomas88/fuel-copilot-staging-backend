"""
Advanced Driver Behavior Scoring - Fase 2B
Evaluación del comportamiento del conductor basado en patrones de consumo

Métricas:
- Aggressiveness Score (0-100)
- Fuel Efficiency Score (0-100)
- Safety Score (0-100)
- Overall Driver Rating (⭐ 1-5)

Factores considerados:
- Aceleraciones bruscas (RPM jumps)
- Frenadas de emergencia (speed changes)
- Conducción en idle (desperdicio)
- Mantenimiento de velocidad constante (eficiencia)
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class DriverBehaviorMetrics:
    """Métricas de comportamiento del conductor"""

    # Umbrales de comportamiento
    RPM_AGGRESSIVE_JUMP = 1500  # Salto de RPM que indica aceleración agresiva
    SPEED_AGGRESSIVE_CHANGE = 20  # Cambio de velocidad agresivo (mph)
    SPEED_VARIANCE_EFFICIENT = 5  # Varianza baja indica conducción eficiente
    IDLE_THRESHOLD_EXCESSIVE = 30  # % de tiempo en idle considerado excesivo

    CONSUMPTION_MULTIPLIER_AGGRESSIVE = (
        1.3  # Multiplicador de consumo por conducción agresiva
    )
    CONSUMPTION_MULTIPLIER_SAFE = 0.95  # Multiplicador de consumo por conducción segura


class DriverBehaviorScorer:
    """Calificador de comportamiento del conductor"""

    def __init__(self):
        """Inicializa scorer de conducción"""
        self.driver_profiles: Dict[str, Dict] = {}  # Perfiles por driver_id
        self.behavior_history: Dict[str, List[Dict]] = {}  # Histórico de sesiones
        self.alerts: Dict[str, List[Dict]] = {}  # Alertas por driver

        logger.info("✅ Driver Behavior Scorer inicializado")

    def score_driving_session(
        self,
        driver_id: str,
        truck_id: str,
        duration_minutes: int,
        consumption_gph: List[float],
        speed_mph: List[float],
        rpm_data: List[int],
        idle_pct_data: List[float],
        distance_miles: float,
        fuel_used_liters: float,
        baseline_consumption_gph: float = 3.5,
    ) -> Dict:
        """
        Califica una sesión de conducción

        Args:
            driver_id: Identificador del conductor
            truck_id: Identificador del truck
            duration_minutes: Duración de la sesión
            consumption_gph: Histórico de consumo
            speed_mph: Histórico de velocidad
            rpm_data: Histórico de RPM
            idle_pct_data: Porcentaje en idle
            distance_miles: Distancia recorrida
            fuel_used_liters: Combustible usado
            baseline_consumption_gph: Consumo base esperado para comparación

        Returns:
            {
                "driver_id": "D001",
                "truck_id": "JC1282",
                "session_duration_minutes": 45,
                "distance_miles": 28.5,
                "fuel_efficiency_score": 78,
                "aggressiveness_score": 25,
                "safety_score": 82,
                "overall_rating_stars": 4,
                "comments": ["Good fuel efficiency", "Minor speeding"],
                "recommendations": ["Maintain steady speed", "Reduce idle time"]
            }
        """

        # Validar datos
        if not consumption_gph or len(consumption_gph) < 5:
            return {"status": "insufficient_data"}

        # Calcular métricas individuales
        efficiency_score = self._calculate_efficiency_score(
            fuel_used_liters, distance_miles, consumption_gph, baseline_consumption_gph
        )
        aggressiveness_score = self._calculate_aggressiveness_score(
            speed_mph, rpm_data, consumption_gph
        )
        safety_score = self._calculate_safety_score(speed_mph, rpm_data, idle_pct_data)

        # Calcular rating general (promedio ponderado)
        overall_rating = (
            efficiency_score * 0.4  # 40% eficiencia de combustible
            + safety_score * 0.4  # 40% seguridad
            + (100 - aggressiveness_score) * 0.2  # 20% no agresividad
        ) / 100

        rating_stars = max(1, min(5, round(overall_rating * 5)))

        # Generar comentarios y recomendaciones
        comments = self._generate_comments(
            efficiency_score, aggressiveness_score, safety_score, idle_pct_data
        )
        recommendations = self._generate_recommendations(
            efficiency_score, aggressiveness_score, safety_score
        )

        # Detectar alertas
        alerts = self._detect_alerts(
            driver_id, efficiency_score, aggressiveness_score, safety_score
        )

        session_result = {
            "driver_id": driver_id,
            "truck_id": truck_id,
            "session_date": datetime.now(timezone.utc).isoformat(),
            "session_duration_minutes": duration_minutes,
            "distance_miles": distance_miles,
            "fuel_used_liters": fuel_used_liters,
            "average_speed_mph": float(np.mean(speed_mph)) if speed_mph else 0,
            "speed_variance_mph": float(np.var(speed_mph)) if speed_mph else 0,
            "avg_idle_pct": float(np.mean(idle_pct_data)) if idle_pct_data else 0,
            "fuel_efficiency_score": int(efficiency_score),
            "aggressiveness_score": int(aggressiveness_score),
            "safety_score": int(safety_score),
            "overall_rating_stars": rating_stars,
            "overall_score": float(overall_rating),
            "comments": comments,
            "recommendations": recommendations,
            "alerts": alerts,
        }

        # Guardar en histórico
        if driver_id not in self.behavior_history:
            self.behavior_history[driver_id] = []

        self.behavior_history[driver_id].append(session_result)

        # Actualizar perfil conductor
        self._update_driver_profile(driver_id, session_result)

        return session_result

    def get_driver_profile(self, driver_id: str) -> Dict:
        """Obtiene perfil agregado del conductor"""
        if driver_id not in self.driver_profiles:
            return {
                "driver_id": driver_id,
                "status": "no_profile",
                "sessions_count": 0,
            }

        profile = self.driver_profiles[driver_id]
        history = self.behavior_history.get(driver_id, [])

        # Calcular tendencia de últimas sesiones
        recent = history[-10:] if history else []

        return {
            "driver_id": driver_id,
            "total_sessions": len(history),
            "total_distance_miles": profile.get("total_distance_miles", 0),
            "total_fuel_used_liters": profile.get("total_fuel_used_liters", 0),
            "lifetime_efficiency_score": profile.get("avg_efficiency_score", 0),
            "lifetime_aggressiveness_score": profile.get("avg_aggressiveness_score", 0),
            "lifetime_safety_score": profile.get("avg_safety_score", 0),
            "lifetime_rating_stars": profile.get("avg_rating_stars", 0),
            "recent_trend": {
                "avg_efficiency_score": (
                    int(np.mean([s.get("fuel_efficiency_score", 0) for s in recent]))
                    if recent
                    else 0
                ),
                "avg_aggressiveness_score": (
                    int(np.mean([s.get("aggressiveness_score", 0) for s in recent]))
                    if recent
                    else 0
                ),
                "avg_safety_score": (
                    int(np.mean([s.get("safety_score", 0) for s in recent]))
                    if recent
                    else 0
                ),
            },
            "warnings": self._get_active_warnings(driver_id),
        }

    def get_fleet_behavior_summary(self) -> Dict:
        """Obtiene resumen de comportamiento de toda la flota"""
        if not self.driver_profiles:
            return {
                "total_drivers": 0,
                "avg_efficiency_score": 0,
                "avg_safety_score": 0,
                "high_risk_drivers": [],
            }

        profiles = self.driver_profiles.values()

        high_risk = [
            (driver_id, p.get("avg_aggressiveness_score", 0))
            for driver_id, p in self.driver_profiles.items()
            if p.get("avg_aggressiveness_score", 0) > 60
        ]
        high_risk.sort(key=lambda x: x[1], reverse=True)

        return {
            "total_drivers": len(self.driver_profiles),
            "avg_efficiency_score": int(
                np.mean([p.get("avg_efficiency_score", 0) for p in profiles])
            ),
            "avg_safety_score": int(
                np.mean([p.get("avg_safety_score", 0) for p in profiles])
            ),
            "avg_aggressiveness_score": int(
                np.mean([p.get("avg_aggressiveness_score", 0) for p in profiles])
            ),
            "high_risk_drivers": [
                {"driver_id": d_id, "aggressiveness_score": score}
                for d_id, score in high_risk[:5]
            ],
            "total_alerts": sum(
                len(self.alerts.get(d_id, [])) for d_id in self.driver_profiles.keys()
            ),
        }

    # ============ MÉTODOS PRIVADOS ============

    def _calculate_efficiency_score(
        self,
        fuel_used_liters: float,
        distance_miles: float,
        consumption_gph: List[float],
        baseline_gph: float,
    ) -> float:
        """Calcula puntuación de eficiencia de combustible (0-100)"""
        if distance_miles == 0:
            return 50

        # Calcular MPG actual
        actual_mpg = (
            distance_miles / (fuel_used_liters / 3.785) if fuel_used_liters > 0 else 0
        )

        # Estimar MPG base
        baseline_mpg = 6.0  # MPG típico para camión pesado

        # Normalizar: 100 si mejor que baseline, 0 si 50% peor
        efficiency_ratio = actual_mpg / baseline_mpg if baseline_mpg > 0 else 1
        score = max(0, min(100, efficiency_ratio * 100))

        return score

    def _calculate_aggressiveness_score(
        self,
        speed_mph: List[float],
        rpm_data: List[int],
        consumption_gph: List[float],
    ) -> float:
        """Calcula puntuación de agresividad (0-100, mayor = más agresivo)"""
        aggressiveness = 30  # Base

        # Análisis de cambios de velocidad
        if len(speed_mph) > 2:
            speed_changes = np.abs(np.diff(speed_mph))
            large_changes = np.sum(
                speed_changes > DriverBehaviorMetrics.SPEED_AGGRESSIVE_CHANGE
            )
            aggressiveness += min(30, large_changes * 2)

        # Análisis de RPM
        if len(rpm_data) > 2:
            rpm_changes = np.abs(np.diff(rpm_data))
            aggressive_rpm = np.sum(
                rpm_changes > DriverBehaviorMetrics.RPM_AGGRESSIVE_JUMP
            )
            aggressiveness += min(20, aggressive_rpm * 2)

        # Análisis de consumo erático
        if len(consumption_gph) > 2:
            consumption_var = np.var(consumption_gph)
            aggressiveness += min(20, consumption_var * 5)

        return min(100, aggressiveness)

    def _calculate_safety_score(
        self,
        speed_mph: List[float],
        rpm_data: List[int],
        idle_pct_data: List[float],
    ) -> float:
        """Calcula puntuación de seguridad (0-100)"""
        safety = 100

        # Penalidad por varianza alta en velocidad (frenadas de emergencia)
        if len(speed_mph) > 2:
            speed_var = np.var(speed_mph)
            safety -= min(30, speed_var * 2)

        # Penalidad por cambios bruscos de RPM
        if len(rpm_data) > 2:
            rpm_changes = np.abs(np.diff(rpm_data))
            safety -= min(20, np.mean(rpm_changes > 1500) * 40)

        # Bonificación por tiempo en idle moderado
        avg_idle = np.mean(idle_pct_data) if idle_pct_data else 0
        if avg_idle < 10:
            safety = min(100, safety + 5)
        elif avg_idle > 40:
            safety -= min(20, (avg_idle - 40) * 0.5)

        return max(0, safety)

    def _generate_comments(
        self,
        efficiency: float,
        aggressiveness: float,
        safety: float,
        idle_pct_data: List[float],
    ) -> List[str]:
        """Genera comentarios sobre la sesión"""
        comments = []

        if efficiency > 80:
            comments.append("✅ Excelente eficiencia de combustible")
        elif efficiency > 60:
            comments.append("👍 Buena eficiencia de combustible")
        else:
            comments.append("⚠️ Baja eficiencia - oportunidad de mejora")

        if aggressiveness < 30:
            comments.append("✅ Conducción suave y controlada")
        elif aggressiveness > 60:
            comments.append("⚠️ Conducción agresiva detectada")

        if safety > 85:
            comments.append("✅ Conducción segura")
        elif safety < 60:
            comments.append("⚠️ Patrones de conducción inseguros")

        avg_idle = np.mean(idle_pct_data) if idle_pct_data else 0
        if avg_idle > 30:
            comments.append(f"⏱️ Alto tiempo en idle ({avg_idle:.0f}%)")

        return comments

    def _generate_recommendations(
        self,
        efficiency: float,
        aggressiveness: float,
        safety: float,
    ) -> List[str]:
        """Genera recomendaciones personalizadas"""
        recommendations = []

        if efficiency < 70:
            recommendations.append(
                "💡 Mantener velocidades constantes para mejor consumo"
            )

        if aggressiveness > 50:
            recommendations.append("🚗 Evitar aceleraciones bruscas")
            recommendations.append("🛑 Antici par frenadas para suavidad")

        if safety < 70:
            recommendations.append("⚠️ Aumentar distancia de frenado")
            recommendations.append("👁️ Mayor atención a cambios de velocidad")

        if not recommendations:
            recommendations.append("✨ Mantener el buen desempeño actual")

        return recommendations

    def _detect_alerts(
        self,
        driver_id: str,
        efficiency: float,
        aggressiveness: float,
        safety: float,
    ) -> List[Dict]:
        """Detecta alertas basadas en comportamiento"""
        alerts = []

        if aggressiveness > 70:
            alerts.append(
                {
                    "severity": "warning",
                    "type": "aggressive_driving",
                    "message": "Conducción muy agresiva detectada",
                }
            )

        if efficiency < 50:
            alerts.append(
                {
                    "severity": "info",
                    "type": "low_efficiency",
                    "message": "Eficiencia de combustible muy baja",
                }
            )

        if safety < 50:
            alerts.append(
                {
                    "severity": "critical",
                    "type": "unsafe_driving",
                    "message": "Patrones de conducción inseguros",
                }
            )

        # Guardar en histórico de alertas
        if alerts:
            if driver_id not in self.alerts:
                self.alerts[driver_id] = []
            self.alerts[driver_id].extend(alerts)

        return alerts

    def _update_driver_profile(self, driver_id: str, session_result: Dict):
        """Actualiza perfil agregado del conductor"""
        if driver_id not in self.driver_profiles:
            self.driver_profiles[driver_id] = {
                "driver_id": driver_id,
                "total_distance_miles": 0,
                "total_fuel_used_liters": 0,
                "total_sessions": 0,
                "avg_efficiency_score": 0,
                "avg_aggressiveness_score": 0,
                "avg_safety_score": 0,
                "avg_rating_stars": 0,
            }

        profile = self.driver_profiles[driver_id]
        profile["total_sessions"] = len(self.behavior_history.get(driver_id, []))

        # Recalcular promedios
        history = self.behavior_history.get(driver_id, [])
        if history:
            profile["total_distance_miles"] = sum(
                s.get("distance_miles", 0) for s in history
            )
            profile["total_fuel_used_liters"] = sum(
                s.get("fuel_used_liters", 0) for s in history
            )
            profile["avg_efficiency_score"] = int(
                np.mean([s.get("fuel_efficiency_score", 0) for s in history])
            )
            profile["avg_aggressiveness_score"] = int(
                np.mean([s.get("aggressiveness_score", 0) for s in history])
            )
            profile["avg_safety_score"] = int(
                np.mean([s.get("safety_score", 0) for s in history])
            )
            profile["avg_rating_stars"] = round(
                np.mean([s.get("overall_rating_stars", 3) for s in history]), 1
            )

    def _get_active_warnings(self, driver_id: str) -> List[str]:
        """Obtiene advertencias activas para un conductor"""
        recent_alerts = self.alerts.get(driver_id, [])[-10:]

        warning_types = {}
        for alert in recent_alerts:
            atype = alert.get("type", "unknown")
            warning_types[atype] = warning_types.get(atype, 0) + 1

        warnings = []
        for atype, count in warning_types.items():
            if count >= 3:
                warnings.append(f"Recurring: {atype} ({count}x)")

        return warnings


# Instancia global
_behavior_scorer: Optional[DriverBehaviorScorer] = None


def get_behavior_scorer() -> DriverBehaviorScorer:
    """Obtiene instancia singleton del driver behavior scorer"""
    global _behavior_scorer
    if _behavior_scorer is None:
        _behavior_scorer = DriverBehaviorScorer()
    return _behavior_scorer
