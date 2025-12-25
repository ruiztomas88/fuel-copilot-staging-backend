"""
Integration tests for Driver Scoring Engine
Tests with real database (fuel_copilot_local)
"""

import os
import time
from datetime import datetime

import pymysql
import pytest
from pymysql.cursors import DictCursor

from driver_scoring_engine import DriverScoringEngine, get_driver_scoring_engine


@pytest.fixture(scope="module")
def db_connection():
    """Get real database connection"""
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

        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()["DATABASE()"]

        if db_name != "fuel_copilot_local":
            conn.close()
            pytest.skip(
                f"Integration tests require fuel_copilot_local (connected to {db_name})"
            )

        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"Could not connect to fuel_copilot_local: {e}")


@pytest.fixture(scope="module")
def engine(db_connection):
    """Create engine with real DB"""
    return DriverScoringEngine(db_connection=db_connection)


@pytest.fixture(scope="module")
def sample_truck_id(db_connection):
    """Get a truck with sufficient data"""
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT truck_id
            FROM fuel_metrics
            WHERE mpg_current IS NOT NULL
              AND mpg_current > 0
              AND engine_hours IS NOT NULL
            GROUP BY truck_id
            HAVING COUNT(*) >= 50
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """
        )
        result = cursor.fetchone()

    if not result:
        pytest.skip("No trucks with sufficient data")

    return result["truck_id"]


class TestDriverScoringEngineIntegration:
    """Integration tests with real database"""

    def test_calculate_score_real_data(self, engine, sample_truck_id):
        """Test calculating score with real data"""
        score = engine.calculate_score(sample_truck_id, period_days=7, min_samples=20)

        if score is None:
            pytest.skip(f"Insufficient data for {sample_truck_id}")

        assert score.truck_id == sample_truck_id
        assert 0 <= score.overall_score <= 100
        assert 0 <= score.mpg_score <= 100
        assert 0 <= score.idle_score <= 100
        assert 0 <= score.consistency_score <= 100
        assert score.grade in ["A+", "A", "B+", "B", "C+", "C", "D", "F"]

        print(f"\n✓ Driver Score for {sample_truck_id}:")
        print(f"  - Overall: {score.overall_score:.1f} ({score.grade})")
        print(f"  - MPG: {score.mpg_score:.1f}")
        print(f"  - Idle: {score.idle_score:.1f}")
        print(f"  - Consistency: {score.consistency_score:.1f}")

    def test_store_and_retrieve_score(self, engine, sample_truck_id, db_connection):
        """Test storing score in database"""
        score = engine.calculate_score(sample_truck_id, period_days=7)

        if score is None:
            pytest.skip(f"Insufficient data for {sample_truck_id}")

        # Store it
        success = engine.store_score(score)
        assert success is True

        # Verify table exists
        with db_connection.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'driver_scores'")
            result = cursor.fetchone()

        assert result is not None

        # Verify data was stored
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM driver_scores
                WHERE truck_id = %s
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (sample_truck_id,),
            )

            stored = cursor.fetchone()

        assert stored is not None
        assert stored["truck_id"] == sample_truck_id
        assert abs(stored["overall_score"] - score.overall_score) < 0.1
        assert stored["grade"] == score.grade

        print(f"\n✓ Score stored and retrieved from database")

    def test_get_fleet_scores_real(self, engine, db_connection):
        """Test getting scores for entire fleet"""
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(DISTINCT truck_id) as count
                FROM fuel_metrics
                WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 7 DAY)
                  AND mpg_current IS NOT NULL
            """
            )
            truck_count = cursor.fetchone()["count"]

        if truck_count == 0:
            pytest.skip("No recent truck data")

        start_time = time.time()
        fleet_scores = engine.get_fleet_scores(period_days=7, min_score=0.0)
        elapsed = time.time() - start_time

        assert isinstance(fleet_scores, dict)
        assert len(fleet_scores) > 0

        # Check percentiles are assigned
        for truck_id, score in fleet_scores.items():
            if score.fleet_percentile is not None:
                assert 0 <= score.fleet_percentile <= 100

        # Performance check
        avg_time = elapsed / max(len(fleet_scores), 1)
        assert avg_time < 2.0, f"Fleet scoring too slow: {avg_time:.2f}s per truck"

        print(f"\n✓ Fleet Scores ({len(fleet_scores)} trucks in {elapsed:.2f}s):")

        # Show top 3 and bottom 3
        sorted_scores = sorted(
            fleet_scores.items(), key=lambda x: x[1].overall_score, reverse=True
        )

        print("\n  Top 3:")
        for i, (truck_id, score) in enumerate(sorted_scores[:3], 1):
            print(f"    {i}. {truck_id}: {score.overall_score:.1f} ({score.grade})")

        print("\n  Bottom 3:")
        for i, (truck_id, score) in enumerate(sorted_scores[-3:], 1):
            print(f"    {i}. {truck_id}: {score.overall_score:.1f} ({score.grade})")

    def test_score_components_reasonable(self, engine, sample_truck_id):
        """Test that score components are reasonable"""
        score = engine.calculate_score(sample_truck_id, period_days=7)

        if score is None:
            pytest.skip(f"Insufficient data for {sample_truck_id}")

        # Verify weighted calculation
        calculated_overall = (
            score.mpg_score * 0.40
            + score.idle_score * 0.30
            + score.consistency_score * 0.30
        )

        assert abs(score.overall_score - calculated_overall) < 0.1
        print(f"\n✓ Score weighting verified correctly")

    def test_singleton_instance(self):
        """Test singleton pattern"""
        engine1 = get_driver_scoring_engine()
        engine2 = get_driver_scoring_engine()

        assert engine1 is engine2
        print("\n✓ Singleton pattern working")

    def test_performance_benchmark(self, engine, db_connection):
        """Benchmark performance on real data"""
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT truck_id
                FROM fuel_metrics
                WHERE mpg_current IS NOT NULL
                GROUP BY truck_id
                HAVING COUNT(*) >= 50
                ORDER BY COUNT(*) DESC
                LIMIT 5
            """
            )
            trucks = [row["truck_id"] for row in cursor.fetchall()]

        if len(trucks) == 0:
            pytest.skip("No trucks with sufficient data")

        times = []
        for truck_id in trucks:
            start = time.time()
            engine.calculate_score(truck_id, period_days=7)
            times.append(time.time() - start)

        avg_time = sum(times) / len(times)

        print(f"\n✓ Performance Benchmark ({len(trucks)} trucks):")
        print(f"  - Average: {avg_time:.3f}s per truck")
        print(f"  - Min: {min(times):.3f}s")
        print(f"  - Max: {max(times):.3f}s")

        assert avg_time < 1.0, "Scoring too slow"


class TestErrorHandling:
    """Test error handling"""

    def test_invalid_truck_id(self, engine):
        """Test handling invalid truck ID"""
        score = engine.calculate_score("INVALID_TRUCK_999", period_days=7)

        assert score is None
        print("\n✓ Invalid truck ID handled gracefully")

    def test_insufficient_data(self, engine):
        """Test with truck that has insufficient data"""
        score = engine.calculate_score("TRUCK_NO_DATA", period_days=1)

        assert score is None
        print("\n✓ Insufficient data handled gracefully")
