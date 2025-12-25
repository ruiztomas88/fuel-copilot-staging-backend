"""
Route Optimization Engine - Fase 2C
Optimización de rutas basada en consumo de combustible y eficiencia

Features:
- Cálculo de rutas más eficientes (fuel-aware)
- Predicción de consumo por ruta
- Análisis de paradas de descanso
- Integración con mapas (Google Maps API compatible)
- Recomendaciones de velocidad óptima
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class RouteSegment:
    """Segmento de una ruta"""

    def __init__(
        self,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        distance_miles: float,
        elevation_change_ft: float = 0,
        road_type: str = "highway",  # highway, urban, rural
    ):
        self.start_lat = start_lat
        self.start_lon = start_lon
        self.end_lat = end_lat
        self.end_lon = end_lon
        self.distance_miles = distance_miles
        self.elevation_change_ft = elevation_change_ft
        self.road_type = road_type
        self.segment_id = f"{start_lat}_{start_lon}_{end_lat}_{end_lon}"

    def to_dict(self) -> Dict:
        """Serializa segmento"""
        return {
            "segment_id": self.segment_id,
            "start": {"lat": self.start_lat, "lon": self.start_lon},
            "end": {"lat": self.end_lat, "lon": self.end_lon},
            "distance_miles": self.distance_miles,
            "elevation_change_ft": self.elevation_change_ft,
            "road_type": self.road_type,
        }


class Route:
    """Ruta completa con múltiples segmentos"""

    def __init__(
        self,
        route_id: str,
        truck_id: str,
        start_location: Tuple[float, float],
        end_location: Tuple[float, float],
        segments: List[RouteSegment],
    ):
        self.route_id = route_id
        self.truck_id = truck_id
        self.start_location = start_location
        self.end_location = end_location
        self.segments = segments
        self.total_distance_miles = sum(s.distance_miles for s in segments)
        self.total_elevation_change_ft = sum(s.elevation_change_ft for s in segments)
        self.created_at = datetime.now(timezone.utc).isoformat()

        # Cálculos de predicción
        self.predicted_consumption_liters = 0.0
        self.estimated_duration_minutes = 0
        self.optimal_avg_speed_mph = 55  # Velocidad óptima para eficiencia
        self.fuel_cost_estimate_usd = 0.0
        self.efficiency_score = 0.0

    def to_dict(self) -> Dict:
        """Serializa ruta"""
        return {
            "route_id": self.route_id,
            "truck_id": self.truck_id,
            "start_location": self.start_location,
            "end_location": self.end_location,
            "total_distance_miles": self.total_distance_miles,
            "total_elevation_change_ft": self.total_elevation_change_ft,
            "segments": [s.to_dict() for s in self.segments],
            "predicted_consumption_liters": self.predicted_consumption_liters,
            "estimated_duration_minutes": self.estimated_duration_minutes,
            "optimal_avg_speed_mph": self.optimal_avg_speed_mph,
            "fuel_cost_estimate_usd": self.fuel_cost_estimate_usd,
            "efficiency_score": self.efficiency_score,
            "created_at": self.created_at,
        }


class RouteOptimizer:
    """Optimizador de rutas para eficiencia de combustible"""

    def __init__(self, fuel_price_per_gallon: float = 3.50):
        """
        Inicializa optimizador de rutas

        Args:
            fuel_price_per_gallon: Precio actual del combustible
        """
        self.fuel_price_per_gallon = fuel_price_per_gallon
        self.optimized_routes: Dict[str, Route] = {}
        self.route_history: Dict[str, List[Dict]] = {}

        # Modelos de consumo por tipo de carretera y velocidad
        self.consumption_models = {
            "highway": {
                "base_gph": 3.5,
                "speed_factor": 0.0002,
            },  # gph = 3.5 + speed² * factor
            "urban": {"base_gph": 4.2, "speed_factor": 0.0003},
            "rural": {"base_gph": 3.8, "speed_factor": 0.00015},
        }

        logger.info(
            f"✅ Route Optimizer inicializado - Precio combustible: ${fuel_price_per_gallon}/gal"
        )

    def optimize_route(
        self,
        truck_id: str,
        start_lat: float,
        start_lon: float,
        end_lat: float,
        end_lon: float,
        segments: List[RouteSegment],
        truck_capacity_liters: float = 120.0,
        fuel_tank_current_liters: float = 60.0,
        target_avg_speed_mph: float = 60.0,
    ) -> Dict:
        """
        Optimiza una ruta para máxima eficiencia de combustible

        Args:
            truck_id: Identificador del truck
            start_lat, start_lon: Ubicación inicial
            end_lat, end_lon: Ubicación final
            segments: Segmentos de la ruta
            truck_capacity_liters: Capacidad del tanque
            fuel_tank_current_liters: Combustible actual
            target_avg_speed_mph: Velocidad promedio objetivo

        Returns:
            {
                "status": "optimized",
                "route": {...},
                "recommendations": [...],
                "alternatives": [...]
            }
        """

        route_id = f"{truck_id}_{int(datetime.now(timezone.utc).timestamp() * 1000)}"

        # Crear ruta
        route = Route(
            route_id=route_id,
            truck_id=truck_id,
            start_location=(start_lat, start_lon),
            end_location=(end_lat, end_lon),
            segments=segments,
        )

        # Calcular consumo predicho
        consumption_liters = self._predict_consumption(segments, target_avg_speed_mph)
        route.predicted_consumption_liters = consumption_liters

        # Validar que hay suficiente combustible
        fuel_status = self._validate_fuel_availability(
            fuel_tank_current_liters,
            consumption_liters,
            truck_capacity_liters,
            route.total_distance_miles,
        )

        # Calcular duración y velocidad óptima
        optimal_speed = self._find_optimal_speed(segments)
        route.optimal_avg_speed_mph = optimal_speed
        route.estimated_duration_minutes = (
            int((route.total_distance_miles / optimal_speed) * 60)
            if optimal_speed > 0
            else 0
        )

        # Calcular costo
        route.fuel_cost_estimate_usd = (
            consumption_liters / 3.785
        ) * self.fuel_price_per_gallon

        # Calcular score de eficiencia
        route.efficiency_score = self._calculate_efficiency_score(route, fuel_status)

        # Guardar ruta
        self.optimized_routes[route_id] = route

        # Generar recomendaciones
        recommendations = self._generate_recommendations(route, fuel_status)

        # Generar rutas alternativas
        alternatives = self._generate_alternatives(route, segments)

        return {
            "status": "optimized",
            "route": route.to_dict(),
            "fuel_validation": fuel_status,
            "recommendations": recommendations,
            "alternatives": alternatives,
        }

    def get_optimal_speed_profile(
        self,
        segments: List[RouteSegment],
        truck_id: str,
    ) -> Dict:
        """
        Obtiene perfil de velocidad óptima para cada segmento

        Returns:
            {
                "truck_id": "JC1282",
                "speed_profile": [
                    {
                        "segment_id": "...",
                        "road_type": "highway",
                        "optimal_speed_mph": 55,
                        "max_speed_mph": 65,
                        "efficiency_ratio": 0.92,
                        "fuel_savings_pct": 8.5
                    }
                ]
            }
        """
        profile = []

        for segment in segments:
            road_type = segment.road_type
            model = self.consumption_models.get(
                road_type, self.consumption_models["highway"]
            )

            # Velocidad que minimiza consumo (derivada de modelo cuadrático)
            # min_consumption cuando d(gph)/d(speed) = 0
            optimal_speed = 55  # Velocidad típica eficiente

            # Calcular consumo a diferentes velocidades
            consumption_at_55 = model["base_gph"] + (55**2) * model["speed_factor"]
            consumption_at_65 = model["base_gph"] + (65**2) * model["speed_factor"]

            fuel_savings_pct = (
                (consumption_at_65 - consumption_at_55) / consumption_at_65 * 100
            )

            profile.append(
                {
                    "segment_id": segment.segment_id,
                    "road_type": road_type,
                    "optimal_speed_mph": optimal_speed,
                    "max_speed_mph": 65,
                    "min_speed_mph": 45,
                    "consumption_at_optimal_gph": consumption_at_55,
                    "consumption_at_max_gph": consumption_at_65,
                    "fuel_savings_by_slowing_5mph": round(fuel_savings_pct, 1),
                }
            )

        return {
            "truck_id": truck_id,
            "segment_count": len(segments),
            "speed_profile": profile,
            "avg_optimal_speed_mph": round(
                np.mean([p["optimal_speed_mph"] for p in profile]), 1
            ),
        }

    # ============ MÉTODOS PRIVADOS ============

    def _predict_consumption(
        self,
        segments: List[RouteSegment],
        avg_speed_mph: float,
    ) -> float:
        """Predice consumo total para la ruta"""
        total_consumption = 0.0

        for segment in segments:
            road_type = segment.road_type
            model = self.consumption_models.get(road_type)

            if not model:
                continue

            # Consumo base + factor de velocidad
            segment_gph = model["base_gph"] + (avg_speed_mph**2) * model["speed_factor"]

            # Factor de elevación (subidas = más combustible)
            elevation_factor = 1.0
            if segment.elevation_change_ft > 0:
                elevation_factor = 1.0 + (segment.elevation_change_ft / 1000) * 0.1

            # Consumo del segmento
            segment_hours = (
                segment.distance_miles / avg_speed_mph if avg_speed_mph > 0 else 0
            )
            segment_consumption = segment_gph * segment_hours * elevation_factor
            total_consumption += segment_consumption

        return total_consumption

    def _validate_fuel_availability(
        self,
        current_fuel_liters: float,
        predicted_consumption_liters: float,
        capacity_liters: float,
        distance_miles: float,
    ) -> Dict:
        """Valida que hay combustible suficiente"""
        fuel_margin_liters = 10  # Margen de seguridad
        required_fuel = predicted_consumption_liters + fuel_margin_liters

        can_complete = current_fuel_liters >= required_fuel

        # Buscar puntos de refuel si es necesario
        refuel_points = []
        if not can_complete:
            estimated_range = (
                current_fuel_liters / predicted_consumption_liters
            ) * distance_miles
            refuel_points.append(
                {
                    "distance_miles": int(estimated_range * 0.8),
                    "reason": "Fuel tank will be low",
                }
            )

        return {
            "current_fuel_liters": current_fuel_liters,
            "predicted_consumption_liters": round(predicted_consumption_liters, 2),
            "fuel_margin_liters": fuel_margin_liters,
            "can_complete_route": can_complete,
            "fuel_reserve_at_end_liters": max(0, current_fuel_liters - required_fuel),
            "estimated_range_miles": (
                int(
                    (
                        current_fuel_liters
                        / (predicted_consumption_liters / distance_miles)
                    )
                )
                if distance_miles > 0
                else 0
            ),
            "refuel_required_at": refuel_points,
        }

    def _find_optimal_speed(self, segments: List[RouteSegment]) -> float:
        """Encuentra velocidad óptima para la ruta"""
        # Promedio de velocidades óptimas por tipo de carretera
        highway_pct = sum(
            s.distance_miles for s in segments if s.road_type == "highway"
        ) / sum(s.distance_miles for s in segments)

        urban_pct = sum(
            s.distance_miles for s in segments if s.road_type == "urban"
        ) / sum(s.distance_miles for s in segments)

        optimal = highway_pct * 55 + urban_pct * 35 + (1 - highway_pct - urban_pct) * 50

        return optimal

    def _calculate_efficiency_score(self, route: Route, fuel_status: Dict) -> float:
        """Calcula score de eficiencia de la ruta (0-100)"""
        score = 100.0

        # Penalidad por refuel requerido
        if not fuel_status["can_complete_route"]:
            score -= 20

        # Penalidad por alto consumo
        avg_consumption_per_100mi = (
            ((route.predicted_consumption_liters / route.total_distance_miles) * 100)
            if route.total_distance_miles > 0
            else 0
        )

        if avg_consumption_per_100mi > 30:
            score -= min(30, (avg_consumption_per_100mi - 30) * 2)
        elif avg_consumption_per_100mi < 20:
            score += 10

        return max(0, min(100, score))

    def _generate_recommendations(self, route: Route, fuel_status: Dict) -> List[str]:
        """Genera recomendaciones para la ruta"""
        recommendations = []

        if fuel_status["refuel_required_at"]:
            recommendations.append(
                f"⛽ Refuel en milla {fuel_status['refuel_required_at'][0]['distance_miles']}"
            )

        if route.predicted_consumption_liters > 50:
            recommendations.append(
                f"💡 Mantener velocidad de {route.optimal_avg_speed_mph} mph para eficiencia"
            )

        if route.total_elevation_change_ft > 5000:
            recommendations.append(
                "⛰️ Ruta con cambio de elevación significativo - monitor consumo en subidas"
            )

        if route.estimated_duration_minutes > 480:  # > 8 horas
            recommendations.append(
                "⏱️ Considerar paradas de descanso cada 4 horas para seguridad"
            )

        return recommendations

    def _generate_alternatives(
        self, route: Route, segments: List[RouteSegment]
    ) -> List[Dict]:
        """Genera rutas alternativas con diferente velocidad"""
        alternatives = []

        for speed_mph in [50, 55, 60, 65]:
            if speed_mph == route.optimal_avg_speed_mph:
                continue

            alt_consumption = self._predict_consumption(segments, speed_mph)
            alt_duration = (route.total_distance_miles / speed_mph) * 60
            alt_cost = (alt_consumption / 3.785) * self.fuel_price_per_gallon

            consumption_diff = (
                (alt_consumption - route.predicted_consumption_liters)
                / route.predicted_consumption_liters
                * 100
            )

            alternatives.append(
                {
                    "avg_speed_mph": speed_mph,
                    "predicted_consumption_liters": round(alt_consumption, 2),
                    "estimated_duration_minutes": int(alt_duration),
                    "fuel_cost_usd": round(alt_cost, 2),
                    "consumption_vs_optimal_pct": round(consumption_diff, 1),
                    "efficiency_score": self._calculate_efficiency_score(
                        Route(
                            f"{route.route_id}_alt_{speed_mph}",
                            route.truck_id,
                            route.start_location,
                            route.end_location,
                            segments,
                        ),
                        {"can_complete_route": True, "refuel_required_at": []},
                    ),
                }
            )

        return sorted(alternatives, key=lambda x: x["fuel_cost_usd"])


# Instancia global
_route_optimizer: Optional[RouteOptimizer] = None


def get_route_optimizer() -> RouteOptimizer:
    """Obtiene instancia singleton del optimizador de rutas"""
    global _route_optimizer
    if _route_optimizer is None:
        _route_optimizer = RouteOptimizer()
    return _route_optimizer
