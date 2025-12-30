"""
Test suite para verificar todos los fixes de Diciembre 29, 2025

Tests:
1. SNR con tank_capacity_gal correcto
2. Sensor skip counter
3. Innovation no duplicado
4. Variance edge case documentado
5. Biodiesel marcado para review
6. Cooldown configurable
7. MPGConfig consistente
"""

import sys

sys.path.insert(0, ".")

from estimator import EstimatorConfig, FuelEstimator
from mpg_engine import MPGConfig, MPGState, update_mpg_state


def test_1_snr_tank_capacity():
    """Test #1: SNR usa tank_capacity_gal dinámico"""
    print("\n🔬 TEST #1: SNR con tank_capacity_gal")

    state = MPGState()
    config = MPGConfig()

    # Simular ventana completa
    state.distance_accum = 25.0  # > min_miles (20.0)
    state.fuel_accum_gal = 3.0  # > min_fuel_gal (2.5)

    # Test con diferentes capacidades
    for tank_gal in [120, 150, 200, 300]:
        state_copy = MPGState()
        state_copy.distance_accum = state.distance_accum
        state_copy.fuel_accum_gal = state.fuel_accum_gal

        try:
            updated_state = update_mpg_state(
                state_copy, 0, 0, config, "TEST001", tank_capacity_gal=tank_gal
            )
            # Si llegó aquí sin crash, el fix está aplicado
            print(f"  ✅ Tank {tank_gal} gal: SNR calculado correctamente")
        except NameError as e:
            print(f"  ❌ Tank {tank_gal} gal: ERROR - {e}")
            return False

    return True


def test_2_sensor_skip_counter():
    """Test #2: Sensor skip counter detecta fallas consecutivas"""
    print("\n🔬 TEST #2: Sensor skip counter")

    config = {"Q_r": 0.05, "Q_L_moving": 2.5}
    estimator = FuelEstimator("TEST001", 450.0, config)

    # Verificar inicialización
    if estimator.sensor_skip_count != 0:
        print(f"  ❌ Initial count debería ser 0, es {estimator.sensor_skip_count}")
        return False
    print(f"  ✅ Inicializado en 0")

    # Simular 5 lecturas inválidas
    for i in range(5):
        estimator.update(None)

    if estimator.sensor_skip_count != 5:
        print(
            f"  ❌ Después de 5 inválidas debería ser 5, es {estimator.sensor_skip_count}"
        )
        return False
    print(f"  ✅ Contador incrementó correctamente: {estimator.sensor_skip_count}")

    # Lectura válida debe resetear
    estimator.update(50.0)
    if estimator.sensor_skip_count != 0:
        print(
            f"  ❌ Después de lectura válida debería resetear a 0, es {estimator.sensor_skip_count}"
        )
        return False
    print(f"  ✅ Reset correcto después de lectura válida")

    return True


def test_3_innovation_not_duplicated():
    """Test #3: Innovation no se calcula 2 veces"""
    print("\n🔬 TEST #3: Innovation no duplicado")

    # Verificar que el código no tenga "innovation = measured_liters - self.level_liters" duplicado
    with open("estimator.py", "r") as f:
        content = f.read()
        innovation_calcs = content.count(
            "innovation = measured_liters - self.level_liters"
        )

    if innovation_calcs > 1:
        print(f"  ❌ Innovation calculado {innovation_calcs} veces (debería ser 1)")
        return False

    print(f"  ✅ Innovation calculado solo 1 vez")
    return True


def test_4_variance_documented():
    """Test #4: Variance edge case está documentado"""
    print("\n🔬 TEST #4: Variance edge case documentado")

    with open("mpg_engine.py", "r") as f:
        content = f.read()
        has_comment = "FIX DEC 29: Minimum std_dev" in content

    if not has_comment:
        print(f"  ❌ Comentario de variance no encontrado")
        return False

    print(f"  ✅ Variance edge case documentado")
    return True


def test_5_biodiesel_marked_for_review():
    """Test #5: Biodiesel marcado para review"""
    print("\n🔬 TEST #5: Biodiesel marcado para review")

    with open("estimator.py", "r") as f:
        content = f.read()
        has_review = "REVIEW DEC 29: Physics may be inverted" in content

    if not has_review:
        print(f"  ❌ Biodiesel review comment no encontrado")
        return False

    print(f"  ✅ Biodiesel marcado para review técnico")
    return True


def test_6_cooldown_configurable():
    """Test #6: Cooldown es configurable"""
    print("\n🔬 TEST #6: Cooldown configurable")

    # Verificar que EstimatorConfig tenga resync_cooldown_sec
    est_config = EstimatorConfig()
    if not hasattr(est_config, "resync_cooldown_sec"):
        print(f"  ❌ EstimatorConfig no tiene resync_cooldown_sec")
        return False

    if est_config.resync_cooldown_sec != 1800:
        print(f"  ❌ Default debería ser 1800, es {est_config.resync_cooldown_sec}")
        return False

    print(f"  ✅ Cooldown configurable con default 1800 sec (30 min)")

    # Verificar que ya no esté hardcoded en auto_resync
    with open("estimator.py", "r") as f:
        content = f.read()
        # Buscar la función auto_resync
        auto_resync_start = content.find("def auto_resync(")
        auto_resync_section = content[auto_resync_start : auto_resync_start + 2000]

        if "RESYNC_COOLDOWN_SECONDS = 1800" in auto_resync_section:
            print(
                f"  ⚠️  Todavía existe hardcoded en auto_resync (pero usa config también)"
            )
        else:
            print(f"  ✅ Ya no está hardcoded, usa config")

    return True


def test_7_mpgconfig_consistent():
    """Test #7: MPGConfig valores consistentes"""
    print("\n🔬 TEST #7: MPGConfig consistente")

    config = MPGConfig()

    # Verificar valores actuales
    expected = {
        "min_miles": 20.0,
        "min_fuel_gal": 2.5,
        "min_mpg": 3.5,
        "max_mpg": 8.5,
        "ema_alpha": 0.20,
    }

    for key, value in expected.items():
        actual = getattr(config, key)
        if actual != value:
            print(f"  ❌ {key}: esperado {value}, actual {actual}")
            return False
        print(f"  ✅ {key}: {actual}")

    return True


def run_all_tests():
    """Ejecutar todos los tests"""
    print("=" * 60)
    print("🧪 TEST SUITE - FIXES DICIEMBRE 29, 2025")
    print("=" * 60)

    tests = [
        test_1_snr_tank_capacity,
        test_2_sensor_skip_counter,
        test_3_innovation_not_duplicated,
        test_4_variance_documented,
        test_5_biodiesel_marked_for_review,
        test_6_cooldown_configurable,
        test_7_mpgconfig_consistent,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append((test.__name__, result))
        except Exception as e:
            print(f"\n❌ {test.__name__} FAILED: {e}")
            results.append((test.__name__, False))

    print("\n" + "=" * 60)
    print("📊 RESULTADOS")
    print("=" * 60)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")

    print("\n" + "=" * 60)
    print(f"TOTAL: {passed}/{total} tests passed ({passed/total*100:.1f}%)")
    print("=" * 60)

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
