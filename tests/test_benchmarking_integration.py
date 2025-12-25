"""
Integration tests for Benchmarking Engine
Tests with real database (fuel_copilot_local)
"""

import os
import time
from datetime import datetime, timedelta

import pymysql
import pytest
from pymysql.cursors import DictCursor

from benchmarking_engine import BenchmarkingEngine, get_benchmarking_engine


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
def engine(db_connection):
    """Create benchmarking engine with real DB"""
    return BenchmarkingEngine(db_connection=db_connection)


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


class TestBenchmarkingEngineIntegration:
    """Integration tests with real database"""

    def test_identify_peer_group_real_data(self, engine, sample_truck_id):
        """Test identifying peer group with real truck"""
        peer_group = engine.identify_peer_group(sample_truck_id)

        assert peer_group is not None
        assert sample_truck_id in peer_group.truck_ids
        assert len(peer_group.truck_ids) >= 1

        print(f"\n✓ Peer group for {sample_truck_id}: {peer_group}")
        print(f"  - Make: {peer_group.make}")
        print(f"  - Model: {peer_group.model}")
        print(f"  - Year: {peer_group.year}")
        print(f"  - Peers found: {len(peer_group.truck_ids)}")

    def test_get_mpg_data_real(self, engine, db_connection):
        """Test getting MPG data for real trucks"""
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT truck_id 
                FROM fuel_metrics 
                WHERE mpg_current IS NOT NULL 
                GROUP BY truck_id 
                LIMIT 5
            """
            )
            truck_ids = [row["truck_id"] for row in cursor.fetchall()]

        if not truck_ids:
            pytest.skip("No trucks with MPG data found")

        mpg_data = engine.get_mpg_data(truck_ids, period_days=7, min_samples=5)

        assert isinstance(mpg_data, dict)
        assert len(mpg_data) > 0

        print(f"\n✓ MPG data for {len(mpg_data)} trucks:")
        for truck_id, mpg in sorted(mpg_data.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {truck_id}: {mpg:.2f} MPG")

    def test_benchmark_mpg_real(self, engine, sample_truck_id):
        """Test benchmarking MPG with real data"""
        result = engine.benchmark_metric(sample_truck_id, "mpg", period_days=7)

        if result is None:
            pytest.skip(f"Insufficient data to benchmark {sample_truck_id}")

        assert result.truck_id == sample_truck_id
        assert result.metric_name == "mpg"
        assert result.actual_value > 0
        assert result.benchmark_value > 0
        assert 0 <= result.percentile <= 100
        assert result.peer_count >= 0
        assert result.performance_tier in [
            "TOP_10",
            "TOP_25",
            "AVERAGE",
            "BELOW_AVERAGE",
            "BOTTOM_25",
        ]
        assert 0 <= result.confidence <= 1

        print(f"\n✓ MPG Benchmark for {sample_truck_id}:")
        print(f"  - Actual: {result.actual_value:.2f} MPG")
        print(f"  - Benchmark: {result.benchmark_value:.2f} MPG")
        print(f"  - Percentile: {result.percentile:.1f}%")
        print(f"  - Deviation: {result.deviation_pct:+.1f}%")
        print(f"  - Tier: {result.performance_tier}")
        print(f"  - Peers: {result.peer_count}")
        print(f"  - Confidence: {result.confidence:.2f}")

    def test_benchmark_truck_all_metrics_real(self, engine, sample_truck_id):
        """Test benchmarking all metrics with real data"""
        results = engine.benchmark_truck(sample_truck_id, period_days=7)

        assert isinstance(results, dict)

        print(f"\n✓ Complete benchmark for {sample_truck_id}:")

        for metric_name, result in results.items():
            if result:
                print(f"\n  {metric_name.upper()}:")
                print(f"    - Actual: {result.actual_value:.2f}")
                print(f"    - Benchmark: {result.benchmark_value:.2f}")
                print(f"    - Percentile: {result.percentile:.1f}%")
                print(f"    - Tier: {result.performance_tier}")
                print(f"    - Deviation: {result.deviation_pct:+.1f}%")

    def test_get_fleet_outliers_real(self, engine):
        """Test finding fleet outliers with real data"""
        outliers = engine.get_fleet_outliers(
            metric_name="mpg", period_days=7, threshold_percentile=25.0
        )

        assert isinstance(outliers, list)

        if len(outliers) == 0:
            print("\n✓ No MPG outliers found (all trucks performing well)")
        else:
            print(f"\n✓ Found {len(outliers)} MPG outliers (bottom 25%):")
            for i, result in enumerate(outliers[:5], 1):
                print(f"\n  {i}. {result.truck_id}")
                print(
                    f"     - MPG: {result.actual_value:.2f} (vs {result.benchmark_value:.2f} benchmark)"
                )
                print(f"     - Percentile: {result.percentile:.1f}%")
                print(f"     - Deviation: {result.deviation_pct:+.1f}%")
                print(f"     - Tier: {result.performance_tier}")

    def test_singleton_instance(self):
        """Test that singleton returns same instance"""
        engine1 = get_benchmarking_engine()
        engine2 = get_benchmarking_engine()

        assert engine1 is engine2
        print("\n✓ Singleton pattern working correctly")

    def test_performance_baseline(self, engine, db_connection):
        """Test performance baseline (should complete in reasonable time)"""
        with db_connection.cursor() as cursor:
            cursor.execute(
                "SELECT truck_id FROM fuel_metrics GROUP BY truck_id LIMIT 5"
            )
            truck_ids = [row["truck_id"] for row in cursor.fetchall()]

        if not truck_ids:
            pytest.skip("No trucks found")

        start_time = time.time()

        for truck_id in truck_ids:
            engine.benchmark_truck(truck_id, period_days=7)

        elapsed = time.time() - start_time
        avg_time = elapsed / len(truck_ids)

        # Should complete in <2 seconds per truck on average
        assert avg_time < 2.0, f"Benchmarking too slow: {avg_time:.2f}s per truck"

        print(f"\n✓ Performance: {len(truck_ids)} trucks benchmarked in {elapsed:.2f}s")
        print(f"  - Average: {avg_time:.3f}s per truck")


class TestErrorHandling:
    """Test error handling in integration scenarios"""

    def test_invalid_truck_id(self, engine):
        """Test handling of invalid truck ID"""
        result = engine.benchmark_metric("INVALID_TRUCK_999", "mpg", period_days=7)

        # Should return None or handle gracefully
        assert result is None or result.peer_count == 0
        print("\n✓ Invalid truck ID handled gracefully")

    def test_insufficient_data_period(self, engine, sample_truck_id):
        """Test with very short period (may have insufficient data)"""
        result = engine.benchmark_metric(sample_truck_id, "mpg", period_days=1)

        # Should either return None or valid result
        if result is not None:
            assert result.actual_value > 0
            assert 0 <= result.percentile <= 100

        print("\n✓ Short period handled correctly")

    def test_extreme_parameters(self, engine, sample_truck_id):
        """Test with extreme parameters"""
        # Very long period
        result = engine.benchmark_metric(sample_truck_id, "mpg", period_days=365)

        # Should handle gracefully (may have insufficient data or valid result)
        assert result is None or isinstance(result.actual_value, float)

        print("\n✓ Extreme parameters handled correctly")
