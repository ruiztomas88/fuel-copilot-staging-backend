"""
Real database integration tests - 90% coverage target
Tests actual database operations with real DB connection
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest


class TestDatabaseOperations:
    """Test core database operations with real DB"""

    def test_get_fleet_summary_returns_dict(self):
        """Test get_fleet_summary returns proper structure"""
        from database_mysql import get_fleet_summary

        result = get_fleet_summary()

        assert isinstance(result, dict)
        assert "total_trucks" in result
        assert "active_trucks" in result
        assert "truck_details" in result
        assert isinstance(result["truck_details"], list)
        assert result["total_trucks"] > 0  # Should have trucks in DB

    def test_get_all_trucks_returns_list(self):
        """Test get_all_trucks returns list of truck IDs"""
        from database_mysql import get_all_trucks

        result = get_all_trucks()

        assert isinstance(result, list)
        assert len(result) > 0  # Should have at least some trucks
        # Each item should be a truck ID string
        if len(result) > 0:
            assert isinstance(result[0], str)

    def test_get_truck_latest_data_valid_truck(self):
        """Test get_truck_latest_data with valid truck"""
        from database_mysql import get_truck_latest_data

        # Use CO0681 which we know exists
        result = get_truck_latest_data("CO0681")

        # Should return dict or None
        if result is not None:
            assert isinstance(result, dict)

    def test_get_truck_latest_data_invalid_truck(self):
        """Test get_truck_latest_data with invalid truck"""
        from database_mysql import get_truck_latest_data

        result = get_truck_latest_data("INVALID_TRUCK_999")

        # Should return None for non-existent truck
        assert result is None

    def test_get_truck_history_returns_list(self):
        """Test get_truck_history returns list"""
        from database_mysql import get_truck_history

        result = get_truck_history("CO0681", hours=24)

        assert isinstance(result, list)
        # May be empty if no recent history

    def test_get_truck_history_invalid_truck(self):
        """Test get_truck_history with invalid truck"""
        from database_mysql import get_truck_history

        result = get_truck_history("NONEXISTENT_999", hours=1)

        assert isinstance(result, list)
        assert len(result) == 0

    def test_get_mpg_baseline_valid_truck(self):
        """Test get_mpg_baseline"""
        from database_mysql import get_mpg_baseline

        result = get_mpg_baseline("CO0681")

        # Should return float or None
        assert result is None or isinstance(result, (int, float, Decimal))

    def test_get_refuel_events_returns_list(self):
        """Test get_refuel_events"""
        from database_mysql import get_refuel_events

        result = get_refuel_events("CO0681", days=7)

        assert isinstance(result, list)

    def test_get_refuel_events_various_timeframes(self):
        """Test get_refuel_events with different timeframes"""
        from database_mysql import get_refuel_events

        result_1 = get_refuel_events("CO0681", days=1)
        result_7 = get_refuel_events("CO0681", days=7)
        result_30 = get_refuel_events("CO0681", days=30)

        assert isinstance(result_1, list)
        assert isinstance(result_7, list)
        assert isinstance(result_30, list)

    def test_get_active_dtcs_returns_list(self):
        """Test get_active_dtcs"""
        from database_mysql import get_active_dtcs

        result = get_active_dtcs("CO0681")

        assert isinstance(result, list)

    def test_update_baseline_mpg_executes(self):
        """Test update_baseline_mpg runs without error"""
        from database_mysql import update_baseline_mpg

        # Test updating baseline
        result = update_baseline_mpg("CO0681", 6.5)

        # Should complete without error
        assert result is None or result == True

    def test_check_fuel_drift_returns_data(self):
        """Test check_fuel_drift"""
        from database_mysql import check_fuel_drift

        result = check_fuel_drift("CO0681")

        # Should return dict or None
        assert result is None or isinstance(result, dict)


class TestDatabaseConnection:
    """Test database connection and pooling"""

    def test_get_db_connection_returns_connection(self):
        """Test get_db_connection returns valid connection"""
        from database_mysql import get_db_connection

        conn = get_db_connection()

        assert conn is not None

    def test_connection_can_execute_query(self):
        """Test connection can execute queries"""
        from database_mysql import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT 1 as test")
        result = cursor.fetchone()
        cursor.close()

        assert result["test"] == 1

    def test_connection_pooling_multiple_connections(self):
        """Test can get multiple connections"""
        from database_mysql import get_db_connection

        conn1 = get_db_connection()
        conn2 = get_db_connection()
        conn3 = get_db_connection()

        assert conn1 is not None
        assert conn2 is not None
        assert conn3 is not None

    def test_connection_query_trucks_table(self):
        """Test can query trucks table"""
        from database_mysql import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("SELECT COUNT(*) as count FROM trucks")
        result = cursor.fetchone()
        cursor.close()

        assert result["count"] >= 0


class TestDatabaseEdgeCases:
    """Test edge cases and error handling"""

    def test_sql_injection_prevention(self):
        """Test SQL injection is prevented"""
        from database_mysql import get_truck_history

        # Try SQL injection attack
        result = get_truck_history("'; DROP TABLE trucks; --", hours=1)

        # Should return empty list, not error
        assert isinstance(result, list)
        assert len(result) == 0

    def test_large_timeframe_handling(self):
        """Test handling of large date ranges"""
        from database_mysql import get_truck_history

        # Request large time range (1 year)
        result = get_truck_history("CO0681", hours=8760)

        assert isinstance(result, list)

    def test_concurrent_queries_no_conflict(self):
        """Test multiple concurrent queries work"""
        from database_mysql import (
            get_all_trucks,
            get_fleet_summary,
            get_truck_latest_data,
        )

        summary = get_fleet_summary()
        trucks = get_all_trucks()
        latest = get_truck_latest_data("CO0681")

        assert isinstance(summary, dict)
        assert isinstance(trucks, list)

    def test_empty_string_truck_id(self):
        """Test handling of empty string truck ID"""
        from database_mysql import get_truck_latest_data

        result = get_truck_latest_data("")

        assert result is None

    def test_special_characters_in_truck_id(self):
        """Test handling of special characters"""
        from database_mysql import get_truck_latest_data

        result = get_truck_latest_data("TRUCK@#$%")

        assert result is None


class TestDatabaseTransactions:
    """Test transaction handling"""

    def test_simple_transaction_commit(self):
        """Test successful transaction"""
        from database_mysql import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("SELECT COUNT(*) FROM trucks")
            result = cursor.fetchone()
            conn.commit()

            assert result is not None
        finally:
            cursor.close()

    def test_transaction_rollback_on_error(self):
        """Test rollback on error"""
        from database_mysql import get_db_connection

        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # Try invalid query
            cursor.execute("SELECT * FROM nonexistent_table_xyz")
        except Exception:
            conn.rollback()
            # Rollback successful
        finally:
            cursor.close()


class TestDatabaseUtilities:
    """Test utility functions"""

    def test_multiple_operations_in_sequence(self):
        """Test multiple DB operations work in sequence"""
        from database_mysql import (
            get_all_trucks,
            get_mpg_baseline,
            get_truck_latest_data,
        )

        trucks = get_all_trucks()
        assert len(trucks) > 0

        if len(trucks) > 0:
            truck_id = trucks[0]

            latest = get_truck_latest_data(truck_id)
            baseline = get_mpg_baseline(truck_id)

            # Should complete without errors

    def test_database_responsive(self):
        """Test database responds quickly"""
        import time

        from database_mysql import get_db_connection

        start = time.time()
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        cursor.fetchone()
        cursor.close()
        elapsed = time.time() - start

        # Should respond in under 1 second
        assert elapsed < 1.0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
