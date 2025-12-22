"""
Unit Tests for ML API Router
pytest tests/test_ml_router.py
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock
import pandas as pd
from datetime import datetime, timedelta

from main import app
from routers.ml import router


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def mock_db_connection():
    """Mock database connection"""
    with patch('routers.ml.pymysql.connect') as mock_connect:
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        yield mock_cursor


@pytest.fixture
def sample_sensor_data():
    """Sample sensor data for LSTM"""
    dates = pd.date_range(start='2025-11-01', periods=60, freq='D')
    return pd.DataFrame({
        'timestamp_utc': dates,
        'oil_pressure': [45.0 + i * 0.1 for i in range(60)],
        'oil_temp': [200.0 + i * 0.2 for i in range(60)],
        'coolant_temp': [190.0 + i * 0.1 for i in range(60)],
        'engine_load': [60.0 + i * 0.15 for i in range(60)],
        'rpm': [1500 + i * 2 for i in range(60)],
    })


class TestMaintenancePredictionEndpoints:
    """Test LSTM maintenance prediction endpoints"""
    
    @patch('routers.ml.get_maintenance_predictor')
    def test_predict_maintenance_success(self, mock_predictor, client, mock_db_connection):
        """Test single truck maintenance prediction - success"""
        # Mock database response
        mock_db_connection.fetchall.return_value = [
            ('2025-12-01 10:00:00', 45.0, 200.0, 190.0, 60.0, 1500),
            ('2025-12-02 10:00:00', 45.5, 200.5, 190.2, 60.5, 1510),
            # ... more rows (simulate 60 days)
        ] * 30  # 60 rows total
        
        # Mock predictor
        mock_instance = Mock()
        mock_instance.predict_truck.return_value = {
            'maintenance_7d_prob': 0.75,
            'maintenance_14d_prob': 0.45,
            'maintenance_30d_prob': 0.20,
            'recommended_action': 'urgent_maintenance',
            'confidence': 'high'
        }
        mock_predictor.return_value = mock_instance
        
        # Make request
        response = client.get('/fuelAnalytics/api/ml/maintenance/predict/DO9693')
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data['truck_id'] == 'DO9693'
        assert 'timestamp' in data
        assert 0 <= data['maintenance_7d_prob'] <= 1
        assert 0 <= data['maintenance_14d_prob'] <= 1
        assert 0 <= data['maintenance_30d_prob'] <= 1
        assert data['recommended_action'] == 'urgent_maintenance'
        assert data['confidence'] == 'high'
    
    @patch('routers.ml.get_maintenance_predictor')
    def test_predict_maintenance_insufficient_data(self, mock_predictor, client, mock_db_connection):
        """Test prediction with insufficient data"""
        # Mock database response with < 30 rows
        mock_db_connection.fetchall.return_value = [
            ('2025-12-01 10:00:00', 45.0, 200.0, 190.0, 60.0, 1500),
        ] * 10  # Only 10 rows
        
        # Mock predictor
        mock_instance = Mock()
        mock_instance.predict_truck.return_value = {
            'maintenance_7d_prob': 0.0,
            'maintenance_14d_prob': 0.0,
            'maintenance_30d_prob': 0.0,
            'recommended_action': 'insufficient_data',
            'confidence': 'low'
        }
        mock_predictor.return_value = mock_instance
        
        # Make request
        response = client.get('/fuelAnalytics/api/ml/maintenance/predict/TEST001')
        
        # Should still return 200 but with insufficient_data action
        assert response.status_code == 200
        data = response.json()
        assert data['recommended_action'] == 'insufficient_data'
    
    @patch('routers.ml.get_maintenance_predictor')
    def test_predict_fleet_maintenance(self, mock_predictor, client, mock_db_connection):
        """Test fleet-wide predictions"""
        # Mock database response for multiple trucks
        mock_db_connection.fetchall.side_effect = [
            # First query: get all trucks
            [('DO9693',), ('LH1141',), ('FF7702',)],
            # Subsequent queries: sensor data for each truck
            [('2025-12-01', 45.0, 200.0, 190.0, 60.0, 1500)] * 60,
            [('2025-12-01', 46.0, 201.0, 191.0, 61.0, 1505)] * 60,
            [('2025-12-01', 44.0, 199.0, 189.0, 59.0, 1495)] * 60,
        ]
        
        # Mock predictor
        mock_instance = Mock()
        mock_instance.predict_truck.side_effect = [
            {'maintenance_7d_prob': 0.85, 'maintenance_14d_prob': 0.60, 'maintenance_30d_prob': 0.30, 'recommended_action': 'urgent_maintenance', 'confidence': 'high'},
            {'maintenance_7d_prob': 0.15, 'maintenance_14d_prob': 0.10, 'maintenance_30d_prob': 0.05, 'recommended_action': 'normal_operation', 'confidence': 'medium'},
            {'maintenance_7d_prob': 0.50, 'maintenance_14d_prob': 0.35, 'maintenance_30d_prob': 0.15, 'recommended_action': 'schedule_maintenance', 'confidence': 'high'},
        ]
        mock_predictor.return_value = mock_instance
        
        # Make request
        response = client.get('/fuelAnalytics/api/ml/maintenance/fleet-predictions?top_n=3')
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 3
        
        # Should be sorted by 7d probability (highest first)
        if len(data) > 1:
            assert data[0]['maintenance_7d_prob'] >= data[1]['maintenance_7d_prob']


class TestTheftDetectionEndpoints:
    """Test Isolation Forest theft detection endpoints"""
    
    @patch('routers.ml.get_theft_detector')
    def test_predict_theft_normal_event(self, mock_detector, client):
        """Test theft prediction - normal refuel"""
        # Mock detector
        mock_instance = Mock()
        mock_instance.predict_single.return_value = {
            'is_theft': False,
            'confidence': 0.85,
            'anomaly_score': 0.15,
            'risk_level': 'low',
            'explanation': 'Normal refuel pattern'
        }
        mock_detector.return_value = mock_instance
        
        # Make request
        event_data = {
            'fuel_drop_gal': 12.5,
            'timestamp_utc': '2025-12-22 14:00:00',
            'duration_minutes': 10,
            'sat_count': 12,
            'hdop': 1.0,
            'latitude': 34.05,
            'longitude': -118.25,
            'truck_status': 'STOPPED',
            'speed_mph': 0
        }
        
        response = client.post('/fuelAnalytics/api/ml/theft/predict', json=event_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data['is_theft'] == False
        assert data['risk_level'] == 'low'
        assert 0 <= data['confidence'] <= 1
        assert 'explanation' in data
    
    @patch('routers.ml.get_theft_detector')
    def test_predict_theft_suspicious_event(self, mock_detector, client):
        """Test theft prediction - suspicious event"""
        # Mock detector
        mock_instance = Mock()
        mock_instance.predict_single.return_value = {
            'is_theft': True,
            'confidence': 0.92,
            'anomaly_score': -0.45,
            'risk_level': 'critical',
            'explanation': 'Large fuel drop (35 gal) during unusual time (23:30), poor GPS quality'
        }
        mock_detector.return_value = mock_instance
        
        # Make request
        event_data = {
            'fuel_drop_gal': 35.0,
            'timestamp_utc': '2025-12-22 23:30:00',
            'duration_minutes': 3,
            'sat_count': 3,
            'hdop': 4.0,
            'latitude': 34.15,
            'longitude': -118.35,
            'truck_status': 'MOVING',
            'speed_mph': 50
        }
        
        response = client.post('/fuelAnalytics/api/ml/theft/predict', json=event_data)
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data['is_theft'] == True
        assert data['risk_level'] in ['high', 'critical']
        assert data['confidence'] > 0.8
    
    @patch('routers.ml.get_theft_detector')
    def test_recent_theft_predictions(self, mock_detector, client, mock_db_connection):
        """Test recent theft predictions endpoint"""
        # Mock database response
        mock_db_connection.fetchall.return_value = [
            ('DO9693', '2025-12-22 10:00:00', 32.5, 4, 12, 1.0, 34.05, -118.25, 'STOPPED', 0),
            ('LH1141', '2025-12-22 11:00:00', 28.0, 3, 4, 3.5, 34.10, -118.30, 'MOVING', 45),
            ('FF7702', '2025-12-22 12:00:00', 15.0, 8, 14, 0.9, 34.06, -118.26, 'STOPPED', 0),
        ]
        
        # Mock detector
        mock_instance = Mock()
        mock_instance.predict_single.side_effect = [
            {'is_theft': True, 'confidence': 0.88, 'anomaly_score': -0.35, 'risk_level': 'high', 'explanation': 'Suspicious pattern'},
            {'is_theft': True, 'confidence': 0.95, 'anomaly_score': -0.50, 'risk_level': 'critical', 'explanation': 'Very suspicious'},
            {'is_theft': False, 'confidence': 0.70, 'anomaly_score': 0.10, 'risk_level': 'medium', 'explanation': 'Borderline normal'},
        ]
        mock_detector.return_value = mock_instance
        
        # Make request
        response = client.get('/fuelAnalytics/api/ml/theft/recent-predictions?hours=24&min_confidence=0.5')
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert isinstance(data, list)
        assert len(data) <= 100  # Default limit
        
        # All should meet confidence threshold
        for event in data:
            assert event['confidence'] >= 0.5


class TestTrainingEndpoint:
    """Test model training endpoint"""
    
    @patch('routers.ml.get_maintenance_predictor')
    @patch('routers.ml.get_theft_detector')
    def test_train_both_models(self, mock_theft_detector, mock_maintenance_predictor, client, mock_db_connection):
        """Test training both models"""
        # Mock database responses
        mock_db_connection.fetchall.side_effect = [
            # LSTM training data
            [('2025-01-01', 45.0, 200.0, 190.0, 60.0, 1500)] * 1000,
            # Theft training data
            [('DO9693', '2025-01-01', 30.0, 5, 12, 1.0, 34.05, -118.25, 'STOPPED', 0)] * 500,
        ]
        
        # Mock predictors
        mock_lstm = Mock()
        mock_lstm.train.return_value = None
        mock_maintenance_predictor.return_value = mock_lstm
        
        mock_theft = Mock()
        mock_theft.train.return_value = {
            'total_samples': 500,
            'detected_anomalies': 25,
            'normal_events': 475,
            'anomaly_rate': 0.05
        }
        mock_theft_detector.return_value = mock_theft
        
        # Make request
        response = client.post('/fuelAnalytics/api/ml/train', json={'model': 'all'})
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'success'
        assert 'timestamp' in data
        assert 'models_trained' in data
        assert 'lstm' in data['models_trained'] or 'isolation_forest' in data['models_trained']
    
    def test_train_invalid_model(self, client):
        """Test training with invalid model name"""
        response = client.post('/fuelAnalytics/api/ml/train', json={'model': 'invalid_model'})
        
        # Should accept but warn in response
        assert response.status_code in [200, 400]


class TestStatusEndpoint:
    """Test ML system status endpoint"""
    
    @patch('routers.ml.get_maintenance_predictor')
    @patch('routers.ml.get_theft_detector')
    def test_status_models_loaded(self, mock_theft_detector, mock_maintenance_predictor, client):
        """Test status when models are loaded"""
        # Mock predictors
        mock_lstm = Mock()
        mock_lstm.model = Mock()  # Model loaded
        mock_maintenance_predictor.return_value = mock_lstm
        
        mock_theft = Mock()
        mock_theft.model = Mock()  # Model loaded
        mock_theft_detector.return_value = mock_theft
        
        # Make request
        response = client.get('/fuelAnalytics/api/ml/status')
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] in ['ready', 'partial', 'not_ready']
        assert 'lstm_loaded' in data
        assert 'isolation_forest_loaded' in data
        assert 'timestamp' in data
    
    @patch('routers.ml.get_maintenance_predictor')
    @patch('routers.ml.get_theft_detector')
    def test_status_models_not_loaded(self, mock_theft_detector, mock_maintenance_predictor, client):
        """Test status when models are not loaded"""
        # Mock predictors
        mock_lstm = Mock()
        mock_lstm.model = None  # Not loaded
        mock_maintenance_predictor.return_value = mock_lstm
        
        mock_theft = Mock()
        mock_theft.model = None  # Not loaded
        mock_theft_detector.return_value = mock_theft
        
        # Make request
        response = client.get('/fuelAnalytics/api/ml/status')
        
        # Validate response
        assert response.status_code == 200
        data = response.json()
        
        assert data['status'] == 'not_ready'
        assert data['lstm_loaded'] == False
        assert data['isolation_forest_loaded'] == False


class TestErrorHandling:
    """Test error handling scenarios"""
    
    @patch('routers.ml.pymysql.connect')
    def test_database_connection_error(self, mock_connect, client):
        """Test database connection failure"""
        mock_connect.side_effect = Exception("Database connection failed")
        
        response = client.get('/fuelAnalytics/api/ml/maintenance/predict/DO9693')
        
        # Should return 500 or 503
        assert response.status_code in [500, 503]
    
    @patch('routers.ml.get_maintenance_predictor')
    def test_model_prediction_error(self, mock_predictor, client, mock_db_connection):
        """Test model prediction failure"""
        # Mock database response
        mock_db_connection.fetchall.return_value = [
            ('2025-12-01', 45.0, 200.0, 190.0, 60.0, 1500)
        ] * 60
        
        # Mock predictor to raise error
        mock_instance = Mock()
        mock_instance.predict_truck.side_effect = ValueError("Model not loaded")
        mock_predictor.return_value = mock_instance
        
        response = client.get('/fuelAnalytics/api/ml/maintenance/predict/DO9693')
        
        # Should return error
        assert response.status_code in [400, 500, 503]


if __name__ == "__main__":
    pytest.main([__file__, '-v'])
