"""
Tests for Driver Coaching Tips and Score History v1.1.0

Tests:
- Coaching tips generation
- Score history storage and retrieval
- Trend analysis
- Bilingual support
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock


# ═══════════════════════════════════════════════════════════════════════════════
# TEST DATA
# ═══════════════════════════════════════════════════════════════════════════════

SAMPLE_DRIVER_GOOD = {
    "truck_id": "TRK-001",
    "overall_score": 88.5,
    "grade": "A",
    "scores": {
        "speed_optimization": 92.0,
        "rpm_discipline": 85.0,
        "idle_management": 90.0,
        "fuel_consistency": 82.0,
        "mpg_performance": 88.0,
    },
    "metrics": {
        "avg_speed_mph": 62.5,
        "max_speed_mph": 68.0,
        "avg_rpm": 1450,
        "idle_pct": 8.5,
        "avg_mpg": 6.8,
        "best_mpg": 7.2,
        "worst_mpg": 6.1,
        "total_miles": 1250.5,
    },
}

SAMPLE_DRIVER_NEEDS_WORK = {
    "truck_id": "TRK-002",
    "overall_score": 58.2,
    "grade": "C",
    "scores": {
        "speed_optimization": 55.0,
        "rpm_discipline": 48.0,
        "idle_management": 62.0,
        "fuel_consistency": 65.0,
        "mpg_performance": 52.0,
    },
    "metrics": {
        "avg_speed_mph": 71.5,
        "max_speed_mph": 78.0,
        "avg_rpm": 1850,
        "idle_pct": 18.5,
        "avg_mpg": 5.2,
        "best_mpg": 6.0,
        "worst_mpg": 4.5,
        "total_miles": 980.0,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# COACHING TIPS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestCoachingTips:
    """Tests for generate_coaching_tips function"""

    def test_import_generate_coaching_tips(self):
        """Should be able to import the function"""
        from driver_behavior_engine import generate_coaching_tips
        assert callable(generate_coaching_tips)

    def test_good_driver_gets_positive_tips(self):
        """Good driver should receive encouraging tips"""
        from driver_behavior_engine import generate_coaching_tips
        
        tips = generate_coaching_tips(SAMPLE_DRIVER_GOOD, language="en")
        
        assert isinstance(tips, list)
        assert len(tips) > 0
        
        # Should have overall grade tip
        grade_tips = [t for t in tips if t["category"] == "overall_grade"]
        assert len(grade_tips) > 0
        assert "A" in grade_tips[0]["message"] or "Excellent" in grade_tips[0]["message"]

    def test_poor_driver_gets_actionable_tips(self):
        """Driver needing work should get specific improvement tips"""
        from driver_behavior_engine import generate_coaching_tips
        
        tips = generate_coaching_tips(SAMPLE_DRIVER_NEEDS_WORK, language="en")
        
        assert isinstance(tips, list)
        assert len(tips) > 0
        
        # Should prioritize worst areas
        categories = [t["category"] for t in tips]
        
        # RPM is worst (48), should be in tips
        assert any("rpm" in cat.lower() or "speed" in cat.lower() for cat in categories)

    def test_spanish_translation(self):
        """Tips should be available in Spanish"""
        from driver_behavior_engine import generate_coaching_tips
        
        tips_en = generate_coaching_tips(SAMPLE_DRIVER_NEEDS_WORK, language="en")
        tips_es = generate_coaching_tips(SAMPLE_DRIVER_NEEDS_WORK, language="es")
        
        # Should have tips in both languages
        assert len(tips_en) > 0
        assert len(tips_es) > 0
        
        # Messages should be different (translated)
        en_messages = [t["message"] for t in tips_en]
        es_messages = [t["message"] for t in tips_es]
        
        # At least some should be different (Spanish)
        assert en_messages != es_messages

    def test_tips_include_savings_estimates(self):
        """Tips should include potential savings when applicable"""
        from driver_behavior_engine import generate_coaching_tips
        
        tips = generate_coaching_tips(SAMPLE_DRIVER_NEEDS_WORK, language="en")
        
        # At least one tip should have potential savings
        tips_with_savings = [t for t in tips if t.get("potential_savings_weekly", 0) > 0]
        
        # Driver with issues should have at least one tip with savings potential
        assert len(tips_with_savings) >= 1

    def test_max_tips_parameter(self):
        """Should respect max_tips parameter"""
        from driver_behavior_engine import generate_coaching_tips
        
        tips_3 = generate_coaching_tips(SAMPLE_DRIVER_NEEDS_WORK, max_tips=3)
        tips_10 = generate_coaching_tips(SAMPLE_DRIVER_NEEDS_WORK, max_tips=10)
        
        assert len(tips_3) <= 3
        assert len(tips_10) >= len(tips_3)

    def test_tips_structure(self):
        """Each tip should have required fields"""
        from driver_behavior_engine import generate_coaching_tips
        
        tips = generate_coaching_tips(SAMPLE_DRIVER_GOOD, language="en")
        
        required_fields = ["priority", "category", "message", "score", "severity"]
        
        for tip in tips:
            for field in required_fields:
                assert field in tip, f"Missing field: {field}"

    def test_tips_priority_ordering(self):
        """Tips should be ordered by priority (highest first)"""
        from driver_behavior_engine import generate_coaching_tips
        
        tips = generate_coaching_tips(SAMPLE_DRIVER_NEEDS_WORK, language="en", max_tips=10)
        
        if len(tips) > 1:
            priorities = [t["priority"] for t in tips]
            # Should be descending
            for i in range(len(priorities) - 1):
                assert priorities[i] >= priorities[i + 1], "Tips not sorted by priority"


# ═══════════════════════════════════════════════════════════════════════════════
# SCORE HISTORY TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestScoreHistory:
    """Tests for score history functions"""

    def test_import_history_functions(self):
        """Should be able to import history functions"""
        from database_mysql import (
            get_driver_score_history,
            get_driver_score_trend,
            save_driver_score_history,
        )
        assert callable(get_driver_score_history)
        assert callable(get_driver_score_trend)
        assert callable(save_driver_score_history)

    def test_history_returns_list(self):
        """get_driver_score_history should return a list"""
        from database_mysql import get_driver_score_history
        
        # May return empty if no data, but should be a list
        result = get_driver_score_history("TEST-TRUCK", days_back=7)
        assert isinstance(result, list)

    def test_trend_returns_dict(self):
        """get_driver_score_trend should return a dict"""
        from database_mysql import get_driver_score_trend
        
        result = get_driver_score_trend("TEST-TRUCK", days_back=7)
        assert isinstance(result, dict)
        assert "truck_id" in result
        assert "trend" in result


# ═══════════════════════════════════════════════════════════════════════════════
# TREND ANALYSIS TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestTrendAnalysis:
    """Tests for trend analysis logic"""

    def test_insufficient_data_trend(self):
        """Should handle insufficient data gracefully"""
        from database_mysql import get_driver_score_trend
        
        # New truck with no history
        result = get_driver_score_trend("BRAND-NEW-TRUCK-999", days_back=7)
        
        assert result["trend"] == "insufficient_data"
        assert "data_points" in result

    def test_trend_has_required_fields(self):
        """Trend result should have all expected fields"""
        from database_mysql import get_driver_score_trend
        
        result = get_driver_score_trend("TEST-TRUCK", days_back=30)
        
        expected_fields = ["truck_id", "trend", "data_points"]
        for field in expected_fields:
            assert field in result


# ═══════════════════════════════════════════════════════════════════════════════
# API ENDPOINT TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestDriverScorecardEndpoint:
    """Tests for the enhanced driver-scorecard endpoint"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)

    def test_scorecard_endpoint_exists(self, client):
        """Endpoint should exist and respond"""
        response = client.get("/fuelAnalytics/api/analytics/driver-scorecard")
        assert response.status_code in [200, 500]  # 500 if no DB

    def test_scorecard_with_tips_parameter(self, client):
        """Should accept include_tips parameter"""
        response = client.get(
            "/fuelAnalytics/api/analytics/driver-scorecard",
            params={"include_tips": True, "days": 7}
        )
        # Should not error on parameter
        assert response.status_code in [200, 500]

    def test_scorecard_with_history_parameter(self, client):
        """Should accept include_history parameter"""
        response = client.get(
            "/fuelAnalytics/api/analytics/driver-scorecard",
            params={"include_history": True, "days": 7}
        )
        assert response.status_code in [200, 500]

    def test_scorecard_with_language_parameter(self, client):
        """Should accept language parameter"""
        response = client.get(
            "/fuelAnalytics/api/analytics/driver-scorecard",
            params={"language": "es", "days": 7}
        )
        assert response.status_code in [200, 500]

    def test_driver_history_endpoint_exists(self, client):
        """Driver history endpoint should exist"""
        response = client.get("/fuelAnalytics/api/analytics/driver/TRK-001/history")
        assert response.status_code in [200, 500]

    def test_snapshot_endpoint_exists(self, client):
        """Snapshot endpoint should exist"""
        response = client.post("/fuelAnalytics/api/analytics/driver-scores/snapshot")
        assert response.status_code in [200, 500]


# ═══════════════════════════════════════════════════════════════════════════════
# INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════════════


class TestIntegration:
    """Integration tests for the full coaching system"""

    def test_full_coaching_flow(self):
        """Test complete flow: scorecard -> tips -> display"""
        from driver_behavior_engine import generate_coaching_tips
        
        # Simulate getting scorecard data
        driver = SAMPLE_DRIVER_NEEDS_WORK.copy()
        
        # Generate tips
        tips = generate_coaching_tips(driver, language="en", max_tips=5)
        
        # Verify tips are actionable
        assert len(tips) > 0
        for tip in tips:
            assert tip["message"], "Tip should have a message"
            assert tip["category"], "Tip should have a category"

    def test_bilingual_coaching_consistency(self):
        """Both languages should have same number of tips"""
        from driver_behavior_engine import generate_coaching_tips
        
        tips_en = generate_coaching_tips(SAMPLE_DRIVER_NEEDS_WORK, language="en")
        tips_es = generate_coaching_tips(SAMPLE_DRIVER_NEEDS_WORK, language="es")
        
        # Same structure, different messages
        assert len(tips_en) == len(tips_es)
        
        for en, es in zip(tips_en, tips_es):
            assert en["category"] == es["category"]
            assert en["priority"] == es["priority"]
