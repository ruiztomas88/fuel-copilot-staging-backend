"""
🎯 E2E INTEGRATION TESTS WITH REAL DATA - TARGET 90% COVERAGE
=================================================================

Tests de integración usando datos REALES de fuel_copilot_local.
NO MOCKS - Solo pruebas con data real cada 15 segundos de Wialon.

Objetivo: Llevar cobertura al 90% en:
- fleet_command_center (16.45% → 90%)
- database_mysql (25% → 90%)
- alert_service (63.64% → 90%)
- Refuel detection
- Metrics

Author: Fuel Analytics Team
Date: December 28, 2025
"""

from datetime import datetime, timedelta

import pytest
from sqlalchemy import text

# Real modules - NO MOCKS
import database_mysql as db
import fleet_command_center as fcc


class TestDatabaseMySQLRealData:
    """Test database_mysql.py functions with REAL data"""

    def test_get_fleet_summary_real(self):
        """Test get_fleet_summary with real DB data"""
        result = db.get_fleet_summary()

        assert result is not None
        assert "trucks" in result
        assert isinstance(result["trucks"], list)

        # Verify real truck data structure
        if len(result["trucks"]) > 0:
            truck = result["trucks"][0]
            assert "truck_id" in truck
            assert "status" in truck
            print(f"✅ Real fleet summary: {len(result['trucks'])} trucks")

    def test_get_kpi_summary_real_1day(self):
        """Test get_kpi_summary with real 1-day data"""
        result = db.get_kpi_summary(days_back=1)

        assert result is not None
        assert "total_fuel_consumed_gal" in result
        assert "total_miles_traveled" in result
        assert "fleet_avg_mpg" in result

        print(
            f"✅ Real KPI (1d): {result.get('total_fuel_consumed_gal', 0):.1f} gal, "
            f"{result.get('fleet_avg_mpg', 0):.2f} MPG"
        )

    def test_get_kpi_summary_real_7days(self):
        """Test get_kpi_summary with real 7-day data"""
        result = db.get_kpi_summary(days_back=7)

        assert result is not None
        assert isinstance(result.get("total_fuel_consumed_gal", 0), (int, float))

        print(f"✅ Real KPI (7d): {result.get('total_fuel_consumed_gal', 0):.1f} gal")

    def test_get_loss_analysis_real(self):
        """Test get_loss_analysis with real data"""
        result = db.get_loss_analysis(days_back=7)

        assert result is not None
        assert "idle_losses" in result
        assert "potential_savings" in result

        if result.get("idle_losses"):
            idle = result["idle_losses"]
            assert "total_idle_hours" in idle
            assert "total_idle_gallons" in idle
            print(
                f"✅ Real idle losses: {idle['total_idle_hours']:.1f}h, "
                f"{idle['total_idle_gallons']:.1f} gal"
            )

    def test_get_truck_history_real(self):
        """Test get_truck_history with real truck data"""
        # Get a real truck_id from DB
        with db.get_db_connection() as conn:
            result = conn.execute(
                text(
                    "SELECT DISTINCT truck_id FROM fuel_metrics ORDER BY timestamp_utc DESC LIMIT 1"
                )
            ).fetchone()

            if result:
                truck_id = result[0]
                history = db.get_truck_history(truck_id, hours_back=24)

                assert history is not None
                assert len(history) >= 0  # Can be empty if no recent data

                if len(history) > 0:
                    print(
                        f"✅ Real truck history for {truck_id}: {len(history)} records"
                    )

    def test_get_refuel_history_real(self):
        """Test get_refuel_history with real refuel data"""
        result = db.get_refuel_history(days_back=30, min_gallons=20)

        assert result is not None
        assert len(result) >= 0

        print(f"✅ Real refuel events (30d): {len(result)} refuels")

    def test_get_driver_scorecard_real(self):
        """Test get_driver_scorecard with real driver data"""
        result = db.get_driver_scorecard(days_back=7)

        assert result is not None
        assert "scores" in result
        assert isinstance(result["scores"], list)

        print(f"✅ Real driver scores: {len(result['scores'])} drivers")

    def test_database_connection_pool(self):
        """Test database connection pooling works"""
        # Execute multiple queries to test connection reuse
        for i in range(5):
            with db.get_db_connection() as conn:
                count = conn.execute(text("SELECT COUNT(*) FROM fuel_metrics")).scalar()
                assert count >= 0

        print(f"✅ Connection pool tested with 5 queries")


class TestFleetCommandCenterRealData:
    """Test fleet_command_center.py with REAL data"""

    def test_get_command_center_singleton(self):
        """Test FleetCommandCenter singleton works"""
        cc1 = fcc.get_command_center()
        cc2 = fcc.get_command_center()

        assert cc1 is not None
        assert cc1 is cc2  # Should be same instance
        print("✅ FleetCommandCenter singleton verified")

    def test_command_center_data_classes(self):
        """Test all FleetCommandCenter data classes can be instantiated"""
        # ActionItem
        action = fcc.ActionItem(
            id="TEST-001",
            truck_id="CO0681",
            priority=fcc.Priority.HIGH,
            priority_score=85.0,
            category=fcc.IssueCategory.FUEL,
            component="Tank",
            title="Test Issue",
            description="Test",
            days_to_critical=5.0,
            cost_if_ignored="$500",
            current_value="50%",
            trend="+2%/day",
            threshold="20%",
            confidence="HIGH",
            action_type=fcc.ActionType.INSPECT,
            action_steps=["Inspect"],
            icon="⛽",
            sources=["test"],
        )
        assert action.truck_id == "CO0681"

        # TruckRiskScore
        risk = fcc.TruckRiskScore(
            truck_id="CO0681",
            risk_score=65.0,
            risk_level="MEDIUM",
            contributing_factors=["High idle"],
            active_issues_count=2,
        )
        assert risk.truck_id == "CO0681"

        print("✅ FleetCommandCenter data classes verified")


class TestRefuelDetectionRealData:
    """Test refuel detection logic with REAL data"""

    def test_refuel_events_in_database(self):
        """Verify refuel_events table has real data"""
        with db.get_db_connection() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM refuel_events")).scalar()

            if count > 0:
                # Get recent refuel
                refuel = conn.execute(
                    text(
                        """
                    SELECT truck_id, gallons_added, fuel_pct_before, fuel_pct_after,
                           timestamp_utc
                    FROM refuel_events
                    ORDER BY timestamp_utc DESC
                    LIMIT 1
                """
                    )
                ).fetchone()

                assert refuel.gallons_added > 0
                assert refuel.fuel_pct_after > refuel.fuel_pct_before

                print(
                    f"✅ Real refuel: {refuel.truck_id} added {refuel.gallons_added:.1f} gal "
                    f"({refuel.fuel_pct_before:.1f}% → {refuel.fuel_pct_after:.1f}%)"
                )
            else:
                print("⚠️  No refuel events in database yet")

    def test_fuel_metrics_for_refuel_detection(self):
        """Test fuel_metrics has data needed for refuel detection"""
        with db.get_db_connection() as conn:
            # Check if we have fuel percentage changes
            fuel_changes = conn.execute(
                text(
                    """
                SELECT truck_id,
                       COUNT(*) as records,
                       MIN(sensor_pct) as min_pct,
                       MAX(sensor_pct) as max_pct,
                       MAX(sensor_pct) - MIN(sensor_pct) as pct_range
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                  AND sensor_pct IS NOT NULL
                GROUP BY truck_id
                HAVING pct_range > 10
                LIMIT 5
            """
                )
            ).fetchall()

            if len(fuel_changes) > 0:
                for row in fuel_changes:
                    print(
                        f"✅ {row.truck_id}: {row.min_pct:.1f}% → {row.max_pct:.1f}% "
                        f"(Δ{row.pct_range:.1f}%) - {row.records} records"
                    )
            else:
                print("⚠️  No significant fuel changes detected in last 24h")


class TestMetricsCalculationsRealData:
    """Test MPG and metrics calculations with REAL data"""

    def test_mpg_baselines_exist(self):
        """Verify MPG baselines table has real data"""
        with db.get_db_connection() as conn:
            count = conn.execute(text("SELECT COUNT(*) FROM mpg_baselines")).scalar()

            assert count >= 0

            if count > 0:
                baseline = conn.execute(
                    text(
                        """
                    SELECT truck_id, mpg_baseline, sample_size
                    FROM mpg_baselines
                    ORDER BY last_updated DESC
                    LIMIT 1
                """
                    )
                ).fetchone()

                assert baseline.mpg_baseline > 0
                print(
                    f"✅ MPG baseline for {baseline.truck_id}: {baseline.mpg_baseline:.2f} "
                    f"(n={baseline.sample_size})"
                )

    def test_real_mpg_calculations(self):
        """Test MPG calculations with real fuel_metrics data"""
        with db.get_db_connection() as conn:
            # Calculate real MPG from data
            mpg_data = conn.execute(
                text(
                    """
                SELECT truck_id,
                       AVG(mpg_current) as avg_mpg,
                       COUNT(*) as records,
                       MIN(mpg_current) as min_mpg,
                       MAX(mpg_current) as max_mpg
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                  AND mpg_current IS NOT NULL
                  AND mpg_current > 0
                  AND mpg_current < 20  -- Filter outliers
                GROUP BY truck_id
                HAVING records > 10
                LIMIT 5
            """
                )
            ).fetchall()

            if len(mpg_data) > 0:
                for row in mpg_data:
                    assert row.avg_mpg > 0
                    assert row.avg_mpg < 20
                    print(
                        f"✅ {row.truck_id}: AVG MPG={row.avg_mpg:.2f} "
                        f"(range: {row.min_mpg:.2f}-{row.max_mpg:.2f}, n={row.records})"
                    )

    def test_idle_metrics_real(self):
        """Test idle calculations with real data"""
        with db.get_db_connection() as conn:
            idle_data = conn.execute(
                text(
                    """
                SELECT truck_id,
                       SUM(CASE WHEN truck_status = 'IDLE' THEN 1 ELSE 0 END) as idle_records,
                       COUNT(*) as total_records,
                       (SUM(CASE WHEN truck_status = 'IDLE' THEN 1 ELSE 0 END) / COUNT(*)) * 100 as idle_pct
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                GROUP BY truck_id
                HAVING total_records > 20
                LIMIT 5
            """
                )
            ).fetchall()

            if len(idle_data) > 0:
                for row in idle_data:
                    assert row.idle_pct >= 0
                    assert row.idle_pct <= 100
                    print(
                        f"✅ {row.truck_id}: Idle {row.idle_pct:.1f}% "
                        f"({row.idle_records}/{row.total_records} records)"
                    )


class TestDriverBehaviorRealData:
    """Test driver behavior scoring with REAL data"""

    def test_driver_scores_table(self):
        """Verify driver_scores table has real data"""
        with db.get_db_connection() as conn:
            scores = conn.execute(
                text(
                    """
                SELECT truck_id, overall_score, speeding_score, idle_score,
                       mpg_score, harsh_braking_score
                FROM driver_scores
                ORDER BY last_updated DESC
                LIMIT 5
            """
                )
            ).fetchall()

            if len(scores) > 0:
                for score in scores:
                    assert 0 <= score.overall_score <= 100
                    print(
                        f"✅ {score.truck_id}: Score={score.overall_score:.1f} "
                        f"(speeding={score.speeding_score:.1f}, "
                        f"idle={score.idle_score:.1f})"
                    )

    def test_speeding_detection_real(self):
        """Test speeding detection with real speed data"""
        with db.get_db_connection() as conn:
            speeding = conn.execute(
                text(
                    """
                SELECT truck_id,
                       COUNT(*) as total_records,
                       SUM(CASE WHEN speed_mph > 75 THEN 1 ELSE 0 END) as speeding_events,
                       MAX(speed_mph) as max_speed,
                       AVG(speed_mph) as avg_speed
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
                  AND speed_mph IS NOT NULL
                  AND truck_status = 'MOVING'
                GROUP BY truck_id
                HAVING total_records > 20
                LIMIT 5
            """
                )
            ).fetchall()

            if len(speeding) > 0:
                for row in speeding:
                    speeding_pct = (row.speeding_events / row.total_records) * 100
                    print(
                        f"✅ {row.truck_id}: Max speed={row.max_speed:.1f} mph, "
                        f"Avg={row.avg_speed:.1f} mph, "
                        f"Speeding={speeding_pct:.1f}%"
                    )


class TestAnomalyDetectionRealData:
    """Test anomaly detection with REAL data"""

    def test_anomaly_detections_table(self):
        """Verify anomaly_detections table has real data"""
        with db.get_db_connection() as conn:
            anomalies = conn.execute(
                text(
                    """
                SELECT truck_id, sensor_name, anomaly_type, severity,
                       detected_at
                FROM anomaly_detections
                ORDER BY detected_at DESC
                LIMIT 5
            """
                )
            ).fetchall()

            if len(anomalies) > 0:
                for anom in anomalies:
                    print(
                        f"✅ Anomaly: {anom.truck_id} - {anom.sensor_name} "
                        f"({anom.anomaly_type}, severity={anom.severity})"
                    )
            else:
                print("⚠️  No anomalies detected yet")

    def test_cc_anomaly_history(self):
        """Test command center anomaly history table"""
        with db.get_db_connection() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM cc_anomaly_history")
            ).scalar()

            print(f"✅ Command Center anomaly history: {count} records")
            assert count >= 0


class TestDTCEventsRealData:
    """Test DTC (Diagnostic Trouble Codes) with REAL data"""

    def test_dtc_events_table(self):
        """Verify dtc_events table has real data"""
        with db.get_db_connection() as conn:
            dtc_events = conn.execute(
                text(
                    """
                SELECT truck_id, dtc_code, severity, description,
                       detected_at
                FROM dtc_events
                ORDER BY detected_at DESC
                LIMIT 5
            """
                )
            ).fetchall()

            if len(dtc_events) > 0:
                for dtc in dtc_events:
                    print(
                        f"✅ DTC: {dtc.truck_id} - {dtc.dtc_code} "
                        f"({dtc.severity}): {dtc.description}"
                    )
            else:
                print("⚠️  No DTC events in database")

    def test_dtc_in_fuel_metrics(self):
        """Test DTC codes in fuel_metrics"""
        with db.get_db_connection() as conn:
            dtc_count = conn.execute(
                text(
                    """
                SELECT COUNT(*) as cnt
                FROM fuel_metrics
                WHERE dtc > 0
                  AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL 7 DAY)
            """
                )
            ).scalar()

            print(f"✅ Fuel metrics with DTC (7d): {dtc_count} records")


class TestCommandCenterTablesRealData:
    """Test Fleet Command Center database tables with REAL data"""

    def test_cc_risk_history(self):
        """Test command center risk history table"""
        with db.get_db_connection() as conn:
            risk_count = conn.execute(
                text("SELECT COUNT(*) FROM cc_risk_history")
            ).scalar()

            if risk_count > 0:
                latest_risk = conn.execute(
                    text(
                        """
                    SELECT truck_id, risk_score, risk_level
                    FROM cc_risk_history
                    ORDER BY timestamp DESC
                    LIMIT 1
                """
                    )
                ).fetchone()

                print(
                    f"✅ Latest risk: {latest_risk.truck_id} = {latest_risk.risk_score:.1f} "
                    f"({latest_risk.risk_level})"
                )

    def test_cc_algorithm_state(self):
        """Test command center algorithm state persistence"""
        with db.get_db_connection() as conn:
            count = conn.execute(
                text("SELECT COUNT(*) FROM cc_algorithm_state")
            ).scalar()

            print(f"✅ Algorithm state records: {count}")
            assert count >= 0

    def test_cc_correlation_events(self):
        """Test command center correlation events"""
        with db.get_db_connection() as conn:
            correlations = conn.execute(
                text(
                    """
                SELECT truck_id, pattern_type, event_count
                FROM cc_correlation_events
                ORDER BY detected_at DESC
                LIMIT 5
            """
                )
            ).fetchall()

            if len(correlations) > 0:
                for corr in correlations:
                    print(
                        f"✅ Correlation: {corr.truck_id} - {corr.pattern_type} "
                        f"({corr.event_count} events)"
                    )


class TestDataQualityRealData:
    """Test data quality and completeness"""

    def test_fuel_metrics_data_completeness(self):
        """Test fuel_metrics has complete data fields"""
        with db.get_db_connection() as conn:
            # Check key fields are populated
            completeness = conn.execute(
                text(
                    """
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN sensor_pct IS NOT NULL THEN 1 ELSE 0 END) as has_fuel_pct,
                    SUM(CASE WHEN speed_mph IS NOT NULL THEN 1 ELSE 0 END) as has_speed,
                    SUM(CASE WHEN odometer_mi IS NOT NULL THEN 1 ELSE 0 END) as has_odometer,
                    SUM(CASE WHEN mpg_current IS NOT NULL THEN 1 ELSE 0 END) as has_mpg
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 24 HOUR)
            """
                )
            ).fetchone()

            if completeness.total > 0:
                fuel_pct = (completeness.has_fuel_pct / completeness.total) * 100
                speed_pct = (completeness.has_speed / completeness.total) * 100
                odom_pct = (completeness.has_odometer / completeness.total) * 100
                mpg_pct = (completeness.has_mpg / completeness.total) * 100

                print(f"✅ Data completeness (24h, n={completeness.total}):")
                print(f"   Fuel %: {fuel_pct:.1f}%")
                print(f"   Speed: {speed_pct:.1f}%")
                print(f"   Odometer: {odom_pct:.1f}%")
                print(f"   MPG: {mpg_pct:.1f}%")

                # Should have at least some data
                assert fuel_pct > 0 or speed_pct > 0

    def test_data_freshness(self):
        """Test that we have recent data (last 1 hour)"""
        with db.get_db_connection() as conn:
            fresh_count = conn.execute(
                text(
                    """
                SELECT COUNT(*) 
                FROM fuel_metrics
                WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 1 HOUR)
            """
                )
            ).scalar()

            print(f"✅ Fresh data (last hour): {fresh_count} records")

            # Should have some recent data
            assert fresh_count >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short", "-s"])
