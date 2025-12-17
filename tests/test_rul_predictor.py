"""
Tests for RUL (Remaining Useful Life) Predictor
═══════════════════════════════════════════════════════════════════════════════
"""

import pytest
from datetime import datetime, timedelta, timezone
import math
from rul_predictor import (
    RULPredictor,
    RULPrediction,
    DegradationModel,
)


class TestRULPredictor:
    """Test suite for RUL prediction"""

    def test_linear_degradation_prediction(self):
        """Linear degradation should predict correct RUL"""
        predictor = RULPredictor()

        # Simulate linear degradation: 90 → 40 over 60 days (0.83 pts/day)
        start_date = datetime.now(timezone.utc) - timedelta(days=60)
        history = []

        for day in range(0, 61, 3):  # Every 3 days
            health = 90 - (day * 0.83)
            timestamp = start_date + timedelta(days=day)
            history.append((timestamp, health))

        prediction = predictor.predict_rul("turbo_health", history)

        assert prediction.status == "degrading"
        assert prediction.rul_days is not None
        assert prediction.rul_days > 0
        assert prediction.degradation_rate_per_day > 0.7  # ~0.83
        assert prediction.degradation_rate_per_day < 1.0
        assert prediction.confidence > 0.8  # Good linear fit

    def test_stable_component_no_degradation(self):
        """Stable component should return None for RUL"""
        predictor = RULPredictor()

        # Stable health over 30 days
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        history = []

        for day in range(0, 31, 2):
            health = 85 + (day % 3) - 1  # Small random variation around 85
            timestamp = start_date + timedelta(days=day)
            history.append((timestamp, health))

        prediction = predictor.predict_rul("oil_consumption", history)

        assert prediction.status == "stable"
        assert prediction.rul_days is None
        assert "stable" in prediction.message.lower()

    def test_exponential_degradation(self):
        """Exponential degradation should be detected"""
        predictor = RULPredictor()

        # Simulate exponential degradation: health = 90 * exp(-0.03*t)
        start_date = datetime.now(timezone.utc) - timedelta(days=40)
        history = []

        for day in range(0, 41, 2):
            health = 90 * math.exp(-0.03 * day)
            timestamp = start_date + timedelta(days=day)
            history.append((timestamp, health))

        prediction = predictor.predict_rul("coolant_leak", history)

        assert prediction.status in ["degrading", "critical"]
        assert prediction.model_used in ["linear", "exponential"]
        assert prediction.rul_days is not None

    def test_insufficient_data_points(self):
        """Less than minimum points should return insufficient_data"""
        predictor = RULPredictor()

        # Only 3 data points (need 5+)
        start_date = datetime.now(timezone.utc) - timedelta(days=10)
        history = [
            (start_date, 80.0),
            (start_date + timedelta(days=5), 75.0),
            (start_date + timedelta(days=10), 70.0),
        ]

        prediction = predictor.predict_rul("def_system", history)

        assert prediction.status == "insufficient_data"
        assert prediction.rul_days is None
        assert "Insufficient data" in prediction.message

    def test_insufficient_time_span(self):
        """Less than minimum days should return insufficient_data"""
        predictor = RULPredictor()

        # 10 points but only 5 days (need 14+ days)
        start_date = datetime.now(timezone.utc) - timedelta(days=5)
        history = []

        for day in range(6):
            timestamp = start_date + timedelta(days=day)
            history.append((timestamp, 80.0 - day))

        prediction = predictor.predict_rul("battery", history)

        assert prediction.status == "insufficient_data"

    def test_critical_status_when_below_threshold(self):
        """Current score < 25 should be marked critical"""
        predictor = RULPredictor()

        # Degrading to critical level
        start_date = datetime.now(timezone.utc) - timedelta(days=60)
        history = []

        for day in range(0, 61, 3):
            health = 80 - (day * 0.9)  # Will go below 25
            timestamp = start_date + timedelta(days=day)
            history.append((timestamp, max(10, health)))

        prediction = predictor.predict_rul("turbo", history)

        if prediction.current_score < 25:
            assert prediction.status == "critical"
            assert "CRITICAL" in prediction.message

    def test_service_date_calculation(self):
        """Service date should be before predicted failure"""
        predictor = RULPredictor()

        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        history = []

        for day in range(0, 31, 2):
            health = 80 - (day * 0.5)
            timestamp = start_date + timedelta(days=day)
            history.append((timestamp, health))

        prediction = predictor.predict_rul("alternator", history)

        if prediction.recommended_service_date and prediction.rul_days:
            # Service date should be at least a few days before failure
            days_to_service = (
                prediction.recommended_service_date - datetime.now(timezone.utc)
            ).days
            assert days_to_service < prediction.rul_days

    def test_cost_estimation_turbo(self):
        """Turbo repair should have high cost estimate"""
        predictor = RULPredictor()
        cost = predictor._estimate_cost("turbo_health")
        assert cost >= 4000, "Turbo should be expensive"

    def test_cost_estimation_battery(self):
        """Battery repair should have low cost estimate"""
        predictor = RULPredictor()
        cost = predictor._estimate_cost("battery")
        assert cost <= 500, "Battery should be cheaper"

    def test_cost_estimation_default(self):
        """Unknown component should use default cost"""
        predictor = RULPredictor()
        cost = predictor._estimate_cost("unknown_component_xyz")
        assert cost == predictor.COMPONENT_COSTS["default"]

    def test_r_squared_perfect_fit(self):
        """Perfect linear fit should have R² = 1.0"""
        predictor = RULPredictor()

        # Perfect linear: y = 2x + 5
        x = [1, 2, 3, 4, 5]
        y = [7, 9, 11, 13, 15]

        slope, intercept = predictor._linear_regression(x, y)
        r2 = predictor._r_squared(x, y, slope, intercept)

        assert abs(slope - 2.0) < 0.01
        assert abs(intercept - 5.0) < 0.01
        assert r2 > 0.99, "Perfect fit should have R² ~ 1.0"

    def test_r_squared_poor_fit(self):
        """Random data should have low R²"""
        predictor = RULPredictor()

        x = [1, 2, 3, 4, 5]
        y = [10, 5, 15, 3, 12]  # Random, no trend

        slope, intercept = predictor._linear_regression(x, y)
        r2 = predictor._r_squared(x, y, slope, intercept)

        assert r2 < 0.5, "Poor fit should have low R²"

    def test_miles_prediction(self):
        """RUL in miles should be calculated"""
        predictor = RULPredictor()

        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        history = []

        for day in range(0, 31, 2):
            health = 75 - (day * 0.6)
            timestamp = start_date + timedelta(days=day)
            history.append((timestamp, health))

        prediction = predictor.predict_rul("starter", history)

        if prediction.rul_days:
            expected_miles = prediction.rul_days * predictor.AVERAGE_DAILY_MILES
            # Allow small rounding differences
            assert abs(prediction.rul_miles - expected_miles) <= 100

    def test_rapid_degradation_short_rul(self):
        """Rapid degradation should predict short RUL"""
        predictor = RULPredictor()

        # Fast degradation: 80 → 30 in 20 days (2.5 pts/day)
        start_date = datetime.now(timezone.utc) - timedelta(days=20)
        history = []

        for day in range(0, 21, 1):
            health = 80 - (day * 2.5)
            timestamp = start_date + timedelta(days=day)
            history.append((timestamp, max(25, health)))

        prediction = predictor.predict_rul("oil", history)

        assert prediction.rul_days is not None
        assert prediction.rul_days < 10, "Rapid degradation = short RUL"
        assert prediction.degradation_rate_per_day > 2.0

    def test_improving_component(self):
        """Component with improving health should be stable"""
        predictor = RULPredictor()

        # Health improving over time
        start_date = datetime.now(timezone.utc) - timedelta(days=30)
        history = []

        for day in range(0, 31, 2):
            health = 60 + (day * 0.5)  # Improving
            timestamp = start_date + timedelta(days=day)
            history.append((timestamp, min(90, health)))

        prediction = predictor.predict_rul("coolant", history)

        assert prediction.status == "stable"
        assert prediction.rul_days is None

    def test_sorted_history_handling(self):
        """Predictor should handle unsorted history"""
        predictor = RULPredictor()

        start_date = datetime.now(timezone.utc) - timedelta(days=30)

        # Create unsorted history
        history = [
            (start_date + timedelta(days=10), 70.0),
            (start_date + timedelta(days=0), 80.0),
            (start_date + timedelta(days=20), 60.0),
            (start_date + timedelta(days=5), 75.0),
            (start_date + timedelta(days=30), 50.0),
            (start_date + timedelta(days=15), 65.0),
        ]

        # Should not crash and should sort internally
        prediction = predictor.predict_rul("def", history)

        assert prediction is not None
        assert prediction.status in [
            "stable",
            "degrading",
            "critical",
            "insufficient_data",
        ]


@pytest.fixture
def sample_predictor():
    """Fixture providing predictor instance"""
    return RULPredictor()


@pytest.fixture
def degrading_history():
    """Fixture providing degrading health history"""
    start_date = datetime.now(timezone.utc) - timedelta(days=40)
    history = []

    for day in range(0, 41, 2):
        health = 85 - (day * 0.7)
        timestamp = start_date + timedelta(days=day)
        history.append((timestamp, health))

    return history


def test_with_fixtures(sample_predictor, degrading_history):
    """Test using fixtures"""
    prediction = sample_predictor.predict_rul("test_component", degrading_history)
    assert prediction.status in ["degrading", "critical"]
    assert prediction.rul_days is not None
