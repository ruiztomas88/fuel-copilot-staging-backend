"""
Tests for Terrain MPG Contextualization System
=============================================
Tests for terrain factor calculations and contextualized MPG analysis.
"""

import pytest
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestTerrainContextualizedMPG:
    """Test suite for contextualized MPG calculations."""

    def test_calculate_contextualized_mpg_basic(self):
        """Test basic contextualized MPG calculation."""
        from terrain_factor import calculate_contextualized_mpg

        result = calculate_contextualized_mpg(
            raw_mpg=6.0,
            terrain_factor=1.0,  # Flat terrain
            weather_factor=1.0,  # Normal weather
            load_factor=1.0,  # Empty
            baseline_mpg=6.0,
        )

        assert result["raw_mpg"] == 6.0
        assert result["adjusted_mpg"] == 6.0
        assert result["expected_mpg"] == 6.0
        assert result["rating"] in ["EXCELLENT", "GOOD"]
        assert result["factors"]["combined"] == 1.0

    def test_calculate_contextualized_mpg_uphill(self):
        """Test MPG context when climbing (terrain_factor > 1)."""
        from terrain_factor import calculate_contextualized_mpg

        result = calculate_contextualized_mpg(
            raw_mpg=5.0,  # Looks bad
            terrain_factor=1.15,  # 15% uphill penalty
            baseline_mpg=6.0,
        )

        # 5.0 MPG with 15% uphill should be good performance
        assert result["raw_mpg"] == 5.0
        assert result["adjusted_mpg"] == pytest.approx(5.75, rel=0.01)  # 5.0 * 1.15
        assert result["expected_mpg"] == pytest.approx(5.22, rel=0.01)  # 6.0 / 1.15
        # Performance should be close to expected (5.0 vs 5.22 = -4.2%)
        assert result["performance_vs_expected_pct"] <= 0
        assert result["rating"] in ["GOOD", "NEEDS_ATTENTION"]

    def test_calculate_contextualized_mpg_downhill(self):
        """Test MPG context when descending (terrain_factor < 1)."""
        from terrain_factor import calculate_contextualized_mpg

        result = calculate_contextualized_mpg(
            raw_mpg=7.0,  # Looks great
            terrain_factor=0.85,  # 15% downhill boost
            baseline_mpg=6.0,
        )

        # 7.0 MPG with 15% downhill should be judged more strictly
        assert result["raw_mpg"] == 7.0
        assert result["adjusted_mpg"] == pytest.approx(5.95, rel=0.01)  # 7.0 * 0.85
        assert result["expected_mpg"] == pytest.approx(7.06, rel=0.01)  # 6.0 / 0.85

    def test_calculate_contextualized_mpg_loaded(self):
        """Test MPG context when fully loaded."""
        from terrain_factor import calculate_contextualized_mpg

        result = calculate_contextualized_mpg(
            raw_mpg=5.2,  # Looks below baseline
            terrain_factor=1.0,
            weather_factor=1.0,
            load_factor=1.15,  # 15% load penalty
            baseline_mpg=6.0,
        )

        # With load penalty, 5.2 MPG is actually excellent
        assert result["expected_mpg"] == pytest.approx(5.22, rel=0.01)  # 6.0 / 1.15
        # 5.2 vs 5.22 expected = about 0%
        assert abs(result["performance_vs_expected_pct"]) < 5

    def test_calculate_contextualized_mpg_combined_factors(self):
        """Test with multiple environmental factors."""
        from terrain_factor import calculate_contextualized_mpg

        result = calculate_contextualized_mpg(
            raw_mpg=4.5,  # Looks terrible
            terrain_factor=1.10,  # 10% uphill
            weather_factor=1.05,  # 5% headwind
            load_factor=1.10,  # 10% load
            baseline_mpg=6.0,
        )

        # Combined factor: 1.10 * 1.05 * 1.10 = 1.2705
        expected_combined = 1.10 * 1.05 * 1.10
        assert result["factors"]["combined"] == pytest.approx(
            expected_combined, rel=0.01
        )

        # Expected MPG: 6.0 / 1.2705 = 4.72
        assert result["expected_mpg"] == pytest.approx(4.72, rel=0.05)

        # 4.5 vs 4.72 = -4.7% - actually performing well given conditions!
        assert result["rating"] in ["GOOD", "NEEDS_ATTENTION"]

    def test_rating_excellent(self):
        """Test EXCELLENT rating threshold."""
        from terrain_factor import calculate_contextualized_mpg

        result = calculate_contextualized_mpg(
            raw_mpg=6.5,  # Well above baseline
            terrain_factor=1.0,
            baseline_mpg=6.0,
        )

        assert result["rating"] == "EXCELLENT"
        assert result["performance_vs_expected_pct"] >= 5

    def test_rating_critical(self):
        """Test CRITICAL rating threshold."""
        from terrain_factor import calculate_contextualized_mpg

        result = calculate_contextualized_mpg(
            raw_mpg=4.0,  # Way below baseline
            terrain_factor=1.0,  # No excuse - flat terrain
            baseline_mpg=6.0,
        )

        assert result["rating"] == "CRITICAL"
        assert result["performance_vs_expected_pct"] < -15

    def test_message_content(self):
        """Test that messages are descriptive."""
        from terrain_factor import calculate_contextualized_mpg

        # Test excellent message
        result = calculate_contextualized_mpg(raw_mpg=7.0, baseline_mpg=6.0)
        assert "Beating" in result["message"] or "expected" in result["message"].lower()

        # Test critical message
        result = calculate_contextualized_mpg(raw_mpg=3.0, baseline_mpg=6.0)
        assert (
            "investigate" in result["message"].lower()
            or "below" in result["message"].lower()
        )


class TestGetTruckContextualizedMPG:
    """Test the truck-specific contextualized MPG function."""

    def test_get_truck_contextualized_mpg_no_altitude(self):
        """Test when altitude is not available."""
        from terrain_factor import get_truck_contextualized_mpg

        result = get_truck_contextualized_mpg(
            truck_id="T101",
            raw_mpg=5.5,
            altitude=None,  # No altitude data
            baseline_mpg=6.0,
        )

        # Should use terrain_factor=1.0 when no altitude
        assert result["factors"]["terrain"] == 1.0
        assert result["raw_mpg"] == 5.5

    def test_get_truck_contextualized_mpg_with_altitude(self):
        """Test with altitude data."""
        from terrain_factor import get_truck_contextualized_mpg

        result = get_truck_contextualized_mpg(
            truck_id="T102",
            raw_mpg=5.0,
            altitude=5000,  # 5000 ft altitude
            latitude=35.0,
            longitude=-106.0,
            speed=55,
            baseline_mpg=6.0,
        )

        # Should have calculated some terrain factor
        assert "factors" in result
        assert "terrain" in result["factors"]
        # Result should have all expected keys
        assert "raw_mpg" in result
        assert "adjusted_mpg" in result
        assert "rating" in result


class TestTerrainFactorIntegration:
    """Integration tests for terrain factor system."""

    def test_terrain_manager_singleton(self):
        """Test that terrain manager is singleton."""
        from terrain_factor import get_terrain_manager

        manager1 = get_terrain_manager()
        manager2 = get_terrain_manager()

        assert manager1 is manager2

    def test_get_terrain_fuel_factor_function(self):
        """Test the convenience function."""
        from terrain_factor import get_terrain_fuel_factor

        factor = get_terrain_fuel_factor(
            truck_id="TEST123",
            altitude=3000,
            latitude=None,
            longitude=None,
            speed=None,
        )

        # Factor should be a reasonable value
        assert isinstance(factor, float)
        assert 0.5 <= factor <= 2.0  # Sanity check


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_zero_mpg(self):
        """Test handling of zero MPG (parked truck)."""
        from terrain_factor import calculate_contextualized_mpg

        result = calculate_contextualized_mpg(
            raw_mpg=0.0,
            baseline_mpg=6.0,
        )

        assert result["raw_mpg"] == 0.0
        assert result["adjusted_mpg"] == 0.0

    def test_very_high_terrain_factor(self):
        """Test extreme uphill scenario."""
        from terrain_factor import calculate_contextualized_mpg

        result = calculate_contextualized_mpg(
            raw_mpg=3.5,  # Very low MPG
            terrain_factor=1.50,  # Extreme 50% uphill
            baseline_mpg=6.0,
        )

        # 3.5 * 1.5 = 5.25 adjusted
        assert result["adjusted_mpg"] == pytest.approx(5.25, rel=0.01)
        # Expected: 6.0 / 1.5 = 4.0
        assert result["expected_mpg"] == pytest.approx(4.0, rel=0.01)
        # 3.5 vs 4.0 = -12.5%, should be NEEDS_ATTENTION
        assert result["rating"] in ["NEEDS_ATTENTION", "GOOD"]

    def test_negative_mpg_handling(self):
        """Test handling of invalid negative MPG."""
        from terrain_factor import calculate_contextualized_mpg

        # Should handle gracefully
        result = calculate_contextualized_mpg(
            raw_mpg=-1.0,  # Invalid
            baseline_mpg=6.0,
        )

        # Should still return structured result
        assert "rating" in result
        assert "factors" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
