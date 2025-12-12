"""
Tests for BUG #2 Fix: Connection Pool for fuel_copilot database
===============================================================
From Audit v5.4 - predictive_maintenance_v3.py was creating individual
pymysql connections instead of using a connection pool.

Fix: Added get_local_engine() and execute_local_query() to database_pool.py
"""

import pytest
import inspect
import ast
import os


class TestLocalPoolConfiguration:
    """Tests for the new local database pool configuration"""

    def test_local_pool_functions_exist(self):
        """Verify new pool functions exist in database_pool.py"""
        from database_pool import (
            get_local_engine,
            get_local_session_maker,
            get_local_db_session,
            execute_local_query,
        )

        # All functions should be callable
        assert callable(get_local_engine)
        assert callable(get_local_session_maker)
        assert callable(get_local_db_session)
        assert callable(execute_local_query)

    def test_local_database_url_configured(self):
        """Verify LOCAL_DATABASE_URL is configured"""
        import database_pool

        assert hasattr(database_pool, "LOCAL_DATABASE_URL")
        assert "fuel_copilot" in database_pool.LOCAL_DATABASE_URL or "LOCAL_DB_NAME" in str(
            database_pool.LOCAL_DATABASE_URL
        )

    def test_local_pool_variables_initialized(self):
        """Verify local pool global variables exist"""
        import database_pool

        # Check that the module has the local engine variables
        assert hasattr(database_pool, "_local_engine")
        assert hasattr(database_pool, "_LocalSessionLocal")

    def test_close_engine_handles_both_pools(self):
        """Verify close_engine() closes both Wialon and Local pools"""
        import database_pool

        source = inspect.getsource(database_pool.close_engine)

        # Should reference both engines
        assert "_engine" in source
        assert "_local_engine" in source
        assert "Wialon" in source or "wialon" in source.lower()
        assert "LOCAL" in source or "local" in source.lower()


class TestPredictiveMaintenanceUsesPool:
    """Tests that predictive_maintenance_v3.py uses the connection pool"""

    def test_execute_fuel_query_uses_pool(self):
        """Verify execute_fuel_query imports from database_pool"""
        from predictive_maintenance_v3 import execute_fuel_query

        source = inspect.getsource(execute_fuel_query)

        # Should import from database_pool
        assert "database_pool" in source
        assert "execute_local_query" in source

    def test_no_direct_pymysql_connect(self):
        """Verify execute_fuel_query doesn't use direct pymysql.connect()"""
        from predictive_maintenance_v3 import execute_fuel_query

        source = inspect.getsource(execute_fuel_query)

        # Should NOT have direct pymysql.connect
        assert "pymysql.connect" not in source
        assert "connect_timeout=3" not in source

    def test_no_manual_connection_management(self):
        """Verify no manual cursor/conn.close() in execute_fuel_query"""
        from predictive_maintenance_v3 import execute_fuel_query

        source = inspect.getsource(execute_fuel_query)

        # Should NOT have manual connection management
        assert "cursor.close()" not in source
        assert "conn.close()" not in source


class TestPoolStatistics:
    """Tests for pool statistics and monitoring"""

    def test_get_pool_stats_returns_both_pools(self):
        """Verify get_pool_stats returns stats for both pools"""
        import database_pool

        source = inspect.getsource(database_pool.get_pool_stats)

        # Should check both wialon and local pools
        assert "wialon" in source.lower()
        assert "local" in source.lower()


class TestExecuteLocalQuery:
    """Tests for the execute_local_query function"""

    def test_execute_local_query_returns_list(self):
        """Verify execute_local_query returns a list (even on error)"""
        from database_pool import execute_local_query

        # Even with invalid query, should return empty list not crash
        result = execute_local_query("INVALID SQL QUERY")
        assert isinstance(result, list)

    def test_execute_local_query_handles_params(self):
        """Verify execute_local_query signature accepts params"""
        from database_pool import execute_local_query
        import inspect

        sig = inspect.signature(execute_local_query)
        params = list(sig.parameters.keys())

        assert "query" in params
        assert "params" in params


class TestNoRegressionInOtherFiles:
    """Ensure other files still work with the pool changes"""

    def test_get_engine_still_works(self):
        """Verify get_engine() (Wialon pool) still works"""
        from database_pool import get_engine

        # Function should exist and be callable
        assert callable(get_engine)

    def test_get_db_session_still_works(self):
        """Verify get_db_session context manager still works"""
        from database_pool import get_db_session

        # Should be a context manager
        assert hasattr(get_db_session, "__enter__") or callable(get_db_session)

    def test_database_url_unchanged_for_wialon(self):
        """Verify Wialon DATABASE_URL still points to correct database"""
        import database_pool

        assert "wialon_collect" in database_pool.DATABASE_URL


@pytest.mark.integration
class TestConnectionPoolIntegration:
    """Integration tests requiring actual database connection"""

    @pytest.mark.skipif(
        not os.getenv("RUN_DB_TESTS", False),
        reason="Database integration tests disabled",
    )
    def test_local_engine_connects(self):
        """Test that local engine can actually connect"""
        from database_pool import get_local_engine
        from sqlalchemy import text

        engine = get_local_engine()
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1 as test"))
            row = result.fetchone()
            assert row[0] == 1

    @pytest.mark.skipif(
        not os.getenv("RUN_DB_TESTS", False),
        reason="Database integration tests disabled",
    )
    def test_execute_local_query_works(self):
        """Test that execute_local_query actually works"""
        from database_pool import execute_local_query

        result = execute_local_query("SELECT 1 as test")
        assert len(result) == 1
        assert result[0]["test"] == 1
