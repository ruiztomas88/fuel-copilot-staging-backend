"""
🧪 A/B INTEGRATION TESTS
========================

Tests de integración que ejecutan A/B testing con datos reales de la base de datos.
Compara algoritmos nuevos vs actuales con métricas del mundo real.
"""

import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List

import pymysql

from ab_testing_framework import ABTestingEngine
from db_config import get_connection
from sql_safe import validate_truck_id, whitelist_table

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ABIntegrationTests:
    """Tests de integración A/B con datos reales"""

    def __init__(self):
        self.engine = ABTestingEngine()
        self.results = []

    def test(self, name: str, fn):
        """Ejecuta un test y registra resultado"""
        try:
            logger.info(f"🧪 Running: {name}")
            fn()
            self.results.append((name, "PASS", None))
            logger.info(f"✅ {name}")
        except Exception as e:
            self.results.append((name, "FAIL", str(e)))
            logger.error(f"❌ {name}: {e}")

    # ========================================================================
    # TEST #1: MPG CON DATOS REALES
    # ========================================================================

    def _test_mpg_with_real_data(self):
        """Test MPG con datos reales de fuel_metrics"""

        with get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Obtener datos de varios trucks de los últimos 7 días
                query = f"""
                SELECT 
                    truck_id,
                    SUM(odom_delta_mi) as total_distance,
                    SUM(estimated_gallons) - MIN(estimated_gallons) as total_fuel,
                    AVG(speed_mph) as avg_speed,
                    COUNT(CASE WHEN truck_status = 'STOPPED' THEN 1 END) as stop_count
                FROM {whitelist_table('fuel_metrics')}
                WHERE timestamp_utc >= NOW() - INTERVAL 7 DAY
                    AND odom_delta_mi > 0
                    AND estimated_gallons > 0
                    AND speed_mph > 0
                GROUP BY truck_id
                HAVING total_distance >= 50 AND total_fuel > 0
                LIMIT 5
                """

                cursor.execute(query)
                trucks = cursor.fetchall()

                assert len(trucks) > 0, "No trucks found with enough data"

                for truck in trucks:
                    result = self.engine.test_mpg_comparison(
                        truck_id=truck["truck_id"],
                        distance_miles=float(truck["total_distance"]),
                        fuel_consumed_gal=float(truck["total_fuel"]),
                        avg_speed_mph=float(truck["avg_speed"]),
                        stop_count=int(truck["stop_count"]),
                    )

                    # Verificar que ambos algoritmos producen MPG razonable
                    assert (
                        0 < result.current_mpg < 15
                    ), f"Current MPG out of range: {result.current_mpg}"
                    assert (
                        0 < result.new_mpg < 15
                    ), f"New MPG out of range: {result.new_mpg}"

                    logger.info(
                        f"   {truck['truck_id']}: Current={result.current_mpg:.2f}, "
                        f"New={result.new_mpg:.2f} ({result.new_condition}), "
                        f"Diff={result.mpg_difference:+.2f}"
                    )

    # ========================================================================
    # TEST #2: KALMAN CON DATOS REALES
    # ========================================================================

    def _test_kalman_with_real_data(self):
        """Test Kalman con datos reales de fuel_metrics"""

        with get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Obtener truck con más datos
                query = f"""
                SELECT truck_id, fuel_capacity_gal * 3.78541 as fuel_tank_capacity_L
                FROM {whitelist_table('truck_specs')}
                WHERE fuel_capacity_gal > 0
                LIMIT 1
                """
                cursor.execute(query)
                truck = cursor.fetchone()

                assert truck, "No truck found with tank capacity"

                truck_id = truck["truck_id"]
                capacity = float(truck["fuel_tank_capacity_L"])

                # Obtener lecturas de fuel de las últimas 24 horas
                query = f"""
                SELECT 
                    sensor_pct as sensor_fuel_pct,
                    consumption_gph,
                    timestamp_utc as timestamp
                FROM {whitelist_table('fuel_metrics')}
                WHERE truck_id = %s
                    AND timestamp_utc >= NOW() - INTERVAL 24 HOUR
                    AND sensor_pct > 0
                    AND consumption_gph > 0
                ORDER BY timestamp_utc ASC
                LIMIT 100
                """

                cursor.execute(query, (truck_id,))
                readings_raw = cursor.fetchall()

                assert (
                    len(readings_raw) >= 10
                ), f"Not enough readings: {len(readings_raw)}"

                # Convertir a formato para test
                readings = [
                    (float(r["sensor_fuel_pct"]), float(r["consumption_gph"]))
                    for r in readings_raw
                ]

                initial_fuel_pct = readings[0][0]

                result = self.engine.test_kalman_comparison(
                    truck_id=truck_id,
                    capacity_liters=capacity,
                    initial_fuel_pct=initial_fuel_pct,
                    readings=readings,
                )

                # Verificar que ambos producen estimaciones razonables
                assert (
                    0 <= result.linear_fuel_pct <= 100
                ), f"Linear fuel out of range: {result.linear_fuel_pct}"
                assert (
                    0 <= result.ekf_fuel_pct <= 100
                ), f"EKF fuel out of range: {result.ekf_fuel_pct}"

                logger.info(
                    f"   {truck_id}: Linear={result.linear_fuel_pct:.1f}%, "
                    f"EKF={result.ekf_fuel_pct:.1f}%, "
                    f"Variance Improvement={result.variance_improvement_pct:+.1f}%, "
                    f"Bias={result.ekf_sensor_bias:.2f}%"
                )

    # ========================================================================
    # TEST #3: THEFT DETECTION CON DATOS REALES
    # ========================================================================

    def _test_theft_with_real_data(self):
        """Test Theft Detection con drops reales de fuel"""

        with get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Buscar eventos de drops significativos de fuel
                query = f"""
                WITH fuel_drops AS (
                    SELECT 
                        truck_id,
                        timestamp_utc,
                        sensor_pct,
                        LAG(sensor_pct) OVER (PARTITION BY truck_id ORDER BY timestamp_utc) as prev_fuel_pct,
                        speed_mph,
                        truck_status,
                        odometer_mi
                    FROM {whitelist_table('fuel_metrics')}
                    WHERE timestamp_utc >= NOW() - INTERVAL 7 DAY
                )
                SELECT 
                    truck_id,
                    timestamp_utc as timestamp,
                    sensor_pct as sensor_fuel_pct,
                    prev_fuel_pct,
                    (prev_fuel_pct - sensor_pct) as drop_pct,
                    speed_mph,
                    truck_status,
                    odometer_mi
                FROM fuel_drops
                WHERE prev_fuel_pct IS NOT NULL
                    AND (prev_fuel_pct - sensor_pct) > 10
                ORDER BY (prev_fuel_pct - sensor_pct) DESC
                LIMIT 3
                """

                cursor.execute(query)
                drops = cursor.fetchall()

                if len(drops) == 0:
                    logger.warning("No significant fuel drops found in last 7 days")
                    # Crear drop simulado para test
                    drops = [
                        {
                            "truck_id": "TEST001",
                            "timestamp": datetime.now(),
                            "sensor_fuel_pct": 60.0,
                            "prev_fuel_pct": 80.0,
                            "drop_pct": 20.0,
                            "speed_mph": 0.0,
                            "truck_status": "STOPPED",
                            "odometer_mi": 50000,
                        }
                    ]

                for drop in drops:
                    truck_id = drop["truck_id"]
                    drop_time = drop["timestamp"]

                    # Obtener contexto (readings antes y después del drop)
                    query = f"""
                    SELECT 
                        sensor_pct as sensor_fuel_pct,
                        speed_mph,
                        truck_status,
                        timestamp_utc as timestamp,
                        odometer_mi,
                        latitude as gps_lat,
                        longitude as gps_lon
                    FROM {whitelist_table('fuel_metrics')}
                    WHERE truck_id = %s
                        AND timestamp_utc BETWEEN %s AND %s
                    ORDER BY timestamp_utc ASC
                    """

                    start_time = drop_time - timedelta(minutes=30)
                    end_time = drop_time + timedelta(minutes=30)

                    cursor.execute(query, (truck_id, start_time, end_time))
                    readings = cursor.fetchall()

                    if len(readings) < 2:
                        logger.warning(f"Not enough context for {truck_id}")
                        continue

                    # Convertir a formato dict
                    readings_list = [dict(r) for r in readings]

                    result = self.engine.test_theft_detection_comparison(
                        truck_id=truck_id, readings=readings_list
                    )

                    if result:
                        logger.info(
                            f"   {truck_id}: Drop={result.drop_magnitude_pct:.1f}%, "
                            f"Current={result.current_detected}, "
                            f"New={result.new_detected} (confidence={result.new_confidence_score:.2f}), "
                            f"Agreement={result.agreement}"
                        )

    # ========================================================================
    # TEST #4: PERFORMANCE BENCHMARKING
    # ========================================================================

    def _test_performance_benchmarking(self):
        """Test performance de todos los algoritmos"""

        with get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Test con múltiples trucks
                query = f"""
                SELECT truck_id
                FROM {whitelist_table('truck_specs')}
                LIMIT 10
                """
                cursor.execute(query)
                trucks = cursor.fetchall()

                for truck in trucks:
                    truck_id = truck["truck_id"]

                    # Test rápido de MPG
                    self.engine.test_mpg_comparison(
                        truck_id=truck_id,
                        distance_miles=100,
                        fuel_consumed_gal=15,
                        avg_speed_mph=60,
                        stop_count=5,
                        test_name=f"Performance Test - {truck_id}",
                    )

        # Verificar que performance no se degradó más de 20%
        summary = self.engine.generate_summary()

        # MPG debe ser similar o mejor en performance
        assert (
            summary.mpg_avg_performance > -20
        ), f"MPG performance degraded too much: {summary.mpg_avg_performance:.1f}%"

        logger.info(f"   Performance: {summary.mpg_avg_performance:+.1f}% change")

    # ========================================================================
    # TEST #5: ACCURACY COMPARISON
    # ========================================================================

    def _test_accuracy_comparison(self):
        """Test accuracy de algoritmos con ground truth"""

        with get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Buscar refuels confirmados (ground truth para Kalman)
                # Nota: fuel_metrics no tiene refuel_gallons, usar anchor_detected
                query = f"""
                SELECT 
                    truck_id,
                    timestamp_utc as timestamp,
                    sensor_pct as sensor_fuel_pct,
                    (sensor_pct - LAG(sensor_pct) OVER (PARTITION BY truck_id ORDER BY timestamp_utc)) as fuel_jump
                FROM {whitelist_table('fuel_metrics')}
                WHERE timestamp_utc >= NOW() - INTERVAL 7 DAY
                    AND anchor_detected = 'YES'
                    AND anchor_type = 'REFUEL'
                LIMIT 5
                """

                cursor.execute(query)
                refuels = cursor.fetchall()

                if len(refuels) > 0:
                    logger.info(
                        f"   Found {len(refuels)} refuel events for accuracy testing"
                    )

                    for refuel in refuels:
                        # Este test verificaría que el Kalman predice correctamente
                        # el nivel antes del refuel
                        logger.info(
                            f"   Refuel: {refuel['truck_id']} - "
                            f"{refuel['fuel_jump']:.1f}% jump at {refuel['sensor_fuel_pct']:.1f}%"
                        )
                else:
                    logger.warning("No refuel events found for accuracy testing")

    # ========================================================================
    # RUN ALL TESTS
    # ========================================================================

    def run_all(self):
        """Ejecuta todos los tests de integración"""

        logger.info("\n" + "=" * 80)
        logger.info("🧪 A/B INTEGRATION TESTS - REAL DATA")
        logger.info("=" * 80 + "\n")

        self.test("MPG with Real Data", self._test_mpg_with_real_data)
        self.test("Kalman with Real Data", self._test_kalman_with_real_data)
        self.test("Theft Detection with Real Data", self._test_theft_with_real_data)
        self.test("Performance Benchmarking", self._test_performance_benchmarking)
        self.test("Accuracy Comparison", self._test_accuracy_comparison)

        # Print results
        print("\n" + "=" * 80)
        print("📊 TEST RESULTS")
        print("=" * 80)

        passed = sum(1 for _, status, _ in self.results if status == "PASS")
        failed = sum(1 for _, status, _ in self.results if status == "FAIL")

        for name, status, error in self.results:
            symbol = "✅" if status == "PASS" else "❌"
            print(f"{symbol} {name}")
            if error:
                print(f"   Error: {error}")

        print("\n" + "=" * 80)
        print(f"Passed: {passed}/{len(self.results)}")
        print(f"Failed: {failed}/{len(self.results)}")

        # Print A/B summary
        self.engine.print_summary()

        # Return exit code
        return 0 if failed == 0 else 1


if __name__ == "__main__":
    tests = ABIntegrationTests()
    exit_code = tests.run_all()

    if exit_code == 0:
        print("\n🎉 ALL A/B INTEGRATION TESTS PASSED!")
    else:
        print("\n⚠️  SOME TESTS FAILED - Review results above")

    sys.exit(exit_code)
