"""
📊 A/B MONITORING DASHBOARD
===========================

Sistema de monitoring para rastrear performance de algoritmos A/B en producción.
Ejecuta comparaciones cada X minutos y guarda métricas en base de datos.
"""

import json
import logging
import time
from dataclasses import asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pymysql

from ab_testing_framework import ABTestingEngine
from db_config import get_connection
from sql_safe import whitelist_table

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============================================================================
# DATABASE SCHEMA CREATION
# ============================================================================


def create_ab_monitoring_tables():
    """Crea tablas para almacenar resultados de A/B testing"""

    with get_connection() as conn:
        with conn.cursor() as cursor:
            # Tabla principal de monitoring
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ab_monitoring_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    test_type VARCHAR(50) NOT NULL,
                    truck_id VARCHAR(50) NOT NULL,
                    test_name VARCHAR(100),
                    
                    -- Métricas de algoritmo actual
                    current_value FLOAT,
                    current_confidence VARCHAR(20),
                    current_time_ms FLOAT,
                    
                    -- Métricas de algoritmo nuevo
                    new_value FLOAT,
                    new_metadata JSON,
                    new_time_ms FLOAT,
                    
                    -- Comparación
                    difference FLOAT,
                    percent_difference FLOAT,
                    performance_impact_pct FLOAT,
                    
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_test_type (test_type),
                    INDEX idx_truck_id (truck_id),
                    INDEX idx_timestamp (timestamp)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            )

            # Tabla de resúmenes diarios
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ab_monitoring_summary (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    date DATE NOT NULL UNIQUE,
                    
                    -- MPG Summary
                    mpg_tests INT DEFAULT 0,
                    mpg_avg_difference FLOAT,
                    mpg_avg_performance FLOAT,
                    mpg_better_count INT DEFAULT 0,
                    
                    -- Kalman Summary
                    kalman_tests INT DEFAULT 0,
                    kalman_avg_variance_improvement FLOAT,
                    kalman_bias_detected_count INT DEFAULT 0,
                    
                    -- Theft Summary
                    theft_tests INT DEFAULT 0,
                    theft_agreement_pct FLOAT,
                    theft_false_positive_reduction INT DEFAULT 0,
                    theft_avg_confidence FLOAT,
                    
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    INDEX idx_date (date)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            )

            # Tabla de alertas (cuando algoritmo nuevo es significativamente diferente)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS ab_monitoring_alerts (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    alert_type VARCHAR(50) NOT NULL,
                    severity VARCHAR(20) NOT NULL,
                    truck_id VARCHAR(50),
                    message TEXT,
                    metric_value FLOAT,
                    threshold_value FLOAT,
                    metadata JSON,
                    resolved BOOLEAN DEFAULT FALSE,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    resolved_at DATETIME,
                    INDEX idx_alert_type (alert_type),
                    INDEX idx_resolved (resolved),
                    INDEX idx_created_at (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            )

            conn.commit()
            logger.info("✅ A/B monitoring tables created")


# ============================================================================
# MONITORING ENGINE
# ============================================================================


class ABMonitoringEngine:
    """Motor de monitoring para A/B testing continuo"""

    def __init__(self, interval_minutes: int = 60):
        """
        Args:
            interval_minutes: Intervalo entre tests (default: 60 min)
        """
        self.interval_minutes = interval_minutes
        self.running = False
        self.ab_engine = ABTestingEngine()

        # Thresholds para alertas
        self.THRESHOLDS = {
            "mpg_difference_pct": 10.0,  # Alert si MPG difiere >10%
            "kalman_variance_improvement": 20.0,  # Alert si mejora >20%
            "theft_confidence_high": 0.9,  # Alert si confianza >90%
            "performance_degradation": 50.0,  # Alert si performance degrada >50%
        }

    # ========================================================================
    # LOGGING FUNCTIONS
    # ========================================================================

    def log_mpg_test(self, result):
        """Guarda resultado de test MPG en DB"""

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ab_monitoring_log (
                        test_type, truck_id, test_name,
                        current_value, current_confidence, current_time_ms,
                        new_value, new_metadata, new_time_ms,
                        difference, percent_difference, performance_impact_pct
                    ) VALUES (
                        'MPG', %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    )
                """,
                    (
                        result.truck_id,
                        result.test_name,
                        result.current_mpg,
                        result.current_confidence,
                        result.current_time_ms,
                        result.new_mpg,
                        json.dumps(
                            {
                                "condition": result.new_condition,
                                "window_miles": result.new_window_miles,
                            }
                        ),
                        result.new_time_ms,
                        result.mpg_difference,
                        result.percent_difference,
                        result.performance_improvement_pct,
                    ),
                )
                conn.commit()

        # Check para alertas
        self._check_mpg_alerts(result)

    def log_kalman_test(self, result):
        """Guarda resultado de test Kalman en DB"""

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ab_monitoring_log (
                        test_type, truck_id, test_name,
                        current_value, current_confidence, current_time_ms,
                        new_value, new_metadata, new_time_ms,
                        difference, percent_difference, performance_impact_pct
                    ) VALUES (
                        'KALMAN', %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    )
                """,
                    (
                        result.truck_id,
                        result.test_name,
                        result.linear_fuel_pct,
                        str(result.linear_variance),
                        result.linear_time_ms,
                        result.ekf_fuel_pct,
                        json.dumps(
                            {
                                "consumption_rate": result.ekf_consumption_rate,
                                "sensor_bias": result.ekf_sensor_bias,
                                "variance": result.ekf_variance,
                                "bias_detected": result.bias_detected,
                            }
                        ),
                        result.ekf_time_ms,
                        result.fuel_difference_pct,
                        result.variance_improvement_pct,
                        result.performance_impact_pct,
                    ),
                )
                conn.commit()

        self._check_kalman_alerts(result)

    def log_theft_test(self, result):
        """Guarda resultado de test Theft Detection en DB"""

        if not result:
            return

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ab_monitoring_log (
                        test_type, truck_id, test_name,
                        current_value, current_confidence, current_time_ms,
                        new_value, new_metadata, new_time_ms,
                        difference, percent_difference, performance_impact_pct
                    ) VALUES (
                        'THEFT', %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s
                    )
                """,
                    (
                        result.truck_id,
                        result.test_name,
                        1.0 if result.current_detected else 0.0,
                        result.current_classification,
                        result.current_time_ms,
                        1.0 if result.new_detected else 0.0,
                        json.dumps(
                            {
                                "classification": result.new_classification,
                                "confidence": result.new_confidence_score,
                                "factors": result.new_factors,
                                "agreement": result.agreement,
                            }
                        ),
                        result.new_time_ms,
                        result.drop_magnitude_pct,
                        result.new_confidence_score * 100,
                        result.performance_impact_pct,
                    ),
                )
                conn.commit()

        self._check_theft_alerts(result)

    # ========================================================================
    # ALERT CHECKING
    # ========================================================================

    def _check_mpg_alerts(self, result):
        """Verifica si resultado MPG requiere alerta"""

        # Alert si diferencia es muy grande
        if abs(result.percent_difference) > self.THRESHOLDS["mpg_difference_pct"]:
            self._create_alert(
                alert_type="MPG_LARGE_DIFFERENCE",
                severity="WARNING",
                truck_id=result.truck_id,
                message=f"MPG difference {result.percent_difference:+.1f}% exceeds threshold",
                metric_value=abs(result.percent_difference),
                threshold_value=self.THRESHOLDS["mpg_difference_pct"],
                metadata={
                    "current_mpg": result.current_mpg,
                    "new_mpg": result.new_mpg,
                    "condition": result.new_condition,
                },
            )

        # Alert si performance se degrada mucho
        if (
            result.performance_improvement_pct
            < -self.THRESHOLDS["performance_degradation"]
        ):
            self._create_alert(
                alert_type="MPG_PERFORMANCE_DEGRADATION",
                severity="CRITICAL",
                truck_id=result.truck_id,
                message=f"Performance degraded by {abs(result.performance_improvement_pct):.1f}%",
                metric_value=abs(result.performance_improvement_pct),
                threshold_value=self.THRESHOLDS["performance_degradation"],
                metadata={"test_name": result.test_name},
            )

    def _check_kalman_alerts(self, result):
        """Verifica si resultado Kalman requiere alerta"""

        # Alert si detecta bias significativo
        if result.bias_detected:
            self._create_alert(
                alert_type="KALMAN_BIAS_DETECTED",
                severity="INFO",
                truck_id=result.truck_id,
                message=f"Sensor bias detected: {result.ekf_sensor_bias:+.2f}%",
                metric_value=abs(result.ekf_sensor_bias),
                threshold_value=1.0,
                metadata={
                    "linear_fuel": result.linear_fuel_pct,
                    "ekf_fuel": result.ekf_fuel_pct,
                },
            )

        # Alert si variance mejora significativamente
        if (
            result.variance_improvement_pct
            > self.THRESHOLDS["kalman_variance_improvement"]
        ):
            self._create_alert(
                alert_type="KALMAN_VARIANCE_IMPROVEMENT",
                severity="INFO",
                truck_id=result.truck_id,
                message=f"Variance improved by {result.variance_improvement_pct:.1f}%",
                metric_value=result.variance_improvement_pct,
                threshold_value=self.THRESHOLDS["kalman_variance_improvement"],
                metadata={"test_name": result.test_name},
            )

    def _check_theft_alerts(self, result):
        """Verifica si resultado Theft requiere alerta"""

        # Alert si nuevo detector tiene confianza muy alta
        if (
            result.new_detected
            and result.new_confidence_score > self.THRESHOLDS["theft_confidence_high"]
        ):
            self._create_alert(
                alert_type="THEFT_HIGH_CONFIDENCE",
                severity="CRITICAL",
                truck_id=result.truck_id,
                message=f"High confidence theft detected: {result.new_confidence_score:.2f}",
                metric_value=result.new_confidence_score,
                threshold_value=self.THRESHOLDS["theft_confidence_high"],
                metadata={
                    "drop_magnitude": result.drop_magnitude_pct,
                    "classification": result.new_classification,
                    "factors": result.new_factors,
                },
            )

        # Alert si detectores no están de acuerdo
        if not result.agreement:
            self._create_alert(
                alert_type="THEFT_DISAGREEMENT",
                severity="WARNING",
                truck_id=result.truck_id,
                message=f"Detectors disagree: Current={result.current_detected}, New={result.new_detected}",
                metric_value=result.drop_magnitude_pct,
                threshold_value=0.0,
                metadata={
                    "current_classification": result.current_classification,
                    "new_classification": result.new_classification,
                    "new_confidence": result.new_confidence_score,
                },
            )

    def _create_alert(
        self,
        alert_type: str,
        severity: str,
        truck_id: str,
        message: str,
        metric_value: float,
        threshold_value: float,
        metadata: Dict,
    ):
        """Crea una alerta en DB"""

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ab_monitoring_alerts (
                        alert_type, severity, truck_id, message,
                        metric_value, threshold_value, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                    (
                        alert_type,
                        severity,
                        truck_id,
                        message,
                        metric_value,
                        threshold_value,
                        json.dumps(metadata),
                    ),
                )
                conn.commit()

        logger.warning(f"🚨 ALERT: [{severity}] {alert_type} - {message}")

    # ========================================================================
    # DAILY SUMMARY
    # ========================================================================

    def update_daily_summary(self):
        """Actualiza resumen diario con resultados del día"""

        summary = self.ab_engine.generate_summary()
        today = datetime.now().date()

        with get_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ab_monitoring_summary (
                        date,
                        mpg_tests, mpg_avg_difference, mpg_avg_performance, mpg_better_count,
                        kalman_tests, kalman_avg_variance_improvement, kalman_bias_detected_count,
                        theft_tests, theft_agreement_pct, theft_false_positive_reduction, theft_avg_confidence
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON DUPLICATE KEY UPDATE
                        mpg_tests = mpg_tests + VALUES(mpg_tests),
                        mpg_avg_difference = (mpg_avg_difference + VALUES(mpg_avg_difference)) / 2,
                        mpg_avg_performance = (mpg_avg_performance + VALUES(mpg_avg_performance)) / 2,
                        mpg_better_count = mpg_better_count + VALUES(mpg_better_count),
                        kalman_tests = kalman_tests + VALUES(kalman_tests),
                        kalman_avg_variance_improvement = (kalman_avg_variance_improvement + VALUES(kalman_avg_variance_improvement)) / 2,
                        kalman_bias_detected_count = kalman_bias_detected_count + VALUES(kalman_bias_detected_count),
                        theft_tests = theft_tests + VALUES(theft_tests),
                        theft_agreement_pct = (theft_agreement_pct + VALUES(theft_agreement_pct)) / 2,
                        theft_false_positive_reduction = theft_false_positive_reduction + VALUES(theft_false_positive_reduction),
                        theft_avg_confidence = (theft_avg_confidence + VALUES(theft_avg_confidence)) / 2
                """,
                    (
                        today,
                        summary.mpg_tests,
                        summary.mpg_avg_difference,
                        summary.mpg_avg_performance,
                        summary.mpg_better_count,
                        summary.kalman_tests,
                        summary.kalman_avg_variance_improvement,
                        summary.kalman_bias_detected_count,
                        summary.theft_tests,
                        summary.theft_agreement_pct,
                        summary.theft_false_positive_reduction,
                        summary.theft_avg_confidence,
                    ),
                )
                conn.commit()

        logger.info(f"✅ Daily summary updated for {today}")

    # ========================================================================
    # RUN ONE CYCLE
    # ========================================================================

    def run_one_cycle(self):
        """Ejecuta un ciclo de monitoring"""

        logger.info(f"\n{'='*80}")
        logger.info(
            f"🧪 A/B MONITORING CYCLE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.info(f"{'='*80}\n")

        # Reset engine para nuevo ciclo
        self.ab_engine = ABTestingEngine()

        with get_connection() as conn:
            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                # Test MPG con trucks activos
                query = f"""
                SELECT 
                    truck_id,
                    SUM(odom_delta_mi) as distance,
                    SUM(fuel_consumed_gal) as fuel,
                    AVG(speed_mph) as speed,
                    COUNT(CASE WHEN truck_status = 'STOPPED' THEN 1 END) as stops
                FROM {whitelist_table('fuel_metrics')}
                WHERE timestamp >= NOW() - INTERVAL {self.interval_minutes} MINUTE
                    AND odom_delta_mi > 0
                    AND fuel_consumed_gal > 0
                GROUP BY truck_id
                HAVING distance >= 5
                LIMIT 5
                """

                cursor.execute(query)
                trucks = cursor.fetchall()

                logger.info(f"📊 Testing {len(trucks)} trucks with recent activity")

                for truck in trucks:
                    # MPG Test
                    result = self.ab_engine.test_mpg_comparison(
                        truck_id=truck["truck_id"],
                        distance_miles=float(truck["distance"]),
                        fuel_consumed_gal=float(truck["fuel"]),
                        avg_speed_mph=float(truck["speed"]),
                        stop_count=int(truck["stops"]),
                        test_name=f"Monitoring Cycle {datetime.now().hour}:00",
                    )

                    self.log_mpg_test(result)
                    logger.info(
                        f"   MPG {truck['truck_id']}: {result.current_mpg:.2f} → "
                        f"{result.new_mpg:.2f} ({result.new_condition})"
                    )

        # Update daily summary
        self.update_daily_summary()

        logger.info(f"\n✅ Monitoring cycle complete\n")

    # ========================================================================
    # CONTINUOUS MONITORING
    # ========================================================================

    def start_monitoring(self):
        """Inicia monitoring continuo"""

        logger.info(
            f"🚀 Starting A/B Monitoring (interval: {self.interval_minutes} min)"
        )
        self.running = True

        try:
            while self.running:
                self.run_one_cycle()

                logger.info(f"⏸️  Sleeping for {self.interval_minutes} minutes...")
                time.sleep(self.interval_minutes * 60)

        except KeyboardInterrupt:
            logger.info("\n⏹️  Monitoring stopped by user")
            self.running = False

        except Exception as e:
            logger.error(f"❌ Monitoring error: {e}")
            raise

    def stop_monitoring(self):
        """Detiene monitoring"""
        self.running = False
        logger.info("⏹️  Monitoring stop requested")


# ============================================================================
# REPORTING
# ============================================================================


def generate_monitoring_report(days: int = 7):
    """Genera reporte de monitoring de últimos N días"""

    print(f"\n{'='*80}")
    print(f"📊 A/B MONITORING REPORT - Last {days} Days")
    print(f"{'='*80}\n")

    with get_connection() as conn:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            # Summary por día
            cursor.execute(
                f"""
                SELECT 
                    date,
                    mpg_tests,
                    mpg_avg_difference,
                    kalman_tests,
                    kalman_avg_variance_improvement,
                    theft_tests,
                    theft_agreement_pct
                FROM ab_monitoring_summary
                WHERE date >= CURDATE() - INTERVAL {days} DAY
                ORDER BY date DESC
            """
            )

            daily_summaries = cursor.fetchall()

            if daily_summaries:
                print("📅 Daily Summaries:")
                for row in daily_summaries:
                    print(f"\n  {row['date']}:")
                    print(
                        f"    MPG Tests: {row['mpg_tests']} (avg diff: {row['mpg_avg_difference']:+.2f})"
                    )
                    print(
                        f"    Kalman Tests: {row['kalman_tests']} (variance: {row['kalman_avg_variance_improvement']:+.1f}%)"
                    )
                    print(
                        f"    Theft Tests: {row['theft_tests']} (agreement: {row['theft_agreement_pct']:.1f}%)"
                    )

            # Alertas activas
            cursor.execute(
                """
                SELECT 
                    alert_type,
                    severity,
                    COUNT(*) as count,
                    AVG(metric_value) as avg_value
                FROM ab_monitoring_alerts
                WHERE created_at >= NOW() - INTERVAL %s DAY
                    AND resolved = FALSE
                GROUP BY alert_type, severity
                ORDER BY severity DESC, count DESC
            """,
                (days,),
            )

            alerts = cursor.fetchall()

            if alerts:
                print(f"\n🚨 Active Alerts ({sum(a['count'] for a in alerts)} total):")
                for alert in alerts:
                    print(
                        f"  [{alert['severity']}] {alert['alert_type']}: {alert['count']} occurrences (avg: {alert['avg_value']:.2f})"
                    )
            else:
                print("\n✅ No active alerts")

    print(f"\n{'='*80}\n")


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="A/B Monitoring System")
    parser.add_argument("--setup", action="store_true", help="Create monitoring tables")
    parser.add_argument(
        "--monitor", action="store_true", help="Start continuous monitoring"
    )
    parser.add_argument("--cycle", action="store_true", help="Run one monitoring cycle")
    parser.add_argument(
        "--report", type=int, metavar="DAYS", help="Generate report for last N days"
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Monitoring interval in minutes (default: 60)",
    )

    args = parser.parse_args()

    if args.setup:
        create_ab_monitoring_tables()

    elif args.monitor:
        engine = ABMonitoringEngine(interval_minutes=args.interval)
        engine.start_monitoring()

    elif args.cycle:
        engine = ABMonitoringEngine()
        engine.run_one_cycle()

    elif args.report:
        generate_monitoring_report(days=args.report)

    else:
        parser.print_help()
        print("\nExamples:")
        print("  python ab_monitoring.py --setup              # Create tables")
        print("  python ab_monitoring.py --cycle              # Run one cycle")
        print(
            "  python ab_monitoring.py --monitor            # Start continuous (60 min)"
        )
        print("  python ab_monitoring.py --monitor --interval 30  # Every 30 min")
        print("  python ab_monitoring.py --report 7           # Report last 7 days")
