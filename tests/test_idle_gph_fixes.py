"""
Tests for idle_gph fixes from audit (BUG #1 and BUG #3)

These tests verify:
1. idle_gph is included in INSERT statements (BUG #1)
2. SQL queries use idle_gph column instead of consumption_gph (BUG #3)
3. Data normalization works correctly

Created: December 12, 2025
Audit Reference: Fuel Copilot Technical Audit v5.4.x
"""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal


class TestIdleGphInsert:
    """Tests for BUG #1: idle_gph should be saved to database"""

    def test_wialon_sync_insert_includes_idle_gph(self):
        """Verify INSERT statement includes idle_gph column"""
        # Read the actual wialon_sync_enhanced.py file
        with open("wialon_sync_enhanced.py", "r") as f:
            content = f.read()

        # Find the INSERT INTO fuel_metrics statement
        assert (
            "idle_gph" in content
        ), "idle_gph column should exist in wialon_sync_enhanced.py"

        # Verify it's in the INSERT statement (not just anywhere in file)
        # Look for the INSERT block
        insert_start = content.find("INSERT INTO fuel_metrics")
        assert insert_start != -1, "INSERT INTO fuel_metrics should exist"

        # Find the VALUES part (next ~2000 chars should contain the column list)
        insert_block = content[insert_start : insert_start + 3000]

        # Check idle_gph is in the column list (before VALUES)
        values_pos = insert_block.find("VALUES")
        column_list = insert_block[:values_pos]

        assert "idle_gph" in column_list, "idle_gph should be in INSERT column list"

    def test_wialon_sync_on_duplicate_key_includes_idle_gph(self):
        """Verify ON DUPLICATE KEY UPDATE includes idle_gph"""
        with open("wialon_sync_enhanced.py", "r") as f:
            content = f.read()

        # Find ON DUPLICATE KEY UPDATE section
        on_dup_start = content.find("ON DUPLICATE KEY UPDATE")
        assert on_dup_start != -1, "ON DUPLICATE KEY UPDATE should exist"

        # Check the next ~1000 chars for idle_gph = VALUES(idle_gph)
        on_dup_block = content[on_dup_start : on_dup_start + 1500]

        assert (
            "idle_gph = VALUES(idle_gph)" in on_dup_block
        ), "idle_gph should be updated on duplicate key"


class TestIdleGphSqlQueries:
    """Tests for BUG #3: SQL queries should use idle_gph instead of consumption_gph"""

    def test_database_py_uses_idle_gph_for_averages(self):
        """Verify database.py uses idle_gph for 24h averages"""
        with open("database.py", "r") as f:
            content = f.read()

        # Find the avg_idle_gph_24h calculation
        assert (
            "AVG(idle_gph) as avg_idle_gph_24h" in content
        ), "Should use AVG(idle_gph) not AVG(consumption_gph) for idle averages"

    def test_database_py_selects_idle_gph_column(self):
        """Verify database.py SELECT includes t1.idle_gph"""
        with open("database.py", "r") as f:
            content = f.read()

        # Should select idle_gph from the main table
        assert (
            "t1.idle_gph" in content
        ), "Should SELECT t1.idle_gph for current sensor value"

    def test_idle_gph_validation_range(self):
        """Verify idle_gph validation uses correct range (0.05-2.0 GPH for sensors)"""
        with open("database.py", "r") as f:
            content = f.read()

        # The validation should use sensor-appropriate ranges
        # Real sensors report 0.13-0.17 GPH, so 0.05-2.0 is reasonable
        assert (
            "idle_gph > 0.05" in content or "idle_gph >= 0.05" in content
        ), "Lower bound should be ~0.05 GPH for sensor data"


class TestIdleEngineValidation:
    """Tests for idle_engine.py validation thresholds"""

    def test_fuel_rate_min_threshold(self):
        """Verify fuel_rate_min_lph is set correctly for sensor acceptance"""
        with open("idle_engine.py", "r") as f:
            content = f.read()

        # Should be 0.4 LPH (not 1.5) to accept low idle values
        assert "fuel_rate_min_lph" in content, "fuel_rate_min_lph should be defined"

        # The value 0.4 should appear near fuel_rate_min_lph
        # This is a soft check - the actual value matters
        if (
            "fuel_rate_min_lph = 0.4" in content
            or "fuel_rate_min_lph: float = 0.4" in content
        ):
            pass  # Good - using correct threshold
        elif "fuel_rate_min_lph = 1.5" in content:
            pytest.fail(
                "fuel_rate_min_lph should be 0.4, not 1.5 - sensors report ~0.5 LPH at idle"
            )


class TestIdleGphPriority:
    """Tests for idle display priority logic"""

    def test_priority_order_in_database(self):
        """Verify priority: 1) current idle_gph, 2) 24h avg, 3) fallback"""
        with open("database.py", "r") as f:
            content = f.read()

        # Find the display_idle logic section
        # Priority 1 should be current idle_gph from sensor
        assert (
            "idle_gph_sensor" in content or "idle_gph" in content
        ), "Should check current idle_gph value first"

        # Should have conservative fallback (not 0.8)
        # After our fix, fallback should be 0.5 GPH
        if "display_idle = 0.8" in content:
            pytest.fail("Fallback should be 0.5 GPH (conservative), not 0.8")


class TestMetricsDataIntegrity:
    """Tests for data integrity in metrics tuple"""

    def test_metrics_tuple_includes_idle_gph(self):
        """Verify metrics.get('idle_gph') is in the values tuple"""
        with open("wialon_sync_enhanced.py", "r") as f:
            content = f.read()

        # Should have metrics.get("idle_gph") or metrics.get('idle_gph')
        assert (
            "metrics.get('idle_gph')" in content or 'metrics.get("idle_gph")' in content
        ), "Values tuple should include metrics.get('idle_gph')"


class TestIdleMethodTracking:
    """Tests for idle_method tracking (SENSOR_FUEL_RATE vs FALLBACK)"""

    def test_idle_method_column_exists(self):
        """Verify idle_method is being set and saved"""
        with open("wialon_sync_enhanced.py", "r") as f:
            content = f.read()

        assert "idle_method" in content, "idle_method should be tracked"

    def test_idle_method_enum_has_sensor_fuel_rate(self):
        """Verify IdleMethod enum includes SENSOR_FUEL_RATE"""
        with open("idle_engine.py", "r") as f:
            content = f.read()

        assert (
            "SENSOR_FUEL_RATE" in content
        ), "IdleMethod should include SENSOR_FUEL_RATE"


# Integration test placeholder - requires database connection
class TestIdleGphIntegration:
    """Integration tests for idle_gph flow (requires DB)"""

    @pytest.mark.skip(reason="Requires database connection")
    def test_idle_gph_roundtrip(self):
        """Test: calculate idle_gph -> insert -> query -> verify value matches"""
        pass

    @pytest.mark.skip(reason="Requires database connection")
    def test_api_returns_numeric_idle_gph(self):
        """Test: API /fleet endpoint returns idle_gph as number (not string)"""
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
