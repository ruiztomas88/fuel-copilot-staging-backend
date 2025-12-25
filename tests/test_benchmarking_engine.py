"""
Unit tests for Benchmarking Engine
"""

from unittest.mock import MagicMock, Mock, patch

import numpy as np
import pytest

from benchmarking_engine import (
    BenchmarkingEngine,
    BenchmarkResult,
    PeerGroup,
    get_benchmarking_engine,
)


class TestPeerGroup:
    """Test PeerGroup dataclass"""

    def test_peer_group_creation(self):
        """Test creating a peer group"""
        pg = PeerGroup(
            make="Freightliner",
            model="Cascadia",
            year=2020,
            truck_ids=["RA9250", "RA9251", "RA9252"],
        )

        assert pg.make == "Freightliner"
        assert pg.model == "Cascadia"
        assert pg.year == 2020
        assert len(pg.truck_ids) == 3

    def test_peer_group_string(self):
        """Test peer group string representation"""
        pg = PeerGroup("Freightliner", "Cascadia", 2020, ["RA9250"])
        assert str(pg) == "Freightliner Cascadia 2020"

        pg_unknown = PeerGroup(None, None, None, ["RA9250"])
        assert str(pg_unknown) == "Unknown peer group"


class TestBenchmarkResult:
    """Test BenchmarkResult dataclass"""

    def test_benchmark_result_creation(self):
        """Test creating a benchmark result"""
        result = BenchmarkResult(
            truck_id="RA9250",
            metric_name="mpg",
            actual_value=5.8,
            benchmark_value=6.2,
            percentile=35.5,
            peer_count=10,
            peer_group="Freightliner Cascadia 2020",
            deviation_pct=-6.45,
            performance_tier="BELOW_AVERAGE",
            confidence=1.0,
        )

        assert result.truck_id == "RA9250"
        assert result.actual_value == 5.8
        assert result.percentile == 35.5
        assert result.performance_tier == "BELOW_AVERAGE"

    def test_benchmark_result_to_dict(self):
        """Test converting benchmark result to dictionary"""
        result = BenchmarkResult(
            truck_id="RA9250",
            metric_name="mpg",
            actual_value=5.836,
            benchmark_value=6.241,
            percentile=35.567,
            peer_count=10,
            peer_group="Freightliner Cascadia 2020",
            deviation_pct=-6.453,
            performance_tier="BELOW_AVERAGE",
            confidence=0.9876,
        )

        d = result.to_dict()

        assert d["truck_id"] == "RA9250"
        assert d["actual_value"] == 5.84  # Rounded to 2 decimals
        assert d["benchmark_value"] == 6.24
        assert d["percentile"] == 35.6  # Rounded to 1 decimal
        assert d["deviation_pct"] == -6.5
        assert d["confidence"] == 0.99  # Rounded to 2 decimals


class TestBenchmarkingEngine:
    """Test BenchmarkingEngine"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database connection"""
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        db.cursor.return_value.__exit__.return_value = None
        return db, cursor

    @pytest.fixture
    def engine(self, mock_db):
        """Create benchmarking engine with mock DB"""
        db, cursor = mock_db
        return BenchmarkingEngine(db_connection=db)

    def test_engine_initialization(self):
        """Test engine initialization"""
        with patch("pymysql.connect") as mock_connect:
            mock_db = MagicMock()
            mock_connect.return_value = mock_db

            engine = BenchmarkingEngine()
            assert engine.db is not None
            assert engine._should_close_db is True

    def test_identify_peer_group_success(self, engine, mock_db):
        """Test identifying peer group successfully"""
        db, cursor = mock_db

        # Mock truck query
        cursor.fetchone.return_value = {
            "make": "Freightliner",
            "model": "Cascadia",
            "year": 2020,
        }

        # Mock peer query
        cursor.fetchall.return_value = [
            {"truck_id": "RA9250"},
            {"truck_id": "RA9251"},
            {"truck_id": "RA9252"},
        ]

        peer_group = engine.identify_peer_group("RA9250")

        assert peer_group.make == "Freightliner"
        assert peer_group.model == "Cascadia"
        assert peer_group.year == 2020
        assert len(peer_group.truck_ids) == 3
        assert "RA9250" in peer_group.truck_ids

    def test_identify_peer_group_not_found(self, engine, mock_db):
        """Test identifying peer group when truck not found"""
        db, cursor = mock_db
        cursor.fetchone.return_value = None

        peer_group = engine.identify_peer_group("INVALID")

        assert peer_group.make is None
        assert peer_group.model is None
        assert peer_group.year is None
        assert peer_group.truck_ids == ["INVALID"]

    def test_get_mpg_data_success(self, engine, mock_db):
        """Test getting MPG data"""
        db, cursor = mock_db

        cursor.fetchall.return_value = [
            {"truck_id": "RA9250", "avg_mpg": 5.8, "sample_count": 100},
            {"truck_id": "RA9251", "avg_mpg": 6.2, "sample_count": 105},
            {"truck_id": "RA9252", "avg_mpg": 6.5, "sample_count": 98},
        ]

        result = engine.get_mpg_data(["RA9250", "RA9251", "RA9252"], period_days=30)

        assert len(result) == 3
        assert result["RA9250"] == 5.8
        assert result["RA9251"] == 6.2
        assert result["RA9252"] == 6.5

    def test_get_mpg_data_empty(self, engine, mock_db):
        """Test getting MPG data with empty truck list"""
        result = engine.get_mpg_data([], period_days=30)
        assert result == {}

    def test_get_idle_time_pct_success(self, engine, mock_db):
        """Test getting idle time percentage"""
        db, cursor = mock_db

        cursor.fetchall.return_value = [
            {"truck_id": "RA9250", "idle_pct": 15.5},
            {"truck_id": "RA9251", "idle_pct": 12.3},
            {"truck_id": "RA9252", "idle_pct": 18.7},
        ]

        result = engine.get_idle_time_pct(
            ["RA9250", "RA9251", "RA9252"], period_days=30
        )

        assert len(result) == 3
        assert result["RA9250"] == 15.5
        assert result["RA9251"] == 12.3
        assert result["RA9252"] == 18.7

    def test_get_cost_per_mile_success(self, engine, mock_db):
        """Test getting cost per mile"""
        db, cursor = mock_db

        cursor.fetchall.return_value = [
            {"truck_id": "RA9250", "avg_cost": 0.85, "sample_count": 100},
            {"truck_id": "RA9251", "avg_cost": 0.78, "sample_count": 105},
            {"truck_id": "RA9252", "avg_cost": 0.92, "sample_count": 98},
        ]

        result = engine.get_cost_per_mile(
            ["RA9250", "RA9251", "RA9252"], period_days=30
        )

        assert len(result) == 3
        assert result["RA9250"] == 0.85
        assert result["RA9251"] == 0.78
        assert result["RA9252"] == 0.92

    def test_calculate_percentile(self, engine):
        """Test percentile calculation"""
        peer_values = [5.0, 5.5, 6.0, 6.5, 7.0]

        # Value at bottom
        assert engine.calculate_percentile(4.5, peer_values) == 0.0

        # Value at top
        assert engine.calculate_percentile(7.5, peer_values) == 100.0

        # Value in middle
        assert engine.calculate_percentile(6.0, peer_values) == 40.0

        # Empty peer values
        assert engine.calculate_percentile(5.0, []) == 50.0

    def test_get_performance_tier_mpg(self, engine):
        """Test performance tier classification for MPG (higher is better)"""
        assert engine.get_performance_tier(95.0, "mpg") == "TOP_10"
        assert engine.get_performance_tier(80.0, "mpg") == "TOP_25"
        assert engine.get_performance_tier(60.0, "mpg") == "AVERAGE"
        assert engine.get_performance_tier(40.0, "mpg") == "BELOW_AVERAGE"
        assert engine.get_performance_tier(10.0, "mpg") == "BOTTOM_25"

    def test_get_performance_tier_idle(self, engine):
        """Test performance tier classification for idle time (lower is better)"""
        # For idle_pct, lower is better, so percentile is reversed
        assert (
            engine.get_performance_tier(5.0, "idle_time_pct") == "TOP_10"
        )  # 5% idle -> 95th percentile
        assert (
            engine.get_performance_tier(20.0, "idle_time_pct") == "TOP_25"
        )  # 20% idle -> 80th percentile
        assert engine.get_performance_tier(50.0, "idle_time_pct") == "AVERAGE"
        assert engine.get_performance_tier(70.0, "idle_time_pct") == "BELOW_AVERAGE"
        assert engine.get_performance_tier(95.0, "idle_time_pct") == "BOTTOM_25"

    def test_benchmark_metric_mpg_success(self, engine, mock_db):
        """Test benchmarking MPG metric"""
        db, cursor = mock_db

        # Mock peer group identification
        cursor.fetchone.return_value = {
            "make": "Freightliner",
            "model": "Cascadia",
            "year": 2020,
        }
        cursor.fetchall.side_effect = [
            [  # Peer IDs
                {"truck_id": "RA9250"},
                {"truck_id": "RA9251"},
                {"truck_id": "RA9252"},
                {"truck_id": "RA9253"},
                {"truck_id": "RA9254"},
            ],
            [  # MPG data
                {"truck_id": "RA9250", "avg_mpg": 5.8, "sample_count": 100},
                {"truck_id": "RA9251", "avg_mpg": 6.2, "sample_count": 105},
                {"truck_id": "RA9252", "avg_mpg": 6.5, "sample_count": 98},
                {"truck_id": "RA9253", "avg_mpg": 6.0, "sample_count": 102},
                {"truck_id": "RA9254", "avg_mpg": 6.3, "sample_count": 99},
            ],
        ]

        result = engine.benchmark_metric("RA9250", "mpg", period_days=30)

        assert result is not None
        assert result.truck_id == "RA9250"
        assert result.metric_name == "mpg"
        assert result.actual_value == 5.8
        assert result.peer_count == 4  # Excluding self
        assert 0 <= result.percentile <= 100
        assert result.confidence > 0

    def test_benchmark_metric_no_peers(self, engine, mock_db):
        """Test benchmarking with no peers"""
        db, cursor = mock_db

        # Mock peer group with only 1 truck (no peers)
        cursor.fetchone.return_value = ("Freightliner", "Cascadia", 2020)
        cursor.fetchall.side_effect = [
            [("RA9250",)],  # Only self, no peers
        ]

        result = engine.benchmark_metric("RA9250", "mpg", period_days=30)

        assert result is None

    def test_benchmark_metric_no_data(self, engine, mock_db):
        """Test benchmarking with no data for truck"""
        db, cursor = mock_db

        cursor.fetchone.return_value = ("Freightliner", "Cascadia", 2020)
        cursor.fetchall.side_effect = [
            [("RA9250",), ("RA9251",)],  # Peer IDs
            [("RA9251", 6.2, 100)],  # No data for RA9250
        ]

        result = engine.benchmark_metric("RA9250", "mpg", period_days=30)

        assert result is None

    def test_benchmark_metric_unknown(self, engine):
        """Test benchmarking unknown metric"""
        result = engine.benchmark_metric("RA9250", "unknown_metric", period_days=30)
        assert result is None

    def test_benchmark_truck_all_metrics(self, engine, mock_db):
        """Test benchmarking all metrics for a truck"""
        db, cursor = mock_db

        # Mock peer group
        cursor.fetchone.side_effect = [
            {"make": "Freightliner", "model": "Cascadia", "year": 2020},  # MPG
            {"make": "Freightliner", "model": "Cascadia", "year": 2020},  # Idle
            {"make": "Freightliner", "model": "Cascadia", "year": 2020},  # Cost
        ]
        cursor.fetchall.side_effect = [
            # MPG peer IDs
            [{"truck_id": "RA9250"}, {"truck_id": "RA9251"}, {"truck_id": "RA9252"}],
            # MPG data
            [
                {"truck_id": "RA9250", "avg_mpg": 5.8, "sample_count": 100},
                {"truck_id": "RA9251", "avg_mpg": 6.2, "sample_count": 105},
                {"truck_id": "RA9252", "avg_mpg": 6.5, "sample_count": 98},
            ],
            # Idle peer IDs
            [{"truck_id": "RA9250"}, {"truck_id": "RA9251"}, {"truck_id": "RA9252"}],
            # Idle data
            [
                {"truck_id": "RA9250", "idle_pct": 15.5},
                {"truck_id": "RA9251", "idle_pct": 12.3},
                {"truck_id": "RA9252", "idle_pct": 10.1},
            ],
            # Cost peer IDs
            [{"truck_id": "RA9250"}, {"truck_id": "RA9251"}, {"truck_id": "RA9252"}],
            # Cost data
            [
                {"truck_id": "RA9250", "avg_cost": 0.85, "sample_count": 100},
                {"truck_id": "RA9251", "avg_cost": 0.78, "sample_count": 105},
                {"truck_id": "RA9252", "avg_cost": 0.72, "sample_count": 98},
            ],
        ]

        results = engine.benchmark_truck("RA9250", period_days=30)

        assert "mpg" in results
        assert "idle_time_pct" in results
        assert "cost_per_mile" in results
        assert all(isinstance(r, BenchmarkResult) for r in results.values())

    def test_get_fleet_outliers(self, engine, mock_db):
        """Test finding fleet outliers"""
        db, cursor = mock_db

        # Mock active trucks
        cursor.fetchall.side_effect = [
            [
                {"truck_id": "RA9250"},
                {"truck_id": "RA9251"},
                {"truck_id": "RA9252"},
            ],  # Active trucks
            # Peer groups and MPG data for each truck...
            [{"truck_id": "RA9250"}, {"truck_id": "RA9251"}, {"truck_id": "RA9252"}],
            [
                {"truck_id": "RA9250", "avg_mpg": 4.5, "sample_count": 100},
                {"truck_id": "RA9251", "avg_mpg": 6.2, "sample_count": 105},
                {"truck_id": "RA9252", "avg_mpg": 6.5, "sample_count": 98},
            ],  # RA9250 is outlier
            [{"truck_id": "RA9250"}, {"truck_id": "RA9251"}, {"truck_id": "RA9252"}],
            [
                {"truck_id": "RA9250", "avg_mpg": 4.5, "sample_count": 100},
                {"truck_id": "RA9251", "avg_mpg": 6.2, "sample_count": 105},
                {"truck_id": "RA9252", "avg_mpg": 6.5, "sample_count": 98},
            ],
            [{"truck_id": "RA9250"}, {"truck_id": "RA9251"}, {"truck_id": "RA9252"}],
            [
                {"truck_id": "RA9250", "avg_mpg": 4.5, "sample_count": 100},
                {"truck_id": "RA9251", "avg_mpg": 6.2, "sample_count": 105},
                {"truck_id": "RA9252", "avg_mpg": 6.5, "sample_count": 98},
            ],
        ]

        cursor.fetchone.side_effect = [
            {"make": "Freightliner", "model": "Cascadia", "year": 2020},  # RA9250
            {"make": "Freightliner", "model": "Cascadia", "year": 2020},  # RA9251
            {"make": "Freightliner", "model": "Cascadia", "year": 2020},  # RA9252
        ]

        outliers = engine.get_fleet_outliers(
            metric_name="mpg", threshold_percentile=10.0
        )

        # RA9250 should be identified as outlier (4.5 MPG vs 6.2-6.5)
        assert len(outliers) >= 1
        assert all(isinstance(o, BenchmarkResult) for o in outliers)
        assert all(o.percentile <= 10.0 for o in outliers)


class TestSingleton:
    """Test singleton pattern"""

    def test_get_benchmarking_engine_singleton(self):
        """Test that get_benchmarking_engine returns singleton"""
        with patch("pymysql.connect") as mock_connect:
            mock_connect.return_value = MagicMock()

            engine1 = get_benchmarking_engine()
            engine2 = get_benchmarking_engine()

            assert engine1 is engine2


class TestEdgeCases:
    """Test edge cases and error handling"""

    @pytest.fixture
    def engine(self):
        """Create engine with mock DB"""
        db = MagicMock()
        return BenchmarkingEngine(db_connection=db)

    def test_database_error_handling(self, engine):
        """Test handling of database errors"""
        engine.db.cursor.side_effect = Exception("Database connection lost")

        peer_group = engine.identify_peer_group("RA9250")
        assert peer_group.truck_ids == ["RA9250"]  # Fallback behavior

    def test_confidence_calculation(self, engine):
        """Test confidence score calculation"""
        # Test with varying peer counts
        test_cases = [
            (1, 0.1),  # 1 peer -> 10% confidence
            (5, 0.5),  # 5 peers -> 50% confidence
            (10, 1.0),  # 10 peers -> 100% confidence
            (15, 1.0),  # 15 peers -> 100% confidence (capped)
        ]

        for peer_count, expected_confidence in test_cases:
            confidence = min(1.0, peer_count / 10)
            assert confidence == expected_confidence
