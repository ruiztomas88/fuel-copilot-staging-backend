"""
Unit tests for MPG Baseline Tracker
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from mpg_baseline_tracker import (
    MPGBaseline,
    MPGBaselineTracker,
    MPGDegradation,
    get_mpg_baseline_tracker,
)


class TestMPGBaseline:
    """Test MPGBaseline dataclass"""

    def test_baseline_creation(self):
        """Test creating baseline"""
        baseline = MPGBaseline(
            truck_id="RA9250",
            baseline_mpg=6.5,
            period_start=datetime(2024, 12, 1),
            period_end=datetime(2024, 12, 31),
            sample_count=150,
            std_dev=0.8,
            confidence=0.95,
        )

        assert baseline.truck_id == "RA9250"
        assert baseline.baseline_mpg == 6.5
        assert baseline.sample_count == 150
        assert baseline.confidence == 0.95

    def test_baseline_to_dict(self):
        """Test converting baseline to dict"""
        baseline = MPGBaseline(
            truck_id="RA9250",
            baseline_mpg=6.543,
            period_start=datetime(2024, 12, 1),
            period_end=datetime(2024, 12, 31),
            sample_count=150,
            std_dev=0.876,
            confidence=0.9543,
        )

        d = baseline.to_dict()

        assert d["truck_id"] == "RA9250"
        assert d["baseline_mpg"] == 6.54  # Rounded to 2 decimals
        assert d["std_dev"] == 0.88
        assert d["confidence"] == 0.95


class TestMPGDegradation:
    """Test MPGDegradation dataclass"""

    def test_degradation_creation(self):
        """Test creating degradation"""
        deg = MPGDegradation(
            truck_id="RA9250",
            current_mpg=5.8,
            baseline_mpg=6.5,
            degradation_pct=10.8,
            days_declining=3,
            severity="MEDIUM",
            timestamp=datetime.utcnow(),
        )

        assert deg.truck_id == "RA9250"
        assert deg.degradation_pct == 10.8
        assert deg.severity == "MEDIUM"

    def test_degradation_to_dict(self):
        """Test converting degradation to dict"""
        deg = MPGDegradation(
            truck_id="RA9250",
            current_mpg=5.843,
            baseline_mpg=6.512,
            degradation_pct=10.789,
            days_declining=3,
            severity="MEDIUM",
            timestamp=datetime(2024, 12, 23),
        )

        d = deg.to_dict()

        assert d["current_mpg"] == 5.84
        assert d["degradation_pct"] == 10.8
        assert d["severity"] == "MEDIUM"


class TestMPGBaselineTracker:
    """Test MPGBaselineTracker"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database connection"""
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        db.cursor.return_value.__exit__.return_value = None
        return db, cursor

    @pytest.fixture
    def tracker(self, mock_db):
        """Create tracker with mock DB"""
        db, cursor = mock_db
        return MPGBaselineTracker(db_connection=db)

    def test_tracker_initialization(self):
        """Test tracker initialization"""
        with patch("pymysql.connect") as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db

            tracker = MPGBaselineTracker()
            assert tracker.db is not None
            assert tracker._should_close_db is True

    def test_calculate_baseline_success(self, tracker, mock_db):
        """Test calculating baseline with sufficient data"""
        db, cursor = mock_db

        # Mock MPG data (100 samples)
        cursor.fetchall.return_value = [
            {"mpg_current": 6.5, "timestamp_utc": datetime(2024, 12, i % 28 + 1)}
            for i in range(100)
        ]

        baseline = tracker.calculate_baseline("RA9250", period_days=30)

        assert baseline is not None
        assert baseline.truck_id == "RA9250"
        assert baseline.baseline_mpg == 6.5
        assert baseline.sample_count == 100
        assert 0 <= baseline.confidence <= 1

    def test_calculate_baseline_insufficient_data(self, tracker, mock_db):
        """Test calculating baseline with insufficient data"""
        db, cursor = mock_db

        # Only 10 samples (need 50+)
        cursor.fetchall.return_value = [
            {"mpg_current": 6.5, "timestamp_utc": datetime(2024, 12, 1)}
            for i in range(10)
        ]

        baseline = tracker.calculate_baseline("RA9250", period_days=30, min_samples=50)

        assert baseline is None

    def test_calculate_baseline_variance(self, tracker, mock_db):
        """Test baseline with high variance reduces confidence"""
        db, cursor = mock_db

        # High variance data
        mpg_values = [4.0, 8.0, 5.0, 7.5, 4.5, 8.5] * 20  # 120 samples, high variance
        cursor.fetchall.return_value = [
            {"mpg_current": mpg, "timestamp_utc": datetime(2024, 12, i % 28 + 1)}
            for i, mpg in enumerate(mpg_values)
        ]

        baseline = tracker.calculate_baseline("RA9250", period_days=30)

        assert baseline is not None
        assert baseline.std_dev > 1.0
        assert baseline.confidence < 1.0  # Reduced due to variance

    def test_store_baseline_success(self, tracker, mock_db):
        """Test storing baseline"""
        db, cursor = mock_db

        baseline = MPGBaseline(
            truck_id="RA9250",
            baseline_mpg=6.5,
            period_start=datetime(2024, 12, 1),
            period_end=datetime(2024, 12, 31),
            sample_count=150,
            std_dev=0.8,
            confidence=0.95,
        )

        result = tracker.store_baseline(baseline)

        assert result is True
        assert cursor.execute.call_count >= 2  # CREATE TABLE + INSERT

    def test_get_latest_baseline_found(self, tracker, mock_db):
        """Test getting latest baseline when exists"""
        db, cursor = mock_db

        cursor.fetchone.return_value = {
            "truck_id": "RA9250",
            "baseline_mpg": 6.5,
            "period_start": datetime(2024, 12, 1),
            "period_end": datetime(2024, 12, 31),
            "sample_count": 150,
            "std_dev": 0.8,
            "confidence": 0.95,
        }

        baseline = tracker.get_latest_baseline("RA9250")

        assert baseline is not None
        assert baseline.truck_id == "RA9250"
        assert baseline.baseline_mpg == 6.5

    def test_get_latest_baseline_not_found(self, tracker, mock_db):
        """Test getting baseline when none exists"""
        db, cursor = mock_db

        cursor.fetchone.return_value = None

        baseline = tracker.get_latest_baseline("RA9250")

        assert baseline is None

    def test_check_degradation_detected(self, tracker, mock_db):
        """Test degradation detection"""
        db, cursor = mock_db

        # Mock baseline retrieval
        cursor.fetchone.return_value = {
            "truck_id": "RA9250",
            "baseline_mpg": 6.5,
            "period_start": datetime(2024, 12, 1),
            "period_end": datetime(2024, 12, 31),
            "sample_count": 150,
            "std_dev": 0.8,
            "confidence": 0.95,
        }

        # Mock current MPG (degraded)
        cursor.fetchall.return_value = []  # For get_latest_baseline
        cursor.fetchone.side_effect = [
            # First call: get_latest_baseline
            {
                "truck_id": "RA9250",
                "baseline_mpg": 6.5,
                "period_start": datetime(2024, 12, 1),
                "period_end": datetime(2024, 12, 31),
                "sample_count": 150,
                "std_dev": 0.8,
                "confidence": 0.95,
            },
            # Second call: recent MPG (10% degradation)
            {
                "current_mpg": 5.85,  # Down from 6.5
                "sample_count": 50,
                "period_start": datetime(2024, 12, 20),
            },
        ]

        degradation = tracker.check_degradation(
            "RA9250", check_period_days=3, threshold_pct=5.0
        )

        assert degradation is not None
        assert degradation.truck_id == "RA9250"
        assert (
            abs(degradation.degradation_pct - 10.0) < 0.01
        )  # Handle floating point precision
        assert degradation.severity == "MEDIUM"

    def test_check_degradation_not_detected(self, tracker, mock_db):
        """Test when no significant degradation"""
        db, cursor = mock_db

        cursor.fetchone.side_effect = [
            {
                "truck_id": "RA9250",
                "baseline_mpg": 6.5,
                "period_start": datetime(2024, 12, 1),
                "period_end": datetime(2024, 12, 31),
                "sample_count": 150,
                "std_dev": 0.8,
                "confidence": 0.95,
            },
            {
                "current_mpg": 6.45,  # Only 0.77% drop
                "sample_count": 50,
                "period_start": datetime(2024, 12, 20),
            },
        ]

        degradation = tracker.check_degradation(
            "RA9250", check_period_days=3, threshold_pct=5.0
        )

        assert degradation is None

    def test_check_degradation_no_baseline(self, tracker, mock_db):
        """Test degradation check when no baseline exists"""
        db, cursor = mock_db

        cursor.fetchone.return_value = None

        degradation = tracker.check_degradation("RA9250")

        assert degradation is None

    def test_degradation_severity_levels(self, tracker, mock_db):
        """Test severity classification"""
        db, cursor = mock_db

        test_cases = [
            (25.0, "CRITICAL"),  # 25% degradation
            (18.0, "HIGH"),  # 18% degradation
            (12.0, "MEDIUM"),  # 12% degradation
            (7.0, "LOW"),  # 7% degradation
        ]

        for degradation_pct, expected_severity in test_cases:
            baseline_mpg = 6.5
            current_mpg = baseline_mpg * (1 - degradation_pct / 100)

            cursor.fetchone.side_effect = [
                {
                    "truck_id": "RA9250",
                    "baseline_mpg": baseline_mpg,
                    "period_start": datetime(2024, 12, 1),
                    "period_end": datetime(2024, 12, 31),
                    "sample_count": 150,
                    "std_dev": 0.8,
                    "confidence": 0.95,
                },
                {
                    "current_mpg": current_mpg,
                    "sample_count": 50,
                    "period_start": datetime(2024, 12, 20),
                },
            ]

            degradation = tracker.check_degradation("RA9250", threshold_pct=5.0)

            assert degradation is not None
            assert degradation.severity == expected_severity

    def test_get_all_degradations(self, tracker, mock_db):
        """Test getting all fleet degradations"""
        db, cursor = mock_db

        # Mock active trucks
        cursor.fetchall.return_value = [
            {"truck_id": "RA9250"},
            {"truck_id": "RA9251"},
            {"truck_id": "RA9252"},
        ]

        # Mock degradation checks (only RA9250 has degradation)
        cursor.fetchone.side_effect = [
            # RA9250 - has degradation
            {
                "truck_id": "RA9250",
                "baseline_mpg": 6.5,
                "period_start": datetime(2024, 12, 1),
                "period_end": datetime(2024, 12, 31),
                "sample_count": 150,
                "std_dev": 0.8,
                "confidence": 0.95,
            },
            {
                "current_mpg": 5.85,
                "sample_count": 50,
                "period_start": datetime(2024, 12, 20),
            },
            # RA9251 - no degradation
            {
                "truck_id": "RA9251",
                "baseline_mpg": 6.2,
                "period_start": datetime(2024, 12, 1),
                "period_end": datetime(2024, 12, 31),
                "sample_count": 140,
                "std_dev": 0.7,
                "confidence": 0.92,
            },
            {
                "current_mpg": 6.15,
                "sample_count": 45,
                "period_start": datetime(2024, 12, 20),
            },
            # RA9252 - no baseline
            None,
        ]

        degradations = tracker.get_all_degradations(threshold_pct=5.0)

        assert len(degradations) == 1
        assert degradations[0].truck_id == "RA9250"

    def test_update_all_baselines(self, tracker, mock_db):
        """Test updating baselines for all trucks"""
        db, cursor = mock_db

        # Mock active trucks
        cursor.execute.return_value = None
        cursor.fetchall.side_effect = [
            # First call: get active trucks
            [{"truck_id": "RA9250"}, {"truck_id": "RA9251"}],
            # Second call: RA9250 MPG data
            [
                {"mpg_current": 6.5, "timestamp_utc": datetime(2024, 12, i % 28 + 1)}
                for i in range(100)
            ],
            # Third call: RA9251 MPG data
            [
                {"mpg_current": 6.2, "timestamp_utc": datetime(2024, 12, i % 28 + 1)}
                for i in range(80)
            ],
        ]

        results = tracker.update_all_baselines(period_days=30)

        assert len(results) == 2
        assert "RA9250" in results
        assert "RA9251" in results


class TestSingleton:
    """Test singleton pattern"""

    def test_get_mpg_baseline_tracker_singleton(self):
        """Test that get_mpg_baseline_tracker returns singleton"""
        with patch("pymysql.connect") as mock_connect:
            mock_connect.return_value = MagicMock()

            tracker1 = get_mpg_baseline_tracker()
            tracker2 = get_mpg_baseline_tracker()

            assert tracker1 is tracker2


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def mock_db(self):
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        db.cursor.return_value.__exit__.return_value = None
        return db, cursor

    @pytest.fixture
    def tracker(self, mock_db):
        db, cursor = mock_db
        return MPGBaselineTracker(db_connection=db)

    def test_database_error_handling(self, tracker, mock_db):
        """Test handling database errors"""
        db, cursor = mock_db

        cursor.execute.side_effect = Exception("Database error")

        baseline = tracker.calculate_baseline("RA9250")
        assert baseline is None

    def test_empty_results(self, tracker, mock_db):
        """Test handling empty results"""
        db, cursor = mock_db

        cursor.fetchall.return_value = []

        baseline = tracker.calculate_baseline("RA9250")
        assert baseline is None
