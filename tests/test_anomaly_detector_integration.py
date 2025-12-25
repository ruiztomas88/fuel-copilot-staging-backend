"""
Integration tests for Anomaly Detector
Tests with real database (fuel_copilot_local)
"""

import os
import time
from datetime import datetime

import numpy as np
import pymysql
import pytest
from pymysql.cursors import DictCursor

from anomaly_detector import AnomalyDetector, get_anomaly_detector


@pytest.fixture(scope="module")
def db_connection():
    """Get real database connection"""
    try:
        conn = pymysql.connect(
            host=os.getenv("MYSQL_HOST", "localhost"),
            user=os.getenv("MYSQL_USER", "root"),
            password=os.getenv("MYSQL_PASSWORD", ""),
            database=os.getenv("MYSQL_DATABASE", "fuel_copilot_local"),
            port=int(os.getenv("MYSQL_PORT", "3306")),
            charset="utf8mb4",
            autocommit=True,
            cursorclass=DictCursor,
        )

        # Verify database
        with conn.cursor() as cursor:
            cursor.execute("SELECT DATABASE()")
            db_name = cursor.fetchone()["DATABASE()"]

        if db_name != "fuel_copilot_local":
            conn.close()
            pytest.skip(
                f"Integration tests require fuel_copilot_local (connected to {db_name})"
            )

        yield conn
        conn.close()
    except Exception as e:
        pytest.skip(f"Could not connect to fuel_copilot_local: {e}")


@pytest.fixture(scope="module")
def detector(db_connection):
    """Create detector with real DB"""
    return AnomalyDetector(db_connection=db_connection)


@pytest.fixture(scope="module")
def sample_truck_id(db_connection):
    """Get a truck with sufficient data"""
    with db_connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT truck_id
            FROM fuel_metrics
            WHERE mpg_current IS NOT NULL
              AND mpg_current > 0
            GROUP BY truck_id
            HAVING COUNT(*) >= 100
            ORDER BY COUNT(*) DESC
            LIMIT 1
        """
        )
        result = cursor.fetchone()

    if not result:
        pytest.skip("No trucks with sufficient data")

    return result["truck_id"]


class TestAnomalyDetectorIntegration:
    """Integration tests with real database"""

    def test_extract_features_real_data(self, detector, sample_truck_id):
        """Test extracting features from real data"""
        features = detector.extract_features(
            sample_truck_id, period_days=7, min_samples=50
        )

        if features is None:
            pytest.skip(f"Insufficient data for {sample_truck_id}")

        assert features.shape[1] == 6  # 6 features
        assert features.shape[0] >= 50  # At least 50 samples

        # Check feature ranges are reasonable
        mpg_values = features[:, 0]
        assert np.all(mpg_values > 0)
        assert np.all(mpg_values < 15)  # Heavy trucks max MPG

        fuel_level_values = features[:, 1]
        assert np.all(fuel_level_values >= 0)
        assert np.all(fuel_level_values <= 100)

        print(
            f"\n✓ Extracted {features.shape[0]} feature vectors for {sample_truck_id}"
        )
        print(f"  - MPG range: {mpg_values.min():.2f} - {mpg_values.max():.2f}")
        print(
            f"  - Fuel level range: {fuel_level_values.min():.1f}% - {fuel_level_values.max():.1f}%"
        )

    def test_train_model_real_data(self, detector, sample_truck_id):
        """Test training model with real data"""
        start_time = time.time()
        success = detector.train_model(sample_truck_id, period_days=7)
        elapsed = time.time() - start_time

        if not success:
            pytest.skip(f"Could not train model for {sample_truck_id}")

        assert sample_truck_id in detector.models
        assert sample_truck_id in detector.scalers

        # Performance check
        assert elapsed < 5.0, f"Training too slow: {elapsed:.2f}s"

        print(f"\n✓ Trained model for {sample_truck_id} in {elapsed:.2f}s")

    def test_detect_anomalies_real_data(self, detector, sample_truck_id):
        """Test detecting anomalies in real data"""
        # Train model first
        detector.train_model(sample_truck_id, period_days=7)

        # Detect anomalies
        start_time = time.time()
        anomalies = detector.detect_anomalies(sample_truck_id, check_period_days=1)
        elapsed = time.time() - start_time

        assert isinstance(anomalies, list)
        assert elapsed < 2.0, f"Detection too slow: {elapsed:.2f}s"

        if len(anomalies) > 0:
            print(f"\n✓ Detected {len(anomalies)} anomalies for {sample_truck_id}:")
            for i, anomaly in enumerate(anomalies[:5], 1):  # Show top 5
                print(f"\n  {i}. {anomaly.anomaly_type.upper()}")
                print(f"     - Severity: {anomaly.severity}")
                print(f"     - Score: {anomaly.anomaly_score:.3f}")
                print(f"     - {anomaly.description}")
        else:
            print(f"\n✓ No anomalies detected for {sample_truck_id} (good!)")

    def test_anomaly_classification_real(self, detector, sample_truck_id):
        """Test that anomaly classification works correctly"""
        # Train and detect
        detector.train_model(sample_truck_id, period_days=7)
        anomalies = detector.detect_anomalies(sample_truck_id, check_period_days=2)

        if len(anomalies) == 0:
            pytest.skip("No anomalies detected to classify")

        # Check classification
        valid_types = {"fuel_theft", "sensor_malfunction", "unusual_consumption"}
        valid_severities = {"LOW", "MEDIUM", "HIGH", "CRITICAL"}

        for anomaly in anomalies:
            assert anomaly.anomaly_type in valid_types
            assert anomaly.severity in valid_severities
            assert -1.0 <= anomaly.anomaly_score <= 1.0
            assert len(anomaly.description) > 0

        print(f"\n✓ All {len(anomalies)} anomalies properly classified")

    def test_store_and_retrieve_anomaly(self, detector, sample_truck_id, db_connection):
        """Test storing anomaly in database"""
        from anomaly_detector import AnomalyDetection

        # Create test anomaly
        anomaly = AnomalyDetection(
            truck_id=sample_truck_id,
            timestamp=datetime(2025, 1, 1, 12, 0, 0),
            anomaly_type="fuel_theft",
            severity="HIGH",
            anomaly_score=-0.25,
            features={"mpg": 5.5, "fuel_level_pct": 45.2},
            description="Integration test anomaly",
        )

        # Store it
        success = detector.store_anomaly(anomaly)
        assert success is True

        # Verify table exists
        with db_connection.cursor() as cursor:
            cursor.execute("SHOW TABLES LIKE 'anomaly_detections'")
            result = cursor.fetchone()

        assert result is not None

        # Verify data was stored
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM anomaly_detections
                WHERE truck_id = %s
                  AND description = 'Integration test anomaly'
                ORDER BY created_at DESC
                LIMIT 1
            """,
                (sample_truck_id,),
            )

            stored = cursor.fetchone()

        assert stored is not None
        assert stored["anomaly_type"] == "fuel_theft"
        assert stored["severity"] == "HIGH"

        print(f"\n✓ Anomaly stored and retrieved from database")

    def test_get_fleet_anomalies_real(self, detector, db_connection):
        """Test getting anomalies for entire fleet"""
        # Get truck count
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT COUNT(DISTINCT truck_id) as count
                FROM fuel_metrics
                WHERE timestamp_utc > DATE_SUB(NOW(), INTERVAL 1 DAY)
            """
            )
            truck_count = cursor.fetchone()["count"]

        if truck_count == 0:
            pytest.skip("No recent truck data")

        # Get fleet anomalies
        start_time = time.time()
        fleet_anomalies = detector.get_fleet_anomalies(
            check_period_days=1, min_severity="MEDIUM"
        )
        elapsed = time.time() - start_time

        assert isinstance(fleet_anomalies, dict)

        # Performance check (should process multiple trucks reasonably fast)
        avg_time = elapsed / max(truck_count, 1)
        assert avg_time < 3.0, f"Fleet processing too slow: {avg_time:.2f}s per truck"

        total_anomalies = sum(len(anomalies) for anomalies in fleet_anomalies.values())

        print(f"\n✓ Processed {truck_count} trucks in {elapsed:.2f}s")
        print(f"  - Average: {avg_time:.2f}s per truck")
        print(f"  - Trucks with anomalies: {len(fleet_anomalies)}")
        print(f"  - Total anomalies (MEDIUM+): {total_anomalies}")

    def test_singleton_instance(self):
        """Test singleton pattern"""
        detector1 = get_anomaly_detector()
        detector2 = get_anomaly_detector()

        assert detector1 is detector2
        print("\n✓ Singleton pattern working")

    def test_model_persistence(self, detector, sample_truck_id):
        """Test that trained models persist in detector instance"""
        # Train model
        detector.train_model(sample_truck_id, period_days=7)

        # Detect without retraining
        anomalies1 = detector.detect_anomalies(
            sample_truck_id, check_period_days=1, retrain=False
        )

        # Should use cached model
        assert sample_truck_id in detector.models

        print(f"\n✓ Model persistence working for {sample_truck_id}")

    def test_performance_benchmark(self, detector, db_connection):
        """Benchmark performance on real data"""
        # Get 3 sample trucks
        with db_connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT truck_id
                FROM fuel_metrics
                GROUP BY truck_id
                HAVING COUNT(*) >= 100
                ORDER BY COUNT(*) DESC
                LIMIT 3
            """
            )
            trucks = [row["truck_id"] for row in cursor.fetchall()]

        if len(trucks) == 0:
            pytest.skip("No trucks with sufficient data")

        # Benchmark training
        train_times = []
        for truck_id in trucks:
            start = time.time()
            detector.train_model(truck_id, period_days=7)
            train_times.append(time.time() - start)

        # Benchmark detection
        detect_times = []
        for truck_id in trucks:
            start = time.time()
            detector.detect_anomalies(truck_id, check_period_days=1)
            detect_times.append(time.time() - start)

        avg_train = np.mean(train_times)
        avg_detect = np.mean(detect_times)

        print(f"\n✓ Performance Benchmark ({len(trucks)} trucks):")
        print(f"  - Training: {avg_train:.2f}s average")
        print(f"  - Detection: {avg_detect:.2f}s average")

        # Performance assertions
        assert avg_train < 5.0, "Training too slow"
        assert avg_detect < 2.0, "Detection too slow"


class TestErrorHandling:
    """Test error handling in integration scenarios"""

    def test_invalid_truck_id(self, detector):
        """Test handling invalid truck ID"""
        features = detector.extract_features("INVALID_TRUCK_999", period_days=7)

        assert features is None
        print("\n✓ Invalid truck ID handled gracefully")

    def test_train_insufficient_data(self, detector):
        """Test training with insufficient data"""
        success = detector.train_model("TRUCK_NO_DATA", period_days=1)

        assert success is False
        assert "TRUCK_NO_DATA" not in detector.models
        print("\n✓ Insufficient training data handled")

    def test_detect_without_model(self, detector):
        """Test detection when model doesn't exist"""
        # Clear any existing models
        if "NEW_TRUCK" in detector.models:
            del detector.models["NEW_TRUCK"]

        # Should auto-train or return empty
        anomalies = detector.detect_anomalies("NEW_TRUCK", check_period_days=1)

        assert isinstance(anomalies, list)
        print("\n✓ Detection without pre-trained model handled")
