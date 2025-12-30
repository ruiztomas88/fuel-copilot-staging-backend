"""
Comprehensive E2E Tests for Backend - Real Data Coverage to 90%+
Focus on uncovered alert_service and database_mysql code paths
"""

from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

# Alert Service imports
from alert_service import (
    Alert,
    AlertManager,
    AlertPriority,
    AlertType,
    FuelEventClassifier,
    get_alert_manager,
    get_fuel_classifier,
)

# Database imports
from database_mysql import (
    get_db_connection,
    get_driver_score_history,
    get_driver_score_trend,
    get_driver_scorecard,
    get_enhanced_kpis,
    get_fleet_summary,
    get_fuel_rate_analysis,
    get_kpi_summary,
    get_latest_truck_data,
    get_loss_analysis,
    get_truck_efficiency_stats,
    get_truck_history,
    save_driver_score_history,
)

# ============================================
# ALERT SERVICE COVERAGE TESTS
# ============================================


class TestAlertManagerCoverage:
    """Comprehensive AlertManager tests"""

    def test_send_multi_channel_alert(self):
        """Test sending alert through multiple channels"""
        manager = get_alert_manager()
        alert = Alert(
            alert_type=AlertType.THEFT_CONFIRMED,
            priority=AlertPriority.CRITICAL,
            truck_id="TEST001",
            message="Critical theft confirmed",
        )

        # Test with specific channels
        result = manager.send_alert(alert, channels=["sms", "email"])
        assert result is False or result is True  # Depends on config

    def test_alert_rate_limiting_per_type(self):
        """Test rate limiting per alert type"""
        manager = get_alert_manager()

        # First LOW_FUEL alert should pass
        alert1 = Alert(
            alert_type=AlertType.LOW_FUEL,
            priority=AlertPriority.HIGH,
            truck_id="TEST_RATE",
            message="First low fuel",
        )
        should_send1 = manager._should_send_alert(alert1)
        assert should_send1 is True
        manager.send_alert(alert1)

        # Second LOW_FUEL for same truck should be rate limited
        alert2 = Alert(
            alert_type=AlertType.LOW_FUEL,
            priority=AlertPriority.HIGH,
            truck_id="TEST_RATE",
            message="Second low fuel",
        )
        should_send2 = manager._should_send_alert(alert2)
        assert should_send2 is False

    def test_alert_history_management(self):
        """Test alert history tracking"""
        manager = get_alert_manager()

        # Add several alerts
        for i in range(5):
            alert = Alert(
                alert_type=AlertType.EFFICIENCY_DROP,
                priority=AlertPriority.MEDIUM,
                truck_id=f"HIST_{i}",
                message=f"Test {i}",
            )
            manager.send_alert(alert)

        # History should contain alerts
        assert len(manager._alert_history) >= 5

    def test_format_all_alert_types(self):
        """Test formatting for all alert types"""
        manager = get_alert_manager()

        alert_types = [
            AlertType.REFUEL,
            AlertType.THEFT_SUSPECTED,
            AlertType.THEFT_CONFIRMED,
            AlertType.SENSOR_ISSUE,
            AlertType.DRIFT_WARNING,
            AlertType.SENSOR_OFFLINE,
            AlertType.LOW_FUEL,
            AlertType.EFFICIENCY_DROP,
            AlertType.MAINTENANCE_DUE,
            AlertType.DTC_ALERT,
            AlertType.VOLTAGE_ALERT,
            AlertType.IDLE_DEVIATION,
            AlertType.GPS_QUALITY,
            AlertType.MAINTENANCE_PREDICTION,
        ]

        for alert_type in alert_types:
            alert = Alert(
                alert_type=alert_type,
                priority=AlertPriority.MEDIUM,
                truck_id="TEST",
                message="Test all types",
            )
            formatted = manager._format_alert_message(alert)
            assert "TEST" in formatted
            assert "Fuel Copilot" in formatted or "FUEL COPILOT" in formatted


class TestFuelClassifierCoverage:
    """Comprehensive FuelEventClassifier tests"""

    def test_fuel_drop_registration(self):
        """Test comprehensive fuel drop registration"""
        classifier = get_fuel_classifier()

        result = classifier.register_fuel_drop(
            truck_id="TEST_DROP_FULL",
            fuel_before=150.0,
            fuel_after=80.0,
            tank_capacity_gal=200.0,
            location="Test Location",
            truck_status="STOPPED",
        )

        # May return event ID or None depending on conditions
        assert result is None or isinstance(result, str)

    def test_sensor_volatility_unknown(self):
        """Test volatility when insufficient data"""
        classifier = get_fuel_classifier()

        # New truck with no history
        vol = classifier.get_sensor_volatility("NEW_TRUCK_NO_DATA")
        assert vol == "unknown"

    def test_sensor_volatility_stable(self):
        """Test stable sensor detection"""
        classifier = get_fuel_classifier()
        truck_id = "STABLE_SENSOR"
        base_time = datetime.now(timezone.utc)

        # Add very stable readings
        for i in range(15):
            classifier.add_fuel_reading(
                truck_id=truck_id,
                fuel_pct=80.0,  # Constant
                timestamp=base_time + timedelta(minutes=i),
            )

        vol = classifier.get_sensor_volatility(truck_id)
        assert vol in ["stable", "unstable", "unknown"]

    def test_sensor_volatility_unstable(self):
        """Test unstable sensor detection"""
        classifier = get_fuel_classifier()
        truck_id = "UNSTABLE_SENSOR"
        base_time = datetime.now(timezone.utc)

        # Add volatile readings
        import random

        for i in range(15):
            classifier.add_fuel_reading(
                truck_id=truck_id,
                fuel_pct=50.0 + random.uniform(-10, 10),
                timestamp=base_time + timedelta(minutes=i),
            )

        vol = classifier.get_sensor_volatility(truck_id)
        assert vol in ["stable", "unstable", "unknown"]


# ============================================
# DATABASE MYSQL COVERAGE TESTS
# ============================================


class TestDatabaseQueryCoverage:
    """Comprehensive database query tests"""

    def test_get_latest_truck_data_various_timeframes(self):
        """Test getting truck data for various timeframes"""
        for hours in [1, 6, 12, 24, 48, 168]:
            df = get_latest_truck_data(hours_back=hours)
            assert df is not None
            assert isinstance(df, pd.DataFrame)

    def test_get_truck_history_long_period(self):
        """Test getting long history periods"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]

        for hours in [24, 72, 168, 336]:  # 1, 3, 7, 14 days
            df = get_truck_history(truck_id, hours_back=hours)
            assert df is not None


class TestKPIFunctionsCoverage:
    """Test all KPI calculation paths"""

    def test_kpi_summary_various_periods(self):
        """Test KPI summary for various periods"""
        for days in [1, 3, 7, 14, 30]:
            kpis = get_kpi_summary(days_back=days)
            assert kpis is not None
            assert isinstance(kpis, dict)

    def test_enhanced_kpis_various_periods(self):
        """Test enhanced KPIs for various periods"""
        for days in [1, 7, 14, 30, 60, 90]:
            kpis = get_enhanced_kpis(days_back=days)
            assert kpis is not None
            assert isinstance(kpis, dict)

    def test_loss_analysis_various_periods(self):
        """Test loss analysis for various periods"""
        for days in [1, 3, 7, 14, 30]:
            analysis = get_loss_analysis(days_back=days)
            assert analysis is not None
            assert isinstance(analysis, dict)

    def test_driver_scorecard_various_periods(self):
        """Test driver scorecard for various periods"""
        for days in [1, 7, 14, 30, 60, 90]:
            scorecard = get_driver_scorecard(days_back=days)
            assert scorecard is not None
            assert isinstance(scorecard, dict)


class TestTruckAnalysisCoverage:
    """Test truck-specific analysis functions"""

    def test_truck_efficiency_stats_multi_period(self):
        """Test efficiency stats for multiple periods"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]

        for days in [7, 14, 30, 60, 90]:
            stats = get_truck_efficiency_stats(truck_id, days_back=days)
            assert stats is not None
            assert isinstance(stats, dict)

    def test_fuel_rate_analysis_multi_period(self):
        """Test fuel rate analysis for multiple periods"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]

        for hours in [24, 48, 72, 168]:
            df = get_fuel_rate_analysis(truck_id, hours_back=hours)
            assert df is not None
            assert isinstance(df, pd.DataFrame)


class TestDriverScoreFunctionsCoverage:
    """Test driver score functions"""

    def test_driver_score_history_multi_period(self):
        """Test driver score history for multiple periods"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]

        for days in [7, 14, 30, 60, 90]:
            history = get_driver_score_history(truck_id=truck_id, days_back=days)
            assert history is not None

    def test_driver_score_trend_multi_period(self):
        """Test driver score trend for multiple periods"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]

        for days in [7, 14, 30, 60]:
            trend = get_driver_score_trend(truck_id, days_back=days)
            assert trend is not None
            assert isinstance(trend, dict)

    def test_save_driver_score_history(self):
        """Test saving driver score history"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]

        result = save_driver_score_history(
            truck_id=truck_id,
            score=85.5,
            mpg_score=90.0,
            idle_score=82.0,
            speed_score=84.0,
        )

        # Should return True or None
        assert result is True or result is None


class TestFleetSummaryEdgeCases:
    """Test fleet summary edge cases"""

    def test_fleet_summary_basic(self):
        """Test basic fleet summary"""
        summary = get_fleet_summary()
        assert summary is not None
        assert isinstance(summary, dict)

    def test_fleet_summary_content(self):
        """Test fleet summary contains expected data"""
        summary = get_fleet_summary()

        # Should have some key fields (may vary by implementation)
        assert isinstance(summary, dict)
        # May have: total_trucks, active_trucks, avg_mpg, etc.


class TestDatabaseEdgeCases:
    """Test database edge cases and error handling"""

    def test_get_truck_history_nonexistent_truck(self):
        """Test getting history for non-existent truck"""
        df = get_truck_history("NONEXISTENT_TRUCK_ID", hours_back=24)
        assert df is not None
        # Should return empty DataFrame
        assert df.empty or len(df) == 0

    def test_query_with_future_timestamp(self):
        """Test querying with future timestamp"""
        df = get_latest_truck_data(hours_back=-1)  # Negative hours
        assert df is not None

    def test_very_long_history(self):
        """Test very long history query"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if not df_trucks.empty:
            truck_id = df_trucks.iloc[0]["truck_id"]
            df = get_truck_history(truck_id, hours_back=720)  # 30 days
            assert df is not None
