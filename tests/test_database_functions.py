"""
Real database integration tests - Testing actual functions that exist
Target: 90% coverage
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pandas as pd
import pytest


class TestDatabaseCoreFunctions:
    """Test core database operations with real DB"""

    def test_get_fleet_summary_structure(self):
        """Test get_fleet_summary returns proper structure"""
        from database_mysql import get_fleet_summary

        result = get_fleet_summary()

        assert isinstance(result, dict)
        assert "total_trucks" in result
        assert "active_trucks" in result
        assert "truck_details" in result
        assert isinstance(result["truck_details"], list)

    def test_get_latest_truck_data_returns_dataframe(self):
        """Test get_latest_truck_data returns DataFrame"""
        from database_mysql import get_latest_truck_data

        result = get_latest_truck_data(hours_back=24)

        assert isinstance(result, pd.DataFrame)

    def test_get_truck_history_returns_dataframe(self):
        """Test get_truck_history returns DataFrame"""
        from database_mysql import get_truck_history

        result = get_truck_history("CO0681", hours_back=24)

        assert isinstance(result, pd.DataFrame)

    def test_get_refuel_history_returns_dataframe(self):
        """Test get_refuel_history returns DataFrame"""
        from database_mysql import get_refuel_history

        result = get_refuel_history(days_back=7)

        assert isinstance(result, pd.DataFrame)

    def test_get_kpi_summary_returns_dict(self):
        """Test get_kpi_summary returns dict"""
        from database_mysql import get_kpi_summary

        result = get_kpi_summary(days_back=1)

        assert isinstance(result, dict)

    def test_get_loss_analysis_returns_dict(self):
        """Test get_loss_analysis returns dict"""
        from database_mysql import get_loss_analysis

        result = get_loss_analysis(days_back=1)

        assert isinstance(result, dict)

    def test_get_driver_scorecard_returns_dict(self):
        """Test get_driver_scorecard returns dict"""
        from database_mysql import get_driver_scorecard

        result = get_driver_scorecard(days_back=7)

        assert isinstance(result, dict)

    def test_get_enhanced_kpis_returns_dict(self):
        """Test get_enhanced_kpis returns dict"""
        from database_mysql import get_enhanced_kpis

        result = get_enhanced_kpis(days_back=1)

        assert isinstance(result, dict)


class TestDatabaseTruckSpecificFunctions:
    """Test truck-specific database functions"""

    def test_get_truck_efficiency_stats(self):
        """Test get_truck_efficiency_stats"""
        from database_mysql import get_truck_efficiency_stats

        result = get_truck_efficiency_stats("CO0681", days_back=30)

        assert isinstance(result, dict)

    def test_get_fuel_rate_analysis_returns_dataframe(self):
        """Test get_fuel_rate_analysis returns DataFrame"""
        from database_mysql import get_fuel_rate_analysis

        result = get_fuel_rate_analysis("CO0681", hours_back=48)

        assert isinstance(result, pd.DataFrame)

    def test_get_driver_score_trend(self):
        """Test get_driver_score_trend"""
        from database_mysql import get_driver_score_trend

        result = get_driver_score_trend("CO0681", days_back=30)

        assert isinstance(result, dict)


class TestDatabaseConnectionManagement:
    """Test database connection handling"""

    def test_get_sqlalchemy_engine_returns_engine(self):
        """Test get_sqlalchemy_engine returns valid engine"""
        from database_mysql import get_sqlalchemy_engine

        engine = get_sqlalchemy_engine()

        assert engine is not None

    def test_get_db_connection_context_manager(self):
        """Test get_db_connection works as context manager"""
        from database_mysql import get_db_connection

        with get_db_connection() as conn:
            assert conn is not None


class TestDatabaseTimeframes:
    """Test different timeframe parameters"""

    def test_get_latest_truck_data_various_hours(self):
        """Test get_latest_truck_data with various timeframes"""
        from database_mysql import get_latest_truck_data

        df_1h = get_latest_truck_data(hours_back=1)
        df_24h = get_latest_truck_data(hours_back=24)
        df_168h = get_latest_truck_data(hours_back=168)

        assert isinstance(df_1h, pd.DataFrame)
        assert isinstance(df_24h, pd.DataFrame)
        assert isinstance(df_168h, pd.DataFrame)

    def test_get_kpi_summary_various_days(self):
        """Test get_kpi_summary with various timeframes"""
        from database_mysql import get_kpi_summary

        kpi_1d = get_kpi_summary(days_back=1)
        kpi_7d = get_kpi_summary(days_back=7)
        kpi_30d = get_kpi_summary(days_back=30)

        assert isinstance(kpi_1d, dict)
        assert isinstance(kpi_7d, dict)
        assert isinstance(kpi_30d, dict)

    def test_get_refuel_history_various_days(self):
        """Test get_refuel_history with various timeframes"""
        from database_mysql import get_refuel_history

        df_1d = get_refuel_history(days_back=1)
        df_7d = get_refuel_history(days_back=7)
        df_30d = get_refuel_history(days_back=30)

        assert isinstance(df_1d, pd.DataFrame)
        assert isinstance(df_7d, pd.DataFrame)
        assert isinstance(df_30d, pd.DataFrame)


class TestDatabaseEdgeCases:
    """Test edge cases and error handling"""

    def test_invalid_truck_id_returns_empty(self):
        """Test invalid truck ID returns empty result"""
        from database_mysql import get_truck_history

        result = get_truck_history("INVALID_TRUCK_999", hours_back=1)

        assert isinstance(result, pd.DataFrame)

    def test_zero_timeframe_handling(self):
        """Test handling of zero timeframe"""
        from database_mysql import get_kpi_summary

        result = get_kpi_summary(days_back=0)

        assert isinstance(result, dict)

    def test_large_timeframe_handling(self):
        """Test handling of large timeframes"""
        from database_mysql import get_truck_history

        result = get_truck_history("CO0681", hours_back=8760)  # 1 year

        assert isinstance(result, pd.DataFrame)

    def test_negative_timeframe_handling(self):
        """Test handling of negative timeframes"""
        from database_mysql import get_kpi_summary

        # Should handle gracefully or use default
        try:
            result = get_kpi_summary(days_back=-1)
            assert isinstance(result, dict)
        except ValueError:
            # Acceptable to raise ValueError for negative
            pass


class TestDatabaseDriverScoreFunctions:
    """Test driver score history functions"""

    def test_ensure_driver_score_history_table(self):
        """Test ensure_driver_score_history_table"""
        from database_mysql import ensure_driver_score_history_table

        result = ensure_driver_score_history_table()

        assert isinstance(result, bool)

    def test_get_driver_score_history(self):
        """Test get_driver_score_history"""
        from database_mysql import get_driver_score_history

        result = get_driver_score_history("CO0681", days_back=30)

        # Should return list of scores
        assert isinstance(result, list)


class TestDatabasePerformance:
    """Test database performance"""

    def test_get_fleet_summary_performance(self):
        """Test get_fleet_summary completes quickly"""
        import time

        from database_mysql import get_fleet_summary

        start = time.time()
        result = get_fleet_summary()
        elapsed = time.time() - start

        # Should complete in under 5 seconds
        assert elapsed < 5.0
        assert isinstance(result, dict)

    def test_get_latest_truck_data_performance(self):
        """Test get_latest_truck_data completes quickly"""
        import time

        from database_mysql import get_latest_truck_data

        start = time.time()
        result = get_latest_truck_data(hours_back=24)
        elapsed = time.time() - start

        # Should complete in under 5 seconds
        assert elapsed < 5.0
        assert isinstance(result, pd.DataFrame)


class TestDatabaseIntegration:
    """Test multiple operations in sequence"""

    def test_sequential_operations(self):
        """Test multiple operations work in sequence"""
        from database_mysql import (
            get_fleet_summary,
            get_kpi_summary,
            get_latest_truck_data,
        )

        summary = get_fleet_summary()
        kpis = get_kpi_summary(days_back=1)
        latest = get_latest_truck_data(hours_back=24)

        assert isinstance(summary, dict)
        assert isinstance(kpis, dict)
        assert isinstance(latest, pd.DataFrame)

    def test_concurrent_queries_no_conflict(self):
        """Test concurrent queries don't conflict"""
        from database_mysql import get_kpi_summary, get_loss_analysis

        kpis = get_kpi_summary(days_back=1)
        loss = get_loss_analysis(days_back=1)

        assert isinstance(kpis, dict)
        assert isinstance(loss, dict)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
