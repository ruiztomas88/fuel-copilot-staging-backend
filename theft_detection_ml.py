"""
ML-Based Theft Detection using Random Forest
═══════════════════════════════════════════════════════════════════════════════

Machine learning model for fuel theft detection that learns from historical
patterns rather than relying solely on heuristics.

Features used:
- fuel_drop_pct: Percentage of fuel lost
- fuel_drop_gal: Absolute gallons lost
- speed: Vehicle speed at time of drop
- time_since_last_refuel: Hours since last refuel
- location_type: Urban/highway/truck stop
- previous_theft_count: Historical theft count for this truck
- drop_duration: How fast the fuel disappeared
- round_number_score: Suspicion score for round fuel levels

Author: Fuel Analytics Team
Version: 1.0.0
Date: December 23, 2025
"""

import logging
import pickle
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

logger = logging.getLogger(__name__)

# Model persistence
MODEL_DIR = Path(__file__).parent / "models"
MODEL_DIR.mkdir(exist_ok=True)
THEFT_MODEL_PATH = MODEL_DIR / "theft_detection_rf.pkl"
SCALER_PATH = MODEL_DIR / "theft_scaler.pkl"


@dataclass
class TheftFeatures:
    """Features for theft detection ML model"""
    fuel_drop_pct: float
    fuel_drop_gal: float
    speed_mph: float
    time_since_last_refuel_hours: float
    location_type: int  # 0=urban, 1=highway, 2=truck_stop, 3=unknown
    previous_theft_count: int
    drop_duration_minutes: float
    round_number_score: float  # 0-100
    
    def to_array(self) -> np.ndarray:
        """Convert to numpy array for model input"""
        return np.array([
            self.fuel_drop_pct,
            self.fuel_drop_gal,
            self.speed_mph,
            self.time_since_last_refuel_hours,
            self.location_type,
            self.previous_theft_count,
            self.drop_duration_minutes,
            self.round_number_score
        ]).reshape(1, -1)


@dataclass
class TheftPrediction:
    """Theft prediction result"""
    is_theft: bool
    confidence: float  # 0.0 to 1.0
    theft_probability: float  # Probability of class 1 (theft)
    features_importance: Dict[str, float]
    method: str = "random_forest_ml"


class TheftDetectionML:
    """
    Machine Learning-based theft detection using Random Forest
    
    Advantages over heuristics:
    - Learns from data patterns
    - Adapts to fleet-specific behavior
    - Can discover non-obvious correlations
    - Provides probability scores
    
    Requires:
    - Labeled training data (confirmed thefts + confirmed non-thefts)
    - At least 100+ examples for good performance
    """
    
    FEATURE_NAMES = [
        "fuel_drop_pct",
        "fuel_drop_gal",
        "speed_mph",
        "time_since_last_refuel_hours",
        "location_type",
        "previous_theft_count",
        "drop_duration_minutes",
        "round_number_score"
    ]
    
    def __init__(self):
        """Initialize ML theft detector"""
        self.model: Optional[RandomForestClassifier] = None
        self.scaler: Optional[StandardScaler] = None
        self.is_trained = False
        self._load_model()
    
    def _load_model(self):
        """Load pre-trained model if available"""
        if THEFT_MODEL_PATH.exists() and SCALER_PATH.exists():
            try:
                with open(THEFT_MODEL_PATH, 'rb') as f:
                    self.model = pickle.load(f)
                with open(SCALER_PATH, 'rb') as f:
                    self.scaler = pickle.load(f)
                self.is_trained = True
                logger.info("✅ Loaded pre-trained theft detection model")
            except Exception as e:
                logger.warning(f"⚠️ Could not load model: {e}")
                self.model = None
                self.scaler = None
    
    def _save_model(self):
        """Save trained model to disk"""
        try:
            with open(THEFT_MODEL_PATH, 'wb') as f:
                pickle.dump(self.model, f)
            with open(SCALER_PATH, 'wb') as f:
                pickle.dump(self.scaler, f)
            logger.info(f"✅ Saved model to {THEFT_MODEL_PATH}")
        except Exception as e:
            logger.error(f"❌ Could not save model: {e}")
    
    def train(
        self,
        X: np.ndarray,
        y: np.ndarray,
        test_size: float = 0.2,
        random_state: int = 42
    ) -> Dict[str, any]:
        """
        Train the Random Forest model
        
        Args:
            X: Feature matrix (n_samples, 8 features)
            y: Labels (0 = not theft, 1 = theft)
            test_size: Fraction of data for testing
            random_state: Random seed for reproducibility
            
        Returns:
            Training metrics dictionary
        """
        if len(X) < 50:
            raise ValueError(
                f"Need at least 50 samples for training, got {len(X)}. "
                "Collect more labeled data (confirmed thefts + non-thefts)"
            )
        
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=y
        )
        
        # Scale features
        self.scaler = StandardScaler()
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)
        
        # Train Random Forest
        self.model = RandomForestClassifier(
            n_estimators=100,  # 100 trees
            max_depth=10,  # Prevent overfitting
            min_samples_split=5,
            min_samples_leaf=2,
            class_weight='balanced',  # Handle imbalanced data (more non-thefts)
            random_state=random_state,
            n_jobs=-1  # Use all CPU cores
        )
        
        self.model.fit(X_train_scaled, y_train)
        self.is_trained = True
        
        # Evaluate
        y_pred = self.model.predict(X_test_scaled)
        y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]
        
        # Metrics
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)
        
        # Feature importance
        feature_importance = dict(zip(
            self.FEATURE_NAMES,
            self.model.feature_importances_
        ))
        
        # Classification report
        report = classification_report(y_test, y_pred, output_dict=True)
        cm = confusion_matrix(y_test, y_pred)
        
        metrics = {
            "train_accuracy": train_score,
            "test_accuracy": test_score,
            "feature_importance": feature_importance,
            "classification_report": report,
            "confusion_matrix": cm.tolist(),
            "n_train_samples": len(X_train),
            "n_test_samples": len(X_test)
        }
        
        # Save model
        self._save_model()
        
        logger.info(
            f"✅ Model trained: train_acc={train_score:.3f}, "
            f"test_acc={test_score:.3f}"
        )
        
        return metrics
    
    def predict(self, features: TheftFeatures) -> TheftPrediction:
        """
        Predict whether a fuel drop is theft
        
        Args:
            features: TheftFeatures dataclass with all required features
            
        Returns:
            TheftPrediction with is_theft, confidence, and probabilities
        """
        if not self.is_trained or self.model is None or self.scaler is None:
            raise RuntimeError(
                "Model not trained. Call train() first or ensure "
                "pre-trained model is available."
            )
        
        # Convert features to array and scale
        X = features.to_array()
        X_scaled = self.scaler.transform(X)
        
        # Predict
        prediction = self.model.predict(X_scaled)[0]
        probabilities = self.model.predict_proba(X_scaled)[0]
        
        theft_probability = probabilities[1]  # Probability of class 1 (theft)
        confidence = max(probabilities)  # Confidence = max probability
        
        # Feature importance for this prediction
        feature_values = X[0]
        feature_importance = {}
        for name, value, importance in zip(
            self.FEATURE_NAMES,
            feature_values,
            self.model.feature_importances_
        ):
            feature_importance[name] = importance
        
        return TheftPrediction(
            is_theft=bool(prediction == 1),
            confidence=float(confidence),
            theft_probability=float(theft_probability),
            features_importance=feature_importance
        )
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance from trained model"""
        if not self.is_trained or self.model is None:
            return {}
        
        return dict(zip(self.FEATURE_NAMES, self.model.feature_importances_))
    
    def predict_batch(
        self,
        features_list: List[TheftFeatures]
    ) -> List[TheftPrediction]:
        """
        Predict multiple samples at once (more efficient)
        
        Args:
            features_list: List of TheftFeatures
            
        Returns:
            List of TheftPrediction
        """
        if not features_list:
            return []
        
        # Convert all features to array
        X = np.vstack([f.to_array() for f in features_list])
        X_scaled = self.scaler.transform(X)
        
        # Predict
        predictions = self.model.predict(X_scaled)
        probabilities = self.model.predict_proba(X_scaled)
        
        # Build results
        results = []
        for i, (pred, prob) in enumerate(zip(predictions, probabilities)):
            theft_prob = prob[1]
            confidence = max(prob)
            
            feature_importance = dict(zip(
                self.FEATURE_NAMES,
                self.model.feature_importances_
            ))
            
            results.append(TheftPrediction(
                is_theft=bool(pred == 1),
                confidence=float(confidence),
                theft_probability=float(theft_prob),
                features_importance=feature_importance
            ))
        
        return results


# Singleton instance
_theft_ml_detector: Optional[TheftDetectionML] = None


def get_theft_ml_detector() -> TheftDetectionML:
    """Get or create singleton ML theft detector"""
    global _theft_ml_detector
    if _theft_ml_detector is None:
        _theft_ml_detector = TheftDetectionML()
    return _theft_ml_detector


def create_synthetic_training_data(n_samples: int = 200) -> Tuple[np.ndarray, np.ndarray]:
    """
    Create synthetic training data for initial model bootstrap
    
    This generates realistic fuel drop scenarios based on heuristics
    to train the initial model. Should be replaced with real labeled
    data as it becomes available.
    
    Args:
        n_samples: Number of samples to generate
        
    Returns:
        (X, y) where X is features matrix and y is labels
    """
    np.random.seed(42)
    
    X = []
    y = []
    
    theft_samples = n_samples // 3  # 33% thefts (imbalanced like real world)
    
    # Generate THEFT examples
    for _ in range(theft_samples):
        fuel_drop_pct = np.random.uniform(15, 50)  # Significant drops
        fuel_drop_gal = np.random.uniform(30, 120)  # Large amounts
        speed = np.random.uniform(0, 8)  # Stopped or very slow
        time_since_refuel = np.random.uniform(2, 48)  # Any time
        location = np.random.choice([0, 2, 3])  # Urban, truck stop, unknown
        previous_thefts = np.random.randint(0, 5)  # Some history
        duration = np.random.uniform(1, 15)  # Quick disappearance
        round_score = np.random.uniform(40, 100)  # Often round numbers
        
        X.append([
            fuel_drop_pct, fuel_drop_gal, speed, time_since_refuel,
            location, previous_thefts, duration, round_score
        ])
        y.append(1)  # Theft
    
    # Generate NON-THEFT examples
    for _ in range(n_samples - theft_samples):
        fuel_drop_pct = np.random.uniform(2, 15)  # Normal consumption
        fuel_drop_gal = np.random.uniform(5, 40)  # Moderate amounts
        speed = np.random.uniform(10, 75)  # Moving
        time_since_refuel = np.random.uniform(0.5, 24)
        location = np.random.choice([0, 1, 2])  # Any location
        previous_thefts = 0  # No history
        duration = np.random.uniform(30, 300)  # Slow, gradual
        round_score = np.random.uniform(0, 40)  # Less likely round
        
        X.append([
            fuel_drop_pct, fuel_drop_gal, speed, time_since_refuel,
            location, previous_thefts, duration, round_score
        ])
        y.append(0)  # Not theft
    
    return np.array(X), np.array(y)
