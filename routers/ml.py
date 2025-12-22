"""
Machine Learning API Endpoints
LSTM Predictive Maintenance & Isolation Forest Theft Detection

Dec 22 2025 - AI/ML Enhancement
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional

import pandas as pd
import pymysql
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from config import get_local_db_config
from ml_models.lstm_maintenance import get_maintenance_predictor, TENSORFLOW_AVAILABLE
from ml_models.theft_detection import get_theft_detector

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/fuelAnalytics/api/ml", tags=["Machine Learning"])


# ═══════════════════════════════════════════════════════════════════════════════
# REQUEST/RESPONSE MODELS
# ═══════════════════════════════════════════════════════════════════════════════

class MaintenancePrediction(BaseModel):
    """Predictive maintenance result for a truck"""
    truck_id: str
    timestamp: datetime
    maintenance_7d_prob: float = Field(description="Probability of maintenance needed in 7 days")
    maintenance_14d_prob: float = Field(description="Probability of maintenance needed in 14 days")
    maintenance_30d_prob: float = Field(description="Probability of maintenance needed in 30 days")
    recommended_action: str = Field(description="Suggested action: urgent_maintenance, schedule_maintenance, monitor_closely, normal_operation")
    confidence: str = Field(description="Prediction confidence: low, medium, high")


class TheftPrediction(BaseModel):
    """Theft detection result for a fuel drop event"""
    event_id: Optional[int] = None
    truck_id: str
    timestamp: datetime
    fuel_drop_gal: float
    is_theft: bool
    confidence: float = Field(description="Detection confidence 0.0-1.0")
    anomaly_score: float = Field(description="Anomaly score from Isolation Forest")
    risk_level: str = Field(description="Risk level: low, medium, high, critical")
    explanation: str = Field(description="Human-readable explanation")


class MLTrainingRequest(BaseModel):
    """Request to train ML model"""
    model_type: str = Field(description="lstm_maintenance or theft_detection")
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    min_samples: int = Field(default=1000, description="Minimum samples required for training")


class MLTrainingResponse(BaseModel):
    """Training result"""
    model_type: str
    status: str
    samples_used: int
    metrics: Dict
    message: str


# ═══════════════════════════════════════════════════════════════════════════════
# LSTM MAINTENANCE ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/maintenance/predict/{truck_id}", response_model=MaintenancePrediction)
async def predict_maintenance(
    truck_id: str,
    days_history: int = Query(default=30, ge=7, le=90, description="Days of history to analyze")
):
    """
    Predict maintenance probability for a truck using LSTM
    
    Analyzes last N days of sensor data to predict likelihood of
    maintenance issues in next 7, 14, and 30 days.
    
    Returns action recommendations:
    - urgent_maintenance: >70% probability in 7 days - act immediately
    - schedule_maintenance: >60% probability in 14 days - schedule soon  
    - monitor_closely: >50% probability in 30 days - watch sensors
    - normal_operation: <50% probability - continue normal ops
    """
    if not TENSORFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="TensorFlow not installed - LSTM model unavailable"
        )
    
    try:
        # Get predictor
        predictor = get_maintenance_predictor()
        
        # Fetch sensor data from database
        conn = pymysql.connect(**get_local_db_config())
        
        query = """
            SELECT 
                timestamp_utc,
                truck_id,
                oil_pressure,
                oil_temp,
                coolant_temp_f as coolant_temp,
                engine_hours,
                rpm
            FROM truck_sensors_cache
            WHERE truck_id = %s
                AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s DAY)
            ORDER BY timestamp_utc DESC
            LIMIT 1000
        """
        
        df = pd.read_sql(query, conn, params=[truck_id, days_history])
        conn.close()
        
        if len(df) < predictor.sequence_length:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient data: need {predictor.sequence_length} days, got {len(df)} records"
            )
        
        # Make prediction
        result = predictor.predict_truck(df)
        
        return MaintenancePrediction(
            truck_id=truck_id,
            timestamp=datetime.now(),
            **result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting maintenance for {truck_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/maintenance/fleet-predictions", response_model=List[MaintenancePrediction])
async def predict_fleet_maintenance(
    top_n: int = Query(default=10, ge=1, le=50, description="Number of highest-risk trucks to return")
):
    """
    Predict maintenance for entire fleet, return top N highest-risk trucks
    
    Useful for maintenance planning and resource allocation.
    Returns trucks sorted by 7-day maintenance probability (highest first).
    """
    if not TENSORFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="TensorFlow not installed - LSTM model unavailable"
        )
    
    try:
        predictor = get_maintenance_predictor()
        
        # Get all active trucks
        conn = pymysql.connect(**get_local_db_config())
        
        # Get trucks with recent data
        trucks_query = """
            SELECT DISTINCT truck_id
            FROM truck_sensors_cache
            WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL 1 DAY)
        """
        
        trucks_df = pd.read_sql(trucks_query, conn)
        truck_ids = trucks_df['truck_id'].tolist()
        
        predictions = []
        
        for truck_id in truck_ids:
            try:
                # Get sensor data
                query = """
                    SELECT 
                        timestamp_utc,
                        truck_id,
                        oil_pressure,
                        oil_temp,
                        coolant_temp_f as coolant_temp,
                        engine_hours,
                        rpm
                    FROM truck_sensors_cache
                    WHERE truck_id = %s
                        AND timestamp_utc >= DATE_SUB(NOW(), INTERVAL 30 DAY)
                    ORDER BY timestamp_utc DESC
                    LIMIT 1000
                """
                
                df = pd.read_sql(query, conn, params=[truck_id])
                
                if len(df) >= predictor.sequence_length:
                    result = predictor.predict_truck(df)
                    predictions.append(
                        MaintenancePrediction(
                            truck_id=truck_id,
                            timestamp=datetime.now(),
                            **result
                        )
                    )
            except Exception as e:
                logger.warning(f"Skipping {truck_id}: {e}")
                continue
        
        conn.close()
        
        # Sort by 7-day probability (highest risk first)
        predictions.sort(key=lambda x: x.maintenance_7d_prob, reverse=True)
        
        return predictions[:top_n]
        
    except Exception as e:
        logger.error(f"Error predicting fleet maintenance: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# THEFT DETECTION ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/theft/predict", response_model=TheftPrediction)
async def predict_theft(event: Dict):
    """
    Predict theft probability for a fuel drop event using Isolation Forest
    
    Request body should contain:
    - truck_id: str
    - timestamp_utc: datetime
    - fuel_drop_gal: float
    - sat_count: int (optional)
    - hdop: float (optional)
    - latitude: float (optional)
    - longitude: float (optional)
    - truck_status: str (optional)
    - speed_mph: float (optional)
    
    Returns theft prediction with confidence and explanation.
    """
    try:
        detector = get_theft_detector()
        
        # Validate required fields
        if 'truck_id' not in event or 'fuel_drop_gal' not in event:
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: truck_id, fuel_drop_gal"
            )
        
        # Make prediction
        result = detector.predict_single(event)
        
        return TheftPrediction(
            truck_id=event['truck_id'],
            timestamp=pd.to_datetime(event.get('timestamp_utc', datetime.now())),
            fuel_drop_gal=event['fuel_drop_gal'],
            **result
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting theft: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/theft/recent-predictions", response_model=List[TheftPrediction])
async def get_recent_theft_predictions(
    hours: int = Query(default=24, ge=1, le=168, description="Hours to look back"),
    min_confidence: float = Query(default=0.5, ge=0.0, le=1.0, description="Minimum confidence threshold")
):
    """
    Get recent fuel drops analyzed by theft detection model
    
    Returns all theft events detected in last N hours with confidence >= threshold.
    Useful for security dashboard and alert monitoring.
    """
    try:
        detector = get_theft_detector()
        conn = pymysql.connect(**get_local_db_config())
        
        # Get recent theft events from database
        query = """
            SELECT 
                id as event_id,
                truck_id,
                timestamp_utc,
                gallons_lost as fuel_drop_gal,
                detection_method,
                location_lat as latitude,
                location_lon as longitude,
                gps_quality as sat_count
            FROM theft_events
            WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s HOUR)
            ORDER BY timestamp_utc DESC
        """
        
        df = pd.read_sql(query, conn, params=[hours])
        conn.close()
        
        if len(df) == 0:
            return []
        
        # Make predictions
        predictions, scores = detector.predict(df)
        
        results = []
        for idx, row in df.iterrows():
            is_theft = predictions[idx] == -1
            score = scores[idx]
            
            # Map score to confidence
            if score < -0.3:
                confidence = 0.95
                risk_level = 'critical'
            elif score < -0.1:
                confidence = 0.80
                risk_level = 'high'
            elif score < 0.1:
                confidence = 0.60
                risk_level = 'medium'
            else:
                confidence = 0.30
                risk_level = 'low'
            
            if confidence >= min_confidence:
                results.append(
                    TheftPrediction(
                        event_id=int(row['event_id']),
                        truck_id=row['truck_id'],
                        timestamp=row['timestamp_utc'],
                        fuel_drop_gal=row['fuel_drop_gal'],
                        is_theft=bool(is_theft),
                        confidence=round(confidence, 2),
                        anomaly_score=round(float(score), 3),
                        risk_level=risk_level,
                        explanation=detector._generate_explanation(row.to_dict(), score)
                    )
                )
        
        return results
        
    except Exception as e:
        logger.error(f"Error getting theft predictions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# MODEL TRAINING ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@router.post("/train", response_model=MLTrainingResponse)
async def train_model(request: MLTrainingRequest):
    """
    Train ML model on historical data
    
    model_type options:
    - lstm_maintenance: Predictive maintenance model
    - theft_detection: Anomaly detection for theft
    
    Requires sufficient historical data (default: 1000+ samples).
    Training may take several minutes.
    """
    try:
        if request.model_type == "lstm_maintenance":
            return await _train_lstm(request)
        elif request.model_type == "theft_detection":
            return await _train_theft_detector(request)
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown model_type: {request.model_type}"
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error training model: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


async def _train_lstm(request: MLTrainingRequest) -> MLTrainingResponse:
    """Train LSTM maintenance model"""
    if not TENSORFLOW_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="TensorFlow not installed"
        )
    
    predictor = get_maintenance_predictor()
    conn = pymysql.connect(**get_local_db_config())
    
    # Fetch training data
    # TODO: Implement actual training data query with maintenance labels
    # For now, return placeholder
    
    return MLTrainingResponse(
        model_type="lstm_maintenance",
        status="training_not_implemented",
        samples_used=0,
        metrics={},
        message="LSTM training requires labeled maintenance events data - not yet implemented"
    )


async def _train_theft_detector(request: MLTrainingRequest) -> MLTrainingResponse:
    """Train theft detection model"""
    detector = get_theft_detector()
    conn = pymysql.connect(**get_local_db_config())
    
    # Fetch historical theft events
    query = """
        SELECT 
            truck_id,
            timestamp_utc,
            gallons_lost as fuel_drop_gal,
            TIMESTAMPDIFF(MINUTE, start_time, end_time) as duration_minutes,
            location_lat as latitude,
            location_lon as longitude,
            gps_quality as sat_count,
            1.5 as hdop,
            'STOPPED' as truck_status,
            0 as speed_mph
        FROM theft_events
        WHERE timestamp_utc >= %s
        ORDER BY timestamp_utc DESC
        LIMIT 10000
    """
    
    start_date = request.start_date or (datetime.now() - timedelta(days=180)).strftime('%Y-%m-%d')
    
    df = pd.read_sql(query, conn, params=[start_date])
    conn.close()
    
    if len(df) < request.min_samples:
        raise HTTPException(
            status_code=400,
            detail=f"Insufficient data: {len(df)} samples (need {request.min_samples})"
        )
    
    # Train model
    stats = detector.train(df)
    
    return MLTrainingResponse(
        model_type="theft_detection",
        status="success",
        samples_used=stats['total_samples'],
        metrics={
            'anomaly_rate': stats['anomaly_rate'],
            'detected_anomalies': stats['detected_anomalies'],
            'model_path': stats['model_saved']
        },
        message=f"Model trained successfully on {stats['total_samples']} samples"
    )


@router.get("/status")
async def get_ml_status():
    """
    Get ML models status and availability
    
    Returns information about which models are loaded and ready to use.
    """
    status = {
        'tensorflow_available': TENSORFLOW_AVAILABLE,
        'models': {}
    }
    
    # Check LSTM model
    try:
        predictor = get_maintenance_predictor()
        status['models']['lstm_maintenance'] = {
            'loaded': predictor.model is not None,
            'sequence_length': predictor.sequence_length,
            'features': predictor.features,
            'model_path': predictor.model_path
        }
    except Exception as e:
        status['models']['lstm_maintenance'] = {
            'loaded': False,
            'error': str(e)
        }
    
    # Check theft detector
    try:
        detector = get_theft_detector()
        status['models']['theft_detection'] = {
            'loaded': detector.model is not None,
            'contamination': detector.contamination,
            'model_path': detector.model_path
        }
    except Exception as e:
        status['models']['theft_detection'] = {
            'loaded': False,
            'error': str(e)
        }
    
    return status
