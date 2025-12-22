#!/usr/bin/env python3
"""
Integration Tests for ML Models
Tests end-to-end functionality without mocking

pytest tests/test_ml_integration.py -v
"""
from datetime import datetime, timedelta

import pandas as pd
import pytest

from ml_models.lstm_maintenance import TENSORFLOW_AVAILABLE, get_maintenance_predictor
from ml_models.theft_detection import get_theft_detector


class TestLSTMIntegration:
    """Test LSTM model integration"""

    @pytest.mark.skipif(not TENSORFLOW_AVAILABLE, reason="TensorFlow not installed")
    def test_lstm_full_pipeline(self):
        """Test complete LSTM workflow"""
        # Create sample data (60 days)
        dates = pd.date_range(start="2025-11-01", periods=60, freq="D")
        df = pd.DataFrame(
            {
                "timestamp_utc": dates,
                "oil_pressure": [45.0 + i * 0.1 for i in range(60)],
                "oil_temp": [200.0 + i * 0.2 for i in range(60)],
                "coolant_temp": [190.0 + i * 0.1 for i in range(60)],
                "engine_load": [60.0 + i * 0.15 for i in range(60)],
                "rpm": [1500 + i * 2 for i in range(60)],
            }
        )

        # Get predictor
        predictor = get_maintenance_predictor()

        # Predict (should work even without trained model)
        result = predictor.predict_truck(df)

        # Validate result
        assert "maintenance_7d_prob" in result
        assert "maintenance_14d_prob" in result
        assert "maintenance_30d_prob" in result
        assert "recommended_action" in result
        assert "confidence" in result

        # Probabilities should be 0-1
        assert 0 <= result["maintenance_7d_prob"] <= 1
        assert 0 <= result["maintenance_14d_prob"] <= 1
        assert 0 <= result["maintenance_30d_prob"] <= 1


class TestTheftDetectionIntegration:
    """Test Isolation Forest integration"""

    def test_theft_detection_full_pipeline(self):
        """Test complete theft detection workflow"""
        # Create training data
        dates = pd.date_range(start="2025-01-01", periods=100, freq="6H")
        df = pd.DataFrame(
            {
                "fuel_drop_gal": [10.0 + i * 0.5 for i in range(100)],
                "timestamp_utc": dates,
                "duration_minutes": [10] * 100,
                "sat_count": [12] * 100,
                "hdop": [1.0] * 100,
                "latitude": [34.05] * 100,
                "longitude": [-118.25] * 100,
                "truck_status": ["STOPPED"] * 100,
                "speed_mph": [0] * 100,
            }
        )

        # Get detector
        detector = get_theft_detector()

        # Train
        stats = detector.train(df)

        # Validate training stats
        assert stats["total_samples"] == 100
        assert stats["detected_anomalies"] > 0
        assert stats["normal_events"] > 0
        assert 0 < stats["anomaly_rate"] < 1

        # Test prediction - normal event
        normal_event = {
            "fuel_drop_gal": 12.0,
            "timestamp_utc": "2025-12-22 14:00:00",
            "duration_minutes": 10,
            "sat_count": 12,
            "hdop": 1.0,
            "latitude": 34.05,
            "longitude": -118.25,
            "truck_status": "STOPPED",
            "speed_mph": 0,
        }

        result = detector.predict_single(normal_event)

        # Validate result
        assert "is_theft" in result
        assert "confidence" in result
        assert "anomaly_score" in result
        assert "risk_level" in result
        assert "explanation" in result

        assert 0 <= result["confidence"] <= 1
        assert result["risk_level"] in ["low", "medium", "high", "critical"]


class TestModelPersistence:
    """Test model save/load functionality"""

    @pytest.mark.skipif(not TENSORFLOW_AVAILABLE, reason="TensorFlow not installed")
    def test_lstm_persistence(self, tmp_path):
        """Test LSTM model can be saved and loaded"""
        # Get predictor
        predictor = get_maintenance_predictor()

        # Build model
        model = predictor.build_model()
        assert model is not None

        # Set custom paths
        model_path = tmp_path / "test_lstm.h5"
        predictor.model_path = str(model_path)

        # Save
        predictor.model = model
        predictor.save_model()

        assert model_path.exists()

        # Load
        new_predictor = get_maintenance_predictor()
        new_predictor.model_path = str(model_path)
        loaded = new_predictor.load_model()

        assert loaded == True
        assert new_predictor.model is not None

    def test_theft_detector_persistence(self, tmp_path):
        """Test theft detector can be saved and loaded"""
        # Get detector
        detector = get_theft_detector()

        # Create minimal training data
        df = pd.DataFrame(
            {
                "fuel_drop_gal": [10, 15, 20],
                "timestamp_utc": pd.date_range(start="2025-01-01", periods=3, freq="D"),
                "duration_minutes": [10, 10, 10],
                "sat_count": [12, 12, 12],
                "hdop": [1.0, 1.0, 1.0],
            }
        )

        # Train
        detector.train(df)

        # Set custom paths
        model_path = tmp_path / "test_isolation_forest.pkl"
        scaler_path = tmp_path / "test_scaler.pkl"
        detector.model_path = str(model_path)
        detector.scaler_path = str(scaler_path)

        # Save
        detector.save_model()

        assert model_path.exists()
        assert scaler_path.exists()

        # Load
        new_detector = get_theft_detector()
        new_detector.model_path = str(model_path)
        new_detector.scaler_path = str(scaler_path)
        loaded = new_detector.load_model()

        assert loaded == True
        assert new_detector.model is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
