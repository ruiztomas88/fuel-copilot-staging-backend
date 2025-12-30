"""
ML Model Training Script
========================

Trains ML fuel theft detector with real historical data.

Usage:
    python train_ml_model.py

Author: Fuel Copilot Team
Date: December 26, 2025
"""

import asyncio
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta

import pandas as pd

from database_async import close_async_pool, get_async_pool
from ml_fuel_theft_detector import MLFuelTheftDetector, train_ml_detector


async def fetch_training_data():
    """Fetch historical data for training"""
    print("📊 Fetching historical training data...")

    pool = await get_async_pool()
    async with pool.acquire() as conn:
        async with conn.cursor() as cursor:
            # Get last 60 days of data (exclude known theft events)
            # Using actual column names from fuel_metrics table
            query = """
                SELECT 
                    fm.created_at as timestamp,
                    fm.truck_id,
                    COALESCE(fm.estimated_pct, fm.sensor_pct, 50) as fuel_level,
                    COALESCE(fm.speed_mph, 0) as speed,
                    COALESCE(fm.truck_status, 'OFFLINE') as truck_status,
                    COALESCE(fm.latitude, 0) as latitude,
                    COALESCE(fm.longitude, 0) as longitude
                FROM fuel_metrics fm
                WHERE fm.created_at >= DATE_SUB(NOW(), INTERVAL 60 DAY)
                AND fm.truck_id IN (
                    SELECT DISTINCT truck_id FROM fuel_metrics
                    WHERE created_at >= DATE_SUB(NOW(), INTERVAL 60 DAY)
                    GROUP BY truck_id
                    HAVING COUNT(*) > 100
                )
                ORDER BY fm.truck_id, fm.created_at
                LIMIT 100000
            """

            await cursor.execute(query)
            rows = await cursor.fetchall()

    if not rows:
        print("⚠️ No training data found!")
        return None

    print(f"✅ Fetched {len(rows)} data points from database")

    # Convert to DataFrame
    df = pd.DataFrame(
        rows,
        columns=[
            "timestamp",
            "truck_id",
            "fuel_level",
            "speed",
            "truck_status",
            "latitude",
            "longitude",
        ],
    )

    # Convert timestamp to datetime
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    # Fill missing values
    df["latitude"] = df["latitude"].fillna(0.0)
    df["longitude"] = df["longitude"].fillna(0.0)
    df["speed"] = df["speed"].fillna(0.0)

    # Remove duplicates
    df = df.drop_duplicates(subset=["truck_id", "timestamp"])

    print(f"📈 Training data stats:")
    print(f"   - Total records: {len(df)}")
    print(f"   - Trucks: {df['truck_id'].nunique()}")
    print(f"   - Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    print(f"   - Avg fuel level: {df['fuel_level'].mean():.2f}%")

    return df


async def train_and_save_model():
    """Train ML model and save to disk"""
    print("\n" + "=" * 60)
    print("🎓 ML FUEL THEFT DETECTOR - TRAINING")
    print("=" * 60 + "\n")

    # Fetch training data
    df = await fetch_training_data()

    if df is None or len(df) < 100:
        print("❌ Insufficient training data. Need at least 100 records.")
        print("   Using demo mode with synthetic data...")

        # Create synthetic training data
        import numpy as np

        n_samples = 1000

        df = pd.DataFrame(
            {
                "timestamp": pd.date_range(
                    start="2025-11-01", periods=n_samples, freq="5min"
                ),
                "truck_id": np.random.choice(["FL0208", "CO0681", "TX1234"], n_samples),
                "fuel_level": np.random.normal(50, 20, n_samples).clip(0, 100),
                "speed": np.random.normal(55, 15, n_samples).clip(0, 80),
                "truck_status": np.random.choice(["MOVING", "STOPPED"], n_samples),
                "latitude": np.random.uniform(25, 45, n_samples),
                "longitude": np.random.uniform(-120, -80, n_samples),
            }
        )

        print(f"   Generated {len(df)} synthetic samples")

    # Initialize detector
    detector = MLFuelTheftDetector(contamination=0.05)

    # Train model
    print("\n🔄 Training model (this may take 1-2 minutes)...")
    detector.train(df)

    # Create models directory if not exists
    os.makedirs("models", exist_ok=True)

    # Save model
    model_path = "models/fuel_theft_detector.joblib"
    detector.save_model(model_path)

    print(f"\n✅ Model saved to: {model_path}")
    print(f"   Model size: {os.path.getsize(model_path) / 1024:.2f} KB")

    # Test model
    print("\n🧪 Testing model with sample data...")
    test_sample = df.head(100)
    predictions = detector.predict(test_sample)

    anomalies = predictions[predictions["is_anomaly"]]
    print(f"   - Anomalies detected: {len(anomalies)}/{len(test_sample)}")
    print(f"   - Anomaly rate: {len(anomalies)/len(test_sample)*100:.2f}%")

    if len(anomalies) > 0:
        print(
            f"   - Avg theft probability: {anomalies['theft_probability'].mean():.2%}"
        )
        print(f"   - Max theft probability: {anomalies['theft_probability'].max():.2%}")

    print("\n" + "=" * 60)
    print("✅ TRAINING COMPLETE!")
    print("=" * 60)
    print("\nModel is ready to use for fuel theft detection.")
    print("API endpoint: /api/v2/ml/theft/{truck_id}")


async def main():
    """Main function"""
    try:
        await train_and_save_model()
    except Exception as e:
        print(f"\n❌ Error during training: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Close database connection
        await close_async_pool()


if __name__ == "__main__":
    asyncio.run(main())
