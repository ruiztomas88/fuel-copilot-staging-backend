"""
Unit tests for Driver Scoring Engine
Tests with mocked database connections
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from driver_scoring_engine import (
    DriverScore,
    DriverScoringEngine,
    get_driver_scoring_engine,
)


class TestDriverScore:
    """Test DriverScore dataclass"""

    def test_score_creation(self):
        """Test creating driver score"""
        score = DriverScore(
            truck_id="RA9250",
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 7),
            overall_score=85.5,
            mpg_score=90.0,
            idle_score=80.0,
            consistency_score=86.0,
        )

        assert score.truck_id == "RA9250"
        assert score.overall_score == 85.5
        assert score.grade == "B+"

    def test_grade_assignment_a_plus(self):
        """Test A+ grade"""
        score = DriverScore(
            truck_id="RA9250",
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 7),
            overall_score=96.0,
            mpg_score=95.0,
            idle_score=97.0,
            consistency_score=96.0,
        )
        assert score.grade == "A+"

    def test_grade_assignment_f(self):
        """Test F grade"""
        score = DriverScore(
            truck_id="RA9250",
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 7),
            overall_score=45.0,
            mpg_score=40.0,
            idle_score=50.0,
            consistency_score=45.0,
        )
        assert score.grade == "F"

    def test_to_dict(self):
        """Test converting to dictionary"""
        score = DriverScore(
            truck_id="RA9250",
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 7),
            overall_score=85.5,
            mpg_score=90.0,
            idle_score=80.0,
            consistency_score=86.0,
            fleet_percentile=75.5,
        )

        result = score.to_dict()

        assert result["truck_id"] == "RA9250"
        assert result["overall_score"] == 85.5
        assert result["grade"] == "B+"
        assert result["fleet_percentile"] == 75.5


class TestDriverScoringEngine:
    """Test DriverScoringEngine class"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        db.cursor.return_value.__exit__.return_value = False
        return db, cursor

    @pytest.fixture
    def engine(self, mock_db):
        """Create engine with mock DB"""
        db, _ = mock_db
        return DriverScoringEngine(db_connection=db)

    def test_engine_initialization(self, engine):
        """Test engine initialization"""
        assert engine.mpg_weight == 0.40
        assert engine.idle_weight == 0.30
        assert engine.consistency_weight == 0.30
        assert engine.excellent_mpg_threshold == 1.15

    def test_calculate_score_success(self, engine, mock_db):
        """Test calculating score successfully"""
        db, cursor = mock_db

        # Mock fuel metrics data
        cursor.fetchall.return_value = [
            {"mpg_current": 6.5, "idle_pct": 20.0} for _ in range(50)
        ]

        # Mock baseline query
        cursor.fetchone.return_value = {"baseline_mpg": 6.0}

        score = engine.calculate_score("RA9250", period_days=7)

        assert score is not None
        assert score.truck_id == "RA9250"
        assert 0 <= score.overall_score <= 100
        assert 0 <= score.mpg_score <= 100
        assert 0 <= score.idle_score <= 100
        assert 0 <= score.consistency_score <= 100

    def test_calculate_score_insufficient_data(self, engine, mock_db):
        """Test with insufficient data"""
        db, cursor = mock_db

        cursor.fetchall.return_value = [
            {"mpg_current": 6.5, "idle_pct": 20.0} for _ in range(5)  # Only 5 samples
        ]

        score = engine.calculate_score("RA9250", period_days=7, min_samples=20)

        assert score is None

    def test_mpg_score_excellent(self, engine):
        """Test MPG score - excellent performance"""
        mpg_values = [7.5] * 20  # 15% above baseline of 6.5
        score = engine._calculate_mpg_score("RA9250", mpg_values)

        assert score >= 90

    def test_mpg_score_good(self, engine, mock_db):
        """Test MPG score - good performance"""
        db, cursor = mock_db
        cursor.fetchone.return_value = {"baseline_mpg": 6.5}

        mpg_values = [6.8] * 20  # ~5% above baseline of 6.5
        score = engine._calculate_mpg_score("RA9250", mpg_values)

        assert 70 <= score < 90  # Adjusted threshold

    def test_mpg_score_poor(self, engine, mock_db):
        """Test MPG score - poor performance"""
        db, cursor = mock_db
        cursor.fetchone.return_value = {"baseline_mpg": 6.5}

        mpg_values = [5.5] * 20  # Below baseline
        score = engine._calculate_mpg_score("RA9250", mpg_values)

        assert score < 60

    def test_idle_score_excellent(self, engine):
        """Test idle score - excellent (low idle)"""
        idle_values = [10.0] * 20  # 10% idle
        score = engine._calculate_idle_score(idle_values)

        assert score >= 90

    def test_idle_score_poor(self, engine):
        """Test idle score - poor (high idle)"""
        idle_values = [50.0] * 20  # 50% idle
        score = engine._calculate_idle_score(idle_values)

        assert score < 50

    def test_consistency_score_excellent(self, engine):
        """Test consistency score - very consistent"""
        mpg_values = [6.5 + i * 0.1 for i in range(20)]  # Low variance
        score = engine._calculate_consistency_score(mpg_values)

        assert score >= 70  # Should be high

    def test_consistency_score_poor(self, engine):
        """Test consistency score - erratic"""
        mpg_values = [6.5, 4.0, 8.0, 5.0, 7.5, 4.5] * 5  # High variance
        score = engine._calculate_consistency_score(mpg_values)

        assert score < 70  # Should be lower

    def test_get_fleet_scores(self, engine, mock_db):
        """Test getting fleet scores"""
        db, cursor = mock_db

        # Mock trucks
        cursor.fetchall.side_effect = [
            [{"truck_id": "RA9250"}, {"truck_id": "FF7702"}],  # Trucks
            # Data for RA9250
            [{"mpg_current": 6.5, "idle_pct": 20.0} for _ in range(30)],
            # Data for FF7702
            [{"mpg_current": 5.5, "idle_pct": 35.0} for _ in range(30)],
        ]

        cursor.fetchone.return_value = {"baseline_mpg": 6.0}

        fleet_scores = engine.get_fleet_scores(period_days=7)

        assert isinstance(fleet_scores, dict)
        assert "RA9250" in fleet_scores or "FF7702" in fleet_scores

    def test_store_score_success(self, engine, mock_db):
        """Test storing score"""
        db, cursor = mock_db

        score = DriverScore(
            truck_id="RA9250",
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 7),
            overall_score=85.5,
            mpg_score=90.0,
            idle_score=80.0,
            consistency_score=86.0,
        )

        success = engine.store_score(score)

        assert success is True
        assert cursor.execute.call_count >= 1

    def test_weighted_score_calculation(self, engine, mock_db):
        """Test that weighted score is calculated correctly"""
        db, cursor = mock_db

        cursor.fetchall.return_value = [
            {"mpg_current": 6.5, "idle_pct": 20.0} for _ in range(50)
        ]
        cursor.fetchone.return_value = {"baseline_mpg": 6.0}

        score = engine.calculate_score("RA9250", period_days=7)

        # Verify weighted calculation
        expected_overall = (
            score.mpg_score * 0.40
            + score.idle_score * 0.30
            + score.consistency_score * 0.30
        )

        assert abs(score.overall_score - expected_overall) < 0.1


class TestSingleton:
    """Test singleton pattern"""

    def test_get_driver_scoring_engine_singleton(self):
        """Test that singleton returns same instance"""
        engine1 = get_driver_scoring_engine()
        engine2 = get_driver_scoring_engine()

        assert engine1 is engine2


class TestEdgeCases:
    """Test edge cases"""

    def test_consistency_score_single_value(self):
        """Test consistency with only one value"""
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        db.cursor.return_value.__exit__.return_value = False

        engine = DriverScoringEngine(db_connection=db)

        score = engine._calculate_consistency_score([6.5])
        assert score == 50.0  # Default for insufficient data

    def test_store_score_db_error(self):
        """Test handling database error when storing"""
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        db.cursor.return_value.__exit__.return_value = False

        cursor.execute.side_effect = Exception("DB Error")

        engine = DriverScoringEngine(db_connection=db)

        score = DriverScore(
            truck_id="RA9250",
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 7),
            overall_score=85.5,
            mpg_score=90.0,
            idle_score=80.0,
            consistency_score=86.0,
        )

        success = engine.store_score(score)
        assert success is False
