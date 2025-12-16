"""
Tests for Fleet Command Center v1.1.0

Tests the algorithmic improvements:
- Weighted priority scoring by component criticality
- UUID-based action IDs for thread safety
- Cost database
- Pattern detection thresholds
- Caching with TTL
- Historical trend tracking
"""

import pytest
from unittest.mock import patch, MagicMock
import uuid

from fleet_command_center import (
    FleetCommandCenter,
    Priority,
    IssueCategory,
    ActionType,
    ActionItem,
    FleetHealthScore,
    UrgencySummary,
    CommandCenterData,
    _calculate_trend,
    _trend_history,
)


class TestFleetCommandCenterV11:
    """Tests for v1.1.0 improvements"""

    @pytest.fixture
    def fcc(self):
        """Create a FleetCommandCenter instance"""
        return FleetCommandCenter()

    # ═══════════════════════════════════════════════════════════════════════════════
    # VERSION TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_version_is_1_1_0(self, fcc):
        """Verify we're testing v1.1.0"""
        assert fcc.VERSION == "1.1.0"

    # ═══════════════════════════════════════════════════════════════════════════════
    # UUID ACTION ID TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_action_id_is_unique(self, fcc):
        """Action IDs should be unique (thread-safe UUID)"""
        ids = [fcc._generate_action_id() for _ in range(100)]
        assert len(set(ids)) == 100, "All IDs should be unique"

    def test_action_id_format(self, fcc):
        """Action ID should have correct format: ACT-YYYYMMDD-XXXXXXXX"""
        action_id = fcc._generate_action_id()
        parts = action_id.split("-")

        assert len(parts) == 3
        assert parts[0] == "ACT"
        assert len(parts[1]) == 8  # YYYYMMDD
        assert parts[1].isdigit()
        assert len(parts[2]) == 8  # UUID hex
        assert all(c in "0123456789ABCDEF" for c in parts[2])

    def test_concurrent_id_generation(self, fcc):
        """IDs should be unique even in concurrent scenarios"""
        import threading
        import time

        ids = []
        lock = threading.Lock()

        def generate_ids(count):
            for _ in range(count):
                id = fcc._generate_action_id()
                with lock:
                    ids.append(id)

        threads = [threading.Thread(target=generate_ids, args=(50,)) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(ids) == 250
        assert len(set(ids)) == 250, "All concurrent IDs should be unique"

    # ═══════════════════════════════════════════════════════════════════════════════
    # COMPONENT CRITICALITY WEIGHT TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_criticality_weights_exist(self, fcc):
        """All components should have criticality weights"""
        assert hasattr(fcc, "COMPONENT_CRITICALITY")
        assert len(fcc.COMPONENT_CRITICALITY) > 0

    def test_transmission_has_highest_weight(self, fcc):
        """Transmisión should have max criticality (3.0)"""
        assert fcc.COMPONENT_CRITICALITY["Transmisión"] == 3.0

    def test_brakes_have_high_weight(self, fcc):
        """Brake system should have max criticality (3.0) for safety"""
        assert fcc.COMPONENT_CRITICALITY["Sistema de frenos de aire"] == 3.0

    def test_gps_has_lowest_weight(self, fcc):
        """GPS should have lower weight (not safety-critical)"""
        assert fcc.COMPONENT_CRITICALITY["GPS"] < 1.0

    def test_priority_score_boosted_by_criticality(self, fcc):
        """High criticality components should get higher scores"""
        # Same days_to_critical, different components
        _, score_trans = fcc._calculate_priority_score(10, component="Transmisión")
        _, score_gps = fcc._calculate_priority_score(10, component="GPS")

        assert score_trans > score_gps, "Transmisión should score higher than GPS"

    def test_criticality_boost_formula(self, fcc):
        """Test the criticality boost formula"""
        # Base score at 10 days = 65.0 - (10-7)*1.5 = 60.5
        base_days = 10

        # With Transmisión (3.0 criticality)
        # boost = (3.0 - 1.0) * 0.5 = 1.0
        # score = 60.5 * (1 + 1.0) = 121, capped at 100
        _, score_trans = fcc._calculate_priority_score(
            base_days, component="Transmisión"
        )

        # With GPS (0.8 criticality)
        # boost = (0.8 - 1.0) * 0.5 = -0.1
        # score = 60.5 * (1 - 0.1) = 54.45
        _, score_gps = fcc._calculate_priority_score(base_days, component="GPS")

        assert score_trans >= 85, f"Transmisión score {score_trans} should be >= 85"
        assert 50 <= score_gps <= 60, f"GPS score {score_gps} should be 50-60"

    def test_criticality_doesnt_break_capping(self, fcc):
        """Scores should still be capped at 0-100 after criticality boost"""
        # Already critical (0 days) + high criticality
        _, score = fcc._calculate_priority_score(0, component="Transmisión")
        assert score == 100, "Score should be capped at 100"

    def test_no_component_defaults_to_base_calculation(self, fcc):
        """Without component, should use base calculation"""
        priority1, score1 = fcc._calculate_priority_score(10)
        priority2, score2 = fcc._calculate_priority_score(10, component=None)

        # Should be same
        assert score1 == score2

    # ═══════════════════════════════════════════════════════════════════════════════
    # COST DATABASE TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_cost_database_exists(self, fcc):
        """Cost database should exist"""
        assert hasattr(fcc, "COMPONENT_COSTS")
        assert len(fcc.COMPONENT_COSTS) > 0

    def test_cost_database_structure(self, fcc):
        """Each cost entry should have min, max, avg"""
        for component, costs in fcc.COMPONENT_COSTS.items():
            assert "min" in costs, f"{component} missing 'min'"
            assert "max" in costs, f"{component} missing 'max'"
            assert "avg" in costs, f"{component} missing 'avg'"
            assert costs["min"] <= costs["avg"] <= costs["max"]

    def test_get_component_cost_known(self, fcc):
        """Known components should return correct costs"""
        cost = fcc._get_component_cost("Transmisión")
        assert cost["min"] == 8000
        assert cost["max"] == 15000
        assert cost["avg"] == 11500

    def test_get_component_cost_unknown(self, fcc):
        """Unknown components should return default costs"""
        cost = fcc._get_component_cost("Componente Inventado")
        assert cost["min"] == 500
        assert cost["max"] == 2000
        assert cost["avg"] == 1250

    def test_format_cost_string(self, fcc):
        """Cost string should be formatted correctly"""
        cost_str = fcc._format_cost_string("Transmisión")
        assert cost_str == "$8,000 - $15,000"

    def test_high_cost_boosts_priority(self, fcc):
        """High cost components should get priority boost"""
        # Transmisión: avg $11,500 → +10 points
        _, score_trans = fcc._calculate_priority_score(30, component="Transmisión")

        # GPS: avg $300 → no boost
        _, score_gps = fcc._calculate_priority_score(30, component="GPS")

        # Even without criticality, cost should add points
        # But criticality also affects, so Transmisión wins by a lot
        assert score_trans > score_gps

    # ═══════════════════════════════════════════════════════════════════════════════
    # PATTERN DETECTION TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_pattern_thresholds_exist(self, fcc):
        """Pattern thresholds should be defined"""
        assert hasattr(fcc, "PATTERN_THRESHOLDS")
        assert "fleet_wide_issue_pct" in fcc.PATTERN_THRESHOLDS
        assert "min_trucks_for_pattern" in fcc.PATTERN_THRESHOLDS

    def test_pattern_threshold_is_percentage(self, fcc):
        """Fleet-wide issue should be a percentage"""
        pct = fcc.PATTERN_THRESHOLDS["fleet_wide_issue_pct"]
        assert 0 < pct < 1, "Should be a decimal percentage"

    def test_min_trucks_for_pattern(self, fcc):
        """Minimum trucks for pattern should be reasonable"""
        min_trucks = fcc.PATTERN_THRESHOLDS["min_trucks_for_pattern"]
        assert min_trucks >= 2, "Need at least 2 trucks for a pattern"

    # ═══════════════════════════════════════════════════════════════════════════════
    # PRIORITY CALCULATION TESTS (Existing functionality)
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_priority_critical_when_overdue(self, fcc):
        """0 or negative days should be CRITICAL"""
        priority, score = fcc._calculate_priority_score(0)
        assert priority == Priority.CRITICAL
        assert score == 100

        priority, score = fcc._calculate_priority_score(-5)
        assert priority == Priority.CRITICAL

    def test_priority_critical_within_3_days(self, fcc):
        """1-3 days should still be CRITICAL"""
        for days in [1, 2, 3]:
            priority, _ = fcc._calculate_priority_score(days)
            assert priority == Priority.CRITICAL, f"Day {days} should be CRITICAL"

    def test_priority_high_within_week(self, fcc):
        """4-7 days should be HIGH"""
        for days in [4, 5, 6, 7]:
            priority, _ = fcc._calculate_priority_score(days)
            assert priority == Priority.HIGH, f"Day {days} should be HIGH"

    def test_priority_medium_within_month(self, fcc):
        """8-30 days should be MEDIUM"""
        priority, _ = fcc._calculate_priority_score(15)
        assert priority == Priority.MEDIUM

    def test_priority_low_beyond_month(self, fcc):
        """60+ days should be LOW or NONE"""
        priority, _ = fcc._calculate_priority_score(60)
        assert priority in [Priority.LOW, Priority.NONE]

    def test_anomaly_score_adds_to_priority(self, fcc):
        """Anomaly score should boost priority"""
        _, base_score = fcc._calculate_priority_score(20)
        _, boosted_score = fcc._calculate_priority_score(20, anomaly_score=50)

        assert boosted_score > base_score

    # ═══════════════════════════════════════════════════════════════════════════════
    # ACTION TYPE TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_critical_action_type_stop_immediately(self, fcc):
        """CRITICAL with <=1 day should STOP_IMMEDIATELY"""
        action = fcc._determine_action_type(Priority.CRITICAL, days_to_critical=0)
        assert action == ActionType.STOP_IMMEDIATELY

    def test_critical_action_type_schedule_this_week(self, fcc):
        """CRITICAL with >1 day should SCHEDULE_THIS_WEEK"""
        action = fcc._determine_action_type(Priority.CRITICAL, days_to_critical=3)
        assert action == ActionType.SCHEDULE_THIS_WEEK

    def test_high_action_type(self, fcc):
        """HIGH should SCHEDULE_THIS_WEEK"""
        action = fcc._determine_action_type(Priority.HIGH, days_to_critical=5)
        assert action == ActionType.SCHEDULE_THIS_WEEK

    def test_medium_action_type(self, fcc):
        """MEDIUM should SCHEDULE_THIS_MONTH"""
        action = fcc._determine_action_type(Priority.MEDIUM, days_to_critical=20)
        assert action == ActionType.SCHEDULE_THIS_MONTH

    def test_low_action_type(self, fcc):
        """LOW should MONITOR"""
        action = fcc._determine_action_type(Priority.LOW, days_to_critical=45)
        assert action == ActionType.MONITOR

    def test_none_action_type(self, fcc):
        """NONE should NO_ACTION"""
        action = fcc._determine_action_type(Priority.NONE, days_to_critical=100)
        assert action == ActionType.NO_ACTION

    # ═══════════════════════════════════════════════════════════════════════════════
    # DATA CLASS TESTS
    # ═══════════════════════════════════════════════════════════════════════════════

    def test_action_item_to_dict(self, fcc):
        """ActionItem should serialize correctly"""
        item = ActionItem(
            id="ACT-TEST-001",
            truck_id="TRUCK-001",
            priority=Priority.CRITICAL,
            priority_score=95.5,
            category=IssueCategory.TRANSMISSION,
            component="Transmisión",
            title="Test Issue",
            description="Test description",
            days_to_critical=2.5,
            cost_if_ignored="$8,000 - $15,000",
            current_value="225°F",
            trend="+2°F/day",
            threshold="Max: 230°F",
            confidence="HIGH",
            action_type=ActionType.SCHEDULE_THIS_WEEK,
            action_steps=["Step 1", "Step 2"],
            icon="⚙️",
            sources=["PM Engine"],
        )

        d = item.to_dict()

        assert d["id"] == "ACT-TEST-001"
        assert d["priority"] == "CRÍTICO"  # Enum value
        assert d["priority_score"] == 95.5
        assert d["days_to_critical"] == 2.5
        assert d["action_type"] == "Programar Esta Semana"
        assert len(d["action_steps"]) == 2

    def test_urgency_summary_total(self):
        """UrgencySummary should calculate total correctly"""
        summary = UrgencySummary(critical=2, high=3, medium=5, low=1, ok=10)
        assert summary.total_issues == 11  # Excludes 'ok'

    def test_fleet_health_score_dataclass(self):
        """FleetHealthScore should work correctly"""
        health = FleetHealthScore(
            score=85,
            status="Bueno",
            trend="stable",
            description="La flota está operando bien",
        )
        assert health.score == 85
        assert health.status == "Bueno"


class TestComponentCategories:
    """Tests for component categorization"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_all_components_have_categories(self, fcc):
        """All components in COMPONENT_ICONS should have categories"""
        for component in fcc.COMPONENT_ICONS:
            if component not in ["GPS", "Voltaje", "DTC"]:  # Sensor-specific
                assert (
                    component in fcc.COMPONENT_CATEGORIES
                    or component in fcc.COMPONENT_CATEGORIES.values()
                )

    def test_transmission_is_transmission_category(self, fcc):
        """Transmisión should map to TRANSMISSION category"""
        assert fcc.COMPONENT_CATEGORIES["Transmisión"] == IssueCategory.TRANSMISSION

    def test_turbo_components_map_to_turbo(self, fcc):
        """All turbo components should map to TURBO"""
        turbo_components = ["Turbocompresor", "Turbo / Intercooler", "Intercooler"]
        for comp in turbo_components:
            assert fcc.COMPONENT_CATEGORIES.get(comp) == IssueCategory.TURBO


class TestEnums:
    """Tests for enum values"""

    def test_priority_values(self):
        """Priority enum should have correct Spanish values"""
        assert Priority.CRITICAL.value == "CRÍTICO"
        assert Priority.HIGH.value == "ALTO"
        assert Priority.MEDIUM.value == "MEDIO"
        assert Priority.LOW.value == "BAJO"
        assert Priority.NONE.value == "OK"

    def test_action_type_values(self):
        """ActionType enum should have correct Spanish values"""
        assert ActionType.STOP_IMMEDIATELY.value == "Detener Inmediatamente"
        assert ActionType.SCHEDULE_THIS_WEEK.value == "Programar Esta Semana"
        assert ActionType.SCHEDULE_THIS_MONTH.value == "Programar Este Mes"
        assert ActionType.MONITOR.value == "Monitorear"
        assert ActionType.NO_ACTION.value == "Sin Acción"

    def test_issue_category_values(self):
        """IssueCategory enum should have correct values"""
        assert IssueCategory.ENGINE.value == "Motor"
        assert IssueCategory.TRANSMISSION.value == "Transmisión"
        assert IssueCategory.BRAKES.value == "Frenos"


# ═══════════════════════════════════════════════════════════════════════════════
# v1.1.0: HISTORICAL TREND TRACKING TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestHistoricalTrends:
    """Tests for historical trend tracking"""

    def test_calculate_trend_improving(self):
        """Increasing values should return 'improving'"""
        values = [50, 52, 55, 58, 60, 62, 65, 68, 70, 72]
        assert _calculate_trend(values) == "improving"

    def test_calculate_trend_declining(self):
        """Decreasing values should return 'declining'"""
        values = [80, 78, 75, 72, 70, 68, 65, 62, 60, 58]
        assert _calculate_trend(values) == "declining"

    def test_calculate_trend_stable(self):
        """Flat values should return 'stable'"""
        values = [70, 71, 70, 69, 70, 71, 70, 69, 70, 71]
        assert _calculate_trend(values) == "stable"

    def test_calculate_trend_single_value(self):
        """Single value should return 'stable'"""
        assert _calculate_trend([50]) == "stable"

    def test_calculate_trend_empty(self):
        """Empty list should return 'stable'"""
        assert _calculate_trend([]) == "stable"

    def test_calculate_trend_two_values(self):
        """Two values should work"""
        assert _calculate_trend([50, 60]) == "improving"
        assert _calculate_trend([60, 50]) == "declining"

    def test_calculate_trend_small_change_is_stable(self):
        """Changes under 3% should be 'stable'"""
        # 2% increase: should be stable
        values = [100, 100, 101, 101, 102, 102]
        assert _calculate_trend(values) == "stable"


class TestCacheConfiguration:
    """Tests for cache configuration"""

    def test_cache_ttl_constants_exist(self):
        """Cache TTL constants should be defined"""
        from fleet_command_center import CACHE_TTL_DASHBOARD, CACHE_TTL_ACTIONS

        assert CACHE_TTL_DASHBOARD == 30
        assert CACHE_TTL_ACTIONS == 15

    def test_cache_key_constants_exist(self):
        """Cache key constants should be defined"""
        from fleet_command_center import CACHE_KEY_DASHBOARD, CACHE_KEY_ACTIONS

        assert "command_center" in CACHE_KEY_DASHBOARD
        assert "command_center" in CACHE_KEY_ACTIONS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
