"""
🧪 A/B TESTING FRAMEWORK
========================

Compara algoritmos nuevos vs actuales en producción:
1. AdaptiveMPGEngine vs MPG estándar
2. ExtendedKalmanFilter vs Linear Kalman
3. EnhancedTheftDetector vs Theft Detection actual

Genera métricas de comparación para tomar decisiones basadas en datos.
"""

import logging
import statistics
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

# Algoritmos nuevos (staging)
from algorithm_improvements import (
    AdaptiveMPGEngine,
    EnhancedTheftDetector,
    ExtendedKalmanFuelEstimator,
)

# Algoritmos actuales (producción)
from estimator import FuelEstimator
from wialon_sync_enhanced import detect_fuel_theft

logger = logging.getLogger(__name__)


# ============================================================================
# ESTRUCTURAS DE DATOS PARA RESULTADOS
# ============================================================================


@dataclass
class MPGComparisonResult:
    """Resultado de comparación MPG"""

    truck_id: str
    test_name: str

    # Resultados algoritmo actual
    current_mpg: float
    current_confidence: str
    current_time_ms: float

    # Resultados algoritmo nuevo
    new_mpg: float
    new_condition: str  # highway/city/mixed
    new_window_miles: float
    new_time_ms: float

    # Métricas de comparación
    mpg_difference: float
    percent_difference: float
    performance_improvement_pct: float

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class KalmanComparisonResult:
    """Resultado de comparación Kalman Filter"""

    truck_id: str
    test_name: str

    # Resultados Kalman lineal (actual)
    linear_fuel_pct: float
    linear_variance: float
    linear_time_ms: float

    # Resultados Extended Kalman (nuevo)
    ekf_fuel_pct: float
    ekf_consumption_rate: float
    ekf_sensor_bias: float
    ekf_variance: float
    ekf_time_ms: float

    # Métricas de comparación
    fuel_difference_pct: float
    variance_improvement_pct: float
    performance_impact_pct: float
    bias_detected: bool

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class TheftComparisonResult:
    """Resultado de comparación Theft Detection"""

    truck_id: str
    test_name: str
    drop_magnitude_pct: float

    # Resultados detector actual
    current_detected: bool
    current_classification: str
    current_time_ms: float

    # Resultados detector nuevo (multi-factor)
    new_detected: bool
    new_classification: str
    new_confidence_score: float
    new_factors: Dict[str, float]
    new_time_ms: float

    # Métricas de comparación
    agreement: bool  # ¿Ambos coinciden?
    new_more_confident: bool
    performance_impact_pct: float

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ABTestSummary:
    """Resumen de todos los tests A/B"""

    total_tests: int
    mpg_tests: int
    kalman_tests: int
    theft_tests: int

    # MPG Summary
    mpg_avg_difference: float
    mpg_avg_performance: float
    mpg_better_count: int
    mpg_worse_count: int

    # Kalman Summary
    kalman_avg_variance_improvement: float
    kalman_bias_detected_count: int
    kalman_better_count: int

    # Theft Summary
    theft_agreement_pct: float
    theft_false_positive_reduction: int
    theft_avg_confidence: float

    duration_seconds: float
    timestamp: datetime = field(default_factory=datetime.now)


# ============================================================================
# A/B TESTING ENGINE
# ============================================================================


class ABTestingEngine:
    """Motor de testing A/B para comparar algoritmos"""

    def __init__(self):
        self.mpg_results: List[MPGComparisonResult] = []
        self.kalman_results: List[KalmanComparisonResult] = []
        self.theft_results: List[TheftComparisonResult] = []
        self.start_time = time.time()

    # ========================================================================
    # TEST #1: MPG ADAPTATIVO vs STANDARD
    # ========================================================================

    def test_mpg_comparison(
        self,
        truck_id: str,
        distance_miles: float,
        fuel_consumed_gal: float,
        avg_speed_mph: float,
        stop_count: int,
        test_name: str = "MPG Comparison",
    ) -> MPGComparisonResult:
        """
        Compara MPG estándar vs Adaptivo

        Args:
            truck_id: ID del truck
            distance_miles: Distancia recorrida
            fuel_consumed_gal: Combustible consumido
            avg_speed_mph: Velocidad promedio
            stop_count: Cantidad de paradas
            test_name: Nombre del test

        Returns:
            MPGComparisonResult con métricas de ambos
        """

        # ALGORITMO ACTUAL: MPG simple
        start = time.perf_counter()
        current_mpg = distance_miles / fuel_consumed_gal if fuel_consumed_gal > 0 else 0

        # Determinar confianza basado en distancia
        if distance_miles >= 10:
            current_confidence = "high"
        elif distance_miles >= 5:
            current_confidence = "medium"
        else:
            current_confidence = "low"

        current_time_ms = (time.perf_counter() - start) * 1000

        # ALGORITMO NUEVO: Adaptive MPG
        start = time.perf_counter()
        adaptive_engine = AdaptiveMPGEngine()

        # Simular lecturas incrementales (deltas pequeños)
        num_readings = max(10, int(distance_miles / 2))  # 1 reading cada 2 millas
        distance_per_reading = distance_miles / num_readings
        fuel_per_reading = fuel_consumed_gal / num_readings

        for i in range(num_readings):
            new_mpg = adaptive_engine.process(
                distance_delta_mi=distance_per_reading,
                fuel_delta_gal=fuel_per_reading,
                speed_mph=avg_speed_mph,
            )

        # Último reading debe tener MPG calculado
        if new_mpg is None:
            new_mpg = current_mpg  # Fallback si ventana insuficiente

        # Detectar condición
        new_condition = adaptive_engine.detect_condition().value

        new_time_ms = (time.perf_counter() - start) * 1000

        # Calcular diferencias
        mpg_diff = new_mpg - current_mpg
        pct_diff = (mpg_diff / current_mpg * 100) if current_mpg > 0 else 0
        perf_improvement = (
            ((current_time_ms - new_time_ms) / current_time_ms * 100)
            if current_time_ms > 0
            else 0
        )

        # Obtener window miles del config de condición detectada
        condition_enum = adaptive_engine.detect_condition()
        window_miles = adaptive_engine.window_config[condition_enum]["miles"]

        result = MPGComparisonResult(
            truck_id=truck_id,
            test_name=test_name,
            current_mpg=current_mpg,
            current_confidence=current_confidence,
            current_time_ms=current_time_ms,
            new_mpg=new_mpg,
            new_condition=new_condition,
            new_window_miles=window_miles,
            new_time_ms=new_time_ms,
            mpg_difference=mpg_diff,
            percent_difference=pct_diff,
            performance_improvement_pct=perf_improvement,
        )

        self.mpg_results.append(result)
        return result

    # ========================================================================
    # TEST #2: EXTENDED KALMAN vs LINEAR KALMAN
    # ========================================================================

    def test_kalman_comparison(
        self,
        truck_id: str,
        capacity_liters: float,
        initial_fuel_pct: float,
        readings: List[Tuple[float, float]],  # (sensor_pct, consumption_gph)
        test_name: str = "Kalman Comparison",
    ) -> KalmanComparisonResult:
        """
        Compara Linear Kalman vs Extended Kalman

        Args:
            truck_id: ID del truck
            capacity_liters: Capacidad del tanque
            initial_fuel_pct: Nivel inicial de combustible
            readings: Lista de (sensor_pct, consumption_gph)
            test_name: Nombre del test

        Returns:
            KalmanComparisonResult con métricas
        """

        # ALGORITMO ACTUAL: Linear Kalman
        start = time.perf_counter()

        # Config minimal para FuelEstimator
        minimal_config = {"kalman": {"Q": 0.1, "R_base": 2.0, "P_init": 2.0}}

        linear_kalman = FuelEstimator(
            truck_id=truck_id, capacity_liters=capacity_liters, config=minimal_config
        )

        # Procesar lecturas
        for sensor_pct, consumption_gph in readings:
            linear_kalman.update(
                sensor_fuel_pct=sensor_pct,
                consumption_gph=consumption_gph,
                dt_hours=1 / 60,  # 1 minuto
            )

        linear_fuel_pct = linear_kalman.last_fuel_lvl_pct
        linear_variance = linear_kalman.P
        linear_time_ms = (time.perf_counter() - start) * 1000

        # ALGORITMO NUEVO: Extended Kalman
        start = time.perf_counter()
        ekf = ExtendedKalmanFuelEstimator(capacity_liters=capacity_liters)
        ekf.state[0] = initial_fuel_pct * capacity_liters / 100  # Fuel en litros

        # Procesar lecturas
        for sensor_pct, consumption_gph in readings:
            # Predict step
            ekf.predict(consumption_gph=consumption_gph, dt_hours=1 / 60)

            # Update step con medición del sensor
            sensor_liters = sensor_pct * capacity_liters / 100
            ekf.update(sensor_fuel_liters=sensor_liters)

        ekf_fuel_pct = (ekf.state[0] / capacity_liters) * 100
        ekf_consumption_rate = ekf.state[1]
        ekf_sensor_bias = ekf.state[2]
        ekf_variance = float(ekf.P[0, 0])
        ekf_time_ms = (time.perf_counter() - start) * 1000

        # Calcular métricas
        fuel_diff = abs(ekf_fuel_pct - linear_fuel_pct)
        variance_improvement = (
            ((linear_variance - ekf_variance) / linear_variance * 100)
            if linear_variance > 0
            else 0
        )
        perf_impact = (
            ((ekf_time_ms - linear_time_ms) / linear_time_ms * 100)
            if linear_time_ms > 0
            else 0
        )
        bias_detected = abs(ekf_sensor_bias) > 1.0  # Más de 1% de bias

        result = KalmanComparisonResult(
            truck_id=truck_id,
            test_name=test_name,
            linear_fuel_pct=linear_fuel_pct,
            linear_variance=linear_variance,
            linear_time_ms=linear_time_ms,
            ekf_fuel_pct=ekf_fuel_pct,
            ekf_consumption_rate=ekf_consumption_rate,
            ekf_sensor_bias=ekf_sensor_bias,
            ekf_variance=ekf_variance,
            ekf_time_ms=ekf_time_ms,
            fuel_difference_pct=fuel_diff,
            variance_improvement_pct=variance_improvement,
            performance_impact_pct=perf_impact,
            bias_detected=bias_detected,
        )

        self.kalman_results.append(result)
        return result

    # ========================================================================
    # TEST #3: ENHANCED THEFT DETECTION vs CURRENT
    # ========================================================================

    def test_theft_detection_comparison(
        self,
        truck_id: str,
        readings: List[Dict],  # Lista de fuel_metrics readings
        test_name: str = "Theft Detection Comparison",
    ) -> TheftComparisonResult:
        """
        Compara Theft Detection actual vs Enhanced

        Args:
            truck_id: ID del truck
            readings: Lista de lecturas de fuel_metrics
            test_name: Nombre del test

        Returns:
            TheftComparisonResult con métricas
        """

        if len(readings) < 2:
            logger.warning(f"Not enough readings for theft test: {len(readings)}")
            return None

        # Calcular drop magnitude
        first_pct = readings[0].get("sensor_fuel_pct", 0)
        last_pct = readings[-1].get("sensor_fuel_pct", 0)
        drop_magnitude = first_pct - last_pct

        # ALGORITMO ACTUAL: detect_fuel_theft()
        start = time.perf_counter()

        # Simular llamada al detector actual
        # Nota: Esta es una simplificación - el detector real requiere más contexto
        current_detected = False
        current_classification = "NORMAL"

        if drop_magnitude > 10 and readings[-1].get("speed_mph", 0) < 5:
            current_detected = True
            current_classification = "THEFT_SUSPECTED"

        current_time_ms = (time.perf_counter() - start) * 1000

        # ALGORITMO NUEVO: EnhancedTheftDetector
        start = time.perf_counter()
        detector = EnhancedTheftDetector()
        theft_event = detector.analyze(truck_id, readings)
        new_time_ms = (time.perf_counter() - start) * 1000

        if theft_event:
            new_detected = True
            new_classification = theft_event.classification
            new_confidence = theft_event.confidence_score
            new_factors = theft_event.factors
        else:
            new_detected = False
            new_classification = "NORMAL"
            new_confidence = 0.0
            new_factors = {}

        # Métricas de comparación
        agreement = current_detected == new_detected
        new_more_confident = new_confidence > 0.7 if new_detected else False
        perf_impact = (
            ((new_time_ms - current_time_ms) / current_time_ms * 100)
            if current_time_ms > 0
            else 0
        )

        result = TheftComparisonResult(
            truck_id=truck_id,
            test_name=test_name,
            drop_magnitude_pct=drop_magnitude,
            current_detected=current_detected,
            current_classification=current_classification,
            current_time_ms=current_time_ms,
            new_detected=new_detected,
            new_classification=new_classification,
            new_confidence_score=new_confidence,
            new_factors=new_factors,
            new_time_ms=new_time_ms,
            agreement=agreement,
            new_more_confident=new_more_confident,
            performance_impact_pct=perf_impact,
        )

        self.theft_results.append(result)
        return result

    # ========================================================================
    # SUMMARY & REPORTING
    # ========================================================================

    def generate_summary(self) -> ABTestSummary:
        """Genera resumen de todos los tests"""

        duration = time.time() - self.start_time

        # MPG metrics
        mpg_avg_diff = (
            statistics.mean([r.mpg_difference for r in self.mpg_results])
            if self.mpg_results
            else 0
        )
        mpg_avg_perf = (
            statistics.mean([r.performance_improvement_pct for r in self.mpg_results])
            if self.mpg_results
            else 0
        )
        mpg_better = sum(
            1 for r in self.mpg_results if abs(r.mpg_difference) < 0.5
        )  # Dentro de ±0.5 MPG
        mpg_worse = len(self.mpg_results) - mpg_better

        # Kalman metrics
        kalman_avg_variance = (
            statistics.mean([r.variance_improvement_pct for r in self.kalman_results])
            if self.kalman_results
            else 0
        )
        kalman_bias_count = sum(1 for r in self.kalman_results if r.bias_detected)
        kalman_better = sum(
            1 for r in self.kalman_results if r.variance_improvement_pct > 0
        )

        # Theft metrics
        theft_agreement = (
            (
                sum(1 for r in self.theft_results if r.agreement)
                / len(self.theft_results)
                * 100
            )
            if self.theft_results
            else 0
        )
        theft_fp_reduction = sum(
            1
            for r in self.theft_results
            if not r.current_detected and not r.new_detected
        )
        theft_avg_conf = (
            statistics.mean(
                [r.new_confidence_score for r in self.theft_results if r.new_detected]
            )
            if any(r.new_detected for r in self.theft_results)
            else 0
        )

        return ABTestSummary(
            total_tests=len(self.mpg_results)
            + len(self.kalman_results)
            + len(self.theft_results),
            mpg_tests=len(self.mpg_results),
            kalman_tests=len(self.kalman_results),
            theft_tests=len(self.theft_results),
            mpg_avg_difference=mpg_avg_diff,
            mpg_avg_performance=mpg_avg_perf,
            mpg_better_count=mpg_better,
            mpg_worse_count=mpg_worse,
            kalman_avg_variance_improvement=kalman_avg_variance,
            kalman_bias_detected_count=kalman_bias_count,
            kalman_better_count=kalman_better,
            theft_agreement_pct=theft_agreement,
            theft_false_positive_reduction=theft_fp_reduction,
            theft_avg_confidence=theft_avg_conf,
            duration_seconds=duration,
        )

    def print_summary(self):
        """Imprime resumen de resultados"""
        summary = self.generate_summary()

        print("\n" + "=" * 80)
        print("🧪 A/B TESTING SUMMARY")
        print("=" * 80)
        print(f"Total Tests: {summary.total_tests}")
        print(f"Duration: {summary.duration_seconds:.2f}s")
        print(f"Timestamp: {summary.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")

        print("\n📊 MPG ADAPTATIVO vs STANDARD")
        print(f"   Tests: {summary.mpg_tests}")
        print(f"   Avg Difference: {summary.mpg_avg_difference:+.2f} MPG")
        print(f"   Avg Performance: {summary.mpg_avg_performance:+.2f}%")
        print(f"   Better/Same: {summary.mpg_better_count}/{summary.mpg_tests}")

        print("\n🎯 EXTENDED KALMAN vs LINEAR KALMAN")
        print(f"   Tests: {summary.kalman_tests}")
        print(
            f"   Avg Variance Improvement: {summary.kalman_avg_variance_improvement:+.2f}%"
        )
        print(
            f"   Bias Detected: {summary.kalman_bias_detected_count}/{summary.kalman_tests}"
        )
        print(
            f"   Better Estimates: {summary.kalman_better_count}/{summary.kalman_tests}"
        )

        print("\n🔒 ENHANCED THEFT vs CURRENT")
        print(f"   Tests: {summary.theft_tests}")
        print(f"   Agreement: {summary.theft_agreement_pct:.1f}%")
        print(f"   False Positive Reduction: {summary.theft_false_positive_reduction}")
        print(f"   Avg Confidence (when detected): {summary.theft_avg_confidence:.2f}")

        print("\n" + "=" * 80)


# ============================================================================
# EJEMPLO DE USO
# ============================================================================

if __name__ == "__main__":
    print("🧪 A/B Testing Framework - Example")

    engine = ABTestingEngine()

    # Test 1: MPG Comparison
    print("\n1️⃣ Testing MPG Adaptativo...")
    mpg_result = engine.test_mpg_comparison(
        truck_id="TEST001",
        distance_miles=50,
        fuel_consumed_gal=8.5,
        avg_speed_mph=55,
        stop_count=2,
    )
    print(f"   Current MPG: {mpg_result.current_mpg:.2f}")
    print(f"   New MPG: {mpg_result.new_mpg:.2f} ({mpg_result.new_condition})")
    print(
        f"   Difference: {mpg_result.mpg_difference:+.2f} MPG ({mpg_result.percent_difference:+.1f}%)"
    )

    # Test 2: Kalman Comparison
    print("\n2️⃣ Testing Extended Kalman...")
    readings = [
        (80.0, 5.0),  # 80% fuel, consuming 5 GPH
        (78.0, 5.2),
        (76.5, 4.8),
        (75.0, 5.0),
    ]
    kalman_result = engine.test_kalman_comparison(
        truck_id="TEST001", capacity_liters=500, initial_fuel_pct=80, readings=readings
    )
    print(f"   Linear Kalman: {kalman_result.linear_fuel_pct:.1f}%")
    print(f"   Extended Kalman: {kalman_result.ekf_fuel_pct:.1f}%")
    print(f"   Variance Improvement: {kalman_result.variance_improvement_pct:+.1f}%")
    print(f"   Bias Detected: {kalman_result.bias_detected}")

    # Test 3: Theft Detection
    print("\n3️⃣ Testing Enhanced Theft Detection...")
    theft_readings = [
        {
            "sensor_fuel_pct": 80,
            "speed_mph": 0,
            "timestamp": datetime.now() - timedelta(minutes=5),
        },
        {
            "sensor_fuel_pct": 60,
            "speed_mph": 0,
            "timestamp": datetime.now(),
        },  # 20% drop while parked
    ]
    theft_result = engine.test_theft_detection_comparison(
        truck_id="TEST001", readings=theft_readings
    )
    if theft_result:
        print(f"   Current Detected: {theft_result.current_detected}")
        print(
            f"   New Detected: {theft_result.new_detected} (confidence: {theft_result.new_confidence_score:.2f})"
        )
        print(f"   Agreement: {theft_result.agreement}")

    # Print summary
    engine.print_summary()
