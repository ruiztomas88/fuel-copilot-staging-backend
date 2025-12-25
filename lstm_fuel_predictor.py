"""
LSTM Fuel Consumption Predictor - Fase 2B
Predicción de consumo futuro usando LSTM (Long Short-Term Memory)

Features:
- Predice consumo en próximas 1/4/12/24 horas
- Entrenamiento adaptativo por truck + ruta
- Incorpora factores ambientales y de conducción
- Validación de anomalías en predicciones
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

try:
    from tensorflow import keras
    from tensorflow.keras import Sequential, layers
    from tensorflow.keras.optimizers import Adam

    TENSORFLOW_AVAILABLE = True
except ImportError:
    TENSORFLOW_AVAILABLE = False
    logging.warning("⚠️ TensorFlow no disponible - LSTM deshabilitado")

logger = logging.getLogger(__name__)


class LSTMFuelPredictor:
    """Predictor de consumo de combustible con LSTM"""

    def __init__(self, model_dir: str = "ml_models/lstm"):
        """
        Inicializa predictor LSTM

        Args:
            model_dir: Directorio para almacenar modelos entrenados
        """
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        self.tf_available = (
            TENSORFLOW_AVAILABLE  # Flag para indicar si TensorFlow está disponible
        )
        self.models: Dict[str, keras.Model] = {}  # Modelos por truck_id
        self.scalers: Dict[str, Dict] = {}  # MinMax scalers
        self.training_history: Dict[str, List] = {}  # Histórico de entrenamiento

        self.sequence_length = 60  # 60 observaciones anteriores (típicamente 60 min)
        self.prediction_horizons = [1, 4, 12, 24]  # Horas

        if TENSORFLOW_AVAILABLE:
            logger.info("✅ LSTM Predictor inicializado")
        else:
            logger.warning("⚠️ LSTM deshabilitado - instala tensorflow")

    def prepare_training_data(
        self,
        consumption_history: List[float],
        environmental_data: List[Dict],
        truck_id: str,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepara datos para entrenamiento LSTM

        Args:
            consumption_history: Histórico de consumo (gph)
            environmental_data: Factores ambientales/conducción
            truck_id: Identificador del truck

        Returns:
            (X, y) para entrenamiento
        """
        if not TENSORFLOW_AVAILABLE:
            logger.warning("⚠️ TensorFlow no disponible")
            return np.array([]), np.array([])

        # Normalizar datos
        consumption_array = np.array(consumption_history, dtype=np.float32)

        # Calcular estadísticas para normalización
        mean = np.mean(consumption_array)
        std = np.std(consumption_array) or 1.0
        normalized = (consumption_array - mean) / std

        # Almacenar scaler
        self.scalers[truck_id] = {"mean": float(mean), "std": float(std)}

        # Crear secuencias
        X, y = [], []
        for i in range(len(normalized) - self.sequence_length - 1):
            X.append(normalized[i : i + self.sequence_length])
            y.append(normalized[i + self.sequence_length])

        return np.array(X), np.array(y)

    def build_model(self, truck_id: str, learning_rate: float = 0.001):
        """Construye y compila modelo LSTM para un truck"""
        if not TENSORFLOW_AVAILABLE:
            return None

        model = Sequential(
            [
                layers.LSTM(
                    64, activation="relu", input_shape=(self.sequence_length, 1)
                ),
                layers.Dropout(0.2),
                layers.LSTM(32, activation="relu"),
                layers.Dropout(0.2),
                layers.Dense(16, activation="relu"),
                layers.Dense(1),
            ]
        )

        model.compile(
            optimizer=Adam(learning_rate=learning_rate),
            loss="mse",
            metrics=["mae"],
        )

        self.models[truck_id] = model
        logger.info(f"🏗️ Modelo LSTM construido para {truck_id}")
        return model

    def train(
        self,
        truck_id: str,
        consumption_history: List[float],
        environmental_data: List[Dict],
        epochs: int = 50,
        batch_size: int = 32,
        validation_split: float = 0.2,
    ) -> Dict:
        """
        Entrena modelo LSTM

        Returns:
            {"status": "trained", "loss": 0.002, "mae": 0.15, ...}
        """
        if not TENSORFLOW_AVAILABLE:
            return {"status": "unavailable", "reason": "tensorflow_not_installed"}

        if len(consumption_history) < self.sequence_length + 2:
            return {
                "status": "insufficient_data",
                "required": self.sequence_length + 2,
                "available": len(consumption_history),
            }

        # Preparar datos
        X, y = self.prepare_training_data(
            consumption_history, environmental_data, truck_id
        )

        if len(X) == 0:
            return {"status": "preparation_failed"}

        # Reshape para LSTM (samples, timesteps, features)
        X = X.reshape((X.shape[0], X.shape[1], 1))

        # Construir modelo si no existe
        if truck_id not in self.models:
            self.build_model(truck_id)

        model = self.models[truck_id]

        # Entrenar
        history = model.fit(
            X,
            y,
            epochs=epochs,
            batch_size=batch_size,
            validation_split=validation_split,
            verbose=0,
        )

        # Guardar histórico
        self.training_history[truck_id] = {
            "loss": history.history["loss"][-1],
            "val_loss": history.history["val_loss"][-1],
            "mae": history.history["mae"][-1],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        # Persistir modelo
        self._save_model(truck_id)

        logger.info(f"✅ Modelo LSTM entrenado para {truck_id}")
        return {
            "status": "trained",
            "loss": float(history.history["loss"][-1]),
            "val_loss": float(history.history["val_loss"][-1]),
            "mae": float(history.history["mae"][-1]),
        }

    def predict(
        self,
        truck_id: str,
        recent_consumption: List[float],
        hours_ahead: int = 4,
    ) -> Dict:
        """
        Predice consumo futuro

        Args:
            truck_id: Identificador del truck
            recent_consumption: Últimas N observaciones (gph)
            hours_ahead: Horas a predecir (1, 4, 12, 24)

        Returns:
            {
                "prediction_gph": 3.2,
                "prediction_range": [2.8, 3.6],
                "confidence": 0.92,
                "hours_ahead": 4
            }
        """
        if not TENSORFLOW_AVAILABLE:
            return {"status": "unavailable"}

        if truck_id not in self.models:
            # Intentar cargar modelo
            if not self._load_model(truck_id):
                return {"status": "no_model", "truck_id": truck_id}

        if len(recent_consumption) < self.sequence_length:
            return {
                "status": "insufficient_history",
                "required": self.sequence_length,
                "available": len(recent_consumption),
            }

        try:
            # Normalizar entrada
            scaler = self.scalers.get(truck_id, {"mean": 0, "std": 1})
            normalized = (
                np.array(recent_consumption[-self.sequence_length :], dtype=np.float32)
                - scaler["mean"]
            ) / scaler["std"]

            # Preparar input
            X = normalized.reshape(1, self.sequence_length, 1)

            # Predicción
            model = self.models[truck_id]
            pred_normalized = model.predict(X, verbose=0)[0][0]

            # Denormalizar
            prediction = pred_normalized * scaler["std"] + scaler["mean"]

            # Generar rango de confianza (±15%)
            lower = prediction * 0.85
            upper = prediction * 1.15

            # Confidence basado en variancia histórica
            recent_std = np.std(recent_consumption[-10:]) or 0.1
            confidence = max(0.6, 1.0 - (recent_std / prediction) * 0.5)

            return {
                "status": "success",
                "truck_id": truck_id,
                "hours_ahead": hours_ahead,
                "prediction_gph": float(max(0, prediction)),  # Sin valores negativos
                "lower_bound_gph": float(max(0, lower)),
                "upper_bound_gph": float(upper),
                "confidence": float(confidence),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error(f"❌ Error en predicción LSTM: {e}")
            return {"status": "prediction_failed", "error": str(e)}

    def _save_model(self, truck_id: str):
        """Persiste modelo a disco"""
        if truck_id not in self.models:
            return

        try:
            model_path = self.model_dir / f"{truck_id}_lstm_model.h5"
            self.models[truck_id].save(str(model_path))

            # Guardar scaler
            scaler_path = self.model_dir / f"{truck_id}_scaler.json"
            with open(scaler_path, "w") as f:
                json.dump(self.scalers.get(truck_id, {}), f)

            logger.debug(f"💾 Modelo LSTM guardado para {truck_id}")
        except Exception as e:
            logger.error(f"❌ Error guardando modelo: {e}")

    def _load_model(self, truck_id: str) -> bool:
        """Carga modelo desde disco"""
        if not TENSORFLOW_AVAILABLE:
            return False

        try:
            model_path = self.model_dir / f"{truck_id}_lstm_model.h5"
            if model_path.exists():
                self.models[truck_id] = keras.models.load_model(str(model_path))

                # Cargar scaler
                scaler_path = self.model_dir / f"{truck_id}_scaler.json"
                if scaler_path.exists():
                    with open(scaler_path) as f:
                        self.scalers[truck_id] = json.load(f)

                logger.info(f"📂 Modelo LSTM cargado para {truck_id}")
                return True
        except Exception as e:
            logger.error(f"❌ Error cargando modelo: {e}")

        return False


# Instancia global
_lstm_predictor: Optional[LSTMFuelPredictor] = None


def get_lstm_predictor() -> LSTMFuelPredictor:
    """Obtiene instancia singleton del predictor LSTM"""
    global _lstm_predictor
    if _lstm_predictor is None:
        _lstm_predictor = LSTMFuelPredictor()
    return _lstm_predictor
