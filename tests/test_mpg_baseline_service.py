"""
Tests for MPG Baseline Service v5.7.6

Tests cover:
- MPGBaseline dataclass
- DeviationAnalysis dataclass
- Utility functions (IQR filter, percentiles, confidence)
- MPGBaselineService
"""

import statistics
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mpg_baseline_service import (
    DeviationAnalysis,
    MPGBaseline,
    MPGBaselineService,
    calculate_percentile,
    filter_outliers_iqr,
    get_confidence_level,
)


class TestMPGBaseline:
    """Tests for MPGBaseline dataclass"""

    def test_baseline_creation_defaults(self):
        """Should create with default values"""
        baseline = MPGBaseline(truck_id="T001")

        assert baseline.truck_id == "T001"
        assert baseline.baseline_mpg == 5.7
        assert baseline.std_dev == 0.8
        assert baseline.min_mpg == 3.0
        assert baseline.max_mpg == 9.0
        assert baseline.sample_count == 0
        assert baseline.confidence == "LOW"

    def test_baseline_with_values(self):
        """Should create with specified values"""
        baseline = MPGBaseline(
            truck_id="T001",
            baseline_mpg=6.5,
            std_dev=0.5,
            min_mpg=5.0,
            max_mpg=8.0,
            sample_count=100,
            confidence="HIGH",
        )

        assert baseline.baseline_mpg == 6.5
        assert baseline.sample_count == 100
        assert baseline.confidence == "HIGH"

    def test_confidence_score_high_samples(self):
        """Confidence score should be 1.0 for 100+ samples"""
        baseline = MPGBaseline(truck_id="T001", sample_count=100)

        assert baseline.confidence_score == 1.0

    def test_confidence_score_medium_samples(self):
        """Confidence score should be 0.75 for 50-99 samples"""
        baseline = MPGBaseline(truck_id="T001", sample_count=75)

        assert baseline.confidence_score == 0.75

    def test_confidence_score_low_samples(self):
        """Confidence score should be 0.5 for 20-49 samples"""
        baseline = MPGBaseline(truck_id="T001", sample_count=30)

        assert baseline.confidence_score == 0.5

    def test_confidence_score_very_low_samples(self):
        """Confidence score should be 0.25 for 10-19 samples"""
        baseline = MPGBaseline(truck_id="T001", sample_count=15)

        assert baseline.confidence_score == 0.25

    def test_confidence_score_insufficient_samples(self):
        """Confidence score should be 0 for <10 samples"""
        baseline = MPGBaseline(truck_id="T001", sample_count=5)

        assert baseline.confidence_score == 0.0

    def test_to_dict(self):
        """Should serialize to dict"""
        baseline = MPGBaseline(
            truck_id="T001",
            baseline_mpg=6.5,
            std_dev=0.5,
            sample_count=100,
            last_calculated=datetime.now(timezone.utc),
        )

        result = baseline.to_dict()

        assert isinstance(result, dict)
        assert result["truck_id"] == "T001"
        assert result["baseline_mpg"] == 6.5
        assert result["sample_count"] == 100
        assert "confidence_score" in result

    def test_to_dict_rounds_values(self):
        """Should round float values"""
        baseline = MPGBaseline(truck_id="T001", baseline_mpg=6.5555, std_dev=0.5555)

        result = baseline.to_dict()

        assert result["baseline_mpg"] == 6.56
        assert result["std_dev"] == 0.56


class TestDeviationAnalysis:
    """Tests for DeviationAnalysis dataclass"""

    def test_deviation_creation(self):
        """Should create deviation analysis"""
        analysis = DeviationAnalysis(
            truck_id="T001",
            current_mpg=5.0,
            baseline_mpg=6.5,
            deviation_pct=-23.1,
            z_score=-3.0,
            status="CRITICAL_LOW",
            message="MPG significantly below baseline",
            confidence="HIGH",
        )

        assert analysis.truck_id == "T001"
        assert analysis.deviation_pct == -23.1
        assert analysis.status == "CRITICAL_LOW"

    def test_to_dict(self):
        """Should serialize to dict"""
        analysis = DeviationAnalysis(
            truck_id="T001",
            current_mpg=5.5,
            baseline_mpg=6.0,
            deviation_pct=-8.3,
            z_score=-1.5,
            status="LOW",
            message="Below baseline",
            confidence="MEDIUM",
        )

        result = analysis.to_dict()

        assert isinstance(result, dict)
        assert result["current_mpg"] == 5.5
        assert result["status"] == "LOW"

    def test_to_dict_rounds_values(self):
        """Should round float values"""
        analysis = DeviationAnalysis(
            truck_id="T001",
            current_mpg=5.5555,
            baseline_mpg=6.0555,
            deviation_pct=-8.333,
            z_score=-1.555,
            status="LOW",
            message="Test",
            confidence="MEDIUM",
        )

        result = analysis.to_dict()

        assert result["current_mpg"] == 5.56
        assert result["deviation_pct"] == -8.3
        assert (
            abs(result["z_score"] - (-1.55)) < 0.02
        )  # Allow small rounding difference


class TestFilterOutliersIQR:
    """Tests for IQR outlier filtering"""

    def test_filter_normal_data(self):
        """Should not remove normal data points"""
        data = [5.0, 5.5, 6.0, 6.5, 7.0]

        result = filter_outliers_iqr(data)

        assert len(result) == 5

    def test_filter_removes_outliers(self):
        """Should remove extreme outliers"""
        data = [5.0, 5.5, 6.0, 6.5, 7.0, 100.0]  # 100 is extreme outlier

        result = filter_outliers_iqr(data)

        assert 100.0 not in result

    def test_filter_with_small_dataset(self):
        """Should return original for datasets < 4"""
        data = [5.0, 6.0, 7.0]

        result = filter_outliers_iqr(data)

        assert result == data

    def test_filter_with_custom_multiplier(self):
        """Should use custom IQR multiplier"""
        data = [5.0, 5.5, 6.0, 6.5, 7.0, 10.0]

        # With larger multiplier, might keep more data
        result_strict = filter_outliers_iqr(data, multiplier=1.5)
        result_loose = filter_outliers_iqr(data, multiplier=3.0)

        assert len(result_loose) >= len(result_strict)

    def test_filter_empty_list(self):
        """Should handle empty list"""
        result = filter_outliers_iqr([])

        assert result == []

    def test_filter_single_element(self):
        """Should handle single element"""
        result = filter_outliers_iqr([5.0])

        assert result == [5.0]


class TestCalculatePercentile:
    """Tests for percentile calculation"""

    def test_percentile_50_is_median(self):
        """50th percentile should be near median"""
        data = [1, 2, 3, 4, 5]

        result = calculate_percentile(data, 50)

        assert result == 3

    def test_percentile_25(self):
        """25th percentile calculation"""
        data = [1, 2, 3, 4, 5, 6, 7, 8]

        result = calculate_percentile(data, 25)

        assert 2.0 <= result <= 3.0  # Linear interpolation

    def test_percentile_75(self):
        """75th percentile calculation"""
        data = [1, 2, 3, 4, 5, 6, 7, 8]

        result = calculate_percentile(data, 75)

        assert 6.0 <= result <= 7.0  # Linear interpolation

        assert result in [6, 7]

    def test_percentile_empty_list(self):
        """Should return 0 for empty list"""
        result = calculate_percentile([], 50)

        assert result == 0.0

    def test_percentile_0(self):
        """0th percentile should be minimum"""
        data = [3, 1, 4, 1, 5, 9, 2, 6]

        result = calculate_percentile(data, 0)

        assert result == 1

    def test_percentile_100(self):
        """100th percentile should be maximum"""
        data = [3, 1, 4, 1, 5, 9, 2, 6]

        result = calculate_percentile(data, 100)

        assert result == 9


class TestGetConfidenceLevel:
    """Tests for confidence level determination"""

    def test_very_high_confidence(self):
        """Should return VERY_HIGH for 200+ samples with good density"""
        result = get_confidence_level(sample_count=250, days=10)

        assert result == "VERY_HIGH"

    def test_high_confidence(self):
        """Should return HIGH for 100+ samples with good density"""
        result = get_confidence_level(sample_count=120, days=10)

        assert result == "HIGH"

    def test_medium_confidence(self):
        """Should return MEDIUM for 50+ samples with moderate density"""
        result = get_confidence_level(sample_count=60, days=10)

        assert result == "MEDIUM"

    def test_low_confidence(self):
        """Should return LOW for 20+ samples"""
        result = get_confidence_level(sample_count=25, days=10)

        assert result == "LOW"

    def test_insufficient_confidence(self):
        """Should return INSUFFICIENT for <20 samples"""
        result = get_confidence_level(sample_count=10, days=10)

        assert result == "INSUFFICIENT"

    def test_zero_days(self):
        """Should return LOW for zero days"""
        result = get_confidence_level(sample_count=100, days=0)

        assert result == "LOW"


class TestMPGBaselineService:
    """Tests for MPGBaselineService"""

    def test_service_creation_no_pool(self):
        """Should create service without pool"""
        service = MPGBaselineService()

        assert service.db_pool is None
        assert service._baselines_cache == {}

    def test_service_creation_with_pool(self):
        """Should create service with pool"""
        mock_pool = MagicMock()
        service = MPGBaselineService(db_pool=mock_pool)

        assert service.db_pool is mock_pool

    def test_min_valid_mpg_constant(self):
        """Should have MIN_VALID_MPG defined"""
        assert MPGBaselineService.MIN_VALID_MPG == 3.0

    def test_max_valid_mpg_constant(self):
        """Should have MAX_VALID_MPG defined"""
        assert MPGBaselineService.MAX_VALID_MPG == 12.0

    def test_min_samples_constant(self):
        """Should have MIN_SAMPLES defined"""
        assert MPGBaselineService.MIN_SAMPLES == 10


class TestMPGBaselineServiceCalculations:
    """Tests for baseline calculation methods"""

    @pytest.fixture
    def service(self):
        return MPGBaselineService()

    def test_calculate_from_readings_empty(self, service):
        """Should handle empty readings"""
        result = service._calculate_from_readings("T001", [], 30)

        assert result.truck_id == "T001"
        assert result.sample_count == 0

    def test_calculate_from_readings_with_data(self, service):
        """Should calculate from readings"""
        # Create mock rows: (mpg, timestamp)
        now = datetime.now(timezone.utc)
        rows = [
            (6.0, now - timedelta(days=1)),
            (6.2, now - timedelta(days=2)),
            (6.1, now - timedelta(days=3)),
            (6.3, now - timedelta(days=4)),
            (5.9, now - timedelta(days=5)),
        ] * 10  # 50 total readings

        result = service._calculate_from_readings("T001", rows, 30)

        assert result.truck_id == "T001"
        assert result.sample_count > 0


class TestMPGBaselineServiceAsync:
    """Tests for async methods"""

    @pytest.fixture
    def service_with_pool(self):
        mock_pool = MagicMock()
        return MPGBaselineService(db_pool=mock_pool)

    @pytest.mark.asyncio
    async def test_calculate_baseline_no_pool(self):
        """Should return default when no pool"""
        service = MPGBaselineService()

        result = await service.calculate_baseline("T001")

        assert result.truck_id == "T001"
        assert result.sample_count == 0


class TestMPGBaselinePercentiles:
    """Tests for percentile handling in baseline"""

    def test_percentile_25_default(self):
        """Should have default percentile_25"""
        baseline = MPGBaseline(truck_id="T001")

        assert baseline.percentile_25 == 5.0

    def test_percentile_75_default(self):
        """Should have default percentile_75"""
        baseline = MPGBaseline(truck_id="T001")

        assert baseline.percentile_75 == 6.5

    def test_percentile_custom_values(self):
        """Should accept custom percentile values"""
        baseline = MPGBaseline(truck_id="T001", percentile_25=4.5, percentile_75=7.5)

        assert baseline.percentile_25 == 4.5
        assert baseline.percentile_75 == 7.5


class TestDeviationStatus:
    """Tests for deviation status values"""

    def test_normal_status(self):
        """Should have NORMAL status"""
        analysis = DeviationAnalysis(
            truck_id="T001",
            current_mpg=6.0,
            baseline_mpg=6.0,
            deviation_pct=0,
            z_score=0,
            status="NORMAL",
            message="OK",
            confidence="HIGH",
        )
        assert analysis.status == "NORMAL"

    def test_low_status(self):
        """Should have LOW status"""
        analysis = DeviationAnalysis(
            truck_id="T001",
            current_mpg=5.5,
            baseline_mpg=6.0,
            deviation_pct=-8.3,
            z_score=-1.5,
            status="LOW",
            message="Low",
            confidence="HIGH",
        )
        assert analysis.status == "LOW"

    def test_high_status(self):
        """Should have HIGH status"""
        analysis = DeviationAnalysis(
            truck_id="T001",
            current_mpg=7.0,
            baseline_mpg=6.0,
            deviation_pct=16.7,
            z_score=2.0,
            status="HIGH",
            message="High",
            confidence="HIGH",
        )
        assert analysis.status == "HIGH"

    def test_critical_low_status(self):
        """Should have CRITICAL_LOW status"""
        analysis = DeviationAnalysis(
            truck_id="T001",
            current_mpg=4.0,
            baseline_mpg=6.0,
            deviation_pct=-33.3,
            z_score=-4.0,
            status="CRITICAL_LOW",
            message="Critical",
            confidence="HIGH",
        )
        assert analysis.status == "CRITICAL_LOW"


class TestBaselineCache:
    """Tests for baseline caching"""

    def test_cache_initially_empty(self):
        """Cache should start empty"""
        service = MPGBaselineService()

        assert len(service._baselines_cache) == 0

    def test_cache_stores_baseline(self):
        """Should store baseline in cache"""
        service = MPGBaselineService()
        baseline = MPGBaseline(truck_id="T001", baseline_mpg=6.5)
        service._baselines_cache["T001"] = baseline

        assert "T001" in service._baselines_cache
        assert service._baselines_cache["T001"].baseline_mpg == 6.5


class TestFilterOutliersEdgeCases:
    """Edge case tests for outlier filtering"""

    def test_all_same_values(self):
        """Should handle all same values (IQR=0)"""
        data = [5.0, 5.0, 5.0, 5.0, 5.0]

        result = filter_outliers_iqr(data)

        assert len(result) == 5

    def test_two_values(self):
        """Should handle two values"""
        data = [5.0, 6.0]

        result = filter_outliers_iqr(data)

        assert result == data

    def test_negative_values(self):
        """Should handle negative values"""
        data = [-5.0, -2.0, 0.0, 2.0, 5.0]

        result = filter_outliers_iqr(data)

        assert len(result) > 0


class TestMPGBaselineDaysAnalyzed:
    """Tests for days_analyzed field"""

    def test_days_analyzed_default(self):
        """Should have default days_analyzed"""
        baseline = MPGBaseline(truck_id="T001")

        assert baseline.days_analyzed == 0

    def test_days_analyzed_custom(self):
        """Should accept custom days_analyzed"""
        baseline = MPGBaseline(truck_id="T001", days_analyzed=30)

        assert baseline.days_analyzed == 30

    def test_days_analyzed_in_dict(self):
        """Should include days_analyzed in dict"""
        baseline = MPGBaseline(truck_id="T001", days_analyzed=14)

        result = baseline.to_dict()

        assert result["days_analyzed"] == 14


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
