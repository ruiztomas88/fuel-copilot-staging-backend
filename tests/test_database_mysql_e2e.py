"""
E2E Tests for Database MySQL - Real Database Integration
Target: 90%+ coverage using actual MySQL connection
"""

from datetime import datetime, timedelta

import pandas as pd
import pytest

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
    get_refuel_history,
    get_sqlalchemy_engine,
    get_truck_efficiency_stats,
    get_truck_history,
    save_driver_score_history,
)


class TestDatabaseConnection:
    """Test database connection"""

    def test_get_connection(self):
        """Should connect via SQLAlchemy"""
        with get_db_connection() as conn:
            assert conn is not None
            from sqlalchemy import text

            result = conn.execute(text("SELECT 1")).scalar()
            assert result == 1

    def test_get_engine(self):
        """Should get SQLAlchemy engine"""
        engine = get_sqlalchemy_engine()
        assert engine is not None


class TestTruckQueries:
    """Test truck data queries"""

    def test_get_latest_truck_data(self):
        """Should get latest truck data"""
        df = get_latest_truck_data(hours_back=24)
        assert df is not None
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0
        assert "truck_id" in df.columns

    def test_get_latest_truck_data_1hour(self):
        """Should get recent data"""
        df = get_latest_truck_data(hours_back=1)
        assert df is not None
        assert isinstance(df, pd.DataFrame)

    def test_get_truck_history(self):
        """Should get truck history"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]
        df = get_truck_history(truck_id, hours_back=168)

        assert df is not None
        assert isinstance(df, pd.DataFrame)


class TestRefuelHistory:
    """Test refuel history queries"""

    def test_get_refuel_history_30days(self):
        """Should get 30 day refuel history"""
        df = get_refuel_history(days_back=30)
        assert df is not None

    def test_get_refuel_history_7days(self):
        """Should get 7 day refuel history"""
        df = get_refuel_history(days_back=7)
        assert df is not None


class TestFleetSummary:
    """Test fleet summary and KPIs"""

    def test_get_fleet_summary(self):
        """Should get fleet summary"""
        summary = get_fleet_summary()
        assert summary is not None
        assert isinstance(summary, dict)
        assert "total_trucks" in summary or "trucks" in summary

    def test_get_kpi_summary_1day(self):
        """Should get KPI summary"""
        kpis = get_kpi_summary(days_back=1)
        assert kpis is not None
        assert isinstance(kpis, dict)

    def test_get_kpi_summary_7days(self):
        """Should get 7 day KPIs"""
        kpis = get_kpi_summary(days_back=7)
        assert kpis is not None
        assert isinstance(kpis, dict)

    def test_get_enhanced_kpis_1day(self):
        """Should get enhanced KPIs"""
        kpis = get_enhanced_kpis(days_back=1)
        assert kpis is not None
        assert isinstance(kpis, dict)

    def test_get_enhanced_kpis_30days(self):
        """Should get 30 day enhanced KPIs"""
        kpis = get_enhanced_kpis(days_back=30)
        assert kpis is not None


class TestLossAnalysis:
    """Test loss analysis"""

    def test_get_loss_analysis_1day(self):
        """Should get 1 day loss analysis"""
        analysis = get_loss_analysis(days_back=1)
        assert analysis is not None
        assert isinstance(analysis, dict)

    def test_get_loss_analysis_7days(self):
        """Should get 7 day loss analysis"""
        analysis = get_loss_analysis(days_back=7)
        assert analysis is not None


class TestDriverScorecard:
    """Test driver scorecard"""

    def test_get_driver_scorecard_7days(self):
        """Should get 7 day scorecard"""
        scorecard = get_driver_scorecard(days_back=7)
        assert scorecard is not None
        assert isinstance(scorecard, dict)

    def test_get_driver_scorecard_30days(self):
        """Should get 30 day scorecard"""
        scorecard = get_driver_scorecard(days_back=30)
        assert scorecard is not None


class TestDriverScoreHistory:
    """Test driver score history"""

    def test_get_driver_score_history(self):
        """Should get driver score history"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]
        history = get_driver_score_history(truck_id=truck_id, days_back=30)
        assert history is not None

    def test_get_driver_score_trend(self):
        """Should get driver score trend"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]
        trend = get_driver_score_trend(truck_id, days_back=30)
        assert trend is not None
        assert isinstance(trend, dict)


class TestTruckEfficiency:
    """Test truck efficiency stats"""

    def test_get_truck_efficiency_stats(self):
        """Should get efficiency stats"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]
        stats = get_truck_efficiency_stats(truck_id, days_back=30)
        assert stats is not None
        assert isinstance(stats, dict)

    def test_get_fuel_rate_analysis(self):
        """Should get fuel rate analysis"""
        df_trucks = get_latest_truck_data(hours_back=1)
        if df_trucks.empty:
            pytest.skip("No active trucks")

        truck_id = df_trucks.iloc[0]["truck_id"]
        df = get_fuel_rate_analysis(truck_id, hours_back=48)
        assert df is not None
        assert isinstance(df, pd.DataFrame)


class TestDatabaseTables:
    """Test database table queries"""

    def test_fuel_metrics_table(self):
        """Should query fuel_metrics table"""
        with get_db_connection() as conn:
            from sqlalchemy import text

            result = conn.execute(text("SELECT COUNT(*) FROM fuel_metrics")).scalar()
            assert result > 0

    def test_refuel_events_table(self):
        """Should query refuel_events table"""
        with get_db_connection() as conn:
            from sqlalchemy import text

            result = conn.execute(text("SELECT COUNT(*) FROM refuel_events")).scalar()
            assert result >= 0

    def test_driver_scores_table(self):
        """Should query driver_scores table"""
        with get_db_connection() as conn:
            from sqlalchemy import text

            result = conn.execute(text("SELECT COUNT(*) FROM driver_scores")).scalar()
            assert result >= 0

    def test_mpg_baselines_table(self):
        """Should query mpg_baselines table"""
        with get_db_connection() as conn:
            from sqlalchemy import text

            result = conn.execute(text("SELECT COUNT(*) FROM mpg_baselines")).scalar()
            assert result >= 0


class TestDataIntegrity:
    """Test data integrity"""

    def test_fuel_metrics_has_recent_data(self):
        """Should have recent data"""
        with get_db_connection() as conn:
            from sqlalchemy import text

            result = (
                conn.execute(
                    text(
                        """
                SELECT MAX(timestamp_utc) as latest
                FROM fuel_metrics
            """
                    )
                )
                .mappings()
                .first()
            )

            assert result["latest"] is not None
            age = datetime.now() - result["latest"]
            assert age < timedelta(hours=2)

    def test_no_null_truck_ids(self):
        """Should not have NULL truck IDs"""
        with get_db_connection() as conn:
            from sqlalchemy import text

            count = conn.execute(
                text(
                    """
                SELECT COUNT(*) FROM fuel_metrics WHERE truck_id IS NULL
            """
                )
            ).scalar()
            assert count == 0

    def test_truck_id_format(self):
        """Should have valid truck ID format"""
        df = get_latest_truck_data(hours_back=1)
        if not df.empty:
            truck_id = df.iloc[0]["truck_id"]
            assert len(truck_id) >= 4
            assert any(c.isalpha() for c in truck_id)


class TestDatabaseStructure:
    """Test database structure"""

    def test_describe_fuel_metrics(self):
        """Should describe fuel_metrics table"""
        with get_db_connection() as conn:
            from sqlalchemy import text

            columns = conn.execute(text("DESCRIBE fuel_metrics")).mappings().all()
            assert len(columns) > 0

            column_names = [col["Field"] for col in columns]
            assert "truck_id" in column_names
            assert "timestamp_utc" in column_names
            assert "mpg_current" in column_names

    def test_show_tables(self):
        """Should list all tables"""
        with get_db_connection() as conn:
            from sqlalchemy import text

            tables = [row[0] for row in conn.execute(text("SHOW TABLES")).all()]
            assert len(tables) >= 20
            assert "fuel_metrics" in tables
            assert "refuel_events" in tables
