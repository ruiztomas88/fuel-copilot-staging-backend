"""
Unit tests for Anomaly Detector
Tests with mocked database connections
"""

from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from anomaly_detector import AnomalyDetection, AnomalyDetector, get_anomaly_detector


class TestAnomalyDetection:
    """Test AnomalyDetection dataclass"""

    def test_anomaly_creation(self):
        """Test creating anomaly detection"""
        anomaly = AnomalyDetection(
            truck_id="RA9250",
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            anomaly_type="fuel_theft",
            severity="HIGH",
            anomaly_score=-0.25,
            features={"mpg": 5.5, "fuel_level_pct": 45.2},
            description="Test anomaly",
        )

        assert anomaly.truck_id == "RA9250"
        assert anomaly.anomaly_type == "fuel_theft"
        assert anomaly.severity == "HIGH"
        assert anomaly.anomaly_score == -0.25

    def test_anomaly_to_dict(self):
        """Test converting anomaly to dictionary"""
        anomaly = AnomalyDetection(
            truck_id="RA9250",
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            anomaly_type="unusual_consumption",
            severity="MEDIUM",
            anomaly_score=-0.15,
            features={"mpg": 5.5, "fuel_level_pct": 45.2},
            description="Test anomaly",
        )

        result = anomaly.to_dict()

        assert result["truck_id"] == "RA9250"
        assert result["anomaly_type"] == "unusual_consumption"
        assert result["severity"] == "MEDIUM"
        assert result["anomaly_score"] == -0.15
        assert "mpg" in result["features"]


class TestAnomalyDetector:
    """Test AnomalyDetector class"""

    @pytest.fixture
    def mock_db(self):
        """Create mock database"""
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        db.cursor.return_value.__exit__.return_value = False
        return db, cursor

    @pytest.fixture
    def detector(self, mock_db):
        """Create detector with mock DB"""
        db, _ = mock_db
        return AnomalyDetector(db_connection=db)

    def test_detector_initialization(self, detector):
        """Test detector initialization"""
        assert detector.contamination == 0.05
        assert detector.n_estimators == 100
        assert detector.random_state == 42
        assert isinstance(detector.models, dict)
        assert isinstance(detector.scalers, dict)

    def test_extract_features_success(self, detector, mock_db):
        """Test extracting features successfully"""
        db, cursor = mock_db

        # Mock data
        cursor.fetchall.return_value = [
            {
                "mpg_current": 6.5,
                "fuel_level_pct": 75.0,
                "idle_pct": 25.0,
                "speed_avg": 45.0,
                "fuel_flow_rate": 1.5,
                "fuel_change_rate": -2.0,
            }
            for _ in range(100)
        ]

        features = detector.extract_features("RA9250", period_days=7, min_samples=50)

        assert features is not None
        assert features.shape[0] == 100  # 100 samples
        assert features.shape[1] == 6  # 6 features

    def test_extract_features_insufficient_data(self, detector, mock_db):
        """Test with insufficient data"""
        db, cursor = mock_db

        cursor.fetchall.return_value = [
            {
                "mpg_current": 6.5,
                "fuel_level_pct": 75.0,
                "idle_pct": 25.0,
                "speed_avg": 45.0,
                "fuel_flow_rate": 1.5,
                "fuel_change_rate": -2.0,
            }
            for _ in range(10)  # Only 10 samples
        ]

        features = detector.extract_features("RA9250", period_days=7, min_samples=50)

        assert features is None

    @patch("anomaly_detector.StandardScaler")
    @patch("anomaly_detector.IsolationForest")
    def test_train_model_success(self, mock_forest, mock_scaler, detector, mock_db):
        """Test training model successfully"""
        db, cursor = mock_db

        # Mock data
        cursor.fetchall.return_value = [
            {
                "mpg_current": 6.5 + i * 0.1,
                "fuel_level_pct": 75.0 - i * 0.5,
                "idle_pct": 25.0,
                "speed_avg": 45.0,
                "fuel_flow_rate": 1.5,
                "fuel_change_rate": -2.0,
            }
            for i in range(100)
        ]

        # Mock scaler and model
        scaler_instance = MagicMock()
        model_instance = MagicMock()
        mock_scaler.return_value = scaler_instance
        mock_forest.return_value = model_instance

        success = detector.train_model("RA9250", period_days=30)

        assert success is True
        assert "RA9250" in detector.models
        assert "RA9250" in detector.scalers
        scaler_instance.fit_transform.assert_called_once()
        model_instance.fit.assert_called_once()

    @patch("anomaly_detector.StandardScaler")
    @patch("anomaly_detector.IsolationForest")
    def test_train_model_insufficient_data(
        self, mock_forest, mock_scaler, detector, mock_db
    ):
        """Test training with insufficient data"""
        db, cursor = mock_db

        cursor.fetchall.return_value = []  # No data

        success = detector.train_model("RA9250", period_days=30)

        assert success is False
        assert "RA9250" not in detector.models

    def test_classify_anomaly_fuel_theft(self, detector):
        """Test classifying fuel theft"""
        features = {
            "mpg": 6.5,
            "fuel_level_pct": 50.0,
            "idle_pct": 20.0,
            "speed_avg": 2.0,  # Parked
            "fuel_flow_rate": 0.0,
            "fuel_change_rate": -15.0,  # Large drop
        }

        anomaly_type, description = detector._classify_anomaly(features)

        assert anomaly_type == "fuel_theft"
        assert "fuel drop" in description.lower()

    def test_classify_anomaly_sensor_malfunction_mpg(self, detector):
        """Test classifying sensor malfunction (impossible MPG)"""
        features = {
            "mpg": 25.0,  # Impossible for heavy truck
            "fuel_level_pct": 50.0,
            "idle_pct": 20.0,
            "speed_avg": 45.0,
            "fuel_flow_rate": 1.5,
            "fuel_change_rate": -2.0,
        }

        anomaly_type, description = detector._classify_anomaly(features)

        assert anomaly_type == "sensor_malfunction"
        assert "mpg" in description.lower()

    def test_classify_anomaly_sensor_malfunction_fuel_level(self, detector):
        """Test classifying sensor malfunction (invalid fuel level)"""
        features = {
            "mpg": 6.5,
            "fuel_level_pct": 150.0,  # Impossible
            "idle_pct": 20.0,
            "speed_avg": 45.0,
            "fuel_flow_rate": 1.5,
            "fuel_change_rate": -2.0,
        }

        anomaly_type, description = detector._classify_anomaly(features)

        assert anomaly_type == "sensor_malfunction"
        assert "fuel level" in description.lower()

    def test_classify_anomaly_unusual_consumption_low_mpg(self, detector):
        """Test classifying unusual consumption (low MPG)"""
        features = {
            "mpg": 2.5,  # Very low
            "fuel_level_pct": 50.0,
            "idle_pct": 15.0,  # Not idle-related
            "speed_avg": 45.0,
            "fuel_flow_rate": 3.0,
            "fuel_change_rate": -5.0,
        }

        anomaly_type, description = detector._classify_anomaly(features)

        assert anomaly_type == "unusual_consumption"
        assert "low mpg" in description.lower()

    def test_classify_anomaly_unusual_consumption_high_idle(self, detector):
        """Test classifying unusual consumption (high idle)"""
        features = {
            "mpg": 4.0,
            "fuel_level_pct": 50.0,
            "idle_pct": 85.0,  # Very high idle
            "speed_avg": 5.0,
            "fuel_flow_rate": 1.0,
            "fuel_change_rate": -2.0,
        }

        anomaly_type, description = detector._classify_anomaly(features)

        assert anomaly_type == "unusual_consumption"
        assert "idle" in description.lower()

    def test_determine_severity_critical(self, detector):
        """Test severity: CRITICAL"""
        severity = detector._determine_severity(-0.35)
        assert severity == "CRITICAL"

    def test_determine_severity_high(self, detector):
        """Test severity: HIGH"""
        severity = detector._determine_severity(-0.25)
        assert severity == "HIGH"

    def test_determine_severity_medium(self, detector):
        """Test severity: MEDIUM"""
        severity = detector._determine_severity(-0.15)
        assert severity == "MEDIUM"

    def test_determine_severity_low(self, detector):
        """Test severity: LOW"""
        severity = detector._determine_severity(-0.05)
        assert severity == "LOW"

    @patch("anomaly_detector.StandardScaler")
    @patch("anomaly_detector.IsolationForest")
    def test_detect_anomalies_found(self, mock_forest, mock_scaler, detector, mock_db):
        """Test detecting anomalies"""
        db, cursor = mock_db

        # Mock training data
        cursor.fetchall.side_effect = [
            # Training data
            [
                {
                    "mpg_current": 6.5,
                    "fuel_level_pct": 75.0,
                    "idle_pct": 25.0,
                    "speed_avg": 45.0,
                    "fuel_flow_rate": 1.5,
                    "fuel_change_rate": -2.0,
                }
                for _ in range(100)
            ],
            # Check period data
            [
                {
                    "mpg_current": 6.5,
                    "fuel_level_pct": 75.0,
                    "idle_pct": 25.0,
                    "speed_avg": 45.0,
                    "fuel_flow_rate": 1.5,
                    "fuel_change_rate": -2.0,
                }
                for _ in range(10)
            ],
            # Timestamps
            [{"timestamp_utc": datetime(2025, 1, 1, i, 0, 0)} for i in range(10)],
        ]

        # Mock model
        scaler_instance = MagicMock()
        scaler_instance.transform.return_value = np.zeros((10, 6))
        model_instance = MagicMock()
        model_instance.predict.return_value = np.array(
            [-1, 1, -1, 1, 1, 1, 1, 1, 1, 1]
        )  # 2 anomalies
        model_instance.decision_function.return_value = np.array(
            [-0.3, 0.1, -0.2, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1, 0.1]
        )

        mock_scaler.return_value = scaler_instance
        mock_forest.return_value = model_instance

        anomalies = detector.detect_anomalies("RA9250", check_period_days=1)

        assert len(anomalies) == 2
        assert all(isinstance(a, AnomalyDetection) for a in anomalies)
        assert anomalies[0].truck_id == "RA9250"

    def test_store_anomaly_success(self, detector, mock_db):
        """Test storing anomaly"""
        db, cursor = mock_db

        anomaly = AnomalyDetection(
            truck_id="RA9250",
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            anomaly_type="fuel_theft",
            severity="HIGH",
            anomaly_score=-0.25,
            features={"mpg": 5.5},
            description="Test",
        )

        success = detector.store_anomaly(anomaly)

        assert success is True
        assert cursor.execute.call_count >= 1

    def test_get_fleet_anomalies(self, detector, mock_db):
        """Test getting fleet-wide anomalies"""
        db, cursor = mock_db

        # Mock trucks
        cursor.fetchall.side_effect = [
            [{"truck_id": "RA9250"}, {"truck_id": "FF7702"}],  # Trucks list
            # Training data for RA9250
            [
                {
                    "mpg_current": 6.5,
                    "fuel_level_pct": 75.0,
                    "idle_pct": 25.0,
                    "speed_avg": 45.0,
                    "fuel_flow_rate": 1.5,
                    "fuel_change_rate": -2.0,
                }
                for _ in range(100)
            ],
            # Check data for RA9250
            [
                {
                    "mpg_current": 6.5,
                    "fuel_level_pct": 75.0,
                    "idle_pct": 25.0,
                    "speed_avg": 45.0,
                    "fuel_flow_rate": 1.5,
                    "fuel_change_rate": -2.0,
                }
            ],
            # Timestamps for RA9250
            [{"timestamp_utc": datetime(2025, 1, 1, 12, 0, 0)}],
            # Training data for FF7702
            [
                {
                    "mpg_current": 5.5,
                    "fuel_level_pct": 65.0,
                    "idle_pct": 30.0,
                    "speed_avg": 40.0,
                    "fuel_flow_rate": 1.8,
                    "fuel_change_rate": -2.5,
                }
                for _ in range(100)
            ],
            # Check data for FF7702
            [
                {
                    "mpg_current": 5.5,
                    "fuel_level_pct": 65.0,
                    "idle_pct": 30.0,
                    "speed_avg": 40.0,
                    "fuel_flow_rate": 1.8,
                    "fuel_change_rate": -2.5,
                }
            ],
            # Timestamps for FF7702
            [{"timestamp_utc": datetime(2025, 1, 1, 13, 0, 0)}],
        ]

        with patch("anomaly_detector.StandardScaler") as mock_scaler, patch(
            "anomaly_detector.IsolationForest"
        ) as mock_forest:

            scaler_instance = MagicMock()
            scaler_instance.transform.return_value = np.zeros((1, 6))
            model_instance = MagicMock()
            model_instance.predict.return_value = np.array([1])  # No anomalies
            model_instance.decision_function.return_value = np.array([0.1])

            mock_scaler.return_value = scaler_instance
            mock_forest.return_value = model_instance

            fleet_anomalies = detector.get_fleet_anomalies(check_period_days=1)

            assert isinstance(fleet_anomalies, dict)


class TestSingleton:
    """Test singleton pattern"""

    def test_get_anomaly_detector_singleton(self):
        """Test that singleton returns same instance"""
        detector1 = get_anomaly_detector()
        detector2 = get_anomaly_detector()

        assert detector1 is detector2


class TestEdgeCases:
    """Test edge cases"""

    def test_extract_features_with_nan_values(self):
        """Test handling NaN values in features"""
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        db.cursor.return_value.__exit__.return_value = False

        # Data with None values
        cursor.fetchall.return_value = [
            {
                "mpg_current": None if i % 2 == 0 else 6.5,
                "fuel_level_pct": 75.0,
                "idle_pct": 25.0,
                "speed_avg": 45.0,
                "fuel_flow_rate": 1.5,
                "fuel_change_rate": -2.0,
            }
            for i in range(100)
        ]

        detector = AnomalyDetector(db_connection=db)
        features = detector.extract_features("RA9250", period_days=7, min_samples=10)

        # Should skip rows with None
        assert features is None or features.shape[0] < 100

    def test_store_anomaly_db_error(self):
        """Test handling database error when storing"""
        db = MagicMock()
        cursor = MagicMock()
        db.cursor.return_value.__enter__.return_value = cursor
        db.cursor.return_value.__exit__.return_value = False

        # Simulate DB error
        cursor.execute.side_effect = Exception("DB Error")

        detector = AnomalyDetector(db_connection=db)

        anomaly = AnomalyDetection(
            truck_id="RA9250",
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            anomaly_type="fuel_theft",
            severity="HIGH",
            anomaly_score=-0.25,
            features={"mpg": 5.5},
            description="Test",
        )

        success = detector.store_anomaly(anomaly)

        assert success is False
