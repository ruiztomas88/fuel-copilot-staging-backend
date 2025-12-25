"""
Integration tests for MPG Baseline Tracker
Tests with real database (fuel_copilot_local)
"""

import os
import time
from datetime import datetime, timedelta

import pymysql
import pytest
from pymysql.cursors import DictCursor

from mpg_baseline_tracker import MPGBaselineTracker, get_mpg_baseline_tracker


@pytest.fixture(scope="module")
def db_connection():
    """Get real database connection for integration tests"""
    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "fuel_copilot_local"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            charset="utf8mb4",
            autocommit=True,
            cursorclass=DictCursor,
        )

        # Verify we're connected to fuel_copilot_local
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()["DATABASE()"]

        if db_name != "fuel_copilot_local":
            conn.close()
            pytest.skip(
                f"Integration tests require fuel_copilot_local database (connected to {db_name})"
            )

        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"Could not connect to fuel_copilot_local: {e}")


@pytest.fixture(scope="module")
def tracker(db_connection):
    """Create tracker with real DB"""
    return MPGBaselineTracker(db_connection=db_connection)


@pytest.fixture(scope="module")
def sample_truck_id(db_connection):
    """Get a sample truck ID from database"""
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT truck_id 
            FROM fuel_metrics 
            WHERE mpg_current IS NOT NULL 
              AND mpg_current > 0 
            GROUP BY truck_id 
            HAVING COUNT(*) >= 50
            ORDER BY COUNT(*) DESC 
            LIMIT 1
        """
        )
        result = cursor.fetchone()

    if not result:
        pytest.skip("No trucks with sufficient data found")

    return result["truck_id"]


class TestMPGBaselineTrackerIntegration:
    """Integration tests with real database"""

    def test_calculate_baseline_real_data(self, tracker, sample_truck_id):
        """Test calculating baseline with real data"""
        baseline = tracker.calculate_baseline(
            sample_truck_id, period_days=7, min_samples=10
        )

        if baseline is None:
            pytest.skip(f"Insufficient data for {sample_truck_id}")

        assert baseline.truck_id == sample_truck_id
        assert 2.0 < baseline.baseline_mpg < 12.0
        assert baseline.sample_count >= 10
        assert baseline.std_dev >= 0
        assert 0 <= baseline.confidence <= 1

        print(f"\n✓ Baseline for {sample_truck_id}:")
        print(f"  - MPG: {baseline.baseline_mpg:.2f}")
        print(f"  - Samples: {baseline.sample_count}")
        print(f"  - Std Dev: {baseline.std_dev:.2f}")
        print(f"  - Confidence: {baseline.confidence:.2f}")

    def test_store_and_retrieve_baseline(self, tracker, sample_truck_id):
        """Test storing and retrieving baseline"""
        # Calculate baseline
        baseline = tracker.calculate_baseline(
            sample_truck_id, period_days=7, min_samples=10
        )

        if baseline is None:
            pytest.skip(f"Insufficient data for {sample_truck_id}")

        # Store it
        success = tracker.store_baseline(baseline)
        assert success is True

        # Retrieve it
        retrieved = tracker.get_latest_baseline(sample_truck_id)
        assert retrieved is not None
        assert retrieved.truck_id == sample_truck_id
        assert abs(retrieved.baseline_mpg - baseline.baseline_mpg) < 0.01

        print(f"\n✓ Stored and retrieved baseline for {sample_truck_id}")
        print(f"  - Baseline MPG: {retrieved.baseline_mpg:.2f}")

    def test_check_degradation_real_data(self, tracker, sample_truck_id):
        """Test checking degradation with real data"""
        # First ensure we have a baseline
        baseline = tracker.calculate_baseline(
            sample_truck_id, period_days=7, min_samples=10
        )
        if baseline:
            tracker.store_baseline(baseline)

        # Check for degradation (using lenient threshold)
        degradation = tracker.check_degradation(
            sample_truck_id, check_period_days=2, threshold_pct=3.0
        )

        if degradation:
            print(f"\n✓ Degradation detected for {sample_truck_id}:")
            print(f"  - Current MPG: {degradation.current_mpg:.2f}")
            print(f"  - Baseline MPG: {degradation.baseline_mpg:.2f}")
            print(f"  - Degradation: {degradation.degradation_pct:.1f}%")
            print(f"  - Severity: {degradation.severity}")
        else:
            print(f"\n✓ No significant degradation for {sample_truck_id}")

    def test_get_all_degradations_real(self, tracker):
        """Test getting all degradations with real data"""
        # Update baselines first
        tracker.update_all_baselines(period_days=7)

        # Check for degradations
        degradations = tracker.get_all_degradations(
            threshold_pct=5.0, check_period_days=2
        )

        assert isinstance(degradations, list)

        if len(degradations) == 0:
            print("\n✓ No degradations detected (all trucks performing well)")
        else:
            print(f"\n✓ Found {len(degradations)} degradations:")
            for i, deg in enumerate(degradations[:5], 1):  # Show top 5
                print(f"\n  {i}. {deg.truck_id}")
                print(f"     - Current: {deg.current_mpg:.2f} MPG")
                print(f"     - Baseline: {deg.baseline_mpg:.2f} MPG")
                print(f"     - Degradation: {deg.degradation_pct:.1f}%")
                print(f"     - Severity: {deg.severity}")

    def test_update_all_baselines_real(self, tracker, db_connection):
        """Test updating baselines for all trucks"""
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(DISTINCT truck_id) as truck_count
                FROM fuel_metrics
                WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 7 DAY)
                  AND mpg_current IS NOT NULL
            """
            )
            expected_trucks = cursor.fetchone()["truck_count"]

        if expected_trucks == 0:
            pytest.skip("No trucks with recent data")

        start_time = time.time()
        results = tracker.update_all_baselines(period_days=7)
        elapsed = time.time() - start_time

        assert isinstance(results, dict)
        assert len(results) > 0

        successful = sum(1 for v in results.values() if v)

        print(f"\n✓ Updated baselines for {len(results)} trucks in {elapsed:.2f}s")
        print(f"  - Successful: {successful}")
        print(f"  - Failed: {len(results) - successful}")
        print(f"  - Average: {elapsed/len(results):.3f}s per truck")

    def test_singleton_instance(self):
        """Test that singleton returns same instance"""
        tracker1 = get_mpg_baseline_tracker()
        tracker2 = get_mpg_baseline_tracker()

        assert tracker1 is tracker2
        print("\n✓ Singleton pattern working correctly")

    def test_database_table_creation(self, tracker, db_connection):
        """Test that mpg_baselines table is created"""
        # Store a baseline to trigger table creation
        from mpg_baseline_tracker import MPGBaseline

        baseline = MPGBaseline(
            truck_id="TEST_TRUCK",
            baseline_mpg=6.5,
            period_start=datetime(2024, 12, 1),
            period_end=datetime(2024, 12, 7),
            sample_count=100,
            std_dev=0.8,
            confidence=0.95,
        )

        tracker.store_baseline(baseline)

        # Check table exists
        with db_connection.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'mpg_baselines'")
            result = cursor.fetchone()

        assert result is not None

        # Check columns
        with db_connection.cursor() as cursor:
            cursor.execute("DESCRIBE mpg_baselines")
            columns = {row["Field"] for row in cursor.fetchall()}

        required_columns = {
            "id",
            "truck_id",
            "baseline_mpg",
            "period_start",
            "period_end",
            "sample_count",
            "std_dev",
            "confidence",
            "created_at",
        }

        assert required_columns.issubset(columns)
        print("\n✓ mpg_baselines table created with correct schema")

    def test_performance_baseline(self, tracker, db_connection):
        """Test performance baseline"""
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT truck_id 
                FROM fuel_metrics 
                GROUP BY truck_id 
                HAVING COUNT(*) >= 20
                LIMIT 5
            """
            )
            truck_ids = [row["truck_id"] for row in cursor.fetchall()]

        if not truck_ids:
            pytest.skip("No trucks found")

        start_time = time.time()

        for truck_id in truck_ids:
            tracker.calculate_baseline(truck_id, period_days=7, min_samples=10)

        elapsed = time.time() - start_time
        avg_time = elapsed / len(truck_ids)

        # Should complete in <1 second per truck
        assert (
            avg_time < 1.0
        ), f"Baseline calculation too slow: {avg_time:.2f}s per truck"

        print(
            f"\n✓ Performance: {len(truck_ids)} baselines calculated in {elapsed:.2f}s"
        )
        print(f"  - Average: {avg_time:.3f}s per truck")


class TestErrorHandling:
    """Test error handling in integration scenarios"""

    def test_invalid_truck_id(self, tracker):
        """Test handling of invalid truck ID"""
        baseline = tracker.calculate_baseline("INVALID_TRUCK_999", period_days=7)

        assert baseline is None
        print("\n✓ Invalid truck ID handled gracefully")

    def test_no_baseline_degradation_check(self, tracker):
        """Test degradation check when no baseline exists"""
        degradation = tracker.check_degradation("TRUCK_WITH_NO_BASELINE")

        assert degradation is None
        print("\n✓ Missing baseline handled gracefully")

    def test_insufficient_recent_data(self, tracker, sample_truck_id):
        """Test degradation check with insufficient recent data"""
        # Ensure baseline exists
        baseline = tracker.calculate_baseline(
            sample_truck_id, period_days=7, min_samples=10
        )
        if baseline:
            tracker.store_baseline(baseline)

        # Check with very short period (likely insufficient data)
        degradation = tracker.check_degradation(
            sample_truck_id, check_period_days=1, threshold_pct=5.0
        )

        # Should handle gracefully (return None or valid result)
        if degradation:
            assert degradation.truck_id == sample_truck_id

        print("\n✓ Insufficient recent data handled correctly")
