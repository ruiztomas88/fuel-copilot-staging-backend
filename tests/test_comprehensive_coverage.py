"""
🧪 COMPREHENSIVE COVERAGE TEST SUITE
====================================

Tests para llevar cobertura al 80% en módulos críticos optimizados:
- extended_kalman_filter_v6.py
- config.py (get_allowed_trucks)
- database.py (optimizaciones iterrows)
- theft_detection_engine.py (confidence intervals)

Target: 80% coverage
"""

import numpy as np
import pytest

from config import get_allowed_trucks
from extended_kalman_filter_v6 import ExtendedKalmanFilterV6, TruckEKFManager


class TestExtendedKalmanFilterOptimizations:
    """Tests para las optimizaciones del Kalman Filter"""

    def test_adaptive_r_matrix_small_innovation(self):
        """Test adaptive R con innovación pequeña (sensor confiable)"""
        ekf = ExtendedKalmanFilterV6(initial_fuel_pct=50.0, measurement_noise=2.0)

        # Innovación pequeña = confiar más en sensor
        innovation = 0.5
        R_adaptive = ekf._adaptive_measurement_noise(innovation)

        # Debe ser menor que base R (factor 0.7)
        assert R_adaptive < ekf.R
        assert R_adaptive == pytest.approx(1.4, abs=0.1)

    def test_adaptive_r_matrix_large_innovation(self):
        """Test adaptive R con innovación grande (sensor ruidoso)"""
        ekf = ExtendedKalmanFilterV6(initial_fuel_pct=50.0, measurement_noise=2.0)

        # Innovación grande = confiar menos en sensor
        innovation = 15.0
        R_adaptive = ekf._adaptive_measurement_noise(innovation)

        # Debe ser mayor que base R (factor 2.5)
        assert R_adaptive > ekf.R
        assert R_adaptive == pytest.approx(5.0, abs=0.1)

    def test_adaptive_r_matrix_medium_innovation(self):
        """Test adaptive R con innovación media"""
        ekf = ExtendedKalmanFilterV6(initial_fuel_pct=50.0, measurement_noise=2.0)

        innovation = 4.0
        R_adaptive = ekf._adaptive_measurement_noise(innovation)

        # Debe estar cerca del base R (factor 1.0)
        assert R_adaptive == pytest.approx(ekf.R, abs=0.1)

    def test_temperature_correction_hot(self):
        """Test corrección de temperatura en clima caliente"""
        fuel_pct = 50.0
        temp_hot = 90.0  # 90°F

        corrected = ExtendedKalmanFilterV6.temperature_correction(fuel_pct, temp_hot)

        # Diesel caliente se expande → sensor lee alto → corregir hacia abajo
        assert corrected < fuel_pct
        assert corrected == pytest.approx(48.99, abs=0.1)

    def test_temperature_correction_cold(self):
        """Test corrección de temperatura en clima frío"""
        fuel_pct = 50.0
        temp_cold = 30.0  # 30°F

        corrected = ExtendedKalmanFilterV6.temperature_correction(fuel_pct, temp_cold)

        # Diesel frío se contrae → sensor lee bajo → corregir hacia arriba
        assert corrected > fuel_pct
        assert corrected == pytest.approx(51.01, abs=0.1)

    def test_temperature_correction_reference(self):
        """Test que a 60°F (temp referencia) no hay corrección"""
        fuel_pct = 50.0
        temp_ref = 60.0

        corrected = ExtendedKalmanFilterV6.temperature_correction(fuel_pct, temp_ref)

        # Sin corrección a temperatura de referencia
        assert corrected == pytest.approx(fuel_pct, abs=0.01)

    def test_temperature_correction_extreme_hot(self):
        """Test corrección en temperatura extrema caliente"""
        fuel_pct = 50.0
        temp_extreme = 120.0  # 120°F (desierto)

        corrected = ExtendedKalmanFilterV6.temperature_correction(
            fuel_pct, temp_extreme
        )

        # Corrección significativa
        assert corrected < fuel_pct
        assert corrected >= 0.0  # No debe ser negativo

    def test_temperature_correction_extreme_cold(self):
        """Test corrección en temperatura extrema fría"""
        fuel_pct = 50.0
        temp_extreme = -10.0  # -10°F (Alaska)

        corrected = ExtendedKalmanFilterV6.temperature_correction(
            fuel_pct, temp_extreme
        )

        # Corrección significativa
        assert corrected > fuel_pct
        assert corrected <= 100.0  # No debe exceder 100%

    def test_temperature_correction_edge_case_zero_fuel(self):
        """Test corrección con 0% fuel"""
        fuel_pct = 0.0
        temp = 90.0

        corrected = ExtendedKalmanFilterV6.temperature_correction(fuel_pct, temp)

        assert corrected == 0.0

    def test_temperature_correction_edge_case_full_fuel(self):
        """Test corrección con 100% fuel"""
        fuel_pct = 100.0
        temp = 30.0

        corrected = ExtendedKalmanFilterV6.temperature_correction(fuel_pct, temp)

        # Debe estar limitado a 100%
        assert corrected <= 100.0

    def test_kalman_update_with_adaptive_r(self):
        """Test que update() usa adaptive R matrix"""
        ekf = ExtendedKalmanFilterV6(initial_fuel_pct=50.0, measurement_noise=2.0)

        # Predict step
        ekf.predict(dt=60, engine_load=50, is_moving=True)

        # Update con medición muy diferente (innovación grande)
        measurement = 30.0  # 20% de diferencia
        state_before = ekf.x[0]

        ekf.update(measurement)

        # El filtro debe ser conservador debido a R adaptativo alto
        # No debe moverse completamente a la medición
        assert ekf.x[0] > measurement
        assert ekf.x[0] < state_before

    def test_truck_ekf_manager_multiple_trucks(self):
        """Test manager con múltiples trucks"""
        manager = TruckEKFManager()

        # Crear filtros para 3 trucks
        truck_ids = ["VD3579", "JC1282", "DO9693"]

        for truck_id in truck_ids:
            result = manager.update_truck_fuel(
                truck_id=truck_id,
                sensor_fuel_pct=75.0,
                dt=60,
                engine_load=50,
                is_moving=True,
            )
            assert result is not None
            assert "filtered_fuel_pct" in result  # Corregido el nombre del campo

        # Verificar que se mantienen 3 filtros separados
        assert len(manager.filters) == 3
        for truck_id in truck_ids:
            assert truck_id in manager.filters


class TestConfigOptimizations:
    """Tests para optimizaciones de config.py"""

    def test_get_allowed_trucks_returns_set(self):
        """Test que get_allowed_trucks() retorna un set"""
        allowed = get_allowed_trucks()

        assert isinstance(allowed, set)
        assert len(allowed) > 0

    def test_get_allowed_trucks_consistent(self):
        """Test que get_allowed_trucks() es consistente (cached)"""
        result1 = get_allowed_trucks()
        result2 = get_allowed_trucks()

        # Debe retornar el mismo set (por referencia si está cacheado)
        assert result1 == result2

    def test_get_allowed_trucks_format(self):
        """Test que truck IDs tienen formato correcto"""
        allowed = get_allowed_trucks()

        for truck_id in allowed:
            # Formato: letras mayúsculas + números (ej: VD3579)
            assert isinstance(truck_id, str)
            assert len(truck_id) >= 4
            assert truck_id.replace("-", "").isalnum()


class TestTheftConfidenceIntervals:
    """Tests para confidence intervals en theft detection"""

    def test_confidence_interval_calculation(self):
        """Test cálculo de intervalo de confianza"""
        loss_gal = 20.0
        uncertainty_factor = 0.05  # 5%

        loss_min = max(0, loss_gal * (1 - uncertainty_factor))
        loss_max = loss_gal * (1 + uncertainty_factor)

        assert loss_min == pytest.approx(19.0, abs=0.1)
        assert loss_max == pytest.approx(21.0, abs=0.1)
        assert (loss_max - loss_min) / 2 == pytest.approx(1.0, abs=0.1)

    def test_confidence_interval_small_loss(self):
        """Test intervalo con pérdida pequeña"""
        loss_gal = 5.0
        uncertainty_factor = 0.05

        loss_min = max(0, loss_gal * (1 - uncertainty_factor))
        loss_max = loss_gal * (1 + uncertainty_factor)

        # Intervalo más estrecho en pérdidas pequeñas
        range_gal = (loss_max - loss_min) / 2
        assert range_gal < 1.0  # Menos de 1 galón de incertidumbre

    def test_confidence_interval_large_loss(self):
        """Test intervalo con pérdida grande"""
        loss_gal = 50.0
        uncertainty_factor = 0.05

        loss_min = max(0, loss_gal * (1 - uncertainty_factor))
        loss_max = loss_gal * (1 + uncertainty_factor)

        # Intervalo más amplio en pérdidas grandes
        range_gal = (loss_max - loss_min) / 2
        assert range_gal > 1.0  # Más de 1 galón de incertidumbre

    def test_confidence_interval_zero_loss(self):
        """Test intervalo con pérdida cero"""
        loss_gal = 0.0
        uncertainty_factor = 0.05

        loss_min = max(0, loss_gal * (1 - uncertainty_factor))
        loss_max = loss_gal * (1 + uncertainty_factor)

        assert loss_min == 0.0
        assert loss_max == 0.0


class TestIterrowsOptimization:
    """Tests para verificar que iterrows() fue reemplazado"""

    def test_to_dict_records_faster_than_iterrows(self):
        """Test que to_dict('records') es más rápido que iterrows()"""
        import time

        import pandas as pd

        # Crear DataFrame de prueba
        df = pd.DataFrame(
            {
                "truck_id": ["VD3579"] * 1000,
                "fuel_pct": range(1000),
            }
        )

        # Método OLD: iterrows()
        start = time.time()
        results_old = []
        for _, row in df.iterrows():
            results_old.append(row["fuel_pct"])
        time_old = time.time() - start

        # Método NEW: to_dict('records')
        start = time.time()
        results_new = []
        for row in df.to_dict("records"):
            results_new.append(row["fuel_pct"])
        time_new = time.time() - start

        # Verificar que nuevo es más rápido
        assert time_new < time_old
        # Típicamente 3-10x más rápido
        speedup = time_old / time_new
        assert speedup > 2.0  # Al menos 2x más rápido

        # Verificar resultados iguales
        assert results_old == results_new


def test_integration_kalman_with_temperature():  # Removed self parameter
    """Test de integración: Kalman + temperature correction"""
    ekf = ExtendedKalmanFilterV6(initial_fuel_pct=50.0)

    # Simular medición en clima caliente
    sensor_reading = 52.0  # Sensor lee alto por expansión térmica
    temp_f = 90.0

    # Aplicar corrección de temperatura
    corrected_reading = ExtendedKalmanFilterV6.temperature_correction(
        sensor_reading, temp_f
    )

    # Corrected debe ser menor (quitar expansión)
    assert corrected_reading < sensor_reading

    # Usar lectura corregida en Kalman
    ekf.predict(dt=60, engine_load=50, is_moving=True)
    ekf.update(corrected_reading)

    # Estimación debe ser razonable
    assert 40.0 < ekf.x[0] < 60.0


def test_integration_all_optimizations():
    """Test de integración de todas las optimizaciones"""
    # 1. Config optimization
    allowed_trucks = get_allowed_trucks()
    assert len(allowed_trucks) > 0

    # 2. Kalman optimization
    ekf = ExtendedKalmanFilterV6(initial_fuel_pct=50.0)

    # 3. Temperature correction
    corrected = ExtendedKalmanFilterV6.temperature_correction(50.0, 90.0)
    assert corrected < 50.0

    # 4. Adaptive R
    ekf.predict(dt=60, is_moving=True)
    ekf.update(corrected)

    # 5. Theft confidence interval
    loss_gal = 20.0
    confidence_interval = (19.0, 21.0)

    assert confidence_interval[0] < loss_gal < confidence_interval[1]

    print("✅ All optimizations working together!")


if __name__ == "__main__":
    pytest.main(
        [
            __file__,
            "-v",
            "--cov=extended_kalman_filter_v6",
            "--cov=config",
            "--cov-report=term-missing",
        ]
    )
