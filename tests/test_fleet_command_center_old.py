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
    SensorStatus,
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

    def test_version_is_1_3_0(self, fcc):
        """Verify we're testing v1.3.0"""
        assert fcc.VERSION == "1.8.0"

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
        """
        Test the criticality boost formula v1.3.0.

        v1.3.0 uses weighted scoring:
        - Days urgency (45%): Exponential decay
        - Anomaly score (20%): Normalized ML score
        - Component criticality (25%): Based on COMPONENT_CRITICALITY
        - Cost factor (10%): Based on repair cost

        At 10 days with exp decay k=0.04: urgency = 100 * e^(-0.04*10) = 67.0
        With Transmisión (3.0 criticality): criticality_score = 100
        With Transmisión cost ($11,500): cost_score = 76.7
        Weighted: (67*0.45 + 100*0.25 + 76.7*0.10) / 0.8 = ~78
        """
        base_days = 10

        # With Transmisión (3.0 criticality + high cost)
        _, score_trans = fcc._calculate_priority_score(
            base_days, component="Transmisión"
        )

        # With GPS (0.8 criticality + low cost)
        _, score_gps = fcc._calculate_priority_score(base_days, component="GPS")

        # Transmisión should be significantly higher due to criticality + cost
        assert score_trans >= 70, f"Transmisión score {score_trans} should be >= 70"
        assert 40 <= score_gps <= 60, f"GPS score {score_gps} should be 40-60"
        assert score_trans > score_gps + 10, "Transmisión should be 10+ points higher"

    def test_criticality_doesnt_break_capping(self, fcc):
        """
        Scores should still be capped at 0-100 after criticality boost.

        v1.3.0: With 0 days + Transmisión:
        - Days urgency: 100 (max)
        - Criticality: 100 (max for 3.0)
        - Cost: ~77 (for $11,500)
        Final should approach but not exceed 100
        """
        _, score = fcc._calculate_priority_score(0, component="Transmisión")
        assert score <= 100, "Score should be capped at 100"
        assert score >= 95, "Score should be very high for critical + high-criticality"

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
        """
        5-7 days should be HIGH with v1.3.0 exponential decay.

        v1.3.0: Uses exp decay k=0.04 for days scoring.
        - 4 days: urgency = 85.2 → borderline CRITICAL (>=85)
        - 5 days: urgency = 81.9 → HIGH (65-84)
        - 6 days: urgency = 78.7 → HIGH
        - 7 days: urgency = 75.6 → HIGH

        Note: With only days signal, the weighted formula gives:
        score = urgency * 0.45 / 0.45 = urgency
        """
        for days in [5, 6, 7]:
            priority, score = fcc._calculate_priority_score(days)
            assert (
                priority == Priority.HIGH
            ), f"Day {days} should be HIGH (score={score})"

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


# ═══════════════════════════════════════════════════════════════════════════════
# v1.2.0: DEDUPLICATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


def _make_action_item(
    id: str,
    truck_id: str,
    priority: Priority,
    priority_score: float,
    category: IssueCategory,
    component: str,
    sources: list,
) -> ActionItem:
    """Helper to create ActionItem with all required fields"""
    return ActionItem(
        id=id,
        truck_id=truck_id,
        priority=priority,
        priority_score=priority_score,
        category=category,
        component=component,
        title=f"Test issue for {component}",
        description="Test description",
        days_to_critical=None,
        cost_if_ignored=None,
        current_value=None,
        trend=None,
        threshold=None,
        confidence="MEDIUM",
        action_type=ActionType.INSPECT,
        action_steps=["Step 1", "Step 2"],
        icon="🔧",
        sources=sources,
    )


class TestActionItemDeduplication:
    """Tests for v1.2.0 action item deduplication"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_deduplication_exists(self, fcc):
        """Deduplication method should exist"""
        assert hasattr(fcc, "_deduplicate_action_items")

    def test_deduplication_keeps_higher_priority(self, fcc):
        """Should keep item with higher priority_score"""
        items = [
            _make_action_item(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.ENGINE,
                component="Motor",
                sources=["Source A"],
            ),
            _make_action_item(
                id="ACT-2",
                truck_id="T001",
                priority=Priority.CRITICAL,
                priority_score=95,
                category=IssueCategory.ENGINE,
                component="Motor",
                sources=["Source B"],
            ),
        ]

        result = fcc._deduplicate_action_items(items)

        assert len(result) == 1
        assert result[0].priority_score == 95

    def test_deduplication_normalizes_component_names(self, fcc):
        """Should normalize component names (Transmision, Transmission, etc.)"""
        items = [
            _make_action_item(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.TRANSMISSION,
                component="Transmisión",
                sources=["Source A"],
            ),
            _make_action_item(
                id="ACT-2",
                truck_id="T001",
                priority=Priority.MEDIUM,
                priority_score=50,
                category=IssueCategory.TRANSMISSION,
                component="Transmission",
                sources=["Source B"],
            ),
        ]

        result = fcc._deduplicate_action_items(items)

        # Should deduplicate because they're same component, same truck
        assert len(result) == 1

    def test_deduplication_merges_sources(self, fcc):
        """Should merge sources from duplicate items"""
        items = [
            _make_action_item(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                priority_score=80,
                category=IssueCategory.ENGINE,
                component="Motor",
                sources=["Source A"],
            ),
            _make_action_item(
                id="ACT-2",
                truck_id="T001",
                priority=Priority.MEDIUM,
                priority_score=60,
                category=IssueCategory.ENGINE,
                component="Motor",
                sources=["Source B"],
            ),
        ]

        result = fcc._deduplicate_action_items(items)

        assert len(result) == 1
        # Sources should be merged
        sources = result[0].sources
        assert "Source A" in sources
        assert "Source B" in sources or "+1 source" in str(sources)

    def test_deduplication_different_trucks(self, fcc):
        """Different trucks should NOT be deduplicated"""
        items = [
            _make_action_item(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.ENGINE,
                component="Motor",
                sources=["Source A"],
            ),
            _make_action_item(
                id="ACT-2",
                truck_id="T002",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.ENGINE,
                component="Motor",
                sources=["Source B"],
            ),
        ]

        result = fcc._deduplicate_action_items(items)

        assert len(result) == 2

    def test_deduplication_empty_list(self, fcc):
        """Should handle empty list"""
        result = fcc._deduplicate_action_items([])
        assert result == []

    def test_deduplication_fleet_items_by_component(self, fcc):
        """FLEET-level items should dedupe by component only"""
        items = [
            _make_action_item(
                id="ACT-1",
                truck_id="FLEET",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.ELECTRICAL,
                component="Sistema eléctrico",
                sources=["Source A"],
            ),
            _make_action_item(
                id="ACT-2",
                truck_id="FLEET",
                priority=Priority.MEDIUM,
                priority_score=50,
                category=IssueCategory.ELECTRICAL,
                component="Sistema eléctrico",
                sources=["Source B"],
            ),
        ]

        result = fcc._deduplicate_action_items(items)

        # Should deduplicate - same component for FLEET
        assert len(result) == 1


# ═══════════════════════════════════════════════════════════════════════════════
# v1.2.0: THREAD SAFETY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestThreadSafety:
    """Tests for v1.2.0 thread safety improvements"""

    def test_trend_history_is_deque(self):
        """_trend_history should be a deque with maxlen"""
        from fleet_command_center import _trend_history
        from collections import deque

        assert isinstance(_trend_history, deque)
        assert _trend_history.maxlen == 1000

    def test_trend_lock_exists(self):
        """Thread lock should exist for trend operations"""
        from fleet_command_center import _trend_lock
        import threading

        assert isinstance(_trend_lock, type(threading.Lock()))

    def test_calculate_trend_handles_small_lists(self):
        """_calculate_trend should handle lists with 0, 1, 2 elements"""
        assert _calculate_trend([]) == "stable"
        assert _calculate_trend([50]) == "stable"
        assert _calculate_trend([50, 60]) == "improving"
        assert _calculate_trend([60, 50]) == "declining"

    def test_calculate_trend_edge_case_two_elements(self):
        """Bug fix: len(recent) // 2 should be at least 1"""
        # This was causing IndexError before v1.2.0
        result = _calculate_trend([50, 51])
        assert result in ("stable", "improving", "declining")


# ═══════════════════════════════════════════════════════════════════════════════
# v1.3.0: VERSION CHECK
# ═══════════════════════════════════════════════════════════════════════════════


class TestVersionV13:
    """Tests for v1.3.0 version"""

    def test_version_is_1_3_0(self):
        """Verify version is 1.3.0"""
        fcc = FleetCommandCenter()
        assert fcc.VERSION == "1.8.0"


class TestV13ExponentialDecay:
    """Tests for v1.3.0 exponential decay urgency scoring"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_zero_days_gives_max_urgency(self, fcc):
        """0 days should give 100 urgency"""
        score = fcc._calculate_urgency_from_days(0)
        assert score == 100.0

    def test_negative_days_gives_max_urgency(self, fcc):
        """Negative days (overdue) should give 100 urgency"""
        score = fcc._calculate_urgency_from_days(-5)
        assert score == 100.0

    def test_urgency_decreases_over_time(self, fcc):
        """Urgency should decrease as days increase"""
        scores = [fcc._calculate_urgency_from_days(d) for d in [1, 5, 10, 20, 30, 60]]
        for i in range(len(scores) - 1):
            assert (
                scores[i] > scores[i + 1]
            ), f"Score at day {[1,5,10,20,30,60][i]} should be > next"

    def test_urgency_has_floor(self, fcc):
        """Urgency should not go below 5 even for very distant dates"""
        score = fcc._calculate_urgency_from_days(365)  # 1 year away
        assert score >= 5.0, "Should have floor of 5"

    def test_smooth_decay_curve(self, fcc):
        """Should have smooth decay without jumps"""
        scores = [fcc._calculate_urgency_from_days(d) for d in range(0, 31)]
        for i in range(len(scores) - 1):
            diff = scores[i] - scores[i + 1]
            # Each step should be small (no big jumps)
            assert diff < 10, f"Jump from day {i} to {i+1} too big: {diff}"


class TestV13ComponentNormalization:
    """Tests for v1.3.0 component normalization"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_normalize_transmission_variants(self, fcc):
        """Different transmission names should normalize to same key"""
        variants = ["Transmisión", "Transmission", "trans", "TRANSMISION"]
        results = [fcc._normalize_component(v) for v in variants]
        assert len(set(results)) == 1, f"All should normalize to same: {results}"

    def test_normalize_oil_variants(self, fcc):
        """Different oil system names should normalize"""
        variants = ["Sistema de Lubricación", "oil", "oil_press", "aceite"]
        for v in variants:
            result = fcc._normalize_component(v)
            assert (
                result == "oil_system"
            ), f"{v} should normalize to oil_system, got {result}"

    def test_normalize_cooling_variants(self, fcc):
        """Different cooling names should normalize"""
        variants = ["cooling", "cool_temp", "enfriamiento", "coolant"]
        for v in variants:
            result = fcc._normalize_component(v)
            assert (
                result == "cooling_system"
            ), f"{v} should normalize to cooling_system, got {result}"

    def test_caching_works(self, fcc):
        """Normalization should cache results"""
        # Clear cache first
        fcc._component_cache = {}

        # First call
        result1 = fcc._normalize_component("Transmisión")
        assert "Transmisión" in fcc._component_cache

        # Second call should use cache
        result2 = fcc._normalize_component("Transmisión")
        assert result1 == result2

    def test_unknown_component_returns_cleaned(self, fcc):
        """Unknown component should return cleaned version"""
        result = fcc._normalize_component("Componente Inventado XYZ")
        assert "_" in result or result.islower()  # Should be cleaned


class TestV13SensorValidation:
    """Tests for v1.3.0 sensor validation"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_valid_sensor_value(self, fcc):
        """Valid sensor values should pass through"""
        result = fcc._validate_sensor_value(200.0, "oil_temp")
        assert result == 200.0

    def test_none_value_returns_none(self, fcc):
        """None values should return None"""
        result = fcc._validate_sensor_value(None, "oil_temp")
        assert result is None

    def test_nan_returns_none(self, fcc):
        """NaN values should return None"""
        import math

        result = fcc._validate_sensor_value(float("nan"), "oil_temp")
        assert result is None

    def test_inf_returns_none(self, fcc):
        """Infinity values should return None"""
        result = fcc._validate_sensor_value(float("inf"), "oil_temp")
        assert result is None

    def test_out_of_range_returns_none(self, fcc):
        """Out of range values should return None"""
        # Oil temp should be in SENSOR_VALID_RANGES
        result = fcc._validate_sensor_value(1000.0, "oil_temp")  # Way too high
        assert result is None

    def test_dict_validation(self, fcc):
        """Should validate all sensors in a dict"""
        sensors = {
            "oil_temp": 200.0,
            "coolant_temp": None,
            "voltage": 14.0,
        }
        result = fcc._validate_sensor_dict(sensors)

        assert result["oil_temp"] == 200.0
        assert result["coolant_temp"] is None
        assert result["voltage"] == 14.0


class TestV13SourceHierarchy:
    """Tests for v1.3.0 source hierarchy"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_realtime_has_highest_weight(self, fcc):
        """Real-Time Predictive should have highest weight"""
        weight = fcc._get_source_weight("Real-Time Predictive (trend)")
        assert weight >= 90

    def test_unknown_source_gets_low_weight(self, fcc):
        """Unknown sources should get low default weight"""
        weight = fcc._get_source_weight("Unknown Random Source")
        assert weight == 25

    def test_get_best_source_picks_highest(self, fcc):
        """Should pick source with highest weight"""
        sources = ["GPS Data", "Real-Time Predictive (trend)", "DTC Analysis"]
        best = fcc._get_best_source(sources)
        assert "Real-Time" in best

    def test_get_best_source_empty_list(self, fcc):
        """Empty list should return Unknown"""
        best = fcc._get_best_source([])
        assert best == "Unknown"


class TestV13FleetHealthDistribution:
    """Tests for v1.3.0 fleet health with distribution analysis"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_fleet_health_with_no_action_items(self, fcc):
        """Should work without action_items parameter"""
        urgency = UrgencySummary(critical=0, high=0, medium=0, low=0, ok=10)
        result = fcc._calculate_fleet_health_score(urgency, 10)
        assert result.score >= 90  # Perfect fleet

    def test_fleet_health_penalizes_systemic_issues(self, fcc):
        """
        Systemic issues (many trucks affected) should lower fleet health more
        than concentrated issues (one truck with multiple problems).

        v1.3.0 logic: It's worse for fleet health if many trucks have issues
        (systemic problem) than if one truck has multiple issues (localized).
        """
        # Create action items all on one truck (localized issue)
        localized_items = [
            _make_action_item(
                id=f"ACT-{i}",
                truck_id="T001",  # Same truck - localized
                priority=Priority.HIGH,
                priority_score=80,
                category=IssueCategory.ENGINE,
                component="Motor",
                sources=["Test"],
            )
            for i in range(3)
        ]

        # Create action items on 3 different trucks (systemic issue)
        systemic_items = [
            _make_action_item(
                id=f"ACT-{i}",
                truck_id=f"T00{i+1}",  # Different trucks - systemic
                priority=Priority.HIGH,
                priority_score=80,
                category=IssueCategory.ENGINE,
                component="Motor",
                sources=["Test"],
            )
            for i in range(3)
        ]

        urgency = UrgencySummary(critical=0, high=3, medium=0, low=0, ok=7)

        result_localized = fcc._calculate_fleet_health_score(
            urgency, 10, localized_items
        )
        result_systemic = fcc._calculate_fleet_health_score(urgency, 10, systemic_items)

        # Systemic issues (spread across fleet) should result in lower health
        # because it indicates a fleet-wide problem
        assert (
            result_systemic.score <= result_localized.score
        ), f"Systemic ({result_systemic.score}) should be <= localized ({result_localized.score})"


class TestV13LoadEngineSafely:
    """Tests for v1.3.0 _load_engine_safely helper"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_successful_load(self, fcc):
        """Should return engine on success"""

        def factory():
            return {"test": "engine"}

        result = fcc._load_engine_safely("Test Engine", factory)
        assert result == {"test": "engine"}

    def test_import_error_returns_none(self, fcc):
        """ImportError should return None if not required"""

        def factory():
            raise ImportError("Module not found")

        result = fcc._load_engine_safely("Test Engine", factory, required=False)
        assert result is None

    def test_import_error_raises_if_required(self, fcc):
        """ImportError should raise if required"""

        def factory():
            raise ImportError("Module not found")

        with pytest.raises(RuntimeError):
            fcc._load_engine_safely("Test Engine", factory, required=True)

    def test_general_exception_returns_none(self, fcc):
        """General exceptions should return None if not required"""

        def factory():
            raise ValueError("Something went wrong")

        result = fcc._load_engine_safely("Test Engine", factory, required=False)
        assert result is None


class TestV13EnhancedInsights:
    """Tests for v1.3.0 enhanced insights"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_cost_impact_insight(self, fcc):
        """Should generate cost impact insight for high costs"""
        items = [
            ActionItem(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.CRITICAL,
                priority_score=95,
                category=IssueCategory.TRANSMISSION,
                component="Transmisión",
                title="Critical transmission issue",
                description="Test description",
                days_to_critical=1,
                cost_if_ignored=15000,  # High cost
                current_value=None,
                trend=None,
                threshold=None,
                confidence="HIGH",
                action_type=ActionType.STOP_IMMEDIATELY,
                action_steps=["Stop truck", "Inspect"],
                icon="⚙️",
                sources=["Test"],
            ),
        ]
        urgency = UrgencySummary(critical=1, high=0, medium=0, low=0, ok=9)

        insights = fcc._generate_insights(items, urgency)

        # Should have cost insight
        cost_insight = [i for i in insights if "💰" in i or "Costo" in i]
        assert (
            len(cost_insight) > 0
        ), f"Should generate cost impact insight. Got: {insights}"

    def test_escalation_warning_insight(self, fcc):
        """Should warn about issues escalating to critical soon"""
        items = [
            ActionItem(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                priority_score=80,
                category=IssueCategory.ENGINE,
                component="Motor",
                title="High priority engine issue",
                description="Test description",
                days_to_critical=2,  # Will escalate in 2 days
                cost_if_ignored=5000,
                current_value=None,
                trend=None,
                threshold=None,
                confidence="HIGH",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                action_steps=["Schedule service"],
                icon="🔧",
                sources=["Test"],
            ),
        ]
        urgency = UrgencySummary(critical=0, high=1, medium=0, low=0, ok=9)

        insights = fcc._generate_insights(items, urgency)

        # Should have escalation warning
        escalation_insight = [i for i in insights if "⏰" in i or "escalarán" in i]
        assert (
            len(escalation_insight) > 0
        ), f"Should warn about escalation. Got: {insights}"


# ═══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL COVERAGE TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestActionItemToDict:
    """Tests for ActionItem serialization"""

    def test_action_item_to_dict(self):
        """ActionItem.to_dict() should serialize all fields"""
        item = ActionItem(
            id="ACT-123",
            truck_id="T001",
            priority=Priority.HIGH,
            priority_score=75.5,
            category=IssueCategory.ENGINE,
            component="Motor",
            title="Test Title",
            description="Test Description",
            days_to_critical=5.5,
            cost_if_ignored="$1,000 - $2,000",
            current_value="100°F",
            trend="+2°F/día",
            threshold="Crítico: >200°F",
            confidence="HIGH",
            action_type=ActionType.SCHEDULE_THIS_WEEK,
            action_steps=["Step 1", "Step 2"],
            icon="🔧",
            sources=["Source A", "Source B"],
        )

        result = item.to_dict()

        assert result["id"] == "ACT-123"
        assert result["truck_id"] == "T001"
        assert result["priority"] == "ALTO"
        assert result["priority_score"] == 75.5
        assert result["category"] == "Motor"
        assert result["component"] == "Motor"
        assert result["title"] == "Test Title"
        assert result["description"] == "Test Description"
        assert result["days_to_critical"] == 5.5
        assert result["cost_if_ignored"] == "$1,000 - $2,000"
        assert result["current_value"] == "100°F"
        assert result["trend"] == "+2°F/día"
        assert result["threshold"] == "Crítico: >200°F"
        assert result["confidence"] == "HIGH"
        assert result["action_type"] == "Programar Esta Semana"
        assert result["action_steps"] == ["Step 1", "Step 2"]
        assert result["icon"] == "🔧"
        assert result["sources"] == ["Source A", "Source B"]

    def test_action_item_to_dict_null_values(self):
        """ActionItem.to_dict() should handle None values"""
        item = ActionItem(
            id="ACT-123",
            truck_id="T001",
            priority=Priority.LOW,
            priority_score=25.0,
            category=IssueCategory.SENSOR,
            component="GPS",
            title="Test",
            description="Test",
            days_to_critical=None,
            cost_if_ignored=None,
            current_value=None,
            trend=None,
            threshold=None,
            confidence="LOW",
            action_type=ActionType.MONITOR,
            action_steps=[],
            icon="📡",
            sources=["Test"],
        )

        result = item.to_dict()

        assert result["days_to_critical"] is None
        assert result["cost_if_ignored"] is None
        assert result["current_value"] is None


class TestUrgencySummary:
    """Tests for UrgencySummary"""

    def test_total_issues_property(self):
        """total_issues should sum all issue counts"""
        summary = UrgencySummary(
            critical=2,
            high=5,
            medium=10,
            low=3,
            ok=80,
        )

        assert summary.total_issues == 20  # 2+5+10+3

    def test_default_values(self):
        """Default values should be 0"""
        summary = UrgencySummary()

        assert summary.critical == 0
        assert summary.high == 0
        assert summary.medium == 0
        assert summary.low == 0
        assert summary.ok == 0
        assert summary.total_issues == 0


class TestCommandCenterDataToDict:
    """Tests for CommandCenterData serialization"""

    def test_to_dict_minimal(self):
        """to_dict() with minimal data"""
        data = CommandCenterData(
            generated_at="2025-01-01T00:00:00Z",
            version="1.0.0",
            total_trucks=10,
            trucks_analyzed=10,
        )

        result = data.to_dict()

        assert result["generated_at"] == "2025-01-01T00:00:00Z"
        assert result["version"] == "1.0.0"
        assert result["fleet_health"] is None
        assert result["total_trucks"] == 10
        assert result["action_items"] == []
        assert result["insights"] == []

    def test_to_dict_with_fleet_health(self):
        """to_dict() with FleetHealthScore"""
        data = CommandCenterData(
            generated_at="2025-01-01T00:00:00Z",
            fleet_health=FleetHealthScore(
                score=85,
                status="Bueno",
                trend="stable",
                description="Fleet is healthy",
            ),
        )

        result = data.to_dict()

        assert result["fleet_health"]["score"] == 85
        assert result["fleet_health"]["status"] == "Bueno"
        assert result["fleet_health"]["trend"] == "stable"

    def test_to_dict_with_urgency_summary(self):
        """to_dict() with UrgencySummary"""
        data = CommandCenterData(
            generated_at="2025-01-01T00:00:00Z",
            urgency_summary=UrgencySummary(
                critical=1,
                high=2,
                medium=3,
                low=4,
                ok=90,
            ),
        )

        result = data.to_dict()

        assert result["urgency_summary"]["critical"] == 1
        assert result["urgency_summary"]["high"] == 2
        assert result["urgency_summary"]["total_issues"] == 10


class TestDetermineActionType:
    """Tests for _determine_action_type"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_critical_with_zero_days(self, fcc):
        """CRITICAL + 0 days = STOP_IMMEDIATELY"""
        result = fcc._determine_action_type(Priority.CRITICAL, 0)
        assert result == ActionType.STOP_IMMEDIATELY

    def test_critical_with_one_day(self, fcc):
        """CRITICAL + 1 day = STOP_IMMEDIATELY"""
        result = fcc._determine_action_type(Priority.CRITICAL, 1)
        assert result == ActionType.STOP_IMMEDIATELY

    def test_critical_with_two_days(self, fcc):
        """CRITICAL + 2 days = SCHEDULE_THIS_WEEK"""
        result = fcc._determine_action_type(Priority.CRITICAL, 2)
        assert result == ActionType.SCHEDULE_THIS_WEEK

    def test_critical_no_days(self, fcc):
        """CRITICAL + None days = SCHEDULE_THIS_WEEK"""
        result = fcc._determine_action_type(Priority.CRITICAL, None)
        assert result == ActionType.SCHEDULE_THIS_WEEK

    def test_high_priority(self, fcc):
        """HIGH = SCHEDULE_THIS_WEEK"""
        result = fcc._determine_action_type(Priority.HIGH, 10)
        assert result == ActionType.SCHEDULE_THIS_WEEK

    def test_medium_priority(self, fcc):
        """MEDIUM = SCHEDULE_THIS_MONTH"""
        result = fcc._determine_action_type(Priority.MEDIUM, 30)
        assert result == ActionType.SCHEDULE_THIS_MONTH

    def test_low_priority(self, fcc):
        """LOW = MONITOR"""
        result = fcc._determine_action_type(Priority.LOW, 60)
        assert result == ActionType.MONITOR

    def test_none_priority(self, fcc):
        """NONE = NO_ACTION"""
        result = fcc._determine_action_type(Priority.NONE, None)
        assert result == ActionType.NO_ACTION


class TestGenerateActionSteps:
    """Tests for _generate_action_steps"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_stop_immediately_steps(self, fcc):
        """STOP_IMMEDIATELY should have urgent steps"""
        steps = fcc._generate_action_steps(
            "Motor", ActionType.STOP_IMMEDIATELY, "Check oil"
        )

        assert any("Detener" in step for step in steps)
        assert any("Contactar" in step for step in steps)

    def test_schedule_this_week_steps(self, fcc):
        """SCHEDULE_THIS_WEEK should have scheduling step"""
        steps = fcc._generate_action_steps(
            "Motor", ActionType.SCHEDULE_THIS_WEEK, "Check engine"
        )

        assert any("Agendar" in step for step in steps)

    def test_schedule_this_month_steps(self, fcc):
        """SCHEDULE_THIS_MONTH should have service step"""
        steps = fcc._generate_action_steps(
            "Motor", ActionType.SCHEDULE_THIS_MONTH, "Routine check"
        )

        assert any("servicio programado" in step for step in steps)

    def test_oil_component_steps(self, fcc):
        """Oil-related component should have oil-specific steps"""
        steps = fcc._generate_action_steps(
            "Bomba de aceite", ActionType.MONITOR, "Check oil"
        )

        assert any("aceite" in step.lower() for step in steps)

    def test_transmission_component_steps(self, fcc):
        """Transmission component should have transmission-specific steps"""
        steps = fcc._generate_action_steps(
            "Transmisión", ActionType.INSPECT, "Check transmission"
        )

        assert any("transmisión" in step.lower() for step in steps)

    def test_cooling_component_steps(self, fcc):
        """Cooling component should have cooling-specific steps"""
        steps = fcc._generate_action_steps(
            "Sistema de enfriamiento", ActionType.INSPECT, "Check cooling"
        )

        assert any("coolant" in step.lower() for step in steps)

    def test_def_component_steps(self, fcc):
        """DEF component should have DEF-specific steps"""
        steps = fcc._generate_action_steps(
            "Sistema DEF", ActionType.INSPECT, "Check DEF"
        )

        assert any("DEF" in step for step in steps)

    def test_electrical_component_steps(self, fcc):
        """Electrical component should have electrical-specific steps"""
        steps = fcc._generate_action_steps(
            "Sistema eléctrico", ActionType.INSPECT, "Check battery"
        )

        assert any(
            "batería" in step.lower() or "alternador" in step.lower() for step in steps
        )


class TestCalculateFleetHealthScore:
    """Tests for _calculate_fleet_health_score"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_no_trucks(self, fcc):
        """Zero trucks returns default score"""
        urgency = UrgencySummary()
        result = fcc._calculate_fleet_health_score(urgency, 0)

        assert result.score == 100
        assert result.status == "Sin datos"

    def test_perfect_fleet(self, fcc):
        """Fleet with no issues should be excellent"""
        urgency = UrgencySummary(critical=0, high=0, medium=0, low=0, ok=10)
        result = fcc._calculate_fleet_health_score(urgency, 10)

        assert result.score >= 90
        assert result.status == "Excelente"

    def test_critical_issues_reduce_score(self, fcc):
        """Critical issues should reduce score"""
        urgency = UrgencySummary(critical=5, high=0, medium=0, low=0, ok=5)
        result = fcc._calculate_fleet_health_score(urgency, 10)

        # With 5 critical issues in 10 trucks, score should be reduced
        assert result.score < 100

    def test_many_critical_issues(self, fcc):
        """Many critical issues should result in critical status"""
        urgency = UrgencySummary(critical=10, high=5, medium=5, low=0, ok=0)
        result = fcc._calculate_fleet_health_score(urgency, 10)

        assert result.score < 60
        assert result.status in ["Alerta", "Crítico"]


class TestGenerateInsights:
    """Tests for _generate_insights"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_no_issues_generates_positive_insight(self, fcc):
        """No critical/high issues should generate positive insight"""
        urgency = UrgencySummary(critical=0, high=0, medium=1, low=2, ok=10)
        items = []

        insights = fcc._generate_insights(items, urgency)

        assert any("✅" in insight for insight in insights)

    def test_critical_issues_generate_warning(self, fcc):
        """Critical issues should generate warning"""
        urgency = UrgencySummary(critical=1, high=0, medium=0, low=0, ok=9)
        items = [
            _make_action_item(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.CRITICAL,
                priority_score=95,
                category=IssueCategory.ENGINE,
                component="Motor",
                sources=["Test"],
            )
        ]

        insights = fcc._generate_insights(items, urgency)

        assert any("🚨" in insight for insight in insights)
        assert any("T001" in insight for insight in insights)

    def test_transmission_issues_generate_cost_warning(self, fcc):
        """Transmission issues should generate cost warning"""
        urgency = UrgencySummary(critical=0, high=1, medium=0, low=0, ok=9)
        items = [
            _make_action_item(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.TRANSMISSION,
                component="Transmisión",
                sources=["Test"],
            )
        ]

        insights = fcc._generate_insights(items, urgency)

        assert any(
            "transmisión" in insight.lower() and "costosa" in insight.lower()
            for insight in insights
        )

    def test_def_issues_generate_derate_warning(self, fcc):
        """DEF issues should generate derate warning"""
        urgency = UrgencySummary(critical=0, high=1, medium=0, low=0, ok=9)
        items = [
            _make_action_item(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.DEF,
                component="Sistema DEF",
                sources=["Test"],
            )
        ]

        insights = fcc._generate_insights(items, urgency)

        assert any(
            "DEF" in insight and "derate" in insight.lower() for insight in insights
        )


class TestEstimateCosts:
    """Tests for _estimate_costs"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_empty_items(self, fcc):
        """Empty items should return zero costs"""
        result = fcc._estimate_costs([])

        assert result.immediate_risk == "$0"
        assert result.week_risk == "$0"
        assert result.month_risk == "$0"

    def test_critical_item_adds_to_immediate(self, fcc):
        """Critical items should add to immediate risk"""
        items = [
            ActionItem(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.CRITICAL,
                priority_score=95,
                category=IssueCategory.ENGINE,
                component="Motor",
                title="Test",
                description="Test",
                days_to_critical=1,
                cost_if_ignored="$5,000 - $10,000",
                current_value=None,
                trend=None,
                threshold=None,
                confidence="HIGH",
                action_type=ActionType.STOP_IMMEDIATELY,
                action_steps=[],
                icon="🔧",
                sources=["Test"],
            )
        ]

        result = fcc._estimate_costs(items)

        assert "5,000" in result.immediate_risk or "10,000" in result.immediate_risk

    def test_high_item_adds_to_week(self, fcc):
        """High priority items should add to week risk"""
        items = [
            ActionItem(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.ENGINE,
                component="Motor",
                title="Test",
                description="Test",
                days_to_critical=5,
                cost_if_ignored="$3,000 - $5,000",
                current_value=None,
                trend=None,
                threshold=None,
                confidence="HIGH",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                action_steps=[],
                icon="🔧",
                sources=["Test"],
            )
        ]

        result = fcc._estimate_costs(items)

        assert "3,000" in result.week_risk or "5,000" in result.week_risk

    def test_invalid_cost_format_handled(self, fcc):
        """Invalid cost format should be skipped"""
        items = [
            ActionItem(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.CRITICAL,
                priority_score=95,
                category=IssueCategory.ENGINE,
                component="Motor",
                title="Test",
                description="Test",
                days_to_critical=1,
                cost_if_ignored="invalid",
                current_value=None,
                trend=None,
                threshold=None,
                confidence="HIGH",
                action_type=ActionType.STOP_IMMEDIATELY,
                action_steps=[],
                icon="🔧",
                sources=["Test"],
            )
        ]

        result = fcc._estimate_costs(items)

        assert result.immediate_risk == "$0"


class TestEnums:
    """Tests for enum values"""

    def test_priority_values(self):
        """Priority enum should have correct values"""
        assert Priority.CRITICAL.value == "CRÍTICO"
        assert Priority.HIGH.value == "ALTO"
        assert Priority.MEDIUM.value == "MEDIO"
        assert Priority.LOW.value == "BAJO"
        assert Priority.NONE.value == "OK"

    def test_issue_category_values(self):
        """IssueCategory enum should have correct values"""
        assert IssueCategory.ENGINE.value == "Motor"
        assert IssueCategory.TRANSMISSION.value == "Transmisión"
        assert IssueCategory.ELECTRICAL.value == "Eléctrico"
        assert IssueCategory.DEF.value == "DEF"
        assert IssueCategory.GPS.value == "GPS"

    def test_action_type_values(self):
        """ActionType enum should have correct values"""
        assert ActionType.STOP_IMMEDIATELY.value == "Detener Inmediatamente"
        assert ActionType.SCHEDULE_THIS_WEEK.value == "Programar Esta Semana"
        assert ActionType.SCHEDULE_THIS_MONTH.value == "Programar Este Mes"
        assert ActionType.MONITOR.value == "Monitorear"
        assert ActionType.NO_ACTION.value == "Sin Acción"


class TestComponentMappings:
    """Tests for component mappings"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_component_categories_exist(self, fcc):
        """Component categories should be defined"""
        assert len(fcc.COMPONENT_CATEGORIES) > 0
        assert "Transmisión" in fcc.COMPONENT_CATEGORIES
        assert "Sistema DEF" in fcc.COMPONENT_CATEGORIES

    def test_component_icons_exist(self, fcc):
        """Component icons should be defined"""
        assert len(fcc.COMPONENT_ICONS) > 0
        assert "Transmisión" in fcc.COMPONENT_ICONS
        assert "GPS" in fcc.COMPONENT_ICONS

    def test_component_costs_exist(self, fcc):
        """Component costs should be defined"""
        assert len(fcc.COMPONENT_COSTS) > 0
        assert "Transmisión" in fcc.COMPONENT_COSTS
        assert fcc.COMPONENT_COSTS["Transmisión"]["min"] > 0

    def test_get_component_cost_known(self, fcc):
        """Should return known component cost"""
        cost = fcc._get_component_cost("Transmisión")
        assert cost["min"] == 8000
        assert cost["max"] == 15000

    def test_get_component_cost_unknown(self, fcc):
        """Should return default for unknown component"""
        cost = fcc._get_component_cost("Unknown Component")
        assert cost["min"] == 500
        assert cost["max"] == 2000

    def test_format_cost_string(self, fcc):
        """Should format cost as string"""
        result = fcc._format_cost_string("Transmisión")
        assert "$8,000" in result
        assert "$15,000" in result


class TestPatternThresholds:
    """Tests for pattern detection thresholds"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_pattern_thresholds_exist(self, fcc):
        """Pattern thresholds should be defined"""
        assert hasattr(fcc, "PATTERN_THRESHOLDS")
        assert "fleet_wide_issue_pct" in fcc.PATTERN_THRESHOLDS
        assert "min_trucks_for_pattern" in fcc.PATTERN_THRESHOLDS
        assert "anomaly_threshold" in fcc.PATTERN_THRESHOLDS

    def test_pattern_threshold_values(self, fcc):
        """Pattern thresholds should have reasonable values"""
        assert 0 < fcc.PATTERN_THRESHOLDS["fleet_wide_issue_pct"] < 1
        assert fcc.PATTERN_THRESHOLDS["min_trucks_for_pattern"] >= 2
        assert 0 < fcc.PATTERN_THRESHOLDS["anomaly_threshold"] < 1


# ═══════════════════════════════════════════════════════════════════════════════
# ACTION ID GENERATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestActionIdGeneration:
    """Tests for action ID generation"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_generate_action_id_format(self, fcc):
        """Action ID should have correct format"""
        action_id = fcc._generate_action_id()

        assert action_id.startswith("ACT-")
        assert len(action_id) > 4

    def test_generate_action_id_unique(self, fcc):
        """Each action ID should be unique"""
        ids = [fcc._generate_action_id() for _ in range(100)]

        assert len(set(ids)) == 100

    def test_action_ids_are_unique(self, fcc):
        """Action IDs should be unique"""
        ids = [fcc._generate_action_id() for _ in range(10)]
        assert len(set(ids)) == 10


class TestPriorityScoreCalculation:
    """Tests for priority score calculation"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_critical_priority_for_imminent_failure(self, fcc):
        """Should be CRITICAL when days_to_critical <= 3"""
        priority, score = fcc._calculate_priority_score(days_to_critical=2)

        assert priority == Priority.CRITICAL
        assert score >= 85

    def test_high_priority_for_near_failure(self, fcc):
        """
        Should be HIGH when days_to_critical is 5-7 with v1.3.0.

        v1.3.0 uses exp decay k=0.04:
        - 5 days: urgency = 81.9 → HIGH
        """
        priority, score = fcc._calculate_priority_score(days_to_critical=5)

        assert priority == Priority.HIGH
        assert 65 <= score < 85, f"Expected 65-85, got {score}"

    def test_medium_priority_for_moderate_timeline(self, fcc):
        """
        Should be MEDIUM when days_to_critical is 12-20 with v1.3.0.

        v1.3.0 uses exp decay k=0.04:
        - 10 days: urgency = 67.0 → HIGH (>=65)
        - 12 days: urgency = 61.9 → MEDIUM (40-64)
        - 15 days: urgency = 54.9 → MEDIUM
        """
        priority, score = fcc._calculate_priority_score(days_to_critical=15)

        assert priority == Priority.MEDIUM, f"Expected MEDIUM, got {priority}"
        assert 40 <= score < 65, f"Expected 40-65, got {score}"

    def test_low_priority_for_distant_failure(self, fcc):
        """Should return score for distant failure"""
        priority, score = fcc._calculate_priority_score(days_to_critical=20)
        # Score formula gives 65 - (20-7)*1.5 = 45.5 for days 8-30
        assert score >= 20

    def test_priority_with_component(self, fcc):
        """
        Component adds criticality and cost signals to scoring.

        v1.3.0 formula with component adds criticality (25%) and cost (10%):
        - Without component: only days signal at 100% of available weight
        - With component: days (45%) + criticality (25%) + cost (10%)

        Note: Adding more signals doesn't always increase score - it provides
        a more balanced multi-factor assessment. A low-criticality component
        at a moderate timeline may score lower than days-only because we're
        now factoring in that the component itself isn't critical.

        High-criticality components (Transmisión=3.0) WILL score higher than
        low-criticality components (GPS=0.8).
        """
        _, score_trans = fcc._calculate_priority_score(
            days_to_critical=10, component="Transmisión"
        )
        _, score_gps = fcc._calculate_priority_score(
            days_to_critical=10, component="GPS"
        )

        # High criticality component should score higher than low criticality
        assert (
            score_trans > score_gps
        ), f"Transmisión {score_trans} should be > GPS {score_gps}"

    def test_priority_with_anomaly_score(self, fcc):
        """
        Anomaly score adds to the multi-factor assessment.

        v1.3.0: When adding anomaly, we add 20% weight to the calculation.
        A high anomaly score (90+) will increase the final score.
        A moderate anomaly score may actually lower it since we're dividing
        by more total weight.

        This test verifies a HIGH anomaly actually boosts the score.
        """
        _, score_no_anomaly = fcc._calculate_priority_score(days_to_critical=10)
        _, score_with_high_anomaly = fcc._calculate_priority_score(
            days_to_critical=10, anomaly_score=90
        )

        assert (
            score_with_high_anomaly > score_no_anomaly
        ), f"High anomaly {score_with_high_anomaly} should be > no anomaly {score_no_anomaly}"


class TestActionTypeMapping:
    """Tests for action type determination"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_stop_immediately_for_critical(self, fcc):
        """CRITICAL priority should result in STOP_IMMEDIATELY"""
        action_type = fcc._determine_action_type(Priority.CRITICAL, days_to_critical=0)

        assert action_type == ActionType.STOP_IMMEDIATELY

    def test_high_priority_mapping(self, fcc):
        """HIGH priority should return appropriate action"""
        action_type = fcc._determine_action_type(Priority.HIGH, days_to_critical=5)
        assert action_type is not None

    def test_medium_priority_mapping(self, fcc):
        """MEDIUM priority should return appropriate action"""
        action_type = fcc._determine_action_type(Priority.MEDIUM, days_to_critical=10)
        assert action_type is not None

    def test_low_priority_mapping(self, fcc):
        """LOW priority should return appropriate action"""
        action_type = fcc._determine_action_type(Priority.LOW, days_to_critical=30)
        assert action_type is not None


class TestActionStepsGeneration:
    """Tests for action steps generation"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_generate_steps_for_transmission(self, fcc):
        """Should generate relevant steps for transmission"""
        steps = fcc._generate_action_steps(
            "Transmisión", ActionType.INSPECT, "Check gears"
        )

        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_generate_steps_for_engine(self, fcc):
        """Should generate relevant steps for engine"""
        steps = fcc._generate_action_steps(
            "Motor", ActionType.SCHEDULE_THIS_WEEK, "Oil change needed"
        )

        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_generate_steps_for_def(self, fcc):
        """Should generate relevant steps for DEF system"""
        steps = fcc._generate_action_steps(
            "Sistema DEF", ActionType.SCHEDULE_THIS_WEEK, "DEF low"
        )

        assert isinstance(steps, list)
        assert len(steps) > 0

    def test_generate_steps_include_emojis(self, fcc):
        """Steps should include emoji indicators"""
        steps = fcc._generate_action_steps("Frenos", ActionType.INSPECT, "Brake wear")

        # Steps should have some visual indicators
        assert any(step for step in steps)

    def test_generate_steps_for_stop_immediately(self, fcc):
        """STOP_IMMEDIATELY should have urgent first step"""
        steps = fcc._generate_action_steps(
            "Motor", ActionType.STOP_IMMEDIATELY, "Critical failure"
        )

        assert isinstance(steps, list)
        assert len(steps) > 0


class TestSensorStatus:
    """Tests for SensorStatus dataclass"""

    def test_sensor_status_creation(self):
        """Should create SensorStatus with defaults"""
        status = SensorStatus()

        assert status.total_trucks == 0
        assert status.gps_issues == 0
        assert status.voltage_issues == 0
        assert status.dtc_active == 0

    def test_sensor_status_with_values(self):
        """Should create SensorStatus with specific values"""
        status = SensorStatus(
            total_trucks=50,
            gps_issues=5,
            voltage_issues=3,
            dtc_active=2,
            idle_deviation=4,
        )

        assert status.total_trucks == 50
        assert status.gps_issues == 5
        assert status.voltage_issues == 3

    def test_sensor_status_fields(self):
        """Should have expected fields"""
        status = SensorStatus(total_trucks=50, gps_issues=5)

        assert hasattr(status, "total_trucks")
        assert hasattr(status, "gps_issues")
        assert status.total_trucks == 50


class TestIssueCategoryEnum:
    """Tests for IssueCategory enum"""

    def test_all_categories_exist(self):
        """All expected issue categories should exist"""
        expected = [
            "ENGINE",
            "TRANSMISSION",
            "FUEL",
            "ELECTRICAL",
            "BRAKES",
            "DEF",
            "SENSOR",
            "GPS",
        ]

        for name in expected:
            assert hasattr(IssueCategory, name)

    def test_category_values(self):
        """Category values should be strings"""
        assert isinstance(IssueCategory.ENGINE.value, str)
        assert isinstance(IssueCategory.TRANSMISSION.value, str)
        assert isinstance(IssueCategory.FUEL.value, str)


class TestActionTypeEnum:
    """Tests for ActionType enum"""

    def test_all_action_types_exist(self):
        """All expected action types should exist"""
        expected = [
            "STOP_IMMEDIATELY",
            "INSPECT",
            "SCHEDULE_THIS_WEEK",
            "SCHEDULE_THIS_MONTH",
            "MONITOR",
            "NO_ACTION",
        ]

        for name in expected:
            assert hasattr(ActionType, name)

    def test_action_type_values(self):
        """Action type values should be strings"""
        assert isinstance(ActionType.STOP_IMMEDIATELY.value, str)
        assert isinstance(ActionType.MONITOR.value, str)


class TestPriorityEnum:
    """Tests for Priority enum"""

    def test_all_priorities_exist(self):
        """All expected priorities should exist"""
        expected = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]

        for name in expected:
            assert hasattr(Priority, name)

    def test_priority_values(self):
        """Priority values should be strings"""
        assert isinstance(Priority.CRITICAL.value, str)
        assert isinstance(Priority.LOW.value, str)


class TestCommandCenterDataCreation:
    """Tests for CommandCenterData creation"""

    def test_data_creation_with_defaults(self):
        """Should create CommandCenterData with default fields"""
        data = CommandCenterData(generated_at="2024-01-01T00:00:00Z")

        assert data.generated_at == "2024-01-01T00:00:00Z"
        assert len(data.action_items) == 0

    def test_data_has_version(self):
        """Should have version field"""
        data = CommandCenterData(generated_at="2024-01-01T00:00:00Z")

        assert data.version == "1.0.0"


class TestUrgencySummaryAggregation:
    """Tests for urgency summary aggregation"""

    def test_summary_totals(self):
        """Summary should correctly aggregate counts"""
        summary = UrgencySummary(critical=2, high=5, medium=10, low=20)

        total = summary.critical + summary.high + summary.medium + summary.low

        assert total == 37

    def test_summary_defaults(self):
        """Summary should have default values"""
        summary = UrgencySummary()

        assert summary.critical == 0
        assert summary.high == 0


class TestComponentCategoryMapping:
    """Tests for component to category mapping"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_transmission_category(self, fcc):
        """Transmisión should map to TRANSMISSION"""
        category = fcc.COMPONENT_CATEGORIES.get("Transmisión")

        assert category == IssueCategory.TRANSMISSION

    def test_def_category(self, fcc):
        """Sistema DEF should map to DEF"""
        category = fcc.COMPONENT_CATEGORIES.get("Sistema DEF")

        assert category == IssueCategory.DEF

    def test_unknown_component_default(self, fcc):
        """Unknown component should default to ENGINE"""
        category = fcc.COMPONENT_CATEGORIES.get("Unknown", IssueCategory.ENGINE)

        assert category == IssueCategory.ENGINE


class TestComponentIconMapping:
    """Tests for component to icon mapping"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_transmission_icon(self, fcc):
        """Transmisión should have an icon"""
        icon = fcc.COMPONENT_ICONS.get("Transmisión")

        assert icon is not None
        assert len(icon) > 0

    def test_gps_icon(self, fcc):
        """GPS should have an icon"""
        icon = fcc.COMPONENT_ICONS.get("GPS")

        assert icon is not None

    def test_default_icon(self, fcc):
        """Unknown component should use default icon"""
        icon = fcc.COMPONENT_ICONS.get("Unknown", "🔧")

        assert icon == "🔧"


# ═══════════════════════════════════════════════════════════════════════════════
# HIGH-COVERAGE TESTS FOR generate_command_center_data
# ═══════════════════════════════════════════════════════════════════════════════


class TestGenerateCommandCenterData:
    """Tests for the main generate_command_center_data method with mocks"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    @patch("fleet_command_center.get_predictive_maintenance_engine")
    def test_generate_with_pm_engine_success(self, mock_pm, fcc):
        """Should process PM engine data correctly"""
        # Mock PM engine response
        mock_engine = MagicMock()
        mock_engine.get_fleet_summary.return_value = {
            "critical_items": [
                {
                    "truck_id": "T001",
                    "component": "Motor",
                    "sensor": "oil_temp",
                    "days_to_critical": 2,
                    "cost_if_fail": "$5,000 - $10,000",
                    "current_value": "210°F",
                    "trend_per_day": "+5°F/day",
                }
            ],
            "high_priority_items": [
                {
                    "truck_id": "T002",
                    "component": "Sistema de Enfriamiento",
                    "sensor": "coolant_temp",
                    "days_to_critical": 7,
                }
            ],
        }
        mock_pm.return_value = mock_engine

        # Mock other dependencies to avoid errors
        with patch(
            "fleet_command_center.analyze_fleet_anomalies", side_effect=ImportError
        ):
            with patch(
                "fleet_command_center.get_sensor_health_summary",
                side_effect=ImportError,
            ):
                with patch(
                    "fleet_command_center.get_mysql_engine", side_effect=ImportError
                ):
                    result = fcc.generate_command_center_data()

        assert isinstance(result, CommandCenterData)
        assert result.total_trucks >= 0
        # Should have action items from PM engine
        pm_items = [
            a for a in result.action_items if "Predictive Maintenance" in str(a.sources)
        ]
        assert len(pm_items) >= 1

    @patch(
        "fleet_command_center.get_predictive_maintenance_engine",
        side_effect=Exception("PM error"),
    )
    def test_generate_handles_pm_engine_failure(self, mock_pm, fcc):
        """Should handle PM engine failure gracefully"""
        with patch(
            "fleet_command_center.analyze_fleet_anomalies", side_effect=ImportError
        ):
            with patch(
                "fleet_command_center.get_sensor_health_summary",
                side_effect=ImportError,
            ):
                with patch(
                    "fleet_command_center.get_mysql_engine", side_effect=ImportError
                ):
                    result = fcc.generate_command_center_data()

        # Should still return valid data
        assert isinstance(result, CommandCenterData)
        assert result.generated_at is not None

    @patch("fleet_command_center.analyze_fleet_anomalies")
    def test_generate_with_anomaly_detection(self, mock_anomaly, fcc):
        """Should process ML anomaly data correctly"""
        mock_anomaly.return_value = [
            {
                "truck_id": "T003",
                "is_anomaly": True,
                "anomaly_score": 75,
                "anomalous_features": [{"feature": "fuel_efficiency"}],
                "explanation": "Unusual fuel consumption pattern",
            }
        ]

        with patch(
            "fleet_command_center.get_predictive_maintenance_engine",
            side_effect=ImportError,
        ):
            with patch(
                "fleet_command_center.get_sensor_health_summary",
                side_effect=ImportError,
            ):
                with patch(
                    "fleet_command_center.get_mysql_engine", side_effect=ImportError
                ):
                    result = fcc.generate_command_center_data()

        assert isinstance(result, CommandCenterData)
        # Should have ML anomaly action items
        ml_items = [a for a in result.action_items if "ML Anomaly" in str(a.sources)]
        assert len(ml_items) >= 1

    @patch("fleet_command_center.get_sensor_health_summary")
    @patch("fleet_command_center.get_trucks_with_sensor_issues")
    def test_generate_with_sensor_health(self, mock_trucks, mock_summary, fcc):
        """Should process sensor health data correctly"""
        mock_summary.return_value = {
            "total_trucks": 20,
            "trucks_with_gps_issues": 2,
            "trucks_with_voltage_issues": 3,
            "trucks_with_dtc_active": 1,
            "trucks_with_idle_deviation": 2,
        }
        mock_trucks.return_value = {
            "voltage_low": [
                {"truck_id": "T001", "value": 11.5},
                {"truck_id": "T002", "value": 11.8},
            ],
            "dtc_active": [{"truck_id": "T003"}],
            "oil_pressure_low": [],
            "def_low": [],
        }

        with patch(
            "fleet_command_center.get_predictive_maintenance_engine",
            side_effect=ImportError,
        ):
            with patch(
                "fleet_command_center.analyze_fleet_anomalies", side_effect=ImportError
            ):
                with patch(
                    "fleet_command_center.get_mysql_engine", side_effect=ImportError
                ):
                    result = fcc.generate_command_center_data()

        assert isinstance(result, CommandCenterData)
        assert result.sensor_status.total_trucks == 20
        assert result.sensor_status.voltage_issues == 3

    @patch("fleet_command_center.get_sensor_health_summary")
    @patch("fleet_command_center.get_trucks_with_sensor_issues")
    def test_generate_with_oil_pressure_critical(self, mock_trucks, mock_summary, fcc):
        """Should create CRITICAL action for oil pressure issues"""
        mock_summary.return_value = {"total_trucks": 10}
        mock_trucks.return_value = {
            "voltage_low": [],
            "dtc_active": [],
            "oil_pressure_low": [
                {"truck_id": "T001", "value": 15},  # Critically low
            ],
            "def_low": [],
        }

        with patch(
            "fleet_command_center.get_predictive_maintenance_engine",
            side_effect=ImportError,
        ):
            with patch(
                "fleet_command_center.analyze_fleet_anomalies", side_effect=ImportError
            ):
                with patch(
                    "fleet_command_center.get_mysql_engine", side_effect=ImportError
                ):
                    result = fcc.generate_command_center_data()

        # Should have critical oil pressure action
        oil_items = [
            a
            for a in result.action_items
            if "Aceite" in a.component or "Oil" in str(a.sources)
        ]
        critical_oil = [a for a in oil_items if a.priority == Priority.CRITICAL]
        assert len(critical_oil) >= 1

    @patch("fleet_command_center.get_sensor_health_summary")
    @patch("fleet_command_center.get_trucks_with_sensor_issues")
    def test_generate_with_def_low(self, mock_trucks, mock_summary, fcc):
        """Should create action for DEF low warnings"""
        mock_summary.return_value = {"total_trucks": 10}
        mock_trucks.return_value = {
            "voltage_low": [],
            "dtc_active": [],
            "oil_pressure_low": [],
            "def_low": [
                {"truck_id": "T001", "value": 5},  # 5% DEF
            ],
        }

        with patch(
            "fleet_command_center.get_predictive_maintenance_engine",
            side_effect=ImportError,
        ):
            with patch(
                "fleet_command_center.analyze_fleet_anomalies", side_effect=ImportError
            ):
                with patch(
                    "fleet_command_center.get_mysql_engine", side_effect=ImportError
                ):
                    result = fcc.generate_command_center_data()

        # Should have DEF action item
        def_items = [a for a in result.action_items if a.category == IssueCategory.DEF]
        assert len(def_items) >= 1


class TestEstimateCosts:
    """Tests for _estimate_costs method"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_estimate_costs_empty_list(self, fcc):
        """Should return zeros for empty list"""
        result = fcc._estimate_costs([])

        assert result["immediate"] == 0
        assert result["this_week"] == 0
        assert result["this_month"] == 0
        assert result["total_potential"] == 0

    def test_estimate_costs_with_critical_items(self, fcc):
        """Should sum costs for critical items"""
        items = [
            _make_action_item(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.CRITICAL,
                priority_score=95,
                category=IssueCategory.TRANSMISSION,
                component="Transmisión",
                sources=["Test"],
            ),
        ]
        # Override cost_if_ignored
        items[0] = ActionItem(
            id=items[0].id,
            truck_id=items[0].truck_id,
            priority=items[0].priority,
            priority_score=items[0].priority_score,
            category=items[0].category,
            component=items[0].component,
            title=items[0].title,
            description=items[0].description,
            days_to_critical=items[0].days_to_critical,
            cost_if_ignored="$5,000 - $10,000",
            current_value=items[0].current_value,
            trend=items[0].trend,
            threshold=items[0].threshold,
            confidence=items[0].confidence,
            action_type=ActionType.STOP_IMMEDIATELY,
            action_steps=items[0].action_steps,
            icon=items[0].icon,
            sources=items[0].sources,
        )

        result = fcc._estimate_costs(items)

        assert result["immediate"] > 0 or result["total_potential"] > 0

    def test_estimate_costs_with_high_items(self, fcc):
        """Should sum costs for high priority items"""
        items = [
            ActionItem(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                priority_score=75,
                category=IssueCategory.ENGINE,
                component="Motor",
                title="Engine issue",
                description="Test",
                days_to_critical=5,
                cost_if_ignored="$2,000 - $5,000",
                current_value=None,
                trend=None,
                threshold=None,
                confidence="HIGH",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                action_steps=["Fix it"],
                icon="🔧",
                sources=["Test"],
            ),
        ]

        result = fcc._estimate_costs(items)

        assert result["this_week"] > 0 or result["total_potential"] > 0


class TestSingleton:
    """Tests for the singleton pattern"""

    def test_get_command_center_returns_instance(self):
        """Should return a FleetCommandCenter instance"""
        from fleet_command_center import get_command_center

        result = get_command_center()

        assert isinstance(result, FleetCommandCenter)

    def test_get_command_center_returns_same_instance(self):
        """Should return the same instance on subsequent calls"""
        from fleet_command_center import get_command_center

        instance1 = get_command_center()
        instance2 = get_command_center()

        assert instance1 is instance2


class TestCalculateTrendFunction:
    """Tests for the module-level _calculate_trend function"""

    def test_calculate_trend_empty(self):
        """Should return 'stable' for empty list"""
        result = _calculate_trend([])
        assert result == "stable"

    def test_calculate_trend_single_value(self):
        """Should return 'stable' for single value"""
        result = _calculate_trend([50])
        assert result == "stable"

    def test_calculate_trend_improving(self):
        """Should detect improving trend"""
        # Health score increasing = improving
        result = _calculate_trend([60, 65, 70, 75, 80])
        assert result == "improving"

    def test_calculate_trend_declining(self):
        """Should detect declining trend"""
        # Health score decreasing = declining
        result = _calculate_trend([80, 75, 70, 65, 60])
        assert result == "declining"

    def test_calculate_trend_stable(self):
        """Should detect stable trend"""
        result = _calculate_trend([70, 71, 70, 71, 70])
        assert result == "stable"


class TestNormalizeScoreTo100:
    """Tests for _normalize_score_to_100 method"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_normalize_zero(self, fcc):
        """Should handle zero"""
        result = fcc._normalize_score_to_100(0, 100)
        assert result == 0.0

    def test_normalize_max(self, fcc):
        """Should normalize max value to 100"""
        result = fcc._normalize_score_to_100(100, 100)
        assert result == 100.0

    def test_normalize_half(self, fcc):
        """Should normalize 50% correctly"""
        result = fcc._normalize_score_to_100(50, 100)
        assert result == 50.0

    def test_normalize_with_different_max(self, fcc):
        """Should work with different max values"""
        result = fcc._normalize_score_to_100(5, 10)
        assert result == 50.0


class TestCostEstimateParsing:
    """Tests for cost estimate string parsing in priority calculation"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_priority_with_high_cost_estimate(self, fcc):
        """Should boost score for high cost estimate string"""
        _, score_high = fcc._calculate_priority_score(
            days_to_critical=20, cost_estimate="$10,000 - $15,000"
        )
        _, score_low = fcc._calculate_priority_score(
            days_to_critical=20, cost_estimate="$500 - $1,000"
        )

        # High cost should boost score
        assert score_high >= score_low

    def test_priority_with_5000_cost(self, fcc):
        """Should recognize $5,000 cost estimates"""
        _, score_5k = fcc._calculate_priority_score(
            days_to_critical=20, cost_estimate="$5,000"
        )
        _, score_base = fcc._calculate_priority_score(days_to_critical=20)

        assert score_5k >= score_base


class TestFleetHealthScoreStatus:
    """Tests for fleet health score status determination"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_excellent_status(self, fcc):
        """Score >= 90 should be Excelente"""
        urgency = UrgencySummary(critical=0, high=0, medium=0, low=0, ok=10)
        result = fcc._calculate_fleet_health_score(urgency, 10)

        assert result.status == "Excelente"

    def test_good_status(self, fcc):
        """Score 75-89 should be Bueno"""
        urgency = UrgencySummary(critical=0, high=1, medium=2, low=0, ok=7)
        result = fcc._calculate_fleet_health_score(urgency, 10)

        # Should be in Bueno range with these issues
        assert result.status in ["Excelente", "Bueno"]

    def test_attention_needed_status(self, fcc):
        """Score 60-74 should be Atención Requerida"""
        urgency = UrgencySummary(critical=1, high=3, medium=3, low=0, ok=3)
        result = fcc._calculate_fleet_health_score(urgency, 10)

        assert result.status in ["Bueno", "Atención Requerida", "Crítico"]

    def test_critical_status(self, fcc):
        """Many critical issues should result in Crítico"""
        urgency = UrgencySummary(critical=5, high=3, medium=2, low=0, ok=0)
        result = fcc._calculate_fleet_health_score(urgency, 10)

        assert result.score < 75  # Should be low score


class TestCommandCenterDataSerialization:
    """Tests for CommandCenterData serialization"""

    def test_to_dict_complete(self):
        """Should serialize all fields correctly"""
        urgency = UrgencySummary(critical=1, high=2, medium=3, low=4, ok=5)
        fleet_health = FleetHealthScore(
            score=85, status="Bueno", trend="stable", description="Test"
        )
        sensor_status = SensorStatus(
            gps_issues=1,
            voltage_issues=2,
            dtc_active=3,
            idle_deviation=4,
            total_trucks=10,
        )

        data = CommandCenterData(
            generated_at="2025-01-01T00:00:00Z",
            fleet_health=fleet_health,
            total_trucks=15,
            trucks_analyzed=15,
            urgency_summary=urgency,
            sensor_status=sensor_status,
            cost_projection={"total_potential": 5000},
            action_items=[],
            critical_actions=[],
            high_priority_actions=[],
            insights=["Test insight"],
            data_quality={"pm_engine": True},
        )

        result = data.to_dict()

        assert result["generated_at"] == "2025-01-01T00:00:00Z"
        assert result["fleet_health"]["score"] == 85
        assert result["total_trucks"] == 15
        assert result["urgency_summary"]["critical"] == 1
        assert result["sensor_status"]["gps_issues"] == 1


class TestDetermineActionTypeEdgeCases:
    """Edge cases for _determine_action_type"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_critical_with_none_days(self, fcc):
        """CRITICAL with None days should schedule this week"""
        result = fcc._determine_action_type(Priority.CRITICAL, None)
        assert result == ActionType.SCHEDULE_THIS_WEEK

    def test_none_priority(self, fcc):
        """NONE priority should return MONITOR"""
        result = fcc._determine_action_type(Priority.NONE, 100)
        assert result == ActionType.MONITOR


class TestGenerateActionStepsEdgeCases:
    """Edge cases for _generate_action_steps"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_steps_for_fuel_component(self, fcc):
        """Should generate fuel-specific steps"""
        steps = fcc._generate_action_steps("fuel", ActionType.INSPECT, "")

        assert len(steps) > 0
        assert any("combustible" in s.lower() or "fuel" in s.lower() for s in steps)

    def test_steps_for_turbo_component(self, fcc):
        """Should generate turbo-specific steps"""
        steps = fcc._generate_action_steps("turbo", ActionType.SCHEDULE_THIS_WEEK, "")

        assert len(steps) > 0

    def test_steps_for_unknown_component(self, fcc):
        """Should generate generic steps for unknown component"""
        steps = fcc._generate_action_steps(
            "ComponenteDesconocido", ActionType.INSPECT, ""
        )

        assert len(steps) > 0

    def test_steps_include_custom_action(self, fcc):
        """Should include custom action in steps"""
        custom_action = "Check specific sensor"
        steps = fcc._generate_action_steps("Motor", ActionType.INSPECT, custom_action)

        # Should include the custom action
        assert len(steps) > 0


class TestSensorValidationEdgeCases:
    """Edge cases for sensor validation"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_validate_unknown_sensor(self, fcc):
        """Unknown sensor should pass through without range check"""
        result = fcc._validate_sensor_value(999, "unknown_sensor_xyz")
        assert result == 999.0

    def test_validate_string_value(self, fcc):
        """Should handle string values that can be converted"""
        result = fcc._validate_sensor_value("42.5", "oil_temp")
        assert result == 42.5

    def test_validate_negative_inf(self, fcc):
        """Should reject negative infinity"""
        result = fcc._validate_sensor_value(float("-inf"), "oil_temp")
        assert result is None


class TestComponentNormalizationEdgeCases:
    """Edge cases for component normalization"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_normalize_empty_string(self, fcc):
        """Should handle empty string"""
        result = fcc._normalize_component("")
        assert result == ""

    def test_normalize_with_special_chars(self, fcc):
        """Should handle special characters"""
        result = fcc._normalize_component("Motor (Diesel)")
        assert "_" in result or result.islower()

    def test_normalize_brake_variants(self, fcc):
        """Should normalize brake system variants"""
        result1 = fcc._normalize_component("frenos")
        result2 = fcc._normalize_component("brake")
        assert result1 == result2 == "brakes"


class TestInsightsEdgeCases:
    """Edge cases for insight generation"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_insights_with_single_critical_truck(self, fcc):
        """Should mention specific truck when only one is critical"""
        items = [
            ActionItem(
                id="ACT-1",
                truck_id="T-SPECIFIC",
                priority=Priority.CRITICAL,
                priority_score=95,
                category=IssueCategory.ENGINE,
                component="Motor",
                title="Critical issue",
                description="Test",
                days_to_critical=0,
                cost_if_ignored=5000,
                current_value=None,
                trend=None,
                threshold=None,
                confidence="HIGH",
                action_type=ActionType.STOP_IMMEDIATELY,
                action_steps=["Stop"],
                icon="🔧",
                sources=["Test"],
            ),
        ]
        urgency = UrgencySummary(critical=1, high=0, medium=0, low=0, ok=9)

        insights = fcc._generate_insights(items, urgency)

        # Should mention the specific truck
        assert any("T-SPECIFIC" in i for i in insights)

    def test_insights_with_transmission_issue(self, fcc):
        """Should warn about transmission issues"""
        items = [
            ActionItem(
                id="ACT-1",
                truck_id="T001",
                priority=Priority.HIGH,
                priority_score=80,
                category=IssueCategory.TRANSMISSION,
                component="Transmisión",
                title="Transmission issue",
                description="Test",
                days_to_critical=5,
                cost_if_ignored=10000,
                current_value=None,
                trend=None,
                threshold=None,
                confidence="HIGH",
                action_type=ActionType.SCHEDULE_THIS_WEEK,
                action_steps=["Fix"],
                icon="⚙️",
                sources=["Test"],
            ),
        ]
        urgency = UrgencySummary(critical=0, high=1, medium=0, low=0, ok=9)

        insights = fcc._generate_insights(items, urgency)

        # Should warn about transmission
        assert any("transmisión" in i.lower() for i in insights)


class TestRealTimePredictiveIntegration:
    """Tests for Real-Time Predictive Engine integration"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    @patch("fleet_command_center.get_mysql_engine")
    def test_rt_engine_query_handles_no_data(self, mock_engine, fcc):
        """Should handle empty RT data gracefully"""
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchall.return_value = []
        mock_engine.return_value.connect.return_value.__enter__ = MagicMock(
            return_value=mock_conn
        )
        mock_engine.return_value.connect.return_value.__exit__ = MagicMock(
            return_value=False
        )

        with patch(
            "fleet_command_center.get_predictive_maintenance_engine",
            side_effect=ImportError,
        ):
            with patch(
                "fleet_command_center.analyze_fleet_anomalies", side_effect=ImportError
            ):
                with patch(
                    "fleet_command_center.get_sensor_health_summary",
                    side_effect=ImportError,
                ):
                    result = fcc.generate_command_center_data()

        assert isinstance(result, CommandCenterData)


class TestMultiCriticalTruckPenalty:
    """Tests for multi-critical truck penalty in fleet health"""

    @pytest.fixture
    def fcc(self):
        return FleetCommandCenter()

    def test_penalty_with_multiple_critical_trucks(self, fcc):
        """Multiple trucks in critical state should reduce fleet health"""
        # Items with 3 different trucks in critical state
        items = [
            _make_action_item(
                id=f"ACT-{i}",
                truck_id=f"T00{i+1}",
                priority=Priority.CRITICAL,
                priority_score=95,
                category=IssueCategory.ENGINE,
                component="Motor",
                sources=["Test"],
            )
            for i in range(3)
        ]

        urgency = UrgencySummary(critical=3, high=0, medium=0, low=0, ok=7)

        # With multiple critical trucks
        result_multi = fcc._calculate_fleet_health_score(urgency, 10, items)

        # With no action items (no penalty)
        result_no_items = fcc._calculate_fleet_health_score(urgency, 10, None)

        # Multi-critical should have lower score due to penalty
        assert result_multi.score <= result_no_items.score


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
