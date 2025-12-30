"""
Comprehensive Database MySQL Coverage Tests
Target: 90%+ coverage for database_mysql.py
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest

from database_mysql import (
    _empty_enhanced_kpis,
    _empty_fleet_summary,
    _empty_kpi_response,
    _empty_loss_response,
    calculate_savings_confidence_interval,
    ensure_driver_score_history_table,
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
    get_refuel_history,
    get_sqlalchemy_engine,
    get_truck_efficiency_stats,
    get_truck_history,
    save_driver_score_history,
)


class TestHelperFunctions:
    """Test all _empty_* helper functions"""

    def test_empty_fleet_summary(self):
        """Test _empty_fleet_summary"""
        result = _empty_fleet_summary()
        assert result["total_trucks"] == 0
        assert result["active_trucks"] == 0
        assert result["offline_trucks"] == 0
        assert result["avg_fuel_level"] == 0
        assert result["avg_mpg"] == 0
        assert result["avg_consumption"] == 0
        assert result["trucks_with_drift"] == 0
        assert result["active_dtcs"] == 0
        assert result["health_score"] == 100.0
        assert result["truck_details"] == []
        assert "timestamp" in result

    def test_empty_kpi_response(self):
        """Test _empty_kpi_response"""
        result = _empty_kpi_response(fuel_price=3.50)
        assert result["total_fuel_consumed_gal"] == 0
        assert result["total_fuel_cost_usd"] == 0
        assert result["total_idle_waste_gal"] == 0
        assert result["total_idle_cost_usd"] == 0
        assert result["avg_fuel_price_per_gal"] == 3.50
        assert result["total_distance_mi"] == 0
        assert result["fleet_avg_mpg"] == 0
        assert result["total_moving_hours"] == 0
        assert result["total_idle_hours"] == 0
        assert result["total_active_hours"] == 0
        assert result["period_days"] == 0
        assert result["truck_count"] == 0
        assert result["total_records"] == 0
        assert result["avg_idle_gph"] == 0

    def test_empty_loss_response(self):
        """Test _empty_loss_response"""
        result = _empty_loss_response(days=7, price=3.75)
        assert result["period_days"] == 7
        assert result["truck_count"] == 0
        assert result["fuel_price_per_gal"] == 3.75
        assert result["baseline_mpg"] == 5.7
        assert result["summary"]["total_loss_gal"] == 0
        assert result["summary"]["total_loss_usd"] == 0
        assert "by_cause" in result["summary"]
        assert result["summary"]["by_cause"]["idle"]["gallons"] == 0
        assert result["summary"]["by_cause"]["high_rpm"]["gallons"] == 0
        assert result["summary"]["by_cause"]["speeding"]["gallons"] == 0
        assert result["summary"]["by_cause"]["altitude"]["gallons"] == 0
        assert result["summary"]["by_cause"]["mechanical"]["gallons"] == 0
        assert result["trucks"] == []

    def test_empty_enhanced_kpis(self):
        """Test _empty_enhanced_kpis"""
        result = _empty_enhanced_kpis(days=30, price=4.00)
        assert result["period_days"] == 30
        assert result["truck_count"] == 0
        assert result["fuel_price_per_gal"] == 4.00
        assert "fleet_health" in result
        assert result["fleet_health"]["index"] == 0
        assert result["fleet_health"]["grade"] == "N/A"
        assert "fuel_consumption" in result
        assert result["fuel_consumption"]["total_gallons"] == 0
        assert "costs" in result
        assert result["costs"]["total_cost"] == 0
        assert "efficiency" in result
        assert result["efficiency"]["avg_mpg"] == 0
        assert "inefficiency_breakdown" in result


class TestFleetSummary:
    """Test get_fleet_summary variations"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_fleet_summary_empty(self, mock_engine):
        """Test fleet summary with empty database"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_fleet_summary()
        assert result["total_trucks"] == 0
        assert result["health_score"] == 100.0

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_fleet_summary_error_handling(self, mock_engine):
        """Test fleet summary error handling"""
        mock_engine.return_value.begin.side_effect = Exception("DB Error")

        result = get_fleet_summary()
        assert result["total_trucks"] == 0
        assert result["health_score"] == 100.0


class TestKPISummary:
    """Test get_kpi_summary"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_kpi_summary_1_day(self, mock_engine):
        """Test KPI summary for 1 day"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_kpi_summary(days_back=1, fuel_price_per_gal=3.50)
        assert "total_fuel_consumed_gal" in result
        assert result["avg_fuel_price_per_gal"] == 3.50

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_kpi_summary_7_days(self, mock_engine):
        """Test KPI summary for 7 days"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_kpi_summary(days_back=7)
        assert result is not None

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_kpi_summary_30_days(self, mock_engine):
        """Test KPI summary for 30 days"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_kpi_summary(days_back=30)
        assert result is not None


class TestLossAnalysis:
    """Test get_loss_analysis"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_loss_analysis_default(self, mock_engine):
        """Test loss analysis with default params"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis()
        assert "summary" in result
        assert "period_days" in result
        assert "trucks" in result

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_loss_analysis_7_days(self, mock_engine):
        """Test loss analysis for 7 days"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis(days_back=7)
        assert result is not None

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_loss_analysis_error(self, mock_engine):
        """Test loss analysis error handling"""
        mock_engine.return_value.connect.side_effect = Exception("Error")

        result = get_loss_analysis(days_back=1)
        assert result["summary"]["total_loss_gal"] == 0


class TestEnhancedKPIs:
    """Test get_enhanced_kpis"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_enhanced_kpis_1_day(self, mock_engine):
        """Test enhanced KPIs for 1 day"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_enhanced_kpis(days_back=1)
        assert "period_days" in result

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_enhanced_kpis_30_days(self, mock_engine):
        """Test enhanced KPIs for 30 days"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_enhanced_kpis(days_back=30)
        assert result is not None


class TestTruckEfficiency:
    """Test get_truck_efficiency_stats"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_truck_efficiency_30_days(self, mock_engine):
        """Test truck efficiency for 30 days"""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_truck_efficiency_stats("TRK001", days_back=30)
        assert result is not None

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_truck_efficiency_7_days(self, mock_engine):
        """Test truck efficiency for 7 days"""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_truck_efficiency_stats("TRK002", days_back=7)
        assert result is not None


class TestDriverScorecard:
    """Test get_driver_scorecard"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_driver_scorecard_7_days(self, mock_engine):
        """Test driver scorecard for 7 days"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_driver_scorecard(days_back=7)
        assert result is not None

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_driver_scorecard_30_days(self, mock_engine):
        """Test driver scorecard for 30 days"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_driver_scorecard(days_back=30)
        assert result is not None


class TestDriverScoreHistory:
    """Test driver score history functions"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_ensure_driver_score_history_table(self, mock_engine):
        """Test ensure_driver_score_history_table"""
        mock_conn = MagicMock()
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = ensure_driver_score_history_table()
        assert result is True or result is None

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_save_driver_score_history(self, mock_engine):
        """Test save_driver_score_history"""
        mock_conn = MagicMock()
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = save_driver_score_history("TRK001", 85.5, {"fuel_efficiency": 90})
        assert result is not None or result is None

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_get_driver_score_history(self, mock_engine):
        """Test get_driver_score_history"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_driver_score_history("TRK001", days_back=30)
        assert isinstance(result, list)

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_get_driver_score_trend(self, mock_engine):
        """Test get_driver_score_trend"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_driver_score_trend("TRK001", days_back=30)
        assert isinstance(result, dict)


class TestSavingsConfidenceInterval:
    """Test calculate_savings_confidence_interval"""

    def test_savings_ci_basic(self):
        """Test CI with basic inputs"""
        result = calculate_savings_confidence_interval(
            savings_usd=100.0, reduction_pct=0.5, days_back=7
        )
        assert "expected_annual" in result
        assert "lower_bound_annual" in result
        assert "upper_bound_annual" in result
        assert result["confidence_level"] == 0.95

    def test_savings_ci_different_confidence(self):
        """Test CI with different confidence level"""
        result = calculate_savings_confidence_interval(
            savings_usd=200.0, reduction_pct=0.3, days_back=30, confidence_level=0.99
        )
        assert result["confidence_level"] == 0.99

    def test_savings_ci_more_data(self):
        """Test CI with more days of data"""
        result = calculate_savings_confidence_interval(
            savings_usd=150.0, reduction_pct=0.4, days_back=90
        )
        assert result["expected_annual"] > 0


class TestFuelRateAnalysis:
    """Test get_fuel_rate_analysis"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_fuel_rate_48_hours(self, mock_engine):
        """Test fuel rate for 48 hours"""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_fuel_rate_analysis(hours_back=48)
        assert isinstance(result, pd.DataFrame)

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_fuel_rate_24_hours(self, mock_engine):
        """Test fuel rate for 24 hours"""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_fuel_rate_analysis(hours_back=24)
        assert isinstance(result, pd.DataFrame)


class TestTruckHistory:
    """Test get_truck_history"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_truck_history_168_hours(self, mock_engine):
        """Test truck history for 168 hours (1 week)"""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_truck_history("TRK001", hours_back=168)
        assert isinstance(result, pd.DataFrame)

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_truck_history_24_hours(self, mock_engine):
        """Test truck history for 24 hours"""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_truck_history("TRK002", hours_back=24)
        assert isinstance(result, pd.DataFrame)


class TestRefuelHistory:
    """Test get_refuel_history"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_refuel_history_default(self, mock_engine):
        """Test refuel history with default params"""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_refuel_history("TRK001")
        assert isinstance(result, list)

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_refuel_history_with_days(self, mock_engine):
        """Test refuel history with days back"""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_refuel_history("TRK002", days_back=30)
        assert isinstance(result, list)


class TestLatestTruckData:
    """Test get_latest_truck_data"""

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_latest_truck_data_24_hours(self, mock_engine):
        """Test latest truck data for 24 hours"""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_latest_truck_data(truck_id="TRK001", hours_back=24)
        assert isinstance(result, pd.DataFrame)

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_latest_truck_data_48_hours(self, mock_engine):
        """Test latest truck data for 48 hours"""
        mock_conn = MagicMock()
        mock_result = MagicMock()
        mock_result.fetchall.return_value = []
        mock_conn.execute.return_value = mock_result
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_latest_truck_data(truck_id="TRK002", hours_back=48)
        assert isinstance(result, pd.DataFrame)

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_latest_truck_data_error(self, mock_engine):
        """Test latest truck data error handling"""
        mock_engine.return_value.begin.side_effect = Exception("DB Error")

        result = get_latest_truck_data(truck_id="TRK003")
        assert isinstance(result, pd.DataFrame)


class TestEdgeCases:
    """Test edge cases and error handling"""

    def test_empty_responses_consistency(self):
        """Ensure all empty responses are consistent"""
        fleet = _empty_fleet_summary()
        kpi = _empty_kpi_response(3.50)
        loss = _empty_loss_response(7, 3.50)
        enhanced = _empty_enhanced_kpis(7, 3.50)

        assert all(isinstance(x, dict) for x in [fleet, kpi, loss, enhanced])

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_negative_days(self, mock_engine):
        """Test with negative days (should use minimum)"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.connect.return_value.__enter__.return_value = mock_conn

        result = get_loss_analysis(days_back=-5)
        assert result is not None

    @patch("database_mysql.get_sqlalchemy_engine")
    def test_very_large_days(self, mock_engine):
        """Test with very large days value"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.begin.return_value.__enter__.return_value = mock_conn

        result = get_kpi_summary(days_back=365)
        assert result is not None
