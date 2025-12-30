"""
Tests for MPG Baseline Service v5.7.6
═══════════════════════════════════════════════════════════════════════════════

Test coverage for historical MPG baseline calculation.
"""

import statistics
from datetime import datetime

import pytest

from mpg_baseline_service import (
    DeviationAnalysis,
    MPGBaseline,
    MPGBaselineService,
    calculate_baseline_from_list,
    calculate_percentile,
    compare_to_fleet_average,
    filter_outliers_iqr,
    get_confidence_level,
)

# ═══════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestFilterOutliersIQR:
    """Test IQR outlier filtering"""

    def test_filter_removes_outliers(self):
        """Should remove extreme outliers"""
        data = [5.0, 5.5, 5.3, 5.8, 5.6, 20.0, 5.4]  # 20 is outlier
        filtered = filter_outliers_iqr(data)
        assert 20.0 not in filtered
        assert len(filtered) == 6

    def test_filter_keeps_normal_values(self):
        """Should keep values within IQR bounds"""
        data = [5.0, 5.2, 5.4, 5.6, 5.8, 6.0, 6.2]
        filtered = filter_outliers_iqr(data)
        assert len(filtered) == 7  # All should remain

    def test_filter_returns_original_if_too_few(self):
        """Should return original if < 4 values"""
        data = [5.0, 20.0, 5.5]
        filtered = filter_outliers_iqr(data)
        assert filtered == data

    def test_filter_handles_empty_list(self):
        """Should handle empty list"""
        filtered = filter_outliers_iqr([])
        assert filtered == []

    def test_filter_with_multiplier(self):
        """Should respect multiplier parameter"""
        data = [5.0, 5.5, 5.3, 5.8, 5.6, 8.0, 5.4]  # 8.0 is moderate outlier
        filtered_strict = filter_outliers_iqr(data, multiplier=1.0)
        filtered_lenient = filter_outliers_iqr(data, multiplier=3.0)
        # Strict should remove more
        assert len(filtered_strict) <= len(filtered_lenient)


class TestCalculatePercentile:
    """Test percentile calculation"""

    def test_percentile_25(self):
        """Should calculate 25th percentile"""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        p25 = calculate_percentile(data, 25)
        assert 2.5 <= p25 <= 3.5  # Linear interpolation

    def test_percentile_75(self):
        """Should calculate 75th percentile"""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        p75 = calculate_percentile(data, 75)
        assert 7.5 <= p75 <= 8.5  # Linear interpolation

    def test_percentile_50(self):
        """Should calculate median (50th percentile)"""
        data = [1, 2, 3, 4, 5]
        p50 = calculate_percentile(data, 50)
        assert p50 == 3

    def test_percentile_empty_list(self):
        """Should return 0 for empty list"""
        result = calculate_percentile([], 50)
        assert result == 0.0


class TestGetConfidenceLevel:
    """Test confidence level determination"""

    def test_very_high_confidence(self):
        """Should return VERY_HIGH for many samples per day"""
        level = get_confidence_level(sample_count=250, days=20)
        assert level == "VERY_HIGH"

    def test_high_confidence(self):
        """Should return HIGH for good sample count"""
        level = get_confidence_level(sample_count=150, days=20)
        assert level == "HIGH"

    def test_medium_confidence(self):
        """Should return MEDIUM for moderate samples"""
        level = get_confidence_level(sample_count=60, days=15)
        assert level == "MEDIUM"

    def test_low_confidence(self):
        """Should return LOW for few samples"""
        level = get_confidence_level(sample_count=25, days=30)
        assert level == "LOW"

    def test_insufficient_confidence(self):
        """Should return INSUFFICIENT for very few samples"""
        level = get_confidence_level(sample_count=5, days=7)
        assert level == "INSUFFICIENT"

    def test_zero_days(self):
        """Should return LOW for zero days"""
        level = get_confidence_level(sample_count=100, days=0)
        assert level == "LOW"


# ═══════════════════════════════════════════════════════════════════════════════
# DATACLASS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMPGBaseline:
    """Test MPGBaseline dataclass"""

    def test_default_values(self):
        """Should have sensible defaults"""
        baseline = MPGBaseline(truck_id="TEST001")
        assert baseline.baseline_mpg == 5.7
        assert baseline.confidence == "LOW"
        assert baseline.sample_count == 0

    def test_confidence_score_high(self):
        """Should calculate confidence score correctly"""
        baseline = MPGBaseline(truck_id="TEST001", sample_count=150)
        assert baseline.confidence_score == 1.0

    def test_confidence_score_medium(self):
        """Should calculate medium confidence score"""
        baseline = MPGBaseline(truck_id="TEST001", sample_count=60)
        assert baseline.confidence_score == 0.75

    def test_confidence_score_low(self):
        """Should calculate low confidence score"""
        baseline = MPGBaseline(truck_id="TEST001", sample_count=5)
        assert baseline.confidence_score == 0.0

    def test_to_dict(self):
        """Should serialize to dict correctly"""
        baseline = MPGBaseline(
            truck_id="TEST001",
            baseline_mpg=5.85,
            std_dev=0.72,
            sample_count=100,
            confidence="HIGH",
        )
        d = baseline.to_dict()
        assert d["truck_id"] == "TEST001"
        assert d["baseline_mpg"] == 5.85
        assert d["confidence"] == "HIGH"
        assert "confidence_score" in d


class TestDeviationAnalysis:
    """Test DeviationAnalysis dataclass"""

    def test_to_dict(self):
        """Should serialize correctly"""
        analysis = DeviationAnalysis(
            truck_id="TEST001",
            current_mpg=4.5,
            baseline_mpg=5.8,
            deviation_pct=-22.4,
            z_score=-1.8,
            status="LOW",
            message="MPG bajo",
            confidence="HIGH",
        )
        d = analysis.to_dict()
        assert d["status"] == "LOW"
        assert d["z_score"] == -1.8


# ═══════════════════════════════════════════════════════════════════════════════
# BASELINE CALCULATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCalculateBaselineFromList:
    """Test standalone baseline calculation"""

    def test_calculate_normal_data(self):
        """Should calculate correct baseline from normal data"""
        # Generate realistic MPG data (mean ~5.7) - need more samples for confidence
        mpg_data = [
            5.5,
            5.6,
            5.7,
            5.8,
            5.9,
            5.4,
            5.8,
            5.7,
            5.6,
            5.9,
            5.5,
            5.7,
            5.6,
            5.7,
            5.8,
            5.5,
            5.9,
            5.6,
            5.7,
            5.8,
            5.4,
            5.7,
            5.6,
            5.8,
        ]  # 24 samples

        baseline = calculate_baseline_from_list("TEST001", mpg_data, days=7)

        assert baseline.truck_id == "TEST001"
        assert 5.4 <= baseline.baseline_mpg <= 6.0  # Should be close to mean
        assert baseline.sample_count >= 20
        assert baseline.confidence in ("LOW", "MEDIUM", "HIGH")  # At least LOW

    def test_calculate_with_outliers(self):
        """Should filter outliers from calculation"""
        # Data with outliers
        mpg_data = [5.5, 5.6, 5.7, 5.8, 20.0, 5.4, 5.8, 1.0, 5.7, 5.6, 5.9, 5.5]

        baseline = calculate_baseline_from_list("TEST001", mpg_data, days=7)

        # Baseline should not be skewed by outliers
        assert 5.0 <= baseline.baseline_mpg <= 6.5

    def test_calculate_insufficient_data(self):
        """Should mark as INSUFFICIENT with few samples"""
        mpg_data = [5.5, 5.6, 5.7]  # Only 3 samples

        baseline = calculate_baseline_from_list("TEST001", mpg_data, days=1)

        assert baseline.confidence == "INSUFFICIENT"

    def test_filters_invalid_mpg(self):
        """Should filter values outside 3-12 MPG range"""
        # Mix of valid (5.x) and invalid (2.0, 15.0, 50.0) values
        mpg_data = [
            2.0,
            5.5,
            5.6,
            5.7,
            15.0,
            5.8,
            5.9,
            5.4,
            5.7,
            5.6,
            5.8,
            50.0,
            5.5,
            5.6,
            5.7,
            5.8,
        ]  # 13 valid + 3 invalid

        baseline = calculate_baseline_from_list("TEST001", mpg_data, days=7)

        # Should only have valid samples (excluding 2.0, 15.0, 50.0)
        assert baseline.sample_count == 13
        # Mean should be around 5.6-5.7 (only valid values)
        assert 5.4 <= baseline.baseline_mpg <= 6.0

    def test_calculates_percentiles(self):
        """Should calculate percentiles correctly"""
        mpg_data = [4.5, 5.0, 5.2, 5.5, 5.7, 5.9, 6.0, 6.2, 6.5, 6.8, 7.0, 7.5]

        baseline = calculate_baseline_from_list("TEST001", mpg_data, days=7)

        assert baseline.percentile_25 < baseline.baseline_mpg < baseline.percentile_75


# ═══════════════════════════════════════════════════════════════════════════════
# SERVICE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestMPGBaselineService:
    """Test MPGBaselineService class"""

    def test_service_init(self):
        """Should initialize without database"""
        service = MPGBaselineService()
        assert service.db_pool is None
        assert service._baselines_cache == {}

    def test_analyze_deviation_normal(self):
        """Should detect normal deviation"""
        service = MPGBaselineService()

        # Pre-populate cache
        baseline = MPGBaseline(
            truck_id="TEST001", baseline_mpg=5.7, std_dev=0.5, confidence="HIGH"
        )
        service._baselines_cache["TEST001"] = baseline

        # Analyze a normal reading
        analysis = service.analyze_deviation("TEST001", current_mpg=5.8)

        assert analysis.status == "NORMAL"
        assert abs(analysis.z_score) < 1.0

    def test_analyze_deviation_low(self):
        """Should detect LOW status for below baseline"""
        service = MPGBaselineService()

        baseline = MPGBaseline(
            truck_id="TEST001", baseline_mpg=5.7, std_dev=0.5, confidence="HIGH"
        )
        service._baselines_cache["TEST001"] = baseline

        # Analyze a low reading (2+ std devs below)
        analysis = service.analyze_deviation("TEST001", current_mpg=4.5)

        assert analysis.status == "LOW"
        assert analysis.z_score < -2.0

    def test_analyze_deviation_critical_low(self):
        """Should detect CRITICAL_LOW for very low MPG"""
        service = MPGBaselineService()

        baseline = MPGBaseline(
            truck_id="TEST001", baseline_mpg=5.7, std_dev=0.5, confidence="HIGH"
        )
        service._baselines_cache["TEST001"] = baseline

        # Analyze critical low reading
        analysis = service.analyze_deviation("TEST001", current_mpg=3.2)

        assert analysis.status == "CRITICAL_LOW"

    def test_analyze_deviation_without_cached_baseline(self):
        """Should use default baseline if not cached"""
        service = MPGBaselineService()

        analysis = service.analyze_deviation("UNKNOWN_TRUCK", current_mpg=5.5)

        # Should use default baseline (5.7)
        assert analysis.baseline_mpg == 5.7

    def test_get_fleet_summary_empty(self):
        """Should return default summary when no baselines"""
        service = MPGBaselineService()
        summary = service.get_fleet_summary()

        assert summary["total_trucks"] == 0
        assert summary["avg_baseline_mpg"] == 5.7


# ═══════════════════════════════════════════════════════════════════════════════
# COMPARISON TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCompareToFleetAverage:
    """Test fleet comparison function"""

    def test_above_average(self):
        """Should detect truck above fleet average"""
        baseline = MPGBaseline(truck_id="TEST001", baseline_mpg=6.5)

        result = compare_to_fleet_average(baseline, fleet_average=5.7)

        assert result["status"] == "ABOVE_AVERAGE"
        assert result["difference_mpg"] > 0

    def test_below_average(self):
        """Should detect truck below fleet average"""
        baseline = MPGBaseline(truck_id="TEST001", baseline_mpg=4.8)

        result = compare_to_fleet_average(baseline, fleet_average=5.7)

        assert result["status"] == "BELOW_AVERAGE"
        assert result["difference_mpg"] < 0

    def test_average(self):
        """Should detect truck at fleet average"""
        baseline = MPGBaseline(truck_id="TEST001", baseline_mpg=5.8)

        result = compare_to_fleet_average(baseline, fleet_average=5.7)

        assert result["status"] == "AVERAGE"

    def test_custom_fleet_average(self):
        """Should use custom fleet average"""
        baseline = MPGBaseline(truck_id="TEST001", baseline_mpg=5.5)

        result = compare_to_fleet_average(baseline, fleet_average=6.0)

        assert result["fleet_average"] == 6.0


# ═══════════════════════════════════════════════════════════════════════════════
# EDGE CASES
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_all_same_mpg_values(self):
        """Should handle all identical values"""
        mpg_data = [5.7] * 20

        baseline = calculate_baseline_from_list("TEST001", mpg_data, days=7)

        assert baseline.baseline_mpg == 5.7
        assert baseline.std_dev == 0.0  # No variance

    def test_extreme_variance(self):
        """Should handle high variance data"""
        mpg_data = [3.5, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 11.5]

        baseline = calculate_baseline_from_list("TEST001", mpg_data, days=30)

        assert baseline.std_dev > 2.0  # High variance

    def test_zero_std_dev_in_analysis(self):
        """Should handle zero std_dev without division error"""
        service = MPGBaselineService()

        baseline = MPGBaseline(
            truck_id="TEST001",
            baseline_mpg=5.7,
            std_dev=0.0,  # Zero variance
            confidence="HIGH",
        )
        service._baselines_cache["TEST001"] = baseline

        # Should not raise ZeroDivisionError
        analysis = service.analyze_deviation("TEST001", current_mpg=5.8)

        assert analysis.z_score == 0.0  # Graceful handling
