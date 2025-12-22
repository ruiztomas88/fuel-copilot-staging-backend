"""
Unit Tests for LSTM Predictive Maintenance Model
pytest tests/test_lstm_maintenance.py
"""
import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta

from ml_models.lstm_maintenance import LSTMMaintenancePredictor, get_maintenance_predictor, TENSORFLOW_AVAILABLE


@pytest.fixture
def sample_sensor_data():
    """Create sample sensor data for testing"""
    dates = pd.date_range(start='2025-01-01', periods=40, freq='D')
    
    data = {
        'timestamp_utc': dates,
        'truck_id': ['DO9693'] * 40,
        'oil_pressure': np.random.uniform(30, 60, 40),
        'oil_temp': np.random.uniform(180, 220, 40),
        'coolant_temp': np.random.uniform(180, 200, 40),
        'engine_load': np.random.uniform(40, 80, 40),
        'rpm': np.random.uniform(1200, 1800, 40),
    }
    
    return pd.DataFrame(data)


@pytest.fixture
def predictor():
    """Create predictor instance"""
    return LSTMMaintenancePredictor(sequence_length=30, features=5)


class TestLSTMMaintenancePredictor:
    """Test LSTM maintenance predictor"""
    
    def test_init(self, predictor):
        """Test initialization"""
        assert predictor.sequence_length == 30
        assert predictor.features == 5
        assert len(predictor.feature_names) == 5
        assert len(predictor.prediction_windows) == 3
    
    @pytest.mark.skipif(not TENSORFLOW_AVAILABLE, reason="TensorFlow not installed")
    def test_build_model(self, predictor):
        """Test model architecture creation"""
        model = predictor.build_model()
        
        assert model is not None
        assert predictor.model is not None
        
        # Check input shape
        assert model.input_shape == (None, 30, 5)
        
        # Check output shape
        assert model.output_shape == (None, 3)
        
        # Check model compiled
        assert model.optimizer is not None
    
    def test_prepare_sequences(self, predictor, sample_sensor_data):
        """Test sequence preparation"""
        X, y = predictor.prepare_sequences(sample_sensor_data)
        
        # Should create sequences of length 30
        assert X.shape[1] == 30
        assert X.shape[2] == 5
        
        # Should have multiple sequences
        assert X.shape[0] > 0
    
    def test_predict_truck_insufficient_data(self, predictor):
        """Test prediction with insufficient data"""
        # Only 10 days of data (need 30)
        dates = pd.date_range(start='2025-01-01', periods=10, freq='D')
        data = pd.DataFrame({
            'timestamp_utc': dates,
            'truck_id': ['DO9693'] * 10,
            'oil_pressure': [50] * 10,
            'oil_temp': [200] * 10,
            'coolant_temp': [190] * 10,
            'engine_load': [60] * 10,
            'rpm': [1500] * 10,
        })
        
        result = predictor.predict_truck(data)
        
        assert result['recommended_action'] == 'insufficient_data'
        assert result['confidence'] == 'low'
    
    @pytest.mark.skipif(not TENSORFLOW_AVAILABLE, reason="TensorFlow not installed")
    def test_predict_truck_with_model(self, predictor, sample_sensor_data):
        """Test prediction with trained model"""
        # Build and compile model
        predictor.build_model()
        
        # Mock train model (just initialize weights)
        # In real scenario, model would be trained on historical data
        
        result = predictor.predict_truck(sample_sensor_data)
        
        # Should return valid prediction structure
        assert 'maintenance_7d_prob' in result
        assert 'maintenance_14d_prob' in result
        assert 'maintenance_30d_prob' in result
        assert 'recommended_action' in result
        assert 'confidence' in result
        
        # Probabilities should be between 0 and 1
        assert 0 <= result['maintenance_7d_prob'] <= 1
        assert 0 <= result['maintenance_14d_prob'] <= 1
        assert 0 <= result['maintenance_30d_prob'] <= 1
        
        # Action should be valid
        valid_actions = ['urgent_maintenance', 'schedule_maintenance', 'monitor_closely', 'normal_operation']
        assert result['recommended_action'] in valid_actions
    
    def test_singleton_instance(self):
        """Test singleton pattern works"""
        instance1 = get_maintenance_predictor()
        instance2 = get_maintenance_predictor()
        
        assert instance1 is instance2


class TestModelIntegration:
    """Integration tests for LSTM model"""
    
    @pytest.mark.skipif(not TENSORFLOW_AVAILABLE, reason="TensorFlow not installed")
    def test_full_training_pipeline(self, predictor, sample_sensor_data):
        """Test complete training pipeline"""
        # Prepare data
        X, _ = predictor.prepare_sequences(sample_sensor_data)
        
        # Create dummy labels
        y = np.random.randint(0, 2, (X.shape[0], 3))
        y = y / y.sum(axis=1, keepdims=True)  # Normalize to probabilities
        
        # Build model
        predictor.build_model()
        
        # Train for 1 epoch (quick test)
        history = predictor.train(X, y, epochs=1, batch_size=4)
        
        assert 'loss' in history
        assert len(history['loss']) == 1
        
        # Model should be able to predict
        predictions = predictor.predict(X[:5])
        assert predictions.shape == (5, 3)
        
        # Predictions should sum to 1 (softmax output)
        assert np.allclose(predictions.sum(axis=1), 1.0)


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_dataframe(self, predictor):
        """Test with empty dataframe"""
        empty_df = pd.DataFrame()
        
        with pytest.raises(KeyError):
            predictor.prepare_sequences(empty_df)
    
    def test_missing_features(self, predictor):
        """Test with missing feature columns"""
        dates = pd.date_range(start='2025-01-01', periods=40, freq='D')
        data = pd.DataFrame({
            'timestamp_utc': dates,
            'truck_id': ['DO9693'] * 40,
            # Missing other features
        })
        
        with pytest.raises(KeyError):
            predictor.prepare_sequences(data)
    
    @pytest.mark.skipif(not TENSORFLOW_AVAILABLE, reason="TensorFlow not installed")
    def test_predict_before_model_loaded(self, predictor):
        """Test prediction before model is loaded"""
        X = np.random.rand(5, 30, 5)
        
        with pytest.raises(ValueError, match="Model not loaded"):
            predictor.predict(X)


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
