#!/usr/bin/env python3
"""
Train ML Models Script
Trains LSTM maintenance predictor and Isolation Forest theft detector on historical data

Usage:
    python scripts/train_models.py --model all
    python scripts/train_models.py --model lstm
    python scripts/train_models.py --model theft
"""
import argparse
import sys
import os
from datetime import datetime, timedelta
import pandas as pd
import pymysql

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_local_db_config
from ml_models.lstm_maintenance import get_maintenance_predictor
from ml_models.theft_detection import get_theft_detector


def fetch_lstm_training_data(days=90):
    """
    Fetch sensor data for LSTM training
    
    Args:
        days: Number of days of historical data
    
    Returns:
        pd.DataFrame with sensor readings
    """
    print(f"📊 Fetching LSTM training data ({days} days)...")
    
    conn = pymysql.connect(**get_local_db_config())
    
    try:
        query = """
        SELECT 
            timestamp_utc,
            oil_pressure,
            oil_temp,
            coolant_temp,
            engine_load,
            rpm
        FROM truck_sensors_cache
        WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s DAY)
            AND oil_pressure IS NOT NULL
            AND oil_temp IS NOT NULL
            AND coolant_temp IS NOT NULL
            AND engine_load IS NOT NULL
            AND rpm IS NOT NULL
        ORDER BY timestamp_utc ASC
        """
        
        with conn.cursor() as cursor:
            cursor.execute(query, (days,))
            rows = cursor.fetchall()
        
        if not rows:
            print("⚠️  No sensor data found in database")
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=[
            'timestamp_utc', 'oil_pressure', 'oil_temp', 
            'coolant_temp', 'engine_load', 'rpm'
        ])
        
        print(f"✅ Fetched {len(df):,} sensor readings")
        return df
    
    finally:
        conn.close()


def fetch_theft_training_data(days=180):
    """
    Fetch theft event data for Isolation Forest training
    
    Args:
        days: Number of days of historical data
    
    Returns:
        pd.DataFrame with theft events
    """
    print(f"📊 Fetching theft detection training data ({days} days)...")
    
    conn = pymysql.connect(**get_local_db_config())
    
    try:
        query = """
        SELECT 
            truck_id,
            timestamp_utc,
            fuel_drop_gal,
            duration_minutes,
            sat_count,
            hdop,
            latitude,
            longitude,
            truck_status,
            speed_mph
        FROM theft_events
        WHERE timestamp_utc >= DATE_SUB(NOW(), INTERVAL %s DAY)
            AND fuel_drop_gal IS NOT NULL
        ORDER BY timestamp_utc ASC
        """
        
        with conn.cursor() as cursor:
            cursor.execute(query, (days,))
            rows = cursor.fetchall()
        
        if not rows:
            print("⚠️  No theft event data found in database")
            return pd.DataFrame()
        
        df = pd.DataFrame(rows, columns=[
            'truck_id', 'timestamp_utc', 'fuel_drop_gal', 'duration_minutes',
            'sat_count', 'hdop', 'latitude', 'longitude', 'truck_status', 'speed_mph'
        ])
        
        print(f"✅ Fetched {len(df):,} theft events")
        return df
    
    finally:
        conn.close()


def train_lstm_model(epochs=50, batch_size=32):
    """
    Train LSTM maintenance predictor
    
    Args:
        epochs: Training epochs
        batch_size: Batch size for training
    """
    print("\n" + "="*70)
    print("🧠 TRAINING LSTM MAINTENANCE PREDICTOR")
    print("="*70)
    
    # Fetch data
    df = fetch_lstm_training_data(days=90)
    
    if df.empty:
        print("❌ Cannot train LSTM: No data available")
        return False
    
    # Initialize predictor
    predictor = get_maintenance_predictor()
    
    # Create synthetic labels (in production, use real maintenance events)
    print("\n⚠️  NOTE: Using synthetic labels for training")
    print("   In production, fetch real maintenance event labels from database")
    
    # For demo: Create labels based on sensor thresholds
    # 0 = no maintenance, 1 = maintenance in 7-14 days, 2 = maintenance in 30 days
    labels = []
    for _, row in df.iterrows():
        if row['oil_pressure'] > 55 or row['oil_temp'] > 215:
            labels.append(2)  # High risk
        elif row['oil_pressure'] > 50 or row['oil_temp'] > 210:
            labels.append(1)  # Medium risk
        else:
            labels.append(0)  # Low risk
    
    df['maintenance_label'] = labels
    
    try:
        # Train model
        print(f"\n🏋️  Training LSTM model...")
        print(f"   Samples: {len(df):,}")
        print(f"   Epochs: {epochs}")
        print(f"   Batch size: {batch_size}")
        
        history = predictor.train(
            df, 
            epochs=epochs, 
            batch_size=batch_size,
            validation_split=0.2
        )
        
        # Print training summary
        print("\n📈 Training Summary:")
        print(f"   Final loss: {history.history['loss'][-1]:.4f}")
        print(f"   Final accuracy: {history.history['accuracy'][-1]:.4f}")
        if 'val_accuracy' in history.history:
            print(f"   Final val_accuracy: {history.history['val_accuracy'][-1]:.4f}")
        
        # Save model
        predictor.save_model()
        print("\n💾 LSTM model saved successfully")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Error training LSTM model: {e}")
        import traceback
        traceback.print_exc()
        return False


def train_theft_model(contamination=0.05):
    """
    Train Isolation Forest theft detector
    
    Args:
        contamination: Expected proportion of anomalies (0.05 = 5%)
    """
    print("\n" + "="*70)
    print("🕵️  TRAINING ISOLATION FOREST THEFT DETECTOR")
    print("="*70)
    
    # Fetch data
    df = fetch_theft_training_data(days=180)
    
    if df.empty:
        print("❌ Cannot train Isolation Forest: No data available")
        return False
    
    # Initialize detector
    detector = get_theft_detector(contamination=contamination)
    
    try:
        # Train model
        print(f"\n🏋️  Training Isolation Forest...")
        print(f"   Samples: {len(df):,}")
        print(f"   Expected anomaly rate: {contamination*100:.1f}%")
        
        stats = detector.train(df)
        
        # Print training summary
        print("\n📈 Training Summary:")
        print(f"   Total samples: {stats['total_samples']:,}")
        print(f"   Detected anomalies: {stats['detected_anomalies']:,}")
        print(f"   Normal events: {stats['normal_events']:,}")
        print(f"   Actual anomaly rate: {stats['anomaly_rate']*100:.1f}%")
        
        # Save model
        detector.save_model()
        print("\n💾 Isolation Forest model saved successfully")
        
        return True
    
    except Exception as e:
        print(f"\n❌ Error training Isolation Forest: {e}")
        import traceback
        traceback.print_exc()
        return False


def validate_models():
    """
    Validate trained models by making test predictions
    """
    print("\n" + "="*70)
    print("✅ VALIDATING TRAINED MODELS")
    print("="*70)
    
    # Validate LSTM
    print("\n1️⃣  Validating LSTM Maintenance Predictor...")
    try:
        predictor = get_maintenance_predictor()
        
        if predictor.load_model():
            # Create test data (30 days of normal readings)
            test_data = pd.DataFrame({
                'timestamp_utc': pd.date_range(start='2025-12-01', periods=30, freq='D'),
                'oil_pressure': [45.0] * 30,
                'oil_temp': [200.0] * 30,
                'coolant_temp': [190.0] * 30,
                'engine_load': [60.0] * 30,
                'rpm': [1500] * 30,
            })
            
            result = predictor.predict_truck(test_data)
            print(f"   ✅ LSTM model loaded and validated")
            print(f"   Test prediction: {result['recommended_action']}")
        else:
            print("   ⚠️  LSTM model not found - needs training")
    
    except Exception as e:
        print(f"   ❌ LSTM validation failed: {e}")
    
    # Validate Isolation Forest
    print("\n2️⃣  Validating Isolation Forest Theft Detector...")
    try:
        detector = get_theft_detector()
        
        if detector.load_model():
            # Create test event (normal refuel)
            test_event = {
                'fuel_drop_gal': 12.0,
                'timestamp_utc': '2025-12-22 14:00:00',
                'duration_minutes': 10,
                'sat_count': 12,
                'hdop': 1.0,
                'latitude': 34.05,
                'longitude': -118.25,
                'truck_status': 'STOPPED',
                'speed_mph': 0
            }
            
            result = detector.predict_single(test_event)
            print(f"   ✅ Isolation Forest model loaded and validated")
            print(f"   Test prediction: {result['risk_level']} (confidence: {result['confidence']:.2f})")
        else:
            print("   ⚠️  Isolation Forest model not found - needs training")
    
    except Exception as e:
        print(f"   ❌ Isolation Forest validation failed: {e}")


def main():
    """Main training script"""
    parser = argparse.ArgumentParser(description='Train ML models for fuel analytics')
    parser.add_argument(
        '--model', 
        type=str, 
        choices=['all', 'lstm', 'theft'],
        default='all',
        help='Which model to train (default: all)'
    )
    parser.add_argument(
        '--epochs',
        type=int,
        default=50,
        help='Number of training epochs for LSTM (default: 50)'
    )
    parser.add_argument(
        '--contamination',
        type=float,
        default=0.05,
        help='Contamination rate for Isolation Forest (default: 0.05)'
    )
    parser.add_argument(
        '--validate-only',
        action='store_true',
        help='Only validate existing models without training'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("🚀 ML MODEL TRAINING SCRIPT")
    print("="*70)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Model: {args.model}")
    
    if args.validate_only:
        validate_models()
        return
    
    success_count = 0
    total_count = 0
    
    # Train LSTM
    if args.model in ['all', 'lstm']:
        total_count += 1
        if train_lstm_model(epochs=args.epochs):
            success_count += 1
    
    # Train Isolation Forest
    if args.model in ['all', 'theft']:
        total_count += 1
        if train_theft_model(contamination=args.contamination):
            success_count += 1
    
    # Validate all models
    validate_models()
    
    # Final summary
    print("\n" + "="*70)
    print("📊 TRAINING COMPLETE")
    print("="*70)
    print(f"✅ Successfully trained: {success_count}/{total_count} models")
    
    if success_count == total_count:
        print("\n🎉 All models trained successfully!")
        print("\nNext steps:")
        print("1. Restart the backend server to load new models")
        print("2. Test predictions via API endpoints:")
        print("   - GET /fuelAnalytics/api/ml/maintenance/predict/{truck_id}")
        print("   - POST /fuelAnalytics/api/ml/theft/predict")
        print("3. Monitor model performance and retrain as needed")
    else:
        print("\n⚠️  Some models failed to train. Check errors above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
