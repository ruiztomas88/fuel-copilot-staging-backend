"""
LSTM Predictive Maintenance Model
Predicts probability of maintenance issues in next 7, 14, 30 days

Uses TensorFlow/Keras to analyze sensor time series:
- Oil pressure
- Oil temperature
- Coolant temperature
- Engine load
- RPM
- Engine hours

Dec 22 2025 - AI/ML Enhancement
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

try:
    import tensorflow as tf
    from tensorflow import keras
    from tensorflow.keras import layers
    from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint
    from tensorflow.keras.layers import LSTM, Bidirectional, Dense, Dropout
    from tensorflow.keras.models import Sequential, load_model
    from tensorflow.keras.optimizers import Adam

    TENSORFLOW_AVAILABLE = True
    KerasModel = keras.Model
except ImportError:
    TENSORFLOW_AVAILABLE = False
    KerasModel = object  # Fallback type
    logging.warning("⚠️ TensorFlow not available - LSTM model disabled")

logger = logging.getLogger(__name__)


class LSTMMaintenancePredictor:
    """
    LSTM-based predictive maintenance model

    Architecture:
    - Bidirectional LSTM for better pattern recognition
    - Dropout layers for regularization
    - Multi-output: 3 time windows (7d, 14d, 30d)

    Features (5 sensors):
    - oil_pressure
    - oil_temp
    - coolant_temp
    - engine_load
    - rpm

    Training requires:
    - Minimum 6 months historical data
    - Labeled maintenance events
    """

    def __init__(
        self,
        sequence_length: int = 30,  # 30 days of history
        features: int = 5,
        model_path: Optional[str] = None,
    ):
        """
        Initialize LSTM predictor

        Args:
            sequence_length: Number of days to look back
            features: Number of input features (sensors)
            model_path: Path to saved model (if loading existing)
        """
        self.sequence_length = sequence_length
        self.features = features
        self.model = None
        self.scaler = StandardScaler()
        self.model_path = model_path or "models/lstm_maintenance.h5"
        self.scaler_path = "models/lstm_scaler.pkl"

        # Feature names
        self.feature_names = [
            "oil_pressure",
            "oil_temp",
            "coolant_temp",
            "engine_load",
            "rpm",
        ]

        # Output time windows (days ahead)
        self.prediction_windows = [7, 14, 30]

        logger.info(
            f"Initialized LSTM Predictor (seq_length={sequence_length}, features={features})"
        )

    def build_model(self) -> KerasModel:
        """
        Build LSTM architecture

        Returns:
            Compiled Keras model
        """
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow not installed")

        model = Sequential(
            [
                # First Bidirectional LSTM layer
                Bidirectional(
                    LSTM(64, return_sequences=True),
                    input_shape=(self.sequence_length, self.features),
                ),
                Dropout(0.3),
                # Second LSTM layer
                LSTM(32),
                Dropout(0.2),
                # Dense layers
                Dense(16, activation="relu"),
                Dropout(0.2),
                # Output layer: 3 probabilities (7d, 14d, 30d)
                Dense(3, activation="softmax"),
            ]
        )

        # Compile with categorical crossentropy (multi-class)
        model.compile(
            optimizer=Adam(learning_rate=0.001),
            loss="categorical_crossentropy",
            metrics=["accuracy", "AUC"],
        )

        self.model = model
        logger.info("Built LSTM model architecture")
        logger.info(f"Total parameters: {model.count_params():,}")

        return model

    def prepare_sequences(
        self, df: pd.DataFrame, labels: Optional[pd.DataFrame] = None
    ) -> Tuple[np.ndarray, Optional[np.ndarray]]:
        """
        Prepare time series sequences from dataframe

        Args:
            df: DataFrame with columns: timestamp, truck_id, oil_pressure, oil_temp, etc.
            labels: Optional labels (maintenance events) for training

        Returns:
            (X_sequences, y_labels) or (X_sequences, None) if no labels
        """
        # Group by truck
        X_sequences = []
        y_labels = [] if labels is not None else None

        for truck_id in df["truck_id"].unique():
            truck_data = df[df["truck_id"] == truck_id].sort_values("timestamp_utc")

            # Extract features
            features_data = truck_data[self.feature_names].values

            # Normalize
            features_scaled = self.scaler.fit_transform(features_data)

            # Create sequences
            for i in range(len(features_scaled) - self.sequence_length):
                seq = features_scaled[i : i + self.sequence_length]
                X_sequences.append(seq)

                if labels is not None:
                    # Get label for this sequence end date
                    end_date = truck_data.iloc[i + self.sequence_length][
                        "timestamp_utc"
                    ]
                    truck_labels = labels[
                        (labels["truck_id"] == truck_id)
                        & (labels["timestamp_utc"] >= end_date)
                        & (labels["timestamp_utc"] <= end_date + timedelta(days=30))
                    ]

                    # Determine time window (0=none, 1=7d, 2=14d, 3=30d)
                    if len(truck_labels) == 0:
                        label = [1, 0, 0]  # No maintenance needed
                    else:
                        days_until = (
                            truck_labels.iloc[0]["timestamp_utc"] - end_date
                        ).days
                        if days_until <= 7:
                            label = [0, 1, 0]  # Maintenance in 7 days
                        elif days_until <= 14:
                            label = [0, 0, 1]  # Maintenance in 14 days
                        else:
                            label = [0, 0, 1]  # Maintenance in 30 days

                    y_labels.append(label)

        X = np.array(X_sequences)
        y = np.array(y_labels) if y_labels else None

        logger.info(
            f"Prepared {len(X)} sequences from {df['truck_id'].nunique()} trucks"
        )

        return X, y

    def train(
        self,
        X_train: np.ndarray,
        y_train: np.ndarray,
        X_val: Optional[np.ndarray] = None,
        y_val: Optional[np.ndarray] = None,
        epochs: int = 50,
        batch_size: int = 32,
    ) -> Dict:
        """
        Train LSTM model

        Args:
            X_train: Training sequences (n_samples, sequence_length, features)
            y_train: Training labels (n_samples, 3)
            X_val: Validation sequences
            y_val: Validation labels
            epochs: Number of training epochs
            batch_size: Batch size

        Returns:
            Training history dict
        """
        if self.model is None:
            self.build_model()

        # Callbacks
        callbacks = [
            EarlyStopping(
                monitor="val_loss" if X_val is not None else "loss",
                patience=10,
                restore_best_weights=True,
            ),
            ModelCheckpoint(
                self.model_path,
                monitor="val_loss" if X_val is not None else "loss",
                save_best_only=True,
            ),
        ]

        # Train
        validation_data = (X_val, y_val) if X_val is not None else None

        history = self.model.fit(
            X_train,
            y_train,
            validation_data=validation_data,
            epochs=epochs,
            batch_size=batch_size,
            callbacks=callbacks,
            verbose=1,
        )

        # Save scaler
        os.makedirs(os.path.dirname(self.scaler_path), exist_ok=True)
        joblib.dump(self.scaler, self.scaler_path)

        logger.info(f"Model trained and saved to {self.model_path}")
        logger.info(f"Final train loss: {history.history['loss'][-1]:.4f}")
        if X_val is not None:
            logger.info(f"Final val loss: {history.history['val_loss'][-1]:.4f}")

        return history.history

    def predict(self, X: np.ndarray) -> np.ndarray:
        """
        Make predictions

        Args:
            X: Input sequences (n_samples, sequence_length, features)

        Returns:
            Predictions array (n_samples, 3) - probabilities for each time window
        """
        if self.model is None:
            raise ValueError("Model not loaded. Call load_model() or train() first.")

        return self.model.predict(X)

    def predict_truck(self, sensor_data: pd.DataFrame) -> Dict[str, float]:
        """
        Predict maintenance probability for a single truck

        Args:
            sensor_data: Last 30 days of sensor data for truck

        Returns:
            {
                'maintenance_7d_prob': 0.15,
                'maintenance_14d_prob': 0.35,
                'maintenance_30d_prob': 0.50,
                'recommended_action': 'schedule_inspection'
            }
        """
        # Prepare sequence
        features = sensor_data[self.feature_names].values[-self.sequence_length :]

        if len(features) < self.sequence_length:
            logger.warning(
                f"Insufficient data: {len(features)} < {self.sequence_length}"
            )
            return {
                "maintenance_7d_prob": 0.0,
                "maintenance_14d_prob": 0.0,
                "maintenance_30d_prob": 0.0,
                "recommended_action": "insufficient_data",
                "confidence": "low",
            }

        # Scale and reshape
        features_scaled = self.scaler.transform(features)
        X = features_scaled.reshape(1, self.sequence_length, self.features)

        # Predict
        predictions = self.predict(X)[0]

        # Interpret results
        prob_7d = float(predictions[1])
        prob_14d = float(predictions[2])
        prob_30d = float(1 - predictions[0])  # Any maintenance needed

        # Recommendation logic
        if prob_7d > 0.7:
            action = "urgent_maintenance"
            confidence = "high"
        elif prob_14d > 0.6:
            action = "schedule_maintenance"
            confidence = "medium"
        elif prob_30d > 0.5:
            action = "monitor_closely"
            confidence = "medium"
        else:
            action = "normal_operation"
            confidence = "high"

        return {
            "maintenance_7d_prob": round(prob_7d, 3),
            "maintenance_14d_prob": round(prob_14d, 3),
            "maintenance_30d_prob": round(prob_30d, 3),
            "recommended_action": action,
            "confidence": confidence,
        }

    def load_model(self):
        """Load saved model and scaler"""
        if not TENSORFLOW_AVAILABLE:
            raise ImportError("TensorFlow not installed")

        if not os.path.exists(self.model_path):
            logger.warning(f"Model file not found: {self.model_path}")
            return False

        self.model = load_model(self.model_path)

        if os.path.exists(self.scaler_path):
            self.scaler = joblib.load(self.scaler_path)

        logger.info(f"Loaded model from {self.model_path}")
        return True

    def save_model(self):
        """Save model and scaler"""
        if self.model is None:
            raise ValueError("No model to save")

        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        self.model.save(self.model_path)
        joblib.dump(self.scaler, self.scaler_path)

        logger.info(f"Saved model to {self.model_path}")


# Singleton instance
_predictor_instance: Optional[LSTMMaintenancePredictor] = None


def get_maintenance_predictor() -> LSTMMaintenancePredictor:
    """
    Get singleton LSTM predictor instance

    Returns:
        LSTMMaintenancePredictor instance
    """
    global _predictor_instance

    if _predictor_instance is None:
        _predictor_instance = LSTMMaintenancePredictor()

        # Try to load existing model
        try:
            _predictor_instance.load_model()
            logger.info("Loaded existing LSTM model")
        except Exception as e:
            logger.warning(f"Could not load model: {e}")
            logger.info("Model needs to be trained - use /api/ml/train endpoint")

    return _predictor_instance


if __name__ == "__main__":
    # Test model architecture
    print("Testing LSTM Maintenance Predictor...")

    predictor = LSTMMaintenancePredictor()
    model = predictor.build_model()
    model.summary()

    print("\n✅ Model architecture built successfully")
    print(f"Input shape: ({predictor.sequence_length}, {predictor.features})")
    print(f"Output shape: (3,) - probabilities for {predictor.prediction_windows} days")
